# H3-A7-Q1-R1 candidate and future G1 operator plan

This is preparation, **not authorization**. G1 is **NOT AUTHORIZED / NOT RUN**.
Product status remains **IMPLEMENTED_PENDING_CE_QUALIFICATION**. Keep
**ATTACHMENT_HANDLE_UNVERIFIED** and **NOT_PRODUCTION_AUTHORIZED**. A6/R3 T1
is independent and pending; historical R2 remains T1_FAILED_NOT_QUALIFIED.
All L01–L12 live outcomes remain NOT_RUN until separately observed in G1.

The existing Single collector/ranker, acceptance score 30, review score 20,
confidence/hard-pass rules, 128-match policy, closed-loop decisions and CT
controls are unchanged. Diagnostic fields are an optional addition to the
configuration. The loader needs new read-only evidence accessors and must
forward its own Start function for the L10 guard probe; it still does no work
at import. The example still has PID 0, writes off and diagnostics off.

## Disposable fixture and exact layout

The executable is the operator's existing Windows x64 Python running
`tests/ce_mvp_disposable_target.py` and its pure data dependency
`tests/fixtures/ce_mvp_target_layout.py`, both pinned by the R1 manifest.
The latter can be tested without importing the native target. Only `main()`
loads kernel32 or accesses native memory. R1 tests never execute/import it.

After separate approval, launch each fresh instance from the repository:

```powershell
& 'D:\armedforces.io-v2\.venv\Scripts\python.exe' -B 'D:\armedforces.io-v2\tests\ce_mvp_disposable_target.py' 'FRESH_APPROVED_INSTANCE_TOKEN'
```

The token is 1–64 letters/digits/underscore/hyphen. Record the actual command,
executable/script hashes, ready JSON and later exit code in a private local
artifact. This is a foreground operator console, not a background server.
Ready creates `baseline_unique` only after deliberate launch. No CE action is
performed by the helper. Every subsequent mode is selected with a local stdin
command. `status` only observes its current value, and `exit`/EOF releases the
reservation. Unknown/invalid transitions reject without memory changes.

Let B be the fresh 64 KiB reservation. Scan exactly **B..B+0xFFFF**, inclusive;
the value and full context must be inside this range. Pages are 4 KiB, private,
committed PAGE_READWRITE when present; the remainder stays reserved/uncommitted.
No access is made outside this reservation. These are source/layout facts;
native allocation, reads, decommit and release still require G1 observation.

| Command | Controlled layout / operation | Expected CE evidence; tool write cap |
| --- | --- | --- |
| `baseline_unique` | Page 0, value at B+0x128; seven unchanged qualifying markers | Complete count 1, qualified count 1, ACCEPT; initial write 1 |
| `zero_match` | Same complete structure, value 42 instead of 100 | Count 0, bounded NO_CANDIDATE/backoff then RESCAN_LIMIT_EXHAUSTED; 0 |
| `ambiguous` | Independent complete structures at B+0x128 and B+0x2128; pages 0 and 2 | Count 2, independent qualified count 2, AMBIGUOUS_CANDIDATES; 0 |
| `over_limit` | Separate dense page-0 layout: 129 aligned words, B+0x100 through B+0x300 inclusive, each 0x42C80000 | Actual CE FoundList count at least 129, budget rejection, collection/completeness explicitly unproven beyond the guard; 0 |
| `incomplete_structure` | Value at B+0xFD0 in page 0; required +0x30/+0x40/+0x48/+0x50 fields fall in uncommitted page 1 | Count 1; required read failure, SCREENING_READ_FAILED; 0 |
| `invalid_structure` | Complete readable page 0/value 100, all seven markers deliberately zero | Count 1, qualified count 0, CANDIDATE_NOT_QUALIFIED; 0 |
| `value_drift` | Write only the current value's four bytes to 0x42280000; no commit/decommit or marker rewrite | Valid monitoring/value bits 42; no additional scan or write; additional cap 0 |
| `relocate` | Commit next unused page, initialize its valid slot at page+0x128, then decommit the old page in the same process | Old A0 retired; new A1 independently qualifies; exactly one recovery write; additional cap 1 |

