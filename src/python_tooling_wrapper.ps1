[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string] $Command,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $RemainingArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-WrapperUsage {
    [Console]::Error.WriteLine("Usage: .\src\python_tooling_wrapper.ps1 <command>")
    [Console]::Error.WriteLine("")
    [Console]::Error.WriteLine("Read-only commands:")
    [Console]::Error.WriteLine("  status           -> python -m armedforces_tool status overview")
    [Console]::Error.WriteLine("  inventory        -> python -m armedforces_tool commands list --category report")
    [Console]::Error.WriteLine("  report-status    -> python -m armedforces_tool report preview --type full-status")
    [Console]::Error.WriteLine("  manifest-verify  -> python -m armedforces_tool report manifest verify")
    [Console]::Error.WriteLine("  bundle-verify    -> python -m armedforces_tool report bundle verify")
}

function Exit-WithError {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Message,

        [int] $ExitCode = 2
    )

    [Console]::Error.WriteLine("ERROR: $Message")
    Write-WrapperUsage
    exit $ExitCode
}

$allowedCommands = @{
    "status"          = @("status", "overview")
    "inventory"       = @("commands", "list", "--category", "report")
    "report-status"   = @("report", "preview", "--type", "full-status")
    "manifest-verify" = @("report", "manifest", "verify")
    "bundle-verify"   = @("report", "bundle", "verify")
}

$forbiddenCommands = @(
    "report-export",
    "report-export-manifest",
    "bundle-export",
    "bundle-export-dry-run",
    "write",
    "restore",
    "ce",
    "baseline-save",
    "safe-reset",
    "set-diagnostic",
    "prepare-current-case",
    "collect-prepare",
    "case-intake-abandon"
)

if ([string]::IsNullOrWhiteSpace($Command)) {
    Exit-WithError -Message "Missing wrapper command." -ExitCode 2
}

if ($null -eq $RemainingArgs) {
    $RemainingArgs = @()
}

$normalizedCommand = $Command.Trim().ToLowerInvariant()

if ($RemainingArgs.Count -gt 0) {
    Exit-WithError -Message "Wrapper command '$normalizedCommand' does not accept extra arguments." -ExitCode 2
}

if ($forbiddenCommands -contains $normalizedCommand) {
    Exit-WithError -Message "Forbidden wrapper command '$normalizedCommand'. This wrapper exposes read-only Python commands only." -ExitCode 2
}

if (-not $allowedCommands.ContainsKey($normalizedCommand)) {
    Exit-WithError -Message "Unsupported wrapper command '$normalizedCommand'." -ExitCode 2
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$srcPath = Join-Path $repoRoot "src"

if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    [Console]::Error.WriteLine("ERROR: Required Python interpreter not found: $pythonExe")
    [Console]::Error.WriteLine("Run this wrapper from a checkout with the project .venv installed.")
    exit 3
}

$oldPythonPath = $env:PYTHONPATH
$pushedLocation = $false

try {
    $pathSeparator = [System.IO.Path]::PathSeparator
    if ([string]::IsNullOrEmpty($oldPythonPath)) {
        $env:PYTHONPATH = $srcPath
    } else {
        $pythonPathEntries = $oldPythonPath -split [regex]::Escape([string] $pathSeparator)
        if ($pythonPathEntries -notcontains $srcPath) {
            $env:PYTHONPATH = "$srcPath$pathSeparator$oldPythonPath"
        }
    }

    Push-Location -LiteralPath $repoRoot
    $pushedLocation = $true

    $pythonArgs = @("-m", "armedforces_tool") + $allowedCommands[$normalizedCommand]
    & $pythonExe @pythonArgs
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    exit $exitCode
} finally {
    if ($pushedLocation) {
        Pop-Location
    }

    if ($null -eq $oldPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $oldPythonPath
    }
}
