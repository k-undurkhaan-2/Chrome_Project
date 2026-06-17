# Python Tooling Operator Guide

## Purpose

This is the operator entry point for Python tooling in `D:\armedforces.io-v2`.

For the full Phase 3 usage guide, use:

- `docs/python_tooling_phase3_usage_guide.md`

For the current Phase 3 architecture summary, use:

- `docs/architecture/python_tooling_phase3_summary.md`

For the Phase 4 roadmap, use:

- `docs/architecture/python_tooling_phase4_plan.md`

## Current Stable Boundary

Phase 3 is closed at checkpoint:

- `python-tooling-phase3-final-checkpoint-20260616`

Current command inventory:

- commands: about `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable commands:
  - `report export`
  - `report bundle export`

Report manifest commands remain read-only:

- `report manifest preview`
- `report manifest list`
- `report manifest verify`

Report bundle read-only commands remain read-only:

- `report bundle preview`
- `report bundle verify`

`report bundle export --dry-run` remains no-write.

Unsupported / deferred:

- zip bundle export
- bundle `--force` / overwrite
- `docs/reports` bundle output
- CE/runtime mutation
- PowerShell mutation replacement

## Daily Safe Checks

Use these first:

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"

.venv\Scripts\python.exe -m armedforces_tool status overview
.venv\Scripts\python.exe -m armedforces_tool commands list
.venv\Scripts\python.exe -m armedforces_tool commands list --category report
.venv\Scripts\python.exe -m armedforces_tool report manifest verify
.venv\Scripts\python.exe -m armedforces_tool report bundle verify
```

Expected stable results:

- `status overview = SAFE`
- report inventory shows `report export` and `report bundle export` as the only write-capable commands
- `writes_files_count = 2`
- `runs_ce_count = 0`
- `report manifest verify` may return `NO_MANIFEST` when no runtime manifest exists
- `report bundle verify` may return `NO_MANIFEST` when no runtime manifest exists

## Safe Report Workflow

Use the detailed workflow in `docs/python_tooling_phase3_usage_guide.md`.

Short form:

```powershell
.venv\Scripts\python.exe -m armedforces_tool report preview --type full-status
.venv\Scripts\python.exe -m armedforces_tool report export --dry-run --type full-status --out reports/python_tooling/full_status.md
.venv\Scripts\python.exe -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md
.venv\Scripts\python.exe -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md --record-manifest
.venv\Scripts\python.exe -m armedforces_tool report manifest verify
.venv\Scripts\python.exe -m armedforces_tool report manifest list
```

Use dry-run before real export. Clean smoke-created report and manifest artifacts when a validation task requires cleanup.

## Safe Bundle Workflow

Use the detailed workflow in `docs/python_tooling_phase3_usage_guide.md`.

Short form:

```powershell
.venv\Scripts\python.exe -m armedforces_tool report bundle preview
.venv\Scripts\python.exe -m armedforces_tool report bundle verify
.venv\Scripts\python.exe -m armedforces_tool report bundle export --dry-run --out reports/python_tooling/bundles/<bundle_id>/
.venv\Scripts\python.exe -m armedforces_tool report bundle export --out reports/python_tooling/bundles/<bundle_id>/
```

Real bundle export is directory-only and writes only under `reports/python_tooling/bundles/<bundle_id>/`.

## Git Hygiene

Do not commit:

- `log/`
- `reports/` runtime outputs
- `docs/reports/` runtime outputs unless a task explicitly scopes them
- `src/run_case_config.local.lua`
- `src/run_case_config.local.lua.bak`
- `docs/codex_tasks/`

Do not use `git add .`. Stage only the intended files.

Check before and after every task:

```powershell
git status --short
```

## Troubleshooting

- If `python` is not on PATH, use `.venv\Scripts\python.exe`.
- `NO_MANIFEST` from manifest or bundle verify means no runtime manifest currently exists.
- `BUNDLE_ZIP_EXPORT_NOT_IMPLEMENTED` is expected for zip export.
- `OUTPUT_EXISTS` means bundle output already exists and overwrite is unsupported.
- `BAD_PATH` means a protected or traversal path was rejected.
- LF/CRLF warnings from `git diff --check` are acceptable if there is no whitespace error.
