param(
    [Parameter(Position = 0)]
    [string]$Command,
    [switch]$Help,
    [string]$ProjectRoot = "D:\armedforces.io-v2",
    [string]$LogRoot = "D:\armedforces.io-v2\log\auto_output",
    [string]$CaseId,
    [string]$KnownTrueAddr,
    [ValidateSet("quick", "full")]
    [string]$Profile = "quick",
    [string]$TargetValuePattern = "0x42C80000",
    [double]$TargetValueFloat = 100.0,
    [ValidateSet("basic", "debug", "trace")]
    [string]$DiagnosticLevel = "basic",
    [double]$WriteValueFloat = [double]::NaN,
    [string]$BatchId,
    [switch]$EnableWrite,
    [switch]$ConfirmWrite
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$ExpectedProjectRoot = "D:\armedforces.io-v2"
$ProjectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd("\", "/")
$CaseConfigToolPath = Join-Path (Join-Path $ProjectRootPath "src") "case_config_tool.ps1"
$ClassifierPath = Join-Path (Join-Path $ProjectRootPath "src") "batch_log_classifier.ps1"
$CaseConfigPath = Join-Path (Join-Path $ProjectRootPath "src") "run_case_config.local.lua"
$BaselinePath = Join-Path (Join-Path $ProjectRootPath "log\baselines") "baseline_compact_basic_20260613_latest20.md"

function Format-CommandPart {
    param([string]$Value)

    if ($null -eq $Value) {
        return "''"
    }
    if ($Value -match "\s") {
        return '"' + ($Value -replace '"', '\"') + '"'
    }
    return $Value
}

function Format-CommandLine {
    param([string[]]$Parts)

    return (($Parts | ForEach-Object { Format-CommandPart $_ }) -join " ")
}

function Write-CommandHelp {
    Write-Output "Test session workflow helper"
    Write-Output ""
    Write-Output "Usage:"
    Write-Output "  powershell -NoProfile -ExecutionPolicy Bypass -File `"D:\armedforces.io-v2\src\test_session_tool.ps1`" <command> [options]"
    Write-Output ""
    Write-Output "Commands:"
    Write-Output "  prepare        Set run_case_config.local.lua for the next manual CE/Lua run"
    Write-Output "  post-quick     Classify latest quick batch and append registry"
    Write-Output "  post-full      Classify latest full batch and append registry"
    Write-Output "  compare-full   Compare latest 20 baseline-eligible full batches to compact baseline"
    Write-Output "  inspect-latest Inspect the latest batch id from -LogRoot"
    Write-Output "  status         Show config, latest 5 classifier summary, registry summary, and git status"
    Write-Output "  disable-execution       Disable execution/write in local case config"
    Write-Output "  safe-reset              Disable execution and optionally reset target float"
    Write-Output "  prepare-dry-run-write   Prepare full/basic dry-run write config"
    Write-Output "  prepare-guarded-write   Prepare full/basic guarded write config"
    Write-Output "  prepare-restore         Prepare dry-run or write-ready restore config from a batch"
    Write-Output "  post-execution          Summarize latest full execution fields after manual CE run"
    Write-Output ""
    Write-Output "Prepare options:"
    Write-Output "  -KnownTrueAddr <addr> [-CaseId <id>] [-Profile quick|full] [-DiagnosticLevel basic|debug|trace]"
    Write-Output "  prepare-dry-run-write -KnownTrueAddr <addr> -WriteValueFloat <float>"
    Write-Output "  prepare-guarded-write -KnownTrueAddr <addr> -WriteValueFloat <float> -ConfirmWrite"
    Write-Output "  prepare-restore -BatchId <batch> [-EnableWrite -ConfirmWrite]"
    Write-Output "  safe-reset [-TargetValueFloat 100.0]"
    Write-Output ""
    Write-Output "Common options:"
    Write-Output "  -ProjectRoot D:\armedforces.io-v2"
    Write-Output "  -LogRoot D:\armedforces.io-v2\log\auto_output"
}

function Invoke-WorkflowCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [switch]$Capture,
        [switch]$Quiet
    )

    $commandParts = @("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $FilePath) + @($Arguments)
    Write-Host ("Executing: {0}" -f (Format-CommandLine -Parts $commandParts))
    Write-Host ""

    $output = @(& powershell -NoProfile -ExecutionPolicy Bypass -File $FilePath @Arguments 2>&1)
    $exitCode = $LASTEXITCODE
    if (-not $Quiet) {
        foreach ($line in $output) {
            Write-Host $line
        }
    }

    return [pscustomobject][ordered]@{
        exit_code = $exitCode
        output = @($output | ForEach-Object { "$_" })
    }
}

function Assert-ToolExists {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Error ("Required tool not found: {0}" -f $Path)
        exit 1
    }
}

function Format-InvariantFloat {
    param([double]$Value)

    return $Value.ToString("0.0###############", [System.Globalization.CultureInfo]::InvariantCulture)
}

function Test-DoubleParameterProvided {
    param([double]$Value)

    return -not [double]::IsNaN($Value)
}

function Test-KnownTrueAddr {
    param($Value)

    if ($null -eq $Value) {
        return $false
    }
    return "$Value" -match '^0x[0-9A-Fa-f]+$'
}

function Assert-KnownTrueAddr {
    param([string]$Value, [string]$CommandName)

    if (-not (Test-KnownTrueAddr -Value $Value)) {
        Write-Output ("ERROR: -KnownTrueAddr for {0} must match ^0x[0-9A-Fa-f]+$; rejected value: {1}" -f $CommandName, $(if ($Value) { $Value } else { "-" }))
        exit 1
    }
}

function Normalize-ConfigValue {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }
    $text = "$Value".Trim()
    if (($text.StartsWith('"') -and $text.EndsWith('"')) -or ($text.StartsWith("'") -and $text.EndsWith("'"))) {
        return $text.Substring(1, $text.Length - 2)
    }
    return $text
}

function Read-CaseConfigMap {
    param([string]$Path)

    $config = [ordered]@{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $config
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*,?\s*(?:--.*)?$') {
            $config[$matches[1]] = Normalize-ConfigValue -Value $matches[2]
        }
    }
    return $config
}

function Get-ConfigField {
    param($Config, [string]$Key)

    if ($Config -and $Config.Contains($Key)) {
        return $Config[$Key]
    }
    return $null
}

function Test-ExecutionConfigWriteCapable {
    param($Config)

    $executionMode = Get-ConfigField -Config $Config -Key "execution_mode"
    $writeEnabled = Get-ConfigField -Config $Config -Key "write_enabled"
    $executionConfirm = Get-ConfigField -Config $Config -Key "execution_confirm"

    return $executionMode -eq "write" -or $writeEnabled -eq "true" -or ($null -ne $executionConfirm -and "$executionConfirm" -ne "")
}

function Write-ExecutionConfigSafetyWarning {
    param($Config)

    if (Test-ExecutionConfigWriteCapable -Config $Config) {
        Write-Output "WARNING: execution config is write-capable. Run disable-execution or safe-reset before normal detection."
    }
}

function New-SetCaseArguments {
    param(
        [string]$Address,
        [string]$OptionalCaseId,
        [string]$ProfileName
    )

    $args = @(
        "-Set",
        "-KnownTrueAddr", $Address,
        "-TargetValuePattern", $TargetValuePattern,
        "-TargetValueFloat", (Format-InvariantFloat -Value $TargetValueFloat),
        "-DiagnosticLevel", "basic",
        "-ValidationProfile", $ProfileName
    )
    if ($OptionalCaseId) {
        $args = @("-Set", "-CaseId", $OptionalCaseId) + @($args | Select-Object -Skip 1)
    }
    return $args
}

function Get-LogField {
    param($Block, [string]$Key)

    if ($Block -and $Block.Fields -and $Block.Fields.Contains($Key)) {
        return $Block.Fields[$Key]
    }
    return "not_available"
}

function Test-LogTrue {
    param($Value)

    if ($Value -is [bool]) {
        return [bool]$Value
    }
    if ($null -eq $Value) {
        return $false
    }
    return "$Value".Trim().ToLowerInvariant() -eq "true"
}

function Test-LogPresent {
    param($Value)

    if ($null -eq $Value) {
        return $false
    }
    $text = "$Value".Trim()
    return $text -ne "" -and $text -ne "nil" -and $text -ne "-" -and $text -ne "not_available"
}

function Get-ExecutionOutcomeFromBlock {
    param($Block)

    $mode = Get-LogField -Block $Block -Key "execution_mode"
    if (-not (Test-LogPresent -Value $mode) -or $mode -eq "disabled") {
        return "execution_disabled"
    }

    $writeAttempted = Test-LogTrue (Get-LogField -Block $Block -Key "write_attempted")
    $writeOk = Test-LogTrue (Get-LogField -Block $Block -Key "write_ok")
    $readbackOk = Test-LogTrue (Get-LogField -Block $Block -Key "readback_ok")
    $preconditionsOk = Test-LogTrue (Get-LogField -Block $Block -Key "execution_preconditions_ok")
    $failureClass = Get-LogField -Block $Block -Key "execution_failure_class"

    if ($mode -eq "dry_run" -and $preconditionsOk -and -not $writeAttempted) {
        return "execution_dry_run_ready"
    }
    if ($mode -eq "write" -and -not $writeAttempted) {
        return "execution_write_blocked"
    }
    if ($mode -eq "write" -and $writeAttempted -and $writeOk -and $readbackOk) {
        return "execution_write_ok"
    }
    if ($writeAttempted -and -not $readbackOk) {
        return "execution_readback_failed"
    }
    if (Test-LogPresent -Value $failureClass) {
        if (-not $writeAttempted) {
            return "execution_write_blocked"
        }
        return "execution_failed"
    }

    return "execution_unknown"
}

function Read-BatchLogBlocks {
    param([string]$Path)

    $blocks = @()
    $currentName = "batch_header"
    $currentFields = [ordered]@{}

    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*---\s+(.+?)\s+---\s*$') {
            if ($currentFields.Count -gt 0) {
                $blocks += [pscustomobject]@{ Name = $currentName; Fields = $currentFields }
            }
            $currentName = $matches[1]
            $currentFields = [ordered]@{}
            continue
        }
        if ($line -match '^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$') {
            $currentFields[$matches[1]] = $matches[2].Trim()
        }
    }

    if ($currentFields.Count -gt 0) {
        $blocks += [pscustomobject]@{ Name = $currentName; Fields = $currentFields }
    }
    return $blocks
}

function Get-BatchSummaryPath {
    param([string]$Root, [string]$Batch)

    $summaryPath = Join-Path $Root ("{0}__summary.txt" -f $Batch)
    if (Test-Path -LiteralPath $summaryPath) {
        return $summaryPath
    }
    $diagnosticPath = Join-Path $Root ("{0}__diagnostic_diff.txt" -f $Batch)
    if (Test-Path -LiteralPath $diagnosticPath) {
        return $diagnosticPath
    }
    return $null
}

function Select-ExecutionBlock {
    param([object[]]$Blocks)

    $stable = @($Blocks | Where-Object { $_.Name -like "*stable_no_probe_intersection*" -and $_.Fields.Contains("executor_version") })
    if ($stable.Count -gt 0) {
        return $stable[$stable.Count - 1]
    }
    $withExecution = @($Blocks | Where-Object { $_.Fields.Contains("executor_version") -or $_.Fields.Contains("execution_mode") })
    if ($withExecution.Count -gt 0) {
        return $withExecution[$withExecution.Count - 1]
    }
    return $null
}

function Get-LatestBatchId {
    param([string]$Root)

    if (-not (Test-Path -LiteralPath $Root)) {
        Write-Error ("LogRoot does not exist: {0}" -f $Root)
        exit 1
    }

    $batch = Get-ChildItem -LiteralPath $Root -File |
        Where-Object { $_.Name -match "^(\d{8}-\d{6})__" } |
        ForEach-Object {
            if ($_.Name -match "^(\d{8}-\d{6})__") {
                [pscustomobject]@{
                    BatchId = $matches[1]
                    LastWriteTime = $_.LastWriteTime
                }
            }
        } |
        Group-Object BatchId |
        ForEach-Object {
            [pscustomobject]@{
                BatchId = $_.Name
                LastWriteTime = ($_.Group | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime
            }
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if (-not $batch) {
        Write-Error ("No batch logs found under: {0}" -f $Root)
        exit 1
    }
    return $batch.BatchId
}

function Get-LatestClassifierRecord {
    param([string[]]$OutputLines)

    $fields = @{}
    foreach ($line in @($OutputLines)) {
        if ($line -match "^\|\s*(\d{8}-\d{6})\s*\|") {
            $parts = @($line.Trim("|") -split "\|" | ForEach-Object { $_.Trim() })
            if ($parts.Count -ge 9) {
                return [pscustomobject][ordered]@{
                    batch_id = $parts[0]
                    known_true_addr = $parts[1]
                    validation_profile = $parts[3]
                    baseline_eligible = $parts[4]
                    classification = $parts[7]
                    final_hit = $parts[8]
                    rank_awb = $parts[9]
                    stable_rank = $parts[10]
                    best_candidate = $parts[11]
                    recommendation = $parts[13]
                    conclusion = $parts[7]
                }
            }
        } elseif ($line -match "^(batch_id|classification|validation_profile|baseline_eligible|known_true_addr|final_hit|rank_A/W/B|stable_rank|best_candidate|recommendation|conclusion)\s+(.+?)\s*$") {
            $fields[$matches[1]] = $matches[2].Trim()
        }
    }

    if ($fields.ContainsKey("batch_id")) {
        return [pscustomobject][ordered]@{
            batch_id = $fields["batch_id"]
            known_true_addr = $fields["known_true_addr"]
            validation_profile = $fields["validation_profile"]
            baseline_eligible = $fields["baseline_eligible"]
            classification = $fields["classification"]
            final_hit = $fields["final_hit"]
            rank_awb = $fields["rank_A/W/B"]
            stable_rank = $fields["stable_rank"]
            best_candidate = $fields["best_candidate"]
            recommendation = $fields["recommendation"]
            conclusion = $fields["conclusion"]
        }
    }

    return $null
}

function Get-RegistryAppendResult {
    param([string[]]$OutputLines)

    $result = [ordered]@{
        appended_count = "not_available"
        skipped_duplicate_count = "not_available"
    }

    foreach ($line in @($OutputLines)) {
        if ($line -match "^appended_count\s*=\s*(.+)$") {
            $result.appended_count = $matches[1].Trim()
        } elseif ($line -match "^skipped_duplicate_count\s*=\s*(.+)$") {
            $result.skipped_duplicate_count = $matches[1].Trim()
        }
    }
    return [pscustomobject]$result
}

function Get-ComparisonStatus {
    param([string[]]$OutputLines)

    $status = "not_available"
    $codeChanges = "not_available"
    foreach ($line in @($OutputLines)) {
        if ($line -match "^\|\s*comparison status\s*\|\s*([^|]+?)\s*\|") {
            $status = $matches[1].Trim()
        } elseif ($line -match "^- code changes recommended:\s*(.+)$") {
            $codeChanges = $matches[1].Trim()
        }
    }

    return [pscustomobject][ordered]@{
        status = $status
        code_changes_recommended = $codeChanges
    }
}

function Get-MarkdownFieldMap {
    param([string[]]$OutputLines)

    $fields = [ordered]@{}
    foreach ($line in @($OutputLines)) {
        if ($line -match "^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|$") {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            if ($key -and $key -ne "---" -and $key -ne "field" -and -not $fields.Contains($key)) {
                $fields[$key] = $value
            }
        }
    }
    return $fields
}

function Get-RegistrySummaryFields {
    param([string[]]$OutputLines)

    $fields = Get-MarkdownFieldMap -OutputLines $OutputLines
    $summary = [ordered]@{}
    foreach ($key in @(
        "total records",
        "unique batch_id count",
        "unique known_true_addr count",
        "full success count",
        "quick_success count",
        "non-success count",
        "latest recorded_at",
        "latest batch_id"
    )) {
        if ($fields.Contains($key)) {
            $summary[$key] = $fields[$key]
        } else {
            $summary[$key] = "not_available"
        }
    }
    return $summary
}

function Write-WorkflowSummary {
    param([string]$Title, $Fields)

    Write-Output ""
    Write-Output $Title
    Write-Output ("{0,-32} {1}" -f "Field", "Value")
    Write-Output ("{0,-32} {1}" -f "-----", "-----")
    foreach ($key in $Fields.Keys) {
        Write-Output ("{0,-32} {1}" -f $key, $Fields[$key])
    }
}

function Invoke-ClassifierLatest {
    param([string]$ProfileName)

    $args = @("-Latest", "1", "-Profile", $ProfileName, "-LogRoot", $LogRoot, "-ConsoleSummary")
    return Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments $args -Capture
}

function Invoke-ClassifierAppend {
    param([string]$ProfileName)

    $args = @("-Latest", "1", "-Profile", $ProfileName, "-LogRoot", $LogRoot, "-ConsoleSummary", "-AppendRegistry")
    return Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments $args -Capture
}

$availableCommands = @(
    "prepare",
    "post-quick",
    "post-full",
    "compare-full",
    "inspect-latest",
    "status",
    "disable-execution",
    "safe-reset",
    "prepare-dry-run-write",
    "prepare-guarded-write",
    "prepare-restore",
    "post-execution"
)
if ($Help -or -not $Command) {
    Write-CommandHelp
    exit 0
}

if (-not ($availableCommands -contains $Command)) {
    Write-Warning ("Unknown command: {0}" -f $Command)
    Write-CommandHelp
    exit 1
}

Assert-ToolExists -Path $CaseConfigToolPath
Assert-ToolExists -Path $ClassifierPath

if (-not [string]::Equals($ProjectRootPath, $ExpectedProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Warning ("Active project root is {0}; expected {1}" -f $ProjectRootPath, $ExpectedProjectRoot)
}

switch ($Command) {
    "prepare" {
        if (-not $KnownTrueAddr) {
            Write-Output "ERROR: -KnownTrueAddr is required for prepare"
            exit 1
        }
        Assert-KnownTrueAddr -Value $KnownTrueAddr -CommandName "prepare"

        $args = @(
            "-Set",
            "-KnownTrueAddr", $KnownTrueAddr,
            "-TargetValuePattern", $TargetValuePattern,
            "-TargetValueFloat", $TargetValueFloat.ToString("0.0###############", [System.Globalization.CultureInfo]::InvariantCulture),
            "-DiagnosticLevel", $DiagnosticLevel,
            "-ValidationProfile", $Profile
        )
        if ($CaseId) {
            $args = @("-Set", "-CaseId", $CaseId) + @($args | Select-Object -Skip 1)
        }
        $result = Invoke-WorkflowCommand -FilePath $CaseConfigToolPath -Arguments $args -Capture
        if ($result.exit_code -ne 0) {
            exit $result.exit_code
        }

        Write-Output ""
        Write-Output "Case config has been set."
        Write-Output "Next step: manually run the CE/Lua batch runner."
        Write-Output "After the run completes, use:"
        Write-Output "  post-quick  for quick validation"
        Write-Output "  post-full   for full validation"
        exit 0
    }

    "disable-execution" {
        $result = Invoke-WorkflowCommand -FilePath $CaseConfigToolPath -Arguments @("-DisableExecution") -Capture
        if ($result.exit_code -ne 0) {
            exit $result.exit_code
        }

        Write-Output ""
        Write-Output "execution disabled"
        Write-Output "next step: normal detect/full test"
        exit 0
    }

    "safe-reset" {
        $targetRequested = $PSBoundParameters.ContainsKey("TargetValueFloat")
        if ($targetRequested) {
            $targetArgs = @("-SetTargetFloat", (Format-InvariantFloat -Value $TargetValueFloat))
            $targetResult = Invoke-WorkflowCommand -FilePath $CaseConfigToolPath -Arguments $targetArgs -Capture
            if ($targetResult.exit_code -ne 0) {
                exit $targetResult.exit_code
            }
        }

        $disableResult = Invoke-WorkflowCommand -FilePath $CaseConfigToolPath -Arguments @("-DisableExecution") -Capture
        if ($disableResult.exit_code -ne 0) {
            exit $disableResult.exit_code
        }

        $config = Read-CaseConfigMap -Path $CaseConfigPath
        Write-Output ""
        Write-WorkflowSummary -Title "Safe-Reset Summary" -Fields ([ordered]@{
            "target reset requested" = $targetRequested
            "target_value_float" = Get-ConfigField -Config $config -Key "target_value_float"
            "target_value_pattern" = Get-ConfigField -Config $config -Key "target_value_pattern"
            "execution_mode" = Get-ConfigField -Config $config -Key "execution_mode"
            "write_enabled" = Get-ConfigField -Config $config -Key "write_enabled"
            "execution_confirm_present" = [bool](Get-ConfigField -Config $config -Key "execution_confirm")
            "write-capable" = Test-ExecutionConfigWriteCapable -Config $config
            "config_path" = $CaseConfigPath
        })
        Write-Output "- safe-reset complete"
        Write-Output "- next step: normal detect/full test"
        exit 0
    }

    "prepare-dry-run-write" {
        if (-not $KnownTrueAddr) {
            Write-Output "ERROR: -KnownTrueAddr is required for prepare-dry-run-write"
            exit 1
        }
        Assert-KnownTrueAddr -Value $KnownTrueAddr -CommandName "prepare-dry-run-write"
        if (-not (Test-DoubleParameterProvided -Value $WriteValueFloat)) {
            Write-Output "ERROR: -WriteValueFloat is required for prepare-dry-run-write"
            exit 1
        }

        $setResult = Invoke-WorkflowCommand -FilePath $CaseConfigToolPath -Arguments (New-SetCaseArguments -Address $KnownTrueAddr -OptionalCaseId $CaseId -ProfileName "full") -Capture
        if ($setResult.exit_code -ne 0) {
            exit $setResult.exit_code
        }

        $dryRunArgs = @("-SetExecutionDryRun", "-WriteValueFloat", (Format-InvariantFloat -Value $WriteValueFloat), "-Profile", "full")
        $dryRunResult = Invoke-WorkflowCommand -FilePath $CaseConfigToolPath -Arguments $dryRunArgs -Capture
        if ($dryRunResult.exit_code -ne 0) {
            exit $dryRunResult.exit_code
        }

        Write-Output ""
        Write-Output "dry-run write config prepared"
        Write-Output "next step: manually run CE dofile"
        Write-Output "then run: post-full"
        exit 0
    }

    "prepare-guarded-write" {
        if (-not $ConfirmWrite) {
            Write-Output "ERROR: -ConfirmWrite is required for prepare-guarded-write"
            exit 1
        }
        if (-not $KnownTrueAddr) {
            Write-Output "ERROR: -KnownTrueAddr is required for prepare-guarded-write"
            exit 1
        }
        Assert-KnownTrueAddr -Value $KnownTrueAddr -CommandName "prepare-guarded-write"
        if (-not (Test-DoubleParameterProvided -Value $WriteValueFloat)) {
            Write-Output "ERROR: -WriteValueFloat is required for prepare-guarded-write"
            exit 1
        }

        $setResult = Invoke-WorkflowCommand -FilePath $CaseConfigToolPath -Arguments (New-SetCaseArguments -Address $KnownTrueAddr -OptionalCaseId $CaseId -ProfileName "full") -Capture
        if ($setResult.exit_code -ne 0) {
            exit $setResult.exit_code
        }

        $writeArgs = @("-SetExecutionWrite", "-WriteValueFloat", (Format-InvariantFloat -Value $WriteValueFloat), "-ConfirmWrite")
        $writeResult = Invoke-WorkflowCommand -FilePath $CaseConfigToolPath -Arguments $writeArgs -Capture
        if ($writeResult.exit_code -ne 0) {
            exit $writeResult.exit_code
        }

        Write-Output ""
        Write-Warning "this will write live memory after CE dofile if all guards pass"
        Write-Output "run CE manually only when ready"
        Write-Output "then run: post-execution"
        exit 0
    }

    "prepare-restore" {
        if (-not $BatchId) {
            Write-Output "ERROR: -BatchId is required for prepare-restore"
            exit 1
        }
        if ($EnableWrite -and -not $ConfirmWrite) {
            Write-Output "ERROR: -ConfirmWrite is required with -EnableWrite for prepare-restore"
            exit 1
        }
        if ($ConfirmWrite -and -not $EnableWrite) {
            Write-Output "ERROR: -EnableWrite is required with -ConfirmWrite for prepare-restore"
            exit 1
        }

        $restoreArgs = @("-PrepareRestoreFromBatch", $BatchId, "-LogRoot", $LogRoot, "-Apply")
        if ($EnableWrite -and $ConfirmWrite) {
            $restoreArgs += @("-EnableWrite", "-ConfirmWrite")
        }
        $restoreResult = Invoke-WorkflowCommand -FilePath $CaseConfigToolPath -Arguments $restoreArgs -Capture
        if ($restoreResult.exit_code -ne 0) {
            exit $restoreResult.exit_code
        }

        Write-Output ""
        if ($EnableWrite -and $ConfirmWrite) {
            Write-Warning "restore config is write-ready; run CE manually only when ready"
        } else {
            Write-Output "dry-run restore config prepared"
        }
        Write-Output "next step: manually run CE dofile, then run post-execution"
        exit 0
    }

    "post-execution" {
        $classify = Invoke-ClassifierLatest -ProfileName "full"
        if ($classify.exit_code -ne 0) {
            exit $classify.exit_code
        }
        $record = Get-LatestClassifierRecord -OutputLines $classify.output
        $latestBatchId = if ($record -and $record.batch_id) { $record.batch_id } else { Get-LatestBatchId -Root $LogRoot }
        $summaryPath = Get-BatchSummaryPath -Root $LogRoot -Batch $latestBatchId
        if (-not $summaryPath) {
            Write-Error ("No summary or diagnostic log found for batch {0}" -f $latestBatchId)
            exit 1
        }

        $blocks = @(Read-BatchLogBlocks -Path $summaryPath)
        $executionBlock = Select-ExecutionBlock -Blocks $blocks
        if (-not $executionBlock) {
            Write-Error ("No execution fields found in batch log: {0}" -f $summaryPath)
            exit 1
        }

        Write-WorkflowSummary -Title "Post-Execution Summary" -Fields ([ordered]@{
            "batch_id" = $latestBatchId
            "classification" = if ($record) { $record.classification } else { "not_available" }
            "final hit" = if ($record) { $record.final_hit } else { "not_available" }
            "execution_outcome" = Get-ExecutionOutcomeFromBlock -Block $executionBlock
            "execution_mode" = Get-LogField -Block $executionBlock -Key "execution_mode"
            "execution_addr" = Get-LogField -Block $executionBlock -Key "execution_addr"
            "old_value_float" = Get-LogField -Block $executionBlock -Key "old_value_float"
            "requested_write_value_float" = Get-LogField -Block $executionBlock -Key "requested_write_value_float"
            "write_attempted" = Get-LogField -Block $executionBlock -Key "write_attempted"
            "write_ok" = Get-LogField -Block $executionBlock -Key "write_ok"
            "readback_ok" = Get-LogField -Block $executionBlock -Key "readback_ok"
            "readback_float" = Get-LogField -Block $executionBlock -Key "readback_float"
            "execution_failure_class" = Get-LogField -Block $executionBlock -Key "execution_failure_class"
            "rollback_available" = Get-LogField -Block $executionBlock -Key "rollback_available"
            "source_log" = $summaryPath
        })

        $writeAttempted = Test-LogTrue (Get-LogField -Block $executionBlock -Key "write_attempted")
        $writeOk = Test-LogTrue (Get-LogField -Block $executionBlock -Key "write_ok")
        $readbackOk = Test-LogTrue (Get-LogField -Block $executionBlock -Key "readback_ok")
        if ($writeAttempted -or $writeOk -or $readbackOk) {
            Write-Output ""
            Write-Output "- execution completed or attempted"
            Write-Output "- recommended next step: test_session_tool.ps1 disable-execution"
            Write-Output "- if restore completed, also reset target to normal expected value if needed"
        }
        exit 0
    }

    "post-quick" {
        $classify = Invoke-ClassifierLatest -ProfileName "quick"
        if ($classify.exit_code -ne 0) {
            exit $classify.exit_code
        }
        $record = Get-LatestClassifierRecord -OutputLines $classify.output

        $append = Invoke-ClassifierAppend -ProfileName "quick"
        if ($append.exit_code -ne 0) {
            exit $append.exit_code
        }
        $appendResult = Get-RegistryAppendResult -OutputLines $append.output

        $quickPass = $false
        if ($record) {
            $quickPass = $record.classification -eq "quick_success"
        }

        Write-WorkflowSummary -Title "Post-Quick Summary" -Fields ([ordered]@{
            "latest batch id" = if ($record) { $record.batch_id } else { "not_available" }
            "classification" = if ($record) { $record.classification } else { "not_available" }
            "validation_profile" = if ($record) { $record.validation_profile } else { "not_available" }
            "known_true_addr" = if ($record) { $record.known_true_addr } else { "not_available" }
            "final hit true" = if ($record) { $record.final_hit } else { "not_available" }
            "rank A/W/B" = if ($record) { $record.rank_awb } else { "not_available" }
            "stable rank" = if ($record) { $record.stable_rank } else { "not_available" }
            "best_candidate" = if ($record) { $record.best_candidate } else { "not_available" }
            "recommendation" = if ($record) { $record.recommendation } else { "not_available" }
            "conclusion" = if ($record) { $record.conclusion } else { "not_available" }
            "quick_success passed" = $quickPass
            "registry appended_count" = $appendResult.appended_count
            "registry skipped_duplicate_count" = $appendResult.skipped_duplicate_count
        })
        if (-not $quickPass) {
            Write-Output "- next step: use inspect-latest"
        }
        exit 0
    }

    "post-full" {
        $classify = Invoke-ClassifierLatest -ProfileName "full"
        if ($classify.exit_code -ne 0) {
            exit $classify.exit_code
        }
        $record = Get-LatestClassifierRecord -OutputLines $classify.output

        $append = Invoke-ClassifierAppend -ProfileName "full"
        if ($append.exit_code -ne 0) {
            exit $append.exit_code
        }
        $appendResult = Get-RegistryAppendResult -OutputLines $append.output

        Write-WorkflowSummary -Title "Post-Full Summary" -Fields ([ordered]@{
            "latest batch id" = if ($record) { $record.batch_id } else { "not_available" }
            "classification" = if ($record) { $record.classification } else { "not_available" }
            "validation_profile" = if ($record) { $record.validation_profile } else { "not_available" }
            "known_true_addr" = if ($record) { $record.known_true_addr } else { "not_available" }
            "final hit true" = if ($record) { $record.final_hit } else { "not_available" }
            "baseline_eligible" = if ($record) { $record.baseline_eligible } else { "not_available" }
            "rank A/W/B" = if ($record) { $record.rank_awb } else { "not_available" }
            "stable rank" = if ($record) { $record.stable_rank } else { "not_available" }
            "best_candidate" = if ($record) { $record.best_candidate } else { "not_available" }
            "recommendation" = if ($record) { $record.recommendation } else { "not_available" }
            "conclusion" = if ($record) { $record.conclusion } else { "not_available" }
            "registry appended_count" = $appendResult.appended_count
            "registry skipped_duplicate_count" = $appendResult.skipped_duplicate_count
        })
        if ($record -and $record.classification -eq "success") {
            Write-Output "- next step: run compare-full or a baseline preset when ready"
        }
        exit 0
    }

    "compare-full" {
        $args = @("-Latest", "20", "-Profile", "full", "-OnlyBaselineEligible", "-LogRoot", $LogRoot, "-CompareTo", $BaselinePath)
        $result = Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments $args -Capture -Quiet
        if ($result.exit_code -ne 0) {
            $result.output | ForEach-Object { Write-Output $_ }
            exit $result.exit_code
        }

        $comparison = Get-ComparisonStatus -OutputLines $result.output
        Write-WorkflowSummary -Title "Compare-Full Summary" -Fields ([ordered]@{
            "batch selection" = "baseline-eligible full batches only"
            "regression status" = $comparison.status
            "code changes recommended" = $comparison.code_changes_recommended
        })
        Write-Output "- compare-full uses baseline-eligible full batches only"
        if ($comparison.status -eq "PASS" -and $comparison.code_changes_recommended -eq "no") {
            Write-Output "- no code changes recommended"
        } elseif ($comparison.status -eq "FAIL" -or $comparison.status -eq "WARN") {
            Write-Output "- next step: use inspect-latest"
        }
        exit 0
    }

    "inspect-latest" {
        $latestBatchId = Get-LatestBatchId -Root $LogRoot
        Write-Output ("Latest batch id: {0}" -f $latestBatchId)
        $args = @("-InspectBatch", $latestBatchId, "-LogRoot", $LogRoot)
        $result = Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments $args
        exit $result.exit_code
    }

    "status" {
        Write-Output "Current Case Config"
        $caseResult = Invoke-WorkflowCommand -FilePath $CaseConfigToolPath -Arguments @("-Show")
        if ($caseResult.exit_code -ne 0) {
            exit $caseResult.exit_code
        }
        $currentConfig = Read-CaseConfigMap -Path $CaseConfigPath
        Write-ExecutionConfigSafetyWarning -Config $currentConfig

        Write-Output ""
        Write-Output "Latest 5 Classifier Summary"
        $latestResult = Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments @("-Latest", "5", "-LogRoot", $LogRoot, "-ConsoleSummary")
        if ($latestResult.exit_code -ne 0) {
            exit $latestResult.exit_code
        }

        Write-Output ""
        $registryResult = Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments @("-RegistrySummary", "-LogRoot", $LogRoot) -Capture -Quiet
        if ($registryResult.exit_code -ne 0) {
            $registryResult.output | ForEach-Object { Write-Output $_ }
            exit $registryResult.exit_code
        }
        Write-WorkflowSummary -Title "Registry Summary" -Fields (Get-RegistrySummaryFields -OutputLines $registryResult.output)

        Write-Output ""
        Write-Output "Git Status"
        $gitStatus = @(& git -C $ProjectRootPath status --short)
        if ($gitStatus.Count -eq 0) {
            Write-Output "clean"
        } else {
            $gitStatus | ForEach-Object { Write-Output $_ }
        }
        exit 0
    }
}
