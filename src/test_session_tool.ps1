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
    [string]$DiagnosticLevel = "basic"
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$ExpectedProjectRoot = "D:\armedforces.io-v2"
$ProjectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd("\", "/")
$CaseConfigToolPath = Join-Path (Join-Path $ProjectRootPath "src") "case_config_tool.ps1"
$ClassifierPath = Join-Path (Join-Path $ProjectRootPath "src") "batch_log_classifier.ps1"
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
    Write-Output "  compare-full   Compare latest 20 full batches to the compact baseline"
    Write-Output "  inspect-latest Inspect the latest batch id from -LogRoot"
    Write-Output "  status         Show config, latest 5 classifier summary, registry summary, and git status"
    Write-Output ""
    Write-Output "Prepare options:"
    Write-Output "  -CaseId <id> -KnownTrueAddr <addr> [-Profile quick|full] [-DiagnosticLevel basic|debug|trace]"
    Write-Output ""
    Write-Output "Common options:"
    Write-Output "  -ProjectRoot D:\armedforces.io-v2"
    Write-Output "  -LogRoot D:\armedforces.io-v2\log\auto_output"
}

function Invoke-WorkflowCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [switch]$Capture
    )

    $commandParts = @("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $FilePath) + @($Arguments)
    Write-Host ("Executing: {0}" -f (Format-CommandLine -Parts $commandParts))
    Write-Host ""

    $output = @(& powershell -NoProfile -ExecutionPolicy Bypass -File $FilePath @Arguments 2>&1)
    $exitCode = $LASTEXITCODE
    foreach ($line in $output) {
        Write-Host $line
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

$availableCommands = @("prepare", "post-quick", "post-full", "compare-full", "inspect-latest", "status")
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
        if (-not $CaseId) {
            Write-Error "-CaseId is required for prepare"
            exit 1
        }
        if (-not $KnownTrueAddr) {
            Write-Error "-KnownTrueAddr is required for prepare"
            exit 1
        }

        $args = @(
            "-Set",
            "-CaseId", $CaseId,
            "-KnownTrueAddr", $KnownTrueAddr,
            "-TargetValuePattern", $TargetValuePattern,
            "-TargetValueFloat", $TargetValueFloat.ToString("0.0###############", [System.Globalization.CultureInfo]::InvariantCulture),
            "-DiagnosticLevel", $DiagnosticLevel,
            "-ValidationProfile", $Profile
        )
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
        $args = @("-Latest", "20", "-Profile", "full", "-LogRoot", $LogRoot, "-CompareTo", $BaselinePath)
        $result = Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments $args -Capture
        if ($result.exit_code -ne 0) {
            exit $result.exit_code
        }

        $comparison = Get-ComparisonStatus -OutputLines $result.output
        Write-WorkflowSummary -Title "Compare-Full Summary" -Fields ([ordered]@{
            "regression status" = $comparison.status
            "code changes recommended" = $comparison.code_changes_recommended
        })
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
        Write-Output "## Current Case Config"
        $caseResult = Invoke-WorkflowCommand -FilePath $CaseConfigToolPath -Arguments @("-Show")
        if ($caseResult.exit_code -ne 0) {
            exit $caseResult.exit_code
        }

        Write-Output ""
        Write-Output "## Latest 5 Classifier Summary"
        $latestResult = Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments @("-Latest", "5", "-LogRoot", $LogRoot, "-ConsoleSummary")
        if ($latestResult.exit_code -ne 0) {
            exit $latestResult.exit_code
        }

        Write-Output ""
        Write-Output "## Registry Summary"
        $registryResult = Invoke-WorkflowCommand -FilePath $ClassifierPath -Arguments @("-RegistrySummary", "-LogRoot", $LogRoot)
        if ($registryResult.exit_code -ne 0) {
            exit $registryResult.exit_code
        }

        Write-Output ""
        Write-Output "## Git Status"
        $gitStatus = @(& git -C $ProjectRootPath status --short)
        if ($gitStatus.Count -eq 0) {
            Write-Output "clean"
        } else {
            $gitStatus | ForEach-Object { Write-Output $_ }
        }
        exit 0
    }
}
