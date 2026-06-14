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

## Detect-Only Workflow

1. Reset to a safe detect-only target:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" safe-reset -TargetValueFloat 100.0
```

2. Prepare a quick case:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" prepare -KnownTrueAddr "0x25A061C7D48" -Profile quick
```

3. Run CE manually:

```lua
dofile([[D:\armedforces.io-v2\src\execute_module-v5.2.0_batch.lua]])
```

4. Classify the quick result:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" post-quick
```

5. Prepare a full case:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" prepare -KnownTrueAddr "0x25A061C7D48" -Profile full
```

6. Run CE manually again with the same fixed `dofile(...)` command.

7. Classify the full result:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" post-full
```

8. Compare clean full detect-only batches:

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

3. Run CE manually before the write arm expires:

```lua
dofile([[D:\armedforces.io-v2\src\execute_module-v5.2.0_batch.lua]])
```

4. Inspect execution output:

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

2. Run CE manually:

```lua
dofile([[D:\armedforces.io-v2\src\execute_module-v5.2.0_batch.lua]])
```

3. Inspect restore output:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" post-execution
```

Expected successful restore signals:

- `transaction_type = restore_success`
- `write_attempted = true`
- `write_ok = true`
- `readback_ok = true`

4. Reset to safe detect-only config:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\test_session_tool.ps1" safe-reset -TargetValueFloat 100.0
```

5. Run a full detect-only batch afterward to verify the restored target state.

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
