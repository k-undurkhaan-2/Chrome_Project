# Python tooling no-force overwrite rejection checkpoint candidate - 20260620

## Classification

- checkpoint candidate
- docs-only
- no tag created

## Summary

Phase 8 no-force overwrite wording now has:

- a behavior-policy decision that `report export --force` remains supported direct Python CLI behavior
- a no-force existing-output overwrite rejection contract
- a no-force overwrite rejection implementation
- a boundary smoke PASS

This candidate does not create a checkpoint tag. A later validation-only final checkpoint smoke must pass before any tag is considered.

## Stable Tokens

Validated rejection tokens:

- `OVERWRITE_UNSUPPORTED`: applies to no-force existing-output rejection.
- `NO_FILES_WRITTEN`: indicates rejection happened before output artifacts were written.

Reserved token:

- `FORCE_UNSUPPORTED`: reserved only for a real unsupported-force surface. It must not be used for current `report export --force`.

Success tokens that must remain success-only and must not appear in no-force overwrite rejection output:

- `REPORT_EXPORT_OK`
- `MANIFEST_RECORDED`
- `WRITE_COMPLETE`
- `BUNDLE_EXPORT_COMPLETE`
- `BUNDLE_EXPORT_OK`
- `SOURCE_UNCHANGED`

Unrelated rejection tokens that must not be used for overwrite rejection unless current parser semantics explicitly require them:

- `ZIP_UNSUPPORTED`
- `SOURCE_MISSING`
- `SOURCE_INVALID`
- `INVALID_OPTION_COMBINATION`

## Validated Rejection Paths

Validated no-force existing-output rejection paths:

- `report export --out <existing-file>`
- `report bundle export --out <existing-directory>`
- `report bundle export --out <existing-file>`

Boundary smoke and tests confirm:

- existing files/directories remain unchanged
- no partial/temp replacement output remains
- validation does not use production/default report, manifest, or bundle paths

## Explicit Non-Target

`report export --force` is a supported success path, not a rejection target.

Expected preserved behavior:

- `REPORT_EXPORT_OK`
- `WRITE_COMPLETE`
- `overwritten=True`
- `wrote_file=True`

Changing or removing this behavior requires a separate behavior-change/deprecation contract.

## Manifest Semantics

`report export --record-manifest --manifest-out <existing-file>` was not converted to overwrite rejection.

Current semantics are append/preflight manifest semantics, not no-force overwrite rejection.

## No-Write Guarantees

Boundary smoke validated:

- no runtime validation directory
- no production/default report
- no production/default manifest
- no production/default bundle directory
- no `docs/reports/python_tooling`
- no log/registry/session/intake/baseline/local config mutation

## Behavior Preserved

Validation confirmed:

- Candidate A report export success unchanged
- Candidate B manifest export success unchanged
- Candidate C directory bundle success unchanged
- Phase 7.2A invalid option rejection unchanged
- Phase 7.2B missing source rejection unchanged
- Phase 7.2C zip unsupported rejection unchanged
- dry-run behavior unchanged
- JSON / `to_dict()` compatibility unchanged
- wrapper remains read-only
- no CE integration
- no new command
- no write-surface expansion
- `writes_files_count = 2`
- `runs_ce_count = 0`

## Unsupported / Frozen Boundaries

These remain unsupported or frozen:

- zip export remains unsupported
- bundle `--force` remains absent
- wrapper does not expose write-capable exports
- CE is not part of Python tooling
- approved roots/path guards are not loosened
- production/default runtime writes are not used for validation

## Recommended Final Checkpoint Smoke

Recommended next phase:

```text
Phase 8.4 - no-force overwrite rejection final checkpoint smoke
```

The final smoke should validate:

- current git status clean
- status overview SAFE
- report inventory `writes_files_count=2`, `runs_ce_count=0`
- wrapper read-only
- targeted no-force overwrite rejection tests
- `report export --force` success still passes
- Phase 7 rejection tests still pass
- full pytest
- no runtime artifacts
- protected hashes unchanged
- final git status clean

## Optional Tag Recommendation After Final Smoke

Recommended tag only after final smoke passes:

```text
python-tooling-no-force-overwrite-rejection-checkpoint-20260620
```

Do not create this tag in this docs-only candidate task. If a tag is later created, use `git tag --no-sign`.

## Next Options After Checkpoint

Possible next slices after final smoke/checkpoint:

- approved-root/path-guard rejection wording contract
- report path collision / invalid output-root wording contract
- bundle source manifest format/parse rejection wording contract
- broader docs wrap-up

Do not start those slices from this checkpoint candidate.
