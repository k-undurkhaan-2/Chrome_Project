"""B1 API injection, not observed native execution."""
import ctypes as C
from copy import deepcopy
import gc
import pytest

from ce_qualification import native_probe_win32 as w
from ce_qualification.native_probe_protocol import Decoder, ProbeError, Session
from ce_qualification.native_probe_winpipe import NativeProvider, open_native
from native_probe_b0_fakes import CePipeTransport
from native_probe_b1_fakes import SPEC, EXPECTED, ENDPOINT, equipment, FakeWinAPI


def test_abi_width_alignment_and_signatures():
    assert C.sizeof(w.DWORD) == C.sizeof(w.BOOL) == 4
    width = C.sizeof(C.c_void_p)
    assert C.sizeof(w.OVERLAPPED) == (32 if width == 8 else 20)
    assert w.OVERLAPPED.hEvent.offset == (24 if width == 8 else 16)
    assert C.sizeof(w.SECURITY_ATTRIBUTES) == (24 if width == 8 else 12)
    assert w.SECURITY_ATTRIBUTES.lpSecurityDescriptor.offset == width
    assert w.INVALID_HANDLE_VALUE == 2 ** (width * 8) - 1
    assert w.SIGNATURES["CreateNamedPipeW"][1] is w.HANDLE
    assert w.SIGNATURES["GetSecurityInfo"][1] is w.DWORD
    assert w.SIGNATURES["CancelIoEx"][2] == [w.HANDLE, w.P_OV]
    assert w.SIGNATURES["GetOverlappedResult"][2][-1] is w.BOOL
    assert "GetNamedPipeServerProcessId" not in w.SIGNATURES
    assert not any(x in w.SIGNATURES for x in ("TerminateProcess", "DuplicateHandle", "ReadProcessMemory", "WriteProcessMemory"))


def test_default_denial_precedes_dll_loader(monkeypatch):
    monkeypatch.setattr(C, "WinDLL", lambda *_a, **_k: pytest.fail("native loader entered"), raising=False)
    for call in (w.load_native_api, open_native, lambda: NativeProvider().create(SPEC)):
        with pytest.raises(ProbeError, match="BLOCKED_NATIVE_ACTIVATION_UNPROVEN"): call()
    with pytest.raises(ProbeError): w.WinAPI({}, lambda: 0, origin="NATIVE")


@pytest.mark.parametrize("value", [None, 0, w.INVALID_HANDLE_VALUE])
def test_create_invalid_handle_preserves_last_error(value):
    f = FakeWinAPI(); f.create_value = value
    p = NativeProvider(api=f.api, clock_ms=f.clock)
    with pytest.raises(w.Win32Error) as error: p.create(SPEC)
    assert error.value.winerror == 5  # LocalFree changes thread error to 999
    assert not f.closed and "GetSecurityInfo" not in f.calls


@pytest.mark.parametrize("fault", ["null_acl", "unprotected", "wrong_owner", "extra_ace", "generic_write", "inherited", "wrong_logon", "readback_denied"])
def test_dacl_creation_is_not_acl_proof(fault):
    f = FakeWinAPI()
    if fault == "null_acl": f.null_acl = True
    elif fault == "unprotected": f.control = 4
    elif fault == "wrong_owner": f.spec["owner_sid"] = "S-1-5-21-1-2-3-9999"
    elif fault == "extra_ace": f.ace_count = 3
    elif fault == "generic_write": f.ace_mask = 0x40000000
    elif fault == "inherited": f.ace_flags = 0x10
    elif fault == "wrong_logon": f.spec["client_logon_sid"] = "S-1-5-5-99-99"
    elif fault == "readback_denied": f.security_error = 5
    p = NativeProvider(api=f.api, clock_ms=f.clock)
    with pytest.raises(ProbeError): p.create(SPEC)
    assert f.closed.count(f.pipe) == 1 and p.revoked
    with pytest.raises(ProbeError): p.create(SPEC)
    assert f.calls.count("CreateNamedPipeW") == 1


