# H3-A5 Windows process instance and clock observer

Status: inactive, read-only component; synthetic qualification and operator native
qualification are separate gates. No existing runner, Full/Single, H1/H2 or H3
constructor imports or calls this component. Import executes no imports, file,
process, network, clock, registry, CE or native library operations. Explicit
construction and `observe()` are required. No configuration enables it.

## API and trust boundary

```python
boundary = NativeWin32Boundary()  # Explicit trusted bootstrap, loads System32 APIs.
with ProcessObserver(
    independently_selected_pid, boundary,
    expected_executable=independently_selected_canonical_path,
    expected_architecture="x64",
    max_elapsed_ms=5000, tolerance_ms=32, max_sample_ms=100,
) as observer:
    first = observer.observe()
    second = observer.observe()
    public_bytes = observer.render(second)
```

There is no implicit PID, process-name lookup, scanning, default native boundary,
CE attachment, scene assertion, target address, memory or write interface. The
constructor validates arguments and captures six bound methods once; it does
not open a handle. `observe()` opens one handle on first use and retains it until
close/rejection. The caller must close the observer, preferably with `with`.
No destructor performs implicit OS activity. A boundary must implement:

| Method | Exact return contract |
| --- | --- |
| `open_process(pid)` | Positive process-handle integer; no null or pseudo handle. |
| `close_handle(handle)` | Literal `True` after successful close. |
| `is_running(handle)` | Literal Boolean from a zero-time handle wait. |
| `identity(handle)` | Exact tuple `(pid, creation_filetime, executable, architecture)`. |
| `wall_filetime()` | Integer Windows UTC FILETIME, without conversion to float. |
| `monotonic_ms()` | Integer monotonic milliseconds, 0 through `2^53-1`. |

This dependency is trusted code. An injected simulation does not become a real
OS measurement because it returns valid fields. The `os_query_boundary` label
names the interface; provenance is established by the independently reviewed
bootstrap and native probe, not by the label. Expected PID/path/architecture are
constraints on measured data, never substitutes for missing OS results. No
caller-provided creation time, attachment ID or scene is accepted as evidence.

The component is single-threaded, bounded to 64 observations. Capturing methods
prevents ordinary dependency replacement after construction; it cannot defend
against arbitrary hostile Python code, a replaced runtime, or a malicious OS.
Reentrant use poisons the outer observation. Errors close the handle once,
invalidate previous public results, and permanently reject further measurement.
Close uncertainty is `CLOSE_FAILED`; it is never retried with a potentially
reused handle. Interrupted measurements also attempt close and poison the object.

## Native identity

`NativeWin32Boundary` lazily loads `kernel32.dll` using System32 search mode and
explicit pointer-width ctypes signatures. No fallback to WMI, PowerShell text,
operator claims or an older ambiguous architecture API exists. Missing APIs
reject construction. The native allowlist is exactly:

`OpenProcess`, `CloseHandle`, `WaitForSingleObject`, `GetProcessId`,
`GetProcessTimes`, `QueryFullProcessImageNameW`, `IsWow64Process2`,
`GetSystemTimePreciseAsFileTime`, `GetTickCount64`.

The access mask is `0x00101000`: `PROCESS_QUERY_LIMITED_INFORMATION` plus
`SYNCHRONIZE`. The additional right is solely for a nonblocking wait with timeout
zero, which detects a terminated process even if it exited with code 259.
`GetExitCodeProcess` alone would confuse that exit code with `STILL_ACTIVE`.
No VM read/write/operation, debugger privilege, enumeration, injection,
suspension or process termination rights or APIs are requested.

Each observation checks liveness before and after two complete identity queries
through the same held handle. PID must equal the explicitly selected PID;
creation FILETIME, exact measured image spelling and architecture must agree
within and across observations. A recycled numeric PID cannot replace the held
instance. A new observer establishes a new observation, not continuity with an
old observer. The operator probe additionally compares the independent opened
handle against its retained `Popen` launch handle and creation time.

