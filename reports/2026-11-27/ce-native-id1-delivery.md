# Standalone native ID1 delivery

Branch: `codex/temp-ce-native-id1-auto`

Base commit: `8755ce4b8ad89b3d3a3f4cdb80652ddbea879a50`

Delivery date: 2026-11-27 (Asia/Shanghai)

## Product

Open `src/ce_mvp.local.CT` in Cheat Engine 7.6 x64 with the existing sibling
`ce_mvp_config.local.lua`, then check ID1. A portable local package is available
at `reports/2026-11-27/ce-native-id1-product/ce-native-id1-product.zip`.
The ZIP contains exactly two files: the prepared CT and the unchanged local
config. The same files are unpacked in that directory's `standalone/` folder.

The CT embeds the independent runner and both original algorithm files.
There are no imports of the old core/adapter, qualification factory, synthetic
fixture, external Python runtime or engineering mode. Only native CE process,
scan, read/write and timer APIs execute the product workflow. Historical files
elsewhere in the repository are outside this delivery's runtime dependency graph.

## Requirement audit

| Requested behavior | Implementation and evidence |
| --- | --- |
| Temporary branch | `codex/temp-ce-native-id1-auto`, based on the existing checkout. The initial delivery was local; the subsequent user request authorizes signed commit and push of this delivery. No version tag is created. |
| Use the current local config | The original config was not edited; its SHA-256 is recorded below. Each Start reads it again. |
| Check CT ID1 to attach the configured PID | The actual ID1 AA script loads the embedded runner and calls native `openProcess(config.target_pid)`, then verifies CE's opened PID. No PID allowlist or fixed fixture input exists. |
| Exact scan for the configured value | Native `createMemScan`/`firstScan` scan the exact Float32 bits as hexadecimal Dword, four-byte aligned, in writable memory. All private/image/mapped types are included. |
| Feed the full initial pool to the algorithm | Every FoundList index is consumed. Both collector budgets are set to the actual pool size. Original deduplication and target-match filters remain; every survivor is fully scored. Counts must agree before writing. |
| Do not rewrite the algorithm | Both source files match their original byte hashes and Git HEAD. Embedded sources equal the originals after standard text newline normalization. No scoring function is replaced. |
| Write the highest-ranked hard-pass candidate; allow REVIEW | The unchanged result's `best` must have `hard_pass=true`; its address receives the configured Float32 write. Recommendation labels are informational, without an additional execution gate. |
| Periodic decrease/rewrite | A timer checks the selected address according to `monitor_interval_ms`; a value below `write_value` is rechecked and restored. Equal/higher values are left alone. Writes are read back immediately. |
| Stop on question marks | The first unreadable/nonfinite read stops the timer and clears ID1. There are no automatic writes, retries, reattachments or rescans afterward. CE 7.6's actual unreadable Float display is `??`. |
| Product works with arbitrary configured PIDs | Real native runs attached different OS-assigned PIDs through the same table. Unit tests also exercise config rereading and PID replacement. Only the config selects the process. |
| Exclude former engineering design | The active entrypoint and builder were replaced with a direct runner and a three-module embedded table. Engineering modes, qualification gates, mapping/structure continuity gates, diagnostic branches and recovery orchestration are absent from the runner. |

ID2 prints cached status. ID3 is a real Float memory record for the selected
address; the runner prevents its freeze activation so it cannot write after ID1
stops. Opening the CT itself does not attach, scan or write.

## Validation

### Product and unchanged algorithm

- Product regression: **75 passed**, using both Lua 5.3 and Lua 5.4. Tests execute
  the generated CT scripts, the embedded runner and original algorithms.
- Existing algorithm regressions: **182 passed** across
  `test_screening_single_mode.py`, `test_screening_validity_timing.py` and
  `test_stable_prescore_optimization.py`.
- The first combined run had 247 passes (65 product + 182 algorithm); the final
  product run added ten passing cases for configurable search/write values,
  invalid bounds and cleanup failure. There are 257 distinct passing cases in
  this scoped validation, not a claim about the entire historical test suite.
- More than 2,000 matches, the last candidate winning, REVIEW, advisory REJECT,
  complete counts, exact intervals, repeated restores, equal/higher values,
  unreadable/nonfinite values, target changes, manual stop during each phase,
  failed writes/readback, config reload and relocated-table config selection
  are covered. Embedded module contents and XML/Lua delimiter handling are checked.
- `git diff --check` passed. No separate lint tool was run.

### Real Cheat Engine 7.6

