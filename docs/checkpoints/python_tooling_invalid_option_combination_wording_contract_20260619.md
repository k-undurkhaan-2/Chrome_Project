# Python Tooling Invalid Option Combination Wording Contract - 2026-06-19

## Scope

This checkpoint note records the Phase 7.2A contract for invalid option combination wording.

No functionality was implemented. No Python source, wrapper, tests, Lua source, PowerShell source, runtime files, logs, reports, manifests, bundles, local config, registry, baseline, session, or intake state were changed by this contract phase.

## Target Rejection Path

The contract covers this future rejection-path wording slice:

```text
report export --out <report-path> --manifest-out <manifest-path>
```

without:

```text
--record-manifest
```

## Future Expected Behavior

Future implementation should fail closed before any write and should not create:

- report output
- custom manifest output
- default `reports/python_tooling/manifest.jsonl`
- runtime report, manifest, bundle, log, config, registry, baseline, session, or intake files

## Token / Wording Target

Preferred token:

```text
INVALID_OPTION_COMBINATION
```

Preferred no-write companion token:

```text
NO_FILES_WRITTEN
```

The future output must explain that `--manifest-out` requires `--record-manifest`.

## Next Recommended Phase

Recommended next phase:

```text
Phase 7.2A - invalid option combination wording implementation
```

## Tag Status

No tag was created for this contract-only checkpoint note.
