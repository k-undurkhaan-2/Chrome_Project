param(
    [int]$Latest = 5,
    [string]$LogRoot = "D:\armedforces.io-v2\log\auto_output",
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

function Get-BatchIds {
    param([string]$Root, [int]$Count)

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
        true_in_raw = Get-KvValue $kv "true_in_raw"
        true_in_unique = Get-KvValue $kv "true_in_unique"
        true_in_filtered = Get-KvValue $kv "true_in_filtered"
        true_in_prescored = Get-KvValue $kv "true_in_prescored"
        true_in_selected = Get-KvValue $kv "true_in_selected"
        known_true_rank_position = Get-KvValue $kv "known_true_rank_position"
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
    }
}

function Build-ReportLines {
    param([object[]]$Records, [int]$RequestedLatest, [string]$Root)

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
        $values = @()
        foreach ($record in $Records) {
            if ($record.performance_metrics.Contains($metric)) {
                $values += @($record.performance_metrics[$metric])
            }
        }
        $stats = Get-MetricStats -Values $values
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

    return $lines
}

$records = @(Get-BatchIds -Root $LogRoot -Count $Latest | ForEach-Object {
    Get-BatchRecord -Root $LogRoot -BatchId $_
})

$reportLines = @(Build-ReportLines -Records $records -RequestedLatest $Latest -Root $LogRoot)
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
