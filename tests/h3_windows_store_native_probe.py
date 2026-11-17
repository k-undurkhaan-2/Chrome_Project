"""Deliberate operator-only Windows storage check; never collected by pytest.

No target process, CE, approval, arm or production configuration is accessed.
Run --help first. Parent/identity approval is explicit; no automatic fallback.
"""

import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time
import uuid
import zipfile
import io


SOURCE_PATHS = (
    "src/armedforces_tool/h3_windows_durable_store.py",
    "tests/test_h3_windows_durable_store.py",
    "tests/h3_windows_store_native_probe.py",
    "docs/architecture/h3_windows_durable_store_contract.md",
)
RACE_WORKERS = 4
CHILD_TIMEOUT = 30
CRASH_EXIT = 73
UNQUALIFIED = frozenset(("power_loss_durability", "adversarial_external_concurrent_modification",
                        "filesystem_power_fail_metadata_ordering"))
REQUIRED_NATIVE = frozenset((
    "native_junction_root_rejected", "native_junction_ancestor_rejected", "native_hardlink_rejected",
    "reservation_no_replace", "preparation_no_replace", "receipt_no_replace", "finalization_no_replace",
    "immutable_exact_chain", "native_rename_no_replace", "cross_process_same_id",
    "restart_readback_and_replay", "partial_claim_quarantine", "uncertain_not_finalized",
    "mixed_source_rejected", "malformed_finalization_quarantine", "corrupt_predecessor_quarantine",
    "root_path_pin_and_rechecks", "source_integrity",
    *("injected-" + method + "-" + target for method, target in (
        ("write", "receipt-stage"), ("flush", "receipt-stage"), ("close", "receipt-stage"),
        ("read", "receipt-stage"), ("move", "receipt"), ("read", "receipt"))),
    *(f"process_crash_{n}" for n in range(10)),
))


def qualify_results(results):
    if set(results) != REQUIRED_NATIVE | UNQUALIFIED:
        raise AssertionError("INCOMPLETE_NATIVE_REQUIREMENTS")
    if any(results[k]["status"] != "PASS" for k in REQUIRED_NATIVE):
        raise AssertionError("NATIVE_REQUIREMENT_FAILED")
    if any(results[k]["status"] != "UNQUALIFIED" for k in UNQUALIFIED):
        raise AssertionError("UNSUPPORTED_DURABILITY_CLAIM")


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("ascii")


def hash_bytes(body):
    return hashlib.sha256(body).hexdigest()


def source_manifest(repo):
    return {name: {"bytes": len(body), "sha256": hash_bytes(body)}
            for name in SOURCE_PATHS for body in [(repo / name).read_bytes()]}


def load_store(repo):
    spec = importlib.util.spec_from_file_location("h3_probe_store", repo / SOURCE_PATHS[0])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_scratch_parent(module, path, repo, nonce):
    module.local_root(path)
    denied = [str(repo), r"D:\H1_evidence"]
    denied.extend(os.environ[k] for k in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)") if os.environ.get(k))
    candidate = path.casefold().rstrip("\\")
    if len(candidate) <= 2 or any(candidate == p.casefold().rstrip("\\") or
            candidate.startswith(p.casefold().rstrip("\\") + "\\") for p in denied):
        raise AssertionError("PROTECTED_SCRATCH_PARENT")
    # Validate the longest planned path before creating even the fresh child.
    module.local_root(path + "\\h3-native-" + nonce + "\\injected-close-receipt-stage")


