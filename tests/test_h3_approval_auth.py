"""Deterministic review-only authentication tests; fake crypto unless stated.

No test here generates keys, starts GnuPG/agents, touches CE or reads memory.
The standalone native probe has a separate, interactive operator gate.
"""

from dataclasses import FrozenInstanceError, asdict, replace
from datetime import datetime, timezone
import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import types

import pytest

from armedforces_tool import h3_approval_auth as m
import h3_approval_native_probe as probe


WRITE = "A1" * 20
RESTORE = "B2" * 20
SUBKEY = "C3" * 20
OTHER = "D4" * 20
SIGNATURE = b"\xc2\x05\x04test"  # Envelope only; not a real OpenPGP signature.
KEYRING = b"\xc6\x04test"  # Fake public packet; never native-qualified.
NOW = "2026-06-01T12:00:01Z"
TIMESTAMP = 1780315201
PRIVATE = "SECRET PID executable approval content"
ROLES = ("write", "restore")
ROOT = Path(__file__).resolve().parents[1]


def valid_status(fpr=WRITE, primary=None, timestamp=TIMESTAMP):
    return (f"[GNUPG:] NEWSIG\n[GNUPG:] KEY_CONSIDERED {primary or fpr} 0\n"
            f"[GNUPG:] GOODSIG {fpr[-16:]} H3 TEST ONLY\n"
            f"[GNUPG:] VALIDSIG {fpr} 2026-06-01 {timestamp} 0 4 0 22 8 00 {primary or fpr}\n").encode("ascii")


class FakeBackend:
    review_only = True
    keyring_sha256 = m.sha256(KEYRING)

    def __init__(self, output=None):
        self.output, self.calls = output, []

    def verify(self, body, signature):
        self.calls.append((body, signature))
        if isinstance(self.output, Exception):
            raise self.output
        if self.output is not None:
            return self.output
        # An exact immutable fixture registry, not a hash-based verifier.
        role = "restore" if body == probe.fixture(m, "restore") else "write"
        if body != probe.fixture(m, role) or signature != SIGNATURE:
            return m.ToolResult(1, b"[GNUPG:] BADSIG wrong\n")
        return m.ToolResult(0, valid_status(WRITE if role == "write" else RESTORE))


def policy():
    return probe.policy_fixture(m, m.sha256(KEYRING), WRITE, RESTORE)


def authenticator(p=None, backend=None, clock=lambda: (NOW, 1000), guard=None, **pins):
    p = policy() if p is None else p
    raw = m.canonical_json(p) if type(p) is dict else p
    return m.ApprovalAuthenticator(backend or FakeBackend(), raw,
        expected_policy_id=pins.get("expected_policy_id", "test-only-policy-v1"),
        expected_policy_sha256=pins.get("expected_policy_sha256", m.sha256(raw)),
        clock=clock, replay_guard=guard or m.ReviewReplayGuard())


def change(body, field, value):
    values = dict(line.decode("ascii").split("=", 1) for line in body[:-2].split(b"\r\n"))
    values[field] = value
    return "".join(f"{k}={v}\r\n" for k, v in values.items()).encode("ascii")


def check_rejected(result, auth=None):
    assert result.status == "REJECTED"
    assert result.signature_verified is False
    assert result.authorization_status == "NOT_PRODUCTION_AUTHORIZED"
    assert result.write_ready is result.handoff_write_ready is result.write_attempted is result.restore_attempted is False
    assert result.memory_read_attempts == result.memory_write_attempts == 0
    if auth:
        public = auth.render(result)
        assert len(public) < 2048 and PRIVATE.encode() not in public
        assert b"fictional.exe" not in public and b"0x1234" not in public


@pytest.mark.parametrize("role,count", [("write", 38), ("restore", 26)])
def test_exact_inventory_and_original_bytes(role, count):
    from test_handoff_write_restore_protocol import COMMON_FIELDS, WRITE_SOURCE_FIELDS, RESTORE_SOURCE_FIELDS
    assert m.WRITE_FIELDS == tuple(COMMON_FIELDS + WRITE_SOURCE_FIELDS)
    assert m.RESTORE_FIELDS == tuple(COMMON_FIELDS + RESTORE_SOURCE_FIELDS)
    backend = FakeBackend()
    auth = authenticator(backend=backend)
    body = probe.fixture(m, role)
    assert len(body[:-2].split(b"\r\n")) == count
    r = auth.evaluate(body, SIGNATURE, f"single_float32_{role}_once")
    assert r.status == m.PASS and r.signature_verified is True
    assert backend.calls == [(body, SIGNATURE)] and backend.calls[0][0] is body
    assert r.approval_sha256 == m.sha256(body) and r.detached_signature_sha256 == m.sha256(SIGNATURE)
    assert r.authorization_status == "NOT_PRODUCTION_AUTHORIZED"
    assert not any((r.write_ready, r.handoff_write_ready, r.write_attempted, r.restore_attempted))
    assert len(auth.render(r)) < 2048


FIELD_CASES = [(role, key) for role, fields in (("write", m.WRITE_FIELDS), ("restore", m.RESTORE_FIELDS)) for key in fields]


@pytest.mark.parametrize("role,key", FIELD_CASES, ids=[f"{r}-{k}" for r, k in FIELD_CASES])
@pytest.mark.parametrize("fault", ("missing", "duplicate", "renamed", "empty", "too-long", "reordered"))
def test_every_field_framing_rejected_before_crypto(role, key, fault):
    body = probe.fixture(m, role)
    lines = body[:-2].split(b"\r\n")
    index = next(i for i, line in enumerate(lines) if line.startswith(key.encode() + b"="))
    if fault == "missing":
        del lines[index]
    elif fault == "duplicate":
        lines.insert(index, lines[index])
    elif fault == "renamed":
        lines[index] = b"trusted=" + lines[index].split(b"=", 1)[1]
    elif fault == "empty":
        lines[index] = key.encode() + b"="
    elif fault == "too-long":
        lines[index] = key.encode() + b"=" + b"x" * 513
    else:
        other = (index + 1) % len(lines)
        lines[index], lines[other] = lines[other], lines[index]
    backend = FakeBackend()
    auth = authenticator(backend=backend)
    check_rejected(auth.evaluate(b"\r\n".join(lines) + b"\r\n", SIGNATURE, f"single_float32_{role}_once"), auth)
    assert not backend.calls


INVALID = [
    ("schema", "h2_value_report_v1"), ("source_kind", "full"), ("environment", "production"),
    ("authority", "owner"), ("trust_domain", "production-domain"), ("action", "approved=true"),
    ("request_id", "Write-one"), ("request_id", "trailing-"), ("request_id", "a" * 65),
    ("case_id", "../case"), ("session_id", "x=y"), ("attachment_id", "nil_"), ("scene_id", "a b"),
    ("candidate_address", "0x01234"), ("candidate_address", "0xabc"), ("candidate_address", "0x0"),
    ("candidate_address", "0x20000000000000"), ("candidate_address", "4660"),
    ("current_float", "100.0"), ("current_float", "+100"), ("current_float", "1e2"),
    ("current_float", "nan"), ("current_float", "inf"), ("current_float", "100.00000000000001"),
    ("current_pattern", "0x42c80000"), ("current_pattern", "0x7F800000"), ("current_pattern", "0x7FC00000"),
    ("current_pattern", "0x00000000"), ("target_pattern", "0xFF800000"),
    ("pid", "0"), ("pid", "01234"), ("pid", "4294967296"), ("pid", "1.0"),
    ("process_created_utc", "1969-01-01T00:00:00Z"), ("process_created_utc", "2026-02-29T00:00:00Z"),
    ("process_created_utc", "2026-06-02T12:00:00Z"), ("architecture", "arm64"),
    ("executable", "target.exe"), ("executable", r"C:\a\..\b.exe"), ("executable", r"C:\a.exe:stream"),
    ("executable", "C:/a.exe"), ("executable", r"\\server\a.exe"), ("executable", "C:\\a*.exe"),
    ("issued_utc", "2026-06-01T12:00:00+00:00"), ("issued_utc", "2026-06-01T12:00:60Z"),
    ("expires_utc", "2026-06-01T12:00:00Z"), ("expires_utc", "2026-06-01T12:02:01Z"),
    ("max_elapsed_ms", "0"), ("max_elapsed_ms", "120001"), ("max_elapsed_ms", "-1"),
]


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("field,value", INVALID, ids=[f"{i}-{k}" for i, (k, _) in enumerate(INVALID)])
def test_canonical_semantic_failures(role, field, value):
    backend = FakeBackend()
    auth = authenticator(backend=backend)
    check_rejected(auth.evaluate(change(probe.fixture(m, role), field, value), SIGNATURE, f"single_float32_{role}_once"))
    assert not backend.calls


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("fault", ("lf", "bare-cr", "no-final", "blank", "nul", "bom", "unicode", "extra", "oversize", "text", "bytearray"))
def test_byte_framing_and_type(role, fault):
    body = probe.fixture(m, role)
    damaged = {"lf": body.replace(b"\r\n", b"\n"), "bare-cr": body.replace(b"\r\n", b"\r"),
               "no-final": body[:-2], "blank": body + b"\r\n", "nul": body + b"\x00", "bom": b"\xef\xbb\xbf" + body,
               "unicode": body.replace(b"test", b"t\xc3\xa9st", 1), "extra": body + b"approved=true\r\n",
               "oversize": b"a" * 16385, "text": body.decode(), "bytearray": bytearray(body)}[fault]
    check_rejected(authenticator().evaluate(damaged, SIGNATURE, f"single_float32_{role}_once"))


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("bits", (0, 0x80000000, 1, 0x80000001, 0x7F7FFFFF, 0xFF7FFFFF, 0x3F800001))
def test_exact_float32_edge_patterns_match_lua(role, bits):
    from lupa.lua54 import LuaRuntime
    value = struct.unpack("<f", struct.pack("<I", bits))[0]
    text = format(value, ".17g")
    lua = LuaRuntime(register_eval=False, register_builtins=False)
    assert lua.eval('function(x) return string.format("%.17g",string.unpack("<f",string.pack("<I4",x))) end')(bits) == text
    body = change(change(probe.fixture(m, role), "current_float", text), "current_pattern", f"0x{bits:08X}")
    assert m.parse_approval(body, f"single_float32_{role}_once")["current_float"] == text


