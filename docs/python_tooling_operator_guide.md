# Python Tooling Operator Guide

## Purpose

This is the operator entry point for Python tooling in `D:\armedforces.io-v2`.

For the full Phase 3 usage guide, use:

- `docs/python_tooling_phase3_usage_guide.md`

For daily commands and troubleshooting, start with:

- `docs/python_tooling_quick_reference.md`

For the current Phase 3 architecture summary, use:

- `docs/architecture/python_tooling_phase3_summary.md`

For the Phase 4 roadmap, use:

- `docs/architecture/python_tooling_phase4_plan.md`

## Current Stable Boundary

Phase 3 is closed at checkpoint:

- `python-tooling-phase3-final-checkpoint-20260616`

Current command inventory:

- commands: about `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable commands:
  - `report export`
  - `report bundle export`

Report manifest commands remain read-only:

- `report manifest preview`
- `report manifest list`
- `report manifest verify`

Report bundle read-only commands remain read-only:

- `report bundle preview`
- `report bundle verify`

`report bundle export --dry-run` remains no-write.

Unsupported / deferred:

- zip bundle export
- bundle `--force` / overwrite
- `docs/reports` bundle output
- CE/runtime mutation
- PowerShell mutation replacement

## Daily Safe Checks

For the shortest daily checklist, use `docs/python_tooling_quick_reference.md`.

Use these first:

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"

.venv\Scripts\python.exe -m armedforces_tool status overview
.venv\Scripts\python.exe -m armedforces_tool commands list
.venv\Scripts\python.exe -m armedforces_tool commands list --category report
.venv\Scripts\python.exe -m armedforces_tool report manifest verify
.venv\Scripts\python.exe -m armedforces_tool report bundle verify
```

Expected stable results:

- `status overview = SAFE`
- report inventory shows `report export` and `report bundle export` as the only write-capable commands
- `writes_files_count = 2`
- `runs_ce_count = 0`
- `report manifest verify` may return `NO_MANIFEST` when no runtime manifest exists
- `report bundle verify` may return `NO_MANIFEST` when no runtime manifest exists

## Read-Only PowerShell Wrapper

The read-only wrapper is available for the same safe daily checks.

Before starting the next tooling phase, review `docs/architecture/python_tooling_phase4_final_state.md` for the frozen wrapper boundary and handoff state.

Checkpoint tag:

```text
python-tooling-powershell-wrapper-readonly-checkpoint-20260616
```

Wrapper file:

```text
src/python_tooling_wrapper.ps1
```

The wrapper is a thin bridge to `.venv\Scripts\python.exe -m armedforces_tool ...`. It does not replace Python command inventory, and it does not replace legacy PowerShell mutation workflows.

Recommended invocation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 inventory
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 report-status
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 manifest-verify
powershell -NoProfile -ExecutionPolicy Bypass -File .\src\python_tooling_wrapper.ps1 bundle-verify
```

Direct execution such as `.\src\python_tooling_wrapper.ps1 status` may be blocked by local PowerShell `ExecutionPolicy`. That is local policy behavior, not wrapper failure. Operators do not need to change system `ExecutionPolicy`; use `-ExecutionPolicy Bypass -File` for validation and routine wrapper use.

Allowed wrapper commands:

- `status`
- `inventory`
- `report-status`
- `manifest-verify`
- `bundle-verify`

Explicitly forbidden wrapper commands:

- `report-export`
- `report-export-manifest`
- `bundle-export`
- `bundle-export-dry-run`
- `safe-reset`
- `set-diagnostic`
- `prepare-current-case`
- `collect-prepare`
- `case-intake-abandon`
- `unknown-command`
- any write-capable / runtime-adjacent command

Forbidden commands must be rejected nonzero and must not trigger any Python write-capable command.

The wrapper does not run CE and does not write report, manifest, bundle, log, config, registry, baseline, session, or intake state.

### Wrapper Boundary Tests

To validate the read-only wrapper boundary:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_python_tooling_wrapper_readonly.py --basetemp .tmp_pytest
```

