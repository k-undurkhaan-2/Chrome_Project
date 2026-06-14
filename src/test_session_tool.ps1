param(
    [Parameter(Position = 0)]
    [string]$Action,
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
    [switch]$ConfirmWrite,
    [switch]$TrackProcess,
    [int]$ProcessId = 0,
    [string]$ProcessName,
    [int]$IntervalSeconds = 10,
    [switch]$Once,
    [int]$Latest = 50,
    [switch]$IncludeResolved,
    [string]$Reason,
    [string]$Label,
    [string]$Name,
    [string]$Baseline,
    [string]$Level,
    [int]$TargetUnique = 0,
    [int]$MinFullSuccess = 2,
    [int]$Limit = 0,
    [switch]$ShowRejected,
    [switch]$ActiveSession
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$ExpectedProjectRoot = "D:\armedforces.io-v2"
$ProjectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd("\", "/")
$CaseConfigToolPath = Join-Path (Join-Path $ProjectRootPath "src") "case_config_tool.ps1"
$ClassifierPath = Join-Path (Join-Path $ProjectRootPath "src") "batch_log_classifier.ps1"
$CaseConfigPath = Join-Path (Join-Path $ProjectRootPath "src") "run_case_config.local.lua"
$BaselineRoot = Join-Path (Join-Path $ProjectRootPath "log") "baselines"
$BaselinePath = Join-Path $BaselineRoot "baseline_compact_basic_20260613_latest20.md"
$ResolvedWritesPath = Join-Path (Join-Path $ProjectRootPath "log") "execution_resolved_writes.local.jsonl"
$LocalLogRoot = Join-Path $ProjectRootPath "log"
$ActiveTestSessionPath = Join-Path $LocalLogRoot "active_test_session.local.json"
$TestSessionHistoryPath = Join-Path $LocalLogRoot "test_session_history.local.jsonl"
$CaseIntakePath = Join-Path $LocalLogRoot "case_intake.local.jsonl"
$ExecutionConfirmText = "I_ACCEPT_WRITE_TO_LIVE_MEMORY"

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
    Write-Output "  plan           Preview what the next manual CE/Lua run would do"
    Write-Output "  preview-next-run Alias for plan"
    Write-Output "  prepare        Set run_case_config.local.lua for the next manual CE/Lua run"
    Write-Output "  collect-prepare One-shot preflight plus current-case prepare"
    Write-Output "  prepare-collection-case Alias for collect-prepare"
    Write-Output "  prepare-current-case Guarded active-session prepare for current case collection"
    Write-Output "  prepare-case   Alias for prepare-current-case"
    Write-Output "  case-intake-status Show local prepared/completed current-case intake journal"
    Write-Output "  case-intake-abandon Abandon latest open prepared intake without running CE"
    Write-Output "  abandon-current-case Alias for case-intake-abandon"
    Write-Output "  post-current-case Safely complete the latest matching prepared current case"
    Write-Output "  post-quick     Classify latest quick batch and append registry"
    Write-Output "  post-full      Classify latest full batch and append registry"
    Write-Output "  compare-full   Compare latest 20 baseline-eligible full batches to compact baseline"
    Write-Output "  baseline-list  List local baseline Markdown files"
    Write-Output "  baseline-current Show current default compare-full baseline"
    Write-Output "  baseline-save  Save latest baseline-eligible full batch snapshot"
    Write-Output "  baseline-compare Compare against a named or full-path baseline"
    Write-Output "  case-library  Summarize historical and active-session known_true_addr evidence"
    Write-Output "  stable-cases  List stable evidence for baseline candidates"
    Write-Output "  baseline-candidates Alias for stable-cases"
    Write-Output "  retest-queue  Plan active-session retests or new current-session samples"
    Write-Output "  sample-plan   Alias for retest-queue"
    Write-Output "  case-summary   Summarize baseline-eligible case coverage"
    Write-Output "  coverage-plan  Alias for case-summary"
    Write-Output "  inspect-latest Inspect the latest batch id from -LogRoot"
    Write-Output "  status         Show config, latest 5 classifier summary, registry summary, and git status"
    Write-Output "  diagnostic-status       Show current diagnostic/logging level"
    Write-Output "  set-diagnostic          Set local diagnostic level: basic, debug, or trace"
    Write-Output "  disable-execution       Disable execution/write in local case config"
    Write-Output "  safe-reset              Disable execution and optionally reset target float"
    Write-Output "  prepare-dry-run-write   Prepare full/basic dry-run write config"
    Write-Output "  prepare-guarded-write   Prepare full/basic guarded write config"
    Write-Output "  prepare-restore         Prepare dry-run or write-ready restore config from a batch"
    Write-Output "  post-execution          Summarize latest full execution fields after manual CE run"
    Write-Output "  execution-status        Show write/restore transaction safety status"
    Write-Output "  mark-write-resolved     Mark a historical write_success as manually restored"
    Write-Output "  doctor                  Run read-only preflight and safety checks"
    Write-Output "  session-start           Start local active manual test session marker"
    Write-Output "  session-status          Show local active manual test session state"
    Write-Output "  session-end             End local active manual test session marker"
    Write-Output "  session-watch           Foreground watch for process-tracked active session"
    Write-Output "  collection-flow         Read-only guide for current-session case collection"
    Write-Output "  collect-guide           Alias for collection-flow"
    Write-Output ""
    Write-Output "Prepare options:"
    Write-Output "  -KnownTrueAddr <addr> [-CaseId <id>] [-Profile quick|full] [-DiagnosticLevel basic|debug|trace]"
    Write-Output "  collect-prepare -KnownTrueAddr <addr> [-CaseId <id>] [-Profile quick|full]"
    Write-Output "  prepare-collection-case -KnownTrueAddr <addr> [-CaseId <id>] [-Profile quick|full]"
    Write-Output "  prepare-current-case -KnownTrueAddr <addr> [-CaseId <id>] [-Profile quick|full]"
    Write-Output "  prepare-case -KnownTrueAddr <addr> [-CaseId <id>] [-Profile quick|full]"
    Write-Output "  case-intake-status"
    Write-Output "  case-intake-abandon [-Reason <text>]"
    Write-Output "  abandon-current-case [-Reason <text>]"
    Write-Output "  post-current-case"
    Write-Output "  set-diagnostic -Level basic|debug|trace"
    Write-Output "  prepare-dry-run-write -KnownTrueAddr <addr> -WriteValueFloat <float>"
    Write-Output "  prepare-guarded-write -KnownTrueAddr <addr> -WriteValueFloat <float> -ConfirmWrite"
    Write-Output "  prepare-restore -BatchId <batch> [-EnableWrite -ConfirmWrite]"
    Write-Output "  mark-write-resolved -BatchId <batch> -Reason <text>"
    Write-Output "  baseline-save -Name <safe-name> [-Latest 20]"
    Write-Output "  baseline-compare -Baseline <file-or-path> [-Latest 20]"
    Write-Output "  case-library [-Latest 100] [-Profile full|quick]"
    Write-Output "  stable-cases [-Latest 100] [-Profile full] [-MinFullSuccess 2] [-TargetUnique 13] [-ShowRejected] [-KnownTrueAddr <addr>]"
    Write-Output "  retest-queue [-Latest 200] [-Profile full] [-MinFullSuccess 2] [-TargetUnique 13] [-Limit 15] [-ActiveSession]"
    Write-Output "  sample-plan [-Latest 200] [-Profile full] [-Limit 15] [-ActiveSession]"
    Write-Output "  session-start [-Label <text>] [-TrackProcess -ProcessId <pid>|-ProcessName <name>]"
    Write-Output "  session-end [-Reason <text>]"
    Write-Output "  session-watch [-IntervalSeconds 10] [-Once]"
    Write-Output "  collection-flow"
    Write-Output "  collect-guide"
    Write-Output "  case-summary [-Latest 20] [-Profile full] [-Baseline <file-or-path>] [-TargetUnique 13]"
    Write-Output "  safe-reset [-TargetValueFloat 100.0]"
    Write-Output ""
    Write-Output "Common options:"
    Write-Output "  -ProjectRoot D:\armedforces.io-v2"
    Write-Output "  -LogRoot D:\armedforces.io-v2\log\auto_output"
    Write-Output "  plan"
    Write-Output "  preview-next-run"
    Write-Output "  execution-status [-Latest 50] [-IncludeResolved]"
    Write-Output "  doctor [-Latest 50]"
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

function Test-KnownTrueAddrMissingPrefix {
    param($Value)

    if ($null -eq $Value) {
        return $false
    }
    $text = "$Value".Trim()
    return $text -match '^[0-9A-Fa-f]+$'
}

function Get-KnownTrueAddrValidationDetails {
    param($Value)

    if (Test-KnownTrueAddrMissingPrefix -Value $Value) {
        return "KnownTrueAddr looks like a hex address without the required 0x prefix."
    }
    return "KnownTrueAddr must match ^0x[0-9A-Fa-f]+$ and must not be empty or a placeholder."
}

function Get-KnownTrueAddrValidationRecommendation {
    param($Value)

    if (Test-KnownTrueAddrMissingPrefix -Value $Value) {
        return ("Add the 0x prefix, for example 0x{0}." -f "$Value".Trim())
    }
    return "Use a current-session hex address such as 0x25A061C7D48."
}

function Test-RestoreBatchId {
    param($Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $false
    }

    $text = "$Value".Trim()
    if ($text -match '[<>]') {
        return $false
    }
    if ($text.IndexOfAny([System.IO.Path]::GetInvalidFileNameChars()) -ge 0) {
        return $false
    }
    return $text -match '^\d{8}-\d{6}$'
}

function Assert-RestoreBatchId {
    param([string]$Value, [string]$CommandName)

    if (-not (Test-RestoreBatchId -Value $Value)) {
        Write-Output ("ERROR: BatchId looks like a placeholder or invalid id for {0}: {1}" -f $CommandName, (Format-CommandPart $Value))
        Write-Output "Use a real batch id such as 20260613-225514."
        Write-Output "Find one with: powershell -NoProfile -ExecutionPolicy Bypass -File `"D:\armedforces.io-v2\src\batch_log_classifier.ps1`" -Latest 10 -Profile full -ConsoleSummary"
        exit 1
    }
}

function Assert-KnownTrueAddr {
    param([string]$Value, [string]$CommandName)

    if (-not (Test-KnownTrueAddr -Value $Value)) {
        Write-Output ("ERROR: -KnownTrueAddr for {0} is invalid; rejected value: {1}" -f $CommandName, $(if ($Value) { $Value } else { "-" }))
        Write-Output (Get-KnownTrueAddrValidationDetails -Value $Value)
        Write-Output (Get-KnownTrueAddrValidationRecommendation -Value $Value)
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

function Test-ExecutionArmPresent {
    param($Config)

    foreach ($key in @("execution_confirm", "execution_write_request_id", "execution_armed_at_utc", "execution_arm_expires_at_utc")) {
        $value = Get-ConfigField -Config $Config -Key $key
        if (Test-LogPresent -Value $value) {
            return $true
        }
    }
    return $false
}

function Test-NormalTargetConfig {
    param($Config)

    $pattern = Get-ConfigField -Config $Config -Key "target_value_pattern"
    $floatText = Get-ConfigField -Config $Config -Key "target_value_float"
    if (-not (Test-LogPresent -Value $pattern) -or -not (Test-LogPresent -Value $floatText)) {
        return $false
    }

    $normalizedPattern = "$pattern".Trim().ToUpperInvariant()
    if (-not $normalizedPattern.StartsWith("0X")) {
        $normalizedPattern = "0X$normalizedPattern"
    }

    try {
        $targetFloat = [double]::Parse("$floatText", [System.Globalization.CultureInfo]::InvariantCulture)
    } catch {
        return $false
    }

    return $normalizedPattern -eq "0X42C80000" -and ([math]::Abs($targetFloat - 100.0) -le 0.000001)
}

function Normalize-HexPattern {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }
    $text = "$Value".Trim()
    if ($text.StartsWith("0x", [System.StringComparison]::OrdinalIgnoreCase)) {
        $text = $text.Substring(2)
    }
    if ($text -notmatch '^[0-9A-Fa-f]{8}$') {
        return $null
    }
    return ("0x{0}" -f $text.ToUpperInvariant())
}

function Convert-FloatToPattern {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }
    try {
        $number = [double]::Parse("$Value", [System.Globalization.CultureInfo]::InvariantCulture)
        $bytes = [System.BitConverter]::GetBytes([single]$number)
        $u32 = [System.BitConverter]::ToUInt32($bytes, 0)
        return ("0x{0:X8}" -f $u32)
    } catch {
        return $null
    }
}

function Get-TargetConsistencyCheck {
    param($Config)

    $pattern = Normalize-HexPattern -Value (Get-ConfigField -Config $Config -Key "target_value_pattern")
    $expected = Convert-FloatToPattern -Value (Get-ConfigField -Config $Config -Key "target_value_float")
    $matches = $false
    if ($pattern -and $expected) {
        $matches = [string]::Equals($pattern, $expected, [System.StringComparison]::OrdinalIgnoreCase)
    }

    return [pscustomobject][ordered]@{
        matches = $matches
        actual_pattern = $(if ($pattern) { $pattern } else { "-" })
        expected_pattern = $(if ($expected) { $expected } else { "-" })
    }
}

function Get-ConfigDisplayValue {
    param($Config, [string]$Key, [string]$Default = "-")

    $value = Get-ConfigField -Config $Config -Key $Key
    if (Test-LogPresent -Value $value) {
        return "$value"
    }
    return $Default
}

function Test-ConfigBooleanTrue {
    param($Config, [string]$Key)

    $value = Get-ConfigField -Config $Config -Key $Key
    if ($value -is [bool]) {
        return [bool]$value
    }
    if ($null -eq $value) {
        return $false
    }
    return "$value".Trim().ToLowerInvariant() -eq "true"
}

function Convert-ConfigUtcDateTime {
    param($Value)

    if (-not (Test-LogPresent -Value $Value)) {
        return $null
    }

    try {
        return ([datetime]::Parse(
            "$Value",
            [System.Globalization.CultureInfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::RoundtripKind
        )).ToUniversalTime()
    } catch {
        try {
            return ([datetime]::Parse(
                "$Value",
                [System.Globalization.CultureInfo]::InvariantCulture,
                ([System.Globalization.DateTimeStyles]::AssumeUniversal -bor [System.Globalization.DateTimeStyles]::AdjustToUniversal)
            )).ToUniversalTime()
        } catch {
            return $null
        }
    }
}

function Get-ExecutionArmPreview {
    param($Config, [bool]$WriteMode)

    $requestId = Get-ConfigField -Config $Config -Key "execution_write_request_id"
    $armedAt = Get-ConfigField -Config $Config -Key "execution_armed_at_utc"
    $expiresAt = Get-ConfigField -Config $Config -Key "execution_arm_expires_at_utc"
    $hasAnyArmField = (Test-LogPresent -Value $requestId) -or (Test-LogPresent -Value $armedAt) -or (Test-LogPresent -Value $expiresAt)
    $hasAllArmFields = (Test-LogPresent -Value $requestId) -and (Test-LogPresent -Value $armedAt) -and (Test-LogPresent -Value $expiresAt)

    if (-not $hasAnyArmField -and -not $WriteMode) {
        return [pscustomobject][ordered]@{
            valid = "unknown"
            seconds_remaining = "-"
            reason = "not_required"
            malformed = $false
        }
    }

    if (-not $hasAllArmFields) {
        return [pscustomobject][ordered]@{
            valid = "false"
            seconds_remaining = "-"
            reason = "missing_execution_arm"
            malformed = $false
        }
    }

    $expiresAtUtc = Convert-ConfigUtcDateTime -Value $expiresAt
    if (-not $expiresAtUtc) {
        return [pscustomobject][ordered]@{
            valid = "false"
            seconds_remaining = "-"
            reason = "invalid_execution_arm"
            malformed = $true
        }
    }

    $secondsRemaining = ($expiresAtUtc - [datetime]::UtcNow).TotalSeconds
    $secondsText = ([math]::Round($secondsRemaining, 1)).ToString("0.0", [System.Globalization.CultureInfo]::InvariantCulture)
    if ($secondsRemaining -le 0) {
        return [pscustomobject][ordered]@{
            valid = "false"
            seconds_remaining = $secondsText
            reason = "execution_arm_expired"
            malformed = $false
        }
    }

    return [pscustomobject][ordered]@{
        valid = "true"
        seconds_remaining = $secondsText
        reason = "active"
        malformed = $false
    }
}

function Get-NextRunPlan {
    $configExists = Test-Path -LiteralPath $CaseConfigPath
    $config = Read-CaseConfigMap -Path $CaseConfigPath
    $targetConsistency = Get-TargetConsistencyCheck -Config $config

    $diagnosticLevel = Get-ConfigDisplayValue -Config $config -Key "diagnostic_level"
    $executionMode = Get-ConfigDisplayValue -Config $config -Key "execution_mode" -Default "disabled"
    $executionModeLower = "$executionMode".Trim().ToLowerInvariant()
    $writeEnabled = Test-ConfigBooleanTrue -Config $config -Key "write_enabled"
    $executionConfirm = Get-ConfigField -Config $config -Key "execution_confirm"
    $executionConfirmPresent = Test-LogPresent -Value $executionConfirm
    $executionConfirmOk = $executionConfirmPresent -and [string]::Equals("$executionConfirm", $ExecutionConfirmText, [System.StringComparison]::Ordinal)
    $executionAddrSource = Get-ConfigDisplayValue -Config $config -Key "execution_addr_source" -Default "stable_intersection_best_candidate"
    $armPreview = Get-ExecutionArmPreview -Config $config -WriteMode ($executionModeLower -eq "write")
    $armPresent = Test-ExecutionArmPresent -Config $config

    $targetFloatPresent = Test-LogPresent -Value (Get-ConfigField -Config $config -Key "target_value_float")
    $targetPatternPresent = Test-LogPresent -Value (Get-ConfigField -Config $config -Key "target_value_pattern")
    $criticalMalformed = $executionModeLower -eq "write" -and [bool]$armPreview.malformed
    $targetConfigValid = $configExists -and $targetFloatPresent -and $targetPatternPresent -and [bool]$targetConsistency.matches

    $nextRunType = "detect_only"
    $dangerLevel = "SAFE"
    $recommendedNextStep = "Run CE if you want a detect-only batch, then post-full/post-quick."

    if (-not $targetConfigValid -or $criticalMalformed) {
        $nextRunType = "invalid_config"
        $dangerLevel = "FAIL"
        $recommendedNextStep = "Run safe-reset -TargetValueFloat 100.0 or fix config before CE."
    } elseif ($executionModeLower -eq "dry_run") {
        $nextRunType = "dry_run"
        $dangerLevel = "ATTENTION"
        $recommendedNextStep = "Run CE for dry-run validation only, then post-execution."
    } elseif ($executionModeLower -eq "write") {
        if (-not $writeEnabled -or -not $executionConfirmOk -or $armPreview.valid -ne "true") {
            $nextRunType = "write_blocked_by_config"
            $dangerLevel = "ATTENTION"
            $recommendedNextStep = "Run safe-reset or prepare the write/restore again."
        } elseif ([string]::Equals($executionAddrSource, "restore_source_batch_execution_addr", [System.StringComparison]::OrdinalIgnoreCase)) {
            $nextRunType = "restore_write"
            $dangerLevel = "WRITE_CAPABLE"
            $recommendedNextStep = "Run CE before arm expiry, then post-execution. Then safe-reset -TargetValueFloat 100.0."
        } else {
            $nextRunType = "guarded_write"
            $dangerLevel = "WRITE_CAPABLE"
            $recommendedNextStep = "Run CE before arm expiry, then post-execution. Restore immediately after write_success."
        }
    } elseif ($writeEnabled -or $executionConfirmPresent) {
        $nextRunType = "write_blocked_by_config"
        $dangerLevel = "ATTENTION"
        $recommendedNextStep = "Run safe-reset or prepare the write/restore again."
    } elseif ($armPresent) {
        $nextRunType = "detect_only"
        $dangerLevel = "ATTENTION"
        $recommendedNextStep = "Run safe-reset or prepare the write/restore again."
    }

    if ([string]::Equals($diagnosticLevel, "trace", [System.StringComparison]::OrdinalIgnoreCase)) {
        $recommendedNextStep = "{0} Trace diagnostics are enabled; reset to basic after this investigation." -f $recommendedNextStep
    }

    $fields = [ordered]@{
        "config path" = $CaseConfigPath
        "config exists" = $configExists
        "validation_profile" = Get-ConfigDisplayValue -Config $config -Key "validation_profile"
        "diagnostic_level" = $diagnosticLevel
        "known_true_addr" = Get-ConfigDisplayValue -Config $config -Key "known_true_addr"
        "target_value_float" = Get-ConfigDisplayValue -Config $config -Key "target_value_float"
        "target_value_pattern" = Get-ConfigDisplayValue -Config $config -Key "target_value_pattern"
        "expected pattern from float" = $targetConsistency.expected_pattern
        "target config consistent" = [bool]$targetConsistency.matches
        "execution_mode" = $executionMode
        "write_enabled" = $writeEnabled
        "execution_confirm present" = $executionConfirmPresent
        "execution_confirm_ok" = $executionConfirmOk
        "execution_addr_source" = $executionAddrSource
        "write_value_float" = Get-ConfigDisplayValue -Config $config -Key "write_value_float"
        "write_value_pattern" = Get-ConfigDisplayValue -Config $config -Key "write_value_pattern"
        "restore_source_batch_id" = Get-ConfigDisplayValue -Config $config -Key "restore_source_batch_id"
        "restore_execution_addr" = Get-ConfigDisplayValue -Config $config -Key "restore_execution_addr"
        "restore_expected_current_float" = Get-ConfigDisplayValue -Config $config -Key "restore_expected_current_float"
        "restore_expected_current_pattern" = Get-ConfigDisplayValue -Config $config -Key "restore_expected_current_pattern"
        "restore_write_value_float" = Get-ConfigDisplayValue -Config $config -Key "restore_write_value_float"
        "restore_write_value_pattern" = Get-ConfigDisplayValue -Config $config -Key "restore_write_value_pattern"
        "execution_write_request_id" = Get-ConfigDisplayValue -Config $config -Key "execution_write_request_id"
        "execution_armed_at_utc" = Get-ConfigDisplayValue -Config $config -Key "execution_armed_at_utc"
        "execution_arm_expires_at_utc" = Get-ConfigDisplayValue -Config $config -Key "execution_arm_expires_at_utc"
        "execution_arm_valid" = $armPreview.valid
        "execution_arm_seconds_remaining" = $armPreview.seconds_remaining
        "next_run_type" = $nextRunType
        "danger_level" = $dangerLevel
        "recommended_next_step" = $recommendedNextStep
    }

    return [pscustomobject][ordered]@{
        fields = $fields
        danger_level = $dangerLevel
        next_run_type = $nextRunType
        exit_code = $(if ($dangerLevel -eq "FAIL" -or $nextRunType -eq "invalid_config") { 1 } else { 0 })
    }
}

function Write-NextRunPlan {
    param($Plan)

    Write-WorkflowSummary -Title "Next Run Plan" -Fields $Plan.fields
}

function Get-DiagnosticRecommendation {
    param([string]$LevelValue)

    if ([string]::Equals($LevelValue, "basic", [System.StringComparison]::OrdinalIgnoreCase)) {
        return "OK for daily runs."
    }
    if ([string]::Equals($LevelValue, "debug", [System.StringComparison]::OrdinalIgnoreCase)) {
        return "Use only for targeted investigation; reset to basic after diagnosis."
    }
    if ([string]::Equals($LevelValue, "trace", [System.StringComparison]::OrdinalIgnoreCase)) {
        return "High verbosity; trace logs can be large. Reset to basic after diagnosis."
    }
    return "Unknown diagnostic level; use set-diagnostic -Level basic."
}

function Get-DiagnosticDoctorStatus {
    param([string]$LevelValue)

    if ([string]::Equals($LevelValue, "basic", [System.StringComparison]::OrdinalIgnoreCase)) {
        return [pscustomobject][ordered]@{ status = "PASS"; detail = "basic daily logging" }
    }
    if ([string]::Equals($LevelValue, "debug", [System.StringComparison]::OrdinalIgnoreCase)) {
        return [pscustomobject][ordered]@{ status = "WARN"; detail = "debug enabled; use only for investigation" }
    }
    if ([string]::Equals($LevelValue, "trace", [System.StringComparison]::OrdinalIgnoreCase)) {
        return [pscustomobject][ordered]@{ status = "WARN"; detail = "trace enabled; reset to basic after investigation" }
    }
    return [pscustomobject][ordered]@{ status = "FAIL"; detail = "invalid diagnostic_level" }
}

function Get-LatestLogSizeSummary {
    param([string]$Root)

    $empty = [pscustomobject][ordered]@{
        latest_batch_id = "not_available"
        latest_batch_file_count = 0
        latest_batch_log_size_bytes = "not_available"
        latest_batch_last_write_time = "not_available"
    }

    if (-not (Test-Path -LiteralPath $Root)) {
        return $empty
    }

    $files = @(Get-ChildItem -LiteralPath $Root -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "^(\d{8}-\d{6})__" })
    if ($files.Count -eq 0) {
        return $empty
    }

    $latestGroup = $files |
        ForEach-Object {
            if ($_.Name -match "^(\d{8}-\d{6})__") {
                [pscustomobject]@{
                    BatchId = $matches[1]
                    File = $_
                    LastWriteTime = $_.LastWriteTime
                }
            }
        } |
        Group-Object BatchId |
        ForEach-Object {
            [pscustomobject]@{
                BatchId = $_.Name
                Files = @($_.Group | ForEach-Object { $_.File })
                LastWriteTime = ($_.Group | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime
            }
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if (-not $latestGroup) {
        return $empty
    }

    $sizeBytes = 0L
    foreach ($file in @($latestGroup.Files)) {
        $sizeBytes += [int64]$file.Length
    }

    return [pscustomobject][ordered]@{
        latest_batch_id = $latestGroup.BatchId
        latest_batch_file_count = @($latestGroup.Files).Count
        latest_batch_log_size_bytes = $sizeBytes
        latest_batch_last_write_time = $latestGroup.LastWriteTime
    }
}

function Write-DiagnosticStatus {
    $config = Read-CaseConfigMap -Path $CaseConfigPath
    $diagnosticLevelValue = Get-ConfigDisplayValue -Config $config -Key "diagnostic_level"
    $logSummary = Get-LatestLogSizeSummary -Root $LogRoot

    Write-WorkflowSummary -Title "Diagnostic Status" -Fields ([ordered]@{
        "current diagnostic_level" = $diagnosticLevelValue
        "validation_profile" = Get-ConfigDisplayValue -Config $config -Key "validation_profile"
        "execution_mode" = Get-ConfigDisplayValue -Config $config -Key "execution_mode" -Default "disabled"
        "log root" = $LogRoot
        "latest batch id" = $logSummary.latest_batch_id
        "latest batch file count" = $logSummary.latest_batch_file_count
        "latest batch log_size_bytes" = $logSummary.latest_batch_log_size_bytes
        "latest batch last_write_time" = $logSummary.latest_batch_last_write_time
        "recommendation" = Get-DiagnosticRecommendation -LevelValue $diagnosticLevelValue
    })
}

function New-DoctorCheck {
    param([string]$Check, [string]$Status, [string]$Details)

    return [pscustomobject][ordered]@{
        Check = $Check
        Status = $Status
        Details = $Details
    }
}

function Write-DoctorReport {
    param([object[]]$Checks, [string]$Conclusion)

    $checkWidth = 42
    $statusWidth = 9
    Write-Output ""
    Write-Output "Session Doctor"
    Write-Output ("{0,-$checkWidth} {1,-$statusWidth} {2}" -f "Check", "Status", "Details")
    Write-Output ("{0,-$checkWidth} {1,-$statusWidth} {2}" -f "-----", "------", "-------")
    foreach ($item in @($Checks)) {
        Write-Output ("{0,-$checkWidth} {1,-$statusWidth} {2}" -f $item.Check, $item.Status, $item.Details)
    }
    Write-Output ""
    Write-Output ("conclusion = {0}" -f $Conclusion)
}

function Get-DoctorConclusion {
    param([object[]]$Checks)

    if (@($Checks | Where-Object { $_.Status -eq "FAIL" }).Count -gt 0) {
        return "FAIL"
    }
    if (@($Checks | Where-Object { $_.Status -eq "WARN" }).Count -gt 0) {
        return "ATTENTION"
    }
    return "SAFE"
}

function Invoke-DoctorPowerShellFile {
    param([string]$FilePath, [string[]]$Arguments)

    $output = @(& powershell -NoProfile -ExecutionPolicy Bypass -File $FilePath @Arguments 2>&1)
    return [pscustomobject][ordered]@{
        exit_code = $LASTEXITCODE
        output = @($output | ForEach-Object { "$_" })
    }
}

function Test-GitIgnoredPath {
    param([string]$Path)

    $null = @(& git -C $ProjectRootPath check-ignore -q -- $Path 2>&1)
    return $LASTEXITCODE -eq 0
}

function Get-StagedLocalSafetyFiles {
    return @(& git -C $ProjectRootPath diff --cached --name-only -- src/run_case_config.local.lua log 2>&1 | ForEach-Object { "$_" })
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

function Get-RestoreSourceBatchIdFromText {
    param($Value)

    if (-not (Test-LogPresent -Value $Value)) {
        return $null
    }
    $text = "$Value"
    if ($text -match 'restore_(\d{8})[_-](\d{6})(?:_|$)') {
        return ("{0}-{1}" -f $matches[1], $matches[2])
    }
    return $null
}

function Get-RestoreSourceBatchIdFromBlock {
    param($Block)

    $source = Get-LogField -Block $Block -Key "restore_source_batch_id"
    if (Test-LogPresent -Value $source) {
        return $source
    }
    return Get-RestoreSourceBatchIdFromText -Value ($Block.Name)
}

function Get-TransactionTypeFromBlock {
    param($Block)

    $mode = Get-LogField -Block $Block -Key "execution_mode"
    $outcome = Get-ExecutionOutcomeFromBlock -Block $Block
    $restoreSource = Get-RestoreSourceBatchIdFromBlock -Block $Block
    $failureClass = Get-LogField -Block $Block -Key "execution_failure_class"

    if (-not (Test-LogPresent -Value $mode) -or $mode -eq "disabled") {
        return "detect_only"
    }
    if ($mode -eq "dry_run") {
        return "dry_run"
    }
    if ($outcome -eq "execution_write_ok" -and (Test-LogPresent -Value $restoreSource)) {
        return "restore_success"
    }
    if ($outcome -eq "execution_write_ok") {
        return "write_success"
    }
    if ($outcome -eq "execution_write_blocked" -and (Test-LogPresent -Value $restoreSource)) {
        return "restore_blocked"
    }
    if ($outcome -eq "execution_write_blocked") {
        return "write_blocked"
    }
    if (Test-LogPresent -Value $failureClass) {
        return "execution_failed"
    }
    return "unknown"
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

function Get-ClassifierConsoleRecords {
    param([string[]]$OutputLines)

    $records = @()
    $current = $null

    foreach ($line in @($OutputLines)) {
        $text = "$line"
        if ($text -match '^\s*Batch Summary\s*$') {
            if ($null -ne $current -and $current.Count -gt 0) {
                $records += [pscustomobject]$current
            }
            $current = [ordered]@{}
            continue
        }

        if ($null -ne $current -and $text -match '^\s*([A-Za-z0-9_\/ -]+?)\s{2,}(.+?)\s*$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            if ($key -and $key -ne "Field" -and $key -ne "-----") {
                $current[$key] = $value
            }
        }
    }

    if ($null -ne $current -and $current.Count -gt 0) {
        $records += [pscustomobject]$current
    }
    return $records
}

function Get-RecordField {
    param($Record, [string]$Key, [string]$Default = "-")

    if ($null -eq $Record) {
        return $Default
    }
    $property = $Record.PSObject.Properties[$Key]
    if ($null -eq $property) {
        return $Default
    }
    if (-not (Test-LogPresent -Value $property.Value)) {
        return $Default
    }
    return $property.Value
}

function Get-UnpairedWriteRecords {
    param([object[]]$Records)

    $restoredSourceBatches = @{}
    foreach ($record in @($Records)) {
        if ((Get-RecordField -Record $record -Key "transaction_type") -eq "restore_success") {
            $restoreSource = Get-RecordField -Record $record -Key "restore_source_batch"
            if (Test-LogPresent -Value $restoreSource) {
                $restoredSourceBatches[$restoreSource] = $true
            }
        }
    }

    $unpaired = @()
    foreach ($record in @($Records)) {
        $batchId = Get-RecordField -Record $record -Key "batch_id"
        if ((Get-RecordField -Record $record -Key "transaction_type") -eq "write_success" -and -not $restoredSourceBatches.ContainsKey($batchId)) {
            $unpaired += $record
        }
    }
    return $unpaired
}

function Read-ResolvedWriteRecords {
    param([string]$Path)

    $records = @()
    if (-not (Test-Path -LiteralPath $Path)) {
        return $records
    }

    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $Path) {
        $lineNumber += 1
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        try {
            $record = $line | ConvertFrom-Json
        } catch {
            Write-Warning ("Skipping invalid resolved write JSONL line {0}: {1}" -f $lineNumber, $Path)
            continue
        }

        $batchId = Get-RecordField -Record $record -Key "batch_id"
        if (Test-RestoreBatchId -Value $batchId) {
            $records += $record
        } else {
            Write-Warning ("Skipping resolved write record with invalid batch_id on line {0}: {1}" -f $lineNumber, $Path)
        }
    }
    return $records
}

function New-ResolvedBatchSet {
    param([object[]]$Records)

    $set = @{}
    foreach ($record in @($Records)) {
        $batchId = Get-RecordField -Record $record -Key "batch_id"
        if (Test-RestoreBatchId -Value $batchId) {
            $set[$batchId] = $true
        }
    }
    return $set
}

function Get-ResolvedWriteRecord {
    param([object[]]$Records, [string]$Batch)

    foreach ($record in @($Records)) {
        if ((Get-RecordField -Record $record -Key "batch_id") -eq $Batch) {
            return $record
        }
    }
    return $null
}

function Add-ResolvedWriteRecord {
    param([string]$Path, [string]$Batch, [string]$ResolutionReason)

    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }

    $record = [pscustomobject][ordered]@{
        batch_id = $Batch
        resolved_at_utc = [System.DateTime]::UtcNow.ToString("o", [System.Globalization.CultureInfo]::InvariantCulture)
        reason = $ResolutionReason
        source = "manual"
        tool = "test_session_tool.ps1"
    }
    $json = $record | ConvertTo-Json -Compress
    Add-Content -LiteralPath $Path -Value $json -Encoding UTF8
    return $record
}

function New-RestoreCommand {
    param([string]$Batch)

    $workflowPath = Join-Path (Join-Path $ProjectRootPath "src") "test_session_tool.ps1"
    return ('powershell -NoProfile -ExecutionPolicy Bypass -File "{0}" prepare-restore -BatchId "{1}" -EnableWrite -ConfirmWrite' -f $workflowPath, $Batch)
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

    $fieldWidth = 40
    Write-Output ""
    Write-Output $Title
    Write-Output ("{0,-$fieldWidth} {1}" -f "Field", "Value")
    Write-Output ("{0,-$fieldWidth} {1}" -f "-----", "-----")
    foreach ($key in $Fields.Keys) {
        Write-Output ("{0,-$fieldWidth} {1}" -f $key, $Fields[$key])
    }
}

function Get-AlignedSummaryFieldMap {
    param([string[]]$OutputLines)

    $fields = @{}
    foreach ($line in @($OutputLines)) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        if ($line -match '^\s*(Field|-----)\s+(.+?)\s*$') {
            continue
        }
        if ($line -match '^\s*(.+?)\s{2,}(.+?)\s*$') {
            $fields[$matches[1].Trim()] = $matches[2].Trim()
        }
    }
    return $fields
}

function Get-TestSessionToolScriptPath {
    if (Test-LogPresent -Value $PSCommandPath) {
        return $PSCommandPath
    }
    if (Test-LogPresent -Value $MyInvocation.MyCommand.Path) {
        return $MyInvocation.MyCommand.Path
    }
    return (Join-Path (Join-Path $ProjectRootPath "src") "test_session_tool.ps1")
}

function Write-AddressLifetimeNote {
    param(
        [string]$Mode = "historical",
        [bool]$ActiveSessionConfirmed = $false
    )

    Write-Output ""
    Write-Output "Known True Address Lifetime"
    Write-Output ("{0,-36} {1}" -f "Field", "Value")
    Write-Output ("{0,-36} {1}" -f "-----", "-----")
    Write-Output ("{0,-36} {1}" -f "active session confirmed", $ActiveSessionConfirmed)
    Write-Output ("{0,-36} {1}" -f "scope", "known_true_addr values are reusable only within the same active manual test session")
    if ($Mode -eq "retest") {
        if ($ActiveSessionConfirmed) {
            Write-Output ("{0,-36} {1}" -f "planner mode", "prepare guidance is limited to addresses observed/intaked in the current active session")
        } else {
            Write-Output ("{0,-36} {1}" -f "planner mode", "historical evidence mode; collect new current-session addresses if the session ended")
        }
    } elseif ($Mode -eq "stable") {
        Write-Output ("{0,-36} {1}" -f "stable meaning", "stable evidence in collected logs, not permanent address validity")
    } else {
        Write-Output ("{0,-36} {1}" -f "after session end", "treat addresses as historical evidence only")
    }
}

function Get-UtcTimestampText {
    return (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ", [System.Globalization.CultureInfo]::InvariantCulture)
}

function Format-UtcTimestamp {
    param([datetime]$Value)

    return $Value.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ", [System.Globalization.CultureInfo]::InvariantCulture)
}

function Get-ObjectField {
    param($Object, [string]$Key, $Default = $null)

    if ($null -eq $Object) {
        return $Default
    }
    $property = $Object.PSObject.Properties[$Key]
    if ($property) {
        return $property.Value
    }
    return $Default
}

function Test-ObjectBooleanTrue {
    param($Object, [string]$Key)

    $value = Get-ObjectField -Object $Object -Key $Key -Default $false
    if ($value -is [bool]) {
        return [bool]$value
    }
    if ($null -eq $value) {
        return $false
    }
    return "$value".Trim().ToLowerInvariant() -eq "true"
}

function Get-SessionAgeText {
    param($Session)

    $startedAt = Convert-ConfigUtcDateTime -Value (Get-ObjectField -Object $Session -Key "started_at_utc")
    if (-not $startedAt) {
        return "-"
    }
    $age = (Get-Date).ToUniversalTime() - $startedAt
    if ($age.TotalSeconds -lt 0) {
        return "0s"
    }
    return ("{0}d {1:00}:{2:00}:{3:00}" -f [int]$age.TotalDays, $age.Hours, $age.Minutes, $age.Seconds)
}

function Ensure-LocalLogRoot {
    if (-not (Test-Path -LiteralPath $LocalLogRoot)) {
        New-Item -ItemType Directory -Path $LocalLogRoot -Force | Out-Null
    }
}

function Read-ActiveTestSession {
    if (-not (Test-Path -LiteralPath $ActiveTestSessionPath)) {
        return $null
    }
    try {
        return (Get-Content -LiteralPath $ActiveTestSessionPath -Raw | ConvertFrom-Json)
    } catch {
        return [pscustomobject][ordered]@{
            status = "invalid"
            session_id = "-"
            started_at_utc = $null
            ended_at_utc = $null
            label = "-"
            reason = "invalid session json"
            tool = "test_session_tool.ps1"
        }
    }
}

function Test-ActiveTestSession {
    param($Session)

    return (Get-ObjectField -Object $Session -Key "status") -eq "active"
}

function Write-ActiveTestSession {
    param($Session)

    Ensure-LocalLogRoot
    $json = $Session | ConvertTo-Json -Depth 5
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            $json | Set-Content -LiteralPath $ActiveTestSessionPath -Encoding UTF8
            return
        } catch {
            if ($attempt -eq 3) {
                throw
            }
            Start-Sleep -Milliseconds 200
        }
    }
}

function Append-TestSessionHistory {
    param($Session)

    Ensure-LocalLogRoot
    $line = $Session | ConvertTo-Json -Depth 5 -Compress
    Add-Content -LiteralPath $TestSessionHistoryPath -Value $line -Encoding UTF8
}

function New-CaseIntakeId {
    $idStamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss", [System.Globalization.CultureInfo]::InvariantCulture)
    $suffix = ([guid]::NewGuid().ToString("N")).Substring(0, 8)
    return "intake_{0}_{1}" -f $idStamp, $suffix
}

function Add-CaseIntakeEvent {
    param($Record)

    Ensure-LocalLogRoot
    $line = $Record | ConvertTo-Json -Depth 6 -Compress
    Add-Content -LiteralPath $CaseIntakePath -Value $line -Encoding UTF8
}

function Read-CaseIntakeEvents {
    param([string]$Path = $CaseIntakePath)

    $records = @()
    if (-not (Test-Path -LiteralPath $Path)) {
        return $records
    }

    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $Path) {
        $lineNumber += 1
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        try {
            $record = $line | ConvertFrom-Json
            $record | Add-Member -NotePropertyName journal_line -NotePropertyValue $lineNumber -Force
            $records += $record
        } catch {
            Write-Warning ("Skipping invalid case intake JSONL line {0}: {1}" -f $lineNumber, $Path)
        }
    }
    return $records
}

function Get-CaseIntakePreparedEvents {
    param([object[]]$Events)

    return @($Events | Where-Object { (Get-ObjectField -Object $_ -Key "event_type") -eq "prepared" })
}

function Get-CaseIntakeCompletedEvents {
    param([object[]]$Events)

    return @($Events | Where-Object { (Get-ObjectField -Object $_ -Key "event_type") -eq "completed" })
}

function Get-CaseIntakeAbandonedEvents {
    param([object[]]$Events)

    return @($Events | Where-Object { (Get-ObjectField -Object $_ -Key "event_type") -eq "abandoned" })
}

function New-CaseIntakeClosedSet {
    param([object[]]$Events)

    $set = @{}
    $closedEvents = @()
    $closedEvents += @(Get-CaseIntakeCompletedEvents -Events $Events)
    $closedEvents += @(Get-CaseIntakeAbandonedEvents -Events $Events)
    foreach ($event in $closedEvents) {
        $intakeId = Get-ObjectField -Object $event -Key "intake_id" -Default $null
        if (Test-LogPresent -Value $intakeId) {
            $set[$intakeId] = $true
        }
    }
    return $set
}

function Get-CaseIntakeOpenPreparedEvents {
    param([object[]]$Events)

    $closedSet = New-CaseIntakeClosedSet -Events $Events
    return @(
        Get-CaseIntakePreparedEvents -Events $Events |
            Where-Object {
                $intakeId = Get-ObjectField -Object $_ -Key "intake_id" -Default $null
                (Test-LogPresent -Value $intakeId) -and -not $closedSet.ContainsKey($intakeId)
            }
    )
}

function Add-CurrentSessionAddressEvidence {
    param([hashtable]$Map, $Address, [string]$Source)

    if (-not (Test-KnownTrueAddr -Value $Address)) {
        return
    }
    $key = "$Address".Trim().ToUpperInvariant()
    $sources = @()
    if ($Map.ContainsKey($key)) {
        $sources = @($Map[$key])
    }
    if (@($sources | Where-Object { $_ -eq $Source }).Count -eq 0) {
        $sources += $Source
    }
    $Map[$key] = $sources
}

function Get-CurrentSessionAddressEvidenceMap {
    param($Session, [object[]]$Rows)

    $map = @{}
    if (-not (Test-ActiveTestSession -Session $Session)) {
        return $map
    }

    $sessionId = Get-ObjectField -Object $Session -Key "session_id" -Default $null
    if (Test-LogPresent -Value $sessionId) {
        $events = @(Read-CaseIntakeEvents)
        $sessionIntakeEvents = @()
        $sessionIntakeEvents += @(Get-CaseIntakePreparedEvents -Events $events)
        $sessionIntakeEvents += @(Get-CaseIntakeCompletedEvents -Events $events)
        foreach ($event in $sessionIntakeEvents) {
            $eventSessionId = Get-ObjectField -Object $event -Key "session_id" -Default ""
            if (-not [string]::Equals("$eventSessionId", "$sessionId", [System.StringComparison]::Ordinal)) {
                continue
            }
            $eventType = Get-ObjectField -Object $event -Key "event_type" -Default "intake"
            Add-CurrentSessionAddressEvidence -Map $map -Address (Get-ObjectField -Object $event -Key "known_true_addr") -Source ("intake_{0}" -f $eventType)
        }
    }

    $startedAt = Convert-ConfigUtcDateTime -Value (Get-ObjectField -Object $Session -Key "started_at_utc")
    if ($startedAt) {
        foreach ($row in @($Rows)) {
            $batchId = Get-ObjectField -Object $row -Key "latest_full_batch" -Default "-"
            if (-not (Test-RestoreBatchId -Value $batchId)) {
                continue
            }
            $summaryPath = Get-BatchSummaryPath -Root $LogRoot -Batch $batchId
            if (-not $summaryPath) {
                continue
            }
            $batchFile = Get-Item -LiteralPath $summaryPath
            if ($batchFile.LastWriteTimeUtc -ge $startedAt) {
                Add-CurrentSessionAddressEvidence -Map $map -Address (Get-ObjectField -Object $row -Key "known_true_addr") -Source "batch_after_session_start"
            }
        }
    }

    return $map
}

function Get-CurrentSessionAddressSource {
    param([hashtable]$Map, $Address)

    if (-not (Test-KnownTrueAddr -Value $Address)) {
        return "-"
    }
    $key = "$Address".Trim().ToUpperInvariant()
    if (-not $Map.ContainsKey($key)) {
        return "-"
    }
    return (@($Map[$key]) | Sort-Object -Unique) -join "; "
}

function Get-LatestCaseIntakeEvent {
    param([object[]]$Events, [string]$EventType)

    $matches = @($Events | Where-Object { (Get-ObjectField -Object $_ -Key "event_type") -eq $EventType })
    if ($matches.Count -eq 0) {
        return $null
    }
    return $matches[$matches.Count - 1]
}

function New-ActiveTestSession {
    param([string]$SessionLabel, $TrackedProcess)

    $now = Get-UtcTimestampText
    $idStamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss", [System.Globalization.CultureInfo]::InvariantCulture)
    $suffix = ([guid]::NewGuid().ToString("N")).Substring(0, 8)
    $session = [ordered]@{
        session_id = "session_{0}_{1}" -f $idStamp, $suffix
        status = "active"
        started_at_utc = $now
        ended_at_utc = $null
        label = $(if (Test-LogPresent -Value $SessionLabel) { $SessionLabel } else { "" })
        reason = $null
        tool = "test_session_tool.ps1"
        process_tracking_enabled = $false
    }
    if ($TrackedProcess) {
        $session["process_tracking_enabled"] = $true
        $session["process_id"] = $TrackedProcess.process_id
        $session["process_name"] = $TrackedProcess.process_name
        $session["process_start_time"] = $TrackedProcess.process_start_time
    }
    return [pscustomobject]$session
}

function Resolve-TrackedProcess {
    if (-not $TrackProcess) {
        return $null
    }

    if ($ProcessId -le 0 -and -not (Test-LogPresent -Value $ProcessName)) {
        Write-Output "ERROR: -TrackProcess requires -ProcessId or -ProcessName."
        exit 1
    }

    $process = $null
    if ($ProcessId -gt 0) {
        try {
            $process = Get-Process -Id $ProcessId -ErrorAction Stop
        } catch {
            Write-Output ("ERROR: tracked process id does not exist: {0}" -f $ProcessId)
            exit 1
        }
    } else {
        $matches = @(Get-Process | Where-Object { $_.ProcessName -eq $ProcessName })
        if ($matches.Count -eq 0) {
            Write-Output ("ERROR: tracked process name does not exist: {0}" -f $ProcessName)
            exit 1
        }
        if ($matches.Count -gt 1) {
            Write-Output ("ERROR: process name matched multiple processes: {0}" -f $ProcessName)
            Write-Output "Use -ProcessId to choose one process explicitly."
            exit 1
        }
        $process = $matches[0]
    }

    try {
        $startTime = Format-UtcTimestamp -Value $process.StartTime
    } catch {
        Write-Output ("ERROR: unable to read process start time for process id {0}" -f $process.Id)
        exit 1
    }

    return [pscustomobject][ordered]@{
        process_id = [int]$process.Id
        process_name = $process.ProcessName
        process_start_time = $startTime
    }
}

function Get-TrackedProcessState {
    param($Session)

    $enabled = Test-ObjectBooleanTrue -Object $Session -Key "process_tracking_enabled"
    $processIdValue = Get-ObjectField -Object $Session -Key "process_id" -Default $null
    $expectedStart = Get-ObjectField -Object $Session -Key "process_start_time" -Default $null
    $processName = Get-ObjectField -Object $Session -Key "process_name" -Default "-"
    $alive = $false
    $match = $false
    $currentStart = "-"
    $failureReason = $null

    if (-not $enabled) {
        return [pscustomobject][ordered]@{
            process_tracking_enabled = $false
            process_id = $(if ($processIdValue) { $processIdValue } else { "-" })
            process_name = $processName
            process_start_time = $(if ($expectedStart) { $expectedStart } else { "-" })
            tracked_process_alive = "-"
            tracked_process_match = "-"
            current_process_start_time = "-"
            failure_reason = $null
        }
    }

    try {
        $processId = [int]$processIdValue
        $process = Get-Process -Id $processId -ErrorAction Stop
        $alive = $true
        try {
            $currentStart = Format-UtcTimestamp -Value $process.StartTime
            $match = [string]::Equals("$expectedStart", "$currentStart", [System.StringComparison]::OrdinalIgnoreCase)
            if (-not $match) {
                $failureReason = "tracked process restarted or pid reused"
            }
        } catch {
            $match = $false
            $failureReason = "tracked process start time unavailable"
        }
    } catch {
        $failureReason = "tracked process exited"
    }

    return [pscustomobject][ordered]@{
        process_tracking_enabled = $true
        process_id = $(if ($processIdValue) { $processIdValue } else { "-" })
        process_name = $processName
        process_start_time = $(if ($expectedStart) { $expectedStart } else { "-" })
        tracked_process_alive = $alive
        tracked_process_match = $match
        current_process_start_time = $currentStart
        failure_reason = $failureReason
    }
}

function Complete-ActiveTestSession {
    param($Session, [string]$EndReason)

    if (-not $Session) {
        return $null
    }

    $ended = [ordered]@{
        session_id = Get-ObjectField -Object $Session -Key "session_id" -Default "-"
        status = "ended"
        started_at_utc = Get-ObjectField -Object $Session -Key "started_at_utc" -Default $null
        ended_at_utc = Get-UtcTimestampText
        label = Get-ObjectField -Object $Session -Key "label" -Default ""
        reason = $(if (Test-LogPresent -Value $EndReason) { $EndReason } else { "" })
        tool = "test_session_tool.ps1"
        process_tracking_enabled = (Test-ObjectBooleanTrue -Object $Session -Key "process_tracking_enabled")
    }
    foreach ($key in @("process_id", "process_name", "process_start_time")) {
        $value = Get-ObjectField -Object $Session -Key $key -Default $null
        if (Test-LogPresent -Value $value) {
            $ended[$key] = $value
        }
    }

    $endedSession = [pscustomobject]$ended
    Write-ActiveTestSession -Session $endedSession
    Append-TestSessionHistory -Session $endedSession
    return $endedSession
}

function Update-TrackedSessionIfInvalid {
    param($Session)

    if (-not (Test-ActiveTestSession -Session $Session)) {
        return $Session
    }
    $state = Get-TrackedProcessState -Session $Session
    if ($state.process_tracking_enabled -eq $true -and (-not $state.tracked_process_alive -or -not $state.tracked_process_match)) {
        return Complete-ActiveTestSession -Session $Session -EndReason $state.failure_reason
    }
    return $Session
}

function Get-SessionConfigContext {
    $config = Read-CaseConfigMap -Path $CaseConfigPath
    return [ordered]@{
        "known_true_addr" = Get-ConfigDisplayValue -Config $config -Key "known_true_addr"
        "target_value_float" = Get-ConfigDisplayValue -Config $config -Key "target_value_float"
        "target_value_pattern" = Get-ConfigDisplayValue -Config $config -Key "target_value_pattern"
        "execution_mode" = Get-ConfigDisplayValue -Config $config -Key "execution_mode" -Default "disabled"
        "write_enabled" = Get-ConfigDisplayValue -Config $config -Key "write_enabled" -Default "false"
    }
}

function Get-TestSessionSummaryFields {
    param($Session, [string]$Action, [string]$RecommendedNextStep)

    $active = Test-ActiveTestSession -Session $Session
    $fields = [ordered]@{
        "action" = $Action
        "active session" = $active
        "session id" = Get-ObjectField -Object $Session -Key "session_id" -Default "-"
        "status" = Get-ObjectField -Object $Session -Key "status" -Default "none"
        "started_at_utc" = Get-ObjectField -Object $Session -Key "started_at_utc" -Default "-"
        "ended_at_utc" = Get-ObjectField -Object $Session -Key "ended_at_utc" -Default "-"
        "session age" = Get-SessionAgeText -Session $Session
        "label" = Get-ObjectField -Object $Session -Key "label" -Default "-"
        "reason" = Get-ObjectField -Object $Session -Key "reason" -Default "-"
        "process_tracking_enabled" = Test-ObjectBooleanTrue -Object $Session -Key "process_tracking_enabled"
        "session path" = $ActiveTestSessionPath
        "history path" = $TestSessionHistoryPath
    }
    $trackedState = Get-TrackedProcessState -Session $Session
    $fields["process_id"] = $trackedState.process_id
    $fields["process_name"] = $trackedState.process_name
    $fields["process_start_time"] = $trackedState.process_start_time
    $fields["tracked_process_alive"] = $trackedState.tracked_process_alive
    $fields["tracked_process_match"] = $trackedState.tracked_process_match
    $fields["process status note"] = $(if ($trackedState.process_tracking_enabled) { $(if ($trackedState.failure_reason) { $trackedState.failure_reason } else { "tracked process is valid" }) } else { "Process tracking disabled; manually run session-end when testing ends." })
    foreach ($entry in (Get-SessionConfigContext).GetEnumerator()) {
        $fields[$entry.Key] = $entry.Value
    }
    $fields["recommended next step"] = $RecommendedNextStep
    return $fields
}

function Assert-ActiveTestSessionForReuse {
    param([string]$CommandName)

    $session = Update-TrackedSessionIfInvalid -Session (Read-ActiveTestSession)
    if (-not (Test-ActiveTestSession -Session $session)) {
        Write-WorkflowSummary -Title "Active Session Required" -Fields ([ordered]@{
            "command" = $CommandName
            "active session" = $false
            "session path" = $ActiveTestSessionPath
            "status" = Get-ObjectField -Object $session -Key "status" -Default "none"
            "warning" = "No active test session is recorded. Run session-start only if the same CE/process/scene is still active."
            "recommended next step" = "Use sample-plan without -ActiveSession and collect new current-session addresses."
        })
        exit 1
    }
    return $session
}

function Get-SafeBaselineFileName {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return [pscustomobject][ordered]@{ ok = $false; value = $null; error = "baseline name is required" }
    }

    $text = $Value.Trim()
    if ($text -match '[\\/:<>|"?*]' -or $text -match '\.\.') {
        return [pscustomobject][ordered]@{ ok = $false; value = $null; error = "baseline name must not contain path separators, path traversal, or invalid filename characters" }
    }
    if ($text -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
        return [pscustomobject][ordered]@{ ok = $false; value = $null; error = "baseline name may only contain letters, numbers, dot, underscore, and hyphen, and must start with a letter or number" }
    }
    if (-not $text.EndsWith(".md", [System.StringComparison]::OrdinalIgnoreCase)) {
        $text = "$text.md"
    }
    return [pscustomobject][ordered]@{ ok = $true; value = $text; error = $null }
}

function Resolve-BaselinePath {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return [pscustomobject][ordered]@{ ok = $false; path = $null; error = "baseline is required" }
    }

    $text = $Value.Trim()
    if ([System.IO.Path]::IsPathRooted($text)) {
        try {
            return [pscustomobject][ordered]@{ ok = $true; path = [System.IO.Path]::GetFullPath($text); error = $null }
        } catch {
            return [pscustomobject][ordered]@{ ok = $false; path = $null; error = "baseline path is invalid: $($_.Exception.Message)" }
        }
    }

    $safe = Get-SafeBaselineFileName -Value $text
    if (-not $safe.ok) {
        return [pscustomobject][ordered]@{ ok = $false; path = $null; error = $safe.error }
    }
    return [pscustomobject][ordered]@{ ok = $true; path = (Join-Path $BaselineRoot $safe.value); error = $null }
}

function Get-BaselineFileSummary {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return [ordered]@{
            "baseline path" = $Path
            "baseline exists" = $false
            "last write time" = "-"
            "size bytes" = "-"
        }
    }

    $item = Get-Item -LiteralPath $Path
    return [ordered]@{
        "baseline path" = $item.FullName
        "baseline exists" = $true
        "last write time" = $item.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
        "size bytes" = $item.Length
    }
}

function Write-BaselineList {
    param([string]$Directory, [string]$CurrentPath)

    Write-Output ""
    Write-Output "Baseline Files"
    if (-not (Test-Path -LiteralPath $Directory)) {
        Write-Output ("Baseline directory does not exist: {0}" -f $Directory)
        return
    }

    $currentFullPath = [System.IO.Path]::GetFullPath($CurrentPath)
    $files = @(Get-ChildItem -LiteralPath $Directory -Filter "*.md" -File | Sort-Object -Property @{ Expression = "LastWriteTime"; Descending = $true }, Name)
    if ($files.Count -eq 0) {
        Write-Output ("No baseline Markdown files found under: {0}" -f $Directory)
        return
    }

    Write-Output ("{0,-48} {1,-7} {2,-20} {3,10}" -f "filename", "current", "last_write_time", "size")
    Write-Output ("{0,-48} {1,-7} {2,-20} {3,10}" -f "--------", "-------", "---------------", "----")
    foreach ($file in $files) {
        $isCurrent = [string]::Equals($file.FullName, $currentFullPath, [System.StringComparison]::OrdinalIgnoreCase)
        Write-Output ("{0,-48} {1,-7} {2,-20} {3,10}" -f $file.Name, $isCurrent, $file.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"), $file.Length)
    }
}

function Read-BaselineUniqueKnownTrueCount {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match "^- unique known_true_addr count:\s*(\d+)\s*$") {
            return [int]$matches[1]
        }
        if ($line -match "^\|\s*unique known_true_addr count\s*\|\s*(\d+)\s*\|") {
            return [int]$matches[1]
        }
    }
    return $null
}

function Get-RecordKnownTrueAddr {
    param($Record)

    $addr = Get-RecordField -Record $Record -Key "known_true_addr"
    if (Test-LogPresent -Value $addr) {
        return "$addr"
    }
    return $null
}

function Get-RepeatedKnownTrueGroups {
    param([object[]]$Records)

    return @(
        $Records |
            ForEach-Object { Get-RecordKnownTrueAddr -Record $_ } |
            Where-Object { Test-LogPresent -Value $_ } |
            Group-Object |
            Where-Object { $_.Count -gt 1 } |
            Sort-Object -Property @{ Expression = "Count"; Descending = $true }, Name
    )
}

function Format-RepeatedKnownTrueList {
    param($Groups)

    $items = @(
        $Groups |
            ForEach-Object { "{0} count {1}" -f $_.Name, $_.Count }
    )
    if ($items.Count -eq 0) {
        return "none"
    }
    return ($items -join "; ")
}

function Get-UniqueKnownTrueCount {
    param([object[]]$Records)

    return @(
        $Records |
            ForEach-Object { Get-RecordKnownTrueAddr -Record $_ } |
            Where-Object { Test-LogPresent -Value $_ } |
            Select-Object -Unique
    ).Count
}

function Get-RollingDistinctNeeded {
    param([object[]]$Records, [int]$WindowSize, [int]$Target)

    if ($Target -le 0) {
        return "not_available"
    }
    if ($Target -gt $WindowSize) {
        return "not_possible_target_exceeds_window"
    }

    for ($k = 0; $k -le $WindowSize; $k++) {
        $dropCount = [math]::Max(0, $Records.Count + $k - $WindowSize)
        $keepCount = [math]::Max(0, $Records.Count - $dropCount)
        $kept = @()
        if ($keepCount -gt 0) {
            $kept = @($Records | Select-Object -First $keepCount)
        }

        $uniqueAfter = (Get-UniqueKnownTrueCount -Records $kept) + $k
        if ($uniqueAfter -ge $Target) {
            return $k
        }
    }
    return "not_possible"
}

function Write-RepeatedKnownTrueTable {
    param($Groups)

    Write-Output ""
    Write-Output "Repeated known_true_addr"
    if (@($Groups).Count -eq 0) {
        Write-Output "none"
        return
    }

    $addrWidth = 24
    Write-Output ("{0,-$addrWidth} {1}" -f "known_true_addr", "count")
    Write-Output ("{0,-$addrWidth} {1}" -f "---------------", "-----")
    foreach ($group in @($Groups)) {
        Write-Output ("{0,-$addrWidth} {1}" -f $group.Name, $group.Count)
    }
}

function Get-CaseCoverageSummary {
    param([int]$RequestedLatest, [string]$RequestedProfile, [string]$RequestedBaseline, [int]$RequestedTargetUnique)

    $baselinePathValue = if ($RequestedBaseline) { $RequestedBaseline } else { $BaselinePath }
    $resolvedBaseline = Resolve-BaselinePath -Value $baselinePathValue
    if (-not $resolvedBaseline.ok) {
        Write-Output ("ERROR: invalid baseline: {0}" -f $resolvedBaseline.error)
        exit 1
    }

    $baselineExists = Test-Path -LiteralPath $resolvedBaseline.path
    $baselineUniqueCount = $null
    if ($baselineExists) {
        $baselineUniqueCount = Read-BaselineUniqueKnownTrueCount -Path $resolvedBaseline.path
    }

    $targetUniqueValue = $null
    $targetSource = "none"
    if ($null -ne $baselineUniqueCount) {
        $targetUniqueValue = [int]$baselineUniqueCount
        $targetSource = "baseline"
    } elseif ($RequestedTargetUnique -gt 0) {
        $targetUniqueValue = $RequestedTargetUnique
        $targetSource = "TargetUnique"
    }

    $classifierArgs = @("-Latest", "$RequestedLatest", "-Profile", $RequestedProfile, "-OnlyBaselineEligible", "-LogRoot", $LogRoot, "-ConsoleSummary")
    $classifierResult = Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments $classifierArgs -Capture -Quiet
    if ($classifierResult.exit_code -ne 0) {
        $classifierResult.output | ForEach-Object { Write-Output $_ }
        exit $classifierResult.exit_code
    }

    $records = @(Get-ClassifierConsoleRecords -OutputLines $classifierResult.output)
    $uniqueCount = Get-UniqueKnownTrueCount -Records $records
    $successCount = @($records | Where-Object {
        $classification = Get-RecordField -Record $_ -Key "classification"
        $classification -eq "success" -or $classification -eq "quick_success"
    }).Count
    $repeatedGroups = @(Get-RepeatedKnownTrueGroups -Records $records)
    $topRepeated = if ($repeatedGroups.Count -gt 0) { "{0} count {1}" -f $repeatedGroups[0].Name, $repeatedGroups[0].Count } else { "none" }

    $coverageDelta = "not_available"
    $rollingNeeded = "not_available"
    $conclusion = "NO_BASELINE"
    $recommendation = "No baseline target is available; review current coverage only."

    if ($records.Count -eq 0) {
        $conclusion = "INSUFFICIENT_DATA"
        $recommendation = "No eligible batches were found for this window."
    } elseif ($null -ne $targetUniqueValue) {
        $coverageDelta = $uniqueCount - $targetUniqueValue
        $rollingNeeded = Get-RollingDistinctNeeded -Records $records -WindowSize $RequestedLatest -Target $targetUniqueValue
        if ($uniqueCount -ge $targetUniqueValue) {
            $conclusion = "COVERAGE_OK"
            $recommendation = "Coverage is sufficient for the selected baseline."
        } else {
            $conclusion = "COVERAGE_WARN"
            $recommendation = "Collect at least {0} new distinct {1} detect-only baseline-eligible batches." -f $rollingNeeded, $RequestedProfile
        }
    }

    if ($repeatedGroups.Count -gt 0 -and $conclusion -ne "INSUFFICIENT_DATA") {
        $recommendation = "{0} Avoid repeating top repeated addr unless intentionally checking stability." -f $recommendation
    }

    return [pscustomobject][ordered]@{
        fields = [ordered]@{
            "latest N" = $RequestedLatest
            "profile" = $RequestedProfile
            "baseline path" = $resolvedBaseline.path
            "baseline exists" = $baselineExists
            "baseline unique known_true_addr count" = $(if ($null -ne $baselineUniqueCount) { $baselineUniqueCount } else { "not_available" })
            "target unique source" = $targetSource
            "target unique known_true_addr count" = $(if ($null -ne $targetUniqueValue) { $targetUniqueValue } else { "not_available" })
            "current eligible batch count" = $records.Count
            "current success count" = $successCount
            "current unique known_true_addr count" = $uniqueCount
            "coverage delta" = $coverageDelta
            "repeated known_true_addr list with counts" = Format-RepeatedKnownTrueList -Groups $repeatedGroups
            "top repeated addr" = $topRepeated
            "estimated new distinct addr needed under rolling latest-N window" = $rollingNeeded
            "conclusion" = $conclusion
            "recommendation" = $recommendation
        }
        repeated_groups = $repeatedGroups
        conclusion = $conclusion
    }
}

function Test-RecordClassificationSuccess {
    param($Record)

    $classification = Get-RecordField -Record $Record -Key "classification"
    return $classification -eq "success" -or $classification -eq "quick_success"
}

function Test-RecordBaselineEligibleTrue {
    param($Record)

    $eligible = Get-RecordField -Record $Record -Key "baseline_eligible"
    return "$eligible".Trim().ToLowerInvariant() -eq "true"
}

function Test-RecordExecutionBatch {
    param($Record)

    $transactionType = Get-RecordField -Record $Record -Key "transaction_type"
    return (Test-LogPresent -Value $transactionType) -and $transactionType -ne "detect_only"
}

function Test-RecordWriteDependency {
    param($Record)

    $transactionType = Get-RecordField -Record $Record -Key "transaction_type"
    return $transactionType -in @("write_success", "restore_success", "write_blocked", "restore_blocked", "execution_failed")
}

function Get-CaseLibraryConclusion {
    param([object[]]$Records, [object[]]$AddressRows)

    if ($Records.Count -eq 0 -or $AddressRows.Count -eq 0) {
        return "INSUFFICIENT_DATA"
    }
    $duplicateHeavyRows = @($AddressRows | Where-Object { $_.total_cases -ge 5 -or $_.duplicate_count -ge 3 })
    if ($duplicateHeavyRows.Count -gt 0) {
        return "DUPLICATE_HEAVY"
    }
    $stableRows = @($AddressRows | Where-Object { $_.stable_case_candidate -eq $true })
    if ($stableRows.Count -lt 3) {
        return "NEED_MORE_FULL_CASES"
    }
    return "CASE_LIBRARY_OK"
}

function Get-CaseLibraryRecommendation {
    param([string]$Conclusion)

    switch ($Conclusion) {
        "CASE_LIBRARY_OK" { return "Case library has stable full candidates for current planning." }
        "NEED_MORE_FULL_CASES" { return "Collect more distinct full success cases with at least two clean full runs per address." }
        "DUPLICATE_HEAVY" { return "Reduce repeated addresses and add new distinct full detect-only cases." }
        "INSUFFICIENT_DATA" { return "Not enough classified logs found for case library planning." }
        default { return "Review case library output before changing baselines." }
    }
}

function Get-CaseLibrarySummary {
    param([int]$RequestedLatest, [string]$RequestedProfile)

    $classifierArgs = @("-Latest", "$RequestedLatest", "-Profile", $RequestedProfile, "-LogRoot", $LogRoot, "-ConsoleSummary")
    $classifierResult = Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments $classifierArgs -Capture -Quiet
    if ($classifierResult.exit_code -ne 0) {
        $classifierResult.output | ForEach-Object { Write-Output $_ }
        exit $classifierResult.exit_code
    }

    $records = @(Get-ClassifierConsoleRecords -OutputLines $classifierResult.output | Where-Object {
        Test-LogPresent -Value (Get-RecordKnownTrueAddr -Record $_)
    })
    $groups = @($records | Group-Object { Get-RecordKnownTrueAddr -Record $_ } | Sort-Object Name)
    $rows = @()
    foreach ($group in $groups) {
        $addrRecords = @($group.Group)
        $successRecords = @($addrRecords | Where-Object { Test-RecordClassificationSuccess -Record $_ })
        $fullSuccessRecords = @($addrRecords | Where-Object {
            (Get-RecordField -Record $_ -Key "validation_profile") -eq "full" -and (Get-RecordField -Record $_ -Key "classification") -eq "success"
        })
        $profilesSeen = @(
            $addrRecords |
                ForEach-Object { Get-RecordField -Record $_ -Key "validation_profile" } |
                Where-Object { Test-LogPresent -Value $_ } |
                Select-Object -Unique |
                Sort-Object
        )
        $batchIds = @(
            $addrRecords |
                ForEach-Object { Get-RecordField -Record $_ -Key "batch_id" } |
                Where-Object { Test-LogPresent -Value $_ } |
                Sort-Object
        )
        $baselineEligibleCount = @($addrRecords | Where-Object { Test-RecordBaselineEligibleTrue -Record $_ }).Count
        $executionBatchCount = @($addrRecords | Where-Object { Test-RecordExecutionBatch -Record $_ }).Count
        $writeDependencyCount = @($addrRecords | Where-Object { Test-RecordWriteDependency -Record $_ }).Count
        $invalidConfigCount = @($addrRecords | Where-Object { (Get-RecordField -Record $_ -Key "classification") -eq "invalid_config_mismatch" }).Count
        $stableCandidate = $fullSuccessRecords.Count -ge 2 -and $invalidConfigCount -eq 0 -and $writeDependencyCount -eq 0

        $rows += [pscustomobject][ordered]@{
            known_true_addr = $group.Name
            total_cases = $addrRecords.Count
            success_count = $successRecords.Count
            full_success_count = $fullSuccessRecords.Count
            first_seen_batch = $(if ($batchIds.Count -gt 0) { $batchIds[0] } else { "-" })
            last_seen_batch = $(if ($batchIds.Count -gt 0) { $batchIds[$batchIds.Count - 1] } else { "-" })
            profiles_seen = $(if ($profilesSeen.Count -gt 0) { $profilesSeen -join "/" } else { "-" })
            baseline_eligible_count = $baselineEligibleCount
            execution_batches_count = $executionBatchCount
            invalid_config_count = $invalidConfigCount
            stable_case_candidate = $stableCandidate
            duplicate_count = [math]::Max(0, $addrRecords.Count - 1)
        }
    }

    $stableCandidates = @($rows | Where-Object { $_.stable_case_candidate -eq $true })
    $recommendedBaselineCandidates = @(
        $stableCandidates |
            Sort-Object -Property @{ Expression = "baseline_eligible_count"; Descending = $true }, @{ Expression = "full_success_count"; Descending = $true }, known_true_addr |
            Select-Object -ExpandProperty known_true_addr
    )
    $conclusion = Get-CaseLibraryConclusion -Records $records -AddressRows $rows
    $summary = [ordered]@{
        "latest N" = $RequestedLatest
        "profile" = $RequestedProfile
        "total cases" = $records.Count
        "unique known_true_addr count" = $rows.Count
        "baseline eligible count" = @($records | Where-Object { Test-RecordBaselineEligibleTrue -Record $_ }).Count
        "execution batches count" = @($records | Where-Object { Test-RecordExecutionBatch -Record $_ }).Count
        "invalid config count" = @($records | Where-Object { (Get-RecordField -Record $_ -Key "classification") -eq "invalid_config_mismatch" }).Count
        "stable case candidate count" = $stableCandidates.Count
        "current recommended baseline candidates" = $(if ($recommendedBaselineCandidates.Count -gt 0) { $recommendedBaselineCandidates -join "; " } else { "none" })
        "conclusion" = $conclusion
        "recommendation" = Get-CaseLibraryRecommendation -Conclusion $conclusion
    }

    return [pscustomobject][ordered]@{
        fields = $summary
        rows = $rows
        conclusion = $conclusion
    }
}

function Write-CaseLibraryTable {
    param([object[]]$Rows)

    Write-Output ""
    Write-Output "Case Library"
    if (@($Rows).Count -eq 0) {
        Write-Output "No known_true_addr records found."
        return
    }

    Write-Output ("{0,-15} {1,5} {2,7} {3,9} {4,-19} {5,-19} {6,-10} {7,8} {8,5} {9,7} {10,6}" -f "known_true_addr", "cases", "success", "full_succ", "first_seen", "last_seen", "profiles", "eligible", "exec", "invalid", "stable")
    Write-Output ("{0,-15} {1,5} {2,7} {3,9} {4,-19} {5,-19} {6,-10} {7,8} {8,5} {9,7} {10,6}" -f "---------------", "-----", "-------", "---------", "----------", "---------", "--------", "--------", "----", "-------", "------")
    foreach ($row in @($Rows | Sort-Object -Property @{ Expression = "stable_case_candidate"; Descending = $true }, @{ Expression = "full_success_count"; Descending = $true }, known_true_addr)) {
        Write-Output ("{0,-15} {1,5} {2,7} {3,9} {4,-19} {5,-19} {6,-10} {7,8} {8,5} {9,7} {10,6}" -f `
            $row.known_true_addr,
            $row.total_cases,
            $row.success_count,
            $row.full_success_count,
            $row.first_seen_batch,
            $row.last_seen_batch,
            $row.profiles_seen,
            $row.baseline_eligible_count,
            $row.execution_batches_count,
            $row.invalid_config_count,
            $row.stable_case_candidate)
    }
}

function Test-RecordFullSuccess {
    param($Record)

    return (Get-RecordField -Record $Record -Key "validation_profile") -eq "full" -and (Get-RecordField -Record $Record -Key "classification") -eq "success"
}

function Test-RecordBaselineEligibleSuccess {
    param($Record)

    return (Test-RecordFullSuccess -Record $Record) -and (Test-RecordBaselineEligibleTrue -Record $Record)
}

function Test-RecordQuickSuccess {
    param($Record)

    return (Get-RecordField -Record $Record -Key "classification") -eq "quick_success"
}

function Test-RankAwbOne {
    param($Value)

    return "$Value".Trim() -eq "1/1/1"
}

function Test-StableRankOne {
    param($Value)

    return "$Value".Trim() -eq "1"
}

function Get-StableCaseConclusion {
    param([int]$StableCount, [int]$TargetUnique)

    if ($StableCount -ge $TargetUnique) {
        return "READY_FOR_BASELINE"
    }
    return "NEED_MORE_STABLE_CASES"
}

function Get-StableCaseRecommendation {
    param([string]$Readiness)

    if ($Readiness -eq "READY_FOR_BASELINE") {
        return "Use stable candidates to build/refresh baseline."
    }
    return "Collect more distinct full detect-only clean runs."
}

function Test-StableCaseOnlyNeedsCleanRuns {
    param([string[]]$Reasons)

    $allowed = @("full_success_lt_min", "baseline_eligible_lt_min", "no_full_success")
    foreach ($reason in @($Reasons)) {
        if (-not ($allowed -contains $reason)) {
            return $false
        }
    }
    return @($Reasons).Count -gt 0
}

function Test-StableCaseHasQualityIssue {
    param([string[]]$Reasons)

    $qualityReasons = @(
        "latest_full_not_success",
        "latest_final_hit_false",
        "latest_rank_not_1_1_1",
        "latest_stable_rank_not_1",
        "has_invalid_config_mismatch",
        "has_known_true_value_mismatch",
        "has_ranking_issue",
        "has_selected_quota_issue"
    )
    foreach ($reason in @($Reasons)) {
        if ($qualityReasons -contains $reason) {
            return $true
        }
    }
    return $false
}

function Get-StableCaseRecommendedAction {
    param(
        [string[]]$Reasons,
        [bool]$StableCandidate,
        [int]$FullSuccessCount,
        [int]$BaselineEligibleSuccessCount,
        [int]$MinimumFullSuccess
    )

    if ($StableCandidate) {
        return "Ready as stable baseline candidate."
    }

    if (Test-StableCaseHasQualityIssue -Reasons $Reasons) {
        return "Inspect failed batches before using this address as baseline candidate."
    }

    if (@($Reasons | Where-Object { $_ -eq "has_execution_batch" }).Count -gt 0) {
        return "Do not use execution batches for baseline; collect clean detect-only confirmations."
    }

    if (Test-StableCaseOnlyNeedsCleanRuns -Reasons $Reasons) {
        $needed = [Math]::Max($MinimumFullSuccess - $FullSuccessCount, $MinimumFullSuccess - $BaselineEligibleSuccessCount)
        if ($needed -lt 1) {
            $needed = 1
        }
        return ("Collect {0} more full detect-only baseline-eligible success run(s)." -f $needed)
    }

    return "Collect clean full detect-only confirmations and inspect latest failures before baseline use."
}

function Get-StableCasesSummary {
    param([int]$RequestedLatest, [string]$RequestedProfile, [int]$MinimumFullSuccess, [int]$RequestedTargetUnique)

    $classifierArgs = @("-Latest", "$RequestedLatest", "-Profile", $RequestedProfile, "-LogRoot", $LogRoot, "-ConsoleSummary")
    $classifierResult = Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments $classifierArgs -Capture -Quiet
    if ($classifierResult.exit_code -ne 0) {
        $classifierResult.output | ForEach-Object { Write-Output $_ }
        exit $classifierResult.exit_code
    }

    $records = @(Get-ClassifierConsoleRecords -OutputLines $classifierResult.output | Where-Object {
        Test-LogPresent -Value (Get-RecordKnownTrueAddr -Record $_)
    })
    for ($i = 0; $i -lt $records.Count; $i++) {
        $records[$i] | Add-Member -NotePropertyName scan_order -NotePropertyValue ($i + 1) -Force
    }

    $groups = @($records | Group-Object { Get-RecordKnownTrueAddr -Record $_ } | Sort-Object Name)
    $rows = @()
    foreach ($group in $groups) {
        $addrRecords = @($group.Group | Sort-Object scan_order)
        $batchIds = @(
            $addrRecords |
                ForEach-Object { Get-RecordField -Record $_ -Key "batch_id" } |
                Where-Object { Test-LogPresent -Value $_ } |
                Sort-Object
        )
        $fullRecords = @($addrRecords | Where-Object { (Get-RecordField -Record $_ -Key "validation_profile") -eq "full" })
        $latestFull = @($fullRecords | Sort-Object scan_order | Select-Object -First 1)
        $latestFullRecord = if ($latestFull.Count -gt 0) { $latestFull[0] } else { $null }
        $fullSuccessCount = @($addrRecords | Where-Object { Test-RecordFullSuccess -Record $_ }).Count
        $baselineEligibleSuccessCount = @($addrRecords | Where-Object { Test-RecordBaselineEligibleSuccess -Record $_ }).Count
        $quickSuccessCount = @($addrRecords | Where-Object { Test-RecordQuickSuccess -Record $_ }).Count
        $invalidConfigCount = @($addrRecords | Where-Object { (Get-RecordField -Record $_ -Key "classification") -eq "invalid_config_mismatch" }).Count
        $knownTrueMismatchCount = @($addrRecords | Where-Object { (Get-RecordField -Record $_ -Key "classification") -eq "known_true_value_mismatch" }).Count
        $rankingIssueCount = @($addrRecords | Where-Object { (Get-RecordField -Record $_ -Key "classification") -eq "ranking_issue" }).Count
        $selectedQuotaIssueCount = @($addrRecords | Where-Object { (Get-RecordField -Record $_ -Key "classification") -eq "selected_quota_issue" }).Count
        $executionBatchCount = @($addrRecords | Where-Object { (Test-RecordExecutionBatch -Record $_) -or (Test-RecordWriteDependency -Record $_) }).Count

        $latestFinalHitOk = $false
        $latestRankOk = $false
        $latestStableRankOk = $false
        $latestFullSuccessOk = $false
        if ($latestFullRecord) {
            $latestFullSuccessOk = Test-RecordFullSuccess -Record $latestFullRecord
            $latestFinalHitOk = Test-LogTrue (Get-RecordField -Record $latestFullRecord -Key "final_hit")
            $latestRankOk = Test-RankAwbOne -Value (Get-RecordField -Record $latestFullRecord -Key "rank_A/W/B")
            $latestStableRankOk = Test-StableRankOne -Value (Get-RecordField -Record $latestFullRecord -Key "stable_rank")
        }

        $rejectionReasons = @()
        if ($fullSuccessCount -lt $MinimumFullSuccess) { $rejectionReasons += "full_success_lt_min" }
        if ($baselineEligibleSuccessCount -lt $MinimumFullSuccess) { $rejectionReasons += "baseline_eligible_lt_min" }
        if ($fullSuccessCount -eq 0) { $rejectionReasons += "no_full_success" }
        if ($latestFullRecord -and -not $latestFullSuccessOk) { $rejectionReasons += "latest_full_not_success" }
        if ($latestFullRecord -and -not $latestFinalHitOk) { $rejectionReasons += "latest_final_hit_false" }
        if ($latestFullRecord -and -not $latestRankOk) { $rejectionReasons += "latest_rank_not_1_1_1" }
        if ($latestFullRecord -and -not $latestStableRankOk) { $rejectionReasons += "latest_stable_rank_not_1" }
        if ($invalidConfigCount -gt 0) { $rejectionReasons += "has_invalid_config_mismatch" }
        if ($knownTrueMismatchCount -gt 0) { $rejectionReasons += "has_known_true_value_mismatch" }
        if ($rankingIssueCount -gt 0) { $rejectionReasons += "has_ranking_issue" }
        if ($selectedQuotaIssueCount -gt 0) { $rejectionReasons += "has_selected_quota_issue" }
        if ($executionBatchCount -gt 0) { $rejectionReasons += "has_execution_batch" }

        $stableCandidate = $rejectionReasons.Count -eq 0
        $recommendedAction = Get-StableCaseRecommendedAction `
            -Reasons $rejectionReasons `
            -StableCandidate $stableCandidate `
            -FullSuccessCount $fullSuccessCount `
            -BaselineEligibleSuccessCount $baselineEligibleSuccessCount `
            -MinimumFullSuccess $MinimumFullSuccess

        $rows += [pscustomobject][ordered]@{
            known_true_addr = $group.Name
            full_success_count = $fullSuccessCount
            baseline_eligible_count = $baselineEligibleSuccessCount
            quick_success_count = $quickSuccessCount
            first_seen_batch = $(if ($batchIds.Count -gt 0) { $batchIds[0] } else { "-" })
            last_seen_batch = $(if ($batchIds.Count -gt 0) { $batchIds[$batchIds.Count - 1] } else { "-" })
            latest_full_batch = $(if ($latestFullRecord) { Get-RecordField -Record $latestFullRecord -Key "batch_id" } else { "-" })
            last_seen_order = $(if ($latestFullRecord) { $latestFullRecord.scan_order } else { "-" })
            latest_best_candidate = $(if ($latestFullRecord) { Get-RecordField -Record $latestFullRecord -Key "best_candidate" } else { "-" })
            latest_rank_AWB = $(if ($latestFullRecord) { Get-RecordField -Record $latestFullRecord -Key "rank_A/W/B" } else { "-" })
            latest_stable_rank = $(if ($latestFullRecord) { Get-RecordField -Record $latestFullRecord -Key "stable_rank" } else { "-" })
            stable_candidate = $stableCandidate
            total_cases = $addrRecords.Count
            rejection_reasons = $(if ($stableCandidate) { "-" } else { $rejectionReasons -join "; " })
            recommended_action = $recommendedAction
            notes = $(if ($stableCandidate) { "ready" } else { $rejectionReasons -join "; " })
        }
    }

    $stableRows = @($rows | Where-Object { $_.stable_candidate -eq $true })
    $rejectedRows = @($rows | Where-Object { $_.stable_candidate -ne $true })
    $reasonCounts = @{}
    foreach ($row in $rejectedRows) {
        foreach ($reason in @("$($row.rejection_reasons)".Split(";") | ForEach-Object { $_.Trim() } | Where-Object { Test-LogPresent -Value $_ -and $_ -ne "-" })) {
            if (-not $reasonCounts.ContainsKey($reason)) {
                $reasonCounts[$reason] = 0
            }
            $reasonCounts[$reason] += 1
        }
    }
    $reasonSummary = @(
        foreach ($reason in @($reasonCounts.Keys | Sort-Object)) {
            [pscustomobject][ordered]@{
                rejection_reason = $reason
                affected_addr_count = $reasonCounts[$reason]
            }
        }
    )
    $onlyMoreCleanRunsCount = @($rejectedRows | Where-Object {
        $reasons = @("$($_.rejection_reasons)".Split(";") | ForEach-Object { $_.Trim() } | Where-Object { Test-LogPresent -Value $_ -and $_ -ne "-" })
        Test-StableCaseOnlyNeedsCleanRuns -Reasons $reasons
    }).Count
    $qualityIssueCount = @($rejectedRows | Where-Object {
        $reasons = @("$($_.rejection_reasons)".Split(";") | ForEach-Object { $_.Trim() } | Where-Object { Test-LogPresent -Value $_ -and $_ -ne "-" })
        Test-StableCaseHasQualityIssue -Reasons $reasons
    }).Count
    $topRepeated = @($rows | Sort-Object -Property @{ Expression = "total_cases"; Descending = $true }, known_true_addr | Select-Object -First 1)
    $topRepeatedText = if ($topRepeated.Count -gt 0) { "{0} count {1}" -f $topRepeated[0].known_true_addr, $topRepeated[0].total_cases } else { "none" }
    $duplicateHeavyWarning = $topRepeated.Count -gt 0 -and $topRepeated[0].total_cases -ge 5
    $readiness = Get-StableCaseConclusion -StableCount $stableRows.Count -TargetUnique $RequestedTargetUnique

    return [pscustomobject][ordered]@{
        fields = [ordered]@{
            "latest N" = $RequestedLatest
            "profile" = $RequestedProfile
            "min full success" = $MinimumFullSuccess
            "target unique" = $RequestedTargetUnique
            "total unique addr" = $rows.Count
            "stable candidate count" = $stableRows.Count
            "rejected address count" = $rejectedRows.Count
            "addresses needing only more clean full runs" = $onlyMoreCleanRunsCount
            "addresses blocked by quality issues" = $qualityIssueCount
            "coverage readiness" = $readiness
            "top repeated addr" = $topRepeatedText
            "duplicate-heavy warning" = $duplicateHeavyWarning
            "recommended action" = Get-StableCaseRecommendation -Readiness $readiness
        }
        rows = $rows
        reason_summary = $reasonSummary
        stable_count = $stableRows.Count
        rejected_count = $rejectedRows.Count
        readiness = $readiness
    }
}

function Write-StableCasesTable {
    param(
        [object[]]$Rows,
        [switch]$IncludeRejected,
        [string]$Title = "Stable Cases"
    )

    Write-Output ""
    Write-Output $Title
    $displayRows = @($Rows)
    if (-not $IncludeRejected) {
        $displayRows = @($displayRows | Where-Object { $_.stable_candidate -eq $true })
    }
    if ($displayRows.Count -eq 0) {
        Write-Output "No matching known_true_addr rows found."
        return
    }

    Write-Output ("{0,-15} {1,9} {2,8} {3,5} {4,-15} {5,-15} {6,-15} {7,-9} {8,-6} {9,-6} {10,-36} {11}" -f "known_true_addr", "full_succ", "eligible", "quick", "first_seen", "last_seen", "latest_full", "rank_AWB", "stable", "cand", "rejection_reasons", "recommended_action")
    Write-Output ("{0,-15} {1,9} {2,8} {3,5} {4,-15} {5,-15} {6,-15} {7,-9} {8,-6} {9,-6} {10,-36} {11}" -f "---------------", "---------", "--------", "-----", "----------", "---------", "-----------", "--------", "------", "----", "-----------------", "------------------")
    foreach ($row in @($displayRows | Sort-Object -Property @{ Expression = "stable_candidate"; Descending = $true }, @{ Expression = "full_success_count"; Descending = $true }, known_true_addr)) {
        Write-Output ("{0,-15} {1,9} {2,8} {3,5} {4,-15} {5,-15} {6,-15} {7,-9} {8,-6} {9,-6} {10,-36} {11}" -f `
            $row.known_true_addr,
            $row.full_success_count,
            $row.baseline_eligible_count,
            $row.quick_success_count,
            $row.first_seen_batch,
            $row.last_seen_batch,
            $row.latest_full_batch,
            $row.latest_rank_AWB,
            $row.latest_stable_rank,
            $row.stable_candidate,
            $row.rejection_reasons,
            $row.recommended_action)
    }
}

