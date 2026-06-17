# Python Report Bundle Export Dry-Run - 2026-06-16

## Summary

Phase 3.25 adds no-write planning for future Python report bundle export.

## Included

- `python -m armedforces_tool report bundle export --dry-run`
- directory bundle output path planning
- zip bundle output path planning
- JSON dry-run output
- fail-closed real bundle export without `--dry-run`

## Boundary

- no real bundle export
- no bundle directory creation
- no zip creation
- no copied reports
- no `bundle_manifest.json`
- no `index.md`
- no runtime report or manifest writes
- `report export` remains the only write-capable Python command
- `writes_files_count = 1`
- `runs_ce_count = 0`

## Deferred

Real bundle export remains deferred until a guarded implementation phase with smoke validation, cleanup rules, and checkpoint.
