# Python Tooling Invalid Output Extension Wording Contract

## Purpose

This contract defines a narrow wording slice for invalid output extension / unsupported output type rejections in Python report tooling.

This is documentation only. It does not implement behavior, enable new output formats, add commands or options, modify Python source or tests, modify the read-only wrapper, run CE, or authorize report/bundle writes.

Implementation clarified only real current rejection surfaces. It did not weaken path guards, expand approved roots, add write destinations, or convert an unsupported output type into a supported format.

## Current Status

Phase 11 status:

```text
Phase 11.1 contract: completed
Phase 11.2 implementation: completed
Phase 11.3 boundary smoke: PASS
Phase 11.4 checkpoint candidate docs: current
Final checkpoint smoke: pending
```

Implemented surfaces:

```text
report export --out <unsupported-extension>
report export --record-manifest --manifest-out <unsupported-extension>
report bundle export --out <file-like path>
```

Skipped / non-target surface:

```text
report bundle export --out <path.zip> --zip
```

This remains Phase 7.2C zip unsupported with `ZIP_UNSUPPORTED` / `BUNDLE_ZIP_EXPORT_NOT_IMPLEMENTED`.

Phase 11.3 boundary smoke validated `status overview = SAFE`, `writes_files_count = 2`, `runs_ce_count = 0`, wrapper read-only behavior, targeted tests, prior-slice regression tests, full pytest, no runtime artifacts, unchanged protected hashes, and clean final git status.

## Baseline

Stable checkpoint tags:

```text
python-tooling-phase3-final-checkpoint-20260616
python-tooling-powershell-wrapper-readonly-checkpoint-20260616
python-tooling-output-wording-checkpoint-20260618
python-tooling-real-write-output-validation-checkpoint-20260619
python-tooling-rejection-path-wording-checkpoint-20260620
python-tooling-no-force-overwrite-rejection-checkpoint-20260620
python-tooling-path-guard-rejection-checkpoint-20260620
python-tooling-default-manifest-parse-rejection-checkpoint-20260621
```

Current stable state:

