"""Operator-only offline crypto qualification, never pytest auto-collected.

Only disposable synthetic keys, one explicitly approved isolated test agent,
and public-only gpgv verification. No personal keyring or hardware token access.
"""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import re
import sys
import time
import uuid
import zipfile


SOURCE_PATHS = (
    "src/armedforces_tool/h3_approval_auth.py",
    "tests/test_h3_approval_auth.py",
    "tests/h3_approval_native_probe.py",
    "docs/architecture/h3_approval_auth_contract.md",
)
LABEL = "NATIVE_TEST_SIGNATURE_VERIFICATION_ONLY"
REQUIRED = frozenset((
    "exact_write_signature", "exact_restore_signature", "corrupted_signature",
    "one_byte_approval_mutation", "wrong_signer", "absent_signer", "role_mismatch",
    "malformed_policy", "duplicate_signature_packets", "ambiguous_status_injected",
    "fresh_process_readonly_verification", "replay_rejected", "revoked_policy",
    "expired_policy", "test_keys_not_production", "source_integrity", "isolated_agent_stopped",
))


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("ascii")


def sha(body):
    return hashlib.sha256(body).hexdigest()


def source_manifest(repo):
    return {name: {"bytes": len(body), "sha256": sha(body)}
            for name in SOURCE_PATHS for body in [(repo / name).read_bytes()]}


def load_product(repo):
    spec = importlib.util.spec_from_file_location("h3_native_approval_auth", repo / SOURCE_PATHS[0])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fixture(module, role, issued="2026-06-01T12:00:00Z", request=None):
    """Fictional identities only; no source inventory/process lookup."""
    start = datetime.fromisoformat(issued)
    stamp = lambda value: value.strftime("%Y-%m-%dT%H:%M:%SZ")
    a = dict(schema=f"h3_{role}_approval_v1", source_kind="h3_single", environment="synthetic_only",
             request_id=request or f"test-{role}-one", authority="synthetic-authority",
             trust_domain="h3-synthetic-tests-v1", action=f"single_float32_{role}_once",
             case_id="test-fictional-case", session_id="test-fictional-session", candidate_address="0x1234",
             current_float="100", current_pattern="0x42C80000", target_float="200", target_pattern="0x43480000",
             pid="1234", process_created_utc=stamp(start - timedelta(hours=1)), executable=r"C:\Synthetic\fictional.exe",
             architecture="x64", attachment_id="test-fictional-attachment", scene_id="test-fictional-scene",
             issued_utc=issued, expires_utc=stamp(start + timedelta(seconds=120)), max_elapsed_ms="10000")
    if role == "write":
        a.update(source_batch_id="SyntheticBatch", source_case_id="SyntheticCase", source_session_id="SyntheticSession")
        for name in module.SOURCE_NAMES:
            a[name + "_id"] = "test-" + name.replace("_", "-")
            a[name + "_sha256"] = sha(("fictional-" + name).encode("ascii"))
        fields = module.WRITE_FIELDS
    else:
        a.update(source_request_id="test-source-write", source_preparation_sha256="1" * 64,
                 source_receipt_sha256="2" * 64, current_float="200", current_pattern="0x43480000",
                 target_float="100", target_pattern="0x42C80000")
        fields = module.RESTORE_FIELDS
    return "".join(f"{key}={a[key]}\r\n" for key in fields).encode("ascii")


def policy_fixture(module, keyring_hash, write_fpr, restore_fpr=None, issued="2026-06-01T12:00:00Z"):
    start = datetime.fromisoformat(issued)
    stamp = lambda value: value.strftime("%Y-%m-%dT%H:%M:%SZ")
    begin, end = stamp(start - timedelta(hours=1)), stamp(start + timedelta(hours=1))
    signers = [dict(primary_fingerprint=fpr, signing_fingerprint=fpr, role=role,
                    valid_from=begin, valid_until=end, revoked=False)
               for role, fpr in (("write", write_fpr), ("restore", restore_fpr)) if fpr]
    return dict(schema="h3_public_key_policy_v1", policy_id="test-only-policy-v1", purpose="TEST_ONLY_REVIEW",
                authority=module.AUTHORITY, trust_domain=module.DOMAIN, valid_from=begin, valid_until=end,
                revocation_checked_utc=begin, revocation_valid_until=end, keyring_sha256=keyring_hash, signers=signers)


def qualify(results):
    if set(results) != REQUIRED or any(entry.get("status") != "PASS" for entry in results.values()):
        raise RuntimeError("INCOMPLETE_NATIVE_CHECKS")


def emit_new(path, body):
    with path.open("xb") as handle:
        if handle.write(body) != len(body):
            raise RuntimeError("EVIDENCE_SHORT_WRITE")
        handle.flush()
        os.fsync(handle.fileno())
    if path.read_bytes() != body:
        raise RuntimeError("EVIDENCE_READBACK_FAILED")


def record_process(child, summaries, tool, result):
    """Retain bounded original output locally; only hashes enter the ZIP."""
    sequence = len(summaries)
    for stream, body in (("stdout", result.status), ("stderr", result.diagnostics)):
        emit_new(child / f"subprocess-{sequence:03d}.{stream}", body)
    summaries.append({"tool": tool, "sequence": sequence, "exit": result.returncode,
                      "stdout_bytes": len(result.status), "stdout_sha256": sha(result.status),
                      "stderr_bytes": len(result.diagnostics), "stderr_sha256": sha(result.diagnostics)})


def isolated(condition, code):
    if not condition:
        raise RuntimeError(code)


def windows_path(value):
    """Lexical check only; existing objects also require Windows handle checks.

    Do not use WindowsPath equality: it silently folds case. Nor may resolve()
    repair an alias before the original spelling has been inspected.
    """
    isolated(type(value) is str and value.isascii() and len(value) <= 230
             and re.fullmatch(r'[A-Z]:\\[^<>|?*\x00-\x1f\x7f-\uffff"/:]+', value),
             "AGENT_PATH_REJECTED")
    path = PureWindowsPath(value)
    isolated(str(path) == value, "AGENT_PATH_REJECTED")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"{p}{n}" for p in ("COM", "LPT") for n in range(1, 10)}
    isolated(all(part not in (".", "..") and not part.endswith((".", " ")) and "~" not in part
                 and part.split(".")[0].upper() not in reserved for part in path.parts[1:]),
             "AGENT_PATH_REJECTED")
    return path


