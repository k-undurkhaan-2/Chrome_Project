# Python Tooling Missing Source Input Wording Implementation - 2026-06-20

## Scope

Phase 7.2B implemented fail-closed wording for isolated `report bundle export` source-input rejection paths.

Implemented rejection paths:

- missing `--source-report`
- invalid `--source-report`
- missing `--source-manifest`
- invalid `--source-manifest`
- `--source-manifest` without `--source-report`

## Tokens

Implemented tokens:

- `SOURCE_MISSING`
- `SOURCE_INVALID`
- `INVALID_OPTION_COMBINATION`
- `NO_FILES_WRITTEN`

Failure output must not include success tokens:

- `BUNDLE_EXPORT_COMPLETE`
- `BUNDLE_EXPORT_OK`
- `SOURCE_UNCHANGED`
- `REPORT_EXPORT_OK`
- `WRITE_COMPLETE`
- `MANIFEST_RECORDED`

## Boundaries

The implementation remains fail-closed before writing bundle artifacts. Rejected source-input paths do not create:

- bundle directory
- `bundle_manifest.json`
- `index.md`
- copied report

Unchanged boundaries:

- Candidate A/B/C success output
- dry-run behavior
- JSON field shape
- wrapper read-only behavior
- CE/runtime exclusion
- zip unsupported behavior
- `--force` unsupported behavior
- approved-root and protected-path guards

## Validation Expectation

Validation should use pytest temp paths only. Do not manually run real report export, `--record-manifest`, report bundle export, dry-run export, write, restore, or CE for this implementation slice.

No runtime report, manifest, bundle, log, registry, baseline, session, intake, or local config files are part of this checkpoint.