def test_spec_excludes_create_instance_alias_and_nonlocal_names():
    assert SPEC["client_access"] & (4 | 0x40000000) == 0
    with pytest.raises(ProbeError): w.native_spec("\\\\remote\\pipe\\x", SPEC["owner_sid"], SPEC["server_logon_sid"], SPEC["client_logon_sid"])
    with pytest.raises(ProbeError): w.native_spec(ENDPOINT, SPEC["owner_sid"], SPEC["client_logon_sid"], SPEC["client_logon_sid"])


@pytest.mark.parametrize("fault", ["pid", "creation", "path", "sid", "logon_sid", "hash", "pid_reused", "exited", "token_oversize", "logon_disabled", "dacl_changed"])
def test_client_identity_is_fresh_and_bound_to_instance(fault):
    p, f, h = equipment()
    if fault == "pid": f.identity["pid"] = 999
    elif fault == "creation": f.identity["creation"] = "0000000000000002"
    elif fault == "path": f.identity["path"] = "D:\\synthetic\\wrong.exe"
    elif fault in ("sid", "logon_sid"): f.identity[fault] += "9"
    elif fault == "hash": f.image_bytes = b"tampered"
    elif fault == "pid_reused": f.pid_after = 202
    elif fault == "exited": f.process_exited = True
    elif fault == "token_oversize": f.token_size_override = 65537
    elif fault == "logon_disabled": f.logon_attributes = 0xC0000010
    elif fault == "dacl_changed": f.ace_mask = 0x120007
    with pytest.raises(ProbeError): p.query_client(h, EXPECTED, deadline_ms=250)
    assert p.revoked and p.close() and len(f.closed) == len(set(f.closed))


def test_client_query_is_only_unilateral_and_closes_owned_resources_once():
    p, f, h = equipment()
    result = p.query_client(h, EXPECTED, deadline_ms=250)
    assert result["client"] == EXPECTED and not result["os_observed"]
    assert result["server_identity"] == "BLOCKED_CLIENT_HANDLE_UNVERIFIED"
    assert f.process not in f.closed
    with pytest.raises(ProbeError, match="BLOCKED_CLIENT_HANDLE_UNVERIFIED"): p.query_connection(h)
    with pytest.raises(ProbeError, match="BLOCKED_RUNTIME_SECRET_PROVISIONING"): p.challenge()
    assert p.close(h) and p.close(h) and f.closed.count(h) == f.closed.count(f.process) == 1


@pytest.mark.parametrize("direction", ["CONNECT", "READ", "WRITE"])
@pytest.mark.parametrize("completion", [0, w.OPERATION_ABORTED, w.BROKEN_PIPE])
@pytest.mark.parametrize("cancel_error", [0, w.NOT_FOUND])
def test_cancel_never_frees_pending_storage(direction, completion, cancel_error):
    p, f, h = equipment(connect=direction != "CONNECT")
    f.pending_direction, f.cancel_error = direction, cancel_error
    result = p.start_io(h, "pending", direction, b"abc" if direction == "WRITE" else b"", 3 if direction != "CONNECT" else 0, deadline_ms=250)
    assert result["status"] == "PENDING"
    op = p.pending; key = id(op)
    assert not p.close() and not p.close() and p.pending is op
    assert f.calls.count("CancelIoEx") == 1 and h not in f.closed and op.event.value not in f.closed
    gc.collect(); assert w._INFLIGHT[key] is p
    f.completion = completion
    result = p.poll_io(h, "pending")
    assert result["status"] != "COMPLETE" and p.pending is None and key not in w._INFLIGHT
    assert p.close() and len(f.closed) == len(set(f.closed))


def test_unknown_completion_error_retains_operation_and_handle():
    p, f, h = equipment(); f.pending_direction = "READ"
    p.start_io(h, "read", "READ", maximum=3, deadline_ms=250)
    f.completion = 6
    assert p.poll_io(h, "read")["status"] == "PENDING" and p.pending is not None
    assert not p.close() and h not in f.closed
    f.completion = w.OPERATION_ABORTED; p.poll_io(h, "read"); assert p.close()


