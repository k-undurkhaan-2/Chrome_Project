# H3-A7 CE-native closed-loop MVP contract

Delivery status: **IMPLEMENTED_PENDING_CE_QUALIFICATION**. Synthetic execution
is not CE integration acceptance. No live operation or production authorization
was granted by the implementation task.

## Runtime and integration

The runtime is Windows **x64 Cheat Engine 7.6, embedded Lua 5.3**. Prepare with
`src/prepare_ce_mvp.py`, load the generated private `src/ce_mvp.local.CT`,
then deliberately enable its Start record after saving
`src/ce_mvp_config.local.lua`. Merely loading/inspecting the table does not load
the runtime, read the config, attach, scan or write. Its AA syntax-check pass is
also inert. The equivalent Lua entrypoint is `dofile(.../ce_mvp.lua).start()`.
The module returns a singleton with `start()`, `stop()`, and `status()`.

The implementation consists of a dependency-injected state machine, a CE/Win32
adapter, an inert loader, a data-only local configuration, and the CT controls.
There is no Python/PowerShell companion, product CLI, standalone GUI, approval
console, or installer. Python is used only in development and in the separately
authorized disposable **test target**.

Inspection of the actual local repository established:

- `execute_module-v5.2.0_batch.lua` Single dispatch calls
  `MVP0FoundList.run` once with `probe_full_foundlist=false`. It consumes an
  **existing** current MemScan/FoundList; it does not create the initial scan.
- `mvp0_foundlist_collector.lua` and `mvp0_candidate_report.lua` perform real CE
  reads, exact-pattern filtering, structural scoring, family adjustments,
  ranking and recommendation. Those unchanged modules run in a private Lua
  environment using the new adapter's owned scan and guarded read functions.
- `mvp0_value_executor.lua` is the existing Full/arm/restore-oriented guarded
  executor. Single does not call it. A7 does not fabricate Full A/W/B evidence,
  modify that executor, or relax the legacy runner's detect-only policy.
- The handoff write/restore protocols are synthetic-only. A7 never dispatches
  them. Its one Float32 write and immediate readback use CE's actual APIs.

## State and ownership

```text
STOPPED -> ATTACHING -> SCREENING -> CANDIDATE_CHECK -> WRITING
                                                      |
                                                      v
                                                  READBACK -> MONITORING
SCREENING (zero candidates) -> RESCAN_BACKOFF -> SCREENING
MONITORING (confirmed invalidity, same instance) -> RESCAN_BACKOFF -> SCREENING
any running state -> STOPPED (operator) / ERROR (terminal failure)
```

One disabled-then-enabled 50 ms CE timer drives the run. Start on a running
instance returns `false, ALREADY_RUNNING`. No nested or overlapping scans or
writes are started. Recursive timer entry is terminal. A scan's `OnScanDone`
only marks completion; the next timer callback collects results. There is no
busy loop or `waitTillDone` call. Collection yields every 16 read primitives;
scoring and the independent uniqueness check yield for each legacy bounded
candidate. Bounded-mode ranking/report work remains limited to 128 candidates.
Process mode instead uses cooperative complete-population passes described below.
The configured timeout includes scanning and all cooperative processing.

Stop first marks the run inactive and revokes further guarded operations,
disables/destroys its timer, removes its scan callback, releases FoundLists,
destroys its own MemScan, and closes only its own query handle and CE-local
scratch stream. Stop is idempotent. Late callbacks cannot revive the run.
The CE MemScan destructor cancels/joins native scan workers; **native cleanup
can briefly block the UI**. There is no measured CE cancellation-latency claim.
This latency and event disposal must be checked in live qualification. Failed
cleanup is sticky: a new Start is blocked until CE is reloaded. Resources with
uncertain disposal are not blindly closed a second time.

An ordinary terminal error with confirmed cleanup can be followed by a new,
deliberate Start, which reloads the saved configuration and binds a new run.
There is no automatic restart after an error or PID exit, and no automatic
restore/rollback after a possibly partial write.

## Process binding

Only the configured numeric PID is opened. Before CE attachment, the adapter
holds an independent Win32 `OpenProcess` handle with query/synchronize rights
(`0x101400`). `GetProcessId`, `GetProcessTimes` creation FILETIME, and
`WaitForSingleObject(handle, 0)` establish its sampled identity/liveness.
`openProcess(pid)` then selects CE's target. Both the held query handle and the
handle returned by `getOpenedProcessHandle()` must report the same PID and
creation FILETIME and must be unsignaled. The CE-reported handle value is
retained. PID and handle selection are checked again around those observations.

