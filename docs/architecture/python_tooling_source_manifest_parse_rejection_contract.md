# Python Tooling Source Manifest Parse Rejection Contract

## Phase 10.2 Correction Note

Phase 10.2 implementation STOPPED after source inspection found that isolated `report bundle export --source-manifest` content is not parsed today.

This document must not be interpreted as authorizing new isolated source-manifest content parsing behavior. Any future isolated `--source-manifest` content validation requires a separate behavior/surface contract.

Current wording implementation should target only real current surfaces. The existing default manifest parse path may be a separate next slice:

```text
_analyze_existing_manifest()
_parse_manifest_line()
INVALID_MANIFEST
```

Phase 10.3 now defines that separate default manifest parse rejection wording contract at:

```text
docs/architecture/python_tooling_default_manifest_parse_rejection_contract.md
```

It does not authorize isolated `--source-manifest` content parsing.

Phase 10.4 implemented wording for the separate default manifest parser surface, not isolated `--source-manifest` content parsing. Phase 10.5 boundary smoke passed. Any isolated content validation remains out of scope unless a separate behavior/surface contract defines and authorizes it.

## Purpose

This contract defines a narrow future wording slice for:

```text
report bundle export --source-manifest <existing but malformed/invalid manifest>
```

It covers source manifest content and format failures only. It does not implement wording changes, change command behavior, weaken path guards, expand approved roots, add write destinations, change successful bundle export behavior, change wrapper behavior, or change CE/runtime behavior.

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
- wrapper remains read-only
- no CE/runtime mutation in Python tooling
- zip export remains unsupported
- `report export --force` remains supported direct Python CLI behavior
- approved roots and path guards remain strict

## Target Rejection Paths

This contract targets cases where `--source-manifest` points to an existing readable file, but the manifest content cannot be parsed or is semantically invalid.

It is distinct from:

- Phase 7.2B `SOURCE_MISSING` / `SOURCE_INVALID`: missing path, non-file path, or invalid source path
- Phase 9.1 `PATH_GUARD_REJECTED` / `BAD_PATH` / `PATH_REJECTED`: protected path, traversal, or outside approved root

### Case 1 - Malformed JSON/JSONL

Future behavior:

- fail closed before writing
- create no bundle directory
- create no `bundle_manifest.json`
- create no `index.md`
- copy no report
- identify `--source-manifest`
- state that manifest parsing failed
- prefer `MANIFEST_PARSE_FAILED`
- include `NO_FILES_WRITTEN` if compatible

Potential current surfaces:

```text
report bundle export --source-report <report> --source-manifest <malformed-jsonl> --out <bundle-dir>
report bundle export --source-report <report> --source-manifest <invalid-json-line> --out <bundle-dir>
```

### Case 2 - Parsed But Invalid Record Shape

Future behavior:

- fail closed before writing
- identify invalid manifest content or schema
- prefer `MANIFEST_INVALID`
- include `NO_FILES_WRITTEN` if compatible

Potential current surface:

```text
report bundle export --source-report <report> --source-manifest <invalid-record-shape> --out <bundle-dir>
```

### Case 3 - Missing Required Manifest Fields

Future behavior:

- fail closed before writing
- identify missing required fields when safe and concise
- prefer `MANIFEST_INVALID`
- include `NO_FILES_WRITTEN` if compatible

Potential current surface:

```text
report bundle export --source-report <report> --source-manifest <missing-required-fields> --out <bundle-dir>
```

### Case 4 - Empty Manifest

Future implementation must inspect current semantics first:

- if empty manifest is invalid, reject with `MANIFEST_INVALID`
- if empty manifest is valid but has no records, preserve that behavior
- do not invent a rejection if current behavior treats empty manifests as valid

### Case 5 - Manifest References Invalid Or Missing Artifact

Future implementation must inspect current semantics first:

- if current code validates referenced artifacts, reject before writing
- if current code only records metadata without dereferencing, preserve current behavior
- distinguish manifest content invalidity from source path missing/invalidity

## Desired Future Behavior

Future implementation should ensure:

- rejection happens before output artifacts are written
- no bundle directory, `bundle_manifest.json`, `index.md`, copied report, or zip is created
- no production/default report, manifest, bundle, log, config, session, intake, baseline, registry, or runtime state is written during tests
- output identifies `--source-manifest`
- wording distinguishes missing source manifest path, non-file source manifest path, path-guard rejected source manifest path, parse-failed source manifest content, and semantically invalid source manifest content
- output includes `MANIFEST_PARSE_FAILED` or `MANIFEST_INVALID` where appropriate
- output includes `NO_FILES_WRITTEN` if compatible with the existing output style

## Stable Token Policy

Preferred conceptual tokens:

