# Python Tooling Report Export Manifest Output Contract

## Purpose

This contract defines how a future implementation may integrate real-write output helpers into the `report export --record-manifest` path.

This phase is documentation-only:

- no Python source is modified
- no tests are modified
- no real write is executed
- no dry-run command is executed
- no write surface is expanded

## Current Baseline

Current stable boundary:

- Phase 5.17 Candidate A implementation completed
- Phase 5.18 Candidate A boundary smoke passed
- Candidate A is active only for real `report export` without `--record-manifest`
- Candidate B is not active yet
- manifest output integration is deferred
- bundle output integration is deferred
- command inventory: `49` commands
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable Python commands:
  - `report export`
  - `report bundle export`
- wrapper remains read-only
- no CE/runtime mutation exists in Python tooling
- no log/config/session/intake/baseline/registry writes were introduced
- zip export remains unsupported / fail-closed
- `--force` / overwrite remains unsupported

## Candidate B Integration Target

The only future integration target for this contract is:

```text
report export --record-manifest
```

Explicitly excluded:

- real `report export` without `--record-manifest`, already handled by Candidate A
- `report export --dry-run`
- `report bundle export`
- `report bundle export --dry-run`
- wrapper commands
- CE/runtime commands
- restore/write/config/session/baseline/intake commands

## Expected Future Output Semantics

Future `report export --record-manifest` output should include:

- `WRITE_COMPLETE`
- report output path
- manifest path
- `MANIFEST_RECORDED`
- `APPROVED_ROOT`
- `BUNDLE_NOT_CREATED`
- `CE_NOT_RUN`
- `WRAPPER_UNSUPPORTED`
- optional next safe manifest verification command

The output should make clear:

- a report file was written
- the manifest was recorded/appended because `--record-manifest` was used
- the manifest path is visible
- the output path was under an approved root
- no bundle was created
- CE was not run
- the read-only wrapper does not support export commands

The output must not suggest:

- wrapper export shortcut
- `--force`
- zip export
- unsafe path workaround
- bundle creation
- CE execution
- source manifest mutation outside the supported manifest record path

## Integration Constraints

Future implementation must:

- use the existing manifest-recorded helper from `report_output_messages.py`
- not change report file contents
- not change manifest record format
- not change manifest append semantics
- not change output path validation
- not change approved roots
- not change command parsing
- not change dry-run behavior
- not change bundle behavior
- not change JSON output unless separately planned
- not call wrapper
- not run CE
- not write logs/config/session/baseline/intake/registry
- not add `--force`
- not add zip export
- not add new commands/options

## Preferred Future Implementation Strategy

Prefer a minimal source change:

- locate the current `report export --record-manifest` human-readable success output path
- replace or supplement only the human-readable success message
- preserve all side effects exactly as before
- preserve manifest record schema and append behavior exactly as before
- preserve JSON behavior exactly as before if JSON output exists
- preserve Candidate A non-manifest behavior from Phase 5.17
- preserve dry-run behavior from Phase 5.10
- keep helper call close to the existing manifest write-complete branch
- do not refactor unrelated logic

## Future Test Contract

Future implementation tests should include helper-level and command-level validation.

### Helper/Unit Tests

- assert `WRITE_COMPLETE`
- assert report path
- assert manifest path
- assert `MANIFEST_RECORDED`
- assert `APPROVED_ROOT`
- assert `BUNDLE_NOT_CREATED`
- assert `CE_NOT_RUN`
- assert `WRAPPER_UNSUPPORTED`
- assert no unsafe wording such as wrapper export shortcut / `--force` / zip support

### Command-Level Validation

Only if separately authorized in the implementation task.

A future validation involving `--record-manifest` must:

- use an explicit approved output path with a unique `phase5_*` filename
- record absence/presence before run
- record manifest path and hash/state before run
- run exactly one `report export --record-manifest` command
- verify output wording tokens
- verify the expected report file exists if real write is authorized
- verify the manifest record is appended only as expected
- verify no bundle directory is created
- verify no CE run
- verify no unrelated log/config/session/baseline/intake/registry writes
- define cleanup policy explicitly
- never delete pre-existing user files
- verify final state according to cleanup policy

