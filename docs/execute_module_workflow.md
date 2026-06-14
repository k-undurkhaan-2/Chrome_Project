# Execute Module Workflow Runbook

This runbook documents the current execute-module workflow for the active project at:

```text
D:\armedforces.io-v2
```

All Cheat Engine runtime execution is manual. The PowerShell tools prepare local config, inspect logs, classify batches, and report safety status; they do not start CE.

## Overview

The execute module workflow supports:

- detect-only quick and full validation
- guarded float writes
- expiring write arms
- restore config generation from successful write batches
- transaction tracking for write/restore pairing
- manual resolution of already-restored historical writes
- preflight safety checks through `doctor`

The fixed CE runtime command is:

```lua
dofile([[D:\armedforces.io-v2\src\execute_module-v5.2.0_batch.lua]])
```

## Safety First

Default operation should be detect-only. Live memory writes require explicit write mode, `write_enabled=true`, confirmation, a fresh write arm, full validation, stable rank guards, rank `A/W/B = 1/1/1`, and old-value checks.

Run these before and after risky work:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" doctor
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" status
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" execution-status -IncludeResolved
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" safe-reset -TargetValueFloat 100.0
```

After any successful write, restore the original value before returning to normal detect-only testing.

## Requirements

- Windows PowerShell
- Cheat Engine with Lua support
- Git
- The active checkout at `D:\armedforces.io-v2`

## Project Layout

```text
src/        Active Lua runtime modules and PowerShell tools
docs/       Project documentation
reports/    Reviewable reports
log/        Local runtime logs and generated local state, ignored by Git
archive/    Archived historical files
```

Main source entry points:

- `src/execute_module-v5.2.0_batch.lua`
- `src/mvp0_value_executor.lua`
- `src/mvp0_candidate_report.lua`
- `src/mvp0_foundlist_collector.lua`
- `src/test_session_tool.ps1`
- `src/case_config_tool.ps1`
- `src/batch_log_classifier.ps1`

## Common Commands

Run full preflight:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" doctor
```

List workflow commands or inspect one command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" help
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" help -Command prepare-restore
```

Show current local config, recent classifier output, registry summary, and Git status:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" status
```

Preview what the next manual CE run would do:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" plan
```

Show current diagnostic/logging level:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" diagnostic-status
```

Check write/restore transaction safety:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" execution-status -IncludeResolved
```

Return to safe detect-only target config:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" safe-reset -TargetValueFloat 100.0
```

Compare recent clean full batches to the baseline:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" compare-full
```

Summarize case coverage for the rolling full baseline window:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" case-summary
```

Summarize the tested known-true-address library:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" case-library
```

## Baseline Management

Baseline files are local Markdown snapshots under:

```text
D:\armedforces.io-v2\log\baselines
```

They are ignored local state and must not be committed.

List local baselines:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" baseline-list
```

Show the current default `compare-full` baseline:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" baseline-current
```

Save a new baseline from the latest baseline-eligible full batches:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" baseline-save -Name "full_clean_YYYYMMDD" -Latest 20
```

Compare against a named baseline file:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" baseline-compare -Baseline "baseline_compact_basic_20260613_latest20.md"
```

`baseline-save` rejects path traversal and writes only under `log\baselines`.

## Coverage / Case Summary

Use `case-summary` when `compare-full` reports a coverage warning, or before saving a new baseline:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" case-summary -Latest 20
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" coverage-plan -Latest 20 -TargetUnique 13
```

The command is read-only. It does not run CE, does not write registry or baseline files, and does not modify local config.

It reports:

- current baseline-eligible batch count
- current unique `known_true_addr` count
- repeated addresses and top repeated address
- baseline target coverage, when a baseline is available
- estimated new distinct addresses needed for the rolling latest-N window

## Known True Address Lifetime

`known_true_addr` is scoped to the active manual CE/process/session/scene. It can be reused for extra full clean confirmations only while the same manual test session is still valid.

After the user stops the test, the process/session changes, the scene is refreshed, or the target address may no longer match the current runtime state, the address becomes historical evidence only. Historical addresses are useful for coverage analysis and baseline evidence, but they are not guaranteed reusable runtime targets.

Use `retest-queue -ActiveSession` or `sample-plan -ActiveSession` only when the same manual session is still active. Without `-ActiveSession`, treat the planner output as a new-sample collection guide and collect fresh current-session addresses.

## Active Manual Test Session

Use the local session marker when you are deliberately keeping the same CE/process/session/scene alive while collecting additional confirmations:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" session-start -Label "baseline collection"
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" session-status
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" sample-plan -ActiveSession
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" session-end -Reason "collection complete"
```

By default, `session-start` creates a manual-only marker. It does not bind to a process, does not run CE, does not set an expiry, and does not auto-end. Expiry is intentionally disabled by default in the engineering build. Run `session-end` when CE/process/scene changes or testing ends.

Optional process tracking can be enabled when you want the tool to auto-end the marker if the tracked process exits or restarts:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" session-start -Label "tracked collection" -TrackProcess -ProcessId 12345
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" session-start -Label "tracked collection" -TrackProcess -ProcessName "target-process-name"
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" session-watch -IntervalSeconds 10
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" session-watch -Once
```

