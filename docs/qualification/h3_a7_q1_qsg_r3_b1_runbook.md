# R3-B1 offline Win32 provider candidate

Authority: `APPROVE_H3_A7_Q1_QSG_R3_B1_OFFLINE_IMPLEMENTATION` from the
maintainer's current message, limited to the B1 prompt's file whitelist.
R3_B_NOT_AUTHORIZED and G1_LIVE_NOT_APPROVED remain unchanged. Real N01–N09
and L01–L12 are NOT_RUN, including all three real L12 subcases.

## Implementation and closed entry

`native_probe_win32.py` contains actual ctypes structures, signatures and API
control flow. `native_probe_winpipe.NativeProvider` delegates to that body.
Construction/import do not load a DLL, open a pipe or launch a process.
`open_native`, the CLI native entry, Lua `start_native`, default provider methods,
and `load_native_api` reject before native dispatch. No flag, environment variable,
model signature or synthetic record opens them. An explicit future reviewed
source change, new freeze and separate approval are required to install a native
function table. Merely possessing this offline implementation is not activation.

All B1 API tests inject a `WinAPI` table whose functions operate on local fixture
buffers and virtual handle integers. They are labeled SYNTHETIC/os_observed=false.
This trusted injection interface is not a sandbox against hostile Python code.
No new dependency is installed. Python's RLock serializes provider ownership
without creating a thread; competing owner calls reject without waiting.

The signatures use 32-bit DWORD/BOOL and pointer-sized HANDLE/ULONG_PTR. On x64,
OVERLAPPED is 32 bytes and SECURITY_ATTRIBUTES is 24 bytes, with normal ABI
alignment. Windows x86 layouts are specified but not executed in B1. WinDLL would
supply WINAPI and `use_last_error=True`; the loader stays unreachable. Every
function call captures last error before cleanup or logging. GetSecurityInfo's
DWORD return is interpreted directly. NULL and INVALID_HANDLE_VALUE reject.

## Endpoint and identity

The server uses one local `qsg-r3-<32 hex>` endpoint, byte mode, one instance,
4096-byte buffers, FILE_FLAG_FIRST_PIPE_INSTANCE, FILE_FLAG_OVERLAPPED and
PIPE_REJECT_REMOTE_CLIENTS. SECURITY_ATTRIBUTES is non-inheritable and retains
its explicit descriptor until CreateNamedPipeW returns. There is no fallback DACL.

The B1 DACL policy requires a specific account owner SID and two **distinct logon
SIDs**, observed through TokenGroups in future execution. The server ACE has
0x12019f and the client ACE has 0x120003. The client mask excludes bit 0x4, the
FILE_APPEND_DATA/FILE_CREATE_PIPE_INSTANCE alias; GENERIC_WRITE must not be used
to bypass that restriction. The current CE client's requested access is unknown.
Two processes in the same logon cannot meet this proposal by changing labels.
Dedicated distinct logon contexts and client access feasibility need review and
separate authorization. Broad user/group fallback is prohibited.

After creation and again during client verification, GetSecurityInfo reads the
same server handle. The provider checks owner, non-null DACL, present/protected
control bits, exact two non-inherited allow ACEs and exact access masks. Creation
success alone is not proof. Descriptor and converted SID buffers are LocalFree'd.

GetNamedPipeClientProcessId is called only on that connected server instance.
OpenProcess requests QUERY_LIMITED_INFORMATION and SYNCHRONIZE, never memory or
duplication rights. A held process handle binds fresh creation FILETIME, image
path, TokenUser and the enabled logon group. The executable is hashed through a
read-only file handle with no write/delete sharing, with bounded file size/chunks.
PID and process liveness are checked again after sampling. The process handle
stays owned until connection cleanup. The file hash proves disk bytes; mapped
image/DLL equivalence is explicitly NOT_PROVEN and remains a native prerequisite.

Client-side server identity always reports BLOCKED_CLIENT_HANDLE_UNVERIFIED.
Microsoft's GetNamedPipeServerProcessId documentation specifies a handle created
by CreateNamedPipe. This implementation does not call it on an assumed CE handle.
No handle guessing, process memory inspection, global handle scraping, process
termination or DuplicateHandle is present. A future documented CE-owned export or
independently reviewable authenticated helper route needs separate design review
and exact process/privilege authorization before any implementation or execution.

The B0 mutual challenge model remains data-only and binds authorization/candidate
digests, both identities, session, channel, epoch, connection, descriptor and both
role-separated challenges. Native `challenge` returns
BLOCKED_RUNTIME_SECRET_PROVISIONING. A future fresh per-connection secret must be
provisioned through an approved authenticated out-of-band channel, never command
lines, logs or the unverified pipe. No secret-provisioning mechanism is assumed.

## Lua, deadlines and cleanup

The unchanged isolated Lua adapter accepts only injected byte methods. It exposes
HELLO/ECHO/PING/CANCEL/CLOSE under qsg.native-probe.v1, canonical UTF-8 JSON, exact
field sets, duplicate-key rejection, fixed request identity/epoch and single-frame
boundaries. It has no target attach/scan/memory/AA/shell/dynamic-load capabilities.
B1 sends actual fake WinAPI bytes through this client in standalone Lua 5.3 and
5.4. Neither is an observation of CE embedded `_VERSION` or installed API behavior.
The actual connectToPipe shape, Timeout units, destroy completion, exported handle
and UI/worker cancellation remain unverified. UNKNOWN_MODEL is not a native unit.