The dense overflow layout does not claim 129 qualifying structures; L09 requires
129 **actual search positions**, counted independently by CE. No cap is lowered.
Zero-filled page padding and all declared words are checked in synthetic tests
to exclude unintended 100.0 matches. Incomplete and invalid are distinct:
the former has unreadable required fields; the latter has readable wrong fields.
Neither has a second acceptable candidate. Scan-progress incompleteness is
separately tested synthetically; corrupting native scan progress is not a G1 step.

`drift`, `duplicate`, `reset` remain aliases for value_drift, ambiguous,
baseline_unique. Mode reset decommits the old layout before making fresh zeroed
pages. It must only occur after MVP cleanup; it is not an active-run relocation.
Only value_drift and relocate are permitted while MONITORING. Relocation is
bounded to 15 successive unused pages in the fixture; this G1 plan permits just
**one** relocation. Do not use reset to recycle a retired address in a run.
Do not run a timer-driven or network-driven mode loop.

## Observation schema and collection

Enable the following only in the later approved local configuration; use a
different token for **every Start**, and retain evidence before another Start:

```lua
diagnostics = {
  enabled = true,
  session_token = 'FRESH_APPROVED_START_TOKEN',
  event_limit = 512,
  cleanup_start_probe = false,
},
```

`H3A7_CE_MVP.evidence()` returns a deep-copied Lua table without printing,
clock queries, identity queries or memory operations. For a captured console
transcript use `H3A7_CE_MVP.print_evidence()`. It prints bounded, sorted
key/value lines prefixed `[H3-A7-EVIDENCE]`: retained events first, then a
snapshot. Nested fields are flattened with dots, strings are Lua-quoted and
numbers are exact Lua integer/number values. Bits may print as decimal unsigned
integers: compare numerically with the hexadecimal constants below. This is
not JSON. Status remains compatible, including its existing private raw addresses.

| Fields / event group | Definition and limit of the evidence |
| --- | --- |
| `schema=1`, `session_token`, `source`, `sequence`, `event_type` | CE adapter defaults to `CE`; mocks explicitly use `synthetic`; helper JSON uses `target`. Source labels alone do not authenticate provenance: retain actual runtime/transcript metadata. Sequence is local to one Start. |
| `state_before`, `state_after`, `reason`, `stop_reason` | Actual state changes, explicit rejection/stop/cleanup reasons. `cleanup_complete` precedes the final state-transition event. Expected L09 rejection is not a live failure if its full criteria pass. |
| `relative_ms`, `time_source` | Last already-sampled GetTickCount64 control tick minus first tick. Unavailable before the first tick. Several operations share one tick; this is **not** exact event timing, UTC or cleanup latency. No extra clock calls are introduced. |
| `configured_pid`, `identity.query_token`, `identity.ce_reported_token`, `identity.check_complete` | Tokens are PID:creation-FILETIME-hex, sampled from the held query handle and CE-reported handle using GetProcessId/GetProcessTimes/WaitForSingleObject. Latest check starts incomplete and becomes complete only after both checks/selection checks succeed. Failure never reuses a previous successful sample as current proof. |
| `scan_invocation`, `scan_done_observed`, `scan_progress`, `scan_population*` | Original scan's FoundList.Count and existing progress fields, never a second scan. Count is recorded before the guard. >128 immediately rejects with an explicit unproven-progress/collection reason; telemetry never performs extra progress work to bypass that guard. |
| `candidate_population` | Raw/scanned/filtered/selected counts, collection equality and read-failure flag. Collection count completeness does not assert readable/eligible structures; check `read_failure` and ranking separately. |
| `ranking_summary` | Ranked count, independently qualified count, recommendation, manual-review flag, best score, hard pass and confidence from the unchanged ranker. If read/scan guards stop first, ranking is unavailable, not invented as zero. |
| `write_intent`, `write_api_result`, `readback_result`, `readback_verified` | Intended Float32 bits, actual API success, Integer/Float readback bits and verified bit equality. An API `true` without verified readback is not a verified write. |
| `address_label` | A0, A1 etc., assigned on first observed ranking/validation/write/retirement, reused within one Start. No raw target addresses are placed in the diagnostic event tables. A label is not global across Starts. |
| `valid_value_observed`, `monitor_result`, `address_retired`, `backoff` | Existing read bits, validity result, actual retirement and scheduled delay. Prewrite validity can also produce a value event; only monitor_result counts a monitor iteration. |
| `cleanup_begin`, `timer_disposed`, `scan_dispose_begin`, `scan_disposed`, `query_handle_close`, `local_stream_dispose`, `cleanup_complete` | API calls/returns and aggregate cleanup outcome. Cancellation requested is distinct from successful destructor return and measured native-worker completion/latency. |
| `start_rejected`, `cleanup_start_probe` | Active/cleanup guards and, only for L10, the deliberately rejected public Start at cleanup entry. No delays, replacement state machine, arbitrary script callback or forced write. |
| `dropped_events`, `telemetry_error` | A bounded ring evicts oldest events after event_limit. Capture at each boundary; require zero dropped events and no observation error for this plan. A gap invalidates the affected evidence and stops qualification. |

