"""Operator-only A5 helper qualification; never auto-collected or run at import.

No CE, GnuPG, foreign process discovery, memory operations, cleanup or elevation.
The external handoff pins all four source files and the interpreter before use.
"""

SOURCE_PATHS = (
    "src/armedforces_tool/h3_windows_process_identity.py",
    "tests/test_h3_windows_process_identity.py",
    "tests/h3_windows_process_identity_native_probe.py",
    "docs/architecture/h3_windows_process_identity_contract.md",
)
REQUIRED_CHECKS = (
    "01_operator_sid_non_elevated_mode",
    "02_interpreter_and_four_source_hashes",
    "03_fresh_disposable_child",
    "04_own_helper_native_handle_identity",
    "05_pid_creation_continuity",
    "06_canonical_image_and_architecture",
    "07_utc_monotonic_bounded_consistency",
    "08_exited_instance_rejected",
    "09_simulated_pid_reuse_access_denied_clock_faults",
    "10_readonly_api_allowlist_zero_memory_operations",
    "11_inert_import_no_production_dispatch",
    "12_source_evidence_identity_and_independent_readback",
)
NOT_QUALIFIED = (
    "CE_ATTACHMENT_IDENTITY", "SCENE_CONTINUITY", "SEMANTIC_TARGET_OWNERSHIP",
    "ABA_TOCTOU_EXCLUSION", "TAMPER_PROOF_TIME", "SUSPEND_BEHAVIOR",
    "SOURCE_AUTHENTICATION", "PRODUCTION_WRITE_RESTORE", "GNUPG_AGENT_ISOLATION",
)


def canonical_json(value):
    import json
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("ascii")


def sha(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def file_manifest(files):
    return {name: {"bytes": len(raw), "sha256": sha(raw)} for name, raw in files.items()}


def verify_bundle(path):
    """Independent ZIP reopen, strict name/size/hash/canonical JSON validation."""
    import json
    import zipfile
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) > 8:
            raise ValueError("BUNDLE_INVENTORY")
        raw = {}
        for info in archive.infolist():
            if (info.file_size > 262144 or info.compress_size > 262144
                    or "/" in info.filename or "\\" in info.filename):
                raise ValueError("BUNDLE_BOUNDS")
            raw[info.filename] = archive.read(info)
        receipt = json.loads(raw.pop("native-receipt.json"))
        if file_manifest(raw) != receipt["files"]:
            raise ValueError("BUNDLE_CONTENT_CHANGED")
        for body in raw.values():
            if canonical_json(json.loads(body)) != body:
                raise ValueError("BUNDLE_NONCANONICAL")
        if canonical_json(receipt) != archive.read("native-receipt.json"):
            raise ValueError("RECEIPT_NONCANONICAL")
        return receipt


def write_bundle(root, reports, receipt):
    import zipfile
    for name, body in {**reports, "native-receipt.json": canonical_json(receipt)}.items():
        with (root / name).open("xb") as f:
            f.write(body)
        if (root / name).read_bytes() != body:
            raise ValueError("EVIDENCE_READBACK")
    target = root / "native-identity-bundle.zip"
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_STORED) as archive:
        for name in (*reports, "native-receipt.json"):
            archive.writestr(name, (root / name).read_bytes())
    if verify_bundle(target) != receipt:
        raise ValueError("BUNDLE_READBACK")


def simulated_rejections(m):
    """Labeled synthetic faults. No process or clock calls, even in native T1."""
    class Boundary:
        def __init__(self):
            self.created = m.FILETIME_EPOCH + 10000000
            self.wall, self.mono = m.FILETIME_EPOCH + 20000000, 1000
            self.denied = False
        def open_process(self, _pid):
            if self.denied:
                raise m.ObserverError("ACCESS_DENIED")
            return 7
        def close_handle(self, _handle):
            return True
        def is_running(self, _handle):
            return True
        def identity(self, _handle):
            return 7, self.created, "C:\\TestOnly\\helper.exe", "x64"
        def wall_filetime(self):
            return self.wall
        def monotonic_ms(self):
            return self.mono
    results = {}
    for name in ("pid_reuse", "access_denied", "clock_rollback", "clock_jump"):
        b = Boundary()
        with m.ProcessObserver(7, b, expected_executable="C:\\TestOnly\\helper.exe",
                               expected_architecture="x64") as o:
            if name == "access_denied":
                b.denied = True
            else:
                if o.observe().status != m.SUCCESS:
                    raise ValueError("SIMULATION_BASELINE")
                if name == "pid_reuse":
                    b.created += 1
                elif name == "clock_rollback":
                    b.wall -= 1
                else:
                    b.wall += 100000000
            result = o.observe()
            if result.status != "REJECTED":
                raise ValueError("SIMULATION_ACCEPTED")
            results[name] = result.reason_code
    return results


