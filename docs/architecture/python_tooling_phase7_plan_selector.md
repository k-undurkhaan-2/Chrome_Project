# Python Tooling Phase 7 Plan Selector

## Purpose

This document is the Phase 7 entry planning gate after the Phase 6 real-write output validation checkpoint. It does not implement functionality. It evaluates next-work options and selects the safest next direction after the real-write output validation line.

No command, option, source behavior, wrapper behavior, CE behavior, runtime state, or write surface is changed by this selector.

## Current Baseline

Established checkpoint tags:

```text
python-tooling-phase3-final-checkpoint-20260616
python-tooling-powershell-wrapper-readonly-checkpoint-20260616
python-tooling-output-wording-checkpoint-20260618
python-tooling-real-write-output-validation-checkpoint-20260619
```

Current expected state:

- commands approximately `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable Python commands:
  - `report export`
  - `report bundle export`
- wrapper read-only commands:
  - `status`
  - `inventory`
  - `report-status`
  - `manifest-verify`
  - `bundle-verify`
- wrapper remains read-only
- no CE/runtime mutation in Python tooling
- no log/config/session/intake/baseline/registry writes introduced
- zip export unsupported
- `--force` unsupported

## Frozen Boundaries From Previous Phases

- The wrapper remains read-only.
- The wrapper must not gain write-capable commands without separate policy, contract, tests, smoke validation, and checkpoint.
- Real-write validation only proved controlled isolated validation paths.
- Production/default report, manifest, and bundle workflows are not authorized by the Phase 6 checkpoint.
- CE/runtime migration remains out of scope unless separately planned.
- Zip export remains unsupported.
- `--force` remains unsupported.
- Approved roots/path guards must not be weakened.
- Production path mutation requires a new policy.

## Phase 7 Candidate Options

### Option A - Rejection-Path Wording Policy / Contract

Goal:

- improve or plan improved human-readable wording for rejection/fail-closed paths
- likely areas:
  - `BAD_PATH`
  - protected path rejection
  - overwrite / existing output rejection
  - `--force` unsupported
  - zip unsupported
  - invalid option combinations such as `--manifest-out` without `--record-manifest`
  - missing source inputs for bundle export
- no write-surface expansion
- no CE
- no wrapper changes

Risk:

- low to medium
- may touch output wording and tests later
- should not require manual real writes

Suitable when:

- Phase 6 validation line is complete
- next safest work is polishing fail-closed operator clarity

### Option B - Rejection-Path Implementation Slice

Goal:

- implement a narrowly scoped rejection-path wording polish after a contract phase
- likely first slice:
  - `--manifest-out` without `--record-manifest`
  - or bundle missing source input
  - or zip unsupported wording
- tests only
- no manual real writes

Risk:

- medium
- should follow Option A contract

Suitable when:

- Option A contract is complete

### Option C - Production Workflow Documentation

Goal:

- write operator docs for production/default report/export/bundle workflows
- clarify that production paths require separate authorization
- no source changes

Risk:

- low

Suitable when:

- project wants safer human documentation before any more implementation

### Option D - Write-Capable Wrapper Policy Planning

Goal:

- plan whether wrapper should ever support write-capable export commands
- define confirmation prompts, dry-run-first behavior, approved roots, and audit requirements
- no wrapper implementation

Risk:

- high
- would expand operator access if implemented later

Suitable when:

- direct Python workflows are stable
- convenience is needed
- user explicitly wants wrapper write support

### Option E - Write-Capable Wrapper Implementation

Goal:

- implement wrapper export shortcuts after a policy phase

Risk:

- very high
- not recommended before policy and separate checkpoints

Suitable when:

- Option D is complete and explicitly approved

### Option F - Runtime Write/Restore Migration Planning

Goal:

- plan Python migration for runtime write/restore workflows
- no implementation
- no CE
- no state mutation

Risk:

- very high
- approaches runtime/CE mutation territory

Suitable when:

- tooling/report validation line is fully frozen
- transaction/rollback model is ready to discuss

### Option G - CE/Runtime Automation Planning

Goal:

- plan CE automation / runtime integration
- no execution

Risk:

- very high

Suitable when:

- runtime workflow and safety model are mature

### Option H - Maintenance/Freeze

Goal:

- no new feature
- freeze Python tooling after Phase 6 checkpoint
- only documentation and bugfixes

Risk:

- low

Suitable when:

- user wants a stable pause

## Evaluation Matrix

| Option | Implementation Scope | Write-Surface Risk | CE/Runtime Risk | Likely Files Touched | Validation Required | Checkpoint/Tag Needed? | Recommended Priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A - Rejection-path wording policy / contract | docs-only contract | low | none | `docs/architecture/*`, operator docs | docs diff check, optional status/inventory | no tag by default | 1 |
| B - Rejection-path implementation slice | narrow helper/output wording tests | medium | none | `src/armedforces_tool/*`, `tests/*`, docs | targeted pytest, full pytest, no runtime artifact check | checkpoint only if behavior surface grows | 2 |
| C - Production workflow documentation | docs-only operator guide | low | none | operator/docs architecture files | docs diff check | no tag by default | 3 |
| D - Write-capable wrapper policy planning | docs-only policy | high future risk | none if docs-only | wrapper contract docs, operator docs | docs diff check, wrapper status/inventory | no tag by default | 4 |
| E - Write-capable wrapper implementation | wrapper behavior | very high | none if scoped to reports only | wrapper, tests, docs | targeted wrapper tests, full pytest, runtime artifact checks | yes | 8 |
| F - Runtime write/restore migration planning | docs-only runtime migration plan | high future risk | very high | architecture docs | docs diff check, safety status | no tag by default | 5 |
| G - CE/runtime automation planning | docs-only automation plan | high future risk | very high | architecture docs | docs diff check, safety status | no tag by default | 6 |
| H - Maintenance/freeze | docs note / no feature | low | none | docs only | status/inventory, pytest if requested | optional | 7 |

## Recommendation

Recommended order:

1. Option A - Rejection-path wording policy / contract
2. Option B - Rejection-path implementation slice
3. Option C - Production workflow documentation
4. Option D - Write-capable wrapper policy planning
5. Option F - Runtime write/restore migration planning
6. Option G - CE/runtime automation planning
7. Option H - Maintenance/freeze
8. Option E - Write-capable wrapper implementation only after policy

Rationale:

- Phase 6 validated positive success paths under isolated write conditions.
- The remaining low-risk gap is rejection/fail-closed operator clarity.
- Do not jump directly into wrapper write support.
- Do not jump directly into runtime/CE mutation.
- Do not authorize production/default workflow writes by implication.

## Next Concrete Phase Proposal

Recommended:

```text
Phase 7.1 - rejection-path wording policy contract
```

Scope:

- docs-only
- no source changes
- no tests
- no CE
- no real writes
- define rejection-path target list, expected wording, tests, and stop conditions
- no tag

Alternative if the operator wants a pause:

```text
Phase 7.1b - post-checkpoint maintenance freeze note
```

## Stop Conditions

Stop Phase 7 selector or follow-up phases if any of these are required:

- working tree dirty with unexpected files
- source/runtime/log/report/config file change in selector phase
- real write in selector phase
- CE command
- adding `--force`
- adding zip export
- wrapper export shortcut without policy
- weakening path guards
- expanding approved roots
- production/default report/manifest/bundle mutation without a new policy