def records(module, request="native-one", action="write", *, uncertain=False, no_preparation=False):
    """Public fabricated A2 records, never actual approval or memory evidence."""
    f = dict(zip(module.FIELDS, ["nil"] * len(module.FIELDS), strict=True))
    f.update(schema="h3_operation_reservation_v1", source_kind="h3_single", environment="synthetic_only",
             request_id=request, action=f"single_float32_{action}_once", approval_sha256="1" * 64,
             sources_sha256="2" * 64, process_sha256="3" * 64, scope_sha256="4" * 64,
             candidate_address="0x1234", current_float="100", current_pattern="0x42C80000",
             target_float="200", target_pattern="0x43480000", issued_utc="2026-06-01T12:00:00Z",
             expires_utc="2026-06-01T12:02:00Z", max_elapsed_ms="5000", state="RESERVED",
             attempted="false", api_result="not_called", api_ok="false", readback_ok="false",
             execution_success="false", last_checked_utc="2026-06-01T12:00:01Z", last_checked_monotonic_ms="1000")
    if action == "restore":
        f.update(current_float="200", current_pattern="0x43480000", target_float="100", target_pattern="0x42C80000")
    reservation = module.encode(module.FIELDS, f)
    f.update(schema=f"h3_single_{action}_preparation_v1", state="PREPARED", reservation_sha256=hash_bytes(reservation))
    preparation = module.encode(module.FIELDS, f)
    f.update(schema=f"h3_single_{action}_receipt_v1", state="CONFIRMED", preparation_sha256=hash_bytes(preparation),
             attempted="true", api_result="true", api_ok="true", readback_ok="true", execution_success="true")
    if uncertain:
        f.update(state="UNCONFIRMED", api_result="false", api_ok="false", execution_success="false",
                 failure_class="mutation_api_false")
    if no_preparation:
        f.update(state="UNCONFIRMED", preparation_sha256="nil", attempted="false", api_result="not_called",
                 api_ok="false", readback_ok="false", execution_success="false", failure_class="initial_value_mismatch")
    return {"reservation": reservation, "preparation": preparation, "receipt": module.encode(module.FIELDS, f)}


def cycle(module, store, request="native-one", action="write", *, through="finalized"):
    raw = records(module, request, action)
    assert store.reserve(request, "reservation", raw["reservation"]) is True
    if through == "reservation":
        return raw
    for kind in ("preparation", "receipt"):
        assert store.publish(request, kind, raw[kind]) is True
        if through == kind:
            return raw
    assert store.finalize_receipt(request, hash_bytes(raw["receipt"])) is True
    assert store.read_finalized(request) == raw["receipt"]
    return raw


