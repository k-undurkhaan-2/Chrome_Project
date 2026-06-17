# Python Tooling PowerShell Wrapper Contract

## Purpose

This contract defines the future read-only PowerShell thin wrapper interface, safety boundary, error handling, and validation requirements for Python tooling.

This task only writes the contract. It does not implement the wrapper, add a PowerShell script, add a Python command, change Python behavior, run CE, or write runtime artifacts.

## Current Baseline

Current stable baseline:

- Phase 3 final checkpoint tag: `python-tooling-phase3-final-checkpoint-20260616`
- Phase 4.3 wrapper planning completed in `docs/architecture/python_tooling_powershell_wrapper_plan.md`
- command inventory: about `49` commands
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable Python commands:
  - `report export`
  - `report bundle export`
- read-only Python report support includes:
  - `report manifest preview`
  - `report manifest list`
  - `report manifest verify`
  - `report bundle preview`
  - `report bundle verify`
- no CE/runtime mutation exists in Python tooling
- no log/config/session/intake/baseline/registry writes have been introduced

## Wrapper File And Entrypoint

Future wrapper filename:

```text
src/python_tooling_wrapper.ps1
```

This file must not be created in this contract task. Future implementation requires a separate implementation task.

The wrapper is only a thin operator bridge:

- it must not contain business logic
- it must not reimplement Python parser or analysis logic
- it must not bypass Python command inventory
- it must not hide Python safety status
- it must not call write-capable commands in the first phase

## Execution Model

The wrapper must prefer:

```text
.venv\Scripts\python.exe
```

Execution rules:

- do not use system Python by default
- if `.venv` Python is missing, fail clearly and exit nonzero
- do not auto-create a virtual environment
- do not install dependencies
- do not modify persistent environment variables
- process-local `PYTHONPATH` may be set only if explicitly needed
- do not write any files
- forward the Python command exit code

## Approved Wrapper Commands, First Phase

The first implementation phase may only wrap these read-only commands:

- `status`
- `inventory`
- `report-status`
- `manifest-verify`
- `bundle-verify`

Suggested mappings:

```powershell
status ->
  .venv\Scripts\python.exe -m armedforces_tool status overview

inventory ->
  .venv\Scripts\python.exe -m armedforces_tool commands list --category report

report-status ->
  .venv\Scripts\python.exe -m armedforces_tool report preview --type full-status

manifest-verify ->
  .venv\Scripts\python.exe -m armedforces_tool report manifest verify

bundle-verify ->
  .venv\Scripts\python.exe -m armedforces_tool report bundle verify
```

## Explicitly Forbidden Wrapper Commands

The first wrapper phase must not wrap:

- `report export`
- `report export --record-manifest`
- `report bundle export`
- `report bundle export --dry-run`
- any write-capable command
- any CE/runtime command
- `baseline-save`
- `safe-reset`
- `set-diagnostic`
- `prepare-current-case`
- `collect-prepare`
- `case-intake-abandon`
- any command writing log/config/session/intake/baseline/registry files
- any command writing runtime report/manifest/bundle files

## Command Mapping Table

| Wrapper command | Python command | Read-only? | Writes files? | Runs CE? | Allowed in first wrapper? | Expected safe output |
| --- | --- | --- | --- | --- | --- | --- |
| `status` | `status overview` | yes | no | no | yes | `SAFE` visible |
| `inventory` | `commands list --category report` | yes | no | no | yes | `writes_files_count=2`, `runs_ce_count=0` visible |
| `report-status` | `report preview --type full-status` | yes | no | no | yes | CLI full-status preview |
| `manifest-verify` | `report manifest verify` | yes | no | no | yes | manifest status or `NO_MANIFEST` |
| `bundle-verify` | `report bundle verify` | yes | no | no | yes | bundle verification status |
| not allowed | `report export` | no | yes | no | no | blocked before invocation |
| not allowed | `report export --record-manifest` | no | yes | no | no | blocked before invocation |
| not allowed | `report bundle export --dry-run` | yes | no | no | no | blocked in first wrapper phase |
| not allowed | `report bundle export` | no | yes | no | no | blocked before invocation |

## Output Behavior

The wrapper should pass through Python stdout/stderr by default.

Rules:

- do not rewrite JSON content
- do not hide error status
- a concise wrapper summary is allowed only if the Python result remains visible
- `NO_MANIFEST` should be treated as informational when the Python command treats it that way
- `BAD_PATH` should be exposed as-is
- `SAFE`, `writes_files_count`, and `runs_ce_count` must remain visible in relevant command output

## Exit Code Behavior

Exit code contract:

- Python command success -> wrapper exits `0`
- Python command nonzero -> wrapper returns the same nonzero exit code
- missing `.venv` Python -> wrapper exits nonzero
- unsupported wrapper command -> wrapper exits nonzero
- `NO_MANIFEST` behavior follows the underlying Python command and must not be rewritten

## Safety Guarantees

The wrapper must guarantee:

- it does not write `reports/`
- it does not write `docs/reports/`
- it does not write `log/`
- it does not write local config
- it does not write registry/baseline/session/intake files
- it does not write runtime report files
- it does not write runtime manifest files
- it does not write runtime bundle files
- it does not create `reports/python_tooling/bundles/`
- it does not create bundle directories, zip files, `bundle_manifest.json`, or `index.md`
- it does not run CE
- it does not call Lua
- it does not execute real report export
- it does not execute report export with manifest recording
- it does not execute real bundle export
- it does not execute bundle export dry-run in the first phase
- it does not trigger any write-capable command

## Path And Working Directory Behavior

Path rules:

- the wrapper should be run from `D:\armedforces.io-v2`
- if the current directory is not the repository root, the wrapper should fail clearly or require an explicit repo root parameter
- do not search external paths
- do not accept arbitrary output paths in the first wrapper phase
- do not generate files
- do not create directories
- handle paths with spaces by using argument arrays, not string-built shell commands

## Validation Requirements For Future Implementation

Future wrapper implementation must validate:

- wrapper `status` returns `SAFE`
- wrapper `inventory` reports `writes_files_count=2` and `runs_ce_count=0`
- wrapper `report-status` does not create a report file
- wrapper `manifest-verify` does not create a manifest
- wrapper `bundle-verify` does not create a bundle
- wrapper rejects unsupported commands
- wrapper does not call `report export`
- wrapper does not call `report export --record-manifest`
- wrapper does not call `report bundle export --dry-run`
- wrapper does not call `report bundle export`
- wrapper does not write `reports/`
- wrapper does not write `docs/reports/`
- wrapper does not write `log/`
- wrapper does not write config/session/intake/baseline/registry files
- wrapper does not write runtime report/manifest/bundle files
- no CE is run
- git status is clean after smoke
- protected-file hashes are unchanged after smoke

## Failure Handling

Future wrapper implementation must handle:

- `.venv` Python missing: clear error, nonzero exit
- `armedforces_tool` module missing: clear error, nonzero exit
- Python command returns nonzero: preserve nonzero exit
- unsupported wrapper command: list supported read-only wrapper commands, nonzero exit
- PowerShell execution policy issue: print the recommended `-ExecutionPolicy Bypass` invocation
- path with spaces: handle without shell string concatenation
- permission denied: clear error, nonzero exit
- `NO_MANIFEST`: informational if the Python command reports it as informational
- `BAD_PATH`: expose the protected path rejection directly

The wrapper must fail closed. It must not retry with write-capable alternatives.

## Future Extension Policy

Any write-capable wrapper command requires separate:

- planning
- contract
- dry-run behavior where applicable
- smoke validation
- cleanup policy
- checkpoint

Read-only wrapper implementation must not opportunistically add write-capable wrappers.

`report export` and `report bundle export` must not be included as convenience shortcuts in the first wrapper.

The wrapper must not bypass Python command inventory. If a command is write-capable in inventory, it must not be exposed by a read-only wrapper phase.

## Explicit Non-Goals

This contract does not authorize:

- implementing the wrapper
- adding `src/python_tooling_wrapper.ps1`
- adding any `.ps1` file
- adding Python commands
- changing Python behavior
- wrapping write-capable commands
- wrapping CE/runtime mutation
- replacing `test_session_tool.ps1`
- replacing `batch_log_classifier.ps1`
- replacing `case_config_tool.ps1`
- changing Lua/runtime/algorithm behavior
- modifying the existing PowerShell workflow
- creating reports, manifests, bundles, logs, registry files, baselines, session state, intake journals, or local config
