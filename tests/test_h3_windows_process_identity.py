"""Deterministic A5 simulation. No native DLL load, process launch or CE operation."""

import builtins
import copy
import ctypes
from pathlib import Path

import pytest

from armedforces_tool import h3_windows_process_identity as m

IMAGE = r"C:\TestOnly\python.exe"
CREATED = m.FILETIME_EPOCH + 17000000000000000
WALL = CREATED + 10000000


class FakeBoundary:
    def __init__(self):
        self.context = (101, CREATED, IMAGE, "x64")
        self.wall, self.mono = WALL, 1000
        self.running = True
        self.calls = []
        self.fault = None

    def record(self, name, *args):
        self.calls.append((name, args))
        if self.fault == name:
            raise RuntimeError("PRIVATE exception details")

    def open_process(self, pid):
        self.record("open", pid)
        return 42

    def close_handle(self, handle):
        self.record("close", handle)
        return True

    def is_running(self, handle):
        self.record("running", handle)
        return self.running

    def identity(self, handle):
        self.record("identity", handle)
        return self.context

    def wall_filetime(self):
        self.record("wall")
        return self.wall

    def monotonic_ms(self):
        self.record("mono")
        return self.mono


def observer(boundary=None, **kwargs):
    return m.ProcessObserver(101, boundary or FakeBoundary(), expected_executable=IMAGE,
                             expected_architecture="x64", **kwargs)


def rejected(result, code):
    assert result.status == "REJECTED" and result.reason_code == code
    nonoperational(result)


def nonoperational(result):
    for key in ("attachment_verified", "scene_os_measured", "handoff_write_ready", "write_ready",
                "write_attempted", "restore_attempted"):
        assert getattr(result, key) is False
    assert result.authorization_status == "NOT_PRODUCTION_AUTHORIZED"
    assert result.memory_read_attempts == result.memory_write_attempts == 0
    assert result.independent_review_required is True


def test_two_observations_one_held_handle_and_private_diagnostics():
    b = FakeBoundary()
    with observer(b) as o:
        first = o.observe()
        assert first.status == m.SUCCESS
        b.wall += 2500000
        b.mono += 250
        second = o.observe()
        assert second.status == m.SUCCESS and second.observation_count == 2
        assert second.elapsed_upper_ms == 250
        nonoperational(second)
        assert o.diagnostic_observations()[0][0] == b.context
        assert b"INVALID_RESULT" in o.render(first)
        public = o.render(second)
        assert IMAGE.encode() not in public and b"101" not in public and len(public) < 2048
        assert public == o.render(second) and public.endswith(b"\r\n")
    assert [x[0] for x in b.calls].count("open") == 1
    assert b.calls[-1] == ("close", (42,))
    assert b"INVALID_RESULT" in o.render(second)


@pytest.mark.parametrize("change,code", [
    ((101, CREATED + 1, IMAGE, "x64"), "IDENTITY_CHANGED"),
    ((102, CREATED, IMAGE, "x64"), "PID_MISMATCH"),
    ((101, CREATED, r"C:\TestOnly\other.exe", "x64"), "IMAGE_MISMATCH"),
    ((101, CREATED, IMAGE, "x86"), "ARCHITECTURE_MISMATCH"),
    ((101, CREATED, IMAGE, "arm64"), "UNSUPPORTED_ARCHITECTURE"),
])
def test_restart_pid_reuse_image_and_architecture_change(change, code):
    b = FakeBoundary()
    o = observer(b)
    assert o.observe().status == m.SUCCESS
    b.context = change
    rejected(o.observe(), code)
    before = list(b.calls)
    rejected(o.observe(), code)
    assert b.calls == before and b.calls[-1][0] == "close"


def test_identity_changes_within_one_sample():
    b = FakeBoundary()
    seq = iter([b.context, (101, CREATED + 1, IMAGE, "x64")])
    b.identity = lambda _h: next(seq)
    rejected(observer(b).observe(), "IDENTITY_CHANGED")
    assert b.calls[-1][0] == "close"


@pytest.mark.parametrize("raw", [None, (), [], {}, (101,), (101, CREATED, IMAGE, "x64", "scene"),
                                  (True, CREATED, IMAGE, "x64"), (0, CREATED, IMAGE, "x64")])
def test_missing_or_wrong_identity_shape(raw):
    b = FakeBoundary()
    b.context = raw
    rejected(observer(b).observe(), "INVALID_IDENTITY")


