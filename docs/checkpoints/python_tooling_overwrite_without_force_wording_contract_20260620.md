# Python tooling overwrite without force wording contract - 20260620

## Classification

- docs-only contract
- no code changed
- no behavior changed
- no tag created

## Summary

Phase 8.2-contract defines the future no-force existing-output rejection wording slice.

The contract is recorded in:

```text
docs/architecture/python_tooling_overwrite_without_force_wording_contract.md
```

It records:

- `report export --force` is an explicit non-target and remains supported behavior
- future target cases are no-force existing-output rejections
- intended tokens are `OVERWRITE_UNSUPPORTED` and `NO_FILES_WRITTEN`
- `FORCE_UNSUPPORTED` is reserved only for a true unsupported-force surface
- future tests must use pytest temp paths and verify existing files/directories remain unchanged

No tag is created by this contract phase.
