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

Implementation note:

- Phase 7.2B implementation adds fail-closed human-readable wording for missing or invalid isolated bundle source inputs.
- Missing inputs use `SOURCE_MISSING` and `NO_FILES_WRITTEN`.
- Directory/non-file source inputs use `SOURCE_INVALID` and `NO_FILES_WRITTEN`.
- `--source-manifest` without `--source-report` uses `INVALID_OPTION_COMBINATION` and `NO_FILES_WRITTEN`.
- Failure output does not use `SOURCE_UNCHANGED` or bundle/report success tokens.
- Candidate A/B/C success output, dry-run output, wrapper behavior, and CE/runtime boundaries remain unchanged.

Phase 7.2B boundary smoke passed after implementation.

## Phase 7.2C Contract Status

The zip unsupported wording contract exists at:

```text
docs/architecture/python_tooling_zip_unsupported_wording_contract.md
```

It targets zip/archive output requests for `report bundle export`.

Recommended next phase:

```text
Phase 7.2C - zip unsupported wording implementation
```

Implementation note:

- Future implementation must first confirm the current CLI/source has an existing zip rejection surface.
- Zip/archive requests should fail closed with `ZIP_UNSUPPORTED` and, if compatible, `NO_FILES_WRITTEN`.
- Future implementation must not enable zip export, add zip support for testing, add `--force`, modify wrapper behavior, or weaken path guards.
- If no current zip rejection surface exists, implementation must stop and report that a separate parser-surface contract is required.

Phase 7.2C implementation and boundary smoke passed. The existing zip rejection path remains fail-closed with status `BUNDLE_ZIP_EXPORT_NOT_IMPLEMENTED`, includes `ZIP_UNSUPPORTED` and `NO_FILES_WRITTEN`, does not create zip or bundle artifacts, and does not enable zip support.

## Validated Slices

Phase 7 policy now has three validated examples:

- Phase 7.2A invalid option combination: `report export --manifest-out <path>` without `--record-manifest`.
- Phase 7.2B missing or invalid bundle source input: `--source-report`, `--source-manifest`, and `--source-manifest` without `--source-report`.
- Phase 7.2C unsupported zip output: `report bundle export --zip`.

Validated rejection/no-write tokens:

- `INVALID_OPTION_COMBINATION`
- `SOURCE_MISSING`
- `SOURCE_INVALID`
- `ZIP_UNSUPPORTED`
- `NO_FILES_WRITTEN`

Validated token rules:

- success tokens must stay out of rejection output
- `SOURCE_UNCHANGED` is success-only and must not appear in source rejection output
- `NO_FILES_WRITTEN` must be used only when the command did not write output artifacts
- unsupported features such as zip export and `--force` must not become enabled through wording tasks
- rejection wording must not imply wrapper write support, CE execution, or production/default write authorization

## Checkpoint Policy

No tag is created for policy-only or checkpoint-candidate documentation phases.

Consider the future `python-tooling-rejection-path-wording-checkpoint-20260620` tag only after a validation-only final checkpoint smoke confirms the Phase 7.2A, Phase 7.2B, and Phase 7.2C slices remain stable.

## Force / Overwrite Unsupported Contract

The force / overwrite unsupported wording contract exists at:

```text
docs/architecture/python_tooling_force_overwrite_unsupported_wording_contract.md
```

Intended tokens:

- `OVERWRITE_UNSUPPORTED`
- `FORCE_UNSUPPORTED`
- `NO_FILES_WRITTEN`

This future slice must not enable overwrite, must not enable `--force`, must not add a `--force` option only for testing, and must not write or replace existing outputs in rejection cases. If future source inspection finds no current force/overwrite rejection surface, implementation must stop and report that a separate parser-surface contract is needed.

## Supported Behavior Guardrail

Rejection-path wording tasks must not contradict supported success behavior.

If source inspection finds that a requested rejection path is actually supported, the implementation phase must stop and record a behavior policy contract before any wording change.

Phase 8.1 is the current example:

- `report export --force` is supported today
- it is not an unsupported rejection path
- `FORCE_UNSUPPORTED` must not be used for `report export --force`
- future overwrite wording should target no-force existing-output rejection

The behavior policy is recorded in:

```text
docs/architecture/python_tooling_force_overwrite_behavior_policy.md
```

## No-Force Overwrite Rejection Contract

The next precise overwrite wording slice is no-force existing-output rejection:

```text
docs/architecture/python_tooling_overwrite_without_force_wording_contract.md
```

Supported success behavior must be preserved. In particular, `report export --force` remains a supported direct Python success path and must not receive `FORCE_UNSUPPORTED`.

Token scopes must avoid contradicting supported behavior:

- use `OVERWRITE_UNSUPPORTED` for no-force existing-output rejection when that is the true reason
- use `NO_FILES_WRITTEN` only when no output artifact was written
- reserve `FORCE_UNSUPPORTED` for a real unsupported-force surface

## No-Force Overwrite Validated Slice

Phase 8.2 is now another validated rejection-path wording example.

Validated surfaces:

- `report export --out <existing-file>` without `--force`
- `report bundle export --out <existing-directory>`
- `report bundle export --out <existing-file>`

Validated tokens:

- `OVERWRITE_UNSUPPORTED`
- `NO_FILES_WRITTEN`

Guardrails:

- supported success paths must stay separate from rejection wording
- `report export --force` remains success behavior and must not receive `FORCE_UNSUPPORTED`
- no-write tokens apply only to actual no-write rejection paths
- manifest existing-file behavior remains append/preflight unless a future contract changes it

