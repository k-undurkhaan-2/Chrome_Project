# R3-A-IMPLEMENT standalone offline probe

This candidate consumes only the maintainer's separate R3-A-IMPLEMENT grant:
new probe, host, watchdog, protocol, recorder, verifier, offline tests and evidence.
It adds no native backend and changes no QSG-R2 production file. All N01-N09 real
tests remain **NOT_RUN**. G1 LIVE remains **0 PASS / 0 FAIL / 12 NOT_RUN**.

Keep `R3_B_NOT_AUTHORIZED`, `G1_LIVE_NOT_APPROVED`,
`IMPLEMENTED_PENDING_CE_QUALIFICATION`, `ATTACHMENT_HANDLE_UNVERIFIED`,
`NOT_PRODUCTION_AUTHORIZED`, `A6_R3_T1_SEPARATE_PENDING` and historical
`R2_T1_FAILED_NOT_QUALIFIED`. These results confer no production approval.

## Components and trust boundaries

| New component | Responsibility and restriction |
| --- | --- |
| `src/qualification/native_ipc_probe.lua` | Inert Lua 5.3/5.4 module; strict flat JSON codec, pure SHA-256 and cooperative byte-worker steps. No imports, globals traversal, native API names, connection creation, timer, process or memory capability. |
| `src/ce_qualification/native_ipc_probe.py` | Default-off host Coordinator; one outstanding request, bounded partial transfers, local invalidation and explicit cleanup result. CLI `offline` runs an in-memory smoke; `native` always exits 3 without entering native code. |
| `native_probe_protocol.py` | Canonical codec, header-first decoder, request/reply state, modeled peer proof and bilateral HMAC challenge. No production protocol/ledger import. |
| `native_probe_watchdog.py` | Independent injected-clock timeout/cancel/completion model plus case/session limits. No thread, process termination or Windows I/O cancellation implementation. |
| `native_probe_evidence.py`, `native_probe_evidence.schema.json` | Bounded append-only synthetic streams and exclusive-create export. No historical evidence overwrite or ledger calls. |
| `native_probe_schema.py` | Strict implementation of the JSON Schema subset used by this schema; unknown schema keywords reject. No additional runtime dependency. |
| `native_probe_verifier.py` | Read-only independent replay; imports only pure serialization/schema helpers, never the Coordinator, Watchdog, Recorder, Lua runtime or QSG controllers. |
| `tests/qualification/native_probe_fakes.py`, `native_probe_suite.py` | Standalone Lua runtimes in a minimal environment, deterministic queues/clocks, observed counters, ledger/import tripwires and N01-N09 evidence production. |

`new_offline` requires `mode=offline`, `origin=SYNTHETIC` and exactly the listed
capabilities: bounded `read_some`, `write_some`, `close`, monotonic `now_ms`,
`cancelled` flag and `emit` sink. No capability is called during construction.
Only explicit `step()` calls advance the worker. Injected functions are trusted
test equipment, not a sandbox for malicious callables. They must remain the
supplied in-memory fakes in this phase. No existing CE instance is accessed.
Repeated load creates inert module tables, with no global singleton or activity.

The CE worker source is reusable byte-processing logic, not an installed CE
transport wrapper. Both `start_native()` and Python `native_admission()` always
reject with `R3_B_NOT_AUTHORIZED`, including signature-shaped/mock input. A later
reviewed native adapter and admission implementation is still required; editing
a mode string or supplying a Boolean approval is not an activation procedure.

## Wire contract

The schema and origin are exactly `qsg.native-probe.v1` and `SYNTHETIC`.
`qsg.mock.v1`, G1/QSG evidence schemas and native origins are rejected. No
`reserve`, `claim`, PID, address, memory operation, file path, command or Lua-code
field exists. ECHO is inert text; its content is never interpreted.

Each frame is a 4-byte unsigned little-endian body length followed by 1..65,536
UTF-8 bytes. The decoder collects at most four header bytes and validates length
before storing body bytes. Zero/oversize, truncated header/body, trailing or
coalesced frames, duplicate keys, invalid UTF-8, unknown fields and noncanonical
JSON reject. Canonical encoding uses sorted keys, no whitespace, literal UTF-8,
minimal JSON escapes and integers; floats, non-finite numbers and Boolean
integers reject. The Lua protocol envelope is flat and identical to Python.