This check runs on every timer tick and immediately before each adapter memory
primitive (including collector reads, prewrite, write and readback). A stale
`getOpenedProcessID()` alone never establishes liveness. Exit, changed creation
time, different CE PID/handle, failed query, or uncertain native results cause
an error with no subsequent write/retry. GetTickCount64 supplies a monotonic
clock; invalid/backwards observations stop the run.

Win32 calls execute **locally inside CE** through `executeCodeLocalEx` and local
kernel32 exports. Output buffers belong to a CE MemoryStream. There is no
target-code injection, DLL installation, process-name discovery, termination
of another process, or closure of CE's borrowed handle. Missing APIs, unsupported
CE/version/architecture, and unavailable ordinary Win32 handles reject explicitly;
there is no driver/pseudo-handle fallback.

This is a CE-local consistency check, not independently measured kernel-object
equality, hostile-plugin isolation, or an atomic lock on CE's global target.
Selection/exit/memory races between checks and native operations, unobserved
switch-away-and-back, and memory reuse with an indistinguishable fingerprint
cannot be ruled out. The original process instance is bound **at Start**, not
at config-save time. The operator must ensure the saved PID still names the
intended owned process when starting. Status retains
`ATTACHMENT_HANDLE_UNVERIFIED` and `NOT_PRODUCTION_AUTHORIZED`.

## Single candidate policy

The adapter creates its own asynchronous exact **Dword bit-pattern** discovery
scan with `soExactValue`, hexadecimal input, four-byte alignment and `+W-X-C`.
This finds the exact four bytes of the configured Float32 without CE's decimal
Float scan rounding window. Interpretation, structural qualification, write and
readback are exclusively Float32. Discovery does not permit a Dword write.

Process scope is the default when both address fields are absent. After the
original PID/creation-time identity guard, local `GetSystemInfo` supplies the
x64 user-mode envelope. The adapter validates the AMD64 48-byte `SYSTEM_INFO`
layout (architecture/page at 0/4, 64-bit minimum/maximum pointers at 8/16,
allocation granularity at 40), conventional 4 KiB pages and 64 KiB granularity,
ordered bounds and the supported 47-bit user address ceiling. Output markers
detect missing output from the void API. Unsupported layouts/bounds fail closed.
The existing CE-local native-call bridge and scratch stream are reused; no
target code, new privileges or process-name discovery is involved.

Process mode explicitly overrides the owned MemScan's memory-type policy to
private only (`MEM_PRIVATE=true`, image/mapped=false). Bounds selection and
region eligibility are separate: only readable/writable non-executable private
mappings supported by CE's `+W-X-C` policy and four-byte alignment are searched.
Inaccessible or unaligned values are outside this declared scope. Every selected
context must still fit one committed private `PAGE_READWRITE` region. Address
and mapping arithmetic reject overflow. CE-native coverage remains unqualified.

`mode='bounded'` accepts explicit bounds for fixtures/diagnostics. Legacy paired
bounds with no mode retain their bounded meaning. Partial bounds, process mode
combined with bounds, and unknown modes fail config validation before attachment.
Status/evidence expose resolved bounds, source, policies, alignment and
`scope_complete`; resolving the envelope never asserts successful collection.

In legacy bounded mode, FoundList count must agree with scan progress/results
and fit the configured budget (1..128). `max_candidates` must equal `scan_budget`.
The collector receives all matches, exact target pattern/float, target filtering
and prescore selection enabled, no known-true address, no truth probe, and no
Full/stable-intersection claim. More matches than the budget, incomplete scan
progress, truncated collection, or failed reads are errors. The adapter never
silently samples a smaller universe to claim uniqueness. Process mode uses the
complete-population path below; legacy quota values do not limit that path.

The real collector and ranker must produce an `ACCEPT`, no-manual-review best
candidate. Additionally, exactly **one** member of the entire filtered/ranked
population must independently obtain the existing ranker's `ACCEPT` with a
hard pass when scored alone. This prevents family penalties or address tie
breakers from masking two structurally acceptable objects. More than one such
object is `AMBIGUOUS_CANDIDATES`. A nonempty but unqualified population stops;
only an empty population uses the bounded retry policy.

### Complete process population and equivalence contract

Legacy collector inventory: `collect_raw_foundlist_addresses` visits all indices
only when its budget covers `FoundList.Count`; otherwise it allocates even,
structural and neighborhood quotas (70/15/15), with scout/signature limits.
Deduplication then removes repeated addresses. Exact-pattern filtering permits
retry/delayed rechecks. Prescore selection can apply score ordering, per-region
diversity and a selected cap. Its `raw_count` is the native total,
`scanned_count` the admitted raw entries, `filtered_count` the surviving exact
matches and `selected_count` the downstream subset. The old CE bounded adapter
requires scanned=raw and selected=filtered. Those modules' legacy collection
and command flows are unchanged by P2-B.

