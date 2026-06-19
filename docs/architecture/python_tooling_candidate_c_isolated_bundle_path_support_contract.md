# Python Tooling Candidate C Isolated Bundle Path Support Contract

## Purpose

This contract defines future implementation support for isolated Candidate C bundle validation.

It does not implement the support, does not execute `report bundle export`, and does not authorize a real bundle validation smoke by itself. Future implementation requires a separate source/test phase. Future real Candidate C validation still requires a later write-authorized smoke.

The purpose is to validate Candidate C without mutating production/default report, manifest, or bundle paths.

## Problem Statement

Phase 6.3C stopped before execution:

```text
current report bundle export cannot target the required isolated Candidate C paths
```

Confirmed current constraints:

- current `--manifest` is tied to production/default `reports/python_tooling/manifest.jsonl`
- current `--out` is tied to production/default `reports/python_tooling/bundles/`
- Candidate C validation requires isolated source and bundle output paths under `reports/python_tooling/validation/...`
- using production/default paths for validation would mutate normal tooling output state
- adding isolated path support is safer than authorizing production/default bundle mutation

## Proposed Option and Behavior Model

Prefer minimal and explicit support.

### Existing Option To Keep

Keep existing `--out` as the bundle output option.

Future implementation should allow `--out` to target an approved isolated bundle directory under the approved root, not only the hard-coded `reports/python_tooling/bundles/` root.

This is not an approved-root expansion if the validation path is already under the existing approved root. It is a removal of the extra hard-coded production subdirectory restriction for bundle validation.

### New Source Input Options

Add explicit source input options for isolated validation:

```text
--source-report <path>
--source-manifest <path>
```

Rationale:

- `--source-report` clearly identifies the report file to copy into the bundle
- `--source-manifest` clearly identifies the manifest file to read/copy/reference, if the bundle contract uses a manifest
- these names avoid changing the meaning of existing `--manifest` if it is currently bound to the default production manifest
- they avoid confusion with `report export --manifest-out`, which is a write target, not a read source

Do not add aliases unless a future implementation phase explicitly justifies them.

### Existing `--manifest`

Keep existing `--manifest` behavior backward-compatible.

If current `--manifest` means use/read the production/default manifest, keep that behavior unless a future implementation explicitly documents a safe compatibility change.

For Candidate C validation, prefer `--source-manifest` over reusing `--manifest`.

## Future CLI Behavior

### Case 1: Existing Default Bundle Behavior

```powershell
report bundle export --manifest reports/python_tooling/manifest.jsonl --out reports/python_tooling/bundles/<bundle-dir>
```

or whatever current default-style command is confirmed by source/help.

Behavior:

- unchanged for backward compatibility
- still subject to existing path guards
- not used for Candidate C validation

### Case 2: Isolated Source Report and Isolated Bundle Output

```powershell
report bundle export `
  --source-report <source-report-path> `
  --out <isolated-bundle-dir>
```

Behavior:

- reads/copies source report from `<source-report-path>`
- writes directory bundle to `<isolated-bundle-dir>`
- does not read production/default `reports/python_tooling/full_status.md`
- does not write production/default `reports/python_tooling/bundles`
- does not write production/default `reports/python_tooling/manifest.jsonl`
- source report path must pass approved read/path guard
- bundle output path must pass approved write/path guard
- source report remains unchanged

### Case 3: Isolated Source Report, Isolated Source Manifest, Isolated Bundle Output

```powershell
report bundle export `
  --source-report <source-report-path> `
  --source-manifest <source-manifest-path> `
  --out <isolated-bundle-dir>
