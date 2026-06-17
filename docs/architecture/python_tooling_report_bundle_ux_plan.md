# Python Tooling Report / Bundle UX Polish Plan

## Purpose

This is a report/bundle export UX polish planning document.

It only plans future UX polish for report and bundle export workflows. It does not implement behavior changes, modify Python source, add commands, run CE, or execute write-capable commands.

## Current Baseline

Current stable state:

- command inventory: about `49` commands
- `writes_files_count = 2`
- `runs_ce_count = 0`
- current write-capable Python commands:
  - `report export`
  - `report bundle export`
- wrapper remains read-only
- no CE/runtime mutation exists in Python tooling
- no log/config/session/intake/baseline/registry writes have been introduced

## Current Export Boundary

Current boundary:

- `report export` is write-capable
- `report export --record-manifest` writes a runtime report and appends a runtime manifest entry
- `report bundle export` is write-capable directory export
- `report bundle export --dry-run` is no-write, but still must not be routed through the wrapper
- zip export is unsupported / fail-closed
- `--force` / overwrite is unsupported
- protected paths must remain rejected
- approved roots must remain explicit

## UX Problems / Friction Points

Current operator friction points:

- write-capable commands and read-only commands are easy to confuse
- the difference between dry-run, real write, and manifest write needs to be clearer
- `BAD_PATH`, `NO_MANIFEST`, and overwrite rejection need clearer explanation
- bundle export directory-only limitation should be more visible
- zip unsupported state should be more explicit
- wrapper does not support write-capable commands, so misuse should be avoided
- output path / approved root rules need clearer documentation

## Proposed UX Polish Candidates

### Candidate A: Clearer CLI Help Text

Plan:

- improve help text for `report export` and `report bundle export`
- explicitly show write behavior
- explicitly show approved roots
- explicitly warn that the wrapper does not support these commands

### Candidate B: Safer Dry-Run Messaging

Plan:

- dry-run output should clearly say no files were written
- real write output should clearly say files were written
- `--record-manifest` output should clearly say manifest append occurred

### Candidate C: `BAD_PATH` Explanation Polish

Plan:

- `BAD_PATH` should include protected path reason
- `BAD_PATH` should not reveal unsafe workaround
- `BAD_PATH` should point to approved roots / docs

### Candidate D: Overwrite / Force Messaging

Plan:

- output exists should explain `--force` is unsupported
- do not add `--force` yet
- future force policy requires separate planning

### Candidate E: Bundle Export Messaging

Plan:

- clarify directory-only export
- clarify zip unsupported
- clarify `bundle_manifest.json` / `index.md` location only under bundle directory
- clarify source reports / manifest remain unchanged unless specified by a supported command

### Candidate F: Operator Docs / Command Examples

Plan:

- add clearer examples in docs
- distinguish read-only preview from write-capable export
- distinguish wrapper from direct Python

## Risk Assessment

| Candidate | Write-surface risk | Behavior-change risk | Test requirement | Docs-only or source-change requirement |
| --- | --- | --- | --- | --- |
| A: CLI help text | low | low | help output smoke / pytest | source change later |
| B: dry-run messaging | low to medium | medium | dry-run and real-write smoke, if real write is scoped | source change later |
| C: `BAD_PATH` polish | low | medium | path rejection tests | source change later |
| D: overwrite / force messaging | medium | medium | existing-output rejection tests | source change later; no `--force` implementation |
| E: bundle export messaging | low to medium | medium | bundle dry-run / export smoke where scoped | source change later |
| F: docs / examples | low | low | diff check only | docs-only |

## Recommended Implementation Order

Recommended future order:

1. docs-only examples / wording audit
2. CLI help text polish
3. dry-run / real-write output wording polish
4. `BAD_PATH` / overwrite message polish
5. bundle export messaging polish

Rationale:

- the next implementation phase should be narrow
- no expansion of write surface
- no wrapper support for write-capable commands
- no `--force`
- no zip export
- no CE/runtime work

## Future Implementation Guardrails

Guardrails:

- any source change must be in a separate implementation task
- no behavior change unless explicitly requested
- no new write-capable command
- no new output root
- no wrapper integration
- no runtime/log/config/session/baseline/intake writes
- validation must include dry-run only first
- real write tests must be separately authorized if needed

## Stop Conditions

Stop if a future task asks for:

- adding `--force`
- adding zip export
- adding wrapper `report-export` shortcut
- modifying approved roots
- running CE
- executing real write during planning
- unexpected source/test/runtime changes

## Next Concrete Phase Proposal

Recommended next phase:

```text
Phase 5.4: report/bundle export UX polish contract
```

Scope:

- docs-only contract
- define exact messages / help text to change
- no Python source yet
- no write-capable execution

Optional later phase:

```text
Phase 5.5: narrow CLI/help text implementation
```

Phase 5.4 note: `docs/architecture/python_tooling_report_bundle_ux_contract.md` defines the UX polish contract. Implementation remains deferred, and future implementation must follow that contract.

Phase 5.5 note: the first implementation slice completed CLI help text polish for `report export --help` and `report bundle export --help`. It did not add commands, add options, change export behavior, alter path guards, expand wrapper support, or expand the write surface. Future dry-run/output wording polish remains deferred to separately scoped tasks.
