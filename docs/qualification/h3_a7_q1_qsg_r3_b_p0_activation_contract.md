# P0 activation contract v1

Authority is limited to `APPROVE_H3_A7_Q1_QSG_R3_B_P0_OFFLINE_IMPLEMENTATION`
and the seven paths in the P0 prompt section 4. This contract implements only
synthetic activation. R3-B Native IPC and G1 LIVE are NOT APPROVED; all real
N01–N09 and L01–L12, including the three L12 variants, remain NOT_RUN.

## Flow and trust

Previously, the Python native command, Lua start_native, open_native,
require_native_activation, default Win32Provider operations and load_native_api
all rejected. They continue to reject. The B1 WinAPI table remains available to
its existing trusted API-level fakes; P0 never obtains a native function table.
No module import loads a DLL, starts a timer/worker or creates a pipe.

The added Python test entry is `activate_offline`. Its bridge starts COLD and
advances CONFIG_PARSED → CANDIDATE_BOUND → AUTH_BOUND → TECHNICAL_ADMISSION →
RUN_PERMITTED only for the concrete in-memory FakeProvider. That last state is
always modeled, with SYNTHETIC origin, NOT_PROVEN OS evidence and blocked native
activation. Explicit CLOSE with observed cleanup ends STOPPED. CANCEL, failure,
replay, omitted CLOSE, logging failure and uncertain cleanup cannot return PASS.
There is no retry, reconnect or native fallback.

OfflineEnvironment is immutable injected test equipment. Its candidate byte
string and separately retained digest, policy byte string, technical observation
bytes, three clock functions and suite-lifetime ReplayRegistry are supplied by
the harness before the untrusted record. The record cannot choose the trust pin.
The candidate's exact file set includes all seven P0 paths plus the unchanged
protocol module; the manifest pins the approved LP-R1 manifest and CE disk hashes.
Final delivery seals the source manifest separately from the patch and overall
report manifest, avoiding a self-referential source-hash dependency. There is no
CLI, environment variable or approval-file override of the native denial.

The retained approval byte digest models authentication of test input. It is NOT
a signature check, an operator identity measurement, or an installed trust store.
A signature-shaped or authenticated=true additional field is rejected. The
environment, clock functions and existing Lua/WinAPI injected functions are
trusted equipment, not a sandbox against arbitrary hostile Python or Lua code.
Monkey-patching interpreter internals is outside this model's trust boundary.

## Strict record and technical contract

The record discriminator is qsg.native-probe.activation.v1 and its wire protocol
is qsg.native-probe.v1; qsg.mock.v1 is not accepted. Exact keys, canonical UTF-8
JSON and duplicate-key rejection apply at every structured layer. The maximum
record is 65,536 bytes. UTC timestamps must use YYYY-MM-DDTHH:MM:SSZ. A window is
positive, at most 15 minutes, and is rechecked during every transaction.

Authorization digest, complete candidate/asset hashes, host/operator/approver
identity digests, distinct operator and approver, session/channel/epoch/nonce,
case/trial list, exact evidence destination, budgets and watchdog policy must
match the independent test policy. Paths are canonical local absolute Windows
paths under the approved workspace's reports directory; UNC/device/ADS/traversal,
reserved names, trailing spaces/dots and alternative spellings reject. This is
lexical validation, not proof of the filesystem, reparse points or directory ACLs.

Technical observations independently bind the same session, identities and
assets. Every prerequisite must be SYNTHETIC_MATCH: dedicated instance, startup
isolation, DACL, peer principal, client handle, process creation, loaded runtime,
independent watchdog, cleanup completion, secret bootstrap, target absence and
fresh/writable evidence. The existing strict connection-model validator checks
connection-specific handle provenance, both process creation identities, SID
separation, exact DACL/rights and loaded-component fixtures. The actual connection,
actual OS token and actual loaded DLL remain NOT_PROVEN. PID, pipe name, nonce,
role labels and mock authenticated flags never supply those proofs.