@pytest.mark.parametrize("role", ROLES)
def test_noop_and_source_links(role):
    body = probe.fixture(m, role)
    values = m.parse_approval(body, f"single_float32_{role}_once")
    noop = change(change(body, "target_float", values["current_float"]), "target_pattern", values["current_pattern"])
    check_rejected(authenticator().evaluate(noop, SIGNATURE, f"single_float32_{role}_once"))
    if role == "write":
        for name in m.SOURCE_NAMES:
            check_rejected(authenticator().evaluate(change(body, name + "_sha256", "A" * 64), SIGNATURE, m.ACTIONS[0]))
            check_rejected(authenticator().evaluate(change(body, name + "_id", "../injection"), SIGNATURE, m.ACTIONS[0]))
        check_rejected(authenticator().evaluate(change(body, "h2_id", values["a1_id"]), SIGNATURE, m.ACTIONS[0]))
    else:
        check_rejected(authenticator().evaluate(change(body, "source_request_id", values["request_id"]), SIGNATURE, m.ACTIONS[1]))


@pytest.mark.parametrize("body", [b"", b"approved=true\r\n", b"VALUE_CONSISTENT_NOT_AUTHORIZED\r\n",
                                 b"SOURCE_REVIEWABLE_NOT_AUTHORIZED\r\n", b"a" * 64, b"synthetic-proof-1", None, {}])
def test_non_authorizing_sources_not_approvals(body):
    check_rejected(authenticator().evaluate(body, SIGNATURE, m.ACTIONS[0]))


@pytest.mark.parametrize("signature", [b"", b"-----BEGIN PGP SIGNATURE-----", SIGNATURE * 2, b"x", b"x" * 16385,
                                       SIGNATURE[:-1], SIGNATURE + b"x", b"\xc2\xe0x", b"\x8btest", None, bytearray(SIGNATURE)])
def test_signature_envelope_failure(signature):
    backend = FakeBackend()
    check_rejected(authenticator(backend=backend).evaluate(probe.fixture(m, "write"), signature, m.ACTIONS[0]))
    assert not backend.calls


@pytest.mark.parametrize("field", list(policy()))
def test_policy_missing_extra_or_unpinned(field):
    p = policy()
    del p[field]
    with pytest.raises(m.AuthError):
        authenticator(p)
    p = policy()
    p["injected_field"] = "trusted"
    with pytest.raises(m.AuthError):
        authenticator(p)


@pytest.mark.parametrize("field,value", [("schema", "v2"), ("purpose", "PRODUCTION_AUTHORIZED"),
    ("authority", "owner"), ("trust_domain", "owner-domain"), ("policy_id", "other-id"),
    ("keyring_sha256", "A" * 64), ("valid_from", "not-time"), ("valid_until", "2020-01-01T00:00:00Z"),
    ("revocation_valid_until", "2027-01-01T00:00:00Z"), ("signers", []), ("signers", {}), ("signers", [True])])
def test_invalid_policy_fields(field, value):
    p = policy()
    p[field] = value
    with pytest.raises(m.AuthError):
        authenticator(p)


@pytest.mark.parametrize("field,value", [("primary_fingerprint", "A" * 16), ("signing_fingerprint", "a" * 40),
    ("signing_fingerprint", "0" * 40), ("primary_fingerprint", "A" * 64), ("role", "both"),
    ("revoked", "false"), ("valid_from", "2020-01-01T00:00:00Z"), ("valid_until", "2026-06-01T10:00:00Z")])
def test_signer_schema_rejected(field, value):
    p = policy()
    p["signers"][0][field] = value
    with pytest.raises(m.AuthError):
        authenticator(p)


@pytest.mark.parametrize("field", ("role", "primary_fingerprint", "signing_fingerprint"))
def test_rollover_and_multiple_policy_ambiguity(field):
    p = policy()
    p["signers"][1][field] = p["signers"][0][field]
    with pytest.raises(m.AuthError, match="AMBIGUOUS_POLICY"):
        authenticator(p)
    raw = m.canonical_json([policy(), policy()])
    with pytest.raises(m.AuthError):
        authenticator(raw)


@pytest.mark.parametrize("fault", ("changed", "unknown-root", "no-root", "duplicate-json", "not-canonical", "recursive"))
def test_independent_policy_pin(fault):
    raw = m.canonical_json(policy())
    with pytest.raises(m.AuthError):
        if fault == "changed":
            authenticator(raw.replace(b"TEST_ONLY_REVIEW", b"OWNER_APPROVED"), expected_policy_sha256=m.sha256(raw))
        elif fault == "unknown-root":
            authenticator(expected_policy_sha256="f" * 64)
        elif fault == "no-root":
            authenticator(expected_policy_id=None)
        elif fault == "duplicate-json":
            authenticator(raw.replace(b"{", b'{"purpose":"TEST_ONLY_REVIEW",', 1))
        elif fault == "not-canonical":
            authenticator(json.dumps(policy(), indent=2).encode())
        else:
            authenticator(b"[" * 2000 + b"]" * 2000)


def test_policy_is_captured_immutably_and_dependencies_once():
    p, backend, guard = policy(), FakeBackend(), m.ReviewReplayGuard()
    auth = authenticator(p, backend, guard=guard)
    p["signers"][0]["role"] = "restore"
    backend.verify = lambda *_: m.ToolResult(1, b"bad")
    guard.claim = lambda *_: False
    assert auth.evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0]).status == m.PASS
    with pytest.raises(FrozenInstanceError):
        auth._policy.policy_id = "changed"


@pytest.mark.parametrize("role", ROLES)
def test_actions_and_roles_never_inferred_from_signature(role):
    other = "restore" if role == "write" else "write"
    check_rejected(authenticator().evaluate(probe.fixture(m, role), SIGNATURE, f"single_float32_{other}_once"))
    p = policy()
    p["signers"] = [s for s in p["signers"] if s["role"] == other]
    r = authenticator(p).evaluate(probe.fixture(m, role), SIGNATURE, f"single_float32_{role}_once")
    assert r.failure_class == "ROLE_REJECTED"


@pytest.mark.parametrize("fault", ("revoked", "signer-expired", "signer-future", "stale-revocation", "future-revocation"))
def test_time_and_revocation_policy(fault):
    p = policy()
    if fault == "revoked":
        p["signers"][0]["revoked"] = True
    elif fault == "signer-expired":
        p["signers"][0]["valid_until"] = "2026-06-01T12:00:00Z"
    elif fault == "signer-future":
        p["signers"][0]["valid_from"] = "2026-06-01T12:00:02Z"
    elif fault == "stale-revocation":
        p["revocation_valid_until"] = "2026-06-01T12:00:01Z"
    else:
        p["revocation_checked_utc"] = "2026-06-01T12:00:02Z"
    backend = FakeBackend()
    check_rejected(authenticator(p, backend).evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0]))
    assert not backend.calls


