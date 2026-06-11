param(
    [int]$Latest = 5,
    [string]$LogRoot = "D:\armedforces.io-v2\log\auto_output"
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

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

function Parse-ModeLog {
    param([string]$Path)

    $kv = Read-KvMap $Path
    $filterLine = Get-FirstMatchingLine $Path "\[filter_known_true\]"

    return [pscustomobject][ordered]@{
        present = [bool]$Path
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
    $stableRank = Get-KvValue $stable "stable_intersection_known_true_rank_position"
    $bestCandidate = Select-FirstValue @((Get-KvValue $stable "stable_intersection_best_candidate"), (Get-KvValue $summary "best_candidate"))
    $recommendation = Get-Recommendation @($stablePath, $summaryPath)

    $missing = @()
    if (-not $summaryPath) { $missing += "summary.txt" }
    if (-not $diagnosticPath) { $missing += "diagnostic_diff.txt" }
    if (-not $stablePath) { $missing += "stable output" }
    if (-not $noProbeAPath) { $missing += "no_probe_A" }
    if (-not $withProbePath) { $missing += "with_probe" }
    if (-not $noProbeBPath) { $missing += "no_probe_B" }

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
        if ($classification -eq "other" -and $stableRank -eq "1" -and $bestCandidate -eq $knownTrue) {
            $classification = "success"
        }
    }

    return [pscustomobject][ordered]@{
        batch_id = $BatchId
        known_true_addr = $knownTrue
        target_value_pattern = $targetPattern
        target_value_float = $targetFloat
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
    }
}

$records = @(Get-BatchIds -Root $LogRoot -Count $Latest | ForEach-Object {
    Get-BatchRecord -Root $LogRoot -BatchId $_
})

Write-Output "# Batch Log Classification"
Write-Output ""
Write-Output "Log root: ``$LogRoot``"
Write-Output "Latest batches requested: ``$Latest``"
Write-Output ""
Write-Output "| batch_id | known_true_addr | target_pattern | target_float | run_valid | failure_class | collector_empty | raw A/W/B | filtered A/W/B | prescored A/W/B | selected A/W/B | rank A/W/B | stable rank | best_candidate | final hit | recommendation | classification |"
Write-Output "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
foreach ($record in $records) {
    Write-Output ("| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} | {9} | {10} | {11} | {12} | {13} | {14} | {15} | {16} |" -f `
        (Format-Cell $record.batch_id),
        (Format-Cell $record.known_true_addr),
        (Format-Cell $record.target_value_pattern),
        (Format-Cell $record.target_value_float),
        (Format-Cell $record.run_valid),
        (Format-Cell $record.failure_class),
        (Format-Cell $record.collector_empty),
        (Format-Cell $record.true_in_raw),
        (Format-Cell $record.true_in_filtered),
        (Format-Cell $record.true_in_prescored),
        (Format-Cell $record.true_in_selected),
        (Format-Cell $record.known_true_rank_position),
        (Format-Cell $record.stable_intersection_known_true_rank_position),
        (Format-Cell $record.final_best_candidate),
        (Format-Cell $record.final_hit_true_addr),
        (Format-Cell $record.recommendation),
        (Format-Cell $record.classification))
}

Write-Output ""
Write-Output "## Summary"
foreach ($group in ($records | Group-Object classification | Sort-Object Name)) {
    Write-Output ("- {0}: {1}" -f $group.Name, $group.Count)
}

$uniqueTrue = @($records | Where-Object { $_.known_true_addr } | Select-Object -ExpandProperty known_true_addr -Unique)
Write-Output ("- unique known_true_addr count: {0}" -f $uniqueTrue.Count)
if ($uniqueTrue.Count -eq 1) {
    Write-Output "- note: these runs reuse the same known_true_addr, so they prove repeat-run stability rather than cross-case generalization"
} elseif ($uniqueTrue.Count -gt 1) {
    Write-Output "- note: these runs cover multiple known_true_addr values"
}

$detailRecords = @($records | Where-Object { $_.details.Count -gt 0 })
if ($detailRecords.Count -gt 0) {
    Write-Output ""
    Write-Output "## Details"
    foreach ($record in $detailRecords) {
        Write-Output ("- {0}:" -f $record.batch_id)
        foreach ($detail in $record.details) {
            Write-Output ("  - {0}" -f $detail)
        }
    }
}