The process adapter bypasses those admission/selection quotas entirely. It
uses the same `build_candidate`, `score_candidate`, independent one-row
`rank_candidates`/`recommend_action`, family-key builder, rank adjustments,
lexicographic comparator and recommendation thresholds. Both legacy collector
and report modules remain byte-for-byte unchanged. The adapter merges their
one-row family contexts and uses the ranker's exact gap/confidence formula with
its configured thresholds; differential tests compare the resulting summary.

For a stationary, readable population of unique exact-pattern addresses with
valid mapping/context, the process result must equal the legacy collector with
both budgets covering the entire population: identical independent qualifier
count, global best/second, best score/family size, score gap, confidence and
recommendation. No hard-pass or nonwinning row may be removed from the global
family counts. This contract is checked against the real full collector/ranker
for weak, clone, mixed and late-unique populations, including >1,000 entries
and reversed native order, in both Lua 5.3 and 5.4.

Pass one visits every native index, rejects duplicates/gaps, double-checks the
seven structural words, exact search bits/Float32 interpretation and mapping,
then retains a compact candidate snapshot. It counts independent hard-pass
ACCEPTs and accumulates family counts/metadata for every row. The family metadata
fields used by adjustments are encoded in their clone-family key, so incremental
aggregation is equivalent to the array context regardless of input order.

Pass two verifies every index/address and snapshot again, computes fresh local
scores, and applies the complete global context. The comparator defines a total
lexicographic order ending in the unique value address. Maintaining its exact
first and second rows is therefore equivalent to full sorting for the decision;
it is not a per-chunk winner heuristic. The rank summary computes the same
confidence/gap and the unchanged recommendation runs only after all rows have
been evaluated. Independent qualifiers >1 are always ambiguous, regardless of
clone penalties, score ties or their positions in different chunks.

The owned native scan must signal completion, and progress must agree exactly
with its total and FoundList count before, between and after both passes. Counts
and addresses are rechecked; no failed read, invalid mapping, drift or dropped
entry is filtered away to manufacture uniqueness. These cases now reject the
entire process decision. This is deliberately stricter than legacy mismatch
retries, not an equivalence claim for changing/unreadable data. Final candidate
mapping, fields, search bits and original process identity are still checked
before the one write and exact readback. Sampling live memory is not atomic:
undetected changes between observations remain part of the existing race limits.

Resources are explicit: `process_candidate_limit` defaults to and cannot exceed
8192 compact snapshots; it can be lowered to 1. Family tables and duplicate
tracking are bounded by that same count. Only one transient score plus the best
two adjusted rows are needed, with no full scored array, sort or report string
for the process pool. Over-limit FoundLists retain their actual raw count and
fail `PROCESS_CANDIDATE_LIMIT_EXCEEDED` before evaluating any subset. A finite
limit is not a completeness guarantee for a larger population.

Processing yields after `process_chunk_candidates` rows (default 8, range 1..32)
or when the sampled elapsed slice reaches `process_slice_ms` (default 10 ms,
range 1..25). Clock checks occur between guarded reads/score steps; one fixed-size
candidate calculation and native calls cannot be preempted. `scan_timeout_ms`
covers discovery and both passes. Cancellation, stale PID, backward clock,
timeout or uncertain cleanup give zero writes. Native UI/cancellation latency
remains unmeasured. Process-only knobs reject in bounded mode, whose 128-entry
budget/telemetry contract is preserved.

Read-only status exposes native raw count, collected/evaluated/independent
qualified counts, processing phase, resource limit and completeness flags.
`scope_complete=true` means the declared population was completely evaluated,
not that it was accepted or authorized for production. A completed ambiguity or
rejection still writes nothing; incomplete/resource-limited work never claims
complete coverage. Native CE coverage/acceptance remains pending qualification.

The chosen value address must be aligned and its whole `-0x20..+0x53` context
must lie inside the configured range and a single committed, private,
PAGE_READWRITE region. VirtualQueryEx checks mapping attributes on the held
query handle. The snapshot includes the seven existing fields `f08`, `f18`,
`f20`, `f58`, `f68`, `f70`, `f78`; it excludes the mutable value at `f28`.
Prewrite checks require the mapping and all seven fields to match and the value
bits still to equal the configured discovery pattern. A failed prewrite check
stops without a write; it is not converted into a relocation retry.

These are conservative structural heuristics. They cannot prove application
semantics or that a particular real Chrome object is the operator's intended
value. The reusable Single profile may return REVIEW for plausible objects;
the adapter does not change thresholds to force an ACCEPT. The disposable test
layout deliberately satisfies the unchanged rules and proves mechanics only.

## Float32 transaction and monitoring