## Approved-Root / Path-Guard Rejection Contract

The approved-root / path-guard rejection wording contract exists at:

```text
docs/architecture/python_tooling_path_guard_rejection_wording_contract.md
```

Target tokens:

- `PATH_GUARD_REJECTED`
- `OUTSIDE_APPROVED_ROOT`
- `NO_FILES_WRITTEN`

The slice must not weaken path guards, expand approved roots, add write destinations, or imply wrapper write support.

Existing `BAD_PATH` wording may be preserved only if current implementation already uses it for the same guard semantics.

## Approved-Root / Path-Guard Validated Slice

Phase 9.1 is now another validated rejection-path wording example.

Validated surfaces:

- `report export --out <outside-approved-root>`
- `report export --record-manifest --manifest-out <outside-approved-root>`
- `report bundle export --out <outside-approved-root>`
- `report bundle export --source-report <guard-rejected-path>` where current planner semantics already return `BAD_PATH`

Validated tokens:

- `PATH_GUARD_REJECTED`
- `OUTSIDE_APPROVED_ROOT` where approved-root semantics apply
- `NO_FILES_WRITTEN`

Compatibility and guardrails:

- `BAD_PATH` / `PATH_REJECTED` compatibility must be preserved for existing machine-readable result fields.
- Guard tokens must stay scoped to guard rejections.
- Path-guard wording must not weaken guard behavior, expand approved roots, add write destinations, or imply wrapper write support.
- Missing/invalid source input, zip unsupported, no-force overwrite, and extension-only validation remain separate wording slices.

## Source Manifest Parse / Invalid Content Contract

The source manifest parse / invalid-content rejection wording contract exists at:

```text
docs/architecture/python_tooling_source_manifest_parse_rejection_contract.md
```

Target tokens:

- `MANIFEST_PARSE_FAILED`
- `MANIFEST_INVALID`
- `NO_FILES_WRITTEN`

This slice is for `report bundle export --source-manifest <existing but malformed/invalid manifest>` only. It must not replace Phase 7.2B missing/non-file source input wording (`SOURCE_MISSING` / `SOURCE_INVALID`) or Phase 9.1 path-guard wording (`PATH_GUARD_REJECTED`, `BAD_PATH`, `PATH_REJECTED`).

Phase 10.2 is the current behavior-policy example: source inspection found no isolated `--source-manifest` parse/invalid rejection surface because isolated bundle mode validates path/file safety but does not parse manifest content. Rejection-path wording tasks must not introduce new validation behavior. If inspection finds the requested rejection path does not exist, implementation must stop and record a behavior policy before any code change.

## Default Manifest Parse / Invalid Manifest Contract

The default manifest parse rejection wording contract exists at:

```text
docs/architecture/python_tooling_default_manifest_parse_rejection_contract.md
```

Target surface:

- `_analyze_existing_manifest()`
- `_parse_manifest_line()`
- `INVALID_MANIFEST`

Token policy:

- preserve `INVALID_MANIFEST` as the compatibility status where current behavior uses it
- use `MANIFEST_PARSE_FAILED`, `MANIFEST_INVALID`, and `NO_FILES_WRITTEN` only for default manifest parse/invalid wording where current semantics support it
- do not introduce isolated `--source-manifest` content parsing through wording work

Validated status:

- Phase 10.4 implemented this default manifest parser wording.
- Phase 10.5 boundary smoke passed.
- `INVALID_MANIFEST` remains the compatibility status.
- `MANIFEST_PARSE_FAILED` is scoped to malformed default manifest parse failure.
- `MANIFEST_INVALID` is scoped to parseable but invalid default manifest records.
- `NO_FILES_WRITTEN` indicates fail-closed output before bundle artifacts are written.

This is another validated example of the policy rule that wording work must not introduce new validation behavior.

## Invalid Output Extension / Output Type Contract

The invalid output extension / output type rejection wording contract exists at:

```text
docs/architecture/python_tooling_invalid_output_extension_wording_contract.md
```

Target tokens:

- `OUTPUT_EXTENSION_INVALID`
- `OUTPUT_TYPE_UNSUPPORTED`
- `NO_FILES_WRITTEN`

This slice is for output paths rejected because the extension, output type, or output form is invalid or unsupported. It must not replace path guard, overwrite, zip unsupported, source input, or default manifest parse rejection semantics.

Wording work must not enable new output formats, add commands or options, weaken path guards, expand approved roots, or add write destinations. Future implementation must first inspect current source/help/tests and STOP if no real current invalid output extension/type rejection surface exists.

Validated status:

- Phase 11.2 implemented invalid output extension/type wording for current surfaces only.
- Phase 11.3 boundary smoke passed.
- Implemented surfaces are `report export --out <unsupported-extension>`, `report export --record-manifest --manifest-out <unsupported-extension>`, and `report bundle export --out <file-like path>`.
- `OUTPUT_EXTENSION_INVALID` is scoped to unsupported report/manifest output extensions.
- `OUTPUT_TYPE_UNSUPPORTED` is scoped to unsupported bundle output form or file-like targets.
- `NO_FILES_WRITTEN` indicates fail-closed rejection before output artifacts are written.
- `.zip` / zip requests remain `ZIP_UNSUPPORTED` and are not reclassified as generic output type failures.

This is another validated example that wording work may clarify an existing rejection surface but must not enable output formats or move adjacent-domain tokens out of their scoped domains.
