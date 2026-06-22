# Python Tooling Checkpoint Status Overview

## Purpose

This document summarizes the current Python tooling checkpoint chain, command surface, frozen boundaries, and next-step recommendations. It is a compact stable-state reference for operators and future implementation tasks.

## Current checkpoint chain

| Checkpoint tag | Area | Status | Notes |
|---|---|---|---|
| `python-tooling-phase3-final-checkpoint-20260616` | Phase 3 Python tooling | Stable | Report preview/export/bundle foundations and read-only sidecar work established. |
| `python-tooling-powershell-wrapper-readonly-checkpoint-20260616` | PowerShell wrapper | Stable | Wrapper remains read-only and does not expose export shortcuts. |
| `python-tooling-output-wording-checkpoint-20260618` | Output wording | Stable | Help text, dry-run wording, and Candidate A/B/C success wording stabilized. |
| `python-tooling-real-write-output-validation-checkpoint-20260619` | Isolated real-write validation | Stable | Candidate A/B/C isolated validations passed; production/default workflows remain separate. |
| `python-tooling-rejection-path-wording-checkpoint-20260620` | Phase 7 rejection wording | Stable | Invalid option, source input, and zip unsupported wording stabilized. |
| `python-tooling-no-force-overwrite-rejection-checkpoint-20260620` | Phase 8 overwrite rejection | Stable | No-force overwrite rejection stabilized; `report export --force` remains supported. |
| `python-tooling-path-guard-rejection-checkpoint-20260620` | Phase 9 path guard rejection | Stable | Path guard wording stabilized without expanding approved roots. |
| `python-tooling-default-manifest-parse-rejection-checkpoint-20260621` | Phase 10 default manifest parse rejection | Stable | Default manifest parse/invalid wording stabilized; isolated `--source-manifest` content remains unparsed. |
| `python-tooling-invalid-output-extension-rejection-checkpoint-20260621` | Phase 11 invalid output extension/type rejection | Stable | Invalid output extension/type wording stabilized; no new output formats enabled. |

## Current command surface

- command count: approximately 49
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable commands:
  - `report export`
  - `report bundle export`
- wrapper is read-only and does not wrap export commands
- CE is not run by Python tooling

| Command family | Writes files | Runs CE | Status |
|---|---:|---:|---|
| `report export` | yes | no | direct Python only, guarded |
| `report bundle export` | yes | no | direct Python only, guarded |
| wrapper status/inventory | no | no | read-only |
| diagnostic/status/inventory commands | no | no | read-only |

## Frozen success behaviors

These areas are stable and should not be changed casually:

- Candidate A report export success output
- Candidate B report export plus manifest success output
- Candidate C directory bundle success output
- bundle dry-run output
- real write validation output
- `report export --force`
- JSON / `to_dict()` compatibility where already covered
- wrapper read-only boundary

## Frozen rejection domains

| Domain | Tokens | Notes |
|---|---|---|
| invalid option combination | `INVALID_OPTION_COMBINATION`, `NO_FILES_WRITTEN` | Phase 7.2A |
| source missing/invalid | `SOURCE_MISSING`, `SOURCE_INVALID`, `NO_FILES_WRITTEN` | Phase 7.2B |
| zip unsupported | `ZIP_UNSUPPORTED`, `NO_FILES_WRITTEN` | Phase 7.2C |
| no-force overwrite | `OVERWRITE_UNSUPPORTED`, `NO_FILES_WRITTEN` | Phase 8 |
| path guard | `PATH_GUARD_REJECTED`, `OUTSIDE_APPROVED_ROOT`, `BAD_PATH`, `PATH_REJECTED`, `NO_FILES_WRITTEN` | Phase 9 |
| default manifest parse | `INVALID_MANIFEST`, `MANIFEST_PARSE_FAILED`, `MANIFEST_INVALID`, `NO_FILES_WRITTEN` | Phase 10 |
| invalid output extension/type | `OUTPUT_EXTENSION_INVALID`, `OUTPUT_TYPE_UNSUPPORTED`, `NO_FILES_WRITTEN` | Phase 11 |

Success tokens should not appear in rejection output:

```text
REPORT_EXPORT_OK
MANIFEST_RECORDED
WRITE_COMPLETE
BUNDLE_EXPORT_COMPLETE
BUNDLE_EXPORT_OK
SOURCE_UNCHANGED
```

## Runtime artifact policy

Docs-only and validation-only phases must not create:

```text
reports/python_tooling/full_status.md
reports/python_tooling/manifest.jsonl
reports/python_tooling/bundles/
reports/python_tooling/validation/
docs/reports/python_tooling
log/config/session/intake/baseline/registry files
src/run_case_config.local.lua
src/run_case_config.local.lua.bak
```

Use pytest temp paths or fixtures only when tests are explicitly allowed by the current task.

## Manual command policy

- docs-only tasks must not run export, dry-run, write, or restore commands
- validation-only smoke tasks must not run manual export, dry-run, write, or restore commands unless explicitly allowed
- implementation tasks may run pytest only, using temp paths
- wrapper must not be used for export because wrapper is read-only
- CE must not be run for Python tooling validation

## Tag policy

- checkpoint tags are created only after final validation smoke PASS
- tags should use:

```text
git tag --no-sign <tag>
```

- no version/release tag is recommended for docs-only or narrow wording slices unless explicitly designated

## Deferred decisions

- isolated `--source-manifest <existing-file>` content parsing remains a product/behavior decision
- zip export remains unsupported
- enabling new output formats is out of scope
- adding new write destinations is out of scope
- wrapper export shortcuts remain out of scope

## Recommended next slices

Phase 12.2 rejection-message consistency audit is documented in `docs/architecture/python_tooling_rejection_message_consistency_audit.md`. It is docs-only/audit-only; any implementation fixes must be separate and must start from a narrow contract.

1. Candidate B can follow after this overview:
   - `Phase 12.2 - rejection-message consistency audit`
2. Candidate C should be deferred until explicit product/behavior decision:
   - isolated source-manifest content parsing contract
3. Candidate D can be handled as a docs-only operator guide hardening slice if needed:
   - report bundle export operator guide hardening

Do not start any of these from this overview document alone.
