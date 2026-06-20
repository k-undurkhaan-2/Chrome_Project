# Python Tooling Path Guard Rejection Wording Contract

## Purpose

This contract defines a future narrow wording slice for approved-root and path-guard rejections in Python report tooling.

This contract does not implement source changes, does not run commands, and does not authorize new write behavior. Future implementation must be narrow, must not weaken path guards, must not expand approved roots, must not authorize additional write destinations, and must be validated by tests using pytest temp paths only.

## Baseline

Current checkpoint tags:

```text
python-tooling-phase3-final-checkpoint-20260616
python-tooling-powershell-wrapper-readonly-checkpoint-20260616
python-tooling-output-wording-checkpoint-20260618
python-tooling-real-write-output-validation-checkpoint-20260619
python-tooling-rejection-path-wording-checkpoint-20260620
python-tooling-no-force-overwrite-rejection-checkpoint-20260620
```

Current stable state:

- commands approximately `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- wrapper remains read-only
- no CE/runtime mutation
- zip export unsupported
- no-force overwrite rejection clarified
- `report export --force` supported success behavior preserved
- approved-root/path guard boundaries are frozen

## Target Rejection Paths

Future implementation must inspect current source/help/tests and target only real current guard surfaces.

### Case 1: Report Output Outside Approved Root

```text
report export --out <outside-approved-root>
```

Expected future behavior:

- fail closed before writing
- no output file created
- output identifies `--out`
- output identifies that the path is outside approved roots or rejected by guard
- preferred token: `PATH_GUARD_REJECTED` or current equivalent
- optional detail token: `OUTSIDE_APPROVED_ROOT` if compatible
- optional token: `NO_FILES_WRITTEN`

### Case 2: Manifest Output Outside Approved Root

```text
report export --record-manifest --manifest-out <outside-approved-root>
```

Expected future behavior:

- fail closed before writing
- no manifest file created
- output identifies `--manifest-out`
- output identifies approved-root/path-guard reason
- preferred token: `PATH_GUARD_REJECTED` or current equivalent
- optional token: `NO_FILES_WRITTEN`

### Case 3: Bundle Output Outside Approved Root

```text
report bundle export --out <outside-approved-root>
```

Expected future behavior:

- fail closed before writing
- no bundle directory created
- no `bundle_manifest.json`
- no `index.md`
- no copied report
- output identifies `--out`
- output identifies approved-root/path-guard reason
- preferred token: `PATH_GUARD_REJECTED` or current equivalent
- optional token: `NO_FILES_WRITTEN`

### Case 4: Rejected Source Input Path

```text
report bundle export --source-report <guard-rejected-path>
report bundle export --source-manifest <guard-rejected-path>
```

Expected future behavior:

- fail closed before writing
- no bundle directory created
- output distinguishes guard rejection from missing/invalid source input
- output identifies the offending option
- preferred token: `PATH_GUARD_REJECTED` or current equivalent
- optional detail token: `OUTSIDE_APPROVED_ROOT` if accurate
- optional token: `NO_FILES_WRITTEN`

Do not replace Phase 7.2B `SOURCE_MISSING` / `SOURCE_INVALID` wording unless the actual reason is path-guard rejection.

### Case 5: Traversal / Protected Path Rejection

Examples:

```text
..\protected-output
../protected-output
<reserved-protected-path>
```

Expected future behavior:

- fail closed before writing
- output identifies path guard rejection
- no path normalization loophole
- no partial output
- preferred token: `PATH_GUARD_REJECTED` or current equivalent
- optional token: `NO_FILES_WRITTEN`

## Desired Future Behavior

Future implementation should ensure:

- guard rejection fails before writing anything
- no report file is created
- no manifest file is created
- no bundle directory is created
- no `bundle_manifest.json`
- no `index.md`
- no copied report
- no zip file
- no production/default report/manifest/bundle path is written during tests
- error wording identifies the offending path/option
- error wording does not reveal unsafe internal implementation details
- error wording tells the operator the path was rejected by approved-root/path-guard policy
- output includes `PATH_GUARD_REJECTED` if compatible
- output may include `OUTSIDE_APPROVED_ROOT` if accurate
- output includes `NO_FILES_WRITTEN` if compatible

## Stable Token Policy

Preferred conceptual tokens:

```text
PATH_GUARD_REJECTED
OUTSIDE_APPROVED_ROOT
```

Optional existing token:

```text
NO_FILES_WRITTEN
```

Existing token that may already exist and must be inspected before changing:

```text
BAD_PATH
```

Token meanings:

- `PATH_GUARD_REJECTED`: a path was rejected by approved-root/path-guard policy
- `OUTSIDE_APPROVED_ROOT`: the path is outside allowed/approved roots
- `NO_FILES_WRITTEN`: rejection happened before output artifacts were written
- `BAD_PATH`: use only if current implementation already uses it for this exact guard condition

Rules:

- do not use `SOURCE_MISSING` for guard rejection unless the file truly does not exist and no guard rejection is involved
- do not use `SOURCE_INVALID` for approved-root rejection unless current code semantically treats it as invalid source path and docs explain why
- do not use `OVERWRITE_UNSUPPORTED` for path-guard rejection
- do not use `ZIP_UNSUPPORTED` for path-guard rejection
- do not use `INVALID_OPTION_COMBINATION` unless current parser actually models the condition that way
- do not use success tokens in guard rejection output
- `SOURCE_UNCHANGED` remains success-only
- do not introduce `FORCE_UNSUPPORTED` for this slice

## Wording Draft

Recommended human-readable wording for write target rejection:

```text
Output Rejected
status                   PATH_GUARD_REJECTED
reason                   OUTSIDE_APPROVED_ROOT
output_option            --out
output_path              <path>
write_status             NO_FILES_WRITTEN
conclusion               OUTPUT_REJECTED
```

Recommended human-readable wording for manifest target rejection:

```text
Report Export Rejected
status                   PATH_GUARD_REJECTED
reason                   OUTSIDE_APPROVED_ROOT
output_option            --manifest-out
output_path              <path>
write_status             NO_FILES_WRITTEN
conclusion               REPORT_EXPORT_REJECTED
```

Recommended human-readable wording for bundle target rejection:

```text
Bundle Export Rejected
status                   PATH_GUARD_REJECTED
reason                   OUTSIDE_APPROVED_ROOT
output_option            --out
output_path              <path>
write_status             NO_FILES_WRITTEN
conclusion               BUNDLE_EXPORT_REJECTED
```

If current output framework does not use this exact table shape, preserve the existing human-readable style and include equivalent information.

## Must Not Appear In Path-Guard Rejection Output

Success tokens:

```text
REPORT_EXPORT_OK
MANIFEST_RECORDED
WRITE_COMPLETE
BUNDLE_EXPORT_COMPLETE
BUNDLE_EXPORT_OK
SOURCE_UNCHANGED
```

Unrelated rejection tokens, unless they are the actual current reason:

```text
ZIP_UNSUPPORTED
OVERWRITE_UNSUPPORTED
SOURCE_MISSING
SOURCE_INVALID
FORCE_UNSUPPORTED
```

## Success Behavior To Preserve

Future implementation must preserve:

- Candidate A report export success
- Candidate B manifest success
- Candidate C directory bundle success
- `report export --force` supported success behavior
- Phase 7.2A invalid option rejection
- Phase 7.2B missing source rejection
- Phase 7.2C zip unsupported rejection
- Phase 8.2 no-force overwrite rejection
- dry-run behavior
- JSON / `to_dict()` compatibility
- command inventory/write surface

## Error / Result Status

Future implementation should choose result statuses consistent with current code.

Preferred conceptual status:

```text
OUTPUT_REJECTED
```

or existing equivalent.

Rules:

- do not change JSON schema unless already consistent with current result model
- do not change successful Candidate A/B/C behavior
- do not change `report export --force`
- do not change dry-run behavior
- do not expand approved roots

## Test Requirements For Future Implementation

Future implementation must add or update tests only for real current surfaces.

Tests must use pytest temp paths and must not write production/default runtime artifacts.

### Guarded Report Output Path

Construct a path rejected by current approved-root/path-guard policy.

Attempt report export to that path using only test-controlled paths.

Assert:

- non-success result
- no output file created
- output includes guard token or current equivalent
- output includes `NO_FILES_WRITTEN` if compatible
- offending option/path appears if safe
- success tokens absent

### Guarded Manifest Output Path

Construct a guard-rejected manifest output path.

Assert:

- non-success result
- no manifest file created
- output identifies `--manifest-out`
- guard token or current equivalent appears
- `NO_FILES_WRITTEN` if compatible
- success tokens absent

### Guarded Bundle Output Path

Construct a guard-rejected bundle output path.

Assert:

- non-success result
- no bundle directory created
- no `bundle_manifest.json`
- no `index.md`
- no copied report
- output identifies `--out`
- guard token or current equivalent appears
- `NO_FILES_WRITTEN` if compatible
- success tokens absent

### Guarded Source Input Path

Only if current code has a read/source guard surface.

Assert:

- non-success result
- no bundle directory created
- output distinguishes path-guard rejection from missing/invalid source input if possible
- offending source option appears
- guard token or current equivalent appears
- success tokens absent

### Existing Behavior Unchanged

Ensure all still pass:

- Candidate A report export success tests
- Candidate B manifest success tests
- Candidate C directory bundle success tests
- `report export --force` success tests
- Phase 7.2A invalid option rejection tests
- Phase 7.2B missing source rejection tests
- Phase 7.2C zip unsupported rejection tests
- Phase 8.2 no-force overwrite rejection tests
- dry-run tests
- command inventory tests if impacted

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
- path guard / approved root helper module if one already exists
- `tests/test_report_export.py`
- `tests/test_report_export_manifest_output_integration.py`
- `tests/test_report_bundle.py`
- `tests/test_report_bundle_output_messages.py`
- command inventory tests if impacted
- docs for implementation notes

Do not modify these files in this contract task.

## Future Validation Commands

Future implementation should run relevant targeted tests plus full pytest:

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"

.venv\Scripts\python.exe -m pytest tests/test_report_export.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_report_export_manifest_output_integration.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_report_bundle.py --basetemp .tmp_pytest
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

- weaken path guards
- expand approved roots
- add write-capable commands
- add wrapper export shortcuts
- add CE integration
- enable new overwrite behavior
- add new force behavior
- enable zip export
- mutate production/default paths during validation
- change JSON schema without contract
- perform manual real writes
- create runtime artifacts outside pytest temp dirs

## Stop Conditions For Future Implementation

Future implementation must stop if:

- no current path-guard rejection surface exists
- implementing wording would require broad path guard refactor
- implementation would weaken guard behavior
- implementation would expand approved roots
- tests would need to write production/default paths
- manual real writes are required to validate
- wrapper changes are required
- CE/runtime behavior is involved
- Candidate A/B/C success outputs would change
- `report export --force` behavior would change
- Phase 7.2A/7.2B/7.2C rejection outputs would change unexpectedly
- Phase 8.2 no-force overwrite rejection output would change unexpectedly

## Recommended Next Phase

Recommended:

```text
Phase 9.1 - approved-root / path-guard rejection wording implementation
```

Scope:

- conditional narrow source/test/docs implementation
- only if real current guard surfaces exist
- no guard weakening
- no manual real writes
- no CE
- no wrapper changes
- no tag

If source inspection shows no current path-guard rejection surface exists, the implementation phase should stop and report that a separate guard-surface contract would be needed.

## Tag Policy

- no tag is created by this contract
- no tag should be created for this contract-only work
- a future checkpoint may be considered only after implementation and boundary smoke pass
