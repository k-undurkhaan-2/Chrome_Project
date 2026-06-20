# Python Tooling Overwrite Without Force Wording Implementation - 2026-06-20

## Scope

Phase 8.2 implemented a narrow no-force existing-output rejection wording slice.

Implemented surfaces:

- `report export --out <existing-file>` without `--force`
- `report bundle export --out <existing-directory>`
- `report bundle export --out <existing-file>`

Inspected and skipped:

- `report export --record-manifest --manifest-out <existing-file>` remains append/preflight manifest semantics, not overwrite rejection.

## Stable Tokens

No-force existing-output rejection now emits:

- `OVERWRITE_UNSUPPORTED`
- `NO_FILES_WRITTEN`

The output must not use `FORCE_UNSUPPORTED` for `report export --force`, because `report export --force` remains a supported approved-target overwrite success path.

## Preserved Behavior

- Candidate A report export success output unchanged
- Candidate B manifest success output unchanged
- Candidate C bundle success output unchanged
- Phase 7.2A invalid option rejection unchanged
- Phase 7.2B source input rejection unchanged
- Phase 7.2C zip unsupported rejection unchanged
- dry-run behavior unchanged
- JSON / `to_dict()` schema unchanged
- wrapper remains read-only
- `writes_files_count = 2`
- `runs_ce_count = 0`

## Validation Policy

Validation must use pytest temp paths only. Do not manually run real report export, `--record-manifest`, bundle export, or dry-run commands for this slice.

## Recommended Next Step

Run a Phase 8.2 boundary smoke to confirm wording tokens, no-write behavior, command inventory stability, wrapper read-only behavior, and absence of runtime artifacts.
