[CmdletBinding()]
param(
    [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string] $Ref,
    [string] $RepositoryPath = 'C:\Services\kk-pricewatch-collector',
    [string] $DataPath = 'C:\ProgramData\KKPriceWatchCollector'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Administrator {
    $principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run this script as Administrator.' }
}
function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments)] [string[]] $Arguments)
    & git -C $RepositoryPath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "git command failed: git $($Arguments -join ' ')" }
}
function Install-Package {
    & $pythonExe -m pip install --upgrade $RepositoryPath
    if ($LASTEXITCODE -ne 0) { throw 'Package installation failed.' }
    & $pythonExe -m compileall -q (Join-Path $RepositoryPath 'app')
    if ($LASTEXITCODE -ne 0) { throw 'Python compile smoke check failed.' }
    # Avoid Python string literals here: Windows PowerShell 5.1 does not preserve
    # nested quotes consistently when invoking native executables.
    & $pythonExe -c 'from app.main import create_app; assert callable(create_app)'
    if ($LASTEXITCODE -ne 0) { throw 'Python import smoke check failed.' }
}
function Wait-Health {
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    do {
        try {
            $result = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 3
            if ($result.status -eq 'ok' -and @($result.PSObject.Properties).Count -eq 1) { return }
        } catch {
            # A connection failure is expected while the service is starting.
        }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'Collector did not become healthy within 60 seconds.'
}

Assert-Administrator
$RepositoryPath = [IO.Path]::GetFullPath($RepositoryPath)
$pythonExe = Join-Path $RepositoryPath '.venv\Scripts\python.exe'
$serviceExe = Join-Path ([IO.Path]::GetFullPath($DataPath)) 'service\KKPriceWatchCollector.exe'
if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) { throw "Virtual environment not found: $pythonExe" }
if (-not (Test-Path -LiteralPath $serviceExe -PathType Leaf)) { throw "Service wrapper not found: $serviceExe" }
if (-not (Get-Service -Name 'KKPriceWatchCollector' -ErrorAction SilentlyContinue)) { throw 'Collector service is not installed.' }
$status = (& git -C $RepositoryPath status --porcelain)
if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect the Git working tree.' }
if ($status) { throw 'Working tree is not clean; commit or remove changes before updating.' }
$previousSha = (& git -C $RepositoryPath rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Unable to determine the current Git commit.' }

& $serviceExe stop
if ($LASTEXITCODE -ne 0) { throw 'Unable to stop the Collector service.' }
try {
    Invoke-Git fetch origin -- $Ref
    Invoke-Git checkout --detach FETCH_HEAD
    Install-Package
    & $serviceExe start
    if ($LASTEXITCODE -ne 0) { throw 'Unable to start the updated Collector service.' }
    Wait-Health
    Write-Host "SUCCESS: Collector updated to $((& git -C $RepositoryPath rev-parse HEAD).Trim())."
} catch {
    $updateError = $_.Exception.Message
    Write-Warning "Update failed; rolling back to $previousSha. Error: $updateError"
    try {
        & $serviceExe stop | Out-Null
        Invoke-Git checkout --detach $previousSha
        Install-Package
        & $serviceExe start
        if ($LASTEXITCODE -ne 0) { throw 'Unable to start the rolled-back Collector service.' }
        Wait-Health
    } catch {
        $rollbackError = $_.Exception.Message
        throw "Update failed. Rollback attempted for $previousSha but did not complete: $rollbackError. Original error: $updateError"
    }
    throw "Update failed and rollback to $previousSha completed successfully. Original error: $updateError"
}