Counter definitions (all start at zero):

- `adapter_read_calls`: invocations of target `readInteger`/`readFloat`, counted
  immediately before the call, including failed calls. This **does not equal
  OS-level memory reads**; native scanner work and CE-local identity-buffer reads
  are excluded. `adapter_readback_calls` counts readback routine entries.
- `adapter_write_attempts`: actual writeFloat invocations; exceptions still count.
  `adapter_write_successes`: calls returning Boolean true. `verified_writes`:
  both readback primitives reproduce the exact intended Float32 bits.
  Existing core `write_count` means attempted transaction dispatch, not success.
- `adapter_scan_invocations`, `scan_completions`, `scan_cancel_requests`,
  `scan_disposals`: respective native API invocation, observed callback flag,
  disposal request before done, and successfully returned disposal operations.
  Core `scan_count` counts attempts including acquisition failure.
- `identity_checks`, `mapping_queries`, `valid_monitor_checks`,
  `invalid_monitor_checks`, `retirements`, `cleanup_attempts`, `rejected_starts`:
  existing checks/actions and outcomes. Existing `monitor_checks`,
  `invalid_count`, `rescan_attempts` are copied unchanged into every snapshot.

Capture before and after L05: delta monitor_checks >=20, delta
valid_monitor_checks >=20, delta invalid_monitor_checks=0, no gaps or intervening
restart, state stays MONITORING, and **zero deltas** for both scan counters and
both attempted/verified write counters. Wait for completed checks, not merely
20 seconds. For L06 capture a separate boundary, issue value_drift once, observe
at least 3 valid monitor results with 0x42280000, and again no new scan/write.

Helper JSON adds a monotonic sequence/time, actual GetProcessTimes self-query,
UTC observation string, committed pages, reservation size, its own word-write
counter and decommit/release acknowledgement. It explicitly does **not** claim
to count CE writes. Its creation token is corroboration only. CE's independent
query/borrowed-handle samples must agree with it; a separate operator OS query
of that fresh PID must also corroborate the creation FILETIME. Use Windows
Process.StartTime.ToUniversalTime().ToFileTimeUtc() formatted as 16 hex digits,
recording its API/source and actual command, and reject inaccessible identity.
Never use a target-supplied UTC timestamp as process-creation evidence.

