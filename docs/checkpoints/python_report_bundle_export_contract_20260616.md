# Python Report Bundle Export Contract - 2026-06-16

## Summary

Phase 3.24 adds a documentation-only contract for future Python report bundle export.

## Boundary

- no bundle export implementation
- no new Python command
- no new write-capable behavior
- `report export` remains the only write-capable Python command
- `writes_files_count = 1`
- `runs_ce_count = 0`

## Contract Coverage

- approved bundle outputs under `reports/python_tooling/bundles/`
- directory bundle format
- zip bundle format
- `bundle_manifest.json` data model
- dry-run requirements
- write ordering
- overwrite / force policy
- failure handling
- cleanup policy
- command inventory impact
- required future tests and smoke validation

## Deferred

Bundle dry-run and real bundle export remain deferred. Any implementation must follow this contract, the Python write-capable feature policy, smoke cleanup rules, and a checkpoint before expanding scope.
