"""Pure qsg.native-probe.v1 codec and offline session model; no native backend.

Canonical JSON here means sorted keys, compact separators, literal UTF-8,
minimal JSON escapes, and integer numbers (no floats). This is a versioned
profile, not a claim to implement every JSON canonicalization standard.
"""
from copy import deepcopy
import hashlib
import hmac
import json
import re
import struct

SCHEMA = "qsg.native-probe.v1"
MAX_BODY = 65536
METHODS = frozenset({"HELLO", "ECHO", "PING", "CANCEL", "CLOSE"})
FIELDS = frozenset({"schema", "origin", "kind", "method", "session_id", "channel_id",
                    "epoch", "request_id", "sequence", "payload", "request_sha256", "result"})
CORRELATION = ("session_id", "channel_id", "epoch", "request_id", "sequence")


class ProbeError(ValueError):
    """Only fixed, non-secret error codes cross the probe boundary."""


def require(condition, code):
    if not condition:
        raise ProbeError(code)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    def inspect(v, depth=0):
        require(depth <= 12, "JSON_DEPTH")
        if type(v) is dict:
            require(all(type(k) is str for k in v), "JSON_KEY")
            for item in v.values():
                inspect(item, depth + 1)
        elif type(v) is list:
            for item in v:
                inspect(item, depth + 1)
        else:
            require(v is None or type(v) in (str, int, bool), "JSON_TYPE")
    inspect(value)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (UnicodeError, ValueError, RecursionError):
        raise ProbeError("JSON_ENCODING") from None


def decode(raw):
    require(type(raw) is bytes, "JSON_BYTES")
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "DUPLICATE_KEY")
            out[key] = value
        return out
    def invalid(_):
        raise ProbeError("JSON_NUMBER")
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs,
                           parse_float=invalid, parse_constant=invalid)
        require(canonical(value) == raw, "NONCANONICAL_JSON")
        return value
    except ProbeError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise ProbeError("INVALID_JSON") from None


def identifier(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}", value), "IDENTIFIER")


def digest_string(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "SHA256")


def validate_message(value):
    require(type(value) is dict and set(value) == FIELDS, "MESSAGE_FIELDS")
    require(value["schema"] == SCHEMA and value["origin"] == "SYNTHETIC", "ORIGIN_OR_VERSION")
    require(type(value["method"]) is str and value["method"] in METHODS, "METHOD")
    require(value["kind"] in ("REQUEST", "RESPONSE"), "MESSAGE_KIND")
    for name in ("session_id", "channel_id", "request_id"):
        identifier(value[name])
    for name in ("epoch", "sequence"):
        require(type(value[name]) is int and 1 <= value[name] <= 2147483647, "INTEGER")
    require(type(value["payload"]) is str, "PAYLOAD")
    if value["kind"] == "REQUEST":
        require(value["request_sha256"] == "" and value["result"] == "", "REQUEST_FIELDS")
    else:
        digest_string(value["request_sha256"])
        expected = {"CANCEL": "CANCELLED", "CLOSE": "CLOSED"}.get(value["method"], "OK")
        require(value["result"] == expected, "RESPONSE_RESULT")
    if value["method"] != "ECHO":
        require(value["payload"] == "", "CONTROL_PAYLOAD")
    return value


def frame(value):
    validate_message(value)
    body = canonical(value)
    require(1 <= len(body) <= MAX_BODY, "FRAME_LENGTH")
    return struct.pack("<I", len(body)) + body


class Decoder:
    """One frame, one immutable deadline; validate header before body storage."""
    def __init__(self, deadline_ms, clock_ms):
        require(type(deadline_ms) is int and deadline_ms >= 0, "DEADLINE")
        self.deadline, self.clock = deadline_ms, clock_ms
        self.header, self.body = bytearray(), bytearray()
        self.length, self.done, self.failed, self.last = None, False, False, -1

    def feed(self, chunk, *, final=False):
        try:
            require(not self.done and not self.failed, "FRAME_TERMINAL")
            now = self.clock()
            require(type(now) is int and now >= self.last, "CLOCK_REVERSED")
            self.last = now
            require(now < self.deadline, "REQUEST_TIMEOUT")
            require(type(chunk) is bytes and len(chunk) <= MAX_BODY + 4, "FRAME_LENGTH")
            take = min(4 - len(self.header), len(chunk))
            self.header.extend(chunk[:take])
            rest = memoryview(chunk)[take:]
            if len(self.header) == 4 and self.length is None:
                self.length = struct.unpack("<I", self.header)[0]
                require(1 <= self.length <= MAX_BODY, "FRAME_LENGTH")
            if self.length is not None:
                require(len(self.body) + len(rest) <= self.length, "TRAILING_BYTES")
                self.body.extend(rest)
            if self.length is not None and len(self.body) == self.length:
                value = validate_message(decode(bytes(self.body)))
                self.done = True
                return value
            require(not final, "TRUNCATED_FRAME")
            return None
        except Exception:
            self.failed = True
            raise


def reply_to(request):
    validate_message(request)
    require(request["kind"] == "REQUEST", "MESSAGE_KIND")
    result = deepcopy(request)
    result.update(kind="RESPONSE", request_sha256=sha256(canonical(request)),
                  result={"CANCEL": "CANCELLED", "CLOSE": "CLOSED"}.get(request["method"], "OK"))
    return result


