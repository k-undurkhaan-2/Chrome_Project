# Core Feature Next Module Intake

## Purpose

This document records the next-module intake after Python tooling stabilization and before returning to CE/Lua/core feature implementation. It is docs-only and intake-only; it does not authorize CE execution, runtime writes, source edits, or implementation work.

## Stable Tooling Baseline

- latest stable Python tooling checkpoint tag: `python-tooling-invalid-output-extension-rejection-checkpoint-20260621`
- command count: approximately 49
- `writes_files_count = 2`
- `runs_ce_count = 0`
- wrapper remains read-only
- write-capable Python commands remain only:
  - `report export`
  - `report bundle export`
- Python tooling is not the active implementation target unless a future task explicitly selects it.

## Current Core Project Inventory

Read-only repository inspection covered `src`, `docs/architecture`, `docs/checkpoints`, and grep terms for runtime, candidate/rank/stable, session, diagnostic, baseline, registry, and workflow state. No CE execution or runtime mutation was performed.

| Area | Evidence | Current apparent status | Risk / unknown |
|---|---|---|---|
| CE/Lua runtime scripts | `src/execute_module-v5.2.0_batch.lua`, `src/mvp0_value_executor.lua`, `src/mvp0_candidate_report.lua`, `src/mvp0_foundlist_collector.lua`; `docs/execute_module_workflow.md` fixed CE command | Runtime entrypoint and Lua modules remain present. Runbook says CE execution is manual and default operation should be detect-only. | Current live CE state is unknown. CE remains blocked until a later task explicitly authorizes it. |
| Session workflow scripts | `src/test_session_tool.ps1`, `src/case_config_tool.ps1`, `src/batch_log_classifier.ps1`; checkpoint `case-collection-workflow-checkpoint-20260614.md` | Existing workflow covers doctor/status/plan, session start/end, prepare-current-case, post-current-case, case intake, sample-plan, retest-queue, baseline compare. | Local session/log state must not be mutated during intake. Next phase must define whether it only plans or may prepare/run cases. |
| Diagnostic/logging controls | `diagnostic_level` appears in Lua runtime, config tooling, Python status tooling, and `run_case_config.example.lua` | Diagnostic levels are part of runtime config and safety/status views. Workflow docs distinguish normal detect-only checks from risky work. | Allowed diagnostic level for any future CE run is not selected. Logging controls need explicit boundary before runtime work. |
| Candidate/rank/stable result logic | `stable_intersection`, `prescore`, `candidate`, `rank`, `rank_guard_ok`, `known_true_rank_position` appear in Lua runtime and PowerShell classifier/session tools | Candidate selection, stable intersection, prescore, and rank guard logic are active core domains. Runtime includes rank guard checks and stable intersection summaries. | Next algorithmic target is not selected. Latest live logs may be needed later, but this intake does not read/write runtime logs beyond tracked repo inspection. |
| Baseline/registry/session safety | `baseline`, `case_registry`, `case_intake`, `active_session`, `known_true_addr` appear across PowerShell tools, Python read-only tooling, tests, and docs | Safety model distinguishes historical evidence from active-session evidence. Checkpoints record local-only files and CE manual-only boundaries. | Future tasks must state whether registry/session/baseline/intake writes are allowed. Default remains no writes. |
| Python tooling/reporting support | `src/armedforces_tool/*.py`, read-only wrapper, report/export/bundle docs, Phase 12 overview/audit/operator docs | Tooling is stable and not the current implementation target. Write surface remains `report export` and `report bundle export`; wrapper read-only. | Deferred Python tooling behavior remains isolated `--source-manifest` content parsing, which requires product/behavior decision. |
| Documentation/checkpoint state | `docs/execute_module_workflow.md`, `docs/checkpoints/case-collection-workflow-checkpoint-20260614.md`, Python tooling architecture/checkpoint docs | Core workflow checkpoint exists from 2026-06-14; Python tooling/docs-hardening sequence is closed and smoke-validated. | Core CE/Lua current state has not been revalidated after the tooling detour. |

## Candidate Next Modules

### Candidate A - CE/Lua current-state revalidation plan

Type: planning/validation contract first.

Goal:

- define a safe plan to revalidate the current CE/Lua workflow without immediately running CE
- identify what must be checked before runtime collection resumes
- confirm local config fields the operator must supply

Pros:

- directly reconnects to core runtime project
- avoids accidental CE/log/config mutation
- good first step after the tooling detour

Cons:

- no new feature implementation yet
- likely requires a later CE-authorized task

Suggested next phase:

```text
Phase 13.2 - CE/Lua current-state revalidation plan
```

### Candidate B - candidate/rank/stable next-module selector

Type: docs-first design selector.

Goal:

- inspect current candidate/rank/stable intersection behavior
- select whether next implementation targets collector, filter, prescore, stable intersection, rank stability, or source address handling

Pros:

- close to core feature value
- avoids random runtime edits

Cons:

- may need latest logs later
- implementation may require CE/runtime validation

Suggested next phase:

```text
Phase 13.2 - candidate ranking next-module selector
```

### Candidate C - runtime diagnostics boundary review

Type: docs-first safety review.

Goal:

- review diagnostic/logging entrances
- decide what stays operator-facing vs internal
- prepare later cleanup if needed

Pros:

- useful before runtime testing
- aligns with later need to close diagnostic/logging doors

Cons:

- mostly safety/polish unless tied to feature work

Suggested next phase:

```text
Phase 13.2 - runtime diagnostics boundary review
```

### Candidate D - deferred source-manifest content parsing behavior contract

Type: Python tooling product/behavior contract.

Goal:

- revisit isolated `--source-manifest <existing-file>` content parsing

Pros:

- known deferred Python tooling issue

Cons:

- not core CE/Lua work
- requires explicit product/behavior decision
- should remain deferred unless project owner chooses tooling behavior work

Suggested next phase:

```text
Phase 13.2 - source-manifest parsing behavior contract
```

## Recommendation

Default recommendation:

```text
Candidate A - CE/Lua current-state revalidation plan
```

Rationale:

- Python tooling/docs stabilization is complete
- before changing runtime scripts, the project needs a safe current-state revalidation plan
- CE should remain blocked until a later task explicitly authorizes it
- this bridges back to core workflow without touching runtime behavior

Candidate B can follow after current-state revalidation identifies the algorithmic target. Candidate C can be combined with Candidate A only if kept docs-only and narrow. Candidate D remains deferred unless explicitly selected.

## Missing Information For Next Phase

The next phase must clarify:

- which runtime case/target will be used
- whether CE execution is allowed or still blocked
- whether current `true_addr` / `known_true_addr` is available
- whether logs should be collected or only inspected
- allowed diagnostic level
- whether baseline/registry/session writes are allowed
- files allowed to change
- required tests/smokes before commit/tag

## Safety Boundaries For Next Phase

Until explicitly changed:

- no CE run
- no runtime log writes
- no registry/session/baseline/intake writes
- no local config mutation
- no `src/run_case_config.local.lua` or `.bak` mutation
- no broad source edits
- no `git add .`
- no tag until final smoke/checkpoint
- Python tooling write surface unchanged
- wrapper read-only

## Suggested Next Task File

Recommended:

```text
core_feature_phase13_2_ce_lua_current_state_revalidation_plan_task.md
```

Alternative if Candidate B is chosen:

```text
core_feature_phase13_2_candidate_ranking_next_module_selector_task.md
```
