"""CE LuaPipe and overlapped Win32 model integration; no native handles."""
import ast
import importlib
from copy import deepcopy
import pytest

from ce_qualification.native_probe_protocol import ProbeError, canonical, frame, reply_to
from ce_qualification.native_probe_winpipe import NativeProvider, pipe_spec, EpochRegistry, SyntheticServer
from native_probe_fakes import ROOT, error_code
from native_probe_b0_fakes import equipment, ENDPOINT, SECRET, CHALLENGES


@pytest.mark.parametrize("backend", ["lua53", "lua54"])
@pytest.mark.parametrize("parameter", [25, 100, 250])
@pytest.mark.parametrize("size", [1, 127, 4096])
def test_N04_N05_ce_winpipe_adapter_roundtrip(backend, parameter, size):
    h, s, p, ce, *_ = equipment(backend=backend, parameter=parameter)
    ce.read_size = ce.write_size = p.short_write = size
    h.exchange("HELLO", "hello")
    payload = "\x00你好🙂" * 600
    assert h.exchange("ECHO", "echo", payload)["payload"] == payload
    h.exchange("PING", "ping"); h.exchange("CLOSE", "close")
    assert h.close() == "CLOSED" and ce.resources == 0 and p.calls.count("close") == 1
    assert ce.connect_calls == 1 and ce.destroy_calls == 1
    assert ce.pipe[b"Timeout"] == 1 and ce.pipe[b"OnAboutToTimeout"]() is True


@pytest.mark.parametrize("backend", ["lua53", "lua54"])
def test_N04_maximum_body_and_exact_observed_byte_counts(backend):
    h, s, p, ce, _, _, events, host, _ = equipment(backend=backend)
    h.exchange("HELLO", "hello")
    probe = {"schema": "qsg.native-probe.v1", "origin": "SYNTHETIC", "kind": "REQUEST", "method": "ECHO",
             "session_id": "b0", "channel_id": "channel", "epoch": 1, "request_id": "max", "sequence": 2,
             "payload": "", "request_sha256": "", "result": ""}
    payload = "x" * (65536 - len(canonical(reply_to(probe))))
    result = h.exchange("ECHO", "max", payload)
    assert len(frame(result)) == 65540
    writes = sum(e["returned_bytes"] for e in events if e["kind"] == "WRITE")
    reads = sum(e["returned_bytes"] for e in events if e["kind"] == "READ")
    assert writes == ce.sent_bytes and reads == ce.received_bytes
    h.close()


def test_N02_constructing_model_is_inert_and_native_provider_cannot_enter():
    h, s, p, ce, *_ = equipment(open_now=False)
    assert p.calls == [] and ce.connect_calls == 0 and ce.load_attempts() == 0
    with pytest.raises(ProbeError, match="SYNTHETIC_PROVIDER_REQUIRED"):
        SyntheticServer(NativeProvider(), lambda: 0, lambda _: None, s.expected, EpochRegistry(), secret=SECRET, challenges=CHALLENGES)
    assert p.calls == []


def test_N03_explicit_dacl_access_masks_and_first_instance():
    _, s, p, *_ = equipment()
    assert p.spec["open_mode"] == 0x40080003 and p.spec["pipe_mode"] == 8
    assert p.spec["max_instances"] == 1 and p.spec["inheritable"] is False
    assert p.spec["client_access"] & 4 == 0 and "D:P" in p.spec["sddl"]
    assert "WD" not in p.spec["sddl"]
    s.close()


@pytest.mark.parametrize("fault", ["create", "invalid_handle", "closed", "peer", "mutual", "result", "short_zero", "overlong", "operation"])
def test_N03_N07_N08_host_failures_close_without_retry(fault):
    h, s, p, ce, *_ = equipment(open_now=False)
    if fault == "create": p.create = lambda _spec: (_ for _ in ()).throw(OSError("model create failure"))
    elif fault == "invalid_handle": p.create = lambda _spec: 0
    elif fault == "peer": p.proof["client"]["creation"] = "0000000000000099"
    elif fault == "mutual": p.challenge = lambda *_: {"CLIENT": "0" * 64, "SERVER": "0" * 64}
    if fault in ("create", "invalid_handle", "peer", "mutual"):
        assert error_code(lambda: s.open(ENDPOINT, deadline_ms=250)) != "ACCEPTED"
    else:
        s.open(ENDPOINT, deadline_ms=250)
        if fault == "closed": p.closed = True
        else:
            original = p.start_io
            def broken(handle, op, direction, data, maximum):
                answer = original(handle, op, direction, data, maximum)
                if fault == "result": answer["count"] = True
                elif fault == "short_zero": answer["count"] = 0
                elif fault == "overlong": answer["count"] = 5000
                elif fault == "operation": answer["operation"] = "old-operation"
                return answer
            p.start_io = broken
        assert error_code(lambda: h.exchange("HELLO", "hello")) != "ACCEPTED"
    assert s.revoked
    calls = len(p.calls)
    assert error_code(lambda: h.exchange("HELLO", "retry")) != "ACCEPTED"
    assert p.calls.count("create") <= 1


