param(
    [int]$Latest = 5,
    [string]$LogRoot = "D:\armedforces.io-v2\log\auto_output",
    [ValidateSet("all", "full", "quick")]
    [string]$Profile = "all",
    [switch]$OnlyBaselineEligible,
    [string]$InspectBatch,
    [switch]$ExplainFailures,
    [string]$CompareTo,
    [string]$OutFile
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$ClassificationOrder = @(
    "success",
    "quick_success",
    "quick_failure",
    "collector_runtime_empty",
    "incomplete_output",
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
        if ($Record.classification -eq "known_true_value_mismatch" -or $Record.classification -eq "suspected_filter_bug") {
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

    return [pscustomobject][ordered]@{
        batch_id = $BatchId
        known_true_addr = $knownTrue
        target_value_pattern = $targetPattern
        target_value_float = $targetFloat
        diagnostic_level = $diagnosticLevel
        validation_profile = $validationProfile
        baseline_eligible = Select-FirstValue @((Get-KvValue $stable "baseline_eligible"), (Get-KvValue $summary "baseline_eligible"))
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
    $lines += ("| diagnostic_level | {0} |" -f (Format-Cell $Record.diagnostic_level))
    $lines += ("| validation_profile | {0} |" -f (Format-Cell $Record.validation_profile))
    $lines += ("| classification | {0} |" -f (Format-Cell $Record.classification))
    $lines += ("| run_valid | {0} |" -f (Format-Cell $Record.run_valid))
    $lines += ("| collector_empty | {0} |" -f (Format-Cell $Record.collector_empty))
    $lines += ("| baseline_eligible | {0} |" -f (Format-Cell $Record.baseline_eligible))
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

function Build-ReportLines {
    param([object[]]$Records, [int]$RequestedLatest, [string]$Root, [string]$CompareTo, [string]$Profile, [bool]$OnlyBaselineEligible, [bool]$ExplainFailures)

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
    $cleanBaselineStatus = "CLEAN"
    if ($quickRecords.Count -gt 0) {
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
    $lines += "| batch_id | known_true_addr | diagnostic_level | validation_profile | baseline_eligible | run_valid | collector_empty | classification | final hit | rank A/W/B | stable rank | best_candidate | selected A/W/B | recommendation |"
    $lines += "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    foreach ($record in $Records) {
        $lines += ("| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} | {9} | {10} | {11} | {12} | {13} |" -f `
            (Format-Cell $record.batch_id),
            (Format-Cell $record.known_true_addr),
            (Format-Cell (Normalize-ReportValue $record.diagnostic_level)),
            (Format-Cell (Normalize-ReportValue $record.validation_profile)),
            (Format-Cell $record.baseline_eligible),
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

$reportLines = @()
if ($InspectBatch) {
    $record = Get-BatchRecord -Root $LogRoot -BatchId $InspectBatch
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

    $reportLines = @(Build-ReportLines -Records $records -RequestedLatest $Latest -Root $LogRoot -CompareTo $CompareTo -Profile $Profile -OnlyBaselineEligible ([bool]$OnlyBaselineEligible) -ExplainFailures ([bool]$ExplainFailures))
}
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
        Write-Output ("Baseline report saved to: {0}" -f $resolvedOutFile)
    } catch {
        Write-Warning ("Failed to save baseline report to {0}: {1}" -f $OutFile, $_.Exception.Message)
    }
}
