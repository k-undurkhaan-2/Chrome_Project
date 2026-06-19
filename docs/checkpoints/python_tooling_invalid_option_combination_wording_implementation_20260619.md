# Python Tooling Invalid Option Combination Wording Implementation - 2026-06-19

## Scope

This checkpoint note records the Phase 7.2A implementation slice for invalid option combination wording.

Target rejection path:

```text
report export --out <report-path> --manifest-out <manifest-path>
```

without:

```text
--record-manifest
```

## Implemented Wording

The human-readable rejection output includes:

- `INVALID_OPTION_COMBINATION`
- `NO_FILES_WRITTEN`
- `--manifest-out`
- `--record-manifest`
- `REPORT_EXPORT_REJECTED`

The rejection output must not include real-write success tokens:

- `REPORT_EXPORT_OK`
- `WRITE_COMPLETE`
- `MANIFEST_RECORDED`
- `BUNDLE_EXPORT_COMPLETE`
- `BUNDLE_EXPORT_OK`

## Boundary

This implementation does not add commands or options. It does not change the wrapper, Lua runtime, PowerShell source, CE behavior, path guards, approved roots, Candidate A/B/C success behavior, dry-run behavior, or JSON schema.

## Tag Status

No tag was created for this implementation checkpoint note.
