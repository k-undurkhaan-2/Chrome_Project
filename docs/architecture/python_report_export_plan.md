# Python Report Export / Markdown Rendering Plan

## Purpose

Report export / Markdown rendering is a Phase 3 candidate direction for turning existing Python read-only analysis and status results into human-readable reports.

This document is planning only. It does not implement a report command, does not add CLI behavior, and does not change the current read-only Python sidecar.

## Current Boundary

The current Python tooling remains read-only:

- It does not run CE.
- It does not write config, logs, session state, intake journals, baselines, or registry files.
- It does not replace the PowerShell workflow.
- It does not generate write or restore actions.

PowerShell remains authoritative for workflow mutation commands, guarded write preparation, restore preparation, local config updates, and manual operator flow.

## Why Report Export Needs A Separate Contract

Report export introduces file-writing behavior. That means it cannot be mixed directly into the current read-only sidecar layer without a separate contract, separate validation, and clear command inventory risk marking.

The future contract must define:

- Output directory.
- File naming.
- Overwrite policy.
- Dry-run / preview mode.
- Protected file exclusions.
- Command inventory risk marking.
- Regression checks.

Until that contract exists, report output should remain console-only.

## Candidate Report Types

Future report export may support these report types:

- Status overview report.
- Safety doctor report.
- Baseline compare report.
- Case summary report.
- Registry summary report.
- Transaction history report.
- Full project status bundle.

These are candidates only. No report export command is implemented in this phase.

## Proposed Output Location

Future report export should write only under one approved report directory, such as:

- `reports/python_tooling/`
- `docs/reports/python_tooling/`

The final directory should be selected before implementation and documented in the command help, tests, and command inventory.

Report export must not write under:

- `log/`
- `src/`
- `tests/`
- `docs/codex_tasks/`
- Local config files.
- Session or intake files.
- Baseline files.
- Registry files.

## Proposed Safety Model

Future report export should use this safety model:

- Default to dry-run / preview first.
- Require explicit `--out` or `--output-dir` for any file write.
- Never overwrite an existing file unless `--force` is provided.
- Write only under the approved report directory.
- Create parent directories only when explicit behavior is requested and validated.
- Never modify existing protected files.
- Optionally run protected-file hash checks before and after export.
- Mark report export commands as `writes_files=true` in command inventory.
- Keep report export commands separate from the current read-only commands.

The first implementation should prefer rendering the exact content that would be written, without writing it.

## Proposed Command Shape

Possible future command shapes:

```powershell
python -m armedforces_tool report preview --type status-overview
python -m armedforces_tool report export --type status-overview --out reports/python_tooling/status_overview_YYYYMMDD.md
python -m armedforces_tool report export --type full-status --output-dir reports/python_tooling
```

These examples are documentation only. They are not implemented in this phase.

## Required Gates Before Implementation

Before any report export implementation, the project should complete these gates:

- Design approved.
- Planning docs committed.
- Output directory policy finalized.
- Tests for path safety.
- Tests for overwrite behavior.
- Tests for dry-run behavior.
- Smoke check.
- Separate checkpoint before enabling any write-capable report command.

## Explicit Non-Goals

This phase does not:

- Implement any report command.
- Write report files.
- Migrate guarded write or restore logic.
- Automate CE.
- Modify the PowerShell workflow.
- Change command inventory read-only claims before real export commands exist.
- Mix report export with write or restore behavior.

## Recommended Next Step After Planning

If report export is approved later, the recommended implementation sequence is:

1. Add `report preview` only, with strictly no file writes.
2. Add `report export` later, with a controlled output directory, path safety validation, overwrite rules, tests, and updated command inventory risk marking.

## Phase 3.5 Contract Note

`docs/architecture/python_report_export_contract.md` now defines the future write-capable contract for `report export`.

Implementation remains deferred. `report preview` remains stdout-only and does not write report files.
