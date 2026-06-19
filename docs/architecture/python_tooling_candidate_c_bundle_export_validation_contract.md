# Python Tooling Candidate C Bundle Export Validation Contract

## Purpose

This contract defines a future Candidate C real-write validation smoke for:

```text
report bundle export
```

This document does not run `report bundle export`, does not authorize execution by itself, and does not change command behavior. Future execution requires an explicit operator prompt that authorizes the exact write targets.

Candidate C validates bundle export success output wording and bundle artifact boundaries. It is the largest Phase 6 real-write validation slice so far because it creates a directory bundle with multiple files. Candidate C must not run until isolated source and bundle output paths are confirmed from the existing CLI/source contract.

## Baseline and Prerequisites

Checkpoint baseline:

```text
python-tooling-phase3-final-checkpoint-20260616
python-tooling-powershell-wrapper-readonly-checkpoint-20260616
python-tooling-output-wording-checkpoint-20260618
```

Validation milestones:

```text
Phase 6.3A-R2 Candidate A real report export validation smoke: PASS
Phase 6.3B-R1 Candidate B report export manifest validation smoke: PASS
```

Future Candidate C prerequisites:

- clean working tree before execution
- Candidate A validation PASS has been recorded
- Candidate B validation PASS has been recorded
- `overall_status = SAFE`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- wrapper remains read-only
- direct Python invocation only
- no CE
- exact source report path/input option must be confirmed from existing CLI/source
- exact bundle output path option must be confirmed from existing CLI/source
- target bundle directory must not exist
- source fixture path must not exist unless the future execution task explicitly creates it and owns cleanup
- no zip
- no `--force`
- no overwrite
- no runtime/log/config/session/baseline/intake/registry writes

## Candidate C Scope

Allowed in the future execution smoke:

- create a controlled source report fixture under the declared validation root only if required and explicitly authorized by the future execution prompt
- optionally create a controlled source manifest fixture under the declared validation root only if required by the current bundle CLI contract and explicitly authorized
- run one real `report bundle export` command
- use directory bundle output only
- use human-readable output mode only, unless existing command semantics force otherwise
- inspect stdout/stderr, return code, bundle directory existence, `bundle_manifest.json`, `index.md`, copied report content, hashes, and final status
- clean up only files/directories created by the same validation task, if cleanup is explicitly authorized in that future task

Not allowed:

- zip export
- production/default reports or manifest paths
- `report export`
- `report export --record-manifest`
- `--dry-run`
- wrapper export shortcut
- CE
- `--force`
- overwrite
- approved-root expansion
- path-guard weakening
- source/test/doc implementation changes
- deleting pre-existing user files

## CLI Support Requirement

The future Candidate C execution smoke must first confirm the exact current bundle CLI contract.

It must determine:

- bundle output directory option
- source report option or source report discovery behavior
- optional source manifest option, if the command supports or needs one
- whether the bundle output type is directory-only
- whether zip is rejected / unsupported
- whether overwrite is rejected / unsupported

Possible existing options to inspect, depending on the current CLI contract:

```text
--out
--out-dir
--bundle-out
--source-report
--report
--manifest
--manifest-path
```

Use only options that actually exist.

If the command cannot target an isolated bundle output directory under the declared validation root, STOP before running `report bundle export`.

If the command cannot target an isolated source report/manifest input or would require reading production/default reports/manifest, STOP before running `report bundle export`.

Do not add or modify CLI options in the future smoke.

## Proposed Future Validation Paths

Proposed future source and output paths:

```text
reports/python_tooling/validation/phase6_real_write_output_validation/candidate_c_bundle_export/source/report_output.md
reports/python_tooling/validation/phase6_real_write_output_validation/candidate_c_bundle_export/source/manifest.jsonl
reports/python_tooling/validation/phase6_real_write_output_validation/candidate_c_bundle_export/bundle/
```

Expected bundle contents if the current CLI contract matches the existing implementation:

```text
reports/python_tooling/validation/phase6_real_write_output_validation/candidate_c_bundle_export/bundle/bundle_manifest.json
reports/python_tooling/validation/phase6_real_write_output_validation/candidate_c_bundle_export/bundle/index.md
reports/python_tooling/validation/phase6_real_write_output_validation/candidate_c_bundle_export/bundle/reports/
```

