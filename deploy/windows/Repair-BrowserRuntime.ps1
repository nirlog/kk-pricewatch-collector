[CmdletBinding()]
param(
    [string] $RepositoryPath = 'C:\Services\kk-pricewatch-collector',
    [string] $DataPath = 'C:\ProgramData\KKPriceWatchCollector',
    [Parameter(Mandatory)] [string] $ChromeBinary,
    [string] $Python,
    [switch] $Repair,
    [switch] $CleanupOrphanProfiles,
    [switch] $CleanupWhatIf
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'BrowserRuntime.psm1') -Force

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run this script from an elevated PowerShell session.'
    }
}

Assert-Administrator
$RepositoryPath = [IO.Path]::GetFullPath($RepositoryPath)
$DataPath = [IO.Path]::GetFullPath($DataPath)
$ChromeBinary = [IO.Path]::GetFullPath($ChromeBinary)
if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = Join-Path $RepositoryPath '.venv\Scripts\python.exe'
} else {
    $Python = [IO.Path]::GetFullPath($Python)
}
if (-not (Test-Path -LiteralPath (Join-Path $RepositoryPath 'pyproject.toml') -PathType Leaf)) {
    throw "Repository path is invalid: $RepositoryPath"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Virtual-environment Python was not found: $Python"
}
if (-not (Test-Path -LiteralPath $ChromeBinary -PathType Leaf)) {
    throw "Chrome binary was not found: $ChromeBinary"
}

$browserDataPath = Join-Path $DataPath 'browser'
$seleniumCachePath = Join-Path $DataPath 'selenium-cache'
foreach ($path in @($browserDataPath, $seleniumCachePath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "Browser runtime directory was not found: $path"
    }
}

if ($Repair -or ($CleanupOrphanProfiles -and -not $CleanupWhatIf)) {
    $service = Get-Service -Name 'KKPriceWatchCollector' -ErrorAction SilentlyContinue
    if (-not $service -or $service.Status -ne 'Stopped') {
        throw 'Stop the installed KKPriceWatchCollector service before repair or cleanup.'
    }
}

try {
    Invoke-BrowserRuntimeMaintenance -RepositoryPath $RepositoryPath -Python $Python -ChromeBinary $ChromeBinary -DataPath $DataPath -Repair:$Repair
} finally {
    if ($CleanupOrphanProfiles) {
        Remove-OrphanedBrowserProfiles -BrowserDataPath $browserDataPath -WhatIf:$CleanupWhatIf
    }
}