function Write-StableRejectionReasonSummary {
    param([object[]]$Rows)

    Write-Output ""
    Write-Output "Rejection Reason Summary"
    if (@($Rows).Count -eq 0) {
        Write-Output "No rejected addresses."
        return
    }

    Write-Output ("{0,-36} {1,10}" -f "rejection_reason", "addr_count")
    Write-Output ("{0,-36} {1,10}" -f "----------------", "----------")
    foreach ($row in @($Rows | Sort-Object -Property @{ Expression = "affected_addr_count"; Descending = $true }, rejection_reason)) {
        Write-Output ("{0,-36} {1,10}" -f $row.rejection_reason, $row.affected_addr_count)
    }
}

function Invoke-StableCasesCommand {
    param(
        [string]$CommandName,
        [bool]$LatestProvided,
        [bool]$ProfileProvided,
        [bool]$TargetUniqueProvided,
        [bool]$KnownTrueAddrProvided
    )

    $stableLatest = if ($LatestProvided) { $Latest } else { 100 }
    if ($stableLatest -lt 1) {
        Write-Output ("ERROR: -Latest must be greater than 0 for {0}" -f $CommandName)
        exit 1
    }
    if ($MinFullSuccess -lt 1) {
        Write-Output ("ERROR: -MinFullSuccess must be greater than 0 for {0}" -f $CommandName)
        exit 1
    }
    if ($KnownTrueAddrProvided) {
        Assert-KnownTrueAddr -Value $KnownTrueAddr -CommandName $CommandName
    }

    $stableTargetUnique = if ($TargetUniqueProvided -and $TargetUnique -gt 0) { $TargetUnique } else { 13 }
    $stableProfile = if ($ProfileProvided) { $Profile } else { "full" }
    $stable = Get-StableCasesSummary -RequestedLatest $stableLatest -RequestedProfile $stableProfile -MinimumFullSuccess $MinFullSuccess -RequestedTargetUnique $stableTargetUnique

    $rows = @($stable.rows)
    $reasonRows = @($stable.reason_summary)
    $tableTitle = "Stable Cases"
    $includeRejectedRows = $ShowRejected

    if ($KnownTrueAddrProvided) {
        $rows = @($rows | Where-Object { [string]::Equals($_.known_true_addr, $KnownTrueAddr, [System.StringComparison]::OrdinalIgnoreCase) })
        if ($rows.Count -eq 0) {
            Write-Output ("ERROR: known_true_addr not found in latest {0} {1} records: {2}" -f $stableLatest, $stableProfile, $KnownTrueAddr)
            exit 1
        }
        $reasonRows = @()
        foreach ($reason in @("$($rows[0].rejection_reasons)".Split(";") | ForEach-Object { $_.Trim() } | Where-Object { Test-LogPresent -Value $_ -and $_ -ne "-" })) {
            $reasonRows += [pscustomobject][ordered]@{
                rejection_reason = $reason
                affected_addr_count = 1
            }
        }
        $tableTitle = "Stable Case Detail"
        $includeRejectedRows = $true
    } elseif ($ShowRejected) {
        $tableTitle = "Stable and Rejected Cases"
    }

    Write-WorkflowSummary -Title "Stable Baseline Candidates Summary" -Fields $stable.fields
    Write-AddressLifetimeNote -Mode "stable" -ActiveSessionConfirmed:$false
    Write-StableRejectionReasonSummary -Rows $reasonRows
    Write-StableCasesTable -Rows $rows -IncludeRejected:$includeRejectedRows -Title $tableTitle
    exit 0
}

