# Python Tooling Candidate B Isolated Manifest Path Support Contract

## Purpose

This contract defines a future implementation to add isolated manifest path support for:

```text
report export --record-manifest
```

This contract does not implement the option. It does not execute `report export`, `--record-manifest`, dry-run export, or any bundle command. A future implementation requires a separate source/test phase, and future real Candidate B validation still requires a later write-authorized smoke.

The purpose is to let Candidate B validation write a manifest record to an isolated validation file instead of mutating the production/default manifest:

```text
reports/python_tooling/manifest.jsonl
```

## Problem Statement

Phase 6.3B Candidate B validation stopped correctly:

```text
STOP: isolated Candidate B manifest path is not supported by existing CLI contract.
```

The current `--record-manifest` implementation writes to a fixed default path:

```text
REPORT_MANIFEST_PATH = Path("reports/python_tooling/manifest.jsonl")
```

Risk:

- current `--record-manifest` writes to fixed production/default tooling manifest state
- using the fixed default path for validation would mutate `reports/python_tooling/manifest.jsonl`
- Candidate B validation requires an isolated manifest file under the declared validation path
- adding isolated path support is safer than allowing default manifest mutation for validation

## Proposed Option

Canonical future option name:

```text
--manifest-out
```

Reason:

- existing report output option is `--out`
- `--manifest-out` clearly identifies the output manifest file path
- it avoids ambiguity with read-only manifest verification commands

Do not add aliases unless a future implementation phase explicitly justifies them.

Alternative names that should not be used unless justified:

```text
--manifest
--manifest-path
--record-manifest-path
```

## Future CLI Behavior

### Case 1: No `--record-manifest`

```powershell
report export --type full-status --out <report-path>
```

Required behavior:

- unchanged
- writes the report file only
- does not write a manifest
- Candidate A behavior remains unchanged

### Case 2: `--record-manifest` Without `--manifest-out`

```powershell
report export --type full-status --out <report-path> --record-manifest
```

Required behavior:

- unchanged for backward compatibility
- writes/records the manifest using the existing default path:
  - `reports/python_tooling/manifest.jsonl`
- this default path must not be used for Candidate B validation unless explicitly authorized by a separate policy

### Case 3: `--record-manifest` With `--manifest-out`

```powershell
report export --type full-status --out <report-path> --record-manifest --manifest-out <manifest-path>
```

Required behavior:

- writes the report to `<report-path>`
- writes/appends the manifest record to `<manifest-path>`
- validates the manifest path with approved root / protected path checks
- does not create or modify production/default `reports/python_tooling/manifest.jsonl`
- keeps report file content, manifest schema, and append semantics unchanged
- keeps Candidate B human-readable success output aligned with the current output wording contract

Expected present in human-readable success output:

- `REPORT_EXPORT_OK`
- `WRITE_COMPLETE`
- `MANIFEST_RECORDED`
- `APPROVED_ROOT`
- `CE_NOT_RUN`
- `WRAPPER_UNSUPPORTED`

Expected absent:

- `NO_FILES_WRITTEN`
- `MANIFEST_NOT_WRITTEN`
- `BUNDLE_EXPORT_COMPLETE`
- `BUNDLE_NOT_CREATED`
- `ZIP_UNSUPPORTED`

### Case 4: `--manifest-out` Without `--record-manifest`

```powershell
report export --type full-status --out <report-path> --manifest-out <manifest-path>
```

Required behavior:

- fail closed before writing anything
- return a non-success status / CLI error
- do not write the report file
- do not write the selected manifest file
- do not write the default manifest
- use clear error wording: `--manifest-out requires --record-manifest`

## Path Guard and Approved Root Policy

The future implementation must not weaken path guards.

Rules:

- `--manifest-out` must be validated by existing approved-root/protected-path logic, or a shared equivalent used for output files
- Candidate B validation manifest path must be under `reports/python_tooling/`
- do not expand approved roots unless separately authorized
- protected paths must remain protected
- paths outside approved roots must fail closed before writing anything
- traversal paths must fail closed before writing anything
- parent creation behavior must match existing safe writer conventions
- no `--force`
- no overwrite behavior added
- manifest append behavior is allowed only for the selected manifest path when `--record-manifest` is set

The default manifest behavior remains backward-compatible:

```text
report export --record-manifest
```

continues to use:

```text
reports/python_tooling/manifest.jsonl
```

That default path is not approved for Candidate B validation unless a future prompt explicitly authorizes default manifest mutation.

## Data Model / JSON Behavior

Future implementation should avoid changing JSON output unless required.

Default expectation:

- existing JSON / `to_dict()` behavior remains unchanged
- human-readable wording may include the selected manifest path only if the current output contract already exposes paths
- if internal result data needs a new field for the selected manifest path, tests must confirm backward-compatible JSON shape or explicitly document any change

