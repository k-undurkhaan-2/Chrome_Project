# Python tooling force / overwrite unsupported wording contract - 20260620

## Classification

- docs-only contract
- no code changed
- no behavior changed
- no tag created

## Summary

Phase 8.1-contract defines the future force / overwrite unsupported rejection wording slice for write-capable Python tooling.

The contract is recorded in:

```text
docs/architecture/python_tooling_force_overwrite_unsupported_wording_contract.md
```

It records:

- potential existing output and force surfaces to inspect in a future implementation phase
- preferred tokens `OVERWRITE_UNSUPPORTED`, `FORCE_UNSUPPORTED`, and `NO_FILES_WRITTEN`
- no-write requirements
- pytest-temp-only validation requirements
- stop conditions if no current surface exists

This checkpoint summary does not authorize implementation, manual export, dry-run, `--record-manifest`, bundle export, CE, wrapper export support, overwrite support, force support, zip support, or runtime artifacts.
