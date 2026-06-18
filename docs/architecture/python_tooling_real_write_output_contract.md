# Python Tooling Real-Write Output Contract

## Purpose

This document defines a future real-write output wording contract for Python report and bundle export commands.

This phase is documentation-only:

- real-write output wording is not implemented here
- no Python source is modified
- no tests are modified
- no real export command is executed
- no dry-run export command is executed
- no write surface is expanded

## Current Baseline

Current stable boundary:

- Phase 5.10 dry-run wording implementation completed
- Phase 5.11 dry-run output boundary smoke passed
- dry-run wording is integrated and verified no-write
- real-write output remains unchanged
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

## Contract Principles

Real-write output wording polish must not:

- change real write behavior
- add commands or options
- add output roots
- add `--force`
- add zip export
- route export through the read-only wrapper
- run CE
- write logs/config/session/baseline/intake/registry
- change manifest write behavior
- change bundle write behavior

Real-write output wording polish must:

- make written artifacts explicit
- make non-created artifacts explicit
- make approved-root status explicit
- make CE exclusion explicit
- make wrapper exclusion explicit
- avoid unsafe workaround hints
- preserve concise operator-facing output

## Integration Targets

The only future real-write output wording targets are:

- real `report export`
- `report export --record-manifest`
- real `report bundle export`

Explicitly excluded:

- dry-run commands, already handled separately
- wrapper commands
- CE/runtime commands
- restore/write/config/session/baseline/intake commands
- zip export
- overwrite / `--force`

## Real Report Export Output Contract

Future real `report export` output should include semantic fields:

- `WRITE_COMPLETE` or equivalent
- report output path
- approved-root confirmation / `APPROVED_ROOT`
- manifest not written unless `--record-manifest` is used
- no bundle created / `BUNDLE_NOT_CREATED`
- no CE run / `CE_NOT_RUN`
- wrapper unsupported reminder / `WRAPPER_UNSUPPORTED`
- next safe read-only verification command, if appropriate

It must not:

- imply manifest append unless `--record-manifest` was used
- imply bundle creation
- imply CE execution
- suggest wrapper export shortcuts
- suggest unsafe path workarounds
- suggest `--force`

## Real Report Export With Manifest Output Contract

Future `report export --record-manifest` output should include semantic fields:

- `WRITE_COMPLETE` or equivalent
- report output path
- manifest path
- manifest append/record status / `MANIFEST_RECORDED`
- approved-root confirmation / `APPROVED_ROOT`
- no bundle created / `BUNDLE_NOT_CREATED`
- no CE run / `CE_NOT_RUN`
- wrapper unsupported reminder / `WRAPPER_UNSUPPORTED`
- next safe manifest verify command, if appropriate

It must not:

- imply bundle creation
- imply CE execution
- hide manifest write behavior
- suggest wrapper export shortcuts
- suggest unsafe path workarounds
- suggest `--force`

## Real Bundle Export Output Contract

Future real `report bundle export` output should include semantic fields:

- `BUNDLE_EXPORT_COMPLETE` or equivalent
- bundle directory path
- bundle manifest path
- index path
- copied report count, if available
- approved-root confirmation / `APPROVED_ROOT`
- source report/manifest unchanged unless explicitly supported behavior says otherwise / `SOURCE_UNCHANGED`
- zip not created / `ZIP_UNSUPPORTED`
- no CE run / `CE_NOT_RUN`
- wrapper unsupported reminder / `WRAPPER_UNSUPPORTED`
- next safe bundle verify command, if appropriate

It must not:

- imply zip creation
- imply source manifest mutation unless explicitly supported
- imply CE execution
- suggest wrapper export shortcuts
- suggest unsafe path workarounds
- suggest `--force`

## Error/Rejection Boundary Reminder

Earlier rejection wording contracts remain authoritative:

- `BAD_PATH` must remain explicit
- overwrite rejection must remain explicit
- `--force` remains unsupported
- zip export remains unsupported
- no unsafe workaround should be suggested

This document does not redefine rejection wording. It only defines future success-path real-write output wording.

## Stable Message Tokens

Recommended future stable tokens:

- `WRITE_COMPLETE`
- `BUNDLE_EXPORT_COMPLETE`
- `APPROVED_ROOT`
- `WRAPPER_UNSUPPORTED`
- `CE_NOT_RUN`
- `ZIP_UNSUPPORTED`
- `MANIFEST_RECORDED`
- `MANIFEST_NOT_WRITTEN`
- `BUNDLE_NOT_CREATED`
- `SOURCE_UNCHANGED`

Future tests should assert stable semantic tokens and concise field presence, not long exact paragraphs.

## Future Implementation Approach

Preferred approach:

- reuse `src/armedforces_tool/report_output_messages.py`
- add or extend helper functions only where needed
- keep command behavior unchanged
- keep command parsing unchanged
- keep path guard unchanged
- keep approved roots unchanged
- keep manifest write behavior unchanged
- keep bundle write behavior unchanged
- do not alter JSON output unless separately planned
- do not call helpers from the wrapper

## Future Test Contract

Future implementation tests should include:

- unit/helper tests for new real-write message helpers
- real-write command output tests only if separately authorized
- artifact safety snapshot before/after
- approved-root explicit output paths
- cleanup policy explicitly stated if any real write validation is authorized
- inventory invariants:
  - `writes_files_count = 2`
  - `runs_ce_count = 0`
- wrapper boundary tests remain valid

Tests must not execute real writes unless a future implementation task explicitly authorizes them.

## Validation Stages For Future Implementation

### Stage 1: Helper-Only Implementation

Preferred next implementation slice:

- implement/extend real-write message helper functions
- test helper strings only
- no real export execution
- no dry-run execution required
- no runtime artifacts

### Stage 2: Real-Write Output Integration

Only if separately authorized:

- integrate helpers into real-write output paths
- run real write only under explicit approved output paths
- record artifact snapshot before/after
- cleanup policy explicitly stated
- no CE
- no wrapper
- no `--force`
- no zip
- no log/config/session/baseline/intake/registry writes

### Stage 3: Final Boundary Smoke

Required after integration:

- full pytest
- status overview
- command inventory
- wrapper read-only checks
- artifact/hash checks
- final clean working tree

## Risk Assessment

| Area | Behavior-change risk | Write-surface risk | Likely future files touched | Required validation | Allowed as next implementation? |
| --- | --- | --- | --- | --- | --- |
| Helper-only real report export message | low | low | `src/armedforces_tool/report_output_messages.py`, tests | helper unit tests only | yes |
| Helper-only report export with manifest message | low | low | `src/armedforces_tool/report_output_messages.py`, tests | helper unit tests only | yes |
| Helper-only bundle export message | low | low | `src/armedforces_tool/report_output_messages.py`, tests | helper unit tests only | yes |
| Real report export integration | medium | medium | `src/armedforces_tool/report_export.py`, tests | explicit real-write smoke with cleanup | no, separate gate |
| Real manifest export integration | medium | medium | `src/armedforces_tool/report_export.py`, tests | explicit real-write + manifest smoke with cleanup | no, separate gate |
| Real bundle export integration | medium | medium | `src/armedforces_tool/report_bundle.py`, tests | explicit bundle write smoke with cleanup | no, separate gate |
| JSON output changes | medium | low | `src/armedforces_tool`, tests | JSON compatibility tests | no |
| Wrapper integration | high | high | wrapper docs/source | wrapper boundary review | no |
| Zip export | high | high | `src/armedforces_tool/report_bundle.py`, tests | new write-capable contract | no |
| `--force` | high | high | `src/armedforces_tool`, tests | new overwrite contract | no |

## Recommended Next Implementation Slice

Recommended next phase:

```text
Phase 5.13 - real-write output helper extension
```

Preferred scope:

- helper-only
- extend `report_output_messages` with real-write helper functions if not already complete
- test helper output only
- no real export execution
- no dry-run export execution
- no write surface expansion

Actual real-write path integration should remain deferred until after helper-only extension and a separate explicit gate.

## Stop Conditions

Stop if a future task includes:

- any implementation request in this contract phase
- any Python source modification in this contract phase
- any test modification in this contract phase
- any request to execute real export in this contract phase
- any request to execute `--record-manifest`
- any request to execute dry-run export in this contract phase
- any request to add `--force`
- any request to add zip export
- any request to add wrapper export shortcut
- any request to change approved roots
- any request to run CE
- any unexpected source/test/runtime changes
