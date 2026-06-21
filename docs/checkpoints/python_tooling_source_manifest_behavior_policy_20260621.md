# Python Tooling Source Manifest Behavior Policy - 20260621

## Summary

Phase 10.2 implementation stopped because no current isolated `--source-manifest` parse/invalid rejection surface exists.

Current isolated behavior:

- `--source-manifest` is path/file validated
- content is not parsed
- missing path remains `SOURCE_MISSING`
- non-file path remains `SOURCE_INVALID`
- guard-rejected path remains `BAD_PATH` / `PATH_GUARD_REJECTED` / `PATH_REJECTED`

## Result

- behavior policy created
- Phase 10.1 contract corrected
- no code changed
- no behavior changed
- no tests changed
- no wrapper change
- no CE run
- no report export, dry-run, `--record-manifest`, bundle export, write, or restore run
- no runtime report, manifest, bundle, log, config, or state written
- no tag created

## Recommended Next Phase

Preferred:

```text
Phase 10.3-contract - default manifest parse rejection wording contract
```

Alternative:

```text
Phase 10.x-contract - isolated source-manifest validation surface contract
```