## Validation Policies

The future implementation task must choose one of these policies.

### Policy 1: Unit/Helper-Only Validation

Preferred if implementation can be tested without running `--record-manifest`:

- no real export execution
- no `--record-manifest` execution
- no dry-run execution
- no runtime artifacts
- helper/message tests only
- full pytest
- inventory invariants

### Policy 2: Manifest-Write Validation With Explicit Cleanup

Allowed only if separately authorized:

- explicit approved output path
- exactly one `report export --record-manifest` invocation
- no bundle export
- no CE
- cleanup policy stated before running
- artifact/hash checks before and after
- manifest append behavior explicitly verified

## Artifact Safety Plan For Future Manifest-Write Validation

If Policy 2 is used later, future validation must snapshot:

- target report output path
- `reports/python_tooling/full_status.md`
- `reports/python_tooling/manifest.jsonl`
- `reports/python_tooling/bundles`
- `docs/reports/python_tooling`
- `log/case_registry.jsonl`

If manifest exists before, record enough information to verify only the expected manifest append occurred.

If `log/case_registry.jsonl` exists before, record hash before and after.

No pre-existing user files/directories may be deleted.

## Risk Assessment

| Area | Behavior-change risk | Write-surface risk | Artifact complexity | Likely future files touched | Recommended validation policy | Allowed in next implementation? |
| --- | --- | --- | --- | --- | --- | --- |
| Human-readable manifest success message only | low | high | report file plus manifest append if real validation is used | `src/armedforces_tool/report_export.py`, tests | Policy 1 first; Policy 2 only if authorized | yes |
| Manifest record format | high | high | manifest schema/content | `src/armedforces_tool/report_export.py`, tests | separate manifest schema contract | no |
| Manifest append semantics | high | high | manifest append behavior | `src/armedforces_tool/report_export.py`, tests | separate manifest behavior contract | no |
| Report file content | high | medium | report markdown content | report preview/export modules, tests | separate content contract | no |
| JSON output changes | medium | low | none if unit-tested | `src/armedforces_tool/report_export.py`, tests | separate JSON contract | no |
| Bundle behavior | high | high | bundle directory/files | `src/armedforces_tool/report_bundle.py`, tests | Candidate C contract | no |
| Wrapper behavior | high | high | wrapper command surface | wrapper source/docs | wrapper write-capable contract | no |
| Approved roots | high | high | output path policy | path guard modules, tests | approved-root contract | no |
| Path guard | high | high | rejection behavior | path guard/export modules, tests | path guard contract | no |
| `--force` | high | high | overwrite behavior | export modules, tests | overwrite contract | no |
| Zip export | high | high | zip artifact | bundle modules, tests | zip export contract | no |

## Recommended Next Phase

Recommended next phase:

```text
Phase 5.20 - report export manifest output helper integration implementation
```

Preferred scope:

- narrow Python source change
- integrate helper into `report export --record-manifest` human-readable success output only
- no bundle export
- no wrapper changes
- no command/options added
- no write surface expansion
- validation policy must be chosen explicitly
- prefer unit/helper-only validation unless real manifest write is separately authorized

Phase 5.20 status: Candidate B integration is implemented for the human-readable success output of `report export --record-manifest`. The implementation uses helper/unit-only validation for this phase; no `--record-manifest` command was executed. Candidate A remains unchanged, bundle output integration remains deferred, and manifest schema, manifest append behavior, report content, path guards, approved roots, command parsing, JSON output, wrapper behavior, and write surface remain unchanged.

## Stop Conditions

Stop if a future task includes:

- any implementation in this contract phase
- any Python source modification in this contract phase
- any test modification in this contract phase
- any real export execution in this contract phase
- any `--record-manifest` execution
- any dry-run export execution
- any bundle export execution
- any request to change JSON output without separate plan
- any request to change manifest schema/append semantics
- any request to add `--force`
- any request to add zip export
- any request to add wrapper export shortcut
- any request to change approved roots
- any request to run CE
- any unexpected source/test/runtime changes
