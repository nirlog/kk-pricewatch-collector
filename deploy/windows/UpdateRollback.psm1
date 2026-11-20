Set-StrictMode -Version Latest

function Invoke-CollectorUpdateRollback {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [scriptblock] $RestoreCheckout,
        [Parameter(Mandatory)] [scriptblock] $InstallPreviousPackage,
        [Parameter(Mandatory)] [scriptblock] $RemoveOrphanedProfiles,
        [Parameter(Mandatory)] [scriptblock] $StartPreviousService,
        [Parameter(Mandatory)] [scriptblock] $WaitForPreviousHealth
    )

    & $RestoreCheckout
    & $InstallPreviousPackage

    # Profile cleanup is useful, but it must never prevent restoration of a
    # previously running Collector. Browser verification deliberately does not
    # run here: an older checkout may have incompatible smoke-test semantics.
    try {
        & $RemoveOrphanedProfiles
    } catch {
        Write-Warning "Rollback browser-profile cleanup failed; restoring the previous service anyway: $($_.Exception.Message)"
    }

    & $StartPreviousService
    & $WaitForPreviousHealth
}

Export-ModuleMember -Function Invoke-CollectorUpdateRollback
