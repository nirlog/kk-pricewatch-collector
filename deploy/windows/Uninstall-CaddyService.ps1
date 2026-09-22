[CmdletBinding()]
param([string] $DataPath = 'C:\ProgramData\KKPriceWatchCaddy')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run this script as Administrator.' }
$DataPath = [IO.Path]::GetFullPath($DataPath)
$service = Get-Service -Name 'KKPriceWatchCaddy' -ErrorAction SilentlyContinue
if (-not $service) { Write-Host 'KKPriceWatchCaddy is not installed.'; exit 0 }
$serviceExe = Join-Path $DataPath 'service\KKPriceWatchCaddy.exe'
if (-not (Test-Path -LiteralPath $serviceExe -PathType Leaf)) { throw "Service wrapper not found: $serviceExe" }
if ($service.Status -ne 'Stopped') {
    & $serviceExe stop
    if ($LASTEXITCODE -ne 0) { throw 'Unable to stop the Caddy service.' }
}
& $serviceExe uninstall
if ($LASTEXITCODE -ne 0) { throw 'Unable to uninstall the Caddy service.' }
Write-Host "Caddy service removed. Caddy configuration and logs remain under: $DataPath"
