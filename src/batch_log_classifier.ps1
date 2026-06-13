param(
    [int]$Latest = 5,
    [string]$LogRoot = "D:\armedforces.io-v2\log\auto_output",
    [ValidateSet("all", "full", "quick")]
    [string]$Profile = "all",
    [switch]$OnlyBaselineEligible,
    [string]$InspectBatch,
    [switch]$ExplainFailures,
    [string]$CompareTo,
    [string]$OutFile,
    [switch]$AppendRegistry,
    [string]$RegistryPath = "D:\armedforces.io-v2\log\case_registry.jsonl",
    [switch]$RegistrySummary,
    [int]$RegistryRecent = 20,
    [string]$RegistryAddr,
    [switch]$RegistryOutliers,
    [string]$ExpectedRepoRoot = "D:\armedforces.io-v2",
    [switch]$ConsoleSummary,
    [switch]$Markdown
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$ClassificationOrder = @(
    "success",
    "quick_success",
    "quick_failure",
    "collector_runtime_empty",
    "incomplete_output",
    "invalid_config_mismatch",
    "known_true_value_mismatch",
    "suspected_filter_bug",
    "selected_quota_issue",
    "ranking_issue",
    "other"
)

$PerformanceMetricNames = @(
    "report_render_ms",
    "total_ms",
    "collector_call_ms",
    "prescore_ms",
    "stable_intersection_ms",
    "write_log_ms",
    "log_size_bytes"
)

$ExecutionFieldNames = @(
    "execution_enabled",
    "execution_mode",
    "write_enabled",
    "execution_confirm_ok",
    "execution_addr",
    "execution_addr_source",
    "execution_preconditions_ok",
    "execution_failure_class",
    "known_true_match_ok",
    "old_value_read_ok",
    "old_value_pattern",
    "old_value_float",
    "target_value_pattern",
    "target_value_float",
    "requested_write_value_float",
    "requested_write_value_pattern",
    "write_method",
    "write_attempted",
    "write_ok",
    "readback_ok",
    "readback_pattern",
    "readback_float",
    "readback_delta",
    "rollback_available",
    "rollback_value_pattern",
    "rollback_value_float",
    "executor_version"
)

function Get-BatchIdInfos {
    param([string]$Root)

    if (-not (Test-Path -LiteralPath $Root)) {
        throw "LogRoot does not exist: $Root"
    }

    Get-ChildItem -LiteralPath $Root -File |
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
        ForEach-Object { $_ }
}

function Get-BatchIds {
    param([string]$Root, [int]$Count)

    Get-BatchIdInfos -Root $Root |
        Select-Object -First $Count |
        ForEach-Object { $_.BatchId }
}

function Get-FirstPath {
    param([string]$Root, [string]$Filter)

    $file = Get-ChildItem -LiteralPath $Root -File -Filter $Filter | Select-Object -First 1
    if ($file) {
        return $file.FullName
    }
    return $null
}

function Read-KvMap {
    param([string]$Path)

    $map = [ordered]@{}
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) {
        return $map
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match "^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$") {
            if (-not $map.Contains($matches[1])) {
                $map[$matches[1]] = $matches[2]
            }
        }
    }
    return $map
}

function Read-KvBlocks {
    param([string]$Path)

    $blocks = @()
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) {
        return $blocks
    }

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
        if ($line -match "^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$") {
            $currentFields[$matches[1]] = $matches[2].Trim()
        }
    }

    if ($currentFields.Count -gt 0) {
        $blocks += [pscustomobject]@{ Name = $currentName; Fields = $currentFields }
    }
    return $blocks
}

function Select-ExecutionBlock {
    param([string[]]$Paths)

    $blocks = @()
    foreach ($path in @($Paths)) {
        $blocks += @(Read-KvBlocks -Path $path)
    }

    $stableBlocks = @($blocks | Where-Object {
        $_.Name -like "*stable_no_probe_intersection*" -and
        ($_.Fields.Contains("executor_version") -or $_.Fields.Contains("execution_mode"))
    })
    if ($stableBlocks.Count -gt 0) {
        return $stableBlocks[$stableBlocks.Count - 1]
    }

    $executionBlocks = @($blocks | Where-Object {
        $_.Fields.Contains("executor_version") -or $_.Fields.Contains("execution_mode")
    })
    if ($executionBlocks.Count -gt 0) {
        return $executionBlocks[$executionBlocks.Count - 1]
    }

    return $null
}

function Test-TextTrue {
    param($Value)

    if ($Value -is [bool]) {
        return [bool]$Value
    }
    if ($null -eq $Value) {
        return $false
    }
    return "$Value".Trim().ToLowerInvariant() -eq "true"
}

function Test-TextFalse {
    param($Value)

    if ($Value -is [bool]) {
        return -not [bool]$Value
    }
    if ($null -eq $Value) {
        return $false
    }
    return "$Value".Trim().ToLowerInvariant() -eq "false"
}

function Test-TextPresent {
    param($Value)

    if ($null -eq $Value) {
        return $false
    }
    $text = "$Value".Trim()
    return $text -ne "" -and $text -ne "nil" -and $text -ne "-"
}

function Normalize-ExecutionFieldValue {
    param($Value)

    if (-not (Test-TextPresent -Value $Value)) {
        return $null
    }
    return "$Value".Trim()
}

function Get-ExecutionFieldMap {
    param($Block)

    $fields = [ordered]@{}
    foreach ($name in $ExecutionFieldNames) {
        $value = $null
        if ($Block -and $Block.Fields -and $Block.Fields.Contains($name)) {
            $value = Normalize-ExecutionFieldValue -Value $Block.Fields[$name]
        }
        $fields[$name] = $value
    }

    if (-not (Test-TextPresent -Value $fields["execution_mode"])) {
        $fields["execution_mode"] = "disabled"
    }
    return $fields
}

function Get-ExecutionFieldValue {
    param($Fields, [string]$Name)

    if ($Fields -and $Fields.Contains($Name)) {
        return $Fields[$Name]
    }
    return $null
}

function Get-ExecutionOutcome {
    param($Fields)

    $mode = Get-ExecutionFieldValue -Fields $Fields -Name "execution_mode"
    if (-not (Test-TextPresent -Value $mode) -or $mode -eq "disabled") {
        return "execution_disabled"
    }

    $writeAttempted = Test-TextTrue (Get-ExecutionFieldValue -Fields $Fields -Name "write_attempted")
    $writeOk = Test-TextTrue (Get-ExecutionFieldValue -Fields $Fields -Name "write_ok")
    $readbackOk = Test-TextTrue (Get-ExecutionFieldValue -Fields $Fields -Name "readback_ok")
    $preconditionsOk = Test-TextTrue (Get-ExecutionFieldValue -Fields $Fields -Name "execution_preconditions_ok")
    $failureClass = Get-ExecutionFieldValue -Fields $Fields -Name "execution_failure_class"

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
    if (Test-TextPresent -Value $failureClass) {
        if (-not $writeAttempted) {
            return "execution_write_blocked"
        }
        return "execution_failed"
    }

    return "execution_unknown"
}

function Test-ExecutionBaselineEligible {
    param($Fields, [string]$Outcome)

    $mode = Get-ExecutionFieldValue -Fields $Fields -Name "execution_mode"
    if (-not (Test-TextPresent -Value $mode)) {
        $mode = "disabled"
    }
    $writeAttempted = Test-TextTrue (Get-ExecutionFieldValue -Fields $Fields -Name "write_attempted")

    return $mode -eq "disabled" -and -not $writeAttempted -and $Outcome -eq "execution_disabled"
}

function Get-ExecutionConclusion {
    param([string]$Outcome)

    switch ($Outcome) {
        "execution_disabled" { return "disabled / detect-only" }
        "execution_dry_run_ready" { return "dry-run ready" }
        "execution_write_blocked" { return "write blocked" }
        "execution_write_ok" { return "write succeeded" }
        "execution_readback_failed" { return "readback failed" }
        "execution_failed" { return "execution failed" }
        default { return "execution unknown" }
    }
}

function Get-KvValue {
    param($Map, [string]$Key)

    if ($Map -and $Map.Contains($Key)) {
        return $Map[$Key]
    }
    return $null
}

function Get-FirstMatchingLine {
    param([string]$Path, [string]$Pattern)

    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    $match = Select-String -LiteralPath $Path -Pattern $Pattern | Select-Object -First 1
    if ($match) {
        return $match.Line.Trim()
    }
    return $null
}

function Get-LineField {
    param([string]$Line, [string]$Name)

    if (-not $Line) {
        return $null
    }

    $pattern = "(?:^|\s)" + [regex]::Escape($Name) + "=([^\s]+)"
    if ($Line -match $pattern) {
        return $matches[1]
    }
    return $null
}

function Get-RawBytesField {
    param([string]$Line)

    if (-not $Line) {
        return $null
    }
    if ($Line -match "observed_raw_bytes=([^=]+?)\s+observed_float=") {
        return $matches[1].Trim()
    }
    return $null
}

function Get-Recommendation {
    param([string[]]$Paths)

    foreach ($path in $Paths) {
        $line = Get-FirstMatchingLine $path "^Recommendation:"
        if ($line -and $line -match "^Recommendation:\s*(.+)$") {
            return $matches[1]
        }
    }
    return $null
}

function Select-FirstValue {
    param([object[]]$Values)

    foreach ($value in $Values) {
        if ($null -ne $value -and "$value" -ne "") {
            return $value
        }
    }
    return $null
}

function Format-Cell {
    param($Value)

    if ($null -eq $Value -or "$Value" -eq "") {
        return "-"
    }

    return ("$Value" -replace "\|", "\|")
}

function Format-Triplet {
    param($A, $W, $B)

    return "$(Format-Cell $A)/$(Format-Cell $W)/$(Format-Cell $B)"
}

function Normalize-ReportValue {
    param($Value)

    if ($null -eq $Value -or "$Value" -eq "" -or "$Value" -eq "nil") {
        return "not_available"
    }
    return "$Value"
}

function Normalize-U32Pattern {
    param($Value)

    if (-not (Test-TextPresent -Value $Value)) {
        return $null
    }

    $text = "$Value".Trim()
    if ($text.StartsWith("0x", [System.StringComparison]::OrdinalIgnoreCase)) {
        $text = $text.Substring(2)
    }
    if ($text -notmatch "^[0-9A-Fa-f]{1,8}$") {
        return $null
    }
    return "0x" + $text.PadLeft(8, "0").ToUpperInvariant()
}

function Get-SingleFloatPattern {
    param($Value)

    if (-not (Test-TextPresent -Value $Value)) {
        return $null
    }

    $number = 0.0
    if (-not [double]::TryParse("$Value", [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$number)) {
        return $null
    }

    $singleValue = [single]$number
    $bytes = [System.BitConverter]::GetBytes($singleValue)
    $u32 = [System.BitConverter]::ToUInt32($bytes, 0)
    return ("0x{0:X8}" -f $u32)
}

function Get-TargetConfigConsistency {
    param($TargetPattern, $TargetFloat)

    $normalizedPattern = Normalize-U32Pattern -Value $TargetPattern
    $expectedPattern = Get-SingleFloatPattern -Value $TargetFloat
    $hasPattern = Test-TextPresent -Value $TargetPattern
    $hasFloat = Test-TextPresent -Value $TargetFloat
    $configMismatch = $false

    if ($hasPattern -and $hasFloat -and $expectedPattern) {
        if (-not $normalizedPattern -or -not [string]::Equals($normalizedPattern, $expectedPattern, [System.StringComparison]::OrdinalIgnoreCase)) {
            $configMismatch = $true
        }
    }

    return [pscustomobject][ordered]@{
        target_value_pattern_normalized = $normalizedPattern
        expected_target_pattern_from_float = $expectedPattern
        config_mismatch = $configMismatch
    }
}

function Limit-Text {
    param($Value, [int]$MaxLength = 180)

    if ($null -eq $Value -or "$Value" -eq "") {
        return "-"
    }

    $text = "$Value"
    if ($text.Length -le $MaxLength) {
        return $text
    }
    return $text.Substring(0, $MaxLength - 3) + "..."
}

function Get-NumericKvValues {
    param([string]$Path, [string]$Key)

    $values = @()
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) {
        return $values
    }

    $pattern = "^\s*" + [regex]::Escape($Key) + "\s*=\s*([^\s]+)\s*$"
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match $pattern) {
            $raw = $matches[1]
            if ($raw -match "^-?\d+(\.\d+)?$") {
                $values += [double]::Parse($raw, [System.Globalization.CultureInfo]::InvariantCulture)
            }
        }
    }
    return $values
}

function Get-PerformanceMap {
    param([string[]]$Paths)

    $map = [ordered]@{}
    foreach ($metric in $PerformanceMetricNames) {
        $map[$metric] = @()
    }

    foreach ($path in $Paths) {
        foreach ($metric in $PerformanceMetricNames) {
            $map[$metric] = @($map[$metric]) + @(Get-NumericKvValues -Path $path -Key $metric)
        }
    }
    return $map
}

function Get-MetricStats {
    param([double[]]$Values)

    $items = @($Values | Sort-Object)
    if ($items.Count -eq 0) {
        return $null
    }

    $sum = 0.0
    foreach ($item in $items) {
        $sum += $item
    }

    $middle = [int][Math]::Floor($items.Count / 2)
    if (($items.Count % 2) -eq 0) {
        $median = ($items[$middle - 1] + $items[$middle]) / 2
    } else {
        $median = $items[$middle]
    }

    return [pscustomobject][ordered]@{
        average = $sum / $items.Count
        median = $median
        min = $items[0]
        max = $items[$items.Count - 1]
        count = $items.Count
    }
}

function Format-Number {
    param($Value)

    if ($null -eq $Value) {
        return "-"
    }

    if ([Math]::Abs([double]$Value - [Math]::Round([double]$Value)) -lt 0.005) {
        return ([Math]::Round([double]$Value)).ToString([System.Globalization.CultureInfo]::InvariantCulture)
    }
    return ([Math]::Round([double]$Value, 2)).ToString([System.Globalization.CultureInfo]::InvariantCulture)
}

function Convert-ReportNumber {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = "$Value".Trim()
    if ($text -eq "" -or $text -eq "-" -or $text -eq "not_available") {
        return $null
    }

    $number = 0.0
    if ([double]::TryParse($text, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$number)) {
        return $number
    }
    return $null
}

function Format-CompareValue {
    param($Value)

    if ($null -eq $Value) {
        return "not_available"
    }
    return Format-Number $Value
}

