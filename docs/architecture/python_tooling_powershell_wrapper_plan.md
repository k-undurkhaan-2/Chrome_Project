# Python Tooling PowerShell Wrapper Plan

## Purpose

This document plans a future thin PowerShell wrapper layer for the Python tooling. It is planning only. It does not implement a wrapper, add a `.ps1` file, add a Python command, or change any existing workflow behavior.

The wrapper goal is operator convenience: keep the Windows entry point familiar while letting the existing Python sidecar commands own read-only status, inventory, preview, and verification logic.

## Baseline

Current stable baseline:

- Python tooling includes read-only analysis, safety/status, baseline, registry, transaction, manifest, bundle preview/verify, command inventory, and report preview commands.
- Write-capable Python commands are limited to:
  - `report export`
  - `report bundle export`
- `runs_ce_count = 0`.
- Existing PowerShell workflow mutation commands remain authoritative for runtime preparation, guarded write, restore, session state, intake state, and local config mutation.
- This planning phase introduces no source changes and no new write surface.

## Wrapper Principle

The wrapper must be a thin launcher, not a second implementation.

Rules:

- Call `.venv\Scripts\python.exe -m armedforces_tool ...` explicitly.
- Do not reimplement parser, safety, baseline, registry, transaction, report, manifest, or bundle logic in PowerShell.
- Preserve Python command output and exit codes where practical.
- Fail clearly if the project virtual environment is missing.
- Keep wrapper commands read-only in the first implementation phase.
- Do not use system Python by default.
- Do not mutate local config, logs, registry files, baselines, sessions, intake journals, reports, manifests, or bundles.

## Read-Only First Scope

The first wrapper implementation should expose only read-only commands.

Allowed first-phase wrapper targets:

- `status overview`
- `commands list`
- `commands list --category report`
- `report preview --type full-status`
- `report manifest verify`
- `report manifest list`
- `report bundle preview`
- `report bundle verify`

Not allowed in the first wrapper implementation:

- `report export`
- `report export --record-manifest`
- `report bundle export`
- `report bundle export --dry-run`
- CE runtime operations
- write / restore workflows
- local config mutation
- log, registry, baseline, session, intake, report, manifest, or bundle writes

The explicit exclusion of `report bundle export --dry-run` keeps the first wrapper phase purely read-only and avoids normalizing bundle export paths through a convenience entry point before a wrapper-specific validation checkpoint exists.

## Proposed Future Wrapper Shape

Potential command shape:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\python_tooling_wrapper.ps1" status
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\python_tooling_wrapper.ps1" inventory
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\python_tooling_wrapper.ps1" report-status
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\python_tooling_wrapper.ps1" manifest-verify
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\armedforces.io-v2\src\python_tooling_wrapper.ps1" bundle-verify
```

This file does not exist yet. It should not be created until a dedicated implementation task is scoped.

Each wrapper command should map to one Python command and forward the exit code. If arguments are added later, the wrapper should validate only shell-level input shape and delegate domain validation to Python.

Phase 4.4 adds a dedicated read-only wrapper contract in `docs/architecture/python_tooling_powershell_wrapper_contract.md`. Wrapper implementation has not started. The first implementation must remain read-only and must not expose report export, manifest recording, bundle export, CE/runtime commands, or PowerShell mutation workflows.

## Safety Model

Safety constraints:

- Read-only first.
- No CE execution.
- No PowerShell mutation workflow replacement.
- No write / restore actions.
- No report export or bundle export wrapper in the first phase.
- No output path creation.
- No directory creation.
- No hidden fallback to write-capable commands.
- No automatic cleanup of user files.
- No auto-detection that mutates session state.

The wrapper should run from `D:\armedforces.io-v2` and verify that the expected Python module can be invoked before launching command-specific work.

## Command Mapping Table

| Future wrapper command | Python command | Read-only | Writes files | Runs CE | Expected result | First phase |
| --- | --- | --- | --- | --- | --- | --- |
| `status` | `status overview` | yes | no | no | `SAFE` / clear status | allowed |
| `inventory` | `commands list` | yes | no | no | command inventory | allowed |
| `report-inventory` | `commands list --category report` | yes | no | no | report command inventory | allowed |
| `report-status` | `report preview --type full-status` | yes | no | no | CLI full status preview | allowed |
| `manifest-list` | `report manifest list` | yes | no | no | manifest records or `NO_MANIFEST` | allowed |
| `manifest-verify` | `report manifest verify` | yes | no | no | manifest verification status | allowed |
| `bundle-preview` | `report bundle preview` | yes | no | no | bundle candidate preview | allowed |
| `bundle-verify` | `report bundle verify` | yes | no | no | bundle verification status | allowed |
| not allowed | `report export` | no | yes | no | report write | blocked |
| not allowed | `report export --record-manifest` | no | yes | no | report + manifest write | blocked |
| not allowed | `report bundle export --dry-run` | yes | no | no | bundle export plan | blocked |
| not allowed | `report bundle export` | no | yes | no | bundle directory write | blocked |

## Validation Model

Before any wrapper implementation is accepted, validation should confirm:

- `git status --short` is clean before and after.
- No `src/*.lua` changes.
- No existing PowerShell mutation command behavior changes.
- Wrapper help lists only read-only commands.
- Each wrapper command exits with the same status as its Python target.
- `status` maps to Python `status overview`.
- report command inventory still shows the real write-capable Python commands accurately.
- No files are created under:
  - `log/`
  - `reports/`
  - `docs/reports/`
  - `reports/python_tooling/bundles/`
  - `src/run_case_config.local.lua`
  - `src/run_case_config.local.lua.bak`
- Protected file hashes are unchanged after wrapper smoke validation.

## Failure Handling

The wrapper should fail closed.

Expected failure handling:

- Missing `.venv\Scripts\python.exe`: print a clear setup error and exit nonzero.
- Python module import failure: print the command that failed and exit nonzero.
- Unknown wrapper command: list supported wrapper commands and exit nonzero.
- Attempted blocked command: print that write-capable commands are intentionally unsupported by the wrapper and exit nonzero.
- Python target nonzero exit: propagate nonzero exit and do not post-process into success.

The wrapper should not catch and suppress safety failures from Python.

## Explicit Non-Goals

This plan does not authorize:

- implementing a wrapper now
- adding a `.ps1` file now
- adding a Python command
- replacing `test_session_tool.ps1`
- replacing PowerShell mutation workflows
- running CE
- wrapping guarded write or restore
- wrapping `safe-reset`, `set-diagnostic`, `prepare-current-case`, `collect-prepare`, or `case-intake-abandon`
- wrapping real report export
- wrapping manifest recording
- wrapping bundle export
- writing logs, reports, manifests, bundles, registry files, baselines, sessions, intake journals, or local config
- zip bundle export
- `--force` / overwrite behavior

## Recommended Implementation Order

Recommended sequence:

1. Add a minimal read-only wrapper contract test plan.
2. Implement wrapper help and command dispatch only.
3. Add wrapper commands for `status` and `inventory`.
4. Add wrapper commands for manifest and bundle read-only verification.
5. Run protected-file hash validation.
6. Record a wrapper read-only boundary checkpoint.
7. Consider whether any dry-run wrapper belongs in a later phase.

Do not add write-capable wrapper commands until a separate wrapper-specific write contract exists.
