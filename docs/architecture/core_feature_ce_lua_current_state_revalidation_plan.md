# CE/Lua Current-State Revalidation Plan

## Purpose

This document defines the safe revalidation plan for returning to the CE/Lua workflow after Python tooling stabilization.

This is not a CE run authorization. This is not an implementation task. Future runtime validation requires explicit operator permission, current case inputs, and a task that scopes any allowed runtime state writes. Protected state files remain frozen until explicitly authorized.

## Stable Baseline

- main repo path: `D:\armedforces.io-v2`
- legacy repo warning: do not use `D:\Lua Developer` unless explicitly instructed
- latest Python tooling checkpoint tag: `python-tooling-invalid-output-extension-rejection-checkpoint-20260621`
- wrapper remains read-only
- `writes_files_count = 2`
- `runs_ce_count = 0`
- CE is blocked in this phase
- no runtime state writes are allowed in this phase

## Read-Only Preflight Inventory

| Area | Evidence to inspect | Current purpose | Risk / unknown |
|---|---|---|---|
| Lua runtime entrypoint | `src/execute_module-v5.2.0_batch.lua`; runbook fixed command in `docs/execute_module_workflow.md` | Manual CE Lua entrypoint for detect/full/write/restore-capable runtime workflow | Current live CE state and target process are unknown; do not execute without explicit authorization |
| value executor | `src/mvp0_value_executor.lua` | Value write/restore support used by guarded runtime paths | Write/restore behavior is out of scope until explicitly authorized |
| foundlist collector | `src/mvp0_foundlist_collector.lua` | Foundlist/candidate collection and stable intersection support | Collector state cannot be validated without CE; Stage 2 must detect runtime-empty cases |
| candidate report | `src/mvp0_candidate_report.lua` | Candidate scoring, prescore, rank, and report logic | Next algorithmic target is not selected |
| session workflow script | `src/test_session_tool.ps1` | Operator workflow, doctor/status/plan/session/case tools | Many commands can write local state; future task must explicitly allow any stateful command |
| case config tool | `src/case_config_tool.ps1` | Local config and run-case configuration support | `src/run_case_config.local.lua` and `.bak` are protected |
| batch classifier | `src/batch_log_classifier.ps1` | Runtime log classification and registry/baseline/session support | Classification may read/write local logs/registry depending command; future scope must be explicit |
| run case local config | `src/run_case_config.local.lua`, `.bak`, example config | Local runtime target/config carrier | Must not be mutated during planning; future Stage 1 must define exact fields and write permission |
| case registry | `log/case_registry.jsonl` | Local historical case registry | Protected local state; writes require explicit authorization |
| active session | `log/active_test_session.local.json` | Local active manual-session marker | Protected local state; writes require explicit authorization |
| session history | `log/test_session_history.local.jsonl` | Local session history | Protected local state; writes require explicit authorization |
| case intake journal | `log/case_intake.local.jsonl` | Local prepared/post case intake journal | Protected local state; writes require explicit authorization |
| baseline files | `log/baselines/` and baseline docs/checkpoints | Baseline comparison/reference state | Baseline save remains forbidden unless explicitly authorized |
| diagnostic controls | `diagnostic_level` in Lua/config/status tooling | Controls runtime diagnostic verbosity | Future task must select `basic`, `debug`, or `trace` before runtime work |
| Python tooling wrapper/status | `src/python_tooling_wrapper.ps1`, `src/armedforces_tool/*.py` | Read-only status/inventory support plus guarded report write commands outside CE | Wrapper remains read-only; Python tooling is support infrastructure, not CE runtime authorization |

## Required Operator Inputs Before CE Run

A future CE-authorized task must collect these inputs without guessing:

- current runtime target / game state / process context
- whether CE execution is allowed
- whether Lua script execution is allowed
- current `true_addr` / `known_true_addr`, if available
- whether true address should be manually supplied after each run
- target value / value type / target mode if applicable
- allowed diagnostic level:
  - `basic`
  - `debug`
  - `trace`
- whether log writes are allowed
- whether registry writes are allowed
- whether session writes are allowed
- whether baseline writes are allowed
- whether local config writes are allowed
- whether post-run classification is allowed
- whether full workflow or quick workflow is allowed

Unknown values must remain unknown until the operator supplies them.

## Protected Files And State

These files/directories must not be modified unless a future task explicitly authorizes them:

```text
src/run_case_config.local.lua
src/run_case_config.local.lua.bak
log/case_registry.jsonl
log/active_session.json
log/active_test_session.local.json
log/session_history.jsonl
log/test_session_history.local.jsonl
log/case_intake_journal.jsonl
log/case_intake.local.jsonl
log/
reports/
docs/reports/
```

