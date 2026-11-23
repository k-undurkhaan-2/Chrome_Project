"""Win32 provider implementation; B1 executes only injected virtual WinAPI.

Import and construction are inert. Loading system DLLs is behind the immutable
native admission gate. Injection is trusted test equipment, not authorization.
No process memory, process termination, handle duplication or CE launch API exists.
"""
import ctypes as C
from dataclasses import dataclass
import hashlib
from pathlib import PureWindowsPath
import re
from threading import RLock

from .native_probe_admission import require_native_activation
from .native_probe_protocol import ProbeError, canonical, require, sha256
from .native_probe_peer import CLIENT_ACCESS, SERVER_ACCESS

DWORD, BOOL, WORD, BYTE = C.c_uint32, C.c_int32, C.c_uint16, C.c_ubyte
HANDLE, PTR, ULONG_PTR = C.c_void_p, C.c_void_p, C.c_size_t
PDWORD, PPTR = C.POINTER(DWORD), C.POINTER(PTR)
INVALID_HANDLE_VALUE = C.c_void_p(-1).value
IO_PENDING, IO_INCOMPLETE, OPERATION_ABORTED = 997, 996, 995
PIPE_CONNECTED, BROKEN_PIPE, PIPE_NOT_CONNECTED = 535, 109, 233
NOT_FOUND, INSUFFICIENT_BUFFER, WAIT_TIMEOUT = 1168, 122, 258


class SECURITY_ATTRIBUTES(C.Structure):
    _fields_ = [("nLength", DWORD), ("lpSecurityDescriptor", PTR), ("bInheritHandle", BOOL)]


class _Offsets(C.Structure):
    _fields_ = [("Offset", DWORD), ("OffsetHigh", DWORD)]


class _Position(C.Union):
    _fields_ = [("offsets", _Offsets), ("Pointer", PTR)]


class OVERLAPPED(C.Structure):
    _fields_ = [("Internal", ULONG_PTR), ("InternalHigh", ULONG_PTR),
                ("position", _Position), ("hEvent", HANDLE)]


class FILETIME(C.Structure):
    _fields_ = [("low", DWORD), ("high", DWORD)]


class SID_AND_ATTRIBUTES(C.Structure):
    _fields_ = [("Sid", PTR), ("Attributes", DWORD)]


class TOKEN_GROUPS(C.Structure):
    _fields_ = [("GroupCount", DWORD), ("Groups", SID_AND_ATTRIBUTES * 1)]


class ACL_SIZE_INFORMATION(C.Structure):
    _fields_ = [("AceCount", DWORD), ("AclBytesInUse", DWORD), ("AclBytesFree", DWORD)]


class ACCESS_ALLOWED_ACE(C.Structure):
    _fields_ = [("AceType", BYTE), ("AceFlags", BYTE), ("AceSize", WORD),
                ("Mask", DWORD), ("SidStart", DWORD)]