@pytest.mark.parametrize("raw", [-1, 0, m.FILETIME_EPOCH - 1, m.FILETIME_MAX + 1, 2**64,
                                  True, None, 1.5, "123", float("nan")])
def test_invalid_creation_and_wall_ticks(raw):
    b = FakeBoundary()
    b.context = (101, raw, IMAGE, "x64")
    rejected(observer(b).observe(), "INVALID_FILETIME")
    b = FakeBoundary()
    b.wall = raw
    rejected(observer(b).observe(), "INVALID_FILETIME")


@pytest.mark.parametrize("ticks,expected", [
    (m.FILETIME_EPOCH, "1970-01-01T00:00:00.0000000Z"),
    (m.FILETIME_EPOCH + 1, "1970-01-01T00:00:00.0000001Z"),
    (m.FILETIME_EPOCH + 9999999, "1970-01-01T00:00:00.9999999Z"),
    (m.FILETIME_MAX, "9999-12-31T23:59:59.9999999Z"),
    (m.FILETIME_EPOCH + 9517824000000000, "2000-02-29T00:00:00.0000000Z"),
])
def test_lossless_utc_without_local_timezone_or_float(ticks, expected):
    assert m.filetime_utc(ticks) == expected


@pytest.mark.parametrize("path", [None, b"C:\\a.exe", "", "c:\\a.exe", "a.exe", "C:a.exe",
    "C:/a.exe", r"\\server\share\a.exe", r"\\?\C:\a.exe", r"C:\a\..\b.exe", r"C:\.\a.exe",
    "C:\\\\a.exe", "C:\\a.exe ", "C:\\a.\\b.exe", "C:\\a.exe:stream", "C:\\a~1.exe",
    "C:\\con\\a.exe", "C:\\COM1.exe", "C:\\lpt9.txt\\a.exe", "C:\\a\x00.exe",
    "C:\\a\n.exe", "C:\\a\x7f.exe", "C:\\中.exe", "C:\\*.exe", "C:\\a.dll",
    "C:\\" + "a" * 254 + ".exe"])
def test_ambiguous_paths_rejected(path):
    with pytest.raises(m.ObserverError, match="INVALID_PATH"):
        m.canonical_executable(path)


@pytest.mark.parametrize("name,value", [
    ("max_elapsed_ms", 0), ("max_elapsed_ms", 120001), ("max_elapsed_ms", True),
    ("tolerance_ms", 15), ("tolerance_ms", 1001), ("tolerance_ms", 1.5),
    ("max_sample_ms", 0), ("max_sample_ms", 1001), ("max_sample_ms", None),
])
def test_invalid_policy_never_opens_process(name, value):
    b = FakeBoundary()
    with pytest.raises(m.ObserverError, match="INVALID_ARGUMENT"):
        observer(b, **{name: value})
    assert b.calls == []


@pytest.mark.parametrize("pid", [None, True, 0, -1, 2**32, "101", 1.1])
def test_invalid_pid_never_measures(pid):
    b = FakeBoundary()
    with pytest.raises(m.ObserverError, match="INVALID_ARGUMENT"):
        m.ProcessObserver(pid, b, expected_executable=IMAGE, expected_architecture="x64")
    assert b.calls == []


@pytest.mark.parametrize("value", [None, -1, m.MAX_MONOTONIC + 1, 2**64, True, 2.5, "1000"])
def test_monotonic_overflow_and_precision_loss(value):
    b = FakeBoundary()
    b.mono = value
    rejected(observer(b).observe(), "INVALID_CLOCK")


@pytest.mark.parametrize("wall_delta,mono_delta,code", [
    (-1, 1, "CLOCK_ROLLBACK"), (10000, -1, "MONOTONIC_REGRESSION"),
    (100000000, 100, "CLOCK_INCONSISTENT"), (0, 100, "CLOCK_INCONSISTENT"),
    (60000000, 6000, "ELAPSED_EXCEEDED"),  # Long pause / suspend simulation.
    (10000000, 2000, "CLOCK_INCONSISTENT"),
])
def test_observed_clock_discontinuities(wall_delta, mono_delta, code):
    b = FakeBoundary()
    o = observer(b)
    assert o.observe().status == m.SUCCESS
    b.wall += wall_delta
    b.mono += mono_delta
    rejected(o.observe(), code)


