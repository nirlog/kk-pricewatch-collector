[CmdletBinding()]
param(
    [string] $Python = 'C:\Services\kk-pricewatch-collector\.venv\Scripts\python.exe',
    [Parameter(Mandatory)] [string] $ChromeBinary,
    [string] $DataPath = 'C:\ProgramData\KKPriceWatchCollector',
    [Parameter(Mandatory)]
    [ValidateSet('ProvisionDriver', 'Offline')]
    [string] $Mode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$browserData = Join-Path $DataPath 'browser'
$seleniumCache = Join-Path $DataPath 'selenium-cache'
$previousEnvironment = @{}
@('SE_CACHE_PATH', 'SE_OFFLINE', 'SE_AVOID_STATS', 'SE_AVOID_BROWSER_DOWNLOAD') | ForEach-Object {
    $previousEnvironment[$_] = [Environment]::GetEnvironmentVariable($_, 'Process')
}

try {
    $env:SE_CACHE_PATH = $seleniumCache
    $env:SE_AVOID_STATS = 'true'
    $env:SE_AVOID_BROWSER_DOWNLOAD = 'true'
    if ($Mode -eq 'Offline') {
        $env:SE_OFFLINE = 'true'
    } else {
        Remove-Item Env:SE_OFFLINE -ErrorAction SilentlyContinue
    }

    & $Python -m app.browser.smoke `
        --chrome-binary $ChromeBinary `
        --browser-data-dir $browserData `
        --selenium-cache-dir $seleniumCache
    if ($LASTEXITCODE -ne 0) { throw "Browser runtime $Mode smoke failed." }
} finally {
    foreach ($name in $previousEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
}