P_OV, P_SA = C.POINTER(OVERLAPPED), C.POINTER(SECURITY_ATTRIBUTES)
# Fixed-width Win32 integers, pointer-width handles. No host c_long assumption.
# (DLL, result, arguments). WINAPI calling convention is supplied by WinDLL.
SIGNATURES = {
    "CreateNamedPipeW": ("kernel32", HANDLE, [C.c_wchar_p, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, P_SA]),
    "ConnectNamedPipe": ("kernel32", BOOL, [HANDLE, P_OV]),
    "CreateEventW": ("kernel32", HANDLE, [P_SA, BOOL, BOOL, C.c_wchar_p]),
    "ReadFile": ("kernel32", BOOL, [HANDLE, PTR, DWORD, PDWORD, P_OV]),
    "WriteFile": ("kernel32", BOOL, [HANDLE, PTR, DWORD, PDWORD, P_OV]),
    "GetOverlappedResult": ("kernel32", BOOL, [HANDLE, P_OV, PDWORD, BOOL]),
    "CancelIoEx": ("kernel32", BOOL, [HANDLE, P_OV]),
    "DisconnectNamedPipe": ("kernel32", BOOL, [HANDLE]),
    "CloseHandle": ("kernel32", BOOL, [HANDLE]),
    "WaitForSingleObject": ("kernel32", DWORD, [HANDLE, DWORD]),
    "GetNamedPipeClientProcessId": ("kernel32", BOOL, [HANDLE, PDWORD]),
    "OpenProcess": ("kernel32", HANDLE, [DWORD, BOOL, DWORD]),
    "GetProcessTimes": ("kernel32", BOOL, [HANDLE] + [C.POINTER(FILETIME)] * 4),
    "QueryFullProcessImageNameW": ("kernel32", BOOL, [HANDLE, DWORD, C.c_wchar_p, PDWORD]),
    "OpenProcessToken": ("advapi32", BOOL, [HANDLE, DWORD, C.POINTER(HANDLE)]),
    "GetTokenInformation": ("advapi32", BOOL, [HANDLE, C.c_int32, PTR, DWORD, PDWORD]),
    "ConvertSidToStringSidW": ("advapi32", BOOL, [PTR, PPTR]),
    "ConvertStringSecurityDescriptorToSecurityDescriptorW": ("advapi32", BOOL, [C.c_wchar_p, DWORD, PPTR, PDWORD]),
    "GetSecurityInfo": ("advapi32", DWORD, [HANDLE, C.c_int32, DWORD] + [PPTR] * 5),
    "GetSecurityDescriptorControl": ("advapi32", BOOL, [PTR, C.POINTER(WORD), PDWORD]),
    "GetSecurityDescriptorLength": ("advapi32", DWORD, [PTR]),
    "GetAclInformation": ("advapi32", BOOL, [PTR, PTR, DWORD, C.c_int32]),
    "GetAce": ("advapi32", BOOL, [PTR, DWORD, PPTR]),
    "LocalFree": ("kernel32", PTR, [PTR]),
    "CreateFileW": ("kernel32", HANDLE, [C.c_wchar_p, DWORD, DWORD, P_SA, DWORD, DWORD, HANDLE]),
    "GetFileSizeEx": ("kernel32", BOOL, [HANDLE, C.POINTER(C.c_int64)]),
}


def load_native_api():
    require_native_activation()  # BEFORE WinDLL lookup/loading, unconditionally denied.
    dlls = {name: C.WinDLL(name, use_last_error=True) for name in ("kernel32", "advapi32")}
    functions = {}
    for name, (dll, result, args) in SIGNATURES.items():
        fn = getattr(dlls[dll], name)
        fn.restype, fn.argtypes = result, args
        functions[name] = fn
    return WinAPI(functions, C.get_last_error, origin="NATIVE")


class WinAPI:
    """A function table. Production loading is gated; tests inject Python functions."""
    def __init__(self, functions, last_error, *, origin):
        require(origin == "SYNTHETIC", "BLOCKED_NATIVE_ACTIVATION_UNPROVEN")
        require(set(functions) == set(SIGNATURES) and callable(last_error), "WINAPI_TABLE")
        require(all(callable(f) for f in functions.values()), "WINAPI_TABLE")
        self.functions, self.last_error, self.origin = functions, last_error, origin

    def call(self, name, *args):
        result = self.functions[name](*args)
        # Capture immediately, before logging, cleanup or another WinAPI call.
        error = int(self.last_error()) & 0xFFFFFFFF
        return result, error

    def checked(self, name, *args):
        result, error = self.call(name, *args)
        if not result:
            raise Win32Error(name, error)
        return result


class Win32Error(ProbeError):
    def __init__(self, api, code):
        self.api, self.winerror = api, code
        super().__init__(f"WIN32_{api}_{code}")


