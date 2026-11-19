"""Inactive, read-only OS observations. No imports or measurements at import time.

This is not an H3-A2 identity adapter, CE attachment proof, or capability.
Only an explicitly supplied, trusted boundary can perform measurements.
"""

QUERY_ACCESS = 0x00101000  # QUERY_LIMITED_INFORMATION | SYNCHRONIZE (zero-time wait).
FILETIME_EPOCH = 116444736000000000
FILETIME_MAX = 2650467743999999999  # 9999-12-31T23:59:59.9999999Z
MAX_MONOTONIC = (1 << 53) - 1
SUCCESS = "OS_PROCESS_CONTEXT_OBSERVED_NOT_AUTHORIZED"
ERROR_CODES = frozenset((
    "INVALID_ARGUMENT", "INVALID_BOUNDARY", "UNSUPPORTED_PLATFORM", "UNSUPPORTED_API",
    "ACCESS_DENIED", "OPEN_FAILED", "INVALID_HANDLE", "QUERY_FAILED", "CLOSE_FAILED",
    "PROCESS_EXITED", "PID_MISMATCH", "INVALID_IDENTITY", "INVALID_FILETIME",
    "INVALID_PATH", "IMAGE_TRUNCATED", "IMAGE_MISMATCH", "ARCHITECTURE_MISMATCH",
    "UNSUPPORTED_ARCHITECTURE", "IDENTITY_CHANGED", "INVALID_CLOCK", "CLOCK_ROLLBACK",
    "MONOTONIC_REGRESSION", "SAMPLE_TOO_LONG", "ELAPSED_EXCEEDED", "CLOCK_INCONSISTENT",
    "CREATION_IN_FUTURE", "DEPENDENCY_REJECTED", "CLOSED", "REVOKED", "INVALID_RESULT",
    "OBSERVATION_LIMIT", "BUSY",
))
PUBLIC_FIELDS = (
    "schema", "status", "reason_code", "measurement_basis", "observation_count",
    "elapsed_upper_ms", "attachment_verified", "scene_os_measured", "authorization_status",
    "handoff_write_ready", "write_ready", "write_attempted", "restore_attempted",
    "memory_read_attempts", "memory_write_attempts", "independent_review_required",
)


class ObserverError(Exception):
    def __init__(self, code):
        self.code = code if type(code) is str and code in ERROR_CODES else "DEPENDENCY_REJECTED"
        super().__init__(self.code)


class Result(tuple):
    """Immutable public view; only its issuer's current view may be rendered."""
    __slots__ = ()

    def __getattr__(self, name):
        if name in PUBLIC_FIELDS:
            return self[PUBLIC_FIELDS.index(name)]
        raise AttributeError(name)


def _integer(value, low, high, code):
    if type(value) is not int or not low <= value <= high:
        raise ObserverError(code)
    return value


def canonical_executable(value):
    """Conservative spelling, not file-content authentication or alias resolution."""
    if (type(value) is not str or not 7 <= len(value) <= 260
            or not value.isascii() or not "A" <= value[0] <= "Z" or value[1:3] != ":\\"):
        raise ObserverError("INVALID_PATH")
    pieces = value[3:].split("\\")
    reserved = ("CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$")
    for piece in pieces:
        base = piece.split(".")[0].upper()
        if (not piece or piece in (".", "..") or piece[-1] in " ."
                or any(ord(c) < 32 or ord(c) == 127 or c in '/:*?"<>|~' for c in piece)
                or base in reserved or base in tuple("COM" + str(i) for i in range(1, 10))
                or base in tuple("LPT" + str(i) for i in range(1, 10))):
            raise ObserverError("INVALID_PATH")
    if not pieces[-1].lower().endswith(".exe"):
        raise ObserverError("INVALID_PATH")
    return value