- commands approximately `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable Python commands remain only `report export` and `report bundle export`
- wrapper remains read-only and does not wrap write-capable commands
- zip export remains unsupported
- `report export --force` remains supported direct Python CLI behavior
- `report bundle export` has no `--force` parser surface
- isolated `--source-manifest` content remains unparsed
- approved roots and path guards remain strict

## Scope Distinction

Invalid output extension / output type rejection is distinct from these established rejection domains:

- path guard rejection: `PATH_GUARD_REJECTED`, `OUTSIDE_APPROVED_ROOT`, `BAD_PATH`, `PATH_REJECTED`
- no-force overwrite rejection: `OVERWRITE_UNSUPPORTED`, `NO_FILES_WRITTEN`
- zip unsupported rejection: `ZIP_UNSUPPORTED`, `NO_FILES_WRITTEN`
- missing or invalid source inputs: `SOURCE_MISSING`, `SOURCE_INVALID`, `NO_FILES_WRITTEN`
- default manifest parse rejection: `INVALID_MANIFEST`, `MANIFEST_PARSE_FAILED`, `MANIFEST_INVALID`, `NO_FILES_WRITTEN`

Future invalid output extension/type wording should use:

```text
OUTPUT_EXTENSION_INVALID
OUTPUT_TYPE_UNSUPPORTED
NO_FILES_WRITTEN
```

If `.zip` output is currently handled by `ZIP_UNSUPPORTED`, do not reclassify it as generic invalid extension without an explicit source-backed reason.

## Potential Target Surfaces

Future implementation must first inspect current source/help/tests and only target real current rejection surfaces.

Potential surfaces:

```text
report export --out <path-with-unsupported-extension>
report export --out <directory-path>
report export --record-manifest --manifest-out <path-with-unsupported-extension>
report bundle export --out <path-with-file-extension-that-is-not-a-directory-target>
report bundle export --out <path-with-unsupported-output-form>
report bundle export --out <path.zip> if not already handled by ZIP_UNSUPPORTED
```

If no current invalid-output-extension/type rejection surface exists, the implementation phase must STOP and report that a separate output-type surface contract is needed.

## Desired Future Behavior

Future implementation should ensure:

- rejection fails before writing anything
- no report file is created
- no manifest file is created
- no bundle directory is created
- no `bundle_manifest.json` is created
- no `index.md` is created
- no report is copied
- no zip file is created
- no production/default report, manifest, or bundle path is written during tests
- output identifies the offending output option/path
- wording distinguishes invalid output extension/type from path guard, overwrite, zip unsupported, source input, and manifest parse errors
- output includes `OUTPUT_EXTENSION_INVALID` or `OUTPUT_TYPE_UNSUPPORTED` if compatible
- output includes `NO_FILES_WRITTEN` if compatible

## Stable Token Policy

Preferred conceptual tokens:

```text
OUTPUT_EXTENSION_INVALID
OUTPUT_TYPE_UNSUPPORTED
NO_FILES_WRITTEN
```

Existing tokens to inspect before changing:

```text
BAD_PATH
PATH_REJECTED
PATH_GUARD_REJECTED
OVERWRITE_UNSUPPORTED
ZIP_UNSUPPORTED
```

Rules:

- do not use output-type tokens for approved-root/path-guard rejection
- do not use output-type tokens for no-force overwrite rejection
- do not use output-type tokens for missing/non-file source inputs
- do not use output-type tokens for default manifest parse failures
- do not use `ZIP_UNSUPPORTED` for generic extension failures unless the actual current reason is zip/archive unsupported
- preserve existing machine-readable status if current code already uses one
- do not use success tokens in rejection output
- do not enable new output formats through wording work

## Wording Draft

Report output unsupported extension:

```text
Report Export Rejected
status                   OUTPUT_EXTENSION_INVALID
output_option            --out
output_path              <path>
write_status             NO_FILES_WRITTEN
conclusion               REPORT_EXPORT_REJECTED
```

Manifest output unsupported extension:

```text
Report Export Rejected
status                   OUTPUT_EXTENSION_INVALID
output_option            --manifest-out
output_path              <path>
write_status             NO_FILES_WRITTEN
conclusion               REPORT_EXPORT_REJECTED
```

Bundle unsupported output type:

```text
Bundle Export Rejected
status                   OUTPUT_TYPE_UNSUPPORTED
output_option            --out
output_path              <path>
supported_output         directory
write_status             NO_FILES_WRITTEN
conclusion               BUNDLE_EXPORT_REJECTED
```

If the current output framework uses a different style, preserve it and include equivalent information.

## Must Not Appear

Invalid output extension/type rejection output must not include success tokens:

```text
REPORT_EXPORT_OK
MANIFEST_RECORDED
WRITE_COMPLETE
BUNDLE_EXPORT_COMPLETE
BUNDLE_EXPORT_OK
SOURCE_UNCHANGED
```

It must avoid unrelated rejection tokens unless they are the actual current reason:

```text
SOURCE_MISSING
SOURCE_INVALID
MANIFEST_PARSE_FAILED
MANIFEST_INVALID
PATH_GUARD_REJECTED
OUTSIDE_APPROVED_ROOT
OVERWRITE_UNSUPPORTED
ZIP_UNSUPPORTED
FORCE_UNSUPPORTED
```

## Success Behavior To Preserve

Future implementation must preserve:

- Candidate A report export success behavior
- Candidate B manifest export success behavior
- Candidate C directory bundle success behavior
- isolated `--source-manifest` path/file-only behavior
- default manifest parse rejection behavior
- `report export --force` supported success behavior
- Phase 7/8/9/10 rejection slices
- dry-run behavior
- JSON / `to_dict()` compatibility
- command inventory/write surface

## Test Requirements For Future Implementation

Future implementation must add/update tests only for real current surfaces, using pytest temp paths only.

Potential tests:

- report output unsupported extension
- report output directory path
- manifest output unsupported extension
- bundle output file-like/unsupported path
- `.zip` output path only if current semantics are not already Phase 7.2C `ZIP_UNSUPPORTED`

Assertions:

- no report artifact is created
- no manifest artifact is created
- no bundle artifact is created
- no zip artifact is created
- output includes the appropriate token or current equivalent
- `NO_FILES_WRITTEN` appears if compatible
- success tokens are absent
- unrelated rejection tokens are absent unless they are the actual current reason

## Runtime Artifact Policy

Future tests must not create:

```text
reports/python_tooling/validation/
reports/python_tooling/full_status.md
reports/python_tooling/manifest.jsonl
reports/python_tooling/bundles/
docs/reports/python_tooling
log/config/session/intake/baseline/registry files
```

## Stop Conditions For Future Implementation

Future implementation must STOP if:

- no current invalid output extension/type rejection surface exists
- implementation would require adding new output type validation
- implementation would enable new output formats
- implementation would weaken path guards or expand approved roots
- implementation would change no-force overwrite behavior
- implementation would change zip unsupported behavior
- implementation would change default manifest parse behavior
- tests require production/default writes
- manual real writes are required
- wrapper changes are required
- CE/runtime behavior is involved
- Candidate A/B/C success outputs would change

## Recommended Next Phase

Recommended next phase:

```text
Phase 11.5 - invalid output extension rejection final checkpoint smoke
```

Do not create `python-tooling-invalid-output-extension-rejection-checkpoint-20260621` until the final checkpoint smoke passes.