Do not use `git add .`. Never commit local config, logs, reports, runtime artifacts, or temp files. Stage only explicit source/docs/test files intended for commit.

## Staged Future Revalidation Workflow

Each stage requires explicit permission before moving to the next.

### Stage 0 - read-only confirmation

Allowed:

- inspect repo
- inspect docs/source
- inspect wrapper status/inventory
- inspect current git status
- inspect current tags
- inspect presence/absence of protected files

Forbidden:

- CE
- Lua execution
- config writes
- log writes
- registry/session/baseline/intake writes

Pass criteria:

- clean git status
- protected files unchanged
- wrapper SAFE/read-only
- Python tooling write surface unchanged
- operator inputs collected for next stage

### Stage 1 - local config planning

Allowed only if explicitly authorized in a future task:

- prepare instructions for `src/run_case_config.local.lua`
- identify fields that must be set
- no actual local config write unless authorized

Required fields to plan:

- `known_true_addr` or equivalent current true address field
- target value/mode/type if current workflow requires it
- diagnostic level
- session/case identifier if required

Pass criteria:

- operator confirms values
- no accidental commit-tracked local config change
- no runtime execution yet

### Stage 2 - CE quick smoke, if authorized

Allowed only if a future task explicitly says CE is allowed.

Expected future workflow:

- use the established quick workflow only
- keep diagnostic level at `basic` unless user authorizes more
- collect the minimum runtime/log sample
- avoid baseline-save
- avoid safe-reset
- avoid broad registry/session mutation unless scoped
- run classifier only if the task allows it

Pass criteria:

- collector not runtime-empty
- no incomplete output
- classification success or clearly classified failure
- candidate/rank/stable fields present if expected
- true address match can be evaluated only if true address was supplied
- no unexpected artifacts outside allowed log/runtime paths
- git tracked source/docs/test files remain clean unless implementation task explicitly modifies them

### Stage 3 - CE full smoke, if quick smoke passes and authorized

Allowed only after Stage 2 passes and operator authorizes full workflow.

Expected future workflow:

- full runtime collection
- post-full classification
- compare expected rank/stable/candidate fields
- no baseline save unless specifically authorized

Pass criteria:

- full workflow completes
- classification success or useful failure class
- stable rank behavior recorded
- no protected file mutation outside task scope
- final git status clean except allowed untracked runtime logs if task allows them

### Stage 4 - implementation target selection

After revalidation, decide whether the next implementation target is collector, filter, prescore, stable intersection, rank stability, source address handling, diagnostics boundary, or documentation.

Do not implement until a separate task authorizes it.

## Revalidation Command Policy

This phase does not provide a command that runs CE.

Safe now:

- `git status`
- read-only grep
- wrapper status/inventory
- Python tooling status/inventory
- source/docs file inspection

Only allowed with explicit future CE authorization:

- Lua execution
- `test_session_tool.ps1` quick/full runtime actions
- any command that writes logs/session/registry/baseline/intake/local config

Always forbidden unless explicitly scoped:

- baseline save
- safe reset
- broad cleanup of logs
- committing local state
- running from `D:\Lua Developer`

## Expected Future Task Names

Phase 13.3 quick revalidation contract is prepared in `docs/architecture/core_feature_ce_lua_quick_revalidation_contract.md`. CE remains blocked until Phase 13.4 explicitly authorizes CE execution and Lua runtime execution. The next runtime task must collect operator permissions and current case inputs before any quick smoke.

Phase 13.5D quick smoke passed with `quick_success` for `0x27A061C7D48`. Phase 13.6 full smoke contract is prepared in `docs/architecture/core_feature_ce_lua_full_smoke_contract.md`; CE remains blocked until explicit future full-smoke authorization.

Recommended next task:

```text
core_feature_phase13_7_full_profile_config_manual_dofile_handoff_task.md
```

Alternative if the user does not want CE yet:

```text
core_feature_phase13_7_candidate_ranking_next_module_selector_task.md
```

## Stop Conditions For Future CE Task

A future CE-authorized task must stop if:

- operator has not supplied runtime target/case
- CE permission is not explicit
- true address is required but missing
- current git status is dirty unexpectedly
- local config is missing or inconsistent
- protected files would be modified outside scope
- log/registry/session/baseline write permissions are unclear
- quick smoke returns collector/runtime empty
- incomplete output appears
- classification cannot determine a useful state
- source edits would be required during runtime validation
- legacy repo path is active

## No Tag Policy

No tag is recommended for this planning phase. A future checkpoint tag is appropriate only after an implementation/validation sequence and final smoke.
