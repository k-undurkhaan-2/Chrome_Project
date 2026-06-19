# Python Tooling Candidate C Isolated Bundle Path Support Contract - 2026-06-19

## Summary

Phase 6.4C created the isolated bundle validation path support contract.

## Recorded STOP

Phase 6.3C stopped because the current `report bundle export` CLI/source cannot target isolated Candidate C validation source/input and bundle output paths.

No real bundle export was run, no bundle was created, and no runtime artifacts were written.

## Contract

The support contract is tracked at:

```text
docs/architecture/python_tooling_candidate_c_isolated_bundle_path_support_contract.md
```

It defines future support for:

- `--source-report <path>`
- `--source-manifest <path>`
- allowing `report bundle export --out` to target an isolated bundle directory under the approved report root

## Boundaries

- no implementation in this phase
- no source/test changes
- no real writes
- no report or bundle export
- no CE
- no tag
