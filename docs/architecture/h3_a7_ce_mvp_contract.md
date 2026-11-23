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
  ranking and recommendation. Their existing algorithms run in a private Lua
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
busy loop or `waitTillDone` call. Collection checkpoints occur between raw
address accesses, guarded reads and score operations in both scope modes.
Legacy ranking/report work remains bounded to at most 128 selected candidates;
that limit does not cap the native FoundList.
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

In both scope modes, the adapter exposes the entire owned native FoundList to
`MVP0FoundList.run`, with exact target pattern/float, filtering and prescore
selection enabled, no known-true address, no truth probe, and no Full/stable-
intersection claim. Count must agree with completed scan progress. The adapter
never rewrites Count to an intake budget or replaces the underlying scan.
Incomplete admission/ranking is explicitly labelled and cannot authorize a write.

The real collector and ranker must produce an `ACCEPT`, no-manual-review best
candidate. Additionally, exactly **one** member of the entire filtered/ranked
population must independently obtain the existing ranker's `ACCEPT` with a
hard pass when scored alone. This prevents family penalties or address tie
breakers from masking two structurally acceptable objects. More than one such
object is `AMBIGUOUS_CANDIDATES`. A nonempty but unqualified population stops;
only an empty population uses the bounded retry policy.

### R1 native FoundList and unchanged legacy Single semantics

R1 supersedes the earlier P2 custom complete-process scorer and its 8192 native
hit ceiling. The owned asynchronous First Scan uses `soExactValue`, `vtDword`,
hexadecimal `string.pack('<f', x)` bits, `+W-X-C`, `fsmAligned` and alignment 4.
Float32 100.0 is `0x42C80000`, not the `0x00000064` searched by CE's decimal
4-Byte integer 100 UI setting. No implicit integer-search mode is supported.
See the [CE MemScan API](https://wiki.cheatengine.org/index.php?title=Lua:Class:MemScan).

The ranker source remains byte-identical. The collector has one memory-only
compatibility change: its temporary prescore entries no longer retain an unused
complete score tree. All selected keys, flags, candidates and ranking inputs
remain unchanged. Before/after differential tests compare complete nested
results, tie vectors, filtering evidence and report text; a 30,001-entry
prescore regression enforces a fixed 128 MiB Lua ceiling.

`collect_raw_foundlist_addresses`
visits all indices when scan_budget covers Count; otherwise it uses its existing
70/15/15 even/structure/neighborhood quotas and scout/signature constraints.
Deduplication, exact-pattern filtering with retries, prescoring, diversity,
family adjustments, ranking, confidence and recommendation thresholds are unchanged.
The adapter passes the identical stream and budgets to this workflow; it never
merges locally ranked winners or constructs its own global score.

| Stage/status | Meaning |
| --- | --- |
| raw_match_count | Actual native FoundList.Count; no wrapper raw-hit ceiling |
| raw_inspected_count | Distinct native indices accessed, including structural scouts |
| raw_admitted_count / collected_count | Legacy scanned_count: entries admitted under scan_budget |
| unique_count | Legacy addresses remaining after deduplication |
| filtered_count | Legacy exact-pattern filtering survivors |
| prescored_count | Legacy prescore-stage population (pass-through when no reduction is needed) |
| selected_count | Legacy selection output under max_candidates |
| ranked_count / evaluated_count | Rows actually ranked by MVP0.run |
| qualified_count | Independent one-row ACCEPT count among ranked rows, not an unsampled global count |

Defaults match the historical collector: scan_budget=2000 and max_candidates=20.
The adapter permits raw admission 1..65536 and ranking 1..128, with ranking budget
no greater than admission. These independent CPU/memory/report budgets never
truncate native Count. The full native pool can exceed 30k, even when intake is
bounded. A configured full 30k intake still runs the original prescorer before
bounded final ranking; no algorithmic optimization discards/reorders its input.

`raw_admission_complete` requires admitted=native. `ranking_complete` requires
selected=filtered and ranked=selected. `collection_complete` requires both;
`scope_complete` additionally requires no failed reader. `coverage` is
full_population or sampled_or_reduced. Reduced coverage always stops with
`INCOMPLETE_CANDIDATE_POPULATION`, including a sampled ACCEPT. The adapter does
not infer global uniqueness from prescores or top-N. Only complete coverage,
exactly one independent qualifier, the original no-manual-review ACCEPT, and
valid selected mapping/fields can set global_uniqueness_proven. Existing
prewrite, exact-bit readback and identity gates still apply. This preserves the
write safety gate; it does not promise that a 30k stable population can be written
under the default bounded algorithm budgets.

The native count/progress is checked on initialization, before/after raw intake
and after ranking. Observed indices are revalidated before the legacy view is
released. Duplicates, gaps, count changes, read failures, cancellation, timeout,
identity loss and cleanup errors stop safely. Native FoundList ownership stays
with the adapter until deterministic disposal; the collector's destroy closes
only its view. Failed native cleanup blocks writing and restart.

Collection yields after collection_batch_size=256 address/read/score checkpoints
(range 16..2048), or collection_slice_ms=10 (range 1..25). Both modes share these
limits. Native calls, fixed candidate calculations, Lua sorts and bounded report
rendering cannot be preempted. scan_timeout_ms covers the whole cycle. Sorting
scales with admitted/scouted candidates; report text scales with at most 128
ranked rows. No 30k score/report dump is exposed in Status. The removed P2 process
snapshot settings reject explicitly instead of silently changing their meaning.

Differential regressions compare identical native order and intake/ranking
budgets with the unwrapped legacy workflow; sampling is intentionally order-
sensitive. No claim of order invariance is made for sampled inputs. Synthetic
30k timing/memory evidence is not CE-native timing or acceptance. Races between
identity/memory observations remain part of the existing non-atomic read limits.

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
