# R3-B0 offline native transport adapter candidate

Authority consumed: the separate user instruction
`APPROVE_H3_A7_Q1_QSG_R3_B0_OFFLINE_IMPLEMENTATION`, restricted to Section 2
of the B0 prompt. No R3-B execution authority is present. All real N01-N09 and
L01-L12 remain NOT_RUN. Keep R3_B_NOT_AUTHORIZED, G1_LIVE_NOT_APPROVED,
IMPLEMENTED_PENDING_CE_QUALIFICATION, ATTACHMENT_HANDLE_UNVERIFIED,
NOT_PRODUCTION_AUTHORIZED, A6_R3_T1_SEPARATE_PENDING and historical
R2_T1_FAILED_NOT_QUALIFIED. No version tag is recommended.

## Activation and component boundaries

`native_ipc_probe offline` preserves R3-A's in-memory CLI. `native` still exits
3 with R3_B_NOT_AUTHORIZED and also reports BLOCKED_NATIVE_ACTIVATION_UNPROVEN.
Lua `start_native()` still unconditionally rejects. No CLI option, environment
variable, protocol rename, JSON Boolean, signature-shaped text or synthetic
verification result can activate the native provider.

`native_probe_winpipe.open_native()` is the explicit future activation seam:
it calls `require_native_activation()` BEFORE calling a provider factory.
That admission function unconditionally raises in this frozen candidate.
Every method on `NativeProvider` separately calls the same hard stop. The class
is a future OS provider stub; it contains no ctypes/FFI/DLL loading or callable
Win32 implementation. Completing that backend and trusted runtime admission
requires another scoped source change, new freeze and independent approval.
This is offline adapter readiness, not technical clearance to execute R3-B.

`SyntheticServer` implements the host-server state machine against explicit
injected create/connect/read/write/poll/query/challenge/cancel/close operations.
`new_ce_pipe_model` maps injected `connectToPipe`, LuaPipe `Connected`, `Timeout`,
`readBytes`, `writeBytes`, `OnAboutToTimeout`, `destroy`, and separate close
observation into the unchanged byte worker. Both constructors are inert;
opening the synthetic connection requires an explicit call. The ordinary Lua
worker, Python protocol, R3-A event schema and historical evidence semantics are
preserved. The old static token audit now allows the name `connectToPipe` only
as part of this injected contract; strict Lua ambient-capability tripwires remain.

Injected callables are trusted test equipment, not a sandbox against hostile
Python/Lua code. `origin=SYNTHETIC` is a provenance label, never OS authentication
or an authorization mechanism. No model path has a fallback into NativeProvider.
The production MVP and QSG-R2 modules have no new dependency on these modules.

## Wire and bounded I/O

The wire protocol remains `qsg.native-probe.v1`, SYNTHETIC only, with exactly
HELLO/ECHO/PING/CANCEL/CLOSE. No target PID/address, memory operation, reserve,
claim, code execution, shell or filesystem command is allowed. Frames retain
4-byte unsigned little-endian length and 1..65536 canonical UTF-8 JSON bytes.
Duplicate/unknown keys, malformed UTF-8/JSON, truncation, coalesced/trailing
frames, request reuse, correlation mismatches and late responses reject.

Each completed operation retains its actual returned count and SHA-256. Host
and Lua evidence retain complete frame digests and chunk bytes. A late host
completion is recorded but cannot be accepted. The server holds one operation
at a time, retains pending buffers and polls at most 128 times without sleeping.
Polling is cooperative test behavior, not a proven native scheduling mechanism.

Candidate Win32 configuration: PIPE_ACCESS_DUPLEX (0x3),
FILE_FLAG_FIRST_PIPE_INSTANCE (0x80000), FILE_FLAG_OVERLAPPED (0x40000000),
PIPE_REJECT_REMOTE_CLIENTS (0x8); byte type/read mode and WAIT are zero. One
instance, 4096-byte buffers, non-inheritable security attributes and explicit
protected DACL. Pipe names are local and session-specific, with 128-bit suffix
shape. Tests use deterministic suffixes; future runtime must supply secure
random generation and retain endpoint/channel/epoch tombstones across its
approved session. Failed opens consume a tombstone; close never enables replay.

