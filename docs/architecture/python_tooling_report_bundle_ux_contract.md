# Python Tooling Report / Bundle UX Contract

## Purpose

This document defines the future UX polish contract for report/bundle export commands.

It is contract-only. It does not implement behavior changes, modify Python source, change wrapper behavior, add commands, add tests, run CE, or execute any report/bundle export command.

## Current Baseline

Current stable state:

- command inventory: about `49` commands
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable Python commands:
  - `report export`
  - `report bundle export`
- wrapper remains read-only
- no CE/runtime mutation exists in Python tooling
- no log/config/session/intake/baseline/registry writes have been introduced
- zip export is unsupported / fail-closed
- `--force` / overwrite is unsupported

## Contract Principles

UX polish must not:

- expand write surface
- introduce new commands
- add new output roots
- enable `--force`
- add zip export
- route write-capable commands through the wrapper
- run CE
- write logs/config/session/baseline/intake/registry
- modify existing mutation workflows

Any future source implementation must be narrow and separately authorized.

## Command Family Boundary

### `report export`

`report export` is write-capable.

Future UX polish may improve:

- help text
- dry-run wording
- real-write success wording
- `--record-manifest` wording
- approved-root explanation
- protected-path rejection explanation
- overwrite rejection explanation

Future UX polish must not:

- add new output roots
- add `--force`
- route through wrapper
- write outside approved roots
- create manifests unless `--record-manifest` is explicitly used

### `report bundle export`

`report bundle export` is write-capable.

Future UX polish may improve:

- help text
- dry-run wording
- real-write success wording
- directory-only explanation
- zip unsupported explanation
- `bundle_manifest.json` / `index.md` location explanation
- protected-path rejection explanation
- overwrite rejection explanation

Future UX polish must not:

- add zip export
- add `--force`
- route through wrapper
- write outside approved roots
- mutate source reports/manifests unexpectedly

## Exact UX Message Requirements

Future implementation does not need to use exact final English prose, but the following semantic fields must be visible.

### Dry-Run Messages

For `report export --dry-run` and `report bundle export --dry-run`, output should clearly include:

- `DRY_RUN` or equivalent
- no files written
- intended output path or output directory
- whether the path is under an approved root
- which command would perform the real write
- warning that wrapper does not support write-capable export commands

### Real Report Export Success Message

For future real `report export`, output should clearly include:

- `WRITE_COMPLETE` or equivalent
- report output path
- approved root confirmation
- manifest not written unless `--record-manifest` is used
- next safe verification command, if applicable

### Report Export With `--record-manifest`

For future `report export --record-manifest`, output should clearly include:

- report output path
- manifest path
- manifest append/record status
- approved root confirmation
- no bundle created
- no CE run

### Real Bundle Export Success Message

For future real `report bundle export`, output should clearly include:

- `BUNDLE_EXPORT_COMPLETE` or equivalent
- bundle directory path
- bundle manifest path
- index path
- source report/manifest unchanged unless explicitly stated by supported behavior
- zip not created
- approved root confirmation

### `BAD_PATH` Message

For protected/unapproved paths, output should clearly include:

- `BAD_PATH`
- rejected path
- rejection reason category
- approved roots or reference to approved-root docs
- no unsafe workaround
- no write performed

### Overwrite Rejection Message

For existing output path/directory, output should clearly include:

- output already exists
- overwrite rejected
- `--force` unsupported
- choose a different approved output path
- no write performed

### Zip Unsupported Message

For zip-related requests, output should clearly include:

- zip export unsupported
- directory bundle export is the only supported bundle export mode
- no zip file created
- no write performed if the request was zip-only

### Wrapper Boundary Message

Docs and future help text should clearly state:

- wrapper is read-only
- wrapper does not support `report export`
- wrapper does not support `report bundle export`
- write-capable export commands must be invoked directly through Python only under an explicit task

## Help Text Contract

Future help text requirements apply to:

- `report export --help`
- `report bundle export --help`

Help text should show:

- whether command writes files
- dry-run availability and no-write meaning
- approved output roots
- overwrite / `--force` unsupported state
- wrapper not supported for write-capable commands
- CE not run
- manifest behavior for `--record-manifest`
- bundle directory-only behavior
- zip unsupported state

Do not implement help text in this phase.

## Documentation Example Contract

Future documentation examples must:

- separate read-only preview from write-capable export
- label commands as read-only or write-capable
- avoid suggesting wrapper for write-capable exports
- show dry-run before real write where relevant
- state when files will be written

## Validation Contract For Future Implementation

Future implementation tasks must validate in staged form.

### Stage 1: Help Text Only

Requirements:

- help text commands only
- no report export
- no bundle export
- no runtime writes
- pytest if tests are updated
- `writes_files_count = 2`
- `runs_ce_count = 0`

### Stage 2: Dry-Run Wording Only

Requirements:

- dry-run commands only
- no real writes
- no manifest writes
- no bundle directories
- artifact snapshot before/after
- pytest if tests are updated

### Stage 3: Real Write Validation

Only if separately authorized.

Requirements:

- explicit output path under approved root
- pre/post artifact snapshot
- cleanup policy explicitly stated
- no CE
- no log/config/session/baseline/intake/registry writes
- no wrapper invocation
- no `--force`
- no zip export

## Risk Assessment

| Contract area | Write-surface risk | Behavior-change risk | Likely future files touched | Required validation | Allowed in next implementation? |
| --- | --- | --- | --- | --- | --- |
| Help text polish | low | low | `src/armedforces_tool`, tests | help output checks, pytest | yes |
| Dry-run wording polish | low | medium | `src/armedforces_tool`, tests | dry-run-only smoke, artifact snapshot | only if explicitly scoped |
| Real report export success wording | medium | medium | `src/armedforces_tool`, tests | real-write smoke with cleanup | no, separate task |
| `--record-manifest` wording | medium | medium | `src/armedforces_tool`, tests | real-write + manifest cleanup | no, separate task |
| Bundle export success wording | medium | medium | `src/armedforces_tool`, tests | bundle export smoke with cleanup | no, separate task |
| `BAD_PATH` wording | low | medium | `src/armedforces_tool`, tests | protected path rejection tests | yes if scoped |
| Overwrite rejection wording | low | medium | `src/armedforces_tool`, tests | existing-output rejection tests | yes if scoped |
| Zip unsupported wording | low | low | `src/armedforces_tool`, tests | zip request rejection tests | yes if scoped |
| Wrapper boundary docs | low | low | docs only | diff check | yes |

## Recommended Next Implementation Slice

Recommended next phase:

```text
Phase 5.5: report/bundle export help text UX polish implementation
```

Scope:

- narrow CLI/help text only
- may modify Python source/tests
- must not execute real export
- must not execute dry-run export unless separately included in that task
- must not expand write surface
- must not change behavior beyond help text / wording

Phase 5.5 status: the narrow CLI help text slice has been implemented for `report export --help` and `report bundle export --help`. Command behavior, path guards, write behavior, manifest behavior, bundle behavior, wrapper behavior, approved roots, and write surface remain unchanged.

## Stop Conditions

Stop if a future task includes:

- any implementation request in this contract phase
- any Python source modification in this contract phase
- any test modification in this contract phase
- any request to add `--force`
- any request to add zip export
- any request to add wrapper export shortcut
- any request to change approved roots
- any request to run CE
- any request to execute real write
- any unexpected source/test/runtime changes