@pytest.mark.parametrize("failure", ["nil", "zero", "partial", "sparse", "bad_byte", "oversize"])
def test_N04_ce_read_result_classes(failure):
    h, s, p, ce, *_ = equipment()
    if failure == "partial":
        ce.read_size = 1
        assert h.exchange("HELLO", "hello")["result"] == "OK"
    else:
        values = {"nil": None, "zero": [], "sparse": {2: 1}, "bad_byte": [256], "oversize": [1] * 4097}
        ce.read_override = lambda _: None if failure == "nil" else ce.lua.table_from(values[failure])
        assert error_code(lambda: h.exchange("HELLO", "hello")) != "ACCEPTED"
    h.close()


@pytest.mark.parametrize("count", [None, 0, -1, True, 65537])
def test_N04_ce_write_invalid_counts(count):
    h, s, p, ce, *_ = equipment()
    ce.write_override = lambda *_: count
    assert error_code(lambda: h.exchange("HELLO", "hello")) != "ACCEPTED"


@pytest.mark.parametrize("source", ["owner", "watchdog", "watchdog_failure", "ce"])
def test_N05_fixed_deadline_and_independent_watchdog(source):
    h, s, p, ce, c, wc, *_ = equipment()
    if source == "owner": p.hook = lambda _: c.advance(125)
    elif source == "watchdog": p.hook = lambda _: wc.advance(2000)
    elif source == "watchdog_failure": h.watchdog_clock = lambda: (_ for _ in ()).throw(RuntimeError("model watchdog unavailable"))
    else: ce.read_hook = lambda: ce.clock.advance(250)
    assert error_code(lambda: h.exchange("HELLO", "hello")) != "ACCEPTED"
    assert h.closed and h.session.pending is None


def test_N05_late_native_model_completion_counts_are_retained_but_not_accepted():
    h, s, p, ce, c, _, events, host_events, _ = equipment()
    p.hook = lambda direction: c.advance(250) if direction == "READ" else None
    assert error_code(lambda: h.exchange("HELLO", "hello")) == "REQUEST_TIMEOUT"
    assert any(e["kind"] == "READ" and e["returned_bytes"] > 0 for e in events)
    assert not any(kind == "ACCEPT" for kind, _ in host_events)


@pytest.mark.parametrize("mutation", ["zero", "oversize", "truncated", "merged", "utf8", "unknown", "replay"])
def test_N04_N08_malformed_frames_through_ce_pipe_adapter(mutation):
    import struct
    from native_probe_suite import packet, raw_packet
    h, s, p, ce, *_ = equipment()
    request = packet(session_id="b0", channel_id="channel")
    raw = frame(request)
    if mutation == "zero": raw = b"\0" * 4
    elif mutation == "oversize": raw = struct.pack("<I", 65537)
    elif mutation == "truncated": raw = raw[:-1]
    elif mutation == "merged": raw += raw
    elif mutation == "utf8": raw = struct.pack("<I", 1) + b"\xff"
    elif mutation == "unknown": raw = raw_packet({**request, "target_pid": 1})
    elif mutation == "replay": ce.send(raw); assert ce.receive(4096)
    ce.send(raw)
    if mutation == "truncated":
        assert ce.receive(4096) == b""
        ce.clock.advance(250)
    assert error_code(lambda: ce.receive(4096)) != "ACCEPTED"
    ce.close()


@pytest.mark.parametrize("stage", ["before", "WRITE", "READ", "after"])
def test_N06_cancel_suppresses_future_reply(stage):
    h, s, p, ce, *_ = equipment()
    if stage == "before": h.cancel()
    elif stage == "after": h.exchange("HELLO", "hello"); h.cancel()
    else: p.hook = lambda action: h.cancel() if action == stage else None
    assert error_code(lambda: h.exchange("HELLO" if stage != "after" else "PING", "next")) != "ACCEPTED"
    assert h.closed and h.session.pending is None


@pytest.mark.parametrize("allow_cancel", [False, True])
def test_N06_pending_cancel_is_not_completion_and_retains_buffers(allow_cancel):
    h, s, p, ce, c, _, *_ = equipment(allow_cancel=allow_cancel)
    p.pending_direction = "READ"
    p.hook = lambda direction: c.advance(10) if direction == "POLL" else None
    assert error_code(lambda: h.exchange("HELLO", "hello")) == "REQUEST_TIMEOUT"
    assert s.pending is not None and s.cleanup == "UNCERTAIN" and "close" not in p.calls
    assert p.calls.count("cancel") == int(allow_cancel)
    assert s.close() is False and p.calls.count("cancel") == int(allow_cancel)
    p.poll_result = {"operation": s.pending["operation"], "status": "ABORTED", "count": 0, "data": b""}
    assert s.observe_cleanup() == "CLOSED" and s.revoked and ce.resources == 0
    assert error_code(lambda: h.exchange("PING", "late")) != "ACCEPTED"