@pytest.mark.parametrize("delta,ok", [(319999, True), (320000, True), (320001, False)])
def test_tolerance_uses_exact_integer_ticks(delta, ok):
    b = FakeBoundary()
    o = observer(b)
    o.observe()
    b.wall += delta
    result = o.observe()
    assert (result.status == m.SUCCESS) is ok


@pytest.mark.parametrize("values,code", [([1000, 999], "MONOTONIC_REGRESSION"),
                                       ([1000, 1101], "SAMPLE_TOO_LONG")])
def test_slow_or_regressing_single_sample(values, code):
    b = FakeBoundary()
    seq = iter(values)
    b.monotonic_ms = lambda: next(seq)
    rejected(observer(b).observe(), code)


def test_drift_is_checked_against_first_sample_not_only_previous():
    b = FakeBoundary()
    o = observer(b)
    o.observe()
    b.wall += 1300000
    b.mono += 100
    assert o.observe().status == m.SUCCESS
    b.wall += 1300000
    b.mono += 100
    rejected(o.observe(), "CLOCK_INCONSISTENT")


@pytest.mark.parametrize("stage", ["open", "running", "identity", "wall", "mono", "close"])
def test_exceptions_are_bounded_and_handle_close_is_attempted_once(stage):
    b = FakeBoundary()
    b.fault = stage
    if stage == "close":
        b.running = False
    o = observer(b)
    result = o.observe()
    rejected(result, "CLOSE_FAILED" if stage == "close" else "DEPENDENCY_REJECTED")
    assert b"PRIVATE" not in o.render(result)
    assert [x[0] for x in b.calls].count("close") == (0 if stage == "open" else 1)
    o.observe()
    o.close() if stage != "close" else None
    assert [x[0] for x in b.calls].count("close") == (0 if stage == "open" else 1)


@pytest.mark.parametrize("running,code", [(False, "PROCESS_EXITED"), (None, "QUERY_FAILED"),
                                         (1, "QUERY_FAILED"), ("true", "QUERY_FAILED")])
def test_liveness_requires_literal_boolean(running, code):
    b = FakeBoundary()
    b.running = running
    rejected(observer(b).observe(), code)


def test_exit_revocation_and_bound_methods():
    b = FakeBoundary()
    o = observer(b)
    b.identity = lambda _h: pytest.fail("replaced dependency must not be captured")
    result = o.observe()
    assert result.status == m.SUCCESS
    o.revoke()
    assert b"INVALID_RESULT" in o.render(result)
    rejected(o.observe(), "REVOKED")


def test_result_copies_forgery_and_malformed_input_fail_closed():
    with observer() as o:
        result = o.observe()
        with pytest.raises(AttributeError):
            result.write_ready = True
        for invalid in (None, {}, tuple(result), m.Result(result), copy.deepcopy(list(result)), "PASS"):
            assert b"reason_code=INVALID_RESULT\r\n" in o.render(invalid)
            assert b"write_ready=false\r\n" in o.render(invalid)


def test_reentrancy_poison_and_interruption_cleanup():
    b = FakeBoundary()
    holder = []
    b.wall_filetime = lambda: (holder[0].observe(), WALL)[1]
    o = observer(b)
    holder.append(o)
    rejected(o.observe(), "BUSY")
    assert b.calls[-1][0] == "close"
    b = FakeBoundary()
    def interrupt():
        raise KeyboardInterrupt()
    b.wall_filetime = interrupt
    o = observer(b)
    with pytest.raises(KeyboardInterrupt):
        o.observe()
    assert b.calls[-1][0] == "close"
    rejected(o.observe(), "DEPENDENCY_REJECTED")


def test_observation_limit_and_creation_in_future():
    with observer() as o:
        for _ in range(64):
            assert o.observe().status == m.SUCCESS
        rejected(o.observe(), "OBSERVATION_LIMIT")
    b = FakeBoundary()
    b.wall = CREATED - 1
    rejected(observer(b).observe(), "CREATION_IN_FUTURE")


def test_mutated_exception_code_and_invalid_boundary_remain_bounded():
    b = FakeBoundary()
    error = m.ObserverError("ACCESS_DENIED")
    error.code = "PRIVATE arbitrarily altered exception"
    def fail(_handle):
        raise error
    b.identity = fail
    o = observer(b)
    result = o.observe()
    rejected(result, "DEPENDENCY_REJECTED")
    assert b"PRIVATE" not in o.render(result)
    with pytest.raises(m.ObserverError, match="INVALID_BOUNDARY"):
        observer(object())