One operation owns one OVERLAPPED, event and buffer. Read/write allocations reject
invalid bounds before allocation. A fixed owner-clock deadline is checked before
dispatch and after success; late success is rejected. Connect's completion byte
count is ignored because Win32 leaves it undefined. There is no retry/reconnect.

CancelIoEx is a request, including ERROR_NOT_FOUND races. The provider retains
the operation, event, pipe and buffer until GetOverlappedResult confirms terminal
completion. Unknown completion errors remain uncertain. A module-level retention
map prevents GC from reclaiming pending storage if the caller drops its reference.
It is released only after observed completion; an indefinitely pending operation
requires externally authorized resolution, not a fabricated cleanup PASS.
CloseHandle is attempted at most once per owned handle; failure leaves UNCERTAIN.
Disconnect/close never waits for a peer to drain, and FlushFileBuffers is not used.

The owner uses a single monotonic clock; watchdog and Lua clocks stay distinct.
The 250 ms RPC, 2 s external cutoff, 60 s case, 15 min session, one CE/server/request,
three repetitions/vector and twenty cleanup cycles are proposals, not measured
native limits. Existing Limits/Watchdog tests exercise model boundaries. The B1
trace bundle records twenty cleanups plus three cancellation, timeout and late
completion vectors each. Its watchdog cutoff model is separate evidence, not a
claimed OS hard stop or a cross-clock latency measurement.

Local metadata calls and synchronous executable-file reads cannot be interrupted
by merely checking a Python clock. The provider checks the deadline around them,
but an independent externally enforceable hard stop still requires R3-B design,
measurement and explicit exact-process cleanup authority. Moving a blocking CE
call to a worker does not establish UI responsiveness or cancellation semantics.

## Long-path evidence and protected scope

`native_probe_b1_boundary.py` measures both evidence data-body length and the
serialized record envelope, separately from the four-byte wire prefix. Exact
65,535/65,536/65,537 UTF-8 bytes are exercised at short and long Unicode paths.
The wire limit applies to the JSON body; the legacy evidence limit applies to
record.data. Oversize headers reject before body allocation/transport. The
65,536 limit is not enlarged and required fields are not removed or truncated.

The original QSG full-session L12-MISSING payload duplicates retained evidence
and embeds absolute paths. Its protected serializer rejects PAYLOAD_BOUND when
that data exceeds 65,536. B1 retains fresh short/119-character/long reproductions
and runs the entire repository test set at normal and deliberately long temp
paths. A passing shorter-path run cannot clear a longer-path failure.

A content-addressed retained-evidence record with separately hashed path metadata
is a possible future design. Substituting it changes the protected evidence
contract and its verifier/fixture expectations; it is **not** applied here.
BLOCKED_LONG_PATH_FIX_OUT_OF_SCOPE is retained if the protected reproduction
fails. A separate bounded scope request must identify the protected serializer,
fixture and verifier files and preserve raw evidence without increasing the cap.

## Reproduction and admission

The fresh B1 report directory records exact argv, runtime binary hashes, selected
environment, each attempt's output and exit code, source hashes, original failures,
boundary raw records, patch reconstruction and frozen-input comparisons. Its
`run_command.py` uses exclusive-create output paths and the existing pinned Python
3.14/Lupa 5.3/5.4 environment. Never overwrite an earlier attempt.

The independent `native_probe_b1_verifier` imports neither provider nor recorder,
watchdog, tests or Lua. It replays event chains, ownership order, bytes/digests,
deadline/cancel outcomes and distinct actor clocks. Mutation tests also recompute
hashes, so semantic rejection is tested separately from anchor mismatch. As with
B0, integrity needs separately retained anchors. This is independent code/data
replay, not an independent human or subagent review, nor OS authentication.

Before R3-B: independently review code and this candidate, resolve or explicitly
accept protected long-path limitations, establish trusted signed scope-specific
authorization, fix exact CE EXE/DLL/probe and candidate hashes, identities, absolute
window, evidence directory, cases/vectors and cleanup privileges. Verify supported
dedicated CE startup excludes existing-instance reuse, autorun, restored sessions
and auto-attach. A new user/profile directory or an executable hash alone does not
prove these. The launch-isolation proposal is a dedicated separately authorized
logon/profile plus independently recorded startup configuration and process
creation lineage; it stays BLOCKED until the installed build's supported controls
and absence of those paths can be demonstrated without launching CE in B1.

Then resolve client handle provenance, requested access masks, bilateral OS peer
identity, component equivalence, secret provisioning, DACL readback, timeout/UI
responsiveness, cancellation completion and external watchdog cleanup. Any
termination or PROCESS_DUP_HANDLE must name an exact owned PID+creation instance
and receive separate permission. Native transport qualification never grants G1.

Preserve IMPLEMENTED_PENDING_CE_QUALIFICATION, ATTACHMENT_HANDLE_UNVERIFIED,
NOT_PRODUCTION_AUTHORIZED, A6_R3_T1_SEPARATE_PENDING and R2_T1_FAILED_NOT_QUALIFIED.
No new version tag is recommended.

## Primary references (design evidence, not installed-runtime observations)

- [CreateNamedPipeW](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-createnamedpipew)
- [Pipe security and access rights](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights)
- [Client PID query](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeclientprocessid)
- [Server PID handle contract](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeserverprocessid)
- [OVERLAPPED ABI](https://learn.microsoft.com/en-us/windows/win32/api/minwinbase/ns-minwinbase-overlapped)
- [Completion observation](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-getoverlappedresult)
- [CancelIoEx](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex)
- [GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo)
- [Token information](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation)
- [Token groups](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-token_groups)