function Get-RetestReasonList {
    param($Row)

    return @("$($Row.rejection_reasons)".Split(";") | ForEach-Object { $_.Trim() } | Where-Object { Test-LogPresent -Value $_ -and $_ -ne "-" })
}

function Get-MissingCleanFullRuns {
    param($Row, [int]$MinimumFullSuccess)

    $missingFull = $MinimumFullSuccess - [int]$Row.full_success_count
    $missingEligible = $MinimumFullSuccess - [int]$Row.baseline_eligible_count
    $missing = [Math]::Max($missingFull, $missingEligible)
    if ($missing -lt 0) {
        return 0
    }
    return $missing
}

function Test-RetestBlockedReason {
    param([string[]]$Reasons)

    $blockedReasons = @(
        "has_invalid_config_mismatch",
        "has_known_true_value_mismatch",
        "has_ranking_issue",
        "has_selected_quota_issue",
        "latest_final_hit_false",
        "latest_rank_not_1_1_1",
        "latest_stable_rank_not_1",
        "latest_full_not_success",
        "no_full_success"
    )
    foreach ($reason in @($Reasons)) {
        if ($blockedReasons -contains $reason) {
            return $true
        }
    }
    return $false
}

function Test-RetestOnlyCleanCountReasons {
    param([string[]]$Reasons)

    $allowed = @("full_success_lt_min", "baseline_eligible_lt_min")
    foreach ($reason in @($Reasons)) {
        if (-not ($allowed -contains $reason)) {
            return $false
        }
    }
    return @($Reasons).Count -gt 0
}

