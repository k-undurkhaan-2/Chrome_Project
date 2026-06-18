# Python Tooling Dry-Run Output Integration Contract

## Purpose

This document defines the future contract for integrating report/bundle output wording helpers into dry-run report and bundle export output.

This phase is documentation-only. It does not execute dry-run commands, implement integration, modify Python source, modify tests, add commands, add options, run CE, or expand write surface.

Phase 5.12 note: `docs/architecture/python_tooling_real_write_output_contract.md` now defines the separate future real-write output wording contract. Dry-run output implementation remains separate and has already been completed; real-write output implementation remains deferred.

## Current Baseline

Current stable boundary:

- Phase 5.7 output helpers exist in `src/armedforces_tool/report_output_messages.py`
- Phase 5.8 helper-only boundary smoke passed
- helpers are not wired into export or dry-run paths yet
- command inventory: about `49` commands
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable commands:
  - `report export`
  - `report bundle export`
- wrapper remains read-only
- no CE/runtime mutation exists in Python tooling
- no log/config/session/intake/baseline/registry writes have been introduced

## Integration Targets

The only future integration targets are:

- `report export --dry-run`
- `report bundle export --dry-run`

Explicitly excluded:

- real `report export`
- `report export --record-manifest`
- real `report bundle export`
- wrapper commands
- CE/runtime paths
- log/config/session/baseline/intake/registry write paths

## Non-Goals

The future dry-run integration must not:

- add commands
- add options
- add `--force`
- add zip export
- change approved roots
- change path guard behavior
- change manifest write behavior
- change bundle export behavior
- route export through the wrapper
- modify real-write behavior
- run CE
- write logs/config/session/baseline/intake/registry

## Future Dry-Run Output Contract

Dry-run output must remain no-write and should make that boundary visible.

### `report export --dry-run`

Future output should use or align with the report export dry-run helper and include:

- `DRY_RUN`
- `NO_FILES_WRITTEN`
- intended report path
- `APPROVED_ROOT` or approved-root status
- manifest write status
- `WRAPPER_UNSUPPORTED`
- `CE_NOT_RUN`
- confirmation that the command remains no-write

It must not:

- create a report file
- append manifest
- create bundle output
- modify log/config/session/baseline/intake/registry
- call CE

### `report bundle export --dry-run`

Future output should use or align with the bundle export dry-run helper and include:

- `DRY_RUN`
- `NO_FILES_WRITTEN`
- intended bundle directory
- intended `bundle_manifest.json` path
- intended `index.md` path
- `APPROVED_ROOT` or approved-root status
- directory-only bundle mode
- `ZIP_UNSUPPORTED`
- `WRAPPER_UNSUPPORTED`
- `CE_NOT_RUN`
- confirmation that the command remains no-write

It must not:

- create bundle directory
- create zip
- create `bundle_manifest.json`
- create `index.md`
- modify source reports/manifests
- modify log/config/session/baseline/intake/registry
- call CE

## Helper Integration Approach

Preferred future implementation approach:

- reuse `src/armedforces_tool/report_output_messages.py`
- keep formatting helper calls isolated to dry-run output paths only
- avoid changing business logic
- avoid changing command parsing
- avoid changing path validation
- keep output deterministic enough for tests
- assert stable message tokens instead of long exact paragraphs

If future implementation needs small adapter functions, they must:

- not write files
- not call CE
- not modify environment
- not mutate state
- not alter command inventory

## Test Contract For Future Implementation

Future tests should cover:

- `report export --dry-run` exits successfully
- `report export --dry-run` includes required tokens
- `report export --dry-run` creates no report/manifest/bundle artifacts
- `report bundle export --dry-run` exits successfully
- `report bundle export --dry-run` includes required tokens
- `report bundle export --dry-run` creates no bundle directory / zip / manifest / index
- inventory invariants remain:
  - `writes_files_count = 2`
  - `runs_ce_count = 0`
- helper unit tests remain valid
- wrapper boundary tests remain valid

Tests must not execute:

- real `report export`
- `report export --record-manifest`
- real `report bundle export`
- CE/runtime commands

## Artifact Safety Contract

Future implementation validation must record before/after state for:

- `reports/python_tooling/full_status.md`
- `reports/python_tooling/manifest.jsonl`
- `reports/python_tooling/bundles`
- `docs/reports/python_tooling`
- `log/case_registry.jsonl`

If `log/case_registry.jsonl` exists before validation, its hash must remain unchanged.

Do not delete pre-existing user files or directories.

## Validation Stages For Future Implementation

### Stage 1: Unit / Helper Tests

- run helper tests
- execute no export or dry-run command
- create no runtime artifacts

### Stage 2: Dry-Run Command Validation

Only in the future implementation task:

- execute dry-run commands only
- perform no real writes
- append no manifest
- create no bundle directory
- run no CE
- record before/after artifact snapshots

### Stage 3: Full Regression

- run full pytest
- run status overview
- run command inventory
- run wrapper read-only status/inventory
- check final git status

## Risk Assessment

| Area | Behavior-change risk | Write-surface risk | Likely future files touched | Required tests | Allowed in next implementation? |
| --- | --- | --- | --- | --- | --- |
| `report export --dry-run` output wording | medium | low | `src/armedforces_tool`, tests | dry-run output tokens and artifact snapshot | yes, if scoped |
| `report bundle export --dry-run` output wording | medium | low | `src/armedforces_tool`, tests | dry-run output tokens and artifact snapshot | yes, if scoped |
| Helper adapter functions | low | low | `src/armedforces_tool`, tests | unit tests and reference inspection | yes, if scoped |
| Inventory invariants | low | low | tests | inventory checks | yes |
| Artifact snapshot validation | low | low | tests or smoke scripts | before/after path/hash checks | yes |
| Wrapper exclusion reminder | low | low | output helpers/docs | wrapper boundary tests | yes |

## Recommended Next Implementation Slice

Recommended next phase:

```text
Phase 5.10: dry-run output wording implementation
```

Recommended future scope:

- integrate helpers into dry-run output only
- modify Python source narrowly
- add dry-run output tests
- execute dry-run commands only after artifact snapshot
- do not execute real export
- do not execute `--record-manifest`
- do not execute CE
- do not modify wrapper
- do not add commands/options
- do not expand write surface

Phase 5.10 status: dry-run output wording has been integrated for `report export --dry-run` and `report bundle export --dry-run` only. Integration uses the existing output message helpers, keeps JSON output and real-write output unchanged, and does not change command parsing, approved roots, path guards, manifest behavior, bundle behavior, wrapper behavior, or write surface.

Phase 5.25 status: Phase 5 output wording final state summary exists. Candidate A/B/C wording integrations are completed at the human-readable output level, behavior/write surface remains unchanged, and any checkpoint is deferred to a separate validation gate.

## Stop Conditions

Stop if a future task includes:

- any implementation request in this contract phase
- any Python source modification in this contract phase
- any test modification in this contract phase
- any request to execute dry-run in this contract phase
- any request to execute real export
- any request to execute `--record-manifest`
- any request to add `--force`
- any request to add zip export
- any request to add wrapper export shortcut
- any request to change approved roots
- any request to run CE
- any unexpected source/test/runtime changes
