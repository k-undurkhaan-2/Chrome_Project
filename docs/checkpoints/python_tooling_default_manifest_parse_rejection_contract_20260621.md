# Python Tooling Default Manifest Parse Rejection Contract - 20260621

## Summary

Phase 10.3 defines a docs-only contract for future wording around the existing default manifest parse / invalid manifest rejection surface.

Target surface:

```text
_analyze_existing_manifest()
_parse_manifest_line()
INVALID_MANIFEST
```

## Result

- contract created
- no code changed
- no behavior changed
- no tests changed
- no wrapper change
- no CE run
- no report export, dry-run, `--record-manifest`, bundle export, write, or restore run
- no runtime report, manifest, bundle, log, config, or state written
- no tag created

## Scope

This contract is not isolated `--source-manifest` content parsing.

Isolated `--source-manifest` remains path/file validated and content-unparsed unless a future isolated source-manifest validation surface contract authorizes a behavior change.

## Next Step

Recommended next phase:

```text
Phase 10.3 - default manifest parse rejection wording implementation
```

Implementation must first inspect current source/help/tests and stop if no safe default manifest parse rejection surface can be tested.
