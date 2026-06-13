param(
    [Parameter(Position = 0)]
    [string]$Preset,
    [switch]$Help,
    [string]$ProjectRoot = "D:\armedforces.io-v2",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function Format-CommandPart {
    param([string]$Value)

    if ($null -eq $Value) {
        return "''"
    }

    if ($Value -match "\s") {
        return "'" + ($Value -replace "'", "''") + "'"
    }
    return $Value
}

function Format-CommandLine {
    param([string[]]$Parts)

    return (($Parts | ForEach-Object { Format-CommandPart $_ }) -join " ")
}

function Write-PresetHelp {
    param($PresetMap)

    Write-Output "Classifier command presets"
    Write-Output ""
    Write-Output "Usage:"
    Write-Output "  powershell -NoProfile -ExecutionPolicy Bypass -File `"D:\armedforces.io-v2\src\classifier_preset.ps1`" <preset>"
    Write-Output ""
    Write-Output "Available presets:"
    foreach ($name in $PresetMap.Keys) {
        Write-Output ("  {0,-18} {1}" -f $name, $PresetMap[$name].description)
    }
    Write-Output ""
    Write-Output "Extra arguments after the preset are appended to the classifier command."
}

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd("\", "/")
$classifierPath = Join-Path (Join-Path $projectRootPath "src") "batch_log_classifier.ps1"
$baselinePath = Join-Path (Join-Path $projectRootPath "log\baselines") "baseline_compact_basic_20260613_latest20.md"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$baselineOutPath = Join-Path (Join-Path $projectRootPath "log\baselines") ("baseline_full_latest20_{0}.md" -f $timestamp)
$compareOutPath = Join-Path (Join-Path $projectRootPath "log\baselines") ("compare_full_latest20_{0}.md" -f $timestamp)

$presets = [ordered]@{
    "quick-latest5" = [pscustomobject]@{
        description = "Latest 5 quick-profile records"
        args = @("-Latest", "5", "-Profile", "quick")
    }
    "full-latest20" = [pscustomobject]@{
        description = "Latest 20 full-profile records"
        args = @("-Latest", "20", "-Profile", "full")
    }
    "compare-full" = [pscustomobject]@{
        description = "Compare latest 20 full-profile records to compact baseline"
        args = @("-Latest", "20", "-Profile", "full", "-CompareTo", $baselinePath)
    }
    "save-full-baseline" = [pscustomobject]@{
        description = "Save latest 20 full-profile baseline report"
        args = @("-Latest", "20", "-Profile", "full", "-OutFile", $baselineOutPath)
    }
    "compare-full-save" = [pscustomobject]@{
        description = "Compare latest 20 full-profile records and save report"
        args = @("-Latest", "20", "-Profile", "full", "-CompareTo", $baselinePath, "-OutFile", $compareOutPath)
    }
    "registry-summary" = [pscustomobject]@{
        description = "Show registry summary"
        args = @("-RegistrySummary")
    }
    "registry-recent" = [pscustomobject]@{
        description = "Show 20 most recent registry records"
        args = @("-RegistryRecent", "20")
    }
    "explain-full" = [pscustomobject]@{
        description = "Latest 20 full-profile records with failure explanations"
        args = @("-Latest", "20", "-Profile", "full", "-ExplainFailures")
    }
}

if ($Help -or -not $Preset) {
    Write-PresetHelp -PresetMap $presets
    exit 0
}

if (-not $presets.Contains($Preset)) {
    Write-Warning ("Unknown preset: {0}" -f $Preset)
    Write-PresetHelp -PresetMap $presets
    exit 1
}

if (-not (Test-Path -LiteralPath $classifierPath)) {
    Write-Error ("Classifier script not found: {0}" -f $classifierPath)
    exit 1
}

$presetArgs = @($presets[$Preset].args)
if ($ExtraArgs) {
    $presetArgs += @($ExtraArgs)
}

$commandParts = @("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $classifierPath) + $presetArgs
Write-Output ("Executing: {0}" -f (Format-CommandLine -Parts $commandParts))
Write-Output ""

& powershell -NoProfile -ExecutionPolicy Bypass -File $classifierPath @presetArgs
exit $LASTEXITCODE
