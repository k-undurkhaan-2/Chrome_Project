# Python Tooling Candidate A Real Report Export Validation Contract

## Purpose

This contract defines a future Candidate A real-write validation smoke for:

```text
report export
```

This contract does not run `report export`. It does not authorize execution by itself. Future execution requires explicit operator approval.

Candidate A validates report export output wording only. It is the smallest real-write validation slice because it writes one report file, does not record a manifest, and does not create a bundle.

## Baseline and Prerequisites

Current checkpoint tags:

```text
python-tooling-phase3-final-checkpoint-20260616
python-tooling-powershell-wrapper-readonly-checkpoint-20260616
python-tooling-output-wording-checkpoint-20260618
```

Prerequisites for the future Candidate A smoke:

- clean working tree before execution
- `overall_status = SAFE`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- wrapper remains read-only
- direct Python invocation only
- no CE
- target output path must not exist
- no `--force`
- no `--record-manifest`
- no bundle command
- no runtime/log/config/session/baseline/intake/registry writes

## Candidate A Scope

Allowed in the future execution smoke:

- one real `report export` command
- human-readable output mode only, unless existing command semantics force otherwise
- one output file inside the predeclared validation root
- post-run inspection of stdout/stderr, return code, output file existence, hash, and final status
- cleanup of only files/directories created by the same validation task, if cleanup is explicitly authorized in that future task

Not allowed:

- `--record-manifest`
- `report bundle export`
- `--dry-run`
- wrapper export shortcut
- CE
- zip export
- `--force`
- overwrite
- approved-root expansion
- path-guard weakening
- source/test/doc implementation changes
- deleting pre-existing user files

## Proposed Future Output Path

Exact proposed future validation path:

```text
reports/python_tooling/validation/phase6_real_write_output_validation/candidate_a_report_export/report_output.md
```

This path is a proposal for the future execution smoke. It must not be created in this contract task.

If it already exists at future execution time, the execution smoke must stop before running `report export`.

The parent validation directory must not be cleaned if it existed before. Only artifacts created by the future Candidate A task may be removed by that task.

## Future Command Template

The future execution smoke must first confirm the exact existing output-path option by read-only source/help inspection. It must not add or change any option.

Conservative command template:

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"
.venv\Scripts\python.exe -m armedforces_tool report export <existing-output-path-option> reports/python_tooling/validation/phase6_real_write_output_validation/candidate_a_report_export/report_output.md
```

The future execution smoke must not use:

```text
--dry-run
--record-manifest
--force
```

## Future Snapshot Plan

Before and after Candidate A validation, capture:

```powershell
git status --short --untracked-files=all
Test-Path reports/python_tooling/full_status.md
Test-Path reports/python_tooling/manifest.jsonl
Test-Path reports/python_tooling/bundles
Test-Path reports/python_tooling/validation
Test-Path docs/reports/python_tooling
Test-Path log/case_registry.jsonl
Test-Path reports/python_tooling/validation/phase6_real_write_output_validation/candidate_a_report_export/report_output.md
```

If files exist:

- record SHA256 hash
- do not modify
- do not delete
- stop if the exact Candidate A output file exists before execution

If directories exist:

- record existence
- record child listing where practical
- do not delete pre-existing directories

If `log/case_registry.jsonl` exists:

- record SHA256 before and after
- hash must remain unchanged

## Future Evidence Requirements

The future Candidate A execution smoke must report:

- exact command line run
- exit code
- stdout/stderr
- whether `REPORT_EXPORT_OK` appeared as expected
- whether `WRITE_COMPLETE` appeared as expected
- whether `CE_NOT_RUN` appeared as expected
- whether `WRAPPER_UNSUPPORTED` or equivalent direct-Python boundary wording appeared if expected by current output wording contract
- whether `APPROVED_ROOT` appeared as expected
- confirm `NO_FILES_WRITTEN` does not appear in real-write success output
- confirm `MANIFEST_RECORDED` does not appear
- confirm `BUNDLE_EXPORT_COMPLETE` does not appear
- output file path
- output file hash
- limited content excerpt or metadata from the created report file, if safe
- artifact before/after table
- cleanup result, if cleanup is authorized
- final `git status --short --untracked-files=all`
- final status/inventory

## Future Cleanup Contract

Preferred cleanup policy:

- cleanup is explicit and opt-in in the future execution prompt
- if cleanup is authorized, remove only:
  - `reports/python_tooling/validation/phase6_real_write_output_validation/candidate_a_report_export/report_output.md`
  - empty directories created by the same validation task

Do not remove:

- pre-existing `reports/python_tooling/validation`
- pre-existing parent directories
- `reports/python_tooling/full_status.md`
- `reports/python_tooling/manifest.jsonl`
- `reports/python_tooling/bundles`
- `docs/reports/python_tooling`
- `log/`
- local config
- any user-created files

If cleanup is not authorized:

- leave artifacts in place
- report exact remaining paths and hashes

## Future Stop Conditions

The future Candidate A execution smoke must stop before running `report export` if:

- working tree is dirty with unexpected files
- `overall_status` is not SAFE
- `writes_files_count` is not `2`
- `runs_ce_count` is not `0`
- wrapper is no longer read-only
- target output file exists
- target parent path exists but is not expected or appears user-owned
- exact output-path option cannot be confirmed from existing CLI/source contract
- command would require `--force`
- command would overwrite anything
- command would write manifest
- command would write bundle
- command would write log/registry/baseline/session/intake/local config
- command would run CE
- command would require source/test/doc changes
- path guard / approved root behavior appears changed
- any runtime artifact outside the declared validation path would be written

## Post-Validation Interpretation

A future Candidate A PASS means:

- real report export success output wording was validated once under a controlled path
- Candidate A output wording is confirmed at runtime for one safe path
- no manifest or bundle behavior was validated
- Candidate B/C still remain unvalidated
- this does not authorize wrapper write support
- this does not authorize CE/runtime mutation

A future Candidate A FAIL means:

- do not proceed to Candidate B/C
- preserve evidence
- do not rerun with `--force`
- do not manually repair artifacts unless separately authorized
- report exact failure boundary

## Next Phase Recommendation

Recommended next phase after this contract:

```text
Phase 6.3A: Candidate A real report export validation smoke
```

That future phase must be explicitly write-authorized and must follow this contract.

Do not run Phase 6.3A in this task.

## Tag Policy

- no tag is created by Phase 6.2A
- no tag should be created after contract-only work
- a future tag may be considered only after Candidate A/B/C validation smokes pass and cleanup is verified

## Out Of Scope

- implementation changes
- tests
- wrapper write-capable support
- CE automation
- runtime write/restore migration
- Candidate B manifest validation execution
- Candidate C bundle validation execution
- zip export
- `--force`
- approved-root expansion
- path guard weakening
- JSON output changes