Every envelope has `schema`, `origin`, `kind`, `method`, `session_id`, `channel_id`,
`epoch`, `request_id`, `sequence`, `payload`, `request_sha256` and `result`.
Only `HELLO`, `ECHO`, `PING`, `CANCEL` and `CLOSE` are permitted. HELLO is first
and unique; ECHO alone permits text payload. Request digest/result fields are
empty. Responses echo all correlation fields and payload, bind the canonical
request SHA-256, and return OK, CANCELLED or CLOSED for the appropriate method.
Sequence and epoch are exact positive 31-bit integers; IDs are bounded ASCII.

One request is outstanding. Any correlation, sequencing, transport, cancellation
or recording failure invalidates it and closes the fake channel; there is no
implicit retry/reconnect or privilege recovery. Reused request IDs/epochs and
late/duplicate responses reject. Local cancel/close works during a wait without
trying to send a concurrent CANCEL/CLOSE frame. These wire messages are exercised
when the channel is idle. The maximum ECHO request payload reserves room for the
larger reply envelope: a 65,536-byte request that cannot fit its reply fails
closed. Tests separately cover maximum request decoding and an exact 65,536-byte
reply end to end, plus the 4096-byte crossing and one-byte fragments.

Every successful partial send/receive and completed frame records its actual
byte count and SHA-256. Replay reconstructs complete frames from chunks and
compares host/worker bytes, binding, method and response. Synthetic public ECHO
test payloads are included in hex for replay. Secret keys never enter messages,
command lines or evidence. HELLO is only protocol initialization, not OS identity.

## Timing, cancellation and identity assumptions

The complete host request has one 250 ms model deadline starting before the first
send; no fragment refreshes it. The Lua receive/reply operation has its own
250 ms model clock window. The independent watchdog models a 250 ms deadline and
2000 ms hard cutoff, and separately records cancellation request versus observed
I/O completion and closed resources. A blocked/uncertain cleanup remains
INDETERMINATE even if a late completion arrives after cutoff. The total-limit
model rejects at 60,000 ms per case and 900,000 ms per session. All are design
hypotheses, not measured CE latency guarantees. A cooperative Python/Lua fake
cannot interrupt a blocked native call; no real watchdog process exists here.

The installed `celua.txt` describes LuaPipe.Timeout in seconds and connectToPipe's
timeout in milliseconds. Native parameter/property units, OnAboutToTimeout,
destructor behavior, UI heartbeat and cancellation completion remain UNKNOWN /
NOT_RUN. No test launches CE or loads its installed Lua DLL. Standalone Lupa
Lua 5.3/5.4 runtimes are explicitly distinct from CE's embedded Lua.

The modeled peer schema checks restricted DACL/handle fixture labels, an approved
principal/owner, both PID-plus-creation identities and session/channel/epoch.
Unknowns, mismatches, reused epochs and mock `authenticated=true` reject.
Separate bilateral HMAC model responses bind both challenges, the role and full
session binding. They do not supply native OS identity or a deployed handshake.

Future transport design is **host server / CE client**, with a cryptographically
random isolated endpoint, explicit restricted DACL, local-only access, minimum
client read/write and server instance/access rights reviewed separately, and no
broad generic-write grant that accidentally permits pipe-instance creation.
Actual masks, owner/token restrictions and security-descriptor verification must
be frozen with the future native adapter. `GetNamedPipeClientProcessId`,
`GetNamedPipeServerProcessId`, `DuplicateHandle`, usable CE client handle access,
image/creation identity and principal verification remain unverified assumptions
for the pinned binary. A pipe name, PID, nonce or Connected Boolean is insufficient.
No real DACL/endpoint or negative-principal attempt is performed now.

## Offline commands and evidence

Use the existing repository `.venv/Scripts/python.exe` (Python 3.14.3) and the
already pinned standalone Lupa runtime from the R2 runtime manifest. No package
installation, CE launch or configuration change is necessary. Actual invocations,
environment paths, source hashes, durations and exit codes are preserved by
`reports/2026-11-20/qsg_r3_a_implement_20261120T122231Z/run_command.py`.

