# Python Tooling Real-Write Output Validation Policy

## Purpose

This policy governs future manual real-write validation of Python tooling report/bundle output wording.

This policy does not execute real writes. It does not authorize future real writes by itself. Each future real-write validation phase still requires explicit operator authorization, exact output paths, snapshots, cleanup rules, evidence requirements, and stop conditions.

Future validation must use approved output paths, before/after snapshots, bounded cleanup, and fail-closed stop conditions.

## Baseline and Checkpoints

Current checkpoint tags:

```text
python-tooling-phase3-final-checkpoint-20260616
python-tooling-powershell-wrapper-readonly-checkpoint-20260616
python-tooling-output-wording-checkpoint-20260618
```

Current state:

- commands = `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- wrapper remains read-only
- no CE in Python tooling
- no runtime mutation migration
- no zip export
- no `--force`

## Validation Candidates Covered

### Candidate A: Real Report Export Success Output

Future command class:

```text
report export
```

Purpose:

- validate real human-readable success output for report export
- validate output wording only
- validate file creation under approved output path only

Must not include:

- `--record-manifest`
- bundle export
- CE
- wrapper shortcut
- zip
- overwrite / `--force`

### Candidate B: Report Export With Manifest Success Output

Future command class:

```text
report export --record-manifest
```

Purpose:

- validate real human-readable success output when report file and manifest record are written
- validate manifest wording only
- validate manifest append behavior only in a controlled approved test manifest path if supported by existing command/options
- stop and report that no isolated manifest path exists if existing command/options cannot isolate the manifest path

Must not include:

- bundle export
- CE
- wrapper shortcut
- zip
- overwrite / `--force`
- modifying production/user manifest paths without explicit approval

### Candidate C: Real Bundle Export Success Output

Future command class:

```text
report bundle export
```

Purpose:

- validate real human-readable success output for directory bundle export
- validate bundle output wording only
- validate file creation under approved output path only

Must not include:

- zip export
- wrapper shortcut
- CE
- overwrite / `--force`
- modifying source report/manifest files

Phase 6.5C implementation note:

- `report bundle export` now supports `--source-report` and `--source-manifest` for isolated validation inputs.
- `report bundle export --out` may target an isolated bundle directory under `reports/python_tooling/` when source inputs are supplied.
- Default production bundle behavior under `reports/python_tooling/bundles/` remains backward-compatible.
- Future Candidate C real validation should use the isolated validation root and must still be separately authorized.

## Approved Output Path Policy

Recommended future validation root:

```text
reports/python_tooling/validation/phase6_real_write_output_validation/
```

This path is only a proposed future validation root. It must not be created in Phase 6.1.

Future validation tasks must:

- explicitly name the exact output file/directory path before running
- verify the path is inside an existing approved root
- reject paths outside approved roots
- stop if the destination already exists
- not use `--force`
- not overwrite existing files
- not delete pre-existing user files

Suggested future path layout:

```text
reports/python_tooling/validation/phase6_real_write_output_validation/
  candidate_a_report_export/
    report_output.md
  candidate_b_report_export_manifest/
    report_output.md
    manifest.jsonl
  candidate_c_bundle_export/
    bundle/
      bundle_manifest.json
      index.md
      reports/
