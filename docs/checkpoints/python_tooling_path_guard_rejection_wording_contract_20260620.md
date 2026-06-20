# Python Tooling Path Guard Rejection Wording Contract - 20260620

## Classification

- contract summary
- docs-only
- no behavior change
- no tag created

## Summary

Phase 9.1 defines a future approved-root / path-guard rejection wording slice.

Target area:

- report output paths outside approved roots
- manifest output paths outside approved roots
- bundle output paths outside approved roots
- guarded source report / source manifest input paths
- path traversal attempts
- reserved/protected path rejection

## Token Policy

Preferred future tokens:

- `PATH_GUARD_REJECTED`
- `OUTSIDE_APPROVED_ROOT`
- `NO_FILES_WRITTEN`

Existing token to inspect before changing:

- `BAD_PATH`

Tokens that should not be repurposed for path-guard rejection unless current semantics truly require it:

- `SOURCE_MISSING`
- `SOURCE_INVALID`
- `OVERWRITE_UNSUPPORTED`
- `ZIP_UNSUPPORTED`
- `INVALID_OPTION_COMBINATION`
- `FORCE_UNSUPPORTED`

## Boundaries

Future implementation must not:

- weaken path guards
- expand approved roots
- add write destinations
- add commands or options
- add wrapper export shortcuts
- run CE
- manually run real export commands for validation
- create production/default report, manifest, or bundle artifacts

## Next Step

Recommended next phase:

```text
Phase 9.1 - approved-root / path-guard rejection wording implementation
```

The implementation must first inspect real current source/help/tests and stop if no current guard rejection surface exists.
