# Python Tooling Rejection Message Consistency Audit

## Purpose

This document audits rejection-message and token consistency after Phases 7-11. It is docs-only and audit-only; it does not implement fixes, change behavior, add commands/options, or authorize export/write execution.

## Baseline

- latest checkpoint tag: `python-tooling-invalid-output-extension-rejection-checkpoint-20260621`
- current overview doc: `docs/architecture/python_tooling_checkpoint_status_overview.md`
- command count: approximately 49
- `writes_files_count = 2`
- `runs_ce_count = 0`
- wrapper remains read-only
- write-capable commands remain unchanged:
  - `report export`
  - `report bundle export`
- Python tooling does not run CE.

## Audit method

The audit used read-only inspection only:

- source/test/docs token grep across `src`, `tests`, and `docs`
- source/test token grep across `src` and `tests` to reduce docs noise
- command descriptor inspection for `report export` and `report bundle export`
- wrapper status/inventory checks
- runtime artifact checks for report, manifest, bundle, validation, docs-report, and log paths
- no manual report export, dry-run, `--record-manifest`, bundle export, write, restore, or CE execution

Pytest was not run for this docs-only audit. Existing test references were inspected and record the relevant success-token exclusion and domain-boundary assertions.

## Token family table

| Domain | Primary tokens | No-write token | Expected scope | Current audit status |
|---|---|---|---|---|
| invalid option combination | `INVALID_OPTION_COMBINATION` | `NO_FILES_WRITTEN` | invalid command-option combinations such as `--manifest-out` without `--record-manifest` | OK - present in source/tests and scoped to option-combination rejection |
| source missing/invalid | `SOURCE_MISSING`, `SOURCE_INVALID` | `NO_FILES_WRITTEN` | missing or invalid bundle source report/manifest inputs | OK - present in source/tests and scoped to source input rejection |
| zip unsupported | `ZIP_UNSUPPORTED`, `BUNDLE_ZIP_EXPORT_NOT_IMPLEMENTED` | `NO_FILES_WRITTEN` | zip/archive bundle request rejection | OK - compatibility status preserved and zip remains unsupported |
| no-force overwrite | `OVERWRITE_UNSUPPORTED` | `NO_FILES_WRITTEN` | existing output without authorized overwrite | OK - scoped to no-force overwrite; `report export --force` remains supported |
| path guard | `PATH_GUARD_REJECTED`, `OUTSIDE_APPROVED_ROOT`, `BAD_PATH`, `PATH_REJECTED` | `NO_FILES_WRITTEN` | protected path, traversal, and outside-approved-root rejection | OK - compatibility tokens preserved and guard wording remains path-specific |
| default manifest parse | `INVALID_MANIFEST`, `MANIFEST_PARSE_FAILED`, `MANIFEST_INVALID` | `NO_FILES_WRITTEN` | default manifest parse failure or invalid default manifest records | OK - isolated `--source-manifest` content remains path/file-only and is not mixed into this domain |
| invalid output extension/type | `OUTPUT_EXTENSION_INVALID`, `OUTPUT_TYPE_UNSUPPORTED` | `NO_FILES_WRITTEN` | unsupported report/manifest extension and unsupported bundle output type | OK - scoped to invalid output extension/type; zip remains separate |

## Adjacent-domain separation

- `PATH_GUARD_REJECTED` / `OUTSIDE_APPROVED_ROOT` / `BAD_PATH` / `PATH_REJECTED` remain path guard only.
- `OVERWRITE_UNSUPPORTED` remains no-force overwrite only.
- `ZIP_UNSUPPORTED` remains zip/archive unsupported only.
- `SOURCE_MISSING` / `SOURCE_INVALID` remain source path/input only.
- `MANIFEST_PARSE_FAILED` / `MANIFEST_INVALID` / `INVALID_MANIFEST` remain default manifest parse/invalid only.
- `OUTPUT_EXTENSION_INVALID` / `OUTPUT_TYPE_UNSUPPORTED` remain output extension/type only.
- `FORCE_UNSUPPORTED`, where present, is used as a reserved/forbidden token in tests and must not be used for current supported `report export --force`.

## Success-token exclusion

Rejection output must not include:

```text
REPORT_EXPORT_OK
MANIFEST_RECORDED
WRITE_COMPLETE
BUNDLE_EXPORT_COMPLETE
BUNDLE_EXPORT_OK
SOURCE_UNCHANGED
```

The audit found these success tokens in success helpers, success tests, and explicit forbidden-token assertions for rejection paths. No source/test evidence was found requiring an immediate fix in this audit-only phase.

## NO_FILES_WRITTEN policy

Current expected policy:

- rejection output should include `NO_FILES_WRITTEN` when the rejection is a fail-closed no-write path and compatible with the current output style
- success outputs must not use `NO_FILES_WRITTEN`
- dry-run success/preview paths remain distinct from rejection no-write paths
- no current domain was identified as intentionally omitting `NO_FILES_WRITTEN` where the Phase 7-11 policy expects it

## Compatibility and schema

- JSON / `to_dict()` compatibility must remain unchanged.
- Existing machine-readable statuses remain preserved where compatibility matters:
  - `BUNDLE_ZIP_EXPORT_NOT_IMPLEMENTED`
  - `INVALID_MANIFEST`
  - `BAD_PATH` / `PATH_REJECTED` where applicable
- Human-readable output may add explanatory tokens, but must not break existing status compatibility or move tokens across adjacent domains.

## Runtime artifact safety

Audit/docs phases must not create:

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

Runtime artifact inspection during this audit found no report, manifest, bundle, validation, or docs-report artifacts.

## Findings

| Finding | Severity | Evidence | Recommended follow-up |
|---|---|---|---|
| Rejection token families remain present and scoped | OK | Token grep across `src`, `tests`, and `docs`; source/test count review | No fix required |
| Success tokens remain success-scoped or explicitly forbidden in rejection tests | OK | Source/test grep shows success helpers and rejection-path negative assertions | No fix required |
| `NO_FILES_WRITTEN` policy remains represented across fail-closed rejection tests/helpers | OK | Source/test grep shows `NO_FILES_WRITTEN` in output helpers and rejection tests | No fix required |
| Adjacent domains remain separated | OK | Token review keeps zip, source input, overwrite, path guard, manifest parse, and output-type domains distinct | No fix required |
| Isolated `--source-manifest` content parsing remains deferred | BLOCKED_BY_PRODUCT_DECISION | Prior Phase 10 policy and current overview record path/file-only behavior | Separate product/behavior decision required before implementation |

No low-risk implementation fix candidate is required from this audit.

## Recommended next phase

Recommended next phase:

```text
Phase 12.3 - report bundle export operator guide hardening
```

Rationale: the rejection-message audit did not identify a narrow fix requirement. The next low-risk step is operator-facing documentation hardening for bundle export, dry-run, source input, manifest, and validation boundaries.

Alternative:

```text
Phase 12.3 - Python tooling checkpoint wrap-up docs
```

Use the wrap-up option if the goal is to pause behavior-adjacent work after the audit.

## Operator Documentation Follow-Up

After this audit, Phase 12.3 selected report bundle export operator guide hardening to clarify how bundle-related rejection domains appear to operators. That docs phase does not imply token-domain changes, source behavior changes, command surface changes, or write-surface expansion.