@pytest.mark.parametrize("reading", [("2026-06-01T12:02:00Z", 1000), ("2026-06-01T11:59:59Z", 1000),
    (NOW, True), (NOW, -1), (NOW, 2**53), (NOW,), [NOW, 1000], ("bad", 1000)])
def test_clock_failures(reading):
    check_rejected(authenticator(clock=lambda: reading).evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0]))


@pytest.mark.parametrize("after", [(NOW, 999), (NOW, 11001), ("2026-06-01T12:00:05Z", 1001),
                                    ("2026-06-01T12:00:00Z", 1001), ("2026-06-01T12:02:00Z", 120000)])
def test_crypto_latency_is_inside_clock_gate(after):
    readings = iter([(NOW, 1000), after])
    check_rejected(authenticator(clock=lambda: next(readings)).evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0]))


@pytest.mark.parametrize("field,value", [(0, OTHER), (1, "2026-06-02"), (2, "1780315202"), (2, "01780315201"),
    (3, "1780315201"), (4, "5"), (5, "1"), (6, "1"), (7, "2"), (8, "01"), (9, OTHER)])
def test_validsig_fields(field, value):
    lines = valid_status().splitlines()
    fields = lines[-1].decode().split(" ")[2:]
    fields[field] = value
    lines[-1] = ("[GNUPG:] VALIDSIG " + " ".join(fields)).encode()
    r = m.ToolResult(0, b"\n".join(lines) + b"\n")
    check_rejected(authenticator(backend=FakeBackend(r)).evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0]))


@pytest.mark.parametrize("tag", ("BADSIG", "ERRSIG", "EXPSIG", "EXPKEYSIG", "REVKEYSIG", "KEYREVOKED",
                                "NO_PUBKEY", "FAILURE", "ERROR", "PLAINTEXT", "TRUST_ULTIMATE", "UNKNOWN"))
def test_unexpected_or_failure_status(tag):
    r = m.ToolResult(0, valid_status() + f"[GNUPG:] {tag} {PRIVATE}\n".encode())
    auth = authenticator(backend=FakeBackend(r))
    check_rejected(auth.evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0]), auth)


@pytest.mark.parametrize("fault", ("double", "duplicate-good", "duplicate-valid", "missing-good", "missing-valid", "missing-new",
    "wrong-good", "wrong-primary", "considered-flags", "hostile", "nul", "unicode", "oversize", "no-newline", "bare-cr", "empty"))
def test_status_ambiguity_and_hostile_output(fault):
    valid = valid_status()
    lines = valid.splitlines(keepends=True)
    bad = {"double": valid * 2, "duplicate-good": valid + lines[2], "duplicate-valid": valid + lines[3],
           "missing-good": b"".join(lines[:2] + lines[3:]), "missing-valid": b"".join(lines[:3]),
           "missing-new": b"".join(lines[1:]), "wrong-good": valid.replace(WRITE[-16:].encode() + b" H3", b"F" * 16 + b" H3"),
           "wrong-primary": valid.replace(b"KEY_CONSIDERED " + WRITE.encode(), b"KEY_CONSIDERED " + OTHER.encode()),
           "considered-flags": valid.replace(b" 0\n", b" 2\n", 1), "hostile": PRIVATE.encode() + valid,
           "nul": valid + b"\0", "unicode": valid + b"\xff", "oversize": valid + b"x" * 16384,
           "no-newline": valid[:-1], "bare-cr": valid.replace(b"\n", b"\r"), "empty": b""}[fault]
    check_rejected(authenticator(backend=FakeBackend(m.ToolResult(0, bad))).evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0]))


def test_explicit_subkey_pin_and_consistent_sig_id():
    p = policy()
    p["signers"][0]["signing_fingerprint"] = SUBKEY
    status = valid_status(SUBKEY, WRITE).replace(b"[GNUPG:] GOODSIG", b"[GNUPG:] SIG_ID abcdefghijklmnopqrstuvwx 2026-06-01 1780315201\n[GNUPG:] GOODSIG")
    result = authenticator(p, FakeBackend(m.ToolResult(0, status))).evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0])
    assert result.status == m.PASS
    check_rejected(authenticator(p, FakeBackend()).evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0]))


@pytest.mark.parametrize("output", [m.ToolResult(1, valid_status()), m.ToolResult(True, valid_status()),
    m.ToolResult(0, valid_status(), b"x" * 16385), m.ToolResult(0, valid_status().decode()),
    {"returncode": 0, "status": valid_status()}, True, RuntimeError(PRIVATE), m.AuthError(PRIVATE),
    m.AuthError("TOOL_TIMEOUT"), m.AuthError("TOOL_UNAVAILABLE"), m.AuthError("TOOL_OUTPUT_LIMIT")])
def test_tool_failure_isolation(output):
    auth = authenticator(backend=FakeBackend(output))
    check_rejected(auth.evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0]), auth)


def test_signature_and_one_byte_changes_require_crypto():
    body = probe.fixture(m, "write")
    for changed_body, sig in ((body.replace(b"test-write-one", b"test-write-onf"), SIGNATURE),
                              (body, SIGNATURE[:-1] + b"X")):
        backend = FakeBackend()
        check_rejected(authenticator(backend=backend).evaluate(changed_body, sig, m.ACTIONS[0]))
        assert backend.calls == [(changed_body, sig)]


def test_replay_across_authenticators_signatures_and_policy_versions():
    guard = m.ReviewReplayGuard()
    body = probe.fixture(m, "write")
    assert authenticator(guard=guard).evaluate(body, SIGNATURE, m.ACTIONS[0]).status == m.PASS
    for sig in (SIGNATURE, SIGNATURE[:-1] + b"X"):
        backend = FakeBackend()
        r = authenticator(backend=backend, guard=guard).evaluate(body, sig, m.ACTIONS[0])
        assert r.failure_class == "REPLAY_REJECTED" and not backend.calls
    assert guard.claim("different-policy", "test-write-one", "1" * 64, "2" * 64) is False


def test_replay_guard_failure_busy_and_capacity():
    class BadGuard:
        def claim(self, *args):
            return "true"
    check_rejected(authenticator(guard=BadGuard()).evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0]))
    auth = authenticator()
    auth._lock.acquire()
    try:
        assert auth.evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0]).failure_class == "BUSY"
    finally:
        auth._lock.release()
    guard = m.ReviewReplayGuard()
    for i in range(4096):
        assert guard.claim("p", f"r-{i}", "a", "s") is True
    assert guard.claim("p", "new", "a", "s") is False


def test_result_hostile_object_is_not_serialized():
    auth = authenticator()
    r = auth.evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0])
    class Hostile:
        def __deepcopy__(self, memo):
            pytest.fail("untrusted result copied")

        def __eq__(self, other):
            pytest.fail("untrusted result compared")
    object.__setattr__(r, "status", Hostile())
    assert json.loads(auth.render(r))["failure_class"] == "INVALID_RESULT"


@pytest.mark.parametrize("field", list(asdict(m.ReviewResult("x", "x", "x", "x", "x", False))))
def test_result_mutation_copy_and_forgery(field):
    auth = authenticator()
    r = auth.evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0])
    with pytest.raises(FrozenInstanceError):
        setattr(r, field, "forged")
    assert json.loads(auth.render(replace(r)))["failure_class"] == "INVALID_RESULT"
    assert json.loads(authenticator().render(r))["failure_class"] == "INVALID_RESULT"
    object.__setattr__(r, field, "forged")
    assert json.loads(auth.render(r))["failure_class"] == "INVALID_RESULT"


def test_a2_constructor_and_verifier_do_not_accept_result_as_grant():
    from lupa.lua54 import LuaRuntime
    from test_handoff_write_restore_protocol import safe_module, DEPENDENCIES
    lua = LuaRuntime(register_eval=False, register_builtins=False, unpack_returned_tuples=True)
    auth = authenticator()
    r = auth.evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0])
    for role in ROLES:
        protocol = safe_module(lua, f"mvp0_handoff_{role}_protocol.lua")
        result = protocol.new_synthetic(lua.table_from(asdict(r)))
        assert isinstance(result, tuple) and result[0] is None
        # The A4 result is not the exact authenticated-bytes/domain/authority
        # triple required by A2. No bridging callback is provided by A4.
        calls = []
        def forbidden(*_):
            calls.append(True)
            raise AssertionError("must stop at authentication")
        wrap = lua.eval("function(f) return function(...) return f(...) end end")
        names = DEPENDENCIES + (["read_evidence", "revalidate_sources"] if role == "write" else [])
        deps = lua.table_from({name: wrap(forbidden) for name in names})
        deps.environment = "synthetic_only"
        deps.clock = lua.eval('function() return "2026-06-01T12:00:01Z",1000 end')
        deps.verify_approval = wrap(lambda *_: lua.table_from(asdict(r)))
        engine = protocol.new_synthetic(deps)
        output = engine.run(probe.fixture(m, role).decode(), "not-a-production-proof")
        assert output.failure_class == "approval_untrusted"
        assert output.write_attempted is False and output.restore_attempted is False and not calls


