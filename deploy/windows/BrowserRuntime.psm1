Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-BrowserRuntimeSmoke {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string] $RepositoryPath,
        [Parameter(Mandatory)] [string] $Python,
        [Parameter(Mandatory)] [string] $ChromeBinary,
        [Parameter(Mandatory)] [string] $DataPath,
        [Parameter(Mandatory)]
        [ValidateSet('ProvisionDriver', 'Offline')]
        [string] $Mode,
        [scriptblock] $SmokeCommand
    )

    $browserData = Join-Path $DataPath 'browser'
    $seleniumCache = Join-Path $DataPath 'selenium-cache'
    $environmentNames = @(
        'SE_CACHE_PATH',
        'SE_OFFLINE',
        'SE_AVOID_STATS',
        'SE_AVOID_BROWSER_DOWNLOAD'
    )
    $previousEnvironment = @{}
    foreach ($name in $environmentNames) {
        $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    }
    $locationChanged = $false

    try {
        $env:SE_CACHE_PATH = $seleniumCache
        $env:SE_AVOID_STATS = 'true'
        $env:SE_AVOID_BROWSER_DOWNLOAD = 'true'
        if ($Mode -eq 'Offline') {
            $env:SE_OFFLINE = 'true'
        } else {
            Remove-Item Env:SE_OFFLINE -ErrorAction SilentlyContinue
        }

        Push-Location -LiteralPath $RepositoryPath
        $locationChanged = $true
        if ($SmokeCommand) {
            & $SmokeCommand $Mode $Python $ChromeBinary $browserData $seleniumCache
        } else {
            # Selenium Manager diagnostics can include machine-specific details. The
            # maintenance boundary emits only the fixed result below.
            & $Python -m app.browser.smoke --chrome-binary $ChromeBinary --browser-data-dir $browserData --selenium-cache-dir $seleniumCache *> $null
            if ($LASTEXITCODE -ne 0) { throw "Browser runtime $Mode smoke failed." }
        }
    } finally {
        if ($locationChanged) { Pop-Location }
        foreach ($name in $environmentNames) {
            if ($null -eq $previousEnvironment[$name]) {
                Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
            } else {
                [Environment]::SetEnvironmentVariable(
                    $name,
                    $previousEnvironment[$name],
                    'Process'
                )
            }
        }
    }
}

function Invoke-BrowserRuntimeMaintenance {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string] $RepositoryPath,
        [Parameter(Mandatory)] [string] $Python,
        [Parameter(Mandatory)] [string] $ChromeBinary,
        [Parameter(Mandatory)] [string] $DataPath,
        [switch] $Repair,
        [scriptblock] $SmokeCommand
    )

    try {
        Invoke-BrowserRuntimeSmoke -RepositoryPath $RepositoryPath -Python $Python -ChromeBinary $ChromeBinary -DataPath $DataPath -Mode Offline -SmokeCommand $SmokeCommand
        Write-Host 'Browser runtime is healthy in offline mode.'
        return
    } catch {
        if (-not $Repair) {
            throw 'Offline browser runtime verification failed. Driver provisioning was not allowed.'
        }
    }

    Write-Host 'Offline verification failed; explicitly requested driver repair is starting.'
    Invoke-BrowserRuntimeSmoke -RepositoryPath $RepositoryPath -Python $Python -ChromeBinary $ChromeBinary -DataPath $DataPath -Mode ProvisionDriver -SmokeCommand $SmokeCommand
    Invoke-BrowserRuntimeSmoke -RepositoryPath $RepositoryPath -Python $Python -ChromeBinary $ChromeBinary -DataPath $DataPath -Mode Offline -SmokeCommand $SmokeCommand
    Write-Host 'Browser runtime was repaired and verified in offline mode.'
}

function Remove-OrphanedBrowserProfiles {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string] $BrowserDataPath,
        [switch] $WhatIf,
        [scriptblock] $ChildProvider,
        [scriptblock] $RemoveProfile
    )

    $browserRoot = [IO.Path]::GetFullPath($BrowserDataPath).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    )
    if (-not (Test-Path -LiteralPath $browserRoot -PathType Container)) {
        throw "Browser data directory does not exist: $browserRoot"
    }

    if ($ChildProvider) {
        $children = @(& $ChildProvider $browserRoot)
    } else {
        $children = @(Get-ChildItem -LiteralPath $browserRoot -Directory -Force)
    }
    foreach ($child in $children) {
        if ($child.Name -notmatch '^chrome-[^\\/]+$') { continue }
        $parent = [IO.Path]::GetFullPath($child.Parent.FullName).TrimEnd(
            [IO.Path]::DirectorySeparatorChar,
            [IO.Path]::AltDirectorySeparatorChar
        )
        if (-not $parent.Equals($browserRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Refusing to clean a browser profile outside the browser data directory.'
        }
        if (($child.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            Write-Warning "Skipped reparse-point browser profile: $($child.Name)"
            continue
        }
        if ($WhatIf) {
            Write-Host "Would remove orphan browser profile: $($child.Name)"
            continue
        }
        if ($RemoveProfile) {
            & $RemoveProfile $child.FullName
        } else {
            Remove-Item -LiteralPath $child.FullName -Recurse -Force
        }
        Write-Host "Removed orphan browser profile: $($child.Name)"
    }
}

Export-ModuleMember -Function Invoke-BrowserRuntimeSmoke, Invoke-BrowserRuntimeMaintenance, Remove-OrphanedBrowserProfiles