These tests cover wrapper read-only behavior only. They do not authorize write-capable wrapper behavior and do not replace full pytest or smoke validation.

## Safe Report Workflow

Use the detailed workflow in `docs/python_tooling_phase3_usage_guide.md`.

Report/bundle export UX polish planning exists in `docs/architecture/python_tooling_report_bundle_ux_plan.md`. Current report/bundle commands remain unchanged, and the read-only wrapper still does not support write-capable export commands.

Report/bundle export UX contract exists in `docs/architecture/python_tooling_report_bundle_ux_contract.md`. Current command behavior is unchanged, and there is still no wrapper support for write-capable export commands.

Phase 5.5 help text polish is implemented for:

```powershell
.venv\Scripts\python.exe -m armedforces_tool report export --help
.venv\Scripts\python.exe -m armedforces_tool report bundle export --help
```

Use these help pages before any explicitly scoped export task. They clarify write-capable behavior, no-write dry-run meaning, approved roots, wrapper exclusion, and the fact that CE is not run by these commands. The polish is wording-only; export behavior and write boundaries remain unchanged.

The output wording contract exists in `docs/architecture/python_tooling_report_bundle_output_wording_contract.md`. It documents future dry-run, real-write, and rejection output requirements, but no output wording implementation is included yet. Current report/bundle command behavior remains unchanged.

Phase 5.7 added output wording helpers as implementation preparation. The helpers are not wired into current report/bundle commands, so current command behavior and write boundaries remain unchanged.

The dry-run output integration contract exists in `docs/architecture/python_tooling_dry_run_output_integration_contract.md`. Dry-run output integration is not active yet, and real export behavior is unchanged.

Dry-run output wording is now improved for `report export --dry-run` and `report bundle export --dry-run`. Real export behavior is unchanged, and the wrapper remains read-only.

The real-write output wording contract exists in `docs/architecture/python_tooling_real_write_output_contract.md`. No real-write output implementation is active yet; real export behavior is unchanged and the wrapper remains read-only.

Phase 5.13 added helper-only real-write output wording functions for future integration. Current command behavior is unchanged: real export remains direct Python, write-capable, and unavailable through the read-only wrapper.

The real-write output integration gate exists in `docs/architecture/python_tooling_real_write_output_integration_gate.md`. No real-write output integration is active yet, and the wrapper remains read-only.

The Candidate A real report export output contract exists in `docs/architecture/python_tooling_real_report_export_output_contract.md`. It does not change current command behavior, and the wrapper remains read-only.

Real report export output wording is improved for the non-`--record-manifest` success path. The wrapper remains read-only, and `--record-manifest` plus bundle output integration remain deferred.

The Candidate B manifest export output contract exists in `docs/architecture/python_tooling_report_export_manifest_output_contract.md`. No manifest output integration is active yet, and the wrapper remains read-only.

Manifest export output wording is improved for the `--record-manifest` success path. The wrapper remains read-only, and bundle output integration remains deferred.

Short form:

```powershell
.venv\Scripts\python.exe -m armedforces_tool report preview --type full-status
.venv\Scripts\python.exe -m armedforces_tool report export --dry-run --type full-status --out reports/python_tooling/full_status.md
.venv\Scripts\python.exe -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md
.venv\Scripts\python.exe -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md --record-manifest
.venv\Scripts\python.exe -m armedforces_tool report manifest verify
.venv\Scripts\python.exe -m armedforces_tool report manifest list
```

Use dry-run before real export. Clean smoke-created report and manifest artifacts when a validation task requires cleanup.

## Safe Bundle Workflow

Use the detailed workflow in `docs/python_tooling_phase3_usage_guide.md`.

Short form:

```powershell
.venv\Scripts\python.exe -m armedforces_tool report bundle preview
.venv\Scripts\python.exe -m armedforces_tool report bundle verify
.venv\Scripts\python.exe -m armedforces_tool report bundle export --dry-run --out reports/python_tooling/bundles/<bundle_id>/
.venv\Scripts\python.exe -m armedforces_tool report bundle export --out reports/python_tooling/bundles/<bundle_id>/
```