function Format-CompareDelta {
    param($Baseline, $Current)

    if ($null -eq $Baseline -or $null -eq $Current) {
        return "not_available"
    }
    $delta = [double]$Current - [double]$Baseline
    if ($delta -gt 0) {
        return "+" + (Format-Number $delta)
    }
    return Format-Number $delta
}

function Get-ClassificationCount {
    param($Counts, [string]$Name)

    if ($Counts -and $Counts.Contains($Name) -and $null -ne $Counts[$Name]) {
        return [int]$Counts[$Name]
    }
    return $null
}

function Get-NonSuccessCount {
    param($Counts)

    if (-not $Counts) {
        return $null
    }

    $total = 0
    $hasValue = $false
    foreach ($key in $Counts.Keys) {
        if ($key -ne "success") {
            if ($null -ne $Counts[$key]) {
                $total += [int]$Counts[$key]
                $hasValue = $true
            }
        }
    }
    if (-not $hasValue) {
        return $null
    }
    return $total
}

function Get-PerformanceStatsMap {
    param([object[]]$Records)

    $statsByMetric = [ordered]@{}
    foreach ($metric in $PerformanceMetricNames) {
        $values = @()
        foreach ($record in $Records) {
            if ($record.performance_metrics.Contains($metric)) {
                $values += @($record.performance_metrics[$metric])
            }
        }
        $statsByMetric[$metric] = Get-MetricStats -Values $values
    }
    return $statsByMetric
}

function Read-BaselineReport {
    param([string]$Path)

    $classificationCounts = [ordered]@{}
    foreach ($classification in $ClassificationOrder) {
        $classificationCounts[$classification] = $null
    }

    $performance = [ordered]@{}
    foreach ($metric in $PerformanceMetricNames) {
        $performance[$metric] = $null
    }

    $result = [ordered]@{
        readable = $false
        path = $Path
        error = $null
        generated_at = "not_available"
        latest_n = $null
        validation_profile = "not_available"
        clean_baseline_status = "not_available"
        unique_known_true_addr_count = $null
        classification_counts = $classificationCounts
        performance = $performance
    }

    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) {
        $result.error = "baseline file not found"
        return [pscustomobject]$result
    }

    $result.readable = $true
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match "^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$") {
            $field = $matches[1].Trim()
            $value = $matches[2].Trim()
            switch ($field) {
                "generated_at" { $result.generated_at = $value }
                "latest N" { $result.latest_n = Convert-ReportNumber $value }
                "validation_profile" { $result.validation_profile = $value }
                default {
                    if ($ClassificationOrder -contains $field) {
                        $result.classification_counts[$field] = [int](Convert-ReportNumber $value)
                    }
                }
            }
        }

        if ($line -match "^\|\s*([A-Za-z0-9_]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*$") {
            $metric = $matches[1].Trim()
            if ($PerformanceMetricNames -contains $metric) {
                $result.performance[$metric] = [pscustomobject][ordered]@{
                    count = Convert-ReportNumber $matches[2]
                    average = Convert-ReportNumber $matches[3]
                    median = Convert-ReportNumber $matches[4]
                    min = Convert-ReportNumber $matches[5]
                    max = Convert-ReportNumber $matches[6]
                }
            }
        }

        if ($line -match "^- unique known_true_addr count:\s*(\d+)\s*$") {
            $result.unique_known_true_addr_count = [int]$matches[1]
        } elseif ($line -match "^- clean baseline status:\s*(\S+)\s*$") {
            $result.clean_baseline_status = $matches[1]
        }
    }

    return [pscustomobject]$result
}

function New-ComparisonMetric {
    param([string]$Name, $Baseline, $Current, [string]$Status)

    return [pscustomobject][ordered]@{
        name = $Name
        baseline = $Baseline
        current = $Current
        delta = Format-CompareDelta -Baseline $Baseline -Current $Current
        status = $Status
    }
}

function Get-PerformanceMetricValue {
    param($Performance, [string]$Metric, [string]$Field)

    if ($Performance -and $Performance.Contains($Metric) -and $null -ne $Performance[$Metric]) {
        return $Performance[$Metric].$Field
    }
    return $null
}

