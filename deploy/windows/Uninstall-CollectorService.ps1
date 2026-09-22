[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
param(
    [string] $DataPath = 'C:\ProgramData\KKPriceWatchCollector',
    [switch] $PurgeData
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run this script as Administrator.' }
$DataPath = [IO.Path]::GetFullPath($DataPath)
$serviceExe = Join-Path $DataPath 'service\KKPriceWatchCollector.exe'
$service = Get-Service -Name 'KKPriceWatchCollector' -ErrorAction SilentlyContinue
if ($service) {
    if (-not (Test-Path -LiteralPath $serviceExe -PathType Leaf)) { throw "Service wrapper not found: $serviceExe" }
    if ($service.Status -ne 'Stopped') {
        & $serviceExe stop
        if ($LASTEXITCODE -ne 0) { throw 'Unable to stop the Collector service.' }
    }
    & $serviceExe uninstall
    if ($LASTEXITCODE -ne 0) { throw 'Unable to uninstall the Collector service.' }
} else {
    Write-Host 'KKPriceWatchCollector is not installed.'
}
if ($PurgeData) {
    if ($PSCmdlet.ShouldProcess($DataPath, 'Permanently delete all Collector secrets, logs, and service data')) {
        Remove-Item -LiteralPath $DataPath -Recurse -Force
        Write-Host "Persistent data deleted: $DataPath"
    }
} else {
    Write-Host "Repository was not removed. Persistent secrets and logs remain in: $DataPath"
    Write-Host 'Use -PurgeData and confirm explicitly to delete persistent data.'
}
