# Python Report Manifest Plan

## Purpose

This document plans future Python report manifest / report index support for `D:\armedforces.io-v2`.

A report manifest would be a persistent index or metadata record for report export outputs. It could help operators find exported reports, verify report hashes, inspect report provenance, and audit report generation history.

This phase is planning only. It does not implement manifest behavior, add a Python command, change `report export`, or write any manifest file.

## Current Baseline

Current Python report tooling state:

- `report export` is implemented.
- `report export` is the only write-capable Python command.
- `writes_files_count = 1`.
- `runs_ce_count = 0`.
- approved output roots:
  - `reports/python_tooling/`
  - `docs/reports/python_tooling/`
- `report export --dry-run` writes nothing.
- `report preview` writes nothing and renders to stdout.

`report export` does not write:

- `log/`
- local config
- session state
- intake journal
- baseline files
- registry files

## Why Manifest Needs Separate Planning

A manifest introduces persistent state beyond a single report `.md` file. It is not just another report output; it is an index that may be appended, updated, verified, repaired, or used by later tooling.

Candidate manifest forms include:

- `manifest.json`
- `manifest.jsonl`
- `report_index.md`

Because this state can outlive individual reports, it needs a separate contract covering:

- manifest location
- file format
- append / update rules
- overwrite rules
- corruption recovery
- locking / concurrency assumptions
- cleanup behavior
- command inventory marking
- protected-file hash checks

No manifest write should be added as an incidental side effect of report export without this contract.

## Candidate Manifest Locations

Allowed candidate locations for future design:

- `reports/python_tooling/manifest.jsonl`
- `reports/python_tooling/manifest.json`
- `docs/reports/python_tooling/manifest.jsonl`
- `docs/reports/python_tooling/report_index.md`

These locations are under the existing approved report roots. They are candidates only; no manifest location is implemented by this plan.

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

## Manifest Data Model

A future manifest record should be explicit, compact, and audit-friendly.

Candidate top-level fields:

- `report_id`
- `report_type`
- `created_at`
- `output_path`
- `output_root`
- `file_size`
- `sha256`
- `command`
- `dry_run = false`
- `status`

Candidate `source_summary` fields:

- status overview result
- baseline compare result
- case summary result
- registry summary result
- transaction summary result

Example JSONL record shape:

```json
{
  "report_id": "full-status-20260616-120000",
  "report_type": "full-status",
  "created_at": "2026-06-16T12:00:00Z",
  "output_path": "reports/python_tooling/full_status_20260616-120000.md",
  "output_root": "reports/python_tooling",
  "file_size": 12345,
  "sha256": "<hex>",
  "command": "python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status_20260616-120000.md",
  "dry_run": false,
  "status": "written",
  "source_summary": {
    "status_overview": "SAFE",
    "baseline_compare": "BASELINE_COMPARE_PASS",
    "case_summary": "COVERAGE_OK",
    "registry_summary": "REGISTRY_OK",
    "transaction_summary": "TRANSACTION_HISTORY_OK"
  }
}
```

## Write Rules

Future manifest support would be write-capable behavior and must be governed by a separate contract.

Required write rules:

- default to dry-run first
- no overwrite unless explicitly allowed
- append-only JSONL should be preferred unless there is a strong reason for mutable JSON
- append-only JSONL still requires validation, duplicate detection, and corruption handling
- mutable JSON requires a temp file plus atomic replace plan
- manifest write must not occur if report export fails
- manifest write must be tested separately from report export write
- manifest write must not create or modify protected local state
- command inventory must mark manifest-writing commands as `writes_files=true`

## Failure Handling

Future implementation must define behavior for these failure cases before code is written:

- report written but manifest write failed
- manifest written but report write failed
- partial or corrupt manifest row
- partial or corrupt mutable manifest file
- duplicate `report_id`
- missing report file referenced by manifest
- report file hash mismatch
- manifest path exists but is not a regular file
- concurrent export attempts

Planned recovery approach:

- Prefer append-only JSONL to reduce whole-file corruption risk.
- Validate each manifest row independently.
- Treat invalid rows as warnings for read-only list/verify commands.
- Never silently rewrite or drop invalid historical rows.
- Provide a future read-only `verify` command before any repair command.
- Require a separate repair contract before implementing manifest mutation or cleanup.

## Proposed Command Shape

These are possible future commands only. They are not implemented by this phase.

```powershell
python -m armedforces_tool report manifest preview
python -m armedforces_tool report manifest list
python -m armedforces_tool report manifest verify
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md --record-manifest
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md --record-manifest --dry-run
```

Potential read-only commands:

- `report manifest preview`
- `report manifest list`
- `report manifest verify`

Potential write-capable command shape:

- `report export ... --record-manifest`

Any write-capable command shape must go through a separate contract and smoke checkpoint.

## Safety Model

Safety requirements:

- manifest commands should start read-only
- manifest read/list/verify commands can remain read-only
- manifest write/update requires a separate contract
- manifest must remain under approved report roots
- no writes to log/config/session/intake/baseline/registry
- no CE run
- no runtime mutation
- no PowerShell or Lua behavior change
- command inventory must mark manifest-writing commands as `writes_files=true`

Manifest planning must not weaken the existing boundary where `report export` is the only write-capable Python command.

## Recommended Implementation Order

Recommended order:

1. manifest planning doc
2. manifest read-only preview/list design
3. manifest verify read-only command
4. manifest write contract
5. manifest dry-run implementation
6. manifest write implementation
7. guarded smoke/checkpoint

The first implementation step should be read-only. It should inspect existing report roots and print what a manifest would contain without writing anything.

## Explicit Non-Goals

This phase does not:

- implement manifest commands
- write manifest files
- change `report export` behavior
- add `--record-manifest`
- migrate guarded write / restore
- automate CE
- write log/config/session/intake/baseline/registry
- modify PowerShell behavior
- modify Lua behavior
- modify runtime behavior
- modify filtering, ranking, scoring, thresholds, quota, or stable intersection behavior