function Get-RegressionComparisonLines {
    param($Current, [string]$BaselinePath)

    $baseline = Read-BaselineReport -Path $BaselinePath
    $status = "PASS"
    $reasons = @()
    $codeChangesRecommended = "no"
    $replacementSampleRecommended = "no"
    $fullBaselineRerunRecommended = "no"

    if (-not $baseline.readable) {
        $status = "NOT_COMPARABLE"
        $reasons += $baseline.error
    } elseif ($baseline.clean_baseline_status -eq "not_available" -or $null -eq (Get-ClassificationCount $baseline.classification_counts "success")) {
        $status = "NOT_COMPARABLE"
        $reasons += "baseline fields insufficient"
    } elseif ($baseline.clean_baseline_status -ne "CLEAN" -or $baseline.validation_profile -match "quick") {
        $status = "NOT_COMPARABLE"
        $reasons += "baseline is not a clean full baseline"
    } elseif ($Current.clean_baseline_status -eq "NOT_BASELINE_ELIGIBLE") {
        $status = "NOT_COMPARABLE"
        $reasons += "current latest N is not baseline eligible"
        $fullBaselineRerunRecommended = "yes"
    } else {
        $baselineSuccess = Get-ClassificationCount $baseline.classification_counts "success"
        $currentSuccess = Get-ClassificationCount $Current.classification_counts "success"
        if ($null -ne $baselineSuccess -and $null -ne $currentSuccess -and $currentSuccess -lt $baselineSuccess) {
            $status = "FAIL"
            $reasons += "success count decreased"
            $replacementSampleRecommended = "yes"
        }

        foreach ($failureClass in @("collector_runtime_empty", "incomplete_output", "known_true_value_mismatch", "suspected_filter_bug", "selected_quota_issue", "ranking_issue")) {
            $currentCount = Get-ClassificationCount $Current.classification_counts $failureClass
            if ($currentCount -gt 0) {
                $status = "FAIL"
                $reasons += "$failureClass count is $currentCount"
                $replacementSampleRecommended = "yes"
                if (@("known_true_value_mismatch", "suspected_filter_bug", "selected_quota_issue", "ranking_issue") -contains $failureClass) {
                    $codeChangesRecommended = "yes"
                }
            }
        }

        if ($status -ne "FAIL") {
            if ($null -ne $baseline.unique_known_true_addr_count -and $Current.unique_known_true_addr_count -lt $baseline.unique_known_true_addr_count) {
                $status = "WARN"
                $reasons += "unique known_true_addr coverage decreased"
                $fullBaselineRerunRecommended = "yes"
            }

            $baselineTotalAvg = Get-PerformanceMetricValue -Performance $baseline.performance -Metric "total_ms" -Field "average"
            $currentTotalAvg = Get-PerformanceMetricValue -Performance $Current.performance -Metric "total_ms" -Field "average"
            if ($null -ne $baselineTotalAvg -and $null -ne $currentTotalAvg -and $currentTotalAvg -gt ($baselineTotalAvg * 1.25)) {
                $status = "WARN"
                $reasons += "avg total_ms slowed by more than 25%"
            }

            $baselineReportAvg = Get-PerformanceMetricValue -Performance $baseline.performance -Metric "report_render_ms" -Field "average"
            $currentReportAvg = Get-PerformanceMetricValue -Performance $Current.performance -Metric "report_render_ms" -Field "average"
            if ($null -ne $baselineReportAvg -and $null -ne $currentReportAvg -and $currentReportAvg -gt ($baselineReportAvg * 1.5)) {
                $status = "WARN"
                $reasons += "avg report_render_ms slowed by more than 50%"
            }

            $baselineLogAvg = Get-PerformanceMetricValue -Performance $baseline.performance -Metric "log_size_bytes" -Field "average"
            $currentLogAvg = Get-PerformanceMetricValue -Performance $Current.performance -Metric "log_size_bytes" -Field "average"
            if ($null -ne $baselineLogAvg -and $null -ne $currentLogAvg -and $currentLogAvg -gt ($baselineLogAvg * 1.5)) {
                $status = "WARN"
                $reasons += "avg log_size_bytes grew by more than 50%"
            }
        }
    }

    if ($status -eq "PASS" -and $reasons.Count -eq 0) {
        $reasons += "no regression detected"
    }

    $comparisonRows = @(
        (New-ComparisonMetric -Name "success count" -Baseline (Get-ClassificationCount $baseline.classification_counts "success") -Current (Get-ClassificationCount $Current.classification_counts "success") -Status $status),
        (New-ComparisonMetric -Name "non-success count" -Baseline (Get-NonSuccessCount $baseline.classification_counts) -Current (Get-NonSuccessCount $Current.classification_counts) -Status $status),
        (New-ComparisonMetric -Name "unique known_true_addr count" -Baseline $baseline.unique_known_true_addr_count -Current $Current.unique_known_true_addr_count -Status $status),
        (New-ComparisonMetric -Name "avg total_ms" -Baseline (Get-PerformanceMetricValue -Performance $baseline.performance -Metric "total_ms" -Field "average") -Current (Get-PerformanceMetricValue -Performance $Current.performance -Metric "total_ms" -Field "average") -Status $status),
        (New-ComparisonMetric -Name "median total_ms" -Baseline (Get-PerformanceMetricValue -Performance $baseline.performance -Metric "total_ms" -Field "median") -Current (Get-PerformanceMetricValue -Performance $Current.performance -Metric "total_ms" -Field "median") -Status $status),
        (New-ComparisonMetric -Name "avg report_render_ms" -Baseline (Get-PerformanceMetricValue -Performance $baseline.performance -Metric "report_render_ms" -Field "average") -Current (Get-PerformanceMetricValue -Performance $Current.performance -Metric "report_render_ms" -Field "average") -Status $status),
        (New-ComparisonMetric -Name "avg log_size_bytes" -Baseline (Get-PerformanceMetricValue -Performance $baseline.performance -Metric "log_size_bytes" -Field "average") -Current (Get-PerformanceMetricValue -Performance $Current.performance -Metric "log_size_bytes" -Field "average") -Status $status)
    )

    $lines = @()
    $lines += "## Regression Comparison"
    $lines += ""
    $lines += "| field | value |"
    $lines += "|---|---|"
    $lines += ("| baseline file path | {0} |" -f (Format-Cell $BaselinePath))
    $lines += ("| baseline generated_at | {0} |" -f (Format-Cell $baseline.generated_at))
    $lines += ("| current latest N | {0} |" -f (Format-Cell $Current.latest_n))
    $lines += ("| comparison status | {0} |" -f (Format-Cell $status))
    $lines += ("| comparison notes | {0} |" -f (Format-Cell ($reasons -join "; ")))
    $lines += ""
    $lines += "| metric | baseline | current | delta | status |"
    $lines += "|---|---:|---:|---:|---|"
    foreach ($row in $comparisonRows) {
        $lines += ("| {0} | {1} | {2} | {3} | {4} |" -f `
            (Format-Cell $row.name),
            (Format-Cell (Format-CompareValue $row.baseline)),
            (Format-Cell (Format-CompareValue $row.current)),
            (Format-Cell $row.delta),
            (Format-Cell $row.status))
    }
    $lines += ""
    $lines += "Comparison conclusion:"
    $lines += ("- status: {0}" -f $status)
    $lines += ("- code changes recommended: {0}" -f $codeChangesRecommended)
    $lines += ("- replacement sample recommended: {0}" -f $replacementSampleRecommended)
    $lines += ("- full baseline rerun recommended: {0}" -f $fullBaselineRerunRecommended)

    return $lines
}

function Get-RepoRoot {
    param([string]$Root)

    $candidates = @()
    if ($Root) {
        $logParent = Split-Path -Parent $Root
        if ($logParent) {
            $candidates += Split-Path -Parent $logParent
        }
    }
    if ($PSScriptRoot) {
        $candidates += Split-Path -Parent $PSScriptRoot
    }

    foreach ($candidate in $candidates | Where-Object { $_ } | Select-Object -Unique) {
        if (Test-Path -LiteralPath (Join-Path $candidate ".git")) {
            return [System.IO.Path]::GetFullPath($candidate)
        }
    }

    return $null
}

function ConvertTo-NormalizedPath {
    param([string]$Path)

    if (-not $Path) {
        return $null
    }

    try {
        return ([System.IO.Path]::GetFullPath($Path)).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    } catch {
        return $Path.TrimEnd("\", "/")
    }
}

function Test-PathUnderRoot {
    param([string]$Path, [string]$Root)

    $normalizedPath = ConvertTo-NormalizedPath -Path $Path
    $normalizedRoot = ConvertTo-NormalizedPath -Path $Root
    if (-not $normalizedPath -or -not $normalizedRoot) {
        return $false
    }

    if ([string]::Equals($normalizedPath, $normalizedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }

    $rootPrefix = $normalizedRoot + [System.IO.Path]::DirectorySeparatorChar
    return $normalizedPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-ScriptEnvironmentInfo {
    param([string]$ExpectedRoot, [string]$Root)

    $scriptPath = $PSCommandPath
    if (-not $scriptPath) {
        $scriptPath = $MyInvocation.ScriptName
    }
    $scriptPath = ConvertTo-NormalizedPath -Path $scriptPath

    $scriptRepoRoot = $null
    if ($scriptPath) {
        $scriptDir = Split-Path -Parent $scriptPath
        if ($scriptDir) {
            $scriptRepoRoot = ConvertTo-NormalizedPath -Path (Split-Path -Parent $scriptDir)
        }
    }

    $expectedRootNormalized = ConvertTo-NormalizedPath -Path $ExpectedRoot
    $expectedScriptPath = $null
    if ($expectedRootNormalized) {
        $expectedScriptPath = ConvertTo-NormalizedPath -Path (Join-Path (Join-Path $expectedRootNormalized "src") "batch_log_classifier.ps1")
    }

    $legacyRoot = ConvertTo-NormalizedPath -Path "D:\Lua Developer"
    $legacyPathDetected = (Test-PathUnderRoot -Path $scriptPath -Root $legacyRoot) -or (Test-PathUnderRoot -Path $scriptRepoRoot -Root $legacyRoot)
    $isExpectedRepo = $false
    if ($scriptPath -and $expectedScriptPath) {
        $isExpectedRepo = [string]::Equals($scriptPath, $expectedScriptPath, [System.StringComparison]::OrdinalIgnoreCase)
    }

    return [pscustomobject][ordered]@{
        script_path = $scriptPath
        script_repo_root = $scriptRepoRoot
        expected_repo_root = $expectedRootNormalized
        expected_script_path = $expectedScriptPath
        log_root = ConvertTo-NormalizedPath -Path $Root
        is_expected_repo = $isExpectedRepo
        legacy_path_detected = $legacyPathDetected
        legacy_root = $legacyRoot
    }
}

function Write-EnvironmentWarning {
    param($Environment)

    if ($Environment -and $Environment.legacy_path_detected) {
        Write-Warning ("classifier is running from legacy path {0}. Active project root is {1}." -f $Environment.legacy_root, $Environment.expected_repo_root)
    }
}

function Add-EnvironmentHeaderLines {
    param([object[]]$Lines, $Environment)

    $Lines += ("| script_path | {0} |" -f (Format-Cell $Environment.script_path))
    $Lines += ("| script_repo_root | {0} |" -f (Format-Cell $Environment.script_repo_root))
    $Lines += ("| expected_repo_root | {0} |" -f (Format-Cell $Environment.expected_repo_root))
    $Lines += ("| log_root | {0} |" -f (Format-Cell $Environment.log_root))
    $Lines += ("| is_expected_repo | {0} |" -f (Format-Cell $Environment.is_expected_repo))
    $Lines += ("| legacy_path_detected | {0} |" -f (Format-Cell $Environment.legacy_path_detected))
    return $Lines
}

function Invoke-GitText {
    param([string]$RepoPath, [string[]]$Arguments)

    if (-not $RepoPath) {
        return $null
    }

    try {
        $output = & git -C $RepoPath @Arguments 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $null
        }
        return @($output)
    } catch {
        return $null
    }
}

function Get-GitStatusSummary {
    param([string]$RepoPath)

    if (-not $RepoPath) {
        return "not_available"
    }

    $lines = @(Invoke-GitText -RepoPath $RepoPath -Arguments @("status", "--short"))
    if ($lines.Count -eq 0) {
        return "clean"
    }

    $modified = 0
    $added = 0
    $deleted = 0
    $renamed = 0
    $untracked = 0
    $other = 0

    foreach ($line in $lines) {
        if (-not $line) { continue }
        if ($line.StartsWith("??")) {
            $untracked += 1
        } elseif ($line.Substring(0, [Math]::Min(2, $line.Length)) -match "M") {
            $modified += 1
        } elseif ($line.Substring(0, [Math]::Min(2, $line.Length)) -match "A") {
            $added += 1
        } elseif ($line.Substring(0, [Math]::Min(2, $line.Length)) -match "D") {
            $deleted += 1
        } elseif ($line.Substring(0, [Math]::Min(2, $line.Length)) -match "R") {
            $renamed += 1
        } else {
            $other += 1
        }
    }

    $parts = @()
    if ($modified -gt 0) { $parts += "modified=$modified" }
    if ($added -gt 0) { $parts += "added=$added" }
    if ($deleted -gt 0) { $parts += "deleted=$deleted" }
    if ($renamed -gt 0) { $parts += "renamed=$renamed" }
    if ($untracked -gt 0) { $parts += "untracked=$untracked" }
    if ($other -gt 0) { $parts += "other=$other" }

    return ($parts -join ", ")
}

function Parse-ModeLog {
    param([string]$Path)

    $kv = Read-KvMap $Path
    $filterLine = Get-FirstMatchingLine $Path "\[filter_known_true\]"

    return [pscustomobject][ordered]@{
        present = [bool]$Path
        diagnostic_level = Get-KvValue $kv "diagnostic_level"
        validation_profile = Get-KvValue $kv "validation_profile"
        raw_count = Get-KvValue $kv "raw_count"
        unique_count = Get-KvValue $kv "unique_count"
        filtered_count = Get-KvValue $kv "filtered_count"
        prescored_count = Get-KvValue $kv "prescored_count"
        selected_count = Get-KvValue $kv "selected_count"
        best_candidate = Get-KvValue $kv "best_candidate"
        best_score = Get-KvValue $kv "best_score"
        second_score = Get-KvValue $kv "second_score"
        score_gap = Get-KvValue $kv "score_gap"
        true_in_raw = Get-KvValue $kv "true_in_raw"
        true_in_unique = Get-KvValue $kv "true_in_unique"
        true_in_filtered = Get-KvValue $kv "true_in_filtered"
        true_in_prescored = Get-KvValue $kv "true_in_prescored"
        true_in_selected = Get-KvValue $kv "true_in_selected"
        known_true_rank_position = Get-KvValue $kv "known_true_rank_position"
        known_true_final_score = Get-KvValue $kv "known_true_final_score"
        known_true_prescore_rank = Get-KvValue $kv "known_true_prescore_rank"
        known_true_prescore_score = Get-KvValue $kv "known_true_prescore_score"
        selected_cap = Get-KvValue $kv "selected_cap"
        selected_drop_reason = Get-KvValue $kv "selected_drop_reason"
        cutoff_score = Get-KvValue $kv "cutoff_score"
        candidate_at_cutoff = Get-KvValue $kv "candidate_at_cutoff"
        known_true_addr = Get-KvValue $kv "known_true_addr"
        filter_known_true_present = [bool]$filterLine
        target_value_pattern = Get-LineField $filterLine "target_pattern"
        target_value_float = Get-LineField $filterLine "target_float"
        observed_pattern = Get-LineField $filterLine "observed_pattern"
        observed_raw_bytes = Get-RawBytesField $filterLine
        observed_float = Get-LineField $filterLine "observed_float"
        delta = Get-LineField $filterLine "float_delta"
        exact_pattern_match = Get-LineField $filterLine "exact_pattern_match"
        tolerance_pass = Get-LineField $filterLine "tolerance_pass"
        mismatch_reason = Get-LineField $filterLine "mismatch_reason"
        final_filter_outcome = Get-LineField $filterLine "final_filter_outcome"
    }
}

function Test-BaselineEligibleRecord {
    param($Record)

    if (-not $Record) {
        return $false
    }
    if ($Record.classification -eq "invalid_config_mismatch" -or $Record.config_mismatch -eq "true") {
        return $false
    }
    if ($Record.execution_baseline_eligible -eq "false") {
        return $false
    }
    if ($Record.baseline_eligible -eq "true") {
        return $true
    }
    if ($Record.baseline_eligible -eq "false") {
        return $false
    }
    return $Record.validation_profile -eq "full"
}

function Test-RecordProfileFilter {
    param($Record, [string]$Profile, [bool]$OnlyBaselineEligible)

    if (-not $Record) {
        return $false
    }
    if ($Profile -ne "all" -and $Record.validation_profile -ne $Profile) {
        return $false
    }
    if ($OnlyBaselineEligible -and -not (Test-BaselineEligibleRecord -Record $Record)) {
        return $false
    }
    return $true
}

function Get-DropStageDiagnosis {
    param($Record)

    if (-not $Record) {
        return [pscustomobject][ordered]@{
            drop_stage = "unknown"
            likely_cause = "missing record"
            algorithm_failure = "unknown"
            replacement_sample_recommended = "no"
            trace_rerun_recommended = "no"
            code_change_recommended = "no"
        }
    }

    switch ($Record.classification) {
        "incomplete_output" {
            return [pscustomobject][ordered]@{
                drop_stage = "incomplete_output"
                likely_cause = "missing expected output files"
                algorithm_failure = "no"
                replacement_sample_recommended = "yes"
                trace_rerun_recommended = "no"
                code_change_recommended = "no"
            }
        }
        "collector_runtime_empty" {
            return [pscustomobject][ordered]@{
                drop_stage = "collector_runtime_empty"
                likely_cause = "collector produced empty runtime sample"
                algorithm_failure = "no"
                replacement_sample_recommended = "yes"
                trace_rerun_recommended = "no"
                code_change_recommended = "no"
            }
        }
        "quick_success" {
            return [pscustomobject][ordered]@{
                drop_stage = "quick_success"
                likely_cause = "smoke_test_only"
                algorithm_failure = "no"
                replacement_sample_recommended = "no"
                trace_rerun_recommended = "no"
                code_change_recommended = "no"
            }
        }
        "success" {
            return [pscustomobject][ordered]@{
                drop_stage = "success"
                likely_cause = "known_true reached final best candidate"
                algorithm_failure = "no"
                replacement_sample_recommended = "no"
                trace_rerun_recommended = "no"
                code_change_recommended = "no"
            }
        }
        "known_true_value_mismatch" {
            return [pscustomobject][ordered]@{
                drop_stage = "filter_target_match_failure"
                likely_cause = "truth_value_mismatch"
                algorithm_failure = "no"
                replacement_sample_recommended = "no"
                trace_rerun_recommended = "yes"
                code_change_recommended = "no"
            }
        }
        "invalid_config_mismatch" {
            return [pscustomobject][ordered]@{
                drop_stage = "invalid_config_mismatch"
                likely_cause = "target_value_pattern does not match target_value_float"
                algorithm_failure = "no"
                replacement_sample_recommended = "yes"
                trace_rerun_recommended = "no"
                code_change_recommended = "no"
            }
        }
        "suspected_filter_bug" {
            return [pscustomobject][ordered]@{
                drop_stage = "filter_target_match_failure"
                likely_cause = "suspected_filter_bug"
                algorithm_failure = "yes"
                replacement_sample_recommended = "no"
                trace_rerun_recommended = "yes"
                code_change_recommended = "yes"
            }
        }
        "selected_quota_issue" {
            return [pscustomobject][ordered]@{
                drop_stage = "selected_quota_issue"
                likely_cause = "known_true reached filtered but did not enter selected"
                algorithm_failure = "unknown"
                replacement_sample_recommended = "no"
                trace_rerun_recommended = "yes"
                code_change_recommended = "no"
            }
        }
        "ranking_issue" {
            return [pscustomobject][ordered]@{
                drop_stage = "ranking_issue"
                likely_cause = "known_true selected but final best_candidate differs"
                algorithm_failure = "yes"
                replacement_sample_recommended = "no"
                trace_rerun_recommended = "yes"
                code_change_recommended = "yes"
            }
        }
    }

    return [pscustomobject][ordered]@{
        drop_stage = "unknown"
        likely_cause = "classification did not map to a known inspector path"
        algorithm_failure = "unknown"
        replacement_sample_recommended = "no"
        trace_rerun_recommended = "yes"
        code_change_recommended = "no"
    }
}

function Get-FirstProblemMode {
    param($Record)

    if (-not $Record -or -not $Record.modes) {
        return $null
    }

    foreach ($modeName in @("no_probe_A", "with_probe", "no_probe_B")) {
        $mode = $Record.modes[$modeName]
        if (-not $mode -or -not $mode.present) {
            continue
        }
        if ($Record.classification -eq "known_true_value_mismatch" -or $Record.classification -eq "invalid_config_mismatch" -or $Record.classification -eq "suspected_filter_bug") {
            if ($mode.true_in_raw -eq "true" -and $mode.true_in_unique -eq "true" -and $mode.true_in_filtered -eq "false") {
                return $mode
            }
        } elseif ($Record.classification -eq "selected_quota_issue") {
            if ($mode.true_in_filtered -eq "true" -and $mode.true_in_selected -eq "false") {
                return $mode
            }
        } elseif ($Record.classification -eq "ranking_issue") {
            if ($mode.true_in_selected -eq "true") {
                return $mode
            }
        }
    }
    return $Record.modes["no_probe_A"]
}

function Add-InspectorModeRows {
    param([object[]]$Lines, $Record)

    $Lines += "| mode | raw | unique | filtered | prescored | selected | rank | best_candidate |"
    $Lines += "|---|---:|---:|---:|---:|---:|---:|---|"
    foreach ($modeName in @("no_probe_A", "with_probe", "no_probe_B")) {
        $mode = $Record.modes[$modeName]
        if ($mode -and $mode.present) {
            $Lines += ("| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} |" -f `
                (Format-Cell $modeName),
                (Format-Cell $mode.true_in_raw),
                (Format-Cell $mode.true_in_unique),
                (Format-Cell $mode.true_in_filtered),
                (Format-Cell $mode.true_in_prescored),
                (Format-Cell $mode.true_in_selected),
                (Format-Cell $mode.known_true_rank_position),
                (Format-Cell $mode.best_candidate))
        } else {
            $Lines += ("| {0} | - | - | - | - | - | - | - |" -f (Format-Cell $modeName))
        }
    }
    return $Lines
}