class OwnedHandle:
    def __init__(self, api, value, kind):
        value = value.value if isinstance(value, HANDLE) else value
        require(type(value) is int and 0 < value < INVALID_HANDLE_VALUE, "INVALID_HANDLE")
        self.api, self.value, self.kind = api, value, kind
        self.attempted, self.closed = False, False

    def close(self):
        if not self.attempted:
            self.attempted = True  # no retry against a potentially recycled handle
            result, self.close_error = self.api.call("CloseHandle", self.value)
            self.closed = bool(result)
        return self.closed


def native_spec(endpoint, owner_sid, server_logon_sid, client_logon_sid):
    require(type(endpoint) is str and re.fullmatch(r"\\\\\.\\pipe\\qsg-r3-[0-9a-f]{32}", endpoint), "LOCAL_ENDPOINT")
    require(type(owner_sid) is str and re.fullmatch(r"S-1-5-21-(?:[0-9]+-){3}[0-9]+", owner_sid), "OWNER_SID")
    for sid in (server_logon_sid, client_logon_sid):
        require(type(sid) is str and re.fullmatch(r"S-1-5-5-[0-9]+-[0-9]+", sid), "LOGON_SID")
    require(server_logon_sid != client_logon_sid, "PRINCIPAL_SEPARATION_UNPROVEN")
    return {"endpoint": endpoint, "owner_sid": owner_sid, "server_logon_sid": server_logon_sid,
            "client_logon_sid": client_logon_sid, "open_mode": 0x40080003, "pipe_mode": 8,
            "instances": 1, "buffer_bytes": 4096, "client_access": CLIENT_ACCESS,
            "sddl": f"O:{owner_sid}D:P(A;;0x{SERVER_ACCESS:x};;;{server_logon_sid})"
                    f"(A;;0x{CLIENT_ACCESS:x};;;{client_logon_sid})"}


# Keep the owner, OVERLAPPED, event and buffer alive even if the caller drops its
# last reference after an uncertain cancellation. Only observed completion removes
# this pin. There is deliberately no destructor that frees pending I/O resources.
_INFLIGHT = {}


def serialized(function):
    """Never wait for another owner thread. Internal owner calls may recurse."""
    def call(self, *args, **kwargs):
        self._access()
        require(self._lock.acquire(blocking=False), "CONCURRENT_OWNER")
        try:
            return function(self, *args, **kwargs)
        finally:
            self._lock.release()
    return call


@dataclass
class Operation:
    name: str
    direction: str
    deadline: int
    buffer: object
    size: int
    event: OwnedHandle
    overlapped: OVERLAPPED
    cancel_requested: bool = False


