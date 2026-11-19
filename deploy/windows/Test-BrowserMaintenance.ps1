[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'BrowserRuntime.psm1') -Force

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

$testRoot = Join-Path ([IO.Path]::GetTempPath()) ("kk-pricewatch-browser-" + [Guid]::NewGuid())
New-Item -ItemType Directory -Path $testRoot | Out-Null
try {
    $dataPath = Join-Path $testRoot 'data'
    $browserPath = Join-Path $dataPath 'browser'
    $cachePath = Join-Path $dataPath 'selenium-cache'
    New-Item -ItemType Directory -Path $browserPath, $cachePath | Out-Null

    $oldCache = 'previous-cache'
    $oldOffline = 'previous-offline'
    $oldStats = 'previous-stats'
    $oldToken = 'production-token-marker'
    $env:SE_CACHE_PATH = $oldCache
    $env:SE_OFFLINE = $oldOffline
    $env:SE_AVOID_STATS = $oldStats
    Remove-Item Env:SE_AVOID_BROWSER_DOWNLOAD -ErrorAction SilentlyContinue
    $env:KK_PRICEWATCH_API_TOKEN = $oldToken
    $observed = [Collections.Generic.List[string]]::new()
    $inspectEnvironment = {
        param($Mode, $Python, $Chrome, $BrowserData, $Cache)
        [void] $observed.Add($Mode)
        Assert-True ($env:SE_OFFLINE -eq 'true') 'Offline mode was not set.'
        Assert-True ($env:SE_CACHE_PATH -eq $Cache) 'Selenium cache was not set.'
        Assert-True ($env:KK_PRICEWATCH_API_TOKEN -eq $oldToken) 'Production token environment changed.'
    }
    Invoke-BrowserRuntimeSmoke -RepositoryPath $PSScriptRoot -Python 'python' -ChromeBinary 'chrome' -DataPath $dataPath -Mode Offline -SmokeCommand $inspectEnvironment
    Assert-True ($observed.Count -eq 1) 'Smoke test seam was not invoked.'
    Assert-True ($env:SE_CACHE_PATH -eq $oldCache) 'SE_CACHE_PATH was not restored.'
    Assert-True ($env:SE_OFFLINE -eq $oldOffline) 'SE_OFFLINE was not restored.'
    Assert-True ($env:SE_AVOID_STATS -eq $oldStats) 'SE_AVOID_STATS was not restored.'
    Assert-True (-not (Test-Path Env:SE_AVOID_BROWSER_DOWNLOAD)) 'Absent SE_AVOID_BROWSER_DOWNLOAD was not restored.'
    Assert-True ($env:KK_PRICEWATCH_API_TOKEN -eq $oldToken) 'Token environment was not preserved.'

    $verifyCalls = [Collections.Generic.List[string]]::new()
    $alwaysFailOffline = {
        param($Mode)
        [void] $verifyCalls.Add($Mode)
        throw 'simulated offline failure'
    }
    try {
        Invoke-BrowserRuntimeMaintenance -RepositoryPath $PSScriptRoot -Python 'python' -ChromeBinary 'chrome' -DataPath $dataPath -SmokeCommand $alwaysFailOffline
        throw 'Verification-only maintenance unexpectedly succeeded.'
    } catch {
        Assert-True ($_.Exception.Message -eq 'Offline browser runtime verification failed. Driver provisioning was not allowed.') 'Verification-only failure was not sanitized.'
    }
    Assert-True (($verifyCalls -join ',') -eq 'Offline') 'Verification-only mode attempted provisioning.'

    $repairCalls = [Collections.Generic.List[string]]::new()
    $repairState = [PSCustomObject] @{ OfflineAttempts = 0 }
    $repairSucceeds = {
        param($Mode)
        [void] $repairCalls.Add($Mode)
        if ($Mode -eq 'Offline') {
            $repairState.OfflineAttempts += 1
            if ($repairState.OfflineAttempts -eq 1) { throw 'simulated initial failure' }
        }
    }
    Invoke-BrowserRuntimeMaintenance -RepositoryPath $PSScriptRoot -Python 'python' -ChromeBinary 'chrome' -DataPath $dataPath -Repair -SmokeCommand $repairSucceeds
    Assert-True (($repairCalls -join ',') -eq 'Offline,ProvisionDriver,Offline') 'Repair sequence was incorrect.'

    $failedRepairCalls = [Collections.Generic.List[string]]::new()
    $repairStillFails = {
        param($Mode)
        [void] $failedRepairCalls.Add($Mode)
        if ($Mode -eq 'Offline') { throw 'simulated offline failure' }
    }
    try {
        Invoke-BrowserRuntimeMaintenance -RepositoryPath $PSScriptRoot -Python 'python' -ChromeBinary 'chrome' -DataPath $dataPath -Repair -SmokeCommand $repairStillFails
        throw 'A failed final offline verification unexpectedly succeeded.'
    } catch {
        Assert-True ($_.Exception.Message -eq 'simulated offline failure') 'Final offline failure was lost.'
    }
    Assert-True (($failedRepairCalls -join ',') -eq 'Offline,ProvisionDriver,Offline') 'Failed repair sequence was incorrect.'

    $stale = Join-Path $browserPath 'chrome-stale'
    $dryRun = Join-Path $browserPath 'chrome-dry-run'
    $unrelated = Join-Path $browserPath 'unrelated'
    $nested = Join-Path $unrelated 'chrome-nested'
    $outside = Join-Path $testRoot 'outside'
    New-Item -ItemType Directory -Path $stale, $dryRun, $unrelated, $nested, $outside | Out-Null
    Set-Content -LiteralPath (Join-Path $browserPath 'chrome-file') -Value 'keep'
    Set-Content -LiteralPath (Join-Path $cachePath 'driver-marker') -Value 'keep'
    $junction = Join-Path $browserPath 'chrome-junction'
    New-Item -ItemType Junction -Path $junction -Target $outside | Out-Null

    Remove-OrphanedBrowserProfiles -BrowserDataPath $browserPath -WhatIf
    Assert-True (Test-Path -LiteralPath $dryRun -PathType Container) 'Dry-run removed a profile.'
    Remove-Item -LiteralPath $dryRun -Recurse -Force
    Remove-OrphanedBrowserProfiles -BrowserDataPath $browserPath

    Assert-True (-not (Test-Path -LiteralPath $stale)) 'Stale profile was not removed.'
    Assert-True (Test-Path -LiteralPath $unrelated -PathType Container) 'Unrelated directory was removed.'
    Assert-True (Test-Path -LiteralPath $nested -PathType Container) 'Nested directory was scanned.'
    Assert-True (Test-Path -LiteralPath (Join-Path $browserPath 'chrome-file') -PathType Leaf) 'Matching file was removed.'
    Assert-True (Test-Path -LiteralPath (Join-Path $cachePath 'driver-marker') -PathType Leaf) 'Selenium cache was modified.'
    if ($PSVersionTable.PSEdition -eq 'Desktop' -or $IsWindows) {
        Assert-True ($null -ne (Get-Item -LiteralPath $junction -Force -ErrorAction SilentlyContinue)) 'Reparse point was removed.'
    }
    Assert-True (Test-Path -LiteralPath $outside -PathType Container) 'Cleanup escaped the browser directory.'

    Write-Host 'Browser maintenance control-flow tests passed.'
} finally {
    Remove-Item -LiteralPath $testRoot -Recurse -Force
}