Correlate one approved session, per-instance token, per-Start token and command
sequence in a private ledger. Bracket each helper command with CE snapshots and
record operator UTC observations; clocks have different epochs/resolutions.
Do not subtract helper relative time from CE relative time or fabricate precision.
Preserve raw CE status/stdout/addresses only in operator-private `.log` files
(already ignored), outside tracked report text. Use aliases and sanitized
excerpts in reports; no generated `.log` is committed. The absence of a hidden
extra native operation and independent attachment-handle equivalence remain
unproven by API telemetry; maintain ATTACHMENT_HANDLE_UNVERIFIED.

## Frozen G1 configuration and session budgets

Only after explicit approval: launch the approved fixture, verify a fresh PID,
OS creation identity and reported B, and copy the safe example to the ignored
`src/ce_mvp_config.local.lua`. Start with writes disabled. Do not create this
file during R1. Confirm B..B+0xFFFF is exactly 65536 bytes, B and all value
addresses are four-byte aligned, and the target really owns the allocation.
Reject stale PID/address/config, failure to corroborate identity, wrong bitness
or unknown bounds. Never widen the scan or lower the cap to force success.

| Setting | Frozen value |
| --- | --- |
| CE / Lua | CE 7.6 x64; actual embedded `_VERSION` must be observed as Lua 5.3 in G1 |
| Profile / type | single / float32 |
| Search / write / drift | 100.0 = 0x42C80000 / 125.0 = 0x42FA0000 / 42.0 = 0x42280000 |
| Range | Fresh B through B+0xFFFF inclusive, no expansion |
| Discovery / candidate bound | Exact Dword bits of Float32, alignment 4, +W-X-C; scan_budget=max_candidates=128 |
| Filtering | filter_target_match=true; use_prescore_selection=true; existing score/uniqueness rules |
| Monitor / invalidity | 1000 ms; 2 consecutive invalid checks |
| Retry / spacing | base 1000 ms; cap 30000 ms; minimum rescan spacing 2000 ms; max_rescan_attempts=5 total per Start (at most 6 scans) |
| Scan timeout | 120000 ms including collection/ranking |
| Output | log_limit=200; diagnostics event_limit=512; fresh token per Start; optional unique ignored .log |
| Extensions | h3_a3_store=false, h3_a4_approval=false, strict_attachment=false |
| Initiation | write_enabled=false until deliberate approved Start; all negative runs use the same validated machinery and an administrative write ceiling of zero |
| Session | One session, at most 60 minutes from first launch, at most 5 minutes per isolated scenario phase; stop earlier on any uncertainty |

Write ceilings count **attempts**, including failed/partial writes. They are
operator-observed qualification limits, not newly added automatic product
authorization controls. Keep monitoring counters; stop immediately on any
unexpected extra attempt, unexplained read/write, readback mismatch, identity
uncertainty, missing evidence, unexpected error, timeout or cleanup uncertainty.
The product's own existing fail-closed guards remain authoritative. No live
repair, silent retry, elevation, process fallback, additional target or expanded
scope is permitted. If the session cannot fit the window, leave remaining rows
NOT_RUN and seek a new separately scoped session later.

| Session allocation | Instance / Start bounds | Tool write ceiling |
| --- | --- | --- |
| Positive L02–L08 | One fresh source, one Start; initial, 20 stable checks, drift, one relocation, then exit | 2 total: 1 initial + 1 recovery; stable/drift/exit add 0 |
| L09 five negative controls | Five fresh instances, one Start each: zero_match, ambiguous, over_limit, incomplete_structure, invalid_structure | 0 for every negative |
| L10 | One fresh instance, two Starts: baseline before Stop, then zero_match after confirmed cleanup | 1 first Start; 0 second Start |
| L11 | Two explicitly approved fresh instances; source zero_match, destination baseline_unique; one source Start only | 0 source + 0 destination |
| L01 / L12 | L01 inert loading; L12 two deliberate invalid/disabled Start attempts using L10's still-live verified PID, before its exit | 0 |
| Aggregate | At most 9 target instances; only L11 may have 2 alive concurrently; at most 9 successful Start calls and 2 rejected L12 attempts, plus specifically rejected L10 guard probes | **3 attempts total across the session**, never more than each row's ceiling |

