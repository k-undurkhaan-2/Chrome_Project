# Python tooling rejection-path wording checkpoint candidate - 20260620

## Classification

- checkpoint candidate
- docs-only
- no tag created

## Summary

Phase 7 rejection-path wording now has three implemented and smoke-validated slices:

- invalid option combination for `report export --manifest-out <path>` without `--record-manifest`
- missing or invalid source input for `report bundle export`
- unsupported zip request for `report bundle export --zip`

This checkpoint candidate records the current documented state only. It does not create a tag, does not authorize any new write path, and does not change Python, wrapper, PowerShell, Lua, test, CE, runtime, report, manifest, bundle, log, config, session, intake, registry, or baseline behavior.

## Stable Tokens

Stable rejection/no-write tokens and intended scope:

- `INVALID_OPTION_COMBINATION`: option combinations that are invalid before any write can begin.
- `SOURCE_MISSING`: source report or source manifest path is missing.
- `SOURCE_INVALID`: source report or source manifest path is present but is not a valid file input.
- `ZIP_UNSUPPORTED`: zip/archive bundle output request is rejected.
- `NO_FILES_WRITTEN`: the command failed or planned without writing output artifacts.

Success-only tokens:

- `SOURCE_UNCHANGED`
- `BUNDLE_EXPORT_OK`
- `BUNDLE_EXPORT_COMPLETE`
- `REPORT_EXPORT_OK`
- `MANIFEST_RECORDED`
- `WRITE_COMPLETE`

Rules:

- Success tokens must not appear in rejection outputs.
- `SOURCE_UNCHANGED` remains success-only.
- `SOURCE_MISSING` and `SOURCE_INVALID` remain source-input specific.
- `ZIP_UNSUPPORTED` remains zip/archive specific.
- `INVALID_OPTION_COMBINATION` remains option-combination specific.
- `NO_FILES_WRITTEN` indicates failure or dry-run planning before output artifacts are written.

## Validated Rejection Paths

Invalid option combination:

```text
report export --manifest-out <path>
```

without:

```text
--record-manifest
```

Missing or invalid bundle source input:

```text
report bundle export --source-report <missing/non-file> --out <bundle-dir>
report bundle export --source-report <report> --source-manifest <missing/non-file> --out <bundle-dir>
report bundle export --source-manifest <manifest> --out <bundle-dir>
```

Unsupported zip output:

```text
report bundle export --zip
```

## No-Write Guarantees

Boundary smoke validation recorded that rejection paths did not create or mutate:

- runtime validation directory
- production/default report
- production/default manifest
- production/default bundle directory
- zip file
- bundle directory
- `bundle_manifest.json`
- `index.md`
- copied report
- log files
- registry files
- session state
- intake journal
- baseline files
- local config files

## Behavior Preserved

Validation confirmed:

- Candidate A report export success output remains unchanged.
- Candidate B manifest export success output remains unchanged.
- Candidate C directory bundle success output remains unchanged.
- Dry-run behavior remains unchanged.
- JSON / `to_dict()` compatibility remains unchanged where relevant.
- `BUNDLE_ZIP_EXPORT_NOT_IMPLEMENTED` remains the status for zip rejection.
- The PowerShell wrapper remains read-only.
- CE is not integrated into Python tooling.
- No new write-capable command was added.
- No command count or write-surface expansion was introduced.
- `writes_files_count = 2`.
- `runs_ce_count = 0`.

## Unsupported / Frozen Boundaries

These boundaries remain unsupported or frozen:

- zip export remains unsupported
- `--force` / overwrite remains unsupported
- wrapper does not expose write-capable exports
- CE is not part of Python tooling
- approved roots and path guards are not loosened
- production/default runtime writes are not used for validation
- runtime write/restore migration remains out of scope

## Recommended Final Checkpoint Smoke

Recommended next validation-only phase:

```text
Phase 7.4 - rejection-path wording final checkpoint smoke
```

The final smoke should validate:

- current git status clean
- status overview `SAFE`
- report inventory `writes_files_count = 2`
- report inventory `runs_ce_count = 0`
- wrapper read-only
- targeted rejection-path tests
- full pytest
- no runtime artifacts
- protected hashes unchanged
- final git status clean

## Tag Recommendation After Final Smoke

Recommended tag only after Phase 7.4 passes:

```text
python-tooling-rejection-path-wording-checkpoint-20260620
```

Do not create this tag in the current docs-only checkpoint candidate task.

If a tag is later created, use:

```powershell
git tag --no-sign python-tooling-rejection-path-wording-checkpoint-20260620
```

## Next Options After Checkpoint

After final smoke and any checkpoint decision, possible next slices are:

- `--force` / overwrite unsupported wording contract
- approved-root/path-guard rejection wording contract
- report path collision / existing output rejection wording contract
- broader docs wrap-up

Do not start those slices in this checkpoint candidate task.
