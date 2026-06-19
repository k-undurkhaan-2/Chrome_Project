# Python Tooling Invalid Option Combination Wording Contract

## Purpose

This document defines the Phase 7.2A contract for the first narrow rejection-path wording implementation slice:

```text
--manifest-out without --record-manifest
```

This contract does not implement source changes, run commands, add commands, add options, or authorize writes.

Future implementation must be narrow, test-backed, and limited to fail-closed wording for this invalid option combination. It must not alter success paths, dry-run behavior, Candidate A/B/C success wording, report content, manifest schema, bundle behavior, path guards, wrapper behavior, or CE/runtime behavior.

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

## Target Rejection Path

Target invalid option combination:

```powershell
report export --out <report-path> --manifest-out <manifest-path>
```

without:

```text
--record-manifest
```

`--manifest-out` is only meaningful when a manifest write is requested. Without `--record-manifest`, the command should reject the combination before any write is attempted.

## Desired Future Behavior

Future implementation should ensure:

- the command fails closed before writing anything
- no report file is created
- no custom manifest is created
- no default production manifest is created
- no runtime report, runtime manifest, runtime bundle, log, registry, baseline, session, intake, or local config file is written
- no parent directories are created if avoidable
- exit status is nonzero or follows the existing CLI error style
- output clearly explains that the option combination is invalid
- output names the invalid option: `--manifest-out`
- output names the required companion flag: `--record-manifest`
- output includes or maps to a stable invalid-combination token
- output includes a no-write signal if compatible with the existing style

This future behavior must not:

- change successful `REPORT_EXPORT_OK` behavior
- change `report export --record-manifest` behavior
- change `report export --record-manifest --manifest-out <path>` behavior
- change Candidate A/B/C success output behavior
- change dry-run behavior
- change JSON output or `to_dict()` unless a separate contract authorizes it

## Stable Token Policy

Preferred token:

```text
INVALID_OPTION_COMBINATION
```

Meaning:

- an option was supplied in a combination that is invalid before any write should occur
- the operator must change the command before retrying
- no report, manifest, bundle, log, config, registry, baseline, session, or intake file should be written

Recommended companion no-write token:

```text
NO_FILES_WRITTEN
```

Rules:

- do not reuse `BAD_PATH` for this condition
- do not use `MANIFEST_NOT_WRITTEN` as the primary rejection token
- do not emit success-write tokens
- do not emit bundle success tokens
- do not emit `WRAPPER_UNSUPPORTED` unless wrapper context is actually involved
- do not emit `CE_NOT_RUN` unless the existing error-output style includes CE boundary tokens for this command class

Forbidden success tokens in this rejection path:

- `REPORT_EXPORT_OK`
- `WRITE_COMPLETE`
- `MANIFEST_RECORDED`
- `BUNDLE_EXPORT_COMPLETE`
- `BUNDLE_EXPORT_OK`

If adding `INVALID_OPTION_COMBINATION` is too broad for the first implementation, the future task may improve wording without a new token, but it must document why and preserve equivalent assertions in tests.

## Wording Draft

Recommended future human-readable shape:

```text
Invalid option combination
status                   INVALID_OPTION_COMBINATION
invalid_option           --manifest-out
requires                 --record-manifest
write_status             NO_FILES_WRITTEN
conclusion               REPORT_EXPORT_REJECTED
```

If the current output framework does not use this table shape, preserve the existing style and include equivalent information:

- invalid option
- missing required companion flag
- rejection status
- no-write status

The wording should be concise enough for PowerShell and direct CLI output.

## Error / Result Status

Preferred conceptual result status:

```text
REPORT_EXPORT_REJECTED
```

An existing equivalent is acceptable if it already fits the report export result model.

Rules:

- do not change successful `REPORT_EXPORT_OK` status
- do not change dry-run success status
- do not change manifest-recorded success status
- do not change bundle export statuses
- do not change JSON schema without a separate contract

## Test Requirements For Future Implementation

Future implementation must use tests rather than manual real writes.

### Invalid Combination Fails Closed

Use pytest temporary paths:

```text
report export --out <tmp-report> --manifest-out <tmp-manifest>
```

without:

```text
--record-manifest
```

Assert:

- command/result is non-success
- invalid-combination wording appears
- `--manifest-out` appears in the error wording
- `--record-manifest` appears in the error wording
- report file does not exist
- custom manifest file does not exist
- default `reports/python_tooling/manifest.jsonl` does not exist
- no runtime artifacts are created
- forbidden success tokens are absent

### Valid Combination Still Works In Tests

Existing or updated tests should still cover:

```text
report export --out <tmp-report> --record-manifest --manifest-out <tmp-manifest>
```

Assert:

- command/result succeeds
- report file exists
- custom manifest file exists
- default production manifest is not written
- `MANIFEST_RECORDED` appears
- invalid-combination wording is absent

### Existing Behavior Remains Stable

Future implementation must keep these regressions green:

- Candidate A tests
- Candidate B tests
- Candidate C tests
- dry-run tests
- default `--record-manifest` behavior
- command inventory with `writes_files_count = 2`
- command inventory with `runs_ce_count = 0`

## Suggested Future Implementation Files

Likely future source/test files:

- `src/armedforces_tool/cli.py`
- `src/armedforces_tool/report_export.py`
- `src/armedforces_tool/report_output_messages.py`
- `tests/test_report_export.py`
- `tests/test_report_export_manifest_output_integration.py`
- `tests/test_real_report_export_output_integration.py`
- `tests/test_report_bundle_output_messages.py`

Do not modify these files in this contract phase.

## Future Validation Commands

Future implementation should run targeted tests first:

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"

.venv\Scripts\python.exe -m pytest tests/test_report_export.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_report_export_manifest_output_integration.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_real_report_export_output_integration.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest tests/test_report_bundle_output_messages.py --basetemp .tmp_pytest
.venv\Scripts\python.exe -m pytest --basetemp .tmp_pytest
Remove-Item -Recurse -Force .tmp_pytest -ErrorAction SilentlyContinue
```

Also run read-only status/inventory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 inventory
```

Future implementation validation must not manually run real report export, dry-run, `--record-manifest`, report bundle export, bundle export, write, restore, or CE unless a later task explicitly authorizes it.

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
- change JSON schema without a separate contract
- perform manual real writes
- create runtime artifacts outside pytest temporary directories

## Stop Conditions For Future Implementation

Stop if:

- cleanly detecting this invalid combination requires a broad command parser refactor
- adding the token changes unrelated success output
- JSON changes are required
- tests would need to write production/default paths
- real writes are required to validate
- wrapper changes are required
- CE/runtime behavior is involved
- path guards would need weakening
- Candidate A/B/C success outputs would change

## Recommended Next Phase

Recommended next phase:

```text
Phase 7.2A - invalid option combination wording implementation
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