function Get-RetestPriority {
    param($Row, [int]$MissingCleanFullRuns)

    $reasons = @(Get-RetestReasonList -Row $Row)
    if (Test-RetestBlockedReason -Reasons $reasons) {
        return "BLOCKED"
    }
    if (@($reasons | Where-Object { $_ -eq "has_execution_batch" }).Count -gt 0) {
        return "LOW"
    }
    if ((Test-RetestOnlyCleanCountReasons -Reasons $reasons) -and $MissingCleanFullRuns -le 1) {
        return "HIGH"
    }
    if ((Test-RetestOnlyCleanCountReasons -Reasons $reasons) -and $MissingCleanFullRuns -gt 1) {
        return "MEDIUM"
    }
    if ([int]$Row.total_cases -ge 5) {
        return "LOW"
    }
    return "MEDIUM"
}

function Get-RetestRecommendedAction {
    param(
        [string]$Priority,
        [int]$MissingCleanFullRuns,
        [bool]$ActiveSessionConfirmed,
        [bool]$CurrentSessionAddress = $false
    )

    if ($ActiveSessionConfirmed -and -not $CurrentSessionAddress) {
        return "Historical address only unless manually re-verified in the current session."
    }

    switch ($Priority) {
        "HIGH" {
            if ($ActiveSessionConfirmed -and $CurrentSessionAddress) {
                return "Reuse this active-session addr for 1 more full detect-only baseline-eligible run."
            }
            return "If the same manual test session is still active, rerun this addr once; otherwise collect a new distinct current-session addr."
        }
        "MEDIUM" { return "Collect more full clean confirmations; reuse only if the same active session is still valid." }
        "LOW" {
            if ($ActiveSessionConfirmed -and $CurrentSessionAddress) {
                return "Reuse only if additional active-session stability confirmation is needed."
            }
            return "Collect a new current-session addr; keep this addr only as historical evidence unless the same session is still active."
        }
        "BLOCKED" { return "Use as diagnostic evidence first; do not reuse until issue is understood." }
        default { return "Review this address before scheduling retest." }
    }
}

function Get-RetestConclusion {
    param(
        [int]$StableCount,
        [int]$TargetUniqueValue,
        [int]$HighCount,
        [int]$MediumCount,
        [int]$LowCount,
        [int]$BlockedCount
    )

    if ($StableCount -ge $TargetUniqueValue) {
        return "READY_FOR_BASELINE"
    }
    if ($HighCount -gt 0) {
        return "COLLECT_HIGH_PRIORITY_RETESTS"
    }
    if ($MediumCount -gt 0 -or $LowCount -gt 0) {
        return "COLLECT_MORE_DISTINCT_CASES"
    }
    if ($BlockedCount -gt 0) {
        return "INSPECT_BLOCKED_CASES"
    }
    return "COLLECT_MORE_DISTINCT_CASES"
}

