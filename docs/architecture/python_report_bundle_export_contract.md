# Python Report Bundle Export Contract

## Purpose

This contract defines the controlled write boundary for future Python report bundle export support in `D:\armedforces.io-v2`.

Phase 3.24 wrote the contract. Phase 3.25 implements dry-run planning only. Phase 3.26 final smoke passed for the dry-run boundary. It does not implement real bundle export or add write-capable behavior.

## Current Baseline

Current Python report tooling state:

- `report bundle preview` and `report bundle verify` are implemented and read-only.
- `report export` is the only write-capable Python command.
- `writes_files_count = 1`.
- `runs_ce_count = 0`.
- no CE/runtime mutation exists in Python tooling.
- bundle export dry-run planning is implemented.
- Phase 3.26 dry-run boundary final smoke passed.
- checkpoint tag: `python-report-bundle-export-dry-run-checkpoint-20260616`.
- real bundle export is not implemented.
- there is no runtime bundle output.

## Proposed Write Behavior

Future commands only:

```powershell
python -m armedforces_tool report bundle export --dry-run
python -m armedforces_tool report bundle export --out reports/python_tooling/bundles/<bundle_id>/
python -m armedforces_tool report bundle export --zip --out reports/python_tooling/bundles/<bundle_id>.zip
```

Contract rules:

- dry-run is implemented and must remain no-write.
- real export must go through a separate implementation phase.
- bundle export is a new write-capable surface.
- `report bundle preview` and `report bundle verify` do not authorize export.
- this contract does not change `report export`, manifest writer, or read-only bundle behavior.

## Dry-Run Boundary Status

The implemented dry-run path is limited to path validation and export planning.

Phase 3.26 final smoke confirmed:

- directory dry-run writes nothing
- zip dry-run writes nothing
- JSON dry-run writes nothing
- real bundle export returns `BUNDLE_EXPORT_NOT_IMPLEMENTED`
- no bundle directory is created
- no zip archive is created
- no copied reports are created
- no `bundle_manifest.json` is created
- no `index.md` is created
- no runtime report, runtime manifest, or runtime bundle artifact is created
- no log/config/session/intake/baseline/registry write occurs
- command inventory remains `writes_files_count = 1`
- command inventory remains `runs_ce_count = 0`
- `report export` remains the only write-capable Python command

Real bundle export remains deferred. A future real write phase must still follow the approved bundle root, no-overwrite default, cleanup rules, protected artifact checks, smoke validation, and checkpoint process defined by this contract and the Python write-capable feature policy.

## Approved Output Boundary

First-version planned outputs:

```text
reports/python_tooling/bundles/<bundle_id>/
reports/python_tooling/bundles/<bundle_id>.zip
```

Explicitly forbidden outputs:

- `log/`
- `src/`
- `tests/`
- `docs/codex_tasks/`
- `docs/reports/`
- `src/run_case_config.local.lua`
- registry files
- baseline files
- session files
- intake journal files
- local config files
- any path outside the approved bundle root
- traversal paths

Mutation of `reports/python_tooling/manifest.jsonl` is forbidden unless a future contract explicitly defines manifest write behavior. Bundle export may read this manifest, but this contract does not authorize mutating it.

## Bundle Directory Format

Planned directory output:

```text
reports/python_tooling/bundles/<bundle_id>/
|-- bundle_manifest.json
|-- index.md
`-- reports/
    `-- <copied report files>
```

Rules:

- copied reports must come only from approved manifest references.
- `bundle_manifest.json` is bundle state, not report manifest state.
- `index.md` is a generated summary, not the source of truth.
- source report files must not be deleted.
- source manifest must not be mutated.
- bundle writes must be staged in a temporary output and finalized only after verification succeeds.

## Bundle Zip Format

Planned zip output:

- `<bundle_id>.zip`
- contains `bundle_manifest.json`
- contains `index.md`
- contains copied report files under `reports/`
- zip creation must be atomic or use a temporary path plus final rename
- failed zip creation must not leave a partial archive at the final output path

## Bundle Manifest Data Model

Planned `bundle_manifest.json` fields:

- `schema_version`
- `bundle_id`
- `created_at`
- `bundle_type`
- `source_manifest_path`
- `included_reports`
- `included_manifest_entries`
- `output_path`
- `output_root`
- `file_count`
- `total_size`
- `per_file_hashes`
- `command`
- `status`

Planned `included_reports` fields:

- `report_id`
- `report_type`
- `source_path`
- `bundle_path`
- `file_size`
- `sha256`

