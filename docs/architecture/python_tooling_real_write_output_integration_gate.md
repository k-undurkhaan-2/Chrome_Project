# Python Tooling Real-Write Output Integration Gate

## Purpose

This document is a planning gate before any real-write output helper integration.

This phase is documentation-only:

- no Python source is modified
- no tests are modified
- no real write is executed
- no dry-run command is executed
- no write surface is expanded

The purpose is to define whether and how future phases may wire existing real-write output helpers into real report and bundle export execution paths.

## Current Baseline

Current stable boundary:

- Phase 5.13 helper-only real-write output helpers completed
- Phase 5.14 helper boundary smoke passed
- real-write helpers are still helper-only
- real-write output integration is not active
- command inventory: `49` commands
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable Python commands:
  - `report export`
  - `report bundle export`
- wrapper remains read-only
- wrapper does not wrap write-capable export commands
- no CE/runtime mutation exists in Python tooling
- no log/config/session/intake/baseline/registry writes were introduced
- zip export remains unsupported / fail-closed
- `--force` / overwrite remains unsupported

## Integration Candidates

### Candidate A: Real Report Export Output Integration

Target:

- real `report export`

Future integration may display:

- `WRITE_COMPLETE`
- report output path
- `APPROVED_ROOT`
- `MANIFEST_NOT_WRITTEN`
- `BUNDLE_NOT_CREATED`
- `CE_NOT_RUN`
- `WRAPPER_UNSUPPORTED`

Must not change:

- report file contents
- output path validation
- approved roots
- manifest write behavior
- command parsing
- JSON output unless separately planned

### Candidate B: Report Export With Manifest Output Integration

Target:

- `report export --record-manifest`

Future integration may display:

- `WRITE_COMPLETE`
- report output path
- manifest path
- `MANIFEST_RECORDED`
- `APPROVED_ROOT`
- `BUNDLE_NOT_CREATED`
- `CE_NOT_RUN`
- `WRAPPER_UNSUPPORTED`

Must not change:

- manifest record format
- manifest append semantics
- report write behavior
- path guard behavior
- command parsing
- JSON output unless separately planned

### Candidate C: Real Bundle Export Output Integration

Target:

- real `report bundle export`

Future integration may display:

- `BUNDLE_EXPORT_COMPLETE`
- bundle directory path
- bundle manifest path
- index path
- copied report count if available
- `SOURCE_UNCHANGED`
- `ZIP_UNSUPPORTED`
- `APPROVED_ROOT`
- `CE_NOT_RUN`
- `WRAPPER_UNSUPPORTED`

Must not change:

- bundle directory contents
- `bundle_manifest.json` format
- `index.md` format
- source report/manifest behavior
- path guard behavior
- command parsing
- JSON output unless separately planned

## Recommended Integration Order

Recommended order:

1. Candidate A: real `report export` output integration
2. Candidate B: `report export --record-manifest` output integration
3. Candidate C: real `report bundle export` output integration

Rationale:

- report export without manifest is the smallest real-write surface
- manifest append adds another write surface and should be separate
- bundle export creates multiple files/directories and should remain last

## Required Gate Before Implementation

Before any future implementation, require:

- explicit task naming the selected candidate
- explicit approved output path policy
- artifact snapshot plan
- cleanup policy if real writes are used in validation
- confirmation that wrapper remains read-only
- confirmation that no CE is run
- confirmation that no `--force` or zip support is added
- confirmation that no commands or options are added

## Future Implementation Constraints

Any future implementation must:

- use existing real-write helpers from `report_output_messages.py`
- avoid changing business logic
- avoid changing command parsing
- avoid changing path guard behavior
- avoid changing approved roots
- avoid changing report content
- avoid changing manifest schema
- avoid changing bundle content
- avoid changing JSON output unless separately planned
- not call wrapper
- not call CE
- not write logs/config/session/baseline/intake/registry
- not add `--force`
- not add zip export

## Future Validation Contract

For each future implementation slice, validation must include:

- pre-check clean git status
- status overview `SAFE`
- command inventory:
  - `writes_files_count = 2`
  - `runs_ce_count = 0`
- targeted tests for output tokens
- full pytest
- pre/post artifact snapshot
- explicit output path under an approved root if real write validation is authorized
- registry hash comparison if `log/case_registry.jsonl` exists
- final clean status
- proof wrapper source unchanged
- proof no CE run

## Real-Write Validation Policy