function Get-RetestQueueSummary {
    param(
        [int]$RequestedLatest,
        [string]$RequestedProfile,
        [int]$MinimumFullSuccess,
        [int]$RequestedTargetUnique,
        [int]$RequestedLimit,
        [bool]$ActiveSessionConfirmed,
        $ActiveSessionRecord = $null
    )

    $stable = Get-StableCasesSummary -RequestedLatest $RequestedLatest -RequestedProfile $RequestedProfile -MinimumFullSuccess $MinimumFullSuccess -RequestedTargetUnique $RequestedTargetUnique
    $currentSessionAddressMap = @{}
    if ($ActiveSessionConfirmed -and $ActiveSessionRecord) {
        $currentSessionAddressMap = Get-CurrentSessionAddressEvidenceMap -Session $ActiveSessionRecord -Rows $stable.rows
    }
    $queueRows = @()
    foreach ($row in @($stable.rows | Where-Object { $_.stable_candidate -ne $true })) {
        $missing = Get-MissingCleanFullRuns -Row $row -MinimumFullSuccess $MinimumFullSuccess
        $priority = Get-RetestPriority -Row $row -MissingCleanFullRuns $missing
        $priorityRank = switch ($priority) {
            "HIGH" { 1 }
            "MEDIUM" { 2 }
            "LOW" { 3 }
            "BLOCKED" { 4 }
            default { 5 }
        }
        $activeSessionSource = if ($ActiveSessionConfirmed) { Get-CurrentSessionAddressSource -Map $currentSessionAddressMap -Address $row.known_true_addr } else { "-" }
        $activeSessionAddress = $ActiveSessionConfirmed -and (Test-LogPresent -Value $activeSessionSource) -and $activeSessionSource -ne "-"
        $queueRows += [pscustomobject][ordered]@{
            known_true_addr = $row.known_true_addr
            full_success_count = $row.full_success_count
            baseline_eligible_count = $row.baseline_eligible_count
            quick_success_count = $row.quick_success_count
            latest_full_batch = $row.latest_full_batch
            latest_rank_AWB = $row.latest_rank_AWB
            latest_stable_rank = $row.latest_stable_rank
            rejection_reasons = $row.rejection_reasons
            missing_clean_full_runs = $missing
            retest_priority = $priority
            priority_rank = $priorityRank
            recommended_action = Get-RetestRecommendedAction -Priority $priority -MissingCleanFullRuns $missing -ActiveSessionConfirmed $ActiveSessionConfirmed -CurrentSessionAddress $activeSessionAddress
            active_session_addr = $activeSessionAddress
            active_session_source = $activeSessionSource
            active_session_prepare = $(if ($activeSessionAddress -and $priority -in @("HIGH", "MEDIUM", "LOW")) { "prepare-current-case -KnownTrueAddr `"$($row.known_true_addr)`" -Profile full" } else { "-" })
        }
    }

    $orderedRows = @($queueRows | Sort-Object -Property `
        @{ Expression = "priority_rank"; Ascending = $true },
        @{ Expression = "missing_clean_full_runs"; Ascending = $true },
        @{ Expression = "baseline_eligible_count"; Descending = $true },
        @{ Expression = "latest_full_batch"; Descending = $true },
        known_true_addr)
    $displayRows = @($orderedRows | Select-Object -First $RequestedLimit)
    $highCount = @($queueRows | Where-Object { $_.retest_priority -eq "HIGH" }).Count
    $mediumCount = @($queueRows | Where-Object { $_.retest_priority -eq "MEDIUM" }).Count
    $lowCount = @($queueRows | Where-Object { $_.retest_priority -eq "LOW" }).Count
    $blockedCount = @($queueRows | Where-Object { $_.retest_priority -eq "BLOCKED" }).Count
    $currentSessionAddrCount = @($queueRows | Where-Object { $_.active_session_addr -eq $true }).Count
    $activeSessionPrepareCount = @($queueRows | Where-Object { Test-LogPresent -Value $_.active_session_prepare -and $_.active_session_prepare -ne "-" }).Count
    $conclusion = Get-RetestConclusion `
        -StableCount $stable.stable_count `
        -TargetUniqueValue $RequestedTargetUnique `
        -HighCount $highCount `
        -MediumCount $mediumCount `
        -LowCount $lowCount `
        -BlockedCount $blockedCount

    return [pscustomobject][ordered]@{
        fields = [ordered]@{
            "latest N" = $RequestedLatest
            "profile" = $RequestedProfile
            "min full success" = $MinimumFullSuccess
            "target unique" = $RequestedTargetUnique
            "display limit" = $RequestedLimit
            "active session confirmed" = $ActiveSessionConfirmed
            "total unique addr" = $stable.fields["total unique addr"]
            "stable candidate count" = $stable.stable_count
            "high priority retest count" = $highCount
            "medium priority retest count" = $mediumCount
            "low priority retest count" = $lowCount
            "blocked address count" = $blockedCount
            "duplicate-heavy top addr" = $stable.fields["top repeated addr"]
            "current-session address count" = $currentSessionAddrCount
            "active-session prepare command count" = $activeSessionPrepareCount
            "conclusion" = $conclusion
        }
        rows = $displayRows
        all_rows = $queueRows
        conclusion = $conclusion
        high_count = $highCount
        medium_count = $mediumCount
        blocked_count = $blockedCount
        current_session_addr_count = $currentSessionAddrCount
        active_session_prepare_count = $activeSessionPrepareCount
    }
}

function Write-RetestQueueTable {
    param([object[]]$Rows, [bool]$ActiveSessionConfirmed = $false)

    Write-Output ""
    Write-Output "Retest Queue"
    if (@($Rows).Count -eq 0) {
        Write-Output "No retest rows found."
        return
    }

    if ($ActiveSessionConfirmed) {
        Write-Output ("{0,-15} {1,8} {2,8} {3,5} {4,-15} {5,-9} {6,-6} {7,7} {8,-8} {9,-34} {10,-22} {11,-96} {12}" -f "known_true_addr", "full", "eligible", "quick", "latest_full", "rank_AWB", "stable", "missing", "priority", "rejection_reasons", "active_session_source", "recommended_action", "active_session_prepare")
        Write-Output ("{0,-15} {1,8} {2,8} {3,5} {4,-15} {5,-9} {6,-6} {7,7} {8,-8} {9,-34} {10,-22} {11,-96} {12}" -f "---------------", "----", "--------", "-----", "-----------", "--------", "------", "-------", "--------", "-----------------", "---------------------", "------------------", "----------------------")
        foreach ($row in @($Rows)) {
            Write-Output ("{0,-15} {1,8} {2,8} {3,5} {4,-15} {5,-9} {6,-6} {7,7} {8,-8} {9,-34} {10,-22} {11,-96} {12}" -f `
                $row.known_true_addr,
                $row.full_success_count,
                $row.baseline_eligible_count,
                $row.quick_success_count,
                $row.latest_full_batch,
                $row.latest_rank_AWB,
                $row.latest_stable_rank,
                $row.missing_clean_full_runs,
                $row.retest_priority,
                $row.rejection_reasons,
                $row.active_session_source,
                $row.recommended_action,
                $row.active_session_prepare)
        }
    } else {
        Write-Output ("{0,-15} {1,8} {2,8} {3,5} {4,-15} {5,-9} {6,-6} {7,7} {8,-8} {9,-34} {10}" -f "known_true_addr", "full", "eligible", "quick", "latest_full", "rank_AWB", "stable", "missing", "priority", "rejection_reasons", "recommended_action")
        Write-Output ("{0,-15} {1,8} {2,8} {3,5} {4,-15} {5,-9} {6,-6} {7,7} {8,-8} {9,-34} {10}" -f "---------------", "----", "--------", "-----", "-----------", "--------", "------", "-------", "--------", "-----------------", "------------------")
        foreach ($row in @($Rows)) {
            Write-Output ("{0,-15} {1,8} {2,8} {3,5} {4,-15} {5,-9} {6,-6} {7,7} {8,-8} {9,-34} {10}" -f `
                $row.known_true_addr,
                $row.full_success_count,
                $row.baseline_eligible_count,
                $row.quick_success_count,
                $row.latest_full_batch,
                $row.latest_rank_AWB,
                $row.latest_stable_rank,
                $row.missing_clean_full_runs,
                $row.retest_priority,
                $row.rejection_reasons,
                $row.recommended_action)
        }
    }
}

function Invoke-RetestQueueCommand {
    param(
        [string]$CommandName,
        [bool]$LatestProvided,
        [bool]$ProfileProvided,
        [bool]$TargetUniqueProvided,
        [bool]$LimitProvided
    )

    $queueLatest = if ($LatestProvided) { $Latest } else { 200 }
    if ($queueLatest -lt 1) {
        Write-Output ("ERROR: -Latest must be greater than 0 for {0}" -f $CommandName)
        exit 1
    }
    if ($MinFullSuccess -lt 1) {
        Write-Output ("ERROR: -MinFullSuccess must be greater than 0 for {0}" -f $CommandName)
        exit 1
    }
    $queueLimit = if ($LimitProvided) { $Limit } else { 15 }
    if ($queueLimit -lt 1) {
        Write-Output ("ERROR: -Limit must be greater than 0 for {0}" -f $CommandName)
        exit 1
    }
    $queueTargetUnique = if ($TargetUniqueProvided -and $TargetUnique -gt 0) { $TargetUnique } else { 13 }
    $queueProfile = if ($ProfileProvided) { $Profile } else { "full" }
    $activeSessionRecord = $null
    if ($ActiveSession) {
        $activeSessionRecord = Assert-ActiveTestSessionForReuse -CommandName $CommandName
    }

    $queue = Get-RetestQueueSummary `
        -RequestedLatest $queueLatest `
        -RequestedProfile $queueProfile `
        -MinimumFullSuccess $MinFullSuccess `
        -RequestedTargetUnique $queueTargetUnique `
        -RequestedLimit $queueLimit `
        -ActiveSessionConfirmed $ActiveSession `
        -ActiveSessionRecord $activeSessionRecord
    if ($ActiveSession -and $activeSessionRecord) {
        $trackedState = Get-TrackedProcessState -Session $activeSessionRecord
        $queue.fields["active session id"] = Get-ObjectField -Object $activeSessionRecord -Key "session_id" -Default "-"
        $queue.fields["active session started_at_utc"] = Get-ObjectField -Object $activeSessionRecord -Key "started_at_utc" -Default "-"
        $queue.fields["active session label"] = Get-ObjectField -Object $activeSessionRecord -Key "label" -Default "-"
        $queue.fields["process tracking enabled"] = $trackedState.process_tracking_enabled
        $queue.fields["tracked process id"] = $trackedState.process_id
        $queue.fields["tracked process name"] = $trackedState.process_name
        $queue.fields["tracked process alive"] = $trackedState.tracked_process_alive
        $queue.fields["tracked process match"] = $trackedState.tracked_process_match
        $queue.fields["active-session warning"] = $(if ($trackedState.process_tracking_enabled) { "Tracked process is valid for this local marker." } else { "Manual session marker; process changes are not auto-detected." })
    }

    Write-WorkflowSummary -Title "Retest Queue Summary" -Fields $queue.fields
    Write-AddressLifetimeNote -Mode "retest" -ActiveSessionConfirmed $ActiveSession
    Write-RetestQueueTable -Rows $queue.rows -ActiveSessionConfirmed $ActiveSession
    exit 0
}

function Invoke-CollectionClassifierReadOnly {
    param(
        [int]$RequestedLatest,
        [string]$RequestedProfile,
        [switch]$OnlyBaselineEligible
    )

    $args = @("-Latest", "$RequestedLatest", "-Profile", $RequestedProfile)
    if ($OnlyBaselineEligible) {
        $args += "-OnlyBaselineEligible"
    }
    $args += @("-LogRoot", $LogRoot, "-ConsoleSummary")

    $output = @(& powershell -NoProfile -ExecutionPolicy Bypass -File $ClassifierPath @args 2>&1)
    $exitCode = $LASTEXITCODE
    $records = @()
    if ($exitCode -eq 0) {
        $records = @(Get-ClassifierConsoleRecords -OutputLines $output)
    }

    return [pscustomobject][ordered]@{
        exit_code = $exitCode
        output = @($output | ForEach-Object { "$_" })
        records = $records
    }
}

function Get-CollectionDoctorConclusion {
    $scriptPath = $PSCommandPath
    if (-not (Test-LogPresent -Value $scriptPath)) {
        $scriptPath = $MyInvocation.MyCommand.Path
    }
    if (-not (Test-LogPresent -Value $scriptPath)) {
        return [pscustomobject][ordered]@{
            conclusion = "not_available"
            exit_code = "not_available"
        }
    }

    $result = Invoke-DoctorPowerShellFile -FilePath $scriptPath -Arguments @(
        "doctor",
        "-Latest", "$Latest",
        "-ProjectRoot", $ProjectRootPath,
        "-LogRoot", $LogRoot
    )
    $conclusion = "not_available"
    foreach ($line in @($result.output)) {
        if ("$line" -match '^conclusion\s*=\s*(.+?)\s*$') {
            $conclusion = $matches[1].Trim()
        }
    }

    return [pscustomobject][ordered]@{
        conclusion = $conclusion
        exit_code = $result.exit_code
    }
}

function Get-CollectionSessionState {
    $session = Read-ActiveTestSession
    $trackedState = Get-TrackedProcessState -Session $session
    $status = Get-ObjectField -Object $session -Key "status" -Default "none"
    $active = Test-ActiveTestSession -Session $session
    $trackedStale = $false
    if ($active -and $trackedState.process_tracking_enabled -eq $true) {
        $trackedStale = ($trackedState.tracked_process_alive -ne $true) -or ($trackedState.tracked_process_match -ne $true)
    }

    $sessionConclusion = "SESSION_ENDED"
    if ($null -eq $session) {
        $sessionConclusion = "NO_ACTIVE_SESSION"
    } elseif ($trackedStale) {
        $sessionConclusion = "STALE_TRACKED_SESSION"
    } elseif ($active) {
        $sessionConclusion = "ACTIVE"
    } elseif ($status -eq "ended") {
        $sessionConclusion = "SESSION_ENDED"
    }

    return [pscustomobject][ordered]@{
        session = $session
        tracked_state = $trackedState
        status = $status
        active = $active
        tracked_stale = $trackedStale
        conclusion = $sessionConclusion
    }
}

function Get-CollectionCoverageHint {
    $latestCount = 20
    $result = Invoke-CollectionClassifierReadOnly -RequestedLatest $latestCount -RequestedProfile "full" -OnlyBaselineEligible
    if ($result.exit_code -ne 0) {
        return [pscustomobject][ordered]@{
            conclusion = "not_available"
            detail = "classifier latest full baseline-eligible summary failed"
        }
    }

    $records = @($result.records)
    $baselineExists = Test-Path -LiteralPath $BaselinePath
    $baselineUniqueCount = $null
    if ($baselineExists) {
        $baselineUniqueCount = Read-BaselineUniqueKnownTrueCount -Path $BaselinePath
    }
    $uniqueCount = Get-UniqueKnownTrueCount -Records $records
    $targetUnique = if ($null -ne $baselineUniqueCount) { [int]$baselineUniqueCount } else { $null }

    $conclusion = "NO_BASELINE"
    if ($records.Count -eq 0) {
        $conclusion = "INSUFFICIENT_DATA"
    } elseif ($null -ne $targetUnique) {
        if ($uniqueCount -ge $targetUnique) {
            $conclusion = "COVERAGE_OK"
        } else {
            $conclusion = "COVERAGE_WARN"
        }
    }

    return [pscustomobject][ordered]@{
        conclusion = $conclusion
        detail = ("latest={0}; eligible={1}; unique={2}; baseline_unique={3}" -f `
            $latestCount,
            $records.Count,
            $uniqueCount,
            $(if ($null -ne $baselineUniqueCount) { $baselineUniqueCount } else { "not_available" }))
    }
}

function Get-CollectionStableHint {
    $latestCount = 100
    $targetUniqueValue = 13
    $minFullSuccessValue = 2
    $result = Invoke-CollectionClassifierReadOnly -RequestedLatest $latestCount -RequestedProfile "full"
    if ($result.exit_code -ne 0) {
        return [pscustomobject][ordered]@{
            stable_readiness = "not_available"
            sample_plan_conclusion = "not_available"
            detail = "classifier latest full summary failed"
        }
    }

    $records = @($result.records | Where-Object { Test-LogPresent -Value (Get-RecordKnownTrueAddr -Record $_) })
    for ($i = 0; $i -lt $records.Count; $i++) {
        $records[$i] | Add-Member -NotePropertyName scan_order -NotePropertyValue ($i + 1) -Force
    }

    $stableCount = 0
    $groups = @($records | Group-Object { Get-RecordKnownTrueAddr -Record $_ })
    foreach ($group in $groups) {
        $addrRecords = @($group.Group | Sort-Object scan_order)
        $fullRecords = @($addrRecords | Where-Object { (Get-RecordField -Record $_ -Key "validation_profile") -eq "full" })
        $latestFull = @($fullRecords | Sort-Object scan_order | Select-Object -First 1)
        $latestFullRecord = if ($latestFull.Count -gt 0) { $latestFull[0] } else { $null }
        $fullSuccessCount = @($addrRecords | Where-Object { Test-RecordFullSuccess -Record $_ }).Count
        $baselineEligibleSuccessCount = @($addrRecords | Where-Object { Test-RecordBaselineEligibleSuccess -Record $_ }).Count
        $qualityIssueCount = @($addrRecords | Where-Object {
            (Get-RecordField -Record $_ -Key "classification") -in @(
                "invalid_config_mismatch",
                "known_true_value_mismatch",
                "ranking_issue",
                "selected_quota_issue"
            )
        }).Count
        $executionBatchCount = @($addrRecords | Where-Object { (Test-RecordExecutionBatch -Record $_) -or (Test-RecordWriteDependency -Record $_) }).Count

        $latestFullOk = $false
        if ($latestFullRecord) {
            $latestFullOk = (Test-RecordFullSuccess -Record $latestFullRecord) -and `
                (Test-LogTrue (Get-RecordField -Record $latestFullRecord -Key "final_hit")) -and `
                (Test-RankAwbOne -Value (Get-RecordField -Record $latestFullRecord -Key "rank_A/W/B")) -and `
                (Test-StableRankOne -Value (Get-RecordField -Record $latestFullRecord -Key "stable_rank"))
        }

        if ($fullSuccessCount -ge $minFullSuccessValue -and `
            $baselineEligibleSuccessCount -ge $minFullSuccessValue -and `
            $qualityIssueCount -eq 0 -and `
            $executionBatchCount -eq 0 -and `
            $latestFullOk) {
            $stableCount += 1
        }
    }

    $stableReadiness = if ($stableCount -ge $targetUniqueValue) { "READY_FOR_BASELINE" } else { "NEED_MORE_STABLE_CASES" }
    $sampleConclusion = if ($stableReadiness -eq "READY_FOR_BASELINE") { "READY_FOR_BASELINE" } else { "COLLECT_MORE_DISTINCT_CASES" }

    return [pscustomobject][ordered]@{
        stable_readiness = $stableReadiness
        sample_plan_conclusion = $sampleConclusion
        detail = ("latest={0}; unique={1}; stable_candidates={2}; target_unique={3}" -f `
            $latestCount,
            $groups.Count,
            $stableCount,
            $targetUniqueValue)
    }
}

function Get-CollectionFlowState {
    $config = Read-CaseConfigMap -Path $CaseConfigPath
    $configExists = Test-Path -LiteralPath $CaseConfigPath
    $targetConsistency = Get-TargetConsistencyCheck -Config $config
    $targetFloatPresent = Test-LogPresent -Value (Get-ConfigField -Config $config -Key "target_value_float")
    $targetPatternPresent = Test-LogPresent -Value (Get-ConfigField -Config $config -Key "target_value_pattern")
    $targetConfigValid = $configExists -and $targetFloatPresent -and $targetPatternPresent -and [bool]$targetConsistency.matches
    $plan = Get-NextRunPlan
    $sessionState = Get-CollectionSessionState
    $doctor = Get-CollectionDoctorConclusion
    $coverage = Get-CollectionCoverageHint
    $stable = Get-CollectionStableHint
    $intakeEvents = @(Read-CaseIntakeEvents)
    $openIntakes = @(Get-CaseIntakeOpenPreparedEvents -Events $intakeEvents)
    $latestOpenIntake = if ($openIntakes.Count -gt 0) { $openIntakes[$openIntakes.Count - 1] } else { $null }

    $gitStatus = @(& git -C $ProjectRootPath status --short 2>&1 | ForEach-Object { "$_" })
    $projectPathOk = [string]::Equals($ProjectRootPath, $ExpectedProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)
    $executionMode = Get-ConfigDisplayValue -Config $config -Key "execution_mode" -Default "disabled"
    $executionModeLower = "$executionMode".Trim().ToLowerInvariant()
    $writeEnabled = Test-ConfigBooleanTrue -Config $config -Key "write_enabled"
    $confirmPresent = Test-LogPresent -Value (Get-ConfigField -Config $config -Key "execution_confirm")
    $armPresent = Test-ExecutionArmPresent -Config $config
    $writeCapable = (Test-ExecutionConfigWriteCapable -Config $config) -or $armPresent -or ($plan.danger_level -eq "WRITE_CAPABLE") -or ($executionModeLower -notin @("", "disabled"))

    $conclusion = "SESSION_ENDED"
    if ($writeCapable) {
        $conclusion = "BLOCKED_WRITE_CAPABLE"
    } elseif (-not $targetConfigValid) {
        $conclusion = "BLOCKED_INVALID_CONFIG"
    } elseif ($sessionState.conclusion -eq "NO_ACTIVE_SESSION") {
        $conclusion = "NO_ACTIVE_SESSION"
    } elseif ($sessionState.conclusion -eq "STALE_TRACKED_SESSION") {
        $conclusion = "STALE_TRACKED_SESSION"
    } elseif ($sessionState.conclusion -eq "SESSION_ENDED") {
        $conclusion = "SESSION_ENDED"
    } elseif ($sessionState.active -and $plan.next_run_type -eq "detect_only" -and $plan.danger_level -eq "SAFE") {
        $conclusion = "READY_TO_COLLECT_CASE"
    } else {
        $conclusion = "BLOCKED_INVALID_CONFIG"
    }

    return [pscustomobject][ordered]@{
        conclusion = $conclusion
        fields = [ordered]@{
            "project root" = $ProjectRootPath
            "project path is v2 path" = $projectPathOk
            "git status" = $(if ($gitStatus.Count -eq 0) { "clean" } else { "{0} entries" -f $gitStatus.Count })
            "doctor conclusion" = $doctor.conclusion
            "doctor exit code" = $doctor.exit_code
            "plan next_run_type" = $plan.next_run_type
            "plan danger_level" = $plan.danger_level
            "config path" = $CaseConfigPath
            "config exists" = $configExists
            "validation_profile" = Get-ConfigDisplayValue -Config $config -Key "validation_profile"
            "diagnostic_level" = Get-ConfigDisplayValue -Config $config -Key "diagnostic_level"
            "target_value_float" = Get-ConfigDisplayValue -Config $config -Key "target_value_float"
            "target_value_pattern" = Get-ConfigDisplayValue -Config $config -Key "target_value_pattern"
            "expected pattern from float" = $targetConsistency.expected_pattern
            "target config consistent" = [bool]$targetConsistency.matches
            "target config valid" = $targetConfigValid
            "execution_mode" = $executionMode
            "write_enabled" = $writeEnabled
            "execution_confirm present" = $confirmPresent
            "execution arm present" = $armPresent
            "execution write-capable" = $writeCapable
            "session status" = $sessionState.status
            "session id" = Get-ObjectField -Object $sessionState.session -Key "session_id" -Default "-"
            "session conclusion" = $sessionState.conclusion
            "process_tracking_enabled" = $sessionState.tracked_state.process_tracking_enabled
            "tracked_process_alive" = $sessionState.tracked_state.tracked_process_alive
            "tracked_process_match" = $sessionState.tracked_state.tracked_process_match
            "tracked process note" = $(if ($sessionState.tracked_state.failure_reason) { $sessionState.tracked_state.failure_reason } else { "no tracked process issue detected" })
            "case-summary conclusion" = $coverage.conclusion
            "case-summary detail" = $coverage.detail
            "stable-cases readiness" = $stable.stable_readiness
            "stable-cases detail" = $stable.detail
            "sample-plan conclusion" = $stable.sample_plan_conclusion
            "open prepared intake count" = $openIntakes.Count
            "latest open intake" = Get-ObjectField -Object $latestOpenIntake -Key "intake_id" -Default "-"
            "case intake reminder" = $(if ($openIntakes.Count -gt 0) { "Open prepared case exists. Run CE and then post-current-case, or inspect case-intake-status." } else { "none" })
            "collection conclusion" = $conclusion
            "collection-flow mutates files" = $false
        }
    }
}

function Get-CollectionFlowSteps {
    param([string]$Conclusion)

    $ceCommand = 'dofile([[D:\armedforces.io-v2\src\execute_module-v5.2.0_batch.lua]])'
    $prefix = 'powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1"'
    switch ($Conclusion) {
        "BLOCKED_WRITE_CAPABLE" {
            return @(
                [pscustomobject][ordered]@{ Step = "1"; Action = "$prefix safe-reset -TargetValueFloat 100.0" },
                [pscustomobject][ordered]@{ Step = "2"; Action = "$prefix collection-flow" }
            )
        }
        "BLOCKED_INVALID_CONFIG" {
            return @(
                [pscustomobject][ordered]@{ Step = "1"; Action = "$prefix safe-reset -TargetValueFloat 100.0" },
                [pscustomobject][ordered]@{ Step = "2"; Action = "$prefix collection-flow" }
            )
        }
        "NO_ACTIVE_SESSION" {
            return @(
                [pscustomobject][ordered]@{ Step = "1"; Action = "$prefix session-start -Label `"case collection`"" },
                [pscustomobject][ordered]@{ Step = "2"; Action = "Manually verify a current-session known_true_addr" },
                [pscustomobject][ordered]@{ Step = "3"; Action = "$prefix collect-prepare -KnownTrueAddr `"<current_addr>`" -Profile full" },
                [pscustomobject][ordered]@{ Step = "4"; Action = "Run CE: $ceCommand" },
                [pscustomobject][ordered]@{ Step = "5"; Action = "$prefix post-current-case" }
            )
        }
        "SESSION_ENDED" {
            return @(
                [pscustomobject][ordered]@{ Step = "1"; Action = "$prefix session-start -Label `"case collection`"" },
                [pscustomobject][ordered]@{ Step = "2"; Action = "Collect new current-session addresses; do not reuse old addresses unless freshly verified" },
                [pscustomobject][ordered]@{ Step = "3"; Action = "$prefix collect-prepare -KnownTrueAddr `"<current_addr>`" -Profile full" },
                [pscustomobject][ordered]@{ Step = "4"; Action = "Run CE: $ceCommand" },
                [pscustomobject][ordered]@{ Step = "5"; Action = "$prefix post-current-case" }
            )
        }
        "STALE_TRACKED_SESSION" {
            return @(
                [pscustomobject][ordered]@{ Step = "1"; Action = "Review the tracked session; collection-flow does not auto-end it" },
                [pscustomobject][ordered]@{ Step = "2"; Action = "$prefix session-end -Reason `"tracked process changed`"" },
                [pscustomobject][ordered]@{ Step = "3"; Action = "$prefix session-start -Label `"case collection`"" },
                [pscustomobject][ordered]@{ Step = "4"; Action = "Manually verify a fresh current-session known_true_addr" }
            )
        }
        "READY_TO_COLLECT_CASE" {
            return @(
                [pscustomobject][ordered]@{ Step = "1"; Action = "$prefix sample-plan -ActiveSession" },
                [pscustomobject][ordered]@{ Step = "2"; Action = "Choose a currently valid known_true_addr from the active session" },
                [pscustomobject][ordered]@{ Step = "3"; Action = "$prefix collect-prepare -KnownTrueAddr `"<current_addr>`" -Profile full" },
                [pscustomobject][ordered]@{ Step = "4"; Action = "Run CE: $ceCommand" },
                [pscustomobject][ordered]@{ Step = "5"; Action = "$prefix post-current-case" },
                [pscustomobject][ordered]@{ Step = "6"; Action = "$prefix case-summary" }
            )
        }
        default {
            return @(
                [pscustomobject][ordered]@{ Step = "1"; Action = "$prefix doctor" },
                [pscustomobject][ordered]@{ Step = "2"; Action = "$prefix plan" }
            )
        }
    }
}

function Write-CollectionFlowSteps {
    param([object[]]$Rows)

    Write-Output ""
    Write-Output "Recommended Steps"
    Write-Output ("{0,-6} {1}" -f "Step", "Action")
    Write-Output ("{0,-6} {1}" -f "----", "------")
    foreach ($row in @($Rows)) {
        Write-Output ("{0,-6} {1}" -f $row.Step, $row.Action)
    }
}

function Write-PrepareCurrentCaseFailure {
    param(
        [string]$CommandName,
        [string]$Reason,
        [string]$Details,
        [string]$RecommendedFix
    )

    Write-WorkflowSummary -Title "Prepare Current Case Rejected" -Fields ([ordered]@{
        "command" = $CommandName
        "result" = "rejected before config write"
        "reason" = $Reason
        "details" = $Details
        "recommended fix" = $RecommendedFix
        "config modified" = $false
        "ce runtime run" = $false
    })
}

function Test-PrepareCurrentCasePreconditions {
    param([string]$CommandName, [string]$Address)

    if (-not (Test-KnownTrueAddr -Value $Address)) {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = "invalid_known_true_addr"
            details = Get-KnownTrueAddrValidationDetails -Value $Address
            recommended_fix = Get-KnownTrueAddrValidationRecommendation -Value $Address
            session = $null
            plan = $null
            config = $null
        }
    }

    $session = Read-ActiveTestSession
    if (-not (Test-ActiveTestSession -Session $session)) {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = "no_active_session"
            details = ("session status = {0}" -f (Get-ObjectField -Object $session -Key "status" -Default "none"))
            recommended_fix = 'test_session_tool.ps1 session-start -Label "case collection"'
            session = $session
            plan = $null
            config = $null
        }
    }

    $trackedState = Get-TrackedProcessState -Session $session
    if ($trackedState.process_tracking_enabled -eq $true -and (-not $trackedState.tracked_process_alive -or -not $trackedState.tracked_process_match)) {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = "stale_tracked_session"
            details = $(if ($trackedState.failure_reason) { $trackedState.failure_reason } else { "tracked process is not valid" })
            recommended_fix = 'test_session_tool.ps1 session-end -Reason "tracked process changed"; then start a new session'
            session = $session
            plan = $null
            config = $null
        }
    }

    $config = Read-CaseConfigMap -Path $CaseConfigPath
    $writeCapable = (Test-ExecutionConfigWriteCapable -Config $config) -or (Test-ExecutionArmPresent -Config $config)
    if ($writeCapable) {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = "write_capable_config"
            details = ("execution_mode={0}; write_enabled={1}; confirm_present={2}; arm_present={3}" -f `
                (Get-ConfigDisplayValue -Config $config -Key "execution_mode" -Default "disabled"),
                (Test-ConfigBooleanTrue -Config $config -Key "write_enabled"),
                (Test-LogPresent -Value (Get-ConfigField -Config $config -Key "execution_confirm")),
                (Test-ExecutionArmPresent -Config $config))
            recommended_fix = "test_session_tool.ps1 safe-reset -TargetValueFloat 100.0"
            session = $session
            plan = $null
            config = $config
        }
    }

    $targetConsistency = Get-TargetConsistencyCheck -Config $config
    $targetNormal = Test-NormalTargetConfig -Config $config
    if (-not $targetNormal -or -not [bool]$targetConsistency.matches) {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = "invalid_target_config"
            details = ("target_value_float={0}; target_value_pattern={1}; expected_pattern_from_float={2}; consistent={3}" -f `
                (Get-ConfigDisplayValue -Config $config -Key "target_value_float"),
                (Get-ConfigDisplayValue -Config $config -Key "target_value_pattern"),
                $targetConsistency.expected_pattern,
                [bool]$targetConsistency.matches)
            recommended_fix = "test_session_tool.ps1 safe-reset -TargetValueFloat 100.0"
            session = $session
            plan = $null
            config = $config
        }
    }

    $plan = Get-NextRunPlan
    if ($plan.next_run_type -ne "detect_only" -or $plan.danger_level -ne "SAFE") {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = "plan_not_safe"
            details = ("next_run_type={0}; danger_level={1}" -f $plan.next_run_type, $plan.danger_level)
            recommended_fix = "test_session_tool.ps1 plan"
            session = $session
            plan = $plan
            config = $config
        }
    }

    return [pscustomobject][ordered]@{
        ok = $true
        reason = "ok"
        details = "all preconditions passed"
        recommended_fix = "-"
        session = $session
        plan = $plan
        config = $config
    }
}

function Write-CollectPrepareFailure {
    param(
        [string]$CommandName,
        [string]$FailedGate,
        [string]$Reason,
        [string]$RecommendedFix
    )

    Write-WorkflowSummary -Title "Collect Prepare Summary" -Fields ([ordered]@{
        "command" = $CommandName
        "overall result" = "FAIL"
        "failed gate" = $FailedGate
        "reason" = $Reason
        "recommended fix" = $RecommendedFix
        "config modified" = $false
        "case intake appended" = $false
        "ce runtime run" = $false
    })
}

function Test-CollectPrepareDoctorGate {
    param([string]$CommandName)

    $scriptPath = Get-TestSessionToolScriptPath
    $doctorResult = Invoke-DoctorPowerShellFile -FilePath $scriptPath -Arguments @(
        "doctor",
        "-Latest", "$Latest",
        "-ProjectRoot", $ProjectRootPath,
        "-LogRoot", $LogRoot
    )
    $doctorConclusion = "not_available"
    foreach ($line in @($doctorResult.output)) {
        if ("$line" -match '^conclusion\s*=\s*(.+?)\s*$') {
            $doctorConclusion = $matches[1].Trim()
        }
    }
    if ($doctorResult.exit_code -ne 0 -or $doctorConclusion -ne "SAFE") {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = ("doctor conclusion={0}; exit_code={1}" -f $doctorConclusion, $doctorResult.exit_code)
            recommended_fix = "Run test_session_tool.ps1 doctor and resolve any FAIL/WARN before collect-prepare."
        }
    }

    $validateResult = Invoke-DoctorPowerShellFile -FilePath $CaseConfigToolPath -Arguments @("-Validate")
    if ($validateResult.exit_code -ne 0) {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = "case_config_tool.ps1 -Validate failed"
            recommended_fix = "Run case_config_tool.ps1 -Validate, then fix local config or safe-reset."
        }
    }

    $config = Read-CaseConfigMap -Path $CaseConfigPath
    $targetConsistency = Get-TargetConsistencyCheck -Config $config
    $targetNormal = Test-NormalTargetConfig -Config $config
    if (-not $targetNormal -or -not [bool]$targetConsistency.matches) {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = ("target_value_float={0}; target_value_pattern={1}; expected_pattern_from_float={2}; consistent={3}" -f `
                (Get-ConfigDisplayValue -Config $config -Key "target_value_float"),
                (Get-ConfigDisplayValue -Config $config -Key "target_value_pattern"),
                $targetConsistency.expected_pattern,
                [bool]$targetConsistency.matches)
            recommended_fix = "Run test_session_tool.ps1 safe-reset -TargetValueFloat 100.0."
        }
    }

    $executionMode = Get-ConfigDisplayValue -Config $config -Key "execution_mode" -Default "disabled"
    $executionModeLower = "$executionMode".Trim().ToLowerInvariant()
    $writeEnabled = Test-ConfigBooleanTrue -Config $config -Key "write_enabled"
    $confirmPresent = Test-LogPresent -Value (Get-ConfigField -Config $config -Key "execution_confirm")
    $armPresent = Test-ExecutionArmPresent -Config $config
    $writeCapable = (Test-ExecutionConfigWriteCapable -Config $config) -or $writeEnabled -or $confirmPresent -or $armPresent -or ($executionModeLower -notin @("", "disabled"))
    if ($writeCapable) {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = ("execution_mode={0}; write_enabled={1}; confirm_present={2}; arm_present={3}" -f $executionMode, $writeEnabled, $confirmPresent, $armPresent)
            recommended_fix = "Run test_session_tool.ps1 safe-reset -TargetValueFloat 100.0 before collecting cases."
        }
    }

    return [pscustomobject][ordered]@{
        ok = $true
        reason = "doctor SAFE; config valid; target normal; execution disabled"
        recommended_fix = "-"
    }
}

function Test-CollectPreparePlanGate {
    $plan = Get-NextRunPlan
    if ($plan.next_run_type -ne "detect_only" -or $plan.danger_level -ne "SAFE") {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = ("next_run_type={0}; danger_level={1}" -f $plan.next_run_type, $plan.danger_level)
            recommended_fix = "Run test_session_tool.ps1 plan and resolve unsafe next-run state."
            plan = $plan
        }
    }
    return [pscustomobject][ordered]@{
        ok = $true
        reason = "next_run_type=detect_only; danger_level=SAFE"
        recommended_fix = "-"
        plan = $plan
    }
}

function Test-CollectPrepareSessionGate {
    param([string]$CommandName, [string]$Address)

    if (-not (Test-LogPresent -Value $Address)) {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = "-KnownTrueAddr is required."
            recommended_fix = "Pass -KnownTrueAddr with a current-session hex address."
            session = $null
        }
    }
    if (-not (Test-KnownTrueAddr -Value $Address)) {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = Get-KnownTrueAddrValidationDetails -Value $Address
            recommended_fix = Get-KnownTrueAddrValidationRecommendation -Value $Address
            session = $null
        }
    }

    $session = Read-ActiveTestSession
    if (-not (Test-ActiveTestSession -Session $session)) {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = ("session status={0}" -f (Get-ObjectField -Object $session -Key "status" -Default "none"))
            recommended_fix = 'Run test_session_tool.ps1 session-start -Label "case collection".'
            session = $session
        }
    }

    $trackedState = Get-TrackedProcessState -Session $session
    if ($trackedState.process_tracking_enabled -eq $true -and (-not $trackedState.tracked_process_alive -or -not $trackedState.tracked_process_match)) {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = $(if ($trackedState.failure_reason) { $trackedState.failure_reason } else { "tracked process is not valid" })
            recommended_fix = 'Run session-end -Reason "tracked process changed", then start a new active session.'
            session = $session
        }
    }

    return [pscustomobject][ordered]@{
        ok = $true
        reason = ("session_id={0}; known_true_addr valid" -f (Get-ObjectField -Object $session -Key "session_id" -Default "-"))
        recommended_fix = "-"
        session = $session
    }
}

