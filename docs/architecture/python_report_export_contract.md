# Python Report Export Contract

## Purpose

This document defines the future write-capable contract for Python `report export`.

It is not an implementation. It does not add a Python command, does not change current CLI behavior, and does not permit report file writes in the current phase.

## Current State

The current Python report layer is:

- `report preview` is implemented and stdout-only.
- `report export` is not implemented.
- The current Python command inventory should remain entirely read-only.
- Current stable state:
  - `status overview = SAFE`
  - pytest = `97 passed`

The existing read-only sidecar remains the default Python tooling boundary.

## Write-Capable Boundary

Future `report export` is write-capable. It must be treated separately from the current read-only command layer.

Requirements:

- Command inventory must mark `writes_files=true`.
- `risk_level` must not be `READ_ONLY`.
- Output path must be explicit.
- Default behavior must not overwrite files.
- Default behavior must require dry-run / preview first.

`report export` must not be presented as equivalent to `report preview`. Preview renders to stdout; export writes a Markdown file and therefore needs a stronger safety contract.

## Approved Output Roots

Future report export may write only under one of these roots:

```text
reports/python_tooling/
docs/reports/python_tooling/
```

Report export must not write under:

- `log/`
- `src/`
- `tests/`
- `docs/codex_tasks/`
- `.git/`
- `.codex/`
- `src/run_case_config.local.lua`
- `src/run_case_config.local.lua.bak`
- `log/case_registry.jsonl`
- `log/case_intake.local.jsonl`
- `log/active_test_session.local.json`
- `log/test_session_history.local.jsonl`
- `log/baselines/*.md`

These protected paths remain forbidden even if `--force` is provided.

## Path Safety Rules

Future implementation must enforce these path safety rules before any write:

- Normalize / resolve the absolute path.
- Reject path traversal with `..`.
- Reject absolute paths outside approved output roots.
- Reject symlink escape if detectable on the host filesystem.
- Reject reserved Windows device names when applicable.
- Reject writing to protected files.
- Reject extensions other than `.md` unless explicitly approved later.

Validation must happen before parent directory creation, overwrite checks, or file writes.

## File Naming Rules

Recommended default naming:

```text
reports/python_tooling/<report_type>_<YYYYMMDD-HHMMSS>.md
```

Requirements:

- `report_type` must come from a whitelist.
- Timestamp must use a consistent format.
- Filename must be sanitized.
- No user-controlled raw filename is allowed without validation.

Recommended report type whitelist:

- `status-overview`
- `safety-doctor`
- `baseline-compare`
- `case-summary`
- `registry-summary`
- `transaction-summary`
- `full-status`

## Overwrite Policy

Overwrite rules:

- Default behavior is no overwrite.
- If the target file exists, fail with a clear error.
- `--force` is required for overwrite.
- Even with `--force`, protected paths are never allowed.
- Overwrite must be limited to files under approved output roots.

The error message should include the target path and the recommended safer action.

## Dry-Run / Preview Policy

Dry-run and preview rules:

- `report preview` remains stdout-only.
- `report export --dry-run` should show target path and content summary without writing.
- The first export implementation should support dry-run before write.
- Smoke checks must verify dry-run creates no files.

Dry-run output should include:

- report type
- resolved output path
- whether parent directory exists
- whether target file already exists
- whether `--force` would be required
- short content summary

## Proposed Command Shape

Possible future command shapes:

```powershell
python -m armedforces_tool report export --type status-overview --output-dir reports/python_tooling --dry-run
python -m armedforces_tool report export --type status-overview --output-dir reports/python_tooling
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status_YYYYMMDD-HHMMSS.md
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status_YYYYMMDD-HHMMSS.md --force
```

These examples are documentation only. They are not implemented in this phase.

## Required Tests Before Implementation

Future implementation must include tests for:

- Path traversal rejected.
- Outside root rejected.
- Protected file rejected.
- Default no overwrite.
- Force overwrite allowed only under approved root.
- Dry-run writes nothing.
- Export writes exactly one intended `.md`.
- Command inventory marks `writes_files=true`.
- No CE run.
- No config, log, session, intake, baseline, or registry writes.

Tests should use temporary directories and fixtures rather than real project logs.

## Required Smoke Check Before Enabling

Future smoke check must include:

- Protected-file hash before/after.
- `git status --short`.
- Verify report file is created only under approved directory.
- Verify no report file is created during dry-run.
- pytest.
- No CE.
- No PowerShell, Lua, or runtime mutation.

The smoke check should explicitly report all created report files and confirm no protected files changed.

## Explicit Non-Goals

This phase does not:

- Implement `report export`.
- Write report files.
- Allow writing log, baseline, config, session, intake, or registry files.
- Migrate guarded write / restore.
- Automate CE.
- Modify PowerShell workflow.
- Modify Lua runtime.
- Change the filtering algorithm.

## Recommended Next Implementation Step

If implementation is approved later, the recommended order is:

1. Implement `report export --dry-run` only.
2. Create a separate checkpoint.
3. Then implement real `.md` writing under approved output roots.

## Phase 3.6 Dry-Run Implementation Note

`report export --dry-run` is the only implemented export command shape in Phase 3.6.

It validates approved output roots, target extension, protected paths, traversal, existing target state, and `--force` overwrite metadata. It prints the target plan and content summary only.

It does not:

- create output directories
- write `.md` report files
- write logs, registry files, baselines, session state, intake journal, or local config
- run CE
- enable real `report export`

Calling `report export` without `--dry-run` must continue to fail with `REPORT_EXPORT_NOT_IMPLEMENTED`.
