# Python Tooling Rejection-Path Wording Policy

## Purpose

This document defines the Phase 7.1 policy for future rejection-path and fail-closed wording in Python tooling.

It is a policy contract only. It does not implement wording changes, does not add commands or options, does not authorize report or bundle writes, does not change wrapper behavior, and does not change CE/runtime behavior.

The goal is to make future failure messages more actionable without weakening existing safety boundaries.

## Baseline

Current checkpoint baseline:

```text
python-tooling-phase3-final-checkpoint-20260616
python-tooling-powershell-wrapper-readonly-checkpoint-20260616
python-tooling-output-wording-checkpoint-20260618
python-tooling-real-write-output-validation-checkpoint-20260619
```

Current expected boundaries:

- command inventory remains approximately `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable Python commands remain:
  - `report export`
  - `report bundle export`
- read-only PowerShell wrapper remains read-only
- no wrapper export shortcut exists
- no CE/runtime mutation is migrated into Python tooling
- zip export remains unsupported
- `--force` / overwrite remains unsupported
- approved roots and protected-path guards remain unchanged

## Rejection-Path Categories

Future wording work should classify rejection output into explicit categories. Each category should state what failed, why it failed, what was not written, and what the operator should do next.

### Path Guard / BAD_PATH

Applies to:

- output path outside approved roots
- path traversal
- protected roots such as `log/`, `src/`, `tests/`, `docs/codex_tasks/`
- protected baseline/report locations not authorized by the command contract

Expected wording:

- include `BAD_PATH`
- name the rejected path role, such as report output, manifest output, source report, source manifest, or bundle output
- state that no report, manifest, bundle, log, config, registry, baseline, session, or intake file was written
- avoid suggesting path guard bypasses

### Existing Output / Overwrite Refused

Applies to:

- target report already exists
- target bundle directory already exists
- target manifest or bundle artifact would overwrite an existing file

Expected wording:

- include a stable token such as `OUTPUT_EXISTS` or `OVERWRITE_REFUSED`
- state that overwrite is unsupported unless a separately contracted behavior exists
- state that `--force` is unsupported where relevant
- state that no replacement write happened
- avoid recommending deletion of user files as an automatic fix

### Force Unsupported

Applies to:

- `--force` supplied to commands where force is explicitly unsupported
- future attempts to add force semantics without a contract

Expected wording:

- include `FORCE_UNSUPPORTED`
- state that overwrite is deliberately fail-closed
- state that a future force behavior would require a separate policy, tests, smoke validation, and checkpoint

### Zip Unsupported

Applies to:

- bundle export requests that ask for zip output
- any future zip-like archive output before a zip contract exists

Expected wording:

- include `ZIP_UNSUPPORTED`
- state that directory bundle export is the supported real-write bundle form
- state that no zip, bundle directory, `bundle_manifest.json`, or `index.md` was created

### Invalid Option Combination

Applies to:

- `--manifest-out` without `--record-manifest`
- `--source-manifest` without `--source-report`
- incompatible dry-run and real-write options
- options that only make sense in a specific command mode

Expected wording:

- include `INVALID_OPTION_COMBINATION`
- identify the invalid option
- identify the required companion option or mode
- state that the command failed closed before any write
- state that no default production path was mutated

### Missing Or Invalid Source Inputs

Applies to:

- missing source report for bundle export
- missing source manifest when explicitly supplied
- source path is a directory instead of a file
- source path is outside approved readable boundaries
- source input cannot be parsed or verified

Expected wording:

- include a stable token such as `SOURCE_MISSING`, `SOURCE_INVALID`, or `SOURCE_UNREADABLE`
- name the failed source role
- state that no bundle was created
- state that source files were not modified
- reserve `SOURCE_UNCHANGED` for successful verification output, not source rejection output

### Wrapper Unsupported

Applies to:

- attempts to use the read-only PowerShell wrapper for write-capable report or bundle export
- attempts to add wrapper export shortcuts without a policy phase

Expected wording:

- include `WRAPPER_UNSUPPORTED`
- state that the wrapper is read-only
- state that write-capable commands require direct Python invocation and explicit task authorization
- state that no Python write-capable command was dispatched by the wrapper

### CE Not Run / Runtime Out Of Scope

Applies to:

- any report or bundle command where an operator might expect CE/runtime action
- future rejection messages where CE/runtime remains outside the command boundary

Expected wording:

- include `CE_NOT_RUN`
- state that no CE command was run
- state that no runtime write, restore, baseline save, diagnostic mutation, case intake mutation, or local config mutation was performed

### Dry-Run No-Write

Applies to:

- `report export --dry-run`
- `report bundle export --dry-run`
- future dry-run-only planning commands

Expected wording:

- include `DRY_RUN`
- include `NO_FILES_WRITTEN`
- describe the planned output path and approved root
- avoid success-write tokens such as `WRITE_COMPLETE`, `MANIFEST_RECORDED`, or `BUNDLE_EXPORT_COMPLETE`
- state that no report, manifest, bundle, log, config, registry, baseline, session, or intake file was written

## Token Policy

Tokens should be stable enough for tests, smoke checks, and operator grep/search.

Existing or recommended tokens:

- `BAD_PATH`
- `OUTPUT_EXISTS`
- `OVERWRITE_REFUSED`
- `FORCE_UNSUPPORTED`
- `ZIP_UNSUPPORTED`
- `INVALID_OPTION_COMBINATION`
- `SOURCE_MISSING`
- `SOURCE_INVALID`
- `SOURCE_UNREADABLE`
- `WRAPPER_UNSUPPORTED`
- `CE_NOT_RUN`
- `DRY_RUN`
- `NO_FILES_WRITTEN`
- `APPROVED_ROOT`

Rules:

- do not introduce a new token when an existing token already expresses the condition
- do not emit success-write tokens in fail-closed output
- do not emit fail-closed tokens in success output unless the message explicitly describes a skipped optional feature
- keep JSON output backward-compatible unless a separate contract authorizes a schema change
- document and test every new token
- prefer exact uppercase snake-case tokens

## Wording Principles

Future rejection wording should follow these principles:

- concise enough for PowerShell and CLI output
- explicit about the failed gate
- explicit about whether any file was written
- explicit about CE/runtime not being run
- explicit about wrapper limitations when the wrapper is involved
- distinguish path rejection from overwrite rejection
- distinguish dry-run no-write from fail-closed rejection
- avoid raw stack traces for expected operator mistakes
- avoid suggesting unsafe workarounds
- avoid implying production/default workflows are authorized by isolated validation work

## Testing Policy

Future implementation slices must test rejection wording without creating runtime artifacts.

Required test themes:

- expected token is present
- unrelated success tokens are absent
- command fails nonzero where appropriate
- no report, manifest, bundle, log, registry, baseline, session, intake, or local config file is written
- JSON output remains stable where the command supports JSON
- dry-run output remains no-write
- wrapper rejection does not dispatch direct Python write-capable commands
- path guard tests use pytest temporary directories or tracked fixtures only

Tests must not:

- use production report or manifest files
- create `reports/python_tooling/validation/`
- create `reports/python_tooling/bundles/`
- write default `reports/python_tooling/manifest.jsonl`
- run CE
- run real report export or real bundle export unless a future explicitly authorized validation task allows it

## Future Implementation Slices

Recommended sequence:

1. `Phase 7.2A-contract` - invalid option combination wording contract.
2. `Phase 7.2A-implementation` - improve `--manifest-out` without `--record-manifest` fail-closed wording.
3. Missing source input wording for bundle export.
4. Zip unsupported wording.
5. Existing output / overwrite refused wording.
6. BAD_PATH / protected path wording.
7. Wrapper unsupported wording audit.

Each implementation slice should be narrow, test-backed, and independently reviewable.

## Boundaries

This policy does not authorize:

- new commands
- new options
- write-capable wrapper behavior
- CE automation
- runtime write/restore migration
- report or bundle write execution
- zip export
- `--force`
- approved-root expansion
- protected-path weakening
- production/default report, manifest, or bundle mutation
- JSON schema changes without a separate contract

## Stop Conditions

Stop future rejection-path wording work if any of these occur:

- implementation requires a new write surface
- implementation requires real report or bundle writes
- implementation requires CE
- implementation changes path guards
- implementation expands approved roots
- implementation enables zip export or `--force`
- implementation changes wrapper read-only behavior
- tests require runtime logs, baseline files, local config, session state, intake journals, or registry writes
- output wording would make a fail-closed command look successful

## Recommended Next Phase

Default next phase:

```text
Phase 7.2A-contract - invalid option combination wording contract
```

First target:

```text
--manifest-out without --record-manifest
```

Rationale:

- it is a narrow rejection path
- it is already known from Candidate B isolated manifest support
- it should not require real writes
- it can be tested with command argument parsing and fail-closed assertions

## Phase 7.2A Contract Status

The invalid option combination wording contract exists at:

```text
docs/architecture/python_tooling_invalid_option_combination_wording_contract.md
```

The first target remains:

```text
--manifest-out without --record-manifest
```

Recommended next phase:

```text
Phase 7.2A - invalid option combination wording implementation
```

Implementation note:

- Phase 7.2A implementation adds human-readable rejection wording for this invalid option combination.
- The wording uses `INVALID_OPTION_COMBINATION` and `NO_FILES_WRITTEN`.
- It does not add a command or option and does not authorize real writes.

## Phase 7.2B Contract Status

The missing source input wording contract exists at:

```text
docs/architecture/python_tooling_missing_source_input_wording_contract.md
```

It covers missing or invalid `--source-report` / `--source-manifest` inputs for isolated bundle export. It also covers `--source-manifest` without `--source-report` as an invalid option combination.

Recommended next phase:

```text
Phase 7.2B - missing source input wording implementation
```

## Checkpoint Policy

No new tag is recommended for this policy-only phase.

Consider a future checkpoint only after at least one implemented rejection-path slice passes targeted tests, full pytest, command inventory checks, and no-runtime-artifact validation.
