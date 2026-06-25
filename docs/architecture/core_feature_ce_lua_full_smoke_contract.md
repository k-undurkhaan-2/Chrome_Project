# CE/Lua Full Smoke Contract

## Purpose

This contract defines the boundary for a future controlled CE/Lua full-profile smoke after a successful quick smoke.

This contract does not authorize CE by itself. This contract does not run CE. Actual CE execution requires a future task that explicitly says CE is allowed. Actual Lua runtime execution requires a future task that explicitly says Lua runtime execution is allowed.

The full smoke is validation, not implementation. It must not run `baseline-save` unless a separate baseline task explicitly authorizes it.

## Quick-Smoke Evidence Baseline

Phase 13.5D passed the manual CE Lua post-quick / classifier gate.

| Field | Evidence |
|---|---|
| batch id | `20260625-233355` |
| classification | `quick_success` |
| validation profile | `quick` |
| transaction type | `detect_only` |
| collector empty | `false` |
| final hit | `True` |
| best candidate | `0x27A061C7D48` |
| rank A/W/B | `1/-/-` |
| stable rank | skipped because quick profile |
| total time | `3523 ms` |
| log size | `2719 bytes` |
| registry append | `appended_count=1`, `skipped_duplicate_count=0` |

Quick-profile evaluation used `0x27A061C7D48`. The stale address `0x272061C7D48` did not appear in the latest evaluation and must not be used for future hit/rank/stable-rank evaluation.

The quick gate reported no source/test/docs/wrapper/Lua/PowerShell changes, no baseline-save, no safe-reset, and no full workflow.

## Future Authorization Checklist

A future full smoke task must require explicit operator confirmation for:

```text
CE execution allowed: yes/no
Lua runtime script execution allowed: yes/no
full workflow allowed: yes/no
quick workflow only: yes/no

runtime target/case: <required>
current true_addr / known_true_addr: <required>
true address supplied before run or after run: before/after/unknown
target value: <required if workflow needs it>
target value type / scan type: <required if workflow needs it>
target mode: <required if workflow needs it>

diagnostic_level allowed: basic/debug/trace
post-run classifier allowed: yes/no

local config write allowed: yes/no
runtime log write allowed: yes/no
registry write allowed: yes/no
active session write allowed: yes/no
session history write allowed: yes/no
case intake write allowed: yes/no
baseline write allowed: yes/no

allowed runtime output location(s): <explicit list>
allowed files to modify: <explicit list>
allowed untracked runtime artifacts after run: <explicit list/pattern>
```

Recommended safe full-smoke authorization if the operator agrees:

```text
CE execution allowed: yes
Lua runtime script execution allowed: yes
full workflow allowed: yes
quick workflow only: no
diagnostic_level allowed: basic
post-run classifier allowed: yes
baseline write allowed: no
```

Do not infer this authorization from the quick-smoke pass. Phase 13.7 or another future task must explicitly provide it.

## Required Current Case Inputs

Future full smoke should use these inputs unless the operator changes them:

```text
runtime target/case: PID=00005948
current true_addr / known_true_addr: 0x27A061C7D48
true address supplied before run or after run: before
target value: 100
target value type / scan type: float/exact value
target mode: not required
diagnostic_level allowed: basic
```

If PID or true address has changed again, the future full-smoke task must stop and request fresh inputs.

## Local Config Policy

Protected local config:

```text
src/run_case_config.local.lua
src/run_case_config.local.lua.bak
```

Future full-smoke config may update only if explicitly authorized:

- `known_true_addr` / `true_addr = 0x27A061C7D48`
- `target_value_float = 100.0`
- `diagnostic_level = basic`
- `validation_profile = full`
- `execution_mode = disabled` or equivalent manual/no-auto-runtime mode

Rules:

- do not set diagnostic above `basic` unless explicitly authorized
- do not enable baseline-save
- do not run full workflow until config is confirmed
- record config/backup before/after hashes
- do not stage or commit local config or backup

## Runtime Write Policy

Allowed future full-smoke write locations only if explicitly authorized:

```text
log/auto_output/**
log/case_registry.jsonl
log/active_test_session.local.json
log/test_session_history.local.jsonl
log/case_intake.local.jsonl
```

Forbidden unless a separate explicit task authorizes:

```text
baseline files/checkpoints
reports/python_tooling/full_status.md
reports/python_tooling/manifest.jsonl
reports/python_tooling/bundles/
reports/python_tooling/validation/
docs/reports/python_tooling
source/test/docs/wrapper/Lua/PowerShell files
```