def test_import_has_no_filesystem_process_network_clock_activity(monkeypatch):
    import builtins
    import socket
    import subprocess
    import time
    # Load source before poisoning. Dependency imports themselves are Python's
    # loader responsibility; executing this module has no external operations.
    body = (ROOT / "src/armedforces_tool/h3_approval_auth.py").read_bytes()
    code = compile(body, "h3_import_isolation", "exec")
    isolated = types.ModuleType("h3_import_isolation")
    monkeypatch.setitem(sys.modules, isolated.__name__, isolated)
    def forbidden(*args, **kwargs):
        raise AssertionError("import side effect")
    for owner, names in ((builtins, ("open",)), (Path, ("open", "read_bytes", "stat", "mkdir")),
                         (subprocess, ("Popen", "run")), (socket, ("socket", "create_connection")),
                         (time, ("time", "monotonic", "monotonic_ns", "sleep"))):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    exec(code, isolated.__dict__)
    assert isolated.PASS == m.PASS


@pytest.mark.parametrize("path", ["gpgv.exe", r"C:\x\..\gpgv.exe", r"\\host\share\gpgv.exe", r"C:\x\gpgv.exe:ads",
    "C:/x/gpgv.exe", r"C:\x\gpgv*.exe", r"C:\x\NUL", r"C:\x\name.\gpgv.exe"])
def test_native_path_rejects_untrusted_arguments_before_process(path, monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: pytest.fail("unexpected process"))
    with pytest.raises((m.AuthError, OSError)):
        m.NativeGpgvBackend(executable=path, executable_sha256="a" * 64, public_keyring=KEYRING,
                            scratch_root=r"C:\test-root", approved_test_only=True)


@pytest.mark.parametrize("tag", (5, 7, 8, 9, 11, 18))
def test_private_or_nonpublic_keyring_rejected(tag):
    keyring = KEYRING + bytes([0xC0 | tag, 4]) + b"test"
    with pytest.raises(m.AuthError, match="PUBLIC_KEYRING_REQUIRED"):
        m.NativeGpgvBackend(executable=r"C:\test\gpgv.exe", executable_sha256="a" * 64, public_keyring=keyring,
                            scratch_root=r"C:\test-root", approved_test_only=True)


def test_native_backend_has_no_default_or_production_enablement():
    with pytest.raises(m.AuthError, match="UNPINNED_BACKEND"):
        m.NativeGpgvBackend(executable=r"C:\test\gpgv.exe", executable_sha256="a" * 64, public_keyring=KEYRING,
                            scratch_root=r"C:\test-root")
    with pytest.raises(TypeError):
        m.ApprovalAuthenticator()
    assert not hasattr(m, "new_production")


def test_native_invocation_uses_fixed_argv_exact_files_and_public_home(tmp_path, monkeypatch):
    # Fake filesystem path validator and fake subprocess only. This does not
    # qualify NTFS, a real binary, signatures or native key custody.
    binary = tmp_path / "gpgv.exe"
    binary.write_bytes(b"fake verifier")
    calls = []
    monkeypatch.setattr(m, "native_path", lambda value, **_: Path(value))
    def runner(args, **kw):
        calls.append((args, kw))
        base = Path(kw["cwd"])
        assert (base / "approval.bin").read_bytes() == probe.fixture(m, "write")
        assert (base / "detached.sig").read_bytes() == SIGNATURE
        assert (base / "public.gpg").read_bytes() == KEYRING
        assert args == (str(binary), "--homedir", str(base / "home"), "--keyring", str(base / "public.gpg"),
                        "--status-fd", "1", "--weak-digest", "SHA1", "--", str(base / "detached.sig"), str(base / "approval.bin"))
        assert kw["timeout"] == 10 and kw["output_limit"] == 16384
        assert set(kw["env"]) <= {"GNUPGHOME", "TEMP", "TMP", "SystemRoot"}
        assert kw["env"]["GNUPGHOME"] == str(base / "home") and not list((base / "home").iterdir())
        return m.ToolResult(0, valid_status())
    b = m.NativeGpgvBackend(executable=str(binary), executable_sha256=m.sha256(binary.read_bytes()),
        public_keyring=KEYRING, scratch_root=str(tmp_path), approved_test_only=True, runner=runner)
    assert authenticator(backend=b).evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0]).status == m.PASS
    assert len(calls) == 1


@pytest.mark.parametrize("fault", ("binary", "approval", "signature", "keyring", "home"))
def test_native_input_or_tool_tamper_fails_closed(tmp_path, monkeypatch, fault):
    binary = tmp_path / "gpgv.exe"
    binary.write_bytes(b"fake")
    monkeypatch.setattr(m, "native_path", lambda value, **_: Path(value))
    def runner(args, **kw):
        base = Path(kw["cwd"])
        target = binary if fault == "binary" else base / {"approval": "approval.bin", "signature": "detached.sig",
                                                         "keyring": "public.gpg", "home": "home/unexpected"}[fault]
        target.write_bytes(b"tampered")
        return m.ToolResult(0, valid_status())
    b = m.NativeGpgvBackend(executable=str(binary), executable_sha256=m.sha256(binary.read_bytes()),
        public_keyring=KEYRING, scratch_root=str(tmp_path), approved_test_only=True, runner=runner)
    check_rejected(authenticator(backend=b).evaluate(probe.fixture(m, "write"), SIGNATURE, m.ACTIONS[0]))


@pytest.mark.parametrize("fault", ("success", "nonzero", "overflow", "timeout", "unavailable"))
def test_bounded_subprocess_with_fake_popen(monkeypatch, fault):
    import io
    import subprocess
    import time
    state = []
    class Process:
        def __init__(self, args, **kw):
            state.append((args, kw))
            if fault == "unavailable":
                raise FileNotFoundError(PRIVATE)
            self.stdout = io.BytesIO(b"x" * (17000 if fault == "overflow" else 3))
            self.stderr = io.BytesIO()
            self.returncode = 1 if fault == "nonzero" else 0
            self.killed = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def poll(self):
            return None if fault == "timeout" and not self.killed else self.returncode

        def wait(self, timeout):
            return self.returncode

        def kill(self):
            self.killed = True
    monkeypatch.setattr(subprocess, "Popen", Process)
    ticks = iter((0, 20))
    monkeypatch.setattr(time, "monotonic", lambda: next(ticks, 20))
    if fault in ("success", "nonzero"):
        result = m.bounded_process([r"C:\fixed\gpgv.exe"], cwd=r"C:\fixed", env={})
        assert result.status == b"xxx" and result.returncode == (fault == "nonzero")
    else:
        with pytest.raises(m.AuthError):
            m.bounded_process([r"C:\fixed\gpgv.exe"], cwd=r"C:\fixed", env={})
    assert state[0][1]["shell"] is False and state[0][1]["stdin"] == subprocess.DEVNULL


@pytest.mark.parametrize("args,timeout,limit", [([], 10, 100), (["x"] * 41, 10, 100), (["x" * 1025], 10, 100),
    (["x\0"], 10, 100), (["x"], 0, 100), (["x"], 61, 100), (["x"], 10, 65537)])
def test_process_argument_limits(args, timeout, limit):
    with pytest.raises(m.AuthError):
        m.bounded_process(args, cwd="unused", env={}, timeout=timeout, output_limit=limit)


def test_probe_complete_inventory_and_no_default_execution(tmp_path):
    complete = {name: {"status": "PASS"} for name in probe.REQUIRED}
    probe.qualify(complete)
    for name in probe.REQUIRED:
        missing = dict(complete)
        del missing[name]
        with pytest.raises(RuntimeError):
            probe.qualify(missing)
        for status in ("FAIL", "SKIP", "UNQUALIFIED"):
            with pytest.raises(RuntimeError):
                probe.qualify({**complete, name: {"status": status}})
    assert not Path(probe.__file__).name.startswith("test_")
    assert probe.LABEL == "NATIVE_TEST_SIGNATURE_VERIFICATION_ONLY"
    summaries = []
    probe.record_process(tmp_path, summaries, "gpgv", m.ToolResult(0, b"bounded test stdout", b"test stderr"))
    assert (tmp_path / "subprocess-000.stdout").read_bytes() == b"bounded test stdout"
    assert summaries[0]["stdout_sha256"] == m.sha256(b"bounded test stdout")
    assert "bounded test stdout" not in json.dumps(summaries)


