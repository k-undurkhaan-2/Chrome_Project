# Python Tooling Operator Guide

## Purpose

The Python tooling is a read-only sidecar for `D:\armedforces.io-v2`.

It is for analysis, status checks, parity checks, and operator visibility. It does not replace the existing PowerShell workflow, does not run CE, and does not write config, log, registry, baseline, session, or intake files.

Use Python tooling when you want a fast, structured view of the current project state. Continue to use the PowerShell tools for workflow mutation, local config updates, guarded runtime actions, and operator commands that intentionally write local state.

## Daily Commands

Recommended daily entry points:

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"

python -m armedforces_tool status overview
python -m armedforces_tool commands quickstart
python -m armedforces_tool commands list
python -m armedforces_tool safety doctor
python -m armedforces_tool baseline compare
python -m armedforces_tool case summary --latest 20 --profile full
python -m armedforces_tool registry summary
python -m armedforces_tool transaction summary
python -m armedforces_tool report preview --type full-status
```

## Command Groups

### `logs`

Read batch summary logs and compare Python parsing with the PowerShell classifier.

Representative commands:

```powershell
python -m armedforces_tool logs parse-latest --latest 5 --profile full
python -m armedforces_tool logs parse-batch --batch-id "20260614-232227"
python -m armedforces_tool logs parity-latest --latest 5 --profile full
```

### `case`

Analyze case coverage, historical known-true address evidence, stable candidates, retest queues, and sample plans.

Representative commands:

```powershell
python -m armedforces_tool case summary --latest 20 --profile full
python -m armedforces_tool case library --latest 100 --profile all
python -m armedforces_tool case stable-cases --latest 100 --profile full
python -m armedforces_tool case retest-queue --latest 100 --profile full
python -m armedforces_tool case sample-plan --latest 100 --profile full
```

### `safety`

Read local safety state and compare Python safety summaries with existing PowerShell checks.

Representative commands:

```powershell
python -m armedforces_tool safety status
python -m armedforces_tool safety plan
python -m armedforces_tool safety execution-status
python -m armedforces_tool safety doctor
python -m armedforces_tool safety doctor-parity
```

### `status`

Read workflow-facing status summaries, including diagnostic level, case intake state, and consolidated overview.

Representative commands:

```powershell
python -m armedforces_tool status diagnostic
python -m armedforces_tool status case-intake
python -m armedforces_tool status overview
```

### `baseline`

Read baseline metadata and compare the current baseline-eligible full window against the default baseline.

Representative commands:

```powershell
python -m armedforces_tool baseline list
python -m armedforces_tool baseline current
python -m armedforces_tool baseline compare
```

### `registry`

Read the local case registry JSONL without appending records or replacing the PowerShell classifier append workflow.

Representative commands:

```powershell
python -m armedforces_tool registry summary
python -m armedforces_tool registry list --limit 20
python -m armedforces_tool registry show --known-true-addr "0xCE061C7D48"
python -m armedforces_tool registry show --batch-id "20260614-232227"
```

### `transaction`

Read execution transaction history from existing batch summaries and registry records. This is for visibility only; it does not generate write or restore commands.

Representative commands:

```powershell
python -m armedforces_tool transaction summary
python -m armedforces_tool transaction list --limit 20
python -m armedforces_tool transaction list --transaction-type write_success
python -m armedforces_tool transaction show --batch-id "20260614-232227"
python -m armedforces_tool transaction show --known-true-addr "0x2CA061C7D48"
```

### `report`

Render existing Python read-only summaries as Markdown to stdout. This is preview-only: it does not write `.md` files, does not create directories, and does not implement `report export`.

Representative commands:

```powershell
python -m armedforces_tool report preview
python -m armedforces_tool report preview --type baseline-compare
python -m armedforces_tool report preview --type full-status
python -m armedforces_tool report preview --type full-status --json
```

Supported preview types include `status-overview`, `safety-doctor`, `baseline-compare`, `case-summary`, `registry-summary`, `transaction-summary`, and `full-status`.

### `commands`

Discover Python sidecar commands and their safety properties. This is not a replacement for argparse `--help`; it is an operator index.

Representative commands:

```powershell
python -m armedforces_tool commands list
python -m armedforces_tool commands quickstart
python -m armedforces_tool commands show --command "status overview"
```

## Safety Boundary

The current Python tooling layer is read-only.

It must not:

- run CE
- write local config
- write logs, registry, baselines, session files, or intake journals
- replace the guarded PowerShell workflow
- mutate runtime state
- perform guarded writes or restores
- generate write or restore actions from transaction history
- write Markdown report files from `report preview`

Any future write-capable command must be designed as a separate explicit contract. Do not mix write-capable workflows into the current read-only Python sidecar layer.

## Known Acceptable WARNs

The following parity WARN results are currently acceptable and are not Python failures:

- `status case-intake-parity` may WARN because PowerShell does not expose `active_session_detected`.
- `baseline current-parity` may WARN because PowerShell does not expose profile / unique count.
- `baseline compare-parity` may WARN because PowerShell does not expose coverage count fields.

Other WARN or FAIL results should be reviewed before checkpointing.

## Checkpoint Tags

- `python-tooling-readonly-analysis-checkpoint-20260615`: Python read-only log, case summary, case library, stable-cases, and sample planning analysis.
- `python-safety-status-checkpoint-20260615`: Python safety status, plan, and execution-status sidecar checks.
- `python-doctor-safety-checkpoint-20260615`: Python aggregate safety doctor.
- `python-workflow-status-checkpoint-20260615`: Python diagnostic and case-intake status views.
- `python-baseline-status-checkpoint-20260615`: Python baseline list/current/compare views.
- `python-status-overview-checkpoint-20260615`: Python consolidated status overview.
- `python-command-inventory-checkpoint-20260615`: Python command inventory, quickstart, and descriptor index.

## Recommended Smoke Commands

```powershell
cd D:\armedforces.io-v2
$env:PYTHONPATH="D:\armedforces.io-v2\src"

python -m armedforces_tool status overview
python -m armedforces_tool commands quickstart
python -m armedforces_tool safety doctor
python -m armedforces_tool baseline compare
python -m armedforces_tool case summary --latest 20 --profile full
python -m armedforces_tool report preview --type full-status

.venv\Scripts\python.exe -m pytest --basetemp .tmp_pytest
Remove-Item -Recurse -Force .tmp_pytest -ErrorAction SilentlyContinue

git status --short
```

## Current Stable State

Current expected stable results:

- `status overview = SAFE`
- `safety doctor = SAFE`
- `baseline compare = BASELINE_COMPARE_PASS`
- `case summary = COVERAGE_OK`
- command inventory = 40 read-only commands after Phase 3.4 report preview
- pytest = 97 passed

## Next Migration Candidates

Possible next read-only migration directions:

- Python read-only registry view
- Python read-only transaction history view
- Python report export with controlled file writes, after a separate write-capable contract
- thin PowerShell wrappers that call Python
- later native backend contract planning

Do not migrate guarded write / restore yet.

Do not automate CE yet.

Do not mix write-capable workflows into the current read-only Python layer.

## Git Hygiene

Do not commit:

- `log/`
- `log/*.jsonl`
- `log/baselines/*.md`
- `src/run_case_config.local.lua`
- `src/run_case_config.local.lua.bak`
- `docs/codex_tasks/`

Python smoke checks should leave the working tree clean except for intentional documentation or source changes.
