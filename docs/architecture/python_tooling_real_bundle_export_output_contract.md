# Python Tooling Real Bundle Export Output Contract

## Purpose

This contract defines how a future implementation may integrate real-write output helpers into the real `report bundle export` path.

This phase is documentation-only:

- no Python source is modified
- no tests are modified
- no real bundle write is executed
- no dry-run command is executed
- no write surface is expanded

## Current Baseline

The current stable baseline is:

- Candidate A real `report export` output integration is implemented and boundary-smoked
- Candidate B `report export --record-manifest` output integration is implemented and boundary-smoked
- Candidate C is not active yet
- bundle output integration is deferred
- command inventory remains at `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable commands remain:
  - `report export`
  - `report bundle export`
- wrapper remains read-only
- no CE/runtime mutation is introduced by Python tooling
- no log/config/session/intake/baseline/registry writes are introduced
- zip export remains unsupported / fail-closed
- `--force` / overwrite remains unsupported

## Candidate C Integration Target

The only future integration target covered by this contract is:

```text
real report bundle export
```

Explicitly excluded:

- real `report export`
- `report export --record-manifest`
- `report export --dry-run`
- `report bundle export --dry-run`
- wrapper commands
- CE/runtime commands
- restore/write/config/session/baseline/intake commands
- zip export
- overwrite / `--force`

## Expected Future Output Semantics

Future real `report bundle export` human-readable output should include:

- `BUNDLE_EXPORT_COMPLETE`
- bundle directory path
- bundle manifest path
- index path
- copied report count, if available
- `SOURCE_UNCHANGED`
- `ZIP_UNSUPPORTED`
- `APPROVED_ROOT`
- `CE_NOT_RUN`
- `WRAPPER_UNSUPPORTED`
- optional next safe bundle verification command

The output should make clear:

- a bundle directory was written
- `bundle_manifest.json` was written inside the bundle directory
- `index.md` was written inside the bundle directory
- copied report count is visible if the implementation knows it
- source report/manifest state is unchanged unless supported behavior explicitly says otherwise
- no zip file was created
- the output path was under an approved root
- CE was not run
- the read-only wrapper does not support export commands

The output must not suggest:

- zip file creation
- wrapper export shortcut
- `--force`
- unsafe path workaround
- source manifest mutation unless explicitly supported
- CE execution
- approved-root bypass

## Integration Constraints

Future implementation must:

- use the existing bundle export helper from `report_output_messages.py`
- not change bundle directory structure
- not change `bundle_manifest.json` format
- not change `index.md` format
- not change copied report content
- not change source report/manifest behavior
- not change output path validation
- not change approved roots
- not change command parsing
- not change dry-run behavior
- not change Candidate A / Candidate B report export behavior
- not change JSON output unless separately planned
- not call wrapper
- not run CE
- not write logs/config/session/baseline/intake/registry
- not add `--force`
- not add zip export
- not add new commands/options

## Preferred Future Implementation Strategy

Prefer a minimal source change:

- locate the current real `report bundle export` human-readable success output path
- replace or supplement only the human-readable success message
- preserve all side effects exactly as before
- preserve bundle directory contents exactly as before
- preserve `bundle_manifest.json` and `index.md` content exactly as before
- preserve JSON behavior exactly as before if JSON output exists
- preserve dry-run behavior from Phase 5.10
- preserve Candidate A and Candidate B report export behavior
- keep helper call close to the existing bundle write-complete branch
- do not refactor unrelated logic

## Future Test Contract

Future implementation tests should include helper-level and command-level validation.

### Helper / Unit Tests

Helper tests should assert:

- `BUNDLE_EXPORT_COMPLETE`
- bundle directory path
- bundle manifest path
- index path
- copied report count if provided
- `SOURCE_UNCHANGED`
- `ZIP_UNSUPPORTED`
- `APPROVED_ROOT`
- `CE_NOT_RUN`
- `WRAPPER_UNSUPPORTED`
- no unsafe wording such as wrapper export shortcut / `--force` / zip support

### Command-Level Validation

Command-level validation is allowed only if separately authorized in the implementation task.

A future validation involving real bundle export must:

- use an explicit approved output directory with a unique `phase5_*` name
- record absence/presence before run
- run exactly one real `report bundle export` command
- verify output wording tokens
- verify expected bundle directory exists if real write is authorized
- verify expected `bundle_manifest.json` exists if real write is authorized
- verify expected `index.md` exists if real write is authorized
- verify no zip is created
- verify no CE run
- verify no unrelated log/config/session/baseline/intake/registry writes
- define cleanup policy explicitly
- never delete pre-existing user files
- verify final state according to cleanup policy

## Validation Policies

Future implementation must choose one validation policy.

### Policy 1 - Unit / Helper-Only Validation

Preferred if implementation can be tested without running real bundle export.

- no real bundle export execution
- no dry-run execution
- no runtime artifacts
- helper/message tests only
- full pytest
- inventory invariants

### Policy 2 - Real Bundle Write Validation With Explicit Cleanup

Allowed only if separately authorized.

- explicit approved bundle directory
- exactly one real `report bundle export` invocation
- no report export
- no `--record-manifest`
- no CE
- no zip
- cleanup policy stated before running
- artifact/hash checks before and after
- bundle artifact expectations explicitly verified

## Artifact Safety Plan For Future Real Bundle Validation

If Policy 2 is used later, future validation must snapshot:

- target bundle directory
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
| Human-readable bundle success message only | low | medium | bundle directory already written by existing command | `src/armedforces_tool/report_bundle.py`, tests | Policy 1 first; Policy 2 only if authorized | yes |
| Bundle directory structure | high | high | directory tree | `src/armedforces_tool/report_bundle.py`, tests | separate bundle structure contract | no |
| `bundle_manifest.json` content | high | high | bundle manifest content | `src/armedforces_tool/report_bundle.py`, tests | separate manifest contract | no |
| `index.md` content | high | high | bundle index content | `src/armedforces_tool/report_bundle.py`, tests | separate index contract | no |
| Copied reports | high | high | report file copies | `src/armedforces_tool/report_bundle.py`, tests | separate copied-report contract | no |
| Source report/manifest behavior | high | high | source state | bundle/report modules, tests | separate source-state contract | no |
| JSON output changes | medium | low | none if unit-tested | `src/armedforces_tool/report_bundle.py`, tests | separate JSON contract | no |
| Wrapper behavior | high | high | wrapper command surface | wrapper source/docs | wrapper write-capable contract | no |
| Approved roots | high | high | output path policy | bundle/path guard modules, tests | approved-root contract | no |
| Path guard | high | high | rejection behavior | bundle/path guard modules, tests | path guard contract | no |
| `--force` | high | high | overwrite behavior | bundle modules, tests | overwrite contract | no |
| Zip export | high | high | zip artifact | `src/armedforces_tool/report_bundle.py`, tests | zip export contract | no |

## Recommended Next Phase

Recommended next phase:

```text
Phase 5.23 - real bundle export output helper integration implementation
```

Preferred scope:

- narrow Python source change
- integrate helper into real `report bundle export` human-readable success output only
- no report export changes
- no wrapper changes
- no command/options added
- no write surface expansion
- validation policy must be chosen explicitly
- prefer unit/helper-only validation unless real bundle write is separately authorized

Phase 5.23 status: Candidate C helper integration is implemented for the human-readable success output of real `report bundle export`. Validation used the helper/unit-only policy; no real bundle export command was executed. Candidate A and Candidate B remain unchanged. Bundle directory structure, `bundle_manifest.json`, `index.md`, copied report content, source report/manifest behavior, path guards, approved roots, command parsing, JSON output, wrapper behavior, and write surface remain unchanged.

Phase 5.25 status: Phase 5 output wording final state summary exists. Candidate A/B/C wording integrations are completed at the human-readable output level, behavior/write surface remains unchanged, and any checkpoint is deferred to a separate validation gate.

## Stop Conditions

Stop if a future task includes:

- any implementation in this contract phase
- any Python source modification in this contract phase
- any test modification in this contract phase
- any real bundle export execution in this contract phase
- any report export execution
- any `--record-manifest` execution
- any dry-run export execution
- any request to change JSON output without separate plan
- any request to change bundle directory structure
- any request to change `bundle_manifest.json` or `index.md` format
- any request to add `--force`
- any request to add zip export
- any request to add wrapper export shortcut
- any request to change approved roots
- any request to run CE
- any unexpected source/test/runtime changes
