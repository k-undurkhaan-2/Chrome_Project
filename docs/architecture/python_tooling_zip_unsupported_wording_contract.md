# Python Tooling Zip Unsupported Wording Contract

## Purpose

This document defines the Phase 7.2C contract for a future narrow rejection-path wording implementation slice:

```text
report bundle export zip / archive output request
```

This contract does not implement source changes, run commands, add commands, add options, or authorize writes.

Future implementation must be narrow, test-backed, and limited to fail-closed wording for zip/archive bundle output requests. It must not create zip/archive files, must not create directory bundles as a fallback in a zip rejection case, must not enable zip export, and must be validated by tests only.

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
- wrapper remains read-only
- no CE/runtime mutation
- zip export remains unsupported
- `--force` / overwrite remains unsupported
- approved-root and protected-path guard boundaries are frozen
- write-capable Python commands remain:
  - `report export`
  - `report bundle export`

## Target Rejection Path

Target unsupported feature:

```text
zip/archive bundle output
```

Future implementation must first inspect current CLI/source/help/tests to determine the actual rejection surface. Candidate surfaces include:

- existing `--zip` rejection path
- existing bundle output type field
- `.zip` output path rejection
- current tests that mention zip unsupported
- latent docs/help wording

Future implementation must formalize wording for the actual current rejection path only. Do not add zip support. Do not add a new zip option just to test rejection wording unless a separate parser-surface contract explicitly authorizes it.

If current CLI/source has no zip/archive rejection surface, the future implementation must stop and report that a separate parser-surface contract is required.

## Desired Future Behavior

Future implementation should ensure:

- zip/archive request fails closed before writing anything
- no zip file is created
- no directory bundle is created as a fallback
- no `bundle_manifest.json` is created
- no `index.md` is created
- no copied report is created
- no production/default bundle path is created
- output clearly says zip export is unsupported
- output states directory bundle is the supported form, if that remains the current contract
- output includes stable token `ZIP_UNSUPPORTED`
- output includes `NO_FILES_WRITTEN` if compatible with the existing output style
- output does not suggest zip can be enabled with `--force`
- output does not suggest the read-only wrapper can produce zip output
- output does not imply CE/runtime involvement

## Stable Token Policy

Primary token:

```text
ZIP_UNSUPPORTED
```

Optional no-write token:

```text
NO_FILES_WRITTEN
```

Rules:

- `ZIP_UNSUPPORTED` means the user requested zip/archive output, but zip export is unsupported.
- `ZIP_UNSUPPORTED` must not appear in successful directory bundle output.
- `ZIP_UNSUPPORTED` must not appear in unrelated path, source-input, or invalid-option rejection output.
- `NO_FILES_WRITTEN` may appear if current rejection wording style supports it.
- success tokens must not appear in zip rejection output.

## Wording Draft

Recommended human-readable wording for future implementation:

```text
Bundle Export Rejected
status                   ZIP_UNSUPPORTED
requested_output         zip
supported_output         directory
write_status             NO_FILES_WRITTEN
conclusion               BUNDLE_EXPORT_REJECTED
```

If the current output framework does not use this exact table shape, preserve the existing human-readable style and include equivalent information.

## Must Not Appear In Zip Rejection Output

The zip unsupported rejection output must not include:

```text
BUNDLE_EXPORT_COMPLETE
BUNDLE_EXPORT_OK
SOURCE_UNCHANGED
REPORT_EXPORT_OK
WRITE_COMPLETE
MANIFEST_RECORDED
SOURCE_MISSING
SOURCE_INVALID
INVALID_OPTION_COMBINATION
```

`SOURCE_MISSING` and `SOURCE_INVALID` must remain source-input specific.

`INVALID_OPTION_COMBINATION` should be used only if current CLI/source represents the zip request as an invalid option combination rather than an unsupported feature. If so, the implementation must document why.

## Error / Result Status

Future implementation should choose a result status consistent with the current code.

Preferred conceptual status:

```text
BUNDLE_EXPORT_REJECTED
```

An existing equivalent is acceptable if it fits the bundle export result model.

Rules:

- do not change JSON schema unless already consistent with the current result model
- do not change successful Candidate C `BUNDLE_EXPORT_OK` behavior
- do not change dry-run success behavior
- do not change Candidate A/B success behavior
- do not change missing source input rejection behavior
- do not change invalid option combination rejection behavior

## Test Requirements For Future Implementation

Future implementation must add or update tests to cover the actual current zip/archive rejection surface.

### Explicit Zip Option Rejection

If current CLI has or exposes an unsupported zip flag:

```text
report bundle export --source-report <tmp-report> --out <tmp-bundle> --zip
```

Assert:

- non-success result
- `ZIP_UNSUPPORTED` appears
- `NO_FILES_WRITTEN` appears if compatible
- no zip file exists
- bundle directory does not exist
- `bundle_manifest.json` does not exist
- `index.md` does not exist
- copied report does not exist
- success tokens are absent

### Zip-Like Output Path Rejection

If current CLI rejects `.zip` output paths:

```text
report bundle export --source-report <tmp-report> --out <tmp-output.zip>
```

Assert:

- non-success result
- `ZIP_UNSUPPORTED` appears if the rejection is specifically zip/archive unsupported
- no zip file exists
- no directory bundle exists
- success tokens are absent

### Existing Unsupported Output Type

If current CLI supports a bundle type or format field:

```text
report bundle export --source-report <tmp-report> --out <tmp-bundle> --type zip
```

or equivalent.

Assert the same no-write and wording conditions.

### Existing Behavior Unchanged

Future implementation must keep these regressions green:

- Candidate A report export success tests
- Candidate B manifest success tests
- Candidate C isolated bundle success tests
- bundle dry-run tests
- missing source input rejection tests
- invalid option combination tests
- default bundle behavior tests
- command inventory tests

## Runtime Artifact Policy

Future implementation tests must not create:

- `reports/python_tooling/validation/`
- production/default `reports/python_tooling/full_status.md`
- production/default `reports/python_tooling/manifest.jsonl`
- production/default `reports/python_tooling/bundles/`
- `docs/reports/python_tooling`
- log/config/session/intake/baseline/registry files
- any `.zip` artifact outside pytest temp paths

Use pytest temporary paths and tracked fixtures only.

## Suggested Future Implementation Files

Likely future source/test files:

- `src/armedforces_tool/report_bundle.py`
- `src/armedforces_tool/report_output_messages.py`
- `src/armedforces_tool/cli.py` only if current zip rejection surface already exists in parser/help and needs wording adjustment
- `tests/test_report_bundle.py`
- `tests/test_report_bundle_output_messages.py`
- `tests/test_real_bundle_export_output_integration.py`
- `tests/test_report_bundle_dry_run_output.py`
- docs for implementation notes

Do not modify those files in this contract task.

## Future Validation Commands

Future implementation should run:

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

## Boundary Requirements

Future implementation must not:

- add write-capable commands
- add wrapper export shortcuts
- add CE integration
- enable zip export
- create any zip artifact in production/default paths
- add `--force`
- weaken path guards
- expand approved roots
- mutate production/default paths
- change JSON schema without contract
- perform manual real writes
- create runtime artifacts outside pytest temporary directories

## Stop Conditions For Future Implementation

Future implementation must stop if:

- there is no current zip/archive rejection surface and implementation would require adding a new user-facing option
- adding zip rejection wording would accidentally enable zip output
- tests would need to write production/default paths
- manual real writes are required to validate
- wrapper changes are required
- CE/runtime behavior is involved
- path guards would need weakening
- approved roots would need expansion
- Candidate A/B/C success outputs would change
- missing source input rejection output would change unexpectedly
- invalid option combination rejection output would change unexpectedly

## Recommended Next Phase

Recommended next phase:

```text
Phase 7.2C - zip unsupported wording implementation
```

Scope:

- narrow source/test/docs implementation
- no manual real writes
- no CE
- no wrapper changes
- no tag by default

If source inspection shows no current zip rejection surface exists, the implementation phase should stop and report that a separate parser-surface contract is required before zip wording can be implemented.

## Tag Policy

No tag is created by this contract.

No tag should be created for this contract-only work.

A future rejection-path checkpoint may be considered only after a coherent set of rejection-path wording slices passes final smoke.
