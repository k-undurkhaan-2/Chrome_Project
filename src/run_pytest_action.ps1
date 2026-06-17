[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$logRoot = Join-Path $repoRoot "log"
$baseTemp = Join-Path $logRoot ("pytest-tmp-{0}" -f ([guid]::NewGuid().ToString("N")))

if (-not (Test-Path -LiteralPath $python)) {
    Write-Error "Python virtual environment executable not found: $python"
    exit 1
}

if (-not (Test-Path -LiteralPath $logRoot)) {
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
}

try {
    & $python -m pytest --basetemp $baseTemp
    $testExitCode = $LASTEXITCODE
} finally {
    try {
        if (Test-Path -LiteralPath $baseTemp) {
            Remove-Item -LiteralPath $baseTemp -Recurse -Force -ErrorAction Stop
        }
    } catch {
        Write-Warning ("pytest basetemp cleanup failed for {0}: {1}" -f $baseTemp, $_.Exception.Message)
    }
}

exit $testExitCode
