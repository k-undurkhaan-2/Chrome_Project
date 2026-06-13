param(
    [switch]$Show,
    [switch]$Set,
    [switch]$Validate,
    [switch]$Help,
    [switch]$Markdown,
    [string]$CaseId,
    [string]$KnownTrueAddr,
    [string]$TargetValuePattern = "0x42C80000",
    [double]$TargetValueFloat = 100.0,
    [ValidateSet("basic", "debug", "trace")]
    [string]$DiagnosticLevel = "basic",
    [ValidateSet("full", "quick")]
    [string]$ValidationProfile = "full",
    [ValidateSet("full", "quick")]
    [string]$SetProfile,
    [ValidateSet("basic", "debug", "trace")]
    [string]$SetDiagnosticLevel,
    [string]$PrepareRestoreFromBatch,
    [string]$LogRoot = "D:\armedforces.io-v2\log\auto_output",
    [switch]$Apply,
    [switch]$EnableWrite,
    [switch]$ConfirmWrite
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$ScriptRoot = $PSScriptRoot
$RepoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $ScriptRoot)).TrimEnd("\", "/")
$ConfigPath = Join-Path $ScriptRoot "run_case_config.local.lua"
$BackupPath = Join-Path $ScriptRoot "run_case_config.local.lua.bak"
$ExamplePath = Join-Path $ScriptRoot "run_case_config.example.lua"
$RelativeConfigPath = "src/run_case_config.local.lua"
$ExecutionConfirmText = "I_ACCEPT_WRITE_TO_LIVE_MEMORY"
$PreservedConfigKeys = @(
    "execution_mode",
    "write_enabled",
    "execution_confirm",
    "write_value_float",
    "write_value_pattern",
    "write_method",
    "execution_addr_source",
    "require_known_true_match",
    "require_full_profile",
    "require_old_value_match",
    "readback_tolerance"
)

function Write-Help {
    Write-Output "Case config helper"
    Write-Output ""
    Write-Output "Usage:"
    Write-Output "  powershell -NoProfile -ExecutionPolicy Bypass -File `"D:\armedforces.io-v2\src\case_config_tool.ps1`" -Show"
    Write-Output "  powershell -NoProfile -ExecutionPolicy Bypass -File `"D:\armedforces.io-v2\src\case_config_tool.ps1`" -Show -Markdown"
    Write-Output "  powershell -NoProfile -ExecutionPolicy Bypass -File `"D:\armedforces.io-v2\src\case_config_tool.ps1`" -Validate"
    Write-Output "  powershell -NoProfile -ExecutionPolicy Bypass -File `"D:\armedforces.io-v2\src\case_config_tool.ps1`" -Set -KnownTrueAddr 0x25A061C7D48 [-CaseId case_001]"
    Write-Output "  powershell -NoProfile -ExecutionPolicy Bypass -File `"D:\armedforces.io-v2\src\case_config_tool.ps1`" -SetProfile quick"
    Write-Output "  powershell -NoProfile -ExecutionPolicy Bypass -File `"D:\armedforces.io-v2\src\case_config_tool.ps1`" -SetDiagnosticLevel trace"
    Write-Output "  powershell -NoProfile -ExecutionPolicy Bypass -File `"D:\armedforces.io-v2\src\case_config_tool.ps1`" -PrepareRestoreFromBatch 20260613-183041 [-Apply] [-EnableWrite -ConfirmWrite]"
}

function Format-Cell {
    param($Value)

    if ($null -eq $Value -or "$Value" -eq "") {
        return "-"
    }
    return ("$Value" -replace "\|", "\|")
}

function Read-CaseConfig {
    param([string]$Path)

    $config = [ordered]@{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $config
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*([A-Za-z0-9_]+)\s*=\s*"(.*)"\s*,?\s*$') {
            $value = $matches[2] -replace '\\"', '"' -replace '\\\\', '\'
            $config[$matches[1]] = $value
        } elseif ($line -match '^\s*([A-Za-z0-9_]+)\s*=\s*([^",{}\s]+)\s*,?\s*$') {
            $config[$matches[1]] = $matches[2]
        }
    }

    return $config
}

function Get-ConfigValue {
    param($Config, [string]$Key)

    if ($Config -and $Config.Contains($Key)) {
        return $Config[$Key]
    }
    return $null
}

function ConvertTo-LuaString {
    param([string]$Value)

    if ($null -eq $Value) {
        return ""
    }
    return $Value -replace '\\', '\\' -replace '"', '\"'
}

function ConvertTo-LuaLiteral {
    param([string]$Key, $Value)

    if ($null -eq $Value) {
        return 'nil'
    }

    $text = "$Value"
    if ($Key -in @("write_enabled", "require_known_true_match", "require_full_profile", "require_old_value_match")) {
        if ($text -match '^(?i:true|false)$') {
            return $text.ToLowerInvariant()
        }
    }
    if ($Key -in @("write_value_float", "readback_tolerance")) {
        $number = 0.0
        if ([double]::TryParse($text, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$number)) {
            return $number.ToString("0.0###############", [System.Globalization.CultureInfo]::InvariantCulture)
        }
    }

    return ('"{0}"' -f (ConvertTo-LuaString $text))
}

function Test-HexString {
    param($Value)

    if ($null -eq $Value) {
        return $false
    }
    return "$Value" -match '^0x[0-9A-Fa-f]+$'
}

function New-GeneratedCaseId {
    param([string]$Address)

    $hex = "$Address" -replace '^0x', ''
    $hex = $hex -replace '[^0-9A-Fa-f]', ''
    if (-not $hex) {
        $hex = "addr"
    }

    $suffixLength = [Math]::Min(5, $hex.Length)
    $suffix = $hex.Substring($hex.Length - $suffixLength).ToUpperInvariant()
    return ("case_{0}_{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss"), $suffix)
}

function Test-NumberString {
    param($Value)

    if ($null -eq $Value) {
        return $false
    }

    $number = 0.0
    return [double]::TryParse("$Value", [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$number)
}

function Test-GitIgnored {
    param([string]$RelativePath)

    try {
        & git -C $RepoRoot check-ignore -q -- $RelativePath
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Get-GitShortStatus {
    param([string]$RelativePath)

    try {
        $status = & git -C $RepoRoot status --short -- $RelativePath 2>$null
        return @($status)
    } catch {
        return @()
    }
}

function New-CompleteConfig {
    param($Base)

    $config = [ordered]@{
        case_id = Get-ConfigValue -Config $Base -Key "case_id"
        known_true_addr = Get-ConfigValue -Config $Base -Key "known_true_addr"
        target_value_pattern = Get-ConfigValue -Config $Base -Key "target_value_pattern"
        target_value_float = Get-ConfigValue -Config $Base -Key "target_value_float"
        diagnostic_level = Get-ConfigValue -Config $Base -Key "diagnostic_level"
        validation_profile = Get-ConfigValue -Config $Base -Key "validation_profile"
    }

    if (-not $config.target_value_pattern) { $config.target_value_pattern = "0x42C80000" }
    if (-not $config.target_value_float) { $config.target_value_float = "100.0" }
    if (-not $config.diagnostic_level) { $config.diagnostic_level = "basic" }
    if (-not $config.validation_profile) { $config.validation_profile = "full" }

    Add-PreservedConfigFields -Config $config -Base $Base
    return $config
}

function Add-PreservedConfigFields {
    param($Config, $Base)

    foreach ($key in $PreservedConfigKeys) {
        if ($Base -and $Base.Contains($key) -and -not $Config.Contains($key)) {
            $Config[$key] = $Base[$key]
        }
    }
}

function Write-CaseConfig {
    param($Config)

    if (Test-Path -LiteralPath $ConfigPath) {
        Copy-Item -LiteralPath $ConfigPath -Destination $BackupPath -Force
    }

    $floatText = ([double]$Config.target_value_float).ToString("0.0###############", [System.Globalization.CultureInfo]::InvariantCulture)
    $lines = @(
        "return {",
        ('  case_id = "{0}",' -f (ConvertTo-LuaString $Config.case_id)),
        ('  known_true_addr = "{0}",' -f (ConvertTo-LuaString $Config.known_true_addr)),
        ('  target_value_pattern = "{0}",' -f (ConvertTo-LuaString $Config.target_value_pattern)),
        ('  target_value_float = {0},' -f $floatText),
        ('  diagnostic_level = "{0}",' -f (ConvertTo-LuaString $Config.diagnostic_level)),
        ('  validation_profile = "{0}",' -f (ConvertTo-LuaString $Config.validation_profile))
    )
    foreach ($key in $PreservedConfigKeys) {
        if ($Config.Contains($key)) {
            $lines += ('  {0} = {1},' -f $key, (ConvertTo-LuaLiteral -Key $key -Value $Config[$key]))
        }
    }
    $lines += "}"

    Set-Content -LiteralPath $ConfigPath -Value $lines -Encoding UTF8
}

function Write-ConfigSummary {
    param($Config)

    $exists = Test-Path -LiteralPath $ConfigPath
    $gitignored = Test-GitIgnored -RelativePath $RelativeConfigPath

    Write-Output "| field | value |"
    Write-Output "|---|---|"
    Write-Output ("| case_id | {0} |" -f (Format-Cell (Get-ConfigValue -Config $Config -Key "case_id")))
    Write-Output ("| known_true_addr | {0} |" -f (Format-Cell (Get-ConfigValue -Config $Config -Key "known_true_addr")))
    Write-Output ("| target_value_pattern | {0} |" -f (Format-Cell (Get-ConfigValue -Config $Config -Key "target_value_pattern")))
    Write-Output ("| target_value_float | {0} |" -f (Format-Cell (Get-ConfigValue -Config $Config -Key "target_value_float")))
    Write-Output ("| diagnostic_level | {0} |" -f (Format-Cell (Get-ConfigValue -Config $Config -Key "diagnostic_level")))
    Write-Output ("| validation_profile | {0} |" -f (Format-Cell (Get-ConfigValue -Config $Config -Key "validation_profile")))
    Write-Output ("| config path | {0} |" -f (Format-Cell $ConfigPath))
    Write-Output ("| config exists | {0} |" -f (Format-Cell $exists))
    Write-Output ("| config is gitignored | {0} |" -f (Format-Cell $gitignored))

    if (-not $gitignored) {
        Write-Warning ("Local config is not ignored by git: {0}" -f $RelativeConfigPath)
    }
}

function Get-ConfigSummaryRows {
    param($Config)

    $exists = Test-Path -LiteralPath $ConfigPath
    $gitignored = Test-GitIgnored -RelativePath $RelativeConfigPath

    return @(
        [pscustomobject]@{ Field = "case_id"; Value = Format-Cell (Get-ConfigValue -Config $Config -Key "case_id") },
        [pscustomobject]@{ Field = "known_true_addr"; Value = Format-Cell (Get-ConfigValue -Config $Config -Key "known_true_addr") },
        [pscustomobject]@{ Field = "target_value_pattern"; Value = Format-Cell (Get-ConfigValue -Config $Config -Key "target_value_pattern") },
        [pscustomobject]@{ Field = "target_value_float"; Value = Format-Cell (Get-ConfigValue -Config $Config -Key "target_value_float") },
        [pscustomobject]@{ Field = "diagnostic_level"; Value = Format-Cell (Get-ConfigValue -Config $Config -Key "diagnostic_level") },
        [pscustomobject]@{ Field = "validation_profile"; Value = Format-Cell (Get-ConfigValue -Config $Config -Key "validation_profile") },
        [pscustomobject]@{ Field = "config path"; Value = Format-Cell $ConfigPath },
        [pscustomobject]@{ Field = "config exists"; Value = Format-Cell $exists },
        [pscustomobject]@{ Field = "config is gitignored"; Value = Format-Cell $gitignored }
    )
}

function Write-ConfigSummaryConsole {
    param($Config)

    $gitignored = Test-GitIgnored -RelativePath $RelativeConfigPath
    $fieldWidth = 24

    Write-Output "Case Config"
    Write-Output ""
    Write-Output ("{0,-$fieldWidth} {1}" -f "Field", "Value")
    Write-Output ("{0,-$fieldWidth} {1}" -f "-----", "-----")
    foreach ($row in @(Get-ConfigSummaryRows -Config $Config)) {
        Write-Output ("{0,-$fieldWidth} {1}" -f $row.Field, $row.Value)
    }

    if (-not $gitignored) {
        Write-Warning ("Local config is not ignored by git: {0}" -f $RelativeConfigPath)
    }
}

function Write-ConfigSummaryOutput {
    param($Config, [bool]$UseMarkdown)

    if ($UseMarkdown) {
        Write-Output "# Case Config"
        Write-Output ""
        Write-ConfigSummary -Config $Config
    } else {
        Write-ConfigSummaryConsole -Config $Config
    }
}

function Test-LogValuePresent {
    param($Value)

    return ($null -ne $Value -and "$Value" -ne "" -and "$Value" -ne "nil" -and "$Value" -ne "-")
}

function Test-LogBoolTrue {
    param($Value)

    return (Test-LogValuePresent -Value $Value) -and "$Value".ToLowerInvariant() -eq "true"
}

function Get-LogField {
    param($Block, [string]$Key)

    if ($Block -and $Block.Fields -and $Block.Fields.Contains($Key)) {
        return $Block.Fields[$Key]
    }
    return $null
}

function Get-BatchLogPath {
    param([string]$BatchId, [string]$Root)

    if (-not (Test-Path -LiteralPath $Root)) {
        throw ("Log root does not exist: {0}" -f $Root)
    }

    $summaryPath = Join-Path $Root ("{0}__summary.txt" -f $BatchId)
    if (Test-Path -LiteralPath $summaryPath) {
        return $summaryPath
    }

    $diagnosticPath = Join-Path $Root ("{0}__diagnostic_diff.txt" -f $BatchId)
    if (Test-Path -LiteralPath $diagnosticPath) {
        return $diagnosticPath
    }

    $candidates = @(Get-ChildItem -LiteralPath $Root -File -Filter ("{0}*" -f $BatchId) |
        Where-Object { $_.Name -like "*summary.txt" -or $_.Name -like "*diagnostic_diff.txt" } |
        Sort-Object Name)

    if ($candidates.Count -gt 0) {
        return $candidates[0].FullName
    }

    throw ("No summary or diagnostic log found for batch {0} in {1}" -f $BatchId, $Root)
}

function Read-BatchLogBlocks {
    param([string]$Path)

    $blocks = @()
    $currentName = "batch_header"
    $currentFields = [ordered]@{}

    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*---\s+(.+?)\s+---\s*$') {
            if ($currentFields.Count -gt 0) {
                $blocks += [pscustomobject]@{
                    Name = $currentName
                    Fields = $currentFields
                }
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
        $blocks += [pscustomobject]@{
            Name = $currentName
            Fields = $currentFields
        }
    }

    return $blocks
}

function Select-RestoreSourceBlock {
    param([object[]]$Blocks)

    $eligible = @($Blocks | Where-Object {
        Test-LogValuePresent -Value (Get-LogField -Block $_ -Key "execution_addr")
    })

    $rollbackBlocks = @($eligible | Where-Object {
        Test-LogBoolTrue -Value (Get-LogField -Block $_ -Key "rollback_available")
    })

    if ($rollbackBlocks.Count -gt 0) {
        return $rollbackBlocks[$rollbackBlocks.Count - 1]
    }

    if ($eligible.Count -gt 0) {
        return $eligible[$eligible.Count - 1]
    }

    return $null
}

function Get-RequiredRestoreField {
    param($Block, [string[]]$Keys, [string]$Label)

    foreach ($key in $Keys) {
        $value = Get-LogField -Block $Block -Key $key
        if (Test-LogValuePresent -Value $value) {
            return $value
        }
    }

    throw ("Cannot prepare restore config because {0} is missing." -f $Label)
}

function New-RestoreCaseId {
    param([string]$BatchId, [string]$Address)

    $hex = "$Address" -replace '^0x', ''
    $hex = $hex -replace '[^0-9A-Fa-f]', ''
    if (-not $hex) {
        $hex = "addr"
    }
    $suffixLength = [Math]::Min(5, $hex.Length)
    $suffix = $hex.Substring($hex.Length - $suffixLength).ToUpperInvariant()
    $safeBatch = "$BatchId" -replace '[^0-9A-Za-z_]', '_'
    return ("restore_{0}_{1}" -f $safeBatch, $suffix)
}

function New-RestorePlan {
    param(
        [string]$BatchId,
        [string]$Root,
        [bool]$ApplyConfig,
        [bool]$EnableWriteConfig,
        [bool]$ConfirmWriteConfig
    )

    $logPath = Get-BatchLogPath -BatchId $BatchId -Root $Root
    $blocks = @(Read-BatchLogBlocks -Path $logPath)
    $sourceBlock = Select-RestoreSourceBlock -Blocks $blocks
    if ($null -eq $sourceBlock) {
        throw ("Cannot prepare restore config because no execution block was found in {0}" -f $logPath)
    }

    $executionAddr = Get-RequiredRestoreField -Block $sourceBlock -Keys @("execution_addr") -Label "execution_addr"
    $currentPattern = Get-RequiredRestoreField -Block $sourceBlock -Keys @("readback_pattern") -Label "readback_pattern"
    $currentFloat = Get-RequiredRestoreField -Block $sourceBlock -Keys @("readback_float") -Label "readback_float"
    $restorePattern = Get-RequiredRestoreField -Block $sourceBlock -Keys @("rollback_value_pattern", "old_value_pattern") -Label "rollback or old value pattern"
    $restoreFloat = Get-RequiredRestoreField -Block $sourceBlock -Keys @("rollback_value_float", "old_value_float") -Label "rollback or old value float"
    $rollbackAvailable = Test-LogBoolTrue -Value (Get-LogField -Block $sourceBlock -Key "rollback_available")
    $writeReady = $EnableWriteConfig -and $ConfirmWriteConfig

    if (-not (Test-HexString -Value $executionAddr)) {
        throw ("Cannot prepare restore config because execution_addr is not a hex address: {0}" -f $executionAddr)
    }
    if (-not (Test-HexString -Value $currentPattern)) {
        throw ("Cannot prepare restore config because readback_pattern is not a hex pattern: {0}" -f $currentPattern)
    }
    if (-not (Test-HexString -Value $restorePattern)) {
        throw ("Cannot prepare restore config because rollback/old pattern is not a hex pattern: {0}" -f $restorePattern)
    }
    if (-not (Test-NumberString -Value $currentFloat)) {
        throw ("Cannot prepare restore config because readback_float is not numeric: {0}" -f $currentFloat)
    }
    if (-not (Test-NumberString -Value $restoreFloat)) {
        throw ("Cannot prepare restore config because rollback/old float is not numeric: {0}" -f $restoreFloat)
    }
    if ($writeReady -and -not $rollbackAvailable) {
        throw "Cannot prepare write-ready restore config because rollback_available is not true."
    }

    return [ordered]@{
        source_batch = $BatchId
        source_log_path = $logPath
        source_block = $sourceBlock.Name
        execution_addr = $executionAddr
        restore_target_current_pattern = $currentPattern
        restore_target_current_float = $currentFloat
        restore_write_value_pattern = $restorePattern
        restore_write_value_float = $restoreFloat
        rollback_available = $rollbackAvailable
        apply = $ApplyConfig
        write_enabled = $writeReady
        confirm_write = $ConfirmWriteConfig
        config_path = $ConfigPath
    }
}

function New-RestoreConfig {
    param($Plan)

    $writeReady = [bool]$Plan.write_enabled
    $config = [ordered]@{
        case_id = New-RestoreCaseId -BatchId $Plan.source_batch -Address $Plan.execution_addr
        known_true_addr = $Plan.execution_addr
        target_value_pattern = $Plan.restore_target_current_pattern
        target_value_float = $Plan.restore_target_current_float
        diagnostic_level = "basic"
        validation_profile = "full"
        execution_mode = $(if ($writeReady) { "write" } else { "dry_run" })
        write_enabled = $(if ($writeReady) { "true" } else { "false" })
        write_value_float = $Plan.restore_write_value_float
        write_value_pattern = $Plan.restore_write_value_pattern
        write_method = "float"
        execution_addr_source = "stable_intersection_best_candidate"
        require_known_true_match = "true"
        require_full_profile = "true"
        require_old_value_match = "true"
        readback_tolerance = "0.0001"
    }

    if ($writeReady) {
        $config.execution_confirm = $ExecutionConfirmText
    }

    return $config
}

function Write-RestorePlanConsole {
    param($Plan)

    $fieldWidth = 32
    Write-Output "Restore Plan"
    Write-Output ""
    Write-Output ("{0,-$fieldWidth} {1}" -f "Field", "Value")
    Write-Output ("{0,-$fieldWidth} {1}" -f "-----", "-----")
    foreach ($key in @(
        "source_batch",
        "execution_addr",
        "restore_target_current_pattern",
        "restore_target_current_float",
        "restore_write_value_pattern",
        "restore_write_value_float",
        "rollback_available",
        "apply",
        "write_enabled",
        "confirm_write",
        "config_path"
    )) {
        Write-Output ("{0,-$fieldWidth} {1}" -f $key, (Format-Cell $Plan[$key]))
    }
}

function New-ValidationRow {
    param([string]$Status, [string]$Check, [string]$Detail)

    return [pscustomobject][ordered]@{
        status = $Status
        check = $Check
        detail = $Detail
    }
}

function Test-CaseConfig {
    param($Config)

    $rows = @()
    $exists = Test-Path -LiteralPath $ConfigPath
    $gitignored = Test-GitIgnored -RelativePath $RelativeConfigPath

    if ($exists) {
        $rows += New-ValidationRow -Status "PASS" -Check "config file exists" -Detail $ConfigPath
    } else {
        $rows += New-ValidationRow -Status "FAIL" -Check "config file exists" -Detail $ConfigPath
    }

    $knownTrue = Get-ConfigValue -Config $Config -Key "known_true_addr"
    if (Test-HexString -Value $knownTrue) {
        $rows += New-ValidationRow -Status "PASS" -Check "known_true_addr hex" -Detail $knownTrue
    } else {
        $rows += New-ValidationRow -Status "FAIL" -Check "known_true_addr hex" -Detail (Format-Cell $knownTrue)
    }

    $pattern = Get-ConfigValue -Config $Config -Key "target_value_pattern"
    if (Test-HexString -Value $pattern) {
        $rows += New-ValidationRow -Status "PASS" -Check "target_value_pattern hex" -Detail $pattern
    } else {
        $rows += New-ValidationRow -Status "FAIL" -Check "target_value_pattern hex" -Detail (Format-Cell $pattern)
    }

    $floatValue = Get-ConfigValue -Config $Config -Key "target_value_float"
    if (Test-NumberString -Value $floatValue) {
        $rows += New-ValidationRow -Status "PASS" -Check "target_value_float numeric" -Detail $floatValue
    } else {
        $rows += New-ValidationRow -Status "FAIL" -Check "target_value_float numeric" -Detail (Format-Cell $floatValue)
    }

    $diagnosticLevel = Get-ConfigValue -Config $Config -Key "diagnostic_level"
    if (@("basic", "debug", "trace") -contains $diagnosticLevel) {
        $rows += New-ValidationRow -Status "PASS" -Check "diagnostic_level allowed" -Detail $diagnosticLevel
    } else {
        $rows += New-ValidationRow -Status "FAIL" -Check "diagnostic_level allowed" -Detail (Format-Cell $diagnosticLevel)
    }

    $validationProfile = Get-ConfigValue -Config $Config -Key "validation_profile"
    if (@("full", "quick") -contains $validationProfile) {
        $rows += New-ValidationRow -Status "PASS" -Check "validation_profile allowed" -Detail $validationProfile
    } else {
        $rows += New-ValidationRow -Status "FAIL" -Check "validation_profile allowed" -Detail (Format-Cell $validationProfile)
    }

    if ($gitignored) {
        $rows += New-ValidationRow -Status "PASS" -Check "local config gitignored" -Detail $RelativeConfigPath
    } else {
        $rows += New-ValidationRow -Status "WARN" -Check "local config gitignored" -Detail "add $RelativeConfigPath to .gitignore"
    }

    $exampleStatus = @(Get-GitShortStatus -RelativePath "src/run_case_config.example.lua")
    if ($exampleStatus.Count -eq 0) {
        $rows += New-ValidationRow -Status "PASS" -Check "example config unchanged" -Detail $ExamplePath
    } else {
        $rows += New-ValidationRow -Status "FAIL" -Check "example config unchanged" -Detail ($exampleStatus -join "; ")
    }

    return $rows
}

function Write-ValidationRows {
    param([object[]]$Rows)

    Write-Output "| status | check | detail |"
    Write-Output "|---|---|---|"
    foreach ($row in $Rows) {
        Write-Output ("| {0} | {1} | {2} |" -f (Format-Cell $row.status), (Format-Cell $row.check), (Format-Cell $row.detail))
    }
}

$actions = @()
if ($Show) { $actions += "Show" }
if ($Set) { $actions += "Set" }
if ($Validate) { $actions += "Validate" }
if ($SetProfile) { $actions += "SetProfile" }
if ($SetDiagnosticLevel) { $actions += "SetDiagnosticLevel" }
if ($PrepareRestoreFromBatch) { $actions += "PrepareRestoreFromBatch" }

if ($Help -or $actions.Count -eq 0) {
    Write-Help
    exit 0
}

if ($actions.Count -gt 1) {
    Write-Error ("Choose exactly one action. Requested: {0}" -f ($actions -join ", "))
    exit 1
}

$currentConfig = Read-CaseConfig -Path $ConfigPath

if ($Show) {
    Write-ConfigSummaryOutput -Config $currentConfig -UseMarkdown ([bool]$Markdown)
    exit 0
}

if ($Validate) {
    Write-Output "# Case Config Validation"
    Write-Output ""
    $rows = @(Test-CaseConfig -Config $currentConfig)
    Write-ValidationRows -Rows $rows

    if (@($rows | Where-Object { $_.status -eq "WARN" }).Count -gt 0) {
        Write-Warning "Validation completed with warnings."
    }
    if (@($rows | Where-Object { $_.status -eq "FAIL" }).Count -gt 0) {
        exit 1
    }
    exit 0
}

if ($Set) {
    if (-not $KnownTrueAddr) {
        Write-Error "-KnownTrueAddr is required with -Set"
        exit 1
    }

    $generatedCaseId = $false
    if (-not $CaseId) {
        $CaseId = New-GeneratedCaseId -Address $KnownTrueAddr
        $generatedCaseId = $true
    }

    $newConfig = [ordered]@{
        case_id = $CaseId
        known_true_addr = $KnownTrueAddr
        target_value_pattern = $TargetValuePattern
        target_value_float = $TargetValueFloat.ToString("0.0###############", [System.Globalization.CultureInfo]::InvariantCulture)
        diagnostic_level = $DiagnosticLevel
        validation_profile = $ValidationProfile
    }
    Add-PreservedConfigFields -Config $newConfig -Base $currentConfig
    Write-CaseConfig -Config $newConfig
    Write-Output ("Updated local config: {0}" -f $ConfigPath)
    if ($generatedCaseId) {
        Write-Output ("generated_case_id = {0}" -f $CaseId)
    }
    if (Test-Path -LiteralPath $BackupPath) {
        Write-Output ("Backup path: {0}" -f $BackupPath)
    }
    Write-ConfigSummaryOutput -Config (Read-CaseConfig -Path $ConfigPath) -UseMarkdown ([bool]$Markdown)
    exit 0
}

if ($PrepareRestoreFromBatch) {
    if ($EnableWrite -xor $ConfirmWrite) {
        Write-Warning "Restore write-ready config requires both -EnableWrite and -ConfirmWrite; generating dry-run restore config."
    }

    $writeReady = [bool]($EnableWrite -and $ConfirmWrite)
    $plan = New-RestorePlan `
        -BatchId $PrepareRestoreFromBatch `
        -Root $LogRoot `
        -ApplyConfig ([bool]$Apply) `
        -EnableWriteConfig $writeReady `
        -ConfirmWriteConfig ([bool]$ConfirmWrite)

    Write-RestorePlanConsole -Plan $plan

    if ($Apply) {
        $restoreConfig = New-RestoreConfig -Plan $plan
        Write-CaseConfig -Config $restoreConfig
        Write-Output ""
        Write-Output ("Applied restore config: {0}" -f $ConfigPath)
        if (Test-Path -LiteralPath $BackupPath) {
            Write-Output ("Backup path: {0}" -f $BackupPath)
        }
        Write-Output ""
        Write-ConfigSummaryOutput -Config (Read-CaseConfig -Path $ConfigPath) -UseMarkdown ([bool]$Markdown)
    }
    exit 0
}

if ($SetProfile) {
    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        Write-Error ("Local config does not exist: {0}" -f $ConfigPath)
        exit 1
    }
    $newConfig = New-CompleteConfig -Base $currentConfig
    if (-not $newConfig.case_id -or -not $newConfig.known_true_addr) {
        Write-Error "Existing config is missing case_id or known_true_addr; use -Set first."
        exit 1
    }
    $newConfig.validation_profile = $SetProfile
    Write-CaseConfig -Config $newConfig
    Write-Output ("Updated validation_profile to {0}" -f $SetProfile)
    Write-Output ("Backup path: {0}" -f $BackupPath)
    Write-ConfigSummaryOutput -Config (Read-CaseConfig -Path $ConfigPath) -UseMarkdown ([bool]$Markdown)
    exit 0
}

if ($SetDiagnosticLevel) {
    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        Write-Error ("Local config does not exist: {0}" -f $ConfigPath)
        exit 1
    }
    $newConfig = New-CompleteConfig -Base $currentConfig
    if (-not $newConfig.case_id -or -not $newConfig.known_true_addr) {
        Write-Error "Existing config is missing case_id or known_true_addr; use -Set first."
        exit 1
    }
    $newConfig.diagnostic_level = $SetDiagnosticLevel
    Write-CaseConfig -Config $newConfig
    Write-Output ("Updated diagnostic_level to {0}" -f $SetDiagnosticLevel)
    Write-Output ("Backup path: {0}" -f $BackupPath)
    Write-ConfigSummaryOutput -Config (Read-CaseConfig -Path $ConfigPath) -UseMarkdown ([bool]$Markdown)
    exit 0
}
