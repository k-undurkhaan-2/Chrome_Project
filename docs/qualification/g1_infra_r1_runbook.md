# G1-INFRA-R1 test equipment and future integration boundary

**SYNTHETIC ONLY. G1 LIVE NOT APPROVED.** All L01–L12, including the three
L12 rejection cases, remain NOT_RUN. Product status remains
IMPLEMENTED_PENDING_CE_QUALIFICATION, ATTACHMENT_HANDLE_UNVERIFIED and
NOT_PRODUCTION_AUTHORIZED. A6/R3 independent T1 remains pending; historical R2
remains T1_FAILED_NOT_QUALIFIED.

There are no live start buttons, executable target entrypoints, native memory
providers, background services or arming commands in this package. Every
recorder/exporter and session gate is disabled by default. Explicit test opt-in
only accepts SYNTHETIC policy. No string is accepted as live authorization.

## Components and provenance

The new `src/ce_qualification` package is isolated test equipment, not imported
by the product loader. `tests/qualification/support.py` executes unchanged R1
Lua modules against the existing table-backed CE/Win32 mock and unchanged pure
offset fixture. It never imports the native disposable target. No R1 source,
fixture, plan or historical report is amended.

- `target.py`: version `g1-target-recorder-v2-synthetic-only`; A/B instance
  identities include designation, simulated PID, nonzero creation FILETIME and
  SHA-256 of the versioned recorder. Each allocation is a fresh Python bytearray
  of 65,536 bytes, not a native process reservation. Commit/decommit events model
  4 KiB pages. Unique, zero, ambiguous, 129-plus, incomplete, invalid, drift and
  relocation reuse the frozen layout plan. No production threshold changes.
- `recorder.py`: accepts copied plain diagnostic tables; no CE callback or
  process API. The caller obtains `evidence()` from the mock, then normalizes
  existing events, identities, counters, raw bits and cleanup. The original
  ring sequence must start at 1, have no drops and preserve prior event contents.
  Repeated snapshots do not duplicate events. CE embedded `_VERSION` remains
  NOT_RUN; actual host Lupa version is separately labeled `synthetic_lua`.
- `budget.py`: pre-dispatch reservations, process-instance/allocation/Float32
  and candidate checks, exclusive session owner, durable journal and retained
  head. It models L04+L07 <=2, L10 <=1, all other cases 0, total <=3.
- `verifier.py`: offline reader with independent reconciliation rules; does not
  import the controller, CE recorder or target implementation or trust their
  derived PASS flags. Read-only CLI accepts a sealed bundle and sealed policy.

Native target provisioning and transport integration are NOT_RUN. A future
target provider must implement target-self allocation/read/decommit/release and
GetProcessTimes identity capture, stay inside its own new 64 KiB reservation,
and receive separate review and a new file/runtime provenance manifest. Do not
replace the frozen target with this Python model in an approval record.

## Records and transport

The versioned envelope is in `src/ce_qualification/evidence.schema.json`.
Every event carries source/actor, origin, session/run/scenario, sequence and
event ID, UTC and a named monotonic clock origin, predecessor and content hash.
Canonical JSON uses sorted keys, ASCII escapes, no NaN/Infinity, compact
separators and a final newline per record. Duplicate JSON keys are rejected.
Raw Float32 is always `0x` plus eight uppercase hexadecimal digits. Float32
nonfinite values cannot be used as successful write/readback evidence.

| Source / events | Required evidence and interpretation |
| --- | --- |
| Target `allocation` | Full creation identity + file hash, allocation ID, base, size 65536, PAGE_READWRITE and owner token |
| Target `commit`, `retire`, `decommit`, `reallocate` | Region IDs, bounded page ranges, active/retired addresses, same process token; permanent retirement |
| Target `mode`, `planned_drift` | Exact mode, intended bits, independently scanned synthetic bytearray match count; 129 actual words with cap 128 |
| Target `checkpoint`, `checkpoint_missing` | Target-self sampled word or explicit failure; anchor and optional attempt ID; no memory dump |
| Target `shutdown`, `exception`, `cleanup` | Lifecycle and release outcome, bounded reason codes |
| CE `ce_event`, `ce_snapshot` | Whitelisted original R1 fields, per-Start sequence, state/counters/identity; address aliases require external bindings |
| CE `ce_dispatch`, `ce_checkpoint` | Synthetic harness evidence only: unique attempt ID, reservation digest, identity/allocation/address/bits, target checkpoint anchor and original diagnostic sequence |
| CE `config_rejected` | One actual synthetic Start result, bounded diagnostic, eight before/after API-attempt counters and restored guard; retained evidence explicitly labeled |
| Budget `enrollment`, `start`, `stop`, `retire` | Policy digest, exact target instance and allocation, run state, permanent address retirement |
| Budget `reservation`, `dispatch`, `outcome` | Pre-call durable reservation, unique attempt ID/digest, SUCCESS/FAILED/INDETERMINATE; no automatic retry |

