[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $WinSWPath,
    [string] $RepositoryPath = 'C:\Services\kk-pricewatch-collector',
    [string] $Python = 'py',
    [string] $DataPath = 'C:\ProgramData\KKPriceWatchCollector',
    [string] $ProtectedTokenFile
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

function Wait-CollectorHealth {
    param([int] $TimeoutSeconds = 60)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 3
            if ($response.status -eq 'ok' -and @($response.PSObject.Properties).Count -eq 1) { return }
        } catch { Start-Sleep -Seconds 2 }
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

& $Python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 or newer is required.' }

$venvPath = Join-Path $RepositoryPath '.venv'
if (-not (Test-Path -LiteralPath $venvPath -PathType Container)) {
    & $Python -m venv $venvPath
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
Set-Service -Name 'KKPriceWatchCollector' -StartupType Automatic
& $serviceExe start
if ($LASTEXITCODE -ne 0) { throw 'WinSW failed to start the Collector service.' }
Wait-CollectorHealth
Write-Host 'SUCCESS: KKPriceWatchCollector is installed, running, and healthy.'