Because this involves real write-capable commands, any future implementation task must choose one validation policy.

### Policy 1: Helper/Unit-Only Validation

Preferred first:

- do not execute real write
- test helper output and formatting integration through mocked/unit path if possible
- no runtime artifacts
- no cleanup needed

### Policy 2: Real-Write Validation With Explicit Cleanup

Only if separately authorized:

- use explicit approved output path with a unique `phase5_*` target
- record target absence before run
- execute exactly the authorized real-write command
- verify output wording
- verify artifacts expected for that command only
- cleanup generated test artifacts only if explicitly allowed in that future task
- do not delete pre-existing user files
- verify final artifact state according to the cleanup policy
- never run CE
- never use wrapper

## Explicit Non-Goals

This planning gate does not authorize:

- implementation
- real export execution
- dry-run execution
- `--record-manifest` execution
- source modifications
- test modifications
- new commands
- new options
- `--force`
- zip export
- wrapper export shortcuts
- approved-root changes
- path guard changes
- CE automation
- runtime write/restore migration
- log/config/session/baseline/intake/registry writes

## Risk Assessment

| Candidate | Write-surface risk | Behavior-change risk | Artifact complexity | Likely future files touched | Recommended validation policy | Recommended priority |
| --- | --- | --- | --- | --- | --- | --- |
| Real report export output integration | medium | medium | single report file | `src/armedforces_tool/report_export.py`, tests | Policy 1 first; Policy 2 only if authorized | 1 |
| Report export with manifest output integration | medium | medium | report file plus manifest append | `src/armedforces_tool/report_export.py`, tests | Policy 1 first; Policy 2 only if authorized | 2 |
| Real bundle export output integration | high | medium | bundle directory with multiple files | `src/armedforces_tool/report_bundle.py`, tests | Policy 1 first; Policy 2 only if authorized | 3 |
| JSON output changes | low | medium | none if read-only tests | `src/armedforces_tool`, tests | separate JSON compatibility contract | defer |
| Wrapper export shortcuts | high | high | possible write-capable wrapper surface | wrapper docs/source | new wrapper write-capable contract | no |
| Zip export | high | high | zip archive plus metadata | `src/armedforces_tool/report_bundle.py`, tests | new zip export contract | no |
| `--force` | high | high | overwrite behavior | `src/armedforces_tool`, tests | new overwrite contract | no |

## Recommended Next Phase

Recommended next phase:

```text
Phase 5.16 - real report export output integration contract
```

Scope:

- docs-only contract for Candidate A
- no source changes
- no real write execution
- define exact helper integration points and validation policy

Do not jump directly to implementation unless explicitly authorized.

Phase 5.16 status: `docs/architecture/python_tooling_real_report_export_output_contract.md` now defines the dedicated Candidate A contract. Candidate A remains docs-only, and the next possible phase is Candidate A implementation with an explicit validation policy.

Phase 5.17 status: Candidate A implementation completed under helper/unit-only validation. Candidate B (`report export --record-manifest`) and Candidate C (`report bundle export`) remain deferred.

Phase 5.19 status: Candidate B now has a dedicated contract in `docs/architecture/python_tooling_report_export_manifest_output_contract.md`. The staged order remains Candidate A, Candidate B, Candidate C; Candidate C remains deferred.

Phase 5.20 status: Candidate B implementation completed under helper/unit-only validation. Candidate C remains deferred.

Phase 5.22 status: Candidate C now has a dedicated contract in `docs/architecture/python_tooling_real_bundle_export_output_contract.md`. The staged order Candidate A/B/C is fully contracted, and Candidate C implementation remains deferred.

Phase 5.23 status: Candidate C implementation completed under helper/unit-only validation. The staged A/B/C real-write wording integrations are now implemented at the human-readable output level; real-write validation remains separate unless explicitly authorized.

Phase 5.25 status: Phase 5 output wording final state summary exists. Candidate A/B/C wording integrations are completed at the human-readable output level, behavior/write surface remains unchanged, and any checkpoint is deferred to a separate validation gate.

## Stop Conditions

Stop if a future task includes:

- any implementation request in this gate phase
- any Python source modification in this gate phase
- any test modification in this gate phase
- any request to execute real export in this gate phase
- any request to execute `--record-manifest`
- any request to execute dry-run export
- any request to add `--force`
- any request to add zip export
- any request to add wrapper export shortcut
- any request to change approved roots
- any request to run CE
- any unexpected source/test/runtime changes
