# Python tooling invalid output extension wording contract - 20260621

## Classification

- contract checkpoint
- docs-only
- no implementation
- no tag created

## Summary

Phase 11.1 defines a future rejection-path wording contract for invalid output extension / unsupported output type failures.

The contract is recorded at:

```text
docs/architecture/python_tooling_invalid_output_extension_wording_contract.md
```

## Target Area

Potential future surfaces:

- `report export --out <unsupported-extension>`
- `report export --out <directory-path>`
- `report export --record-manifest --manifest-out <unsupported-extension>`
- `report bundle export --out <file-like-or-unsupported-output-form>`
- `report bundle export --out <path.zip>` only if current semantics are not already `ZIP_UNSUPPORTED`

## Token Policy

Preferred future tokens:

```text
OUTPUT_EXTENSION_INVALID
OUTPUT_TYPE_UNSUPPORTED
NO_FILES_WRITTEN
```

The implementation phase must preserve existing machine-readable status where current code already has one.

## Boundary

The contract does not:

- implement behavior
- enable new output formats
- add commands or options
- weaken path guards
- expand approved roots
- add write destinations
- change zip unsupported behavior
- change no-force overwrite behavior
- change default manifest parse behavior

## Next Phase

Next recommended phase is conditional implementation after source/help/test inspection. If no current invalid output extension/type rejection surface exists, implementation must STOP and report the missing surface.