# R2-S1 stdlib socket tests. This self-contained block is also collected by
# pytest; the original tests above are unchanged. The external S1 runner may
# execute these exact unittest cases without importing pytest or Lupa. That
# limited check is NOT the required H3-A4/legacy/combined qualification.
import unittest
from pathlib import PureWindowsPath
from unittest.mock import patch


class _SocketIO:
    """Entirely in-memory Windows fixture; no real filesystem/process/socket."""

    local = r"C:\H3Synthetic\AppData\Local"
    home = local + "\\ChromeProject-H3-Approval-Qualification\\auth-" + "1" * 32 + "\\test-gnupg"
    executable = r"D:\H3SyntheticTools\gpg-agent.exe"
    sid = "S-1-5-21-111-222-333-1001"
    binary_hash = "a" * 64

    def __init__(self):
        self.directory = probe.derived_socket_directory(self.home, self.local)
        home = PureWindowsPath(self.home)
        paths = (self.local, str(home.parent.parent), str(home.parent), self.home,
                 str(PureWindowsPath(self.directory).parent))
        self.nodes = {path: self.identity(index + 1) for index, path in enumerate(paths)}
        self.bodies, self.calls, self.rows = {}, [], [("127.0.0.1", 49000, 700)]
        self.clock, self.current, self.exit, self.output_ok = 100, None, None, True
        self.process = type("FakeLaunch", (), {"pid": 800})()
        self.inspect_error, self.spawn_error = None, None
        self.process_changes = {}

    @staticmethod
    def identity(index, created=1):
        return {"file_id": [1, index], "created": created, "security_sha256": "b" * 64}

    def now(self):
        self.clock += 1
        return self.clock

    def inspect(self, path, *, directory=False):
        self.calls.append(("inspect", path))
        if self.inspect_error:
            raise self.inspect_error
        if path not in self.nodes:
            raise FileNotFoundError(path)
        return dict(self.nodes[path])

    def exists(self, path):
        self.calls.append(("exists", path))
        return path in self.nodes

    def mkdir(self, path):
        self.calls.append(("mkdir", path))
        if path in self.nodes:
            raise FileExistsError(path)
        self.nodes[path] = self.identity(len(self.nodes) + 1, self.clock)

    def children(self, path):
        # Never allow the implementation to enumerate a user's shared base.
        assert path in (self.home, self.directory)
        self.calls.append(("children", path))
        return [PureWindowsPath(key).name for key in self.nodes if str(PureWindowsPath(key).parent) == path]

    def spawn(self, argv, binary_hash):
        self.calls.append(("spawn", list(argv)))
        if self.spawn_error:
            raise self.spawn_error
        assert binary_hash == self.binary_hash
        assert argv[0] == self.executable and argv[1:4] == ["--no-options", "--homedir", self.home]
        assert argv[argv.index("--extra-socket") + 1] == argv[argv.index("--browser-socket") + 1] == "none"
        assert not any(flag in argv for flag in ("--enable-ssh-support", "--enable-putty-support",
                                                 "--enable-win32-openssh-support", "--steal-socket"))
        self.current = {"pid": self.process.pid, "path": self.executable, "sid": self.sid, "created": self.clock}
        self.current.update(self.process_changes)
        for index, (name, body) in enumerate((
                ("S.gpg-agent", b"49100\n" + b"n" * 16),
                ("S.gpg-agent.ssh", b"!<socket >49101 s 12345678-12345678-12345678-12345678\x00"))):
            path = self.directory + "\\" + name
            self.nodes[path] = self.identity(100 + index, self.clock)
            self.bodies[path] = body
            self.rows.append(("127.0.0.1", 49100 + index, self.process.pid))
        return self.process

    def process_identity(self, process):
        assert process is self.process
        self.calls.append(("process_identity", process.pid))
        if self.exit is not None:
            raise RuntimeError("AGENT_PROCESS_EXITED")
        return dict(self.current)

    def begin_capture(self, process):
        self.calls.append(("begin_capture", process.pid))

    def endpoint(self, path):
        self.calls.append(("endpoint", path))
        return dict(self.nodes[path]), self.bodies[path]

    def listeners(self):
        self.calls.append(("listeners",))
        return list(self.rows)

    def healthy(self, process):
        return self.output_ok

    def poll(self, process):
        assert process is self.process
        return self.exit

    def terminate(self, process):
        assert process is self.process
        self.calls.append(("terminate", process.pid))
        self.exit = 1
        self.rows = [row for row in self.rows if row[2] != process.pid]


