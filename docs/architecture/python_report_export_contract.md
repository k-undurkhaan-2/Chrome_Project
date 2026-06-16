# Python Report Export Contract

## Purpose

This document defines the write-capable contract for Python `report export`.

The implemented command is intentionally narrow: it writes one Markdown report file only under approved output roots after path validation. It does not run CE and does not mutate runtime, local config, logs, registry, session, intake, or baseline files.

## Current State

The current Python report layer is:

- `report preview` is implemented and stdout-only.
- `report export --dry-run` validates output paths without writing.
- `report export` writes one `.md` file only under approved output roots.
- The command inventory marks `report export` as write-capable while keeping all CE/runtime mutation flags false.
- Current stable state:
  - `status overview = SAFE`
  - pytest = `114 passed`

The existing read-only sidecar remains the default Python tooling boundary. `report export` is the only Python tooling command with file-write capability.

## Implementation Status

Current implementation status:

- `report preview` is stdout-only.
- `report export --dry-run` is implemented and must not write files or create directories.
- guarded real `report export` is implemented.
- write scope is limited to `reports/python_tooling/` and `docs/reports/python_tooling/`.
- checkpoint tag: `python-report-export-guarded-checkpoint-20260616`
- smoke validation passed with protected files unchanged.
- current pytest result: `114 passed`.

No Python report command runs CE or writes config, logs, registry, baseline, session state, intake journal, or runtime files.

## Write-Capable Boundary

`report export` is write-capable. It must be treated separately from the read-only command layer.

Requirements:

- Command inventory must mark `writes_files=true`.
- `risk_level` must not be `READ_ONLY`.
- Output path must be explicit.
- Default behavior must not overwrite files.
- Dry-run remains available and must not write.

`report export` must not be presented as equivalent to `report preview`. Preview renders to stdout; export writes a Markdown file and therefore needs a stronger safety contract.

## Approved Output Roots

Report export may write only under one of these roots:

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

Implementation must enforce these path safety rules before any write:

- Normalize / resolve the absolute path.
- Reject path traversal with `..`.
- Reject absolute paths outside approved output roots.
- Reject symlink escape if detectable on the host filesystem.
- Reject reserved Windows device names when applicable.
- Reject writing to protected files.
- Reject extensions other than `.md` unless explicitly approved later.

Validation must happen before parent directory creation, overwrite checks, or file writes.

## File Naming Rules

Default naming when `--output-dir` is used:

```text
reports/python_tooling/<report_type>_<YYYYMMDD-HHMMSS>.md
```

Requirements:

- `report_type` must come from a whitelist.
- Timestamp must use a consistent format.
- Filename must be sanitized.
- No user-controlled raw filename is allowed without validation.

Report type whitelist:

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

## Command Shape

Supported command shapes:

```powershell
python -m armedforces_tool report export --type status-overview --output-dir reports/python_tooling --dry-run
python -m armedforces_tool report export --type status-overview --output-dir reports/python_tooling
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status_YYYYMMDD-HHMMSS.md
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status_YYYYMMDD-HHMMSS.md --force
```

`--dry-run` validates the exact target and content metadata without creating directories or files. Without `--dry-run`, the command writes the report if all path and overwrite gates pass.

## Required Tests

Implementation must include tests for:

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

## Required Smoke Check

Smoke check must include:

- Protected-file hash before/after.
- `git status --short`.
- Verify report file is created only under approved directory.
- Verify no report file is created during dry-run.
- pytest.
- No CE.
- No PowerShell, Lua, or runtime mutation.

The smoke check should explicitly report all created report files and confirm no protected files changed.

## Manifest / Report Index Boundary

Current `report export` writes only the requested `.md` report file. It does not record a manifest, update an index, append JSONL, or write any persistent report metadata file.

Current `report export` does not record a manifest. Manifest / report index support is governed by `docs/architecture/python_report_manifest_write_contract.md`.

A future `--record-manifest` flag must follow that contract. Current `report export` behavior remains unchanged until a separate implementation task explicitly adds the flag and validates the write boundary.

## Explicit Non-Goals

This contract does not:

- Allow writing report files outside approved roots.
- Allow writing log, baseline, config, session, intake, or registry files.
- Migrate guarded write / restore.
- Automate CE.
- Modify PowerShell workflow.
- Modify Lua runtime.
- Change the filtering algorithm.

## Phase 3.6 Dry-Run Implementation Note

`report export --dry-run` is the only implemented export command shape in Phase 3.6.

It validates approved output roots, target extension, protected paths, traversal, existing target state, and `--force` overwrite metadata. It prints the target plan and content summary only.

It does not:

- create output directories
- write `.md` report files
- write logs, registry files, baselines, session state, intake journal, or local config
- run CE
- enable real `report export`

## Phase 3.7 Real Export Implementation Note

`report export` writes exactly one `.md` report file after the same path validation used by `--dry-run`.

It:

- allows only `reports/python_tooling/` and `docs/reports/python_tooling/`
- creates the approved parent directory only after validation
- refuses existing targets unless `--force` is supplied
- rejects path traversal, protected roots, and non-`.md` paths
- never writes logs, registry files, baselines, session state, intake journal, or local config
- never runs CE

The dry-run behavior remains no-write and must not create directories or files.
