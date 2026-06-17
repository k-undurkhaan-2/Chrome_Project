# Python Tooling Operator Guide

## Purpose

The Python tooling is a read-only sidecar for `D:\armedforces.io-v2`.

It is for analysis, status checks, parity checks, and operator visibility. It does not replace the existing PowerShell workflow, does not run CE, and does not write config, log, registry, baseline, session, or intake files.

Use Python tooling when you want a fast, structured view of the current project state. Continue to use the PowerShell tools for workflow mutation, local config updates, guarded runtime actions, and operator commands that intentionally write local state.

## Daily Commands

Recommended daily entry points:

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"

python -m armedforces_tool status overview
python -m armedforces_tool commands quickstart
python -m armedforces_tool commands list
python -m armedforces_tool safety doctor
python -m armedforces_tool baseline compare
python -m armedforces_tool case summary --latest 20 --profile full
python -m armedforces_tool registry summary
python -m armedforces_tool transaction summary
python -m armedforces_tool report preview --type full-status
```

## Command Groups

### `logs`

Read batch summary logs and compare Python parsing with the PowerShell classifier.

Representative commands:

```powershell
python -m armedforces_tool logs parse-latest --latest 5 --profile full
python -m armedforces_tool logs parse-batch --batch-id "20260614-232227"
python -m armedforces_tool logs parity-latest --latest 5 --profile full
```

### `case`

Analyze case coverage, historical known-true address evidence, stable candidates, retest queues, and sample plans.

Representative commands:

```powershell
python -m armedforces_tool case summary --latest 20 --profile full
python -m armedforces_tool case library --latest 100 --profile all
python -m armedforces_tool case stable-cases --latest 100 --profile full
python -m armedforces_tool case retest-queue --latest 100 --profile full
python -m armedforces_tool case sample-plan --latest 100 --profile full
```

### `safety`

Read local safety state and compare Python safety summaries with existing PowerShell checks.

Representative commands:

```powershell
python -m armedforces_tool safety status
python -m armedforces_tool safety plan
python -m armedforces_tool safety execution-status
python -m armedforces_tool safety doctor
python -m armedforces_tool safety doctor-parity
```

### `status`

Read workflow-facing status summaries, including diagnostic level, case intake state, and consolidated overview.

Representative commands:

```powershell
python -m armedforces_tool status diagnostic
python -m armedforces_tool status case-intake
python -m armedforces_tool status overview
```

### `baseline`

Read baseline metadata and compare the current baseline-eligible full window against the default baseline.

Representative commands:

```powershell
python -m armedforces_tool baseline list
python -m armedforces_tool baseline current
python -m armedforces_tool baseline compare
```

### `registry`

Read the local case registry JSONL without appending records or replacing the PowerShell classifier append workflow.

Representative commands:

```powershell
python -m armedforces_tool registry summary
python -m armedforces_tool registry list --limit 20
python -m armedforces_tool registry show --known-true-addr "0xCE061C7D48"
python -m armedforces_tool registry show --batch-id "20260614-232227"
```

### `transaction`

Read execution transaction history from existing batch summaries and registry records. This is for visibility only; it does not generate write or restore commands.

Representative commands:

```powershell
python -m armedforces_tool transaction summary
python -m armedforces_tool transaction list --limit 20
python -m armedforces_tool transaction list --transaction-type write_success
python -m armedforces_tool transaction show --batch-id "20260614-232227"
python -m armedforces_tool transaction show --known-true-addr "0x2CA061C7D48"
```

### `report`

Render existing Python summaries as Markdown. `report preview` is stdout-only and never writes files. `report export --dry-run` validates a future output path without writing. `report export` can write one `.md` report file, but only under the approved roots `reports/python_tooling/` or `docs/reports/python_tooling/`.

Report manifest views are read-only:

- `report manifest preview` discovers candidate manifest paths and reports `NO_MANIFEST` when none exists.
- `report manifest list` lists JSONL manifest entries if a manifest exists.
- `report manifest verify` validates required fields, duplicate `report_id` values, and missing referenced report files.

Report bundle preview, verify, and dry-run views are read-only:

- `report bundle preview` reads `reports/python_tooling/manifest.jsonl` and previews a future bundle shape.
- `report bundle verify` validates bundle readiness from the runtime report manifest and referenced report files.
- `report bundle export --dry-run` validates a future bundle output path and previews a future directory or zip bundle without writing.
- These read-only commands do not create bundle directories, zip files, copied reports, `bundle_manifest.json`, or `index.md`.
- Real directory bundle export is implemented for `reports/python_tooling/bundles/<bundle_id>/`.
- Real zip bundle export is not implemented and fails closed.

Manifest recording is available through `report export --record-manifest` for reports written under `reports/python_tooling/`. It writes the report and appends one JSONL record to `reports/python_tooling/manifest.jsonl`.

Manifest dry-run planning remains no-write. `report export --dry-run --record-manifest` previews the report path, planned manifest path, and planned manifest entry without creating directories, a report, or a manifest.

First-version manifest recording does not support `docs/reports/python_tooling/`. Using `--record-manifest` with a `docs/reports/python_tooling/*.md` target fails closed before writing.

Representative commands:

```powershell
python -m armedforces_tool report preview
python -m armedforces_tool report preview --type baseline-compare
python -m armedforces_tool report preview --type full-status
python -m armedforces_tool report preview --type full-status --json
python -m armedforces_tool report manifest preview
python -m armedforces_tool report manifest list
python -m armedforces_tool report manifest verify
python -m armedforces_tool report bundle preview
python -m armedforces_tool report bundle verify
python -m armedforces_tool report bundle export --dry-run --out reports/python_tooling/bundles/bundle_dry_run/
python -m armedforces_tool report bundle export --dry-run --zip --out reports/python_tooling/bundles/bundle_dry_run.zip
python -m armedforces_tool report bundle export --out reports/python_tooling/bundles/bundle_directory/
python -m armedforces_tool report export --dry-run --type full-status --out reports/python_tooling/full_status.md
python -m armedforces_tool report export --dry-run --type full-status --out reports/python_tooling/full_status.md --record-manifest
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md --record-manifest
```

Supported preview types include `status-overview`, `safety-doctor`, `baseline-compare`, `case-summary`, `registry-summary`, `transaction-summary`, and `full-status`.

## Report bundle workflow

Report bundle commands provide read-only preview/verification, no-write export planning, and guarded directory-only real export:

```powershell
python -m armedforces_tool report bundle preview
python -m armedforces_tool report bundle verify
python -m armedforces_tool report bundle preview --json
python -m armedforces_tool report bundle verify --json
python -m armedforces_tool report bundle export --dry-run --out reports/python_tooling/bundles/bundle_dry_run/
python -m armedforces_tool report bundle export --dry-run --zip --out reports/python_tooling/bundles/bundle_dry_run.zip
python -m armedforces_tool report bundle export --dry-run --out reports/python_tooling/bundles/bundle_dry_run/ --json
python -m armedforces_tool report bundle export --out reports/python_tooling/bundles/<bundle_id>/
```

Read-only boundary:

- `report bundle preview`, `report bundle verify`, and `report bundle export --dry-run` are read-only
- they read `reports/python_tooling/manifest.jsonl` by default
- they return `NO_MANIFEST` when the runtime manifest is absent
- bad `--manifest` paths return `BAD_PATH` or an equivalent rejection
- dry-run bad `--out` paths return `BAD_PATH` or an equivalent rejection
- they do not create a bundle directory
- they do not create a zip archive
- they do not copy report files
- they do not write `bundle_manifest.json`
- they do not write `index.md`
- they do not write the report manifest
- they do not call `report export`
- they do not run CE

Current inventory boundary:

- commands: about `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable commands: `report export`, `report bundle export`

Real directory bundle export boundary:

- approved output root: `reports/python_tooling/bundles/<bundle_id>/`
- creates only `bundle_manifest.json`, `index.md`, and copied reports under the bundle directory
- reads `reports/python_tooling/manifest.jsonl` but does not modify it
- reads source reports under `reports/python_tooling/` but does not modify or delete them
- rejects existing output directories; `--force` / overwrite is not implemented
- rejects real `--zip`; zip export remains deferred
- does not write `log/`, config, session, intake, baseline, or registry files
- does not run CE

Smoke cleanup rule: remove only bundle directories and smoke source report/manifest artifacts created by the current smoke. Do not delete pre-existing user bundles, reports, or manifests.

The bundle export contract is documented in `architecture/python_report_bundle_export_contract.md`.

## Report bundle directory export workflow

Use this flow only after a runtime report manifest exists under `reports/python_tooling/manifest.jsonl`.

```powershell
python -m armedforces_tool report bundle export --dry-run --out reports/python_tooling/bundles/<bundle_id>/
python -m armedforces_tool report bundle export --out reports/python_tooling/bundles/<bundle_id>/
python -m armedforces_tool report bundle verify
python -m armedforces_tool report bundle preview
```

Current directory export boundary:

- real directory export writes only under `reports/python_tooling/bundles/<bundle_id>/`
- creates `bundle_manifest.json`
- creates `index.md`
- copies referenced reports into the bundle-local `reports/` directory
- does not modify source reports
- does not modify `reports/python_tooling/manifest.jsonl`
- does not write `log/`, config, session, intake, baseline, or registry files
- does not run CE
- real zip export remains unsupported and fails closed
- `--force` / overwrite remains unsupported
- existing output directories are rejected
- smoke-created bundle artifacts must be cleaned by the operator after validation

Current inventory boundary:

- commands: about `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable commands: `report export`, `report bundle export`

## Report bundle export dry-run workflow

Use bundle export dry-run to validate a future bundle output path and preview bundle metadata without creating a bundle:

```powershell
python -m armedforces_tool report bundle export --dry-run --out reports/python_tooling/bundles/<bundle_id>/
python -m armedforces_tool report bundle export --dry-run --zip --out reports/python_tooling/bundles/<bundle_id>.zip
python -m armedforces_tool report bundle export --dry-run --out reports/python_tooling/bundles/<bundle_id>/ --json
```

Current dry-run boundary:

- dry-run commands do not create bundle directories
- dry-run commands do not create zip archives
- dry-run commands do not copy report files
- dry-run commands do not write `bundle_manifest.json`
- dry-run commands do not write `index.md`
- dry-run commands do not write the report manifest
- dry-run commands do not write reports, docs, logs, config, session state, intake state, baselines, or registry files
- when the runtime manifest is absent, dry-run returns `NO_MANIFEST` or `NOT_READY`
- real directory `report bundle export` is implemented separately and is write-capable
- real zip `report bundle export --zip` is not implemented and fails closed

Phase 3.26 final smoke confirmed the no-write boundary for directory, zip, and JSON dry-run paths. Phase 3.29 later added guarded directory-only real export; dry-run remains no-write.

Current inventory boundary:

- commands: about `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable commands: `report export`, `report bundle export`
- `report bundle export --dry-run` is read-only

Real bundle export scope:

- real bundle directory export is implemented
- output root: `reports/python_tooling/bundles/<bundle_id>/`
- zip export remains deferred
- `--zip` remains unsupported / fail-closed until a separate contract and smoke validation exist
- current `writes_files_count` is `2`
- write-capable commands are `report export` and `report bundle export`

## Report Export Boundary

`report export` and `report bundle export` are currently the write-capable Python commands. Daily status checks should still begin with:

```powershell
python -m armedforces_tool status overview
```

Before real export, use one of the safer read/check paths:

```powershell
python -m armedforces_tool report preview --type full-status
python -m armedforces_tool report export --dry-run --type full-status --out reports/python_tooling/full_status.md
```

Real export writes exactly one `.md` file only under `reports/python_tooling/` or `docs/reports/python_tooling/`. Existing targets are not overwritten unless `--force` is supplied. Protected paths remain rejected even with `--force`.

See [Report Export Operator Guide](report_export_operator_guide.md) for the full boundary, cleanup rules, and smoke procedure.

### `commands`

Discover Python sidecar commands and their safety properties. This is not a replacement for argparse `--help`; it is an operator index.

Representative commands:

```powershell
python -m armedforces_tool commands list
python -m armedforces_tool commands quickstart
python -m armedforces_tool commands show --command "status overview"
```

## Safety Boundary

The current Python tooling layer is mostly read-only, with explicitly guarded report write commands.

It must not:

- run CE
- write local config
- write logs, registry, baselines, session files, or intake journals
- replace the guarded PowerShell workflow
- mutate runtime state
- perform guarded writes or restores
- generate write or restore actions from transaction history
- write Markdown report files from `report preview`
- write report files outside `reports/python_tooling/` or `docs/reports/python_tooling/`

Write-capable behavior is currently limited to `report export` and `report bundle export`. Neither command runs CE or mutates runtime/config/log/session/intake/baseline/registry state. `report export` writes approved `.md` reports only. `report bundle export` writes approved directory bundles only and does not support zip output or overwrite.

Future Python write-capable commands must follow the [Python Write-Capable Feature Policy](architecture/python_write_capable_feature_policy.md).

## Known Acceptable WARNs

The following parity WARN results are currently acceptable and are not Python failures:

- `status case-intake-parity` may WARN because PowerShell does not expose `active_session_detected`.
- `baseline current-parity` may WARN because PowerShell does not expose profile / unique count.
- `baseline compare-parity` may WARN because PowerShell does not expose coverage count fields.

Other WARN or FAIL results should be reviewed before checkpointing.

## Checkpoint Tags

- `python-tooling-readonly-analysis-checkpoint-20260615`: Python read-only log, case summary, case library, stable-cases, and sample planning analysis.
- `python-safety-status-checkpoint-20260615`: Python safety status, plan, and execution-status sidecar checks.
- `python-doctor-safety-checkpoint-20260615`: Python aggregate safety doctor.
- `python-workflow-status-checkpoint-20260615`: Python diagnostic and case-intake status views.
- `python-baseline-status-checkpoint-20260615`: Python baseline list/current/compare views.
- `python-status-overview-checkpoint-20260615`: Python consolidated status overview.
- `python-command-inventory-checkpoint-20260615`: Python command inventory, quickstart, and descriptor index.
- `python-report-export-guarded-checkpoint-20260616`: Guarded real `report export` writes under approved report roots only.
- `python-report-manifest-real-write-checkpoint-20260616`: Controlled `report export --record-manifest` writes under `reports/python_tooling/` only.

## Recommended Smoke Commands

```powershell
cd D:\armedforces.io-v2
$env:PYTHONPATH="D:\armedforces.io-v2\src"

python -m armedforces_tool status overview
python -m armedforces_tool commands quickstart
python -m armedforces_tool safety doctor
python -m armedforces_tool baseline compare
python -m armedforces_tool case summary --latest 20 --profile full
python -m armedforces_tool report preview --type full-status

python -m armedforces_tool report export --dry-run --type status-overview --output-dir reports/python_tooling
python -m armedforces_tool report export --dry-run --type full-status --out reports/python_tooling/full_status_test.md
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md

.venv\Scripts\python.exe -m pytest --basetemp .tmp_pytest
Remove-Item -Recurse -Force .tmp_pytest -ErrorAction SilentlyContinue

git status --short
```

`report export --dry-run` validates export paths and prints metadata only. It does not create directories and does not create `.md` files. Real `report export` creates the approved parent directory if needed and writes exactly one `.md` file under `reports/python_tooling/` or `docs/reports/python_tooling/`.

With `--record-manifest`, real export is limited to `reports/python_tooling/` and appends exactly one JSONL row to `reports/python_tooling/manifest.jsonl` after the report file is written and hashed. `docs/reports/python_tooling/` remains valid for ordinary report export, but not for manifest-recorded export in the first implementation.

## Report Manifest Current Workflow

### Dry-Run Workflow

Use dry-run first:

```powershell
python -m armedforces_tool report export --dry-run --type full-status --out reports/python_tooling/full_status.md --record-manifest
```

Expected behavior:

- no report file is written
- no manifest file is written
- no report directory is created solely by dry-run
- output shows `would_write_report=true`
- output shows `would_write_manifest=true`
- planned manifest path is `reports/python_tooling/manifest.jsonl`

### Real Export Workflow

After reviewing the dry-run result, real manifest-recorded export is:

```powershell
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md --record-manifest
```

Expected behavior:

- the report is written under `reports/python_tooling/`
- one JSONL row is appended to `reports/python_tooling/manifest.jsonl`
- `report export` is one of the guarded write-capable Python commands
- no CE, runtime, log, config, session, intake, baseline, or registry file is modified

Verify the result after writing:

```powershell
python -m armedforces_tool report manifest verify
python -m armedforces_tool report manifest list
```

`report manifest preview`, `report manifest list`, and `report manifest verify` remain read-only. They must not modify manifest files and must not write runtime files.

### Smoke Cleanup Rules

For smoke-created report/manifest files:

- remove smoke-created report files after validation
- remove smoke-created `manifest.jsonl` only if it was created by that smoke
- never delete pre-existing user reports
- never delete a pre-existing user manifest
- never delete `reports/python_tooling/` just because smoke validation completed

### Unsupported First-Version Boundary

This first manifest-recorded export boundary does not support:

```text
docs/reports/python_tooling/*.md + --record-manifest
```

That combination must fail closed with `MANIFEST_OUTPUT_ROOT_UNSUPPORTED` or an equivalent rejection. No `docs/reports/python_tooling/manifest.jsonl` should be written.

Current command inventory boundary:

- total commands: about `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable Python commands: `report export`, `report bundle export`

## Current Stable State

Current expected stable results:

- `status overview = SAFE`
- `safety doctor = SAFE`
- `baseline compare = BASELINE_COMPARE_PASS`
- `case summary = COVERAGE_OK`
- command inventory includes read-only analysis commands plus write-capable `report export` and `report bundle export` commands
- pytest covers the current Python sidecar command set

## Phase 3 Current State

Phase 3 currently includes:

- registry read-only view:
  - `registry summary`
  - `registry list`
  - `registry show`
  - checkpoint: `python-registry-status-checkpoint-20260615`
- transaction history read-only view:
  - `transaction summary`
  - `transaction list`
  - `transaction show`
  - write/restore history is visible but not executable
  - checkpoint: `python-transaction-history-checkpoint-20260615`
- report preview:
  - `report preview`
  - stdout-only
  - `full-status` defaults to CLI-friendly text
  - Markdown output requires `--format markdown`
  - checkpoints: `python-report-preview-checkpoint-20260615`, `python-report-preview-cli-checkpoint-20260615`
- report manifest read-only views:
  - `report manifest preview`
  - `report manifest list`
  - `report manifest verify`
  - no manifest writes
  - JSONL verify support only; JSON and Markdown indexes remain planned
- report manifest write contract:
  - `--record-manifest`
  - first approved manifest location: `reports/python_tooling/manifest.jsonl`
  - append-only JSONL planned
  - real manifest recording is implemented only through `report export`
- report manifest dry-run planning:
  - `report export --dry-run --record-manifest`
  - no report write
  - no manifest write
- report manifest real recording:
  - `report export --record-manifest`
  - writes the report under `reports/python_tooling/`
  - appends `reports/python_tooling/manifest.jsonl`
  - `docs/reports/python_tooling/` with `--record-manifest` fails closed
  - final boundary smoke passed with smoke-created report/manifest cleaned
- report bundle read-only views:
  - `report bundle preview`
  - `report bundle verify`
  - reads only `reports/python_tooling/manifest.jsonl` by default
  - no bundle directory, zip, copied report, bundle manifest, or index writes
- report bundle export:
  - `report bundle export --dry-run` remains no-write
  - directory-only `report bundle export --out reports/python_tooling/bundles/<bundle_id>/` is implemented
  - zip export remains deferred
- report export dry-run:
  - `report export --dry-run`
  - no-write path safety preview
  - checkpoint: `python-report-export-dry-run-checkpoint-20260615`
- guarded report export:
  - first write-capable Python command
  - writes only approved `.md` reports under `reports/python_tooling/` or `docs/reports/python_tooling/`
  - default no overwrite
  - `--force` applies only under approved roots
  - checkpoints: `python-report-export-guarded-checkpoint-20260616`, `python-report-export-boundary-checkpoint-20260616`

Current command inventory state:

- total commands = about `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable commands = `report export`, `report bundle export`
- `report export --dry-run` remains read-only
- `report bundle export --dry-run` remains read-only

Safe report export flow:

```powershell
python -m armedforces_tool report preview --type full-status
python -m armedforces_tool report export --dry-run --type full-status --out reports/python_tooling/full_status.md
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md
```

Dry-run first is recommended. Default behavior does not overwrite; use `--force` only intentionally. Never export outside approved roots.

## Next Migration Candidates

Possible next migration directions:

- report manifest repair / cleanup planning
- report manifest index rendering planning
- report bundle format planning
- thin PowerShell read-only wrapper pilot
- native backend contract planning
- write-capable feature policy template

Future write-capable Python commands must use the same pattern as `report export`: explicit policy, contract, dry-run where applicable, path/state protections, validation smoke, cleanup rules, and checkpoint.

Still active non-goals:

- no CE automation
- no guarded write / restore migration
- no Python writes to log, config, session, intake, baseline, or registry files
- no PowerShell workflow mutation replacement
- no Lua/runtime changes
- no algorithm rewrite

Previous candidate tracks completed in Phase 3:

- Python read-only registry view
- Python read-only transaction history view
- report preview / export boundary

Do not migrate guarded write / restore yet.

Do not automate CE yet.

Do not mix write-capable workflows into the current read-only Python layer.

## Git Hygiene

Do not commit:

- `log/`
- `log/*.jsonl`
- `log/baselines/*.md`
- `src/run_case_config.local.lua`
- `src/run_case_config.local.lua.bak`
- `docs/codex_tasks/`

Python smoke checks should leave the working tree clean except for intentional documentation or source changes.
