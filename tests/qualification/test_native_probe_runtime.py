"""Real standalone Lua 5.3/5.4 with in-memory transports, not CE's Lua."""
import ast
import hashlib
import importlib
from pathlib import Path

import pytest

from ce_qualification.native_ipc_probe import Coordinator, main
from ce_qualification.native_probe_protocol import ProbeError, canonical, frame, reply_to
from ce_qualification.native_probe_watchdog import Limits, Watchdog
from native_probe_fakes import Clock, LuaTransport, ROOT, error_code, load_probe
from native_probe_suite import packet, raw_packet


@pytest.mark.parametrize("backend", ["lua53", "lua54"])
@pytest.mark.parametrize("raw", [b"", b"abc", b"x" * 4096, b"x" * 65536], ids=["empty", "abc", "4096", "65536"])
def test_N04_lua_sha256_matches_independent_python(backend, raw):
    _, module, _, calls = load_probe(backend)
    assert module[b"sha256"](raw).decode() == hashlib.sha256(raw).hexdigest()
    assert calls() == 0


@pytest.mark.parametrize("backend", ["lua53", "lua54"])
def test_N02_lazy_duplicate_load_native_block(backend):
    _, one, two, calls = load_probe(backend)
    assert calls() == 0
    assert one[b"version"] == two[b"version"] == b"qsg.native-probe.v1"
    assert error_code(one[b"start_native"]) == "R3_B_NOT_AUTHORIZED"
    assert calls() == 0


@pytest.mark.parametrize("backend", ["lua53", "lua54"])
@pytest.mark.parametrize("size", [1, 127, 4096])
def test_N04_lua_host_byte_interop(backend, size):
    t = LuaTransport({"session_id": "offline", "channel_id": "fake", "epoch": 1},
                     backend=backend, read_size=size, write_size=size)
    h = Coordinator(t, Clock(), lambda *_a, **_k: None, enabled=True)
    h.exchange("HELLO", "hello")
    payload = "\x00\b\t\n\f\r\\\"/你好🙂" * 320
    assert h.exchange("ECHO", "echo", payload)["payload"] == payload
    h.exchange("PING", "ping")
    h.exchange("CANCEL", "cancel")
    assert t.resources == 0
    assert h.close() == "CLOSED" and t.close_calls == 1


@pytest.mark.parametrize("backend", ["lua53", "lua54"])
@pytest.mark.parametrize("raw", [b"\0" * 4, b"\xff" * 4, b"x", frame(packet()) + b"x",
    raw_packet(packet(method="claim")), raw_packet(packet(epoch=True)), raw_packet(packet(target_pid=1)),
    b'\x02\0\0\0{}', b'\x04\0\0\0null'])
def test_N08_lua_rejects_corrupt_and_forbidden_frames(backend, raw):
    _, module, _, _ = load_probe(backend)
    assert error_code(lambda: module[b"decode_frame"](raw)) != "ACCEPTED"


def test_N05_lua_wait_is_cooperative_and_times_out():
    c = Clock(); t = LuaTransport({"session_id": "offline", "channel_id": "fake", "epoch": 1}, c)
    assert t.worker[b"step"]() == b"WAIT"
    c.value = 249; assert t.worker[b"step"]() == b"WAIT"
    c.value = 250; assert error_code(t.worker[b"step"]) == "REQUEST_TIMEOUT"
    t.close(); assert t.resources == 0


@pytest.mark.parametrize("stage", ["send", "receive"])
def test_N06_cancel_inflight_invalidates_and_closes(stage):
    t = LuaTransport({"session_id": "offline", "channel_id": "fake", "epoch": 1})
    h = Coordinator(t, Clock(), lambda *_a, **_k: None, enabled=True)
    t.hook = lambda s: h.cancel() if s == stage else None
    with pytest.raises(ProbeError, match="CANCELLED|DISCONNECTED"):
        h.exchange("HELLO", "hello")
    assert h.closed and h.session.pending is None and t.resources == 0


@pytest.mark.parametrize("answer", [0, -1, True, 5000, None])
def test_N04_invalid_send_counts(answer):
    t = LuaTransport({"session_id": "offline", "channel_id": "fake", "epoch": 1})
    t.send = lambda _: answer
    h = Coordinator(t, Clock(), lambda *_a, **_k: None, enabled=True)
    with pytest.raises(ProbeError, match="SHORT_OR_INVALID_SEND"):
        h.exchange("HELLO", "hello")
    assert t.resources == 0


def test_N05_api_return_after_deadline_never_accepted():
    clock = Clock()
    t = LuaTransport({"session_id": "offline", "channel_id": "fake", "epoch": 1})
    original = t.receive
    def delayed(n):
        raw = original(n); clock.advance(250); return raw
    t.receive = delayed
    h = Coordinator(t, clock, lambda *_a, **_k: None, enabled=True)
    with pytest.raises(ProbeError, match="REQUEST_TIMEOUT"):
        h.exchange("HELLO", "hello")
    assert t.resources == 0


def test_N06_reentry_from_transport_is_fail_closed():
    t = LuaTransport({"session_id": "offline", "channel_id": "fake", "epoch": 1})
    h = Coordinator(t, Clock(), lambda *_a, **_k: None, enabled=True)
    t.hook = lambda _: h.exchange("PING", "nested")
    with pytest.raises(ProbeError, match="REENTRANT_REQUEST"):
        h.exchange("HELLO", "hello")
    assert t.resources == 0


@pytest.mark.parametrize("stage", ["before", "during", "after"])
def test_N06_watchdog_cancellation_requires_observation(stage):
    c = Clock(); events = []
    w = Watchdog(c, lambda *e: events.append(e), enabled=True)
    w.arm("r1")
    if stage == "during": c.advance(249)
    if stage == "after": c.advance(250); w.poll()
    w.cancel()
    assert w.state == "CANCEL_REQUESTED"
    assert w.observe_completion(io_completed=False, resources_closed=True) == "INDETERMINATE"


