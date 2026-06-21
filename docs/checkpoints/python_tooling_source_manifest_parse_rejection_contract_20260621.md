# Python Tooling Source Manifest Parse Rejection Contract - 20260621

## Summary

Phase 10.1 defines a docs-only contract for future source manifest parse / invalid-content rejection wording.

Target command family:

```text
report bundle export --source-manifest <existing but malformed/invalid manifest>
```

## Result

- contract created
- no code changed
- no behavior changed
- no Python command or option added
- no wrapper change
- no tests changed
- no CE run
- no report export, dry-run, `--record-manifest`, bundle export, write, or restore run
- no runtime report, manifest, bundle, log, config, or state written
- no tag created

## Token Scope

Target future tokens:

- `MANIFEST_PARSE_FAILED`
- `MANIFEST_INVALID`
- `NO_FILES_WRITTEN`

Existing domains remain separate:

- `SOURCE_MISSING` / `SOURCE_INVALID` for missing or non-file source paths
- `PATH_GUARD_REJECTED` / `BAD_PATH` / `PATH_REJECTED` for path guard rejection
- `ZIP_UNSUPPORTED` for zip/archive rejection
- `OVERWRITE_UNSUPPORTED` for no-force overwrite rejection

## Next Step

Recommended next phase:

```text
Phase 10.1 - source manifest parse/invalid rejection wording implementation
```

Implementation must first inspect current source/help/tests and stop if no real current source-manifest parse or invalid-content rejection surface exists.