def derived_socket_directory(home, local_appdata):
    """GnuPG 2.4.8 common/homedir.c: ASCII lower/slashes, SHA-1/80, z-base-32.

    SHA-1 here names a directory; it is not authentication or freshness proof.
    The accepted spelling is narrower than GnuPG's permissive normalization.
    """
    path, local = windows_path(home), windows_path(local_appdata)
    parent = local / "ChromeProject-H3-Approval-Qualification"
    isolated(str(path.parent.parent.parent) == str(local)
             and str(path.parent.parent) == str(parent)
             and re.fullmatch(r"auth-[0-9a-f]{32}", path.parent.name)
             and path.name == "test-gnupg", "AGENT_HOME_REJECTED")
    normalized = home.lower().replace("\\", "/").encode("ascii")
    number = int.from_bytes(hashlib.sha1(normalized).digest()[:10], "big")
    alphabet = "ybndrfg8ejkmcpqxot1uwisza345h769"
    suffix = "".join(alphabet[(number >> shift) & 31] for shift in range(75, -1, -5))
    return str(local / "gnupg" / ("d." + suffix))


def reported_directory(body):
    # Named --list-dirs output in 2.4.8 is RAW, not percent-escaped. Decoding
    # it with unquote could turn a literal path into a different path.
    isolated(type(body) is bytes and 0 < len(body) <= 512, "AGENT_PATH_REPORT_AMBIGUOUS")
    match = re.fullmatch(rb"([^\r\n]+)\r?\n", body)
    isolated(match is not None, "AGENT_PATH_REPORT_AMBIGUOUS")
    try:
        value = match[1].decode("ascii")
    except UnicodeError:
        raise RuntimeError("AGENT_PATH_REPORT_AMBIGUOUS") from None
    windows_path(value)
    return value


def endpoint_port(name, body):
    """Read libassuan's Windows descriptor format, never connect or use nonce.

    The primary endpoint is decimal/LF plus 16 bytes. The SSH artifact uses
    the Cygwin descriptor; only its port is needed for OS ownership checking.
    Redirection, trailing data and alternative formats fail closed.
    """
    isolated(type(body) is bytes, "AGENT_ENDPOINT_FORMAT_REJECTED")
    if name == "S.gpg-agent":
        match = re.fullmatch(rb"([1-9][0-9]{0,4})\n[\s\S]{16}", body)
    elif name == "S.gpg-agent.ssh":
        match = re.fullmatch(rb"!<socket >([1-9][0-9]{0,4}) s [0-9a-f]{8}(?:-[0-9a-f]{8}){3}\x00", body)
    else:
        raise RuntimeError("AGENT_ENDPOINT_FORBIDDEN")
    isolated(match is not None and int(match[1]) <= 65535, "AGENT_ENDPOINT_FORMAT_REJECTED")
    return int(match[1])


