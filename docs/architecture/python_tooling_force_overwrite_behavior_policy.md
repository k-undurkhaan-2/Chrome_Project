# Python tooling force / overwrite behavior policy

## Purpose

This policy resolves the Phase 8.1 implementation STOP finding:

```text
report export --force is supported today, not an unsupported rejection path.
```

This document records the current behavior and sets the near-term policy for future overwrite wording work. It does not implement source changes, does not change tests, does not modify the PowerShell wrapper, does not add commands or options, does not run CE, and does not authorize report, manifest, bundle, log, config, registry, baseline, session, intake, or runtime writes.

## Current Behavior Inventory

Read-only inspection during Phase 8.1 found:

- `report export --force` is present in CLI help.
- `report export --force` is present in the command descriptor.
- `report export --force` enables overwrite when the approved target already exists.
- `src/armedforces_tool/report_export.py` computes `would_overwrite = bool(target_exists and force)`.
- `src/armedforces_tool/report_export.py` writes the target when `force=True`.
- `tests/test_report_export.py` includes `test_real_export_existing_target_with_force_overwrites`.
- That test asserts `REPORT_EXPORT_OK`, `overwritten is True`, `wrote_file is True`, and existing file content is replaced.
- `report export --out <existing-file>` without `--force` is a rejection path.
- `report bundle export --out <existing-directory>` is a rejection path.
- `report bundle export --force` does not exist in current help or command descriptor.

Therefore, treating all force/overwrite behavior as unsupported would contradict current user-facing behavior and tests.

## Near-Term Policy

Preserve current behavior:

```text
report export --force remains supported for now.
```

Reasons:

- it is already user-facing
- it is already implemented
- it is already tested as successful overwrite behavior
- removing or changing it is behavior removal, not wording cleanup
- wrapper remains read-only, so this does not expose new wrapper write paths
- write-capable command count remains unchanged

Future wording work must not relabel `report export --force` as unsupported unless a separate behavior change/deprecation contract explicitly authorizes that migration.

## Future Wording Target

The next safe wording target is:

```text
overwrite rejection without force
```

Examples:

```text
report export --out <existing-file>
report export --record-manifest --manifest-out <existing-file>
report bundle export --out <existing-directory>
report bundle export --out <existing-file>
```

The wording should clarify rejection only when overwrite is not authorized.

## Token Policy Correction

Corrected token policy:

- `FORCE_UNSUPPORTED` must not be used for `report export --force`, because it is supported today.
- `FORCE_UNSUPPORTED` can only be used in future for a command where `--force` is truly unsupported, for example if `report bundle export --force` is ever surfaced as a rejected option.
- `OVERWRITE_UNSUPPORTED` may be used for existing-output rejection where overwrite is not authorized.
- `NO_FILES_WRITTEN` may be used where no output is written.

Recommended token scope for no-force overwrite rejection:

```text
OVERWRITE_UNSUPPORTED
NO_FILES_WRITTEN
```

Do not introduce `FORCE_UNSUPPORTED` into an implementation unless a real unsupported-force surface exists.

## Success Behavior

`report export --force` success must remain a success path and keep success-oriented output such as:

```text
REPORT_EXPORT_OK
WRITE_COMPLETE
```

It may preserve existing metadata such as:

```text
overwritten = True
wrote_file = True
```

Do not relabel this success path as a rejection path.

## Safety Boundaries

These boundaries remain unchanged:

- wrapper remains read-only
- no wrapper export shortcut
- no CE
- no new command
- no new option
- no approved-root expansion
- no path guard weakening
- tests must use pytest temp paths only
- production/default report, manifest, bundle, log, config, session, intake, baseline, and registry paths must not be used for wording tests

## Migration / Deprecation Option

If future product direction wants to remove or deprecate `report export --force`, that must be a separate high-risk behavior change contract:

```text
Phase 8.x - report export force deprecation/removal contract
```

That future contract would need:

- user-facing behavior change analysis
- migration path
- documentation update
- tests changed from success to rejection
- explicit approval
- final smoke
- no silent behavior removal

Do not do that in the current rejection wording track.

## Recommended Next Phase

Recommended:

```text
Phase 8.2-contract - overwrite rejection without force wording contract
```

Alternative numbering:

```text
Phase 8.1B-contract - overwrite rejection without force wording contract
```

The next contract must state explicitly that `report export --force` success remains unchanged.

## Phase 8.2 Follow-Up

The Phase 8.2 no-force overwrite rejection contract narrows future implementation to existing-output rejection where overwrite is not authorized.

`report export --force` remains supported near-term and must not be relabeled as unsupported.

`FORCE_UNSUPPORTED` remains reserved and must not be used for current `report export --force`.

See:

```text
docs/architecture/python_tooling_overwrite_without_force_wording_contract.md
```