With `PYTHONPATH` including `src` and the recorded Lupa directory,
`PYTHONDONTWRITEBYTECODE=1`, and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`:

```text
.venv/Scripts/python.exe -B -m ce_qualification.native_ipc_probe offline
.venv/Scripts/python.exe -B -m pytest tests/qualification/test_native_probe_protocol.py tests/qualification/test_native_probe_runtime.py tests/qualification/test_native_probe_evidence.py -q
.venv/Scripts/python.exe -B -m pytest tests -q
.venv/Scripts/python.exe -B tests/qualification/native_probe_suite.py --output <NEW-directory> --candidate-sha256 <source-manifest-hash> --authorization-sha256 <approval-record-hash>
.venv/Scripts/python.exe -B -m ce_qualification.native_probe_verifier --manifest <evidence.json> --manifest-sha256 <retained-hash> --plan tests/fixtures/qualification/native_probe_plan.json --plan-sha256 <retained-plan-hash> --candidate-sha256 <source-manifest-hash> --authorization-sha256 <approval-record-hash>
```

Use a fresh test temp/output path each run. A pre-existing output fails rather
than being overwritten. Do not rerun a historical report's packaging script.
Read the final manifest for which successful run matches the frozen source;
earlier failures and superseded passing runs remain intact.

Four synthetic actors produce independent streams: HOST, LUA_MODEL, WATCHDOG and
OBSERVER. Each event includes case/trial, event ID/sequence, offset UTC, clock ID,
elapsed model time, session/channel/epoch/request binding, candidate/authorization
digests, frame metadata, response/error/cancel stage and chained content hashes.
Each stream is capped at 8192 events and 8 MiB and has an explicit terminal event,
count/head/sequence and raw log hash. A separately pinned fixture supplies the
expected-observation checklist. Test witnesses record actual negative error codes
and counters; verifier independently reconstructs successful wire traces,
watchdog transitions and 20 simulated closed sessions. It does not trust a
controller PASS field. It never subtracts clocks belonging to different actors.

Verifier exit 0 means complete **synthetic** evidence, 1 contradiction/corruption,
2 missing/uncertain evidence. Missing streams/checks/terminal observations cannot
pass even after an internally consistent rehash. Integrity requires independently
retained external anchors; a hash chain alone proves neither completeness nor
OS identity. This is independent replay logic in the same task, not an independent
human or separate-agent attestation. Exported synthetic raw TXT/XML/JSONL and
historical failures are evidence artifacts, not production runtime logs.

## Separate R3-B admission requirements

R3-B is not granted. Before any native execution, a new signed, scope-specific
approval and reviewed runtime admission implementation must identify all of:

1. Exact R3-A source manifest/patch hashes, plus separately reviewed native
   adapter/admission hashes; installed CE executable/DLL hashes and versions.
2. Host, approving/operator principals, time window with timezone, and one fresh
   exclusive evidence destination; authentic signature validation against a
   separately trusted approver key. No mock proof can satisfy this requirement.
3. One newly launched dedicated CE and one host server. Prove startup isolation
   from existing CE instances, autorun, restore, automatic attachment and plugins.
   Uncertain isolation stops before connecting. No target A/B, attach, scan,
   target allocation/read/write or production ledger access is allowed.
4. Random isolated local endpoint, exact restricted DACL and access masks,
   principal/owner verification, both OS peer PIDs plus creation/image identities,
   usable verified client handle, session/channel/epoch binding and bilateral
   challenge response. Missing handle/DACL/OS proof is a hard stop.
5. Explicit independent watchdog and process-control permissions applying only
   to dedicated newly created processes; reviewed bounded I/O/cancel/close path,
   completion observation and escalation procedure for uncertain cleanup.
6. Approved N01-N09 message/error vectors, at most one outstanding request,
   proposed 250 ms complete request / 2 s external cutoff / 60 s case / 15 min
   session, at most three repetitions per vector and 20 cleanup cycles. Native
   measurements must validate the units and feasibility, not assume them.
7. Logging/resource limits, secret handling without command-line/evidence
   disclosure, immutable externally anchored evidence, independent verification,
   explicit stop conditions and no automatic retries after failure.

None of these native execution/process-control permissions is consumed here.
Even a future R3-B pass would leave G1 L01-L12, native memory operations,
attachment-handle equivalence and physical power-loss persistence to independent
decisions and authorization. **No new version tag recommended.**