```

Behavior:

- reads/copies or references source report
- reads/copies or references source manifest according to existing bundle behavior
- writes directory bundle to `<isolated-bundle-dir>`
- does not read/write production/default report/manifest/bundle paths
- source report and source manifest remain unchanged
- output remains directory bundle only

### Case 4: Invalid or Incomplete Isolated Inputs

If `--source-manifest` is supplied without `--source-report` and the bundle command requires a report source:

- fail closed before writing anything
- no bundle directory created
- clear error wording

If `--source-report` path does not exist:

- fail closed before writing anything

If `--source-manifest` path does not exist and supplied:

- fail closed before writing anything

If `--out` target already exists:

- fail closed before writing anything
- no `--force` added

## Path Guard and Approved Root Policy

Future implementation must not weaken path guards.

Rules:

- `--source-report` path must be validated for safe read access
- `--source-manifest` path must be validated for safe read access
- `--out` bundle directory must be validated for safe write access
- supplied paths outside approved roots must fail closed before writing anything
- protected paths must fail closed
- production/default paths are not used when isolated inputs are supplied
- no approved-root expansion unless separately authorized
- no `--force`
- no overwrite behavior added
- zip remains unsupported
- parent creation behavior must match existing safe writer conventions

Production/default paths must not be used for Candidate C validation:

```text
reports/python_tooling/full_status.md
reports/python_tooling/manifest.jsonl
reports/python_tooling/bundles/
```

## Source Unchanged Policy

Future Candidate C implementation/smoke must guarantee:

- source report hash unchanged before/after
- source manifest hash unchanged before/after, if used
- output wording `SOURCE_UNCHANGED` is truthful
- bundle export must not mutate source fixtures

## Bundle Output Structure

Future isolated bundle output should preserve current bundle structure.

Expected directory output should include whatever current implementation already creates, likely:

```text
bundle_manifest.json
index.md
reports/
```

Rules:

- no schema/structure change unless separately documented
- no zip output
- no `--force`
- no overwrite
- `bundle_manifest.json` should reference the isolated source/report metadata consistently
- copied report content should match the controlled source report fixture

## Output Wording

Future Candidate C success output with isolated paths should include:

```text
BUNDLE_EXPORT_COMPLETE
SOURCE_UNCHANGED
APPROVED_ROOT
CE_NOT_RUN
WRAPPER_UNSUPPORTED
BUNDLE_EXPORT_OK
```

Expected absent:

```text
NO_FILES_WRITTEN
REPORT_EXPORT_OK
MANIFEST_RECORDED
MANIFEST_NOT_WRITTEN
BUNDLE_NOT_CREATED
ZIP_UNSUPPORTED
```

`WRITE_COMPLETE` should not be added unless current bundle output already uses it intentionally; if present, document whether it is acceptable or noisy.

## Data Model / JSON Behavior

Default expectation:

- JSON output / `to_dict()` remains backward-compatible
- bundle manifest schema remains unchanged unless separately documented
- command result schema remains backward-compatible
- if internal result data needs new source path fields, avoid exposing them in JSON unless already consistent with existing output schema

If JSON changes are unavoidable:

- stop and report before implementing unless the change is trivial and fully covered by tests
- document the change clearly

## Command Inventory and Write Surface

Future implementation must preserve:

- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable commands remain:
  - `report export`
  - `report bundle export`
- no new command
- no wrapper write-capable support
- no CE command
- no zip support
- no `--force`

If command inventory parameter metadata is updated, it may list:

```text
--source-report
--source-manifest
```

and updated `--out` semantics for `report bundle export`.

Do not change risk level / writes / runs_ce metadata unless there is a clearly documented reason.

## Future Implementation Files Likely Touched

Expected future implementation may touch:

- `src/armedforces_tool/cli.py`
- `src/armedforces_tool/report_bundle.py`
- `src/armedforces_tool/report_output_messages.py` only if output wording/path display needs adjustment
- `src/armedforces_tool/command_inventory.py` only for parameter metadata
- tests related to report bundle behavior

Do not modify these files in this contract task.

## Future Tests Required

Required future tests:

- `report bundle export --help` includes `--source-report`
- `report bundle export --help` includes `--source-manifest` if implemented
- `--source-report <path> --out <isolated-bundle-dir>` writes bundle in pytest temp path
- `--source-report <path> --source-manifest <path> --out <isolated-bundle-dir>` writes bundle in pytest temp path
- isolated `--out` does not write production/default `reports/python_tooling/bundles`
- isolated inputs do not read/write production/default `reports/python_tooling/full_status.md`
- isolated inputs do not read/write production/default `reports/python_tooling/manifest.jsonl`
- source report hash unchanged after bundling
- source manifest hash unchanged after bundling, if used
- `bundle_manifest.json` exists and remains schema-compatible
- `index.md` exists
- copied report exists and content matches controlled fixture
- zip remains unsupported
- `--force` remains unsupported
- existing default behavior remains backward-compatible
- Candidate A tests still pass
- Candidate B tests still pass
- dry-run tests still pass
- JSON output remains unchanged or explicitly tested

Suggested test files:

```text
tests/test_report_bundle.py
tests/test_real_bundle_export_output_integration.py
tests/test_report_bundle_output_messages.py
tests/test_report_bundle_help_text.py
tests/test_report_bundle_dry_run_output.py
tests/test_real_report_export_output_integration.py
tests/test_report_export_manifest_output_integration.py
```

## Future Validation Commands

The future implementation phase should run:

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"

.venv\Scripts\python.exe -m pytest tests/test_report_bundle.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_real_bundle_export_output_integration.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_report_bundle_output_messages.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_report_bundle_help_text.py --basetemp .tmp_pytest
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

Tests may use temporary test directories controlled by pytest.

The future implementation phase must not create:

- `reports/python_tooling/validation/`
- production/default `reports/python_tooling/full_status.md`
- production/default `reports/python_tooling/manifest.jsonl`
- production/default `reports/python_tooling/bundles/`
- `docs/reports/python_tooling`
- log/config/session/intake/baseline/registry files

## Future Candidate C Validation Smoke After Support

After implementation and boundary smoke pass, Candidate C validation smoke can be rerun with confirmed options.

Possible future command shape:

```powershell
.venv\Scripts\python.exe -m armedforces_tool report bundle export `
  --source-report reports/python_tooling/validation/phase6_real_write_output_validation/candidate_c_bundle_export/source/report_output.md `
  --source-manifest reports/python_tooling/validation/phase6_real_write_output_validation/candidate_c_bundle_export/source/manifest.jsonl `
  --out reports/python_tooling/validation/phase6_real_write_output_validation/candidate_c_bundle_export/bundle
```

