"""Inactive H3 evidence-store prototype; Python 3.14 stdlib, no H3 dispatch.

Only a trusted bootstrap may supply a backend. ``True`` means checked storage
publication in the qualified context, never memory/owner authority or proof of
unexpected power-loss durability. See h3_windows_durable_store_contract.md.
"""

from contextlib import contextmanager
from datetime import datetime
import hashlib
import math
import re
import struct


MAX_RECORD = 16384
FIELDS = tuple("schema source_kind environment request_id action approval_sha256 "
               "sources_sha256 process_sha256 scope_sha256 candidate_address "
               "current_float current_pattern target_float target_pattern issued_utc "
               "expires_utc max_elapsed_ms reservation_sha256 preparation_sha256 state "
               "attempted api_result api_ok readback_ok execution_success failure_class "
               "last_checked_utc last_checked_monotonic_ms".split())
KINDS = ("reservation", "preparation", "receipt")
RESERVED = {"con", "prn", "aux", "nul", "clock$", "conin$", "conout$"} | {
    f"{p}{n}" for p in ("com", "lpt") for n in range(1, 10)}
FAILURES = frozenset("initial_value_mismatch preparation_persistence_failed "
                    "preparation_readback_failed identity_mismatch scene_mismatch "
                    "clock_unavailable approval_not_current clock_rollback "
                    "monotonic_deadline clock_discontinuity prewrite_value_mismatch "
                    "mutation_api_false mutation_api_nil mutation_api_nonboolean "
                    "mutation_api_exception readback_mismatch protocol_exception "
                    "hash_unavailable".split())


class StoreError(Exception):
    """Fail-closed code; component details are private unless explicitly sanitized."""

    def __init__(self, code, *, api=None, component=None, winerror=None):
        super().__init__(code)
        self.code, self.api = code, api
        self.component, self.winerror = component, winerror


def require(condition, code="INVALID_RECORD"):
    if not condition:
        raise StoreError(code)


def path_require(condition, code, component):
    if not condition:
        raise StoreError(code, component=component)


def sha256(body):
    return hashlib.sha256(body).hexdigest()


def request_token(value):
    require(type(value) is str and re.fullmatch(r"[a-z][a-z0-9-]{0,63}", value)
            and not value.endswith("-") and value not in RESERVED, "INVALID_REQUEST_ID")
    return value


def digest(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def decimal(value, low, high):
    require(re.fullmatch(r"0|[1-9][0-9]{0,15}", value) is not None)
    result = int(value)
    require(low <= result <= high)
    return result


def utc(value):
    require(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value) is not None)
    try:
        result = datetime.fromisoformat(value[:-1])
    except ValueError:
        raise StoreError("INVALID_RECORD") from None
    require(result.year >= 1970)
    return result


def encode(fields, values):
    return "".join(f"{k}={values[k]}\r\n" for k in fields).encode("ascii")


def parse(body, fields=FIELDS):
    require(type(body) is bytes and 0 < len(body) <= MAX_RECORD and body.endswith(b"\r\n"))
    lines = body[:-2].split(b"\r\n")
    require(len(lines) == len(fields))
    result = {}
    for key, line in zip(fields, lines, strict=True):
        require(all(32 <= c <= 126 for c in line))
        prefix = key.encode("ascii") + b"="
        require(line.startswith(prefix) and 1 <= len(line) - len(prefix) <= 512)
        result[key] = line[len(prefix):].decode("ascii")
    return result