class TripBackend:
    """Probe/test-only deterministic interruption around actual backend calls.

    Crash mode calls os._exit in the probe-owned child only. Failure mode raises
    after the native primitive completed: acknowledgement uncertainty, not an
    assertion that Windows actually failed the primitive.
    """

    def __init__(self, backend, module, method, name, *, crash=False, short=False):
        self.backend, self.module, self.method, self.name = backend, module, method, name
        self.crash, self.short, self.fired = crash, short, False
        self.handles = {}

    def __getattr__(self, key):
        return getattr(self.backend, key)

    def _trip(self, method, name):
        if not self.fired and (method, name) == (self.method, self.name):
            self.fired = True
            if self.crash:
                os._exit(CRASH_EXIT)
            raise self.module.StoreError("INJECTED_IO_UNCERTAIN", api=method)

    def create_new(self, name):
        h = self.backend.create_new(name)
        self.handles[h] = name
        try:
            self._trip("create", name)
        except self.module.StoreError:
            self.backend.close(h)
            raise
        return h

    def write(self, h, body):
        if self.short and not self.fired and self.handles[h] == self.name:
            self.fired = True
            return self.backend.write(h, body[:max(1, len(body) // 2)])
        count = self.backend.write(h, body)
        self._trip("write", self.handles[h])
        return count

    def flush(self, h):
        self.backend.flush(h)
        self._trip("flush", self.handles[h])

    def close(self, h):
        name = self.handles.pop(h)
        self.backend.close(h)
        self._trip("close", name)

    def read(self, name):
        body = self.backend.read(name)
        self._trip("read", name)
        return body

    def move_new(self, source, target):
        self.backend.move_new(source, target)
        self._trip("move", target)


def expect_error(module, function, allowed):
    try:
        function()
    except module.StoreError as error:
        assert error.code in allowed, error.code
        return {"status": "PASS", "rejection": error.code, "winerror": error.winerror}
    raise AssertionError("unexpected operation success")


def emit_new(backend, name, body):
    """Report/signal writes stay inside a verified root and never replace files."""
    h = backend.create_new(name)
    try:
        assert backend.write(h, body) == len(body)
        backend.flush(h)
    finally:
        backend.close(h)
    assert backend.read(name) == body


def reparse_and_link_checks(module, bundle):
    """Owned NTFS fixtures only; never require symlink privilege or elevation."""
    target = bundle.create_child("junction-target")
    alias = bundle.create_child("junction-alias")
    api, c, w = bundle.api, bundle.api.c, bundle.api.w
    substitute, display = ("\\??\\" + target).encode("utf-16-le"), target.encode("utf-16-le")
    path_buffer = substitute + b"\0\0" + display + b"\0\0"
    payload = (struct.pack("<IHHHHHH", 0xA0000003, 8 + len(path_buffer), 0,
                           0, len(substitute), len(substitute) + 2, len(display)) + path_buffer)
    ioctl = api.k.DeviceIoControl
    ioctl.argtypes = [w.HANDLE, w.DWORD, c.c_void_p, w.DWORD, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p]
    ioctl.restype = w.BOOL
    bundle.check()
    h = api._open(alias, 0x40000000, 0, 3, 0x02200000)
    try:
        count, buffer = w.DWORD(), c.create_string_buffer(payload)
        if not ioctl(h, 0x900A4, buffer, len(payload), None, 0, c.byref(count), None):
            api._error("DeviceIoControl:FSCTL_SET_REPARSE_POINT", alias)
    finally:
        api.close(h)
    def open_unsafe(path):
        with module.WindowsBackend(path, approved_test_root=True):
            raise AssertionError("reparse root was accepted")
    reparse = expect_error(module, lambda: open_unsafe(alias), {"REPARSE_OR_TYPE_UNSAFE"})
    ancestor = expect_error(module, lambda: open_unsafe(alias + "\\descendant"), {"REPARSE_OR_TYPE_UNSAFE"})
    emit_new(bundle, "link-source", b"owned hardlink fixture\n")
    bundle.check()
    os.link(bundle.path("link-source"), bundle.path("link-alias"))
    bundle.check()
    hardlink = expect_error(module, lambda: bundle.read("link-alias"), {"HARDLINK_UNSAFE"})
    return {"native_junction_root_rejected": reparse, "native_junction_ancestor_rejected": ancestor,
            "native_hardlink_rejected": hardlink}


def sanitized_error(error, module=None, parts=()):
    result = {"type": type(error).__name__, "status": "FAIL"}
    if module is not None and isinstance(error, module.StoreError):
        result.update(code=error.code, api=error.api, winerror=error.winerror)
        if error.component:
            # Identify exact component without exporting a private ancestor name.
            result["component_sha256"] = hash_bytes(error.component.encode("utf-8"))
            result["component_depth"] = parts.index(error.component) if error.component in parts else None
    else:
        code = str(error) if isinstance(error, AssertionError) else ""
        result["code"] = code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,80}", code) else "UNHANDLED_EXCEPTION"
    return result


def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=["storage-native-only"], required=True)
    p.add_argument("--diagnostic", choices=["debug"], required=True)
    p.add_argument("--scratch-parent", help="Existing approved empty/dedicated parent; no production data.")
    p.add_argument("--approve-disposable-parent", action="store_true", help="Confirm test parent and runtime identity are explicitly approved.")
    p.add_argument("--expected-sid", help="Exact approved product/test Windows principal SID.")
    p.add_argument("--expected-snapshot", required=True, help="SHA-256 of canonical four-source manifest JSON.")
    p.add_argument("--expected-python-sha256", required=True, help="SHA-256 of the qualified sys.executable.")
    p.add_argument("--child", choices=["race", "restart", "crash"], help=argparse.SUPPRESS)
    for arg in ("root", "root-identity", "run-nonce", "worker", "trip-method", "trip-name"):
        p.add_argument("--" + arg, help=argparse.SUPPRESS)
    return p


def child_command(args, mode, root, identity, nonce, **extra):
    command = [sys.executable, "-I", "-B", "-S", str(Path(__file__).absolute()),
               "--mode", "storage-native-only", "--diagnostic", "debug", "--child", mode,
               "--root", root, "--root-identity", identity, "--run-nonce", nonce,
               "--expected-snapshot", args.expected_snapshot, "--expected-python-sha256", args.expected_python_sha256]
    for key, value in extra.items():
        command += ["--" + key.replace("_", "-"), value]
    return command


def spawn(command):
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        env.pop(key, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=env, creationflags=subprocess.CREATE_NO_WINDOW)


def collect(process, *, expected=0):
    try:
        stdout, stderr = process.communicate(timeout=CHILD_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()  # Only this probe-owned helper; never a process search.
        process.communicate(timeout=5)
        raise RuntimeError("OWNED_HELPER_TIMEOUT") from None
    assert process.returncode == expected and not stderr and len(stdout) <= 8192
    return {"exit_code": process.returncode, "stdout": stdout.decode("ascii"), "stderr": ""}


def child(args, module):
    assert args.root_identity and re.fullmatch(r"[0-9a-f]{32}", args.run_nonce or "")
    with module.WindowsBackend(args.root, approved_test_root=True, expected_identity=args.root_identity) as backend:
        assert backend.read("native-run") == (args.run_nonce + "\n" + args.expected_snapshot + "\n").encode("ascii")
        store = module.EvidenceStore(backend)
        if args.child == "race":
            assert args.worker in tuple(str(n) for n in range(RACE_WORKERS))
            emit_new(backend, "ready-" + args.worker, b"ready\n")
            deadline = time.monotonic() + 15
            while True:
                try:
                    assert backend.read("race-go") == b"go\n"
                    break
                except module.StoreError as error:
                    if error.code != "MISSING" or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.02)
            try:
                result = store.reserve("native-race", "reservation", records(module, "native-race")["reservation"])
                output = {"result": "WIN" if result is True else "FAIL"}
            except module.StoreError as error:
                assert error.code == "COLLISION"
                output = {"result": "COLLISION", "winerror": error.winerror}
        elif args.child == "restart":
            raw = records(module, "native-write")
            assert store.read_finalized("native-write") == raw["receipt"]
            output = expect_error(module, lambda: store.reserve("native-race", "reservation",
                                  records(module, "native-race")["reservation"]), {"COLLISION"})
            output["receipt_sha256"] = hash_bytes(raw["receipt"])
        else:
            trip = TripBackend(backend, module, args.trip_method, args.trip_name, crash=True)
            cycle(module, module.EvidenceStore(trip), "native-crash")
            raise AssertionError("crash checkpoint not reached")
        print(json.dumps(output, sort_keys=True))
    return 0


def native_checks(args, module, root, nonce, snapshot, expected_identity, evidence):
    results, race, integrity, transcripts = {}, {}, {}, []
    evidence.update({"native-results.json": results, "process-race.json": race,
                     "file-integrity.json": integrity, "controlled-transcripts.json": transcripts})
    with module.WindowsBackend(root, approved_test_root=True, expected_identity=expected_identity) as bundle:
        root_facts = {"status": "PASS", "root_identity": bundle.identity, "volume": bundle.volume,
                      "pinned_components": len(bundle.parts), "parent_path_sha256": hash_bytes(args.scratch_parent.encode("utf-8"))}
        evidence["root-capability.json"] = root_facts
        results.update(reparse_and_link_checks(module, bundle))

        @contextmanager
        def fresh(name):
            path = bundle.create_child(name)
            with module.WindowsBackend(path, approved_test_root=True) as backend:
                store = module.EvidenceStore(backend, initialize=True)
                emit_new(backend, "native-run", (nonce + "\n" + args.expected_snapshot + "\n").encode("ascii"))
                yield path, backend, store

        with fresh("main-store") as (path, backend, store):
            raw = cycle(module, store, "native-write")
            cycle(module, store, "native-restore", "restore")
            for kind in module.KINDS:
                assert store.read_record("native-write", kind) == raw[kind]
                integrity[kind] = {"bytes": len(raw[kind]), "sha256": hash_bytes(raw[kind])}
            for kind in ("claim", "gate", "finalized"):
                body = backend.read("r-native-write." + kind)
                integrity[kind] = {"bytes": len(body), "sha256": hash_bytes(body)}
            expected_final = store.read_finalized("native-write")
            for name, fn in (
                ("reservation_no_replace", lambda: store.reserve("native-write", "reservation", raw["reservation"])),
                ("preparation_no_replace", lambda: store.publish("native-write", "preparation", raw["preparation"])),
                ("receipt_no_replace", lambda: store.publish("native-write", "receipt", raw["receipt"])),
                ("finalization_no_replace", lambda: store.finalize_receipt("native-write", hash_bytes(raw["receipt"]))),
            ):
                results[name] = expect_error(module, fn, {"COLLISION", "STAGE_ORDER"})
            assert store.read_finalized("native-write") == expected_final
            results["immutable_exact_chain"] = {"status": "PASS"}
            # A direct native no-replace rename must retain both source/target.
            emit_new(backend, "rename-source", b"new\n")
            emit_new(backend, "rename-target", b"old\n")
            results["native_rename_no_replace"] = expect_error(module, lambda: backend.move_new("rename-source", "rename-target"), {"COLLISION"})
            assert backend.read("rename-source") == b"new\n" and backend.read("rename-target") == b"old\n"
            processes = []
            try:
                for n in range(RACE_WORKERS):
                    processes.append(spawn(child_command(args, "race", path, backend.identity, nonce, worker=str(n))))
                deadline = time.monotonic() + 20
                while True:
                    ready = sum("ready-" + str(n) in backend.names() for n in range(RACE_WORKERS))
                    if ready == RACE_WORKERS:
                        break
                    assert time.monotonic() < deadline and all(p.poll() is None for p in processes)
                    time.sleep(0.02)
                emit_new(backend, "race-go", b"go\n")
                observed = [collect(p) for p in processes]
            finally:
                for p in processes:
                    if p.poll() is None:
                        p.kill()
                        p.communicate(timeout=5)
            outcomes = [json.loads(r["stdout"]) for r in observed]
            assert sum(r["result"] == "WIN" for r in outcomes) == 1
            assert sum(r["result"] == "COLLISION" for r in outcomes) == RACE_WORKERS - 1
            race.update(status="PASS", workers=RACE_WORKERS, barrier="all-ready then race-go", outcomes=outcomes)
            results["cross_process_same_id"] = {"status": "PASS", "winners": 1, "rejected": RACE_WORKERS - 1}
            transcripts.extend(observed)
            identity = backend.identity
        # All main-store handles closed before a fresh process reopens it.
        restart = collect(spawn(child_command(args, "restart", path, identity, nonce)))
        transcripts.append(restart)
        assert json.loads(restart["stdout"])["receipt_sha256"] == hash_bytes(expected_final)
        results["restart_readback_and_replay"] = {"status": "PASS"}

        # Real native files plus injected acknowledgement failures, separate roots.
        for method, target in (("write", "receipt.stage"), ("flush", "receipt.stage"),
                               ("close", "receipt.stage"), ("read", "receipt.stage"),
                               ("move", "receipt"), ("read", "receipt")):
            key = "injected-" + method + "-" + target.replace(".", "-")
            with fresh(key) as (_, backend, _):
                trip = TripBackend(backend, module, method, "r-native-fault." + target)
                results[key] = expect_error(module, lambda: cycle(module, module.EvidenceStore(trip), "native-fault"), {"INJECTED_IO_UNCERTAIN"})
                assert trip.fired
                expect_error(module, lambda: module.EvidenceStore(backend), {"NAMESPACE_QUARANTINED"})
                results[key]["evidence_type"] = "native_files_with_injected_acknowledgement_failure"

        checkpoints = [("create", "claim"), ("create", "receipt.stage"), ("write", "receipt.stage"),
                       ("flush", "receipt.stage"), ("close", "receipt.stage"), ("read", "receipt.stage"),
                       ("move", "receipt"), ("read", "receipt"),
                       ("flush", "finalized.stage"), ("move", "finalized")]
        for number, (method, target) in enumerate(checkpoints):
            with fresh(f"crash-{number}") as (path, backend, _):
                identity = backend.identity
            result = collect(spawn(child_command(args, "crash", path, identity, nonce,
                             trip_method=method, trip_name="r-native-crash." + target)), expected=CRASH_EXIT)
            transcripts.append(result)
            with module.WindowsBackend(path, approved_test_root=True, expected_identity=identity) as backend:
                store = module.EvidenceStore(backend)
                expect_error(module, lambda: store.reserve("native-crash", "reservation",
                             records(module, "native-crash")["reservation"]), {"COLLISION"})
                if target == "finalized" and method == "move":
                    assert store.read_finalized("native-crash") == records(module, "native-crash")["receipt"]
                    outcome = "confirmed_chain_retrievable_after_lost_ack"
                else:
                    expect_error(module, lambda: store.read_finalized("native-crash"),
                                 {"MISSING", "REQUEST_QUARANTINED"})
                    outcome = "consumed_and_not_finalized"
                results[f"process_crash_{number}"] = {"status": "PASS", "method": method,
                                                      "artifact": target, "outcome": outcome, "exit_code": CRASH_EXIT}

        # Deliberately malformed files in dedicated disposable roots; no editing
        # of previously published records or production evidence.
        with fresh("corrupt-store") as (_, backend, _):
            emit_new(backend, "r-native-corrupt.claim", b"partial")
            store = module.EvidenceStore(backend)
            results["partial_claim_quarantine"] = expect_error(module, lambda: store.reserve("native-corrupt", "reservation",
                                                   records(module, "native-corrupt")["reservation"]), {"COLLISION"})
        with fresh("invalid-store") as (_, backend, store):
            raw = records(module, "native-invalid", uncertain=True)
            store.reserve("native-invalid", "reservation", raw["reservation"])
            store.publish("native-invalid", "preparation", raw["preparation"])
            store.publish("native-invalid", "receipt", raw["receipt"])
            results["uncertain_not_finalized"] = expect_error(module, lambda: store.finalize_receipt("native-invalid", hash_bytes(raw["receipt"])), {"NOT_CONFIRMED"})
            results["mixed_source_rejected"] = expect_error(module, lambda: store.publish("native-invalid", "receipt",
                                               raw["receipt"].replace(b"source_kind=h3_single", b"source_kind=full")), {"INVALID_RECORD"})
        with fresh("malformed-final-store") as (_, backend, store):
            cycle(module, store, "native-malformed", through="receipt")
            emit_new(backend, "r-native-malformed.finalized", b"h3-finalized-v1\r\ntruncated")
            results["malformed_finalization_quarantine"] = expect_error(module, lambda: store.read_finalized("native-malformed"), {"REQUEST_QUARANTINED"})
        with fresh("malformed-prep-store") as (_, backend, store):
            raw = records(module, "native-malformed")
            store.reserve("native-malformed", "reservation", raw["reservation"])
            emit_new(backend, "r-native-malformed.preparation", raw["preparation"][:-1])
            results["corrupt_predecessor_quarantine"] = expect_error(module, lambda: store.publish("native-malformed", "receipt", raw["receipt"]), {"INVALID_RECORD"})
        results["root_path_pin_and_rechecks"] = {"status": "PASS", "note": "All native file operations validated pinned ancestors, root, final paths and file identities."}
        results["power_loss_durability"] = {"status": "UNQUALIFIED"}
        results["adversarial_external_concurrent_modification"] = {"status": "UNQUALIFIED"}
        results["filesystem_power_fail_metadata_ordering"] = {"status": "UNQUALIFIED"}
        assert source_manifest(Path(__file__).resolve().parents[1]) == snapshot
        results["source_integrity"] = {"status": "PASS"}
        qualify_results(results)
        return bundle.identity


def main(argv=None):
    if sys.flags.optimize:
        raise AssertionError("OPTIMIZED_PROBE_FORBIDDEN")
    args = parser().parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    snapshot = source_manifest(repo)
    assert hash_bytes(json_bytes(snapshot)) == args.expected_snapshot, "SOURCE_SNAPSHOT_MISMATCH"
    assert sys.version_info[:3] == (3, 14, 3) and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
    assert hash_bytes(Path(sys.executable).read_bytes()) == args.expected_python_sha256, "PYTHON_MISMATCH"
    module = load_store(repo)
    if args.child:
        return child(args, module)
    assert os.name == "nt" and args.approve_disposable_parent and args.scratch_parent and args.expected_sid
    who = subprocess.run([str(Path(os.environ["SystemRoot"]) / "System32/whoami.exe"), "/user", "/fo", "csv", "/nh"],
                         capture_output=True, timeout=10, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    sid = re.search(rb"S-1-5-[0-9-]+", who.stdout)
    assert sid and sid.group().decode("ascii") == args.expected_sid, "PRINCIPAL_MISMATCH"
    assert b"codexsandbox" not in who.stdout.lower(), "SANDBOX_IDENTITY_NOT_QUALIFIED"
    nonce = uuid.uuid4().hex
    root, root_identity, output = None, None, {}
    try:
        validate_scratch_parent(module, args.scratch_parent, repo, nonce)
        with module.WindowsBackend(args.scratch_parent, approved_test_root=True) as parent:
            assert shutil.disk_usage(args.scratch_parent).free >= 64 * 1024 * 1024, "INSUFFICIENT_SPACE"
            root = parent.create_child("h3-native-" + nonce)
            with module.WindowsBackend(root, approved_test_root=True) as fresh_root:
                root_identity = fresh_root.identity
            # Keep parent pins through the complete native qualification.
            native_checks(args, module, root, nonce, snapshot, root_identity, output)
            status = "PASS_HANDOFF_H3_A3_T1_WINDOWS_NATIVE_STORE_QUALIFIED_LIMITED_SCOPE"
            with module.WindowsBackend(root, approved_test_root=True, expected_identity=root_identity) as bundle:
                manifest = {}
                for name, data in output.items():
                    body = json_bytes(data)
                    emit_new(bundle, name, body)
                    manifest[name] = {"bytes": len(body), "sha256": hash_bytes(body)}
                receipt = {"status": status, "mode": args.mode, "diagnostic": args.diagnostic,
                           "principal_sid": args.expected_sid, "windows": list(sys.getwindowsversion()),
                           "architecture": "x64" if sys.maxsize > 2**32 else "x86", "python": sys.version,
                           "python_sha256": args.expected_python_sha256, "snapshot_sha256": args.expected_snapshot,
                           "sources": snapshot, "root_identity": root_identity, "root_label": "h3-native-" + nonce,
                           "manifest": manifest, "native_memory_operations": 0,
                           "required_native_checks": len(REQUIRED_NATIVE), "passed_native_checks": len(REQUIRED_NATIVE),
                           "limits": {"race_workers": RACE_WORKERS, "child_timeout_seconds": CHILD_TIMEOUT,
                                      "record_bytes": module.MAX_RECORD, "power_loss_durability": "UNQUALIFIED",
                                      "adversarial_tampering": "UNQUALIFIED", "production_authority": False}}
                receipt_bytes = json_bytes(receipt)
                emit_new(bundle, "native-receipt.json", receipt_bytes)
                # Export only these sanitized reports, never source store records.
                memory = io.BytesIO()
                with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for name in (*manifest, "native-receipt.json"):
                        archive.writestr(name, bundle.read(name))
                payload = memory.getvalue()
                # Keep exported bundle within the same bounded record API.
                emit_new(bundle, "native-bundle.zip", payload)
        print(json.dumps({"status": status, "bundle": root + "\\native-bundle.zip",
                          "bundle_sha256": hash_bytes(payload), "receipt_sha256": hash_bytes(receipt_bytes)}, indent=2))
        return 0
    except Exception as error:
        try:
            parts = module.local_root(args.scratch_parent)
        except module.StoreError:
            parts = ()
        failure = sanitized_error(error, module, parts)
        # Never improvise another root or suppress a failed trust check. Console
        # is the fallback if no trusted report root was established.
        failure["status"] = "BLOCKED_HANDOFF_H3_A3_T1_" + failure["code"]
        failure.update(snapshot_sha256=args.expected_snapshot, native_memory_operations=0,
                       completed_results=output, remaining_tests="NOT_RUN_OR_INCOMPLETE")
        if root_identity is not None:
            try:
                with module.WindowsBackend(root, approved_test_root=True, expected_identity=root_identity) as safe:
                    # Separate name cannot overwrite any partial successful report.
                    emit_new(safe, "native-failure.json", json_bytes(failure))
                failure["failure_report"] = root + "\\native-failure.json"
            except module.StoreError as report_error:
                failure["failure_report_write"] = sanitized_error(report_error, module, parts)
        print(json.dumps(failure, indent=2))
        if isinstance(error, module.StoreError) and error.component:
            print("LOCAL_DIAGNOSTIC_COMPONENT=" + error.component, file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
    except Exception as error:
        early = sanitized_error(error)
        early["status"] = "BLOCKED_HANDOFF_H3_A3_T1_" + early["code"]
        print(json.dumps(early, indent=2))
        exit_code = 1
    raise SystemExit(exit_code)