class TestAgentSocketIsolation(unittest.TestCase):
    def make(self):
        io = _SocketIO()
        guard = probe.IsolatedAgent(io.home, io.local, io.executable, io.binary_hash, io.sid, io)
        return guard, io

    @staticmethod
    def bind(guard, reports=None, versions=None):
        reports = reports if reports is not None else {key: (value + "\r\n").encode("ascii")
                                                       for key, value in guard.expected_paths().items()}
        versions = versions if versions is not None else {name: f"{name} (GnuPG) 2.4.8"
                                                          for name in ("gpg", "gpgv", "gpg-agent", "gpgconf")}
        guard.bind(reports, versions)

    def started(self):
        guard, io = self.make()
        guard.prepare()
        self.bind(guard)
        guard.start()
        self.assertTrue(guard.ready())
        return guard, io

    def assert_no_activation(self, io):
        self.assertFalse(any(call[0] in ("spawn", "endpoint", "terminate", "process_identity") for call in io.calls))

    def test_recorded_248_mapping_without_any_io(self):
        # Historical path is a PURE test vector, never passed to the IO adapter.
        local = r"C:\Users\llzz\AppData\Local"
        home = local + r"\ChromeProject-H3-Approval-Qualification\auth-cfefb28d18f745cfa58e88f69cc84fda\test-gnupg"
        import subprocess
        with patch("pathlib.Path.open", side_effect=AssertionError("filesystem contact")), \
             patch.object(subprocess, "Popen", side_effect=AssertionError("process contact")):
            self.assertEqual(probe.derived_socket_directory(home, local), local + r"\gnupg\d.ky53fx8m8j5rj8d1")

    def test_valid_lifecycle_and_personal_agent_separation(self):
        guard, io = self.started()
        guard.authorize()
        before = dict(io.nodes)
        self.assertTrue(guard.stop())
        self.assertEqual(io.nodes, before)  # No unlink, rmdir or cleanup by path.
        self.assertEqual(io.rows, [("127.0.0.1", 49000, 700)])
        self.assertEqual([call for call in io.calls if call[0] == "terminate"], [("terminate", 800)])
        self.assertEqual(guard.evidence["ssh_connections"], 0)
        self.assertNotIn(r"C:\Users\llzz", guard.directory)

    def test_home_scope_rejects_personal_and_other_roots(self):
        io = _SocketIO()
        for home in (io.local + r"\gnupg", r"C:\Users\Someone\AppData\Roaming\gnupg",
                     io.home.replace("auth-", "other-"), io.home.replace("test-gnupg", "gnupg"),
                     io.home.replace("H3Synthetic", "SomeOtherProfile")):
            with self.subTest(home=home), self.assertRaises(RuntimeError):
                probe.derived_socket_directory(home, io.local)

    def test_home_hash_changes_for_new_home(self):
        io = _SocketIO()
        other = io.home.replace("1" * 32, "2" * 32)
        self.assertNotEqual(io.directory, probe.derived_socket_directory(other, io.local))

    def test_ascii_case_mapping_and_exact_report_spelling(self):
        io = _SocketIO()
        upper_local = io.local.upper()
        home = io.home.replace(io.local, upper_local)
        self.assertEqual(PureWindowsPath(probe.derived_socket_directory(home, upper_local)).name,
                         PureWindowsPath(io.directory).name)
        guard, io = self.make()
        guard.prepare()
        reports = {key: (value + "\n").encode() for key, value in guard.expected_paths().items()}
        reports["agent-socket"] = reports["agent-socket"].replace(b"gnupg", b"GNUPG")
        with self.assertRaisesRegex(RuntimeError, "MAPPING_MISMATCH"):
            self.bind(guard, reports)
        self.assert_no_activation(io)

    def test_alias_traversal_and_windows_normalization_rejected(self):
        base = _SocketIO.home
        paths = (base.lower(), base.replace("\\", "/"), base + "\\", base + ".", base + " ",
                 base + ":stream", base.replace("test-gnupg", r"a\..\test-gnupg"),
                 base.replace("test-gnupg", r".\test-gnupg"), base.replace("test-gnupg", r"x\\test-gnupg"),
                 base.replace("test-gnupg", "TEST~1"), base.replace("test-gnupg", "NUL"),
                 base.replace("test-gnupg", "tést"), "\\\\?\\" + base, r"\\host\share\test-gnupg")
        for path in paths:
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                probe.windows_path(path)

    def test_raw_report_has_no_percent_decoding(self):
        self.assertEqual(probe.reported_directory(b"C:\\literal%41\\dir\r\n"), r"C:\literal%41\dir")
        for body in (b"", b"C:\\dir", b"C:\\dir\n\n", b" C:\\dir\n", b"C:\\a\nC:\\b\n",
                     b"C:\\a\r", b"C:\\a\x00\n", b"C:\\a\xff\n", b"C:\\a\n" * 600):
            with self.subTest(body=body[:30]), self.assertRaises(RuntimeError):
                probe.reported_directory(body)

    def test_all_mapping_reports_bound_independently(self):
        for key in self.make()[0].expected_paths():
            with self.subTest(key=key):
                guard, io = self.make()
                guard.prepare()
                reports = {name: (value + "\n").encode() for name, value in guard.expected_paths().items()}
                reports[key] = b"C:\\H3Synthetic\\foreign-home\\S.gpg-agent\n"
                with self.assertRaisesRegex(RuntimeError, "MAPPING_MISMATCH"):
                    self.bind(guard, reports)
                self.assert_no_activation(io)

    def test_wrong_hash_basename_parent_and_altered_home(self):
        for mutate in (lambda p: p.replace("d.", "d.x"), lambda p: p.replace("S.gpg-agent", "S.gpg-agent.extra"),
                       lambda p: p.replace("gnupg", "other"),
                       lambda p: probe.derived_socket_directory(_SocketIO.home.replace("1" * 32, "2" * 32), _SocketIO.local)
                       + "\\S.gpg-agent"):
            guard, io = self.make()
            guard.prepare()
            reports = {key: (value + "\n").encode() for key, value in guard.expected_paths().items()}
            reports["agent-socket"] = (mutate(guard.expected_paths()["agent-socket"]) + "\n").encode()
            with self.assertRaisesRegex(RuntimeError, "MAPPING_MISMATCH"):
                self.bind(guard, reports)
            self.assert_no_activation(io)

    def test_missing_extra_report_and_unqualified_version(self):
        for fault in ("missing", "extra", "version"):
            guard, io = self.make()
            guard.prepare()
            reports = {key: (value + "\n").encode() for key, value in guard.expected_paths().items()}
            versions = {name: f"{name} (GnuPG) 2.4.8" for name in ("gpg", "gpgv", "gpg-agent", "gpgconf")}
            if fault == "missing":
                del reports["homedir"]
            elif fault == "extra":
                reports["other-socket"] = b"C:\\other\n"
            else:
                versions["gpg-agent"] = "gpg-agent (GnuPG) 2.4.9"
            with self.assertRaises(RuntimeError):
                self.bind(guard, reports, versions)
            self.assert_no_activation(io)

    def test_preexisting_derived_directory_is_never_adopted(self):
        for name in (None, "S.gpg-agent", "S.gpg-agent.ssh", "unknown"):
            with self.subTest(name=name):
                guard, io = self.make()
                io.nodes[io.directory] = io.identity(99)
                if name:
                    io.nodes[io.directory + "\\" + name] = io.identity(98)
                before = dict(io.nodes)
                with self.assertRaisesRegex(RuntimeError, "DIRECTORY_NOT_FRESH"):
                    guard.prepare()
                self.assertEqual(before, io.nodes)
                self.assert_no_activation(io)

    def test_stale_endpoints_appearing_before_launch(self):
        for name in ("S.gpg-agent", "S.gpg-agent.ssh", "S.gpg-agent.extra", "S.gpg-agent.browser", "unknown"):
            with self.subTest(name=name):
                guard, io = self.make()
                guard.prepare()
                self.bind(guard)
                io.nodes[io.directory + "\\" + name] = io.identity(99)
                with self.assertRaisesRegex(RuntimeError, "NOT_FRESH"):
                    guard.start()
                self.assert_no_activation(io)

    def test_directory_created_during_exclusive_mkdir_is_rejected(self):
        guard, io = self.make()
        def racing_mkdir(path):
            io.nodes[path] = io.identity(999)
            raise FileExistsError(path)
        io.mkdir = racing_mkdir
        with self.assertRaises(FileExistsError):
            guard.prepare()
        self.assert_no_activation(io)

    def test_preexisting_shared_parent_is_not_enumerated(self):
        guard, io = self.make()
        guard.prepare()
        base = str(PureWindowsPath(io.directory).parent)
        self.assertNotIn(("children", base), io.calls)
        self.assertNotIn(("mkdir", base), io.calls)

    def test_missing_shared_parent_created_exclusively(self):
        guard, io = self.make()
        base = str(PureWindowsPath(io.directory).parent)
        del io.nodes[base]
        guard.prepare()
        self.assertIn(("mkdir", base), io.calls)
        self.assert_no_activation(io)

    def test_filesystem_owner_reparse_acl_and_metadata_errors_stop_before_launch(self):
        for error in (PermissionError("metadata denied"), RuntimeError("AGENT_OWNER_MISMATCH"),
                      RuntimeError("AGENT_CANONICAL_PATH_MISMATCH"), RuntimeError("NATIVE_PATH_REJECTED"),
                      RuntimeError("AGENT_SHARED_WRITE_ACCESS"), RuntimeError("AGENT_ACL_UNPROVEN")):
            guard, io = self.make()
            io.inspect_error = error
            with self.assertRaises(type(error)):
                guard.prepare()
            self.assert_no_activation(io)

    def test_directory_identity_replacement_before_launch(self):
        guard, io = self.make()
        guard.prepare()
        self.bind(guard)
        io.nodes[io.directory] = io.identity(999)
        with self.assertRaisesRegex(RuntimeError, "DIRECTORY_CHANGED"):
            guard.start()
        self.assert_no_activation(io)

    def test_home_must_remain_empty_before_launch(self):
        guard, io = self.make()
        guard.prepare()
        self.bind(guard)
        io.nodes[io.home + "\\gpg-agent.conf"] = io.identity(999)
        with self.assertRaisesRegex(RuntimeError, "HOME_NOT_FRESH"):
            guard.start()
        self.assert_no_activation(io)

    def test_unbound_or_repeated_launch_refused(self):
        guard, io = self.make()
        with self.assertRaisesRegex(RuntimeError, "START_NOT_APPROVED"):
            guard.start()
        self.assert_no_activation(io)
        guard, io = self.started()
        with self.assertRaisesRegex(RuntimeError, "START_NOT_APPROVED"):
            guard.start()
        self.assertEqual(sum(call[0] == "spawn" for call in io.calls), 1)

    def test_launch_failure_has_no_endpoint_cleanup(self):
        guard, io = self.make()
        guard.prepare()
        self.bind(guard)
        io.spawn_error = OSError("cannot launch")
        with self.assertRaises(OSError):
            guard.start()
        self.assertFalse(guard.stop())
        self.assertFalse(any(call[0] in ("terminate", "endpoint") for call in io.calls))

    def test_diagnostic_capture_failure_retains_owned_launch_handle(self):
        guard, io = self.make()
        guard.prepare()
        self.bind(guard)
        io.begin_capture = lambda process: (_ for _ in ()).throw(RuntimeError("capture unavailable"))
        with self.assertRaisesRegex(RuntimeError, "capture unavailable"):
            guard.start()
        self.assertIs(guard.process, io.process)
        self.assertIsNotNone(guard.identity)
        self.assertTrue(guard.stop())
        self.assertFalse(any(call[0] == "endpoint" for call in io.calls))

    def test_launch_identity_mismatch_never_connects_or_kills(self):
        for field, value in (("pid", 700), ("path", r"D:\Other\gpg-agent.exe"),
                             ("sid", "S-1-5-21-1-2-3-9999"), ("created", 1), ("created", 9999)):
            with self.subTest(field=field, value=value):
                guard, io = self.make()
                guard.prepare()
                self.bind(guard)
                io.process_changes[field] = value
                with self.assertRaisesRegex(RuntimeError, "IDENTITY_UNPROVEN"):
                    guard.start()
                with self.assertRaisesRegex(RuntimeError, "CLEANUP_IDENTITY_UNPROVEN"):
                    guard.stop()
                self.assertFalse(any(call[0] in ("terminate", "endpoint") for call in io.calls))

    def test_primary_and_ssh_descriptor_formats_and_redirect_rejection(self):
        valid = {"S.gpg-agent": b"49100\n" + b"n" * 16,
                 "S.gpg-agent.ssh": b"!<socket >49101 s 12345678-12345678-12345678-12345678\x00"}
        self.assertEqual(probe.endpoint_port("S.gpg-agent", valid["S.gpg-agent"]), 49100)
        self.assertEqual(probe.endpoint_port("S.gpg-agent.ssh", valid["S.gpg-agent.ssh"]), 49101)
        for name, good in valid.items():
            for bad in (b"", good[:-1], good + b"x", b"%Assuan%\nsocket=C:\\personal\n",
                        b"0\n" + b"n" * 16, b"65536\n" + b"n" * 16, b"049100\n" + b"n" * 16):
                with self.subTest(name=name, body=bad), self.assertRaises(RuntimeError):
                    probe.endpoint_port(name, bad)

    def test_other_endpoints_and_ssh_use_forbidden(self):
        guard, io = self.started()
        before = list(io.calls)
        for endpoint in ("S.gpg-agent.ssh", "S.gpg-agent.extra", "S.gpg-agent.browser", "ssh", "unknown"):
            with self.subTest(endpoint=endpoint), self.assertRaisesRegex(RuntimeError, "USE_FORBIDDEN"):
                guard.authorize(endpoint)
        self.assertEqual(before, io.calls)

    def test_unapproved_endpoint_appearance_stops_before_read_or_connection(self):
        for name in ("S.gpg-agent.extra", "S.gpg-agent.browser", "S.gpg-agent.other", "S.GPG-AGENT"):
            guard, io = self.started()
            io.nodes[io.directory + "\\" + name] = io.identity(999, io.clock)
            before = len([call for call in io.calls if call[0] == "endpoint"])
            with self.assertRaisesRegex(RuntimeError, "UNAPPROVED_ENDPOINT"):
                guard.authorize()
            self.assertEqual(before, len([call for call in io.calls if call[0] == "endpoint"]))

    def test_listener_foreign_pid_same_home_or_other_home_never_authorized(self):
        for rows in ([("127.0.0.1", 49100, 700), ("127.0.0.1", 49101, 800)],
                     [("0.0.0.0", 49100, 800), ("127.0.0.1", 49101, 800)],
                     [("127.0.0.1", 49100, 800)],
                     [("127.0.0.1", 49100, 800), ("127.0.0.1", 49101, 800), ("::1", 49102, 800)],
                     [("127.0.0.1", 49100, 800)] * 2 + [("127.0.0.1", 49101, 800)]):
            guard, io = self.started()
            io.rows = rows
            with self.assertRaisesRegex(RuntimeError, "LISTENER_IDENTITY_UNPROVEN"):
                guard.authorize()
            # An independent retained launch identity permits stopping only our
            # process even when someone else's listener is observed. No kill by path.
            guard.stop()
            self.assertFalse(any(call == ("terminate", 700) for call in io.calls))

    def test_listener_metadata_denial_is_not_treated_as_absence(self):
        guard, io = self.started()
        io.listeners = lambda: (_ for _ in ()).throw(PermissionError("table denied"))
        with self.assertRaises(PermissionError):
            guard.authorize()
        self.assertTrue(guard.failed)

    def test_endpoint_creation_identity_bytes_or_port_mutation(self):
        for fault in ("stale", "identity", "bytes", "port", "shared-port"):
            guard, io = self.started()
            path = io.directory + "\\S.gpg-agent"
            if fault == "stale":
                io.nodes[path]["created"] = 1
            elif fault == "identity":
                io.nodes[path]["file_id"] = [1, 999]
            elif fault == "bytes":
                io.bodies[path] = b"49100\n" + b"x" * 16
            elif fault == "port":
                io.bodies[path] = b"49000\n" + b"n" * 16  # Existing foreign agent.
            else:
                io.bodies[path] = b"49101\n" + b"n" * 16
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                guard.authorize()

    def test_changed_process_or_directory_and_output_overflow_fail_closed(self):
        for fault in ("pid", "sid", "created", "path", "directory", "output", "exit"):
            guard, io = self.started()
            if fault == "directory":
                io.nodes[io.directory] = io.identity(999)
            elif fault == "output":
                io.output_ok = False
            elif fault == "exit":
                io.exit = 1
            else:
                io.current[fault] = "changed"
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                guard.authorize()

    def test_missing_endpoint_is_only_a_preconnection_wait(self):
        guard, io = self.make()
        guard.prepare()
        self.bind(guard)
        guard.start()
        path = io.directory + "\\S.gpg-agent.ssh"
        saved = io.nodes.pop(path)
        self.assertFalse(guard.ready())
        io.nodes[path] = saved
        self.assertTrue(guard.ready())
        del io.nodes[path]
        with self.assertRaisesRegex(RuntimeError, "DISAPPEARED"):
            guard.authorize()

    def test_no_client_use_before_ready_even_after_caught_error(self):
        guard, io = self.make()
        guard.prepare()
        self.bind(guard)
        guard.start()
        with self.assertRaisesRegex(RuntimeError, "NOT_READY"):
            guard.authorize()
        with self.assertRaisesRegex(RuntimeError, "PREVIOUS_FAILURE"):
            guard.ready()
        self.assertFalse(any(call[0] == "endpoint" for call in io.calls))

    def test_failure_latches_and_does_not_adopt_replacement(self):
        guard, io = self.started()
        original = dict(io.current)
        io.current["pid"] = 700
        with self.assertRaises(RuntimeError):
            guard.authorize()
        io.current = original
        before = list(io.calls)
        with self.assertRaisesRegex(RuntimeError, "PREVIOUS_FAILURE"):
            guard.authorize()
        self.assertEqual(before, io.calls)

    def test_cleanup_identity_mismatch_and_prelaunch_no_cleanup(self):
        guard, io = self.make()
        self.assertFalse(guard.stop())
        self.assertEqual(io.calls, [])
        guard, io = self.started()
        io.current["created"] += 1
        with self.assertRaisesRegex(RuntimeError, "CLEANUP_IDENTITY_CHANGED"):
            guard.stop()
        self.assertFalse(any(call[0] == "terminate" for call in io.calls))

    def test_cleanup_never_uses_unproven_endpoints(self):
        guard, io = self.started()
        io.nodes[io.directory] = io.identity(999)
        io.nodes[io.directory + "\\S.gpg-agent.extra"] = io.identity(998)
        before_nodes, before_calls = dict(io.nodes), len(io.calls)
        guard.stop()
        self.assertEqual(before_nodes, io.nodes)
        self.assertFalse(any(call[0] in ("endpoint", "children", "inspect", "spawn")
                             for call in io.calls[before_calls:]))

    def test_shutdown_requires_no_owned_listener(self):
        guard, io = self.started()
        io.terminate = lambda process: setattr(io, "exit", 1)
        with self.assertRaisesRegex(RuntimeError, "SHUTDOWN_UNPROVEN"):
            guard.stop()


