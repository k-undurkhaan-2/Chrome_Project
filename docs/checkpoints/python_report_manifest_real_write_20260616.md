# Python Report Manifest Real Write - 2026-06-16

## Purpose

Record the Phase 3.16 boundary for controlled Python report manifest writing in `D:\armedforces.io-v2`.

## Included

- `report export --record-manifest` real write path.
- Report output restricted to `reports/python_tooling/*.md`.
- Manifest output restricted to `reports/python_tooling/manifest.jsonl`.
- Append-only JSONL manifest records.
- Post-write file size and SHA256 recording.
- Existing manifest preflight for parse errors, unsupported schema, and duplicate `report_id`.
- `report manifest preview`, `report manifest list`, and `report manifest verify` remain read-only.

## Excluded

- No manifest under `docs/reports/python_tooling/`.
- No mutable JSON manifest.
- No manifest repair or cleanup command.
- No report index rendering.
- No writes to `log/`, registry, baseline, session, intake, or local config files.
- No CE automation.
- No PowerShell or Lua changes.

## Safety State

- `report export` remains the only write-capable Python command.
- `writes_files_count` remains `1`.
- `runs_ce_count` remains `0`.
- Dry-run with `--record-manifest` remains no-write.
- Real manifest recording requires an approved `reports/python_tooling/*.md` target.
- Existing report targets still require `--force` to overwrite.

## Smoke Cleanup Requirement

Smoke validation may create:

- `reports/python_tooling/full_status_manifest_smoke.md`
- `reports/python_tooling/manifest.jsonl`

These files must be deleted before final reporting if they were created by the smoke check. Pre-existing user report or manifest files must not be deleted.

## Suggested Validation

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"

.venv\Scripts\python.exe -m armedforces_tool report export --dry-run --type full-status --out reports/python_tooling/full_status_manifest_dry_run.md --record-manifest
.venv\Scripts\python.exe -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status_manifest_smoke.md --record-manifest
.venv\Scripts\python.exe -m armedforces_tool report manifest verify
.venv\Scripts\python.exe -m armedforces_tool report manifest list
.venv\Scripts\python.exe -m pytest --basetemp .tmp_pytest
```

## Next Candidates

- Manifest repair / cleanup planning.
- Report index rendering planning.
- Optional manifest support for `docs/reports/python_tooling/` after a separate contract update.
