# Python Tooling Wrapper Test Hardening - 2026-06-16

## Summary

Read-only PowerShell wrapper boundary tests were added.

## Coverage

The tests cover allowed wrapper commands:

- `status`
- `inventory`
- `report-status`
- `manifest-verify`
- `bundle-verify`

The tests cover forbidden wrapper commands:

- `report-export`
- `report-export-manifest`
- `bundle-export`
- `bundle-export-dry-run`
- `safe-reset`
- `set-diagnostic`
- `prepare-current-case`
- `collect-prepare`
- `case-intake-abandon`
- `unknown-command`

## Artifact Safety

Tests snapshot relevant report, manifest, bundle, and registry paths before and after wrapper calls. Existing user files are not deleted or cleaned by tests.

## Boundary

- no wrapper source behavior changed
- no Python behavior changed
- no Lua/runtime behavior changed
- no tag created by this task
