# Python Tooling Phase 4 Final State

## Purpose

This document records the Phase 4 final state / handoff summary for Python tooling.

Use it before starting future tooling work to quickly confirm:

- what is currently available
- which safety boundaries are frozen
- which workflows are stable
- which areas are not migrated yet
- which future Phase 5 directions are possible

## Checkpoint Tags

Current checkpoints:

- `python-tooling-phase3-final-checkpoint-20260616`
- `python-tooling-powershell-wrapper-readonly-checkpoint-20260616`

Meaning:

- Phase 3 final checkpoint: Python report / manifest / bundle tooling stable baseline.
- PowerShell wrapper read-only checkpoint: read-only PowerShell wrapper implemented and boundary-smoked.

## Current Stable Command State

Current Python tooling state:

- command inventory: about `49` commands
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable Python commands:
  - `report export`
  - `report bundle export`
- no CE/runtime mutation exists in Python tooling
- no log/config/session/intake/baseline/registry writes have been introduced

## Read-Only PowerShell Wrapper State

Wrapper file:

```text
src/python_tooling_wrapper.ps1
```

Allowed wrapper commands:

- `status`
- `inventory`
- `report-status`
- `manifest-verify`
- `bundle-verify`

Recommended invocation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 inventory
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 report-status
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 manifest-verify
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 bundle-verify
```

Direct `.ps1` execution may be blocked by local PowerShell `ExecutionPolicy`. Use `ExecutionPolicy Bypass -File` as the recommended operator invocation. No system `ExecutionPolicy` change is required.

## Frozen Safety Boundary

The current wrapper boundary is frozen:

- wrapper is read-only
- wrapper does not wrap `report export`
- wrapper does not wrap `report export --record-manifest`
- wrapper does not wrap `report bundle export`
- wrapper does not wrap `report bundle export --dry-run`
- wrapper does not run CE
- wrapper does not call Lua
- wrapper does not write `reports/`
- wrapper does not write `docs/reports/`
- wrapper does not write `log/`
- wrapper does not write local config
- wrapper does not write registry / baseline / session / intake files
- wrapper does not create bundle directories or zip files

## Current Operator Workflows

### Direct Python Read-Only Checks

```powershell
.venv\Scripts\python.exe -m armedforces_tool status overview
.venv\Scripts\python.exe -m armedforces_tool commands list --category report
.venv\Scripts\python.exe -m armedforces_tool report manifest verify
.venv\Scripts\python.exe -m armedforces_tool report bundle verify
```

### Wrapper Read-Only Checks

Use these wrapper commands:

- `status`
- `inventory`
- `report-status`
- `manifest-verify`
- `bundle-verify`

### Write-Capable Python Operations

Currently only:

- `report export`
- `report bundle export`

These remain direct Python commands only. They must not be invoked through the read-only wrapper.

Future write-capable wrapper support requires separate policy, contract, dry-run behavior where applicable, smoke validation, cleanup policy, and checkpoint work.

## What Is Not Migrated Yet

Not migrated:

- CE automation
- runtime write/restore
- log writes
- registry writes
- `baseline-save`
- active session writes
- case intake writes
- diagnostic mutation
- local config mutation
- legacy PowerShell mutation workflow replacement

## Recommended Next Work

Future directions, without starting them here:

1. Phase 5 option A: write-capable wrapper policy planning
2. Phase 5 option B: runtime write/restore migration planning
3. Phase 5 option C: operator quick reference / troubleshooting consolidation
4. Phase 5 option D: read-only wrapper tests hardening
5. Phase 5 option E: bundle/report export UX polish

Any write-capable wrapper work requires separate planning, contract, dry-run behavior where applicable, smoke validation, cleanup policy, and checkpoint.

Do not mix write-capable wrapper work with read-only wrapper maintenance.

Phase 5 selector note: `docs/architecture/python_tooling_phase5_plan_selector.md` now defines the next-work planning gate. Phase 4 remains the frozen baseline, and future work should pass through that selector before implementation begins.

Phase 5.1 note: `docs/python_tooling_quick_reference.md` adds docs-only operator quick reference / troubleshooting consolidation. The Phase 4 frozen boundary remains unchanged.

Phase 5.2 note: the read-only wrapper now has dedicated boundary tests in `tests/test_python_tooling_wrapper_readonly.py`. The Phase 4 frozen boundary remains unchanged.

Phase 5.3 note: `docs/architecture/python_tooling_report_bundle_ux_plan.md` plans report/bundle export UX polish only. The Phase 4 frozen boundary remains unchanged.

Phase 5.4 note: `docs/architecture/python_tooling_report_bundle_ux_contract.md` defines the report/bundle UX contract only. The Phase 4 frozen boundary remains unchanged.

## Final Safety Statement

Phase 4 leaves Python tooling with stable read-only status/report visibility and a read-only PowerShell convenience wrapper, while preserving all CE/runtime/log/config/session/baseline/intake mutation boundaries.
