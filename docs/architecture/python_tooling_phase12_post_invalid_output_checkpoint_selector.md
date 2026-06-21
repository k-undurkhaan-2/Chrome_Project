# Python Tooling Phase 12 Post Invalid Output Checkpoint Selector

## Purpose

This document selects the next safe Python tooling slice after the invalid output extension rejection checkpoint. It is a docs-only selector and does not authorize new behavior, new commands, new options, CE execution, report export, bundle export, or runtime writes.

## Current stable baseline

Latest checkpoint tag:

```text
python-tooling-invalid-output-extension-rejection-checkpoint-20260621
```

Expected stable tags:

```text
python-tooling-phase3-final-checkpoint-20260616
python-tooling-powershell-wrapper-readonly-checkpoint-20260616
python-tooling-output-wording-checkpoint-20260618
python-tooling-real-write-output-validation-checkpoint-20260619
python-tooling-rejection-path-wording-checkpoint-20260620
python-tooling-no-force-overwrite-rejection-checkpoint-20260620
python-tooling-path-guard-rejection-checkpoint-20260620
python-tooling-default-manifest-parse-rejection-checkpoint-20260621
python-tooling-invalid-output-extension-rejection-checkpoint-20260621
```

Current command surface:

- command count: 49
- `writes_files_count = 2`
- `runs_ce_count = 0`
- wrapper remains read-only
- wrapper does not expose write-capable export shortcuts
- write-capable Python commands remain unchanged:
  - `report export`
  - `report bundle export`
- Python tooling does not run CE or perform runtime mutation.
- Approved-root path guards remain strict.
- Zip export remains unsupported and fail-closed.
- No new output formats, write destinations, commands, or options were added by Phase 11.

## Frozen completed areas

The following areas are complete and should remain frozen unless a future selector and contract explicitly reopen them:

- report export success output
- report export manifest success output
- report bundle directory success output
- bundle dry-run output
- wrapper read-only boundary
- real-write validation output
- rejection path wording for:
  - invalid option combination
  - source missing or invalid
  - zip unsupported
  - no-force overwrite
  - path guard
  - default manifest parse
  - invalid output extension or output type
- command inventory and write-surface metadata
- approved-root path guard behavior
- local config, log, session, intake, baseline, and registry safety boundaries

Candidate A/B/C success output, `report export --force`, dry-run behavior, wrapper boundaries, command inventory, and write-surface metadata are stable and should not be changed casually.

## Candidate next slices

### Candidate A - checkpoint/status overview docs sync

Type: docs-only.

Goal:

- create or update a compact status overview of all Python tooling checkpoints and command surface
- make the operator guide and quick reference easier to use
- make no source, test, or behavior changes

Pros:

- low risk
- improves handoff and later maintenance
- useful after many small checkpoint tags

Cons:

- no new behavior improvement

Suggested phase name:

```text
Phase 12.1 - Python tooling checkpoint/status overview docs sync
```

### Candidate B - rejection-message consistency audit

Type: read-only / docs-first, with implementation only if a clear low-risk inconsistency exists.

Goal:

- audit all rejection output tokens and messages after Phases 7-11
- confirm no success tokens appear in rejection paths
- confirm no rejection domain bleeds into adjacent domains
- propose narrow fix candidates only if needed

Pros:

- useful after multiple rejection wording slices
- may find small inconsistencies without adding behavior

Cons:

- can expand in scope if not kept read-only
- any implementation should be separate and conditional

Suggested phase name:

```text
Phase 12.1 - rejection-message consistency audit
```

### Candidate C - isolated source-manifest content parsing contract

Type: product/behavior decision gate, docs-only contract first.

Goal:

- revisit the deferred `report bundle export --source-manifest <existing-file>` behavior
- decide whether isolated `--source-manifest` should remain path/file-only or parse content
- if parsing is desired, create a separate behavior contract before any implementation

Pros:

- closes the known deferred question from Phase 10

Cons:

- not merely wording
- may introduce new validation behavior
- requires an explicit product decision
- should not be implemented automatically

Suggested phase name:

```text
Phase 12.1 - isolated source-manifest content parsing behavior contract
```

### Candidate D - report bundle export UX/operator docs hardening

Type: docs-only or docs-first.

Goal:

- clarify operator-facing bundle export, dry-run, manifest, source-report, and source-manifest behavior
- emphasize manual export restrictions for validation phases

Pros:

- low risk
- improves operator correctness

Cons:

- mostly documentation polish

Suggested phase name:

```text
Phase 12.1 - report bundle export operator guide hardening
```

## Recommended next slice

Recommended next slice:

```text
Phase 12.1 - Python tooling checkpoint/status overview docs sync
```

Rationale:

- multiple checkpoint tags now exist and should be easy to audit from one compact overview
- behavior is stable after Phase 11.5 final smoke
- a checkpoint/status overview improves handoff before starting another behavior-adjacent slice
- the work is low-risk and docs-only

Candidate B can follow after the docs sync. Candidate C should be deferred until an explicit product/behavior decision because isolated `--source-manifest` content parsing would introduce behavior, not just wording. Candidate D can be combined with Candidate A only if the edit remains narrow; otherwise keep it separate.

## Safety rules for next slice

The next slice should preserve:

- no CE
- no manual write-capable export during validation-only or docs-only phases
- wrapper remains read-only
- `writes_files_count = 2`
- `runs_ce_count = 0`
- no new commands, options, output formats, or write destinations unless an explicit implementation contract exists
- no production/default reports, manifests, bundles, logs, config, session, intake, baseline, or registry writes
- pytest temp paths only for behavior tests
- no tag before final checkpoint smoke

## Suggested next task file

Recommended next task file:

```text
python_tooling_phase12_1_checkpoint_status_overview_docs_task.md
```

If Candidate B is selected instead:

```text
python_tooling_phase12_1_rejection_message_consistency_audit_task.md
```