def validate_record(body, request, kind):
    """Exact A2 wire checks; claims are structural, not authenticated authority."""
    request_token(request)
    require(kind in KINDS, "INVALID_KIND")
    f = parse(body)
    require(f["request_id"] == request and f["source_kind"] == "h3_single"
            and f["environment"] == "synthetic_only")
    require(f["action"] in ("single_float32_write_once", "single_float32_restore_once"))
    action = "write" if f["action"] == "single_float32_write_once" else "restore"
    schema = "h3_operation_reservation_v1" if kind == "reservation" else f"h3_single_{action}_{kind}_v1"
    require(f["schema"] == schema)
    require(all(digest(f[k]) for k in FIELDS[5:9]))
    address = f["candidate_address"]
    require(re.fullmatch(r"0x[1-9A-F][0-9A-F]{0,13}", address) is not None)
    require(int(address, 16) <= 0x1FFFFFFFFFFFFF)
    for prefix in ("current", "target"):
        pattern = f[prefix + "_pattern"]
        require(re.fullmatch(r"0x[0-9A-F]{8}", pattern) is not None)
        number = struct.unpack("<f", struct.pack("<I", int(pattern, 16)))[0]
        require(math.isfinite(number) and format(number, ".17g") == f[prefix + "_float"])
    require(f["current_pattern"] != f["target_pattern"])
    issued, expires, checked = (utc(f[k]) for k in ("issued_utc", "expires_utc", "last_checked_utc"))
    require(0 < (expires - issued).total_seconds() <= 120 and issued <= checked < expires)
    decimal(f["max_elapsed_ms"], 1, 120000)
    decimal(f["last_checked_monotonic_ms"], 0, 0x1FFFFFFFFFFFFF)
    for key in ("attempted", "api_ok", "readback_ok", "execution_success"):
        require(f[key] in ("true", "false"))
    require(f["api_result"] in ("not_called", "true", "false", "nil", "nonboolean", "exception"))
    if kind != "receipt":
        require(f["state"] == ("RESERVED" if kind == "reservation" else "PREPARED"))
        require(all(f[k] == "false" for k in ("attempted", "api_ok", "readback_ok", "execution_success")))
        require(f["api_result"] == "not_called" and f["failure_class"] == "nil")
    elif f["state"] == "CONFIRMED":
        require(all(f[k] == "true" for k in ("attempted", "api_result", "api_ok", "readback_ok", "execution_success")))
        require(f["failure_class"] == "nil")
    else:
        require(f["state"] == "UNCONFIRMED" and f["execution_success"] == "false"
                and f["failure_class"] in FAILURES)
        require((f["api_ok"] == "true") == (f["api_result"] == "true"))
        require((f["attempted"] == "false") == (f["api_result"] == "not_called"))
        if f["attempted"] == "false":
            require(f["readback_ok"] == "false")
    if kind == "reservation":
        require(f["reservation_sha256"] == f["preparation_sha256"] == "nil")
    else:
        require(digest(f["reservation_sha256"]))
        require(f["preparation_sha256"] == "nil" if kind == "preparation" else
                (digest(f["preparation_sha256"]) or
                 (f["preparation_sha256"] == "nil" and f["attempted"] == "false")))
    return f


def validate_chain(records, request):
    parsed = {k: validate_record(b, request, k) for k, b in records.items()}
    require("reservation" in parsed, "INCOMPLETE_CHAIN")
    first = parsed["reservation"]
    previous = first
    for kind in KINDS[1:]:
        if kind not in parsed:
            continue
        f = parsed[kind]
        require(all(f[k] == first[k] for k in FIELDS[1:17]), "CHAIN_MISMATCH")
        require(f["reservation_sha256"] == sha256(records["reservation"]), "CHAIN_MISMATCH")
        if kind == "receipt":
            prep_hash = sha256(records["preparation"]) if "preparation" in records else "nil"
            require(f["preparation_sha256"] == prep_hash, "CHAIN_MISMATCH")
            require("preparation" in records or f["attempted"] == "false", "INCOMPLETE_CHAIN")
        now, before, start = (utc(x["last_checked_utc"]) for x in (f, previous, first))
        mono, old, origin = (int(x["last_checked_monotonic_ms"]) for x in (f, previous, first))
        require(now >= before and mono >= old and mono - origin <= int(f["max_elapsed_ms"])
                and abs((now - start).total_seconds() * 1000 - (mono - origin)) <= 1000, "CHAIN_TIME")
        previous = f
    return parsed