The image buffer has 261 UTF-16 character slots; returned character count,
terminator and actual string length must agree, with at most 260 characters.
The conservative canonical subset is an uppercase drive-qualified ASCII path,
backslash separators, executable basename ending in `.exe`, no empty/dot/dot-dot
components, trailing dots/spaces, streams, reserved DOS devices, controls,
wildcards, short-name tilde, UNC/device prefix or alternate separators. Ambiguous
spellings are rejected, not normalized. This is a measured path identity, not a
file-content signature, file-ID guarantee, junction equivalence proof or DLL
provenance measurement. Native T1 records the separately pinned interpreter hash.

Supported `IsWow64Process2` pairs are unknown/x86 -> x86, unknown/AMD64 -> x64,
and x86/AMD64 -> x86. ARM64 and other combinations fail closed. An expected
architecture mismatch is distinct from an unsupported architecture.

Creation and UTC values retain raw 100-ns FILETIME ticks. Canonical encoding is
`YYYY-MM-DDTHH:MM:SS.fffffffZ`, 1970 through 9999, Gregorian UTC only. Integer
division preserves all seven fractional digits without local timezone/DST or
floating-point rounding. These digits encode the API representation, not a
claim of measured 100-ns accuracy. This schema is deliberately separate from
A2's whole-second UTC format; no implicit truncation or adapter is provided.

## Clock checks

Every sample brackets identity and UTC queries with `GetTickCount64` readings:
`monotonic_before`, liveness/identity, UTC, identity/liveness, `monotonic_after`.
Both monotonic values must be integral, nonnegative, within `2^53-1`, and ordered.
The complete sample width is at most `max_sample_ms` (1-1000, no larger than the
elapsed limit). A later sample cannot start before the previous sample ended.
Creation cannot follow its observed wall UTC. UTC rollback by even one tick is
rejected; no rounding hides it.

The conservative total elapsed bound is `current.after - first.before`, at most
`max_elapsed_ms` (1-120000). For both first/current and adjacent sample pairs,
UTC elapsed ticks must lie within the monotonic interval
`[max(0, current.before - previous.after - tolerance),
current.after - previous.before + tolerance] * 10000`.
`tolerance_ms` is explicitly bounded to 16-1000; default 32 reflects tick-clock
granularity and sampling uncertainty, not a measured wall-time accuracy claim.
Checking the first sample as well as adjacent pairs prevents cumulative drift
from escaping this observation window. Overflow, booleans, floats, missing
fields, regressions, forward jumps and long pauses fail closed.

Two consistent readings cannot prove tamper-proof UTC, unobserved continuity,
suspend-safe monotonic behavior, ABA resistance, exclusion of concurrent changes
or freedom from TOCTOU. These remain `NOT_QUALIFIED`. No system clock is changed
by any test; rollback, jump and suspend cases are injected simulations.

## Results and failures

Successful observations have `OS_PROCESS_CONTEXT_OBSERVED_NOT_AUTHORIZED`.
Failures have `REJECTED` and a fixed allowlisted reason, never exception text.
The module's `ERROR_CODES` enumerates bounded argument, handle, process, image,
architecture, time, lifecycle and dependency failures. Unknown dependency
exceptions map to `DEPENDENCY_REJECTED`. Constructor failures raise a bounded
`ObserverError`; measurement failures return a bounded result.

Every public result always has:

```text
attachment_verified=false
scene_os_measured=false
authorization_status=NOT_PRODUCTION_AUTHORIZED
handoff_write_ready=false
write_ready=false
write_attempted=false
restore_attempted=false
memory_read_attempts=0
memory_write_attempts=0
independent_review_required=true
```

`render` emits deterministic ordered ASCII `key=value\r\n`, below 2048 bytes,
without PID, raw path, timestamps or operator details. Result tuples are immutable;
only the latest exact object from the issuer may be rendered. Copies, foreign or
malformed objects and results revoked by another observation, close or explicit
`revoke()` render `INVALID_RESULT`. `diagnostic_observations()` is an explicit
private view containing the measured path; only the approved native helper
test stores detailed diagnostics in its disposable child. Diagnostics are never
an authority token.