def test_N05_watchdog_cutoff_and_clock_are_independent():
    c = Clock(1000000); w = Watchdog(c, lambda *_: None, enabled=True); w.arm("r")
    c.advance(249); assert w.poll() == "ARMED"
    c.advance(1); assert w.poll() == "DEADLINE"
    c.advance(1749); assert w.poll() == "DEADLINE"
    c.advance(1); assert w.poll() == "INDETERMINATE"
    assert w.observe_completion(io_completed=True, resources_closed=True) == "INDETERMINATE"
    c.value = 1
    with pytest.raises(ProbeError, match="WATCHDOG_CLOCK"): w.poll()


def test_N05_case_and_session_limits_exact_boundary():
    c = Clock(); limits = Limits(c); limits.start_case()
    c.value = 59999; limits.check()
    c.value = 60000
    with pytest.raises(ProbeError, match="CASE_TIMEOUT"): limits.check()
    with pytest.raises(ProbeError, match="LIMITS_CLOSED"): limits.finish_case()
    c = Clock(); limits = Limits(c)
    c.value = 899999; limits.check()
    c.value = 900000
    with pytest.raises(ProbeError, match="SESSION_TIMEOUT"): limits.start_case()


@pytest.mark.parametrize("backend", ["lua53", "lua54"])
@pytest.mark.parametrize("bad", ["duplicate", "noncanonical", "utf8", "control", "float", "boolean"])
def test_N04_lua_canonical_adversarial_vectors(backend, bad):
    _, module, _, _ = load_probe(backend)
    body = canonical(packet())
    if bad == "duplicate": body = body[:-1] + b',"epoch":1}'
    elif bad == "noncanonical": body = body.replace(b'"epoch":1', b'"epoch":01')
    elif bad == "utf8": body = body.replace(b'"test"', b'"\xff"')
    elif bad == "control": body = body.replace(b'"test"', b'"t\x01est"')
    elif bad == "float": body = body.replace(b'"epoch":1', b'"epoch":1.0')
    elif bad == "boolean": body = body.replace(b'"epoch":1', b'"epoch":true')
    import struct
    assert error_code(lambda: module[b"decode_frame"](struct.pack("<I", len(body)) + body)) != "ACCEPTED"


def test_N07_lua_restart_and_replayed_hello_close_transport():
    t = LuaTransport({"session_id": "test", "channel_id": "fake", "epoch": 1})
    raw = frame(packet())
    t.send(raw); assert t.receive(4096)
    t.send(raw)
    assert error_code(lambda: t.receive(4096)) == "REQUEST_REPLAY"
    t.close(); assert t.resources == 0


def test_N06_close_during_wait_suppresses_reply():
    t = LuaTransport({"session_id": "offline", "channel_id": "fake", "epoch": 1})
    h = Coordinator(t, Clock(), lambda *_a, **_k: None, enabled=True)
    t.hook = lambda stage: h.close() if stage == "receive" else None
    with pytest.raises(ProbeError, match="CANCELLED"): h.exchange("HELLO", "hello")
    assert h.session.pending is None and t.resources == 0


def test_N09_cleanup_exception_is_not_success():
    t = LuaTransport({"session_id": "offline", "channel_id": "fake", "epoch": 1})
    original = t.close
    t.close = lambda: (_ for _ in ()).throw(RuntimeError("fake close failure"))
    h = Coordinator(t, Clock(), lambda *_a, **_k: None, enabled=True)
    assert h.close() == h.close() == "INDETERMINATE"
    assert t.resources == 2
    original()


def test_N01_cli_commands_and_default_off(capsys):
    assert main(["native"]) == 3
    assert "R3_B_NOT_AUTHORIZED" in capsys.readouterr().out
    assert main(["offline"]) == 0
    assert "SYNTHETIC_SMOKE_PASS" in capsys.readouterr().out
    with pytest.raises(ProbeError, match="OFFLINE_PROBE_DISABLED"):
        Coordinator(None, Clock(), lambda *_: None)


def test_N02_static_capability_and_import_audit():
    names = ["native_ipc_probe", "native_probe_protocol", "native_probe_watchdog", "native_probe_evidence",
             "native_probe_schema", "native_probe_verifier"]
    forbidden = {"ctypes", "subprocess", "socket", "multiprocessing", "win32pipe", "win32api",
                 "qsg_store", "qsg_broker", "budget", "target", "sqlite3", "os"}
    for name in names:
        source = (ROOT / "src/ce_qualification" / (name + ".py")).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): assert not any(a.name.split('.')[0] in forbidden for a in node.names)
            if isinstance(node, ast.ImportFrom): assert (node.module or '').split('.')[0] not in forbidden
        importlib.import_module("ce_qualification." + name)
    source = (ROOT / "src/qualification/native_ipc_probe.lua").read_text(encoding="utf-8")
    for token in ("_G", "require(", "dofile(", "loadfile(", "openProcess", "writeFloat", "createTimer", "createPipe"):
        assert token not in source
    # B0 only references the CE API through injected test equipment. The strict
    # Lua environment still rejects every ambient capability lookup at runtime.
    assert "provider.connectToPipe" in source
    verifier = (ROOT / "src/ce_qualification/native_probe_verifier.py").read_text(encoding="utf-8")
    imports = [n.module for n in ast.walk(ast.parse(verifier)) if isinstance(n, ast.ImportFrom)]
    assert not any(n in imports for n in ("native_ipc_probe", "native_probe_evidence", "native_probe_watchdog"))
