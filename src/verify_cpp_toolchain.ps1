[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Find-VsDevCmd {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path -LiteralPath $vswhere) {
        $found = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find "Common7\Tools\VsDevCmd.bat" 2>$null | Select-Object -First 1
        if ($found) {
            return $found
        }
    }

    return "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"
}

function Import-DeveloperEnvironment {
    param([Parameter(Mandatory = $true)][string]$VsDevCmdPath)

    if (-not (Test-Path -LiteralPath $VsDevCmdPath)) {
        throw "VsDevCmd.bat not found: $VsDevCmdPath"
    }

    $repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
    $logRoot = Join-Path $repoRoot "log"
    if (-not (Test-Path -LiteralPath $logRoot)) {
        New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    }

    $cmdPath = Join-Path $logRoot ("vsdev-env-{0}.cmd" -f ([guid]::NewGuid().ToString("N")))
    try {
        $cmdLines = @(
            "@echo off",
            ('call "{0}" -arch=amd64 -host_arch=amd64 >nul' -f $VsDevCmdPath),
            "if errorlevel 1 exit /b %errorlevel%",
            "set"
        )
        Set-Content -LiteralPath $cmdPath -Value $cmdLines -Encoding ASCII

        $lines = & cmd.exe /d /s /c "`"$cmdPath`""
        if ($LASTEXITCODE -ne 0) {
            throw "VsDevCmd.bat failed with exit code $LASTEXITCODE"
        }

        $importedNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
        foreach ($line in $lines) {
            if ($line -match "^([^=]+)=(.*)$") {
                $name = $matches[1]
                if ($importedNames.Add($name)) {
                    Set-Item -Path "env:$name" -Value $matches[2]
                }
            }
        }
    } finally {
        try {
            if (Test-Path -LiteralPath $cmdPath) {
                Remove-Item -LiteralPath $cmdPath -Force -ErrorAction Stop
            }
        } catch {
            Write-Warning ("Temporary VsDevCmd loader cleanup failed for {0}: {1}" -f $cmdPath, $_.Exception.Message)
        }
    }
}

function Resolve-ToolPath {
    param([Parameter(Mandatory = $true)][string]$Name)

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $paths = & where.exe $Name 2>$null
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0 -or -not $paths) {
        throw "$Name not found in Developer environment PATH"
    }

    foreach ($path in @($paths)) {
        if (Test-Path -LiteralPath $path) {
            return $path
        }
    }

    throw "$Name resolved by where.exe, but no returned path exists"
}

function Add-ProjectPythonToPath {
    $repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
    $venvScripts = Join-Path $repoRoot ".venv\Scripts"
    $venvPython = Join-Path $venvScripts "python.exe"

    if (Test-Path -LiteralPath $venvPython) {
        $env:Path = "$venvScripts;$env:Path"
    }
}

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [switch]$SuppressOutput
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        if ($SuppressOutput) {
            & $FilePath @Arguments *> $null
        } else {
            & $FilePath @Arguments
        }
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "$Label failed with exit code $exitCode"
    }
}

try {
    $vsDevCmd = Find-VsDevCmd
    Write-Output ("VsDevCmd.bat = {0}" -f $vsDevCmd)
    Import-DeveloperEnvironment -VsDevCmdPath $vsDevCmd
    Add-ProjectPythonToPath

    $cl = Resolve-ToolPath -Name "cl.exe"
    Write-Output ("cl.exe = {0}" -f $cl)
    Invoke-NativeChecked -Label "cl.exe" -FilePath $cl -Arguments @("/?") -SuppressOutput

    Write-Output "where.exe cl.exe"
    Invoke-NativeChecked -Label "where.exe cl.exe" -FilePath "where.exe" -Arguments @("cl.exe")

    $cmake = Resolve-ToolPath -Name "cmake.exe"
    Write-Output "cmake --version"
    Invoke-NativeChecked -Label "cmake --version" -FilePath $cmake -Arguments @("--version")

    $ninja = Resolve-ToolPath -Name "ninja.exe"
    Write-Output "ninja --version"
    Invoke-NativeChecked -Label "ninja --version" -FilePath $ninja -Arguments @("--version")

    $python = Resolve-ToolPath -Name "python.exe"
    Write-Output "python --version"
    Invoke-NativeChecked -Label "python --version" -FilePath $python -Arguments @("--version")
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