class Session:
    """Host-side single outstanding request, with no reconnect/retry transition."""
    def __init__(self, session_id, channel_id, epoch, clock_ms):
        identifier(session_id); identifier(channel_id)
        require(type(epoch) is int and 1 <= epoch <= 2147483647, "INTEGER")
        self.binding = {"session_id": session_id, "channel_id": channel_id, "epoch": epoch}
        self.clock, self.last = clock_ms, -1
        self.state, self.sequence, self.pending = "NEW", 0, None
        self.used, self.deadline = set(), None

    def now(self):
        value = self.clock()
        require(type(value) is int and value >= 0 and value >= self.last, "CLOCK_REVERSED")
        self.last = value
        return value

    def begin(self, method, request_id, payload=""):
        try:
            require(self.state in ("NEW", "READY") and self.pending is None, "SESSION_NOT_READY")
            require(method == "HELLO" if self.state == "NEW" else method in METHODS - {"HELLO"}, "METHOD_ORDER")
            identifier(request_id)
            require(request_id not in self.used, "REQUEST_REPLAY")
            self.sequence += 1
            message = {"schema": SCHEMA, "origin": "SYNTHETIC", "kind": "REQUEST", "method": method,
                       **self.binding, "request_id": request_id, "sequence": self.sequence,
                       "payload": payload, "request_sha256": "", "result": ""}
            raw = frame(message)
            self.deadline = self.now() + 250
            self.pending = deepcopy(message)
            self.used.add(request_id)
            self.state = "WAITING"
            return raw
        except Exception:
            self.invalidate("FAILED")
            raise

    def accept(self, message):
        try:
            require(self.state == "WAITING" and self.pending is not None, "NO_PENDING_REQUEST")
            require(self.now() < self.deadline, "REQUEST_TIMEOUT")
            validate_message(message)
            p = self.pending
            require(message["kind"] == "RESPONSE" and all(message[k] == p[k] for k in CORRELATION)
                    and message["method"] == p["method"]
                    and message["request_sha256"] == sha256(canonical(p))
                    and message["payload"] == p["payload"], "RESPONSE_BINDING")
            self.pending = None
            self.state = {"CANCEL": "CANCELLED", "CLOSE": "CLOSED"}.get(p["method"], "READY")
            return deepcopy(message)
        except Exception:
            self.invalidate("FAILED")
            raise

    def invalidate(self, state="CANCELLED"):
        self.pending = None
        self.state = state


def validate_peer_model(proof, expected, *, used_epochs):
    """Checks fixture data only. Even valid data is never OS peer evidence."""
    fields = {"origin", "principal", "owner", "client_pid", "server_pid", "client_creation",
              "server_creation", "dacl", "client_handle", "session_id", "channel_id", "epoch",
              "client_challenge", "server_challenge", "os_evidence"}
    require(type(proof) is dict and set(proof) == fields and set(expected) == fields, "PEER_SCHEMA")
    require(proof["origin"] == "SYNTHETIC" and proof["os_evidence"] == "NOT_RUN", "MOCK_IS_NOT_OS_PROOF")
    require(proof == expected, "PEER_MISMATCH")
    require(proof["principal"] not in ("", "UNKNOWN") and proof["owner"] == proof["principal"], "PRINCIPAL")
    require(proof["dacl"] == "RESTRICTED_MODEL" and proof["client_handle"] == "KNOWN_MODEL", "PEER_PROOF_MISSING")
    for key in ("client_pid", "server_pid"):
        require(type(proof[key]) is int and proof[key] > 0, "PROCESS_IDENTITY")
    for key in ("client_creation", "server_creation"):
        require(type(proof[key]) is str and re.fullmatch(r"[0-9A-F]{16}", proof[key])
                and int(proof[key], 16) > 0, "PROCESS_IDENTITY")
    for key in ("session_id", "channel_id"):
        identifier(proof[key])
    require(type(proof["epoch"]) is int and proof["epoch"] > 0, "INTEGER")
    for key in ("client_challenge", "server_challenge"):
        digest_string(proof[key])
    require(proof["client_challenge"] != proof["server_challenge"], "CHALLENGE_REUSE")
    epoch = (proof["session_id"], proof["channel_id"], proof["epoch"])
    require(epoch not in used_epochs, "EPOCH_REPLAY")
    used_epochs.add(epoch)
    return "SYNTHETIC_PEER_MODEL_ONLY"


def challenge_response(secret, binding, client_challenge, server_challenge, role):
    """Offline bilateral HMAC model; keys are never part of messages/evidence."""
    require(type(secret) is bytes and len(secret) >= 32, "SECRET")
    require(role in ("CLIENT", "SERVER"), "ROLE")
    require(type(binding) is dict and set(binding) == {"session_id", "channel_id", "epoch"}, "BINDING")
    identifier(binding["session_id"]); identifier(binding["channel_id"])
    require(type(binding["epoch"]) is int and binding["epoch"] > 0, "INTEGER")
    digest_string(client_challenge); digest_string(server_challenge)
    require(client_challenge != server_challenge, "CHALLENGE_REUSE")
    return hmac.new(secret, canonical({**binding, "client_challenge": client_challenge,
                    "server_challenge": server_challenge, "role": role, "schema": SCHEMA}), "sha256").hexdigest()


def check_challenge(secret, binding, client_challenge, server_challenge, role, response):
    digest_string(response)
    require(hmac.compare_digest(challenge_response(secret, binding, client_challenge, server_challenge, role), response),
            "CHALLENGE_MISMATCH")
    return "SYNTHETIC_CHALLENGE_ONLY"


def native_admission(*_args, **_kwargs):
    # No JSON flag, mock proof, signature-shaped string or command can enable it.
    raise ProbeError("R3_B_NOT_AUTHORIZED")
