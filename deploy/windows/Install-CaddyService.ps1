[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $CaddyPath,
    [Parameter(Mandatory)] [string] $CaddyfilePath,
    [Parameter(Mandatory)] [string] $WinSWPath,
    [string] $DataPath = 'C:\ProgramData\KKPriceWatchCaddy'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run this script as Administrator.' }
$CaddyPath = [IO.Path]::GetFullPath($CaddyPath)
$CaddyfilePath = [IO.Path]::GetFullPath($CaddyfilePath)
$WinSWPath = [IO.Path]::GetFullPath($WinSWPath)
$DataPath = [IO.Path]::GetFullPath($DataPath)
foreach ($file in @($CaddyPath, $CaddyfilePath, $WinSWPath)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Required file not found: $file" }
}
if (Get-Service -Name 'KKPriceWatchCaddy' -ErrorAction SilentlyContinue) {
    throw 'KKPriceWatchCaddy is already installed. Uninstall it before reinstalling configuration.'
}
& $CaddyPath validate --config $CaddyfilePath
if ($LASTEXITCODE -ne 0) { throw 'Caddy configuration validation failed.' }
$servicePath = Join-Path $DataPath 'service'
$logPath = Join-Path $DataPath 'logs'
@($DataPath, $servicePath, $logPath) | ForEach-Object { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
$serviceExe = Join-Path $servicePath 'KKPriceWatchCaddy.exe'
$serviceXml = Join-Path $servicePath 'KKPriceWatchCaddy.xml'
Copy-Item -LiteralPath $WinSWPath -Destination $serviceExe -Force
$template = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'templates\caddy-service.xml') -Raw
$escape = { param([string] $Value) [Security.SecurityElement]::Escape($Value) }
$template = $template.Replace('{{CADDY_EXE}}', (& $escape $CaddyPath))
$template = $template.Replace('{{CADDYFILE}}', (& $escape $CaddyfilePath))
$template = $template.Replace('{{CADDY_DIR}}', (& $escape (Split-Path -Parent $CaddyfilePath)))
$template = $template.Replace('{{CADDY_LOG_DIR}}', (& $escape $logPath))
[IO.File]::WriteAllText($serviceXml, $template, [Text.UTF8Encoding]::new($false))
& $serviceExe install
if ($LASTEXITCODE -ne 0) { throw 'WinSW failed to install the Caddy service.' }
Set-Service -Name 'KKPriceWatchCaddy' -StartupType Automatic
& $serviceExe start
if ($LASTEXITCODE -ne 0) { throw 'WinSW failed to start the Caddy service.' }
Write-Host 'SUCCESS: KKPriceWatchCaddy is installed and running.'
