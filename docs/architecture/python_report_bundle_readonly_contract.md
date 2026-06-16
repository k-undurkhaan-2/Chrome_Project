# Python Report Bundle Read-Only Contract

## Purpose

This contract defines the boundary for future Python report bundle read-only preview / verify commands in `D:\armedforces.io-v2`.

Phase 3.20 wrote the contract. Phase 3.21 implements the read-only bundle preview / verify commands. It does not implement bundle export or any write-capable bundle behavior.

## Current Baseline

Current Python report tooling state:

- report bundle read-only preview / verify are implemented.
- `report export` is the only write-capable Python command.
- `report manifest preview`, `report manifest list`, and `report manifest verify` are read-only.
- `report bundle preview` and `report bundle verify` are read-only.
- `writes_files_count = 1`.
- `runs_ce_count = 0`.
- no CE or runtime mutation exists in Python tooling.
- no bundle output exists.

## Read-Only Command Shape

Implemented read-only commands:

```powershell
python -m armedforces_tool report bundle preview
python -m armedforces_tool report bundle verify
```

Optional future parameters:

- `--manifest reports/python_tooling/manifest.jsonl`
- `--json`
- `--limit N`

These commands are status/preview commands only. They do not create a bundle directory, copy reports, write a bundle manifest, or create a zip archive.

## Read-Only Guarantees

Read-only bundle commands must not:

- create a bundle directory
- create a zip archive
- copy report files
- write a bundle manifest
- write a report manifest
- write `reports/`
- write `docs/reports/`
- write log/config/session/intake/baseline/registry files
- call `report export`
- run CE

The commands may only read approved manifest and report inputs and print derived output.

## Input Discovery

Default input:

```text
reports/python_tooling/manifest.jsonl
```

Preview / verify may:

- inspect manifest entries
- verify referenced report files exist
- compute read-only planned bundle shape
- compute per-file hashes by reading files only
- filter candidate reports by report type, bundle type, or limit

Input discovery must not create missing files or directories.

## Path Safety

Allowed runtime inputs:

- `reports/python_tooling/manifest.jsonl`
- `reports/python_tooling/*.md` files referenced by the manifest

Forbidden runtime inputs:

- `log/`
- `src/`
- `tests/` as runtime input
- `docs/codex_tasks/`
- local config files
- session files
- intake journal files
- registry files
- baseline files
- `docs/reports/` unless a future contract explicitly allows it

Path traversal must be rejected.

## Preview Output Model

Planned preview output fields:

- `status`
- `source_manifest_path`
- `manifest_entry_count`
- `candidate_report_count`
- `missing_report_count`
- `planned_bundle_id`
- `planned_bundle_root`
- `planned_bundle_files`
- `planned_bundle_manifest`
- `would_write_bundle=false`
- `writes_files=false`

Preview output is advisory only. It must not write files.

## Verify Output Model

Planned verify output fields:

- `status`
- `source_manifest_path`
- `manifest_valid`
- `referenced_reports_checked`
- `missing_reports`
- `duplicate_report_ids`
- `invalid_entries`
- `bundle_ready`
- `writes_files=false`

Verify output should explain why a bundle is not ready without creating a bundle.

## Status Values

Planned statuses:

- `OK`
- `NO_MANIFEST`
- `INVALID_MANIFEST`
- `MISSING_REPORTS`
- `BAD_PATH`
- `UNSUPPORTED_FORMAT`
- `NOT_READY`

## Command Inventory Expectations

Implementation expectations:

- total command count may increase
- `report bundle preview` must be `read_only=true`
- `report bundle verify` must be `read_only=true`
- `writes_files=false`
- `runs_ce=false`
- `risk_level=READ_ONLY`
- `writes_files_count` must remain `1`
- `runs_ce_count` must remain `0`
- only `report export` remains write-capable

## Tests Required

Tests should cover:

- no manifest -> `NO_MANIFEST`
- valid manifest + referenced reports -> `OK`
- valid manifest + missing report -> `MISSING_REPORTS`
- corrupt manifest -> `INVALID_MANIFEST`
- bad path rejected
- traversal rejected
- protected paths rejected
- preview writes nothing
- verify writes nothing
- no bundle directory created
- no zip created
- command inventory flags are read-only
- `writes_files_count` remains `1`
- `runs_ce_count` remains `0`
- no CE/runtime/log/config/session/intake/baseline/registry writes

Tests should use fixtures or temporary directories and must not write runtime report, manifest, or bundle files.

## Explicit Non-Goals

This contract does not authorize:

- implementing bundle export
- creating a bundle directory
- creating a zip archive
- writing `bundle_manifest.json`
- writing `index.md`
- modifying `report export`
- modifying the manifest writer
- writing `docs/reports`
- writing log/config/session/intake/baseline/registry
- running CE
- modifying PowerShell behavior
- modifying Lua behavior
- modifying runtime behavior
- modifying filtering, ranking, scoring, thresholds, quota, or stable intersection behavior