```text
MANIFEST_PARSE_FAILED
MANIFEST_INVALID
NO_FILES_WRITTEN
```

Existing tokens to preserve for their current domains:

```text
SOURCE_MISSING
SOURCE_INVALID
PATH_GUARD_REJECTED
BAD_PATH
PATH_REJECTED
```

Rules:

- do not use `MANIFEST_PARSE_FAILED` for missing path, non-file path, or path-guard rejection
- do not use `MANIFEST_INVALID` for missing/non-file path
- do not use `SOURCE_MISSING` or `SOURCE_INVALID` for malformed content when the manifest file exists and is readable
- do not use `PATH_GUARD_REJECTED`, `BAD_PATH`, or `PATH_REJECTED` for content parse failures when the path was accepted
- do not use `OVERWRITE_UNSUPPORTED`, `ZIP_UNSUPPORTED`, `INVALID_OPTION_COMBINATION`, or `FORCE_UNSUPPORTED` for manifest content failures unless current semantics truly require it and the implementation report explains why
- do not use success tokens in rejection output

## Wording Draft

Recommended parse failure wording:

```text
Bundle Export Rejected
status                   MANIFEST_PARSE_FAILED
source_option            --source-manifest
source_kind              manifest
write_status             NO_FILES_WRITTEN
conclusion               BUNDLE_EXPORT_REJECTED
```

Recommended invalid-content wording:

```text
Bundle Export Rejected
status                   MANIFEST_INVALID
source_option            --source-manifest
source_kind              manifest
write_status             NO_FILES_WRITTEN
conclusion               BUNDLE_EXPORT_REJECTED
```

Preserve the existing human-readable style if the output framework uses a different shape.

## Must Not Appear

Manifest parse/invalid rejection output must not include success tokens:

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
ZIP_UNSUPPORTED
OVERWRITE_UNSUPPORTED
PATH_GUARD_REJECTED
OUTSIDE_APPROVED_ROOT
SOURCE_MISSING
SOURCE_INVALID
FORCE_UNSUPPORTED
```

## Success Behavior To Preserve

Future implementation must preserve:

- Candidate A report export success
- Candidate B manifest success
- Candidate C directory bundle success
- `report export --force`
- Phase 7.2A invalid option combination rejection
- Phase 7.2B missing/non-file source input rejection
- Phase 7.2C zip unsupported rejection
- Phase 8.2 no-force overwrite rejection
- Phase 9.1 path-guard rejection
- dry-run behavior
- JSON / `to_dict()` compatibility
- command inventory/write surface

## Test Requirements

Future implementation tests must use pytest temp paths and avoid production/default runtime artifacts.

Tests should cover real current surfaces only:

- malformed JSON/JSONL source manifest
- parsed but invalid record shape, if current semantics reject it
- missing required fields, if current semantics reject them
- empty manifest, only if current semantics reject it
- invalid artifact references, only if current semantics validate them

Assertions:

- non-success result
- no bundle directory
- no `bundle_manifest.json`
- no `index.md`
- no copied report
- output identifies `--source-manifest`
- `MANIFEST_PARSE_FAILED`, `MANIFEST_INVALID`, or an existing equivalent appears
- `NO_FILES_WRITTEN` appears if compatible
- success tokens are absent
- missing/non-file/path-guard semantics are unchanged

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
- any existing manifest parse/helper module, if one already exists
- `tests/test_report_bundle.py`
- `tests/test_report_bundle_output_messages.py`
- `tests/test_real_bundle_export_output_integration.py`
- implementation notes in the Phase 10 docs

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

## Boundary Requirements

Future implementation must not:

- run CE
- manually execute production/default report or bundle writes
- use the read-only wrapper for write-capable exports
- weaken path guards
- expand approved roots
- add write destinations
- create runtime validation artifacts outside pytest temp paths
- change successful report or bundle output content
- change manifest schema
- change command inventory counts except where separately contracted

## Stop Conditions For Future Implementation

Future implementation must STOP if:

- no current source manifest parse/format rejection surface exists
- implementation requires a broad manifest model refactor
- implementation weakens path guards or expands approved roots
- tests require production/default writes
- manual real writes are required
- wrapper changes are required
- CE/runtime behavior is involved
- Candidate A/B/C success outputs would change
- `report export --force` behavior would change
- Phase 7/8/9 rejection outputs would change unexpectedly

## Recommended Next Phase

```text
Phase 10.1 - source manifest parse/invalid rejection wording implementation
```

This is superseded by the Phase 10.2 STOP result for isolated `--source-manifest`. The recommended near-term next phase is:

```text
Phase 10.3-contract - default manifest parse rejection wording contract
```

An isolated source-manifest parse implementation should proceed only after a separate isolated source-manifest validation surface contract defines the behavior.
