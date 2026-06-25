# CE/Lua Quick Revalidation Contract

## Purpose

This contract defines the boundary for a future controlled CE/Lua quick runtime smoke in Phase 13.4.

This contract does not authorize CE by itself. This contract does not run CE. Actual CE execution requires a future task that explicitly says CE is allowed. Actual Lua runtime execution requires a future task that explicitly says Lua runtime execution is allowed.

Protected local state must not be committed. The future quick smoke is not a full workflow, not a baseline save, and not an implementation task.

## Stable Baseline

- main repo path: `D:\armedforces.io-v2`
- legacy repo warning: do not use `D:\Lua Developer` unless explicitly instructed
- latest Python tooling checkpoint tag: `python-tooling-invalid-output-extension-rejection-checkpoint-20260621`
- wrapper remains read-only
- `writes_files_count = 2`
- `runs_ce_count = 0`
- no source/test/wrapper/Lua/PowerShell changes are introduced by this contract phase
- CE is blocked in this contract phase

## Future Operator Authorization Checklist

A future CE quick smoke task must collect explicit operator answers for each item below. This contract intentionally does not fill these values.

| Permission | Future operator input |
|---|---|
| CE execution allowed | yes/no |
| Lua runtime script execution allowed | yes/no |
| quick workflow only | yes/no |
| full workflow allowed | yes/no |
| local config write allowed | yes/no |
| runtime log write allowed | yes/no |
| registry write allowed | yes/no |
| active session write allowed | yes/no |
| session history write allowed | yes/no |
| case intake write allowed | yes/no |
| baseline write allowed | yes/no |
| post-run classifier allowed | yes/no |
| diagnostic level allowed | `basic`, `debug`, or `trace` |
| final git status may contain allowed untracked runtime/log files | yes/no |

If any required permission is ambiguous, Phase 13.4 must stop before CE, Lua execution, local config writes, or runtime state writes.

## Required Current Case Inputs

The future CE quick smoke task must collect or confirm:

- target runtime / game / process context
- current test case name or id
- current `true_addr` / `known_true_addr`, if available
- whether true address is expected before the run or supplied after the run
- target value
- value type / scan type, if applicable
- expected candidate or candidate group, if known
- expected quick workflow profile
- diagnostic level
- whether old session/log state should be preserved, ignored, or explicitly referenced
- whether the test should compare to a previous checkpoint or baseline

Unknown values must remain unknown until supplied by the operator. Do not infer a live runtime target from historical logs.

## Local Config Policy

Protected local config files:

```text
src/run_case_config.local.lua
src/run_case_config.local.lua.bak
```

Default rule:

- no write in this contract phase
- no commit ever
- no `git add .`
- future CE quick smoke may write or update local config only if explicitly authorized

If a future task authorizes local config writes, it must:

- show intended field changes before writing if possible
- preserve backup behavior if existing tooling supports it
- record before/after hashes
- confirm final local config files are not staged
- confirm `.gitignore` protection or local-only/untracked status
- never commit local config or backup files

Fields likely requiring future confirmation:

```text
known_true_addr
true_addr
target_value
target_value_type
target_mode
diagnostic_level
session_id / case_id if current workflow uses it
```

Use actual field names from existing config/tooling if different.

## Runtime State Write Policy

Protected runtime/local state files and directories:

```text
log/case_registry.jsonl
log/active_test_session.local.json
log/test_session_history.local.jsonl
log/case_intake.local.jsonl
log/
reports/
docs/reports/
```

Default rule:

- no writes in this contract phase
- future CE quick smoke may write only the minimum scoped runtime/log/session files explicitly allowed by the future task
- baseline writes are forbidden unless explicitly authorized in a separate baseline task
- safe-reset is forbidden unless explicitly authorized
- broad log cleanup is forbidden unless explicitly authorized
- runtime artifacts must not be committed

If future quick smoke writes logs/session/registry/intake state, it must:

- record before/after file existence
- record before/after hashes for pre-existing protected files
- identify expected new files
- keep writes local/runtime only
- finish with a clean `git status` or only explicitly allowed untracked local runtime artifacts
- never stage log/report/local state files

## Allowed Future Quick Workflow

The future quick smoke boundary is:

```text
quick workflow only
diagnostic_level = basic by default
single/current case only
minimal runtime sample
post-run classification only if authorized
no baseline save
no safe reset
no full workflow
```

Future quick smoke may use existing workflow tooling only if explicitly authorized, including:

```text
src/test_session_tool.ps1
src/case_config_tool.ps1
src/batch_log_classifier.ps1
```

This contract does not provide runtime-executing commands. Phase 13.4 must provide its own exact commands only after operator authorization is explicit.

## Future-Only Command Categories

Safe in this contract phase:

```text
git status / git log / git tag inspection
source and docs grep
source and log directory inventory
read-only Python tooling wrapper status
read-only Python tooling wrapper inventory
```

Future-only, allowed only if Phase 13.4 explicitly authorizes CE/Lua/runtime writes:

```text
CE execution
Lua runtime script execution
test_session_tool quick action
case_config_tool local config write action
batch_log_classifier latest quick classification
any command that writes log/session/registry/intake/local config
```

Forbidden unless a separate explicit task authorizes:

```text
full workflow
baseline-save
safe-reset
set-diagnostic trace/debug beyond the allowed diagnostic level
broad log cleanup
report export / report bundle export
Python tooling write-capable export commands
running from D:\Lua Developer
committing local config/log/report/runtime artifacts
git add .
```

## Future Pre-Run Checks

Before runtime execution, Phase 13.4 must verify:

- repo path is `D:\armedforces.io-v2`
- legacy `D:\Lua Developer` is not used
- git tracked status is clean
- expected checkpoint tag exists
- CE permission is explicit
- Lua runtime permission is explicit
- local config permission is explicit if config must be changed
- log/session/registry/intake write permission is explicit if quick workflow writes them
- `true_addr` / `known_true_addr` policy is clear
- target value/mode/type is clear
- diagnostic level is `basic` unless otherwise authorized
- protected file hash snapshot is captured
- wrapper remains read-only
- Python tooling write surface remains unchanged

## Quick Smoke PASS/WARN/FAIL Criteria

### PASS

PASS if:

- quick workflow completes
- collector is not runtime-empty
- output is not incomplete
- classification returns success or a clearly useful quick-success style result
- candidate/rank/stable fields appear if expected
- true address evaluation is possible if true address was supplied
- no unexpected protected file mutation occurs
- no source/test/docs files change unexpectedly
- no baseline save or safe reset occurs
- no broad cleanup occurs
- final git status is clean or only shows explicitly allowed untracked runtime artifacts
- runtime artifacts are not staged

### WARN

WARN if:

- quick workflow completes but true address was not supplied, so hit cannot be evaluated
- classification is useful but not baseline-eligible
- candidate/rank/stable fields are partial but explainable
- only explicitly allowed runtime/log files changed
- final status contains only explicitly allowed untracked local logs

### FAIL

FAIL if:

- CE permission was ambiguous
- Lua execution happened without explicit authorization
- collector/runtime output is empty
- output is incomplete
- classification cannot determine useful state
- unexpected protected file mutation occurs
- source/test/docs changed unexpectedly
- local config changed without authorization
- baseline save occurred without authorization
- safe reset occurred without authorization
- broad log cleanup occurred
- wrong repo path was used
- legacy `D:\Lua Developer` was used
- runtime artifacts were staged
- final git status has unexpected changes

## Future Output Requirements

The future Phase 13.4 final report must include:

- explicit permissions received
- current case inputs used
- local config changes, if any
- protected hashes before/after
- commands run
- quick workflow result
- classifier result
- candidate/rank/stable summary
- true address/hit result if supplied
- runtime artifacts created
- final git status
- PASS/WARN/FAIL result
- recommendation:
  - proceed to full smoke
  - repeat quick smoke with corrected inputs
  - select implementation target
  - stop and fix runtime issue

## Recommended Next Task

Phase 13.5D quick revalidation passed with batch `20260625-233355`, `quick_success`, `best_candidate = 0x27A061C7D48`, and true-address rank 1. Quick profile skipped stable intersection, so Phase 13.6 prepares the full smoke contract in `docs/architecture/core_feature_ce_lua_full_smoke_contract.md` for future stable-rank validation.

After this contract is committed, recommended next task:

```text
core_feature_phase13_4_ce_lua_quick_revalidation_smoke_task.md
```

This future task may authorize CE/Lua quick smoke only if the user explicitly agrees and supplies the required inputs.

Alternative if the user does not want CE yet:

```text
core_feature_phase13_4_candidate_ranking_next_module_selector_task.md
```

## No Tag Policy

No tag is recommended for this contract phase.

Future checkpoint tags should wait for an implementation/validation sequence and final smoke.