`session-watch` is optional foreground polling for process-tracked sessions. It does not run CE and only writes ignored local session state under `log\`.

`session-start` is only a local operator marker stored under ignored `log\`. It does not prove permanent address validity, and it does not make historical addresses safe after the process or scene changes.

Use `sample-plan -ActiveSession` or `retest-queue -ActiveSession` only while the same CE/process/session/scene is still unchanged. After ending the session, or after any process/scene refresh, run `session-end` and treat old addresses as historical evidence only.

## Case Collection Flow

Use `collection-flow` before collecting a new current-session `known_true_addr`. It is a read-only navigator that checks the current project path, config safety, target consistency, active session marker, plan state, and coverage hints, then recommends the next operator step:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" collection-flow
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" collect-guide
```

`collect-guide` is an alias for the same output. These commands do not run CE, do not write `run_case_config.local.lua`, do not append registry records, do not save baselines, and do not auto-end active session markers. If a process-tracked session is stale, the guide reports `STALE_TRACKED_SESSION` and leaves the local session file unchanged.

Typical conclusions:

- `NO_ACTIVE_SESSION`: start a new manual session, manually verify a current-session address, then prepare a full detect-only case.
- `READY_TO_COLLECT_CASE`: run `sample-plan -ActiveSession`, choose a currently valid address, prepare it, run CE manually, then `post-full`.
- `STALE_TRACKED_SESSION`: manually review or end the stale session before collecting new addresses.
- `BLOCKED_WRITE_CAPABLE`: run `safe-reset -TargetValueFloat 100.0` before detect-only collection.
- `BLOCKED_INVALID_CONFIG`: reset or fix target pattern/float consistency before CE.

The CE command remains:

```lua
dofile([[D:\armedforces.io-v2\src\execute_module-v5.2.0_batch.lua]])
```

## Case Library / Test Matrix

Use `case-library` to review historical `known_true_addr` coverage, active-session observations when the session is still valid, and the historical sample matrix from `log\auto_output`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" case-library
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" case-library -Latest 200
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" case-library -Profile full
```

The command is read-only. It does not run CE, does not write files, and does not modify local config. `known_true_addr` values in this report are reusable only within the same active manual test session; after the session ends, treat them as historical evidence only.

It reports per-address first/last seen batch, profiles seen, success counts, baseline-eligible counts, execution batch counts, invalid config counts, and `stable_case_candidate`.

## Stable Cases / Baseline Candidates

Use `stable-cases` to review stable evidence for baseline candidate coverage from collected logs:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" stable-cases
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" stable-cases -Latest 200
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" stable-cases -MinFullSuccess 1 -TargetUnique 13
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" stable-cases -ShowRejected
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" stable-cases -KnownTrueAddr "0x25A061C7D48"
```

`baseline-candidates` is an alias for the same read-only view. These commands do not run CE, do not write files, do not modify local config, and do not save a baseline. Use `baseline-save` separately when you intentionally want to write a local baseline snapshot under ignored `log\baselines`.

Stable here means stable evidence in collected logs, not permanent address validity. Old addresses are not guaranteed reusable after the manual session ends.

Use `-ShowRejected` to plan retests for addresses that are not yet stable baseline candidates. The output includes compact rejection reason codes and recommended retest actions. Use `-KnownTrueAddr` to inspect one address in detail; placeholder values such as `0x...` are rejected before any log scan.

## Retest Queue / Sample Plan

Use `retest-queue` to choose the next known true addresses worth collecting as clean full detect-only runs:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" retest-queue
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" retest-queue -Latest 200 -Limit 10
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" sample-plan
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" retest-queue -ActiveSession
```

`sample-plan` is an alias for the same read-only planner. These commands use rejected `stable-cases` data to rank addresses as `HIGH`, `MEDIUM`, `LOW`, or `BLOCKED`. They do not run CE, do not write files, do not modify local config, and do not save a baseline. Use `baseline-save` separately when you intentionally want to write a local baseline snapshot.

If the current manual test session is still active, listed addresses may be reused for additional full clean confirmations. Pass `-ActiveSession` only in that case. If the manual session has ended, use the queue as a new-sample collection plan and collect new current-session addresses instead.

## Detect-Only Workflow

1. Reset to a safe detect-only target:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" safe-reset -TargetValueFloat 100.0
```

2. Prepare a quick case:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" prepare -KnownTrueAddr "0x25A061C7D48" -Profile quick
```

3. Preview the next run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" plan
```

4. Run CE manually:

```lua
dofile([[D:\armedforces.io-v2\src\execute_module-v5.2.0_batch.lua]])
```

