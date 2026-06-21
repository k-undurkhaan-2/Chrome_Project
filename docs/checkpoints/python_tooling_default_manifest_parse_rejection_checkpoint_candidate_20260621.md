# Python tooling default manifest parse rejection checkpoint candidate - 20260621

## Classification

- checkpoint candidate
- docs-only
- no tag created

## Summary

Phase 10 default manifest parse rejection wording now has a checkpoint candidate.

Completed inputs:

- Phase 10.2 STOP: isolated `--source-manifest` content is not parsed today.
- Phase 10.2-R1 policy: isolated `--source-manifest` stays path/file validation only.
- Phase 10.3 contract: default manifest parser surface selected.
- Phase 10.4 implementation: `INVALID_MANIFEST` plus `MANIFEST_PARSE_FAILED`, `MANIFEST_INVALID`, and `NO_FILES_WRITTEN`.
- Phase 10.5 boundary smoke: PASS.

## Implemented Surface

The implemented surface is the real existing default manifest parser:

```text
_analyze_existing_manifest()
_parse_manifest_line()
INVALID_MANIFEST
```

Implemented rejection categories:

- malformed default manifest JSON/JSONL
- parseable but invalid default manifest records

## Explicit Non-Target

This checkpoint candidate does not introduce content parsing for:

```text
report bundle export --source-manifest <existing-file>
```

Isolated `--source-manifest` remains path/file validation only:

- missing source manifest remains Phase 7.2B `SOURCE_MISSING`
- non-file source manifest remains Phase 7.2B `SOURCE_INVALID`
- source-manifest without source-report remains Phase 7.2B `INVALID_OPTION_COMBINATION`
- guard-rejected source manifest remains Phase 9.1 `BAD_PATH` / `PATH_GUARD_REJECTED` / `PATH_REJECTED`
- content validation for isolated source manifests requires a separate behavior/surface contract

## Stable Tokens And Compatibility

Stable default-manifest tokens:

```text
INVALID_MANIFEST
MANIFEST_PARSE_FAILED
MANIFEST_INVALID
NO_FILES_WRITTEN
```

Token scope:

- `INVALID_MANIFEST` remains the machine-readable compatibility status.
- `MANIFEST_PARSE_FAILED` applies to malformed default manifest parse failure.
- `MANIFEST_INVALID` applies to parseable but invalid default manifest records.
- `NO_FILES_WRITTEN` indicates rejection before output artifacts were written.
- These tokens are for the default manifest parser surface, not isolated `--source-manifest` content parsing.

Unrelated rejection tokens stay in their own domains:

```text
SOURCE_MISSING
SOURCE_INVALID
PATH_GUARD_REJECTED
BAD_PATH
PATH_REJECTED
OVERWRITE_UNSUPPORTED
ZIP_UNSUPPORTED
INVALID_OPTION_COMBINATION
FORCE_UNSUPPORTED
```

Success tokens must stay out of default manifest rejection output:

```text
REPORT_EXPORT_OK
MANIFEST_RECORDED
WRITE_COMPLETE
BUNDLE_EXPORT_COMPLETE
BUNDLE_EXPORT_OK
SOURCE_UNCHANGED
```

## No-Write Guarantees

Phase 10.5 boundary smoke validated that default manifest parse/invalid rejection does not create:

- runtime validation directory
- production/default report
- production/default manifest
- production/default bundle directory
- `docs/reports/python_tooling`
- bundle directory
- `bundle_manifest.json`
- `index.md`
- copied report
- zip
- log, registry, session, intake, baseline, or local config mutation

## Preserved Behavior

Validation confirmed:

- Candidate A report export success unchanged
- Candidate B manifest export success unchanged
- Candidate C directory bundle success unchanged
- isolated `--source-manifest` path/file-only behavior unchanged
- `report export --force` unchanged
- Phase 7.2A invalid option rejection unchanged
- Phase 7.2B missing source rejection unchanged
- Phase 7.2C zip unsupported rejection unchanged
- Phase 8.2 no-force overwrite rejection unchanged
- Phase 9.1 path-guard rejection unchanged
- dry-run behavior unchanged
- JSON / `to_dict()` compatibility unchanged
- wrapper remains read-only
- no CE integration
- no new command
- no write-surface expansion
- `writes_files_count = 2`
- `runs_ce_count = 0`

## Safety Boundaries

These boundaries remain frozen:

- isolated `--source-manifest` content parsing is not introduced
- path guards were not weakened
- approved roots were not expanded
- no write destination was added
- no wrapper export shortcut was added
- production/default runtime writes are not used for validation
- CE remains outside Python tooling

## Recommended Final Checkpoint Smoke

Recommended next validation-only phase:

```text
Phase 10.7 - default manifest parse rejection final checkpoint smoke
```

The final smoke should validate:

- current git status clean
- status overview `SAFE`
- report inventory `writes_files_count = 2`
- report inventory `runs_ce_count = 0`
- wrapper read-only
- targeted default manifest parse rejection tests
- prior Phase 7/8/9 regression coverage
- full pytest
- no runtime artifacts
- protected hashes unchanged
- final git status clean

## Optional Tag After Final Smoke

Recommended tag only after final smoke passes:

```text
python-tooling-default-manifest-parse-rejection-checkpoint-20260621
```

Do not create this tag in the current docs-only candidate task.

If the tag is later created, use:

```text
git tag --no-sign python-tooling-default-manifest-parse-rejection-checkpoint-20260621
```

## Next Options After Checkpoint

After final smoke and any checkpoint tag, possible next slices are:

- bundle source manifest validation surface contract, if product direction wants isolated source-manifest content parsing
- invalid output extension wording contract
- docs wrap-up / operator guide hardening
- broader status/checkpoint overview

Do not start those slices from this checkpoint candidate.
