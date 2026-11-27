# Manual first-pass snapshot export

`src/mvp0_manual_export.lua` exports an **existing, expressly approved frozen
Lua table** from an operator-owned production application or representative real
test environment. It accepts the ordinary AC5/AC6 record shape; it has no live
input adapter. The operator must already possess the original population and
approved observations before invoking it. No Native MVP Start or ranking batch
is required. Loading the module is inert; `export` performs local file I/O only.

**The existing bounded Single result cannot provide this complete real dataset.**
The collector's selected addresses and ordinary ranked results are not the
original population. An existing address-only snapshot can produce an inventory,
but cannot supply equivalent scoring observations. No complete real snapshot was
provided or captured during implementation. Full replay-ready real export is
supported only when the operator already has the complete approved record table
described below. The exporter cannot manufacture it from bounded results, recover
discarded observations, or acquire missing data. Artificial tests establish
implementation behavior only, not real provenance or effectiveness.

## Prepare and invoke once

Use the research checkout containing this utility. First verify the local output
area, then create it if absent, from that checkout in PowerShell:

```powershell
git check-ignore -v log/manual-export-check.manifest.json
if ($LASTEXITCODE -ne 0) { throw 'Output area is not ignored' }
New-Item -ItemType Directory -Path log -Force | Out-Null
```

Keep this directory local, outside synchronization/upload jobs. Use **one manual
invocation at a time per output directory**, including across CE instances.
The writer uses the repository's serialized manual reservation convention, not
an interprocess lock. Do not delete reservations or mutate input tables while an
export is running. No background activity is installed.

In CE's Lua Engine, run the following with the actual absolute research checkout
path. `approved_initial_records` must already be a frozen, dense, ordinary Lua
array supplied by the approved existing data source. This example does not
create or read target data. Fill the metadata from the source; retain UNKNOWN
where it is not established. Use the real category only when it is true and the
data export is expressly authorized:

```lua
local exporter = dofile([[D:/path/to/research-checkout/src/mvp0_manual_export.lua]])
local snapshot = {
  records=approved_initial_records,
  authorized_owned=true,
  permission_disposition='EXPRESSLY_APPROVED',
  source_category='AUTHORIZED_REPRESENTATIVE_REAL',
  -- Alternatively AUTHORIZED_REAL_PRODUCTION; ARTIFICIAL_FIXTURE for tests only.
  population_basis='INITIAL_SNAPSHOT',
  source_snapshot_status='OPERATOR_FROZEN_COPY',
  acquisition_completeness='UNKNOWN',
  source_id='UNKNOWN', configuration_id='UNKNOWN',
  source_revision='UNKNOWN', algorithm_revision='UNKNOWN',
  capture_utc='UNKNOWN',
  observation_started_utc='UNKNOWN', observation_finished_utc='UNKNOWN',
  -- expected_source_count=<independently established count>, otherwise omit.
  -- capture_wall_ms=<previously measured acquisition duration>, otherwise omit.
  evaluation_options=approved_evaluation_options,
}
local result = exporter.export(snapshot)
print(result.outcome, result.dataset_id, result.exported_count, result.manifest_path)
```

This authority declaration describes permission for these already acquired data;
a PID, production origin, prior run, score, or configuration is not permission.
Source/configuration identifiers and errors stay local. Do not include private
configuration contents, credentials, unrelated memory, or third-party game data.

The exporter copies the supplied table and compares it with the source after
copying and before manifest publication. An observed change produces INCOMPLETE
with `source_changed_during_export`. These equality checks do not establish an
atomic snapshot of an external changing application or detect a change undone
between checks. The supported source is an operator-frozen plain table, not a
live table, FoundList object, callback, or process reader. Record the original
observation interval; do not replace it with the export time. Report known source
errors in `source_error`; unavailable/inconsistent sources can be declared with
`source_snapshot_status='UNAVAILABLE'` or `'INCONSISTENT'` and remain INCOMPLETE.

## Input and completeness

Every source occurrence occupies its original array position. Duplicates remain
present. The exporter does not filter, prescore, select, rank, normalize identities,
or apply count budgets. Sparse arrays and non-data objects fail rather than being
silently shortened. Each record may contain only:

| Field | Preserved meaning |
| --- | --- |
| `addr` | Original numeric identity, a positive integer at most `2^53-1`, for replay. Original nonempty string identities are preserved for inventories; they are not converted. Absent/false identities are explicit incomplete occurrences. |
| `mapped` | Previously observed boolean. Absent means unavailable, never false by default. |
| `protect` | Previously observed uint32 protection value. Absent is not replaced with zero. |
| `memory` | Original plain numeric-address-to-uint32 map, required by AC5 even for unmapped records. Only mapped records supply AC5 lookup words. Original associations are preserved. |
| `unavailable` | Optional numeric-address-to-`true` map declaring words already known to be unavailable. It is exported as evidence and never converted into zero or passed as a scoring feature. |

The unchanged scorer uses words at `addr + {-0x20,-0x10,-8,0,0x30,0x40,0x48,0x50}`.
Approved word maps may retain overlapping associations within this supplied
population. Words outside those contract locations are rejected, not silently
dropped. For a mapped record, each required lookup must be available among the
original mapped word maps or explicitly declared unavailable for that occurrence.
Only declare known original missingness: an unobserved/unknown gap must stay
incomplete. AC5's per-record eligibility and global lookup semantics remain
unchanged. Conflicting duplicates or words are preserved in an INCOMPLETE export.