class Win32Provider:
    origin = "NATIVE"  # default instance must never be accepted by SyntheticServer

    def __init__(self, *, api=None, clock_ms=None):
        require(api is None or isinstance(api, WinAPI) and api.origin == "SYNTHETIC", "SYNTHETIC_WINAPI_REQUIRED")
        require(api is None or callable(clock_ms), "CLOCK_REQUIRED")
        self.api, self.clock = api, clock_ms
        if api is not None:
            self.origin = "SYNTHETIC"
        self.pipe, self.process, self.pending = None, None, None
        self.used, self.revoked, self.connected = False, False, False
        self.last, self.cleanup = -1, "NOT_OBSERVED"
        self.handles, self.trace, self.operations = [], [], set()
        self.spec, self.security = None, None
        self.close_attempted, self.metadata_cleanup_failed = False, False
        self.trace_bytes = 0
        self._lock = RLock()  # no thread is created

    def _access(self):
        if self.api is None:
            require_native_activation()

    def _now(self):
        now = self.clock()
        if type(now) is not int or now < 0 or now < self.last:
            self.revoked = True
            raise ProbeError("CLOCK_REVERSED")
        self.last = now
        return now

    def _record(self, event, **data):
        row = {"origin": "SYNTHETIC", "os_observed": False, "actor": "WIN32_MODEL",
               "clock_id": "win32-model", "at_ms": self._now(), "event": event,
               "sequence": len(self.trace) + 1, "previous_sha256": self.trace[-1]["sha256"] if self.trace else "0" * 64,
               "data": data}
        row["sha256"] = sha256(canonical(row))
        size = len(canonical(row))
        require(len(self.trace) < 8192 and self.trace_bytes + size <= 8 * 1024 * 1024, "TRACE_FULL")
        self.trace.append(row)
        self.trace_bytes += size

    def _own(self, value, kind):
        handle = OwnedHandle(self.api, value, kind)
        require(not any(h.value == handle.value and not h.closed for h in self.handles), "HANDLE_ALIAS")
        self.handles.append(handle)
        return handle

    def _handle(self, handle):
        self._access()
        require(self.pipe is not None and handle == self.pipe.value and not self.pipe.attempted, "HANDLE_BINDING")

    def _free(self, pointer):
        if pointer.value:
            result, error = self.api.call("LocalFree", pointer)
            if result:
                self.metadata_cleanup_failed = True
                raise Win32Error("LocalFree", error)

    def _sid(self, pointer):
        require(bool(pointer), "SID_MISSING")
        text = PTR()
        self.api.checked("ConvertSidToStringSidW", pointer, C.byref(text))
        try:
            require(bool(text.value), "SID_MISSING")
            return C.wstring_at(text.value)
        finally:
            self._free(text)

    @serialized
    def create(self, spec, *, deadline_ms=None):
        self._access()
        require(not self.used, "SERVER_ALREADY_USED")
        self.used = True
        try:
            now = self._now()
            deadline = now + 250 if deadline_ms is None else deadline_ms
            require(type(deadline) is int and 0 < deadline - now <= 250, "REQUEST_BOUND")
            require(spec == native_spec(*(spec[k] for k in ("endpoint", "owner_sid", "server_logon_sid", "client_logon_sid"))), "PIPE_SPEC")
            self.spec = dict(spec)
            descriptor, length = PTR(), DWORD()
            self.api.checked("ConvertStringSecurityDescriptorToSecurityDescriptorW", spec["sddl"], 1,
                             C.byref(descriptor), C.byref(length))
            try:
                require(descriptor.value and 0 < length.value <= 65536, "SECURITY_DESCRIPTOR")
                attributes = SECURITY_ATTRIBUTES(C.sizeof(SECURITY_ATTRIBUTES), descriptor, False)
                value, error = self.api.call("CreateNamedPipeW", spec["endpoint"], spec["open_mode"],
                    spec["pipe_mode"], 1, 4096, 4096, 0, C.byref(attributes))
                if value in (None, 0, INVALID_HANDLE_VALUE, -1):
                    raise Win32Error("CreateNamedPipeW", error)
                self.pipe = self._own(value, "PIPE")
            finally:
                self._free(descriptor)  # descriptor/attributes held through CreateNamedPipeW
            self.security = self.read_security(self.pipe.value)
            require(self._now() < deadline, "REQUEST_TIMEOUT")
            self._record("CREATE", handle=self.pipe.value, spec_sha256=sha256(canonical(spec)),
                         security=self.security)
            return self.pipe.value
        except Exception:
            self.revoked = True
            self.close()
            raise

    @serialized
    def read_security(self, handle):
        self._handle(handle)
        owner, acl, descriptor = PTR(), PTR(), PTR()
        code, _ = self.api.call("GetSecurityInfo", handle, 6, 5, C.byref(owner), None,
                               C.byref(acl), None, C.byref(descriptor))
        if code:
            raise Win32Error("GetSecurityInfo", code)  # returns DWORD, not GetLastError
        try:
            require(owner.value and acl.value and descriptor.value, "DACL_MISSING")
            control, revision = WORD(), DWORD()
            self.api.checked("GetSecurityDescriptorControl", descriptor, C.byref(control), C.byref(revision))
            require(control.value & 0x1004 == 0x1004, "DACL_NOT_PROTECTED")
            owner_sid = self._sid(owner)
            require(owner_sid == self.spec["owner_sid"], "DACL_OWNER")
            info = ACL_SIZE_INFORMATION()
            self.api.checked("GetAclInformation", acl, C.byref(info), C.sizeof(info), 2)
            require(info.AceCount == 2 and 8 <= info.AclBytesInUse <= 65536, "DACL_ACCESS")
            aces = []
            for n in range(2):
                pointer = PTR()
                self.api.checked("GetAce", acl, n, C.byref(pointer))
                require(pointer.value, "DACL_ACE_MISSING")
                ace = C.cast(pointer, C.POINTER(ACCESS_ALLOWED_ACE)).contents
                require(ace.AceType == 0 and ace.AceFlags == 0 and 16 <= ace.AceSize <= info.AclBytesInUse, "DACL_ACE")
                aces.append({"sid": self._sid(pointer.value + ACCESS_ALLOWED_ACE.SidStart.offset), "mask": ace.Mask})
            expected = [{"sid": self.spec["server_logon_sid"], "mask": SERVER_ACCESS},
                        {"sid": self.spec["client_logon_sid"], "mask": CLIENT_ACCESS}]
            require(aces == expected, "DACL_ACCESS")
            size = self.api.checked("GetSecurityDescriptorLength", descriptor)
            require(0 < size <= 65536, "SECURITY_DESCRIPTOR_SIZE")
            return {"owner_sid": owner_sid, "aces": aces, "protected": True,
                    "descriptor_sha256": sha256(C.string_at(descriptor, size)), "handle": handle}
        finally:
            self._free(descriptor)

    @serialized
    def start_io(self, handle, operation, direction, data=b"", maximum=0, *, deadline_ms):
        self._handle(handle)
        require(not self.revoked and self.pending is None, "IO_OVERLAP_OR_REVOKED")
        require(type(operation) is str and operation and operation not in self.operations, "IO_REPLAY")
        require(type(deadline_ms) is int and 0 < deadline_ms - self._now() <= 250, "REQUEST_BOUND")
        require(direction in ("CONNECT", "READ", "WRITE"), "IO_DIRECTION")
        require(type(data) is bytes and type(maximum) is int, "IO_BYTES")
        if direction == "CONNECT":
            require(not self.connected and not data and maximum == 0, "CONNECT_STATE")
        else:
            require(self.connected and 1 <= maximum <= 4096, "IO_BOUND")
            require((direction == "READ" and not data) or (direction == "WRITE" and len(data) == maximum), "IO_BYTES")
        try:
            buffer = C.create_string_buffer(data, maximum) if direction == "WRITE" else C.create_string_buffer(maximum)
            event_value, error = self.api.call("CreateEventW", None, True, False, None)
            if event_value in (None, 0, INVALID_HANDLE_VALUE): raise Win32Error("CreateEventW", error)
            event = self._own(event_value, "EVENT")
            ov = OVERLAPPED(); ov.hEvent = event.value
            op = Operation(operation, direction, deadline_ms, buffer, maximum, event, ov)
            self._record("IO_START", operation=operation, direction=direction, maximum=maximum, deadline_ms=deadline_ms)
            # Logging can fail before any submission. Only pin after that point;
            # otherwise CancelIoEx would target an operation that never existed.
            self.pending = op; self.operations.add(operation); _INFLIGHT[id(op)] = self
            count = DWORD()
            if direction == "CONNECT":
                ok, error = self.api.call("ConnectNamedPipe", handle, C.byref(ov))
            else:
                ok, error = self.api.call("ReadFile" if direction == "READ" else "WriteFile",
                    handle, buffer, maximum, C.byref(count), C.byref(ov))
            if ok or direction == "CONNECT" and error == PIPE_CONNECTED:
                return self._finish("COMPLETE", count.value, 0)
            if error == IO_PENDING:
                return self._pending_result()
            return self._finish("FAILED", 0, error)  # initiation failed, no pending I/O
        except Exception:
            self.revoked = True
            self.close()
            raise

    def _pending_result(self):
        if self._now() >= self.pending.deadline:
            self.revoked = True
            self.cancel_io(self.pipe.value, self.pending.name)
        return {"operation": self.pending.name, "status": "PENDING", "count": 0, "data": b""}

    def _finish(self, status, count, error):
        op = self.pending
        require(op is not None, "NO_PENDING_IO")
        # Completion is known before releasing the pin, even on malformed counts.
        self.pending = None; _INFLIGHT.pop(id(op), None)
        valid = type(count) is int and 0 <= count <= op.size
        if status == "COMPLETE" and op.direction != "CONNECT": valid = valid and count > 0
        raw = bytes(op.buffer[:count]) if valid and op.direction == "READ" else b""
        closed = op.event.close()
        late = self._now() >= op.deadline or self.revoked or op.cancel_requested
        if not valid or not closed: status = "FAILED"
        if late and status == "COMPLETE": status = "REJECTED_LATE"
        self.revoked |= status != "COMPLETE"
        if status == "COMPLETE" and op.direction == "CONNECT": self.connected = True
        self._record("IO_COMPLETE", operation=op.name, direction=op.direction, status=status,
                     count=count, error=error, event_closed=closed,
                     wire_hex=(raw if op.direction == "READ" else bytes(op.buffer[:count]) if valid else b"").hex(),
                     sha256=sha256(raw if op.direction == "READ" else bytes(op.buffer[:count]) if valid else b""))
        return {"operation": op.name, "status": status, "count": count, "data": raw}

    @serialized
    def poll_io(self, handle, operation):
        self._handle(handle)
        require(self.pending is not None and self.pending.name == operation, "IO_OPERATION_BINDING")
        count = DWORD()
        ok, error = self.api.call("GetOverlappedResult", handle, C.byref(self.pending.overlapped), C.byref(count), False)
        if ok:
            # Win32 does not define bytes transferred for ConnectNamedPipe.
            return self._finish("COMPLETE", 0 if self.pending.direction == "CONNECT" else count.value, 0)
        if error in (OPERATION_ABORTED, BROKEN_PIPE, PIPE_NOT_CONNECTED):
            return self._finish("ABORTED" if error == OPERATION_ABORTED else "FAILED", 0, error)
        # Unknown error/invalid handle is not trusted completion evidence.
        if error != IO_INCOMPLETE:
            self.revoked = True
        return self._pending_result()

    @serialized
    def cancel_io(self, handle, operation):
        self._handle(handle)
        require(self.pending is not None and self.pending.name == operation, "IO_OPERATION_BINDING")
        self.revoked = True
        op = self.pending
        if op.cancel_requested: return False
        op.cancel_requested = True
        ok, error = self.api.call("CancelIoEx", handle, C.byref(op.overlapped))
        self._record("CANCEL_REQUEST", operation=op.name, accepted=bool(ok), error=0 if ok else error)
        return bool(ok)  # including ERROR_NOT_FOUND: must still observe completion

    @serialized
    def await_io(self, handle, operation):
        """Bounded owner tick; the external watchdog has a separate actor clock."""
        for _ in range(128):
            result = self.poll_io(handle, operation)
            if result["status"] != "PENDING" or self.revoked: return result
            wait_ms = max(0, min(10, self.pending.deadline - self._now()))
            code, _ = self.api.call("WaitForSingleObject", self.pending.event.value, wait_ms)
            if code not in (0, WAIT_TIMEOUT):
                self.revoked = True; self.cancel_io(handle, operation)
                return self._pending_result()
        self.revoked = True; self.cancel_io(handle, operation)
        return self._pending_result()

    def _token_data(self, token, kind):
        size = DWORD()
        ok, error = self.api.call("GetTokenInformation", token, kind, None, 0, C.byref(size))
        require(not ok and error == INSUFFICIENT_BUFFER and 0 < size.value <= 65536, "TOKEN_SIZE")
        capacity = size.value; buffer = C.create_string_buffer(capacity)
        self.api.checked("GetTokenInformation", token, kind, buffer, capacity, C.byref(size))
        require(0 < size.value <= capacity, "TOKEN_SIZE")
        return buffer, size.value

    def _principal(self, process):
        value = HANDLE()
        self.api.checked("OpenProcessToken", process, 8, C.byref(value))  # TOKEN_QUERY only
        token = self._own(value, "TOKEN")
        try:
            user, size = self._token_data(token.value, 1)
            require(size >= C.sizeof(SID_AND_ATTRIBUTES), "TOKEN_USER")
            sid = self._sid(C.cast(user, C.POINTER(SID_AND_ATTRIBUTES)).contents.Sid)
            groups, size = self._token_data(token.value, 2)
            require(size >= TOKEN_GROUPS.Groups.offset, "TOKEN_GROUPS")
            count = C.cast(groups, C.POINTER(DWORD)).contents.value
            require(count <= 1024 and TOKEN_GROUPS.Groups.offset + count * C.sizeof(SID_AND_ATTRIBUTES) <= size, "TOKEN_GROUPS")
            logons = []
            for n in range(count):
                group = SID_AND_ATTRIBUTES.from_buffer(groups, TOKEN_GROUPS.Groups.offset + n * C.sizeof(SID_AND_ATTRIBUTES))
                if group.Attributes & 0xC0000000 == 0xC0000000:
                    require(group.Attributes & 4 and not group.Attributes & 0x10, "LOGON_GROUP_DISABLED")
                    logons.append(self._sid(group.Sid))
            require(len(logons) == 1, "LOGON_GROUP_MISSING")
            return sid, logons[0]
        finally:
            require(token.close(), "TOKEN_CLOSE_UNCERTAIN")

    def _hash_image(self, path, deadline):
        # Hold a read-only file handle with no write/delete sharing throughout the
        # hash. This proves disk bytes, NOT the process's mapped component bytes.
        value, error = self.api.call("CreateFileW", path, 0x80000000, 1, None, 3, 0x08000000, None)
        if value in (None, 0, INVALID_HANDLE_VALUE): raise Win32Error("CreateFileW", error)
        image = self._own(value, "IMAGE")
        try:
            size = C.c_int64(); self.api.checked("GetFileSizeEx", value, C.byref(size))
            require(0 < size.value <= 256 * 1024 * 1024, "IMAGE_SIZE")
            left, digest = size.value, hashlib.sha256()
            buffer = C.create_string_buffer(65536)
            while left:
                require(self._now() < deadline, "REQUEST_TIMEOUT")
                count = DWORD(); amount = min(left, 65536)
                self.api.checked("ReadFile", value, buffer, amount, C.byref(count), None)
                require(0 < count.value <= amount, "IMAGE_READ_COUNT")
                digest.update(buffer[:count.value]); left -= count.value
            return digest.hexdigest()
        finally:
            require(image.close(), "IMAGE_CLOSE_UNCERTAIN")

    @serialized
    def query_client(self, handle, expected, *, deadline_ms):
        self._handle(handle)
        require(self.connected and not self.revoked and self.pending is None, "PEER_NOT_READY")
        require(set(expected) == {"pid", "creation", "path", "image_sha256", "sid", "logon_sid"}, "PEER_EXPECTED")
        try:
            require(type(deadline_ms) is int and 0 < deadline_ms - self._now() <= 250, "REQUEST_BOUND")
            require(type(expected["pid"]) is int and 0 < expected["pid"] <= 0xFFFFFFFF,
                    "PEER_PID")
            require(all(type(expected[k]) is str for k in expected if k != "pid"), "PEER_FIELDS")
            pid = DWORD(); self.api.checked("GetNamedPipeClientProcessId", handle, C.byref(pid))
            require(pid.value > 0 and pid.value == expected["pid"], "PEER_PID")
            if self.process is None:
                value, error = self.api.call("OpenProcess", 0x1000 | 0x100000, False, pid.value)
                if value in (None, 0, INVALID_HANDLE_VALUE): raise Win32Error("OpenProcess", error)
                self.process = self._own(value, "PROCESS")
            process = self.process.value
            require(self.api.call("WaitForSingleObject", process, 0)[0] == WAIT_TIMEOUT, "PEER_EXITED")
            times = [FILETIME() for _ in range(4)]
            self.api.checked("GetProcessTimes", process, *(C.byref(t) for t in times))
            creation = f"{(times[0].high << 32) | times[0].low:016X}"
            require(int(creation, 16) > 0, "PEER_CREATION")
            buffer, count = C.create_unicode_buffer(32768), DWORD(32768)
            self.api.checked("QueryFullProcessImageNameW", process, 0, buffer, C.byref(count))
            require(0 < count.value < 32768, "IMAGE_PATH")
            path = buffer[:count.value]
            require(PureWindowsPath(path).is_absolute() and not path.startswith("\\\\"), "IMAGE_PATH")
            sid, logon = self._principal(process)
            identity = {"pid": pid.value, "creation": creation, "path": path,
                        "image_sha256": self._hash_image(path, deadline_ms), "sid": sid, "logon_sid": logon}
            require(identity == expected and logon == self.spec["client_logon_sid"], "PEER_IDENTITY_MISMATCH")
            # Requery the SAME connected instance and held process after observation.
            again = DWORD(); self.api.checked("GetNamedPipeClientProcessId", handle, C.byref(again))
            require(again.value == pid.value and self.api.call("WaitForSingleObject", process, 0)[0] == WAIT_TIMEOUT, "PEER_CHANGED")
            require(self.read_security(handle) == self.security, "DACL_CHANGED")
            require(self._now() < deadline_ms, "REQUEST_TIMEOUT")
            self._record("CLIENT_IDENTITY", handle=handle, identity=identity,
                         server_identity="BLOCKED_CLIENT_HANDLE_UNVERIFIED", mapped_image="NOT_PROVEN")
            return {"origin": "SYNTHETIC", "os_observed": False, "client": identity,
                    "server_identity": "BLOCKED_CLIENT_HANDLE_UNVERIFIED", "mapped_image": "NOT_PROVEN"}
        except Exception:
            self.revoked = True; self.close(); raise

    def query_connection(self, *_args, **_kwargs):
        self._access()
        # Microsoft documents a server-created handle for GetNamedPipeServerProcessId.
        # An arbitrary CE LuaPipe object/handle is not a justified client-side witness.
        raise ProbeError("BLOCKED_CLIENT_HANDLE_UNVERIFIED")

    def challenge(self, *_args, **_kwargs):
        self._access()
        raise ProbeError("BLOCKED_RUNTIME_SECRET_PROVISIONING")

    @serialized
    def close(self, handle=None):
        self._access()
        if handle is not None:
            require(self.pipe is not None and handle == self.pipe.value, "HANDLE_BINDING")
        if self.close_attempted: return self.cleanup == "CLOSED"
        self.revoked = True
        if self.pending is not None:
            self.cancel_io(self.pipe.value, self.pending.name)
            self.cleanup = "PENDING_COMPLETION"
            return False
        self.close_attempted = True
        ok = not self.metadata_cleanup_failed
        if self.pipe is not None and not self.pipe.attempted:
            result, error = self.api.call("DisconnectNamedPipe", self.pipe.value)
            ok = bool(result) or error == PIPE_NOT_CONNECTED
        for resource in reversed(self.handles):
            ok = resource.close() and ok
        self.connected = False
        self.cleanup = "CLOSED" if ok else "UNCERTAIN"
        self._record("CLEANUP", result=self.cleanup, pending=False,
                     owned=len(self.handles), closed=sum(h.closed for h in self.handles))
        return ok
