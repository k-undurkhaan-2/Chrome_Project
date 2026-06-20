# Python tooling path-guard rejection checkpoint candidate - 20260620

## Classification

```text
checkpoint candidate
docs-only
no tag created
```

## Summary

Phase 9 path-guard rejection wording now has:

- a path-guard wording contract
- a path-guard wording implementation
- Phase 9.1 boundary smoke PASS

This candidate prepares the checkpoint record only. It does not create a tag, add commands, change behavior, or authorize runtime writes.

## Implemented Surfaces

Implemented path-guard wording surfaces:

```text
report export --out <outside-approved-root>
report export --record-manifest --manifest-out <outside-approved-root>
report bundle export --out <outside-approved-root>
report bundle export --source-report <guard-rejected-path>
```

The `--source-report` surface applies where the current planner already returns `BAD_PATH`.

## Skipped / Non-Target Surfaces

These surfaces remain owned by prior slices:

- missing/invalid source inputs remain Phase 7.2B `SOURCE_MISSING` / `SOURCE_INVALID`
- zip unsupported remains Phase 7.2C `ZIP_UNSUPPORTED`
- no-force overwrite remains Phase 8.2 `OVERWRITE_UNSUPPORTED`
- extension-only validation is not treated as approved-root/path-guard wording

This checkpoint candidate does not add new guard surfaces or write destinations.

## Stable Tokens And Compatibility

Stable path-guard wording tokens:

```text
PATH_GUARD_REJECTED
OUTSIDE_APPROVED_ROOT
NO_FILES_WRITTEN
```

Compatibility statuses preserved:

```text
BAD_PATH
PATH_REJECTED
```

Token rules:

- `PATH_GUARD_REJECTED` applies to guard rejection wording.
- `OUTSIDE_APPROVED_ROOT` appears where approved-root semantics apply.
- `NO_FILES_WRITTEN` indicates rejection before output artifacts are written.
- `BAD_PATH` / `PATH_REJECTED` remain compatible machine-readable statuses where applicable.
- unrelated tokens must not be substituted into path-guard rejection wording unless current semantics require it.

Unrelated rejection tokens:

```text
SOURCE_MISSING
SOURCE_INVALID
OVERWRITE_UNSUPPORTED
ZIP_UNSUPPORTED
FORCE_UNSUPPORTED
INVALID_OPTION_COMBINATION
```

Success tokens that must stay out of rejection output:

```text
REPORT_EXPORT_OK
MANIFEST_RECORDED
WRITE_COMPLETE
BUNDLE_EXPORT_COMPLETE
BUNDLE_EXPORT_OK
SOURCE_UNCHANGED
```

## No-Write Guarantees

Phase 9.1 boundary smoke validated:

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
- `report export --force` unchanged
- Phase 7.2A invalid option rejection unchanged
- Phase 7.2B missing source rejection unchanged
- Phase 7.2C zip unsupported rejection unchanged
- Phase 8.2 no-force overwrite rejection unchanged
- dry-run behavior unchanged
- JSON / `to_dict()` compatibility unchanged
- wrapper remains read-only
- no CE integration
- no new command
- no write-surface expansion
- `writes_files_count = 2`
- `runs_ce_count = 0`

## Guard Safety Boundaries

These boundaries remain frozen:

- path guards were not weakened
- approved roots were not expanded
- no write destination was added
- no wrapper export shortcut was added
- production/default runtime writes are not used for validation
- CE remains outside Python tooling

## Recommended Final Checkpoint Smoke

Recommended next validation-only phase:

```text
Phase 9.3 - path-guard rejection final checkpoint smoke
```

The final smoke should validate:

- current git status clean
- status overview SAFE
- report inventory `writes_files_count=2`, `runs_ce_count=0`
- wrapper read-only
- targeted path-guard rejection tests
- Phase 7/8 regression coverage
- full pytest
- no runtime artifacts
- protected hashes unchanged
- final git status clean

## Optional Tag Recommendation After Final Smoke

Create this tag only after final smoke passes:

```text
python-tooling-path-guard-rejection-checkpoint-20260620
```

Do not create this tag in the current docs-only candidate task. If a tag is later created, use:

```powershell
git tag --no-sign python-tooling-path-guard-rejection-checkpoint-20260620
```

## Next Options After Checkpoint

After final smoke/checkpoint, possible next slices:

- bundle source manifest format/parse rejection wording contract
- report/bundle invalid output extension wording contract
- approved-root operator docs hardening
- broader docs wrap-up

Do not start those slices in this checkpoint candidate task.
