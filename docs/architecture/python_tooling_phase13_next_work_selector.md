# Python Tooling Phase 13 Next Work Selector

## Purpose

This selector chooses the next safe work item after the Phase 12 Python tooling docs-hardening sequence. It is docs-only and selector-only; it does not implement behavior, change command surfaces, run CE, or authorize export/write execution.

## Current closure state

- Phase 12.4 docs-hardening final smoke passed.
- No files changed during Phase 12.4.
- No commit or tag was required for Phase 12.4 because it was validation-only.
- Latest behavior checkpoint remains:
  - `python-tooling-invalid-output-extension-rejection-checkpoint-20260621`

The Phase 12 sequence is closed:

- Phase 12.0 post invalid-output checkpoint selector
- Phase 12.1 checkpoint/status overview docs sync
- Phase 12.2 rejection-message consistency audit
- Phase 12.3 report bundle export operator guide hardening
- Phase 12.4 docs-hardening final smoke

## Stable baseline

- command count: approximately 49
- `writes_files_count = 2`
- `runs_ce_count = 0`
- wrapper remains read-only
- write-capable commands remain unchanged:
  - `report export`
  - `report bundle export`
- Python tooling does not run CE.
- no new output formats are enabled
- no new command, option, or write destination was added by the Phase 12 docs-hardening sequence
- isolated `--source-manifest` content parsing remains deferred
- zip export remains unsupported and fail-closed

## Candidate next work items

### Candidate A - isolated source-manifest content parsing behavior contract

Type: product/behavior decision gate; docs-only contract first.

Goal:

- revisit the deferred `report bundle export --source-manifest <existing-file>` surface
- decide whether isolated `--source-manifest` should remain path/file-only or parse content
- if parsing is desired, create a behavior contract before implementation

Pros:

- addresses the known deferred question from Phase 10
- clarifies future bundle source behavior

Cons:

- not a wording-only change
- may introduce new validation behavior
- requires explicit product/behavior decision
- should not be implemented automatically

Suggested next phase if selected:

```text
Phase 13.1 - isolated source-manifest content parsing behavior contract
```

### Candidate B - return to core feature / CE-Lua workflow development

Type: new functional work selector.

Goal:

- leave Python tooling documentation and wrapper work stable
- select the next project feature outside the Python tooling docs chain
- identify required task, tests, and safety boundary before touching runtime, CE, or Lua paths

Pros:

- moves the project forward after tooling/docs stabilization
- avoids over-polishing tooling

Cons:

- requires a separate feature-intake decision
- may need more context about the intended next module

Suggested next phase if selected:

```text
Phase 13.1 - core feature next-module intake
```

### Candidate C - report bundle export operator docs final polish

Type: docs-only.

Goal:

- optional minor editorial pass after Phase 12.3
- no behavior changes

Pros:

- low risk

Cons:

- Phase 12.4 already validated docs-hardening closure
- likely diminishing returns

Suggested next phase if selected:

```text
Phase 13.1 - report bundle docs polish
```

### Candidate D - rejection-message implementation backlog review

Type: read-only audit/planning.

Goal:

- review whether any deferred rejection-message fix candidates remain
- produce a backlog list only, not implementation

Pros:

- safe and systematic

Cons:

- Phase 12.2 already found no immediate low-risk implementation fix candidate

Suggested next phase if selected:

```text
Phase 13.1 - rejection-message backlog review
```

## Recommendation

Default recommendation:

```text
Candidate B - return to core feature / CE-Lua workflow development
```

Rationale:

- Python tooling docs-hardening has passed final smoke
- rejection wording and checkpoint docs are stable
- continuing docs-only polishing has diminishing returns
- the next valuable step is to choose a functional next module or feature intake

If the project owner wants to resolve a known deferred Python tooling behavior first, choose Candidate A instead:

```text
Phase 13.1 - isolated source-manifest content parsing behavior contract
```

Candidate A requires an explicit product/behavior decision and must start as a contract, not implementation.

## Safety rules for next work

Future phases should preserve:

- no CE unless explicitly authorized by a runtime/CE task
- no manual export, dry-run, write, or restore in docs-only or validation-only tasks
- wrapper remains read-only
- `writes_files_count = 2`
- `runs_ce_count = 0`
- no new commands, options, output formats, or write destinations without explicit contract
- no production/default reports, manifests, bundles, logs, config, session, intake, baseline, or registry writes unless the task explicitly allows them
- pytest temp paths only for Python behavior tests
- no tag before final checkpoint smoke

## Suggested next task file

If Candidate B is selected:

```text
python_tooling_phase13_1_core_feature_next_module_intake_task.md
```

If Candidate A is selected:

```text
python_tooling_phase13_1_source_manifest_parsing_behavior_contract_task.md
```