@pytest.mark.parametrize("mode", ["immediate", "pending", "late_success", "clock_reversed"])
def test_fixed_deadline_races(mode):
    p, f, h = equipment()
    if mode in ("pending", "late_success"): f.pending_direction = "READ"
    if mode == "immediate": f.hook = lambda name: f.clock.advance(250) if name == "ReadFile" else None
    result = p.start_io(h, "read", "READ", maximum=3, deadline_ms=250)
    if mode == "immediate": assert result["status"] == "REJECTED_LATE"
    elif mode == "pending":
        result = p.await_io(h, "read"); assert f.clock() == 250 and result["status"] == "PENDING"
        f.completion = w.OPERATION_ABORTED; p.poll_io(h, "read")
    elif mode == "late_success":
        f.clock.advance(250); f.completion = 0
        assert p.poll_io(h, "read")["status"] == "REJECTED_LATE"
    else:
        f.clock.value = -1
        with pytest.raises(ProbeError): p.start_io(h, "next", "READ", maximum=3, deadline_ms=250)
        f.clock.value = 0
    assert p.close()


@pytest.mark.parametrize("count", [0, 4, 0xFFFFFFFF])
def test_bad_counts_are_terminal_failure_not_buffer_overread(count):
    p, f, h = equipment(); f.count_override = count
    result = p.start_io(h, "read", "READ", maximum=3, deadline_ms=250)
    assert result["status"] == "FAILED" and result["data"] == b"" and p.pending is None
    assert p.close()


def test_wrong_handle_replay_and_close_failure():
    p, f, h = equipment()
    with pytest.raises(ProbeError): p.start_io(h + 1, "r", "READ", maximum=1, deadline_ms=250)
    with pytest.raises(ProbeError): p.start_io(h, "connect", "READ", maximum=1, deadline_ms=250)
    f.close_failure = True
    assert not p.close() and not p.close() and p.cleanup == "UNCERTAIN" and f.closed.count(h) == 1


@pytest.mark.parametrize("api", ["CreateEventW", "ReadFile", "WriteFile"])
def test_api_failures_do_not_retry(api):
    p, f, h = equipment(); f.fail_api, f.fail_error = api, w.BROKEN_PIPE
    direction = "WRITE" if api == "WriteFile" else "READ"
    try:
        result = p.start_io(h, "io", direction, b"abc" if direction == "WRITE" else b"", 3, deadline_ms=250)
        assert result["status"] == "FAILED"
    except w.Win32Error as error:
        assert api == "CreateEventW" and error.winerror == w.BROKEN_PIPE
    p.close(); assert f.closed.count(h) == 1


def test_oom_before_start_cannot_dispatch(monkeypatch):
    p, f, h = equipment(); calls = len(f.calls)
    monkeypatch.setattr(C, "create_string_buffer", lambda *_: (_ for _ in ()).throw(MemoryError()))
    with pytest.raises(MemoryError): p.start_io(h, "read", "READ", maximum=3, deadline_ms=250)
    assert "ReadFile" not in f.calls[calls:] and p.pending is None and p.revoked


@pytest.mark.parametrize("backend", ["lua53", "lua54"])
@pytest.mark.parametrize("fragment", [1, 127, 4096])
def test_winapi_body_to_isolated_lua_byte_client(backend, fragment):
    binding = {"session_id": "b1", "channel_id": "channel", "epoch": 1}
    ce = CePipeTransport(binding, backend=backend, endpoint=ENDPOINT)
    ce.read_size = ce.write_size = fragment
    p, f, h = equipment(client=ce); f.write_limit = fragment
    session = Session(**binding, clock_ms=f.clock)
    ordinal = 0
    for method, payload in [("HELLO", ""), ("ECHO", "你好🙂" * 50), ("PING", ""), ("CLOSE", "")]:
        raw = session.begin(method, method.lower(), payload)
        while raw:
            ordinal += 1; part = raw[:4096]
            result = p.start_io(h, str(ordinal), "WRITE", part, len(part), deadline_ms=session.deadline)
            assert result["status"] == "COMPLETE"; raw = raw[result["count"]:]
        decoder = Decoder(session.deadline, f.clock); answer = None
        while answer is None:
            ordinal += 1
            result = p.start_io(h, str(ordinal), "READ", maximum=4096, deadline_ms=session.deadline)
            assert result["status"] == "COMPLETE"
            answer = decoder.feed(result["data"])
        assert session.accept(answer)["payload"] == payload
    assert p.close() and ce.close() is True


