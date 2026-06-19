# Python Tooling Missing Source Input Wording Contract - 2026-06-19

## Scope

This checkpoint note records the Phase 7.2B contract for missing or invalid source input wording.

No functionality was implemented. No Python source, wrapper, tests, Lua source, PowerShell source, runtime files, logs, reports, manifests, bundles, local config, registry, baseline, session, or intake state were changed by this contract phase.

## Target Rejection Paths

The contract covers future fail-closed wording for:

- `report bundle export --source-report <missing-report> --out <bundle-dir>`
- `report bundle export --source-report <directory> --out <bundle-dir>`
- `report bundle export --source-report <report> --source-manifest <missing-manifest> --out <bundle-dir>`
- `report bundle export --source-report <report> --source-manifest <directory> --out <bundle-dir>`
- `report bundle export --source-manifest <manifest> --out <bundle-dir>` without `--source-report`

## Future Expected Behavior

Future implementation should fail closed before any bundle artifact is written and should not create:

- bundle directory
- `bundle_manifest.json`
- `index.md`
- copied report
- runtime report, manifest, bundle, log, config, registry, baseline, session, or intake files

## Token / Wording Target

Preferred tokens:

```text
SOURCE_MISSING
SOURCE_INVALID
INVALID_OPTION_COMBINATION
NO_FILES_WRITTEN
```

`SOURCE_UNCHANGED` is reserved for successful bundle export output and must not be used as a failure token.

## Next Recommended Phase

Recommended next phase:

```text
Phase 7.2B - missing source input wording implementation
```

## Tag Status

No tag was created for this contract-only checkpoint note.
