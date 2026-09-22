[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $WinSWPath,
    [string] $RepositoryPath = 'C:\Services\kk-pricewatch-collector',
    [string] $Python = 'py',
    [string] $DataPath = 'C:\ProgramData\KKPriceWatchCollector',
    [string] $ProtectedTokenFile,
    [switch] $RecreateVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run this script from an elevated PowerShell session.'
    }
}

function Test-UserScopedPath {
    param([Parameter(Mandatory)] [string] $Path)

    $fullPath = [IO.Path]::GetFullPath($Path)
    $profileRoots = @($env:USERPROFILE, (Join-Path $env:SystemDrive 'Users'))
    foreach ($root in $profileRoots) {
        if ([string]::IsNullOrWhiteSpace($root)) { continue }
        $fullRoot = [IO.Path]::GetFullPath($root).TrimEnd('\', '/')
        if ($fullPath.Equals($fullRoot, [StringComparison]::OrdinalIgnoreCase) -or
            $fullPath.StartsWith("$fullRoot\", [StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Assert-ServiceCompatiblePython {
    param(
        [Parameter(Mandatory)] [string] $Executable,
        [string] $Context = 'Selected Python installation'
    )

    $resolved = [IO.Path]::GetFullPath($Executable)
    if (Test-UserScopedPath -Path $resolved) {
        throw "$Context is user-scoped and cannot be used by LocalService. " +
            "Detected base runtime: $resolved. Install Python 3.12+ for all users and " +
            'provide its executable path with -Python.'
    }
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "$Context base runtime does not exist or is inaccessible: $resolved"
    }
    return $resolved
}

function Resolve-PythonRuntime {
    param(
        [Parameter(Mandatory)] [string] $Command,
        [string] $Context = 'Selected Python installation'
    )

    try {
        $runtimeJson = & $Command -c (
            'import json, sys; print(json.dumps({' +
            '"executable": sys.executable, ' +
            '"base_executable": getattr(sys, "_base_executable", sys.executable), ' +
            '"version": list(sys.version_info[:3])}))'
        )
    } catch {
        throw "Unable to run the Python command '$Command': $($_.Exception.Message)"
    }
    if ($LASTEXITCODE -ne 0 -or -not $runtimeJson) {
        throw "Unable to resolve a Python runtime from '$Command'."
    }
    try {
        $runtime = ($runtimeJson | Select-Object -Last 1) | ConvertFrom-Json
    } catch {
        throw "Python command '$Command' did not return valid runtime information."
    }
    if ([int] $runtime.version[0] -lt 3 -or
        ([int] $runtime.version[0] -eq 3 -and [int] $runtime.version[1] -lt 12)) {
        throw 'Python 3.12 or newer is required.'
    }
    $baseExecutable = Assert-ServiceCompatiblePython `
        -Executable ([string] $runtime.base_executable) -Context $Context
    # Always use the concrete interpreter selected by a launcher such as py.
    $resolvedExecutable = Assert-ServiceCompatiblePython `
        -Executable ([string] $runtime.executable) -Context $Context
    return [PSCustomObject] @{ Executable = $resolvedExecutable; BaseExecutable = $baseExecutable }
}

function Get-VenvBaseExecutable {
    param([Parameter(Mandatory)] [string] $VenvPath)

    $configurationPath = Join-Path $VenvPath 'pyvenv.cfg'
    if (-not (Test-Path -LiteralPath $configurationPath -PathType Leaf)) {
        throw "Existing virtual environment has no pyvenv.cfg: $configurationPath"
    }
    $configuration = @{}
    foreach ($line in Get-Content -LiteralPath $configurationPath) {
        if ($line -match '^\s*([^#=]+?)\s*=\s*(.*?)\s*$') {
            $configuration[$matches[1].Trim().ToLowerInvariant()] = $matches[2]
        }
    }
    if ($configuration.ContainsKey('executable')) {
        return [IO.Path]::GetFullPath($configuration['executable'])
    }
    if ($configuration.ContainsKey('home')) {
        return [IO.Path]::GetFullPath((Join-Path $configuration['home'] 'python.exe'))
    }
    throw "Existing virtual environment does not identify its base runtime: $configurationPath"
}

function Wait-CollectorHealth {
    param([int] $TimeoutSeconds = 60)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 3
            if ($response.status -eq 'ok' -and @($response.PSObject.Properties).Count -eq 1) { return }
        } catch {
            # A connection failure is expected while the service is starting.
        }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'Collector health check did not return the expected response within the timeout.'
}

Assert-Administrator
$RepositoryPath = [IO.Path]::GetFullPath($RepositoryPath)
$WinSWPath = [IO.Path]::GetFullPath($WinSWPath)
$DataPath = [IO.Path]::GetFullPath($DataPath)
if (-not (Test-Path -LiteralPath $WinSWPath -PathType Leaf)) { throw "WinSW executable not found: $WinSWPath" }
if (-not (Test-Path -LiteralPath (Join-Path $RepositoryPath 'pyproject.toml') -PathType Leaf) -or
    -not (Test-Path -LiteralPath (Join-Path $RepositoryPath 'app') -PathType Container)) {
    throw "Repository/runtime directory is invalid: $RepositoryPath"
}
if (Get-Service -Name 'KKPriceWatchCollector' -ErrorAction SilentlyContinue) {
    throw 'KKPriceWatchCollector is already installed. Use Update-Collector.ps1 for an existing installation.'
}
$portListener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($portListener) {
    throw 'Port 8000 is already in use. Stop the foreground Collector before installing the Windows service.'
}

$pythonRuntime = Resolve-PythonRuntime -Command $Python
$basePythonExe = $pythonRuntime.Executable

$venvPath = Join-Path $RepositoryPath '.venv'
if (Test-Path -LiteralPath $venvPath -PathType Container) {
    $venvBaseExecutable = Get-VenvBaseExecutable -VenvPath $venvPath
    try {
        [void] (Resolve-PythonRuntime -Command $venvBaseExecutable `
            -Context 'Existing virtual environment')
    } catch {
        if (-not $RecreateVenv) {
            throw "$($_.Exception.Message) Recreate .venv with a machine-wide Python runtime " +
                'or rerun this installer with -RecreateVenv.'
        }
    }
    if ($RecreateVenv) {
        Remove-Item -LiteralPath $venvPath -Recurse -Force
    }
}
if (-not (Test-Path -LiteralPath $venvPath -PathType Container)) {
    & $basePythonExe -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create the Python virtual environment.' }
}
$pythonExe = Join-Path $venvPath 'Scripts\python.exe'
& $pythonExe -m pip install --upgrade $RepositoryPath
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed.' }

$logPath = Join-Path $DataPath 'logs'
$secretPath = Join-Path $DataPath 'secrets'
$servicePath = Join-Path $DataPath 'service'
@($DataPath, $logPath, $secretPath, $servicePath) | ForEach-Object {
    New-Item -ItemType Directory -Path $_ -Force | Out-Null
}
$tokenFile = Join-Path $secretPath 'api-token.txt'
if ($ProtectedTokenFile) {
    $source = [IO.Path]::GetFullPath($ProtectedTokenFile)
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Protected token file not found: $source" }
    Copy-Item -LiteralPath $source -Destination $tokenFile -Force
} elseif (-not (Test-Path -LiteralPath $tokenFile -PathType Leaf)) {
    $secureToken = Read-Host 'Collector API token' -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
    $plainToken = $null
    try {
        $plainToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        if ([string]::IsNullOrWhiteSpace($plainToken)) { throw 'API token must not be blank.' }
        [IO.File]::WriteAllText($tokenFile, $plainToken, [Text.UTF8Encoding]::new($false))
    } finally {
        if ($null -ne $plainToken) { $plainToken = $null }
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}
$strictUtf8 = [Text.UTF8Encoding]::new($false, $true)
try {
    $tokenCheck = $strictUtf8.GetString([IO.File]::ReadAllBytes($tokenFile)).TrimEnd("`r", "`n")
} catch {
    throw "Token file must exist and contain valid UTF-8: $tokenFile"
}
if ([string]::IsNullOrWhiteSpace($tokenCheck)) { throw 'Token file must contain a non-blank token.' }
$tokenCheck = $null
& icacls.exe $tokenFile /inheritance:r /grant:r '*S-1-5-32-544:(F)' '*S-1-5-18:(F)' '*S-1-5-19:(R)'
if ($LASTEXITCODE -ne 0) { throw 'Failed to restrict the token file ACL.' }

$serviceExe = Join-Path $servicePath 'KKPriceWatchCollector.exe'
$serviceXml = Join-Path $servicePath 'KKPriceWatchCollector.xml'
Copy-Item -LiteralPath $WinSWPath -Destination $serviceExe -Force
$templatePath = Join-Path $PSScriptRoot 'templates\collector-service.xml'
$template = Get-Content -LiteralPath $templatePath -Raw
$escape = { param([string] $Value) [Security.SecurityElement]::Escape($Value) }
$template = $template.Replace('{{PYTHON_EXE}}', (& $escape $pythonExe))
$template = $template.Replace('{{REPOSITORY_DIR}}', (& $escape $RepositoryPath))
$template = $template.Replace('{{TOKEN_FILE}}', (& $escape $tokenFile))
$template = $template.Replace('{{LOG_DIR}}', (& $escape $logPath))
[IO.File]::WriteAllText($serviceXml, $template, [Text.UTF8Encoding]::new($false))

& $serviceExe install
if ($LASTEXITCODE -ne 0) { throw 'WinSW failed to install the Collector service.' }
$serviceRegistered = $true
try {
    Set-Service -Name 'KKPriceWatchCollector' -StartupType Automatic
    & $serviceExe start
    if ($LASTEXITCODE -ne 0) { throw 'WinSW failed to start the Collector service.' }
    Wait-CollectorHealth
} catch {
    $installError = $_.Exception.Message
    $cleanupError = $null
    if ($serviceRegistered) {
        try {
            $registeredService = Get-Service -Name 'KKPriceWatchCollector' -ErrorAction SilentlyContinue
            if ($registeredService -and $registeredService.Status -ne 'Stopped') {
                & $serviceExe stop | Out-Null
            }
            & $serviceExe uninstall | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'WinSW failed to uninstall the incomplete service.' }
        } catch {
            $cleanupError = $_.Exception.Message
        }
    }
    if ($cleanupError) {
        throw "Collector installation failed: $installError Cleanup also failed: $cleanupError"
    }
    throw "Collector installation failed; the incomplete service was removed: $installError"
}
Write-Host 'SUCCESS: KKPriceWatchCollector is installed, running, and healthy.'