5. Classify the quick result:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" post-quick
```

6. Prepare a full case:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" prepare -KnownTrueAddr "0x25A061C7D48" -Profile full
```

7. Run `plan`, then run CE manually again with the same fixed `dofile(...)` command.

8. Classify the full result:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" post-full
```

9. Compare clean full detect-only batches:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" compare-full
```

`compare-full` uses baseline-eligible full batches only, so execution batches and invalid config batches are skipped.

## Guarded Write Workflow

1. Run preflight:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" doctor
```

2. Prepare a guarded write:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" prepare-guarded-write -KnownTrueAddr "0x25A061C7D48" -WriteValueFloat 999.0 -ConfirmWrite
```

3. Preview the armed write and confirm `danger_level = WRITE_CAPABLE` only when you are ready:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" plan
```

4. Run CE manually before the write arm expires:

```lua
dofile([[D:\armedforces.io-v2\src\execute_module-v5.2.0_batch.lua]])
```

5. Inspect execution output:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" post-execution
```

Expected successful write signals:

- `transaction_type = write_success`
- `write_attempted = true`
- `write_ok = true`
- `readback_ok = true`
- `rollback_available = true`

The default write arm expires after 10 minutes. If it expires, regenerate the write config before running CE.

## Restore Workflow

1. Prepare restore config from a successful `write_success` batch:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" prepare-restore -BatchId "YYYYMMDD-HHMMSS" -EnableWrite -ConfirmWrite
```

Replace `YYYYMMDD-HHMMSS` with a real batch id, for example `20260613-225514`.

2. Preview the restore and confirm `next_run_type = restore_write` before running CE:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" plan
```

3. Run CE manually:

```lua
dofile([[D:\armedforces.io-v2\src\execute_module-v5.2.0_batch.lua]])
```

4. Inspect restore output:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" post-execution
```

Expected successful restore signals:

- `transaction_type = restore_success`
- `write_attempted = true`
- `write_ok = true`
- `readback_ok = true`

5. Reset to safe detect-only config:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" safe-reset -TargetValueFloat 100.0
```

6. Run a full detect-only batch afterward to verify the restored target state.

## Transaction Safety

Check current transaction status:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" execution-status -IncludeResolved
```

If a historical `write_success` was restored manually outside the logged restore workflow, mark it resolved:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" mark-write-resolved -BatchId "YYYYMMDD-HHMMSS" -Reason "manual restore to 100.0"
```

Use manual resolution only after confirming the live value was restored.

## Diagnostic Levels

Default daily runs should use compact/basic diagnostics:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" set-diagnostic -Level basic
```

Check the current diagnostic and logging state:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" diagnostic-status
```

Available levels:

- `basic`: default daily mode, compact output.
- `debug`: targeted investigation only; reset to `basic` afterward.
- `trace`: deep investigation only; logs can be large, reset to `basic` afterward.

Enable investigation diagnostics explicitly:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" set-diagnostic -Level debug
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" set-diagnostic -Level trace
```

Diagnostic logs are local runtime output under `log/` and must not be committed.

## Doctor / Preflight

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" doctor
```

The doctor checks:

- project path
- required source files
- local config presence and ignore status
- config validation
- execution write/confirm/arm safety
- diagnostic level policy
- target float/pattern consistency
- active unpaired writes
- baseline comparison status
- ignored local log/config files
- staged local safety files

Exit code behavior:

- `SAFE`: exit `0`
- `ATTENTION`: exit `0`, review warnings
- `FAIL`: exit `1`

## Git Hygiene

Do not commit:

- `log/`
- `log/*.jsonl`
- `log/baselines/*.md`
- `src/run_case_config.local.lua`
- `src/run_case_config.local.lua.bak`
- `docs/codex_tasks/`

Before committing:

```powershell
git status --short
cmd /c git diff --check -- docs/execute_module_workflow.md README.md
```

The intended commit for this runbook should include only `docs/execute_module_workflow.md`.

## Troubleshooting

`<WRITE_BATCH_ID>` is a placeholder. Replace it with a real batch id such as `20260613-225514`.

`missing_execution_arm` means the write config is missing arm fields. Regenerate the guarded write or restore config.

`execution_arm_expired` means the write arm expired. Regenerate the config and run CE before the next expiry.

`restore_old_value_mismatch` means the current value does not match the expected current value from the write batch. Do not force restore; inspect the current memory state first.

`missing_execution_addr` means the executor could not determine a safe write address. Re-run full detect-only validation and inspect execution fields.

`invalid_config_mismatch` means `target_value_pattern` does not match `target_value_float`. Run config validation and reset the target if needed.

`known_true_value_mismatch` means the known true address was found but does not contain the expected target value. Check whether a write changed the target value.

`NOT_BASELINE_ELIGIBLE` means the batch should not be used as a clean detect-only baseline. Use `compare-full`, which filters to baseline-eligible full batches.
