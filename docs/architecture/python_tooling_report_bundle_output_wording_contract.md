# Python Tooling Report / Bundle Output Wording Contract

## Purpose

This document defines future output wording requirements for report and bundle export UX polish.

This is a documentation-only contract. It does not implement behavior changes, modify Python source, modify the PowerShell wrapper, add commands, add options, run CE, or execute report/bundle export commands.

## Current Baseline

Current stable boundary:

- command inventory: about `49` commands
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable Python commands:
  - `report export`
  - `report bundle export`
- wrapper remains read-only
- wrapper does not wrap write-capable export commands
- no CE/runtime mutation exists in Python tooling
- no log/config/session/intake/baseline/registry writes have been introduced
- zip export is unsupported / fail-closed
- bundle overwrite / `--force` remains unsupported
- Phase 5.5 help text polish has been completed for `report export --help` and `report bundle export --help`

## Output Wording Principles

Output wording polish must not:

- change command behavior
- add new commands or options
- expand approved output roots
- enable unsupported overwrite or `--force` behavior
- add zip export
- route export commands through the read-only PowerShell wrapper
- change manifest write behavior
- change bundle write behavior

Output wording polish must:

- make write/no-write status visible
- make artifact locations visible
- make approved-root status visible
- make CE exclusion visible
- make wrapper exclusion visible
- avoid unsafe workaround hints
- use stable phrases that future tests can assert without depending on long exact paragraphs

## Dry-Run Output Contract

Future dry-run output should make the no-write boundary unambiguous.

### `report export --dry-run`

Output should clearly show:

- `DRY_RUN` or equivalent
- no files written
- report path that would be written
- approved-root status
- whether a manifest would be written
- reminder that real write requires running the non-dry-run command
- reminder that the wrapper does not support `report export`
- CE not run

### `report bundle export --dry-run`

Output should clearly show:

- `DRY_RUN` or equivalent
- no files written
- bundle directory that would be created
- bundle manifest path that would be created
- index path that would be created
- approved-root status
- directory-only bundle mode
- zip not created / unsupported
- reminder that the wrapper does not support `report bundle export`
- CE not run

## Real Write Success Output Contract

Future real-write success output should make completed writes explicit while keeping the write boundary visible.

### `report export`

Output should clearly show:

- `WRITE_COMPLETE` or equivalent
- report file path
- approved-root confirmation
- manifest not written unless `--record-manifest` is used
- no bundle created
- CE not run
- next safe verification or preview command, if appropriate

### `report export --record-manifest`

Output should clearly show:

- `WRITE_COMPLETE` or equivalent
- report file path
- manifest path
- manifest append/record status
- approved-root confirmation
- no bundle created
- CE not run

### `report bundle export`

Output should clearly show:

- `BUNDLE_EXPORT_COMPLETE` or equivalent
- bundle directory path
- bundle manifest path
- index path
- copied report count, if available
- source report/manifest unchanged unless explicitly stated by supported behavior
- zip not created
- approved-root confirmation
- CE not run

## Error / Rejection Output Contract

Future rejection output should clearly state why no write occurred and what safe next step exists.

### `BAD_PATH`

Output should clearly show:

- `BAD_PATH`
- rejected path
- rejected category or reason
- approved roots or a reference to approved-root documentation
- no write performed
- no unsafe workaround

### Overwrite Rejection

Output should clearly show:

- output already exists
- overwrite rejected
- unsupported overwrite mode or missing explicit authorization, as applicable to the command
- choose a different approved output path when overwrite is unsupported
- no write performed

### Zip Unsupported

Output should clearly show:

- zip export unsupported
- directory bundle export is the only supported real bundle mode
- no zip file created
- no write performed if the request was zip-only

### Wrapper Boundary Rejection / Reminder

Output and docs should clearly show:

- wrapper is read-only
- wrapper does not support export commands
- use direct Python only for write-capable export under an explicit task
- wrapper support for write-capable export is deferred and requires separate policy, contract, and smoke validation

## Message Token / Wording Guidance

Recommended stable tokens or phrases for future tests:

- `DRY_RUN`
- `WRITE_COMPLETE`
- `BUNDLE_EXPORT_COMPLETE`
- `BAD_PATH`
- `NO_FILES_WRITTEN`
- `APPROVED_ROOT`
- `OVERWRITE_UNSUPPORTED`
- `ZIP_UNSUPPORTED`
- `WRAPPER_UNSUPPORTED`
- `CE_NOT_RUN`

Future tests should assert semantic tokens/phrases rather than long exact paragraphs.

## Documentation Example Contract

Future docs and examples should:

- label each command as read-only, dry-run no-write, or write-capable
- show dry-run before real write where relevant
- never show wrapper invocation for write-capable export commands
- clearly state when files are written
- clearly state when no files are written
- show approved-root expectations
- avoid suggesting protected-path bypasses

## Future Implementation Validation Contract

Future implementation must be staged.

### Stage 1: Output Wording Tests With Simulated / Unit Paths

Preferred if practical:

- no real export
- no dry-run export unless explicitly included in the future task
- no runtime writes
- validate formatting helpers or message builders if available
- pytest can assert stable tokens and semantic phrases

### Stage 2: Dry-Run Output Validation

Only if separately authorized:

- dry-run commands only
- no files written
- artifact snapshot before/after
- no manifest append
- no bundle directory
- no CE

### Stage 3: Real-Write Output Validation

Only if separately authorized:

- explicit approved output path
- pre/post artifact snapshot
- cleanup policy explicitly stated
- no wrapper invocation
- no unsupported `--force`
- no zip
- no CE
- no log/config/session/baseline/intake/registry writes

## Risk Assessment

| Output area | Behavior-change risk | Write-surface risk | Likely future files touched | Test approach | Allowed in next implementation? |
| --- | --- | --- | --- | --- | --- |
| Dry-run report output | low | low | `src/armedforces_tool`, tests | helper tests or dry-run-only smoke if scoped | yes, if scoped |
| Dry-run bundle output | low | low | `src/armedforces_tool`, tests | helper tests or dry-run-only smoke if scoped | yes, if scoped |
| Real report write output | medium | medium | `src/armedforces_tool`, tests | real-write smoke with cleanup | no, separate task |
| Real report plus manifest output | medium | medium | `src/armedforces_tool`, tests | real-write and manifest smoke with cleanup | no, separate task |
| Real bundle output | medium | medium | `src/armedforces_tool`, tests | bundle export smoke with cleanup | no, separate task |
| `BAD_PATH` | low | low | `src/armedforces_tool`, tests | unit/path rejection tests | yes, if scoped |
| Overwrite rejection | low | medium | `src/armedforces_tool`, tests | existing-output rejection tests | yes, if scoped |
| Zip unsupported | low | low | `src/armedforces_tool`, tests | zip rejection tests | yes, if scoped |
| Wrapper boundary reminder | low | low | docs, possibly help text | help/docs checks | yes, if scoped |

## Recommended Next Implementation Slice

Recommended next phase:

```text
Phase 5.7: report/bundle output wording helper contract-to-implementation
```

Preferred scope:

- implement wording through message helpers if practical
- test message helpers without executing real writes
- keep behavior unchanged
- add no commands or options
- execute no real export
- run no CE

Alternative next slice:

```text
Phase 5.7a: dry-run output wording implementation
```

Use the alternative only if dry-run validation is separately authorized and artifact snapshot checks are included.

Phase 5.7 status: a helper-only implementation slice added output wording message helpers and helper unit tests. The helpers are not wired into report export, report export dry-run, report bundle export, or report bundle export dry-run execution paths. Command behavior, approved roots, path guards, manifest behavior, bundle behavior, wrapper behavior, and write surface remain unchanged.

## Stop Conditions

Stop if a future task includes:

- any implementation request in this contract phase
- any Python source modification in this contract phase
- any test modification in this contract phase
- any request to execute dry-run export in this contract phase
- any request to execute real export
- any request to add `--force`
- any request to add zip export
- any request to add wrapper export shortcut
- any request to change approved roots
- any request to run CE
- any unexpected source/test/runtime changes