def test_close_exception_revokes_previous_success():
    b = FakeBoundary()
    o = observer(b)
    result = o.observe()
    b.fault = "close"
    with pytest.raises(m.ObserverError, match="CLOSE_FAILED"):
        o.close()
    assert b"INVALID_RESULT" in o.render(result)
    rejected(o.observe(), "CLOSE_FAILED")


class APIFunction:
    def __init__(self, api, name):
        self.api, self.name = api, name

    def __call__(self, *args):
        return self.api.call(self.name, args)


class FakeAPI:
    """ctypes ABI mock: exercises out parameters and signature declarations."""
    def __init__(self):
        self.calls, self.fail = [], None
        self.machine, self.native = 0, 0x8664
        self.path, self.path_length = IMAGE, None
        self.wait, self.handle = 258, 42
        for name in m.NativeWin32Boundary.API_NAMES:
            setattr(self, name, APIFunction(self, name))

    def call(self, name, args):
        self.calls.append((name, args))
        if name == self.fail:
            ctypes.set_last_error(5)
            return 0
        if name == "OpenProcess":
            return self.handle
        if name == "WaitForSingleObject":
            return self.wait
        if name == "GetProcessId":
            return 101
        if name in ("GetProcessTimes", "GetSystemTimePreciseAsFileTime"):
            ft = args[1 if name == "GetProcessTimes" else 0]._obj
            ticks = CREATED if name == "GetProcessTimes" else WALL
            ft.low, ft.high = ticks & 0xFFFFFFFF, ticks >> 32
        if name == "QueryFullProcessImageNameW":
            args[2].value = self.path
            args[3]._obj.value = len(self.path) if self.path_length is None else self.path_length
        if name == "IsWow64Process2":
            args[1]._obj.value, args[2]._obj.value = self.machine, self.native
        if name == "GetTickCount64":
            return 1000
        return 1


def test_native_abi_uses_only_allowlisted_readonly_apis(monkeypatch):
    def forbidden(*_a, **_k):
        pytest.fail("native DLL loading in synthetic test")
    monkeypatch.setattr(ctypes, "WinDLL", forbidden)
    api = FakeAPI()
    boundary = m.NativeWin32Boundary(api=api)
    with observer(boundary) as o:
        assert o.observe().status == m.SUCCESS
        assert o.observe().status == m.SUCCESS
    assert api.calls[0] == ("OpenProcess", (0x101000, False, 101))
    assert all(name in m.NativeWin32Boundary.API_NAMES for name, _ in api.calls)
    assert all(args[1] == 0 for name, args in api.calls if name == "WaitForSingleObject")
    assert api.CloseHandle.argtypes == [ctypes.c_void_p]
    assert api.GetTickCount64.restype is ctypes.c_uint64
    assert api.GetSystemTimePreciseAsFileTime.restype is None


@pytest.mark.parametrize("name", ["OpenProcess", "GetProcessId", "GetProcessTimes",
    "QueryFullProcessImageNameW", "IsWow64Process2", "CloseHandle"])
def test_native_api_access_denial_and_close_failures(name):
    api = FakeAPI()
    api.fail = name
    if name == "CloseHandle":
        api.wait = 0
    rejected(observer(m.NativeWin32Boundary(api=api)).observe(),
             "CLOSE_FAILED" if name == "CloseHandle" else "ACCESS_DENIED")
    assert sum(n == "CloseHandle" for n, _ in api.calls) == (0 if name == "OpenProcess" else 1)


@pytest.mark.parametrize("machine,native,expected", [(0, 0x8664, "x64"), (0, 0x014C, "x86"),
    (0x014C, 0x8664, "x86"), (0, 0xAA64, None), (0x8664, 0xAA64, None), (1, 0x8664, None)])
def test_architecture_api_values(machine, native, expected):
    api = FakeAPI()
    api.machine, api.native = machine, native
    boundary = m.NativeWin32Boundary(api=api)
    if expected is None:
        with pytest.raises(m.ObserverError, match="UNSUPPORTED_ARCHITECTURE"):
            boundary.identity(42)
    else:
        assert boundary.identity(42)[3] == expected


@pytest.mark.parametrize("length", [0, 261, 0xFFFFFFFF, 1, len(IMAGE) + 1])
def test_native_path_length_must_match_full_terminated_buffer(length):
    api = FakeAPI()
    api.path_length = length
    rejected(observer(m.NativeWin32Boundary(api=api)).observe(), "IMAGE_TRUNCATED")