`evaluation_options` uses the [unchanged AC5/AC6 options](algorithm_a_offline_scoring.md):
required uint32 `target_value_pattern`, optional finite `target_value_float`,
`session_id`, `filter_target_match=true`, `use_prescore_selection=true`, and the
existing explicit population mode/budgets when supplied. No truth or live settings
are accepted. Missing settings produce an inventory/incomplete export. Valid
bounded options are recorded but never limit export enumeration.

| Outcome | Meaning |
| --- | --- |
| REPLAY_READY | Entire supplied initial population exported, source table unchanged at checks, replay observations/settings reconciled, including explicit legitimate missing-word semantics. A known complete empty input can be replay-ready and evaluate to EMPTY. |
| ADDRESS_ONLY | Entire supplied identity inventory exported, without sufficient scoring observations. Does not satisfy the replay dataset requirement. |
| INCOMPLETE | Source/count/identity inconsistency, non-initial or unknown population basis, missing/contradictory observations/settings, unknown source category, source error, or source change. Inspect manifest `issues` and counts. |
| FAILED | Invalid input, I/O failure, interruption or resource exhaustion; no successful return or published manifest for that attempt. Reservations and partial files remain diagnostic only. |

`inventory_complete` concerns the supplied identity inventory and count
reconciliation. `acquisition_completeness` is independently UNKNOWN,
SUPPLIER_ASSERTED_COMPLETE, or INCOMPLETE; a matching source count never proves
external completeness. `population_basis` must truthfully be INITIAL_SNAPSHOT
for replay readiness; BOUNDED_OR_FILTERED and UNKNOWN remain INCOMPLETE.
REPLAY_READY does not establish actual provenance, independent truth, accuracy,
or permission for any subsequent operation.

## Local artifacts and independent labels

Files go to the utility's own checkout `log/`, with a unique
`manual-export-<UTC>-<counter>` prefix. Existing files and failed reservations are
not reused. Each successful invocation publishes `.manifest.json` last, after
closing `.records.jsonl` and `.labels.json`. `.manifest.pending` and `.reserved`
alone are not successful datasets. Repeated invocations and module reloads choose
unused names. JSONL has one record per occurrence; numeric map keys are decimal
JSON keys and are restored exactly by the loader. Files are data, never Lua code.

The manifest includes version, provenance/permission, source and export intervals,
counts, issues, options, revisions or UNKNOWN, file identity, byte count and MD5.
The CE built-in `md5file` reads only the frozen local file. MD5 detects accidental
corruption; it does not authenticate data or provenance. The loader checks the
file identity/hash/size, counts and replay observations independently. These APIs
are documented in the [CE Lua reference](https://wiki.cheatengine.org/index.php?title=Lua).

Default labels are an empty `outcomes` object with status UNKNOWN. If independent
labels already exist, supply a separate optional second argument:

```lua
local result = exporter.export(snapshot, {
  independent=true, basis=approved_independent_label_basis,
  outcomes=approved_occurrence_labels,
})
```

`outcomes` maps original **1-based occurrence indices** to POSITIVE, NEGATIVE,
AMBIGUOUS, or UNKNOWN. The operator must supply an independent basis, not the
scorer's result. The sidecar binds labels to `dataset_id` and `records_md5`.
Later local annotation must retain those identities and the original occurrence
indices. Absent/UNKNOWN labels are never negative. Labels do not influence export
membership or replay readiness; the replay loader never opens the label file.

## Offline replay and targeted checks

Use `src/mvp0_export_loader.py` with the existing caller-owned Lua runtime.
`load_inventory(path)` verifies all exported occurrences for inspection;
`load_replay(path, lua)` admits REPLAY_READY only and returns
`(records, options, manifest)`. No code from a dataset is executed. The latter
passes only `addr`, `mapped`, `protect`, and `memory` to the unchanged scorer.

For bounded/full comparison, load the file once, keep those records frozen, and
copy the recorded options separately for each call. Set
`population_mode='bounded'` explicitly for the bounded call. For the full call,
set `population_mode='full'` and **remove both** `scan_budget` and `max_candidates`.
Call the existing raw AC5 `run(records, options, load_module)` or AC6
`run(options, {records=records, load_module=load_module})` with the existing trusted
repository loader. Retain the runtime allocator and worker resource limits.
Errors/cancellations are unsuccessful, without partial success or fallback.

`export_wall_ms` covers entry, copying, validation, local serialization, checksum,
labels and final source check; it excludes manifest serialization/publication.
`records.bytes` measures JSONL payload; `output_bytes_excluding_manifest` and the
returned `output_bytes` identify the other size boundaries. Capture wall time is
only a supplied observation or UNKNOWN. Time each later AC5/AC6 call separately
around the call, including collection/scoring/reporting, excluding module setup,
data loading, export, truth analysis and Python conversion of the returned result.
Retain mode, coverage counts, truth availability, results, timer boundaries and
the existing worker resource measurements with that local evaluation. No native
end-to-end performance or independent accuracy follows from repeated fixture runs.

From the research checkout, after checking/creating ignored `log/` as above:

```powershell
.venv/Scripts/python.exe -B -m pytest -q tests/test_manual_export.py tests/test_offline_full_population.py tests/test_offline_collector_interface.py --basetemp=log/manual-export-verification
```

Use a fresh unused basetemp name to retain prior evidence. The focused suite uses
the existing Lua 5.3/5.4 fixtures and allocator limit, including 8,003 source
occurrences, bounded/full parity, source changes, failures, duplicate/missing/empty
inputs, independent labels and forbidden target/shell API doubles. It does not
start CE, acquire real data, change scoring, or schedule a real capture.
