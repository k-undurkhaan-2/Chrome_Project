# Python Tooling Path Guard Rejection Wording Implementation

## Scope

Phase 9.1 implemented a narrow human-readable wording improvement for existing approved-root and path-guard rejection surfaces.

Implemented surfaces:

- `report export --out <outside-approved-root>`
- `report export --record-manifest --manifest-out <outside-approved-root>`
- `report bundle export --out <outside-approved-root>`
- `report bundle export --source-report <guard-rejected-path>` where current planner semantics return `BAD_PATH`

## Stable Tokens

- `PATH_GUARD_REJECTED`
- `OUTSIDE_APPROVED_ROOT` where accurate
- `NO_FILES_WRITTEN`

Existing `BAD_PATH` and `PATH_REJECTED` result fields remain compatible.

## Boundaries

- no approved-root expansion
- no path guard weakening
- no new write destination
- no new command or option
- no wrapper change
- no CE/runtime behavior
- no manual real export validation

## Validation Model

Validation uses pytest temp paths and read-only status/inventory checks. It must not create runtime report, manifest, bundle, log, registry, baseline, session, intake, or local config artifacts.

## Tag Policy

No tag is created by this implementation note. A checkpoint tag requires a later boundary smoke.
