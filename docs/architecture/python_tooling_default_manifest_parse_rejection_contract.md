# Python Tooling Default Manifest Parse Rejection Contract

## Purpose

This contract defines future wording for the existing default manifest parse / invalid manifest rejection surface:

```text
_analyze_existing_manifest()
_parse_manifest_line()
INVALID_MANIFEST
```

It is documentation only. It does not implement source changes, run commands, add commands or options, change isolated `--source-manifest` behavior, change wrapper behavior, or authorize CE/runtime behavior.

Future implementation must target only the real default manifest parser surface, preserve `INVALID_MANIFEST` compatibility when that is the current machine-readable status, avoid weakening path guards, avoid expanding approved roots, and avoid creating bundle output in rejection cases.

## Baseline

Current stable checkpoint tags:

```text
python-tooling-phase3-final-checkpoint-20260616
python-tooling-powershell-wrapper-readonly-checkpoint-20260616
python-tooling-output-wording-checkpoint-20260618
python-tooling-real-write-output-validation-checkpoint-20260619
python-tooling-rejection-path-wording-checkpoint-20260620
python-tooling-no-force-overwrite-rejection-checkpoint-20260620
python-tooling-path-guard-rejection-checkpoint-20260620
```

Current expected stable state:

- commands approximately `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable Python commands remain only `report export` and `report bundle export`
- wrapper remains read-only and does not wrap write-capable commands
- no CE/runtime mutation in Python tooling
- zip export remains unsupported / fail-closed
- `report export --force` remains supported direct Python CLI behavior
- `report bundle export` has no `--force` parser surface
- no-force existing-output rejection wording is clarified
- path-guard rejection wording is clarified
- isolated `--source-manifest` content remains unparsed
- default manifest parser exists and can return `INVALID_MANIFEST`
- approved roots and path guards remain strict

## Scope Distinction

### Isolated Source-Manifest Path

```text
report bundle export --source-report <report> --source-manifest <manifest-path> --out <bundle-dir>
```

Current policy:

- path/file validation only
- content is not parsed
- do not introduce content parsing in this wording slice
- do not use `MANIFEST_PARSE_FAILED` / `MANIFEST_INVALID` for isolated `--source-manifest` unless a separate validation-surface contract later authorizes it

### Default Manifest Parser

```text
reports/python_tooling/manifest.jsonl
_analyze_existing_manifest()
_parse_manifest_line()
INVALID_MANIFEST
```

This contract target:

- existing default manifest parse/invalid surface
- wording can be clarified without introducing new validation behavior
- current status/schema compatibility must be preserved

## Target Rejection Paths

### Case 1 - Malformed Default Manifest Line

Expected future behavior:

- fail closed before writing
- create no bundle directory
- create no `bundle_manifest.json`
- create no `index.md`
- copy no report
- output says default manifest parse failed
- preserve `INVALID_MANIFEST` if it is the current status
- preferred wording token: `MANIFEST_PARSE_FAILED` or existing equivalent
- optional token: `NO_FILES_WRITTEN`

### Case 2 - Invalid Default Manifest Record Shape

Expected future behavior:

- fail closed before writing
- create no bundle artifacts
- output says default manifest record is invalid
- preserve `INVALID_MANIFEST` if it is the current status
- preferred wording token: `MANIFEST_INVALID` or existing equivalent
- optional token: `NO_FILES_WRITTEN`

### Case 3 - Missing Required Fields

Expected future behavior:

- fail closed before writing
- output identifies invalid manifest structure if safe
- preserve `INVALID_MANIFEST` if it is the current status
- preferred wording token: `MANIFEST_INVALID`
- optional token: `NO_FILES_WRITTEN`

### Case 4 - Empty Default Manifest

Future implementation must inspect current behavior:

- if empty default manifest is invalid, clarify rejection wording
- if empty default manifest is valid/no-op, preserve current behavior and document it
- do not invent a rejection if current behavior treats empty default manifest as valid

## Desired Future Behavior

Future implementation should ensure:

- default manifest parse/invalid rejection fails before writing anything
- no bundle directory is created
- no `bundle_manifest.json` is created
- no `index.md` is created
- no copied report is created
- no zip file is created
- no production/default runtime report, manifest, or bundle path is written during validation
- error wording identifies the default manifest parse/invalid issue
- error wording distinguishes default manifest parsing from isolated `--source-manifest` path validation
- current machine-readable status is preserved if it is `INVALID_MANIFEST`
- output includes a stable human-readable token if compatible: `MANIFEST_PARSE_FAILED` or `MANIFEST_INVALID`
- output includes `NO_FILES_WRITTEN` if compatible

## Stable Token Policy

Preferred conceptual tokens:

```text
MANIFEST_PARSE_FAILED
MANIFEST_INVALID
NO_FILES_WRITTEN
```

Existing compatibility status:

```text
INVALID_MANIFEST
```

Existing source/path tokens to keep scoped to their domains:

```text
SOURCE_MISSING
SOURCE_INVALID
PATH_GUARD_REJECTED
BAD_PATH
PATH_REJECTED
OVERWRITE_UNSUPPORTED
ZIP_UNSUPPORTED
INVALID_OPTION_COMBINATION
```

Rules:

- preserve `INVALID_MANIFEST` if it is current machine-readable status
- do not use `MANIFEST_PARSE_FAILED` for missing/non-file/path-guard source manifest paths
- do not use `MANIFEST_INVALID` for isolated `--source-manifest` unless a future validation-surface contract authorizes content parsing
- do not use `SOURCE_MISSING` / `SOURCE_INVALID` for malformed default manifest content
- do not use `PATH_GUARD_REJECTED` for parse failures unless the actual reason is guard rejection
- do not use `OVERWRITE_UNSUPPORTED` or `ZIP_UNSUPPORTED` for default manifest parse failures
- do not use `FORCE_UNSUPPORTED`
- do not use success tokens in parse/invalid rejection output
- `SOURCE_UNCHANGED` remains success-only

## Wording Draft

Recommended wording for default manifest parse failure:

```text
Bundle Export Rejected
status                   INVALID_MANIFEST
reason                   MANIFEST_PARSE_FAILED
source_kind              default_manifest
write_status             NO_FILES_WRITTEN
conclusion               BUNDLE_EXPORT_REJECTED
```

Recommended wording for default manifest semantic invalidity:

```text
Bundle Export Rejected
status                   INVALID_MANIFEST
reason                   MANIFEST_INVALID
source_kind              default_manifest
write_status             NO_FILES_WRITTEN
conclusion               BUNDLE_EXPORT_REJECTED
```

If the current output framework does not use this exact shape, preserve the existing human-readable style and include equivalent information.

## Must Not Appear

Default manifest parse/invalid rejection output must not include success tokens:

```text
REPORT_EXPORT_OK
MANIFEST_RECORDED
WRITE_COMPLETE
BUNDLE_EXPORT_COMPLETE
BUNDLE_EXPORT_OK
SOURCE_UNCHANGED
```

It must avoid unrelated rejection tokens unless they are the actual current reason:

```text
SOURCE_MISSING
SOURCE_INVALID
PATH_GUARD_REJECTED
OUTSIDE_APPROVED_ROOT
OVERWRITE_UNSUPPORTED
ZIP_UNSUPPORTED
FORCE_UNSUPPORTED
```

## Success Behavior To Preserve

Future implementation must preserve:

- Candidate A report export success
- Candidate B manifest success
- Candidate C directory bundle success
- isolated `--source-manifest` path/file-only behavior
- `report export --force` supported success behavior
- Phase 7.2A invalid option rejection
- Phase 7.2B missing source rejection
- Phase 7.2C zip unsupported rejection
- Phase 8.2 no-force overwrite rejection
- Phase 9.1 path-guard rejection
- dry-run behavior
- JSON / `to_dict()` compatibility
- command inventory/write surface

## Test Requirements For Future Implementation

Future implementation must add/update tests only for real current surfaces and use pytest temp paths only.

Potential tests:

### Malformed Default Manifest

Construct a test-controlled default manifest with malformed content if current helpers support test injection.

Assert:

- non-success result
- current status remains `INVALID_MANIFEST` if applicable
- human-readable wording includes `MANIFEST_PARSE_FAILED` or equivalent
- `NO_FILES_WRITTEN` appears if compatible
- no bundle directory / `bundle_manifest.json` / `index.md` / copied report
- success tokens absent

### Invalid Default Manifest Record

Construct a default manifest line that parses but has invalid record shape.

Assert:

- non-success result if current semantics reject it
- status compatibility preserved
- `MANIFEST_INVALID` or equivalent appears if implemented
- no bundle artifacts
- success tokens absent

### Empty Default Manifest

Only test rejection if current semantics reject it. If current semantics accept empty manifests, preserve that behavior and document it.

### Isolated Source-Manifest Content Remains Unparsed

Add or preserve guard coverage that malformed isolated `--source-manifest` content is not newly parsed/rejected by this slice, unless a separate behavior contract later authorizes that.

## Existing Behavior Unchanged

Ensure all still pass:

- Candidate A report export success tests
- Candidate B manifest success tests
- Candidate C directory bundle success tests
- isolated source-manifest path validation tests
- `report export --force` success tests
- Phase 7.2A invalid option rejection tests
- Phase 7.2B missing source rejection tests
- Phase 7.2C zip unsupported rejection tests
- Phase 8.2 no-force overwrite rejection tests
- Phase 9.1 path-guard rejection tests
- dry-run tests
- command inventory tests if any

## Runtime Artifact Policy

Future implementation tests must not create:

```text
reports/python_tooling/validation/
reports/python_tooling/full_status.md
reports/python_tooling/manifest.jsonl
reports/python_tooling/bundles/
docs/reports/python_tooling
log/config/session/intake/baseline/registry files
```

## Suggested Future Implementation Files

Likely future files if implementation proceeds:

- `src/armedforces_tool/report_bundle.py`
- `src/armedforces_tool/report_output_messages.py`
- manifest parse/helper module if one already exists
- `tests/test_report_bundle.py`
- `tests/test_report_bundle_output_messages.py`
- `tests/test_real_bundle_export_output_integration.py`
- docs for implementation notes

Do not modify these files in this contract task.

## Future Validation Commands

Future implementation should run:

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"

.venv\Scripts\python.exe -m pytest tests/test_report_bundle.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_report_bundle_output_messages.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_real_bundle_export_output_integration.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest --basetemp .tmp_pytest
Remove-Item -Recurse -Force .tmp_pytest -ErrorAction SilentlyContinue
```

Also run read-only wrapper status/inventory.

## Stop Conditions For Future Implementation

Future implementation must STOP if:

- no current default manifest parse/invalid rejection surface can be safely tested
- implementation would require broad manifest model refactor
- implementation would introduce isolated `--source-manifest` content parsing
- implementation would weaken path guards or expand approved roots
- tests require production/default writes
- manual real writes are required
- wrapper changes are required
- CE/runtime behavior is involved
- Candidate A/B/C success outputs would change
- isolated source-manifest path behavior would change
- Phase 7/8/9 rejection outputs would change unexpectedly

## Recommended Next Phase

```text
Phase 10.3 - default manifest parse rejection wording implementation
```

This is conditional on real current default manifest parse surfaces.

## Tag Policy

No tag is created by this contract. A future checkpoint may be considered only after implementation and boundary smoke pass.
