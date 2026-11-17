"""Deterministic storage simulation, not Windows native qualification.

Every file here is an in-memory fake, including contention/restart/fault cases.
The separate native probe must qualify actual Win32 calls under the operator.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import ctypes
import importlib.util
from pathlib import Path
import struct
import threading

import pytest

from armedforces_tool import h3_windows_durable_store as m
from h3_windows_store_native_probe import TripBackend, records, cycle
import h3_windows_store_native_probe as probe


class MemoryFS:
    def __init__(self):
        self.files, self.handles, self.gates = {}, {}, set()
        self.lock, self.next_handle = threading.RLock(), 1
        self.identity = "0000000000000001-" + "2" * 32
        self.root_error = None
        self.events = []

    def check(self):
        if self.root_error:
            raise m.StoreError(self.root_error)

    def names(self):
        return sorted(self.files)

    def create_new(self, name):
        with self.lock:
            self.events.append(("create", name))
            if name in self.files:
                raise m.StoreError("COLLISION", winerror=80)
            self.files[name] = b""
            h = self.next_handle
            self.next_handle += 1
            self.handles[h] = name
            return h

    def write(self, h, body):
        self.events.append(("write", self.handles[h]))
        self.files[self.handles[h]] += body
        return len(body)

    def flush(self, h):
        self.events.append(("flush", self.handles[h]))

    def close(self, h):
        self.events.append(("close", self.handles[h]))
        del self.handles[h]

    def read(self, name):
        self.events.append(("read", name))
        if name not in self.files:
            raise m.StoreError("MISSING", winerror=2)
        return self.files[name]

    def move_new(self, source, target):
        with self.lock:
            self.events.append(("move", target))
            if target in self.files:
                raise m.StoreError("COLLISION", winerror=183)
            if source not in self.files:
                raise m.StoreError("MISSING")
            self.files[target] = self.files.pop(source)

    @contextmanager
    def guard(self, name):
        with self.lock:
            if name in self.gates:
                raise m.StoreError("BUSY", winerror=32)
            if self.read(name) != b"h3-transition-gate-v1\r\n":
                raise m.StoreError("REQUEST_QUARANTINED")
            self.gates.add(name)
        try:
            yield
        finally:
            with self.lock:
                self.gates.remove(name)


@pytest.fixture
def backend():
    return MemoryFS()


@pytest.fixture
def store(backend):
    return m.EvidenceStore(backend, initialize=True)


def change(body, field, value):
    f = m.parse(body)
    f[field] = value
    return m.encode(m.FIELDS, f)


def rejected(fn, *codes):
    with pytest.raises(m.StoreError) as error:
        fn()
    if codes:
        assert error.value.code in codes
    return error.value


@pytest.mark.parametrize("action", ["write", "restore"])
def test_exact_cycle_reopen_and_finalization(store, backend, action):
    raw = cycle(m, store, action=action)
    reopened = m.EvidenceStore(backend)
    for kind in m.KINDS:
        assert reopened.read_record("native-one", kind) == raw[kind]
    assert reopened.read_finalized("native-one") == raw["receipt"]
    assert not any(n.endswith(".stage") for n in backend.files)
    assert not backend.handles
    for kind in (*m.KINDS, "finalized"):
        name = "r-native-one." + kind
        events = [event for event in backend.events if event[1] in (name, name + ".stage")]
        assert events.index(("flush", name + ".stage")) < events.index(("close", name + ".stage"))
        closed = events.index(("close", name + ".stage"))
        assert closed < events.index(("read", name + ".stage"), closed) < events.index(("move", name))


@pytest.mark.parametrize("action", ["write", "restore"])
@pytest.mark.parametrize("stage", ["claim", "gate", "reservation", "preparation", "receipt", "finalized"])
@pytest.mark.parametrize("method", ["create", "write", "flush", "close", "read", "move", "read-published"])
def test_each_io_boundary_fails_closed_and_preserves_consumption(backend, action, stage, method):
    m.EvidenceStore(backend, initialize=True)
    # Claim/gate have no rename; exercise their independent reopening instead.
    actual_method = "read" if method in ("move", "read-published") and stage in ("claim", "gate") else method
    suffix = stage if stage in ("claim", "gate") or method in ("move", "read-published") else stage + ".stage"
    if actual_method == "read-published":
        actual_method = "read"
    trip = TripBackend(backend, m, actual_method, "r-native-one." + suffix)
    failed = m.EvidenceStore(trip)
    rejected(lambda: cycle(m, failed, action=action), "INJECTED_IO_UNCERTAIN")
    assert trip.fired and "r-native-one.claim" in backend.files
    assert not backend.handles
    rejected(lambda: m.EvidenceStore(backend), "NAMESPACE_QUARANTINED")
    assert "quarantine" in backend.files
    assert failed.poisoned is True


@pytest.mark.parametrize("kind", ["claim", "gate", "reservation", "preparation", "receipt", "finalized"])
def test_short_writes_never_publish(backend, kind):
    m.EvidenceStore(backend, initialize=True)
    suffix = kind if kind in ("claim", "gate") else kind + ".stage"
    trip = TripBackend(backend, m, "write", "r-native-one." + suffix, short=True)
    rejected(lambda: cycle(m, m.EvidenceStore(trip)), "SHORT_WRITE")
    assert trip.fired and "r-native-one.claim" in backend.files
    assert "r-native-one." + kind not in backend.files or kind in ("claim", "gate")


@pytest.mark.parametrize("kind", ["reservation", "preparation", "receipt", "finalized"])
@pytest.mark.parametrize("damage", [b"", b"partial", b"garbage\r\n"])
def test_staged_crash_artifacts_never_count_as_published(store, backend, kind, damage):
    raw = records(m)
    if kind != "reservation":
        store.reserve("native-one", "reservation", raw["reservation"])
    if kind in ("receipt", "finalized"):
        store.publish("native-one", "preparation", raw["preparation"])
    if kind == "finalized":
        store.publish("native-one", "receipt", raw["receipt"])
    if kind == "reservation":
        backend.files["r-native-one.claim"] = b"partial"
    backend.files["r-native-one." + kind + ".stage"] = damage
    reopened = m.EvidenceStore(backend)
    rejected(lambda: reopened.reserve("native-one", "reservation", raw["reservation"]), "COLLISION")
    rejected(lambda: reopened.read_finalized("native-one"), "MISSING")
    if kind != "reservation":
        rejected(lambda: reopened.finalize_receipt("native-one", m.sha256(raw["receipt"])), "REQUEST_QUARANTINED")


@pytest.mark.parametrize("stage", m.KINDS)
@pytest.mark.parametrize("field", m.FIELDS)
@pytest.mark.parametrize("damage", ["missing", "duplicate", "order"])
def test_complete_schema_inventory_is_strict(stage, field, damage):
    body = records(m)[stage]
    lines = body[:-2].split(b"\r\n")
    n = m.FIELDS.index(field)
    if damage == "missing":
        lines.pop(n)
    elif damage == "duplicate":
        lines.insert(n, lines[n])
    else:
        other = (n + 1) % len(lines)
        lines[n], lines[other] = lines[other], lines[n]
    rejected(lambda: m.validate_record(b"\r\n".join(lines) + b"\r\n", "native-one", stage), "INVALID_RECORD")


@pytest.mark.parametrize("body", [b"", b"x" * 16385, b"schema=full\r\n", b"handoff_kind=single_candidate_proposal\r\n",
                                    b"verification_status=VALUE_CONSISTENT_NOT_AUTHORIZED\r\n",
                                    b"review_status=SOURCE_REVIEWABLE_NOT_AUTHORIZED\r\n", None, "text", bytearray(b"x")])
def test_non_h3_text_and_nonbytes_rejected_without_io(store, backend, body):
    before = dict(backend.files)
    rejected(lambda: store.reserve("native-one", "reservation", body), "INVALID_RECORD")
    assert backend.files == before


@pytest.mark.parametrize("damage", ["lf", "bare-cr", "bom", "nul", "unicode", "truncated", "unknown", "blank", "value-too-long"])
def test_framing_is_canonical(damage):
    body = records(m)["receipt"]
    variants = {"lf": body.replace(b"\r\n", b"\n"), "bare-cr": body + b"\r", "bom": b"\xef\xbb\xbf" + body,
                "nul": body.replace(b"CONFIRMED", b"CON\x00FIRMED"), "unicode": body.replace(b"h3_single", b"h3_\xc3\xa9"),
                "truncated": body[:-1], "unknown": body + b"approved=true\r\n", "blank": body + b"\r\n",
                "value-too-long": change(body, "failure_class", "x" * 513)}
    rejected(lambda: m.validate_record(variants[damage], "native-one", "receipt"))


@pytest.mark.parametrize("request_id", ["", "A", "a-", "a" * 65, "../x", "a/b", "a\\b", "a:b", "a.", "a ",
                                    ".", "..", "é", "a\x00", "a\r\n", "1a", "a_b", "CON", "nul", "aux", "prn",
                                    "con", "com1", "lpt9", "conin$", "C:\\x", "\\\\?\\C:\\x", "\\\\server\\x"])
def test_aliases_and_unsafe_request_paths_never_touch_backend(store, backend, request_id):
    before = list(backend.events)
    rejected(lambda: store.reserve(request_id, "reservation", records(m)["reservation"]), "INVALID_REQUEST_ID")
    assert backend.events == before


@pytest.mark.parametrize("field,value", [
    ("schema", "h3_single_write_receipt_v2"), ("source_kind", "full"), ("environment", "production"),
    ("request_id", "other"), ("action", "single_float32_restore_once"), ("approval_sha256", "A" * 64),
    ("sources_sha256", "nil"), ("process_sha256", "0" * 63), ("scope_sha256", "x" * 64),
    ("candidate_address", "0x0001"), ("candidate_address", "0x20000000000000"), ("candidate_address", "0xabc"),
    ("current_float", "100.0"), ("current_float", "100.00000001"), ("target_float", "2e2"),
    ("current_pattern", "0x7F800000"), ("target_pattern", "0x7FC00000"),
    ("issued_utc", "2026-02-29T12:00:00Z"), ("expires_utc", "2026-06-01T12:02:01Z"),
    ("last_checked_utc", "2026-06-01T12:02:00Z"), ("last_checked_utc", "1969-06-01T12:00:01Z"),
    ("max_elapsed_ms", "0"), ("max_elapsed_ms", "05000"), ("last_checked_monotonic_ms", "9007199254740992"),
    ("reservation_sha256", "nil"), ("preparation_sha256", "nil"), ("state", "UNCONFIRMED"),
    ("attempted", "false"), ("api_result", "false"), ("api_ok", "false"), ("readback_ok", "false"),
    ("execution_success", "false"), ("failure_class", "readback_mismatch"),
])
def test_promoted_or_malformed_receipts_rejected(field, value):
    rejected(lambda: m.validate_record(change(records(m)["receipt"], field, value), "native-one", "receipt"))


@pytest.mark.parametrize("action", ["write", "restore"])
@pytest.mark.parametrize("missing_prep", [False, True])
def test_uncertain_and_prewrite_rejected_receipts_are_storable_but_never_finalized(store, action, missing_prep):
    raw = records(m, action=action, uncertain=True, no_preparation=missing_prep)
    store.reserve("native-one", "reservation", raw["reservation"])
    if not missing_prep:
        store.publish("native-one", "preparation", raw["preparation"])
    store.publish("native-one", "receipt", raw["receipt"])
    assert store.read_record("native-one", "receipt") == raw["receipt"]
    rejected(lambda: store.finalize_receipt("native-one", m.sha256(raw["receipt"])), "NOT_CONFIRMED")
    rejected(lambda: store.publish("native-one", "preparation", raw["preparation"]), "STAGE_ORDER")


@pytest.mark.parametrize("field", m.FIELDS[1:17])
def test_cross_record_binding_cannot_be_swapped(store, field):
    raw = records(m)
    store.reserve("native-one", "reservation", raw["reservation"])
    f = m.parse(raw["preparation"])
    f[field] = "other" if field != "action" else "single_float32_restore_once"
    rejected(lambda: store.publish("native-one", "preparation", m.encode(m.FIELDS, f)))


@pytest.mark.parametrize("field,value", [("reservation_sha256", "0" * 64), ("last_checked_monotonic_ms", "999"),
                                       ("last_checked_monotonic_ms", "6001"), ("last_checked_utc", "2026-06-01T12:00:00Z"),
                                       ("last_checked_utc", "2026-06-01T12:00:03Z")])
def test_hash_and_chronology_links_are_checked(store, field, value):
    raw = records(m)
    store.reserve("native-one", "reservation", raw["reservation"])
    rejected(lambda: store.publish("native-one", "preparation", change(raw["preparation"], field, value)), "CHAIN_MISMATCH", "CHAIN_TIME")


@pytest.mark.parametrize("artifact", ["claim", "reservation", "preparation", "receipt", "finalized"])
@pytest.mark.parametrize("damage", ["delete", "truncate", "corrupt", "wrong-id"])
def test_finalized_reads_revalidate_every_predecessor(store, backend, artifact, damage):
    cycle(m, store)
    name = "r-native-one." + artifact
    if damage == "delete":
        del backend.files[name]
    elif damage == "truncate":
        backend.files[name] = backend.files[name][:-1]
    elif damage == "wrong-id":
        backend.files[name] = backend.files[name].replace(b"native-one", b"native-two")
    else:
        backend.files[name] = b"corrupt"
    rejected(lambda: m.EvidenceStore(backend).read_finalized("native-one"))


def test_unfinalized_receipt_is_insufficient(store):
    raw = cycle(m, store, through="receipt")
    assert store.read_record("native-one", "receipt") == raw["receipt"]
    rejected(lambda: store.read_finalized("native-one"), "MISSING")
    rejected(lambda: store.finalize_receipt("native-one", "0" * 64), "CHAIN_MISMATCH")


def test_crash_after_finalized_rename_keeps_verifiable_chain(store, backend):
    cycle(m, store)
    # A crashed process loses its Python state; no persistent bytes are removed.
    assert m.EvidenceStore(backend).read_finalized("native-one") == records(m)["receipt"]
    rejected(lambda: m.EvidenceStore(backend).reserve("native-one", "reservation", records(m)["reservation"]), "COLLISION")


@pytest.mark.parametrize("attempt", ["reservation", "preparation", "receipt", "finalized"])
def test_immutable_bytes_never_replaced(store, backend, attempt):
    raw = cycle(m, store)
    before = dict(backend.files)
    calls = {"reservation": lambda: store.reserve("native-one", "reservation", raw["reservation"]),
             "preparation": lambda: store.publish("native-one", "preparation", raw["preparation"]),
             "receipt": lambda: store.publish("native-one", "receipt", raw["receipt"]),
             "finalized": lambda: store.finalize_receipt("native-one", m.sha256(raw["receipt"]))}
    rejected(calls[attempt], "COLLISION", "STAGE_ORDER")
    assert all(backend.files[k] == v for k, v in before.items())


def test_simulated_independent_process_contention_and_cross_action_namespace(store, backend):
    # Threads stand in for separate interpreters sharing an atomic fake FS.
    barrier = threading.Barrier(8)
    def contender(n):
        instance = m.EvidenceStore(backend)
        raw = records(m, action="write" if n % 2 else "restore")
        barrier.wait(timeout=5)
        try:
            return instance.reserve("native-one", "reservation", raw["reservation"])
        except m.StoreError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(contender, range(8)))
    assert results.count(True) == 1 and results.count("COLLISION") == 7
    rejected(lambda: m.EvidenceStore(backend).reserve("native-one", "reservation", records(m)["reservation"]), "COLLISION")


def test_transition_lock_blocks_concurrent_stage_changes(store, backend):
    raw = records(m)
    store.reserve("native-one", "reservation", raw["reservation"])
    with backend.guard("r-native-one.gate"):
        rejected(lambda: m.EvidenceStore(backend).publish("native-one", "preparation", raw["preparation"]), "BUSY")
    assert store.publish("native-one", "preparation", raw["preparation"])


@pytest.mark.parametrize("state", ["missing", "different-root", "corrupt", "preexisting", "quarantine"])
def test_reopen_cannot_silently_create_namespace(backend, state):
    if state == "preexisting":
        backend.files["untrusted"] = b"x"
        rejected(lambda: m.EvidenceStore(backend, initialize=True), "ROOT_NOT_FRESH")
        return
    if state != "missing":
        m.EvidenceStore(backend, initialize=True)
    if state == "different-root":
        backend.identity = "different"
    if state == "corrupt":
        backend.files["namespace"] = b"corrupt"
    if state == "quarantine":
        backend.files["quarantine"] = b""
    before = dict(backend.files)
    rejected(lambda: m.EvidenceStore(backend))
    assert backend.files == before


@pytest.mark.parametrize("code", ["ROOT_TRUST_UNPROVEN", "ROOT_IDENTITY_MISMATCH", "REPARSE_OR_TYPE_UNSAFE", "NATIVE_IO_UNCERTAIN"])
def test_root_failures_during_operation_poison_live_object(store, backend, code):
    backend.root_error = code
    rejected(lambda: store.reserve("native-one", "reservation", records(m)["reservation"]), code)
    assert store.poisoned
    backend.root_error = None
    rejected(lambda: store.reserve("native-one", "reservation", records(m)["reservation"]), "NAMESPACE_QUARANTINED")


@pytest.mark.parametrize("path", ["relative", "C:relative", "c:\\test", "C:/test", "C:\\test\\", "C:\\a\\..\\b",
                                 "C:\\a\\.\\b", "C:\\con", "C:\\test:stream", "C:\\a ", "C:\\a.", "C:\\a~1",
                                 "C:\\é", "\\\\?\\C:\\test", "\\\\.\\C:\\test", "\\\\server\\share", "C:\\a\\\\b"])
def test_unsafe_native_roots_rejected_before_api(path):
    class Never:
        def __getattr__(self, _):
            pytest.fail("native boundary was touched")
    rejected(lambda: m.WindowsBackend(path, approved_test_root=True, api=Never()), "UNSAFE_ROOT_PATH")


class DirectoryAPI:
    """Simulates Win32 root handles including a handle larger than DWORD."""
    def __init__(self, fault=None):
        self.fault, self.handles, self.closed = fault, {}, []
        self.next_handle = 2**48
        self.filesystem = "NTFS"

    def open_directory(self, path):
        if self.fault == "access" and path == "C:\\approved":
            raise m.StoreError("ROOT_TRUST_UNPROVEN", api="CreateFileW", component=path, winerror=5)
        self.next_handle += 1
        self.handles[self.next_handle] = path
        return self.next_handle

    def inspect(self, h, path, *, directory):
        assert h > 2**32 and self.handles[h] == path and directory
        if self.fault == "reparse" and path == "C:\\approved":
            raise m.StoreError("REPARSE_OR_TYPE_UNSAFE")
        return {"identity": "id-" + path + ("-changed" if self.fault == "changed" else "")}

    def close(self, h):
        self.closed.append(h)
        del self.handles[h]

    def volume(self, h, drive):
        return {"filesystem": self.filesystem, "flags": 8, "drive_type": 3}


@pytest.mark.parametrize("fault", ["access", "reparse", "wrong-identity", "fat", "changed"])
def test_native_root_boundary_simulation_failures_release_all_pins(fault):
    api = DirectoryAPI(fault)
    if fault == "fat":
        api.filesystem = "FAT32"
    if fault == "changed":
        api.fault = None
        backend = m.WindowsBackend("C:\\approved", approved_test_root=True, api=api)
        api.fault = "changed"
        rejected(backend.check, "ROOT_IDENTITY_MISMATCH")
        backend.shutdown()
    else:
        error = rejected(lambda: m.WindowsBackend("C:\\approved", approved_test_root=True, api=api,
                         expected_identity="wrong" if fault == "wrong-identity" else None))
        if fault == "access":
            assert error.winerror == 5 and error.component == "C:\\approved"
    assert not api.handles


def test_unreadable_ancestor_metadata_is_root_trust_unproven():
    api = DirectoryAPI()
    def denied(handle, path, *, directory):
        raise m.StoreError("NATIVE_IO_UNCERTAIN", api="GetFileInformationByHandleEx", winerror=5)
    api.inspect = denied
    error = rejected(lambda: m.WindowsBackend("C:\\approved", approved_test_root=True, api=api), "ROOT_TRUST_UNPROVEN")
    assert error.component == "C:\\" and error.winerror == 5 and not api.handles


def test_default_inactive_constructor_and_pointer_width(monkeypatch):
    rejected(lambda: m.WindowsBackend("C:\\approved"), "TEST_BOOTSTRAP_REQUIRED")
    class Function:
        pass
    class DLL:
        def __init__(self):
            self.functions = {}
        def __getattr__(self, key):
            return self.functions.setdefault(key, Function())
    fake = DLL()
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, **kwargs: fake)
    api = m.Win32()
    assert api.k.CreateFileW.restype is ctypes.wintypes.HANDLE
    assert ctypes.sizeof(api.k.CreateFileW.restype) == struct.calcsize("P")
    assert ctypes.sizeof(api.FileID) == 24 and ctypes.sizeof(api.Info) == 52
    assert len(api.k.CreateFileW.argtypes) == 7 and len(api.k.GetVolumeInformationByHandleW.argtypes) == 8


def test_import_has_no_native_file_process_or_dispatch_side_effects(monkeypatch):
    import builtins
    import subprocess
    source = Path(m.__file__).read_bytes()
    code = compile(source, m.__file__, "exec")
    def forbidden(*args, **kwargs):
        pytest.fail("import attempted runtime IO")
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(ctypes, "WinDLL", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    namespace = {"__name__": "inactive_h3_import"}
    exec(code, namespace)
    assert "EvidenceStore" in namespace and "backend" not in namespace


class FileAPI(DirectoryAPI):
    """Exercise WindowsBackend orchestration without opening a Windows path."""
    def __init__(self):
        super().__init__()
        self.fs, self.read_handles, self.file_names = MemoryFS(), {}, {}
        self.mismatch, self.read_count = False, 0

    def create_new(self, path):
        h = self.fs.create_new(path.rsplit("\\", 1)[-1])
        self.file_names[h] = path
        return h

    def open_read(self, path):
        self.next_handle += 1
        name = path.rsplit("\\", 1)[-1]
        self.read_handles[self.next_handle] = self.fs.read(name)
        self.file_names[self.next_handle] = path
        return self.next_handle

    open_gate = open_read

    def inspect(self, h, path, *, directory):
        if directory:
            return super().inspect(h, path, directory=True)
        assert self.file_names[h] == path
        name = path.rsplit("\\", 1)[-1]
        size = len(self.fs.files[name])
        return {"identity": "file-" + name, "size": size, "written": self.read_count if self.mismatch else 0,
                "attributes": 128, "links": 1}

    def read(self, h, limit):
        self.read_count += 1
        return self.read_handles[h][:limit]

    def write(self, h, body):
        return self.fs.write(h, body)

    def flush(self, h):
        self.fs.flush(h)

    def close(self, h):
        if h in self.read_handles:
            del self.read_handles[h]
            del self.file_names[h]
        elif h in self.fs.handles:
            self.fs.close(h)
            del self.file_names[h]
        else:
            super().close(h)

    def names(self, path):
        return self.fs.names()

    def move_new(self, source, target):
        self.fs.move_new(source.rsplit("\\", 1)[-1], target.rsplit("\\", 1)[-1])


def test_complete_windows_backend_orchestration_using_simulated_native_boundary():
    api = FileAPI()
    with m.WindowsBackend("C:\\approved", approved_test_root=True, api=api) as backend:
        raw = cycle(m, m.EvidenceStore(backend, initialize=True))
        assert m.EvidenceStore(backend).read_finalized("native-one") == raw["receipt"]
    assert not api.handles and not api.fs.handles and not api.read_handles


@pytest.mark.parametrize("fault", ["metadata-drift", "oversize", "truncated-read"])
def test_native_read_checks_size_metadata_and_closes_handles(fault):
    api = FileAPI()
    api.fs.files["probe"] = b"abc"
    with m.WindowsBackend("C:\\approved", approved_test_root=True, api=api) as backend:
        if fault == "metadata-drift":
            api.mismatch = True
        elif fault == "oversize":
            api.fs.files["probe"] = b"x" * (m.MAX_RECORD + 1)
        else:
            api.read = lambda h, limit: b"a"
        rejected(lambda: backend.read("probe"), "READBACK_MISMATCH", "RECORD_TOO_LARGE")
        assert not api.read_handles


@pytest.mark.parametrize("name", ["../x", "a\\b", "a:b", "NUL", "nul", "x.", "x ", "a" * 111, "é"])
def test_backend_basenames_are_strict(name):
    api = FileAPI()
    with m.WindowsBackend("C:\\approved", approved_test_root=True, api=api) as backend:
        rejected(lambda: backend.create_new(name), "UNSAFE_CHILD")
    assert not api.fs.files


@pytest.mark.parametrize("operation,error,expected", [
    ("create", 80, "COLLISION"), ("create", 183, "COLLISION"), ("create", 5, "NATIVE_IO_UNCERTAIN"),
    ("read", 2, "MISSING"), ("read", 3, "MISSING"), ("read", 32, "NATIVE_IO_UNCERTAIN"),
    ("gate", 32, "BUSY"), ("directory", 5, "ROOT_TRUST_UNPROVEN"),
    ("directory", 32, "ROOT_TRUST_UNPROVEN"),
])
def test_exact_native_creation_flags_error_codes_and_pointer_return(monkeypatch, operation, error, expected):
    class Function:
        def __call__(self, *args):
            self.args = args
            ctypes.set_last_error(error)
            return ctypes.c_void_p(-1).value
    class DLL:
        def __getattr__(self, name):
            function = Function()
            setattr(self, name, function)
            return function
    fake = DLL()
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: fake)
    api = m.Win32()
    fn = {"create": api.create_new, "read": api.open_read, "gate": api.open_gate,
          "directory": api.open_directory}[operation]
    failure = rejected(lambda: fn("C:\\approved"), expected)
    assert failure.winerror == error and failure.component == "C:\\approved"
    args = fake.CreateFileW.args
    assert args[3] is args[6] is None and args[4] == (1 if operation == "create" else 3)
    assert args[5] & 0x00200000  # OPEN_REPARSE_POINT, never follow a link.
    assert args[2] == (0 if operation in ("create", "gate") else 1)
    assert args[5] & 0x80000000 if operation == "create" else True


def test_probe_requires_all_enumerated_native_checks():
    result = {name: {"status": "PASS"} for name in probe.REQUIRED_NATIVE}
    result.update({name: {"status": "UNQUALIFIED"} for name in probe.UNQUALIFIED})
    assert len(probe.REQUIRED_NATIVE) == 34
    probe.qualify_results(result)
    for name in probe.REQUIRED_NATIVE:
        for status in ("FAIL", "UNQUALIFIED", "SKIP"):
            altered = dict(result)
            altered[name] = {"status": status}
            with pytest.raises(AssertionError):
                probe.qualify_results(altered)
        altered = dict(result)
        del altered[name]
        with pytest.raises(AssertionError):
            probe.qualify_results(altered)
    for name in probe.UNQUALIFIED:
        altered = dict(result)
        altered[name] = {"status": "PASS"}
        with pytest.raises(AssertionError):
            probe.qualify_results(altered)


def test_probe_error_sanitization_keeps_exact_code_without_private_path():
    private = "C:\\private-user\\secret"
    error = m.StoreError("ROOT_TRUST_UNPROVEN", api="CreateFileW", component=private, winerror=5)
    public = probe.sanitized_error(error, m, ("C:\\", private))
    assert public["winerror"] == 5 and public["component_depth"] == 1
    assert public["component_sha256"] == m.sha256(private.encode())
    assert private not in str(public)
    assert probe.sanitized_error(ValueError(private))["code"] == "UNHANDLED_EXCEPTION"


def test_probe_rejects_optimized_python_before_loading_or_io(monkeypatch):
    class Flags:
        optimize = 1
    monkeypatch.setattr(probe.sys, "flags", Flags())
    with pytest.raises(AssertionError, match="OPTIMIZED_PROBE_FORBIDDEN"):
        probe.main([])


@pytest.mark.parametrize("path", ["D:\\armedforces.io-v2", "D:\\armedforces.io-v2\\tests", "D:\\H1_evidence",
                                 "D:\\h1_EVIDENCE\\private", "C:\\", "C:\\Windows\\temp", "C:\\Program Files\\temp"])
def test_probe_rejects_protected_roots_before_any_io(monkeypatch, path):
    monkeypatch.setenv("SystemRoot", "C:\\Windows")
    monkeypatch.setenv("ProgramFiles", "C:\\Program Files")
    with pytest.raises(AssertionError, match="PROTECTED_SCRATCH_PARENT"):
        probe.validate_scratch_parent(m, path, Path(r"D:\armedforces.io-v2"), "0" * 32)


def test_probe_checks_full_planned_path_before_creating_root():
    probe.validate_scratch_parent(m, "C:\\approved", Path(r"D:\armedforces.io-v2"), "0" * 32)
    rejected(lambda: probe.validate_scratch_parent(m, "C:\\" + "a" * 79 + "\\" + "b" * 25,
              Path(r"D:\armedforces.io-v2"), "0" * 32), "UNSAFE_ROOT_PATH")


@pytest.mark.parametrize("bits", [0, 0x80000000, 1, 0x80000001, 0x007FFFFF, 0x00800000,
                                  0x3DCCCCCD, 0xC1480000, 0x42C80000, 0x7F7FFFFF, 0xFF7FFFFF])
def test_a2_finite_float32_canonical_boundaries(bits):
    body = records(m)["reservation"]
    body = change(body, "current_pattern", f"0x{bits:08X}")
    body = change(body, "current_float", format(struct.unpack("<f", struct.pack("<I", bits))[0], ".17g"))
    assert m.validate_record(body, "native-one", "reservation")["current_pattern"] == f"0x{bits:08X}"


# Actual A2 producers are invoked only in the existing synthetic Lua fixture.
# Its host debug.traceback remains intact; no production or native adapter runs.
from test_handoff_candidate_verify import evidence_sets  # noqa: E402,F401
from test_handoff_write_restore_protocol import Simulation, upstream  # noqa: E402,F401


@pytest.mark.parametrize("action", ["write", "restore"])
@pytest.mark.parametrize("outcome", ["confirmed", "api-false", "prewrite-rejected"])
def test_actual_published_a2_bytes_are_accepted_without_wire_translation(store, upstream, action, outcome):
    sim = Simulation(upstream)
    approval = sim.restore_ready() if action == "restore" else sim.issue()
    if outcome == "api-false":
        sim.write_behavior = "false"
    elif outcome == "prewrite-rejected":
        sim.read_faults[1] = None
    result = sim.run(action, approval)
    request = "write-one" if action == "write" else "restore-one"
    raw = {kind: sim.records[(request, kind)].encode("ascii") for kind in m.KINDS if (request, kind) in sim.records}
    assert store.reserve(request, "reservation", raw["reservation"])
    for kind in ("preparation", "receipt"):
        if kind in raw:
            assert store.publish(request, kind, raw[kind])
    if outcome == "confirmed":
        assert result.execution_success and store.finalize_receipt(request, m.sha256(raw["receipt"]))
        assert store.read_finalized(request) == raw["receipt"]
    else:
        assert not result.execution_success
        rejected(lambda: store.finalize_receipt(request, m.sha256(raw["receipt"])), "NOT_CONFIRMED")
    assert sim.lua.eval("type(debug.traceback)") == "function"
    assert not sim.lua.globals().forbidden_calls