class EvidenceStore:
    """Explicit trusted backend, shared persistent namespace; no default backend.

    Backend operations: check, create_new, write, flush, close, read, move_new,
    names, guard, identity. They must raise StoreError and preserve ambiguous artifacts.
    Reopening NEVER initializes a namespace. Fresh bootstrap is separate.
    """

    def __init__(self, backend, *, initialize=False):
        self.backend, self.poisoned = backend, False
        self.namespace = ("h3-test-store-v1\r\nroot=" + backend.identity + "\r\n").encode("ascii")
        backend.check()
        if initialize:
            require(backend.names() == [], "ROOT_NOT_FRESH")
            self._new("namespace", self.namespace)
        require(backend.read("namespace") == self.namespace, "NAMESPACE_MISMATCH")
        self._healthy()

    def _healthy(self):
        require(not self.poisoned, "NAMESPACE_QUARANTINED")
        self.backend.check()
        try:
            self.backend.read("quarantine")
        except StoreError as error:
            if error.code != "MISSING":
                raise
        else:
            raise StoreError("NAMESPACE_QUARANTINED")
        require(self.backend.read("namespace") == self.namespace, "NAMESPACE_MISMATCH")

    def _poison(self):
        self.poisoned = True
        try:
            self._new("quarantine", b"ROOT_TRUST_OR_IO_UNCERTAIN\r\n")
        except StoreError:
            pass  # Caller must retain external quarantine if storage is unavailable.

    def _new(self, name, body):
        h = self.backend.create_new(name)
        try:
            require(self.backend.write(h, body) == len(body), "SHORT_WRITE")
            self.backend.flush(h)
        finally:
            self.backend.close(h)
        require(self.backend.read(name) == body, "READBACK_MISMATCH")

    def _publish(self, name, body):
        self._new(name + ".stage", body)
        self.backend.check()
        self.backend.move_new(name + ".stage", name)
        require(self.backend.read(name) == body, "READBACK_MISMATCH")
        self.backend.check()

    @contextmanager
    def _operation(self):
        try:
            self._healthy()
            yield
            self.backend.check()
        except StoreError as error:
            # Invalid caller data and definitive collisions do not invalidate
            # other IDs. All ambiguous I/O/root errors poison this namespace.
            if error.code not in ("COLLISION", "INVALID_RECORD", "INVALID_REQUEST_ID", "INVALID_KIND",
                                  "CHAIN_MISMATCH", "CHAIN_TIME", "INCOMPLETE_CHAIN", "NOT_CONFIRMED",
                                  "MISSING", "REQUEST_QUARANTINED", "BUSY", "STAGE_ORDER"):
                self._poison()
            raise

    @staticmethod
    def _name(request, kind):
        request_token(request)
        require(kind in (*KINDS, "claim", "finalized", "gate"), "INVALID_KIND")
        return f"r-{request}.{kind}"

    def _claim_bytes(self, request, reservation):
        return (f"h3-claim-v1\r\nrequest={request}\r\nreservation={sha256(reservation)}\r\n"
                f"namespace={sha256(self.namespace)}\r\n").encode("ascii")

    @contextmanager
    def _guard(self, request, *, transition=False):
        with self.backend.guard(self._name(request, "gate")):
            if transition:
                for kind in (*KINDS, "finalized"):
                    try:
                        self.backend.read(self._name(request, kind) + ".stage")
                    except StoreError as error:
                        if error.code != "MISSING":
                            raise
                    else:
                        raise StoreError("REQUEST_QUARANTINED")
            yield

    def _absent(self, request, kinds):
        for kind in kinds:
            try:
                self.backend.read(self._name(request, kind))
            except StoreError as error:
                if error.code != "MISSING":
                    raise
            else:
                raise StoreError("STAGE_ORDER")

    def _records(self, request, through):
        records = {}
        for kind in KINDS[:KINDS.index(through) + 1]:
            try:
                records[kind] = self.backend.read(self._name(request, kind))
            except StoreError as error:
                if kind != "preparation" or through != "receipt" or error.code != "MISSING":
                    raise
        require(self.backend.read(self._name(request, "claim")) ==
                self._claim_bytes(request, records["reservation"]), "REQUEST_QUARANTINED")
        validate_chain(records, request)
        return records

    def reserve(self, request_id, kind, exact_bytes):
        require(kind == "reservation", "INVALID_KIND")
        validate_record(exact_bytes, request_id, kind)
        with self._operation():
            # CREATE_NEW is the linearization point, even for an empty claim.
            self._new(self._name(request_id, "claim"), self._claim_bytes(request_id, exact_bytes))
            self._new(self._name(request_id, "gate"), b"h3-transition-gate-v1\r\n")
            with self._guard(request_id, transition=True):
                self._publish(self._name(request_id, kind), exact_bytes)
                require(self._records(request_id, kind)[kind] == exact_bytes, "READBACK_MISMATCH")
        return True

    def publish(self, request_id, kind, exact_bytes):
        require(kind in ("preparation", "receipt"), "INVALID_KIND")
        f = validate_record(exact_bytes, request_id, kind)
        with self._operation(), self._guard(request_id, transition=True):
            self._absent(request_id, ("receipt", "finalized") if kind == "preparation" else ("finalized",))
            records = self._records(request_id, "reservation")
            if kind == "receipt":
                try:
                    records["preparation"] = self._records(request_id, "preparation")["preparation"]
                except StoreError as error:
                    if error.code != "MISSING" or f["preparation_sha256"] != "nil" or f["attempted"] != "false":
                        raise
            records[kind] = exact_bytes
            validate_chain(records, request_id)
            self._publish(self._name(request_id, kind), exact_bytes)
            require(self._records(request_id, kind)[kind] == exact_bytes, "READBACK_MISMATCH")
        return True

    def read_record(self, request_id, kind):
        request_token(request_id)
        require(kind in KINDS, "INVALID_KIND")
        with self._operation(), self._guard(request_id):
            result = self._records(request_id, kind)[kind]
        return result

    def _final_bytes(self, request, records):
        f = validate_chain(records, request)["receipt"]
        require(f["state"] == "CONFIRMED" and "preparation" in records, "NOT_CONFIRMED")
        return (f"h3-finalized-v1\r\nnamespace={sha256(self.namespace)}\r\nrequest={request}\r\n"
                f"action={f['action']}\r\n" + "".join(f"{k}={sha256(records[k])}\r\n" for k in KINDS)).encode("ascii")

    def finalize_receipt(self, request_id, receipt_sha256):
        request_token(request_id)
        require(digest(receipt_sha256))
        with self._operation(), self._guard(request_id, transition=True):
            records = self._records(request_id, "receipt")
            require(sha256(records["receipt"]) == receipt_sha256, "CHAIN_MISMATCH")
            self._publish(self._name(request_id, "finalized"), self._final_bytes(request_id, records))
            require(self._read_finalized(request_id) == records["receipt"], "READBACK_MISMATCH")
        return True

    def read_finalized(self, request_id):
        request_token(request_id)
        with self._operation(), self._guard(request_id):
            result = self._read_finalized(request_id)
        return result

    def _read_finalized(self, request_id):
        records = self._records(request_id, "receipt")
        require(self.backend.read(self._name(request_id, "finalized")) ==
                self._final_bytes(request_id, records), "REQUEST_QUARANTINED")
        return records["receipt"]