## Input Rules

Bundle export input must come from:

- `reports/python_tooling/manifest.jsonl`
- `reports/python_tooling/*.md` files referenced by the manifest

Forbidden runtime reads:

- `log/`
- `src/`
- `tests/`
- `docs/codex_tasks/`
- `docs/reports/`
- local config files
- session files
- intake journal files
- registry files
- baseline files
- traversal paths

## Write Ordering

Future implementation must use this order:

1. validate output path
2. validate source manifest path
3. parse manifest
4. verify referenced report files
5. prepare bundle plan
6. create temporary bundle output
7. copy report files
8. write `bundle_manifest.json`
9. write `index.md`
10. verify hashes and file count
11. finalize rename/move to final output

Failure rules:

- invalid input -> no write
- missing referenced report -> no write
- corrupt manifest -> no write
- output already exists -> reject by default
- `--force` behavior must be defined separately and must not be enabled by default

## Dry-Run Semantics

Implemented dry-run displays:

- `would_create_bundle=true`
- planned output path
- planned files
- planned `bundle_manifest` fields
- source manifest path
- bundle type
- write safety status

Dry-run must not:

- create directories
- create zip archives
- copy files
- write `bundle_manifest.json`
- write `index.md`
- write `reports/`
- write `docs/reports/`
- write log/config/state files

## Overwrite / Force Rules

Planned rules:

- existing output is rejected by default.
- future `--force`, if allowed, may only work inside the approved bundle root.
- `--force` must not delete source reports.
- `--force` must not modify source manifest.
- `--force` must only replace the target bundle artifact.
- `--force` requires separate tests and smoke validation.

## Failure Handling

Future implementation must explicitly handle:

- no manifest
- corrupt manifest
- missing referenced report
- duplicate `bundle_id`
- output directory exists
- output zip exists
- partial bundle directory
- partial zip
- hash mismatch after copy
- index generation failed
- `bundle_manifest.json` write failed
- cleanup rollback failed

Required posture:

- fail closed
- no silent success
- operator-visible status
- explicit cleanup rules
- no deletion of pre-existing user files
- partial artifacts must be distinguishable from pre-existing user artifacts

## Command Inventory Impact

Current dry-run inventory impact:

- `report bundle export --dry-run` is read-only.
- `writes_files_count` remains `1`.
- `runs_ce_count` must remain `0`.
- `report bundle preview` and `report bundle verify` remain read-only.
- `report export` remains write-capable.
- real bundle export, if implemented later as a new command, would be a new write-capable command.
- `writes_files_count` would increase from `1` to `2` if real bundle export is implemented as a new command.
- command inventory must clearly show real bundle export risk level is not `READ_ONLY`.

## Required Tests For Future Implementation

Future tests must cover:

- dry-run writes nothing
- real directory bundle writes only under approved root
- real zip bundle writes only under approved root
- no manifest -> no write
- corrupt manifest -> no write
- missing report -> no write
- bad output path rejected
- traversal rejected
- protected paths rejected
- output exists rejected by default
- `--force` behavior if implemented
- copied report hashes match
- `bundle_manifest.json` has required fields
- `index.md` generated
- source reports are not deleted
- source manifest unchanged
- command inventory flags correct
- `runs_ce_count` remains `0`
- no log/config/session/intake/baseline/registry writes

## Required Smoke Validation For Future Implementation

Future smoke must include:

- pre-smoke git status clean
- protected artifact snapshot
- dry-run no-write
- real directory or zip smoke under approved bundle root
- verify bundle contents
- cleanup only smoke-created bundle artifact
- post-cleanup no runtime bundle remains
- pytest
- git diff/status clean

## Cleanup Policy

Cleanup rules:

- smoke-created bundle directory may be deleted only if created by smoke
- smoke-created zip may be deleted only if created by smoke
- never delete pre-existing bundle directory/zip
- never delete `reports/python_tooling/manifest.jsonl`
- never delete source reports
- never delete `reports/python_tooling/`
- cleanup failures must be reported, not hidden

## Explicit Non-Goals

This contract does not authorize:

- implementing real bundle export
- creating bundle directories
- creating zip archives
- writing `bundle_manifest.json`
- writing `index.md`
- modifying `report export`
- modifying manifest writer
- writing `docs/reports`
- writing log/config/session/intake/baseline/registry
- running CE
- modifying PowerShell behavior
- modifying Lua behavior
- modifying runtime behavior
- modifying filtering, ranking, scoring, thresholds, quota, or stable intersection behavior
