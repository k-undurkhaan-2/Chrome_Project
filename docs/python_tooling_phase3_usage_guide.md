# Python Tooling Phase 3 Usage Guide

## Purpose

This is the operator usage guide after Phase 3 completion. It is not a development plan.

Use it for daily checks, report workflows, bundle workflows, troubleshooting, and Git hygiene for the completed Phase 3 Python tooling surface.

## Current Stable Baseline

Phase 3 final checkpoint:

- `python-tooling-phase3-final-checkpoint-20260616`

Current command inventory:

- commands: about `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable commands:
  - `report export`
  - `report bundle export`

## Daily Safe Status Checks

Run:

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
- report inventory has `writes_files_count = 2`
- report inventory has `runs_ce_count = 0`
- write-capable commands are `report export` and `report bundle export`
- `report manifest verify` may return `NO_MANIFEST` when no runtime manifest exists
- `report bundle verify` may return `NO_MANIFEST` when no runtime manifest exists

## Read-Only Commands

These commands are read-only:

- `report preview`
- `report manifest preview`
- `report manifest list`
- `report manifest verify`
- `report bundle preview`
- `report bundle verify`
- `commands list`
- `status overview`

Read-only means:

- no CE run
- no report write
- no manifest write
- no bundle write
- no log/config/session/intake/baseline/registry write

## Dry-Run No-Write Commands

These commands are dry-run / no-write:

- `report export --dry-run`
- `report export --dry-run --record-manifest`
- `report bundle export --dry-run`

Dry-run means:

- validates or previews paths and metadata
- writes no report files
- writes no manifest files
- creates no bundle directory
- creates no `bundle_manifest.json`
- creates no `index.md`
- copies no reports

## Write-Capable Commands

The current write-capable Python commands are only:

- `report export`
- `report bundle export`

### `report export`

Allowed write boundaries:

- approved `.md` report files under `reports/python_tooling/`
- approved `.md` report files under `docs/reports/python_tooling/` where the report export contract permits

Rejected:

- protected paths such as `log/`, `src/`, `tests/`, and `docs/codex_tasks/`
- path traversal
- non-`.md` output
- existing files unless the report export contract explicitly permits `--force`

### `report export --record-manifest`

Allowed write boundaries:

- report output under `reports/python_tooling/*.md`
- append-only `reports/python_tooling/manifest.jsonl`

Rejected:

- `docs/reports/python_tooling/` with `--record-manifest`
- protected paths
- traversal paths

### `report bundle export`

Allowed write boundaries:

- `reports/python_tooling/bundles/<bundle_id>/`
- `bundle_manifest.json` inside that bundle directory
- `index.md` inside that bundle directory
- copied report files under the bundle-local `reports/` directory

Rejected / deferred:

- zip output
- existing bundle output
- `--force` / overwrite
- `docs/reports` bundle output
- source report mutation
- source manifest mutation

## Safe Report Workflow

Use this sequence:

```powershell
.venv\Scripts\python.exe -m armedforces_tool report preview --type full-status
.venv\Scripts\python.exe -m armedforces_tool report export --dry-run --type full-status --out reports/python_tooling/full_status.md
.venv\Scripts\python.exe -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md
.venv\Scripts\python.exe -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md --record-manifest
.venv\Scripts\python.exe -m armedforces_tool report manifest verify
.venv\Scripts\python.exe -m armedforces_tool report manifest list
```

Rules:

- run dry-run before real export
- use `--record-manifest` only when you need a runtime report manifest entry
- `report manifest verify` and `report manifest list` are read-only
- clean smoke-created report and manifest artifacts when a validation task requires cleanup

## Safe Bundle Workflow

Use this sequence:

```powershell
.venv\Scripts\python.exe -m armedforces_tool report bundle preview
.venv\Scripts\python.exe -m armedforces_tool report bundle verify
.venv\Scripts\python.exe -m armedforces_tool report bundle export --dry-run --out reports/python_tooling/bundles/<bundle_id>/
.venv\Scripts\python.exe -m armedforces_tool report bundle export --out reports/python_tooling/bundles/<bundle_id>/
```

Rules:

- preview and verify are read-only
- dry-run writes nothing
- real bundle export writes only under `reports/python_tooling/bundles/<bundle_id>/`
- real bundle export creates `bundle_manifest.json`, `index.md`, and copied reports only inside the bundle directory
- source reports and source manifest must remain unchanged
- clean smoke-created bundle artifacts when a validation task requires cleanup

## Forbidden / High-Risk Actions

Do not run these unless a task explicitly scopes them:

- CE
- runtime write / restore
- `baseline-save`
- `safe-reset`
- `set-diagnostic`
- `prepare-current-case`
- `collect-prepare`
- `case-intake-abandon`

Python tooling must not write:

- `log/`
- registry files
- baseline files
- session files
- intake files
- local config files

## Unsupported / Deferred Features

Deferred features:

- zip bundle export
- `--force` / overwrite for bundle export
- `docs/reports` bundle output
- CE/native runtime mutation
- PowerShell mutation replacement

## Read-Only PowerShell Wrapper

A read-only PowerShell thin wrapper is available for the safest daily status checks.

The wrapper is checkpointed at:

```text
python-tooling-powershell-wrapper-readonly-checkpoint-20260616
```

Recommended wrapper invocation uses `ExecutionPolicy Bypass`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 inventory
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 report-status
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 manifest-verify
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 bundle-verify
```

Direct `.\src\python_tooling_wrapper.ps1 ...` execution may be blocked by local PowerShell `ExecutionPolicy`. Use the command shape above; do not change system policy for the project.

The wrapper is read-only and exposes only the commands above. It does not wrap report export, manifest recording, bundle export dry-run, real bundle export, CE operations, write / restore operations, local config mutation, or session/intake mutation.

Write-capable commands remain direct Python commands only and must not be wrapped yet.

Direct Python usage remains valid:

```powershell
.venv\Scripts\python.exe -m armedforces_tool status overview
.venv\Scripts\python.exe -m armedforces_tool report preview --type full-status
.venv\Scripts\python.exe -m armedforces_tool report manifest verify
.venv\Scripts\python.exe -m armedforces_tool report bundle verify
```

## Troubleshooting

### Python Not On PATH

Use:

```powershell
.venv\Scripts\python.exe -m armedforces_tool status overview
```

### `NO_MANIFEST`

`NO_MANIFEST` from manifest or bundle verify means no runtime manifest currently exists under the approved report roots. This is normal after smoke cleanup.

### `BUNDLE_ZIP_EXPORT_NOT_IMPLEMENTED`

This is expected. Zip export is deferred and fail-closed.

### `OUTPUT_EXISTS`

The bundle output already exists. Bundle overwrite is unsupported; choose a new bundle ID.

### `BAD_PATH`

A protected or traversal path was rejected. Use only approved output roots.

### LF / CRLF Warnings

`git diff --check` may print LF/CRLF warnings on Windows. These are acceptable if there is no whitespace error.

## Git Hygiene

Rules:

- never use `git add .`
- commit only intended docs/source/test files
- do not commit `docs/codex_tasks/`
- do not commit `reports/`
- do not commit `log/`
- do not commit local config

Check before and after every task:

```powershell
git status --short
```