function Get-BatchRecord {
    param([string]$Root, [string]$BatchId)

    $summaryPath = Get-FirstPath $Root "$BatchId`__summary.txt"
    $diagnosticPath = Get-FirstPath $Root "$BatchId`__diagnostic_diff.txt"
    $stablePath = Get-FirstPath $Root "$BatchId*stable_no_probe_intersection.log"
    $noProbeAPath = Get-FirstPath $Root "$BatchId*no_probe_A.log"
    $withProbePath = Get-FirstPath $Root "$BatchId*with_probe.log"
    $noProbeBPath = Get-FirstPath $Root "$BatchId*no_probe_B.log"

    $summary = Read-KvMap $summaryPath
    $stable = Read-KvMap $stablePath
    $executionBlock = Select-ExecutionBlock -Paths @($summaryPath, $diagnosticPath, $stablePath)
    $executionFields = Get-ExecutionFieldMap -Block $executionBlock
    $executionOutcome = Get-ExecutionOutcome -Fields $executionFields
    $executionBaselineEligible = if (Test-ExecutionBaselineEligible -Fields $executionFields -Outcome $executionOutcome) { "true" } else { "false" }
    $noProbeA = Parse-ModeLog $noProbeAPath
    $withProbe = Parse-ModeLog $withProbePath
    $noProbeB = Parse-ModeLog $noProbeBPath

    $knownTrue = Select-FirstValue @(
        (Get-KvValue $stable "known_true_addr"),
        (Get-KvValue $summary "known_true_addr"),
        $noProbeA.known_true_addr,
        $withProbe.known_true_addr,
        $noProbeB.known_true_addr
    )
    $targetPattern = Select-FirstValue @(
        (Get-KvValue $stable "target_value_pattern"),
        (Get-KvValue $summary "target_value_pattern"),
        $noProbeA.target_value_pattern,
        $withProbe.target_value_pattern,
        $noProbeB.target_value_pattern
    )
    $targetFloat = Select-FirstValue @(
        (Get-KvValue $stable "target_value_float"),
        (Get-KvValue $summary "target_value_float"),
        $noProbeA.target_value_float,
        $withProbe.target_value_float,
        $noProbeB.target_value_float
    )
    $targetConfigConsistency = Get-TargetConfigConsistency -TargetPattern $targetPattern -TargetFloat $targetFloat
    $runValid = Select-FirstValue @((Get-KvValue $stable "run_valid"), (Get-KvValue $summary "run_valid"))
    $failureClass = Select-FirstValue @((Get-KvValue $stable "failure_class"), (Get-KvValue $summary "failure_class"))
    $collectorEmpty = Select-FirstValue @((Get-KvValue $stable "collector_empty"), (Get-KvValue $summary "collector_empty"))
    $diagnosticLevel = Select-FirstValue @(
        (Get-KvValue $stable "diagnostic_level"),
        (Get-KvValue $summary "diagnostic_level"),
        $noProbeA.diagnostic_level,
        $withProbe.diagnostic_level,
        $noProbeB.diagnostic_level
    )
    $validationProfile = Select-FirstValue @(
        (Get-KvValue $stable "validation_profile"),
        (Get-KvValue $summary "validation_profile"),
        $noProbeA.validation_profile
    )
    if (-not $validationProfile -or $validationProfile -eq "nil") {
        $validationProfile = "full"
    }
    $isQuickProfile = $validationProfile -eq "quick"
    $stableRank = Get-KvValue $stable "stable_intersection_known_true_rank_position"
    $bestCandidate = Select-FirstValue @((Get-KvValue $stable "stable_intersection_best_candidate"), (Get-KvValue $summary "best_candidate"))
    $recommendation = Get-Recommendation @($stablePath, $summaryPath)
    $performancePaths = @()
    if ($summaryPath) {
        $performancePaths += $summaryPath
    } else {
        $performancePaths += @($stablePath, $noProbeAPath, $withProbePath, $noProbeBPath)
    }
    $performanceMetrics = Get-PerformanceMap -Paths $performancePaths

    $missing = @()
    if (-not $summaryPath) { $missing += "summary.txt" }
    if (-not $diagnosticPath) { $missing += "diagnostic_diff.txt" }
    if (-not $noProbeAPath) { $missing += "no_probe_A" }
    if (-not $isQuickProfile) {
        if (-not $stablePath) { $missing += "stable output" }
        if (-not $withProbePath) { $missing += "with_probe" }
        if (-not $noProbeBPath) { $missing += "no_probe_B" }
    }

    $modes = [ordered]@{
        no_probe_A = $noProbeA
        with_probe = $withProbe
        no_probe_B = $noProbeB
    }

    $details = @()
    foreach ($modeName in $modes.Keys) {
        $mode = $modes[$modeName]
        if ($mode.true_in_filtered -eq "false" -and $mode.true_in_prescored -eq "true") {
            $details += "$modeName has diagnostic contradiction: true_in_filtered=false but true_in_prescored=true"
        }
    }

    $classification = "other"
    if ($missing.Count -gt 0) {
        $classification = "incomplete_output"
        $details += "missing: " + ($missing -join ", ")
    } elseif ($targetConfigConsistency.config_mismatch) {
        $classification = "invalid_config_mismatch"
        $details += ("target_value_pattern does not match target_value_float: actual={0}, expected_from_float={1}, target_value_float={2}" -f `
            (Format-Cell $targetPattern),
            (Format-Cell $targetConfigConsistency.expected_target_pattern_from_float),
            (Format-Cell $targetFloat))
    } elseif ($runValid -eq "false" -or $collectorEmpty -eq "true" -or $failureClass -eq "collector_runtime_empty") {
        $classification = "collector_runtime_empty"
    } else {
        foreach ($modeName in $modes.Keys) {
            $mode = $modes[$modeName]
            if ($mode.true_in_raw -eq "true" -and $mode.true_in_unique -eq "true" -and $mode.true_in_filtered -eq "false") {
                if ($mode.exact_pattern_match -eq "false" -and ($mode.mismatch_reason -eq "pattern_mismatch" -or $mode.final_filter_outcome -eq "value_mismatch")) {
                    $classification = "known_true_value_mismatch"
                    $details += "$modeName known_true mismatch: observed_pattern=$($mode.observed_pattern), observed_raw_bytes=$($mode.observed_raw_bytes), observed_float=$($mode.observed_float), delta=$($mode.delta), exact_pattern_match=$($mode.exact_pattern_match), tolerance_pass=$($mode.tolerance_pass), mismatch_reason=$($mode.mismatch_reason), final_filter_outcome=$($mode.final_filter_outcome)"
                } else {
                    $classification = "suspected_filter_bug"
                    $details += "$modeName filtered out known_true without clear pattern mismatch: observed_pattern=$($mode.observed_pattern), exact_pattern_match=$($mode.exact_pattern_match), mismatch_reason=$($mode.mismatch_reason), final_filter_outcome=$($mode.final_filter_outcome)"
                }
            }
        }
        if ($classification -eq "other") {
            foreach ($modeName in $modes.Keys) {
                $mode = $modes[$modeName]
                if ($mode.true_in_filtered -eq "true" -and $mode.true_in_selected -eq "false") {
                    $classification = "selected_quota_issue"
                    $details += "$modeName known_true reached filtered but not selected"
                }
            }
        }
        if ($classification -eq "other" -and $bestCandidate -and $knownTrue -and $bestCandidate -ne $knownTrue) {
            foreach ($modeName in $modes.Keys) {
                if ($modes[$modeName].true_in_selected -eq "true") {
                    $classification = "ranking_issue"
                    $details += "known_true selected but final best_candidate=$bestCandidate"
                    break
                }
            }
        }
        if ($classification -eq "other" -and $isQuickProfile) {
            if ($noProbeA.known_true_rank_position -eq "1" -and $bestCandidate -and $knownTrue -and $bestCandidate -eq $knownTrue) {
                $classification = "quick_success"
            } else {
                $classification = "quick_failure"
                $details += "quick profile did not meet smoke success criteria"
            }
        }
        if ($classification -eq "other" -and $stableRank -eq "1" -and $bestCandidate -eq $knownTrue) {
            $classification = "success"
        }
    }

    $baselineEligible = Select-FirstValue @((Get-KvValue $stable "baseline_eligible"), (Get-KvValue $summary "baseline_eligible"))
    if ($targetConfigConsistency.config_mismatch) {
        $baselineEligible = "false"
    }
    if ($executionBaselineEligible -eq "false") {
        $baselineEligible = "false"
    }
    if ($targetConfigConsistency.config_mismatch) {
        $recommendation = "fix target pattern/float consistency and rerun"
    }

    return [pscustomobject][ordered]@{
        batch_id = $BatchId
        known_true_addr = $knownTrue
        target_value_pattern = $targetPattern
        target_value_float = $targetFloat
        expected_target_pattern_from_float = $targetConfigConsistency.expected_target_pattern_from_float
        config_mismatch = if ($targetConfigConsistency.config_mismatch) { "true" } else { "false" }
        diagnostic_level = $diagnosticLevel
        validation_profile = $validationProfile
        baseline_eligible = $baselineEligible
        execution_baseline_eligible = $executionBaselineEligible
        execution_outcome = $executionOutcome
        execution_enabled = Get-ExecutionFieldValue -Fields $executionFields -Name "execution_enabled"
        execution_mode = Get-ExecutionFieldValue -Fields $executionFields -Name "execution_mode"
        write_enabled = Get-ExecutionFieldValue -Fields $executionFields -Name "write_enabled"
        execution_confirm_ok = Get-ExecutionFieldValue -Fields $executionFields -Name "execution_confirm_ok"
        execution_addr = Get-ExecutionFieldValue -Fields $executionFields -Name "execution_addr"
        execution_addr_source = Get-ExecutionFieldValue -Fields $executionFields -Name "execution_addr_source"
        execution_preconditions_ok = Get-ExecutionFieldValue -Fields $executionFields -Name "execution_preconditions_ok"
        execution_failure_class = Get-ExecutionFieldValue -Fields $executionFields -Name "execution_failure_class"
        known_true_match_ok = Get-ExecutionFieldValue -Fields $executionFields -Name "known_true_match_ok"
        old_value_read_ok = Get-ExecutionFieldValue -Fields $executionFields -Name "old_value_read_ok"
        old_value_pattern = Get-ExecutionFieldValue -Fields $executionFields -Name "old_value_pattern"
        old_value_float = Get-ExecutionFieldValue -Fields $executionFields -Name "old_value_float"
        requested_write_value_float = Get-ExecutionFieldValue -Fields $executionFields -Name "requested_write_value_float"
        requested_write_value_pattern = Get-ExecutionFieldValue -Fields $executionFields -Name "requested_write_value_pattern"
        write_method = Get-ExecutionFieldValue -Fields $executionFields -Name "write_method"
        write_attempted = Get-ExecutionFieldValue -Fields $executionFields -Name "write_attempted"
        write_ok = Get-ExecutionFieldValue -Fields $executionFields -Name "write_ok"
        readback_ok = Get-ExecutionFieldValue -Fields $executionFields -Name "readback_ok"
        readback_pattern = Get-ExecutionFieldValue -Fields $executionFields -Name "readback_pattern"
        readback_float = Get-ExecutionFieldValue -Fields $executionFields -Name "readback_float"
        readback_delta = Get-ExecutionFieldValue -Fields $executionFields -Name "readback_delta"
        rollback_available = Get-ExecutionFieldValue -Fields $executionFields -Name "rollback_available"
        rollback_value_pattern = Get-ExecutionFieldValue -Fields $executionFields -Name "rollback_value_pattern"
        rollback_value_float = Get-ExecutionFieldValue -Fields $executionFields -Name "rollback_value_float"
        executor_version = Get-ExecutionFieldValue -Fields $executionFields -Name "executor_version"
        run_valid = $runValid
        failure_class = $failureClass
        collector_empty = $collectorEmpty
        true_in_raw = Format-Triplet $noProbeA.true_in_raw $withProbe.true_in_raw $noProbeB.true_in_raw
        true_in_unique = Format-Triplet $noProbeA.true_in_unique $withProbe.true_in_unique $noProbeB.true_in_unique
        true_in_filtered = Format-Triplet $noProbeA.true_in_filtered $withProbe.true_in_filtered $noProbeB.true_in_filtered
        true_in_prescored = Format-Triplet $noProbeA.true_in_prescored $withProbe.true_in_prescored $noProbeB.true_in_prescored
        true_in_selected = Format-Triplet $noProbeA.true_in_selected $withProbe.true_in_selected $noProbeB.true_in_selected
        known_true_rank_position = Format-Triplet $noProbeA.known_true_rank_position $withProbe.known_true_rank_position $noProbeB.known_true_rank_position
        stable_intersection_known_true_rank_position = $stableRank
        final_best_candidate = $bestCandidate
        final_hit_true_addr = ($bestCandidate -and $knownTrue -and $bestCandidate -eq $knownTrue)
        recommendation = $recommendation
        classification = $classification
        details = $details
        performance_metrics = $performanceMetrics
        missing_files = $missing
        log_paths = [ordered]@{
            summary = $summaryPath
            diagnostic_diff = $diagnosticPath
            no_probe_A = $noProbeAPath
            with_probe = $withProbePath
            no_probe_B = $noProbeBPath
            stable = $stablePath
        }
        modes = $modes
        summary_map = $summary
        stable_map = $stable
        execution_map = $executionFields
    }
}

function Get-InspectionLines {
    param($Record)

    $diagnosis = Get-DropStageDiagnosis -Record $Record
    $problemMode = Get-FirstProblemMode -Record $Record
    $lines = @()

    $lines += "# Batch Failure / Anomaly Inspection"
    $lines += ""
    $lines += "| field | value |"
    $lines += "|---|---|"
    $lines += ("| batch_id | {0} |" -f (Format-Cell $Record.batch_id))
    $lines += ("| known_true_addr | {0} |" -f (Format-Cell $Record.known_true_addr))
    $lines += ("| target_value_pattern | {0} |" -f (Format-Cell $Record.target_value_pattern))
    $lines += ("| target_value_float | {0} |" -f (Format-Cell $Record.target_value_float))
    $lines += ("| expected_target_pattern_from_float | {0} |" -f (Format-Cell $Record.expected_target_pattern_from_float))
    $lines += ("| config_mismatch | {0} |" -f (Format-Cell $Record.config_mismatch))
    $lines += ("| diagnostic_level | {0} |" -f (Format-Cell $Record.diagnostic_level))
    $lines += ("| validation_profile | {0} |" -f (Format-Cell $Record.validation_profile))
    $lines += ("| classification | {0} |" -f (Format-Cell $Record.classification))
    $lines += ("| run_valid | {0} |" -f (Format-Cell $Record.run_valid))
    $lines += ("| collector_empty | {0} |" -f (Format-Cell $Record.collector_empty))
    $lines += ("| baseline_eligible | {0} |" -f (Format-Cell $Record.baseline_eligible))
    $lines += ""

    $lines += "## Execution"
    $lines += ""
    $lines += "| field | value |"
    $lines += "|---|---|"
    $lines += ("| execution_outcome | {0} |" -f (Format-Cell $Record.execution_outcome))
    $lines += ("| execution_conclusion | {0} |" -f (Format-Cell (Get-ExecutionConclusion -Outcome $Record.execution_outcome)))
    $lines += ("| execution_baseline_eligible | {0} |" -f (Format-Cell $Record.execution_baseline_eligible))
    $lines += ("| execution_enabled | {0} |" -f (Format-Cell $Record.execution_enabled))
    $lines += ("| execution_mode | {0} |" -f (Format-Cell $Record.execution_mode))
    $lines += ("| write_enabled | {0} |" -f (Format-Cell $Record.write_enabled))
    $lines += ("| execution_confirm_ok | {0} |" -f (Format-Cell $Record.execution_confirm_ok))
    $lines += ("| execution_addr | {0} |" -f (Format-Cell $Record.execution_addr))
    $lines += ("| execution_addr_source | {0} |" -f (Format-Cell $Record.execution_addr_source))
    $lines += ("| execution_preconditions_ok | {0} |" -f (Format-Cell $Record.execution_preconditions_ok))
    $lines += ("| execution_failure_class | {0} |" -f (Format-Cell $Record.execution_failure_class))
    $lines += ("| old_value_float | {0} |" -f (Format-Cell $Record.old_value_float))
    $lines += ("| old_value_pattern | {0} |" -f (Format-Cell $Record.old_value_pattern))
    $lines += ("| requested_write_value_float | {0} |" -f (Format-Cell $Record.requested_write_value_float))
    $lines += ("| requested_write_value_pattern | {0} |" -f (Format-Cell $Record.requested_write_value_pattern))
    $lines += ("| write_attempted | {0} |" -f (Format-Cell $Record.write_attempted))
    $lines += ("| write_ok | {0} |" -f (Format-Cell $Record.write_ok))
    $lines += ("| readback_ok | {0} |" -f (Format-Cell $Record.readback_ok))
    $lines += ("| readback_float | {0} |" -f (Format-Cell $Record.readback_float))
    $lines += ("| readback_pattern | {0} |" -f (Format-Cell $Record.readback_pattern))
    $lines += ("| readback_delta | {0} |" -f (Format-Cell $Record.readback_delta))
    $lines += ("| rollback_available | {0} |" -f (Format-Cell $Record.rollback_available))
    $lines += ("| executor_version | {0} |" -f (Format-Cell $Record.executor_version))
    $lines += ""

    $lines += "## Pipeline Path"
    $lines += ""
    $lines = Add-InspectorModeRows -Lines $lines -Record $Record
    $lines += ""
    $lines += ("- stable rank: {0}" -f (Format-Cell $Record.stable_intersection_known_true_rank_position))
    $lines += ("- final best_candidate: {0}" -f (Format-Cell $Record.final_best_candidate))
    $lines += ("- final hit true_addr: {0}" -f (Format-Cell $Record.final_hit_true_addr))
    $lines += ""

    $lines += "## Drop-Stage Diagnosis"
    $lines += ""
    $lines += ("- drop_stage: {0}" -f $diagnosis.drop_stage)
    $lines += ("- likely_cause: {0}" -f $diagnosis.likely_cause)

    if ($Record.classification -eq "collector_runtime_empty") {
        $lines += ("- empty modes: {0}" -f (Format-Cell (Get-KvValue $Record.summary_map "empty_modes")))
        foreach ($modeName in @("no_probe_A", "with_probe", "no_probe_B")) {
            $mode = $Record.modes[$modeName]
            $lines += ("- {0}: raw_count={1}, unique_count={2}, filtered_count={3}, selected_count={4}" -f `
                $modeName,
                (Format-Cell ($mode.raw_count)),
                (Format-Cell ($mode.unique_count)),
                (Format-Cell ($mode.filtered_count)),
                (Format-Cell ($mode.selected_count)))
        }
        $lines += "- recommendation: rerun sample, do not count as algorithm failure"
    } elseif ($Record.classification -eq "invalid_config_mismatch") {
        $lines += ("- target_value_pattern: {0}" -f (Format-Cell $Record.target_value_pattern))
        $lines += ("- target_value_float: {0}" -f (Format-Cell $Record.target_value_float))
        $lines += ("- expected_target_pattern_from_float: {0}" -f (Format-Cell $Record.expected_target_pattern_from_float))
        $lines += ("- config_mismatch: {0}" -f (Format-Cell $Record.config_mismatch))
        if ($problemMode -and $problemMode.filter_known_true_present) {
            $lines += ("- observed_pattern: {0}" -f (Format-Cell $problemMode.observed_pattern))
            $lines += ("- observed_raw_bytes: {0}" -f (Format-Cell $problemMode.observed_raw_bytes))
            $lines += ("- observed_float: {0}" -f (Format-Cell $problemMode.observed_float))
            $lines += ("- exact_pattern_match: {0}" -f (Format-Cell $problemMode.exact_pattern_match))
            $lines += ("- mismatch_reason: {0}" -f (Format-Cell $problemMode.mismatch_reason))
            $lines += ("- final_filter_outcome: {0}" -f (Format-Cell $problemMode.final_filter_outcome))
        }
        $lines += "- recommendation: fix target pattern/float consistency and rerun"
    } elseif ($Record.classification -eq "known_true_value_mismatch" -or $Record.classification -eq "suspected_filter_bug") {
        if ($problemMode -and $problemMode.filter_known_true_present) {
            $lines += ("- target_value_pattern: {0}" -f (Format-Cell $problemMode.target_value_pattern))
            $lines += ("- target_value_float: {0}" -f (Format-Cell $problemMode.target_value_float))
            $lines += ("- observed_pattern: {0}" -f (Format-Cell $problemMode.observed_pattern))
            $lines += ("- observed_raw_bytes: {0}" -f (Format-Cell $problemMode.observed_raw_bytes))
            $lines += ("- observed_float: {0}" -f (Format-Cell $problemMode.observed_float))
            $lines += ("- delta: {0}" -f (Format-Cell $problemMode.delta))
            $lines += ("- exact_pattern_match: {0}" -f (Format-Cell $problemMode.exact_pattern_match))
            $lines += ("- tolerance_pass: {0}" -f (Format-Cell $problemMode.tolerance_pass))
            $lines += ("- mismatch_reason: {0}" -f (Format-Cell $problemMode.mismatch_reason))
            $lines += ("- final_filter_outcome: {0}" -f (Format-Cell $problemMode.final_filter_outcome))
        } else {
            $lines += "- filter_known_true detail: missing_diagnostic_detail"
        }
    } elseif ($Record.classification -eq "selected_quota_issue") {
        $lines += ("- known_true_prescore_rank: {0}" -f (Format-Cell $problemMode.known_true_prescore_rank))
        $lines += ("- known_true_prescore_score: {0}" -f (Format-Cell $problemMode.known_true_prescore_score))
        $lines += ("- selected_cap: {0}" -f (Format-Cell $problemMode.selected_cap))
        $lines += ("- selected_drop_reason: {0}" -f (Format-Cell $problemMode.selected_drop_reason))
        $lines += ("- cutoff_score: {0}" -f (Format-Cell $problemMode.cutoff_score))
        $lines += ("- candidate_at_cutoff: {0}" -f (Format-Cell $problemMode.candidate_at_cutoff))
        if (-not $problemMode.known_true_prescore_rank) {
            $lines += "- selected-stage outlier, insufficient rank diagnostics"
            $lines += "- recommendation: rerun with current anomaly diagnostics or monitor if intermittent"
        }
    } elseif ($Record.classification -eq "ranking_issue") {
        $lines += ("- known_true_rank_position: {0}" -f (Format-Cell $problemMode.known_true_rank_position))
        $lines += ("- known_true_final_score: {0}" -f (Format-Cell $problemMode.known_true_final_score))
        $lines += ("- best_candidate: {0}" -f (Format-Cell $problemMode.best_candidate))
        $lines += ("- best_score: {0}" -f (Format-Cell $problemMode.best_score))
        $lines += ("- second_score: {0}" -f (Format-Cell $problemMode.second_score))
        $lines += ("- score_gap: {0}" -f (Format-Cell $problemMode.score_gap))
    } elseif ($Record.classification -eq "incomplete_output") {
        $missing = @($Record.missing_files)
        $missingText = "none"
        if ($missing.Count -gt 0) {
            $missingText = $missing -join ", "
        }
        $lines += ("- missing files: {0}" -f $missingText)
        $lines += "- recommendation: not an algorithm failure; rerun or inspect output persistence"
    } elseif ($Record.classification -eq "quick_success") {
        $lines += "- smoke_test_only"
        $lines += ("- baseline_eligible: {0}" -f (Format-Cell $Record.baseline_eligible))
        $lines += ("- skipped_modes: {0}" -f (Format-Cell (Get-KvValue $Record.summary_map "skipped_modes")))
        $lines += "- recommendation: use full profile for formal baseline"
    }

    $lines += ""
    $lines += "Diagnosis conclusion:"
    $lines += ("- drop_stage: {0}" -f $diagnosis.drop_stage)
    $lines += ("- likely_cause: {0}" -f $diagnosis.likely_cause)
    $lines += ("- algorithm_failure: {0}" -f $diagnosis.algorithm_failure)
    $lines += ("- replacement_sample_recommended: {0}" -f $diagnosis.replacement_sample_recommended)
    $lines += ("- trace_rerun_recommended: {0}" -f $diagnosis.trace_rerun_recommended)
    $lines += ("- code_change_recommended: {0}" -f $diagnosis.code_change_recommended)

    return $lines
}