def test_twenty_connection_cleanup_cycles():
    for _ in range(20):
        p, f, h = equipment(); p.query_client(h, EXPECTED, deadline_ms=250)
        assert p.close() and len(f.closed) == len(set(f.closed))
    assert not w._INFLIGHT


def test_pending_connect_ignores_undefined_completion_byte_count():
    p, f, h = equipment(connect=False); f.pending_direction = "CONNECT"
    assert p.start_io(h, "connect", "CONNECT", deadline_ms=250)["status"] == "PENDING"
    f.completion, f.count_override = 0, 0xFFFFFFFF
    assert p.poll_io(h, "connect") == {"operation": "connect", "status": "COMPLETE", "count": 0, "data": b""}
    assert p.close()


def test_already_connected_race_and_single_outstanding_io():
    p, f, h = equipment(connect=False); f.connect_error = w.PIPE_CONNECTED
    assert p.start_io(h, "connect", "CONNECT", deadline_ms=250)["status"] == "COMPLETE"
    f.pending_direction = "READ"
    p.start_io(h, "read", "READ", maximum=1, deadline_ms=250)
    with pytest.raises(ProbeError, match="IO_OVERLAP_OR_REVOKED"):
        p.start_io(h, "second", "WRITE", b"x", 1, deadline_ms=250)
    p.close(); f.completion = w.OPERATION_ABORTED; p.poll_io(h, "read"); assert p.close()


def test_concurrent_owner_denies_without_wait_or_native_dispatch():
    from threading import Lock
    p, f, h = equipment(); original = p._lock
    lock = Lock(); lock.acquire(); p._lock = lock
    before = list(f.calls)
    with pytest.raises(ProbeError, match="CONCURRENT_OWNER"):
        p.start_io(h, "read", "READ", maximum=1, deadline_ms=250)
    assert f.calls == before
    p._lock = original; lock.release(); assert p.close()


def test_identity_and_creation_late_success_fail_closed():
    p, f, h = equipment()
    f.hook = lambda name: f.clock.advance(250) if name == "QueryFullProcessImageNameW" else None
    with pytest.raises(ProbeError, match="REQUEST_TIMEOUT"):
        p.query_client(h, EXPECTED, deadline_ms=250)
    assert p.revoked and p.close()
    f = FakeWinAPI(); p = NativeProvider(api=f.api, clock_ms=f.clock)
    f.hook = lambda name: f.clock.advance(250) if name == "CreateNamedPipeW" else None
    with pytest.raises(ProbeError, match="REQUEST_TIMEOUT"): p.create(SPEC)
    assert p.close() and f.closed.count(f.pipe) == 1


def test_trace_limit_cannot_silently_drop_an_event():
    p, f, h = equipment(); p.trace_bytes = 8 * 1024 * 1024
    with pytest.raises(ProbeError, match="TRACE_FULL"): p._record("UNRECORDED")
    assert all(r["event"] != "UNRECORDED" for r in p.trace)
    p.trace_bytes = 0; assert p.close()


def test_start_record_failure_closes_unsubmitted_event_without_cancellation():
    p, f, h = equipment(); before = len(f.calls)
    record = p._record
    def fail_start(event, **data):
        if event == "IO_START": raise MemoryError("synthetic record allocation failure")
        return record(event, **data)
    p._record = fail_start
    with pytest.raises(MemoryError): p.start_io(h, "never-submitted", "READ", maximum=1, deadline_ms=250)
    assert p.pending is None and not w._INFLIGHT and p.revoked
    assert "ReadFile" not in f.calls[before:] and "CancelIoEx" not in f.calls[before:]
    assert p.close() and len(f.closed) == len(set(f.closed))
