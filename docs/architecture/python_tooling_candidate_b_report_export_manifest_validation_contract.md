# Python Tooling Candidate B Report Export Manifest Validation Contract

## Purpose

This contract defines a future Candidate B real-write validation smoke for:

```text
report export --record-manifest
```

This contract is documentation only. It does not run `report export`, does not run `--record-manifest`, and does not authorize execution by itself. Future execution requires a separately scoped operator prompt with explicit approval.

Candidate B validates report export plus manifest success output wording only. It is more risky than Candidate A because it writes a report file and writes or appends a manifest record. Candidate B must not run until an isolated manifest path policy is confirmed from the existing CLI/source contract.

## Baseline and Prerequisites

Current checkpoint tags:

```text
python-tooling-phase3-final-checkpoint-20260616
python-tooling-powershell-wrapper-readonly-checkpoint-20260616
python-tooling-output-wording-checkpoint-20260618
```

Candidate A status:

```text
Phase 6.3A-R2 Candidate A real report export validation smoke: PASS
```

The future Candidate B execution smoke requires:

- clean working tree before execution
- Candidate A validation PASS recorded
- `overall_status = SAFE`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- wrapper remains read-only
- direct Python invocation only
- no CE
- target output path does not exist
- target manifest path is isolated and either absent or explicitly controlled for append validation
- no `--force`
- no bundle command
- no runtime/log/config/session/baseline/intake/registry writes

## Candidate B Scope

Allowed in a future execution smoke:

- one real `report export --record-manifest` command
- human-readable output mode only, unless existing command semantics force otherwise
- one output report file inside the predeclared validation root
- one controlled manifest record write or append inside the predeclared validation root only if existing CLI/source supports an isolated manifest path
- post-run inspection of stdout/stderr, return code, report file existence/hash, manifest file existence/hash, manifest line count, and final status
- cleanup of only files/directories created by the same validation task, if cleanup is explicitly authorized in that future task

Not allowed:

- production/default manifest path writes unless explicitly approved by the future execution prompt
- `report bundle export`
- `--dry-run`
- wrapper export shortcuts
- CE
- zip export
- `--force`
- overwrite
- approved-root expansion
- path-guard weakening
- source/test/doc implementation changes
- deleting pre-existing user files

## Manifest Isolation Requirement

This is the primary Candidate B boundary.

The future Candidate B execution smoke must first confirm whether the existing CLI/source supports an isolated manifest path for `--record-manifest`.

Possible isolated-manifest option names, if they exist in the current CLI contract, might include:

```text
--manifest
--manifest-path
--record-manifest-path
--manifest-out
```

If an isolated manifest path option exists, the future smoke may use:

```text
reports/python_tooling/validation/phase6_real_write_output_validation/candidate_b_report_export_manifest/manifest.jsonl
```

If no isolated manifest path option exists, the future execution smoke must stop before running `report export --record-manifest` and report:

```text
STOP: isolated Candidate B manifest path is not supported by existing CLI contract.
```

Do not add or modify CLI options in the execution smoke.

Do not write to production/default `reports/python_tooling/manifest.jsonl` unless the future prompt explicitly authorizes default manifest mutation and defines cleanup/rollback policy for that exact file. The default stance is: do not use the production/default manifest path for Candidate B validation.

## Phase 6.3B STOP and Support Contract

Phase 6.3B Candidate B validation smoke stopped before execution:

```text
STOP: isolated Candidate B manifest path is not supported by existing CLI contract.
```

No `report export --record-manifest` command was run, and no runtime report, manifest, or bundle artifact was created.

The support contract for unblocking Candidate B is:

```text
docs/architecture/python_tooling_candidate_b_isolated_manifest_path_support_contract.md
```

Future Candidate B execution must wait for `--manifest-out` or equivalent isolated manifest path support. The production/default manifest path remains disallowed for Candidate B validation unless a future prompt explicitly authorizes that exact mutation.

## Proposed Future Output Paths

Exact proposed future validation paths:

```text
reports/python_tooling/validation/phase6_real_write_output_validation/candidate_b_report_export_manifest/report_output.md
reports/python_tooling/validation/phase6_real_write_output_validation/candidate_b_report_export_manifest/manifest.jsonl
```

These paths are a proposal for the future execution smoke. They must not be created by this contract task.

At future execution time:

- if the report output path exists, stop before running the command
- if the manifest path exists, stop unless the future task explicitly validates append behavior
- do not clean the parent validation directory if it existed before execution
- remove only artifacts created by the future Candidate B task, if cleanup is authorized

## Future Command Template

The future execution smoke must first confirm the exact existing output-path option and isolated manifest-path option by read-only help/source inspection. It must not add or change any option.

Conservative command template:

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"

.venv\Scripts\python.exe -m armedforces_tool report export `
  --type full-status `
  <existing-output-path-option> reports/python_tooling/validation/phase6_real_write_output_validation/candidate_b_report_export_manifest/report_output.md `
  --record-manifest `
  <existing-manifest-path-option-if-supported> reports/python_tooling/validation/phase6_real_write_output_validation/candidate_b_report_export_manifest/manifest.jsonl
```

If no existing isolated manifest path option exists, future execution must stop and must not run `--record-manifest`.

The future execution smoke must not use:

```text
--dry-run
--force
```

The future execution smoke must not use wrapper export shortcuts.

## Future Snapshot Plan

Before and after Candidate B validation, capture:

```powershell
git status --short --untracked-files=all
Test-Path reports/python_tooling/full_status.md
Test-Path reports/python_tooling/manifest.jsonl
Test-Path reports/python_tooling/bundles
Test-Path reports/python_tooling/validation
Test-Path docs/reports/python_tooling
Test-Path log/case_registry.jsonl
Test-Path reports/python_tooling/validation/phase6_real_write_output_validation/candidate_b_report_export_manifest/report_output.md
Test-Path reports/python_tooling/validation/phase6_real_write_output_validation/candidate_b_report_export_manifest/manifest.jsonl
Test-Path reports/python_tooling/validation/phase6_real_write_output_validation/candidate_b_report_export_manifest
```

If files exist:

- record SHA256 hash
- do not modify
- do not delete
- stop if the exact Candidate B report output file exists before execution
- stop if the exact Candidate B manifest file exists before execution unless the future task explicitly validates append behavior

If directories exist:

- record existence
- record child listing where practical
- do not delete pre-existing directories

If `log/case_registry.jsonl` exists:

- record SHA256 before and after
- hash must remain unchanged

If production/default `reports/python_tooling/manifest.jsonl` exists:

- record SHA256 before and after
- hash must remain unchanged unless the future prompt explicitly authorizes default manifest mutation

Default expected behavior for Candidate B smoke:

- isolated validation manifest path changes
- production/default `reports/python_tooling/manifest.jsonl` remains absent or unchanged

## Future Evidence Requirements

The future Candidate B execution smoke must report:

- exact command line run
- confirmed output path option
- confirmed manifest path option, or STOP reason if unsupported
- exit code
- stdout/stderr
- whether `REPORT_EXPORT_OK` appeared as expected
- whether `WRITE_COMPLETE` appeared as expected
- whether `MANIFEST_RECORDED` appeared as expected
- whether `APPROVED_ROOT` appeared as expected
- whether `CE_NOT_RUN` appeared as expected
- whether `WRAPPER_UNSUPPORTED` or equivalent direct-Python boundary wording appeared if expected by the current output wording contract
- confirm `NO_FILES_WRITTEN` does not appear
- confirm `MANIFEST_NOT_WRITTEN` does not appear
- confirm `BUNDLE_EXPORT_COMPLETE` does not appear
- confirm `BUNDLE_NOT_CREATED` does not appear unless the current Candidate B contract intentionally keeps this token with explicit justification; default is absent
- confirm `ZIP_UNSUPPORTED` does not appear
- output report path
- output report hash
- manifest path
- manifest hash
- manifest line count / appended record count
- limited manifest record excerpt, if safe
- limited report content excerpt or metadata, if safe
- artifact before/after table
- final status/inventory
- cleanup result, if cleanup is authorized

## Expected Candidate B Output Wording

Expected present in future Candidate B real-write success output:

- `REPORT_EXPORT_OK`
- `WRITE_COMPLETE`
- `MANIFEST_RECORDED`
- `APPROVED_ROOT`
- `CE_NOT_RUN`
- `WRAPPER_UNSUPPORTED` or equivalent direct-Python/wrapper-boundary wording if currently part of the contract

Expected absent:

- `NO_FILES_WRITTEN`
- `MANIFEST_NOT_WRITTEN`
- `BUNDLE_EXPORT_COMPLETE`
- `BUNDLE_NOT_CREATED`
- `ZIP_UNSUPPORTED`
- dry-run success wording
- bundle export wording

## Future Cleanup Contract

Preferred cleanup policy:

- cleanup is explicit and opt-in in the future execution prompt
- if cleanup is authorized, remove only:
  - `reports/python_tooling/validation/phase6_real_write_output_validation/candidate_b_report_export_manifest/report_output.md`
  - `reports/python_tooling/validation/phase6_real_write_output_validation/candidate_b_report_export_manifest/manifest.jsonl`
  - empty directories created by the same validation task

Do not remove:

- pre-existing `reports/python_tooling/validation`
- pre-existing parent directories
- `reports/python_tooling/full_status.md`
- production/default `reports/python_tooling/manifest.jsonl`
- `reports/python_tooling/bundles`
- `docs/reports/python_tooling`
- `log/`
- local config
- any user-created files

If cleanup is not authorized:

- leave artifacts in place
- report exact remaining paths and hashes

If cleanup fails:

- report failure
- do not hide remaining files
- do not delete pre-existing files to compensate

## Future Stop Conditions

The future Candidate B execution smoke must stop before running `report export --record-manifest` if:

- working tree is dirty with unexpected files
- Candidate A PASS is not established
- `overall_status` is not SAFE
- `writes_files_count` is not `2`
- `runs_ce_count` is not `0`
- wrapper is no longer read-only
- exact output-path option cannot be confirmed from existing CLI/source contract
- isolated manifest path option cannot be confirmed from existing CLI/source contract
- target output file exists
- target manifest file exists and append behavior is not explicitly part of the task
- production/default `reports/python_tooling/manifest.jsonl` would be modified without explicit approval
- command would require `--force`
- command would overwrite anything
- command would write bundle
- command would write log/registry/baseline/session/intake/local config
- command would run CE
- command would require wrapper export support
- command would require zip support
- command would require source/test/doc changes
- path guard / approved root behavior appears changed
- any runtime artifact outside the declared validation path would be written

## Post-Validation Interpretation

A future Candidate B PASS means:

- real `report export --record-manifest` success output wording was validated once under a controlled path
- report file creation was validated under the Candidate B path
- manifest record creation/append was validated under the isolated Candidate B manifest path
- Candidate B output wording is confirmed at runtime for one safe path
- Candidate C still remains unvalidated
- this does not authorize wrapper write support
- this does not authorize CE/runtime mutation
- this does not authorize production/default manifest mutation outside the exact validation policy

A future Candidate B FAIL means:

- do not proceed to Candidate C
- preserve evidence
- do not rerun with `--force`
- do not manually repair artifacts unless separately authorized
- report exact failure boundary
- if a manifest was partially written, report exact path/hash/content excerpt and stop

## Next Phase Recommendation

Recommended next phase after this contract:

```text
Phase 6.3B: Candidate B report export manifest validation smoke
```

That future phase must be explicitly write-authorized and must follow this contract.

Do not run Phase 6.3B in this task.

## Tag Policy

- no tag is created by Phase 6.2B
- no tag should be created after contract-only work
- a future tag may be considered only after Candidate A/B/C validation smokes pass and cleanup is verified

## Out Of Scope

- implementation changes
- tests
- wrapper write-capable support
- CE automation
- runtime write/restore migration
- Candidate B execution
- Candidate C bundle validation execution
- production/default manifest mutation without explicit approval
- zip export
- `--force`
- approved-root expansion
- path guard weakening
- JSON output changes
