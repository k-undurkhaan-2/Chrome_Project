# Report Export Operator Guide

## Purpose

`report export` is currently the only write-capable Python tooling command.

It is intentionally narrow:

- writes only Markdown report files
- writes only under approved report output roots
- does not run CE
- does not mutate runtime state
- does not write config, log, session, intake, baseline, or registry files
- does not participate in guarded write or restore workflows

Use `report preview` or `report export --dry-run` before a real export when checking a report target.

## Current Commands

```powershell
python -m armedforces_tool report preview --type full-status
python -m armedforces_tool report export --dry-run --type full-status --out reports/python_tooling/full_status.md
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.md --force
```

Command behavior:

- `report preview` is stdout-only.
- `report export --dry-run` validates the path and content metadata without writing files or creating directories.
- `report export` writes exactly one `.md` report file after path validation.
- `--force` only overwrites approved report `.md` files under approved roots.

## Approved Output Roots

Only these roots are allowed:

```text
reports/python_tooling/
docs/reports/python_tooling/
```

Report export must not write under:

- `log/`
- `src/`
- `tests/`
- `docs/codex_tasks/`
- `.git/`
- `.codex/`
- `src/run_case_config.local.lua`
- `src/run_case_config.local.lua.bak`
- `log/case_registry.jsonl`
- `log/case_intake.local.jsonl`
- `log/active_test_session.local.json`
- `log/test_session_history.local.jsonl`
- `log/baselines/*.md`

These paths remain forbidden even when `--force` is supplied.

## Safety Guarantees

Guarded report export guarantees:

- no CE run
- no PowerShell, Lua, or runtime mutation
- no log, config, session, intake, baseline, or registry writes
- path traversal is rejected
- non-`.md` output is rejected
- protected paths are rejected
- default behavior does not overwrite
- `--force` still cannot write protected paths

## Validation Cleanup Rule

Smoke or validation may temporarily create report files under approved roots. The cleanup rule is strict:

- record files created during the current validation
- delete only files created during the current validation
- never delete report files that existed before the smoke check
- never delete pre-existing `reports/` or `docs/reports/` directories

If validation creates an empty approved subdirectory that did not exist before the check, remove it only when it is empty and clearly created by that validation.

## Recommended Guarded Smoke

```powershell
$env:PYTHONPATH="D:\armedforces.io-v2\src"

git status --short

python -m armedforces_tool report export --dry-run --type full-status --out reports/python_tooling/full_status_dry_run.md
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status_smoke.md
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status_smoke.md
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status_smoke.md --force

python -m armedforces_tool report export --type full-status --out ../full_status.md
python -m armedforces_tool report export --type full-status --out log/full_status.md
python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status.txt

Remove-Item -Force reports/python_tooling/full_status_smoke.md -ErrorAction SilentlyContinue

python -m armedforces_tool status overview
python -m armedforces_tool commands list --category report
git status --short
```

Expected results:

- dry-run reports `REPORT_EXPORT_DRY_RUN_OK` and writes nothing
- approved real export reports `REPORT_EXPORT_OK`
- overwrite without `--force` reports `REPORT_EXPORT_OVERWRITE_REJECTED`
- overwrite with `--force` succeeds only under an approved root
- bad paths are rejected
- status overview remains `SAFE`
- report command inventory shows exactly one write-capable command: `report export`

## Checkpoint

Checkpoint tag:

```text
python-report-export-guarded-checkpoint-20260616
```

The checkpoint means:

- real report export is stable
- approved output roots are enforced
- dry-run remains no-write
- there is exactly one write-capable Python command
- pytest passed with `114 passed`
- protected files were unchanged

## Next Steps

Possible future directions:

- report export polish
- report bundle format
- report manifest planning

Non-goals:

- do not migrate guarded write or restore
- do not automate CE
- do not allow Python to write log, config, session, intake, baseline, or registry files
