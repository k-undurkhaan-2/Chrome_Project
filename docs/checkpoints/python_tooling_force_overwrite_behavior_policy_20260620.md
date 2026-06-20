# Python tooling force / overwrite behavior policy - 20260620

## Classification

- docs-only behavior policy
- no code changed
- no behavior changed
- no tag created

## Summary

Phase 8.1 implementation stopped correctly because `report export --force` is currently a supported overwrite success path, not an unsupported rejection path.

Current behavior recorded:

- `report export --force` appears in help and command descriptor.
- `report_export.py` writes and overwrites approved targets when `force=True`.
- `test_real_export_existing_target_with_force_overwrites` asserts `REPORT_EXPORT_OK`, `overwritten=True`, and `wrote_file=True`.

Near-term policy:

- preserve `report export --force` current success behavior
- do not use `FORCE_UNSUPPORTED` for `report export --force`
- target future wording at no-force existing-output rejection
- keep wrapper read-only and write surface unchanged

Recommended next phase:

```text
Phase 8.2-contract - overwrite rejection without force wording contract
```

No tag is created by this policy phase.
