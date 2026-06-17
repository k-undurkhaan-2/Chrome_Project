# Python Report Bundle Directory Export Contract - 2026-06-16

## Purpose

Record the Phase 3.28 contract refinement for the first future real Python report bundle export implementation.

## Scope

The first future real bundle export is narrowed to directory-only output:

```text
reports/python_tooling/bundles/<bundle_id>/
```

No implementation is added in this phase.

## Deferred

- zip export
- `--force`
- overwrite of existing bundle directories
- `docs/reports` bundle output
- source manifest mutation
- report manifest mutation
- source report deletion
- log/config/session/intake/baseline/registry writes

## Required Future Write Ordering

1. validate output path
2. validate source manifest path
3. parse manifest
4. verify referenced reports
5. compute source report hashes
6. create a temporary bundle directory under the approved root
7. copy reports into temporary bundle `reports/`
8. write `bundle_manifest.json`
9. write `index.md`
10. verify copied hashes
11. atomically move to final bundle directory
12. run read-only bundle verification if applicable

## Cleanup Policy

Future smoke cleanup may delete only bundle artifacts created by the current smoke. It must never delete pre-existing bundle directories, source reports, `reports/python_tooling/manifest.jsonl`, or `reports/python_tooling/`.

## Status

- real directory export: not implemented
- zip export: deferred
- `report export`: still the only write-capable Python command
- current `writes_files_count`: `1`
- current `runs_ce_count`: `0`