function Invoke-CollectPrepareCommand {
    param([string]$CommandName, [bool]$ProfileProvided)

    $collectProfile = if ($ProfileProvided) { $Profile } else { "full" }

    $sessionGate = Test-CollectPrepareSessionGate -CommandName $CommandName -Address $KnownTrueAddr
    if (-not $sessionGate.ok) {
        Write-CollectPrepareFailure -CommandName $CommandName -FailedGate "session/address" -Reason $sessionGate.reason -RecommendedFix $sessionGate.recommended_fix
        exit 1
    }

    $doctorGate = Test-CollectPrepareDoctorGate -CommandName $CommandName
    if (-not $doctorGate.ok) {
        Write-CollectPrepareFailure -CommandName $CommandName -FailedGate "doctor" -Reason $doctorGate.reason -RecommendedFix $doctorGate.recommended_fix
        exit 1
    }

    $planGate = Test-CollectPreparePlanGate
    if (-not $planGate.ok) {
        Write-CollectPrepareFailure -CommandName $CommandName -FailedGate "plan" -Reason $planGate.reason -RecommendedFix $planGate.recommended_fix
        exit 1
    }

    $scriptPath = Get-TestSessionToolScriptPath
    $prepareArgs = @(
        "prepare-current-case",
        "-KnownTrueAddr", $KnownTrueAddr,
        "-Profile", $collectProfile,
        "-ProjectRoot", $ProjectRootPath,
        "-LogRoot", $LogRoot
    )
    if ($CaseId) {
        $prepareArgs += @("-CaseId", $CaseId)
    }

    $prepareResult = Invoke-DoctorPowerShellFile -FilePath $scriptPath -Arguments $prepareArgs
    $prepareFields = Get-AlignedSummaryFieldMap -OutputLines $prepareResult.output
    if ($prepareResult.exit_code -ne 0) {
        Write-CollectPrepareFailure `
            -CommandName $CommandName `
            -FailedGate "prepare-current-case" `
            -Reason $(if ($prepareFields.ContainsKey("reason")) { $prepareFields["reason"] } else { ($prepareResult.output | Select-Object -First 1) }) `
            -RecommendedFix $(if ($prepareFields.ContainsKey("recommended fix")) { $prepareFields["recommended fix"] } else { "Run prepare-current-case directly for details." })
        exit $prepareResult.exit_code
    }

    Write-WorkflowSummary -Title "Collect Prepare Summary" -Fields ([ordered]@{
        "command" = $CommandName
        "overall result" = "PASS"
        "doctor gate" = "PASS"
        "plan gate" = "PASS"
        "session gate" = "PASS"
        "prepared known_true_addr" = $KnownTrueAddr
        "profile" = $collectProfile
        "intake_id" = $(if ($prepareFields.ContainsKey("intake_id")) { $prepareFields["intake_id"] } else { "-" })
        "session_id" = Get-ObjectField -Object $sessionGate.session -Key "session_id" -Default "-"
        "config modified" = $true
        "case intake appended" = $true
        "ce runtime run" = $false
        "next CE command" = 'dofile([[D:\armedforces.io-v2\src\execute_module-v5.2.0_batch.lua]])'
        "after CE command" = "test_session_tool.ps1 post-current-case"
    })
    exit 0
}

function Invoke-PrepareCurrentCaseCommand {
    param([string]$CommandName, [bool]$ProfileProvided)

    if (-not $KnownTrueAddr) {
        Write-PrepareCurrentCaseFailure `
            -CommandName $CommandName `
            -Reason "missing_known_true_addr" `
            -Details "-KnownTrueAddr is required." `
            -RecommendedFix "Pass -KnownTrueAddr with a current-session hex address."
        exit 1
    }

    $prepareProfile = if ($ProfileProvided) { $Profile } else { "full" }
    $precheck = Test-PrepareCurrentCasePreconditions -CommandName $CommandName -Address $KnownTrueAddr
    if (-not $precheck.ok) {
        Write-PrepareCurrentCaseFailure `
            -CommandName $CommandName `
            -Reason $precheck.reason `
            -Details $precheck.details `
            -RecommendedFix $precheck.recommended_fix
        exit 1
    }

    $args = @(
        "-Set",
        "-KnownTrueAddr", $KnownTrueAddr,
        "-TargetValuePattern", "0x42C80000",
        "-TargetValueFloat", "100.0",
        "-DiagnosticLevel", "basic",
        "-ValidationProfile", $prepareProfile
    )
    if ($CaseId) {
        $args = @("-Set", "-CaseId", $CaseId) + @($args | Select-Object -Skip 1)
    }

    $result = Invoke-DoctorPowerShellFile -FilePath $CaseConfigToolPath -Arguments $args
    if ($result.exit_code -ne 0) {
        $result.output | ForEach-Object { Write-Output $_ }
        exit $result.exit_code
    }

    $updatedConfig = Read-CaseConfigMap -Path $CaseConfigPath
    $intakeId = New-CaseIntakeId
    $preparedEvent = [ordered]@{
        event_type = "prepared"
        intake_id = $intakeId
        session_id = Get-ObjectField -Object $precheck.session -Key "session_id" -Default "-"
        known_true_addr = Get-ConfigDisplayValue -Config $updatedConfig -Key "known_true_addr"
        profile = Get-ConfigDisplayValue -Config $updatedConfig -Key "validation_profile"
        target_value_float = 100.0
        target_value_pattern = "0x42C80000"
        prepared_at_utc = Get-UtcTimestampText
        config_case_id = Get-ConfigDisplayValue -Config $updatedConfig -Key "case_id"
        status = "open"
        tool = "test_session_tool.ps1"
    }
    Add-CaseIntakeEvent -Record ([pscustomobject]$preparedEvent)

    $profilePostCommand = if ($prepareProfile -eq "quick") { "test_session_tool.ps1 post-quick" } else { "test_session_tool.ps1 post-full" }
    Write-WorkflowSummary -Title "Prepare Current Case Summary" -Fields ([ordered]@{
        "command" = $CommandName
        "intake_id" = $intakeId
        "session_id" = Get-ObjectField -Object $precheck.session -Key "session_id" -Default "-"
        "known_true_addr" = Get-ConfigDisplayValue -Config $updatedConfig -Key "known_true_addr"
        "profile" = Get-ConfigDisplayValue -Config $updatedConfig -Key "validation_profile"
        "target_value_float" = Get-ConfigDisplayValue -Config $updatedConfig -Key "target_value_float"
        "target_value_pattern" = Get-ConfigDisplayValue -Config $updatedConfig -Key "target_value_pattern"
        "precheck next_run_type" = $precheck.plan.next_run_type
        "precheck danger_level" = $precheck.plan.danger_level
        "config modified" = $true
        "intake journal appended" = $true
        "intake journal path" = $CaseIntakePath
        "ce runtime run" = $false
        "next CE command" = "dofile([[D:\armedforces.io-v2\src\execute_module-v5.2.0_batch.lua]])"
        "after CE command" = "test_session_tool.ps1 post-current-case"
        "profile post fallback" = $profilePostCommand
    })
    exit 0
}

function Write-CaseIntakeOpenTable {
    param([object[]]$Rows)

    Write-Output ""
    Write-Output "Open Prepared Cases"
    if (@($Rows).Count -eq 0) {
        Write-Output "none"
        return
    }

    Write-Output ("{0,-28} {1,-20} {2,-15} {3,-6} {4,-15} {5}" -f "intake_id", "prepared_at_utc", "known_true_addr", "profile", "session", "config_case_id")
    Write-Output ("{0,-28} {1,-20} {2,-15} {3,-6} {4,-15} {5}" -f "---------", "---------------", "---------------", "-------", "-------", "--------------")
    foreach ($row in @($Rows)) {
        Write-Output ("{0,-28} {1,-20} {2,-15} {3,-6} {4,-15} {5}" -f `
            (Get-ObjectField -Object $row -Key "intake_id" -Default "-"),
            (Get-ObjectField -Object $row -Key "prepared_at_utc" -Default "-"),
            (Get-ObjectField -Object $row -Key "known_true_addr" -Default "-"),
            (Get-ObjectField -Object $row -Key "profile" -Default "-"),
            (Get-ObjectField -Object $row -Key "session_id" -Default "-"),
            (Get-ObjectField -Object $row -Key "config_case_id" -Default "-"))
    }
}

function Write-CaseIntakeStatus {
    $events = @(Read-CaseIntakeEvents)
    $prepared = @(Get-CaseIntakePreparedEvents -Events $events)
    $completed = @(Get-CaseIntakeCompletedEvents -Events $events)
    $abandoned = @(Get-CaseIntakeAbandonedEvents -Events $events)
    $open = @(Get-CaseIntakeOpenPreparedEvents -Events $events)
    $latestPrepared = Get-LatestCaseIntakeEvent -Events $events -EventType "prepared"
    $latestCompleted = Get-LatestCaseIntakeEvent -Events $events -EventType "completed"
    $latestAbandoned = Get-LatestCaseIntakeEvent -Events $events -EventType "abandoned"
    $journalIgnored = Test-GitIgnoredPath -Path "log/case_intake.local.jsonl"

    Write-WorkflowSummary -Title "Case Intake Status" -Fields ([ordered]@{
        "journal path" = $CaseIntakePath
        "journal exists" = (Test-Path -LiteralPath $CaseIntakePath)
        "journal gitignored" = $journalIgnored
        "prepared event count" = $prepared.Count
        "open prepared case count" = $open.Count
        "completed event count" = $completed.Count
        "abandoned event count" = $abandoned.Count
        "latest prepared intake" = Get-ObjectField -Object $latestPrepared -Key "intake_id" -Default "-"
        "latest prepared addr" = Get-ObjectField -Object $latestPrepared -Key "known_true_addr" -Default "-"
        "latest completed intake" = Get-ObjectField -Object $latestCompleted -Key "intake_id" -Default "-"
        "latest completed batch" = Get-ObjectField -Object $latestCompleted -Key "batch_id" -Default "-"
        "latest abandoned intake" = Get-ObjectField -Object $latestAbandoned -Key "intake_id" -Default "-"
        "latest abandoned reason" = Get-ObjectField -Object $latestAbandoned -Key "reason" -Default "-"
        "ce runtime run" = $false
    })
    Write-CaseIntakeOpenTable -Rows $open
}

function Get-LatestOpenCaseIntake {
    param([object[]]$Events)

    $open = @(Get-CaseIntakeOpenPreparedEvents -Events $Events)
    if ($open.Count -eq 0) {
        return $null
    }
    return $open[$open.Count - 1]
}

function Test-IntakeBatchNewerThanPrepare {
    param($Intake, [string]$BatchId)

    $preparedAt = Convert-ConfigUtcDateTime -Value (Get-ObjectField -Object $Intake -Key "prepared_at_utc")
    if (-not $preparedAt) {
        return [pscustomobject][ordered]@{
            ok = $false
            detail = "prepared_at_utc missing or invalid"
        }
    }

    $summaryPath = Get-BatchSummaryPath -Root $LogRoot -Batch $BatchId
    if (-not $summaryPath) {
        return [pscustomobject][ordered]@{
            ok = $false
            detail = "latest batch summary/diagnostic file not found"
        }
    }

    $batchFile = Get-Item -LiteralPath $summaryPath
    $batchWriteUtc = $batchFile.LastWriteTimeUtc
    return [pscustomobject][ordered]@{
        ok = ($batchWriteUtc -gt $preparedAt)
        detail = ("batch_file_utc={0}; prepared_at_utc={1}; path={2}" -f `
            (Format-UtcTimestamp -Value $batchWriteUtc),
            (Format-UtcTimestamp -Value $preparedAt),
            $summaryPath)
    }
}

function Invoke-PostCurrentCaseCommand {
    $events = @(Read-CaseIntakeEvents)
    $latestPrepared = Get-LatestCaseIntakeEvent -Events $events -EventType "prepared"
    $openIntake = Get-LatestOpenCaseIntake -Events $events
    if (-not $openIntake) {
        $latestPreparedId = Get-ObjectField -Object $latestPrepared -Key "intake_id" -Default "-"
        Write-WorkflowSummary -Title "Post Current Case Summary" -Fields ([ordered]@{
            "result" = "no_open_prepared_case"
            "latest prepared intake" = $latestPreparedId
            "journal path" = $CaseIntakePath
            "completion appended" = $false
            "ce runtime run" = $false
            "recommended next step" = "case-intake-status"
        })
        exit 0
    }

    $intakeId = Get-ObjectField -Object $openIntake -Key "intake_id"
    $profile = Get-ObjectField -Object $openIntake -Key "profile"
    $knownTrueAddr = Get-ObjectField -Object $openIntake -Key "known_true_addr"
    if (-not (Test-LogPresent -Value $profile)) {
        $profile = "full"
    }

    $classifierResult = Invoke-CollectionClassifierReadOnly -RequestedLatest 1 -RequestedProfile $profile
    if ($classifierResult.exit_code -ne 0 -or @($classifierResult.records).Count -eq 0) {
        Write-WorkflowSummary -Title "Post Current Case Summary" -Fields ([ordered]@{
            "result" = "no matching latest batch"
            "intake_id" = $intakeId
            "reason" = "classifier latest batch unavailable"
            "completion appended" = $false
            "recommended next step" = "Run post-full or post-quick, case-intake-status, and confirm CE was run after prepare."
        })
        exit 1
    }

    $record = @($classifierResult.records)[0]
    $batchId = Get-RecordField -Record $record -Key "batch_id"
    $recordAddr = Get-RecordField -Record $record -Key "known_true_addr"
    $recordProfile = Get-RecordField -Record $record -Key "validation_profile"
    $batchFresh = Test-IntakeBatchNewerThanPrepare -Intake $openIntake -BatchId $batchId
    $addrMatches = [string]::Equals("$recordAddr", "$knownTrueAddr", [System.StringComparison]::OrdinalIgnoreCase)
    $profileMatches = [string]::Equals("$recordProfile", "$profile", [System.StringComparison]::OrdinalIgnoreCase)

    if (-not $addrMatches -or -not $profileMatches -or -not $batchFresh.ok) {
        Write-WorkflowSummary -Title "Post Current Case Summary" -Fields ([ordered]@{
            "result" = "no matching latest batch"
            "intake_id" = $intakeId
            "intake known_true_addr" = $knownTrueAddr
            "latest batch id" = $batchId
            "latest known_true_addr" = $recordAddr
            "addr matches" = $addrMatches
            "intake profile" = $profile
            "latest validation_profile" = $recordProfile
            "profile matches" = $profileMatches
            "batch newer than prepare" = $batchFresh.ok
            "batch freshness detail" = $batchFresh.detail
            "completion appended" = $false
            "recommended next step" = "Run CE after prepare, then post-current-case. You may also run post-full/post-quick and case-intake-status."
        })
        exit 1
    }

    $completedEvent = [ordered]@{
        event_type = "completed"
        intake_id = $intakeId
        session_id = Get-ObjectField -Object $openIntake -Key "session_id" -Default "-"
        known_true_addr = $knownTrueAddr
        profile = $profile
        completed_at_utc = Get-UtcTimestampText
        batch_id = $batchId
        classification = Get-RecordField -Record $record -Key "classification"
        final_hit = (Test-LogTrue (Get-RecordField -Record $record -Key "final_hit"))
        stable_rank = Get-RecordField -Record $record -Key "stable_rank"
        rank_AWB = Get-RecordField -Record $record -Key "rank_A/W/B"
        recommendation = Get-RecordField -Record $record -Key "recommendation"
        tool = "test_session_tool.ps1"
    }
    Add-CaseIntakeEvent -Record ([pscustomobject]$completedEvent)

    Write-WorkflowSummary -Title "Post Current Case Summary" -Fields ([ordered]@{
        "result" = "completed"
        "intake_id" = $intakeId
        "session_id" = Get-ObjectField -Object $openIntake -Key "session_id" -Default "-"
        "known_true_addr" = $knownTrueAddr
        "profile" = $profile
        "batch_id" = $batchId
        "classification" = $completedEvent.classification
        "final_hit" = $completedEvent.final_hit
        "stable_rank" = $completedEvent.stable_rank
        "rank_AWB" = $completedEvent.rank_AWB
        "recommendation" = $completedEvent.recommendation
        "completion appended" = $true
        "journal path" = $CaseIntakePath
    })
    exit 0
}

function Invoke-CaseIntakeAbandonCommand {
    param([string]$CommandName)

    $events = @(Read-CaseIntakeEvents)
    $openIntake = Get-LatestOpenCaseIntake -Events $events
    if (-not $openIntake) {
        Write-WorkflowSummary -Title "Case Intake Abandon Summary" -Fields ([ordered]@{
            "command" = $CommandName
            "result" = "no open prepared intake"
            "abandoned appended" = $false
            "journal path" = $CaseIntakePath
            "ce runtime run" = $false
            "recommended next step" = "case-intake-status"
        })
        exit 0
    }

    $reasonText = if ([string]::IsNullOrWhiteSpace($Reason)) { "not specified" } else { $Reason.Trim() }
    $abandonedEvent = [ordered]@{
        event_type = "abandoned"
        intake_id = Get-ObjectField -Object $openIntake -Key "intake_id" -Default "-"
        session_id = Get-ObjectField -Object $openIntake -Key "session_id" -Default "-"
        known_true_addr = Get-ObjectField -Object $openIntake -Key "known_true_addr" -Default "-"
        profile = Get-ObjectField -Object $openIntake -Key "profile" -Default "-"
        abandoned_at_utc = Get-UtcTimestampText
        reason = $reasonText
        tool = "test_session_tool.ps1"
    }
    Add-CaseIntakeEvent -Record ([pscustomobject]$abandonedEvent)

    Write-WorkflowSummary -Title "Case Intake Abandon Summary" -Fields ([ordered]@{
        "command" = $CommandName
        "result" = "abandoned"
        "intake_id" = $abandonedEvent.intake_id
        "session_id" = $abandonedEvent.session_id
        "known_true_addr" = $abandonedEvent.known_true_addr
        "profile" = $abandonedEvent.profile
        "abandoned_at_utc" = $abandonedEvent.abandoned_at_utc
        "reason" = $abandonedEvent.reason
        "abandoned appended" = $true
        "journal path" = $CaseIntakePath
        "config modified" = $false
        "ce runtime run" = $false
    })
    exit 0
}

function New-WorkflowHelpItem {
    param(
        [string]$Category,
        [string]$CommandName,
        [string]$Purpose,
        [string]$Syntax,
        [string]$Example,
        [string]$SafetyNotes,
        [string]$NextCommand
    )

    return [pscustomobject][ordered]@{
        category = $Category
        command = $CommandName
        purpose = $Purpose
        syntax = $Syntax
        example = $Example
        safety_notes = $SafetyNotes
        next_command = $NextCommand
    }
}

