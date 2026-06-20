# Python tooling overwrite rejection without force wording contract

## Purpose

This document defines the Phase 8.2 contract for the next narrow rejection-path wording slice:

```text
existing-output overwrite rejection without force
```

This contract is documentation only. It does not implement wording changes, does not modify Python source or tests, does not modify the PowerShell wrapper, does not add commands or options, does not run CE, and does not authorize report, manifest, bundle, log, config, registry, baseline, session, intake, local config, or runtime writes.

This contract explicitly does not target:

```text
report export --force
```

`report export --force` is currently a supported direct Python CLI success path and must remain unchanged unless a future high-risk behavior change/deprecation contract explicitly authorizes changing it.

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
- zip export remains unsupported / fail-closed
- `report export --force` currently exists and enables approved-target overwrite
- `report bundle export` currently has no `--force` parser surface
- approved roots and path guards remain strict

## Target Rejection Cases

Future implementation must first inspect actual current source/help/tests and then target only real existing no-force rejection surfaces.

### Case 1 - Report export target already exists without force

```text
report export --out <existing-file>
```

Expected future behavior:

- fail closed if current behavior rejects overwrite without force
- existing file remains byte-for-byte unchanged
- no partial/temp replacement output remains
- output identifies the existing output path
- output states overwrite is unsupported unless explicitly authorized
- preferred token: `OVERWRITE_UNSUPPORTED`
- optional token: `NO_FILES_WRITTEN`

### Case 2 - Manifest output target already exists without authorized overwrite

```text
report export --record-manifest --manifest-out <existing-file>
```

Expected future behavior:

- future implementation must inspect whether this path currently overwrites, appends, rejects, or has different manifest semantics
- if current behavior rejects overwrite without authorization, clarify wording
- existing manifest remains byte-for-byte unchanged in rejection cases
- output identifies `--manifest-out`
- preferred token: `OVERWRITE_UNSUPPORTED` if overwrite rejection is the actual reason
- optional token: `NO_FILES_WRITTEN`
- do not break any append semantics if current manifest handling intentionally appends rather than overwrites

### Case 3 - Bundle output directory already exists

```text
report bundle export --out <existing-directory>
```

Expected future behavior:

- future implementation must inspect current behavior
- if current behavior rejects existing output directory, clarify wording
- existing directory and sentinel files remain unchanged
- no `bundle_manifest.json` is created or replaced
- no `index.md` is created or replaced
- no copied report is created or replaced
- preferred token: `OVERWRITE_UNSUPPORTED`
- optional token: `NO_FILES_WRITTEN`

### Case 4 - Bundle output path is an existing file

```text
report bundle export --out <existing-file>
```

Expected future behavior:

- fail closed
- existing file remains byte-for-byte unchanged
- no directory is created over the file
- output identifies the output path
- token may be `OVERWRITE_UNSUPPORTED` or a more accurate current invalid-output token if current code treats this as invalid output path rather than overwrite
- optional token: `NO_FILES_WRITTEN`

## Explicit Non-Target

This slice must not treat this path as rejection:

```text
report export --force
```

Current behavior:

- exposes `--force` in help
- lists `--force` in command descriptor
- implements overwrite when `force=True`
- has a passing test asserting successful overwrite

Do not introduce:

```text
FORCE_UNSUPPORTED
```

for `report export --force`.

`FORCE_UNSUPPORTED` is reserved only for a future real unsupported-force surface, such as if a command exposes `--force` but intentionally rejects it.

## Desired Future Behavior

Future implementation should ensure:

- no-force existing-output rejection fails closed before writing anything
- existing output files/directories remain unchanged
- no partial/temp output remains
- no production/default report, manifest, or bundle path is written during tests
- error wording identifies the offending output path or option
- error wording says overwrite is unsupported or not authorized
- output includes stable token `OVERWRITE_UNSUPPORTED`
- output includes `NO_FILES_WRITTEN` if compatible with current output style

## Stable Token Policy

Primary token for this slice:

```text
OVERWRITE_UNSUPPORTED
```

Optional no-write token:

```text
NO_FILES_WRITTEN
```

Reserved token, not for this slice unless a real unsupported-force surface exists:

```text
FORCE_UNSUPPORTED
```

Meaning:

- `OVERWRITE_UNSUPPORTED`: requested output would overwrite or reuse an existing path, and overwrite is not authorized in this invocation.
- `NO_FILES_WRITTEN`: failure happened before any output artifact was written.
- `FORCE_UNSUPPORTED`: a real `--force` surface exists for a command and is explicitly unsupported; this is not applicable to `report export --force` today.

Rules:

- do not use `FORCE_UNSUPPORTED` for `report export --force`
- do not use `ZIP_UNSUPPORTED` for overwrite failures
- do not use `SOURCE_MISSING` / `SOURCE_INVALID` for existing output path failures
- do not use `INVALID_OPTION_COMBINATION` unless the current parser actually models the condition that way
- do not use success tokens in no-force overwrite rejection output
- `SOURCE_UNCHANGED` remains success-only

## Wording Draft

Recommended human-readable wording for existing output rejection:

```text
Output Rejected
status                   OVERWRITE_UNSUPPORTED
output_path              <path>
write_status             NO_FILES_WRITTEN
conclusion               OUTPUT_REJECTED
```

Alternative for report export target:

```text
Report Export Rejected
status                   OVERWRITE_UNSUPPORTED
output_option            --out
output_path              <path>
write_status             NO_FILES_WRITTEN
conclusion               REPORT_EXPORT_REJECTED
```

Alternative for manifest target:

```text
Report Export Rejected
status                   OVERWRITE_UNSUPPORTED
output_option            --manifest-out
output_path              <path>
write_status             NO_FILES_WRITTEN
conclusion               REPORT_EXPORT_REJECTED
```

Alternative for bundle target:

```text
Bundle Export Rejected
status                   OVERWRITE_UNSUPPORTED
output_option            --out
output_path              <path>
write_status             NO_FILES_WRITTEN
conclusion               BUNDLE_EXPORT_REJECTED
```

If the current output framework does not use this exact table shape, preserve the existing human-readable style and include equivalent information.

## Must Not Appear In No-Force Overwrite Rejection Output