class IsolatedAgent:
    """Test-only state machine. IO is injected; importing performs no operations.

    A retained process handle plus OS listener ownership establishes the link
    BEFORE any gpg connection. No GETINFO probe of an unproven endpoint, no
    default-agent discovery, and no endpoint-based cleanup are permitted.
    """

    endpoints = ("S.gpg-agent", "S.gpg-agent.ssh")

    def __init__(self, home, local_appdata, executable, binary_hash, sid, io):
        self.home, self.local, self.executable = home, local_appdata, executable
        self.directory = derived_socket_directory(home, local_appdata)
        windows_path(executable)
        isolated(re.fullmatch(r"[0-9a-f]{64}", binary_hash) and re.fullmatch(r"S-1-5-[0-9-]+", sid),
                 "AGENT_IDENTITY_UNPROVEN")
        self.binary_hash, self.sid, self.io = binary_hash, sid, io
        self.directories, self.process, self.identity, self.sockets = {}, None, None, None
        self.bound, self.failed = False, False
        self.evidence = {"home": home, "socket_directory": self.directory, "events": [],
                         "ssh_connections": 0, "cleanup": "NOT_STARTED"}

    def prepare(self):
        isolated(not self.directories and self.process is None, "AGENT_SETUP_REUSED")
        home = PureWindowsPath(self.home)
        # The shared gnupg parent may exist. Never enumerate it or its siblings.
        for path in (self.local, str(home.parent.parent), str(home.parent), self.home):
            self.directories[path] = self.io.inspect(path, directory=True)
        isolated(not self.io.children(self.home), "AGENT_HOME_NOT_FRESH")
        base = str(PureWindowsPath(self.directory).parent)
        if not self.io.exists(base):
            self.io.mkdir(base)
        self.directories[base] = self.io.inspect(base, directory=True)
        # Even an empty pre-existing d.<hash> is not owned by this run.
        isolated(not self.io.exists(self.directory), "AGENT_SOCKET_DIRECTORY_NOT_FRESH")
        self.io.mkdir(self.directory)  # Exclusive: an intervening creator fails.
        self.directories[self.directory] = self.io.inspect(self.directory, directory=True)
        self.fresh()
        self.evidence["events"].append({"stage": "before_metadata", "directory_created_exclusively": True,
                                        "endpoints_absent": True, "time": self.io.now()})

    def stable_directories(self):
        isolated(bool(self.directories), "AGENT_SETUP_MISSING")
        for path, identity in self.directories.items():
            isolated(self.io.inspect(path, directory=True) == identity, "AGENT_DIRECTORY_CHANGED")

    def fresh(self):
        self.stable_directories()
        isolated(not self.io.children(self.directory), "AGENT_SOCKET_NOT_FRESH_ISOLATED")

    def expected_paths(self):
        root = PureWindowsPath(self.directory)
        return {"homedir": self.home, "socketdir": self.directory,
                **{key: str(root / name) for key, name in (
                    ("agent-socket", "S.gpg-agent"), ("agent-ssh-socket", "S.gpg-agent.ssh"),
                    ("agent-extra-socket", "S.gpg-agent.extra"), ("agent-browser-socket", "S.gpg-agent.browser"))}}

    def bind(self, reports, versions):
        isolated(versions == {name: f"{name} (GnuPG) 2.4.8" for name in ("gpg", "gpgv", "gpg-agent", "gpgconf")},
                 "AGENT_VERSION_UNQUALIFIED")
        isolated(set(reports) == set(self.expected_paths()), "AGENT_PATH_REPORT_AMBIGUOUS")
        isolated({key: reported_directory(value) for key, value in reports.items()} == self.expected_paths(),
                 "AGENT_HOME_SOCKET_MAPPING_MISMATCH")
        self.fresh()
        self.bound = True

    def start(self):
        isolated(self.bound and self.process is None and not self.failed, "AGENT_START_NOT_APPROVED")
        self.fresh()
        isolated(not self.io.children(self.home), "AGENT_HOME_NOT_FRESH")
        argv = [self.executable, "--no-options", "--homedir", self.home, "--daemon", "--no-detach",
                "--disable-scdaemon", "--no-allow-external-cache", "--allow-loopback-pinentry",
                "--extra-socket", "none", "--browser-socket", "none"]
        self.before = self.io.now()
        self.process = self.io.spawn(argv, self.binary_hash)
        self.evidence["events"].append({"stage": "process_created_identity_pending", "pid": self.process.pid,
                                        "time": self.before})
        after = self.io.now()
        identity = self.io.process_identity(self.process)
        isolated(identity["pid"] == self.process.pid and type(identity["pid"]) is int and identity["pid"] > 0
                 and identity["path"] == self.executable and identity["sid"] == self.sid
                 and type(identity["created"]) is int and self.before <= identity["created"] <= after,
                 "AGENT_IDENTITY_UNPROVEN")
        self.identity = identity
        self.evidence["events"].append({"stage": "launched", "pid": identity["pid"], "created": identity["created"],
                                        "sid_sha256": sha(self.sid.encode("ascii")), "binary_sha256": self.binary_hash,
                                        "argv_sha256": sha(json_bytes(argv))})
        self.io.begin_capture(self.process)

    def observe(self):
        self.stable_directories()
        isolated(self.io.healthy(self.process), "AGENT_OUTPUT_LIMIT")
        isolated(self.identity is not None and self.io.process_identity(self.process) == self.identity,
                 "AGENT_IDENTITY_CHANGED")
        names = self.io.children(self.directory)
        isolated(set(names) <= set(self.endpoints) and len(names) == len(set(names)), "AGENT_UNAPPROVED_ENDPOINT")
        if set(names) != set(self.endpoints):
            return None  # Bounded startup wait only; never a reason to connect.
        sockets = {}
        for name in self.endpoints:
            identity, body = self.io.endpoint(str(PureWindowsPath(self.directory) / name))
            isolated(identity["created"] >= self.before, "AGENT_ENDPOINT_NOT_FRESH")
            sockets[name] = {"identity": identity, "sha256": sha(body), "port": endpoint_port(name, body)}
        ports = {entry["port"] for entry in sockets.values()}
        isolated(len(ports) == 2, "AGENT_ENDPOINT_IDENTITY_AMBIGUOUS")
        expected = sorted(("127.0.0.1", port, self.identity["pid"]) for port in ports)
        # Include ANY listener for our PID, and any competing listener for these
        # ports. The table is metadata; no other PID is opened or contacted.
        actual = sorted(row for row in self.io.listeners() if row[2] == self.identity["pid"] or row[1] in ports)
        isolated(actual == expected, "AGENT_LISTENER_IDENTITY_UNPROVEN")
        return sockets

    def ready(self):
        isolated(not self.failed, "AGENT_PREVIOUS_FAILURE")
        try:
            observed = self.observe()
            if observed is None:
                isolated(self.sockets is None, "AGENT_ENDPOINT_DISAPPEARED")
                return False
            if self.sockets is not None:
                isolated(observed == self.sockets, "AGENT_ENDPOINT_CHANGED")
            self.sockets = observed
            return True
        except Exception:
            self.failed = True
            raise

    def authorize(self, endpoint="S.gpg-agent"):
        try:
            isolated(endpoint == "S.gpg-agent", "AGENT_ENDPOINT_USE_FORBIDDEN")
            isolated(self.sockets is not None and self.ready(), "AGENT_NOT_READY")
        except Exception:
            self.failed = True
            raise

    def stop(self):
        if self.process is None:
            return False
        # An uncertain endpoint never authorizes gpgconf --kill. Terminate only
        # the retained launch handle after checking that exact process again.
        isolated(self.identity is not None, "AGENT_CLEANUP_IDENTITY_UNPROVEN")
        if self.io.poll(self.process) is None:
            isolated(self.io.process_identity(self.process) == self.identity, "AGENT_CLEANUP_IDENTITY_CHANGED")
            self.io.terminate(self.process)
        isolated(self.io.poll(self.process) is not None
                 and not any(row[2] == self.identity["pid"] for row in self.io.listeners()),
                 "AGENT_SHUTDOWN_UNPROVEN")
        self.evidence["cleanup"] = "OWNED_PROCESS_STOPPED_ARTIFACTS_RETAINED"
        self.evidence["sockets"] = self.sockets
        return True