function Get-TripletPart {
    param($Value, [int]$Index)

    if ($null -eq $Value) {
        return $null
    }
    $parts = "$Value" -split "/"
    if ($Index -ge 0 -and $Index -lt $parts.Count) {
        $item = $parts[$Index]
        if ($item -and $item -ne "-") {
            return $item
        }
    }
    return $null
}

function Get-RegistryMetricTotal {
    param($Record, [string]$Metric)

    if (-not $Record -or -not $Record.performance_metrics -or -not $Record.performance_metrics.Contains($Metric)) {
        return $null
    }

    $sum = 0.0
    $hasValue = $false
    foreach ($value in @($Record.performance_metrics[$Metric])) {
        if ($null -ne $value) {
            $sum += [double]$value
            $hasValue = $true
        }
    }
    if (-not $hasValue) {
        return $null
    }
    return [Math]::Round($sum, 2)
}

function New-RegistryEntry {
    param($Record, [string]$Root)

    return [pscustomobject][ordered]@{
        recorded_at = (Get-Date -Format "o")
        batch_id = $Record.batch_id
        known_true_addr = $Record.known_true_addr
        target_value_pattern = $Record.target_value_pattern
        target_value_float = $Record.target_value_float
        expected_target_pattern_from_float = $Record.expected_target_pattern_from_float
        config_mismatch = $Record.config_mismatch
        diagnostic_level = $Record.diagnostic_level
        validation_profile = $Record.validation_profile
        baseline_eligible = $Record.baseline_eligible
        classification = $Record.classification
        run_valid = $Record.run_valid
        collector_empty = $Record.collector_empty
        final_hit = $Record.final_hit_true_addr
        rank_A = Get-TripletPart -Value $Record.known_true_rank_position -Index 0
        rank_W = Get-TripletPart -Value $Record.known_true_rank_position -Index 1
        rank_B = Get-TripletPart -Value $Record.known_true_rank_position -Index 2
        stable_rank = $Record.stable_intersection_known_true_rank_position
        best_candidate = $Record.final_best_candidate
        execution_mode = $Record.execution_mode
        execution_outcome = $Record.execution_outcome
        execution_addr = $Record.execution_addr
        execution_confirm_ok = $Record.execution_confirm_ok
        old_value_float = $Record.old_value_float
        requested_write_value_float = $Record.requested_write_value_float
        write_attempted = $Record.write_attempted
        write_ok = $Record.write_ok
        readback_ok = $Record.readback_ok
        readback_float = $Record.readback_float
        execution_failure_class = $Record.execution_failure_class
        rollback_available = $Record.rollback_available
        execution_baseline_eligible = $Record.execution_baseline_eligible
        total_ms = Get-RegistryMetricTotal -Record $Record -Metric "total_ms"
        report_render_ms = Get-RegistryMetricTotal -Record $Record -Metric "report_render_ms"
        log_size_bytes = Get-RegistryMetricTotal -Record $Record -Metric "log_size_bytes"
        log_root = $Root
        source = "classifier"
    }
}

