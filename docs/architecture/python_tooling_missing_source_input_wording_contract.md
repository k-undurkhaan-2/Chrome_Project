# Python Tooling Missing Source Input Wording Contract

## Purpose

This document defines the Phase 7.2B contract for the next narrow rejection-path wording implementation slice:

```text
report bundle export missing or invalid source input
```

This contract does not implement source changes, run commands, add commands, add options, or authorize writes.

Future implementation must be narrow, test-backed, and limited to fail-closed wording for missing or invalid isolated bundle source inputs. It must not alter success paths, dry-run behavior, Candidate A/B/C success wording, bundle artifact structure, path guards, wrapper behavior, or CE/runtime behavior.

## Baseline

Current checkpoint baseline:

```text
python-tooling-phase3-final-checkpoint-20260616
python-tooling-powershell-wrapper-readonly-checkpoint-20260616
python-tooling-output-wording-checkpoint-20260618
python-tooling-real-write-output-validation-checkpoint-20260619
```

Current expected state:

- commands approximately `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable Python commands remain:
  - `report export`
  - `report bundle export`
- wrapper remains read-only
- no CE/runtime mutation
- no log/config/session/intake/baseline/registry writes introduced
- zip export remains unsupported
- `--force` / overwrite remains unsupported
- approved-root and protected-path guard boundaries are frozen

## Target Rejection Paths

### Missing Source Report

Command pattern:

```powershell
report bundle export --source-report <missing-report-path> --out <bundle-dir>
```

Expected fail-closed behavior:

- reject before creating the bundle directory
- do not create `bundle_manifest.json`
- do not create `index.md`
- do not copy any report
- do not write runtime report, runtime manifest, runtime bundle, log, registry, baseline, session, intake, or local config files

Expected wording:

- identify `--source-report`
- say the source report is missing
- include or map to `SOURCE_MISSING`
- include `NO_FILES_WRITTEN` if compatible with the existing output style

Forbidden success tokens:

- `BUNDLE_EXPORT_COMPLETE`
- `BUNDLE_EXPORT_OK`
- `SOURCE_UNCHANGED`
- `REPORT_EXPORT_OK`
- `WRITE_COMPLETE`
- `MANIFEST_RECORDED`
- `ZIP_UNSUPPORTED`

### Invalid Source Report

Command pattern:

```powershell
report bundle export --source-report <directory-path> --out <bundle-dir>
```

Expected fail-closed behavior:

- reject before creating the bundle directory
- do not create `bundle_manifest.json`
- do not create `index.md`
- do not copy any report

Expected wording:

- identify `--source-report`
- say the source report is invalid or not a file
- include or map to `SOURCE_INVALID`
- include `NO_FILES_WRITTEN` if compatible with the existing output style

### Missing Source Manifest

Command pattern:

```powershell
report bundle export --source-report <report-path> --source-manifest <missing-manifest-path> --out <bundle-dir>
```

Expected fail-closed behavior:

- reject before creating the bundle directory
- do not create `bundle_manifest.json`
- do not create `index.md`
- do not copy any report
- leave the source report unchanged

Expected wording:

- identify `--source-manifest`
- say the source manifest is missing
- include or map to `SOURCE_MISSING`
- include `NO_FILES_WRITTEN` if compatible with the existing output style

### Invalid Source Manifest

Command pattern:

```powershell
report bundle export --source-report <report-path> --source-manifest <directory-path> --out <bundle-dir>
```

Expected fail-closed behavior:

- reject before creating the bundle directory
- do not create `bundle_manifest.json`
- do not create `index.md`
- do not copy any report
- leave the source report unchanged

Expected wording:

- identify `--source-manifest`
- say the source manifest is invalid or not a file
- include or map to `SOURCE_INVALID`
- include `NO_FILES_WRITTEN` if compatible with the existing output style

### Source Manifest Without Source Report

Command pattern:

```powershell
report bundle export --source-manifest <manifest-path> --out <bundle-dir>
```

Expected fail-closed behavior:

- reject before creating the bundle directory
- do not create `bundle_manifest.json`
- do not create `index.md`
- do not copy any report

Expected wording:

- identify `--source-manifest`
- say `--source-manifest` requires `--source-report`
- include or map to `INVALID_OPTION_COMBINATION`
- include `NO_FILES_WRITTEN` if compatible with the existing output style

## Desired Future Behavior

Future implementation should ensure:

- command fails before creating a bundle directory
- no `bundle_manifest.json` is created
- no `index.md` is created
- no copied report is created
- no production/default path is read or written unless current backward-compatible default behavior explicitly requires it outside isolated mode
- no source file is modified
- wording identifies whether the input is a source report or source manifest
- wording identifies the relevant flag:
  - `--source-report`
  - `--source-manifest`
- output includes a no-write signal if compatible:
  - `NO_FILES_WRITTEN`
- output uses or maps to stable rejection tokens:
  - `SOURCE_MISSING`
  - `SOURCE_INVALID`
  - `INVALID_OPTION_COMBINATION`

## Stable Token Policy

Preferred new tokens for this slice:

```text
SOURCE_MISSING
SOURCE_INVALID
```

Existing tokens that may apply:

```text
INVALID_OPTION_COMBINATION
NO_FILES_WRITTEN
```

Meanings:

- `SOURCE_MISSING`: required source input path does not exist
- `SOURCE_INVALID`: source input path exists but is unusable, for example a directory instead of a file
- `INVALID_OPTION_COMBINATION`: source-related flags are supplied in an incomplete or invalid combination
- `NO_FILES_WRITTEN`: failure happened before any output artifact was written

Rules:

- do not use `BAD_PATH` for missing local source files unless path guard is the actual rejection reason
- do not use `SOURCE_UNCHANGED` in failure output
- reserve `SOURCE_UNCHANGED` for successful bundle export output
- do not use `BUNDLE_EXPORT_COMPLETE`
- do not use `BUNDLE_EXPORT_OK`
- do not use report export success tokens
- keep dry-run no-write wording separate from real fail-closed wording

## Wording Drafts

Recommended missing source report wording:

```text
Bundle Export Rejected
status                   SOURCE_MISSING
source_kind              report
source_option            --source-report
write_status             NO_FILES_WRITTEN
conclusion               BUNDLE_EXPORT_REJECTED
```

Recommended invalid source report wording:

```text
Bundle Export Rejected
status                   SOURCE_INVALID
source_kind              report
source_option            --source-report
write_status             NO_FILES_WRITTEN
conclusion               BUNDLE_EXPORT_REJECTED
```

Recommended missing source manifest wording:

```text
Bundle Export Rejected
status                   SOURCE_MISSING
source_kind              manifest
source_option            --source-manifest
write_status             NO_FILES_WRITTEN
conclusion               BUNDLE_EXPORT_REJECTED
```

Recommended invalid source manifest wording:

```text
Bundle Export Rejected
status                   SOURCE_INVALID
source_kind              manifest
source_option            --source-manifest
write_status             NO_FILES_WRITTEN
conclusion               BUNDLE_EXPORT_REJECTED
```

Recommended source manifest without source report wording:

```text
Bundle Export Rejected
status                   INVALID_OPTION_COMBINATION
invalid_option           --source-manifest
requires                 --source-report
write_status             NO_FILES_WRITTEN
conclusion               BUNDLE_EXPORT_REJECTED
```

If the current output framework does not use this exact table shape, preserve the existing human-readable style and include equivalent information.

## Must Not Appear In Failure Output

Missing or invalid source-input rejection output must not include:

```text
BUNDLE_EXPORT_COMPLETE
BUNDLE_EXPORT_OK
SOURCE_UNCHANGED
REPORT_EXPORT_OK
WRITE_COMPLETE
MANIFEST_RECORDED
ZIP_UNSUPPORTED
```

`CE_NOT_RUN` and `WRAPPER_UNSUPPORTED` may appear only if the existing rejection output style already includes boundary status lines. Do not add them broadly unless consistent with existing output design.

## Error / Result Status

Preferred conceptual status:

```text
BUNDLE_EXPORT_REJECTED
```

An existing equivalent is acceptable if it already fits the bundle export result model.

Rules:

- do not change successful Candidate C `BUNDLE_EXPORT_OK` behavior
- do not change dry-run success behavior
- do not change Candidate A/B success behavior
- do not change JSON schema unless a separate contract authorizes it

## Test Requirements For Future Implementation

Future implementation must use tests rather than manual real writes.

### Missing Source Report

Use pytest temporary paths:

```text
report bundle export --source-report <missing-report> --out <tmp-bundle>
```

Assert:

- result is non-success
- missing-source wording appears
- `--source-report` appears in the error wording
- `SOURCE_MISSING` appears if implemented
- `NO_FILES_WRITTEN` appears if compatible
- bundle directory does not exist
- no `bundle_manifest.json`
- no `index.md`
- no copied report
- success tokens are absent

### Invalid Source Report

Use a pytest temporary directory as the source report path:

```text
report bundle export --source-report <directory> --out <tmp-bundle>
```

Assert:

- result is non-success
- invalid-source wording appears
- `--source-report` appears in the error wording
- `SOURCE_INVALID` appears if implemented
- bundle directory does not exist
- success tokens are absent

### Missing Source Manifest

Use an existing source report fixture and a missing manifest path:

```text
report bundle export --source-report <tmp-report> --source-manifest <missing-manifest> --out <tmp-bundle>
```

Assert:

- result is non-success
- source report hash is unchanged
- missing-source wording appears
- `--source-manifest` appears in the error wording
- `SOURCE_MISSING` appears if implemented
- bundle directory does not exist
- success tokens are absent

### Invalid Source Manifest

Use an existing source report fixture and a directory path as manifest:

```text
report bundle export --source-report <tmp-report> --source-manifest <directory> --out <tmp-bundle>
```

Assert:

- result is non-success
- source report hash is unchanged
- invalid-source wording appears
- `--source-manifest` appears in the error wording
- `SOURCE_INVALID` appears if implemented
- bundle directory does not exist
- success tokens are absent

### Source Manifest Without Source Report

Use an existing source manifest fixture:

```text
report bundle export --source-manifest <tmp-manifest> --out <tmp-bundle>
```

Assert:

- result is non-success
- invalid-option-combination wording appears
- `--source-manifest` appears in the error wording
- `--source-report` appears as required companion
- `INVALID_OPTION_COMBINATION` appears if implemented
- bundle directory does not exist
- success tokens are absent

### Existing Behavior Unchanged

Future implementation must keep these regressions green:

- Candidate A report export success tests
- Candidate B manifest success tests
- Candidate C isolated bundle success tests
- bundle dry-run tests
- zip unsupported tests
- default bundle behavior tests
- command inventory tests

## Runtime Artifact Policy

Future implementation tests must not create:

- `reports/python_tooling/validation/`
- production/default `reports/python_tooling/full_status.md`
- production/default `reports/python_tooling/manifest.jsonl`
- production/default `reports/python_tooling/bundles/`
- `docs/reports/python_tooling`
- log files
- registry files
- baseline files
- session files
- intake files
- local config files

Use pytest temporary paths and tracked fixtures only.

## Suggested Future Implementation Files

Likely future source/test files:

- `src/armedforces_tool/report_bundle.py`
- `src/armedforces_tool/report_output_messages.py`
- `tests/test_report_bundle.py`
- `tests/test_real_bundle_export_output_integration.py`
- `tests/test_report_bundle_output_messages.py`

Do not modify these files in this contract phase.

## Future Validation Commands

Future implementation should run targeted tests first:

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"

.venv\Scripts\python.exe -m pytest tests/test_report_bundle.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_real_bundle_export_output_integration.py --basetemp .tmp_pytest
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

Future implementation validation must not manually run report export, dry-run, `--record-manifest`, report bundle export, bundle export, write, restore, or CE unless a later task explicitly authorizes it.

## Boundary Requirements

Future implementation must not:

- add write-capable commands
- add wrapper export shortcuts
- add CE integration
- enable zip export
- add `--force`
- weaken path guards
- expand approved roots
- mutate production/default paths
- change JSON schema without contract
- perform manual real writes
- create runtime artifacts outside pytest temporary directories

## Stop Conditions For Future Implementation

Stop if:

- cleanly detecting missing or invalid source inputs requires a broad parser refactor
- adding tokens changes unrelated success output
- JSON changes are required
- tests would need to write production/default paths
- manual real writes are required to validate
- wrapper changes are required
- CE/runtime behavior is involved
- path guards would need weakening
- Candidate A/B/C success outputs would change

## Recommended Next Phase

Recommended next phase:

```text
Phase 7.2B - missing source input wording implementation
```

Scope:

- narrow source/test/docs implementation
- no manual real writes
- no CE
- no wrapper changes
- no tag by default

## Tag Policy

No tag is created by this contract.

No tag is recommended for contract-only work.

A future rejection-path checkpoint may be considered only after a coherent set of rejection-path wording implementation slices passes targeted tests, full pytest, command inventory checks, and no-runtime-artifact validation.
