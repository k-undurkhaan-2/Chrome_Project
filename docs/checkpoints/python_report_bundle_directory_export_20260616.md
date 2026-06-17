# Python Report Bundle Directory Export - 2026-06-16

## Purpose

Record the Phase 3.29 implementation state for directory-only Python report bundle export.

## Included

- `report bundle export --out reports/python_tooling/bundles/<bundle_id>/`
- directory-only bundle output
- copied report files under bundle-local `reports/`
- bundle-local `bundle_manifest.json`
- bundle-local `index.md`
- source report hash verification
- source manifest remains read-only
- source reports remain read-only

## Excluded

- zip export
- `--force`
- overwrite of existing bundle directories
- writes to `docs/reports`
- writes to `log/`, registry, baseline, session, intake, or local config
- CE/runtime mutation

## Inventory State

- write-capable commands: `report export`, `report bundle export`
- `writes_files_count = 2`
- `runs_ce_count = 0`

## Cleanup Boundary

Smoke validation may delete only smoke-created source reports, smoke-created manifests, and smoke-created bundle directories. Pre-existing user reports, manifests, and bundle directories must not be deleted.
