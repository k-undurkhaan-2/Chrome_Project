"""API-level Win32 fakes. All handles are virtual, pointers address local fixtures."""
import ctypes as C
from copy import deepcopy

from ce_qualification import native_probe_win32 as w
from ce_qualification.native_probe_winpipe import NativeProvider
from native_probe_fakes import Clock

ENDPOINT = "\\\\.\\pipe\\qsg-r3-" + "b" * 32
OWNER = "S-1-5-21-1-2-3-1001"
SERVER_LOGON, CLIENT_LOGON = "S-1-5-5-10-11", "S-1-5-5-12-13"
SPEC = w.native_spec(ENDPOINT, OWNER, SERVER_LOGON, CLIENT_LOGON)
IMAGE = b"synthetic PE bytes, never an executable"
EXPECTED = {"pid": 101, "creation": "0000000000000001", "path": "D:\\synthetic\\ce.exe",
            "image_sha256": w.sha256(IMAGE), "sid": "S-1-5-21-1-2-3-1002", "logon_sid": CLIENT_LOGON}


def setout(pointer, value, kind=w.DWORD):
    C.cast(pointer, C.POINTER(kind))[0] = value


class FakeWinAPI:
    def __init__(self, *, client=None):
        self.clock, self.client = Clock(), client
        self.calls, self.closed, self.buffers, self.sid_names = [], [], [], {}
        self.error, self.next_handle = 0, 0x100000010
        self.pipe, self.image, self.process = 0x100000001, 0x100000002, 0x100000003
        self.identity = deepcopy(EXPECTED)
        self.image_bytes, self.image_cursor = IMAGE, 0
        self.spec, self.control, self.ace_count = deepcopy(SPEC), 0x1004, 2
        self.ace_mask, self.ace_flags, self.null_acl, self.security_error = None, 0, False, 0
        self.fail_api, self.close_failure, self.create_value = None, False, self.pipe
        self.fail_error, self.pending_direction, self.completion = 5, None, None
        self.cancel_error, self.pending, self.connect_error = 0, None, 0
        self.read_data, self.write_limit, self.count_override = b"bytes", 4096, None
        self.pid_after, self.pid_queries, self.process_exited = None, 0, False
        self.token_size_override, self.logon_attributes = None, 0xC0000004
        self.hook = lambda name: None
        self.descriptor = self._buffer(b"SYNTHETIC-DACL-ONLY")
        functions = {name: self._wrap(name) for name in w.SIGNATURES}
        self.api = w.WinAPI(functions, lambda: self.error, origin="SYNTHETIC")

    def _wrap(self, name):
        def invoke(*args):
            self.calls.append(name); self.hook(name)
            if name == self.fail_api:
                self.error = self.fail_error
                if name in ("CreateNamedPipeW", "CreateFileW"): return w.INVALID_HANDLE_VALUE
                return 0
            return getattr(self, name)(*args)
        return invoke

    def _buffer(self, data):
        value = C.create_string_buffer(data); self.buffers.append(value)
        return C.addressof(value)

    def _sid(self, name):
        address = self._buffer(b"fake-sid" + b"\0" * 24); self.sid_names[address] = name
        return address

    def _fail(self, code):
        self.error = code; return 0

    def ConvertStringSecurityDescriptorToSecurityDescriptorW(self, text, revision, out, size):
        assert text == SPEC["sddl"] and revision == 1
        setout(out, self.descriptor, w.PTR); setout(size, 20); return 1

    def LocalFree(self, pointer):
        self.error = 999  # must not overwrite a previously captured call failure
        return None

    def CreateNamedPipeW(self, name, flags, mode, instances, output, input_, timeout, attributes):
        assert (name, flags, mode, instances, output, input_, timeout) == (ENDPOINT, 0x40080003, 8, 1, 4096, 4096, 0)
        sa = C.cast(attributes, C.POINTER(w.SECURITY_ATTRIBUTES)).contents
        assert sa.nLength == C.sizeof(w.SECURITY_ATTRIBUTES) and not sa.bInheritHandle
        assert sa.lpSecurityDescriptor == self.descriptor
        if self.client: self.client.connect()
        if self.create_value in (None, 0, w.INVALID_HANDLE_VALUE): self.error = 5
        return self.create_value

    def GetSecurityInfo(self, handle, kind, information, owner, group, acl, sacl, descriptor):
        assert handle == self.pipe and kind == 6 and information == 5
        if self.security_error: return self.security_error
        setout(owner, self._sid(self.spec["owner_sid"]), w.PTR)
        setout(acl, None if self.null_acl else self.descriptor, w.PTR)
        setout(descriptor, self.descriptor, w.PTR); return 0

    def GetSecurityDescriptorControl(self, sd, control, revision):
        setout(control, self.control, w.WORD); setout(revision, 1); return 1

    def GetSecurityDescriptorLength(self, sd): return 20

    def ConvertSidToStringSidW(self, sid, out):
        address = sid.value if isinstance(sid, w.PTR) else sid
        value = C.create_unicode_buffer(self.sid_names[address]); self.buffers.append(value)
        setout(out, C.addressof(value), w.PTR); return 1

    def GetAclInformation(self, acl, out, size, kind):
        value = w.ACL_SIZE_INFORMATION(self.ace_count, 128, 0)
        C.memmove(out, C.byref(value), C.sizeof(value)); return 1

    def GetAce(self, acl, index, out):
        buffer = C.create_string_buffer(40); self.buffers.append(buffer)
        ace = w.ACCESS_ALLOWED_ACE.from_buffer(buffer)
        ace.AceType, ace.AceFlags, ace.AceSize = 0, self.ace_flags, 32
        ace.Mask = w.SERVER_ACCESS if index == 0 else w.CLIENT_ACCESS if self.ace_mask is None else self.ace_mask
        self.sid_names[C.addressof(buffer) + w.ACCESS_ALLOWED_ACE.SidStart.offset] = self.spec["server_logon_sid" if index == 0 else "client_logon_sid"]
        setout(out, C.addressof(buffer), w.PTR); return 1

    def CreateEventW(self, attributes, manual, initial, name):
        assert attributes is None and manual is True and initial is False and name is None
        self.next_handle += 1; return self.next_handle

    def ConnectNamedPipe(self, handle, ov):
        if self.pending_direction == "CONNECT":
            self.pending = ("CONNECT", None, 0, C.cast(ov, w.P_OV).contents.hEvent)
            return self._fail(w.IO_PENDING)
        return self._fail(self.connect_error) if self.connect_error else 1

    def _complete(self, direction, buffer, size, out):
        if direction == "READ":
            raw = self.client.receive(size) if self.client else self.read_data[:size]
            C.memmove(buffer, raw, len(raw)); count = len(raw)
        elif direction == "WRITE":
            raw = bytes(buffer[:min(size, self.write_limit)])
            count = self.client.send(raw) if self.client else len(raw)
        else: count = 0
        setout(out, count if self.count_override is None else self.count_override); return 1

    def ReadFile(self, handle, buffer, size, count, ov):
        if handle == self.image:
            assert ov is None
            raw = self.image_bytes[self.image_cursor:self.image_cursor + size]
            self.image_cursor += len(raw); C.memmove(buffer, raw, len(raw)); setout(count, len(raw)); return 1
        return self._io("READ", buffer, size, count, ov)

    def WriteFile(self, handle, buffer, size, count, ov):
        return self._io("WRITE", buffer, size, count, ov)

    def _io(self, direction, buffer, size, count, ov):
        if self.pending_direction == direction:
            self.pending = (direction, buffer, size, C.cast(ov, w.P_OV).contents.hEvent)
            return self._fail(w.IO_PENDING)
        return self._complete(direction, buffer, size, count)

    def GetOverlappedResult(self, handle, ov, count, wait):
        assert wait is False and self.pending is not None
        assert C.cast(ov, w.P_OV).contents.hEvent == self.pending[3]
        if self.completion is None: return self._fail(w.IO_INCOMPLETE)
        if self.completion:
            error = self.completion
            if error in (w.OPERATION_ABORTED, w.BROKEN_PIPE, w.PIPE_NOT_CONNECTED): self.pending = None
            return self._fail(error)
        direction, buffer, size, _ = self.pending; self.pending = None
        return self._complete(direction, buffer, size, count)

    def CancelIoEx(self, handle, ov):
        assert self.pending and C.cast(ov, w.P_OV).contents.hEvent == self.pending[3]
        return self._fail(self.cancel_error) if self.cancel_error else 1

    def CloseHandle(self, handle):
        assert handle not in self.closed, "double close"
        self.closed.append(handle)
        return self._fail(6) if self.close_failure else 1

    def DisconnectNamedPipe(self, handle): return 1

    def WaitForSingleObject(self, handle, milliseconds):
        if handle == self.process: return 0 if self.process_exited else w.WAIT_TIMEOUT
        self.clock.advance(milliseconds); return w.WAIT_TIMEOUT

    def GetNamedPipeClientProcessId(self, handle, out):
        assert handle == self.pipe
        self.pid_queries += 1
        setout(out, self.pid_after if self.pid_queries > 1 and self.pid_after is not None else self.identity["pid"])
        return 1

    def OpenProcess(self, access, inherit, pid):
        assert access == 0x101000 and inherit is False and pid == self.identity["pid"]
        return self.process

    def GetProcessTimes(self, handle, created, exited, kernel, user):
        value = int(self.identity["creation"], 16)
        C.cast(created, C.POINTER(w.FILETIME))[0] = w.FILETIME(value & 0xFFFFFFFF, value >> 32)
        return 1

    def QueryFullProcessImageNameW(self, handle, flags, buffer, count):
        buffer.value = self.identity["path"]; setout(count, len(buffer.value)); return 1

    def OpenProcessToken(self, process, access, out):
        assert process == self.process and access == 8
        self.next_handle += 1; setout(out, self.next_handle, w.HANDLE); return 1

    def GetTokenInformation(self, token, kind, buffer, capacity, out):
        value = w.SID_AND_ATTRIBUTES(self._sid(self.identity["sid"]), 0) if kind == 1 else w.TOKEN_GROUPS()
        if kind == 2:
            value.GroupCount = 1; value.Groups[0] = w.SID_AND_ATTRIBUTES(self._sid(self.identity["logon_sid"]), self.logon_attributes)
        size = C.sizeof(value)
        if buffer is None:
            setout(out, size if self.token_size_override is None else self.token_size_override)
            return self._fail(w.INSUFFICIENT_BUFFER)
        C.memmove(buffer, C.byref(value), size); setout(out, size); return 1

    def CreateFileW(self, path, access, share, sa, mode, flags, template):
        assert path == self.identity["path"] and access == 0x80000000 and share == 1 and mode == 3
        self.image_cursor = 0; return self.image

    def GetFileSizeEx(self, handle, size):
        setout(size, len(self.image_bytes), C.c_int64); return 1


def equipment(*, client=None, connect=True):
    fake = FakeWinAPI(client=client)
    provider = NativeProvider(api=fake.api, clock_ms=fake.clock)
    handle = provider.create(SPEC)
    if connect:
        assert provider.start_io(handle, "connect", "CONNECT", deadline_ms=250)["status"] == "COMPLETE"
    return provider, fake, handle