Expected automatic zero-match retries are included in the existing five-retry
budget. No retry of a failed qualification scenario or unplanned fixture reset
is approved by this draft. Preserve all evidence before starting the next run.

## L01 controlled load observation

This fixture-level guard is additional G1 test equipment, disabled by default;
it has no target action and must be removed before any deliberate Start.
It counts attempted calls to the actual CE Lua API surface and rejects any
attempt before forwarding it. This is distinct from native OS operation counts.
Use a fresh CE session with no other Lua scripts or concurrent target controls.

1. Record actual CE version/bitness and `_VERSION`. With MVP not started, run:

   ```lua
   L01_guard=dofile([[D:\armedforces.io-v2\tests\fixtures\ce_mvp_prestart_guard.lua]]).new(_G)
   L01_guard.install()
   ```

2. Load the CT without enabling Start. Evaluate `dofile([[D:\armedforces.io-v2\src\ce_mvp.lua]])`
   only to import it. Perform CE's AA syntax checks; each Lua block has its
   syntaxcheck early return. Do not enable Start as a substitute for syntax checking.
3. Print/capture all attempted-call counters:

   ```lua
   local s=L01_guard.snapshot()
   print('L01 source=' .. s.source .. ' installed=' .. tostring(s.installed))
   for k,v in pairs(s.attempted_calls) do print('L01 attempted_' .. k .. '=' .. v) end
   L01_guard.restore()
   print('L01 guard_installed=' .. tostring(L01_guard.snapshot().installed))
   ```

All eight counters must be zero, guard restoration must succeed, and MVP remains
STOPPED. Unexpected calls or changed wrapper ownership fail the observation and
stop the session; preserve the output. These counters cover the MVP's API surface,
not arbitrary unrelated CE plugins or OS activity. Import-inert source and the
actual guard trace support L01 together; synthetic output is not live evidence.

## L10 controlled cleanup and repeated Start

1. Fresh baseline instance/config, diagnostics enabled and
   `cleanup_start_probe=true` for this first Start only. Wait for one verified
   initial write/MONITORING. Capture status and evidence.
2. Call `H3A7_CE_MVP.start()` once while active. Require false/ALREADY_RUNNING,
   one start_rejected event and no extra scanner/timer/write.
3. Call Stop once. The opt-in one-shot probe invokes the **public loader Start**
   synchronously after running=false/cleanup_pending=true and before resource
   disposal. Require false/CLEANUP_IN_PROGRESS in start_rejected and
   cleanup_start_probe, call_ok=true, accepted=false. This tests the actual guard
   at the cleanup boundary; it does **not** simulate UI responsiveness or force
   native cleanup to block. No sleeps, monkeypatches or arbitrary callbacks.
4. Require successful timer destruction, query-handle close, local-stream
   disposal and cleanup_complete/cleanup_ok=true. If a scan existed, require its
   disposal return as well. Keep native cancellation latency supplementary.
   Capture a second Stop and >=3 monitor intervals with unchanged reads/scans/
   writes/monitor counters; evidence snapshots themselves are read-only.
5. Only after full cleanup, set helper `zero_match`, set a fresh Start token,
   set cleanup_start_probe=false and save the same approved PID/range again.
   A deliberate new Start must return true and create a fresh run. Observe count
   0/backoff, then Stop before its five-minute bound. Zero writes on this second
   run. Capture cleanup and late counter stability, then perform L12 while this
   helper is still alive. Exit it after L12 and record release/exit status.

