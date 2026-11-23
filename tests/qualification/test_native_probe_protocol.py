"""Adversarial frame and authority boundary tests, entirely offline."""
from copy import deepcopy
import random
import struct

import pytest

from ce_qualification.native_probe_protocol import (Decoder, ProbeError, Session, canonical, check_challenge,
    challenge_response, decode, frame, native_admission, reply_to, validate_peer_model)
from native_probe_fakes import Clock, peer_fixture
from native_probe_suite import packet, raw_packet, ready_session


@pytest.mark.parametrize("length", [1, 4095, 4096, 4097, 65535, 65536])
def test_N04_body_boundaries(length):
    p = packet("ECHO")
    overhead = len(canonical(p))
    if length < overhead:
        with pytest.raises(ProbeError):
            Decoder(250, Clock()).feed(struct.pack("<I", length) + b"x" * length, final=True)
        return
    p["payload"] = "x" * (length - overhead)
    raw = frame(p)
    assert len(raw) == length + 4
    assert Decoder(250, Clock()).feed(raw, final=True) == p


@pytest.mark.parametrize("cut", [1, 2, 3, 4, 5, 7, 127, 4095, 4096, 4097])
def test_N04_fragmentation_preserves_exact_bytes(cut):
    p = packet("ECHO", payload="你好🙂" * 600)
    raw = frame(p)
    decoder = Decoder(250, Clock())
    assert decoder.feed(raw[:cut]) is None
    assert decoder.feed(raw[cut:], final=True) == p
    with pytest.raises(ProbeError, match="FRAME_TERMINAL"):
        decoder.feed(raw)


@pytest.mark.parametrize("edit", [
    {"schema": "qsg.mock.v1"}, {"origin": "NATIVE"}, {"epoch": True}, {"sequence": False},
    {"sequence": 0}, {"sequence": 2147483648}, {"epoch": -1}, {"kind": "COMMAND"},
    {"method": "reserve"}, {"method": "claim"}, {"method": "writeFloat"}, {"method": "SHELL"},
    {"target_pid": 1}, {"address": "1000"}, {"lua": "print(1)"}, {"path": "ledger.sqlite"},
    {"payload": "nonempty-control"}, {"session_id": "../name"}, {"request_id": ""},
    {"request_sha256": "a" * 64}, {"result": "OK"}, {"payload": []}, {"method": []},
])
def test_N08_strict_whitelist(edit):
    with pytest.raises((ProbeError, TypeError)):
        Decoder(250, Clock()).feed(raw_packet(packet(**edit)), final=True)


def invalid_bodies():
    raw = canonical(packet())
    return [raw.replace(b'"epoch":1', b'"epoch":1.0'), raw.replace(b'"epoch":1', b'"epoch":1e0'),
            raw.replace(b'"epoch":1', b'"epoch":NaN'), raw.replace(b'"epoch":1', b'"epoch":Infinity'),
            raw.replace(b'"epoch":1', b'"epoch":01'), raw.replace(b'"epoch":1', b'"epoch":-0'),
            b" " + raw, raw + b"\n", b"\xef\xbb\xbf" + raw,
            raw.replace(b'"schema":', b'"schema" :'), raw.replace(b'"test"', b'"te\\u0073t"'),
            raw.replace(b'"test"', b'"\xff"'), raw.replace(b'"test"', b'"\xc0\xaf"'),
            raw.replace(b'"test"', b'"\xed\xa0\x80"'), raw[:-1] + b',"epoch":1}',
            b"[]", b"null", b"true", b'{"nested":' + b"[" * 1000 + b"]" * 1000 + b"}"]


@pytest.mark.parametrize("body", invalid_bodies())
def test_N04_noncanonical_and_invalid_utf8(body):
    with pytest.raises((ProbeError, TypeError)):
        Decoder(250, Clock()).feed(struct.pack("<I", len(body)) + body, final=True)


@pytest.mark.parametrize("length", [0, 65537, 0xFFFFFFFF])
def test_N08_reject_header_before_body_allocation(length):
    decoder = Decoder(250, Clock())
    with pytest.raises(ProbeError, match="FRAME_LENGTH"):
        decoder.feed(struct.pack("<I", length) + b"x" * 4096)
    assert len(decoder.body) == 0
    with pytest.raises(ProbeError, match="FRAME_TERMINAL"):
        decoder.feed(frame(packet()))


