# Python Tooling Phase 3 Plan

## Purpose

Phase 3 is a planning stage after completion of the Phase 2 read-only Python sidecar.

The goal is to define safe next migration candidates and their boundaries before adding more tooling. Phase 3 does not automate CE and does not replace the existing PowerShell workflow mutation commands.

Python remains a sidecar for analysis, status, baseline visibility, parity checks, and operator-facing reports. Write capability is allowed only when a separate contract is explicitly designed, reviewed, validated, and checkpointed.

## Current Phase 2 Stable Baseline

Current stable state at the Phase 2 complete checkpoint:

- `status overview = SAFE`
- `safety doctor = SAFE`
- `baseline compare = BASELINE_COMPARE_PASS`
- `case summary = COVERAGE_OK`
- command inventory = 33 read-only commands
- pytest = 64 passed
- protected files unchanged in final smoke
- Phase 2 complete checkpoint tag: `python-tooling-phase2-complete-20260615`

## Current Phase 3 State

Phase 3 current state as of 2026-06-16:

- `status overview = SAFE`
- command inventory = `42` commands
- `writes_files_count = 1`
- `runs_ce_count = 0`
- only write-capable Python command = `report export`
- `report preview` remains stdout-only
- `report export --dry-run` remains no-write
- guarded `report export` writes only approved `.md` report files
- approved report export roots:
  - `reports/python_tooling/`
  - `docs/reports/python_tooling/`
- current pytest result: `114 passed`

Completed Phase 3 tracks:

- registry view:
  - `registry summary`
  - `registry list`
  - `registry show`
  - read-only behavior
  - checkpoint: `python-registry-status-checkpoint-20260615`
- transaction history view:
  - `transaction summary`
  - `transaction list`
  - `transaction show`
  - write/restore history is visible but not executable
  - checkpoint: `python-transaction-history-checkpoint-20260615`
- report preview:
  - `report preview`
  - stdout-only behavior
  - `full-status` is CLI-friendly by default
  - Markdown output requires `--format markdown`
  - checkpoints:
    - `python-report-preview-checkpoint-20260615`
    - `python-report-preview-cli-checkpoint-20260615`
- report export dry-run:
  - `report export --dry-run`
  - no-write path safety preview
  - checkpoint: `python-report-export-dry-run-checkpoint-20260615`
- guarded report export:
  - first write-capable Python command
  - writes only approved `.md` report files
  - default no overwrite
  - `--force` only under approved roots
  - checkpoints:
    - `python-report-export-guarded-checkpoint-20260616`
    - `python-report-export-boundary-checkpoint-20260616`

Non-goals still active:

- no CE automation
- no guarded write / restore migration
- no Python writes to log, config, session, intake, baseline, or registry files
- no PowerShell workflow mutation replacement
- no Lua/runtime changes
- no algorithm rewrite

## Phase 3 Candidate Tracks

### Track A - Read-Only Registry View

Goal: add Python read-only views over registry / case history data.

Useful outputs could include:

- registry summary
- recent records
- classification breakdown
- active vs historical execution-related records
- invalid config / non-baseline-eligible summaries

Boundary:

- do not write registry files
- do not replace classifier append behavior
- do not change PowerShell behavior
- do not add mutation commands

### Track B - Read-Only Transaction History View

Goal: add Python read-only views over execution transaction history, including write / restore state.

Useful outputs could include:

- write_success and restore_success history
- unpaired write visibility
- manually resolved write markers
- transaction timeline summaries

Boundary:

- analyze only
- do not enable writes
- do not generate write-ready restore configs
- do not trigger restore or safe-reset workflows

### Track C - Report Export / Markdown Rendering

Goal: plan Python report rendering for operator-readable summaries.

Possible reports:

- coverage reports
- baseline comparison reports
- registry summaries
- transaction summaries
- case-library snapshots

Boundary:

- default behavior remains read-only
- any file-writing report command must be designed separately
- output paths, overwrite behavior, and ignored/report directories must be explicit
- do not silently write to `log/`, registry, baseline, session, intake, or local config paths

### Track D - Thin PowerShell Wrappers Calling Python

Goal: pilot selected PowerShell read-only commands that call Python internally, reducing duplicate parsing and analysis logic.

Good first candidates:

- read-only baseline status commands
- read-only case-summary / case-library views
- read-only safety / status display commands

Boundary:

- do not change guarded write / restore / runtime mutation commands
- preserve PowerShell command names and operator output expectations
- start with read-only commands only
- keep rollback path simple by leaving Python sidecar commands available directly

### Track E - Native Backend Contract Planning

Goal: document future C/C++/Rust backend request/result contracts.

This track is contract planning only. It is not native backend implementation.

Boundary:

- no native backend code
- no process attach implementation
- no memory write implementation
- no replacement for CE runtime
- preserve all current safety gates in any future design

## Explicit Non-Goals

Phase 3 should not:

- migrate guarded write / restore
- automate CE
- add additional write-capable Python commands without a separate contract and checkpoint
- replace PowerShell workflow mutation commands
- rewrite the screening/filtering algorithm
- modify collector, executor, or Lua runtime behavior
- add integer or bytes write support
- bypass current guarded `writeFloat` safety gates
- commit logs, local config, registry files, baselines, session files, or intake journals

## Completed Execution Order

1. Registry read-only view
2. Transaction history read-only view
3. Report export planning
4. Report preview
5. Report export dry-run
6. Guarded report export
7. Report export boundary documentation

This order kept Phase 3 risk-managed: read-only visibility came first, and the only write-capable command was implemented after an explicit report export contract.

## Required Gates Before Any Write-Capable Work

Any future write-capable Python work requires a separate design checkpoint before implementation.

Required gates:

- separate write-capable contract
- separate checkpoint
- explicit user confirmation flow
- dry-run first
- protected file hash checks
- rollback / restore plan
- clear boundary from existing read-only command inventory
- no mixing of write-capable workflows into current read-only commands
- no CE automation without a dedicated request/result safety design

## Suggested Next Candidates

Potential next tasks:

- report manifest planning
- report bundle format planning
- thin PowerShell read-only wrapper pilot
- native backend contract planning
- write-capable feature policy template

Any future write-capable Python task should follow the `report export` pattern: explicit contract, dry-run where applicable, protected-file checks, validation cleanup rules, and a checkpoint before expanding scope.
