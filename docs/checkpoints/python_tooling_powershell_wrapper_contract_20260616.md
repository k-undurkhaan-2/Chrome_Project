# Python Tooling PowerShell Wrapper Contract - 2026-06-16

## Summary

This checkpoint records the Phase 4.4 read-only PowerShell wrapper contract.

## Contract Status

The wrapper contract is documentation-only:

- no wrapper implementation
- no `src/python_tooling_wrapper.ps1`
- no new `.ps1` file
- no Python command
- no Python behavior change
- no CE run
- no runtime artifact write

## Approved First-Phase Wrapper Commands

Approved read-only first-phase wrapper commands:

- `status`
- `inventory`
- `report-status`
- `manifest-verify`
- `bundle-verify`

These map to existing Python commands and must preserve Python output and exit codes.

## Forbidden Wrapper Commands

Forbidden in the first wrapper phase:

- `report export`
- `report export --record-manifest`
- `report bundle export`
- `report bundle export --dry-run`
- write / restore commands
- CE/runtime commands
- local config, log, registry, baseline, session, intake, report, manifest, or bundle writes

## Safety Guarantees

The wrapper must remain read-only, must not run CE, must not call Lua, must not create report or bundle artifacts, and must not expose write-capable commands as convenience shortcuts.

## Validation Requirements

Future implementation must validate:

- `status` returns `SAFE`
- `inventory` keeps `writes_files_count=2` and `runs_ce_count=0`
- `report-status` writes no report file
- `manifest-verify` writes no manifest
- `bundle-verify` writes no bundle
- unsupported commands are rejected
- protected file hashes remain unchanged

## Next Step

The next implementation task, if scoped, should add a read-only wrapper pilot for `status` and `inventory` only.