@pytest.mark.parametrize("length", [0, 1, 2, 3, 4, 10])
def test_N04_truncation(length):
    with pytest.raises(ProbeError, match="TRUNCATED_FRAME"):
        Decoder(250, Clock()).feed(frame(packet())[:length], final=True)


def test_N04_deterministic_fuzz_256_vectors():
    rng = random.Random(73013)
    raw = frame(packet("ECHO", payload="x" * 120))
    for _ in range(256):
        altered = bytearray(raw)
        pos = rng.randrange(len(raw)); altered[pos] ^= 1 << rng.randrange(8)
        decoder = Decoder(250, Clock())
        try:
            result = decoder.feed(bytes(altered), final=True)
        except (ProbeError, TypeError):
            assert decoder.failed
        else:
            assert frame(result) == bytes(altered)


@pytest.mark.parametrize("field,value", [("session_id", "other"), ("channel_id", "other"), ("epoch", 2),
    ("request_id", "other"), ("sequence", 99), ("method", "ECHO"), ("request_sha256", "0" * 64)])
def test_N07_reply_correlation(field, value):
    session = ready_session()
    request = decode(session.begin("PING", "p")[4:])
    reply = {**reply_to(request), field: value}
    with pytest.raises(ProbeError):
        session.accept(reply)
    assert session.pending is None and session.state == "FAILED"


def test_N05_deadline_not_refreshed_and_clock_rollback():
    clock = Clock()
    decoder = Decoder(250, clock)
    raw = frame(packet())
    for index, value in enumerate([0, 100, 249]):
        clock.value = value
        assert decoder.feed(raw[index:index + 1]) is None
    clock.value = 250
    with pytest.raises(ProbeError, match="REQUEST_TIMEOUT"):
        decoder.feed(raw[3:])
    clock.value = 10; decoder = Decoder(250, clock); decoder.feed(raw[:1]); clock.value = 9
    with pytest.raises(ProbeError, match="CLOCK_REVERSED"):
        decoder.feed(raw[1:])


def test_N08_replay_and_double_start_fail_closed():
    s = ready_session(); raw = s.begin("PING", "p")
    with pytest.raises(ProbeError, match="SESSION_NOT_READY"):
        s.begin("PING", "second")
    with pytest.raises(ProbeError, match="NO_PENDING_REQUEST"):
        s.accept(reply_to(decode(raw[4:])))
    s = ready_session(); req = decode(s.begin("PING", "p")[4:]); s.accept(reply_to(req))
    with pytest.raises(ProbeError, match="REQUEST_REPLAY"):
        s.begin("PING", "p")


@pytest.mark.parametrize("field,value", [("principal", "UNKNOWN"), ("owner", "UNKNOWN"), ("client_pid", 0),
    ("server_pid", True), ("client_creation", "0000000000000000"), ("dacl", "UNKNOWN"),
    ("client_handle", "UNKNOWN"), ("os_evidence", "VERIFIED"), ("authenticated", True)])
def test_N03_missing_or_bad_peer_proof(field, value):
    proof = peer_fixture(); altered = {**proof, field: value}
    with pytest.raises(ProbeError):
        validate_peer_model(altered, altered, used_epochs=set())


@pytest.mark.parametrize("proof", [None, {}, {"signed": True}, {"authenticated": True}, {"origin": "NATIVE"},
    {"scope": "R3-B", "signature": "fixture", "expires": "2099-01-01"}])
def test_N01_native_gate_has_no_data_bypass(proof):
    with pytest.raises(ProbeError, match="R3_B_NOT_AUTHORIZED"):
        native_admission(proof)


def test_N03_bilateral_role_epoch_and_secret_binding():
    p = peer_fixture(); binding = {k: p[k] for k in ("session_id", "channel_id", "epoch")}
    secret = b"test" * 8
    proof = challenge_response(secret, binding, p["client_challenge"], p["server_challenge"], "CLIENT")
    for other_secret, other_binding, role in [(b"bad!" * 8, binding, "CLIENT"),
                                             (secret, {**binding, "epoch": 2}, "CLIENT"), (secret, binding, "SERVER")]:
        with pytest.raises(ProbeError, match="CHALLENGE_MISMATCH"):
            check_challenge(other_secret, other_binding, p["client_challenge"], p["server_challenge"], role, proof)
