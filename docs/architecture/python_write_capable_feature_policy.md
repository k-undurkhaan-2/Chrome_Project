# Python Write-Capable Feature Policy

## Purpose

This document defines the unified admission policy for any future Python write-capable feature in `D:\armedforces.io-v2`.

This policy does not authorize new writes by itself. It defines the required process, checks, and documentation before a new Python command may write files or modify durable state.

## Current Baseline

Current Python tooling baseline:

- only write-capable Python command = `report export`
- `writes_files_count = 1`
- `runs_ce_count = 0`
- `report export` writes only `.md` files under approved report roots:
  - `reports/python_tooling/`
  - `docs/reports/python_tooling/`
- `report export --dry-run` remains read-only and writes nothing
- no CE or runtime mutation exists in Python tooling

## Definition Of Write-Capable

### Read-Only

Read-only commands only inspect files, parse existing state, or print derived output. They do not write files, create directories, mutate local state, or run CE.

### Dry-Run / Preview

Dry-run or preview commands compute what would happen and print a plan, but write nothing. They may remain `read_only=true` only if they create no files, directories, journals, registry records, configs, or runtime state.

### Write-Capable

Write-capable commands may:

- write files
- create output files
- modify project files
- modify state, journal, config, log, session, intake, baseline, or registry data
- otherwise mutate durable project state

Any such command must follow this policy before implementation.

### Runtime-Mutating

Runtime-mutating commands may affect CE, attached processes, live memory, executor behavior, write/restore actions, or runtime state.

Runtime-mutating commands require a separate, stricter contract beyond this file. They must not be introduced through the general Python tooling sidecar without dedicated runtime safety design.

## Mandatory Lifecycle

Every write-capable feature must go through this sequence:

1. Planning document
2. Contract document
3. Dry-run only implementation
4. Dry-run smoke check
5. Dry-run checkpoint
6. Real write implementation
7. Guarded smoke check
8. Boundary / operator guide update
9. Final boundary checkpoint

No step should be skipped.

## Required Safety Gates

Every write-capable feature must define and validate:

- approved output or state roots
- explicit target path or explicit state target
- default no overwrite / no mutation
- dry-run first
- no protected file modification
- protected-file hash checks
- path traversal protection where paths are involved
- no CE run unless a separate CE-specific contract exists
- no PowerShell, Lua, or runtime mutation unless explicitly scoped
- cleanup rules for validation-created files
- command inventory risk marking

## Command Inventory Requirements

Every write-capable command must be reflected in command inventory metadata:

- `read_only=false`
- `writes_files=true` if it writes files
- `runs_ce=true` only if CE is actually invoked
- `risk_level` must not be `READ_ONLY`
- dry-run commands may remain `read_only=true` only if they write nothing

Current expected baseline:

- `report export` is write-capable
- `report export --dry-run` is read-only
- `runs_ce_count = 0`

## Protected Areas

By default, future Python write-capable features may not write to:

- `log/`
- `src/`
- `tests/`
- `docs/codex_tasks/`
- `.git/`
- `.codex/`
- `src/run_case_config.local.lua`
- `src/run_case_config.local.lua.bak`
- `log/case_registry.jsonl`
- `log/case_intake.local.jsonl`
- `log/active_test_session.local.json`
- `log/test_session_history.local.jsonl`
- `log/baselines/*.md`

These areas may only be written by Python if a future contract explicitly allows a narrow state mutation and defines rollback, tests, cleanup, and checkpoint gates.

## Validation-Created File Cleanup Rule

Smoke checks may create test output files only when the contract allows it.

When validation creates files:

- record every file created by the current validation
- delete only files created by the current validation
- never delete files that existed before the smoke check
- never delete pre-existing user directories
- report cleanup results explicitly

## Required Tests

Every write-capable feature must include tests for:

- dry-run writes nothing
- real write writes only the intended file or state
- bad path or bad state target rejected
- protected path rejected
- default overwrite / mutation rejected
- force / confirm only works within approved scope
- command inventory flags correct
- protected hashes unchanged outside the allowed target
- no CE unless explicitly part of the contract

## Manifest / Index State Note

Report manifest or report index files are write-capable state, even if they live under an approved report root.

The report manifest write contract follows this policy and keeps manifest writing separate from read-only manifest preview/list/verify commands. Append-only JSONL may reduce corruption risk compared with mutable JSON, but it is still write-capable state and still needs validation, duplicate handling, failure recovery, protected-file hash checks, cleanup rules, and command inventory marking.

## Bundle / Package State Note

Report bundle export is a separate write-capable surface.

A future bundle may create:

- bundle directories
- zip archives
- bundle manifests
- copied report files
- Markdown or JSON indexes

The report manifest write contract does not authorize bundle writes. Bundle directory, zip, index, copied report, and bundle manifest behavior require a separate planning document, a separate write contract, dry-run behavior, guarded smoke validation, cleanup rules, and a checkpoint before implementation.

The first bundle contract must define its own approved roots and must not inherit permission to write `docs/reports/`, `log/`, registry, baseline, session, intake, local config, source, tests, or `docs/codex_tasks/`.

## Required Final Report Fields

Every write-capable feature final report must include:

- commands run
- files changed
- allowed writes performed
- rejected writes tested
- cleanup result
- protected hashes
- command inventory flags
- pytest result
- CE/runtime confirmation
- final recommendation

## Template For Future Codex Tasks

```text
Background:
- <current checkpoint / stable state>

Current target:
- <feature name>
- <whether this is planning / contract / dry-run / real write>

Scope:
Allowed to modify:
- <files>

Forbidden modifications:
- src/*.ps1
- src/*.lua
- log/
- protected local files
- <feature-specific forbidden areas>

Dry-run requirements:
- <what dry-run computes>
- <must not write>

Real write requirements:
- <approved roots / state targets>
- <overwrite policy>
- <protected path rules>

Validation:
- <commands>
- <expected PASS/WARN/FAIL>

Cleanup:
- <validation-created files>
- <cleanup rules>

Protected hash check:
- <protected files>

Final Report Required:
- commands run
- files changed
- allowed writes
- rejected writes
- cleanup result
- protected hashes
- pytest result
- final recommendation
```

## Explicit Non-Goals

This policy does not authorize:

- guarded write / restore migration
- CE automation
- PowerShell mutation replacement
- Lua/runtime modification
- filtering algorithm rewrite

Those require separate contracts and checkpoints.
