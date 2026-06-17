# Python Report Bundle Plan

## Purpose

This document plans future Python report bundle / report package support for `D:\armedforces.io-v2`.

A report bundle would package or archive Python tooling report outputs, related manifest entries, and a compact index into a single operator-facing artifact. Planning is complete and read-only preview / verify support is implemented. Bundle export remains deferred and no new write-capable behavior is authorized.

## Current Baseline

Current Python report tooling state:

- `report export` is implemented.
- `report export --record-manifest` is implemented.
- `report bundle preview` and `report bundle verify` are implemented as read-only commands.
- Phase 3.22 read-only boundary final smoke passed.
- first-version manifest path: `reports/python_tooling/manifest.jsonl`.
- `report export` is the only write-capable Python command.
- `writes_files_count = 1`.
- `runs_ce_count = 0`.
- no CE or runtime mutation exists in Python tooling.
- no writes to `log/`, config, session, intake, baseline, or registry files are authorized by report tooling.
- no bundle directory, zip, copied report, `bundle_manifest.json`, or `index.md` is implemented.

## Why Bundle Needs Separate Planning

A bundle would introduce a new output shape beyond a single Markdown report or append-only report manifest entry.

Candidate bundle artifacts could include:

- a bundle directory
- a zip archive
- a bundle manifest
- copied report files
- a summary index

These are new write boundaries. They must not reuse the existing report export manifest boundary. The current `report export --record-manifest` contract authorizes only one report file under `reports/python_tooling/` plus `reports/python_tooling/manifest.jsonl`; it does not authorize bundle directories, zip archives, copied reports, or bundle indexes.

## Candidate Bundle Outputs

Candidate outputs for a future contract:

- `reports/python_tooling/bundles/<bundle_id>/`
- `reports/python_tooling/bundles/<bundle_id>.zip`
- `reports/python_tooling/bundles/<bundle_id>/bundle_manifest.json`
- `reports/python_tooling/bundles/<bundle_id>/index.md`

These candidate outputs remain unimplemented after the read-only boundary. They are listed only to define the future write surface that still requires a separate contract.

Explicitly forbidden unless a future contract narrowly allows them:

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

## Bundle Data Model

A future bundle manifest should use an explicit schema.

Candidate fields:

- `schema_version`
- `bundle_id`
- `created_at`
- `bundle_type`
- `included_reports`
- `included_manifest_entries`
- `source_manifest_path`
- `output_path`
- `output_root`
- `file_count`
- `total_size`
- `sha256` or per-file hashes
- `command`
- `status`

Candidate `included_reports` fields:

- `report_id`
- `report_type`
- `source_path`
- `bundle_path`
- `file_size`
- `sha256`

## Read-Only First Strategy

The first implementation starts with read-only bundle preview and verification.

Read-only bundle preview:

- previews what would be bundled
- inspects existing manifest entries
- validates referenced report files
- shows missing or invalid report references
- writes nothing
- creates no zip archive
- creates no directory

Read-only bundle verification checks runtime manifest readiness for a future bundle and still writes nothing. Existing bundle candidate verification can be added later only after a write contract defines their format.

## Read-Only Contract Status

`docs/architecture/python_report_bundle_readonly_contract.md` defines the future boundary for read-only bundle preview / verify commands.

The contract documents:

- proposed read-only command shape
- input discovery from `reports/python_tooling/manifest.jsonl`
- path safety for referenced report files
- preview and verify output models
- planned status values
- command inventory expectations
- future test requirements

Read-only bundle preview / verify are implemented. Bundle write/export still requires a separate write-capable contract before any dry-run or real write behavior is implemented.

The read-only boundary final smoke confirmed that preview / verify returned clear status, rejected bad manifest paths, kept command inventory at `writes_files_count = 1` and `runs_ce_count = 0`, and created no runtime report, manifest, or bundle artifacts.

`docs/architecture/python_report_bundle_export_contract.md` now defines the future write boundary for bundle export. It does not implement bundle export, enable a bundle write surface, or change preview / verify behavior.

## Proposed Future Command Shape

Possible future commands only:

```powershell
python -m armedforces_tool report bundle preview
python -m armedforces_tool report bundle verify
python -m armedforces_tool report bundle export --dry-run
python -m armedforces_tool report bundle export --out reports/python_tooling/bundles/<bundle_id>/
python -m armedforces_tool report bundle export --zip --out reports/python_tooling/bundles/<bundle_id>.zip
```

Only `report bundle preview` and `report bundle verify` are implemented. Bundle export commands remain unimplemented and unauthorized.

## Safety Model

Bundle export is a new write-capable surface.

Required safety rules for any future bundle write:

- follow the bundle write contract before implementation
- dry-run first
- explicit approved bundle root
- path traversal rejection
- protected path rejection
- default no overwrite
- no writes to `log/`, config, session, intake, baseline, or registry files
- no CE run
- no runtime mutation
- no deletion of user reports
- no deletion of pre-existing user bundles
- cleanup only smoke-created bundle artifacts
- command inventory must mark bundle export as write-capable if implemented

The existing report manifest contract does not authorize bundle writes.

## Failure Handling

A future bundle implementation must define behavior for:

- missing referenced report
- corrupt source manifest
- duplicate `bundle_id`
- output directory already exists
- zip output already exists
- zip creation failure
- partial bundle directory
- partial zip archive
- hash mismatch
- cleanup / rollback strategy

Recommended failure posture:

- fail closed before writing when source manifest or report references are invalid
- return explicit partial-success status if a later bundle step fails
- never delete pre-existing user files during cleanup
- provide a read-only verification path before any repair behavior

## Recommended Implementation Order

Recommended order:

1. bundle planning doc
2. bundle read-only preview/verify contract
3. bundle read-only preview implementation
4. bundle write contract
5. bundle dry-run implementation
6. bundle real write implementation
7. guarded smoke/checkpoint
8. operator docs wrap-up

## Explicit Non-Goals

This phase does not:

- implement bundle export
- write bundle files, directories, or zip archives
- modify `report export`
- modify the manifest writer
- write `docs/reports`
- write log/config/session/intake/baseline/registry
- run CE
- modify PowerShell behavior
- modify Lua behavior
- modify runtime behavior
- modify filtering, ranking, scoring, thresholds, quota, or stable intersection behavior
