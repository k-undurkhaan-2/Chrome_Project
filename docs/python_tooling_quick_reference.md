# Python Tooling Quick Reference

## Purpose

This is the Python tooling operator quick reference / troubleshooting entry point.

Use it before running tooling commands to quickly confirm:

- safe commands
- wrapper usage
- common status meanings
- troubleshooting steps
- stop conditions

## Current Baseline

Current checkpoints:

- `python-tooling-phase3-final-checkpoint-20260616`
- `python-tooling-powershell-wrapper-readonly-checkpoint-20260616`

Current command inventory:

- commands: about `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable commands:
  - `report export`
  - `report bundle export`
- read-only wrapper commands:
  - `status`
  - `inventory`
  - `report-status`
  - `manifest-verify`
  - `bundle-verify`

## Daily Pre-Check

Minimum safe daily pre-check flow:

```powershell
cd D:\armedforces.io-v2

git status --short

$env:PYTHONPATH="D:\armedforces.io-v2\src"
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 inventory
```

Ideal result:

- `git status` is clean
- `overall_status = SAFE`
- `writes_files_count = 2`
- `runs_ce_count = 0`

## Read-Only Wrapper Commands

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 inventory
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 report-status
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 manifest-verify
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 bundle-verify
```

The wrapper is a read-only thin bridge.

The wrapper:

- does not run CE
- does not write report / manifest / bundle / log / config / state
- does not wrap `report export`
- does not wrap `report bundle export`

## Direct Python Read-Only Commands

```powershell
.venv\Scripts\python.exe -m armedforces_tool status overview
.venv\Scripts\python.exe -m armedforces_tool commands list --category report
.venv\Scripts\python.exe -m armedforces_tool report manifest verify
.venv\Scripts\python.exe -m armedforces_tool report bundle verify
.venv\Scripts\python.exe -m armedforces_tool report preview --type full-status
```

Direct Python usage remains valid. The wrapper is convenience only. Direct Python read-only commands remain the source of truth.

## Write-Capable Commands Boundary

Current write-capable Python commands:

- `report export`
- `report bundle export`

These commands:

- must not be invoked through the wrapper
- must not be executed during docs-only or read-only smoke tasks
- require a separate task, explicit output path, safety boundary, and validation before use

Report/bundle UX polish planning exists in `docs/architecture/python_tooling_report_bundle_ux_plan.md`. Current daily workflow is unchanged. `report export` and `report bundle export` remain write-capable direct Python commands only.

Report/bundle UX contract exists in `docs/architecture/python_tooling_report_bundle_ux_contract.md`. Current daily workflow is unchanged. Export commands remain write-capable direct Python commands only.

Phase 5.5 help text polish is available through:

```powershell
.venv\Scripts\python.exe -m armedforces_tool report export --help
.venv\Scripts\python.exe -m armedforces_tool report bundle export --help
```

These help pages now call out the write-capable boundary, no-write `--dry-run` meaning, approved roots, wrapper exclusion, and CE exclusion. Daily workflow and command behavior are unchanged.

The output wording contract exists in `docs/architecture/python_tooling_report_bundle_output_wording_contract.md`. It defines future dry-run, real-write, and rejection wording requirements only. Current command behavior and daily workflow remain unchanged.

Phase 5.7 added output wording helpers for future UX integration. They do not change current commands, do not run during export yet, and do not alter the daily workflow.

The dry-run output integration contract exists in `docs/architecture/python_tooling_dry_run_output_integration_contract.md`. Current command behavior and daily workflow remain unchanged.

Dry-run output for `report export --dry-run` and `report bundle export --dry-run` now has clearer wording and stable no-write tokens. Daily workflow remains unchanged. Real export remains write-capable and direct-Python only.

## Common Status Meanings

### `SAFE`

`SAFE` is the current Python tooling safety status from `status overview`.

It does not mean all write-capable commands are safe to run casually. It only means `status overview` found no current tooling safety issue.

### `NO_MANIFEST`

`NO_MANIFEST` is a read-only informational result for manifest / bundle verify when no runtime manifest exists.

It must not automatically create a manifest and should not be treated as a runtime failure.

### `BAD_PATH`

`BAD_PATH` means a protected path or unapproved output path was rejected.