Real bundle export is directory-only and writes only under `reports/python_tooling/bundles/<bundle_id>/`.

Bundle export success wording has been improved for the direct Python real bundle export path. The read-only PowerShell wrapper remains read-only, and zip export plus `--force` remain unsupported.

Phase 6.5C added isolated Candidate C validation inputs for future explicitly authorized validation tasks:

```powershell
.venv\Scripts\python.exe -m armedforces_tool report bundle export `
  --source-report reports/python_tooling/validation/<task>/source/report_output.md `
  --source-manifest reports/python_tooling/validation/<task>/source/manifest.jsonl `
  --out reports/python_tooling/validation/<task>/bundle
```

These options do not change daily safe checks. They remain part of the write-capable `report bundle export` command, are not exposed through the read-only wrapper, and must not be run during read-only smoke checks.

Phase 5 output wording final state is summarized in `docs/architecture/python_tooling_phase5_output_wording_final_state.md`. The checkpoint `python-tooling-output-wording-checkpoint-20260618` exists and covers help text wording, helper wording, dry-run wording, and Candidate A/B/C human-readable success wording integrations.

This checkpoint does not authorize wrapper export shortcuts and does not authorize manual real-write validation without a separate task.

Phase 6 selector exists in `docs/architecture/python_tooling_phase6_plan_selector.md`. The recommended next direction is real-write validation policy planning, not immediate real writes. The wrapper remains read-only.

The real-write validation policy exists in `docs/architecture/python_tooling_real_write_output_validation_policy.md`. Future Candidate A/B/C validation requires exact paths, before/after snapshots, cleanup rules, evidence capture, and stop conditions. The wrapper remains read-only.

The Candidate A contract exists in `docs/architecture/python_tooling_candidate_a_real_report_export_validation_contract.md`. It defines the smallest real-write validation slice: direct Python `report export` only, no wrapper shortcut, exact output path, snapshots, cleanup rules, and stop conditions.

Candidate A Phase 6.3A-R2 real report export validation smoke has passed. The Candidate B manifest validation contract now exists in `docs/architecture/python_tooling_candidate_b_report_export_manifest_validation_contract.md`.

Candidate B covers direct Python `report export --record-manifest` only. It requires an exact report path, an isolated manifest path, before/after snapshots, evidence capture, cleanup rules, and stop conditions. If the existing CLI/source cannot direct `--record-manifest` to an isolated validation manifest path, a future Candidate B execution smoke must stop before running `--record-manifest`. The wrapper remains read-only and must not be used for Candidate B validation.

Phase 6.3B stopped correctly because isolated manifest path support is missing. The support contract exists in `docs/architecture/python_tooling_candidate_b_isolated_manifest_path_support_contract.md` and plans future `--manifest-out <path>` support only. Default manifest mutation is not approved for Candidate B validation.

Phase 6.5B implemented `--manifest-out <path>` for `report export --record-manifest`. Candidate B real validation required a separate boundary smoke and explicit write-authorized rerun. Do not use the default production manifest path for any Candidate B validation rerun.

Candidate B Phase 6.3B-R1 real manifest validation smoke has passed. The smoke used direct Python only, wrote the isolated report and manifest under the declared validation path, kept the production/default manifest absent/unchanged, and cleaned the task-created artifacts.

The Candidate C contract exists in `docs/architecture/python_tooling_candidate_c_bundle_export_validation_contract.md`. It defines the bundle validation slice for a future `report bundle export` smoke. The wrapper remains read-only; Candidate C must use direct Python only and must confirm the exact source report path, optional source manifest path, bundle output path, snapshot list, cleanup boundary, and stop conditions before any real bundle export is run.

Phase 6.3C stopped because `report bundle export` could not yet target isolated Candidate C source/input and bundle output paths. Phase 6.5C implemented that isolated bundle validation path support: `report bundle export` now accepts `--source-report <path>`, accepts `--source-manifest <path>`, and allows isolated `--out <bundle-dir>` under approved roots when source inputs are supplied. Phase 6.6C-R2 boundary behavior passed, and Phase 6.3C-R1 real bundle validation passed under the declared isolated path. Default production bundle mutation is still not approved by Candidate C validation.

Phase 6 real-write output validation is complete for Candidate A/B/C under isolated paths. The final state is summarized in `docs/architecture/python_tooling_real_write_output_validation_final_state.md`. Phase 6.8 final checkpoint smoke passed, and the checkpoint tag `python-tooling-real-write-output-validation-checkpoint-20260619` is established. Production/default export paths remain separate, the wrapper remains read-only, and future work must start from a new selector/gate.

Phase 7 selector exists in `docs/architecture/python_tooling_phase7_plan_selector.md`. The recommended next direction is a rejection-path wording policy contract. Wrapper write support, production/default export workflows, and runtime mutation remain deferred unless a future selector, policy, tests, smoke validation, and checkpoint explicitly authorize them.

Phase 7.1 rejection-path wording policy exists in `docs/architecture/python_tooling_rejection_path_wording_policy.md`. It defines future fail-closed wording policy for path guard failures, overwrite refusal, zip unsupported, invalid option combinations, missing source inputs, wrapper unsupported, `CE_NOT_RUN`, and dry-run no-write output. The next recommended slice is an invalid option combination wording contract for `--manifest-out` without `--record-manifest`. This is documentation-only policy and does not change export behavior or wrapper boundaries.

Phase 7.2A invalid option combination wording contract exists in `docs/architecture/python_tooling_invalid_option_combination_wording_contract.md`. It defines future fail-closed wording for `report export --manifest-out <path>` without `--record-manifest`: the command should explain that `--manifest-out` requires `--record-manifest`, should fail before writing anything, and should not create a report, custom manifest, default manifest, or runtime artifact. No write-surface expansion is planned.

Phase 7.2A implementation clarifies that rejection path with `INVALID_OPTION_COMBINATION` and `NO_FILES_WRITTEN`. Candidate A/B/C success paths, dry-run behavior, wrapper read-only behavior, CE exclusion, zip unsupported behavior, and `--force` unsupported behavior remain unchanged.

Phase 7.2B missing source input wording contract exists in `docs/architecture/python_tooling_missing_source_input_wording_contract.md`. It defines future fail-closed wording for missing or invalid `--source-report` and `--source-manifest` inputs in `report bundle export`. Future implementation should clarify missing source report, invalid source report, missing source manifest, invalid source manifest, and `--source-manifest` without `--source-report` without expanding the write surface.

## Git Hygiene

Do not commit:

- `log/`
- `reports/` runtime outputs
- `docs/reports/` runtime outputs unless a task explicitly scopes them
- `src/run_case_config.local.lua`
- `src/run_case_config.local.lua.bak`
- `docs/codex_tasks/`

Do not use `git add .`. Stage only the intended files.

Check before and after every task:

```powershell
git status --short
```

## Troubleshooting

- If `python` is not on PATH, use `.venv\Scripts\python.exe`.
- `NO_MANIFEST` from manifest or bundle verify means no runtime manifest currently exists.
- `BUNDLE_ZIP_EXPORT_NOT_IMPLEMENTED` is expected for zip export.
- `OUTPUT_EXISTS` means bundle output already exists and overwrite is unsupported.
- `BAD_PATH` means a protected or traversal path was rejected.
- LF/CRLF warnings from `git diff --check` are acceptable if there is no whitespace error.

## Phase 5 Planning Gate

Before starting the next tooling phase, review `docs/architecture/python_tooling_phase5_plan_selector.md`.

The recommended next docs-first direction is operator quick reference / troubleshooting consolidation. Write-capable wrapper work and runtime mutation migration remain deferred until separate planning and validation exist.
