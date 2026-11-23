"""Executable offline evidence matrix; observations are not native attestations."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import struct

from ce_qualification.native_ipc_probe import Coordinator
from ce_qualification.native_probe_evidence import Recorder, export_bundle
from ce_qualification.native_probe_protocol import (Decoder, Session, canonical, check_challenge, challenge_response,
    decode, frame, native_admission, reply_to, require, sha256, validate_peer_model)
from ce_qualification.native_probe_watchdog import Watchdog
from native_probe_fakes import Clock, LuaTransport, ROOT, error_code, load_probe, peer_fixture, table

PLAN = ROOT / "tests/fixtures/qualification/native_probe_plan.json"


def packet(method="HELLO", **updates):
    value = {"schema": "qsg.native-probe.v1", "origin": "SYNTHETIC", "kind": "REQUEST", "method": method,
             "session_id": "test", "channel_id": "fake", "epoch": 1, "request_id": "r1", "sequence": 1,
             "payload": "", "request_sha256": "", "result": ""}
    return {**value, **updates}


def raw_packet(value):
    raw = canonical(value)
    return struct.pack("<I", len(raw)) + raw


def ready_session(clock=None):
    session = Session("test", "fake", 1, clock or Clock())
    hello = decode(session.begin("HELLO", "hello")[4:])
    session.accept(reply_to(hello))
    return session


def build(directory, candidate_sha256, authorization_sha256, *, transport_factory=None):
    # Tripwires make the zero-contact observation an executed assertion. Only
    # synthetic evidence files are exported; no QSG module/store is loaded.
    import builtins
    from unittest.mock import patch
    original_import = builtins.__import__
    contacts = []
    def blocked_store(*_args, **_kwargs):
        contacts.append("STORE_ACCESS")
        raise AssertionError("No ledger interface is authorized")
    def guarded_import(name, *args, **kwargs):
        if name.startswith("ce_qualification.qsg_") or name in ("ce_qualification.budget", "ce_qualification.target"):
            blocked_store()
        return original_import(name, *args, **kwargs)
    with patch("sqlite3.connect", blocked_store), patch("builtins.__import__", guarded_import):
        return _build(directory, candidate_sha256, authorization_sha256, contacts, transport_factory)


def _build(directory, candidate_sha256, authorization_sha256, ledger_contacts, transport_factory=None):
    clocks = {a: Clock(i * 10000) for i, a in enumerate(("HOST", "LUA_MODEL", "WATCHDOG", "OBSERVER"))}
    stamp = datetime.now(timezone.utc).isoformat()
    recorders = {a: Recorder(a, candidate_sha256, authorization_sha256, clocks[a], lambda: stamp, enabled=True) for a in clocks}
    observations = {}
    def note(case, name, value):
        observations[case, name] = value
        clocks["OBSERVER"].advance(1)
        recorders["OBSERVER"].append(case, "CHECK", data={"check_id": name, "observed": value})
    def host(case, sid, **kwargs):
        binding = {"session_id": sid, "channel_id": "fake", "epoch": 1}
        emit_lua = lambda kind, **kw: recorders["LUA_MODEL"].append(case, kind, binding=binding, **kw)
        emit_host = lambda kind, **kw: recorders["HOST"].append(case, kind, binding=binding, **kw)
        if transport_factory is not None:
            return transport_factory(binding, emit_host, emit_lua, clocks["HOST"], **kwargs)
        transport = LuaTransport(binding, emit=emit_lua, **kwargs)
        return Coordinator(transport, clocks["HOST"], emit_host, session_id=sid, enabled=True), transport
    def rejected(raw):
        return error_code(lambda: Decoder(250, Clock()).feed(raw, final=True))

    # N01 compares identity inputs as data only. Actual file hashes are separately
    # verified in the package baseline; no runtime PID/creation proof is invented.
    expected = {"candidate": candidate_sha256, "ce": "49cc24f682ff330631672dc89f2e4d7d277598d0d61541a3fee4dd3cd941583d",
                "dll": "436f6bf9ac414e7e7259bef4f6e287702a41e1fddbdd9af7d43350d47539a3c9"}
    def identity(observed):
        require(observed == expected, "IDENTITY_MISMATCH")
        return True
    note("N01", "identity_match", identity(dict(expected)))
    note("N01", "hash_mismatch", error_code(lambda: identity({**expected, "dll": "0" * 64})))
    note("N01", "native_admission", error_code(lambda: native_admission({"signed": True, "runtime": None})))
    note("N01", "runtime_evidence", "NOT_RUN")

    lua, module, second, attempts = load_probe()
    note("N02", "ambient_calls", attempts())
    note("N02", "duplicate_load_calls", attempts())
    note("N02", "native_start", error_code(module[b"start_native"]))
    bad_cap = table(lua, {"mode": "offline", "origin": "SYNTHETIC", "forbidden": True})
    note("N02", "capability_rejection", error_code(lambda: second[b"new_offline"](bad_cap, lua.table())))

    p, used = peer_fixture(), set()
    note("N03", "peer_model", validate_peer_model(p, p, used_epochs=used))
    note("N03", "epoch_replay", error_code(lambda: validate_peer_model(p, p, used_epochs=used)))
    for name, field, value in (("wrong_principal", "principal", "UNKNOWN"), ("missing_handle", "client_handle", "UNKNOWN"),
                               ("mock_os_proof", "os_evidence", "VERIFIED")):
        note("N03", name, error_code(lambda field=field, value=value: validate_peer_model({**p, field: value}, p, used_epochs=set())))
    binding = {k: p[k] for k in ("session_id", "channel_id", "epoch")}
    # Public fixture key only; neither this key nor any future secret enters logs.
    secret = b"public-offline-fixture-key-32bytes"
    responses = [challenge_response(secret, binding, p["client_challenge"], p["server_challenge"], role) for role in ("CLIENT", "SERVER")]
    note("N03", "bilateral_challenge", all(check_challenge(secret, binding, p["client_challenge"], p["server_challenge"], role, response)
         == "SYNTHETIC_CHALLENGE_ONLY" for role, response in zip(("CLIENT", "SERVER"), responses)))
    note("N03", "bad_challenge", error_code(lambda: check_challenge(secret, binding, p["client_challenge"], p["server_challenge"], "SERVER", responses[0])))

    h, t = host("N04", "SYNTHETIC-SIZES", read_size=127, write_size=113)
    h.exchange("HELLO", "hello")
    echoed = h.exchange("ECHO", "utf8", "离线\nprobe\\\"🙂")
    note("N04", "fragment_roundtrip", echoed["payload"] == "离线\nprobe\\\"🙂")
    h.exchange("ECHO", "cross4096", "x" * 4096)
    sample = packet("ECHO", session_id="SYNTHETIC-SIZES", request_id="max", sequence=4)
    payload_size = 65536 - len(canonical(reply_to(sample)))
    h.exchange("ECHO", "max", "x" * payload_size)
    h.exchange("PING", "ping")
    h.exchange("CLOSE", "close")
    note("N04", "max_body", 65536)
    normal = frame(packet())
    dup = canonical(packet())[:-1] + b',"schema":"qsg.native-probe.v1"}'
    note("N04", "duplicate_key", rejected(struct.pack("<I", len(dup)) + dup))
    note("N04", "short_header", rejected(normal[:3]))
    note("N04", "trailing_bytes", rejected(normal + normal))
    note("N04", "unknown_field", rejected(raw_packet({**packet(), "unknown": 1})))

    c = Clock(250)
    note("N05", "exact_deadline", error_code(lambda: Decoder(250, c).feed(normal)))
    c = Clock(); decoder = Decoder(250, c); decoder.feed(normal[:5]); c.advance(249); decoder.feed(normal[5:6]); c.advance(1)
    note("N05", "slow_fragments", error_code(lambda: decoder.feed(normal[6:])))
    c = Clock(); s = ready_session(c); request = decode(s.begin("PING", "late")[4:]); c.advance(250)
    note("N05", "late_reply", error_code(lambda: s.accept(reply_to(request))))
    wclock = clocks["WATCHDOG"]
    def watch_emit(kind, data):
        data = dict(data); request_id = data.pop("request_id")
        recorders["WATCHDOG"].append("N05", kind, request={"request_id": request_id}, data=data)
    watch = Watchdog(wclock, watch_emit, enabled=True); watch.arm("blocked-call")
    wclock.advance(250); watch.poll(); wclock.advance(1750)
    note("N05", "watchdog_cutoff", watch.poll())
    watch.observe_completion(io_completed=False, resources_closed=False)
    note("N05", "api_timeout_units", "UNKNOWN")

    # Cancellation cases use fresh isolated fakes, with no retry of old authority.
    def silent_host():
        t = LuaTransport({"session_id": "offline", "channel_id": "fake", "epoch": 1})
        return Coordinator(t, Clock(), lambda *_a, **_k: None, enabled=True), t
    h, t = silent_host(); h.cancel()
    note("N06", "before_cancel", error_code(lambda: h.exchange("HELLO", "h")))
    h, t = silent_host(); t.hook = lambda stage: h.cancel() if stage == "receive" else None
    note("N06", "during_cancel", error_code(lambda: h.exchange("HELLO", "h")))
    s = ready_session(); req = decode(s.begin("PING", "cancelled")[4:]); s.invalidate()
    note("N06", "after_cancel_reply", error_code(lambda: s.accept(reply_to(req))))
    idle = LuaTransport({"session_id": "idle", "channel_id": "fake", "epoch": 1})
    heartbeat = sum(idle.worker[b"step"]() == b"WAIT" for _ in range(3)); idle.close()
    note("N06", "heartbeat_steps", heartbeat)
    def cancel_watch_emit(kind, data):
        data = dict(data); request_id = data.pop("request_id")
        recorders["WATCHDOG"].append("N06", kind, request={"request_id": request_id}, data=data)
    wclock.advance(1)
    w = Watchdog(wclock, cancel_watch_emit, enabled=True); w.arm("cancel"); w.cancel()
    note("N06", "uncertain_cleanup", w.observe_completion(io_completed=False, resources_closed=False))

    h, t = silent_host(); t.receive = lambda _: b""
    note("N07", "disconnect", error_code(lambda: h.exchange("HELLO", "h")))
    note("N07", "resend", error_code(lambda: h.session.begin("PING", "again")))
    s = ready_session(); req = decode(s.begin("PING", "stale")[4:]); reply = reply_to(req); reply["epoch"] = 2
    note("N07", "stale_epoch", error_code(lambda: s.accept(reply)))
    note("N07", "restart_epoch", error_code(lambda: validate_peer_model(p, p, used_epochs=used)))

    s = ready_session(); req = decode(s.begin("PING", "wrong")[4:]); reply = reply_to(req); reply["session_id"] = "wrong"
    note("N08", "wrong_session", error_code(lambda: s.accept(reply)))
    s = ready_session(); req = decode(s.begin("PING", "replay")[4:]); reply = reply_to(req); s.accept(reply)
    note("N08", "replay", error_code(lambda: s.accept(reply)))
    note("N08", "oversize", rejected(struct.pack("<I", 65537)))
    note("N08", "zero_length", rejected(b"\0" * 4))
    note("N08", "invalid_method", rejected(raw_packet(packet("reserve"))))
    note("N08", "mock_version", rejected(raw_packet(packet(schema="qsg.mock.v1"))))

    resources, closes = 0, 0
    for i in range(20):
        h, t = host("N09", f"SYNTHETIC-CYCLE-{i:02}")
        h.exchange("HELLO", "hello")
        h.exchange("CLOSE", "close")
        h.close(); t.close()
        resources += t.resources; closes += t.close_calls
    note("N09", "cleanup_cycles", 20)
    note("N09", "orphan_resources", resources)
    note("N09", "close_calls", closes)
    # Imports/capabilities and guarded execution are separately tested; none of
    # these fakes has a ledger reference or filesystem/production-store interface.
    note("N09", "ledger_contacts", len(ledger_contacts))
    for recorder in recorders.values():
        recorder.finish()
    seal = export_bundle(directory, list(recorders.values()), PLAN.read_bytes(), candidate_sha256, authorization_sha256)
    return seal, observations


def main(argv=None):
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Offline N01-N09 evidence, standalone Lua only")
    parser.add_argument("--output", required=True)
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--authorization-sha256", required=True)
    args = parser.parse_args(argv)
    seal, observations = build(args.output, args.candidate_sha256, args.authorization_sha256)
    print(json.dumps({"manifest_sha256": seal, "observations": len(observations), "native": "NOT_RUN", "origin": "SYNTHETIC"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