def local_root(path):
    """Conservative canonical subset; no normalization, expansion or fallback."""
    require(type(path) is str and len(path) <= 160 and re.match(r"^[A-Z]:\\", path), "UNSAFE_ROOT_PATH")
    parts = path[3:].split("\\") if len(path) > 3 else []
    for part in parts:
        require(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_. -]{0,79}", part) is not None
                and not part.endswith((".", " ")) and ".." not in part
                and part.split(".")[0].lower() not in RESERVED, "UNSAFE_ROOT_PATH")
    return [path[:3]] + [path[:3] + "\\".join(parts[:n]) for n in range(1, len(parts) + 1)]


class WindowsBackend:
    """Explicit storage-native-only test runtime. Construction establishes trust.

    No privilege/ACL changes. All directories stay open without write/delete
    sharing; unsupported capabilities and sharing/access errors fail closed.
    ``expected_identity`` is mandatory on reopen, obtained from trusted bootstrap.
    """

    def __init__(self, root, *, approved_test_root=False, expected_identity=None, api=None):
        require(approved_test_root is True, "TEST_BOOTSTRAP_REQUIRED")
        self.root, self.parts, self.pins = root, local_root(root), []
        self.api = api if api is not None else Win32()
        self.closed = False
        try:
            for part in self.parts:
                h = self.api.open_directory(part)
                try:
                    facts = self._inspect_directory(h, part)
                except BaseException:
                    self.api.close(h)
                    raise
                self.pins.append((part, h, facts["identity"]))
            self.identity = self.pins[-1][2]
            path_require(expected_identity is None or self.identity == expected_identity, "ROOT_IDENTITY_MISMATCH", root)
            self.volume = self.api.volume(self.pins[-1][1], self.parts[0])
            require(self.volume["filesystem"] == "NTFS" and self.volume["drive_type"] == 3
                    and self.volume["flags"] & 8 and not self.volume["flags"] & 0x80000, "FILESYSTEM_UNQUALIFIED")
            self.check()
        except BaseException:
            self.shutdown()
            raise

    def _inspect_directory(self, handle, path):
        try:
            return self.api.inspect(handle, path, directory=True)
        except StoreError as error:
            if error.winerror is not None:
                raise StoreError("ROOT_TRUST_UNPROVEN", api=error.api, component=path,
                                 winerror=error.winerror) from None
            raise

    def check(self):
        require(not self.closed, "BACKEND_CLOSED")
        for path, h, identity in self.pins:
            path_require(self._inspect_directory(h, path)["identity"] == identity, "ROOT_IDENTITY_MISMATCH", path)
            other = self.api.open_directory(path)
            try:
                path_require(self._inspect_directory(other, path)["identity"] == identity, "ROOT_IDENTITY_MISMATCH", path)
            finally:
                self.api.close(other)

    def path(self, name):
        require(type(name) is str and len(name) <= 110 and
                re.fullmatch(r"[a-z][a-z0-9.-]*", name) and ".." not in name
                and not name.endswith(".") and name.split(".")[0] not in RESERVED, "UNSAFE_CHILD")
        return self.root.rstrip("\\") + "\\" + name

    def names(self):
        self.check()
        result = self.api.names(self.root)
        self.check()
        return result

    def create_child(self, name):
        """Bootstrap only: one new directory directly under a pinned parent."""
        self.check()
        path = self.path(name)
        self.api.mkdir(path)
        self.check()
        return path

    def create_new(self, name):
        self.check()
        path = self.path(name)
        h = self.api.create_new(path)
        try:
            self.api.inspect(h, path, directory=False)
        except BaseException:
            self.api.close(h)
            raise
        return h

    def write(self, handle, body):
        self.check()
        require(type(body) is bytes and 0 < len(body) <= MAX_RECORD, "INVALID_RECORD")
        return self.api.write(handle, body)

    def flush(self, handle):
        self.api.flush(handle)

    def close(self, handle):
        self.api.close(handle)

    def read(self, name):
        self.check()
        path = self.path(name)
        h = self.api.open_read(path)
        try:
            before = self.api.inspect(h, path, directory=False)
            require(before["size"] <= MAX_RECORD, "RECORD_TOO_LARGE")
            body = self.api.read(h, MAX_RECORD + 1)
            after = self.api.inspect(h, path, directory=False)
            require(before == after and len(body) == before["size"], "READBACK_MISMATCH")
        finally:
            self.api.close(h)
        self.check()
        return body

    def move_new(self, source, target):
        self.check()
        # Both strict basenames, same pinned root, no replace/copy/reboot flags.
        self.api.move_new(self.path(source), self.path(target))
        self.check()

    @contextmanager
    def guard(self, name):
        self.check()
        path = self.path(name)
        h = self.api.open_gate(path)
        try:
            self.api.inspect(h, path, directory=False)
            require(self.api.read(h, 64) == b"h3-transition-gate-v1\r\n", "REQUEST_QUARANTINED")
            yield
        finally:
            self.api.close(h)

    def shutdown(self):
        errors = []
        for _, h, _ in reversed(self.pins):
            try:
                self.api.close(h)
            except StoreError as error:
                errors.append(error)
        self.pins.clear()
        self.closed = True
        if errors:
            raise errors[0]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.shutdown()


