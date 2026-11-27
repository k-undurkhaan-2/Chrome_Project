# Manual CE First Scan export

Use this utility only with an **expressly authorized, operator-owned test
application** already attached in CE 7.6. Invoking it declares permission to read
and export the observations below. Third-party games and unauthorized targets
are unsupported.

## Run once

1. Finish the ordinary **First Scan** in CE and leave that scan tab selected.
   Supported input: **Exact Value**, **Float** with a finite decimal literal, or
   **4 Bytes** with a decimal integer or hexadecimal uint32 literal. Use the
   existing complete result, before any Next Scan. Unknown-value, range, formula,
   inverted, OnlyOne/IsUnique, other value types, and hexadecimal Float scans
   cannot supply this offline contract and receive an explicit error.
2. Open **Memory View → Tools → Lua Engine** and execute this single line:

   ```lua
   dofile([[D:/armedforces.io-v2/src/mvp0_manual_export.lua]]).export()
   ```

   If the checkout is elsewhere, change only the absolute file path. No prepared
   records, configuration, Native MVP run, scoring batch, or additional scan is
   required. The utility creates its checkout's ignored `log/` directory itself
   using CE's bundled LuaFileSystem; nothing needs installing.
3. Read the printed **outcome, occurrence count, capture/export times, and
   manifest path**. `REPLAY_READY` means the frozen dataset satisfies the existing
   loader. `INCOMPLETE` means inspect the manifest's `issues`, counts, and
   `source_error`; it is not admitted for replay. `EXPORT_FAILED` reports the
   unavailable capability or failed operation and is not a delivered dataset.

Use one invocation at a time per checkout, including across CE instances. Leave
the process attachment and selected scan unchanged until it returns. This is a
synchronous utility; large populations can take time and memory. It installs no
timer, worker, telemetry, or background collection.

## What is captured

Every occurrence in the existing `MemScan.FoundList` is retained in source order,
including duplicates and candidates whose current values no longer match. The
count is reconciled with CE's completed `ADDRESSES.TMP` file before and after
capture (the progress counter can reset after scanning). No filtering,
ranking, sampling, 8000/100 limit, or fallback population is applied during export.
The already attached process supplies read-only region metadata and eight fixed
32-bit observation locations per occurrence, at these existing scorer offsets:

```text
candidate address + {-0x20, -0x10, -8, 0, 0x30, 0x40, 0x48, 0x50}
```

Only these word observations and each candidate's mapped/protection observations
enter the records. No pointer following or arbitrary memory dump is performed.
Failed/inaccessible reads are explicit `unavailable` words, never fabricated
zeroes. Unknown mapping metadata remains unknown. Conflicting duplicates or
overlapping words remain in an incomplete export; observed candidate mapping
changes are retained in `ce_capture.mapping_changes`. Attachment, membership,
settings, or count changes abort the export. The utility never attaches, scans,
injects, changes target memory, or invokes the collector/scorer/writer/Native MVP.

**The membership comes from First Scan; the observations are read at export
time.** CE does not supply historical structural observations from that scan.
`source_snapshot_status=CE_SEQUENTIAL_READ` and `ce_capture.atomic=false` describe
this limitation. Reads and mapping checks are sequential; undetected changes
between checks remain possible. `source_unchanged_at_checks` describes the
internal frozen table during serialization, not an atomic live process snapshot.
Complete enumeration of CE's supplied result does not prove complete external
acquisition; `acquisition_completeness` remains `UNKNOWN`.

The target bit pattern is derived from CE's recorded scan value and type, never
from a potentially changed candidate. Recorded options use full population mode.
The unchanged offline eligibility predicate still applies during later scoring;
for Float scans, CE's rounded matches need not all match that exact bit pattern.
Unknown revisions and independent truth remain `UNKNOWN`.

## Local files and later replay

Outputs stay under `D:/armedforces.io-v2/log/` with a unique
`manual-export-<UTC>-<counter>` prefix. Each invocation writes `.records.jsonl`
and `.labels.json`, then publishes `.manifest.json` last. Existing files and
failed `.reserved` names are never reused. A `.pending` file is not success.
Keep all artifacts local and outside upload/synchronization jobs; never commit
datasets, private configuration, or logs. MD5 checks detect accidental corruption,
not authenticity.

The existing `src/mvp0_export_loader.py` accepts the resulting version-1 format:
`load_replay(manifest_path, lua)` returns `(records, options, manifest)` for the
existing caller-owned runtime and trusted AC5/AC6 module loader. Pass these to
AC5 `run(records, options, load_module)` or AC6
`run(options, {records=records, load_module=load_module})`. The algorithms and
their resource limits are unchanged. For a bounded comparison, copy the options
and select `population_mode='bounded'`; reuse the same frozen records.

Independent labels may be added afterward to `.labels.json`: retain `dataset_id`
and `records_md5`, set `status='SUPPLIED_INDEPENDENT'`, `independent=true`, and an
independent `basis`; map original 1-based occurrence indices in `outcomes` to
`POSITIVE`, `NEGATIVE`, `AMBIGUOUS`, or `UNKNOWN`. Missing labels are not negative.
The replay loader never opens the label sidecar.

`capture_wall_ms` covers enumeration and observation; `export_wall_ms` covers
freezing, validation, serialization, hashing, and final internal source checks,
excluding manifest publication. Time offline computation separately around the
existing AC5/AC6 call, excluding export and loading.

Implementation checks use the existing Lua 5.3/5.4 tests and controlled CE API
doubles, including direct no-argument export and AC5/AC6 replay. They do not prove
a live CE capture: no running owned-test CE session was available during this
correction. API behavior was checked against the installed CE reference and the
[official CE source](https://github.com/cheat-engine/cheat-engine/tree/master/Cheat%20Engine).
