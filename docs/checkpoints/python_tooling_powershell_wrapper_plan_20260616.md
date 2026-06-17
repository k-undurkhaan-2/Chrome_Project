# Python Tooling PowerShell Wrapper Plan - 2026-06-16

## Summary

This checkpoint records Phase 4.3 planning for a future read-only PowerShell thin wrapper around Python tooling.

## Scope

Planning only:

- no wrapper implementation
- no `.ps1` file added
- no Python command added
- no Python behavior changed
- no CE run
- no report, manifest, bundle, log, registry, baseline, session, intake, or local config writes

## Planned Wrapper Direction

The future wrapper should call `.venv\Scripts\python.exe -m armedforces_tool ...` and stay thin. It should not reimplement Python analysis logic in PowerShell.

Initial planned wrapper scope is read-only:

- status overview
- command inventory
- report command inventory
- full-status report preview
- manifest list / verify
- bundle preview / verify

## Explicitly Deferred

Deferred from the first wrapper phase:

- real report export
- report export with manifest recording
- bundle export dry-run
- real bundle export
- CE operations
- write / restore operations
- local config mutation
- log, registry, baseline, session, intake, report, manifest, or bundle writes

## Safety Model

The wrapper should fail closed, forward Python exit codes, and reject write-capable commands. Protected-file hash checks should be part of wrapper smoke validation.

## Next Step

The recommended next implementation task is a read-only wrapper pilot for `status` and `inventory` only, with no write-capable command exposure.
