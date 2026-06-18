# Python Tooling Candidate B Isolated Manifest Path Support Contract - 2026-06-18

## Summary

Phase 6.4B added a docs-only contract for future isolated manifest path support.

## Recorded State

- Phase 6.3B Candidate B validation smoke: STOP
- STOP reason: isolated Candidate B manifest path is not supported by the existing CLI contract
- Candidate A Phase 6.3A-R2 real report export validation smoke: PASS
- wrapper boundary: read-only
- expected command inventory: `writes_files_count = 2`, `runs_ce_count = 0`

## Support Contract

Future implementation should add:

```text
--manifest-out <path>
```

for:

```text
report export --record-manifest
```

`--manifest-out` must be valid only with `--record-manifest`. Without `--record-manifest`, it must fail closed before writing any report or manifest file.

## Safety Notes

- no option was implemented
- no Python source changed
- no wrapper source changed
- no tests changed
- no report export command was executed
- no dry-run command was executed
- no `--record-manifest` command was executed
- no runtime report/manifest/bundle was written
- no CE was run
- no tag was created