Client requested access is separately modeled as 0x120003 (READ_DATA,
WRITE_DATA, READ_CONTROL, SYNCHRONIZE), excluding FILE_CREATE_PIPE_INSTANCE.
Server access is 0x12019f. Only two explicit principal ACEs are allowed. Distinct
server/client principals are required by this least-privilege proposal. If the
future CE client requests generic write, or both roles share indistinguishable
principals, this proposal remains blocked; do not broaden the DACL to make a
connection succeed. Actual CE access masks and the feasibility of the principal
separation have not been measured.

Microsoft documents that default pipe DACLs are broader than this proposal and
that generic write also confers create-instance permission. See
[pipe security and access rights](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights).
Flags are based on
[CreateNamedPipe documentation](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createnamedpipea).
Documentation review is not an observation on the installed host.

## OS identity, connection binding and challenge

`native_probe_peer` validates two process identities with PID, nonzero creation
FILETIME, token user SID, executable and loaded-component hashes. Both query
records bind their observing process, connection ID and actual modeled handle.
The host-side query uses GetNamedPipeClientProcessId on its server handle; the
client-side contract uses GetNamedPipeServerProcessId on a verified client
handle. Creation/token/image evidence names held-process-handle GetProcessTimes,
GetTokenInformation(TokenUser), QueryFullProcessImageName plus file hashing,
and independently pinned loaded components. JSON peer claims are never a source.

DACL proof names GetSecurityInfo(SE_KERNEL_OBJECT), the same connected server
handle, owner SID, non-null present/protected DACL, descriptor digest, exact
non-inherited ACEs, and independently observed client requested access. A
Connected Boolean, known pipe name or process ID cannot replace any proof.

The bilateral HMAC model binds both endpoint identities, connection/session/
channel/epoch, DACL digest, candidate and authorization digests, both challenges,
the complete observed proof digest and a distinct CLIENT/SERVER role. Verification
of both responses precedes model readiness. Keys are not passed through frames,
command lines or evidence. The public deterministic fixture key is not a runtime
secret. Runtime key provisioning and challenge carriage still require review;
this model does not silently extend the frozen wire message vocabulary.

The installed CE LuaPipe's safely obtainable client handle remains UNVERIFIED.
An optional future route is a separately authorized helper using a supported,
process-owned handle export followed by DuplicateHandle into its own process,
holding the exact newly spawned CE process instance while querying and closing
only the duplicate. PROCESS_DUP_HANDLE, helper identity and ownership must be
named in the later approval. No guessed handle, CE-memory inspection, global
handle scraping or PID-only duplication is permitted. If a supported export
cannot be established, N03 and dependent native cases stay blocked/NOT_RUN.
The API contracts are documented by Microsoft for
[client PID](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeclientprocessid)
and [server PID](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeserverprocessid);
the installed CE integration has not been tested.

## Deadlines, watchdog, cancellation and ownership

250 ms complete request, 2000 ms external cutoff, 60 s case and 15 min session
remain candidate limits. Fragments/heartbeats do not renew them. The independent
watchdog uses its own injected clock; the owner never subtracts clock domains.
AdapterCoordinator integrates session limits, transport deadline and watchdog
before accepting an operation. A missing/failing watchdog closes the session.
Reply completion (COMPLETE_IO) is separate from session resource completion.

The installed celua.txt describes conflicting constructor/property timeout
units. The 25/100/250 constructor inputs and Timeout=1 are explicit model inputs
only, labeled UNKNOWN_MODEL. They are not converted or claimed as native units.
No timer waits on a pipe, no processMessages loop extends an operation, and no
createThreadNewState assumption is used to claim responsive UI or cancellation.

