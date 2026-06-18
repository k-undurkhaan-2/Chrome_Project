# Python Tooling Real Report Export Output Contract

## Purpose

This contract defines how a future implementation may integrate real-write output helpers into the real `report export` path without `--record-manifest`.

This phase is documentation-only:

- no Python source is modified
- no tests are modified
- no real write is executed
- no dry-run command is executed
- no write surface is expanded

## Current Baseline

Current stable boundary:

- Phase 5.15 real-write output integration gate completed
- Candidate A selected for a dedicated contract
- real-write helpers already exist
- real-write helpers are not wired into real export paths
- `report export --dry-run` wording is already integrated and verified no-write
- real `report export` output integration is not active
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

## Candidate A Integration Target

The only future integration target for this contract is:

```text
real report export
```

Explicitly excluded:

- `report export --record-manifest`
- `report export --dry-run`
- `report bundle export`
- `report bundle export --dry-run`
- wrapper commands
- CE/runtime commands
- restore/write/config/session/baseline/intake commands

## Expected Future Output Semantics

Future real `report export` output should include:

- `WRITE_COMPLETE`
- report output path
- `APPROVED_ROOT`
- `MANIFEST_NOT_WRITTEN`
- `BUNDLE_NOT_CREATED`
- `CE_NOT_RUN`
- `WRAPPER_UNSUPPORTED`
- optional next safe read-only verification command

The output should make clear:

- a report file was written
- the output path was under an approved root
- no manifest was written because `--record-manifest` was not used
- no bundle was created
- CE was not run
- the read-only wrapper does not support export commands

The output must not suggest:

- wrapper export shortcut
- `--force`
- zip export
- unsafe path workaround
- manifest write unless `--record-manifest` is used
- bundle creation
- CE execution

## Integration Constraints

Future implementation must:

- use the existing real report export helper from `report_output_messages.py`
- not change report file contents
- not change output path validation
- not change approved roots
- not change manifest write behavior
- not change command parsing
- not change JSON output unless separately planned
- not call wrapper
- not run CE
- not write logs/config/session/baseline/intake/registry
- not add `--force`
- not add zip export
- not add new commands/options

## Preferred Future Implementation Strategy

Prefer a minimal source change:

- locate the current real `report export` success output path
- replace or supplement only the human-readable success message
- preserve all side effects exactly as before
- preserve JSON behavior exactly as before if JSON output exists
- preserve dry-run behavior from Phase 5.10
- keep helper call close to the existing write-complete branch
- do not refactor unrelated logic

## Future Test Contract

Future implementation tests should include helper-level and command-level validation.

### Helper/Unit Tests

- assert `WRITE_COMPLETE`
- assert report path
- assert `APPROVED_ROOT`
- assert `MANIFEST_NOT_WRITTEN`
- assert `BUNDLE_NOT_CREATED`
- assert `CE_NOT_RUN`
- assert `WRAPPER_UNSUPPORTED`
- assert no unsafe wording such as wrapper export shortcut / `--force` / zip support

### Real Command Validation

Only if separately authorized in the implementation task.

A future real-write validation must:

- use an explicit approved output path with a unique `phase5_*` filename
- record absence/presence before run
- run exactly one real `report export` command without `--record-manifest`
- verify output wording tokens
- verify the expected report file exists if real write is authorized
- verify manifest is not created/appended unless pre-existing state is explicitly recorded
- verify no bundle directory is created
- verify no CE run
- verify no log/config/session/baseline/intake/registry writes
- define cleanup policy explicitly
- never delete pre-existing user files
- verify final state according to cleanup policy

## Validation Policies

The future implementation task must choose one of these policies.

### Policy 1: Unit/Helper-Only Validation

Preferred if implementation can be tested without real export:

- no real export execution
- no dry-run execution
- no runtime artifacts
- helper/message tests only
- full pytest
- inventory invariants

### Policy 2: Real-Write Validation With Explicit Cleanup

Allowed only if separately authorized:

- explicit approved path
- one real `report export` invocation
- no `--record-manifest`
- no bundle export
- no CE
- cleanup policy stated before running
- artifact/hash checks before and after

## Artifact Safety Plan For Future Real-Write Validation

If Policy 2 is used later, future validation must snapshot:

- target report output path
- `reports/python_tooling/full_status.md`
- `reports/python_tooling/manifest.jsonl`
- `reports/python_tooling/bundles`
- `docs/reports/python_tooling`
- `log/case_registry.jsonl`

If `log/case_registry.jsonl` exists before, record hash before and after.

No pre-existing user files/directories may be deleted.

## Risk Assessment

| Area | Behavior-change risk | Write-surface risk | Artifact complexity | Likely future files touched | Recommended validation policy | Allowed in next implementation? |
| --- | --- | --- | --- | --- | --- | --- |
| Human-readable success message only | low | medium | single report file if real validation is used | `src/armedforces_tool/report_export.py`, tests | Policy 1 first; Policy 2 only if authorized | yes |
| JSON output changes | medium | low | none if unit-tested | `src/armedforces_tool/report_export.py`, tests | separate JSON contract | no |
| Report file content | high | medium | report file content changes | report preview/export modules, tests | separate content contract | no |
| Manifest behavior | high | high | manifest append/write | `report_export.py`, tests | Candidate B contract | no |
| Bundle behavior | high | high | bundle directory/files | `report_bundle.py`, tests | Candidate C contract | no |
| Wrapper behavior | high | high | wrapper command surface | wrapper source/docs | wrapper write-capable contract | no |
| Approved roots | high | high | output path policy | path guard modules, tests | approved-root contract | no |
| Path guard | high | high | rejection behavior | path guard/export modules, tests | path guard contract | no |
| `--force` | high | high | overwrite behavior | export modules, tests | overwrite contract | no |
| Zip export | high | high | zip artifact | bundle modules, tests | zip export contract | no |

## Recommended Next Phase

Recommended next phase:

```text
Phase 5.17 - real report export output helper integration implementation
```

Preferred scope:

- narrow Python source change
- integrate helper into real `report export` human-readable success output only
- no `--record-manifest`
- no bundle export
- no wrapper changes
- no command/options added
- no write surface expansion
- validation policy must be chosen explicitly

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
- any request to add `--force`
- any request to add zip export
- any request to add wrapper export shortcut
- any request to change approved roots
- any request to run CE
- any unexpected source/test/runtime changes
