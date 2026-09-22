[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$endpoint = 'http://127.0.0.1:8000/health'
$service = Get-CimInstance Win32_Service -Filter "Name='KKPriceWatchCollector'" -ErrorAction SilentlyContinue
Write-Output ('Service installed: {0}' -f $(if ($null -eq $service) { 'no' } else { 'yes' }))
Write-Output ('Windows service state: {0}' -f $(if ($null -eq $service) { 'not installed' } else { $service.State }))
Write-Output ('Startup type: {0}' -f $(if ($null -eq $service) { 'not installed' } else { $service.StartMode }))
Write-Output "Expected local endpoint: $endpoint"
try {
    $response = Invoke-RestMethod -Uri $endpoint -TimeoutSec 3
    $healthy = $response.status -eq 'ok' -and @($response.PSObject.Properties).Count -eq 1
    Write-Output ('Local health status: {0}' -f $(if ($healthy) { 'healthy' } else { 'unexpected response' }))
} catch {
    Write-Output 'Local health status: unavailable'
}