These paths are proposals for the future execution smoke only. They must not be created in this contract task.

If any target bundle directory or target source fixture exists at future execution time, the execution smoke must stop unless explicitly authorized to reuse that path. The parent validation directory must not be cleaned if it existed before. Only artifacts created by the future Candidate C task may be removed by that task.

## Future Command Template

The future execution smoke must confirm option names from the repository's existing CLI contract before execution.

Placeholder template:

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"

.venv\Scripts\python.exe -m armedforces_tool report bundle export `
  <existing-source-report-option> reports/python_tooling/validation/phase6_real_write_output_validation/candidate_c_bundle_export/source/report_output.md `
  <existing-bundle-output-option> reports/python_tooling/validation/phase6_real_write_output_validation/candidate_c_bundle_export/bundle
```

If a source manifest option is required/supported:

```powershell
  <existing-source-manifest-option> reports/python_tooling/validation/phase6_real_write_output_validation/candidate_c_bundle_export/source/manifest.jsonl
```

The future execution smoke must not use:

```text
--dry-run
--zip
--force
```

The future execution smoke must not use wrapper export shortcuts.

## Future Snapshot Plan

Before and after Candidate C, record:

```powershell
git status --short --untracked-files=all
Test-Path reports/python_tooling/full_status.md
Test-Path reports/python_tooling/manifest.jsonl
Test-Path reports/python_tooling/bundles
Test-Path reports/python_tooling/validation
Test-Path docs/reports/python_tooling
Test-Path log/case_registry.jsonl
Test-Path reports/python_tooling/validation/phase6_real_write_output_validation/candidate_c_bundle_export/source/report_output.md
Test-Path reports/python_tooling/validation/phase6_real_write_output_validation/candidate_c_bundle_export/source/manifest.jsonl
Test-Path reports/python_tooling/validation/phase6_real_write_output_validation/candidate_c_bundle_export/bundle
```

If files exist:

- record SHA256 hash
- do not modify
- do not delete
- stop if any exact Candidate C target file/directory exists before execution unless reuse is explicitly authorized

If directories exist:

- record existence
- record child listing where practical
- do not delete pre-existing directories

If `log/case_registry.jsonl` exists, record SHA256 before and after. The hash must remain unchanged.

If production/default `reports/python_tooling/manifest.jsonl` exists, record SHA256 before and after. The hash must remain unchanged.

Default expected behavior:

- only declared Candidate C validation paths change
- production/default reports/manifest/bundles remain absent or unchanged

## Future Evidence Requirements

The future Candidate C execution smoke must report:

- exact command line run
- confirmed source report option or source discovery behavior
- confirmed source manifest option, if used
- confirmed bundle output option
- exit code
- stdout/stderr
- whether `BUNDLE_EXPORT_COMPLETE` appeared as expected
- whether `SOURCE_UNCHANGED` appeared as expected
- whether `APPROVED_ROOT` appeared as expected
- whether `CE_NOT_RUN` appeared as expected
- whether `WRAPPER_UNSUPPORTED` or equivalent direct-Python boundary wording appeared if expected by current output wording contract
- confirm `NO_FILES_WRITTEN` does not appear
- confirm `REPORT_EXPORT_OK` does not appear
- confirm `WRITE_COMPLETE` does not appear unless current bundle contract intentionally uses it with justification
- confirm `MANIFEST_RECORDED` does not appear
- confirm `MANIFEST_NOT_WRITTEN` does not appear
- confirm `BUNDLE_NOT_CREATED` does not appear
- confirm `ZIP_UNSUPPORTED` does not appear in directory success output
- source report path/hash before and after
- source manifest path/hash before and after, if used
- bundle directory path
- `bundle_manifest.json` hash/size and limited excerpt
- `index.md` hash/size and limited excerpt
- copied report file path/hash/content excerpt
- artifact before/after table
- final status/inventory
- cleanup result, if cleanup is authorized

## Expected Candidate C Output Wording

Expected present in future Candidate C real-write success output:

- `BUNDLE_EXPORT_COMPLETE`
- `SOURCE_UNCHANGED`
- `APPROVED_ROOT`
- `CE_NOT_RUN`
- `WRAPPER_UNSUPPORTED` or equivalent direct-Python/wrapper-boundary wording if currently part of the contract

Expected absent:

- `NO_FILES_WRITTEN`
- `REPORT_EXPORT_OK`
- `MANIFEST_RECORDED`
- `MANIFEST_NOT_WRITTEN`
- `BUNDLE_NOT_CREATED`
- `ZIP_UNSUPPORTED`
- dry-run success wording
- report export success wording

If current helper output intentionally includes a generic success token such as `WRITE_COMPLETE`, the future smoke must classify it according to the current source contract and report whether it is acceptable or noisy.

## Phase 6.3C Validation Status

Candidate C bundle export validation smoke: STOP.

Stop reason:

```text
current report bundle export cannot target the required isolated Candidate C paths
```

Confirmed constraints:

- `--manifest` only accepts `reports/python_tooling/manifest.jsonl`
- `--out` is constrained to `reports/python_tooling/bundles/`
- isolated source/input and bundle output paths under `reports/python_tooling/validation/...` are unsupported

No real `report bundle export` command was run and no artifacts were created.

The support contract for unblocking Candidate C is:

```text
docs/architecture/python_tooling_candidate_c_isolated_bundle_path_support_contract.md
```

Future Candidate C execution must wait for isolated source/report and bundle output support.

## Future Cleanup Contract

Preferred cleanup policy:

- cleanup is explicit and opt-in in the future execution prompt
- if cleanup is authorized, remove only:
  - source fixture files created by the future task
  - created bundle directory
  - empty directories created by the same validation task
- do not remove:
  - pre-existing `reports/python_tooling/validation`
  - pre-existing parent directories
  - `reports/python_tooling/full_status.md`
  - production/default `reports/python_tooling/manifest.jsonl`
  - production/default `reports/python_tooling/bundles`
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

The future Candidate C execution smoke must stop before running `report bundle export` if:

- working tree is dirty with unexpected files
- Candidate A PASS is not established
- Candidate B PASS is not established
- `overall_status` is not SAFE
- `writes_files_count` is not `2`
- `runs_ce_count` is not `0`
- wrapper is no longer read-only
- exact bundle output option cannot be confirmed from existing CLI/source contract
- exact source report option/discovery behavior cannot be confirmed
- command would require production/default report or manifest paths
- target bundle directory exists
- source fixture path exists and reuse is not explicitly authorized
- command would require zip
- command would require `--force`
- command would overwrite anything
- command would write default manifest
- command would write default bundles path
- command would write log/registry/baseline/session/intake/local config
- command would run CE
- command would require wrapper export support
- command would require source/test/doc changes
- path guard / approved root behavior appears changed
- any runtime artifact outside the declared validation path would be written

## Post-Validation Interpretation

A future Candidate C PASS means:

- real `report bundle export` success output wording was validated once under a controlled path
- bundle directory creation was validated under the Candidate C path
- `bundle_manifest.json`, `index.md`, and copied report content were validated under the Candidate C path
- source report/manifest remained unchanged
- Candidate A/B/C Phase 6 real-write output validation line is complete
- this does not authorize wrapper write support
- this does not authorize CE/runtime mutation
- this does not authorize zip export or `--force`

A future Candidate C FAIL means:

- do not create a real-write validation checkpoint
- preserve evidence
- do not rerun with `--force`
- do not manually repair artifacts unless separately authorized
- report exact failure boundary
- if bundle directory was partially written, report exact path/hash/content excerpt and stop

## Next Phase Recommendation

Recommended next phase:

```text
Phase 6.3C - Candidate C bundle export validation smoke
```

This future phase must be explicitly write-authorized and must follow this contract.

Do not run Phase 6.3C in this task.

## Tag Policy

- no tag is created by Phase 6.2C
- no tag should be created after contract-only work
- a future tag may be considered only after Candidate C validation smoke passes and cleanup is verified

Potential future tag after Candidate A/B/C all pass:

```text
python-tooling-real-write-output-validation-checkpoint-20260619
```

This tag name is provisional only.

## Out Of Scope

- implementation changes
- tests
- wrapper write-capable support
- CE automation
- runtime write/restore migration
- Candidate C execution
- production/default reports/manifest/bundles mutation
- zip export
- `--force`
- approved-root expansion
- path guard weakening
- JSON output changes
