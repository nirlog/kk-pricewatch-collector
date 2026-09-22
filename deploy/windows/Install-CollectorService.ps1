[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $WinSWPath,
    [string] $RepositoryPath = 'C:\Services\kk-pricewatch-collector',
    [string] $Python = 'py',
    [string] $DataPath = 'C:\ProgramData\KKPriceWatchCollector',
    [Parameter(Mandatory)] [string] $ChromeBinary,
    [string] $ProtectedTokenFile,
    [switch] $RecreateVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'CollectorRuntime.psm1') -Force

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run this script from an elevated PowerShell session.'
    }
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
$ChromeBinary = [IO.Path]::GetFullPath($ChromeBinary)
if (-not (Test-Path -LiteralPath $WinSWPath -PathType Leaf)) { throw "WinSW executable not found: $WinSWPath" }
if (-not (Test-Path -LiteralPath $ChromeBinary -PathType Leaf)) {
    throw "Machine-wide Chrome executable not found: $ChromeBinary"
}
$usersRoot = [IO.Path]::GetFullPath((Join-Path $env:SystemDrive 'Users'))
if ($ChromeBinary.StartsWith($usersRoot + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Chrome must be machine-wide and must not be installed under C:\Users.'
}
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
$browserPath = Join-Path $DataPath 'browser'
$seleniumCachePath = Join-Path $DataPath 'selenium-cache'
@($DataPath, $logPath, $secretPath, $servicePath, $browserPath, $seleniumCachePath) | ForEach-Object {
    New-Item -ItemType Directory -Path $_ -Force | Out-Null
}
@($browserPath, $seleniumCachePath) | ForEach-Object {
    & icacls.exe $_ /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)(F)' `
        '*S-1-5-18:(OI)(CI)(F)' '*S-1-5-19:(OI)(CI)(M)'
    if ($LASTEXITCODE -ne 0) { throw "Failed to configure browser runtime ACL: $_" }
}

# Provisioning may download only a matching driver. The second run proves that
# production startup can resolve that driver with Selenium Manager fully offline.
$browserSmoke = Join-Path $PSScriptRoot 'Test-BrowserRuntime.ps1'
& $browserSmoke -Python $pythonExe -ChromeBinary $ChromeBinary -DataPath $DataPath `
    -Mode ProvisionDriver
if ($LASTEXITCODE -ne 0) { throw 'ChromeDriver provisioning failed; service was not installed.' }
& $browserSmoke -Python $pythonExe -ChromeBinary $ChromeBinary -DataPath $DataPath `
    -Mode Offline
if ($LASTEXITCODE -ne 0) { throw 'Offline browser verification failed; service was not installed.' }

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
$template = $template.Replace('{{CHROME_BINARY}}', (& $escape $ChromeBinary))
$template = $template.Replace('{{BROWSER_DATA_DIR}}', (& $escape $browserPath))
$template = $template.Replace('{{SELENIUM_CACHE_DIR}}', (& $escape $seleniumCachePath))
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