def test_N07_epoch_and_endpoint_cannot_be_reused_after_close():
    _, s, p, *_ = equipment(); s.close()
    with pytest.raises(ProbeError, match="EPOCH_REPLAY"): s.registry.consume(ENDPOINT, s.expected)
    changed = deepcopy(s.expected); changed["channel_id"] = "new-channel"
    with pytest.raises(ProbeError, match="EPOCH_REPLAY"): s.registry.consume(ENDPOINT.replace("a", "b"), changed)


def test_N09_twenty_cycles_and_uncertain_close_remain_distinct():
    for _ in range(20):
        h, s, p, ce, *_ = equipment(); h.exchange("HELLO", "hello"); h.close(); h.close()
        assert ce.resources == 0 and p.calls.count("close") == 1
    h, s, p, ce, *_ = equipment(); p.close_result = False
    assert h.close() == h.close() == "INDETERMINATE" and s.cleanup == "UNCERTAIN"


def test_N02_new_module_imports_have_no_native_or_ledger_dependencies():
    forbidden = {"ctypes", "os", "subprocess", "socket", "threading", "multiprocessing", "sqlite3", "win32pipe",
                 "qsg_store", "qsg_broker", "budget", "target"}
    for name in ("native_probe_winpipe", "native_probe_peer", "native_probe_admission"):
        path = ROOT / "src/ce_qualification" / (name + ".py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import): assert not any(a.name.split('.')[0] in forbidden for a in node.names)
            elif isinstance(node, ast.ImportFrom): assert (node.module or '').split('.')[0] not in forbidden
        importlib.import_module("ce_qualification." + name)


@pytest.fixture(scope="module")
def adapter_bundle(tmp_path_factory):
    from native_probe_b0_suite import build_adapters
    path = tmp_path_factory.mktemp("b0-evidence") / "pristine"
    seal, trace_seal, _ = build_adapters(path, "c" * 64, "a" * 64)
    return path, seal, trace_seal


def test_N01_N09_independent_adapter_byte_replay(adapter_bundle):
    from ce_qualification.native_probe_verifier import verify, verify_adapter_traces
    from ce_qualification.native_probe_protocol import sha256
    from native_probe_suite import PLAN
    path, seal, trace = adapter_bundle
    original = verify(path / "evidence.json", seal, PLAN, sha256(PLAN.read_bytes()), "c" * 64, "a" * 64)
    assert original["status"] == "SYNTHETIC_PASS", original
    result = verify_adapter_traces(path / "adapter-traces.json", trace, path / "evidence.json", seal, "c" * 64, "a" * 64)
    assert result == {"status": "SYNTHETIC_PASS", "errors": [], "missing": [], "sessions": 21}


@pytest.mark.parametrize("mutation", ["origin", "omission", "session", "replay", "count", "digest", "peer", "terminal", "watchdog", "anchor"])
def test_N09_independent_adapter_mutation_omission_replay(adapter_bundle, tmp_path, mutation):
    from ce_qualification.native_probe_verifier import verify_adapter_traces
    from ce_qualification.native_probe_protocol import sha256, decode
    path, seal, trace_seal = adapter_bundle
    trace = decode((path / "adapter-traces.json").read_bytes())
    sid = next(iter(trace["sessions"])); session = trace["sessions"][sid]
    events = session["events"]; idx = next(i for i, e in enumerate(events) if e["kind"] == "WRITE")
    if mutation == "origin": trace["origin"] = "NATIVE"
    elif mutation == "omission": del events[idx]
    elif mutation == "session": del trace["sessions"][sid]
    elif mutation == "replay": events.insert(idx, deepcopy(events[idx]))
    elif mutation == "count": events[idx]["returned_bytes"] -= 1
    elif mutation == "digest": events[idx]["sha256"] = "0" * 64
    elif mutation == "peer": session["peer"]["client"]["creation"] = "0000000000000099"
    elif mutation == "terminal": events.pop()
    elif mutation == "watchdog": session["watchdog_events"].pop()
    raw = canonical(trace); target = tmp_path / "mutated.json"; target.write_bytes(raw)
    result = verify_adapter_traces(target, "0" * 64 if mutation == "anchor" else sha256(raw),
                                  path / "evidence.json", seal, "c" * 64, "a" * 64)
    assert result["status"] != "SYNTHETIC_PASS", result
