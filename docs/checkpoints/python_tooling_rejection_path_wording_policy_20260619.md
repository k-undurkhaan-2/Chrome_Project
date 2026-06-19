# Python Tooling Rejection-Path Wording Policy - 2026-06-19

## Scope

This checkpoint note records the Phase 7.1 rejection-path wording policy contract.

No functionality was implemented. No Python source, wrapper, tests, Lua source, PowerShell source, runtime files, logs, reports, manifests, bundles, local config, registry, baseline, session, or intake state were changed by this policy phase.

## Policy Added

The policy document is:

```text
docs/architecture/python_tooling_rejection_path_wording_policy.md
```

It defines wording policy for:

- `BAD_PATH`
- protected path rejection
- overwrite / existing output rejection
- `--force` unsupported
- zip unsupported
- invalid option combinations
- missing source inputs
- wrapper unsupported
- `CE_NOT_RUN`
- dry-run no-write output

## Boundaries

The policy keeps these boundaries unchanged:

- `writes_files_count = 2`
- `runs_ce_count = 0`
- wrapper remains read-only
- no CE/runtime mutation
- no zip export
- no `--force`
- no approved-root expansion
- no production/default write authorization

## Next Recommended Phase

Default next phase:

```text
Phase 7.2A-contract - invalid option combination wording contract
```

Priority target:

```text
--manifest-out without --record-manifest
```

## Tag Status

No tag was created for this policy-only checkpoint note.