## Command Inventory and Write Surface

Future implementation must preserve:

- expected command inventory count unless parser metadata changes only by option text
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable commands remain:
  - `report export`
  - `report bundle export`
- no new command
- no wrapper export shortcut
- no CE command
- no zip support
- no `--force`

## Wrapper Boundary

The read-only PowerShell wrapper must remain read-only.

Future `--manifest-out` support must not add wrapper shortcuts for:

- `report export`
- `report export --record-manifest`
- `report bundle export`
- any write-capable export path

## Future Implementation Files Likely Touched

Expected future implementation may touch:

- `src/armedforces_tool/cli.py`
- `src/armedforces_tool/report_export.py`
- `src/armedforces_tool/report_output_messages.py`, only if output path wording needs adjustment
- tests related to report export manifest behavior

Do not modify those files in this contract task.

## Future Tests Required

Required unit/CLI tests:

- `--manifest-out` appears in `report export --help`
- `--manifest-out` without `--record-manifest` fails closed before writing anything
- `--record-manifest --manifest-out <path>` writes manifest to the custom path
- default `reports/python_tooling/manifest.jsonl` is not written when `--manifest-out` is supplied
- default behavior without `--manifest-out` remains unchanged
- Candidate B human-readable success output still includes `MANIFEST_RECORDED`
- Candidate B human-readable success output does not include `BUNDLE_NOT_CREATED`
- Candidate A behavior remains unchanged
- Candidate C behavior remains unchanged
- dry-run behavior remains unchanged
- protected/outside-approved-root manifest path fails closed
- traversal manifest path fails closed
- `--force` remains unsupported
- JSON output remains unchanged, or any change is explicitly covered

Suggested test locations:

```text
tests/test_report_export_manifest_output_integration.py
tests/test_real_report_export_output_integration.py
tests/test_report_bundle_output_messages.py
new or existing manifest path option tests
```

## Future Validation Commands

The future implementation phase should run:

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"

.venv\Scripts\python.exe -m pytest tests/test_report_export_manifest_output_integration.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_real_report_export_output_integration.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_report_bundle_output_messages.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_report_bundle_dry_run_output.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest --basetemp .tmp_pytest
Remove-Item -Recurse -Force .tmp_pytest -ErrorAction SilentlyContinue
```

Also run read-only status/inventory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 inventory
```

## Runtime Artifact Policy for Future Implementation Phase

The future implementation phase should not execute real writes manually.

Tests may use temporary directories controlled by pytest.

The future implementation phase must not create:

- `reports/python_tooling/validation/`
- production/default `reports/python_tooling/manifest.jsonl`
- `reports/python_tooling/bundles/`
- `docs/reports/python_tooling`
- log/config/session/intake/baseline/registry files

## Future Candidate B Validation Smoke After Support

After implementation and boundary smoke pass, the Candidate B validation smoke can be rerun with:

```powershell
.venv\Scripts\python.exe -m armedforces_tool report export `
  --type full-status `
  --out reports/python_tooling/validation/phase6_real_write_output_validation/candidate_b_report_export_manifest/report_output.md `
  --record-manifest `
  --manifest-out reports/python_tooling/validation/phase6_real_write_output_validation/candidate_b_report_export_manifest/manifest.jsonl
```

Only the future smoke may execute that command. This contract task must not execute it.

## Stop Conditions for Future Implementation

Future implementation must stop if:

- adding `--manifest-out` requires write-surface expansion beyond existing `report export`
- adding it requires wrapper write support
- adding it requires CE/runtime mutation
- adding it weakens path guards
- adding it expands approved roots
- adding it changes JSON output in an undocumented way
- tests cannot keep Candidate A/B/C boundaries separate
- default manifest behavior cannot be preserved
- production/default manifest would be written by tests
- any runtime artifacts outside pytest temp paths would be created

## Next Phase Recommendation

Recommended next phase:

```text
Phase 6.5B: isolated manifest path support implementation
```

Scope:

- narrow source/test/docs implementation
- add `--manifest-out`
- no manual real writes
- no CE
- no wrapper changes
- no tag

Then:

```text
Phase 6.6B: isolated manifest path support boundary smoke
Phase 6.3B-R1: Candidate B report export manifest validation smoke rerun
```

## Tag Policy

- no tag is created by Phase 6.4B
- no tag should be created for contract-only work
- a future tag may be considered only after Candidate B and Candidate C validation smokes pass and cleanup is verified

## Out Of Scope

- implementation in this task
- tests in this task
- wrapper write-capable support
- CE automation
- runtime write/restore migration
- Candidate B execution
- Candidate C bundle validation
- production/default manifest mutation for validation
- zip export
- `--force`
- approved-root expansion
- path guard weakening