class TestWindowsAgentMetadata(unittest.TestCase):
    """Exercise ctypes parsing with fabricated API responses, never Win32 IO."""

    def adapter(self):
        import ctypes
        import types
        from ctypes import wintypes  # Preload before the narrow os.name patch.
        module = types.SimpleNamespace(native_path=lambda *_args, **_kw: None)
        with patch.object(ctypes, "WinDLL", create=True, return_value=object()), patch.object(probe.os, "name", "nt"):
            native = probe.WindowsAgentIO(module, _SocketIO.sid, {}, r"C:\H3Synthetic")
        self.assertIs(native.w, wintypes)
        return native

    def filesystem(self, *, directory=False, body=None, fault=None):
        import types
        native = self.adapter()
        c = native.c
        path = _SocketIO.home if directory else r"C:\H3Synthetic\S.gpg-agent"
        native.module.native_path = lambda *_args, **_kwargs: types.SimpleNamespace(lstat=lambda: types.SimpleNamespace(st_ino=123))
        native.security = lambda _handle: "b" * 64
        calls, reads = [], [0]

        def create(*args):
            self.assertEqual(args[0], path)
            self.assertEqual(args[2], 3)  # No FILE_SHARE_DELETE.
            self.assertEqual(args[4:6], (3, 0x02200000))  # OPEN_EXISTING + no-follow/backup semantics.
            return 123456

        def info(_handle, pointer):
            value = c.cast(pointer, c.POINTER(native.FileInfo)).contents
            value.attributes = 0x10 if directory else 0
            value.creation.dwLowDateTime, value.write.dwLowDateTime = 100, 101
            value.volume, value.index_low, value.links = 1, 123, 1
            value.size_low = len(body or b"x")
            value.access.dwLowDateTime = reads[0]  # A read can legitimately change atime.
            if fault == "reparse":
                value.attributes |= 0x400
            elif fault == "wrong-type":
                value.attributes ^= 0x10
            elif fault == "hardlink":
                value.links = 2
            elif fault == "missing-id":
                value.index_low = 0
            elif fault == "changed-write" and reads[0]:
                value.write.dwLowDateTime += 1
            return 1

        def final(_handle, buffer, _size, _flags):
            buffer.value = "\\\\?\\" + (path.upper() if fault == "case" else path)
            return len(buffer.value)

        def read(_handle, buffer, size, count, _overlapped):
            self.assertEqual(size, 129)
            c.memmove(buffer, body, len(body))
            c.cast(count, c.POINTER(native.w.DWORD)).contents.value = len(body)
            reads[0] += 1
            return 1

        functions = {"CreateFileW": create, "GetFileInformationByHandle": info,
                     "GetFinalPathNameByHandleW": final, "ReadFile": read,
                     "CloseHandle": lambda handle: calls.append(("closed", handle)) or 1}
        native.api = lambda _dll, name, *_types: functions[name]
        return native, path, calls

    def test_handle_path_and_metadata_checks(self):
        for directory in (False, True):
            native, path, calls = self.filesystem(directory=directory)
            self.assertEqual(native.inspect(path, directory=directory)["file_id"], [1, 123])
            self.assertEqual(calls, [("closed", 123456)])

    def test_handle_reparse_type_hardlink_identity_and_case_rejected(self):
        for fault in ("reparse", "wrong-type", "hardlink", "missing-id", "case"):
            with self.subTest(fault=fault):
                native, path, calls = self.filesystem(fault=fault)
                with self.assertRaises(RuntimeError):
                    native.inspect(path)
                self.assertEqual(calls, [("closed", 123456)])

    def test_descriptor_read_allows_access_time_change_but_not_write_change(self):
        body = b"49100\n" + b"n" * 16
        native, path, calls = self.filesystem(body=body)
        self.assertEqual(native.endpoint(path)[1], body)
        self.assertEqual(calls, [("closed", 123456)])
        native, path, calls = self.filesystem(body=body, fault="changed-write")
        with self.assertRaisesRegex(RuntimeError, "ENDPOINT_CHANGED"):
            native.endpoint(path)

    def security(self, *, mask=0x120089, owner=None, kind=0, null_acl=False):
        import struct
        native = self.adapter()
        c = native.c
        # Synthetic ACL with one ACE, whose SID conversion is injected.
        acl = c.create_string_buffer(struct.pack("<BBHHHBBHII", 2, 0, 20, 1, 0, kind, 0, 12, mask, 0))
        released = []

        def security(_handle, object_type, flags, p_owner, _group, p_acl, _sacl, descriptor):
            self.assertEqual((object_type, flags), (1, 5))  # Owner + DACL, read-only.
            c.cast(p_owner, c.POINTER(c.c_void_p)).contents.value = 100
            c.cast(p_acl, c.POINTER(c.c_void_p)).contents.value = 0 if null_acl else c.addressof(acl)
            c.cast(descriptor, c.POINTER(c.c_void_p)).contents.value = 200
            return 0

        def ace(_acl, index, pointer):
            self.assertEqual(index, 0)
            c.cast(pointer, c.POINTER(c.c_void_p)).contents.value = c.addressof(acl) + 8
            return 1

        native.sid_text = lambda pointer: (owner or native.sid) if pointer.value == 100 else "S-1-5-21-9-9-9-999"
        functions = {"GetSecurityInfo": security, "GetAce": ace,
                     "LocalFree": lambda pointer: released.append(pointer.value)}
        native.api = lambda _dll, name, *_types: functions[name]
        return native, released

    def test_acl_read_grants_do_not_imply_write(self):
        native, released = self.security()
        self.assertEqual(len(native.security(123)), 64)
        self.assertEqual(released, [200])

    def test_acl_unknown_owner_write_grants_null_and_object_aces_rejected(self):
        for options in ({"owner": "S-1-5-21-9-9-9-999"}, {"mask": 2}, {"mask": 0x100},
                        {"mask": 0x40000}, {"mask": 0x40000000}, {"null_acl": True}, {"kind": 5}):
            with self.subTest(options=options):
                native, released = self.security(**options)
                with self.assertRaises(RuntimeError):
                    native.security(123)
                self.assertEqual(released, [200])

    def tcp(self, *, fault=None):
        import struct
        native = self.adapter()
        c = native.c
        swapped = (49100 & 255) << 8 | 49100 >> 8
        ipv4 = struct.pack("<I6I", 1, 2, 0x0100007F, swapped, 0, 0, 800)
        ipv6 = struct.pack("<I", 1) + b"\x00" * 15 + b"\x01" + struct.pack("<II", 0, swapped)
        ipv6 += b"\x00" * 16 + struct.pack("<IIII", 0, 0, 2, 700)
        tables = {2: ipv4, 23: ipv6}

        def get_table(buffer, size, ordered, family, kind, reserved):
            self.assertEqual((ordered, kind, reserved), (False, 3, 0))
            pointer = c.cast(size, c.POINTER(native.w.DWORD))
            if fault == "denied":
                return 5
            if buffer is None:
                pointer.contents.value = 1048577 if fault == "oversize" else len(tables[family])
                return 122
            if fault == "table-race":
                return 122
            body = tables[family]
            if fault == "count":
                body = struct.pack("<I", 8193) + body[4:]
            c.memmove(buffer, body, len(body))
            return 0

        native.api = lambda _dll, name, *_types: {"GetExtendedTcpTable": get_table}[name]
        return native

    def test_ipv4_ipv6_tcp_owner_table_layout_and_network_byte_order(self):
        self.assertEqual(self.tcp().listeners(), [("127.0.0.1", 49100, 800), ("::1", 49100, 700)])

    def test_tcp_table_denial_growth_and_bad_counts_fail_closed(self):
        for fault in ("denied", "oversize", "table-race", "count"):
            with self.subTest(fault=fault), self.assertRaisesRegex(RuntimeError, "METADATA_UNAVAILABLE"):
                self.tcp(fault=fault).listeners()

    def test_exists_catches_only_missing_not_access_denial(self):
        with patch("pathlib.Path.lstat", side_effect=FileNotFoundError):
            self.assertFalse(probe.WindowsAgentIO.exists(r"C:\H3Synthetic\missing"))
        with patch("pathlib.Path.lstat", side_effect=PermissionError), self.assertRaises(PermissionError):
            probe.WindowsAgentIO.exists(r"C:\H3Synthetic\denied")

    def test_process_identity_uses_retained_handle_and_token(self):
        import types
        native = self.adapter()
        c, w = native.c, native.w
        handle = 0x123456789  # Detect accidental 32-bit/numeric-PID substitution.
        process = types.SimpleNamespace(pid=999, _handle=handle, poll=lambda: None)
        closed = []

        def image(actual, flags, buffer, length):
            self.assertEqual((actual, flags), (handle, 0))
            buffer.value = _SocketIO.executable
            c.cast(length, c.POINTER(w.DWORD)).contents.value = len(buffer.value)
            return 1

        def times(actual, created, *_rest):
            self.assertEqual(actual, handle)
            c.cast(created, c.POINTER(w.FILETIME)).contents.dwLowDateTime = 101
            return 1

        def open_token(actual, access, token):
            self.assertEqual((actual, access), (handle, 8))
            c.cast(token, c.POINTER(w.HANDLE)).contents.value = 900
            return 1

        def get_token(token, kind, buffer, length, size):
            self.assertEqual((token.value, kind), (900, 1))
            c.cast(size, c.POINTER(w.DWORD)).contents.value = 32
            if buffer is None:
                return 0
            c.c_void_p.from_buffer(buffer).value = 901
            return 1

        functions = {"GetProcessId": lambda actual: 800 if actual == handle else 0,
                     "QueryFullProcessImageNameW": image, "GetProcessTimes": times,
                     "OpenProcessToken": open_token, "GetTokenInformation": get_token,
                     "CloseHandle": lambda value: closed.append(value.value) or 1}
        native.api = lambda _dll, name, *_types: functions[name]  # OpenProcess is deliberately absent.
        native.sid_text = lambda pointer: _SocketIO.sid if pointer.value == 901 else "bad"
        self.assertEqual(native.process_identity(process), {"pid": 800, "path": _SocketIO.executable,
                                                           "sid": _SocketIO.sid, "created": 101})
        self.assertEqual(closed, [900])

    def test_binary_pin_failure_precedes_popen(self):
        import subprocess
        import types
        native = self.adapter()
        native.module.native_path = lambda _value: types.SimpleNamespace(read_bytes=lambda: b"changed")
        with patch.object(subprocess, "Popen", side_effect=AssertionError("must not launch")), \
             self.assertRaisesRegex(RuntimeError, "TOOL_CHANGED"):
            native.spawn([_SocketIO.executable], "a" * 64)