```

This layout is a policy proposal only; it must not be created by this policy task.

## Snapshot Policy

Future validation phases must snapshot before and after:

- `git status --short --untracked-files=all`
- `reports/python_tooling/full_status.md`
- `reports/python_tooling/manifest.jsonl`
- `reports/python_tooling/bundles`
- `reports/python_tooling/validation`
- `docs/reports/python_tooling`
- `log/case_registry.jsonl`
- any exact candidate output path
- any exact candidate manifest path
- any exact candidate bundle path

If a path exists before validation:

- record existence
- record hash for files
- record directory listing/hash summary for directories when practical
- do not delete it
- do not overwrite it
- stop before running the command if the target output path exists

## Cleanup Policy

Future validation phases must define cleanup before execution.

Allowed cleanup target:

- only files/directories created by the same validation task
- only inside the exact predeclared validation root
- only after capturing post-run evidence
- never delete pre-existing files/directories
- never delete `log/`
- never delete production/user reports outside the predeclared validation root
- never delete local config

If cleanup fails:

- report failure
- do not hide or ignore it
- list remaining artifacts

## Evidence Policy

Future validation phases must capture:

- exact command line run
- exact output text
- return code
- created file paths
- hashes of created files
- selected content excerpts where safe
- artifact before/after table
- final git status
- wrapper/status inventory after validation

For output wording validation, evidence must include stable tokens:

- `WRITE_COMPLETE`
- `MANIFEST_RECORDED`
- `BUNDLE_EXPORT_COMPLETE`
- `SOURCE_UNCHANGED`
- `CE_NOT_RUN`
- `WRAPPER_UNSUPPORTED`
- `APPROVED_ROOT`
- `NO_FILES_WRITTEN` only in dry-run contexts, not real-write success contexts
- `ZIP_UNSUPPORTED` only when testing zip rejection in a separately authorized rejection-path task

## Stop Conditions

Future real-write validation must stop before running any write command if:

- working tree is dirty with unexpected files
- target output path already exists
- target manifest path already exists unless the task explicitly validates append behavior
- target bundle path already exists
- path is outside approved roots
- command would require `--force`
- command would overwrite anything
- command would write to `log/`, local config, registry, baseline, session, intake, or CE runtime state
- command would run CE
- command would require wrapper export support
- command would require zip support
- command would require modifying source code/tests/docs
- command inventory differs from expected `writes_files_count = 2` / `runs_ce_count = 0`
- wrapper becomes write-capable unexpectedly
- approved roots/path guard behavior appears changed

## Candidate Ordering

Recommended future execution order:

1. Candidate A validation contract / smoke
2. Candidate B validation contract / smoke
3. Candidate C validation contract / smoke

Rationale:

- Candidate A has the smallest write surface.
- Candidate B adds manifest append behavior risk.
- Candidate C creates a directory bundle and has the largest artifact surface.

Candidate A contract status: `docs/architecture/python_tooling_candidate_a_real_report_export_validation_contract.md` defined the first planned real-write validation contract. Execution later passed as Phase 6.3A-R2 under the declared isolated path.

Candidate A wording update: report export success output is expected to omit unrelated negative manifest/bundle tokens, including `MANIFEST_NOT_WRITTEN` and `BUNDLE_NOT_CREATED`.

Candidate A validation status: Phase 6.3A-R2 PASS has been recorded.

Candidate B contract status: `docs/architecture/python_tooling_candidate_b_report_export_manifest_validation_contract.md` defines the report export manifest validation slice. Candidate B required isolated manifest path confirmation before execution. If the CLI/source cannot direct `--record-manifest` to an isolated Candidate B manifest path in a future rerun, the execution smoke must stop before running `--record-manifest`.

Candidate B validation status: Phase 6.3B stopped because the existing CLI/source does not support an isolated manifest path. The support contract is `docs/architecture/python_tooling_candidate_b_isolated_manifest_path_support_contract.md`.

Candidate B was blocked until isolated manifest path support existed. Production/default `reports/python_tooling/manifest.jsonl` mutation remains disallowed for Candidate B validation.

Candidate B support status: Phase 6.5B implemented `--manifest-out <path>` for `report export --record-manifest`. Candidate B real validation later passed as Phase 6.3B-R1 after separate boundary smoke and explicit write authorization.

Candidate B validation status: Phase 6.3B-R1 PASS has been recorded. The isolated report and manifest validation artifacts were created under the declared Candidate B validation path, verified, and cleaned up. The production/default manifest remained absent/unchanged.

Candidate C contract status: `docs/architecture/python_tooling_candidate_c_bundle_export_validation_contract.md` defines the final and largest Phase 6 real-write validation slice. Candidate C execution later passed as Phase 6.3C-R1 after isolated source/report paths and bundle output paths were confirmed.

Candidate C validation status: Phase 6.3C stopped because the bundle CLI/source could not yet target isolated source/input and bundle output paths. Phase 6.5C implemented `--source-report <path>`, `--source-manifest <path>`, and isolated `--out <bundle-dir>` support. Phase 6.6C-R2 boundary validation passed, and Phase 6.3C-R1 real bundle validation passed under the declared isolated path. Production/default report, manifest, and bundle mutation remain disallowed by this validation line.

## Final Phase 6 Validation State

Candidate A/B/C real-write output validation has passed under controlled isolated paths. The final-state and checkpoint planning document is `docs/architecture/python_tooling_real_write_output_validation_final_state.md`.

This validation line does not authorize production/default export workflows, wrapper export shortcuts, CE/runtime mutation, zip export, `--force`, approved-root expansion, or default report/manifest/bundle path mutation.

## Future Phase Structure

Each candidate should use two phases:

1. contract phase, docs-only
2. execution smoke phase, write-authorized only after explicit approval

Example:

```text
Phase 6.2A: Candidate A real report export validation contract
Phase 6.3A: Candidate A real report export validation smoke
Phase 6.2B: Candidate B report export manifest validation contract
Phase 6.3B: Candidate B report export manifest validation smoke
Phase 6.2C: Candidate C bundle export validation contract
Phase 6.3C: Candidate C bundle export validation smoke
```

## Tag Policy

- no tag is created by Phase 6.1
- no tag should be created for policy-only docs unless separately requested
- a future tag may be considered only after Candidate A/B/C validation smoke passes and cleanup is verified

Provisional future tag after all real-write validation passes:

```text
python-tooling-real-write-output-validation-checkpoint-20260619
```

This tag name is provisional only.

## Out Of Scope

- implementation changes
- source/test changes
- wrapper write-capable support
- CE automation
- runtime write/restore migration
- zip export
- `--force`
- approved-root expansion
- path guard weakening
- JSON output changes
