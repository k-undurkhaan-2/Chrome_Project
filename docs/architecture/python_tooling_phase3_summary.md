# Python Tooling Phase 3 Current-State Summary

## Purpose

This document summarizes the current Phase 3 Python tooling state for `D:\armedforces.io-v2`.

It records command inventory, read/write boundaries, completed report/manifest/bundle tracks, and deferred work. It is a documentation snapshot only; it does not authorize new behavior.

## Current Command Inventory

Current expected inventory:

- commands: about `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable commands:
  - `report export`
  - `report bundle export`
- all other report, manifest, and bundle commands are read-only or dry-run no-write

## Completed Phase 3 Tracks

### Report Preview

`report preview` renders report content to stdout.

Boundary:

- stdout-only
- read-only
- no runtime report files
- no manifest writes
- no bundle writes
- no CE/runtime mutation

### Report Export

`report export` is write-capable.

Boundary:

- writes approved `.md` report files only
- approved output roots are controlled by the report export contract
- dry-run remains no-write
- bad paths, protected paths, path traversal, and unsupported extensions are rejected
- default behavior does not overwrite existing files

### Report Manifest

Manifest read-only commands:

- `report manifest preview`
- `report manifest list`
- `report manifest verify`

Manifest write boundary:

- `report export --record-manifest` writes through `report export`
- supported runtime manifest path: `reports/python_tooling/manifest.jsonl`
- dry-run remains no-write
- `docs/reports` manifest support remains deferred

### Report Bundle Preview / Verify

Bundle read-only commands:

- `report bundle preview`
- `report bundle verify`

Boundary:

- no bundle directory creation
- no zip creation
- no report copying
- no `bundle_manifest.json`
- no `index.md`
- no report manifest mutation
- no CE/runtime mutation

### Report Bundle Export

`report bundle export` is write-capable as directory-only real export.

Boundary:

- writes only under `reports/python_tooling/bundles/<bundle_id>/`
- creates `bundle_manifest.json` inside the bundle directory
- creates `index.md` inside the bundle directory
- copies referenced reports only into the bundle-local `reports/` directory
- source reports remain unchanged
- source manifest remains unchanged
- dry-run remains no-write
- zip export remains deferred and fail-closed
- `--force` / overwrite remains deferred

## Current Write Boundaries

### `report export`

Allowed where the current report export contract permits:

- `reports/python_tooling/*.md`
- `docs/reports/python_tooling/*.md` only where the existing report export contract allows

### `report export --record-manifest`

Allowed:

- `reports/python_tooling/*.md`
- `reports/python_tooling/manifest.jsonl`

Manifest recording is not supported for `docs/reports/python_tooling/`.

### `report bundle export`

Allowed:

- `reports/python_tooling/bundles/<bundle_id>/`
- `bundle_manifest.json` inside the bundle directory
- `index.md` inside the bundle directory
- `reports/<copied files>` inside the bundle directory only

### Forbidden Write Surfaces

These remain forbidden for Phase 3 Python report tooling:

- `log/`
- registry files
- baseline files
- session files
- intake files
- local config files
- `src/`
- `tests/`
- `docs/codex_tasks/`
- `docs/reports` bundle output
- zip bundle output
- `--force` / overwrite for bundle export

## Current Non-Goals

Phase 3 still does not include:

- CE automation
- runtime write / restore migration
- PowerShell mutation replacement
- Lua/runtime modification
- algorithm rewrite
- zip export
- bundle overwrite / `--force`
- `docs/reports` bundle support

## Operator Daily Checks

Recommended read-only checks:

```powershell
.venv\Scripts\python.exe -m armedforces_tool status overview
.venv\Scripts\python.exe -m armedforces_tool commands list
.venv\Scripts\python.exe -m armedforces_tool commands list --category report
.venv\Scripts\python.exe -m armedforces_tool report manifest verify
.venv\Scripts\python.exe -m armedforces_tool report bundle preview
.venv\Scripts\python.exe -m armedforces_tool report bundle verify
```

## Safe Report Workflow

Recommended report workflow:

```powershell
.venv\Scripts\python.exe -m armedforces_tool report preview --type full-status
.venv\Scripts\python.exe -m armedforces_tool report export --dry-run --type full-status --out reports/python_tooling/full_status.md
.venv\Scripts\python.exe -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md
.venv\Scripts\python.exe -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md --record-manifest
.venv\Scripts\python.exe -m armedforces_tool report manifest verify
.venv\Scripts\python.exe -m armedforces_tool report manifest list
```

Rules:

- use dry-run before real export
- `--record-manifest` records an entry in `reports/python_tooling/manifest.jsonl`
- `report manifest verify` and `report manifest list` are read-only
- smoke-created reports or manifests must be cleaned when the task requires cleanup

## Safe Bundle Workflow

Recommended bundle workflow:

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
- smoke-created bundle outputs must be cleaned by the operator after validation
- source reports and source manifest must remain unchanged
- zip export remains unsupported
- `--force` / overwrite remains unsupported

## Deferred Future Work

Deferred work:

- zip bundle export contract/refinement
- `--force` / overwrite contract
- `docs/reports` bundle support planning
- bundle index / compaction planning
- optional report bundle current-state final smoke
- Phase 3 final checkpoint package