This module does not implement production H3-A2 `identity()` or adapt A4's clock.
A2 only has `new_synthetic`, requiring `attachment_verified=true` and
`measurement_basis=synthetic_os_measurement`. A5 must never fake those fields.
OS identity, operator scene assertion and CE attachment identity are three
separate facts. Future integration needs a separately authorized attachment
adapter, independent review and operational approval. H3-A4 native GnuPG Agent
isolation remains `UNQUALIFIED`; its publication waiver has no operational effect.

## Synthetic and native qualification

The deterministic pytest module covers identity/restart/PID reuse, malformed
fields/paths, access denial, exact Win32 ABI mocks, missing APIs, architecture,
exit detection, handle cleanup, UTC precision, overflow, clock faults, long
pause, result invalidation, import inertness and absence of Lua dispatch. Native
DLL loading is forbidden in the ABI mock test. The standalone probe filename
does not start with `test_`; importing it is inert too.

P1R requires the actual discovered A5 N cases, unchanged ordered 3711 baseline
cases (753 A4 plus 2958 legacy), and combined N+3711. The 95 A4 subchecks are
separate. Require zero failures/errors/skips/xfail/xpass/deselection, fresh
subprocess exits/JUnit, complete preflight ordered-ID comparisons, frozen-source
review and preservation checks. Use the unchanged approved CPython 3.14.3,
pytest 9.1.0, E2 Lupa 2.8/Lua 5.4; no bytecode, cache, plugin autoload or `.pth`
processing. Harness, diagnostics and outputs stay outside this repository.

After P1R, the external hash-pinned PowerShell handoff supplies concrete commands,
four source SHA-256 values, manifest digest and interpreter digest. Run under the
approved ordinary Windows account with `-I -B -S`, mode `identity-native-only`,
diagnostics `debug`. The probe independently queries current token SID/elevation
and LocalAppData, prints all twelve required check families, and requires the
operator to type `APPROVE`. It creates one exclusive
`%LOCALAPPDATA%\ChromeProject-H3-Identity-Qualification\identity-<UUID>` child.
Reparse ancestors and unexpected content reject. No root switching, ACL edits,
elevation, cleanup or private files are involved.

The only observed process is the probe's own finite-lived Python helper launch.
On Windows a venv launcher may delegate Python code to a worker; only the direct
retained launch PID/handle is observed. No worker discovery or arbitrary process
selection is performed. The helper exits naturally after three seconds; no
kill/terminate fallback exists. Check failure or helper timeout blocks native
qualification and retains partial diagnostics. Source/interpreter bytes and
root identities are rechecked, evidence is exclusively created and independently
reopened, and the final ZIP is reopened and verified before successful exit.
Content hashes bind bytes; they do not confer source authentication, immutable
storage against an adversary, or prove the operator's identity by themselves.

The bounded `native-identity-bundle.zip` contains exactly:

```text
native-receipt.json
native-results.json
process-observations.json
clock-observations.json
source-manifest.json
process-transcripts.json
```

Return the original unedited ZIP, its printed SHA-256, raw wrapper stdout/stderr,
`native-parent-exit-code=0` and `native-wrapper-exit-code=0`. Failure may produce
no ZIP; return raw output and any `native-failure.json` without editing/repacking.
The receiver must independently verify sources, checks, SID/non-elevation, root,
OS build/architecture/filesystem, helper identity, clocks, hashes, scope and exit
codes. A console PASS is insufficient. Native acceptance applies only to the
recorded helper test environment, not CE attachment or write/restore authority.
Until accepted original T1 evidence is returned, do not stage, commit or push.

## Primary API references

- [Process access rights](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights)
- [GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes)
- [QueryFullProcessImageNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew)
- [IsWow64Process2](https://learn.microsoft.com/en-us/windows/win32/api/wow64apiset/nf-wow64apiset-iswow64process2)
- [GetSystemTimePreciseAsFileTime](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemtimepreciseasfiletime)
- [GetTickCount64](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-gettickcount64)
- [WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject)