Baseline write remains `no` by default.

## Allowed Future Full Workflow

Future full smoke may use existing workflow tooling only after authorization.

Expected categories:

```text
config prepare for full profile
operator manual dofile in Cheat Engine Lua Engine
post-full classifier / full profile classifier
```

Because CE automation was unavailable in the quick phase, the likely future workflow is:

1. Codex prepares full-profile local config.
2. Operator manually runs:

```lua
dofile([[D:\armedforces.io-v2\src\execute_module-v5.2.0_batch.lua]])
```

3. Operator reports manual dofile completed.
4. Codex runs `post-full` / full classifier only after a new full batch is confirmed.

This contract contains future-only examples. It does not authorize or run those commands.

## Forbidden Commands And Actions

Future full smoke must not run:

```text
baseline-save
safe-reset
broad log cleanup
set-diagnostic debug/trace unless explicitly authorized
report export
report export --force
report export --record-manifest
report export dry-run
report bundle export
report bundle export dry-run
Python tooling write-capable export commands
any command from D:\Lua Developer
git add .
```

## Pre-Run Checks For Future Full Smoke

Future task must check:

- repo path is `D:\armedforces.io-v2`
- `D:\Lua Developer` is not used
- tracked git status is clean before runtime
- checkpoint tag exists
- quick evidence exists and is not stale
- PID/case is still valid
- true address is still valid
- local config has `0x27A061C7D48`
- validation profile is set to full only after authorization
- diagnostic level is `basic`
- baseline write remains disabled
- wrapper is SAFE/read-only
- Python tooling write surface is unchanged
- protected hashes are recorded before runtime
- latest auto_output marker is recorded before runtime

## New Full Batch Gate

Future post-full/classifier task must stop if:

- no new batch exists
- latest batch is the old quick batch `20260625-233355`
- latest batch is older than full-profile config refresh
- latest batch has no plausible output/log files
- latest batch belongs to the stale true address
- latest batch was not produced after the operator manual full dofile

## Full Smoke PASS/WARN/FAIL Criteria

### PASS

PASS if:

- full workflow completes
- collector is not runtime-empty
- output is not incomplete
- classifier returns success or a useful full-profile classification
- `0x27A061C7D48` is evaluated
- best candidate / hit / rank fields are present
- stable intersection fields are present
- stable rank can be evaluated
- no baseline-save occurs
- no safe-reset occurs
- no unexpected protected file mutation occurs
- no source/test/docs/wrapper/Lua/PowerShell changes occur
- only allowed runtime/log/session/registry/intake files changed
- runtime artifacts are not staged

### WARN

WARN if:

- full workflow completes but stable rank cannot be evaluated
- classification is useful but not baseline-eligible
- true address hit can be evaluated but stable fields are partial
- only allowed runtime files changed

### FAIL

FAIL if:

- CE permission is ambiguous
- Lua execution happened without explicit authorization
- quick workflow ran instead of full after full authorization
- collector/runtime output is empty
- output is incomplete
- classifier cannot determine useful state
- true address is missing or stale
- stale address `0x272061C7D48` is used for evaluation
- baseline-save occurred
- safe-reset occurred
- broad cleanup occurred
- report/bundle export ran
- source/test/docs/wrapper/Lua/PowerShell changed
- wrong repo path was used
- `D:\Lua Developer` was used
- runtime artifacts were staged
- final status has unexpected changes

## Future Output Requirements

Future full smoke final report must include:

- explicit authorization block
- current case inputs
- config changes made
- protected hashes before/after
- full batch id/path/timestamp/files
- exact commands run
- classifier result
- candidate/rank/stable summary
- true address hit/rank/stable-rank evaluation
- whether stale address appeared
- runtime artifacts changed
- final git status
- PASS/WARN/FAIL
- recommendation:
  - proceed to candidate/rank/stable next-module selector
  - repeat full smoke with corrected inputs
  - stop and fix runtime issue
  - prepare checkpoint candidate if full smoke is strong enough

## Recommended Next Tasks

After this contract is committed, recommended next task:

```text
core_feature_phase13_7_full_profile_config_manual_dofile_handoff_task.md
```

Then after operator manual dofile:

```text
core_feature_phase13_8_manual_ce_lua_post_full_classifier_gate_task.md
```

Alternative if operator does not want full smoke:

```text
core_feature_phase13_7_candidate_ranking_next_module_selector_task.md
```

## No Tag Policy

No tag is recommended for this contract phase.

A future checkpoint tag should only be considered after full smoke or a later implementation/validation sequence passes final smoke.