class WindowsAgentIO:
    """Native adapters, reached only by the separately authorized operator main.

    All metadata APIs are read-only. No OpenProcess(PID), socket connection,
    ACL mutation, default-home discovery, unlink or directory removal exists.
    """

    def __init__(self, module, sid, env, child):
        import ctypes as c
        from ctypes import wintypes as w
        isolated(os.name == "nt", "REQUIRES_WINDOWS")
        self.c, self.w, self.module, self.sid = c, w, module, sid
        self.env, self.child = dict(env), str(child)
        self.k = c.WinDLL("kernel32", use_last_error=True)
        self.a = c.WinDLL("advapi32", use_last_error=True)
        self.ip = c.WinDLL("iphlpapi", use_last_error=True)
        self.shell = c.WinDLL("shell32", use_last_error=True)

        class FileInfo(c.Structure):
            _fields_ = [("attributes", w.DWORD), ("creation", w.FILETIME), ("access", w.FILETIME),
                        ("write", w.FILETIME), ("volume", w.DWORD), ("size_high", w.DWORD),
                        ("size_low", w.DWORD), ("links", w.DWORD), ("index_high", w.DWORD), ("index_low", w.DWORD)]
        self.FileInfo = FileInfo

    def api(self, dll, name, result, types):
        function = getattr(dll, name)
        function.restype, function.argtypes = result, types
        return function

    @staticmethod
    def ticks(value):
        return value.dwLowDateTime | value.dwHighDateTime << 32

    def now(self):
        value = self.w.FILETIME()
        self.api(self.k, "GetSystemTimePreciseAsFileTime", None, [self.c.c_void_p])(self.c.byref(value))
        return self.ticks(value)

    def local_appdata(self):
        buffer = self.c.create_unicode_buffer(260)
        result = self.api(self.shell, "SHGetFolderPathW", self.c.c_long,
                          [self.w.HWND, self.c.c_int, self.w.HANDLE, self.w.DWORD, self.w.LPWSTR])(
                              None, 0x001C, None, 0, buffer)  # No CSIDL_FLAG_CREATE.
        isolated(result == 0, "LOCAL_APPDATA_IDENTITY_UNPROVEN")
        windows_path(buffer.value)
        return buffer.value

    def close(self, handle):
        isolated(self.api(self.k, "CloseHandle", self.w.BOOL, [self.w.HANDLE])(handle), "HANDLE_CLOSE_FAILED")

    def sid_text(self, sid):
        text = self.w.LPWSTR()
        isolated(self.api(self.a, "ConvertSidToStringSidW", self.w.BOOL,
                          [self.c.c_void_p, self.c.c_void_p])(sid, self.c.byref(text)), "SID_UNPROVEN")
        try:
            return text.value
        finally:
            self.api(self.k, "LocalFree", self.c.c_void_p, [self.c.c_void_p])(self.c.cast(text, self.c.c_void_p))

    def security(self, handle):
        import struct
        c, w = self.c, self.w
        owner, acl, descriptor = c.c_void_p(), c.c_void_p(), c.c_void_p()
        status = self.api(self.a, "GetSecurityInfo", w.DWORD,
                          [w.HANDLE, c.c_int, w.DWORD] + [c.c_void_p] * 5)(
                              handle, 1, 5, c.byref(owner), None, c.byref(acl), None, c.byref(descriptor))
        isolated(status == 0 and descriptor.value, "AGENT_SECURITY_UNPROVEN")
        try:
            isolated(owner.value and acl.value and self.sid_text(owner) == self.sid, "AGENT_OWNER_MISMATCH")
            revision, _, size, count, _ = struct.unpack("<BBHHH", c.string_at(acl, 8))
            isolated(revision in (2, 4) and 8 <= size <= 65535 and count <= 128, "AGENT_ACL_UNPROVEN")
            writable = 0x2 | 0x4 | 0x10 | 0x40 | 0x100 | 0x10000 | 0x40000 | 0x80000 | 0x40000000 | 0x10000000
            for index in range(count):
                ace = c.c_void_p()
                isolated(self.api(self.a, "GetAce", w.BOOL, [c.c_void_p, w.DWORD, c.c_void_p])(
                    acl, index, c.byref(ace)), "AGENT_ACL_UNPROVEN")
                kind, _, length, mask = struct.unpack("<BBHI", c.string_at(ace, 8))
                isolated(kind in (0, 1) and 12 <= length <= size, "AGENT_ACL_UNPROVEN")
                if kind == 0 and mask & writable:
                    principal = self.sid_text(c.c_void_p(ace.value + 8))
                    isolated(principal in (self.sid, "S-1-5-18", "S-1-5-32-544"), "AGENT_SHARED_WRITE_ACCESS")
            return sha(self.sid.encode("ascii") + c.string_at(acl, size))
        finally:
            self.api(self.k, "LocalFree", c.c_void_p, [c.c_void_p])(descriptor)

    def inspect(self, value, *, directory=False, read=False):
        c, w = self.c, self.w
        windows_path(value)
        path = self.module.native_path(value, directory=directory)
        access = 0x20080 | (0x80000000 if read else 0)  # READ_CONTROL, attributes, optional data.
        handle = self.api(self.k, "CreateFileW", w.HANDLE,
                          [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE])(
                              value, access, 3, None, 3, 0x02200000, None)
        isolated(handle not in (None, c.c_void_p(-1).value), "AGENT_FILESYSTEM_IDENTITY_UNPROVEN")
        try:
            info = self.FileInfo()
            get_info = self.api(self.k, "GetFileInformationByHandle", w.BOOL, [w.HANDLE, c.c_void_p])
            isolated(get_info(handle, c.byref(info)), "AGENT_FILESYSTEM_IDENTITY_UNPROVEN")
            buffer = c.create_unicode_buffer(1024)
            size = self.api(self.k, "GetFinalPathNameByHandleW", w.DWORD,
                            [w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD])(handle, buffer, len(buffer), 0)
            isolated(0 < size < len(buffer) and buffer.value == "\\\\?\\" + value,
                     "AGENT_CANONICAL_PATH_MISMATCH")
            index = info.index_low | info.index_high << 32
            isolated(not info.attributes & 0x400 and bool(info.attributes & 0x10) == directory
                     and index != 0 and info.volume != 0 and (directory or info.links == 1)
                     and path.lstat().st_ino == index, "AGENT_FILESYSTEM_IDENTITY_UNPROVEN")
            result = {"file_id": [info.volume, index], "created": self.ticks(info.creation),
                      "security_sha256": self.security(handle)}
            if not read:
                return result
            isolated(not directory and info.size_high == 0 and 0 < info.size_low <= 128,
                     "AGENT_ENDPOINT_FORMAT_REJECTED")
            body, count = c.create_string_buffer(129), w.DWORD()
            isolated(self.api(self.k, "ReadFile", w.BOOL,
                              [w.HANDLE, c.c_void_p, w.DWORD, c.c_void_p, c.c_void_p])(
                                  handle, body, len(body), c.byref(count), None)
                     and count.value == info.size_low, "AGENT_ENDPOINT_CHANGED")
            after = self.FileInfo()
            def stable(value):
                # Reading may update access time; identity, content-write time,
                # size, attributes and link count must remain unchanged.
                return (value.attributes, self.ticks(value.creation), self.ticks(value.write),
                        value.volume, value.size_high, value.size_low, value.links,
                        value.index_high, value.index_low)
            isolated(get_info(handle, c.byref(after)) and stable(info) == stable(after)
                     and self.module.native_path(value).lstat().st_ino == index, "AGENT_ENDPOINT_CHANGED")
            return result, body.raw[:count.value]
        finally:
            self.close(handle)

    def endpoint(self, value):
        return self.inspect(value, read=True)

    @staticmethod
    def exists(value):
        try:
            Path(value).lstat()  # exists() may hide permission/metadata errors.
            return True
        except FileNotFoundError:
            return False

    @staticmethod
    def mkdir(value):
        Path(value).mkdir(exist_ok=False)

    @staticmethod
    def children(value):
        with os.scandir(value) as entries:
            names = []
            for entry in entries:
                names.append(entry.name)
                isolated(len(names) <= 8, "AGENT_UNEXPECTED_CONTENTS")
            return names

    def spawn(self, argv, binary_hash):
        import subprocess
        import threading
        isolated(sha(self.module.native_path(argv[0]).read_bytes()) == binary_hash, "TOOL_CHANGED")
        process = subprocess.Popen(argv, cwd=self.child, env=self.env, shell=False, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        process.h3_output = [bytearray(), bytearray()]
        process.h3_overflow = threading.Event()
        process.h3_readers = []
        return process

    @staticmethod
    def begin_capture(process):
        import threading

        def drain(pipe, target):
            try:
                while block := pipe.read(1024):
                    target.extend(block[:max(0, 16384 - len(target))])
                    if len(target) >= 16384:
                        process.h3_overflow.set()
                        return
            except OSError:
                process.h3_overflow.set()

        # The caller already retains and has identified the launch handle.
        # A thread-start error must not discard it or authorize path cleanup.
        try:
            for pipe, target in zip((process.stdout, process.stderr), process.h3_output, strict=True):
                reader = threading.Thread(target=drain, args=(pipe, target), daemon=True)
                reader.start()
                process.h3_readers.append(reader)
        except Exception:
            process.h3_overflow.set()
            raise

    def process_identity(self, process):
        c, w = self.c, self.w
        isolated(process.poll() is None, "AGENT_PROCESS_EXITED")
        # Popen retains the exact CreateProcess handle: never open a numeric PID.
        handle = int(process._handle)
        pid = self.api(self.k, "GetProcessId", w.DWORD, [w.HANDLE])(handle)
        isolated(pid > 0, "AGENT_IDENTITY_UNPROVEN")
        buffer, length = c.create_unicode_buffer(1024), w.DWORD(1024)
        isolated(self.api(self.k, "QueryFullProcessImageNameW", w.BOOL,
                          [w.HANDLE, w.DWORD, w.LPWSTR, c.c_void_p])(handle, 0, buffer, c.byref(length)),
                 "AGENT_IDENTITY_UNPROVEN")
        times = [w.FILETIME() for _ in range(4)]
        isolated(self.api(self.k, "GetProcessTimes", w.BOOL, [w.HANDLE] + [c.c_void_p] * 4)(
            handle, *(c.byref(value) for value in times)), "AGENT_IDENTITY_UNPROVEN")
        token, size = w.HANDLE(), w.DWORD()
        isolated(self.api(self.a, "OpenProcessToken", w.BOOL, [w.HANDLE, w.DWORD, c.c_void_p])(
            handle, 8, c.byref(token)), "AGENT_IDENTITY_UNPROVEN")
        try:
            get_token = self.api(self.a, "GetTokenInformation", w.BOOL,
                                 [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p])
            get_token(token, 1, None, 0, c.byref(size))
            isolated(0 < size.value <= 4096, "AGENT_IDENTITY_UNPROVEN")
            data = c.create_string_buffer(size.value)
            isolated(get_token(token, 1, data, len(data), c.byref(size)), "AGENT_IDENTITY_UNPROVEN")
            sid = self.sid_text(c.c_void_p.from_buffer(data))
        finally:
            self.close(token)
        return {"pid": pid, "path": buffer.value, "sid": sid, "created": self.ticks(times[0])}

    def listeners(self):
        import ipaddress
        import struct
        c, w = self.c, self.w
        get_table = self.api(self.ip, "GetExtendedTcpTable", w.DWORD,
                             [c.c_void_p, c.c_void_p, w.BOOL, w.DWORD, c.c_int, w.DWORD])
        rows = []
        for family, width in ((2, 24), (23, 56)):
            size = w.DWORD()
            isolated(get_table(None, c.byref(size), False, family, 3, 0) == 122
                     and 4 <= size.value <= 1048576, "AGENT_LISTENER_METADATA_UNAVAILABLE")
            table = c.create_string_buffer(size.value)
            isolated(get_table(table, c.byref(size), False, family, 3, 0) == 0,
                     "AGENT_LISTENER_METADATA_UNAVAILABLE")
            count = struct.unpack_from("<I", table)[0]
            isolated(count <= 8192 and 4 + count * width <= size.value <= len(table), "AGENT_LISTENER_METADATA_UNAVAILABLE")
            for offset in range(4, 4 + count * width, width):
                if family == 2:
                    state, address, port, _, _, pid = struct.unpack_from("<6I", table, offset)
                    address = str(ipaddress.IPv4Address(struct.pack("<I", address)))
                else:
                    address = str(ipaddress.IPv6Address(table.raw[offset:offset + 16]))
                    port = struct.unpack_from("<I", table, offset + 20)[0]
                    state, pid = struct.unpack_from("<II", table, offset + 48)
                isolated(state == 2 and port <= 65535, "AGENT_LISTENER_METADATA_UNAVAILABLE")
                rows.append((address, (port & 255) << 8 | port >> 8, pid))
        return rows

    @staticmethod
    def poll(process):
        return process.poll()

    @staticmethod
    def healthy(process):
        return not process.h3_overflow.is_set()

    @staticmethod
    def terminate(process):
        process.terminate()  # TerminateProcess on the retained handle; no Agent command/cleanup.
        process.wait(timeout=5)

    def capture(self, process):
        for reader in process.h3_readers:
            reader.join(timeout=1)
        isolated(not any(reader.is_alive() for reader in process.h3_readers), "AGENT_OUTPUT_UNAVAILABLE")
        for pipe in (process.stdout, process.stderr):
            pipe.close()
        return self.module.ToolResult(process.returncode, *(bytes(part) for part in process.h3_output))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=["approval-native-only"])
    parser.add_argument("--diagnostic", required=True, choices=["debug"])
    parser.add_argument("--scratch-parent", required=True)
    parser.add_argument("--expected-sid", required=True)
    parser.add_argument("--expected-snapshot", required=True)
    parser.add_argument("--expected-python-sha256", required=True)
    parser.add_argument("--allow-isolated-test-agent", action="store_true")
    for tool in ("gpg", "gpgv", "gpg-agent", "gpgconf"):
        parser.add_argument("--" + tool, required=True)
        parser.add_argument("--" + tool + "-sha256", required=True)
    args = parser.parse_args(argv)
    if os.name != "nt" or sys.flags.optimize or not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("REQUIRES_WINDOWS_ISOLATED_NONOPTIMIZED_PYTHON")
    if not args.allow_isolated_test_agent:
        raise RuntimeError("ISOLATED_TEST_AGENT_NOT_APPROVED")
    repo = Path(__file__).resolve().parents[1]
    manifest = source_manifest(repo)
    if sha(json_bytes(manifest)) != args.expected_snapshot or sha(Path(sys.executable).read_bytes()) != args.expected_python_sha256:
        raise RuntimeError("SOURCE_OR_PYTHON_PIN_MISMATCH")
    m = load_product(repo)
    tools, identities = {}, {}
    for name in ("gpg", "gpgv", "gpg-agent", "gpgconf"):
        path = m.native_path(getattr(args, name.replace("-", "_")))
        expected = getattr(args, name.replace("-", "_") + "_sha256")
        if path.name.lower() != name + ".exe" or not m.digest(expected) or sha(path.read_bytes()) != expected:
            raise RuntimeError("TOOL_PIN_MISMATCH")
        tools[name] = str(path)
        identities[name] = {"sha256": expected, "bytes": path.stat().st_size, "basename": path.name}
    # Metadata and the directly launched agent must use one pinned installation.
    if len({str(Path(value).parent) for value in tools.values()}) != 1:
        raise RuntimeError("INCONSISTENT_TOOL_INSTALLATION")
    import ctypes
    if ctypes.windll.shell32.IsUserAnAdmin():
        raise RuntimeError("ADMINISTRATOR_TOKEN_FORBIDDEN")
    system = Path(os.environ["SystemRoot"])
    identity = m.bounded_process([str(system / "System32/whoami.exe"), "/user", "/fo", "csv", "/nh"],
                                 cwd=str(repo), env={"SystemRoot": str(system)}, timeout=5)
    sids = re.findall(rb"S-1-5-[0-9-]+", identity.status)
    if identity.returncode != 0 or len(sids) != 1 or sids[0].decode("ascii") != args.expected_sid:
        raise RuntimeError("WINDOWS_PRINCIPAL_MISMATCH")
    io = WindowsAgentIO(m, args.expected_sid, {}, repo)
    local_appdata = io.local_appdata()
    if os.environ.get("LOCALAPPDATA") != local_appdata:
        raise RuntimeError("LOCAL_APPDATA_IDENTITY_UNPROVEN")
    parent = Path(args.scratch_parent)
    required_parent = Path(local_appdata) / "ChromeProject-H3-Approval-Qualification"
    if args.scratch_parent != str(required_parent) or len(str(parent)) > 130:
        raise RuntimeError("UNAPPROVED_PARENT")
    m.native_path(str(parent if parent.exists() else parent.parent), directory=True)
    child = parent / ("auth-" + uuid.uuid4().hex)
    home, verification_root = child / "test-gnupg", child / "verification"
    print("Mode: approval-native-only; diagnostic: debug; non-administrator token")
    print("Actual SID:", args.expected_sid)
    print("Disposable parent:", parent)
    print("New test home:", home)
    print("Derived socket directory:", derived_socket_directory(str(home), local_appdata))
    print("Source manifest SHA256:", args.expected_snapshot)
    print("Only synthetic fixtures and disposable TEST ONLY keys; isolated test agent; no personal keys or tokens.")
    print("Confirm this identity and dedicated parent are approved and contain no production data.")
    if input("Type APPROVE before filesystem or cryptographic mutation: ") != "APPROVE":
        raise RuntimeError("OPERATOR_DID_NOT_APPROVE")

    parent.mkdir(exist_ok=True)
    m.native_path(str(parent), directory=True)
    child.mkdir(exist_ok=False)
    home.mkdir()
    verification_root.mkdir()
    env = {"SystemRoot": str(system), "GNUPGHOME": str(home), "HOME": str(home),
           "TEMP": str(child), "TMP": str(child)}
    summaries, results = [], {}
    io.env, io.child = dict(env), str(child)
    agent = IsolatedAgent(str(home), local_appdata, tools["gpg-agent"], identities["gpg-agent"]["sha256"],
                          args.expected_sid, io)

    def run(name, options, *, ok=True):
        if sha(m.native_path(tools[name]).read_bytes()) != identities[name]["sha256"]:
            raise RuntimeError("TOOL_CHANGED")
        uses_agent = name == "gpg" and "--version" not in options
        if uses_agent:
            isolated(options[:len(gpg)] == gpg, "AGENT_CLIENT_OPTIONS_REJECTED")
            agent.authorize()
        r = m.bounded_process([tools[name], *options], cwd=str(child), env=env, timeout=30)
        record_process(child, summaries, name, r)
        if uses_agent:
            agent.authorize()
        if ok and r.returncode != 0:
            raise RuntimeError("NATIVE_TOOL_FAILED")
        return r

    def verification_runner(argv, **options):
        r = m.bounded_process(argv, **options)
        record_process(child, summaries, "gpgv", r)
        return r

    def mark(name, condition, **facts):
        if not condition:
            raise RuntimeError("NATIVE_CHECK_FAILED_" + name.upper())
        results[name] = {"status": "PASS", **facts}

    try:
        # Observe absence and create the directory ourselves BEFORE gpgconf
        # can create it as a pathname-query side effect. No pre-existing d.*
        # directory is adopted, even when empty.
        agent.prepare()
        for name in tools:
            options = ["--homedir", str(home), "--version"]
            if name in ("gpg", "gpg-agent"):
                options.insert(0, "--no-options")
            r = run(name, options)
            first = r.status.decode("ascii", "replace").splitlines()[0]
            identities[name]["version_line"] = first[:160]
        conf = ["--homedir", str(home)]
        reports = {key: run("gpgconf", conf + ["--list-dirs", key]).status for key in agent.expected_paths()}
        from urllib.parse import unquote
        components = run("gpgconf", conf + ["--list-components"]).status.decode("utf-8").splitlines()
        agents = [unquote(line.split(":", 2)[2], errors="strict") for line in components if line.startswith("gpg-agent:")]
        if len(agents) != 1 or agents[0] != tools["gpg-agent"]:
            raise RuntimeError("AGENT_BINARY_NOT_PINNED")
        agent.bind(reports, {name: entry["version_line"] for name, entry in identities.items()})
        # Windows 2.4.8 runs this daemon in the created process (no Unix fork).
        # Retain that handle; gpgconf launch would lose this ownership binding.
        agent.start()
        for _ in range(100):
            if agent.ready():
                break
            time.sleep(0.05)
        else:
            raise RuntimeError("AGENT_STARTUP_TIMEOUT")
        agent.evidence["events"].append({"stage": "before_first_connection", "time": io.now(),
                                         "socket_identity_verified": True})
        gpg = ["--no-options", "--homedir", str(home), "--no-autostart", "--batch", "--no-tty",
               "--pinentry-mode", "loopback", "--passphrase=", "--no-auto-key-retrieve", "--auto-key-locate", "clear"]
        fprs = {}
        for role in ("write", "restore", "absent"):
            r = run("gpg", gpg + ["--status-fd", "1", "--quick-generate-key",
                    f"H3 A4 TEST ONLY {role} <h3-a4-{role}@example.invalid>", "ed25519", "sign", "1d"])
            created = re.findall(rb"(?m)^\[GNUPG:\] KEY_CREATED P ([0-9A-F]{40})\r?$", r.status)
            if len(created) != 1:
                raise RuntimeError("TEST_KEY_CREATION_AMBIGUOUS")
            fprs[role] = created[0].decode("ascii")
        export = run("gpg", gpg + ["--export", fprs["write"], fprs["restore"]]).status
        tags = m.packet_tags(export, m.MAX_KEYRING)
        if tags.count(6) != 2 or any(tag not in (2, 6, 13, 14, 17) for tag in tags):
            raise RuntimeError("EXPORT_NOT_PUBLIC_ONLY")
        emit_new(child / "public.gpg", export)
        issued = (datetime.now(timezone.utc) - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        policy = policy_fixture(m, sha(export), fprs["write"], fprs["restore"], issued)
        approvals, signatures = {}, {}
        for role in ("write", "restore"):
            approvals[role] = fixture(m, role, issued)
            emit_new(child / (role + ".approval"), approvals[role])
        for label, role, signer in (("write", "write", "write"), ("restore", "restore", "restore"),
                                    ("wrong", "write", "restore"), ("absent", "write", "absent")):
            sigpath = child / (label + ".sig")
            run("gpg", gpg + ["--local-user", fprs[signer] + "!", "--digest-algo", "SHA256",
                               "--output", str(sigpath), "--detach-sign", str(child / (role + ".approval"))])
            signatures[label] = sigpath.read_bytes()
        backend = m.NativeGpgvBackend(executable=tools["gpgv"], executable_sha256=identities["gpgv"]["sha256"],
                                     public_keyring=export, scratch_root=str(verification_root), approved_test_only=True,
                                     runner=verification_runner)
        clock = lambda: (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), time.monotonic_ns() // 1000000)

        def auth(p=None, b=backend, guard=None):
            raw = m.canonical_json(policy if p is None else p)
            return m.ApprovalAuthenticator(b, raw, expected_policy_id="test-only-policy-v1",
                expected_policy_sha256=sha(raw), clock=clock, replay_guard=guard or m.ReviewReplayGuard())

        def evaluate(role="write", body=None, sig=None, p=None):
            return auth(p).evaluate(approvals[role] if body is None else body,
                                    signatures[role] if sig is None else sig, f"single_float32_{role}_once")

        for role in ("write", "restore"):
            r = evaluate(role)
            mark("exact_" + role + "_signature", r.status == m.PASS and r.signature_verified,
                 approval_sha256=r.approval_sha256, signature_sha256=r.detached_signature_sha256)
        corrupted = signatures["write"][:-1] + bytes([signatures["write"][-1] ^ 1])
        mark("corrupted_signature", evaluate(sig=corrupted).status == "REJECTED")
        mutated = approvals["write"].replace(b"test-write-one", b"test-write-onf")
        mark("one_byte_approval_mutation", evaluate(body=mutated).status == "REJECTED")
        mark("wrong_signer", evaluate(sig=signatures["wrong"]).failure_class == "SIGNER_MISMATCH")
        mark("absent_signer", evaluate(sig=signatures["absent"]).failure_class == "CRYPTO_REJECTED")
        only_write = {**policy, "signers": [policy["signers"][0]]}
        mark("role_mismatch", evaluate("restore", p=only_write).failure_class == "ROLE_REJECTED")
        malformed = {**policy, "trusted": True}
        try:
            auth(malformed)
        except m.AuthError:
            mark("malformed_policy", True)
        else:
            raise RuntimeError("MALFORMED_POLICY_ACCEPTED")
        mark("duplicate_signature_packets", evaluate(sig=signatures["write"] * 2).status == "REJECTED")
        native = backend.verify(approvals["write"], signatures["write"])
        class ExtraStatus:
            review_only, keyring_sha256 = True, sha(export)

            def verify(self, body, sig):
                return m.ToolResult(native.returncode, native.status + native.status, native.diagnostics)

        ambiguous = auth(b=ExtraStatus()).evaluate(approvals["write"], signatures["write"], m.ACTIONS[0])
        mark("ambiguous_status_injected", ambiguous.status == "REJECTED", mode="injected-after-real-gpgv")
        # A new gpgv process directly reads retained fixed files. No filesystem
        # creation by this repeat verification; compare input hashes afterward.
        readhome = child / "readonly-home"
        readhome.mkdir()
        fixed = (child / "public.gpg", child / "write.sig", child / "write.approval")
        before = {p.name: sha(p.read_bytes()) for p in fixed}
        r = run("gpgv", ["--homedir", str(readhome), "--keyring", str(fixed[0]), "--status-fd", "1",
                          "--weak-digest", "SHA1", "--", str(fixed[1]), str(fixed[2])])
        parsed = m.parse_policy(m.canonical_json(policy), policy["policy_id"], sha(m.canonical_json(policy)))
        m.verify_status(r, parsed.signers[0], m.utc(issued), m.utc(issued) + 120, m.utc(clock()[0]))
        mark("fresh_process_readonly_verification", before == {p.name: sha(p.read_bytes()) for p in fixed}
             and not list(readhome.iterdir()), input_hashes=before)
        guard = m.ReviewReplayGuard()
        first = auth(guard=guard).evaluate(approvals["write"], signatures["write"], m.ACTIONS[0])
        second = auth(guard=guard).evaluate(approvals["write"], signatures["write"], m.ACTIONS[0])
        mark("replay_rejected", first.status == m.PASS and second.failure_class == "REPLAY_REJECTED")
        revoked = {**policy, "signers": [{**policy["signers"][0], "revoked": True}, policy["signers"][1]]}
        mark("revoked_policy", evaluate(p=revoked).failure_class == "SIGNER_INACTIVE", mode="independent-policy")
        expired = policy_fixture(m, sha(export), fprs["write"], fprs["restore"], "2020-01-01T12:00:00Z")
        mark("expired_policy", evaluate(p=expired).failure_class == "STALE_POLICY", mode="independent-policy")
        mark("test_keys_not_production", all(getattr(first, k) is False for k in
             ("write_ready", "handoff_write_ready", "write_attempted", "restore_attempted"))
             and first.authorization_status == "NOT_PRODUCTION_AUTHORIZED"
             and first.memory_read_attempts == first.memory_write_attempts == 0,
             production_constructor=False, key_purpose="TEST_ONLY_REVIEW")
        mark("source_integrity", source_manifest(repo) == manifest)
    finally:
        try:
            if agent.process is not None:
                mark("isolated_agent_stopped", agent.stop(), method="retained_process_handle",
                     artifacts="RETAINED_NO_UNLINK")
        finally:
            try:
                if agent.process is not None and io.poll(agent.process) is not None:
                    record_process(child, summaries, "gpg-agent-direct", io.capture(agent.process))
                    isolated(io.healthy(agent.process), "AGENT_OUTPUT_LIMIT")
            finally:
                emit_new(child / "partial-agent-isolation.json", json_bytes(agent.evidence))
                emit_new(child / "partial-results.json", json_bytes(results))
                emit_new(child / "partial-subprocess-summaries.json", json_bytes(summaries))

    qualify(results)
    for name, path in tools.items():
        if sha(m.native_path(path).read_bytes()) != identities[name]["sha256"]:
            raise RuntimeError("TOOL_CHANGED_AFTER_RUN")
    reports = {
        "native-results.json": json_bytes(results),
        "binary-identity.json": json_bytes({"tools": identities, "python_sha256": args.expected_python_sha256}),
        "test-keyring.json": json_bytes({"sha256": sha(export), "bytes": len(export), "packet_tags": tags,
                                         "fingerprints": fprs, "purpose": "TEST_ONLY_REVIEW", "public_only": True}),
        "source-manifest.json": json_bytes(manifest),
        "subprocess-summaries.json": json_bytes(summaries),
        "agent-isolation.json": json_bytes(agent.evidence),
        # Only these explicitly synthetic public fixtures are exportable. No
        # directory recursion and no private-key, socket or agent files.
        "public.gpg": export,
        "synthetic-write.approval": approvals["write"],
        "synthetic-restore.approval": approvals["restore"],
        "synthetic-write.sig": signatures["write"],
        "synthetic-restore.sig": signatures["restore"],
        "synthetic-wrong-signer.sig": signatures["wrong"],
        "synthetic-absent-signer.sig": signatures["absent"],
        "test-policy.json": m.canonical_json(policy),
    }
    receipt = {"status": LABEL, "parent_exit_code": 0, "required_checks": sorted(REQUIRED),
               "passed": len(results), "mode": args.mode, "diagnostic": args.diagnostic,
               "source_manifest_sha256": args.expected_snapshot, "run_id": child.name,
               "sid_sha256": sha(args.expected_sid.encode("ascii")), "parent_sha256": sha(str(parent).encode("utf-8")),
               "administrator": False, "isolated_test_agent_only": True,
               "authorization_status": "NOT_PRODUCTION_AUTHORIZED", "write_ready": False, "handoff_write_ready": False,
               "memory_read_attempts": 0, "memory_write_attempts": 0, "production_switch_enabled": False,
               "reports": {name: {"bytes": len(body), "sha256": sha(body)} for name, body in reports.items()}}
    reports["native-receipt.json"] = json_bytes(receipt)
    for name, body in reports.items():
        if name == "public.gpg":
            if (child / name).read_bytes() != body:
                raise RuntimeError("PUBLIC_KEYRING_CHANGED")
        else:
            emit_new(child / name, body)
    archive = child / "native-auth-bundle.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, body in reports.items():
            bundle.writestr(name, body)
    with zipfile.ZipFile(archive) as bundle:
        if set(bundle.namelist()) != set(reports) or any(bundle.read(n) != b for n, b in reports.items()):
            raise RuntimeError("ZIP_READBACK_FAILED")
    print(LABEL)
    print("ZIP:", archive)
    print("ZIP SHA256:", sha(archive.read_bytes()))
    print("native-parent-exit-code=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        # No exception body, subprocess UID or raw private fixture is exported.
        code = str(error) if re.fullmatch(r"[A-Z][A-Z0-9_]{0,100}", str(error)) else type(error).__name__
        print("BLOCKED_HANDOFF_H3_A4_T1_" + code, file=sys.stderr)
        print("native-parent-exit-code=1", file=sys.stderr)
        raise SystemExit(1) from None