The manual driver launches an owned process with actual writable memory and a
separate installed CE instance. It substitutes only the PID in a copy of the
current config. It drives the production table's unchanged ID1 scripts through
CE memory records. No CE APIs are mocked. Runtime modules and test fixtures are
not copied beside the table. The controlled target is test evidence, not a
product input requirement or runtime dependency.

| Run | Native PID | Raw / inspected / scored | Result |
| --- | ---: | --- | --- |
| First standalone smoke | 34780 | 1 / 1 / 1 | PASS: write 125, lower to 42, restore 125, release address, stop on `??`, ID1 false. |
| Full initial pool | 42692 | 2101 / 2101 / 2101 | PASS: last structured candidate selected, same write/restore/stop lifecycle. |
| Final delivered CT | 47008 | 2101 / 2101 / 2101 | PASS: 2 write calls, 1 rewrite, `VALUE_UNREADABLE (???)`, ID1 false; no additional writes for 2200 ms after stop. |

The final smoke's generated CT is byte-identical to `src/ce_mvp.local.CT` and the
packaged CT. Final native elapsed time was 11641 ms. Scratch evidence is local
and ignored under `reports/2026-11-26/ce-native-id1-local/product-smoke-000658/`.
All target and CE processes started by these tests were closed by the driver.

The user's configured PID 20560 was not running at the final process check.
Consequently, no live application-specific result for that PID is claimed.
Any existing, accessible PID can be selected in the config; the requested
original Single algorithm and search value still determine whether candidates
are present and whether rank 1 passes its hard filter.

## Integrity

| File | SHA-256 |
| --- | --- |
| `ce_mvp_config.local.lua` (original and packaged) | `6fc037481633d1abc1dd3e0707ebf544b8dd353df61597f8c8c17a697b7b7066` |
| `mvp0_candidate_report.lua` (unchanged) | `2fa9d93ba34ff140aead6e87c1d59a5e149720d894bb0f7bd14267ab10182694` |
| `mvp0_foundlist_collector.lua` (unchanged) | `efc91853c8ed3aa6e8ec059259e5789225747298912fb15dac620a0a1a70e9e4` |
| Final `ce_mvp.local.CT` | `1982ff1fce5f107282b1753a156ccb2fae188cde35d9741d057dfbba6a210c60` |
| Portable ZIP | `225ea8288f2e9070fb2376ccbee183dc668a535b49f1789011df9db62ea997bd` |

## Files changed for this delivery

Modified active sources/documentation:

- `.gitignore`
- `README.md`
- `docs/ce_mvp_quickstart.md`
- `src/ce_mvp.lua`
- `src/ce_mvp.CT`
- `src/ce_mvp_config.example.lua`
- `src/prepare_ce_mvp.py`

Added/replaced product tests:

- `tests/test_ce_mvp_native.py`
- `tests/fixtures/ce_mvp_product_mock.lua`
- `tests/ce_mvp_native_smoke.py`

Historical snapshot of the superseded intermediate implementation:

- `history/ce-mvp-engineering/README.md`
- `history/ce-mvp-engineering/src/ce_mvp.lua`
- `history/ce-mvp-engineering/src/ce_mvp_core.lua`
- `history/ce-mvp-engineering/src/ce_mvp_adapter.lua`
- `history/ce-mvp-engineering/src/ce_mvp.CT`
- `history/ce-mvp-engineering/src/ce_mvp_config.example.lua`
- `history/ce-mvp-engineering/src/prepare_ce_mvp.py`
- `history/ce-mvp-engineering/tests/test_ce_mvp_native.py`

Delivery reports:

- `reports/2026-11-26/ce-native-id1-delivery.md` (superseded pointer)
- `reports/2026-11-27/ce-native-id1-delivery.md` (this report)

Generated local-only files include `src/ce_mvp.local.CT`, the original-table
backup, test scratch/evidence and the portable package plus its integrity
manifest. The package contains a byte-preserved copy of the private config and
is explicitly ignored. Runtime logs are not included in the proposed change.
The original algorithm files, local config and unrelated pre-existing changes
are preserved. The old core/adapter and read-only test files have no content diff.

## Commit and version advice

Suggested commit: `feat(mvp0): deliver standalone native ID1 scan and value maintenance`

No new version tag recommended. This is a temporary delivery branch with scoped
native verification, not a new repository-wide release checkpoint.

## Limits

Validation covers the independent product and the unchanged algorithms. Old
engineering/qualification entrypoint tests target the retired interface and were
not migrated or used as product acceptance. No claim of a passing repository-wide
engineering suite is made. The product does not load those interfaces.

Scan/ranking stops on the configured timeout without writing partial results.
Periodic checking observes changes at CE timer ticks; it is not continuous
memory monitoring. A stopped run requires a deliberate new ID1 Start.