function Get-WorkflowHelpItems {
    $prefix = 'powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1"'
    return @(
        New-WorkflowHelpItem "Safety / Preflight" "plan" "Preview what the next manual CE run would do" "test_session_tool.ps1 plan" "$prefix plan" "Read-only; does not run CE or modify local config" "run CE manually only if the plan is acceptable"
        New-WorkflowHelpItem "Safety / Preflight" "preview-next-run" "Alias for plan" "test_session_tool.ps1 preview-next-run" "$prefix preview-next-run" "Read-only; same output as plan" "run CE manually only if the plan is acceptable"
        New-WorkflowHelpItem "Safety / Preflight" "doctor" "Run read-only preflight and safety checks" "test_session_tool.ps1 doctor [-Latest 50]" "$prefix doctor" "Read-only; does not run CE or write registry" "status"
        New-WorkflowHelpItem "Safety / Preflight" "collection-flow" "Guide current-session case collection without mutating config or session state" "test_session_tool.ps1 collection-flow" "$prefix collection-flow" "Strictly read-only; shows open case intake reminders without writing the append-only local journal" "session-start or sample-plan -ActiveSession"
        New-WorkflowHelpItem "Safety / Preflight" "collect-guide" "Alias for collection-flow" "test_session_tool.ps1 collect-guide" "$prefix collect-guide" "Strictly read-only; same output as collection-flow" "session-start or sample-plan -ActiveSession"
        New-WorkflowHelpItem "Safety / Preflight" "status" "Show config, recent classifier output, registry summary, and git status" "test_session_tool.ps1 status" "$prefix status" "Read-only; may print current write-capable warnings" "execution-status -IncludeResolved"
        New-WorkflowHelpItem "Safety / Preflight" "diagnostic-status" "Show current diagnostic/logging level and latest log size" "test_session_tool.ps1 diagnostic-status" "$prefix diagnostic-status" "Read-only; does not run CE or modify config" "set-diagnostic -Level basic"
        New-WorkflowHelpItem "Safety / Preflight" "set-diagnostic" "Set local diagnostic level to basic, debug, or trace" "test_session_tool.ps1 set-diagnostic -Level basic|debug|trace" "$prefix set-diagnostic -Level debug" "Writes ignored local config only; trace can produce large logs" "diagnostic-status"
        New-WorkflowHelpItem "Safety / Preflight" "safe-reset" "Disable execution and optionally reset target to safe value" "test_session_tool.ps1 safe-reset [-TargetValueFloat 100.0]" "$prefix safe-reset -TargetValueFloat 100.0" "Writes local config; does not run CE" "doctor"
        New-WorkflowHelpItem "Safety / Preflight" "session-start" "Create local active manual test session marker" "test_session_tool.ps1 session-start [-Label <text>] [-TrackProcess -ProcessId <pid>|-ProcessName <name>]" "$prefix session-start -Label `"baseline collection`"; $prefix session-start -Label `"tracked`" -TrackProcess -ProcessId 12345" "Manual-only by default; optional process tracking; no default expiry; operator marker only" "sample-plan -ActiveSession"
        New-WorkflowHelpItem "Safety / Preflight" "session-status" "Show local active manual test session state and config context" "test_session_tool.ps1 session-status" "$prefix session-status" "Read-only; -ActiveSession depends on this local session record" "sample-plan"
        New-WorkflowHelpItem "Safety / Preflight" "session-end" "End local active manual test session marker" "test_session_tool.ps1 session-end [-Reason <text>]" "$prefix session-end -Reason `"manual validation complete`"" "Ends active-session reuse guidance; does not run CE or modify config" "sample-plan"
        New-WorkflowHelpItem "Safety / Preflight" "session-watch" "Foreground watch for a process-tracked active session" "test_session_tool.ps1 session-watch [-IntervalSeconds 10] [-Once]" "$prefix session-watch -Once" "Only works with -TrackProcess sessions; no default expiry is enabled" "session-end"
        New-WorkflowHelpItem "Detect-only workflow" "prepare" "Prepare local case config for a manual CE detect run" "test_session_tool.ps1 prepare -KnownTrueAddr <addr> [-CaseId <id>] [-Profile quick|full]" "$prefix prepare -KnownTrueAddr `"0x25A061C7D48`" -Profile full" "Writes local config; validates KnownTrueAddr; does not run CE" "run CE manually, then post-full or post-quick"
        New-WorkflowHelpItem "Detect-only workflow" "collect-prepare" "Run one-shot collection preflight gates, then prepare current case" "test_session_tool.ps1 collect-prepare -KnownTrueAddr <addr> [-CaseId <id>] [-Profile quick|full]" "$prefix collect-prepare -KnownTrueAddr `"0x25A061C7D48`" -Profile full" "Runs doctor, plan, and session/address gates before calling prepare-current-case; writes local config and intake only if all gates pass; does not run CE" "run CE manually, then post-current-case"
        New-WorkflowHelpItem "Detect-only workflow" "prepare-collection-case" "Alias for collect-prepare" "test_session_tool.ps1 prepare-collection-case -KnownTrueAddr <addr> [-CaseId <id>] [-Profile quick|full]" "$prefix prepare-collection-case -KnownTrueAddr `"0x25A061C7D48`" -Profile full" "Same gated behavior as collect-prepare" "run CE manually, then post-current-case"
        New-WorkflowHelpItem "Detect-only workflow" "prepare-current-case" "Guarded active-session prepare for current case collection" "test_session_tool.ps1 prepare-current-case -KnownTrueAddr <addr> [-CaseId <id>] [-Profile quick|full]" "$prefix prepare-current-case -KnownTrueAddr `"0x25A061C7D48`" -Profile full" "Requires active manual test session; checks plan SAFE, target 100.0/0x42C80000, and non-write-capable config before writing local config; appends an ignored prepared intake event; does not run CE" "run CE manually, then post-current-case"
        New-WorkflowHelpItem "Detect-only workflow" "prepare-case" "Alias for prepare-current-case" "test_session_tool.ps1 prepare-case -KnownTrueAddr <addr> [-CaseId <id>] [-Profile quick|full]" "$prefix prepare-case -KnownTrueAddr `"0x25A061C7D48`" -Profile full" "Preferred alias/wrapper over raw prepare; writes local config and appends ignored local intake journal only after guard checks; does not run CE" "run CE manually, then post-current-case"
        New-WorkflowHelpItem "Detect-only workflow" "case-intake-status" "Show open and completed local current-case intake journal entries" "test_session_tool.ps1 case-intake-status" "$prefix case-intake-status" "Read-only; journal is append-only ignored local state under log/case_intake.local.jsonl" "post-current-case"
        New-WorkflowHelpItem "Detect-only workflow" "case-intake-abandon" "Abandon latest open prepared intake when CE was not run" "test_session_tool.ps1 case-intake-abandon [-Reason <text>]" "$prefix case-intake-abandon -Reason `"decided not to run CE`"" "Appends ignored local abandoned event only; does not rewrite journal, run CE, or modify config" "case-intake-status"
        New-WorkflowHelpItem "Detect-only workflow" "abandon-current-case" "Alias for case-intake-abandon" "test_session_tool.ps1 abandon-current-case [-Reason <text>]" "$prefix abandon-current-case -Reason `"validation no CE run`"" "Appends ignored local abandoned event only; same behavior as case-intake-abandon" "case-intake-status"
        New-WorkflowHelpItem "Detect-only workflow" "post-current-case" "Safely complete latest matching prepared current case after CE" "test_session_tool.ps1 post-current-case" "$prefix post-current-case" "Does not run CE; appends completed event only if latest batch matches open intake by addr/profile and is newer than prepare" "case-summary"
        New-WorkflowHelpItem "Detect-only workflow" "post-full" "Classify latest full batch and append registry" "test_session_tool.ps1 post-full" "$prefix post-full" "Does not run CE; appends registry record" "compare-full"
        New-WorkflowHelpItem "Detect-only workflow" "post-quick" "Classify latest quick batch and append registry" "test_session_tool.ps1 post-quick" "$prefix post-quick" "Does not run CE; appends registry record" "prepare-current-case -Profile full"
        New-WorkflowHelpItem "Detect-only workflow" "compare-full" "Compare latest clean full batches against the default baseline" "test_session_tool.ps1 compare-full" "$prefix compare-full" "Read-only; uses baseline-eligible full batches only" "baseline-current"
        New-WorkflowHelpItem "Execution workflow" "prepare-dry-run-write" "Prepare full/basic execution dry-run config" "test_session_tool.ps1 prepare-dry-run-write -KnownTrueAddr <addr> -WriteValueFloat <float>" "$prefix prepare-dry-run-write -KnownTrueAddr `"0x25A061C7D48`" -WriteValueFloat 999.0" "Writes local config but does not arm live write" "run CE manually, then post-full"
        New-WorkflowHelpItem "Execution workflow" "prepare-guarded-write" "Prepare guarded live write config with confirm and arm" "test_session_tool.ps1 prepare-guarded-write -KnownTrueAddr <addr> -WriteValueFloat <float> -ConfirmWrite" "$prefix prepare-guarded-write -KnownTrueAddr `"0x25A061C7D48`" -WriteValueFloat 999.0 -ConfirmWrite" "Writes live-memory capable config; run CE only when ready before arm expiry" "post-execution"
        New-WorkflowHelpItem "Execution workflow" "post-execution" "Summarize latest full execution fields after manual CE run" "test_session_tool.ps1 post-execution" "$prefix post-execution" "Read-only; does not run CE" "prepare-restore or safe-reset"
        New-WorkflowHelpItem "Restore / transaction safety" "prepare-restore" "Prepare restore config from a successful write batch" "test_session_tool.ps1 prepare-restore -BatchId <YYYYMMDD-HHMMSS> [-EnableWrite -ConfirmWrite]" "$prefix prepare-restore -BatchId `"20260613-225514`" -EnableWrite -ConfirmWrite" "Validates BatchId; write-ready only with both EnableWrite and ConfirmWrite" "run CE manually, then post-execution"
        New-WorkflowHelpItem "Restore / transaction safety" "execution-status" "Show write/restore transaction safety status" "test_session_tool.ps1 execution-status [-Latest 50] [-IncludeResolved]" "$prefix execution-status -IncludeResolved" "Read-only; resolved writes are local ignored state" "safe-reset"
        New-WorkflowHelpItem "Restore / transaction safety" "mark-write-resolved" "Mark a historical write_success as manually restored" "test_session_tool.ps1 mark-write-resolved -BatchId <YYYYMMDD-HHMMSS> -Reason <text>" "$prefix mark-write-resolved -BatchId `"20260613-225514`" -Reason `"manual restore to 100.0`"" "Writes ignored local JSONL only; use only after manual recovery is confirmed" "execution-status -IncludeResolved"
        New-WorkflowHelpItem "Baseline management" "baseline-list" "List local baseline Markdown files" "test_session_tool.ps1 baseline-list" "$prefix baseline-list" "Read-only; baselines live under ignored log/baselines" "baseline-current"
        New-WorkflowHelpItem "Baseline management" "baseline-current" "Show current default compare-full baseline" "test_session_tool.ps1 baseline-current" "$prefix baseline-current" "Read-only" "baseline-compare"
        New-WorkflowHelpItem "Baseline management" "baseline-save" "Save latest baseline-eligible full snapshot as a local baseline" "test_session_tool.ps1 baseline-save -Name <safe-name> [-Latest 20]" "$prefix baseline-save -Name `"full_clean_YYYYMMDD`" -Latest 20" "Writes ignored log/baselines/*.md; do not commit baseline files" "baseline-compare"
        New-WorkflowHelpItem "Baseline management" "baseline-compare" "Compare latest clean full batches against a chosen baseline" "test_session_tool.ps1 baseline-compare -Baseline <file-or-path> [-Latest 20]" "$prefix baseline-compare -Baseline `"baseline_compact_basic_20260613_latest20.md`"" "Read-only; rejects missing baseline file" "compare-full"
        New-WorkflowHelpItem "Baseline management" "case-library" "Summarize historical and active-session known_true_addr evidence" "test_session_tool.ps1 case-library [-Latest 100] [-Profile full|quick]" "$prefix case-library -Latest 100" "Read-only; known_true_addr is active-test-session scoped and reusable only before the manual session ends" "case-summary"
        New-WorkflowHelpItem "Baseline management" "stable-cases" "List stable evidence for baseline candidates and rejection reasons" "test_session_tool.ps1 stable-cases [-Latest 100] [-Profile full] [-MinFullSuccess 2] [-TargetUnique 13] [-ShowRejected] [-KnownTrueAddr <addr>]" "$prefix stable-cases -ShowRejected; $prefix stable-cases -KnownTrueAddr `"0x25A061C7D48`"" "Read-only; stable means evidence in logs, not permanent address validity; known_true_addr is active-test-session scoped" "baseline-save"
        New-WorkflowHelpItem "Baseline management" "baseline-candidates" "Alias for stable-cases" "test_session_tool.ps1 baseline-candidates [-Latest 100] [-Profile full] [-ShowRejected]" "$prefix baseline-candidates" "Read-only; same output as stable-cases; known_true_addr is active-test-session scoped" "baseline-save"
        New-WorkflowHelpItem "Baseline management" "retest-queue" "Plan active-session retests or new current-session samples from rejected stable-cases" "test_session_tool.ps1 retest-queue [-Latest 200] [-Profile full] [-MinFullSuccess 2] [-TargetUnique 13] [-Limit 15] [-ActiveSession]" "$prefix retest-queue -Latest 200 -Limit 10; $prefix retest-queue -ActiveSession" "Read-only; -ActiveSession shows prepare commands only for addresses observed or intaked in the current active session" "prepare-current-case"
        New-WorkflowHelpItem "Baseline management" "sample-plan" "Alias for retest-queue" "test_session_tool.ps1 sample-plan [-Latest 200] [-Profile full] [-Limit 15] [-ActiveSession]" "$prefix sample-plan -ActiveSession" "Read-only; historical addresses remain historical unless manually re-verified in the current session" "prepare-current-case"
        New-WorkflowHelpItem "Baseline management" "case-summary" "Summarize known_true_addr coverage for latest baseline-eligible batches" "test_session_tool.ps1 case-summary [-Latest 20] [-Profile full] [-Baseline <file-or-path>] [-TargetUnique 13]" "$prefix case-summary -Latest 20" "Read-only; does not run CE or write files" "collect new distinct full cases if coverage warns"
        New-WorkflowHelpItem "Baseline management" "coverage-plan" "Alias for case-summary" "test_session_tool.ps1 coverage-plan [-Latest 20] [-Profile full]" "$prefix coverage-plan" "Read-only; same output as case-summary" "collect new distinct full cases if coverage warns"
        New-WorkflowHelpItem "Diagnostics / inspection" "inspect-latest" "Inspect the latest batch id from LogRoot" "test_session_tool.ps1 inspect-latest" "$prefix inspect-latest" "Read-only; does not run CE" "doctor"
        New-WorkflowHelpItem "Diagnostics / inspection" "help" "List workflow commands or show command-specific help" "test_session_tool.ps1 help [-Command <name>]" "$prefix help -Command prepare-restore" "Read-only" "doctor"
    )
}

function Get-WorkflowHelpItem {
    param([string]$CommandName)

    foreach ($item in @(Get-WorkflowHelpItems)) {
        if ([string]::Equals($item.command, $CommandName, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $item
        }
    }
    return $null
}

function Write-WorkflowCommandIndex {
    $items = @(Get-WorkflowHelpItems)
    Write-Output ""
    Write-Output "Workflow Command Index"
    foreach ($category in @("Safety / Preflight", "Detect-only workflow", "Execution workflow", "Restore / transaction safety", "Baseline management", "Diagnostics / inspection")) {
        Write-Output ""
        Write-Output $category
        Write-Output ("{0,-24} {1,-82} {2}" -f "Command", "Purpose", "Next")
        Write-Output ("{0,-24} {1,-82} {2}" -f "-------", "-------", "----")
        foreach ($item in @($items | Where-Object { $_.category -eq $category })) {
            Write-Output ("{0,-24} {1,-82} {2}" -f $item.command, $item.purpose, $item.next_command)
        }
    }
    Write-Output ""
    Write-Output "For command details: test_session_tool.ps1 help -Command <name>"
}

function Write-WorkflowSpecificHelp {
    param([string]$CommandName)

    $item = Get-WorkflowHelpItem -CommandName $CommandName
    if (-not $item) {
        Write-Output ("ERROR: unknown command: {0}" -f $CommandName)
        Write-Output "Run: test_session_tool.ps1 help"
        exit 1
    }

    Write-WorkflowSummary -Title ("Command Help: {0}" -f $item.command) -Fields ([ordered]@{
        "category" = $item.category
        "purpose" = $item.purpose
        "syntax" = $item.syntax
        "common example" = $item.example
        "safety notes" = $item.safety_notes
        "related next command" = $item.next_command
    })
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
    "help",
    "plan",
    "preview-next-run",
    "collection-flow",
    "collect-guide",
    "session-start",
    "session-status",
    "session-end",
    "session-watch",
    "prepare",
    "collect-prepare",
    "prepare-collection-case",
    "prepare-current-case",
    "prepare-case",
    "case-intake-status",
    "case-intake-abandon",
    "abandon-current-case",
    "post-current-case",
    "post-quick",
    "post-full",
    "compare-full",
    "baseline-list",
    "baseline-current",
    "baseline-save",
    "baseline-compare",
    "case-library",
    "stable-cases",
    "baseline-candidates",
    "retest-queue",
    "sample-plan",
    "case-summary",
    "coverage-plan",
    "inspect-latest",
    "status",
    "diagnostic-status",
    "set-diagnostic",
    "disable-execution",
    "safe-reset",
    "prepare-dry-run-write",
    "prepare-guarded-write",
    "prepare-restore",
    "post-execution",
    "execution-status",
    "mark-write-resolved",
    "doctor"
)

$RequestedHelpCommand = $Command
if (-not $Action -and $Command) {
    $Action = $Command
    $RequestedHelpCommand = $null
}

if ($Help -or -not $Action) {
    Write-CommandHelp
    exit 0
}

if (-not ($availableCommands -contains $Action)) {
    Write-Warning ("Unknown command: {0}" -f $Action)
    Write-CommandHelp
    exit 1
}

Assert-ToolExists -Path $CaseConfigToolPath
Assert-ToolExists -Path $ClassifierPath

if (-not [string]::Equals($ProjectRootPath, $ExpectedProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Warning ("Active project root is {0}; expected {1}" -f $ProjectRootPath, $ExpectedProjectRoot)
}

switch ($Action) {
    "help" {
        if ($RequestedHelpCommand) {
            Write-WorkflowSpecificHelp -CommandName $RequestedHelpCommand
        } else {
            Write-WorkflowCommandIndex
        }
        exit 0
    }

    "session-start" {
        $existingSession = Read-ActiveTestSession
        if (Test-ActiveTestSession -Session $existingSession) {
            Write-WorkflowSummary -Title "Active Test Session Summary" -Fields (Get-TestSessionSummaryFields `
                -Session $existingSession `
                -Action "already active" `
                -RecommendedNextStep "Use sample-plan -ActiveSession only if CE/process/scene is still unchanged.")
            exit 0
        }

        $trackedProcess = Resolve-TrackedProcess
        $session = New-ActiveTestSession -SessionLabel $Label -TrackedProcess $trackedProcess
        Write-ActiveTestSession -Session $session
        Write-WorkflowSummary -Title "Active Test Session Summary" -Fields (Get-TestSessionSummaryFields `
            -Session $session `
            -Action "started" `
            -RecommendedNextStep "You may use sample-plan -ActiveSession only if CE/process/scene is still unchanged.")
        if (-not $TrackProcess) {
            Write-Output "WARNING: Manual session marker only. Run session-end when CE/process/scene changes or testing ends."
        }
        exit 0
    }

    "session-status" {
        $session = Update-TrackedSessionIfInvalid -Session (Read-ActiveTestSession)
        $nextStep = if (Test-ActiveTestSession -Session $session) {
            "You may use sample-plan -ActiveSession only if CE/process/scene is still unchanged."
        } else {
            "Use sample-plan without -ActiveSession and collect new current-session addresses."
        }
        Write-WorkflowSummary -Title "Active Test Session Summary" -Fields (Get-TestSessionSummaryFields `
            -Session $session `
            -Action "status" `
            -RecommendedNextStep $nextStep)
        exit 0
    }

    "session-end" {
        $session = Update-TrackedSessionIfInvalid -Session (Read-ActiveTestSession)
        if (-not (Test-ActiveTestSession -Session $session)) {
            Write-WorkflowSummary -Title "Active Test Session Summary" -Fields (Get-TestSessionSummaryFields `
                -Session $session `
                -Action "no active session" `
                -RecommendedNextStep "Use sample-plan without -ActiveSession and collect new current-session addresses.")
            exit 0
        }

        $endedSession = Complete-ActiveTestSession -Session $session -EndReason $Reason
        Write-WorkflowSummary -Title "Active Test Session Summary" -Fields (Get-TestSessionSummaryFields `
            -Session $endedSession `
            -Action "ended" `
            -RecommendedNextStep "Use sample-plan without -ActiveSession and collect new current-session addresses.")
        exit 0
    }

    "session-watch" {
        if ($IntervalSeconds -lt 1) {
            Write-Output "ERROR: -IntervalSeconds must be greater than 0 for session-watch."
            exit 1
        }
        $session = Update-TrackedSessionIfInvalid -Session (Read-ActiveTestSession)
        if (-not (Test-ActiveTestSession -Session $session)) {
            Write-WorkflowSummary -Title "Session Watch Summary" -Fields (Get-TestSessionSummaryFields `
                -Session $session `
                -Action "no active tracked session" `
                -RecommendedNextStep "Start a tracked session with session-start -TrackProcess before using session-watch.")
            exit 1
        }
        $trackedState = Get-TrackedProcessState -Session $session
        if (-not $trackedState.process_tracking_enabled) {
            Write-WorkflowSummary -Title "Session Watch Summary" -Fields (Get-TestSessionSummaryFields `
                -Session $session `
                -Action "process tracking disabled" `
                -RecommendedNextStep "session-watch requires session-start -TrackProcess. Manual sessions do not auto-end.")
            exit 1
        }

        Write-Output "Session watch started. Press Ctrl+C to stop foreground polling."
        while ($true) {
            $session = Update-TrackedSessionIfInvalid -Session (Read-ActiveTestSession)
            $trackedState = Get-TrackedProcessState -Session $session
            Write-WorkflowSummary -Title "Session Watch Poll" -Fields (Get-TestSessionSummaryFields `
                -Session $session `
                -Action "poll" `
                -RecommendedNextStep $(if (Test-ActiveTestSession -Session $session) { "Process still matches; continue only while CE/process/scene is unchanged." } else { "Session ended; use sample-plan without -ActiveSession." }))
            if (-not (Test-ActiveTestSession -Session $session)) {
                exit 0
            }
            if ($Once) {
                exit 0
            }
            Start-Sleep -Seconds $IntervalSeconds
        }
    }

    "plan" {
        $plan = Get-NextRunPlan
        Write-NextRunPlan -Plan $plan
        exit $plan.exit_code
    }

    "preview-next-run" {
        $plan = Get-NextRunPlan
        Write-NextRunPlan -Plan $plan
        exit $plan.exit_code
    }

    "collection-flow" {
        $flow = Get-CollectionFlowState
        Write-WorkflowSummary -Title "Collection Flow Summary" -Fields $flow.fields
        Write-CollectionFlowSteps -Rows (Get-CollectionFlowSteps -Conclusion $flow.conclusion)
        Write-Output ""
        Write-Output "CE Runtime Command"
        Write-Output "dofile([[D:\armedforces.io-v2\src\execute_module-v5.2.0_batch.lua]])"
        exit 0
    }

    "collect-guide" {
        $flow = Get-CollectionFlowState
        Write-WorkflowSummary -Title "Collection Flow Summary" -Fields $flow.fields
        Write-CollectionFlowSteps -Rows (Get-CollectionFlowSteps -Conclusion $flow.conclusion)
        Write-Output ""
        Write-Output "CE Runtime Command"
        Write-Output "dofile([[D:\armedforces.io-v2\src\execute_module-v5.2.0_batch.lua]])"
        exit 0
    }

    "diagnostic-status" {
        Write-DiagnosticStatus
        exit 0
    }

    "collect-prepare" {
        Invoke-CollectPrepareCommand -CommandName "collect-prepare" -ProfileProvided ($PSBoundParameters.ContainsKey("Profile"))
    }

    "prepare-collection-case" {
        Invoke-CollectPrepareCommand -CommandName "prepare-collection-case" -ProfileProvided ($PSBoundParameters.ContainsKey("Profile"))
    }

    "prepare-current-case" {
        Invoke-PrepareCurrentCaseCommand -CommandName "prepare-current-case" -ProfileProvided ($PSBoundParameters.ContainsKey("Profile"))
    }

    "prepare-case" {
        Invoke-PrepareCurrentCaseCommand -CommandName "prepare-case" -ProfileProvided ($PSBoundParameters.ContainsKey("Profile"))
    }

    "case-intake-status" {
        Write-CaseIntakeStatus
        exit 0
    }

    "case-intake-abandon" {
        Invoke-CaseIntakeAbandonCommand -CommandName "case-intake-abandon"
    }

    "abandon-current-case" {
        Invoke-CaseIntakeAbandonCommand -CommandName "abandon-current-case"
    }

    "post-current-case" {
        Invoke-PostCurrentCaseCommand
    }

    "set-diagnostic" {
        $requestedLevel = $Level
        if (-not $requestedLevel -and $PSBoundParameters.ContainsKey("DiagnosticLevel")) {
            $requestedLevel = $DiagnosticLevel
        }
        if (-not $requestedLevel) {
            Write-Output "ERROR: -Level is required for set-diagnostic. Allowed values: basic, debug, trace."
            exit 1
        }

        $normalizedLevel = "$requestedLevel".Trim().ToLowerInvariant()
        if (-not (@("basic", "debug", "trace") -contains $normalizedLevel)) {
            Write-Output ("ERROR: invalid diagnostic level: {0}" -f $requestedLevel)
            Write-Output "Allowed values: basic, debug, trace."
            Write-Output "No config changes were written."
            exit 1
        }

        $result = Invoke-WorkflowCommand -FilePath $CaseConfigToolPath -Arguments @("-SetDiagnosticLevel", $normalizedLevel) -Capture -Quiet
        if ($result.exit_code -ne 0) {
            $result.output | ForEach-Object { Write-Output $_ }
            exit $result.exit_code
        }

        $config = Read-CaseConfigMap -Path $CaseConfigPath
        Write-WorkflowSummary -Title "Set Diagnostic Summary" -Fields ([ordered]@{
            "diagnostic_level" = Get-ConfigDisplayValue -Config $config -Key "diagnostic_level"
            "validation_profile" = Get-ConfigDisplayValue -Config $config -Key "validation_profile"
            "execution_mode" = Get-ConfigDisplayValue -Config $config -Key "execution_mode" -Default "disabled"
            "config_path" = $CaseConfigPath
            "config modified" = $true
            "ce runtime run" = $false
            "recommendation" = Get-DiagnosticRecommendation -LevelValue $normalizedLevel
        })
        if ($normalizedLevel -eq "trace") {
            Write-Warning "trace logs can be large; reset to basic after diagnosis"
        }
        exit 0
    }

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
        Assert-RestoreBatchId -Value $BatchId -CommandName "prepare-restore"
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

        $executionOutcome = Get-ExecutionOutcomeFromBlock -Block $executionBlock
        $transactionType = Get-TransactionTypeFromBlock -Block $executionBlock
        $restoreSourceBatchId = Get-RestoreSourceBatchIdFromBlock -Block $executionBlock

        Write-WorkflowSummary -Title "Post-Execution Summary" -Fields ([ordered]@{
            "batch_id" = $latestBatchId
            "transaction_type" = $transactionType
            "classification" = if ($record) { $record.classification } else { "not_available" }
            "final hit" = if ($record) { $record.final_hit } else { "not_available" }
            "execution_outcome" = $executionOutcome
            "execution_mode" = Get-LogField -Block $executionBlock -Key "execution_mode"
            "execution_addr" = Get-LogField -Block $executionBlock -Key "execution_addr"
            "execution_addr_source" = Get-LogField -Block $executionBlock -Key "execution_addr_source"
            "restore_source_batch_id" = $restoreSourceBatchId
            "restore_execution_addr" = Get-LogField -Block $executionBlock -Key "restore_execution_addr"
            "restore_current_value_match" = Get-LogField -Block $executionBlock -Key "restore_current_value_match"
            "restore_current_float" = Get-LogField -Block $executionBlock -Key "restore_current_float"
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
        if ($transactionType -eq "write_success") {
            Write-Output ""
            Write-Output "write completed"
            Write-Output "recommended next step:"
            Write-Output ("test_session_tool.ps1 prepare-restore -BatchId `"{0}`" -EnableWrite -ConfirmWrite" -f $latestBatchId)
            Write-Output "then run CE and post-execution"
        } elseif ($transactionType -eq "restore_success") {
            Write-Output ""
            Write-Output "restore completed"
            Write-Output ("restored source batch id = {0}" -f $(if (Test-LogPresent -Value $restoreSourceBatchId) { $restoreSourceBatchId } else { "-" }))
            Write-Output "recommended next step:"
            Write-Output "test_session_tool.ps1 safe-reset -TargetValueFloat 100.0"
        } elseif ($transactionType -eq "restore_blocked") {
            Write-Output ""
            Write-Output "restore blocked safely"
            Write-Output ("failure class = {0}" -f (Get-LogField -Block $executionBlock -Key "execution_failure_class"))
            Write-Output "no write attempted"
        }
        if ($writeAttempted -or $writeOk -or $readbackOk) {
            Write-Output ""
            Write-Output "- execution completed or attempted"
            Write-Output "- recommended next step: test_session_tool.ps1 disable-execution"
            Write-Output "- if restore completed, also reset target to normal expected value if needed"
        }
        exit 0
    }

    "execution-status" {
        if ($Latest -lt 1) {
            Write-Output "ERROR: -Latest must be greater than 0 for execution-status"
            exit 1
        }

        $classifyArgs = @("-Latest", "$Latest", "-LogRoot", $LogRoot, "-ConsoleSummary")
        $classify = Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments $classifyArgs -Capture -Quiet
        if ($classify.exit_code -ne 0) {
            $classify.output | ForEach-Object { Write-Output $_ }
            exit $classify.exit_code
        }

        $records = @(Get-ClassifierConsoleRecords -OutputLines $classify.output)
        if ($records.Count -eq 0) {
            Write-Output "ERROR: no classifier records found for execution-status"
            exit 1
        }

        $latestRecord = $records[0]
        $unpairedWrites = @(Get-UnpairedWriteRecords -Records $records)
        $resolvedWrites = @(Read-ResolvedWriteRecords -Path $ResolvedWritesPath)
        $resolvedBatchSet = New-ResolvedBatchSet -Records $resolvedWrites
        $activeUnpairedWrites = @()
        $manuallyResolvedWrites = @()
        foreach ($writeRecord in $unpairedWrites) {
            $writeBatchId = Get-RecordField -Record $writeRecord -Key "batch_id"
            if ($resolvedBatchSet.ContainsKey($writeBatchId)) {
                $manuallyResolvedWrites += $writeRecord
            } else {
                $activeUnpairedWrites += $writeRecord
            }
        }

        $latestActiveUnpairedWrite = if ($activeUnpairedWrites.Count -gt 0) { $activeUnpairedWrites[0] } else { $null }
        $latestActiveUnpairedBatchId = Get-RecordField -Record $latestActiveUnpairedWrite -Key "batch_id"
        $latestResolvedWrite = if ($manuallyResolvedWrites.Count -gt 0) { $manuallyResolvedWrites[0] } else { $null }
        $latestResolvedBatchId = Get-RecordField -Record $latestResolvedWrite -Key "batch_id"
        $recommendedRestore = if ($latestActiveUnpairedWrite) { New-RestoreCommand -Batch $latestActiveUnpairedBatchId } else { "-" }

        $currentConfig = Read-CaseConfigMap -Path $CaseConfigPath
        $writeCapable = Test-ExecutionConfigWriteCapable -Config $currentConfig
        $armPresent = Test-ExecutionArmPresent -Config $currentConfig
        $targetNormal = Test-NormalTargetConfig -Config $currentConfig

        $safetyConclusion = "SAFE: no active unpaired writes and config not write-capable"
        if ($activeUnpairedWrites.Count -gt 0 -and $writeCapable) {
            $safetyConclusion = "WARNING: both unpaired write and write-capable config"
        } elseif ($writeCapable -and $armPresent) {
            $safetyConclusion = "WARNING: restore is armed / confirm present"
        } elseif ($writeCapable) {
            $safetyConclusion = "WARNING: config is write-capable"
        } elseif ($activeUnpairedWrites.Count -gt 0) {
            $safetyConclusion = "ATTENTION: unpaired write exists"
        } elseif (-not $targetNormal) {
            $safetyConclusion = "ATTENTION: target is not normal expected value"
        }

        Write-WorkflowSummary -Title "Execution Transaction Status" -Fields ([ordered]@{
            "latest scanned batches" = $Latest
            "latest batch id" = Get-RecordField -Record $latestRecord -Key "batch_id"
            "latest transaction_type" = Get-RecordField -Record $latestRecord -Key "transaction_type"
            "active_unpaired_write_success count" = $activeUnpairedWrites.Count
            "manually_resolved_write count" = $manuallyResolvedWrites.Count
            "latest active unpaired write batch id" = $latestActiveUnpairedBatchId
            "latest manually resolved write batch id" = $latestResolvedBatchId
            "recommended restore command" = $recommendedRestore
            "current config execution_mode" = Get-ConfigField -Config $currentConfig -Key "execution_mode"
            "current config write_enabled" = Get-ConfigField -Config $currentConfig -Key "write_enabled"
            "current config confirm present" = [bool](Get-ConfigField -Config $currentConfig -Key "execution_confirm")
            "current config arm present" = $armPresent
            "current config target_value_float" = Get-ConfigField -Config $currentConfig -Key "target_value_float"
            "current config target_value_pattern" = Get-ConfigField -Config $currentConfig -Key "target_value_pattern"
            "current config target normal" = $targetNormal
            "safety conclusion" = $safetyConclusion
        })

        if ($activeUnpairedWrites.Count -gt 0) {
            Write-Output ""
            Write-Output "Recommended restore command:"
            Write-Output $recommendedRestore
        } else {
            Write-Output ""
            Write-Output ("No active unpaired successful writes found in latest {0} batches." -f $Latest)
        }
        if ($manuallyResolvedWrites.Count -gt 0) {
            Write-Output "manually resolved historical writes exist"
        }
        if ($IncludeResolved) {
            $latestResolvedRecord = if ($latestResolvedBatchId -ne "-") { Get-ResolvedWriteRecord -Records $resolvedWrites -Batch $latestResolvedBatchId } else { $null }
            Write-WorkflowSummary -Title "Resolved Writes Summary" -Fields ([ordered]@{
                "resolved list path" = $ResolvedWritesPath
                "resolved records total" = $resolvedWrites.Count
                "resolved writes in scan" = $manuallyResolvedWrites.Count
                "latest resolved batch id" = $latestResolvedBatchId
                "latest resolved_at_utc" = Get-RecordField -Record $latestResolvedRecord -Key "resolved_at_utc"
                "latest resolved reason" = Get-RecordField -Record $latestResolvedRecord -Key "reason"
            })
        }
        exit 0
    }

    "mark-write-resolved" {
        if (-not $BatchId) {
            Write-Output "ERROR: -BatchId is required for mark-write-resolved"
            exit 1
        }
        Assert-RestoreBatchId -Value $BatchId -CommandName "mark-write-resolved"
        if ([string]::IsNullOrWhiteSpace($Reason)) {
            Write-Output "ERROR: -Reason is required for mark-write-resolved"
            exit 1
        }

        $resolvedWrites = @(Read-ResolvedWriteRecords -Path $ResolvedWritesPath)
        $existing = Get-ResolvedWriteRecord -Records $resolvedWrites -Batch $BatchId
        $status = "appended"
        $resolvedAt = "-"
        if ($existing) {
            $status = "already resolved"
            $resolvedAt = Get-RecordField -Record $existing -Key "resolved_at_utc"
        } else {
            $record = Add-ResolvedWriteRecord -Path $ResolvedWritesPath -Batch $BatchId -ResolutionReason $Reason
            $resolvedAt = Get-RecordField -Record $record -Key "resolved_at_utc"
        }

        Write-WorkflowSummary -Title "Manual Write Resolution" -Fields ([ordered]@{
            "batch_id" = $BatchId
            "status" = $status
            "resolved_at_utc" = $resolvedAt
            "reason" = $Reason
            "source" = "manual"
            "tool" = "test_session_tool.ps1"
            "resolved list path" = $ResolvedWritesPath
            "config modified" = $false
            "ce runtime run" = $false
        })
        exit 0
    }

    "doctor" {
        if ($Latest -lt 1) {
            Write-Output "ERROR: -Latest must be greater than 0 for doctor"
            exit 1
        }

        $checks = @()
        $srcRoot = Join-Path $ProjectRootPath "src"
        $requiredSourceFiles = @(
            $CaseConfigToolPath,
            $ClassifierPath,
            (Join-Path $srcRoot "classifier_preset.ps1"),
            (Join-Path $srcRoot "execute_module-v5.2.0_batch.lua"),
            (Join-Path $srcRoot "mvp0_value_executor.lua"),
            (Join-Path $srcRoot "mvp0_foundlist_collector.lua"),
            (Join-Path $srcRoot "mvp0_candidate_report.lua")
        )

        if ([string]::Equals($ProjectRootPath, $ExpectedProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            $checks += New-DoctorCheck -Check "project path is v2 path" -Status "PASS" -Details $ProjectRootPath
        } else {
            $checks += New-DoctorCheck -Check "project path is v2 path" -Status "FAIL" -Details ("expected {0}; actual {1}" -f $ExpectedProjectRoot, $ProjectRootPath)
        }

        $missingSources = @($requiredSourceFiles | Where-Object { -not (Test-Path -LiteralPath $_) })
        if ($missingSources.Count -eq 0) {
            $checks += New-DoctorCheck -Check "required source files exist" -Status "PASS" -Details ("{0} files present" -f $requiredSourceFiles.Count)
        } else {
            $checks += New-DoctorCheck -Check "required source files exist" -Status "FAIL" -Details ($missingSources -join "; ")
        }

        $configExists = Test-Path -LiteralPath $CaseConfigPath
        $checks += New-DoctorCheck `
            -Check "run_case_config.local.lua exists" `
            -Status $(if ($configExists) { "PASS" } else { "FAIL" }) `
            -Details $CaseConfigPath

        $configIgnored = Test-GitIgnoredPath -Path "src/run_case_config.local.lua"
        $checks += New-DoctorCheck `
            -Check "local config is gitignored" `
            -Status $(if ($configIgnored) { "PASS" } else { "FAIL" }) `
            -Details "src/run_case_config.local.lua"

        $validateResult = Invoke-DoctorPowerShellFile -FilePath $CaseConfigToolPath -Arguments @("-Validate")
        $checks += New-DoctorCheck `
            -Check "config validation passes" `
            -Status $(if ($validateResult.exit_code -eq 0) { "PASS" } else { "FAIL" }) `
            -Details $(if ($validateResult.exit_code -eq 0) { "case_config_tool -Validate exit 0" } else { ($validateResult.output | Select-Object -First 1) })

        $currentConfig = Read-CaseConfigMap -Path $CaseConfigPath
        $writeCapable = Test-ExecutionConfigWriteCapable -Config $currentConfig
        $armPresent = Test-ExecutionArmPresent -Config $currentConfig
        $executionDetails = "execution_mode={0}; write_enabled={1}; confirm_present={2}; arm_present={3}" -f `
            (Get-ConfigField -Config $currentConfig -Key "execution_mode"),
            (Get-ConfigField -Config $currentConfig -Key "write_enabled"),
            [bool](Get-ConfigField -Config $currentConfig -Key "execution_confirm"),
            $armPresent
        $checks += New-DoctorCheck `
            -Check "execution config is safe" `
            -Status $(if ($writeCapable -or $armPresent) { "WARN" } else { "PASS" }) `
            -Details $executionDetails

        $diagnosticStatus = Get-DiagnosticDoctorStatus -LevelValue (Get-ConfigField -Config $currentConfig -Key "diagnostic_level")
        $checks += New-DoctorCheck `
            -Check "diagnostic level policy" `
            -Status $diagnosticStatus.status `
            -Details $diagnosticStatus.detail

        $targetConsistency = Get-TargetConsistencyCheck -Config $currentConfig
        $checks += New-DoctorCheck `
            -Check "target pattern matches float" `
            -Status $(if ($targetConsistency.matches) { "PASS" } else { "FAIL" }) `
            -Details ("actual={0}; expected_from_float={1}" -f $targetConsistency.actual_pattern, $targetConsistency.expected_pattern)

        $targetNormal = Test-NormalTargetConfig -Config $currentConfig
        $checks += New-DoctorCheck `
            -Check "current target is normal" `
            -Status $(if ($targetNormal) { "PASS" } else { "WARN" }) `
            -Details ("target_value_float={0}; target_value_pattern={1}" -f (Get-ConfigField -Config $currentConfig -Key "target_value_float"), (Get-ConfigField -Config $currentConfig -Key "target_value_pattern"))

        $classifyResult = Invoke-DoctorPowerShellFile -FilePath $ClassifierPath -Arguments @("-Latest", "$Latest", "-LogRoot", $LogRoot, "-ConsoleSummary")
        if ($classifyResult.exit_code -eq 0) {
            $records = @(Get-ClassifierConsoleRecords -OutputLines $classifyResult.output)
            $unpairedWrites = @(Get-UnpairedWriteRecords -Records $records)
            $resolvedWrites = @(Read-ResolvedWriteRecords -Path $ResolvedWritesPath)
            $resolvedBatchSet = New-ResolvedBatchSet -Records $resolvedWrites
            $activeUnpairedWrites = @()
            $manualUnpairedWrites = @()
            foreach ($writeRecord in $unpairedWrites) {
                $writeBatchId = Get-RecordField -Record $writeRecord -Key "batch_id"
                if ($resolvedBatchSet.ContainsKey($writeBatchId)) {
                    $manualUnpairedWrites += $writeRecord
                } else {
                    $activeUnpairedWrites += $writeRecord
                }
            }
            $checks += New-DoctorCheck `
                -Check "active unpaired writes" `
                -Status $(if ($activeUnpairedWrites.Count -eq 0) { "PASS" } else { "WARN" }) `
                -Details ("active={0}; manual_resolved={1}; raw={2}; latest={3}" -f $activeUnpairedWrites.Count, $manualUnpairedWrites.Count, $unpairedWrites.Count, $(if ($records.Count -gt 0) { Get-RecordField -Record $records[0] -Key "batch_id" } else { "-" }))
        } else {
            $checks += New-DoctorCheck -Check "active unpaired writes" -Status "FAIL" -Details "classifier console summary failed"
        }

        $checks += New-DoctorCheck -Check "compare-full baseline filter" -Status "PASS" -Details "compare command includes -OnlyBaselineEligible"
        $compareArgs = @("-Latest", "20", "-Profile", "full", "-OnlyBaselineEligible", "-LogRoot", $LogRoot, "-CompareTo", $BaselinePath)
        $compareResult = Invoke-DoctorPowerShellFile -FilePath $ClassifierPath -Arguments $compareArgs
        if ($compareResult.exit_code -ne 0) {
            $checks += New-DoctorCheck -Check "compare-full result" -Status "FAIL" -Details "classifier compare command failed"
        } else {
            $comparison = Get-ComparisonStatus -OutputLines $compareResult.output
            $comparisonStatus = "$($comparison.status)"
            if ($comparisonStatus -eq "PASS") {
                $checks += New-DoctorCheck -Check "compare-full result" -Status "PASS" -Details "Regression Comparison = PASS"
            } elseif ($comparisonStatus -eq "WARN") {
                $checks += New-DoctorCheck -Check "compare-full result" -Status "WARN" -Details "Regression Comparison = WARN"
            } elseif ($comparisonStatus -eq "FAIL") {
                $checks += New-DoctorCheck -Check "compare-full result" -Status "FAIL" -Details "Regression Comparison = FAIL"
            } else {
                $checks += New-DoctorCheck -Check "compare-full result" -Status "WARN" -Details ("Regression Comparison = {0}" -f $comparisonStatus)
            }
        }

        $logIgnored = Test-GitIgnoredPath -Path "log/doctor_probe.tmp"
        $checks += New-DoctorCheck `
            -Check "log directory is ignored" `
            -Status $(if ($logIgnored) { "PASS" } else { "FAIL" }) `
            -Details "log/"

        if (Test-Path -LiteralPath $ResolvedWritesPath) {
            $resolvedIgnored = Test-GitIgnoredPath -Path "log/execution_resolved_writes.local.jsonl"
            $checks += New-DoctorCheck `
                -Check "resolved writes file is ignored" `
                -Status $(if ($resolvedIgnored) { "PASS" } else { "FAIL" }) `
                -Details "log/execution_resolved_writes.local.jsonl"
        } else {
            $checks += New-DoctorCheck -Check "resolved writes file is ignored" -Status "PASS" -Details "file not present"
        }

        $stagedSafetyFiles = @(Get-StagedLocalSafetyFiles)
        if ($stagedSafetyFiles.Count -eq 0) {
            $checks += New-DoctorCheck -Check "no config/log files staged" -Status "PASS" -Details "none"
        } else {
            $checks += New-DoctorCheck -Check "no config/log files staged" -Status "FAIL" -Details ($stagedSafetyFiles -join "; ")
        }

        $conclusion = Get-DoctorConclusion -Checks $checks
        Write-DoctorReport -Checks $checks -Conclusion $conclusion
        Write-Output "Before running CE, preview with: test_session_tool.ps1 plan"
        Write-Output "For command list, run: test_session_tool.ps1 help"
        if ($conclusion -eq "FAIL") {
            exit 1
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

    "baseline-list" {
        Write-BaselineList -Directory $BaselineRoot -CurrentPath $BaselinePath
        exit 0
    }

    "baseline-current" {
        $fields = Get-BaselineFileSummary -Path $BaselinePath
        $fields["batch selection"] = "baseline-eligible full batches only"
        $fields["latest count"] = 20
        Write-WorkflowSummary -Title "Current Baseline" -Fields $fields
        exit 0
    }

    "baseline-save" {
        $baselineLatest = if ($PSBoundParameters.ContainsKey("Latest")) { $Latest } else { 20 }
        if ($baselineLatest -lt 1) {
            Write-Output "ERROR: -Latest must be greater than 0 for baseline-save"
            exit 1
        }
        $safeName = Get-SafeBaselineFileName -Value $Name
        if (-not $safeName.ok) {
            Write-Output ("ERROR: invalid baseline name: {0}" -f $safeName.error)
            Write-Output "Use a simple filename such as full_clean_20260614 or full_clean_20260614.md."
            exit 1
        }

        if (-not (Test-Path -LiteralPath $BaselineRoot)) {
            New-Item -ItemType Directory -Path $BaselineRoot -Force | Out-Null
        }

        $outPath = Join-Path $BaselineRoot $safeName.value
        $existedBefore = Test-Path -LiteralPath $outPath
        $args = @("-Latest", "$baselineLatest", "-Profile", "full", "-OnlyBaselineEligible", "-LogRoot", $LogRoot, "-OutFile", $outPath)
        $result = Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments $args -Capture -Quiet
        if ($result.exit_code -ne 0) {
            $result.output | ForEach-Object { Write-Output $_ }
            exit $result.exit_code
        }

        $ignored = Test-GitIgnoredPath -Path ("log/baselines/{0}" -f $safeName.value)
        Write-WorkflowSummary -Title "Baseline Save Summary" -Fields ([ordered]@{
            "baseline path" = $outPath
            "baseline exists" = (Test-Path -LiteralPath $outPath)
            "overwrote existing file" = $existedBefore
            "latest count" = $baselineLatest
            "batch selection" = "baseline-eligible full batches only"
            "git ignored" = $ignored
            "commit guidance" = "do not commit log/baselines/*.md"
        })
        Write-Output "- baseline file is local generated state"
        Write-Output "- do not stage or commit this baseline file"
        exit 0
    }

    "baseline-compare" {
        $baselineLatest = if ($PSBoundParameters.ContainsKey("Latest")) { $Latest } else { 20 }
        if ($baselineLatest -lt 1) {
            Write-Output "ERROR: -Latest must be greater than 0 for baseline-compare"
            exit 1
        }
        $resolvedBaseline = Resolve-BaselinePath -Value $Baseline
        if (-not $resolvedBaseline.ok) {
            Write-Output ("ERROR: invalid baseline: {0}" -f $resolvedBaseline.error)
            exit 1
        }
        if (-not (Test-Path -LiteralPath $resolvedBaseline.path)) {
            Write-Output ("ERROR: baseline file not found: {0}" -f $resolvedBaseline.path)
            exit 1
        }

        $args = @("-Latest", "$baselineLatest", "-Profile", "full", "-OnlyBaselineEligible", "-LogRoot", $LogRoot, "-CompareTo", $resolvedBaseline.path)
        $result = Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments $args -Capture -Quiet
        if ($result.exit_code -ne 0) {
            $result.output | ForEach-Object { Write-Output $_ }
            exit $result.exit_code
        }

        $comparison = Get-ComparisonStatus -OutputLines $result.output
        Write-WorkflowSummary -Title "Baseline Compare Summary" -Fields ([ordered]@{
            "baseline path" = $resolvedBaseline.path
            "baseline exists" = $true
            "latest count" = $baselineLatest
            "batch selection" = "baseline-eligible full batches only"
            "regression status" = $comparison.status
            "code changes recommended" = $comparison.code_changes_recommended
        })
        if ($comparison.status -eq "PASS" -and $comparison.code_changes_recommended -eq "no") {
            Write-Output "- no code changes recommended"
        } elseif ($comparison.status -eq "FAIL" -or $comparison.status -eq "WARN") {
            Write-Output "- next step: inspect comparison details or use inspect-latest"
        }
        exit 0
    }

    "case-library" {
        $libraryLatest = if ($PSBoundParameters.ContainsKey("Latest")) { $Latest } else { 100 }
        if ($libraryLatest -lt 1) {
            Write-Output "ERROR: -Latest must be greater than 0 for case-library"
            exit 1
        }
        $libraryProfile = if ($PSBoundParameters.ContainsKey("Profile")) { $Profile } else { "all" }
        $library = Get-CaseLibrarySummary -RequestedLatest $libraryLatest -RequestedProfile $libraryProfile
        Write-WorkflowSummary -Title "Case Library Summary" -Fields $library.fields
        Write-AddressLifetimeNote -Mode "historical" -ActiveSessionConfirmed:$false
        Write-CaseLibraryTable -Rows $library.rows
        exit 0
    }

    "stable-cases" {
        Invoke-StableCasesCommand `
            -CommandName "stable-cases" `
            -LatestProvided ($PSBoundParameters.ContainsKey("Latest")) `
            -ProfileProvided ($PSBoundParameters.ContainsKey("Profile")) `
            -TargetUniqueProvided ($PSBoundParameters.ContainsKey("TargetUnique")) `
            -KnownTrueAddrProvided ($PSBoundParameters.ContainsKey("KnownTrueAddr"))
    }

    "baseline-candidates" {
        Invoke-StableCasesCommand `
            -CommandName "baseline-candidates" `
            -LatestProvided ($PSBoundParameters.ContainsKey("Latest")) `
            -ProfileProvided ($PSBoundParameters.ContainsKey("Profile")) `
            -TargetUniqueProvided ($PSBoundParameters.ContainsKey("TargetUnique")) `
            -KnownTrueAddrProvided ($PSBoundParameters.ContainsKey("KnownTrueAddr"))
    }

    "retest-queue" {
        Invoke-RetestQueueCommand `
            -CommandName "retest-queue" `
            -LatestProvided ($PSBoundParameters.ContainsKey("Latest")) `
            -ProfileProvided ($PSBoundParameters.ContainsKey("Profile")) `
            -TargetUniqueProvided ($PSBoundParameters.ContainsKey("TargetUnique")) `
            -LimitProvided ($PSBoundParameters.ContainsKey("Limit"))
    }

    "sample-plan" {
        Invoke-RetestQueueCommand `
            -CommandName "sample-plan" `
            -LatestProvided ($PSBoundParameters.ContainsKey("Latest")) `
            -ProfileProvided ($PSBoundParameters.ContainsKey("Profile")) `
            -TargetUniqueProvided ($PSBoundParameters.ContainsKey("TargetUnique")) `
            -LimitProvided ($PSBoundParameters.ContainsKey("Limit"))
    }

    "case-summary" {
        $summaryLatest = if ($PSBoundParameters.ContainsKey("Latest")) { $Latest } else { 20 }
        if ($summaryLatest -lt 1) {
            Write-Output "ERROR: -Latest must be greater than 0 for case-summary"
            exit 1
        }
        $summaryProfile = if ($PSBoundParameters.ContainsKey("Profile")) { $Profile } else { "full" }
        $summary = Get-CaseCoverageSummary -RequestedLatest $summaryLatest -RequestedProfile $summaryProfile -RequestedBaseline $Baseline -RequestedTargetUnique $TargetUnique
        Write-WorkflowSummary -Title "Case Coverage Summary" -Fields $summary.fields
        Write-RepeatedKnownTrueTable -Groups $summary.repeated_groups
        exit 0
    }

    "coverage-plan" {
        $summaryLatest = if ($PSBoundParameters.ContainsKey("Latest")) { $Latest } else { 20 }
        if ($summaryLatest -lt 1) {
            Write-Output "ERROR: -Latest must be greater than 0 for coverage-plan"
            exit 1
        }
        $summaryProfile = if ($PSBoundParameters.ContainsKey("Profile")) { $Profile } else { "full" }
        $summary = Get-CaseCoverageSummary -RequestedLatest $summaryLatest -RequestedProfile $summaryProfile -RequestedBaseline $Baseline -RequestedTargetUnique $TargetUnique
        Write-WorkflowSummary -Title "Case Coverage Summary" -Fields $summary.fields
        Write-RepeatedKnownTrueTable -Groups $summary.repeated_groups
        exit 0
    }

    "compare-full" {
        $baselineExists = Test-Path -LiteralPath $BaselinePath
        $args = @("-Latest", "20", "-Profile", "full", "-OnlyBaselineEligible", "-LogRoot", $LogRoot, "-CompareTo", $BaselinePath)
        $result = Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments $args -Capture -Quiet
        if ($result.exit_code -ne 0) {
            $result.output | ForEach-Object { Write-Output $_ }
            exit $result.exit_code
        }

        $comparison = Get-ComparisonStatus -OutputLines $result.output
        Write-WorkflowSummary -Title "Compare-Full Summary" -Fields ([ordered]@{
            "default baseline path" = $BaselinePath
            "baseline file exists" = $baselineExists
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
        Write-Output ""
        Write-Output "For transaction safety, run: test_session_tool.ps1 execution-status"
        Write-Output "For full preflight, run: test_session_tool.ps1 doctor"
        Write-Output "Before running CE, preview with: test_session_tool.ps1 plan"
        Write-Output "For command list, run: test_session_tool.ps1 help"
        exit 0
    }
}