@pytest.mark.parametrize("name", m.NativeWin32Boundary.API_NAMES)
def test_missing_native_api_fails_without_fallback(name):
    api = FakeAPI()
    delattr(api, name)
    with pytest.raises(m.ObserverError, match="UNSUPPORTED_API"):
        m.NativeWin32Boundary(api=api)
    assert api.calls == []


def test_signaled_handle_rejects_even_exit_code_259_and_wait_error():
    api = FakeAPI()
    api.wait = 0  # Signaled, irrespective of exit code; no GetExitCodeProcess ambiguity.
    rejected(observer(m.NativeWin32Boundary(api=api)).observe(), "PROCESS_EXITED")
    api = FakeAPI()
    api.wait = 0xFFFFFFFF
    ctypes.set_last_error(6)
    rejected(observer(m.NativeWin32Boundary(api=api)).observe(), "QUERY_FAILED")


@pytest.mark.parametrize("handle", [0, None, -1, True, 2**64, 2**64 - 1])
def test_invalid_injected_handles_reject(handle):
    b = FakeBoundary()
    b.open_process = lambda _pid: handle
    rejected(observer(b).observe(), "INVALID_HANDLE")


def test_module_import_is_inert_even_with_imports_and_io_forbidden(monkeypatch):
    code = compile(Path(m.__file__).read_bytes(), "isolated-a5", "exec")
    def forbidden(*_args, **_kwargs):
        raise AssertionError("import-time side effect")
    import os
    import socket
    import subprocess
    import time
    import winreg
    with monkeypatch.context() as mp:
        for owner, names in ((builtins, ("open",)), (Path, ("open", "read_bytes", "stat")),
            (os, ("open", "stat", "listdir", "scandir")), (socket, ("socket",)),
            (subprocess, ("Popen", "run")), (time, ("time", "monotonic", "perf_counter")),
            (ctypes, ("WinDLL", "CDLL")), (winreg, ("OpenKey",))):
            for name in names:
                mp.setattr(owner, name, forbidden)
        # Install this last: pytest's setter itself imports inspect.
        mp.setattr(builtins, "__import__", forbidden)
        namespace = {"__name__": "isolated_a5"}
        exec(code, namespace)
    assert namespace["SUCCESS"] == m.SUCCESS


def test_no_production_dispatch_or_h3_identity_adapter():
    root = Path(__file__).resolve().parents[1]
    for path in (root / "src").glob("*.lua"):
        assert b"h3_windows_process_identity" not in path.read_bytes()
    assert not hasattr(m.ProcessObserver, "identity")
    assert not hasattr(m.ProcessObserver, "write")


def test_native_probe_is_not_auto_collected_and_import_is_inert(monkeypatch):
    probe_path = Path(__file__).with_name("h3_windows_process_identity_native_probe.py")
    code = compile(probe_path.read_bytes(), str(probe_path), "exec")
    def forbidden(*_a, **_k):
        raise AssertionError("probe import side effect")
    with monkeypatch.context() as mp:
        mp.setattr(builtins, "__import__", forbidden)
        namespace = {"__name__": "probe_import_test", "__file__": str(probe_path)}
        exec(code, namespace)
    assert len(namespace["REQUIRED_CHECKS"]) >= 12
    assert not probe_path.name.startswith("test_")


def test_probe_simulations_and_evidence_binding(tmp_path):
    import h3_windows_process_identity_native_probe as probe
    assert probe.simulated_rejections(m) == {
        "pid_reuse": "IDENTITY_CHANGED", "access_denied": "ACCESS_DENIED",
        "clock_rollback": "CLOCK_ROLLBACK", "clock_jump": "CLOCK_INCONSISTENT"}
    reports = {"example.json": probe.canonical_json({"test_only": True})}
    receipt = {"files": probe.file_manifest(reports)}
    probe.write_bundle(tmp_path, reports, receipt)
    assert probe.verify_bundle(tmp_path / "native-identity-bundle.zip")["files"] == receipt["files"]
    import zipfile
    with zipfile.ZipFile(tmp_path / "tampered.zip", "w") as z:
        z.writestr("native-receipt.json", probe.canonical_json(receipt))
        z.writestr("example.json", b"{}\n")
    with pytest.raises(ValueError):
        probe.verify_bundle(tmp_path / "tampered.zip")
