"""Inactive, review-only H3 approval authentication; no execution integration.

All roots, time, replay state and verification dependencies come from a trusted
bootstrap. Nothing is discovered at import or selected by an approval. A matching
signature is never owner authority. See h3_approval_auth_contract.md.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import struct
import threading
import weakref


MAX_APPROVAL = 16384
MAX_SIGNATURE = 16384
MAX_OUTPUT = 16384
MAX_KEYRING = 65536
AUTHORITY = "synthetic-authority"
DOMAIN = "h3-synthetic-tests-v1"
COMMON_FIELDS = tuple("schema source_kind environment request_id authority trust_domain action "
                      "case_id session_id candidate_address current_float current_pattern "
                      "target_float target_pattern pid process_created_utc executable architecture "
                      "attachment_id scene_id issued_utc expires_utc max_elapsed_ms".split())
SOURCE_NAMES = ("h1_log", "h1_summary", "h1_diagnostic", "h1_companion", "h2", "a1")
WRITE_FIELDS = COMMON_FIELDS + ("source_batch_id", "source_case_id", "source_session_id") + tuple(
    field for name in SOURCE_NAMES for field in (name + "_id", name + "_sha256"))
RESTORE_FIELDS = COMMON_FIELDS + ("source_request_id", "source_preparation_sha256", "source_receipt_sha256")
ACTIONS = ("single_float32_write_once", "single_float32_restore_once")
PASS = "SIGNATURE_AND_POLICY_MATCH_REVIEW_ONLY"


class AuthError(Exception):
    """Bounded reason only. Never expose subprocess/approval/exception text."""


def require(condition, code):
    if not condition:
        raise AuthError(code)


def sha256(body):
    return hashlib.sha256(body).hexdigest()


def canonical_json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def token(value):
    return type(value) is str and re.fullmatch(r"[a-z][a-z0-9-]{0,63}", value) is not None and not value.endswith("-")


def digest(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def fingerprint(value):
    # Deliberately qualify v4 fingerprints only; no truncation/case folding.
    return type(value) is str and re.fullmatch(r"[0-9A-F]{40}", value) is not None and value != "0" * 40


def utc(value):
    require(type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value),
            "INVALID_TIME")
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        raise AuthError("INVALID_TIME") from None
    require(result.year >= 1970, "INVALID_TIME")
    return int((result - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds())


def decimal(value, low, high):
    require(type(value) is str and re.fullmatch(r"0|[1-9][0-9]{0,15}", value), "INVALID_APPROVAL")
    n = int(value)
    require(low <= n <= high, "INVALID_APPROVAL")
    return n


def parse_approval(body, action):
    require(type(action) is str and action in ACTIONS, "INVALID_ACTION")
    require(type(body) is bytes and 0 < len(body) <= MAX_APPROVAL and body.endswith(b"\r\n"), "INVALID_APPROVAL")
    require(all(32 <= c <= 126 for c in body.replace(b"\r\n", b"")), "INVALID_APPROVAL")
    fields = WRITE_FIELDS if action == ACTIONS[0] else RESTORE_FIELDS
    lines = body[:-2].split(b"\r\n")
    require(len(lines) == len(fields), "INVALID_APPROVAL")
    values = {}
    for key, line in zip(fields, lines, strict=True):
        name, sep, value = line.partition(b"=")
        require(name == key.encode("ascii") and sep and 1 <= len(value) <= 512, "INVALID_APPROVAL")
        values[key] = value.decode("ascii")
    a = values
    role = "write" if action == ACTIONS[0] else "restore"
    require(a["schema"] == f"h3_{role}_approval_v1" and a["source_kind"] == "h3_single"
            and a["environment"] == "synthetic_only" and a["authority"] == AUTHORITY
            and a["trust_domain"] == DOMAIN and a["action"] == action, "INVALID_APPROVAL")
    require(all(token(a[k]) for k in ("request_id", "case_id", "session_id", "attachment_id", "scene_id")),
            "INVALID_APPROVAL")
    address = a["candidate_address"]
    require(re.fullmatch(r"0x[1-9A-F][0-9A-F]{0,13}", address) and int(address, 16) <= 0x1FFFFFFFFFFFFF,
            "INVALID_APPROVAL")
    for prefix in ("current", "target"):
        pattern, text = a[prefix + "_pattern"], a[prefix + "_float"]
        require(re.fullmatch(r"0x[0-9A-F]{8}", pattern), "INVALID_APPROVAL")
        value = struct.unpack("<f", struct.pack("<I", int(pattern, 16)))[0]
        require(math.isfinite(value) and len(text) <= 32 and format(value, ".17g") == text, "INVALID_APPROVAL")
    require(a["current_pattern"] != a["target_pattern"], "INVALID_APPROVAL")
    decimal(a["pid"], 1, 4294967295)
    require(a["architecture"] in ("x86", "x64"), "INVALID_APPROVAL")
    path = a["executable"]
    require(len(path) <= 260 and re.fullmatch(r"[A-Z]:\\[^:]+", path)
            and not any(x in path for x in ('..', '/', '\\\\', '<', '>', '|', '?', '*', '"'))
            and not path.endswith("\\"), "INVALID_APPROVAL")
    issued, expires = utc(a["issued_utc"]), utc(a["expires_utc"])
    require(0 < expires - issued <= 120 and utc(a["process_created_utc"]) <= issued, "INVALID_APPROVAL")
    decimal(a["max_elapsed_ms"], 1, 120000)
    for key in fields[len(COMMON_FIELDS):]:
        value = a[key]
        if key.endswith("_sha256"):
            require(digest(value), "INVALID_APPROVAL")
        else:
            require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value)
                    and "__" not in value and not value.endswith("_") and value != "nil", "INVALID_APPROVAL")
    if role == "write":
        require(len({a[n + "_id"] for n in SOURCE_NAMES}) == 6, "INVALID_APPROVAL")
    else:
        require(token(a["source_request_id"]) and a["source_request_id"] != a["request_id"], "INVALID_APPROVAL")
    return a


def packet_tags(body, maximum):
    """Bounded binary OpenPGP envelope check, NOT a cryptographic verifier.

    Definite lengths only. Reject armor, streaming/partial packets, truncation
    and secret-key packets. Cryptography always belongs to the pinned gpgv.
    """
    require(type(body) is bytes and 0 < len(body) <= maximum, "INVALID_PACKET")
    tags, pos = [], 0
    while pos < len(body):
        header = body[pos]
        pos += 1
        require(header & 128 and pos < len(body) and len(tags) < 64, "INVALID_PACKET")
        if header & 64:
            tag, length = header & 63, body[pos]
            pos += 1
            if 192 <= length < 224:
                require(pos < len(body), "INVALID_PACKET")
                length = ((length - 192) << 8) + body[pos] + 192
                pos += 1
            elif length == 255:
                require(pos + 4 <= len(body), "INVALID_PACKET")
                length = int.from_bytes(body[pos:pos + 4], "big")
                pos += 4
            else:
                require(length < 192, "INVALID_PACKET")
        else:
            tag, kind = (header >> 2) & 15, header & 3
            require(kind != 3, "INVALID_PACKET")
            size = 1 << kind
            require(pos + size <= len(body), "INVALID_PACKET")
            length = int.from_bytes(body[pos:pos + size], "big")
            pos += size
        require(length > 0 and pos + length <= len(body), "INVALID_PACKET")
        tags.append(tag)
        pos += length
    return tuple(tags)


@dataclass(frozen=True, slots=True)
class Signer:
    primary_fingerprint: str
    signing_fingerprint: str
    role: str
    valid_from: int
    valid_until: int
    revoked: bool


@dataclass(frozen=True, slots=True)
class Policy:
    policy_id: str
    sha256: str
    keyring_sha256: str
    valid_from: int
    valid_until: int
    revocation_checked: int
    revocation_valid_until: int
    signers: tuple


def parse_policy(body, expected_id, expected_hash):
    require(token(expected_id) and digest(expected_hash), "UNPINNED_POLICY")
    require(type(body) is bytes and 0 < len(body) <= 16384 and sha256(body) == expected_hash, "POLICY_PIN_MISMATCH")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "INVALID_POLICY")
            result[key] = value
        return result

    try:
        p = json.loads(body, object_pairs_hook=unique)
        require(type(p) is dict and canonical_json(p) == body, "INVALID_POLICY")
        require(set(p) == set("schema policy_id purpose authority trust_domain valid_from valid_until "
                              "revocation_checked_utc revocation_valid_until keyring_sha256 signers".split()), "INVALID_POLICY")
        require(p["schema"] == "h3_public_key_policy_v1" and p["policy_id"] == expected_id
                and p["purpose"] == "TEST_ONLY_REVIEW" and p["authority"] == AUTHORITY and p["trust_domain"] == DOMAIN
                and digest(p["keyring_sha256"]), "INVALID_POLICY")
        start, end = utc(p["valid_from"]), utc(p["valid_until"])
        checked, fresh = utc(p["revocation_checked_utc"]), utc(p["revocation_valid_until"])
        require(start <= checked < fresh <= end and fresh - checked <= 86400, "INVALID_POLICY")
        require(type(p["signers"]) is list and 1 <= len(p["signers"]) <= 2, "INVALID_POLICY")
        signers = []
        for s in p["signers"]:
            require(type(s) is dict and set(s) == set("primary_fingerprint signing_fingerprint role valid_from valid_until revoked".split()),
                    "INVALID_POLICY")
            require(fingerprint(s["primary_fingerprint"]) and fingerprint(s["signing_fingerprint"])
                    and s["role"] in ("write", "restore") and type(s["revoked"]) is bool, "INVALID_POLICY")
            begin, stop = utc(s["valid_from"]), utc(s["valid_until"])
            require(start <= begin < stop <= end, "INVALID_POLICY")
            signers.append(Signer(s["primary_fingerprint"], s["signing_fingerprint"], s["role"], begin, stop, s["revoked"]))
        # Rollover is an explicitly provisioned new policy, never a choice among
        # overlapping signers. Separate primary keys for write and restore.
        for key in ("primary_fingerprint", "signing_fingerprint", "role"):
            require(len({getattr(s, key) for s in signers}) == len(signers), "AMBIGUOUS_POLICY")
        return Policy(expected_id, expected_hash, p["keyring_sha256"], start, end, checked, fresh, tuple(signers))
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise AuthError("INVALID_POLICY") from None


@dataclass(frozen=True, slots=True)
class ToolResult:
    returncode: int
    status: bytes
    diagnostics: bytes = b""


def verify_status(result, signer, issued, expires, now):
    require(type(result) is ToolResult and type(result.returncode) is int and result.returncode == 0, "CRYPTO_REJECTED")
    require(type(result.status) is bytes and 0 < len(result.status) <= MAX_OUTPUT
            and type(result.diagnostics) is bytes and len(result.diagnostics) <= MAX_OUTPUT, "INVALID_STATUS")
    raw = result.status.replace(b"\r\n", b"\n")
    require(raw.endswith(b"\n") and all(c == 10 or 32 <= c <= 126 for c in raw), "INVALID_STATUS")
    lines = raw[:-1].split(b"\n")
    require(3 <= len(lines) <= 12, "INVALID_STATUS")
    seen, valid, signature_id = {}, None, None
    for line in lines:
        require(line.startswith(b"[GNUPG:] ") and len(line) <= 2048, "INVALID_STATUS")
        tag, _, args = line[9:].decode("ascii").partition(" ")
        seen[tag] = seen.get(tag, 0) + 1
        if tag == "KEY_CONSIDERED":
            require(seen[tag] <= 4 and args == signer.primary_fingerprint + " 0" and seen.get("NEWSIG") == 1,
                    "AMBIGUOUS_SIGNATURE")
        else:
            require(seen[tag] == 1, "AMBIGUOUS_SIGNATURE")
            if tag == "NEWSIG":
                require(len(seen) == 1 and args == "", "INVALID_STATUS")
            elif tag == "GOODSIG":
                key, sep, uid = args.partition(" ")
                require(seen.get("NEWSIG") == 1 and "VALIDSIG" not in seen and sep and uid
                        and key in (signer.signing_fingerprint, signer.signing_fingerprint[-16:]), "SIGNER_MISMATCH")
            elif tag == "VALIDSIG":
                require(seen.get("GOODSIG") == 1, "INVALID_STATUS")
                valid = args.split(" ")
                require(len(valid) == 10 and valid[0] == signer.signing_fingerprint
                        and valid[9] == signer.primary_fingerprint, "SIGNER_MISMATCH")
                require(valid[4:7] == ["4", "0", "22"] and valid[7] in ("8", "9", "10")
                        and valid[8] == "00", "CRYPTO_POLICY_REJECTED")
                created = decimal(valid[2], 0, 253402300799)
                expiry = decimal(valid[3], 0, 253402300799)
                require(utc(valid[1] + "T00:00:00Z") == created - created % 86400, "INVALID_STATUS")
                require(issued <= created < expires and signer.valid_from <= created < signer.valid_until
                        and created <= now and (expiry == 0 or created < expiry and now < expiry), "SIGNATURE_TIME_REJECTED")
            elif tag == "SIG_ID":
                signature_id = args.split(" ")
                require(seen.get("NEWSIG") == 1 and len(signature_id) == 3
                        and re.fullmatch(r"[A-Za-z0-9+/]{16,64}={0,2}", signature_id[0]), "INVALID_STATUS")
            else:
                # Includes BADSIG/ERRSIG/EXPSIG/EXPKEYSIG/REVKEYSIG/FAILURE,
                # unexpected plaintext/trust output and future status variants.
                raise AuthError("UNEXPECTED_STATUS")
    require(valid is not None and seen.get("NEWSIG") == seen.get("GOODSIG") == seen.get("VALIDSIG") == 1,
            "INVALID_STATUS")
    if signature_id:
        require(signature_id[1:] == valid[1:3], "INVALID_STATUS")


class ReviewReplayGuard:
    """Bounded process-local review consumption, not a durable execution ledger.

    Share this object across authenticators for the review session. A future
    durable policy service is a deployment gate; A3 is not silently used here.
    """

    def __init__(self):
        self._used, self._lock = set(), threading.Lock()

    def claim(self, policy_id, request_id, approval_hash, signature_hash):
        with self._lock:
            # Deliberately no policy-version reset or write/restore namespace split.
            if request_id in self._used or len(self._used) >= 4096:
                return False
            self._used.add(request_id)
            return True


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class ReviewResult:
    status: str
    failure_class: str
    approval_sha256: str
    detached_signature_sha256: str
    policy_sha256: str
    signature_verified: bool
    authorization_status: str = "NOT_PRODUCTION_AUTHORIZED"
    write_ready: bool = False
    handoff_write_ready: bool = False
    write_attempted: bool = False
    restore_attempted: bool = False
    memory_read_attempts: int = 0
    memory_write_attempts: int = 0


class ApprovalAuthenticator:
    """Explicit dependency injection; no defaults, discovery or production mode."""

    def __init__(self, verifier_backend, trust_policy, *, expected_policy_id,
                 expected_policy_sha256, clock, replay_guard):
        policy = parse_policy(trust_policy, expected_policy_id, expected_policy_sha256)
        require(getattr(verifier_backend, "review_only", None) is True
                and getattr(verifier_backend, "keyring_sha256", None) == policy.keyring_sha256, "UNPINNED_BACKEND")
        verify = getattr(verifier_backend, "verify", None)
        claim = getattr(replay_guard, "claim", None)
        require(callable(verify) and callable(clock) and callable(claim), "INVALID_DEPENDENCIES")
        self._policy, self._verify, self._clock, self._claim = policy, verify, clock, claim
        self._results, self._lock = weakref.WeakKeyDictionary(), threading.Lock()

    def _time(self, approval, signer):
        reading = self._clock()
        require(type(reading) is tuple and len(reading) == 2 and type(reading[1]) is int
                and 0 <= reading[1] <= 2**53 - 1, "CLOCK_REJECTED")
        now, mono = utc(reading[0]), reading[1]
        p = self._policy
        require(p.valid_from <= now < p.valid_until and p.revocation_checked <= now < p.revocation_valid_until,
                "STALE_POLICY")
        require(not signer.revoked and signer.valid_from <= now < signer.valid_until, "SIGNER_INACTIVE")
        require(utc(approval["issued_utc"]) <= now < utc(approval["expires_utc"]), "APPROVAL_NOT_CURRENT")
        return now, mono

    def evaluate(self, approval_bytes, detached_signature_bytes, action):
        ah = sha256(approval_bytes) if type(approval_bytes) is bytes and len(approval_bytes) <= MAX_APPROVAL else "nil"
        sh = sha256(detached_signature_bytes) if type(detached_signature_bytes) is bytes and len(detached_signature_bytes) <= MAX_SIGNATURE else "nil"
        failure = "nil"
        acquired = self._lock.acquire(blocking=False)
        try:
            require(acquired, "BUSY")
            a = parse_approval(approval_bytes, action)
            require(packet_tags(detached_signature_bytes, MAX_SIGNATURE) == (2,), "INVALID_SIGNATURE")
            role = "write" if action == ACTIONS[0] else "restore"
            matching = [s for s in self._policy.signers if s.role == role]
            require(len(matching) == 1, "ROLE_REJECTED")
            signer = matching[0]
            before = self._time(a, signer)
            # Even an uncertain verifier attempt consumes this review ID.
            require(self._claim(self._policy.policy_id, a["request_id"], ah, sh) is True, "REPLAY_REJECTED")
            result = self._verify(approval_bytes, detached_signature_bytes)
            after = self._time(a, signer)
            elapsed = after[1] - before[1]
            require(after[0] >= before[0] and 0 <= elapsed <= int(a["max_elapsed_ms"])
                    and abs((after[0] - before[0]) * 1000 - elapsed) <= 1000, "CLOCK_REJECTED")
            verify_status(result, signer, utc(a["issued_utc"]), utc(a["expires_utc"]), after[0])
        except AuthError as error:
            # Never trust the message of an injected exception, even AuthError.
            candidate = error.args[0] if type(error) is AuthError and len(error.args) == 1 and type(error.args[0]) is str else ""
            failure = candidate if candidate in _FAILURES else "DEPENDENCY_REJECTED"
        except Exception:
            failure = "DEPENDENCY_REJECTED"
        finally:
            if acquired:
                self._lock.release()
        value = ReviewResult(PASS if failure == "nil" else "REJECTED", failure, ah, sh,
                             self._policy.sha256, failure == "nil")
        public = asdict(value)
        self._results[value] = (tuple(public.values()), canonical_json(public))
        return value

    def render(self, result):
        """Only an original unchanged result is renderable. Copies are not grants."""
        try:
            if type(result) is ReviewResult:
                saved = self._results.get(result)
                if saved is not None:
                    current = tuple(getattr(result, key) for key in ReviewResult.__dataclass_fields__)
                    if all(type(a) is type(b) and a == b for a, b in zip(current, saved[0], strict=True)):
                        return saved[1]
        except Exception:
            pass
        return canonical_json(asdict(ReviewResult("REJECTED", "INVALID_RESULT", "nil", "nil", "nil", False)))


_FAILURES = frozenset("INVALID_TIME INVALID_APPROVAL INVALID_ACTION INVALID_PACKET INVALID_SIGNATURE "
                      "ROLE_REJECTED CLOCK_REJECTED STALE_POLICY SIGNER_INACTIVE APPROVAL_NOT_CURRENT "
                      "REPLAY_REJECTED BUSY CRYPTO_REJECTED INVALID_STATUS AMBIGUOUS_SIGNATURE "
                      "SIGNER_MISMATCH CRYPTO_POLICY_REJECTED SIGNATURE_TIME_REJECTED UNEXPECTED_STATUS "
                      "TOOL_TIMEOUT TOOL_OUTPUT_LIMIT TOOL_UNAVAILABLE TOOL_IDENTITY_CHANGED "
                      "INPUT_CHANGED NATIVE_PATH_REJECTED DEPENDENCY_REJECTED".split())


def bounded_process(args, *, cwd, env, timeout=10, output_limit=MAX_OUTPUT):
    """Only explicit trusted argv. Stream limits apply while the process runs."""
    import subprocess
    import time

    require(type(args) in (list, tuple) and 1 <= len(args) <= 40
            and all(type(x) is str and 0 < len(x) <= 1024 and "\0" not in x for x in args)
            and sum(map(len, args)) <= 8192, "TOOL_UNAVAILABLE")
    require(type(timeout) in (int, float) and 0 < timeout <= 60
            and type(output_limit) is int and 1 <= output_limit <= 65536, "TOOL_UNAVAILABLE")
    chunks = [bytearray(), bytearray()]
    overflow = threading.Event()
    try:
        with subprocess.Popen(args, cwd=cwd, env=env, shell=False, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as process:
            def read(pipe, target):
                try:
                    while True:
                        part = pipe.read(1024)
                        if not part:
                            return
                        target.extend(part[:max(0, output_limit + 1 - len(target))])
                        if len(target) > output_limit:
                            overflow.set()
                            return
                except OSError:
                    overflow.set()

            workers = [threading.Thread(target=read, args=(pipe, target), daemon=True)
                       for pipe, target in zip((process.stdout, process.stderr), chunks, strict=True)]
            for worker in workers:
                worker.start()
            deadline, failure = time.monotonic() + timeout, None
            while process.poll() is None:
                if overflow.wait(0.01):
                    failure = "TOOL_OUTPUT_LIMIT"
                    break
                if time.monotonic() >= deadline:
                    failure = "TOOL_TIMEOUT"
                    break
            if failure:
                process.kill()
            process.wait(timeout=5)
            for worker in workers:
                worker.join(timeout=1)
            require(not any(w.is_alive() for w in workers), "TOOL_TIMEOUT")
            require(not overflow.is_set(), "TOOL_OUTPUT_LIMIT")
            require(failure is None, failure or "TOOL_TIMEOUT")
            return ToolResult(process.returncode, bytes(chunks[0]), bytes(chunks[1]))
    except (OSError, subprocess.SubprocessError):
        raise AuthError("TOOL_UNAVAILABLE") from None


def native_path(value, *, directory=False):
    """Conservative local Windows paths; static guard, not a hostile-OS proof."""
    import os
    from pathlib import Path
    import stat

    require(os.name == "nt" and type(value) is str and len(value) <= 230
            and re.fullmatch(r"[A-Z]:\\[^<>|?*\x00-\x1f\"/:]+", value), "NATIVE_PATH_REJECTED")
    path = Path(value)
    require(str(path) == value, "NATIVE_PATH_REJECTED")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"{p}{n}" for p in ("COM", "LPT") for n in range(1, 10)}
    for component in path.parts[1:]:
        require(component not in (".", "..") and not component.endswith((".", " "))
                and "~" not in component and component.split(".")[0].upper() not in reserved, "NATIVE_PATH_REJECTED")
    for item in (*reversed(path.parents), path):
        info = item.lstat()
        require(not getattr(info, "st_file_attributes", 0) & 0x400, "NATIVE_PATH_REJECTED")
        if item == path and not directory:
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "NATIVE_PATH_REJECTED")
        else:
            require(stat.S_ISDIR(info.st_mode), "NATIVE_PATH_REJECTED")
    return path


class NativeGpgvBackend:
    """Offline public-only verification, explicitly test/review qualified only.

    No GnuPG defaults, key import, agent, network, shell or private-key operation.
    The bootstrap supplies pinned binary, public bytes and a disposable root.
    """

    review_only = True

    def __init__(self, *, executable, executable_sha256, public_keyring, scratch_root,
                 approved_test_only=False, runner=bounded_process):
        require(approved_test_only is True and digest(executable_sha256), "UNPINNED_BACKEND")
        tags = packet_tags(public_keyring, MAX_KEYRING)
        require(tags[0] == 6 and all(t in (2, 6, 13, 14, 17) for t in tags), "PUBLIC_KEYRING_REQUIRED")
        path = native_path(executable)
        require(path.name.lower() == "gpgv.exe" and sha256(path.read_bytes()) == executable_sha256, "TOOL_IDENTITY_CHANGED")
        root = native_path(scratch_root, directory=True)
        require(callable(runner), "INVALID_DEPENDENCIES")
        self._executable, self._binary_hash = str(path), executable_sha256
        self._keyring, self.keyring_sha256 = public_keyring, sha256(public_keyring)
        self._root, self._run = str(root), runner

    def verify(self, approval_bytes, signature_bytes):
        import os
        from pathlib import Path
        import tempfile

        require(type(approval_bytes) is bytes and 0 < len(approval_bytes) <= MAX_APPROVAL, "INVALID_APPROVAL")
        require(packet_tags(signature_bytes, MAX_SIGNATURE) == (2,), "INVALID_SIGNATURE")
        executable = native_path(self._executable)
        require(sha256(executable.read_bytes()) == self._binary_hash, "TOOL_IDENTITY_CHANGED")
        root = native_path(self._root, directory=True)
        child = Path(tempfile.mkdtemp(prefix="verify-", dir=root))
        home = child / "home"
        home.mkdir()
        originals = {"approval.bin": approval_bytes, "detached.sig": signature_bytes, "public.gpg": self._keyring}
        for name, body in originals.items():
            with (child / name).open("xb") as handle:
                require(handle.write(body) == len(body), "INPUT_CHANGED")
        # Do not inherit GNUPGHOME, agent sockets, home, proxy or loader overrides.
        env = {"GNUPGHOME": str(home), "TEMP": str(child), "TMP": str(child)}
        if "SystemRoot" in os.environ:
            env["SystemRoot"] = os.environ["SystemRoot"]
        args = (self._executable, "--homedir", str(home), "--keyring", str(child / "public.gpg"),
                "--status-fd", "1", "--weak-digest", "SHA1", "--", str(child / "detached.sig"), str(child / "approval.bin"))
        result = self._run(args, cwd=str(child), env=env, timeout=10, output_limit=MAX_OUTPUT)
        require(sha256(native_path(self._executable).read_bytes()) == self._binary_hash, "TOOL_IDENTITY_CHANGED")
        for name, body in originals.items():
            require(native_path(str(child / name)).read_bytes() == body, "INPUT_CHANGED")
        require(not list(home.iterdir()), "INPUT_CHANGED")
        return result