def filetime_utc(value):
    """Lossless FILETIME encoding. Seven digits encode ticks, not accuracy."""
    _integer(value, FILETIME_EPOCH, FILETIME_MAX, "INVALID_FILETIME")
    from datetime import datetime, timedelta, timezone
    seconds, ticks = divmod(value - FILETIME_EPOCH, 10000000)
    date = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    return (f"{date.year:04d}-{date.month:02d}-{date.day:02d}T"
            f"{date.hour:02d}:{date.minute:02d}:{date.second:02d}.{ticks:07d}Z")


def _public(code, count=0, elapsed=0):
    return Result(("h3_windows_process_context_v1", SUCCESS if code == "NONE" else "REJECTED",
                   code, "os_query_boundary", count, elapsed, False, False,
                   "NOT_PRODUCTION_AUTHORIZED", False, False, False, False, 0, 0, True))


def _encode(result):
    def scalar(v):
        return ("true" if v else "false") if type(v) is bool else str(v)
    return "".join(k + "=" + scalar(v) + "\r\n" for k, v in zip(PUBLIC_FIELDS, result)).encode("ascii")


class ProcessObserver:
    """One held handle, one process instance, bounded observations, terminal rejection.

    Expectations constrain OS results; they never supply missing measurements.
    The boundary is trusted code, not authenticated by this class. Single-threaded.
    Construction validates/captures dependencies; first observe opens the handle.
    """
    def __init__(self, pid, boundary, *, expected_executable, expected_architecture,
                 max_elapsed_ms=5000, tolerance_ms=32, max_sample_ms=100):
        self._pid = _integer(pid, 1, 0xFFFFFFFF, "INVALID_ARGUMENT")
        self._image = canonical_executable(expected_executable)
        if type(expected_architecture) is not str or expected_architecture not in ("x86", "x64"):
            raise ObserverError("INVALID_ARGUMENT")
        self._arch = expected_architecture
        self._limit = _integer(max_elapsed_ms, 1, 120000, "INVALID_ARGUMENT")
        self._tolerance = _integer(tolerance_ms, 16, 1000, "INVALID_ARGUMENT")
        self._sample_limit = _integer(max_sample_ms, 1, min(1000, self._limit), "INVALID_ARGUMENT")
        try:
            self._ops = tuple(getattr(boundary, key) for key in (
                "open_process", "close_handle", "is_running", "identity", "wall_filetime", "monotonic_ms"))
            if not all(callable(op) for op in self._ops):
                raise ValueError()
        except Exception:
            raise ObserverError("INVALID_BOUNDARY") from None
        self._handle = None
        self._first = self._previous = self._result = None
        self._count = 0
        self._terminal = None
        self._busy = False

    def _release(self):
        handle, self._handle = self._handle, None
        if handle is not None:
            try:
                if self._ops[1](handle) is not True:
                    return "CLOSE_FAILED"
            except BaseException:
                return "CLOSE_FAILED"
        return None

    def close(self):
        """Terminal. Previously issued observations are revoked, even on close failure."""
        self._result = None
        self._terminal = self._release() or self._terminal or "CLOSED"
        if self._terminal == "CLOSE_FAILED":
            raise ObserverError("CLOSE_FAILED")

    def revoke(self):
        self._terminal = "REVOKED"
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def _identity(self):
        raw = self._ops[3](self._handle)
        if type(raw) is not tuple or len(raw) != 4:
            raise ObserverError("INVALID_IDENTITY")
        pid, created, path, arch = raw
        _integer(pid, 1, 0xFFFFFFFF, "INVALID_IDENTITY")
        if pid != self._pid:
            raise ObserverError("PID_MISMATCH")
        filetime_utc(created)
        canonical_executable(path)
        if path != self._image:
            raise ObserverError("IMAGE_MISMATCH")
        if type(arch) is not str or arch not in ("x86", "x64"):
            raise ObserverError("UNSUPPORTED_ARCHITECTURE")
        if arch != self._arch:
            raise ObserverError("ARCHITECTURE_MISMATCH")
        return raw

    def _running(self):
        running = self._ops[2](self._handle)
        if running is False:
            raise ObserverError("PROCESS_EXITED")
        if running is not True:
            raise ObserverError("QUERY_FAILED")

    def _sample(self):
        mono = self._ops[5]
        start = _integer(mono(), 0, MAX_MONOTONIC, "INVALID_CLOCK")
        self._running()
        identity = self._identity()
        wall = self._ops[4]()
        utc = filetime_utc(wall)
        if self._identity() != identity:
            raise ObserverError("IDENTITY_CHANGED")
        self._running()
        end = _integer(mono(), 0, MAX_MONOTONIC, "INVALID_CLOCK")
        if end < start:
            raise ObserverError("MONOTONIC_REGRESSION")
        if end - start > self._sample_limit:
            raise ObserverError("SAMPLE_TOO_LONG")
        if identity[1] > wall:
            raise ObserverError("CREATION_IN_FUTURE")
        return identity, wall, utc, start, end

    def observe(self):
        if self._busy:
            # A reentrant dependency poisons the outer call too.
            self._terminal = "BUSY"
            self._result = _public("BUSY")
            return self._result
        self._result = None
        if self._terminal:
            self._result = _public(self._terminal)
            return self._result
        self._busy = True
        try:
            if self._count >= 64:
                raise ObserverError("OBSERVATION_LIMIT")
            if self._handle is None:
                raw = self._ops[0](self._pid)
                # Explicit boundary contract: positive pointer-sized integer, not pseudo handles.
                _integer(raw, 1, (1 << 64) - 2, "INVALID_HANDLE")
                self._handle = raw
            current = self._sample()
            first = self._first or current
            previous = self._previous
            if previous is not None:
                if current[0] != first[0]:
                    raise ObserverError("IDENTITY_CHANGED")
                if current[3] < previous[4]:
                    raise ObserverError("MONOTONIC_REGRESSION")
                if current[1] < previous[1]:
                    raise ObserverError("CLOCK_ROLLBACK")
            elapsed = current[4] - first[3]
            if elapsed > self._limit:
                raise ObserverError("ELAPSED_EXCEEDED")
            # Check both adjacent and first-to-current intervals; no cumulative drift bypass.
            for old in (first, previous or first):
                wall_delta = current[1] - old[1]
                lower = max(0, current[3] - old[4] - self._tolerance) * 10000
                upper = (current[4] - old[3] + self._tolerance) * 10000
                if not lower <= wall_delta <= upper:
                    raise ObserverError("CLOCK_INCONSISTENT")
            if self._terminal:
                raise ObserverError(self._terminal)
            self._first, self._previous = first, current
            self._count += 1
            self._result = _public("NONE", self._count, elapsed)
        except Exception as error:
            code = error.code if type(error) is ObserverError else "DEPENDENCY_REJECTED"
            if type(code) is not str or code not in ERROR_CODES:
                code = "DEPENDENCY_REJECTED"
            self._terminal = self._release() or code
            self._result = _public(self._terminal)
        except BaseException:
            self._terminal = self._release() or "DEPENDENCY_REJECTED"
            raise
        finally:
            self._busy = False
        return self._result

    def render(self, result):
        if type(result) is not Result or result is not self._result:
            return _encode(_public("INVALID_RESULT"))
        return _encode(result)

    def diagnostic_observations(self):
        """Private explicit diagnostic view. Contains the measured executable path."""
        return tuple(x for x in (self._first, self._previous) if x is not None)


