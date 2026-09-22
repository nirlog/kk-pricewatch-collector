[CmdletBinding()]
param(
    [string] $Python = 'C:\Services\kk-pricewatch-collector\.venv\Scripts\python.exe',
    [Parameter(Mandatory)] [string] $ChromeBinary,
    [string] $DataPath = 'C:\ProgramData\KKPriceWatchCollector'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$browserData = Join-Path $DataPath 'browser'
$seleniumCache = Join-Path $DataPath 'selenium-cache'
& $Python -m app.browser.smoke `
    --chrome-binary $ChromeBinary `
    --browser-data-dir $browserData `
    --selenium-cache-dir $seleniumCache
if ($LASTEXITCODE -ne 0) { throw 'Production browser runtime smoke failed.' }
