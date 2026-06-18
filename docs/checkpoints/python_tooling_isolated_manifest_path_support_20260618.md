# Python Tooling Isolated Manifest Path Support - 2026-06-18

## Summary

Phase 6.5B implemented isolated manifest path support for report export manifest recording.

## Implemented Option

```text
--manifest-out <path>
```

The option is valid only with:

```text
--record-manifest
```

## Behavior

- `report export` without `--record-manifest` remains unchanged.
- `report export --record-manifest` without `--manifest-out` remains backward-compatible and uses `reports/python_tooling/manifest.jsonl`.
- `report export --record-manifest --manifest-out <path>` records the manifest entry to the approved selected path.
- `--manifest-out` without `--record-manifest` fails closed before writing any report or manifest.
- explicit `--manifest-out reports/python_tooling/manifest.jsonl` is rejected to prevent Candidate B validation from targeting the default manifest.

## Safety Notes

- no new command was added
- no wrapper support was added
- no Lua or PowerShell source changed
- no CE was run
- no manual real report export was run
- no manual `--record-manifest` export was run
- no manual dry-run export was run
- no bundle export was run
- no runtime report/manifest/bundle was written
- no tag was created

## Next Step

Proceed to Phase 6.6B isolated manifest path support boundary smoke before rerunning Candidate B real validation.
