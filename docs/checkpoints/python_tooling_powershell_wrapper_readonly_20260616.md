# Python Tooling PowerShell Wrapper Read-Only Implementation - 2026-06-16

## Summary

This checkpoint records the first read-only PowerShell thin wrapper implementation for Python tooling.

## Added Wrapper

Wrapper file:

```text
src/python_tooling_wrapper.ps1
```

Supported read-only commands:

- `status`
- `inventory`
- `report-status`
- `manifest-verify`
- `bundle-verify`

## Forbidden Commands

The wrapper rejects write-capable or runtime-adjacent commands, including:

- `report-export`
- `report-export-manifest`
- `bundle-export`
- `bundle-export-dry-run`
- `write`
- `restore`
- `ce`
- `baseline-save`
- `safe-reset`
- `set-diagnostic`
- `prepare-current-case`
- `collect-prepare`
- `case-intake-abandon`

## Boundary

The wrapper calls `.venv\Scripts\python.exe -m armedforces_tool ...`, forwards stdout/stderr, and propagates Python exit codes. It does not create reports, manifests, bundles, logs, registry files, baselines, session state, intake journals, or local config.

## Next Step

Keep the wrapper read-only. Any future write-capable wrapper command requires a separate plan, contract, validation, cleanup policy, and checkpoint.
