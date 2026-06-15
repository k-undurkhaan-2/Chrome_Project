# Python Tooling Phase 3 Plan

## Purpose

Phase 3 is a planning stage after completion of the Phase 2 read-only Python sidecar.

The goal is to define safe next migration candidates and their boundaries before adding more tooling. Phase 3 does not introduce write capability, does not automate CE, and does not replace the existing PowerShell workflow mutation commands.

Python remains a sidecar for read-only analysis, status, baseline visibility, parity checks, and operator-facing reports unless a separate write-capable contract is explicitly designed and reviewed.

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
- make the Python read-only layer write-capable
- replace PowerShell workflow mutation commands
- rewrite the screening/filtering algorithm
- modify collector, executor, or Lua runtime behavior
- add integer or bytes write support
- bypass current guarded `writeFloat` safety gates
- commit logs, local config, registry files, baselines, session files, or intake journals

## Recommended Execution Order

1. Registry read-only view
2. Transaction history read-only view
3. Report export planning
4. Thin PowerShell read-only wrapper pilot
5. Native backend contract planning

This order keeps the next steps low-risk and aligned with the current Phase 2 safety model.

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

## Suggested Next Concrete Task

Recommended Phase 3.1 task: `Python read-only registry view`.

Why this is the best next step:

- still read-only
- compatible with existing case-library, baseline, and status layers
- low risk
- useful for follow-on transaction and report views
- exercises local JSONL parsing without changing runtime behavior

Initial Phase 3.1 scope should be limited to reading existing registry files and presenting summary/recent/outlier-style views. It should not append registry records or replace PowerShell classifier append behavior.