The mock transport accepts only a strict checkpoint packet: schema=1, exact
session ID, monotonically increasing sequence, command=`checkpoint`, anchor ID
and bounded address. An acknowledgement identifies the request digest and
target event digest. It accepts no arbitrary code, shell command, file path,
memory dump or configuration content. A future local pipe protocol should keep
this shape, bind both peer identities, require request/ack deadlines and abort
on gaps; no pipe/server is implemented or started here.

Clock offsets are intentional in the examples. Never subtract target monotonic
time from CE or budget time. Cross-source order uses checkpoint/attempt/event
anchors. R1 relative time is the last control tick, not fresh event-time UTC.
Target samples cannot identify the writer or rule out transient intervening
writes. Adapter calls do not count OS memory syscalls. Independently identical
CE attachment handles remain unverified.

## Journal recovery and trust boundary

Provisioning is a separate synthetic-only function, never performed by reload.
One retained authority root has an exclusive enrollment file with session ID,
fixed policy and exact journal path. Reusing that root fails even with a new
session string. Every opening requires its externally retained enrollment hash.
The exact head file seals journal bytes, event count and final digest. Missing,
malformed, truncated or mismatched logs/heads, concurrent owners and incomplete
head replacement fail closed. A lock uses exclusive file creation and remains
after a simulated crash; there is no stale-lock bypass or automatic recovery.

The reservation is appended and flushed with fsync, then the head is written
to an exclusive temporary file and atomically replaced before the mock write.
The gate rechecks journal ownership and expiry before dispatch. It holds a
non-reentrant in-process lock throughout dispatch. Failure/uncertainty consumes
one attempt, including a crash between reservation and call. Stop/new Start and
reload never refund attempts. If storage fails, no further dispatch is allowed.
The retained roster limits each target to its declared scenarios; B is L11-only
with zero writes. The model also preserves the nine-successful-Start ceiling,
five-minute phase window and one-hour session ceiling. A consumed prewrite
checkpoint cannot be replayed. A journal `dispatch` marker is persisted intent
at the call boundary, not proof that the call completed; CE-side events and
target checkpoints supply separate observations.

This is **not** a claim of physical power-loss durability on Windows. Filesystem,
fsync and rename behavior were exercised only under normal execution and fault
injection. Directory-entry persistence, hostile file mutation, authority-root
rollback/deletion and an attacker replacing both chain and anchors are outside
the proof. A digest chain is tamper-evident relative to trustworthy retained
anchors, not tamper-proof. Future live admission needs an independently retained
authorization/enrollment and head anchor, an approved durable-store strategy and
reviewed crash recovery. Never delete a stale lock to keep a session running.

## Offline use

The saved report manifest gives exact input hashes. This command reads files
only; it cannot arm CE or start a target:

```text
python -B -m ce_qualification.verifier --manifest <synthetic-bundle.json> --manifest-sha256 <retained-hash> --policy <synthetic-policy.json> --policy-sha256 <retained-hash>
```

Exit 0 means all requested synthetic criteria passed; 2 means incomplete or
unobserved evidence; 1 means malformed, contradictory or failing evidence.
The output has separate infrastructure, synthetic and live axes. Even exit 0
retains BLOCKED_WRITE_GUARD_WIRING and every live row as NOT_RUN. Exported raw
JSONL files are ignored by the existing Git rules; their hashes and paths must
be recorded separately. The examples contain simulated IDs/addresses only.
Future private raw logs and redacted public reports must be separate; never
rewrite the sealed raw stream to redact it.

## Future installation remains blocked

**BLOCKED_WRITE_GUARD_WIRING.** Frozen public Start passes `_G` to the adapter;
the adapter captures `writeFloat` in a private table at construction. The
diagnostic observer catches recording errors and is deliberately non-blocking.
The existing prestart guard rejects every attempt and is removed before Start;
it cannot implement the three-attempt session policy. A post-construction Lua
wrapper cannot change the captured function. The mock injection in these tests
is not an approved or demonstrated real CE installation route.

Passive export of `evidence()` is possible without additional memory access.
Full live collection is **BLOCKED_PENDING_SEPARATE_SOURCE_REVIEW** because the
frozen diagnostic stream lacks global attempt IDs, allocation bindings and
durable reservation acknowledgements; A0/A1 aliases are local to each Start.
No synthetic transport claim supplies these missing live anchors.

The smallest next authorization is a separate **source review/remediation
candidate only**, covering an explicit fail-closed dispatch dependency at the
captured Float32 primitive and the public loader's construction path, plus
reviewed durable reservation acknowledgement and evidence binding. Keep R1
immutable; freeze a distinct candidate and rerun mock behavior-equivalence,
failure/reentrancy/restart tests. No live operation is included in that request.

After those blockers are resolved, a later independent G1 record must name the
new candidate manifest/digest, target A/B and CE executable identities, owner
and operator, actual permitted operations, exact time window, budgets, evidence
destination and stop conditions. Fresh PID/creation/allocation values are then
observations constrained by that approval. This runbook supplies no live launch
command and creates no private configuration.
