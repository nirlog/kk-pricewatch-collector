Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-UserScopedPath {
    param([Parameter(Mandatory)] [string] $Path)

    $fullPath = [IO.Path]::GetFullPath($Path)
    $profileRoots = @($env:USERPROFILE, (Join-Path $env:SystemDrive 'Users'))
    foreach ($root in $profileRoots) {
        if ([string]::IsNullOrWhiteSpace($root)) { continue }
        $fullRoot = [IO.Path]::GetFullPath($root).TrimEnd('\', '/')
        if ($fullPath.Equals($fullRoot, [StringComparison]::OrdinalIgnoreCase) -or
            $fullPath.StartsWith("$fullRoot\", [StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Assert-ServiceCompatiblePython {
    param(
        [Parameter(Mandatory)] [string] $Executable,
        [string] $Context = 'Selected Python installation'
    )

    $resolved = [IO.Path]::GetFullPath($Executable)
    if (Test-UserScopedPath -Path $resolved) {
        throw "$Context is user-scoped and cannot be used by LocalService. " +
            "Detected base runtime: $resolved. Install Python 3.12+ for all users and " +
            'provide its executable path with -Python.'
    }
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "$Context base runtime does not exist or is inaccessible: $resolved"
    }
    return $resolved
}

function Resolve-PythonRuntime {
    param(
        [Parameter(Mandatory)] [string] $Command,
        [string] $Context = 'Selected Python installation'
    )

    # Keep the command free of Python string literals: embedded quotes are not
    # preserved consistently by Windows PowerShell's native argument passing.
    $probe = 'import sys;print(sys.executable);print(sys._base_executable);' +
        'print(sys.version_info.major);print(sys.version_info.minor);print(sys.version_info.micro)'
    try {
        $probeOutput = @(& $Command -c $probe)
    } catch {
        throw "Unable to run the Python command '$Command': $($_.Exception.Message)"
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to resolve a Python runtime from '$Command'."
    }
    if ($probeOutput.Count -ne 5) {
        throw "Python command '$Command' returned $($probeOutput.Count) runtime lines; expected 5."
    }

    $executable = [string] $probeOutput[0]
    $baseExecutable = [string] $probeOutput[1]
    $versionMajor = 0
    $versionMinor = 0
    $versionMicro = 0
    if ([string]::IsNullOrWhiteSpace($executable) -or
        [string]::IsNullOrWhiteSpace($baseExecutable) -or
        -not [int]::TryParse([string] $probeOutput[2], [ref] $versionMajor) -or
        -not [int]::TryParse([string] $probeOutput[3], [ref] $versionMinor) -or
        -not [int]::TryParse([string] $probeOutput[4], [ref] $versionMicro) -or
        $versionMajor -lt 0 -or $versionMinor -lt 0 -or $versionMicro -lt 0) {
        throw "Python command '$Command' returned invalid runtime information."
    }
    if ($versionMajor -lt 3 -or ($versionMajor -eq 3 -and $versionMinor -lt 12)) {
        throw 'Python 3.12 or newer is required.'
    }

    $baseExecutable = Assert-ServiceCompatiblePython -Executable $baseExecutable -Context $Context
    $executable = Assert-ServiceCompatiblePython -Executable $executable -Context $Context
    return [PSCustomObject] @{
        Executable = $executable
        BaseExecutable = $baseExecutable
        VersionMajor = $versionMajor
        VersionMinor = $versionMinor
        VersionMicro = $versionMicro
    }
}

function Get-VenvBaseExecutable {
    param([Parameter(Mandatory)] [string] $VenvPath)

    $configurationPath = Join-Path $VenvPath 'pyvenv.cfg'
    if (-not (Test-Path -LiteralPath $configurationPath -PathType Leaf)) {
        throw "Existing virtual environment has no pyvenv.cfg: $configurationPath"
    }
    $configuration = @{}
    foreach ($line in Get-Content -LiteralPath $configurationPath) {
        if ($line -match '^\s*([^#=]+?)\s*=\s*(.*?)\s*$') {
            $configuration[$matches[1].Trim().ToLowerInvariant()] = $matches[2]
        }
    }
    if ($configuration.ContainsKey('executable')) {
        return [IO.Path]::GetFullPath($configuration['executable'])
    }
    if ($configuration.ContainsKey('home')) {
        return [IO.Path]::GetFullPath((Join-Path $configuration['home'] 'python.exe'))
    }
    throw "Existing virtual environment does not identify its base runtime: $configurationPath"
}

Export-ModuleMember -Function Resolve-PythonRuntime, Get-VenvBaseExecutable