Stop and inspect the path. Do not bypass the path guard.

### `writes_files_count`

`writes_files_count` is the number of commands in command inventory that can write files.

Current expected value: `2`.

### `runs_ce_count`

`runs_ce_count` is the number of commands in command inventory that can run CE.

Current expected value: `0`.

## PowerShell ExecutionPolicy Troubleshooting

Direct execution such as:

```powershell
.\src\python_tooling_wrapper.ps1 status
```

may be blocked by local PowerShell `ExecutionPolicy`.

This is local machine policy behavior, not wrapper failure. Operators do not need to modify system `ExecutionPolicy`.

Recommended invocation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 status
```

If `Bypass` still fails, check:

- current directory is `D:\armedforces.io-v2`
- `src/python_tooling_wrapper.ps1` exists
- `.venv\Scripts\python.exe` exists
- `PYTHONPATH` is set
- path quoting is correct, especially for paths with spaces

## Missing Python / Venv Troubleshooting

Check:

- `.venv\Scripts\python.exe` exists
- `PYTHONPATH` includes `D:\armedforces.io-v2\src`
- `armedforces_tool` can be imported
- current directory is the repo root

System Python should not be used as the default fallback for wrapper operations.

## Git Hygiene

Safe Git workflow:

```bash
git status --short
git add <explicit file list>
git diff --cached --name-only
git commit -m "<message>"
git push
```

Do not use:

```bash
git add .
```

Do not commit:

```text
docs/codex_tasks/
reports/
docs/reports/
.venv/
.tmp_pytest/
__pycache__/
.pytest_cache/
log/
src/run_case_config.local.lua
src/run_case_config.local.lua.bak
```

## Stop Conditions

Stop if:

- `git status` shows unexpected source/runtime/log/report/config files
- `writes_files_count` is not `2`
- `runs_ce_count` is not `0`
- wrapper starts accepting forbidden commands
- manifest / bundle verify creates a file
- report-status creates a report file
- any command requires CE
- any command requires real export / bundle export
- any protected path is requested to be bypassed

## Wrapper Boundary Tests

Read-only wrapper regression coverage is available through pytest:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_python_tooling_wrapper_readonly.py --basetemp .tmp_pytest
```

These tests validate the read-only wrapper boundary only. Daily operator workflow is unchanged.

## Quick Decision Table

| Need | Use command | Writes files? | Runs CE? | Safe for daily read-only? | Notes |
| --- | --- | --- | --- | --- | --- |
| Check overall status | `python_tooling_wrapper.ps1 status` | no | no | yes | Use `ExecutionPolicy Bypass -File`. |
| Check command inventory | `python_tooling_wrapper.ps1 inventory` | no | no | yes | Confirm `writes_files_count=2`, `runs_ce_count=0`. |
| Preview full status | `python_tooling_wrapper.ps1 report-status` | no | no | yes | Stdout-only status preview. |
| Verify manifest | `python_tooling_wrapper.ps1 manifest-verify` | no | no | yes | `NO_MANIFEST` is informational. |
| Verify bundle | `python_tooling_wrapper.ps1 bundle-verify` | no | no | yes | `NO_MANIFEST` is informational. |
| Export report | `.venv\Scripts\python.exe -m armedforces_tool report export ...` | yes | no | no | Requires explicit scoped task and output path. |
| Export bundle | `.venv\Scripts\python.exe -m armedforces_tool report bundle export ...` | yes | no | no | Requires explicit scoped task and cleanup boundary. |
| Run CE | not supported by Python tooling | no | yes | no | Not part of Python tooling. |
| Reset / restore / runtime mutation | legacy PowerShell workflow only | yes | possible | no | Not migrated into Python tooling. |

## Real-Write Output Contract

The real-write output wording contract exists in `docs/architecture/python_tooling_real_write_output_contract.md`.

Current behavior is unchanged:

- real export remains write-capable direct Python only
- the read-only wrapper still does not support export
- dry-run wording is already handled separately
- real-write output wording implementation is deferred

## Known Non-Goals

This quick reference does not authorize:

- write-capable wrapper
- CE automation
- runtime write/restore migration
- report/bundle export UX changes
- tests hardening
- modifying existing PowerShell mutation workflow