class NativeWin32Boundary:
    """Explicit construction only. No fallback, enumeration, memory or debug API.

    SYNCHRONIZE is necessary to reject even a process that exited with code 259;
    GetExitCodeProcess's STILL_ACTIVE alone would be ambiguous. Wait timeout is 0.
    An injected API table exercises precisely the same ctypes boundary in tests.
    """
    API_NAMES = ("OpenProcess", "CloseHandle", "WaitForSingleObject", "GetProcessId",
                 "GetProcessTimes", "QueryFullProcessImageNameW", "IsWow64Process2",
                 "GetSystemTimePreciseAsFileTime", "GetTickCount64")

    def __init__(self, *, api=None):
        import ctypes as c
        import os
        self._c = c
        if api is None:
            if os.name != "nt":
                raise ObserverError("UNSUPPORTED_PLATFORM")
            try:
                api = c.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
            except Exception:
                raise ObserverError("UNSUPPORTED_API") from None
        class FileTime(c.Structure):
            _fields_ = [("low", c.c_uint32), ("high", c.c_uint32)]
        self._ft = FileTime
        pointer = c.POINTER
        specs = (
            ("OpenProcess", [c.c_uint32, c.c_int32, c.c_uint32], c.c_void_p),
            ("CloseHandle", [c.c_void_p], c.c_int32),
            ("WaitForSingleObject", [c.c_void_p, c.c_uint32], c.c_uint32),
            ("GetProcessId", [c.c_void_p], c.c_uint32),
            ("GetProcessTimes", [c.c_void_p] + [pointer(FileTime)] * 4, c.c_int32),
            ("QueryFullProcessImageNameW", [c.c_void_p, c.c_uint32, c.c_wchar_p, pointer(c.c_uint32)], c.c_int32),
            ("IsWow64Process2", [c.c_void_p, pointer(c.c_uint16), pointer(c.c_uint16)], c.c_int32),
            ("GetSystemTimePreciseAsFileTime", [pointer(FileTime)], None),
            ("GetTickCount64", [], c.c_uint64),
        )
        self._api = {}
        try:
            for name, args, result in specs:
                fn = getattr(api, name)
                fn.argtypes, fn.restype = args, result
                self._api[name] = fn
        except Exception:
            raise ObserverError("UNSUPPORTED_API") from None

    def _check(self, ok, code="QUERY_FAILED"):
        if not ok:
            if self._c.get_last_error() == 5:
                code = "ACCESS_DENIED"
            raise ObserverError(code)

    def open_process(self, pid):
        _integer(pid, 1, 0xFFFFFFFF, "INVALID_ARGUMENT")
        handle = self._api["OpenProcess"](QUERY_ACCESS, False, pid)
        self._check(handle, "OPEN_FAILED")
        if handle == self._c.c_void_p(-1).value:
            raise ObserverError("INVALID_HANDLE")
        return handle

    def close_handle(self, handle):
        self._check(self._api["CloseHandle"](handle), "CLOSE_FAILED")
        return True

    def is_running(self, handle):
        state = self._api["WaitForSingleObject"](handle, 0)
        if state == 0:
            return False
        if state != 258:
            self._check(False)
        return True

    @staticmethod
    def _ticks(ft):
        return (ft.high << 32) | ft.low

    def identity(self, handle):
        c, api = self._c, self._api
        pid = api["GetProcessId"](handle)
        self._check(pid)
        creation, exit_time, kernel, user = (self._ft() for _ in range(4))
        self._check(api["GetProcessTimes"](handle, c.byref(creation), c.byref(exit_time),
                                          c.byref(kernel), c.byref(user)))
        capacity = 261
        path = c.create_unicode_buffer(capacity)
        length = c.c_uint32(capacity)
        self._check(api["QueryFullProcessImageNameW"](handle, 0, path, c.byref(length)))
        if not 1 <= length.value < capacity or path[length.value] != "\0" or len(path.value) != length.value:
            raise ObserverError("IMAGE_TRUNCATED")
        image = canonical_executable(path.value)
        process_machine, native_machine = c.c_uint16(), c.c_uint16()
        self._check(api["IsWow64Process2"](handle, c.byref(process_machine), c.byref(native_machine)))
        architectures = {(0, 0x014C): "x86", (0, 0x8664): "x64", (0x014C, 0x8664): "x86"}
        arch = architectures.get((process_machine.value, native_machine.value))
        if arch is None:
            raise ObserverError("UNSUPPORTED_ARCHITECTURE")
        return pid, self._ticks(creation), image, arch

    def wall_filetime(self):
        value = self._ft()
        self._api["GetSystemTimePreciseAsFileTime"](self._c.byref(value))
        return self._ticks(value)

    def monotonic_ms(self):
        return self._api["GetTickCount64"]()
