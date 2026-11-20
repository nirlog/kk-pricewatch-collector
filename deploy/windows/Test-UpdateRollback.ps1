[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'UpdateRollback.psm1') -Force

function Assert-Equal {
    param([object[]] $Actual, [object[]] $Expected, [string] $Message)
    if (($Actual -join '|') -ne ($Expected -join '|')) {
        throw "$Message Expected '$($Expected -join '|')', got '$($Actual -join '|')'."
    }
}

# A browser/profile problem during rollback cannot block checkout/package restore,
# previous-service startup, or health verification.
$events = [Collections.Generic.List[string]]::new()
Invoke-CollectorUpdateRollback `
    -RestoreCheckout { $events.Add('checkout-previous') } `
    -InstallPreviousPackage { $events.Add('install-previous') } `
    -RemoveOrphanedProfiles { $events.Add('cleanup'); throw 'simulated browser cleanup failure' } `
    -StartPreviousService { $events.Add('start-previous') } `
    -WaitForPreviousHealth { $events.Add('health-previous') }
Assert-Equal $events @('checkout-previous', 'install-previous', 'cleanup', 'start-previous', 'health-previous') 'Rollback order was unsafe.'

$updater = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'Update-Collector.ps1') -Raw
$rollbackStart = $updater.IndexOf('Invoke-CollectorUpdateRollback')
if ($rollbackStart -lt 0) { throw 'Updater does not invoke the rollback helper.' }
$rollbackText = $updater.Substring($rollbackStart)
if ($rollbackText.Contains('Invoke-BrowserRuntimeMaintenance')) { throw 'Rollback depends on browser smoke verification.' }
if ($rollbackText.Contains('-Repair:$RepairBrowserRuntime')) { throw 'Rollback silently provisions a driver.' }
if (-not $rollbackText.Contains('throw "Update failed and rollback')) { throw 'A restored service can incorrectly report update success.' }

$targetVerify = $updater.IndexOf('Invoke-BrowserRuntimeMaintenance')
$targetStart = $updater.IndexOf('& $serviceExe start', $targetVerify)
if ($targetVerify -lt 0 -or $targetStart -lt $targetVerify) { throw 'Target browser verification no longer precedes service startup.' }
if (-not $updater.Contains('-Repair:$RepairBrowserRuntime')) { throw 'The explicit target repair path was removed.' }

Write-Host 'Update rollback regression checks passed.'
