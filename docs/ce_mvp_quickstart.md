# CE-native MVP quick start

Status: **IMPLEMENTED_PENDING_CE_QUALIFICATION**. The code and synthetic tests
are delivered. Real CE 7.6 attachment, writes, readback and relocation have
**not** been tested by this task. P4-R1 implements the maintainer's Option A:
NORMAL result readiness without independent native terminal-success proof.
The short operator test below uses a fresh owned disposable fixture. Do not use a production
target or any historical PID/address from earlier A6 attempts.

## Configure once

Use **Windows x64 Cheat Engine 7.6 with Lua 5.3**. The checkout can live in any
chosen installation directory. Keep the shipped `src` files together; the Lua
module finds its configuration and sibling modules relative to its saved path.

1. Copy `src\ce_mvp_config.example.lua` to `src\ce_mvp_config.local.lua`.
   Keep the local file private: it is ignored by Git and never overwritten by
   the loader. Do not edit the legacy `run_case_config.local.lua` for this tool.
2. Set `target_pid` to the current exact PID of the intended operator-owned
   target. Omit both address fields for automatic process scope. After identity
   checks, the adapter obtains Windows x64 user-mode bounds from `GetSystemInfo`.
   Missing or uncertain OS bounds stop the run; there is no guessed fallback.
3. Set `scan.target_value_float` and its matching `target_value_pattern` to the
   value used to discover new objects. Set `write_value` to the intended finite
   Float32. The example `100.0 / 0x42C80000 -> 125.0 / 0x42FA0000` is a test
   example, not an instruction to use those values on a real application.
4. Leave `screening_profile='single'`, `value_type='float32'`, both filter and
   prescore flags true, and all engineering extensions false. The example's
   Original Single defaults are `scan_budget=2000` for raw admission and
   `max_candidates=20` for final ranking, in both scope modes. CE's original
   FoundList is not capped at either number. These are independent algorithm
   budgets; the original Scope's valid ACCEPT can authorize a scoped write after
   reduction. Reduced coverage does not prove global uniqueness.
5. Adjust monitoring/retry limits if needed. `max_rescan_attempts` is the total
   retry/relocation budget for that Start. After obtaining the applicable target
   authorization, deliberately set `write_enabled=true` and save.

The shipped sample uses PID 0 and disables writes. It is intentionally rejected
before attachment. Numbers such as 0.1 round once to their binary32 representation;
the actual written/read-back bits are shown in status. Readback requires exact
bits, with no epsilon tolerance. Search float/pattern disagreement is rejected.

Automatic scope uses the owned MemScan's `setSpecialScanOptionsOverride` for
`MEM_PRIVATE=true`, `MEM_IMAGE=false`, `MEM_MAPPED=false`, plus `+W-X-C` and
four-byte alignment. It covers eligible readable/writable, non-executable
private mappings supported by CE's scan policy, not inaccessible or unaligned
addresses. Selection additionally requires a whole `-0x20..+0x53` context in one
committed `PAGE_READWRITE` mapping. Unknown bounds, observed API failures and
collection/integrity failures cannot authorize a write. Designed legacy admission/ranking
reduction is allowed. Native scan completeness remains unverified in NORMAL.

For a disposable fixture or advanced diagnostics, explicitly opt into a range:

```lua
-- Inside scan (keep the search/filter/budget settings):
mode = 'bounded',
start_address = '0x100000',
stop_address = '0x10FFFF',
```

These addresses are synthetic examples only. Existing configs with both legacy
address fields keep their historical bounded meaning even without `mode`.
One missing bound, `mode='process'` with bounds, an invalid mode, or an invalid
range is rejected before attachment. No manual bounds means process mode.

Every discovery cycle creates a new native MemScan and obtains that scan's own
FoundList after its completion callback. No manual New Scan / First Scan button or supplied
address list is needed. The unchanged legacy collector consumes that same
FoundList, including its actual Count and zero-based indices. Native counts
19,276, 20,000, 30,000 and above are allowed; there is no 128/8192 raw-hit cap.

**NORMAL result readiness (P4-R1, Option A):** the current owned scan's
`OnScanDone`, initialization of its own FoundList without an observed failure,
and the existing Count/index/address integrity checks allow the unchanged Legacy
Single Filter to consume the available native view. A stable count before that
callback is insufficient. NORMAL no longer requires strict worker-counter
equality or a new native terminal-success interface to select a scoped ACCEPT.