The only wire methods remain HELLO, ECHO, PING, CANCEL and CLOSE. Target PID,
address, reserve/claim, dynamic load, code/shell execution and user-script fields
are rejected by the unchanged protocol. The Lua bind_activation_model interface
validates the separately expected synthetic binding and constructs an inert
offline byte worker. It never calls ambient CE APIs and does not open transport.

## Bounds and terminal behavior

One connection/request is outstanding. A shared suite registry rejects a second
active bridge; pending or uncertain completion retains its connection occupancy,
including after a late provider-only cleanup observation. Frames retain a 1–65,536-byte canonical
JSON body and four-byte prefix. The host deadline is an absolute 250 ms on its
own monotonic clock; fragments do not renew it. Watchdog elapsed time uses a
separate clock epoch, with a 250 ms model deadline and 2 s cutoff. Clock reversal,
expiry, 60 s case/15 min suite exhaustion and message/case/trial exhaustion deny.
The test policy may tighten case/suite/message/evidence budgets. Fixed worker
deadline, watchdog deadline and wire ceiling values must match the implementation.

Proposed later native ceilings are one CE, one server, one outstanding request,
three trials/vector, twenty cleanup iterations, 512 MiB CE, 256 MiB server/helper
and 16 MiB evidence. Memory ceilings are recorded admission hypotheses; this
module does not measure OS working sets. P0 records explicit zero permissions
for native provider/pipe, targets, memory operations, process termination,
handle duplication, production ledgers and automatic retries.

Approval and identity values are logged only as SHA-256. Events are bounded,
append-only, chained synthetic records, charged to the shared suite evidence
ceiling as well as the individual bridge; wire data is represented by byte count
and digest. Retained test fixtures may separately contain public synthetic bytes.
An event overflow cannot produce PASS. Cancellation is a request, not completion
proof. Pending fake operation buffers remain held until the exact owner observes
completion. A late completion may finish cleanup but cannot restore authority.
The B1 real-provider ownership implementation is unchanged and not executed.

DENIED means admission failed or authority was revoked with observed closure.
UNCERTAIN means cleanup, closing evidence or evidence capacity was inadequate.
NOT_PASS covers COLD/incomplete states. SYNTHETIC_PASS requires an explicit CLOSE,
observed closure and STOPPED with intact evidence; it never means native PASS.

## Qualification and remaining native gates

P0-01 covers inert imports and Lua loads; P0-02 approval parsing/window; P0-03
candidate and identity drift; P0-04 identity/path/session/budget ambiguity;
P0-05 fake-vs-OS evidence; P0-06 negative technical and connection proofs;
P0-07 replay/correlation; P0-08 framing; P0-09 deadline/cancel/fault;
P0-10 cleanup/ownership/evidence bounds; P0-11 protected sources/native denial;
P0-12 complete ordinary/long-path and Unicode regression, freeze and patch replay.
The dated report retains raw results, all attempts, command exit codes, source
snapshots and independent evidence replay. No historical B1 PARTIAL is rewritten.

A later R3-B decision needs a new narrow, operator-signed authorization, exact
reviewed P0/native candidate and CE EXE/DLL hashes, approved host and principals,
specific N cases/vectors, evidence directory and time window. It also needs
verified dedicated CE startup with no instance reuse/autorun/restore/autoattach,
supported CE client-handle provenance, actual per-connection bilateral OS peer
and loaded-runtime measurements, exact DACL readback and principal-negative
permissions, approved secret/bootstrap transport, measured timeout units and
UI/cancel behavior, independent externally enforceable watchdog and explicit
cleanup authority limited to exact newly spawned process instances. These are
technical evidence requirements in addition to permission, not facts established
by parsing an authorization record. Any extra source requires new exact scope.

Product statuses remain IMPLEMENTED_PENDING_CE_QUALIFICATION,
ATTACHMENT_HANDLE_UNVERIFIED and NOT_PRODUCTION_AUTHORIZED. Independent A6/R3 T1
remains pending and the historical R2 T1 failure is unchanged. No tag is proposed.
