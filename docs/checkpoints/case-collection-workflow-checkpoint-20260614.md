# Case Collection Workflow Checkpoint - 2026-06-14

## Tag Name

`case-collection-workflow-checkpoint-20260614`

## Branch

`armedforces.io-v2`

## Purpose

This checkpoint records the stable case collection workflow after the session-aware collection tooling was merged back to the main project branch.

It is intended as a recovery, handoff, and next-module planning reference for future work on case collection, baseline coverage, and operator workflow tooling.

## Included Features

This checkpoint includes:

- `collection-flow` / `collect-guide`
- active test session tracker
- `prepare-current-case` / `prepare-case`
- case intake journal
- `case-intake-status`
- `post-current-case`
- `case-intake-abandon`
- `sample-plan` / `retest-queue` active-session semantics

## Safety State

At this checkpoint:

- `doctor` was `SAFE`.
- `plan` reported `detect_only / SAFE`.
- `compare-full` was `PASS`.
- `case-summary` was `COVERAGE_OK`.
- `execution-status` was `SAFE`.
- Active unpaired successful writes were `0`.
- Case intake open count was `0`.
- Execution config was disabled for normal detect-only work.
- Current target was restored to `100.0 / 0x42C80000`.
- CE execution remained manual-only.

## Local-Only Files

The following files and directories are local runtime state and must not be committed:

- `log/`
- `log/case_intake.local.jsonl`
- `log/active_test_session.local.json`
- `log/test_session_history.local.jsonl`
- `src/run_case_config.local.lua`
- `src/run_case_config.local.lua.bak`
- `docs/codex_tasks/`

These files may exist during local operation, validation, or session tracking. They are intentionally excluded from committed project state.

## Normal Collection Flow

Run the preflight checks:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" doctor
```

Preview the next run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" plan
```

Open the collection guide:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" collection-flow
```

Start an active manual session:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" session-start -Label "case collection"
```

Prepare a current-session case after manually confirming a valid current address:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" prepare-current-case -KnownTrueAddr "0xCURRENTADDR" -Profile full
```

Run CE manually:

```lua
dofile([[D:\armedforces.io-v2\src\execute_module-v5.2.0_batch.lua]])
```

Record the completed intake after the CE run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" post-current-case
```

Check coverage:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" case-summary
```

End the active manual session when collection is done:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" session-end
```

## Active Session Semantics

Known true addresses are treated as current-session evidence.

An address collected during one manual session should not be reused as active test input after that session ends unless a new active session reconfirms the address. Historical logs can still be used for coverage, stability, and baseline planning, but they are not proof that the same address is valid in a later live CE session.

`sample-plan -ActiveSession` and `retest-queue -ActiveSession` are guarded by the local active session marker. If no active session exists, they should guide the operator to start a new session instead of implying old addresses are directly reusable.

If a prepared case will not be run in CE, close the open intake without rewriting history:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" case-intake-abandon -Reason "CE run skipped"
```

## Validation Summary

Validation at checkpoint readiness confirmed:

- `git status` was clean.
- `doctor` reported `SAFE`.
- `plan` reported `detect_only / SAFE`.
- `execution-status -IncludeResolved` reported `SAFE`.
- Active unpaired successful writes were `0`.
- `compare-full` reported `PASS`.
- `case-summary` reported `COVERAGE_OK`.
- Case intake open count was `0`.
- The case collection workflow was merged back to `armedforces.io-v2`.
- Runtime, executor, collector, classifier, ranking, scoring, threshold, quota, stable intersection, and screening/filtering algorithms were not changed by this manifest.

CE was not run as part of this manifest.

## Next Development Candidates

Possible next development modules:

- case-intake completed matching refinement after real CE run
- collection session metrics
- baseline refresh workflow
- compact operator dashboard
- next non-tooling algorithm module

These are roadmap candidates only. They are not implemented by this checkpoint.
