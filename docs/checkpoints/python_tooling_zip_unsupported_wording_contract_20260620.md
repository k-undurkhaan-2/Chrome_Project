# Python Tooling Zip Unsupported Wording Contract - 2026-06-20

## Summary

Phase 7.2C defines the future wording contract for unsupported zip/archive output requests in `report bundle export`.

This checkpoint records contract creation only.

## Contract Scope

The future implementation should clarify fail-closed zip/archive rejection output with:

- `ZIP_UNSUPPORTED`
- `NO_FILES_WRITTEN`, if compatible with current output style

It must not:

- enable zip export
- add zip support for testing
- create zip files
- create directory bundles as fallback
- create `bundle_manifest.json`
- create `index.md`
- copy reports
- modify wrapper behavior
- run CE
- write runtime artifacts

## Status

- code changed: no
- tests changed: no
- behavior changed: no
- tag created: no

Future implementation must first confirm that current CLI/source has an existing zip rejection surface. If it does not, the implementation phase must stop and request a separate parser-surface contract.