class Win32:
    """Small injectable native boundary. DLL loading occurs only on construction."""

    def __init__(self):
        import ctypes as c
        from ctypes import wintypes as w
        import os
        require(os.name == "nt", "WINDOWS_REQUIRED")
        self.c, self.w = c, w
        self.k = c.WinDLL("kernel32", use_last_error=True)

        class Info(c.Structure):
            _fields_ = [("attributes", w.DWORD), ("created", w.FILETIME), ("accessed", w.FILETIME),
                        ("written", w.FILETIME), ("serial", w.DWORD), ("size_high", w.DWORD),
                        ("size_low", w.DWORD), ("links", w.DWORD), ("index_high", w.DWORD), ("index_low", w.DWORD)]

        class FileID(c.Structure):
            _fields_ = [("serial", c.c_ulonglong), ("identifier", c.c_ubyte * 16)]

        self.Info, self.FileID = Info, FileID
        signatures = {
            "CreateFileW": ([w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE], w.HANDLE),
            "CloseHandle": ([w.HANDLE], w.BOOL),
            "WriteFile": ([w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p], w.BOOL),
            "ReadFile": ([w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p], w.BOOL),
            "FlushFileBuffers": ([w.HANDLE], w.BOOL),
            "MoveFileExW": ([w.LPCWSTR, w.LPCWSTR, w.DWORD], w.BOOL),
            "CreateDirectoryW": ([w.LPCWSTR, c.c_void_p], w.BOOL),
            "GetFileInformationByHandle": ([w.HANDLE, c.POINTER(Info)], w.BOOL),
            "GetFileInformationByHandleEx": ([w.HANDLE, c.c_int, c.c_void_p, w.DWORD], w.BOOL),
            "GetFinalPathNameByHandleW": ([w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD], w.DWORD),
            "GetVolumeInformationByHandleW": ([w.HANDLE, w.LPWSTR, w.DWORD, c.POINTER(w.DWORD),
                                               c.POINTER(w.DWORD), c.POINTER(w.DWORD), w.LPWSTR, w.DWORD], w.BOOL),
            "GetDriveTypeW": ([w.LPCWSTR], w.UINT),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.k, name)
            function.argtypes, function.restype = args, result

    def _error(self, api, component=None, *, opening=False, creating=False):
        error = self.c.get_last_error()
        code = "COLLISION" if creating and error in (80, 183) else (
            "MISSING" if opening and error in (2, 3) else "NATIVE_IO_UNCERTAIN")
        raise StoreError(code, api=api, component=component, winerror=error)

    def _open(self, path, access, sharing, disposition, flags, *, directory=False):
        h = self.k.CreateFileW(path, access, sharing, None, disposition, flags, None)
        if h == self.c.c_void_p(-1).value:
            if directory:
                raise StoreError("ROOT_TRUST_UNPROVEN", api="CreateFileW", component=path,
                                 winerror=self.c.get_last_error())
            self._error("CreateFileW", path, opening=disposition == 3, creating=disposition == 1)
        return h

    def open_directory(self, path):
        return self._open(path, 0x80, 1, 3, 0x02200000, directory=True)

    def create_new(self, path):
        return self._open(path, 0xC0000000, 0, 1, 0x80200080)

    def open_read(self, path):
        return self._open(path, 0x80000000, 1, 3, 0x00200000)

    def open_gate(self, path):
        try:
            return self._open(path, 0x80000000, 0, 3, 0x00200000)
        except StoreError as error:
            if error.winerror == 32:
                raise StoreError("BUSY", api=error.api, component=path, winerror=32) from None
            raise

    def inspect(self, handle, path, *, directory):
        c, w = self.c, self.w
        info, identity = self.Info(), self.FileID()
        if not self.k.GetFileInformationByHandle(handle, c.byref(info)):
            self._error("GetFileInformationByHandle", path)
        path_require(not info.attributes & 0x400 and bool(info.attributes & 0x10) == directory, "REPARSE_OR_TYPE_UNSAFE", path)
        if not directory:
            path_require(info.links == 1, "HARDLINK_UNSAFE", path)
        if not self.k.GetFileInformationByHandleEx(handle, 18, c.byref(identity), c.sizeof(identity)):
            self._error("GetFileInformationByHandleEx:FileIdInfo", path)
        if directory:
            case_flags = w.DWORD()
            if not self.k.GetFileInformationByHandleEx(handle, 23, c.byref(case_flags), c.sizeof(case_flags)):
                self._error("GetFileInformationByHandleEx:FileCaseSensitiveInfo", path)
            path_require(case_flags.value == 0, "CASE_SENSITIVE_ROOT_UNSUPPORTED", path)
        final = c.create_unicode_buffer(1024)
        length = self.k.GetFinalPathNameByHandleW(handle, final, len(final), 0)
        if not length:
            self._error("GetFinalPathNameByHandleW", path)
        path_require(length < len(final) and final.value.casefold().rstrip("\\") ==
                     ("\\\\?\\" + path).casefold().rstrip("\\"), "PATH_IDENTITY_MISMATCH", path)
        return {"identity": f"{identity.serial:016x}-{bytes(identity.identifier).hex()}",
                "size": (info.size_high << 32) | info.size_low,
                "written": (info.written.dwHighDateTime << 32) | info.written.dwLowDateTime,
                "attributes": info.attributes, "links": info.links}

    def volume(self, handle, drive):
        c, w = self.c, self.w
        fs = c.create_unicode_buffer(64)
        serial, maximum, flags = w.DWORD(), w.DWORD(), w.DWORD()
        if not self.k.GetVolumeInformationByHandleW(handle, None, 0, c.byref(serial), c.byref(maximum),
                                                   c.byref(flags), fs, len(fs)):
            self._error("GetVolumeInformationByHandleW", drive)
        return {"filesystem": fs.value, "volume_serial": serial.value, "flags": flags.value,
                "maximum_component": maximum.value, "drive_type": self.k.GetDriveTypeW(drive)}

    def write(self, handle, body):
        count = self.w.DWORD()
        buffer = self.c.create_string_buffer(body)
        if not self.k.WriteFile(handle, buffer, len(body), self.c.byref(count), None):
            self._error("WriteFile")
        return count.value

    def read(self, handle, limit):
        count, buffer = self.w.DWORD(), self.c.create_string_buffer(limit)
        if not self.k.ReadFile(handle, buffer, limit, self.c.byref(count), None):
            self._error("ReadFile")
        return buffer.raw[:count.value]

    def flush(self, handle):
        if not self.k.FlushFileBuffers(handle):
            self._error("FlushFileBuffers")

    def close(self, handle):
        if not self.k.CloseHandle(handle):
            self._error("CloseHandle")

    def move_new(self, source, target):
        if not self.k.MoveFileExW(source, target, 8):
            self._error("MoveFileExW", target, creating=True)

    def mkdir(self, path):
        if not self.k.CreateDirectoryW(path, None):
            self._error("CreateDirectoryW", path, creating=True)

    def names(self, path):
        import os
        try:
            with os.scandir(path) as entries:
                result = []
                for entry in entries:
                    require(len(result) < 4096, "ROOT_ENTRY_LIMIT")
                    result.append(entry.name)
                return sorted(result)
        except OSError as error:
            raise StoreError("ROOT_TRUST_UNPROVEN", api="scandir", component=path, winerror=error.winerror) from None