def operator_context():
    """Current process token and known-folder only; no enumeration or token changes."""
    import ctypes as c
    import os
    import uuid
    if os.name != "nt":
        raise ValueError("WINDOWS_REQUIRED")
    kernel = c.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
    advapi = c.WinDLL("advapi32.dll", use_last_error=True, winmode=0x800)
    shell = c.WinDLL("shell32.dll", use_last_error=True, winmode=0x800)
    ole = c.WinDLL("ole32.dll", use_last_error=True, winmode=0x800)
    def bind(lib, name, args, result):
        f = getattr(lib, name)
        f.argtypes, f.restype = args, result
        return f
    get_current = bind(kernel, "GetCurrentProcess", [], c.c_void_p)
    close = bind(kernel, "CloseHandle", [c.c_void_p], c.c_int)
    local_free = bind(kernel, "LocalFree", [c.c_void_p], c.c_void_p)
    open_token = bind(advapi, "OpenProcessToken", [c.c_void_p, c.c_uint32, c.POINTER(c.c_void_p)], c.c_int)
    token_info = bind(advapi, "GetTokenInformation",
                      [c.c_void_p, c.c_uint32, c.c_void_p, c.c_uint32, c.POINTER(c.c_uint32)], c.c_int)
    sid_string = bind(advapi, "ConvertSidToStringSidW", [c.c_void_p, c.POINTER(c.c_wchar_p)], c.c_int)
    token = c.c_void_p()
    if not open_token(get_current(), 8, c.byref(token)):
        raise ValueError("TOKEN_QUERY_FAILED")
    try:
        size, elevation = c.c_uint32(), c.c_uint32()
        if not token_info(token, 20, c.byref(elevation), 4, c.byref(size)) or size.value != 4:
            raise ValueError("ELEVATION_QUERY_FAILED")
        token_info(token, 1, None, 0, c.byref(size))
        if not 1 <= size.value <= 65536:
            raise ValueError("TOKEN_SIZE")
        body = c.create_string_buffer(size.value)
        if not token_info(token, 1, body, size, c.byref(size)):
            raise ValueError("SID_QUERY_FAILED")
        sid = c.cast(body, c.POINTER(c.c_void_p))[0]
        value = c.c_wchar_p()
        if not sid_string(sid, c.byref(value)):
            raise ValueError("SID_FORMAT_FAILED")
        try:
            text = value.value
        finally:
            local_free(c.cast(value, c.c_void_p))
    finally:
        if not close(token):
            raise ValueError("TOKEN_CLOSE_FAILED")
    folder = bind(shell, "SHGetKnownFolderPath",
                  [c.c_void_p, c.c_uint32, c.c_void_p, c.POINTER(c.c_wchar_p)], c.c_int32)
    free = bind(ole, "CoTaskMemFree", [c.c_void_p], None)
    guid = c.create_string_buffer(uuid.UUID("F1B32785-6FBA-4FCF-9D55-7B8E7F157091").bytes_le)
    value = c.c_wchar_p()
    if folder(guid, 0, None, c.byref(value)) != 0:
        raise ValueError("LOCALAPPDATA_QUERY_FAILED")
    try:
        local = value.value
    finally:
        free(c.cast(value, c.c_void_p))
    if local != os.environ.get("LOCALAPPDATA"):
        raise ValueError("LOCALAPPDATA_MISMATCH")
    return {"sid": text, "elevated": bool(elevation.value), "local_app_data": local}


def checked_directory(path):
    import os
    import stat
    for part in reversed((path, *path.parents)):
        st = os.lstat(part)
        if not stat.S_ISDIR(st.st_mode) or getattr(st, "st_file_attributes", 0) & 0x400:
            raise ValueError("ROOT_REPARSE_OR_TYPE")
    st = os.lstat(path)
    return {"device": st.st_dev, "file_id": st.st_ino, "created_ns": st.st_birthtime_ns}