Requester initiates/cancels a request; server owner retains operation buffers;
the test broker provides inert replies; watchdog observes an independent cutoff.
Native cancellation and termination are denied. Synthetic cancellation also
defaults off, and requires explicit test equipment opt-in. A requested cancel
does not free a pending operation or close its handle. The external owner can
later observe terminal I/O completion and finish local cleanup without accepting
the stale reply or restoring authority. Coordinator INDETERMINATE does not become
a successful case after late cleanup. Repeated close is bounded and idempotent.

[CancelIoEx](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex)
does not wait for completion and does not make OVERLAPPED storage safe to reuse;
this is why cancellation and completion are separate. Future forced termination
would require an exact independently spawned process handle and creation identity,
explicit rights and a supported escape path. No termination implementation or
termination test exists in B0.

## Prelaunch admission and remaining R3-B requirements

`evaluate_model` checks strict canonical approval data, independently supplied
freeze/runtime identities, operator/approver/host/principal/workspace, absolute
timezone-aware window, fresh bounded evidence destination, allowed N cases and
vectors, caps, zero-target/zero-ledger/zero-retry constraints, cleanup scope and
an injected signature verifier bound to exact payload bytes. Its result is
SYNTHETIC_ADMISSION_ONLY. It performs no directory, process or OS queries.

Startup proof must independently establish supported dedicated-instance startup
with reuse, autorun, restore and autoattach disabled. Merely listing files or
hashing a CE executable fails this contract. No launch arguments have been
invented. The runtime mechanism and trusted signature-verification installation
are unavailable, so native activation remains BLOCKED_NATIVE_ACTIVATION_UNPROVEN.

Before any future R3-B action, a separate affirmative execution record must pin
the completed B0 manifest/source/patch and CE EXE/DLL/probe hashes, operator and
approver, host and approved principals, exact window/evidence path, isolation
proof, only one dedicated CE and server, exact cases/vectors/negative permissions,
resource limits, independent watchdog, and process-instance-specific cleanup.
Helper/principal-negative operations currently have no model allowance. Budgets:
one outstanding request, at most three repetitions/vector and twenty cleanup
cycles, bounded logs/memory, no implicit retries. Record explicit zero target
launch/attach/scan/read/write/allocation and zero production ledger operations,
and the statement “R3-B transport test only, NOT G1 LIVE.” Do not self-fill this
execution approval. Any additional source needed must be separately scoped,
re-frozen and reapproved before activation.

## Evidence and reproduction

The report directory contains the authorization excerpt, before/after SHA-256
allowlist and protected identities, Git baseline, each command/exit/time/source
snapshot, original failed TXT/XML, final focused/full regression, runtime identities,
separate patch and freeze manifests. Historical R2/R3-A artifacts are unchanged.

Use the existing Python 3.14.3 and pinned standalone Lupa Lua 5.3/5.4 described in
runtime.json, with PYTHONDONTWRITEBYTECODE=1 and disabled pytest plugin autoload.
The report's run_command.py captures exact environment and invocations. Each run
uses a new output and test-temp path; do not overwrite old evidence.

`native_probe_b0_suite.py` reuses the unchanged R3-A observation matrix through an
optional factory, running its successful N04/N09 wire traces via both B0 adapters.
It adds independently sealed adapter-traces.json (new sidecar schema, not a change
to the protected R3-A JSON schema). The verifier cross-checks exact chunk counts,
digests, creation/binding/close order and watchdog completion against sealed Host
records. Mutation/omission/replay tests require failure or incomplete evidence.
N01/N03/N05-N08 additional admission, peer and failure injection is recorded in
the named pytest cases; it is not falsely claimed as native or fully represented
by the successful adapter trace sidecar. Four original raw actor streams and
the independent 45-check plan remain in force.

Independent verification means replay logic does not import controllers,
transport, peer-decision code, recorders, watchdog or Lua. It is not independent
human/subagent attestation. Hash chains require separately retained external
anchors; replacing all anchors is outside this proof. The current output can
establish SYNTHETIC_PASS only. G1, attachment-handle equivalence, production
authorization and physical power-loss durability remain separate decisions.
