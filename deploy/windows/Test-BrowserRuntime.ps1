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

Import-Module (Join-Path $PSScriptRoot 'BrowserRuntime.psm1') -Force
$repositoryPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
Invoke-BrowserRuntimeSmoke -RepositoryPath $repositoryPath -Python $Python -ChromeBinary $ChromeBinary -DataPath $DataPath -Mode $Mode
