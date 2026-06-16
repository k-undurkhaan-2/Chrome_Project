# Python Report Bundle Plan - 2026-06-16

## Purpose

Record the planning boundary for future Python report bundle / report package support in `D:\armedforces.io-v2`.

## Current State

- `report export` remains the only write-capable Python command.
- `writes_files_count = 1`.
- `runs_ce_count = 0`.
- `report export --record-manifest` writes only reports under `reports/python_tooling/` and `reports/python_tooling/manifest.jsonl`.
- No bundle command exists.

## Bundle Planning Boundary

Future bundle support may package reports, manifest entries, and an index into a directory or zip archive. This is a separate write-capable surface and is not authorized by the existing report export or report manifest contracts.

Candidate future outputs:

- `reports/python_tooling/bundles/<bundle_id>/`
- `reports/python_tooling/bundles/<bundle_id>.zip`
- `reports/python_tooling/bundles/<bundle_id>/bundle_manifest.json`
- `reports/python_tooling/bundles/<bundle_id>/index.md`

## Deferred Work

- Bundle read-only preview/verify contract.
- Bundle preview implementation.
- Bundle write contract.
- Bundle dry-run implementation.
- Bundle guarded real write implementation.
- Bundle operator docs and checkpoint.

## Non-Goals

- No bundle implementation in this phase.
- No Python command added.
- No report export or manifest writer behavior change.
- No writes to runtime reports, manifests, bundles, logs, registry, baseline, session, intake, or local config.
- No CE automation.