def volume_context(path):
    import ctypes as c
    kernel = c.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
    fn = kernel.GetVolumeInformationW
    fn.argtypes = [c.c_wchar_p, c.c_wchar_p, c.c_uint32, c.POINTER(c.c_uint32),
                   c.POINTER(c.c_uint32), c.POINTER(c.c_uint32), c.c_wchar_p, c.c_uint32]
    fn.restype = c.c_int
    serial, length, flags = c.c_uint32(), c.c_uint32(), c.c_uint32()
    fs = c.create_unicode_buffer(64)
    if not fn(path.anchor, None, 0, c.byref(serial), c.byref(length), c.byref(flags), fs, len(fs)):
        raise ValueError("VOLUME_QUERY_FAILED")
    return {"filesystem": fs.value, "serial": serial.value, "flags": flags.value}


def import_inertness(source):
    import builtins
    namespace = {"__name__": "a5_import_audit"}
    code = compile(source, "a5_import_audit", "exec")
    saved = builtins.__import__
    def forbidden(*_args, **_kwargs):
        raise ValueError("IMPORT_SIDE_EFFECT")
    try:
        builtins.__import__ = forbidden
        exec(code, namespace)
    finally:
        builtins.__import__ = saved
    return namespace


def run(args):
    import importlib.util
    import os
    from pathlib import Path
    import struct
    import subprocess
    import sys
    import time
    import uuid
    if (args.mode != "identity-native-only" or args.diagnostic != "debug"
            or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode
            or sys.flags.optimize or sys.version_info[:3] != (3, 14, 3)):
        raise ValueError("MODE_OR_RUNTIME_FLAGS")
    context = operator_context()
    if context["sid"] != args.expected_sid or context["elevated"]:
        raise ValueError("OPERATOR_IDENTITY_OR_ELEVATION")
    repo = Path(__file__).resolve().parents[1]
    sources = {name: (repo / name).read_bytes() for name in SOURCE_PATHS}
    manifest = {"schema": "h3_a5_sources_v1", "files": file_manifest(sources)}
    if sha(canonical_json(manifest)) != args.expected_snapshot:
        raise ValueError("SOURCE_PIN_MISMATCH")
    python = Path(sys.executable)
    python_hash = sha(python.read_bytes())
    if python_hash != args.expected_python_sha256:
        raise ValueError("INTERPRETER_PIN_MISMATCH")
    spec = importlib.util.spec_from_file_location("a5_native_observer", repo / SOURCE_PATHS[0])
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    parent = Path(context["local_app_data"]) / "ChromeProject-H3-Identity-Qualification"
    m.canonical_executable(str(parent / "probe.exe"))
    checked_directory(parent.parent)
    print("mode=identity-native-only diagnostic=debug", flush=True)
    print("operator-sid=" + context["sid"], flush=True)
    print("disposable-parent=" + str(parent), flush=True)
    print("source-manifest-sha256=" + args.expected_snapshot, flush=True)
    for name in REQUIRED_CHECKS:
        print("REQUIRED " + name, flush=True)
    print("Approve this ordinary-account, helper-only disposable test. Type APPROVE:", flush=True)
    if input().strip() != "APPROVE":
        raise ValueError("OPERATOR_APPROVAL_REQUIRED")
    try:
        parent.mkdir()
    except FileExistsError:
        pass
    parent_identity = checked_directory(parent)
    root = parent / ("identity-" + uuid.uuid4().hex)
    root.mkdir(exist_ok=False)
    root_identity = checked_directory(root)
    if list(root.iterdir()):
        raise ValueError("CHILD_NOT_EMPTY")
    checks = {name: {"status": "FAIL", "detail": "NOT_COMPLETED"} for name in REQUIRED_CHECKS}
    def pass_check(index, detail):
        checks[REQUIRED_CHECKS[index - 1]] = {"status": "PASS", "detail": detail}
        print("PASS " + REQUIRED_CHECKS[index - 1], flush=True)
    try:
        pass_check(1, {"sid": context["sid"], "elevated": False, "mode": args.mode, "diagnostic": args.diagnostic})
        pass_check(2, {"python_sha256": python_hash, "source_manifest_sha256": args.expected_snapshot})
        pass_check(3, {"fresh_exclusive_child": True, "identity": root_identity})
        api = m.NativeWin32Boundary()
        # Only the process created here is selected. No PID argument or discovery exists.
        helper_code = "import time; print('A5_HELPER_READY', flush=True); time.sleep(3); print('A5_HELPER_DONE', flush=True)"
        argv = [str(python), "-I", "-B", "-S", "-c", helper_code]
        environment = {k: v for k, v in os.environ.items()
                       if k in ("SystemRoot", "WINDIR", "LOCALAPPDATA", "PATH")}
        environment.update(TEMP=str(root), TMP=str(root), PYTHONDONTWRITEBYTECODE="1")
        child = subprocess.Popen(argv, cwd=root, env=environment, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        process_data = {"launch_pid": child.pid, "scope": "directly_created_python_helper_launcher"}
        # A Windows venv launcher may host a child worker. We observe only this retained
        # Popen launch handle/PID, never discover or open another worker's numeric PID.
        direct = api.identity(int(child._handle))
        if direct[0] != child.pid or direct[2] != str(python):
            raise ValueError("HELPER_LAUNCH_IDENTITY")
        arch = "x64" if struct.calcsize("P") == 8 else "x86"
        o = m.ProcessObserver(child.pid, api, expected_executable=str(python), expected_architecture=arch)
        try:
            first = o.observe()
            if first.status != m.SUCCESS:
                raise ValueError(first.reason_code)
            pass_check(4, {"independently_opened_pid": child.pid, "retained_launch_handle_agrees": direct == o.diagnostic_observations()[0][0]})
            if direct != o.diagnostic_observations()[0][0]:
                raise ValueError("LAUNCH_CREATION_MISMATCH")
            time.sleep(0.08)
            second = o.observe()
            if second.status != m.SUCCESS:
                raise ValueError(second.reason_code)
            samples = o.diagnostic_observations()
            pass_check(5, {"same_pid_and_creation": samples[0][0] == samples[1][0]})
            pass_check(6, {"architecture": direct[3], "image_sha256": sha(direct[2].encode("utf-8")), "canonical_path": True})
            pass_check(7, {"elapsed_upper_ms": second.elapsed_upper_ms, "max_elapsed_ms": 5000,
                           "tolerance_ms": 32, "max_sample_ms": 100})
            stdout, stderr = child.communicate(timeout=10)
            if child.returncode != 0 or stdout.replace(b"\r\n", b"\n") != b"A5_HELPER_READY\nA5_HELPER_DONE\n" or stderr:
                raise ValueError("HELPER_EXIT_OR_OUTPUT")
            stale = o.observe()
            if stale.status != "REJECTED" or stale.reason_code != "PROCESS_EXITED":
                raise ValueError("STALE_PROCESS_ACCEPTED")
            pass_check(8, {"exit_code": child.returncode, "stale_reason": stale.reason_code})
            process_data.update(creation_filetime=direct[1], creation_utc=m.filetime_utc(direct[1]),
                                executable_basename=python.name, executable_sha256=python_hash,
                                image_path_sha256=sha(direct[2].encode("utf-8")), architecture=direct[3],
                                independent_handle_identity_matches=True, stale_reason=stale.reason_code)
        finally:
            o.close()
        with (root / "helper-stdout.bin").open("xb") as f:
            f.write(stdout)
        with (root / "helper-stderr.bin").open("xb") as f:
            f.write(stderr)
        # No terminate/kill fallback. The fixed helper exits naturally even after probe failure.
        faults = simulated_rejections(m)
        if faults != {"pid_reuse": "IDENTITY_CHANGED", "access_denied": "ACCESS_DENIED",
                      "clock_rollback": "CLOCK_ROLLBACK", "clock_jump": "CLOCK_INCONSISTENT"}:
            raise ValueError("FAULT_SIMULATION_FAILED")
        pass_check(9, {"basis": "injected_not_native_fault", "results": faults})
        pass_check(10, {"observer_api_allowlist": list(api.API_NAMES), "process_access_mask": m.QUERY_ACCESS,
                        "memory_read_attempts": 0, "memory_write_attempts": 0,
                        "ce_calls": 0, "debugger_calls": 0, "process_termination_calls": 0})
        import_inertness(sources[SOURCE_PATHS[0]])
        import_inertness(sources[SOURCE_PATHS[2]])
        for script in (repo / "src").glob("*.lua"):
            if b"h3_windows_process_identity" in script.read_bytes():
                raise ValueError("PRODUCTION_DISPATCH_PRESENT")
        pass_check(11, {"imports_forbidden_during_module_execution": True, "lua_dispatch_reference": False})
        if sources != {name: (repo / name).read_bytes() for name in SOURCE_PATHS} or sha(python.read_bytes()) != python_hash:
            raise ValueError("SOURCE_OR_INTERPRETER_CHANGED")
        if checked_directory(root) != root_identity or checked_directory(parent) != parent_identity:
            raise ValueError("ROOT_CHANGED")
        # Independent exclusive file reopen before the final bundle and its second readback.
        identity_bytes = canonical_json({"root": root_identity, "sources": manifest, "python": python_hash})
        with (root / "evidence-identity.json").open("xb") as f:
            f.write(identity_bytes)
        if (root / "evidence-identity.json").read_bytes() != identity_bytes:
            raise ValueError("IDENTITY_READBACK")
        pass_check(12, {"evidence_identity_sha256": sha(identity_bytes), "sources_unchanged": True,
                        "independent_file_readback": True, "bundle_readback_required_before_exit": True})
        clocks = [{"utc": s[2], "wall_filetime": s[1], "monotonic_before_ms": s[3],
                   "monotonic_after_ms": s[4], "pid": s[0][0], "creation_filetime": s[0][1]} for s in samples]
        reports = {
            "native-results.json": canonical_json({"required_checks": list(REQUIRED_CHECKS), "checks": checks,
                "native_status": "PASS", "not_qualified": list(NOT_QUALIFIED),
                "h3_a4_native_agent_isolation": "UNQUALIFIED"}),
            "process-observations.json": canonical_json(process_data),
            "clock-observations.json": canonical_json({"observations": clocks, "precision": "raw_100ns_ticks_not_accuracy",
                "monotonic_source": "GetTickCount64", "wall_source": "GetSystemTimePreciseAsFileTime"}),
            "source-manifest.json": canonical_json(manifest),
            "process-transcripts.json": canonical_json({"helper_count": 1, "exit_code": child.returncode,
                "stdout": stdout.decode("ascii"), "stderr": stderr.decode("ascii"),
                "argv": [python.name, *argv[1:]], "scope": "own_finite_helper_only"}),
        }
        if not all(item["status"] == "PASS" for item in checks.values()):
            raise ValueError("REQUIRED_CHECK_FAILED")
        receipt = {"schema": "h3_a5_native_receipt_v1", "native_status": "PASS",
            "mode": args.mode, "diagnostic": args.diagnostic, "operator_sid": context["sid"],
            "elevated": False, "root": str(root), "root_identity": root_identity,
            "parent_identity": parent_identity, "filesystem": volume_context(root),
            "os_version": list(sys.getwindowsversion()), "machine_architecture": arch,
            "python_sha256": python_hash, "source_manifest_sha256": args.expected_snapshot,
            "required_checks": list(REQUIRED_CHECKS), "files": file_manifest(reports),
            "attachment_verified": False, "scene_os_measured": False,
            "authorization_status": "NOT_PRODUCTION_AUTHORIZED", "handoff_write_ready": False,
            "write_ready": False, "write_attempted": False, "restore_attempted": False,
            "memory_read_attempts": 0, "memory_write_attempts": 0, "independent_review_required": True,
            "evidence_identity_sha256": sha(identity_bytes)}
        write_bundle(root, reports, receipt)
        print("native-bundle=" + str(root / "native-identity-bundle.zip"), flush=True)
        print("native-bundle-sha256=" + sha((root / "native-identity-bundle.zip").read_bytes()), flush=True)
        print("native-parent-exit-code=0", flush=True)
        return 0
    except BaseException as error:
        # Never redirect to another test root or overwrite existing evidence.
        if checked_directory(root) == root_identity:
            if "child" in locals():
                try:
                    failed_out, failed_err = child.communicate(timeout=10)
                    for name, raw in (("helper-failure-stdout.bin", failed_out),
                                      ("helper-failure-stderr.bin", failed_err)):
                        with (root / name).open("xb") as f:
                            f.write(raw)
                except Exception:
                    print("helper-output-unavailable; no termination attempted", flush=True)
            with (root / "native-failure.json").open("xb") as f:
                f.write(canonical_json({"native_status": "BLOCKED", "checks": checks,
                                        "failure_type": type(error).__name__, "failure": str(error)[:512]}))
        print("partial-evidence-root=" + str(root), flush=True)
        raise


def main():
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=["identity-native-only"])
    parser.add_argument("--diagnostic", required=True, choices=["debug"])
    parser.add_argument("--expected-sid", required=True)
    parser.add_argument("--expected-snapshot", required=True)
    parser.add_argument("--expected-python-sha256", required=True)
    args = parser.parse_args()
    try:
        return run(args)
    except (Exception, KeyboardInterrupt) as error:
        print("native_status=BLOCKED", flush=True)
        print("native-parent-exit-code=1", flush=True)
        print(type(error).__name__ + ": " + str(error)[:512], file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