The no-force overwrite rejection output must not include:

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
FORCE_UNSUPPORTED
```

`FORCE_UNSUPPORTED` must not appear unless the rejected path is a real unsupported force surface, not simply an existing-output rejection.

## Success Behavior To Preserve

Future implementation must preserve current success behavior:

```text
report export --force
```

Expected unchanged behavior:

- still succeeds when current policy allows approved-target overwrite
- still uses success output
- may keep:
  - `REPORT_EXPORT_OK`
  - `WRITE_COMPLETE`
  - `overwritten = True`
  - `wrote_file = True`
- existing overwrite success test must remain valid unless a separate behavior-change contract explicitly changes it

Also preserve:

- Candidate A report export success
- Candidate B manifest success
- Candidate C directory bundle success
- Phase 7.2A invalid option rejection
- Phase 7.2B missing source rejection
- Phase 7.2C zip unsupported rejection
- dry-run behavior
- JSON / `to_dict()` compatibility
- command inventory/write surface

## Error / Result Status

Future implementation should choose result statuses consistent with current code.

Preferred conceptual status:

```text
OUTPUT_REJECTED
```

or an existing equivalent.

Rules:

- do not change JSON schema unless already consistent with current result model
- do not change successful `report export --force` behavior
- do not change successful Candidate A/B/C behavior
- do not change dry-run behavior

## Test Requirements For Future Implementation

Future implementation must add or update tests only for real current surfaces. Tests must use pytest temp paths.

### Existing report output file without force

Prepare an existing file with known content/hash.

Attempt current report export surface that would write to the same file without `--force`.

Assert:

- non-success result if current contract rejects overwrite without force
- existing file hash/content unchanged
- no partial/temp output remains
- output includes `OVERWRITE_UNSUPPORTED` if implemented
- output includes `NO_FILES_WRITTEN` if compatible
- success tokens absent
- `FORCE_UNSUPPORTED` absent

### Existing manifest output file without authorized overwrite

Prepare existing manifest file with known content/hash.

Attempt current manifest output surface that would overwrite or collide with it.

Assert according to actual current behavior:

- if current behavior rejects overwrite, non-success result
- existing manifest hash/content unchanged
- no partial/temp output remains
- output includes `OVERWRITE_UNSUPPORTED` if implemented
- output includes `NO_FILES_WRITTEN` if compatible
- success tokens absent
- `FORCE_UNSUPPORTED` absent

If current manifest behavior intentionally appends, do not convert it to overwrite rejection in this slice.

### Existing bundle output directory

Prepare existing directory with sentinel files.

Attempt bundle export to that directory.

Assert:

- non-success result if current behavior rejects existing bundle output
- sentinel files unchanged
- no `bundle_manifest.json` replacement
- no `index.md` replacement
- no copied report replacement
- output includes `OVERWRITE_UNSUPPORTED` if implemented
- success tokens absent
- `FORCE_UNSUPPORTED` absent

### Existing bundle output file

Prepare existing file at intended bundle output path.

Attempt bundle export to that path.

Assert:

- non-success result
- existing file hash/content unchanged
- no directory created over file
- output uses the chosen existing-output token if appropriate
- success tokens absent
- `FORCE_UNSUPPORTED` absent

### Supported report export force path unchanged

Keep or add guard coverage that:

```text
report export --force
```

continues to behave as currently supported.

Assert existing success expectations remain true:

- `REPORT_EXPORT_OK`
- overwrite metadata unchanged
- existing success test still passes

Do not relabel this path as rejection.

### Existing behavior unchanged

Ensure all still pass:

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
- `tests/test_report_export.py`
- `tests/test_report_export_manifest_output_integration.py`
- `tests/test_real_report_export_output_integration.py`
- `tests/test_report_bundle.py`
- `tests/test_real_bundle_export_output_integration.py`
- `tests/test_report_bundle_output_messages.py`
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

- disable `report export --force`
- relabel `report export --force` success as unsupported
- add write-capable commands
- add wrapper export shortcuts
- add CE integration
- enable new overwrite behavior
- add new force behavior
- enable zip export
- weaken path guards
- expand approved roots
- mutate production/default paths
- change JSON schema without contract
- perform manual real writes
- create runtime artifacts outside pytest temp dirs

## Stop Conditions For Future Implementation

Future implementation must stop if:

- no no-force existing-output rejection surface exists
- implementing wording would require changing `report export --force` success behavior
- implementing wording would require enabling overwrite
- implementation requires broad parser refactor
- tests would need to write production/default paths
- manual real writes are required to validate
- wrapper changes are required
- CE/runtime behavior is involved
- path guards would need weakening
- Candidate A/B/C success outputs would change
- Phase 7.2A/7.2B/7.2C rejection outputs would change unexpectedly

## Phase 8.2 Implementation Status

Implemented on 2026-06-20:

- `report export --out <existing-file>` without `--force` now uses the `OVERWRITE_UNSUPPORTED` and `NO_FILES_WRITTEN` rejection wording path.
- `report bundle export --out <existing-directory>` now uses the `OVERWRITE_UNSUPPORTED` and `NO_FILES_WRITTEN` rejection wording path.
- `report bundle export --out <existing-file>` now uses the same existing-output rejection wording path.
- `report export --force` remains the supported approved-target overwrite success path.

Inspected but not changed:

- `report export --record-manifest --manifest-out <existing-file>` is append/preflight manifest semantics, not an existing-output overwrite rejection surface in this slice.

Implementation boundaries:

- no new command or option
- no new overwrite behavior
- no `FORCE_UNSUPPORTED` use for `report export --force`
- no JSON/result schema change
- no wrapper, PowerShell, Lua, CE, or runtime mutation change

## Recommended Next Phase

Recommended:

```text
Phase 8.4 - no-force overwrite rejection final checkpoint smoke
```

Scope:

- validation-only
- verify implemented `OVERWRITE_UNSUPPORTED` / `NO_FILES_WRITTEN` rejection output
- preserve `report export --force`
- confirm Phase 8.2 boundary smoke remains stable
- no manual real writes
- no CE
- no wrapper changes
- no tag

## Phase 8.2 Boundary Smoke Status

Boundary smoke passed on 2026-06-20.

Validated:

- `report export --out <existing-file>` without `--force`
- `report bundle export --out <existing-directory>`
- `report bundle export --out <existing-file>`
- `OVERWRITE_UNSUPPORTED` / `NO_FILES_WRITTEN` output
- `report export --force` success behavior unchanged
- manifest output existing-file path remains append/preflight semantics
- `writes_files_count = 2`
- `runs_ce_count = 0`
- wrapper remains read-only
- targeted tests and full pytest passed
- no runtime artifacts were created

Final checkpoint smoke remains pending.

## Tag Policy

- no tag is created by this contract
- no tag should be created for this contract/candidate work
- a future checkpoint tag may be considered only after final checkpoint smoke passes