Both search and write values must be finite Lua numbers. `string.pack('<f', v)`
rounds once to the embedded runtime's binary32 representation, then unpacking
produces the actual write value and exact unsigned 32-bit pattern. Ordinary
IEEE rounding is nearest/ties-to-even; the **actual packed bits are authoritative**.
Overflow to infinity is rejected; subnormal rounding/underflow and signed zero
are retained. Search float and explicit pattern must agree after rounding.

There is exactly one `writeFloat(address, rounded_value)` attempt per selected
candidate. Only the Boolean `true` counts as API success. In the same timer
callback, the adapter reads `readInteger` bits and `readFloat`. Both must
reproduce the exact requested binary32 bits. There is **zero epsilon tolerance**.
Nil, exceptions, false/non-Boolean write results and readback disagreement are
terminal. `write_count` counts attempted writes, not verified successes. Status
retains the attempted address/value and any returned readback for diagnosis.

At each configured monitoring interval the address must remain in the same
region/allocation, all seven non-value fields must be identical/readable, and
the value must remain readable finite Float32. A finite numeric change alone
does **not** trigger a rescan, rewrite, or freeze. A failed predicate increments
a consecutive-invalid count; a valid observation resets it. At threshold,
identity is revalidated, the old address is permanently retired for this run,
and a fresh discovery/Single/transaction cycle is scheduled. If a retired
address reappears, it is never written again in that run.

Dynamic changes to any fingerprint field can conservatively invalidate a real
object. Freeing/reusing an object inside a still-committed allocation with
identical seven fields is undetectable with this minimal predicate. Relocated
objects must be discoverable by the original configured search value/pattern.

Retries use `max(base * 2^(attempt-1), spacing remaining)` with exponential
growth capped by `max_backoff_ms` (minimum spacing is an independent floor).
`max_rescan_attempts` bounds **all** retries/relocations per Start and is not
reset after success. Exhaustion is terminal; there is no spin/repeated monitor
write. Status history is a bounded ring. Console and optional append log output
are capped per Start, reserving a final line for the stop reason. Explicit
`status()` calls print a current snapshot. A log failure stops the active run;
logging failure during cleanup cannot prevent cleanup.

## Configuration and optional engineering interfaces

All required settings, numeric ranges, unknown keys, Float32 compatibility,
scan completeness and extension settings are checked before attachment. Local
config is loaded with an empty environment, then copied/validated; it has no
ambient CE/process/I/O capabilities. This is operator-owned trusted local Lua
data, not a sandbox for malicious or infinite config code. The ignored real
config is never created or overwritten by the loader. The sample has PID 0
and `write_enabled=false`, so it cannot start.

`engineering_extensions` exposes disabled names `h3_a3_store`,
`h3_a4_approval`, `strict_attachment`. Selecting anything except false returns
`UNSUPPORTED_ENGINEERING_EXTENSION`. A3 storage, A4 signatures/GPG/ACLs and A6
manual witnesses are not MVP dependencies. No A4 review-only result becomes
live authority. The deliberate Start and `write_enabled=true` are the product's
operator initiation, not authorization for Codex to run the separate live test.

## A6/R3 and qualification boundary

The eight pre-existing D2/A6 dirty files and legacy modules were preserved.
An existing external R3 package at
`<temporary-directory>/h3-a6-t1-r3-20261120-01a1f4c2` records cross-version
synthetic readiness with unchanged A6 sources. A7 needs no R3 source repair.
R3's separately authorized live read-only T1 remains a separate handoff, not
an A7 prerequisite. The original R2 command's Lua 5.4 assertion failed before
witness capture; its outcome remains `T1_FAILED_NOT_QUALIFIED`. No old helper
PID, address, witness or authorization is reused.

See [quick start and live matrix](../ce_mvp_quickstart.md) and the dated
[implementation verification](../../reports/2026-11-20/h3_a7_verification.md).
The latter distinguishes actual host Lua 5.3/5.4 results from **NOT_RUN** CE
qualification. Only separately approved, recorded live demonstrations of all
required loop behaviors can change the delivery status to MVP_ACCEPTED.

API references reviewed alongside installed `C:\Program Files\Cheat Engine\celua.txt`:
[opened PID caveat](https://wiki.cheatengine.org/index.php?title=Lua:getOpenedProcessID),
[CE Lua API index](https://github.com/cheat-engine/cheat-engine/blob/master/Cheat%20Engine/bin/celua.txt),
[scan Lua bindings](https://github.com/cheat-engine/cheat-engine/blob/master/Cheat%20Engine/LuaMemscan.pas),
[native scan lifecycle](https://github.com/cheat-engine/cheat-engine/blob/master/Cheat%20Engine/memscan.pas).
Upstream source review is supporting design evidence, not proof of the installed
binary's live behavior.
