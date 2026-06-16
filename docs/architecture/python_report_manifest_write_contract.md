# Python Report Manifest Write Contract

## Purpose

This contract defines the safety boundary for future Python report manifest writing in `D:\armedforces.io-v2`.

Phase 3.14 only wrote the contract. Phase 3.15 implements dry-run planning for `--record-manifest`. Real manifest writing is still not implemented, `report export` behavior without `--record-manifest` is unchanged, and no write-capable command is added.

## Current Baseline

Current Python tooling state:

- `report export` is the only write-capable Python command.
- `report manifest preview`, `report manifest list`, and `report manifest verify` are read-only.
- `writes_files_count = 1`.
- `runs_ce_count = 0`.
- there is currently no runtime manifest write.
- no CE or runtime mutation exists in Python tooling.
- `report export --dry-run --record-manifest` plans the future manifest entry and writes nothing.
- real `report export --record-manifest` fails closed before any report or manifest write.

Current report export behavior remains unchanged:

- `report export` writes one `.md` report file only under approved report roots.
- `report export --dry-run` writes nothing.
- `report export` does not write logs, registry files, baselines, session state, intake journal, local config, or runtime manifest files.

## Proposed Write Behavior

Future manifest writing may be exposed as an explicit flag on `report export`:

```powershell
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md --record-manifest
```

Dry-run form:

```powershell
python -m armedforces_tool report export --dry-run --type full-status --out reports/python_tooling/full_status.md --record-manifest
```

Required behavior:

- `--record-manifest` is a future ability, not implemented by this contract.
- manifest writing is allowed only after report export succeeds.
- dry-run must not write a report or manifest.
- `report export` without `--record-manifest` remains unchanged.
- manifest writing must not occur as an implicit side effect.

## Approved Manifest Location

The first contract version uses the smallest write boundary:

```text
reports/python_tooling/manifest.jsonl
```

Optional future candidate, not implemented by this contract:

```text
docs/reports/python_tooling/manifest.jsonl
```

Explicitly forbidden manifest locations:

- `log/`
- `log/case_registry.jsonl`
- `log/case_intake.local.jsonl`
- `log/baselines/*.md`
- `src/`
- `tests/`
- `docs/codex_tasks/`
- local config files
- session files
- intake files
- registry files
- baseline files

## Manifest Format

First-version format:

- append-only JSONL
- each line is one JSON object
- each successful manifest write appends one new line

Required fields:

- `report_id`
- `report_type`
- `created_at`
- `output_path`
- `output_root`
- `file_size`
- `sha256`
- `command`
- `dry_run`
- `status`
- `schema_version`

Rules:

- `schema_version` must exist.
- append-only JSONL is preferred over mutable JSON.
- mutable JSON is deferred.
- `report_index.md` generation is deferred.
- manifest records should remain parseable by read-only `report manifest verify`.

## Report ID Strategy

The future implementation must define a stable report ID strategy before writing manifests.

Acceptable strategies:

- deterministic hash from `output_path` + `created_at` + `sha256`
- generated UUID-like ID

Requirements:

- duplicate `report_id` must be detected.
- duplicate behavior must be explicit: reject or warn.
- `report_id` must not depend on mutable runtime global state.
- `report_id` must not require CE state.

## Write Ordering

Required future ordering:

1. validate output path
2. run report generation
3. write report to approved root
4. compute file size and SHA256
5. append manifest entry
6. verify appended entry is parseable

Failure rules:

- if report write fails, do not write manifest
- if manifest append fails, report may already exist, so return clear partial-success status
- do not allow manifest entries pointing to missing reports unless explicitly marked failed
- do not report success unless both report write and manifest append have the expected result

## Failure Handling

Future implementation must handle:

- report write failed before manifest write
- manifest write failed after report write
- manifest append partially written
- corrupt existing manifest
- duplicate `report_id`
- missing report referenced by manifest
- unsupported `schema_version`
- concurrent write assumption

Required policy:

- fail closed
- no silent success
- operator-visible status
- repair or verification path through read-only `report manifest verify`

Partial-success status must be explicit. If a report is written but manifest append fails, the command should say the report exists and the manifest is incomplete.

## Overwrite And Force Rules

Report overwrite rules remain unchanged:

- default report overwrite is rejected
- `--force` only allows overwriting the report file
- `--force` must not delete old manifest entries
- `--force --record-manifest` must append a new manifest entry
- old manifest entries must not be modified
- manifest compaction is deferred
- index rebuild is deferred

Manifest entries are historical records. They should not be rewritten by ordinary export commands.

## Dry-Run Semantics

Future dry-run behavior for `--record-manifest`:

- display `would_write_report`
- display `would_write_manifest`
- no report is created
- no manifest is created
- no directories are created
- output includes planned manifest path
- output includes planned entry fields
- command inventory may remain read-only for dry-run paths only if they write nothing

Dry-run must be safe to execute repeatedly.

## Phase 3.15 Dry-Run Implementation Note

Implemented dry-run command shape:

```powershell
python -m armedforces_tool report export --dry-run --type full-status --out reports/python_tooling/full_status.md --record-manifest
```

Current behavior:

- validates the report output path
- renders report content for metadata only
- sets `would_write_report=true`
- sets `would_write_manifest=true`
- plans `reports/python_tooling/manifest.jsonl`
- prints a planned manifest entry
- writes no report
- writes no manifest
- creates no directories

The dry-run planned manifest path is always `reports/python_tooling/manifest.jsonl`, including when the report output path is under `docs/reports/python_tooling/`.

Real manifest write behavior is still not implemented:

```powershell
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md --record-manifest
```

This fails closed with `MANIFEST_WRITE_NOT_IMPLEMENTED` before any report or manifest write.

## Command Inventory Impact

Future inventory impact:

- `report export` remains write-capable
- no new write-capable command is required if `--record-manifest` is a flag on `report export`
- `writes_files_count` remains `1` if only `report export` remains write-capable
- manifest preview/list/verify remain read-only
- `runs_ce_count` remains `0`

If a future standalone manifest write command is introduced, command inventory must mark it separately as write-capable.

## Required Tests For Future Implementation

Required tests:

- dry-run writes neither report nor manifest
- real export writes report and appends manifest under approved root
- no `--record-manifest` means no manifest write
- manifest write occurs only after report success
- report failure prevents manifest write
- corrupt manifest rejected or fail-closed
- duplicate `report_id` handled
- bad manifest path rejected
- traversal rejected
- protected paths rejected
- `--force` appends a new entry and does not mutate old entries
- inventory still has `writes_files_count = 1`
- manifest preview/list/verify remain read-only
- no CE / runtime / log/config/session/intake/baseline/registry writes

Tests should use temporary directories and fixtures, not runtime report roots.

## Required Smoke Validation For Future Implementation

Required smoke validation:

- protected hash snapshot before/after
- dry-run no-write check
- real write under approved root
- manifest appended
- `report manifest verify` returns OK
- cleanup only smoke-created report and manifest files or lines if safe
- final git status check
- pytest

Smoke validation must not delete pre-existing user reports or pre-existing manifest content.

## Cleanup Policy

If future smoke validation creates a manifest:

- record pre-existing manifest existence
- record pre-existing manifest hash
- record pre-existing manifest line count
- if manifest is created by smoke, it may be deleted
- if manifest already existed, only remove exact lines appended by the smoke if safely identifiable
- do not delete pre-existing report roots
- do not delete user-created reports
- report cleanup results explicitly

If safe cleanup is not possible, leave the file in place and report the exact manual cleanup step.

## Explicit Non-Goals

This contract does not authorize:

- immediate manifest write implementation
- `docs/reports` manifest writing
- mutable JSON manifest
- Markdown report index generation
- CE automation
- guarded write/restore migration
- PowerShell/Lua/runtime changes
- log/config/session/intake/baseline/registry writes
- algorithm rewrite