Only the future smoke may execute that command.

This contract task must not execute it.

## Stop Conditions for Future Implementation

Future implementation must stop if:

- adding isolated source/bundle path support requires write-surface expansion beyond existing `report bundle export`
- adding it requires wrapper write support
- adding it requires CE/runtime mutation
- adding it weakens path guards
- adding it expands approved roots
- adding it requires default production bundle behavior to change
- adding it requires zip support
- adding it requires `--force`
- adding it changes JSON output in an undocumented way
- tests cannot keep Candidate A/B/C boundaries separate
- production/default report/manifest/bundle paths would be written by tests
- runtime artifacts outside pytest temp paths would be created

## Next Phase Recommendation

Recommended next phase:

```text
Phase 6.5C - isolated bundle validation path support implementation
```

Scope:

- narrow source/test/docs implementation
- add isolated source input support
- update bundle `--out` path support without weakening approved-root guard
- no manual real writes
- no CE
- no wrapper changes
- no tag

Then:

```text
Phase 6.6C - isolated bundle path support boundary smoke
Phase 6.3C-R1 - Candidate C bundle export validation smoke rerun
```

## Tag Policy

- no tag is created by Phase 6.4C
- no tag should be created for contract-only work
- a future tag may be considered only after Candidate C validation smoke passes and cleanup is verified

Potential future tag after Candidate A/B/C all pass:

```text
python-tooling-real-write-output-validation-checkpoint-20260619
```

This tag name is provisional only.

## Out Of Scope

- implementation in this task
- tests in this task
- wrapper write-capable support
- CE automation
- runtime write/restore migration
- Candidate C execution
- production/default report/manifest/bundle mutation for validation
- zip export
- `--force`
- approved-root expansion
- path guard weakening
