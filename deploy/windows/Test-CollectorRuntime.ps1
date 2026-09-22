[CmdletBinding()]
param([Parameter(Mandatory)] [string] $Python)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'CollectorRuntime.psm1') -Force

$runtime = Resolve-PythonRuntime -Command $Python -Context 'CI Python installation'
if (-not (Test-Path -LiteralPath $runtime.Executable -PathType Leaf)) {
    throw "Resolved Python executable does not exist: $($runtime.Executable)"
}
if ($runtime.VersionMajor -lt 3 -or
    ($runtime.VersionMajor -eq 3 -and $runtime.VersionMinor -lt 12)) {
    throw "Resolved unsupported Python version: $($runtime.VersionMajor).$($runtime.VersionMinor)"
}

$malformedFailed = $false
try {
    [void] (Resolve-PythonRuntime -Command (Join-Path $env:RUNNER_TEMP 'missing-python.exe'))
} catch {
    $malformedFailed = $true
}
if (-not $malformedFailed) { throw 'A malformed Python invocation unexpectedly succeeded.' }

Write-Host "Resolved machine-wide Python runtime: $($runtime.Executable)"