**Native completion limitation:** `OnScanDone` and an initialized FoundList
do not independently prove successful, complete scanning. CE can release worker
threads before the final callback. Its `getProgress()` can then retain a positive
`TotalAddressesToScan` while returning zero `CurrentlyScanned` and `ResultsFound`.
Those transient counters must not be relabeled as the final FoundList count.
NORMAL can now use this result with `result_ready=true`, `scan_complete=false`
and `global_uniqueness_proven=false`. Raw progress values stay unchanged.

The public [controller implementation](https://github.com/cheat-engine/cheat-engine/blob/ec45d5f47f92a239ba0bf51ec5d04a7509c3fd37/Cheat%20Engine/memscan.pas#L7642)
also reaches the final callback on error paths. Its Pascal error methods are
not exported by the [Lua binding](https://github.com/cheat-engine/cheat-engine/blob/ec45d5f47f92a239ba0bf51ec5d04a7509c3fd37/Cheat%20Engine/LuaMemscan.pas#L296),
and the 7.6 bundled Lua documentation does not specify a terminal success/error
accessor. This public revision is mechanism evidence, not verified source for
the installed 7.6 binary. A stable Count/address list cannot rule out a valid
partial result; zero Count cannot distinguish an empty scan from failed result
initialization. `waitTillDone()` adds no documented success status and is not
used as a blocking workaround.

The existing strict counter rule still computes `scan_complete`: a positive
integer total, equal scanned total and ResultsFound equal to native Count.
QUALIFICATION still blocks on `SCAN_COMPLETION_UNCERTAIN` when it fails. A default
`0/0/0` snapshot never proves completion. In NORMAL, an initialized zero-hit
view selects no write and follows the existing bounded no-candidate retry policy.
`result_ready` does not set strict completion/qualification fields true. The
historical `scan_population_complete` event now explicitly carries both booleans
and a reason; its event name alone is not a completion claim.

Stop, stale/wrong callbacks, identity changes, timeouts, API exceptions, unstable
or invalid FoundList data, failed reads, malformed ranking and uncertain cleanup
still prevent writing. Explicitly observed failures are terminal, without an
automatic failed-operation retry. The public API ambiguity for otherwise usable
partial/error results is accepted for this limited NORMAL mode and remains
unresolved. Stronger native success/error/cancellation attestation and formal
qualification are deferred; QSG is not required for NORMAL execution.

`scan_budget` (1..65536, default 2000) controls legacy raw admission;
`max_candidates` (1..128, default 20, no greater than scan_budget) controls final
ranking/report size. Legacy even/structure/neighborhood admission, exact-value
filter/retry, prescoring, regional diversity and family ranking are preserved.
The example retains the collector's defaults. **P2-R2 REV1 uses the original
Scope's ACCEPT for NORMAL product writing**, including sampled/reduced results.
The actual ranked best must have `hard_pass=true`, an ACCEPT recommendation and
`manual_review_required=false`, with consistent result/candidate fields. REJECT,
REVIEW, malformed results and failed integrity checks permit zero writes. The
diagnostic one-row qualifier count does not veto the original Scope decision.
The same explicit write gate, PID/creation identity, mapping, structural and
original-value checks, retired-address guard and exact Float32 readback apply.

A 30k native pool can therefore produce one scoped write with the default
2,000 admission / 20 ranking budgets. Evidence retains the actual counts,
`coverage='sampled_or_reduced'`, `global_uniqueness_proven=false` and
`write_admission_basis='LEGACY_SCOPE_ACCEPT'`. Selection is order-sensitive and
does not establish uniqueness outside the Scope's evaluated population. The
separately injected QSG QUALIFICATION mode keeps its full-coverage and exactly
one independent qualifier requirements, including `INCOMPLETE_CANDIDATE_POPULATION`
for reduced coverage; its qualification contract is unchanged.

`collection_batch_size=256` (16..2048 checkpoints) and
`collection_slice_ms=10` (1..25 ms) bound cooperative work between address/read/
score operations. Both settings work in either scope. The native scan and all
collection/ranking share `scan_timeout_ms`. Native calls and Lua sorting/report
steps are not preemptible; their input sizes are bounded by the admission and
ranking budgets. Native timing remains unqualified. Removed old P2
`process_candidate_limit`, `process_chunk_candidates` and `process_slice_ms`
settings reject explicitly; use the independent legacy intake settings above.

Search mode is **Float32 exact bits through hexadecimal vtDword**:
Float32 100.0 packs to `42C80000`, whereas CE's UI "4 Bytes, decimal 100" searches
`00000064`. They are different searches. Literal integer mode is not implemented.
The adapter verifies the packed float/pattern agreement, uses hexadecimal input,
and writes/reads back Float32 only. The CE API parameter definitions are documented
in the [MemScan reference](https://wiki.cheatengine.org/index.php?title=Lua:Class:MemScan).

## Prepare the local table (offline)

From the checkout root, run this once with Python 3.10 or later:

```powershell
py -3 .\src\prepare_ce_mvp.py
```

Or invoke the script by its full path from any working directory. For the
current checkout, an equivalent command is:

```powershell
py -3 'D:\armedforces.io-v2\src\prepare_ce_mvp.py'
```

This standard-library-only helper creates `src\ce_mvp.local.CT`, containing the
absolute path of its sibling `ce_mvp.lua`. It checks that all five required Lua
modules exist. It never reads, creates or changes the private config, launches
CE or a target, or enables writes. Repeating preparation produces the same bytes
at the same location. Python is only needed for this offline preparation.

`src\ce_mvp.CT` is the versioned template. Its Start deliberately fails with
`CE_MVP_TABLE_NOT_PREPARED`; open the generated **local** table instead. The exact
local output filename is ignored by Git, like `ce_mvp_config.local.lua`. Do not
commit or distribute this machine-specific generated table.

After moving/copying the checkout, run the helper **at the new location** and load
the newly generated CT. The old generated CT still names its old installation;
it does not follow moves. Stop and close the old CE session before switching
installations. `CE_MVP_DIFFERENT_INSTALLATION_RELOAD_CE` prevents Start from
silently using an already loaded singleton from another directory. Missing files
fail explicitly; there is no current-directory or process-name fallback.

The path is encoded as fixed-width Lua UTF-8 byte escapes, including spaces,
quotes, brackets and XML delimiters. Offline tests cover those encodings and
Unicode path routing. **Native CE Unicode file I/O remains unverified**; if that
CE build cannot open a non-ASCII installation path, use an ASCII directory and
prepare again. This is not a claim of native CE acceptance.

This preparation approach avoids dependence on an unverified CT-directory API.
The upstream [CT path API discussion](https://github.com/cheat-engine/cheat-engine/issues/2276)
records why Open/Save dialog filenames are unreliable after process attachment.

## Load, Start, inspect and Stop

Use **File -> Load** to open `src\ce_mvp.local.CT` from this installation
(`D:\armedforces.io-v2\src\ce_mvp.local.CT` for the command above). Opening the
table and AA syntax checking perform no process/memory operation. After saving
the explicitly authorized local configuration, show CE's Lua Engine output and
enable **H3-A7 Start** once. It attaches to the configured PID automatically,
starts an asynchronous scan, applies the existing Single collector/ranker, writes
the Scope's accepted best candidate once, verifies it, and monitors. No Python companion
or manual initial scan is required while CE runs.

Expected state sequence:

```text
ATTACHING -> SCREENING -> CANDIDATE_CHECK -> WRITING -> READBACK -> MONITORING
```

Inspect the current state by toggling the table's **Status** record or executing:

```lua
H3A7_CE_MVP.status()
```

Status includes PID/creation-time identity token, current and last candidate
address, last written/read-back Float32 and bits, scan/write counts, completed
monitor checks, last check time, error, stop reason and cleanup status. Output
also includes `scan_mode`, resolved `scan_start_address` / `scan_stop_address`,
`bounds_source`, `scan_policy`, `candidate_policy`, `alignment_bytes` and
`result_ready`, `scan_complete` and `scope_complete`. A resolved address envelope
or ready result alone is not proof of complete scanning or collection.
These are read-only snapshots with no extra process access. Output
also exposes native `raw_match_count`, `raw_inspected_count` (distinct indices
visited, including scouts), `raw_admitted_count`, `unique_count`, `filtered_count`,
`prescored_count`, `selected_count` and `ranked_count`. `collected_count` aliases
admitted count; `evaluated_count` aliases ranked count. `coverage`,
`raw_admission_complete`, `ranking_complete` and `global_uniqueness_proven`
describe coverage of the available FoundList separately from scan completion. Counts need not
all match because the original filters remain active. Full coverage requires
all raw entries admitted and every surviving filtered candidate ranked. Only
the historical strict scan evidence plus complete coverage, exactly one independent qualifier, a valid ACCEPT and
valid candidate mapping/fields can set `global_uniqueness_proven=true` within
the declared scan scope. This preserves the historical evidence rule, not a new
native terminal-success guarantee. Reset/unavailable progress leaves
`scan_complete`, `scope_complete` and `global_uniqueness_proven` false even if
all available entries were evaluated. NORMAL does not require that proof to select a write.
`decision_scope='LEGACY_SINGLE_SCOPE'` and `write_admission_basis='LEGACY_SCOPE_ACCEPT'`
record scoped admission; the basis starts as `NONE` each cycle. QSG uses
`decision_scope='QSG_FULL_POPULATION'` and `QSG_FULL_POPULATION_UNIQUE_ACCEPT`.
The basis records selection, not transaction success: check verified-write
counters and exact readback too. Both bounded/process `evidence().scan_scope`
snapshots and `candidate_admitted` events expose these claims. Output
uses local nonsecret process identifiers, not signed authorization. The optional
`.log` path is disabled by default; set an absolute path under an existing local
directory if desired. History/output is bounded; status queries remain available.

**Stop immediately** by unchecking the Start record, or with:

```lua
H3A7_CE_MVP.stop()
```

Stop is safe to call repeatedly. It cancels the timer and scanner and closes its
owned resources. Native scan cleanup may briefly delay UI responsiveness; that
latency has not yet been measured in CE. The Start checkbox is an initiation
control, not a live state indicator: after an automatic error it can remain
checked. Check `status()`, uncheck it, correct the cause, then deliberately Start
again. If `cleanup_ok=false`, reload CE before another Start. Do not run other
attach/switching scripts concurrently with this tool.

A valid finite **value drift does not cause another write**. The monitoring
predicate is readable committed private writable memory plus seven unchanged
surrounding structural words. Confirmed loss of that predicate while the original
process lives retires the old address and starts a fresh bounded cycle. A new
object must again have the configured discovery value. PID exit, target switch,
identity uncertainty, ambiguity, write/readback error, timeout, or retry exhaustion
stops the run. There is no automatic rollback or process-name reattachment.

`status().cycle_id` identifies each discovery attempt in the current Start run.
At a fresh attempt, result readiness, all discovery counts, ranking details and uniqueness/coverage
claims are cleared before resolving the scan bounds. `raw_match_count=nil` and
`coverage='pending'` mean no new native result population has been established.
Historical write/readback fields and cumulative counters still describe prior
operations. Scan invocation, population, ranking and disposal diagnostics carry
the cycle ID. An old completion callback cannot complete the new scanner.
The old FoundList and MemScan must be disposed before any fresh First Scan;
a healthy address causes no new discovery cycle or repeated write.

## Common outcomes

| Status/reason | Meaning and next action |
| --- | --- |
| `INVALID_TARGET_PID`, `WRITE_DISABLED`, missing local config | Finish the saved configuration; no attachment occurred. |
| `SCAN_PATTERN_MISMATCH`, `INVALID_SCAN_SETTINGS` | Correct the Float32 bits, range, or independent intake/ranking budgets. |
| `UNSUPPORTED_ENGINEERING_EXTENSION` | This MVP only implements the disabled extension interfaces. Do not substitute an A4 review-only result. |
| `CE_API_MISSING`, `WIN32_API_MISSING`, `REQUIRES_CE_*` | Verify CE 7.6 x64/Lua 5.3 and ordinary Windows process access. There is no fallback to weaker identity checks. |
| `PROCESS_OPEN_FAILED`, `IDENTITY_UNCERTAIN`, `PID_*`, `CE_TARGET_CHANGED` | Stop; confirm the exact intended PID/instance and access. No automated reattachment follows. |
| `INCOMPLETE_CANDIDATE_POPULATION` | QSG QUALIFICATION only: its stricter full-coverage requirement was not met. NORMAL can write a valid scoped ACCEPT with truthful reduced-coverage evidence. |
| `OBSOLETE_PROCESS_BUDGET_USE_LEGACY_INTAKE_SETTINGS` | Remove the old P2 snapshot knobs and review the independent raw-admission/ranking budgets. |
| `FOUNDLIST_COUNT_CHANGED`, `FOUNDLIST_ADDRESS_CHANGED`, `DUPLICATE_FOUND_ADDRESS` | The complete stable candidate pool cannot be established; zero writes. |
| `PROCESS_SCOPE_UNAVAILABLE`, `PROCESS_SCAN_POLICY_UNAVAILABLE` | Windows x64 bounds or the CE scan policy could not be established; zero writes. |
| `CANDIDATE_NOT_QUALIFIED` | Original Scope did not return a hard-pass ACCEPT without manual review. No write follows. |
| `AMBIGUOUS_CANDIDATES` | QSG QUALIFICATION found multiple independent qualifiers. Its stricter contract remains active. |
| `INVALID_RANK_RESULT`, `INVALID_SCOPE_COUNTS`, `CANDIDATE_NOT_SELECTED` | Result shape, stage counts or selected-candidate linkage is inconsistent; zero writes. |
| `SCAN_COMPLETION_UNCERTAIN` | QUALIFICATION lacks its strict completion evidence; no write follows. NORMAL can use a ready FoundList while preserving unverified completion. |
| `SCREENING_READ_FAILED` | A required candidate read failed; no write follows. |
| `CANDIDATE_CHANGED`, `PREWRITE_CANDIDATE_CHANGED` | Value or structure changed after discovery. The transaction was abandoned. |
| `RESCAN_BACKOFF` | Waiting before a retry; identity checks continue. |
| `RESCAN_LIMIT_EXHAUSTED`, `SCAN_TIMEOUT` | The configured bound was reached. Inspect the target before any deliberate restart. |
| `WRITE_FAILED`, `READBACK_MISMATCH` | Memory might have changed. Stop and inspect it; no write retry or automatic restore occurs. |
| `RETIRED_CANDIDATE` | A previously invalidated address reappeared. It will not be reused in the same run. |
| `cleanup_ok=false` | Cleanup is uncertain. Reload CE; do not bypass the singleton/cleanup guard. |

## Minimum NORMAL operator test (P4-R1)

Use only the fresh repository fixture below. This is a limited usability check,
not formal G1 or native scan qualification. Codex does not launch it, attach CE,
or change the private configuration. N0/MIN/LOCAL publication remains paused.

1. From the checkout root, launch the existing fixture in a PowerShell window:

   ```powershell
   & .\.venv\Scripts\python.exe .\tests\ce_mvp_disposable_target.py ('p4r1-' + [guid]::NewGuid().ToString('N'))
   ```

   Keep it open. Its fresh `ready` JSON gives `pid`, `scan_start`, `scan_stop`,
   `reservation_bytes=65536` and initial `100.0 / 0x42C80000`. Use these values,
   never an earlier PID or address.
2. In the private `src\ce_mvp_config.local.lua`, explicitly set that PID,
   `write_enabled=true` and `scan.mode='bounded'` with exactly those fresh
   `scan_start`/`scan_stop` values as `start_address`/`stop_address`.
   Keep search `100.0 / 0x42C80000`, write `125.0`, Single, the default 2000/20
   budgets and disabled engineering extensions. Enable diagnostics with a fresh
   `session_token`, `event_limit=2048`, `cleanup_start_probe=false` if evidence is
   wanted. The fixture range is a controlled diagnostic boundary; ordinary
   `mode='process'` still needs neither Start nor End.
3. In another PowerShell window run
   `& .\.venv\Scripts\python.exe .\src\prepare_ce_mvp.py`.
   Open `src\ce_mvp.local.CT` in CE 7.6 x64, show Lua Engine output and enable
   **H3-A7 Start** once. No manual First Scan is needed. Inspect **Status** and
   `H3A7_CE_MVP.print_evidence()` for native intake, Legacy ranking, an ACCEPT
   best candidate and `MONITORING`. Confirm `scan_count=1`, `write_count=1` and
   exact `last_written_bits=last_readback_bits=0x42FA0000`. In the fixture window,
   enter `status` and independently confirm `125.0 / 0x42FA0000`.
4. Observe increasing `monitor_checks` with scan/write counts still 1. Enter
   `relocate` once in the fixture window. After confirmed invalidation/backoff,
   check `cycle_id=2`, scan/write counts 2, a new address and exact readback;
   fixture `status` must again show 125.0. Healthy ticks must add no writes.
5. Enter `exit` in the fixture. CE must stop with a PID-exit reason,
   `running=false`, `cleanup_ok=true` and no further writes. Uncheck Start.

Report the two value/readback observations, counts, relocation and cleanup.
Only those actual observations can establish minimum native usability. Even a
passing manual test does not prove complete scan populations, reliable native
error detection or formal qualification. Keep `IMPLEMENTED_PENDING_CE_QUALIFICATION`,
`ATTACHMENT_HANDLE_UNVERIFIED`, `NOT_PRODUCTION_AUTHORIZED` and `G1 L01-L12=NOT_RUN`.

## Separate formal CE qualification procedure

**G1 is NOT AUTHORIZED / NOT RUN.** Follow the complete
[R1 fixture, diagnostics, configuration and controlled-session plan](ce_mvp_q1_r1_plan.md)
after new explicit authorization for that formal session. The minimum NORMAL
test above does not execute or replace the full L01–L12 matrix. All twelve
formal live cases remain NOT_RUN.

The frozen qualification candidate supports baseline_unique, zero_match,
ambiguous, over_limit (129 actual aligned Float32 positions in one page),
incomplete_structure, invalid_structure, value_drift and decommit-based relocate.
The target is manual test equipment and never a runtime companion. R1 tests use
its separate pure layout module; they do not import or launch the native target.

For Q1 the scan range is **exactly the fresh target's 64 KiB reservation**;
scan_budget=max_candidates=128. Do not narrow/expand that range or lower the cap
to substitute for the 129-match observation. Search 100.0/0x42C80000, write
125.0/0x42FA0000, drift 42.0/0x42280000. Preserve Single thresholds and all
disabled engineering extensions. The example config is safe by default.

The optional diagnostics setting is disabled by default. For an approved Start,
use a fresh session_token, event_limit=512 and cleanup_start_probe=false except
for the specifically controlled L10 Stop. Inspect or print evidence with:

```lua
H3A7_CE_MVP.evidence()       -- deep copy; no native calls or printing
H3A7_CE_MVP.print_evidence() -- prints event/counter/identity snapshots
```

Evidence contains actual scan counts/completeness, ranking/uniqueness, adapter
read/write/readback counters, sampled process identity, state transitions and
cleanup. adapter_read_calls is **not an OS memory-read count**. Raw status and
helper addresses belong in private ignored .log files; diagnostic events use
A0/A1 labels. Stop qualification on dropped events or an observation error.

L05 requires **at least 20 consecutive completed valid monitor cycles** with no
extra scan/write; elapsed time alone is insufficient. L06 requires a separate
drift observation with no additional scan/write. The positive+relocation run
permits at most two write attempts. L10 permits one initial write, then a
zero-match restart after confirmed cleanup. All five L09 controls, both L11
targets, L01 and L12 permit zero writes; the aggregate session ceiling is three.

L10's one-shot diagnostic probe observes public Start rejection at the real
cleanup boundary without delaying cleanup. L11 requires two separately approved
owned helper instances and never an unrelated process. See the linked plan for
exact steps, finite instance/time limits, private configuration preparation,
the L01 load guard, and the **unapproved** future G1 scope template.

A pre-live readiness result does not qualify CE or authorize production use.
Only actual authorized L01–L12 observations can support Q1 live qualification;
operator acceptance is a separate scoped decision. Keep
ATTACHMENT_HANDLE_UNVERIFIED and NOT_PRODUCTION_AUTHORIZED. A6/R3 T1 remains
independent and pending; historical R2 remains T1_FAILED_NOT_QUALIFIED.

Implementation detail and limits:
[H3-A7 contract](architecture/h3_a7_ce_mvp_contract.md).
Historical automated commands/results:
[original verification record](../reports/2026-11-20/h3_a7_verification.md).
