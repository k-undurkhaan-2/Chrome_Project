# Python tooling force / overwrite unsupported wording contract

## Purpose

This document defines a future narrow rejection-path wording slice for force and overwrite requests in write-capable Python tooling.

This contract:

- does not implement source changes
- does not run commands
- does not add commands or options
- does not authorize report, manifest, bundle, log, config, registry, baseline, session, intake, CE, or runtime writes
- requires any future implementation to stay narrow
- requires any future implementation to avoid adding overwrite support
- requires any future implementation to avoid adding `--force` support
- requires any future implementation to avoid writing or replacing existing outputs in rejection cases
- requires any future implementation to validate behavior with tests only and pytest temp paths

Future implementation must first inspect current CLI, source, and tests to identify the real existing force/overwrite rejection surface. If no current surface exists, the implementation phase must stop and report that a separate parser-surface contract is needed.

## Baseline

Stable checkpoint tags:

```text
python-tooling-phase3-final-checkpoint-20260616
python-tooling-powershell-wrapper-readonly-checkpoint-20260616
python-tooling-output-wording-checkpoint-20260618
python-tooling-real-write-output-validation-checkpoint-20260619
python-tooling-rejection-path-wording-checkpoint-20260620
```

Current stable state:

- commands approximately `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable Python commands remain:
  - `report export`
  - `report bundle export`
- wrapper remains read-only
- wrapper does not expose write-capable exports
- no CE/runtime mutation is part of Python tooling
- zip export remains unsupported
- `--force` / overwrite remains unsupported unless a current command already has a separately contracted surface
- approved-root and path-guard boundaries are frozen

## Target Rejection Paths

This contract targets the force/overwrite family as a future wording slice. These are potential surfaces for future source inspection, not authorization to run them in this contract phase.

### Case 1 - Report export target already exists

```text
report export --out <existing-file>
```

Expected future behavior:

- fail closed if current contract forbids overwrite
- existing file unchanged
- no temp or partial replacement
- output identifies the existing output path
- output indicates overwrite is unsupported
- preferred token: `OVERWRITE_UNSUPPORTED`
- optional token: `NO_FILES_WRITTEN`

### Case 2 - Manifest output target already exists

```text
report export --record-manifest --manifest-out <existing-file>
```

Expected future behavior:

- fail closed if current contract forbids overwrite
- existing manifest unchanged
- no append or replace unless current contract explicitly allows append
- output identifies `--manifest-out`
- output indicates overwrite is unsupported
- preferred token: `OVERWRITE_UNSUPPORTED`
- optional token: `NO_FILES_WRITTEN`

### Case 3 - Bundle output directory already exists

```text
report bundle export --out <existing-directory>
```

Expected future behavior:

- fail closed if current contract forbids overwrite or reuse
- existing directory unchanged
- no `bundle_manifest.json` replacement
- no `index.md` replacement
- no copied report replacement
- output identifies the output path
- output indicates overwrite is unsupported
- preferred token: `OVERWRITE_UNSUPPORTED`
- optional token: `NO_FILES_WRITTEN`

### Case 4 - Bundle output path is an existing file

```text
report bundle export --out <existing-file>
```

Expected future behavior:

- fail closed
- existing file unchanged
- no directory created over the file
- output indicates the output path is invalid for a directory bundle or that overwrite is unsupported
- preferred token may be `OVERWRITE_UNSUPPORTED` or `OUTPUT_INVALID`, depending on current code semantics
- optional token: `NO_FILES_WRITTEN`

### Case 5 - Unsupported force flag if present

```text
report export --force
report bundle export --force
```

Expected future behavior applies only if the current parser already exposes the flag:

- fail closed for unsupported force requests
- no output written
- output says force is unsupported
- preferred token: `FORCE_UNSUPPORTED`
- optional token: `NO_FILES_WRITTEN`

If the current parser does not expose `--force`, future implementation must not add it in this slice.

## Desired Future Behavior

Future implementation should ensure:

- overwrite / force requests fail closed before writing anything
- existing output files/directories remain byte-for-byte unchanged
- no partial output is created
- no production/default report, manifest, or bundle path is written during tests
- error wording identifies the offending output path or flag
- error wording states overwrite/force is unsupported
- output includes a stable token:
  - `OVERWRITE_UNSUPPORTED`
  - `FORCE_UNSUPPORTED` only for a real existing `--force` surface
- output includes `NO_FILES_WRITTEN` if compatible with the current output framework

## Stable Token Policy

Preferred new tokens:

```text
OVERWRITE_UNSUPPORTED
FORCE_UNSUPPORTED
```

Optional existing token:

```text
NO_FILES_WRITTEN
```

Meaning:

- `OVERWRITE_UNSUPPORTED`: requested output would overwrite or reuse an existing path, and overwrite is not supported.
- `FORCE_UNSUPPORTED`: `--force` or equivalent was requested but is not supported.
- `NO_FILES_WRITTEN`: failure happened before any output artifact was written.

Rules:

- do not use `ZIP_UNSUPPORTED` for overwrite failures
- do not use `SOURCE_MISSING` / `SOURCE_INVALID` for existing output path failures
- do not use `INVALID_OPTION_COMBINATION` unless the current parser treats `--force` as an invalid option combination
- do not use success tokens in rejection output
- `SOURCE_UNCHANGED` remains success-only
- do not add a token that implies overwrite or force is enabled

## Wording Draft

Recommended human-readable wording for existing output rejection:

```text
Output Rejected
status                   OVERWRITE_UNSUPPORTED
output_path              <path>
write_status             NO_FILES_WRITTEN
conclusion               OUTPUT_REJECTED
```

Recommended human-readable wording for unsupported force flag:

```text
Output Rejected
status                   FORCE_UNSUPPORTED
invalid_option           --force
write_status             NO_FILES_WRITTEN
conclusion               OUTPUT_REJECTED
```

If the current output framework does not use this exact table shape, preserve the existing human-readable style and include equivalent information.

## Must Not Appear In Rejection Output

Overwrite/force unsupported rejection output must not include:

```text
REPORT_EXPORT_OK
MANIFEST_RECORDED
WRITE_COMPLETE
BUNDLE_EXPORT_COMPLETE
BUNDLE_EXPORT_OK
SOURCE_UNCHANGED
ZIP_UNSUPPORTED
SOURCE_MISSING
SOURCE_INVALID
```

`INVALID_OPTION_COMBINATION` should appear only if current parser semantics model the condition that way.

## Error / Result Status

Future implementation should choose result statuses consistent with current code.

Preferred conceptual status:

```text
OUTPUT_REJECTED
```

or an existing equivalent.

Rules:

- do not change JSON schema unless already consistent with the current result model
- do not change successful Candidate A `REPORT_EXPORT_OK` behavior
- do not change successful Candidate B `MANIFEST_RECORDED` behavior
- do not change successful Candidate C `BUNDLE_EXPORT_OK` behavior
- do not change dry-run behavior
- do not change Phase 7.2A/7.2B/7.2C rejection behavior unexpectedly

## Test Requirements For Future Implementation

Future implementation must add or update tests only for real current surfaces. Tests must use pytest temp paths.

### Existing report output path

Prepare an existing file with known content/hash.

Attempt the current report export surface that would write to that same file.

Assert:

- non-success result if overwrite is unsupported
- existing file hash unchanged
- no partial/temp output left behind
- output includes `OVERWRITE_UNSUPPORTED` if implemented
- output includes `NO_FILES_WRITTEN` if compatible
- success tokens absent

### Existing manifest output path

Prepare an existing manifest file with known content/hash.

Attempt the current manifest output surface that would overwrite it.

Assert:

- non-success result if overwrite is unsupported
- existing manifest hash unchanged
- no partial/temp output left behind
- output includes `OVERWRITE_UNSUPPORTED` if implemented
- output includes `NO_FILES_WRITTEN` if compatible
- success tokens absent

### Existing bundle output directory

Prepare an existing directory with sentinel files.

Attempt bundle export to that directory.

Assert:

- non-success result if overwrite/reuse is unsupported
- sentinel files unchanged
- no `bundle_manifest.json` replacement
- no `index.md` replacement
- no copied report replacement
- output includes `OVERWRITE_UNSUPPORTED` if implemented
- success tokens absent

### Existing bundle output file

Prepare an existing file at the intended bundle output path.

Attempt bundle export to that path.

Assert:

- non-success result
- existing file hash unchanged
- no directory created over file
- output uses the chosen existing-path token
- success tokens absent

### Unsupported `--force`

Only if the current parser already exposes `--force`.

Assert:

- non-success result
- output includes `FORCE_UNSUPPORTED`
- `NO_FILES_WRITTEN` if compatible
- no output written
- success tokens absent

## Existing Behavior Unchanged

Future implementation must ensure all still pass:

- Candidate A report export success tests
- Candidate B manifest success tests
- Candidate C directory bundle success tests
- Phase 7.2A invalid option rejection tests
- Phase 7.2B missing source rejection tests
- Phase 7.2C zip unsupported rejection tests
- dry-run tests
- command inventory tests if any

## Runtime Artifact Policy

Future implementation tests must not create:

- `reports/python_tooling/validation/`
- production/default `reports/python_tooling/full_status.md`
- production/default `reports/python_tooling/manifest.jsonl`
- production/default `reports/python_tooling/bundles/`
- `docs/reports/python_tooling`
- log/config/session/intake/baseline/registry files

Use pytest temp paths/fixtures only.

## Suggested Future Implementation Files

Likely future source/test files:

- `src/armedforces_tool/report_export.py`
- `src/armedforces_tool/report_bundle.py`
- `src/armedforces_tool/report_output_messages.py`
- `src/armedforces_tool/cli.py` only if an existing `--force` surface is already present
- `tests/test_report_export.py`
- `tests/test_report_export_manifest_output_integration.py`
- `tests/test_report_bundle.py`
- `tests/test_report_bundle_output_messages.py`
- `tests/test_real_report_export_output_integration.py`
- `tests/test_real_bundle_export_output_integration.py`
- docs for implementation notes

Do not modify these files in this contract task.

## Future Validation Commands

Future implementation should run relevant targeted tests plus full pytest:

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"

.venv\Scripts\python.exe -m pytest tests/test_report_export.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_report_export_manifest_output_integration.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_real_report_export_output_integration.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_report_bundle.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_real_bundle_export_output_integration.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_report_bundle_output_messages.py --basetemp .tmp_pytest
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
- enable overwrite
- enable force
- enable zip export
- weaken path guards
- expand approved roots
- mutate production/default paths
- change JSON schema without a separate contract
- perform manual real writes
- create runtime artifacts outside pytest temp dirs

## Stop Conditions For Future Implementation

Future implementation must stop if:

- no current force/overwrite rejection surface exists
- implementing this would require adding a new user-facing `--force` option
- implementing this would require enabling overwrite
- implementation requires broad parser refactor
- tests would need to write production/default paths
- manual real writes are required to validate
- wrapper changes are required
- CE/runtime behavior is involved
- path guards would need weakening
- Candidate A/B/C success outputs would change
- Phase 7.2A/7.2B/7.2C rejection outputs would change unexpectedly

## Recommended Next Phase

Recommended:

```text
Phase 8.1 - force / overwrite unsupported wording implementation
```

Scope:

- conditional narrow source/test/docs implementation
- only if current surfaces exist
- no manual real writes
- no CE
- no wrapper changes
- no tag

If source inspection shows no current force/overwrite rejection surface exists, the implementation phase should stop and report that a separate parser-surface contract is needed before force/overwrite wording can be implemented.

## Tag Policy

- no tag is created by this contract
- no tag should be created for this contract-only work
- a future checkpoint may be considered only after implementation and final smoke pass