function Append-RegistryRecords {
    param([object[]]$Records, [string]$Path, [string]$Root)

    $result = [ordered]@{
        appended = 0
        duplicates = 0
        path = $Path
        error = $null
    }

    try {
        $resolvedPath = [System.IO.Path]::GetFullPath($Path)
        $result.path = $resolvedPath
        $dir = [System.IO.Path]::GetDirectoryName($resolvedPath)
        if ($dir -and -not (Test-Path -LiteralPath $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }

        $seen = @{}
        if (Test-Path -LiteralPath $resolvedPath) {
            foreach ($line in Get-Content -LiteralPath $resolvedPath) {
                if (-not $line) { continue }
                try {
                    $item = $line | ConvertFrom-Json
                    if ($item.batch_id) {
                        $seen["$($item.batch_id)"] = $true
                    }
                } catch {
                    continue
                }
            }
        }

        $newLines = @()
        foreach ($record in @($Records)) {
            if ($seen.ContainsKey($record.batch_id)) {
                $result.duplicates += 1
                continue
            }
            $entry = New-RegistryEntry -Record $record -Root $Root
            $newLines += ($entry | ConvertTo-Json -Compress)
            $seen[$record.batch_id] = $true
            $result.appended += 1
        }

        if ($newLines.Count -gt 0) {
            Add-Content -LiteralPath $resolvedPath -Value $newLines -Encoding UTF8
        }
    } catch {
        $result.error = $_.Exception.Message
    }

    return [pscustomobject]$result
}

function Add-ConsoleField {
    param([object[]]$Lines, [string]$Name, $Value, [int]$Width = 22)

    $Lines += ("{0,-$Width} {1}" -f $Name, (Format-Cell $Value))
    return $Lines
}

function Get-ConsoleRecordConclusion {
    param($Record)

    if (-not $Record) {
        return "not_available"
    }
    if ($Record.classification -eq "success") {
        return "success"
    }
    if ($Record.classification -eq "quick_success") {
        return "quick_success"
    }
    if ($Record.recommendation) {
        return $Record.recommendation
    }
    return "inspect recommended"
}

function Test-ShowExecutionSummary {
    param($Record)

    if (-not $Record) {
        return $false
    }
    if ($Record.execution_outcome -and $Record.execution_outcome -ne "execution_disabled") {
        return $true
    }
    return Test-TextPresent -Value $Record.execution_failure_class
}

function Get-ConsoleSummaryLines {
    param([object[]]$Records)

    $lines = @()
    if (-not $Records -or $Records.Count -eq 0) {
        $lines += "Batch Summary"
        $lines += "-------------"
        $lines = Add-ConsoleField -Lines $lines -Name "records" -Value 0
        return $lines
    }

    foreach ($record in @($Records)) {
        if ($lines.Count -gt 0) {
            $lines += ""
        }
        $lines += "Batch Summary"
        $lines += "-------------"
        $lines = Add-ConsoleField -Lines $lines -Name "batch_id" -Value $record.batch_id
        $lines = Add-ConsoleField -Lines $lines -Name "classification" -Value $record.classification
        $lines = Add-ConsoleField -Lines $lines -Name "validation_profile" -Value $record.validation_profile
        $lines = Add-ConsoleField -Lines $lines -Name "baseline_eligible" -Value $record.baseline_eligible
        $lines = Add-ConsoleField -Lines $lines -Name "known_true_addr" -Value $record.known_true_addr
        $lines = Add-ConsoleField -Lines $lines -Name "final_hit" -Value $record.final_hit_true_addr
        $lines = Add-ConsoleField -Lines $lines -Name "rank_A/W/B" -Value $record.known_true_rank_position
        $lines = Add-ConsoleField -Lines $lines -Name "stable_rank" -Value $record.stable_intersection_known_true_rank_position
        $lines = Add-ConsoleField -Lines $lines -Name "best_candidate" -Value $record.final_best_candidate
        $lines = Add-ConsoleField -Lines $lines -Name "recommendation" -Value $record.recommendation
        $lines = Add-ConsoleField -Lines $lines -Name "conclusion" -Value (Get-ConsoleRecordConclusion -Record $record)
        $lines = Add-ConsoleField -Lines $lines -Name "total_ms" -Value (Format-Number (Get-RegistryMetricTotal -Record $record -Metric "total_ms"))
        $lines = Add-ConsoleField -Lines $lines -Name "log_size_bytes" -Value (Format-Number (Get-RegistryMetricTotal -Record $record -Metric "log_size_bytes"))

        if ($record.config_mismatch -eq "true") {
            $lines += ""
            $lines += "Config"
            $lines += "------"
            $lines = Add-ConsoleField -Lines $lines -Name "target_pattern" -Value $record.target_value_pattern
            $lines = Add-ConsoleField -Lines $lines -Name "target_float" -Value $record.target_value_float
            $lines = Add-ConsoleField -Lines $lines -Name "expected_pattern" -Value $record.expected_target_pattern_from_float
            $lines = Add-ConsoleField -Lines $lines -Name "config_mismatch" -Value $record.config_mismatch
        }

        if (Test-ShowExecutionSummary -Record $record) {
            $lines += ""
            $lines += "Execution"
            $lines += "---------"
            $lines = Add-ConsoleField -Lines $lines -Name "execution_mode" -Value $record.execution_mode
            $lines = Add-ConsoleField -Lines $lines -Name "execution_outcome" -Value $record.execution_outcome
            $lines = Add-ConsoleField -Lines $lines -Name "execution_addr" -Value $record.execution_addr
            $lines = Add-ConsoleField -Lines $lines -Name "write_attempted" -Value $record.write_attempted
            $lines = Add-ConsoleField -Lines $lines -Name "write_ok" -Value $record.write_ok
            $lines = Add-ConsoleField -Lines $lines -Name "readback_ok" -Value $record.readback_ok
            $lines = Add-ConsoleField -Lines $lines -Name "execution_failure" -Value $record.execution_failure_class
        }
    }

    return $lines
}

function Get-RegistryField {
    param($Record, [string]$Name)

    if ($null -eq $Record) {
        return $null
    }

    $property = $Record.PSObject.Properties[$Name]
    if ($property) {
        return $property.Value
    }
    return $null
}

function Get-RegistryText {
    param($Record, [string]$Name)

    $value = Get-RegistryField -Record $Record -Name $Name
    if ($null -eq $value -or "$value" -eq "") {
        return $null
    }
    return "$value"
}

function Get-RegistryNumber {
    param($Record, [string]$Name)

    $value = Get-RegistryField -Record $Record -Name $Name
    if ($null -eq $value -or "$value" -eq "") {
        return $null
    }

    $number = 0.0
    if ([double]::TryParse("$value", [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$number)) {
        return $number
    }
    return $null
}

function Test-RegistryTrue {
    param($Value)

    if ($Value -is [bool]) {
        return [bool]$Value
    }
    if ($null -eq $Value) {
        return $false
    }
    return "$Value".Trim().ToLowerInvariant() -eq "true"
}

function Test-RegistryFalse {
    param($Value)

    if ($Value -is [bool]) {
        return -not [bool]$Value
    }
    if ($null -eq $Value) {
        return $false
    }
    return "$Value".Trim().ToLowerInvariant() -eq "false"
}

function Test-RegistrySuccessClass {
    param($Record)

    $classification = Get-RegistryText -Record $Record -Name "classification"
    return $classification -eq "success" -or $classification -eq "quick_success"
}

function Get-RegistryDate {
    param($Record)

    $recordedAt = Get-RegistryText -Record $Record -Name "recorded_at"
    if (-not $recordedAt) {
        return $null
    }

    try {
        return [datetime]::Parse($recordedAt, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::RoundtripKind)
    } catch {
        return $null
    }
}

function Get-RegistryRecordsNewest {
    param([object[]]$Records)

    $indexed = @()
    for ($i = 0; $i -lt $Records.Count; $i++) {
        $date = Get-RegistryDate -Record $Records[$i]
        $sortDate = [datetime]::MinValue
        if ($date) {
            $sortDate = $date
        }
        $indexed += [pscustomobject][ordered]@{
            record = $Records[$i]
            index = $i
            sort_date = $sortDate
        }
    }

    return @($indexed |
        Sort-Object -Property @{ Expression = { $_.sort_date }; Descending = $true }, @{ Expression = { $_.index }; Descending = $true } |
        ForEach-Object { $_.record })
}

function Read-RegistryJsonl {
    param([string]$Path)

    $result = [ordered]@{
        path = $Path
        exists = $false
        records = @()
        warnings = @()
    }

    try {
        $resolvedPath = [System.IO.Path]::GetFullPath($Path)
        $result.path = $resolvedPath
    } catch {
        $result.warnings += "Could not resolve registry path '$Path': $($_.Exception.Message)"
        return [pscustomobject]$result
    }

    if (-not (Test-Path -LiteralPath $result.path)) {
        return [pscustomobject]$result
    }

    $result.exists = $true
    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $result.path) {
        $lineNumber += 1
        if (-not $line -or $line.Trim() -eq "") {
            continue
        }

        try {
            $record = $line | ConvertFrom-Json
            if ($null -eq $record) {
                $result.warnings += "Skipping registry line ${lineNumber}: empty JSON value"
                continue
            }
            $result.records += $record
        } catch {
            $result.warnings += "Skipping registry line ${lineNumber}: $($_.Exception.Message)"
        }
    }

    return [pscustomobject]$result
}

function Get-RegistryMetricStats {
    param([object[]]$Records, [string]$Metric)

    $values = @()
    foreach ($record in @($Records)) {
        $value = Get-RegistryNumber -Record $record -Name $Metric
        if ($null -ne $value) {
            $values += $value
        }
    }
    return Get-MetricStats -Values $values
}

function Get-RegistryClassificationCount {
    param([object[]]$Records, [string]$Classification)

    return @($Records | Where-Object { (Get-RegistryText -Record $_ -Name "classification") -eq $Classification }).Count
}

function Get-RegistryExecutionOutcomeCount {
    param([object[]]$Records, [string]$Outcome)

    return @($Records | Where-Object { (Get-RegistryText -Record $_ -Name "execution_outcome") -eq $Outcome }).Count
}

function Get-RegistryLikelyReason {
    param($Record)

    foreach ($field in @("likely_reason", "likely_cause", "reason")) {
        $value = Get-RegistryText -Record $Record -Name $field
        if ($value) {
            return $value
        }
    }

    $classification = Get-RegistryText -Record $Record -Name "classification"
    switch ($classification) {
        "incomplete_output" { return "missing expected output files" }
        "collector_runtime_empty" { return "collector produced empty runtime sample" }
        "invalid_config_mismatch" { return "target_value_pattern does not match target_value_float" }
        "known_true_value_mismatch" { return "truth_value_mismatch" }
        "suspected_filter_bug" { return "suspected_filter_bug" }
        "selected_quota_issue" { return "known_true reached filtered but did not enter selected" }
        "ranking_issue" { return "known_true selected but final best_candidate differs" }
        "quick_failure" { return "quick profile did not meet smoke success criteria" }
    }

    $executionMode = Get-RegistryText -Record $Record -Name "execution_mode"
    $executionFailure = Get-RegistryText -Record $Record -Name "execution_failure_class"
    if ($executionMode -eq "write" -and $executionFailure) {
        return "execution write guard/failure: $executionFailure"
    }
    if ((Test-RegistryTrue (Get-RegistryField -Record $Record -Name "write_attempted")) -and (Test-RegistryFalse (Get-RegistryField -Record $Record -Name "write_ok"))) {
        return "execution write attempted but write_ok=false"
    }
    if ((Test-RegistryTrue (Get-RegistryField -Record $Record -Name "write_attempted")) -and (Test-RegistryFalse (Get-RegistryField -Record $Record -Name "readback_ok"))) {
        return "execution write attempted but readback_ok=false"
    }
    if ($executionMode -eq "write" -and (Test-RegistryFalse (Get-RegistryField -Record $Record -Name "execution_confirm_ok"))) {
        return "execution write missing confirmation"
    }

    return $null
}

function Get-RegistryRecommendation {
    param($Record)

    $existing = Get-RegistryText -Record $Record -Name "recommendation"
    if ($existing) {
        return $existing
    }

    $classification = Get-RegistryText -Record $Record -Name "classification"
    switch ($classification) {
        "incomplete_output" { return "rerun or inspect output persistence" }
        "collector_runtime_empty" { return "rerun sample; do not count as algorithm failure" }
        "invalid_config_mismatch" { return "fix target pattern/float consistency and rerun" }
        "known_true_value_mismatch" { return "trace rerun recommended; verify sampled known_true value" }
        "suspected_filter_bug" { return "trace rerun and code review recommended" }
        "selected_quota_issue" { return "trace rerun recommended; inspect selected cap and cutoff diagnostics" }
        "ranking_issue" { return "code review recommended; inspect scoring and ranking diagnostics" }
        "quick_failure" { return "rerun full profile or inspect quick smoke criteria" }
    }

    $executionOutcome = Get-RegistryText -Record $Record -Name "execution_outcome"
    switch ($executionOutcome) {
        "execution_write_blocked" { return "inspect execution_failure_class and config guards" }
        "execution_readback_failed" { return "inspect readback fields before retrying or restoring" }
        "execution_failed" { return "inspect execution fields before retrying" }
    }

    $profile = Get-RegistryText -Record $Record -Name "validation_profile"
    $baselineEligible = Get-RegistryField -Record $Record -Name "baseline_eligible"
    $finalHit = Get-RegistryField -Record $Record -Name "final_hit"
    if ($profile -eq "full" -and (Test-RegistryFalse $baselineEligible)) {
        return "inspect baseline eligibility before using as baseline"
    }
    if (-not (Test-RegistryTrue $finalHit)) {
        return "inspect final best_candidate and rank fields"
    }

    return $null
}

function Test-RegistryOutlier {
    param($Record)

    $profile = Get-RegistryText -Record $Record -Name "validation_profile"
    $classificationOk = Test-RegistrySuccessClass -Record $Record
    $finalHit = Get-RegistryField -Record $Record -Name "final_hit"
    $runValid = Get-RegistryField -Record $Record -Name "run_valid"
    $collectorEmpty = Get-RegistryField -Record $Record -Name "collector_empty"
    $baselineEligible = Get-RegistryField -Record $Record -Name "baseline_eligible"
    $executionMode = Get-RegistryText -Record $Record -Name "execution_mode"
    $executionFailure = Get-RegistryText -Record $Record -Name "execution_failure_class"
    $writeAttempted = Get-RegistryField -Record $Record -Name "write_attempted"
    $writeOk = Get-RegistryField -Record $Record -Name "write_ok"
    $readbackOk = Get-RegistryField -Record $Record -Name "readback_ok"
    $executionConfirmOk = Get-RegistryField -Record $Record -Name "execution_confirm_ok"

    if (-not $classificationOk) {
        return $true
    }
    if (-not (Test-RegistryTrue $finalHit)) {
        return $true
    }
    if (Test-RegistryFalse $runValid) {
        return $true
    }
    if (Test-RegistryTrue $collectorEmpty) {
        return $true
    }
    if ($profile -eq "full" -and (Test-RegistryFalse $baselineEligible)) {
        return $true
    }
    if ((Test-RegistryTrue $writeAttempted) -and (Test-RegistryFalse $writeOk)) {
        return $true
    }
    if ((Test-RegistryTrue $writeAttempted) -and (Test-RegistryFalse $readbackOk)) {
        return $true
    }
    if ($executionMode -eq "write" -and $executionFailure) {
        return $true
    }
    if ($executionMode -eq "write" -and (Test-RegistryFalse $executionConfirmOk)) {
        return $true
    }
    return $false
}

function Get-RegistryOutlierReason {
    param($Record)

    $reasons = @()
    if (-not (Test-RegistrySuccessClass -Record $Record)) {
        $reason = Get-RegistryLikelyReason -Record $Record
        if ($reason) {
            $reasons += $reason
        } else {
            $reasons += "classification is not success or quick_success"
        }
    }
    if (-not (Test-RegistryTrue (Get-RegistryField -Record $Record -Name "final_hit"))) {
        $reasons += "final_hit is not true"
    }
    if (Test-RegistryFalse (Get-RegistryField -Record $Record -Name "run_valid")) {
        $reasons += "run_valid=false"
    }
    if (Test-RegistryTrue (Get-RegistryField -Record $Record -Name "collector_empty")) {
        $reasons += "collector_empty=true"
    }
    if ((Get-RegistryText -Record $Record -Name "validation_profile") -eq "full" -and (Test-RegistryFalse (Get-RegistryField -Record $Record -Name "baseline_eligible"))) {
        $reasons += "full profile marked baseline_eligible=false"
    }
    if ((Test-RegistryTrue (Get-RegistryField -Record $Record -Name "write_attempted")) -and (Test-RegistryFalse (Get-RegistryField -Record $Record -Name "write_ok"))) {
        $reasons += "write_attempted=true and write_ok=false"
    }
    if ((Test-RegistryTrue (Get-RegistryField -Record $Record -Name "write_attempted")) -and (Test-RegistryFalse (Get-RegistryField -Record $Record -Name "readback_ok"))) {
        $reasons += "write_attempted=true and readback_ok=false"
    }
    if ((Get-RegistryText -Record $Record -Name "execution_mode") -eq "write" -and (Get-RegistryText -Record $Record -Name "execution_failure_class")) {
        $reasons += ("execution_failure_class={0}" -f (Get-RegistryText -Record $Record -Name "execution_failure_class"))
    }
    if ((Get-RegistryText -Record $Record -Name "execution_mode") -eq "write" -and (Test-RegistryFalse (Get-RegistryField -Record $Record -Name "execution_confirm_ok"))) {
        $reasons += "execution_mode=write and execution_confirm_ok=false"
    }

    if ($reasons.Count -eq 0) {
        return $null
    }
    return $reasons -join "; "
}

function Add-RegistrySummaryLines {
    param([object[]]$Lines, [object[]]$Records)

    $newest = @(Get-RegistryRecordsNewest -Records $Records | Select-Object -First 1)
    $latestRecord = $null
    if ($newest.Count -gt 0) {
        $latestRecord = $newest[0]
    }

    $uniqueBatchIds = @($Records |
        ForEach-Object { Get-RegistryText -Record $_ -Name "batch_id" } |
        Where-Object { $_ } |
        Select-Object -Unique)
    $uniqueKnownTrue = @($Records |
        ForEach-Object { Get-RegistryText -Record $_ -Name "known_true_addr" } |
        Where-Object { $_ } |
        Select-Object -Unique)
    $fullSuccessCount = @($Records | Where-Object {
        (Get-RegistryText -Record $_ -Name "validation_profile") -eq "full" -and
        (Get-RegistryText -Record $_ -Name "classification") -eq "success"
    }).Count
    $quickSuccessCount = Get-RegistryClassificationCount -Records $Records -Classification "quick_success"
    $nonSuccessCount = @($Records | Where-Object { -not (Test-RegistrySuccessClass -Record $_) }).Count

    $Lines += "## Registry Summary"
    $Lines += ""
    $Lines += "| field | value |"
    $Lines += "|---|---|"
    $Lines += ("| total records | {0} |" -f $Records.Count)
    $Lines += ("| unique batch_id count | {0} |" -f $uniqueBatchIds.Count)
    $Lines += ("| unique known_true_addr count | {0} |" -f $uniqueKnownTrue.Count)
    $Lines += ("| full success count | {0} |" -f $fullSuccessCount)
    $Lines += ("| quick_success count | {0} |" -f $quickSuccessCount)
    $Lines += ("| non-success count | {0} |" -f $nonSuccessCount)
    $Lines += ("| collector_runtime_empty count | {0} |" -f (Get-RegistryClassificationCount -Records $Records -Classification "collector_runtime_empty"))
    $Lines += ("| incomplete_output count | {0} |" -f (Get-RegistryClassificationCount -Records $Records -Classification "incomplete_output"))
    $Lines += ("| invalid_config_mismatch count | {0} |" -f (Get-RegistryClassificationCount -Records $Records -Classification "invalid_config_mismatch"))
    $Lines += ("| known_true_value_mismatch count | {0} |" -f (Get-RegistryClassificationCount -Records $Records -Classification "known_true_value_mismatch"))
    $Lines += ("| selected_quota_issue count | {0} |" -f (Get-RegistryClassificationCount -Records $Records -Classification "selected_quota_issue"))
    $Lines += ("| ranking_issue count | {0} |" -f (Get-RegistryClassificationCount -Records $Records -Classification "ranking_issue"))
    $Lines += ("| execution_write_ok count | {0} |" -f (Get-RegistryExecutionOutcomeCount -Records $Records -Outcome "execution_write_ok"))
    $Lines += ("| execution_dry_run_ready count | {0} |" -f (Get-RegistryExecutionOutcomeCount -Records $Records -Outcome "execution_dry_run_ready"))
    $Lines += ("| execution_write_blocked count | {0} |" -f (Get-RegistryExecutionOutcomeCount -Records $Records -Outcome "execution_write_blocked"))
    $Lines += ("| execution_readback_failed count | {0} |" -f (Get-RegistryExecutionOutcomeCount -Records $Records -Outcome "execution_readback_failed"))
    $Lines += ("| execution_failed count | {0} |" -f (Get-RegistryExecutionOutcomeCount -Records $Records -Outcome "execution_failed"))
    $Lines += ("| latest recorded_at | {0} |" -f (Format-Cell (Get-RegistryText -Record $latestRecord -Name "recorded_at")))
    $Lines += ("| latest batch_id | {0} |" -f (Format-Cell (Get-RegistryText -Record $latestRecord -Name "batch_id")))
    $Lines += ""

    $Lines += "### Most Repeated known_true_addr"
    $Lines += ""
    $knownTrueGroups = @($Records |
        ForEach-Object { Get-RegistryText -Record $_ -Name "known_true_addr" } |
        Where-Object { $_ } |
        Group-Object |
        Sort-Object -Property @{ Expression = "Count"; Descending = $true }, Name |
        Select-Object -First 10)
    if ($knownTrueGroups.Count -eq 0) {
        $Lines += "No known_true_addr values recorded."
    } else {
        $Lines += "| known_true_addr | count |"
        $Lines += "|---|---:|"
        foreach ($group in $knownTrueGroups) {
            $Lines += ("| {0} | {1} |" -f (Format-Cell $group.Name), $group.Count)
        }
    }
    $Lines += ""

    $Lines += "### Performance"
    $Lines += ""
    $Lines += "| metric | average | median | count |"
    $Lines += "|---|---:|---:|---:|"
    foreach ($metric in @("total_ms", "report_render_ms", "log_size_bytes")) {
        $stats = Get-RegistryMetricStats -Records $Records -Metric $metric
        if ($null -eq $stats) {
            $Lines += ("| {0} | - | - | 0 |" -f (Format-Cell $metric))
        } else {
            $Lines += ("| {0} | {1} | {2} | {3} |" -f (Format-Cell $metric), (Format-Number $stats.average), (Format-Number $stats.median), $stats.count)
        }
    }
    $Lines += ""

    return $Lines
}

function Add-RegistryRecentLines {
    param([object[]]$Lines, [object[]]$Records, [int]$Count)

    if ($Count -lt 0) {
        $Count = 0
    }

    $recentRecords = @(Get-RegistryRecordsNewest -Records $Records | Select-Object -First $Count)
    $Lines += "## Recent Registry Records"
    $Lines += ""
    $Lines += ("- requested count: {0}" -f $Count)
    $Lines += ""
    $Lines += "| recorded_at | batch_id | known_true_addr | validation_profile | classification | baseline_eligible | final_hit | rank_A/W/B | stable_rank | total_ms | log_size_bytes |"
    $Lines += "|---|---|---|---|---|---|---|---|---|---:|---:|"
    foreach ($record in $recentRecords) {
        $Lines += ("| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} | {9} | {10} |" -f `
            (Format-Cell (Get-RegistryText -Record $record -Name "recorded_at")),
            (Format-Cell (Get-RegistryText -Record $record -Name "batch_id")),
            (Format-Cell (Get-RegistryText -Record $record -Name "known_true_addr")),
            (Format-Cell (Get-RegistryText -Record $record -Name "validation_profile")),
            (Format-Cell (Get-RegistryText -Record $record -Name "classification")),
            (Format-Cell (Get-RegistryField -Record $record -Name "baseline_eligible")),
            (Format-Cell (Get-RegistryField -Record $record -Name "final_hit")),
            (Format-Cell (Format-Triplet (Get-RegistryText -Record $record -Name "rank_A") (Get-RegistryText -Record $record -Name "rank_W") (Get-RegistryText -Record $record -Name "rank_B"))),
            (Format-Cell (Get-RegistryText -Record $record -Name "stable_rank")),
            (Format-Cell (Format-Number (Get-RegistryNumber -Record $record -Name "total_ms"))),
            (Format-Cell (Format-Number (Get-RegistryNumber -Record $record -Name "log_size_bytes"))))
    }
    $Lines += ""

    return $Lines
}

function Add-RegistryAddrLines {
    param([object[]]$Lines, [object[]]$Records, [string]$Address)

    $matchedRecords = @($Records | Where-Object {
        [string]::Equals((Get-RegistryText -Record $_ -Name "known_true_addr"), $Address, [System.StringComparison]::OrdinalIgnoreCase)
    })
    $newest = @(Get-RegistryRecordsNewest -Records $matchedRecords | Select-Object -First 1)
    $latestRecord = $null
    if ($newest.Count -gt 0) {
        $latestRecord = $newest[0]
    }

    $fullRuns = @($matchedRecords | Where-Object { (Get-RegistryText -Record $_ -Name "validation_profile") -eq "full" }).Count
    $quickRuns = @($matchedRecords | Where-Object { (Get-RegistryText -Record $_ -Name "validation_profile") -eq "quick" }).Count
    $successCount = @($matchedRecords | Where-Object { Test-RegistrySuccessClass -Record $_ }).Count
    $nonSuccessCount = @($matchedRecords | Where-Object { -not (Test-RegistrySuccessClass -Record $_) }).Count
    $batchIds = @($matchedRecords |
        ForEach-Object { Get-RegistryText -Record $_ -Name "batch_id" } |
        Where-Object { $_ } |
        Select-Object -Unique)
    $totalStats = Get-RegistryMetricStats -Records $matchedRecords -Metric "total_ms"
    $averageTotalMs = $null
    if ($null -ne $totalStats) {
        $averageTotalMs = $totalStats.average
    }

    $Lines += "## Registry Address History"
    $Lines += ""
    $Lines += ("- known_true_addr: {0}" -f (Format-Cell $Address))
    $Lines += ""

    if ($matchedRecords.Count -eq 0) {
        $Lines += "No records found for this address."
        $Lines += ""
        return $Lines
    }

    $Lines += "| field | value |"
    $Lines += "|---|---|"
    $Lines += ("| total runs | {0} |" -f $matchedRecords.Count)
    $Lines += ("| full runs | {0} |" -f $fullRuns)
    $Lines += ("| quick runs | {0} |" -f $quickRuns)
    $Lines += ("| success count | {0} |" -f $successCount)
    $Lines += ("| non-success count | {0} |" -f $nonSuccessCount)
    $Lines += ("| latest batch | {0} |" -f (Format-Cell (Get-RegistryText -Record $latestRecord -Name "batch_id")))
    $Lines += ("| all batch ids | {0} |" -f (Format-Cell ($batchIds -join ", ")))
    $Lines += ("| average total_ms | {0} |" -f (Format-Cell (Format-Number $averageTotalMs)))
    $Lines += ("| ever selected_quota_issue | {0} |" -f (Format-Cell (@($matchedRecords | Where-Object { (Get-RegistryText -Record $_ -Name "classification") -eq "selected_quota_issue" }).Count -gt 0)))
    $Lines += ("| ever known_true_value_mismatch | {0} |" -f (Format-Cell (@($matchedRecords | Where-Object { (Get-RegistryText -Record $_ -Name "classification") -eq "known_true_value_mismatch" }).Count -gt 0)))
    $Lines += ("| ever ranking_issue | {0} |" -f (Format-Cell (@($matchedRecords | Where-Object { (Get-RegistryText -Record $_ -Name "classification") -eq "ranking_issue" }).Count -gt 0)))
    $Lines += ""

    $Lines += "### Classifications"
    $Lines += ""
    $Lines += "| classification | count |"
    $Lines += "|---|---:|"
    $classificationGroups = @($matchedRecords |
        ForEach-Object {
            $classification = Get-RegistryText -Record $_ -Name "classification"
            if ($classification) { $classification } else { "not_available" }
        } |
        Group-Object |
        Sort-Object -Property @{ Expression = "Count"; Descending = $true }, Name)
    foreach ($group in $classificationGroups) {
        $Lines += ("| {0} | {1} |" -f (Format-Cell $group.Name), $group.Count)
    }
    $Lines += ""

    return $Lines
}

function Add-RegistryOutlierLines {
    param([object[]]$Lines, [object[]]$Records)

    $outliers = @(Get-RegistryRecordsNewest -Records $Records | Where-Object { Test-RegistryOutlier -Record $_ })

    $Lines += "## Registry Outliers"
    $Lines += ""
    if ($outliers.Count -eq 0) {
        $Lines += "No registry outliers detected."
        $Lines += ""
        return $Lines
    }

    $Lines += "| batch_id | known_true_addr | validation_profile | classification | likely reason | recommendation |"
    $Lines += "|---|---|---|---|---|---|"
    foreach ($record in $outliers) {
        $Lines += ("| {0} | {1} | {2} | {3} | {4} | {5} |" -f `
            (Format-Cell (Get-RegistryText -Record $record -Name "batch_id")),
            (Format-Cell (Get-RegistryText -Record $record -Name "known_true_addr")),
            (Format-Cell (Get-RegistryText -Record $record -Name "validation_profile")),
            (Format-Cell (Get-RegistryText -Record $record -Name "classification")),
            (Format-Cell (Get-RegistryOutlierReason -Record $record)),
            (Format-Cell (Get-RegistryRecommendation -Record $record)))
    }
    $Lines += ""

    return $Lines
}

function Build-RegistryQueryReport {
    param(
        [string]$Path,
        [bool]$IncludeSummary,
        [bool]$IncludeRecent,
        [int]$RecentCount,
        [string]$Address,
        [bool]$IncludeOutliers,
        $Environment
    )

    $registry = Read-RegistryJsonl -Path $Path
    foreach ($warning in @($registry.warnings)) {
        Write-Warning $warning
    }

    $records = @($registry.records)
    $lines = @()
    $lines += "# Case Registry Query Report"
    $lines += ""
    $lines += "| field | value |"
    $lines += "|---|---|"
    $lines += ("| generated_at | {0} |" -f (Format-Cell (Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")))
    $lines = Add-EnvironmentHeaderLines -Lines $lines -Environment $Environment
    $lines += ("| registry path | {0} |" -f (Format-Cell $registry.path))
    $lines += ("| registry exists | {0} |" -f (Format-Cell $registry.exists))
    $lines += ("| readable records | {0} |" -f $records.Count)
    $lines += ("| skipped bad lines | {0} |" -f @($registry.warnings).Count)
    $lines += ""

    if (-not $registry.exists) {
        $lines += ("Registry file not found: {0}" -f $registry.path)
        $lines += ""
        return $lines
    }

    if (@($registry.warnings).Count -gt 0) {
        $lines += "## Warnings"
        $lines += ""
        foreach ($warning in @($registry.warnings)) {
            $lines += ("- {0}" -f $warning)
        }
        $lines += ""
    }

    if ($IncludeSummary) {
        $lines = Add-RegistrySummaryLines -Lines $lines -Records $records
    }
    if ($IncludeRecent) {
        $lines = Add-RegistryRecentLines -Lines $lines -Records $records -Count $RecentCount
    }
    if ($Address) {
        $lines = Add-RegistryAddrLines -Lines $lines -Records $records -Address $Address
    }
    if ($IncludeOutliers) {
        $lines = Add-RegistryOutlierLines -Lines $lines -Records $records
    }

    return $lines
}

function Build-ReportLines {
    param([object[]]$Records, [int]$RequestedLatest, [string]$Root, [string]$CompareTo, [string]$Profile, [bool]$OnlyBaselineEligible, [bool]$ExplainFailures, $Environment)

    $repoRoot = Get-RepoRoot -Root $Root
    $commitHash = "not_available"
    if ($repoRoot) {
        $commitOutput = @(Invoke-GitText -RepoPath $repoRoot -Arguments @("rev-parse", "HEAD"))
        if ($commitOutput.Count -gt 0 -and $commitOutput[0]) {
            $commitHash = $commitOutput[0]
        }
    }

    $diagnosticLevels = @($Records |
        ForEach-Object { Normalize-ReportValue $_.diagnostic_level } |
        Where-Object { $_ -ne "not_available" } |
        Select-Object -Unique)
    $validationProfiles = @($Records |
        ForEach-Object { Normalize-ReportValue $_.validation_profile } |
        Where-Object { $_ -ne "not_available" } |
        Select-Object -Unique)
    $diagnosticLevel = "not_available"
    if ($diagnosticLevels.Count -gt 0) {
        $diagnosticLevel = $diagnosticLevels -join ", "
    }
    $validationProfile = "not_available"
    if ($validationProfiles.Count -gt 0) {
        $validationProfile = $validationProfiles -join ", "
    }

    $classificationCounts = [ordered]@{}
    foreach ($classification in $ClassificationOrder) {
        $classificationCounts[$classification] = 0
    }
    foreach ($record in $Records) {
        if ($classificationCounts.Contains($record.classification)) {
            $classificationCounts[$record.classification] += 1
        } else {
            $classificationCounts["other"] += 1
        }
    }
    $performanceStatsByMetric = Get-PerformanceStatsMap -Records $Records

    $quickRecords = @($Records | Where-Object { $_.validation_profile -eq "quick" })
    $fullSuccessCount = @($Records | Where-Object { $_.validation_profile -eq "full" -and $_.classification -eq "success" }).Count
    $quickSuccessCount = @($Records | Where-Object { $_.classification -eq "quick_success" }).Count
    $nonSuccessRecords = @($Records | Where-Object { $_.classification -ne "success" -and $_.classification -ne "quick_success" })
    $executionBaselineIneligibleRecords = @($Records | Where-Object { $_.execution_baseline_eligible -eq "false" })
    $configMismatchRecords = @($Records | Where-Object { $_.classification -eq "invalid_config_mismatch" -or $_.config_mismatch -eq "true" })
    $cleanBaselineStatus = "CLEAN"
    if ($quickRecords.Count -gt 0 -or $executionBaselineIneligibleRecords.Count -gt 0 -or $configMismatchRecords.Count -gt 0) {
        $cleanBaselineStatus = "NOT_BASELINE_ELIGIBLE"
    } elseif ($nonSuccessRecords.Count -gt 0) {
        $cleanBaselineStatus = "CONTAINS_OUTLIERS"
    }

    $uniqueTrue = @($Records |
        Where-Object { $_.known_true_addr } |
        Select-Object -ExpandProperty known_true_addr -Unique)
    $knownTrueGroups = @($Records |
        Where-Object { $_.known_true_addr } |
        Group-Object known_true_addr |
        Sort-Object -Property @{ Expression = "Count"; Descending = $true }, Name)
    $repeatedKnownTrue = @($knownTrueGroups | Where-Object { $_.Count -gt 1 })

    $lines = @()
    $lines += "# Baseline Batch Log Classification Report"
    $lines += ""
    $lines += "| field | value |"
    $lines += "|---|---|"
    $lines += ("| report_title | {0} |" -f (Format-Cell "Baseline Batch Log Classification Report"))
    $lines += ("| generated_at | {0} |" -f (Format-Cell (Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")))
    $lines = Add-EnvironmentHeaderLines -Lines $lines -Environment $Environment
    $lines += ("| latest N | {0} |" -f (Format-Cell $RequestedLatest))
    $lines += ("| log root path | {0} |" -f (Format-Cell $Root))
    $lines += ("| repository path | {0} |" -f (Format-Cell (Normalize-ReportValue $repoRoot)))
    $lines += ("| git commit hash | {0} |" -f (Format-Cell $commitHash))
    $lines += ("| git working tree status summary | {0} |" -f (Format-Cell (Normalize-ReportValue (Get-GitStatusSummary -RepoPath $repoRoot))))
    $lines += ("| profile filter | {0} |" -f (Format-Cell $Profile))
    $lines += ("| only baseline eligible | {0} |" -f (Format-Cell $OnlyBaselineEligible))
    $lines += ("| diagnostic_level | {0} |" -f (Format-Cell $diagnosticLevel))
    $lines += ("| validation_profile | {0} |" -f (Format-Cell $validationProfile))
    $lines += ("| full_success count | {0} |" -f (Format-Cell $fullSuccessCount))
    $lines += ("| quick_success count | {0} |" -f (Format-Cell $quickSuccessCount))
    $lines += ("| execution_baseline_ineligible count | {0} |" -f (Format-Cell $executionBaselineIneligibleRecords.Count))
    $lines += ("| invalid_config_mismatch count | {0} |" -f (Format-Cell $configMismatchRecords.Count))
    $lines += ""

    $lines += "## Classification Summary"
    $lines += ""
    $lines += "| classification | count |"
    $lines += "|---|---:|"
    foreach ($classification in $ClassificationOrder) {
        $lines += ("| {0} | {1} |" -f (Format-Cell $classification), $classificationCounts[$classification])
    }
    $lines += ""

    $lines += "## Coverage"
    $lines += ""
    $lines += ("- unique known_true_addr count: {0}" -f $uniqueTrue.Count)
    $lines += ("- total batch count: {0}" -f $Records.Count)
    $lines += ("- clean baseline status: {0}" -f $cleanBaselineStatus)
    $lines += ("- execution baseline ineligible count: {0}" -f $executionBaselineIneligibleRecords.Count)
    $lines += ("- invalid config mismatch count: {0}" -f $configMismatchRecords.Count)
    if ($repeatedKnownTrue.Count -eq 0) {
        $lines += "- repeated known_true_addr list: none"
    } else {
        $lines += "- repeated known_true_addr list:"
        foreach ($group in $repeatedKnownTrue) {
            $lines += ("  - {0} ({1})" -f $group.Name, $group.Count)
        }
    }
    if ($uniqueTrue.Count -eq 1) {
        $lines += "- note: these runs reuse the same known_true_addr, so they prove repeat-run stability rather than cross-case generalization"
    } elseif ($uniqueTrue.Count -gt 1) {
        $lines += "- note: these runs cover multiple known_true_addr values"
    }
    $lines += ""

    $lines += "## Correctness Table"
    $lines += ""
    $lines += "| batch_id | known_true_addr | target_value_pattern | target_value_float | expected_target_pattern_from_float | config_mismatch | diagnostic_level | validation_profile | baseline_eligible | execution_outcome | execution_baseline_eligible | run_valid | collector_empty | classification | final hit | rank A/W/B | stable rank | best_candidate | selected A/W/B | recommendation |"
    $lines += "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    foreach ($record in $Records) {
        $lines += ("| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} | {9} | {10} | {11} | {12} | {13} | {14} | {15} | {16} | {17} | {18} | {19} |" -f `
            (Format-Cell $record.batch_id),
            (Format-Cell $record.known_true_addr),
            (Format-Cell $record.target_value_pattern),
            (Format-Cell $record.target_value_float),
            (Format-Cell $record.expected_target_pattern_from_float),
            (Format-Cell $record.config_mismatch),
            (Format-Cell (Normalize-ReportValue $record.diagnostic_level)),
            (Format-Cell (Normalize-ReportValue $record.validation_profile)),
            (Format-Cell $record.baseline_eligible),
            (Format-Cell $record.execution_outcome),
            (Format-Cell $record.execution_baseline_eligible),
            (Format-Cell $record.run_valid),
            (Format-Cell $record.collector_empty),
            (Format-Cell $record.classification),
            (Format-Cell $record.final_hit_true_addr),
            (Format-Cell $record.known_true_rank_position),
            (Format-Cell $record.stable_intersection_known_true_rank_position),
            (Format-Cell $record.final_best_candidate),
            (Format-Cell $record.true_in_selected),
            (Format-Cell $record.recommendation))
    }
    $lines += ""

    $lines += "## Performance Summary"
    $lines += ""
    $lines += "| metric | count | average | median | min | max |"
    $lines += "|---|---:|---:|---:|---:|---:|"
    foreach ($metric in $PerformanceMetricNames) {
        $stats = $performanceStatsByMetric[$metric]
        if ($null -eq $stats) {
            $lines += ("| {0} | 0 | - | - | - | - |" -f (Format-Cell $metric))
        } else {
            $lines += ("| {0} | {1} | {2} | {3} | {4} | {5} |" -f `
                (Format-Cell $metric),
                $stats.count,
                (Format-Number $stats.average),
                (Format-Number $stats.median),
                (Format-Number $stats.min),
                (Format-Number $stats.max))
        }
    }
    $lines += ""

    $lines += "## Outliers"
    $lines += ""
    if ($nonSuccessRecords.Count -eq 0) {
        $lines += "No non-success batches detected."
    } else {
        $lines += "| batch_id | known_true_addr | classification | reason |"
        $lines += "|---|---|---|---|"
        foreach ($record in $nonSuccessRecords) {
            $reason = "-"
            $details = @($record.details)
            if ($details.Count -gt 0) {
                $reason = Limit-Text $details[0]
            } elseif ($record.recommendation) {
                $reason = Limit-Text $record.recommendation
            }
            $lines += ("| {0} | {1} | {2} | {3} |" -f `
                (Format-Cell $record.batch_id),
                (Format-Cell $record.known_true_addr),
                (Format-Cell $record.classification),
                (Format-Cell $reason))
        }
    }
    $lines += ""

    if ($ExplainFailures) {
        $lines += "## Failure / Anomaly Explanations"
        $lines += ""
        if ($nonSuccessRecords.Count -eq 0) {
            $lines += "No failures/anomalies detected."
        } else {
            foreach ($record in $nonSuccessRecords) {
                $lines += Get-InspectionLines -Record $record
                $lines += ""
            }
        }
        $lines += ""
    }

    $codeChangeRecommendation = "no code changes recommended"
    $clearIssueClasses = @("suspected_filter_bug", "selected_quota_issue", "ranking_issue")
    foreach ($record in $nonSuccessRecords) {
        if ($clearIssueClasses -contains $record.classification) {
            $codeChangeRecommendation = "code review recommended for classifier-detected issue"
            break
        }
    }

    $replacementRecommendation = "no replacement sample recommended"
    if ($nonSuccessRecords.Count -gt 0) {
        $replacementRecommendation = "replacement sample recommended for non-success outliers"
    }

    $lines += "## Conclusion"
    $lines += ""
    $lines += ("- clean baseline: {0}" -f $cleanBaselineStatus)
    $lines += ("- replacement sample recommendation: {0}" -f $replacementRecommendation)
    $lines += ("- code change recommendation: {0}" -f $codeChangeRecommendation)

    if ($CompareTo) {
        $currentSnapshot = [pscustomobject][ordered]@{
            latest_n = $RequestedLatest
            clean_baseline_status = $cleanBaselineStatus
            classification_counts = $classificationCounts
            unique_known_true_addr_count = $uniqueTrue.Count
            performance = $performanceStatsByMetric
        }
        $lines += ""
        $lines += Get-RegressionComparisonLines -Current $currentSnapshot -BaselinePath $CompareTo
    }

    return $lines
}

$scriptEnvironment = Get-ScriptEnvironmentInfo -ExpectedRoot $ExpectedRepoRoot -Root $LogRoot
Write-EnvironmentWarning -Environment $scriptEnvironment

$registryRecentRequested = $PSBoundParameters.ContainsKey("RegistryRecent")
$registryQueryRequested = ([bool]$RegistrySummary) -or $registryRecentRequested -or ([bool]$RegistryAddr) -or ([bool]$RegistryOutliers)
if ($registryQueryRequested) {
    $reportLines = @(Build-RegistryQueryReport `
        -Path $RegistryPath `
        -IncludeSummary ([bool]$RegistrySummary) `
        -IncludeRecent $registryRecentRequested `
        -RecentCount $RegistryRecent `
        -Address $RegistryAddr `
        -IncludeOutliers ([bool]$RegistryOutliers) `
        -Environment $scriptEnvironment)
    Write-Output $reportLines

    if ($OutFile) {
        try {
            $resolvedOutFile = [System.IO.Path]::GetFullPath($OutFile)
            $outDir = [System.IO.Path]::GetDirectoryName($resolvedOutFile)
            if ($outDir -and -not (Test-Path -LiteralPath $outDir)) {
                New-Item -ItemType Directory -Path $outDir -Force | Out-Null
            }

            Set-Content -LiteralPath $resolvedOutFile -Value $reportLines -Encoding UTF8
            Write-Output ""
            Write-Output ("Registry query report saved to: {0}" -f $resolvedOutFile)
        } catch {
            Write-Warning ("Failed to save registry query report to {0}: {1}" -f $OutFile, $_.Exception.Message)
        }
    }

    return
}

$reportLines = @()
$recordsForRegistry = @()
$consoleSummaryLines = @()
if ($InspectBatch) {
    $record = Get-BatchRecord -Root $LogRoot -BatchId $InspectBatch
    $recordsForRegistry = @($record)
    $reportLines = @(Get-InspectionLines -Record $record)
} else {
    $records = @()
    foreach ($batchInfo in @(Get-BatchIdInfos -Root $LogRoot)) {
        $record = Get-BatchRecord -Root $LogRoot -BatchId $batchInfo.BatchId
        if (Test-RecordProfileFilter -Record $record -Profile $Profile -OnlyBaselineEligible ([bool]$OnlyBaselineEligible)) {
            $records += $record
        }
        if ($records.Count -ge $Latest) {
            break
        }
    }

    $recordsForRegistry = $records
    $reportLines = @(Build-ReportLines -Records $records -RequestedLatest $Latest -Root $LogRoot -CompareTo $CompareTo -Profile $Profile -OnlyBaselineEligible ([bool]$OnlyBaselineEligible) -ExplainFailures ([bool]$ExplainFailures) -Environment $scriptEnvironment)
    $useConsoleSummary = (([bool]$ConsoleSummary) -or (-not [bool]$Markdown)) -and -not $CompareTo -and -not $ExplainFailures
    if ($useConsoleSummary) {
        $consoleSummaryLines = @(Get-ConsoleSummaryLines -Records $records)
    }
}
if ($consoleSummaryLines.Count -gt 0) {
    Write-Output $consoleSummaryLines
} else {
    Write-Output $reportLines
}

if ($OutFile) {
    try {
        $resolvedOutFile = [System.IO.Path]::GetFullPath($OutFile)
        $outDir = [System.IO.Path]::GetDirectoryName($resolvedOutFile)
        if ($outDir -and -not (Test-Path -LiteralPath $outDir)) {
            New-Item -ItemType Directory -Path $outDir -Force | Out-Null
        }

        Set-Content -LiteralPath $resolvedOutFile -Value $reportLines -Encoding UTF8
        Write-Output ""
        Write-Output ("Baseline report saved to: {0}" -f $resolvedOutFile)
    } catch {
        Write-Warning ("Failed to save baseline report to {0}: {1}" -f $OutFile, $_.Exception.Message)
    }
}

if ($AppendRegistry) {
    $registryResult = Append-RegistryRecords -Records $recordsForRegistry -Path $RegistryPath -Root $LogRoot
    Write-Output ""
    Write-Output "=== registry_append ==="
    Write-Output ("registry_path = {0}" -f $registryResult.path)
    Write-Output ("appended_count = {0}" -f $registryResult.appended)
    Write-Output ("skipped_duplicate_count = {0}" -f $registryResult.duplicates)
    if ($registryResult.error) {
        Write-Warning ("Registry append failed: {0}" -f $registryResult.error)
    }
}