If cleanup is uncertain, do not proceed to step 5, patch guards, or reload and
silently retry. Stop qualification. Manual clicking alone cannot reliably target
a synchronous cleanup interval; the bounded probe supplies that precise control.

## L11 controlled CE target switch

This requires **two** explicitly approved disposable helper instances, with
separate PID/creation tokens and reservations. The source is zero_match, so no
write is possible through a qualified candidate. The destination is a fresh
baseline helper, used only as the controlled mismatch. Its own initialization
is allowed; the MVP has zero read/write/scan allowance to it.

Start only the source. Capture a completed zero-count scan and backoff/active
state. Do not start another MVP or change its saved configuration. Through CE's
normal process selection, deliberately select the exact second approved PID.
Record its actual PID/instance evidence independently. On the next guarded
operation require CE_TARGET_CHANGED, cleanup and **no new MVP target-read,
write or scan call after the switch**. Compare before/after counters and preserve
both helpers' status; destination stays 100.0/0x42C80000. No auto-attachment back
to the source is allowed. Stop, wait >=3 intervals, capture unchanged counters,
and exit both helpers. No unrelated process may be selected. Selection itself
is CE UI activity and is not mislabeled as an MVP adapter memory primitive.

## L12 rejected configuration

After L10 complete cleanup and before its helper exit, retain that verified
PID/range. Reinstall the L01 guard while fully stopped (its counters reset).
Save write_enabled=false; deliberate Start must return WRITE_DISABLED
without new native activity. Then save writes true but scan_budget=129 (the
intentionally invalid setting, used only for this validation rejection); require
INVALID_SCAN_SETTINGS without adapter construction. Capture startup errors,
all eight guard counters at zero, and before/after retained evidence with no
read/scan/write counter changes. Restore the guard and verify it is removed. This
does not count as L09 overflow coverage. Restore the safe local disabled state
afterward. A failed Start may leave the previous run's evidence in the singleton;
label it as retained prior evidence, never a fresh invalid-run telemetry trace.

## Draft separate approval scope — NOT APPROVED

Complete every placeholder only after reviewing the frozen candidate manifest:

> APPROVE_H3_A7_Q1_DISPOSABLE_CE_LIVE_TEST — one-time session only. I control
> the nine-or-fewer disposable instances of `<absolute Python executable + SHA256>`
> running `<target script + SHA256>` with `<layout module + SHA256>`, under
> `<R1 manifest path + SHA256>`. I authorize launching the pinned CE 7.6 x64
> executable and these targets, observing actual Lua 5.3, the L01 API guard,
> opt-in CE diagnostics and L10 one-shot rejected cleanup Start probe. After
> fresh PID/OS creation identity/allocation verification, I authorize the MVP's
> scans/reads and Float32 100.0→125.0 writes only within each source's exact
> 64 KiB B..B+0xFFFF reservation using this plan's frozen settings. I authorize
> the target's local mode/initialization/drift/decommit/release commands. Caps:
> positive 2 attempts, L10 first Start 1, all remaining phases and both L11
> targets 0, aggregate 3 attempts, at most 9 successful Starts plus the named
> rejected controls. L11 may select only its explicitly approved second owned
> target. Session starts `<UTC>` and ends `<UTC, at most 60 minutes later>`,
> each isolated phase at most 5 minutes. Evidence destination is `<private
> ignored local .log paths and sanitized report directory>`. Unexpected extra
> writes, identity uncertainty, unproven counts, wrong values/targets, missing
> evidence, unexpected error, time limit or cleanup uncertainty require immediate
> Stop and preserved evidence; no retries/patches/expanded range/elevation.
> No staging, commit, push, tag, production use or A6/R3 qualification is authorized.

The token alone, this document, a synthetic PASS, or an existing config is not
approval. No actual PID/address or enabled private config is prepared in R1.
After approval, fresh target identity/allocation records complete the scope;
they are observations constrained by it, not permission to substitute a target.
