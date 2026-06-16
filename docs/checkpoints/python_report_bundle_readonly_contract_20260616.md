# Python Report Bundle Read-Only Contract - 2026-06-16

## Purpose

Record the read-only contract boundary for future Python report bundle preview / verify support.

## Included

- Proposed future command shapes:
  - `report bundle preview`
  - `report bundle verify`
- Read-only guarantees.
- Input discovery from `reports/python_tooling/manifest.jsonl`.
- Path safety for referenced report files.
- Preview and verify output models.
- Future test expectations.

## Boundary

- No bundle command is implemented.
- No bundle directory or zip archive is created.
- No bundle manifest or index is written.
- `writes_files_count` must remain `1` when preview/verify are implemented.
- `runs_ce_count` must remain `0`.
- `report export` remains the only write-capable Python command.

## Deferred

- Bundle read-only preview implementation.
- Bundle read-only verify implementation.
- Bundle export write contract.
- Bundle dry-run and real write behavior.
