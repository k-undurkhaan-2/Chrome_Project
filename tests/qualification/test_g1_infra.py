"""G1 infrastructure acceptance, fakes only. No native target import/launch."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import threading

import pytest

from ce_qualification import budget as budget_module
from ce_qualification.budget import GateError, SessionGate, provision_synthetic
from ce_qualification.evidence import (EvidenceError, Stream, SyntheticClock, canonical,
    decode, digest, export_bundle, file_hash, validate_chain)
from ce_qualification.recorder import CERecorder
from ce_qualification.target import Instance, MockTransport, SyntheticMemory, TargetRecorder
from ce_qualification.verifier import verify_bundle, verify_streams
from support import (ROOT, SOURCES, ScenarioSession, gate_at, l12_evidence, layout,
                     plain, policy_for, request_for, target_policy, world)


def begin(gate, policy, run="run-1", scenario="L04"):
    target = policy["targets"][0]
    gate.start(run, scenario, target["identity"], target["allocation_id"])


def rechain(rows):
    """Adversarially re-seal fabricated evidence to test semantic validation."""
    previous = "0" * 64
    for i, row in enumerate(rows, 1):
        row["sequence"] = i; row["event_id"] = f"{row['source']}:{i}"
        row["predecessor_digest"] = previous
        row["content_digest"] = digest({k: v for k, v in row.items() if k != "content_digest"})
        previous = row["content_digest"]


@pytest.mark.parametrize("count", range(5))
def test_zero_through_four_attempts_and_restart_caps(tmp_path, count):
    gate, policy, seal = gate_at(tmp_path)
    attempted = []
    for n in range(count):
        scenario = ["L04", "L07", "L10", "L10"][n]
        run = f"run-{n}"
        begin(gate, policy, run, scenario)
        req = request_for(policy, run_id=run, scenario=scenario)
        if n == 3:
            with pytest.raises(GateError, match="BUDGET"):
                gate.dispatch(req, lambda r: attempted.append(r) or True)
        else:
            gate.dispatch(req, lambda r: attempted.append(r) or True)
        gate.stop(run); gate.close()
        gate = SessionGate(tmp_path / "authority", seal, enabled=True)
    assert len(attempted) == min(count, 3)
    assert len([r for r in gate.stream.rows if r["kind"] == "reservation"]) == min(count, 3)
    gate.close()


@pytest.mark.parametrize("scenario,cap", [("L04", 2), ("L07", 2), ("L10", 1)] +
    [(f"L{i:02}", 0) for i in (1, 2, 3, 5, 6, 8, 9, 11, 12)])
def test_scenario_caps_include_failed_calls(tmp_path, scenario, cap):
    gate, policy, _ = gate_at(tmp_path); begin(gate, policy, scenario=scenario)
    calls = []
    for _ in range(cap): gate.dispatch(request_for(policy, scenario=scenario), lambda r: calls.append(r) or False)
    req = request_for(policy, scenario=scenario)
    with pytest.raises(GateError, match="BUDGET|ZERO_WRITE"):
        gate.dispatch(req, lambda r: calls.append(r) or True)
    assert len(calls) == cap
    gate.close()


@pytest.mark.parametrize("outcome,expected", [(True, "SUCCESS"), (False, "FAILED"), (None, "INDETERMINATE"), (1, "INDETERMINATE")])
def test_every_outcome_consumes_before_dispatch(tmp_path, outcome, expected):
    gate, policy, _ = gate_at(tmp_path); begin(gate, policy)
    def fake(reservation):
        rows = [decode(x) for x in gate.path.read_bytes().splitlines()]
        assert any(r["content_digest"] == reservation["content_digest"] for r in rows)
        head = decode((gate.directory / "head.json").read_bytes())
        assert head["sha256"] == file_hash(gate.path)
        return outcome
    _, actual = gate.dispatch(request_for(policy), fake)
    assert actual == expected
    assert len([r for r in gate.stream.rows if r["kind"] == "reservation"]) == 1
    gate.close()


def test_throw_consumes_and_never_automatically_retries(tmp_path):
    gate, policy, _ = gate_at(tmp_path); begin(gate, policy)
    calls = []
    def fake(row):
        calls.append(row); raise RuntimeError("indeterminate")
    with pytest.raises(RuntimeError): gate.dispatch(request_for(policy), fake)
    assert len(calls) == 1 and gate.stream.rows[-1]["data"]["result"] == "INDETERMINATE"
    gate.close()


def test_reserve_crash_is_consumed_and_stale_lock_never_reclaimed(tmp_path):
    gate, policy, seal = gate_at(tmp_path); begin(gate, policy)
    calls = []
    with pytest.raises(GateError, match="CRASH"):
        gate.dispatch(request_for(policy), lambda r: calls.append(r), crash_after_reserve=True)
    assert not calls
    assert [decode(x) for x in gate.path.read_bytes().splitlines()][-1]["kind"] == "reservation"
    gate.close()
    with pytest.raises(GateError, match="CONCURRENT_OR_UNRECONCILED"):
        SessionGate(tmp_path / "authority", seal, enabled=True)


@pytest.mark.parametrize("failure", ["missing", "tail", "truncated", "head", "enrollment", "pending"])
def test_journal_fail_closed_on_reload(tmp_path, failure):
    gate, policy, seal = gate_at(tmp_path); begin(gate, policy)
    gate.dispatch(request_for(policy), lambda _: True); gate.close()
    if failure == "missing": gate.path.unlink()
    if failure == "tail": gate.path.write_bytes(gate.path.read_bytes() + b"{broken")
    if failure == "truncated": gate.path.write_bytes(gate.path.read_bytes().splitlines(keepends=True)[0])
    if failure == "head": (gate.directory / "head.json").write_bytes(b"{}")
    if failure == "enrollment": (gate.directory / "enrollment.json").write_bytes(b"{}")
    if failure == "pending": (gate.directory / "head.json.pending").write_bytes(b"partial")
    with pytest.raises((EvidenceError, OSError, KeyError)):
        SessionGate(tmp_path / "authority", seal, enabled=True)


@pytest.mark.parametrize("stage", ["journal", "head"])
def test_persistence_failure_never_dispatches(tmp_path, monkeypatch, stage):
    gate, policy, _ = gate_at(tmp_path); begin(gate, policy)
    calls = []
    def fail(*args): raise OSError("injected durability failure")
    monkeypatch.setattr(budget_module.os if stage == "journal" else budget_module,
                        "fsync" if stage == "journal" else "replace_head", fail)
    with pytest.raises(OSError): gate.dispatch(request_for(policy), lambda r: calls.append(r))
    assert not calls and gate.poisoned
    gate.close()


def test_exclusive_ownership_and_concurrent_same_object(tmp_path):
    gate, policy, seal = gate_at(tmp_path); begin(gate, policy)
    with pytest.raises(GateError): SessionGate(tmp_path / "authority", seal, enabled=True)
    entered, release = threading.Event(), threading.Event()
    errors = []
    def fake(_): entered.set(); assert release.wait(5); return True
    def worker():
        try: gate.dispatch(request_for(policy), fake)
        except Exception as exc: errors.append(exc)
    thread = threading.Thread(target=worker); thread.start()
    assert entered.wait(5)
    try:
        with pytest.raises(GateError, match="CONCURRENT"):
            gate.dispatch(request_for(policy), lambda _: True)
        with pytest.raises(GateError, match="IN_PROGRESS"): gate.close()
    finally:
        release.set(); thread.join(5)
    assert not errors
    gate.close()


def test_reentrancy_fails_without_double_reservation(tmp_path):
    gate, policy, _ = gate_at(tmp_path); begin(gate, policy)
    def fake(_):
        with pytest.raises(GateError, match="REENTRANT"):
            gate.dispatch(request_for(policy), lambda _: True)
        return True
    gate.dispatch(request_for(policy), fake)
    assert len([r for r in gate.stream.rows if r["kind"] == "reservation"]) == 1
    gate.close()


def test_expiry_during_reservation_consumes_but_cannot_dispatch(tmp_path):
    policy = policy_for([target_policy()]); policy["window_end"] = "2026-11-20T00:00:01+00:00"
    gate, policy, _ = gate_at(tmp_path, policy); begin(gate, policy)
    gate.stream.clock.wall = budget_module.utc(policy["window_end"]) - timedelta(milliseconds=2)
    calls = []
    with pytest.raises(GateError, match="AFTER_RESERVATION"):
        gate.dispatch(request_for(policy), lambda r: calls.append(r))
    assert not calls and len([r for r in gate.stream.rows if r["kind"] == "reservation"]) == 1
    evidence = verify_streams({"budget": gate.stream.rows}, policy, requested=["L04"])
    assert evidence["infrastructure"] == "FAIL" and "EXPIRY" in evidence["errors"][0]
    gate.close()


def test_offline_crash_reconstruction_preserves_consumption(tmp_path):
    gate, policy, _ = gate_at(tmp_path); begin(gate, policy)
    with pytest.raises(GateError):
        gate.dispatch(request_for(policy), lambda _: True, crash_after_reserve=True)
    evidence = verify_streams({"budget": gate.stream.rows}, policy, requested=["L04"])
    assert evidence["infrastructure"] == "BLOCKED" and evidence["consumed_attempts"] == 1
    gate.close()


def test_session_reseed_and_run_rollover_cannot_refund(tmp_path):
    gate, policy, _ = gate_at(tmp_path); begin(gate, policy)
    gate.dispatch(request_for(policy), lambda _: True); gate.stop("run-1")
    with pytest.raises(GateError): begin(gate, policy)
    changed = deepcopy(policy); changed["session_id"] = "SYNTHETIC-other"
    with pytest.raises(FileExistsError):
        provision_synthetic(gate.directory, tmp_path / "other.jsonl", changed)
    gate.close()


@pytest.mark.parametrize("edit", ["creation", "pid", "ce_switch", "allocation", "outside", "misaligned", "retired",
    "incomplete", "ambiguous", "overflow", "lower_cap", "structure", "bits", "evidence", "stopped", "expired", "backwards", "scenario"])
def test_predispatch_rejections(tmp_path, edit):
    gate, policy, _ = gate_at(tmp_path); begin(gate, policy)
    req = request_for(policy); calls = []
    if edit == "creation": req["identity"]["creation"] = "0000000000000000"
    if edit == "pid": req["identity"]["pid"] += 1
    if edit == "ce_switch": req["ce_identity"]["creation"] = "000000010000005C"
    if edit == "allocation": req["allocation_id"] = "wrong"
    if edit == "outside": req["address"] = 0x110000
    if edit == "misaligned": req["address"] += 1
    if edit == "retired": gate.retire("run-1", req["address"])
    if edit == "incomplete": req["candidate"]["complete"] = False
    if edit == "ambiguous": req["candidate"]["qualified_count"] = 2
    if edit == "overflow": req["candidate"]["raw_count"] = 129
    if edit == "lower_cap": req["candidate"]["hard_limit"] = 1
    if edit == "structure": req["candidate"]["structure_valid"] = False
    if edit == "bits": req["bits"] = "0x7FC00000"
    if edit == "evidence": req["anchor_id"] = ""
    if edit == "stopped": gate.stop("run-1")
    if edit == "expired": gate.stream.clock.wall += timedelta(hours=1)
    if edit == "backwards": gate.stream.clock.wall -= timedelta(seconds=1)
    if edit == "scenario": req["scenario"] = "L10"
    with pytest.raises(EvidenceError): gate.dispatch(req, lambda r: calls.append(r))
    assert not calls and not any(r["kind"] == "reservation" for r in gate.stream.rows)
    gate.close()


def test_all_equipment_default_disarmed_and_no_live_policy(tmp_path):
    gate, policy, _ = gate_at(tmp_path, enabled=False)
    with pytest.raises(GateError, match="DISABLED"): begin(gate, policy)
    gate.close()
    policy["origin"] = "LIVE"
    with pytest.raises(GateError, match="LIVE"):
        provision_synthetic(tmp_path / "live", tmp_path / "live.jsonl", policy)
    stream = Stream("SYNTHETIC-default", "target-A")
    t = target_policy()
    target = TargetRecorder(stream, Instance(**t["identity"]), SyntheticMemory(t["base"]), "alloc")
    with pytest.raises(EvidenceError, match="DISABLED"): target.apply(layout.plan("baseline_unique"))
    assert not stream.rows
    assert CERecorder(Stream("SYNTHETIC-default", "ce")).capture(object(), run_id="r", scenario="L01")["enabled"] is False


@pytest.mark.parametrize("mode,count", [("baseline_unique", 1), ("zero_match", 0), ("ambiguous", 2),
    ("over_limit", 129), ("incomplete_structure", 1), ("invalid_structure", 1)])
def test_owned_bytearray_layout_and_target_self_recording(mode, count):
    stream = Stream("SYNTHETIC-target", "target-A"); t = target_policy()
    target = TargetRecorder(stream, Instance(**t["identity"]), SyntheticMemory(t["base"]), "alloc", enabled=True)
    target.apply(layout.plan(mode)); assert len(target.memory.matches()) == count
    row = target.sample(target.active[0], "checkpoint")
    assert row["data"]["read_kind"] == "TARGET_SELF_SAMPLE"
    transport = MockTransport(target)
    packet = {"schema": 1, "session_id": stream.session_id, "sequence": 1, "command": "checkpoint", "anchor_id": "transport", "address": target.active[0]}
    assert transport.request(packet)["origin"] == "SYNTHETIC"
    with pytest.raises(EvidenceError): transport.request(packet)
    with pytest.raises(EvidenceError): target.sample(0x110000, "outside")
    target.shutdown(exception=True)
    assert stream.rows[-1]["data"]["released"] is True
    validate_chain(stream.rows)


@pytest.mark.parametrize("backend", ["lua53", "lua54"])
def test_passive_diagnostic_capture_has_zero_native_mock_side_effects(backend):
    lua, w = world(backend); w.object(0x100128); w.start(); w.until_state("MONITORING")
    baseline = (w.reads, len(w.writes), len(w.scans), len(w.native_calls))
    recorder = CERecorder(Stream("SYNTHETIC-passive", "ce"), enabled=True)
    recorder.capture(plain(w.loop.evidence()), run_id="r", scenario="L04", model_lua=lua.eval("_VERSION"))
    recorder.capture(plain(w.loop.evidence()), run_id="r", scenario="L04")
    assert baseline == (w.reads, len(w.writes), len(w.scans), len(w.native_calls))
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("backend", ["lua53", "lua54"])
@pytest.mark.parametrize("route", ["initial_failure", "restart_denied", "reentrant", "late_after_stop"])
def test_guard_covers_each_mock_dispatch_route(tmp_path, backend, route):
    session = ScenarioSession(tmp_path, backend)
    lua, w, state = session.model(6, "route-one", "L10")
    if route == "initial_failure":
        w.fail.write_return = False
        for _ in range(100): w.step()
        assert w.loop.status().state == "ERROR" and len(w.writes) == 1
        assert session.gate.stream.rows[-1]["data"]["result"] == "FAILED"
    elif route == "reentrant":
        lua.execute("w.hook=function(e) if e=='write' then w.loop.tick() end end")
        w.step(100)
        assert w.loop.status().state == "ERROR" and len(w.writes) == 1
    else:
        w.until_state("MONITORING"); w.loop.stop()
        if route == "restart_denied":
            session.gate.stop(state["run"]); state["run"] = "route-two"
            session.gate.start(state["run"], "L10", state["target"].identity, state["target"].allocation_id)
            w.locate(0x100128).memory[0x100128] = 0x42C80000
            state["target"].memory.write_word(0x100128, 0x42C80000)
            w.start(); w.step(100)
            assert w.loop.status().state == "ERROR" and len(w.writes) == 1
        else:
            w.step(100); w.loop.tick()
            assert len(w.writes) == 1
    assert len([r for r in session.gate.stream.rows if r["kind"] == "reservation"]) == 1
    w.loop.stop(); w.clean(); session.gate.close()


def test_frozen_adapter_capture_explains_unproved_live_installation():
    lua, w = world(); w.object(0x100128); w.start()
    # A replacement after .new() cannot intercept the function already captured.
    lua.execute("w.ce.writeFloat=function() error('LATE_WRAPPER') end")
    w.until_state("MONITORING")
    assert len(w.writes) == 1
    assert SOURCES["ce_mvp_adapter.lua"].count("f.writeFloat(addr, value)") == 1
    assert SOURCES["ce_mvp_core.lua"].count("a.write_float(selected.address, c.write_value)") == 1
    assert ".new(validated,_G,module)" in SOURCES["ce_mvp.lua"]
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("backend", ["lua53", "lua54"])
def test_positive_routes_and_twenty_cycles_verified_independently(tmp_path, backend):
    session = ScenarioSession(tmp_path, backend); session.positive()
    result = verify_streams(session.streams(), session.policy, requested=[f"L{i:02}" for i in range(2, 8)])
    assert result["infrastructure"] == "PASS", result
    assert result["consumed_attempts"] == 2 and set(result["live"].values()) == {"NOT_RUN"}
    session.gate.close()


def test_nineteen_cycles_inconclusive_never_pass(tmp_path):
    session = ScenarioSession(tmp_path); session.positive(cycles=19)
    result = verify_streams(session.streams(), session.policy, requested=["L05"])
    assert result["infrastructure"] == "BLOCKED", result
    assert result["synthetic"]["L05"] == "INCONCLUSIVE_NOT_OBSERVED"
    session.gate.close()


@pytest.mark.parametrize("backend", ["lua53", "lua54"])
def test_all_five_negative_layouts_use_unmodified_real_single_ranker(tmp_path, backend):
    session = ScenarioSession(tmp_path, backend); session.negative()
    result = verify_streams(session.streams(), session.policy, requested=["L09"])
    assert result["infrastructure"] == "PASS", result
    assert result["consumed_attempts"] == 0
    session.gate.close()


def test_complete_twelve_synthetic_scenarios_never_promoted_to_live(tmp_path):
    session = ScenarioSession(tmp_path)
    session.positive(); session.negative(); session.l10(); session.switches(); l12_evidence(session)
    result = verify_streams(session.streams(), session.policy)
    assert result["infrastructure"] == "PASS", result
    assert len(result["synthetic"]) == 12 and set(result["synthetic"].values()) == {"SYNTHETIC_PASS"}
    assert result["consumed_attempts"] == 3 and result["wiring"] == "BLOCKED_WRITE_GUARD_WIRING"
    manifest, seal = export_bundle(tmp_path / "export", session.streams())
    assert verify_bundle(manifest, seal, session.policy) == result
    session.gate.close()


@pytest.fixture
def positive_bundle(tmp_path):
    session = ScenarioSession(tmp_path); session.positive()
    yield session
    session.gate.close()


@pytest.mark.parametrize("mutation", ["target_bits", "invalid_bits", "creation", "duplicate", "missing",
    "reorder", "tampered", "clock_reverse", "live_origin", "live_lua", "bypass", "stop", "expiry", "state", "monitor_gap"])
def test_independent_verifier_rejects_adversarial_records(positive_bundle, mutation):
    session = positive_bundle; streams = session.streams()
    if mutation in {"target_bits", "invalid_bits", "creation"}:
        row = next(r for r in streams["target-A"] if r["kind"] == "checkpoint" and r["data"].get("attempt_id"))
        if mutation == "creation": row["data"]["identity"]["creation"] = "000000010000FFFF"
        else: row["data"]["bits"] = "0x42C80000" if mutation == "target_bits" else "bad"
        rechain(streams["target-A"])
    if mutation == "duplicate": streams["ce"].insert(2, deepcopy(streams["ce"][2]))
    if mutation == "missing": streams["ce"].pop(2)
    if mutation == "reorder": streams["ce"][2], streams["ce"][3] = streams["ce"][3], streams["ce"][2]
    if mutation == "tampered": streams["ce"][0]["data"]["secret"] = "changed"
    if mutation == "clock_reverse":
        streams["ce"][-1]["clock"]["monotonic_ns"] = 0; rechain(streams["ce"])
    if mutation == "live_origin": streams["ce"][0]["origin"] = "CE_DIAGNOSTIC_FUTURE"; rechain(streams["ce"])
    if mutation == "live_lua":
        next(r for r in streams["ce"] if r["kind"] == "ce_snapshot")["data"]["ce_embedded_lua"] = "Lua 5.3"
        rechain(streams["ce"])
    if mutation == "bypass":
        next(r for r in streams["ce"] if r["kind"] == "ce_dispatch")["data"]["attempt_id"] = "unreserved"
        rechain(streams["ce"])
    if mutation == "stop":
        row = streams["budget"].pop(); streams["budget"].insert(2, row); rechain(streams["budget"])
    if mutation == "expiry":
        next(r for r in streams["budget"] if r["kind"] == "reservation")["clock"]["utc"] = "2026-11-20T02:00:00+00:00"
        rechain(streams["budget"])
    if mutation in {"state", "monitor_gap"}:
        row = next(r for r in streams["ce"] if r["kind"] == "ce_event" and r["data"]["diagnostic"]["event_type"] ==
                   ("state_transition" if mutation == "state" else "monitor_result"))
        if mutation == "state": row["data"]["diagnostic"]["state_after"] = "MONITORING"
        else: row["data"]["diagnostic"]["counters"]["monitor_checks"] += 50
        rechain(streams["ce"])
    result = verify_streams(streams, session.policy, requested=["L04", "L05", "L07"])
    assert result["infrastructure"] == "FAIL", (mutation, result)
    assert set(result["live"].values()) == {"NOT_RUN"}


def test_missing_two_sided_evidence_is_inconclusive(positive_bundle):
    session = positive_bundle; streams = session.streams()
    streams["ce"] = [r for r in streams["ce"] if r["kind"] != "ce_checkpoint"]
    rechain(streams["ce"])
    result = verify_streams(streams, session.policy, requested=["L04"])
    assert result["infrastructure"] == "BLOCKED" and result["missing"]


def test_independent_file_hash_and_duplicate_json_keys(positive_bundle, tmp_path):
    session = positive_bundle
    manifest, seal = export_bundle(tmp_path / "export", session.streams())
    path = manifest.parent / "ce.jsonl"; path.write_bytes(path.read_bytes() + b"\n")
    assert verify_bundle(manifest, seal, session.policy)["infrastructure"] == "FAIL"
    with pytest.raises(EvidenceError): decode('{"a":1,"a":2}')


@pytest.mark.parametrize("case", ["MISSING", "DISABLED", "INVALID"])
def test_each_l12_wrong_diagnostic_is_rejected(positive_bundle, case):
    session = positive_bundle; l12_evidence(session); streams = session.streams()
    row = next(r for r in streams["ce"] if r["scenario"] == "L12-" + case)
    row["data"]["diagnostic"] = "MISSING_CONFIG"; rechain(streams["ce"])
    result = verify_streams(streams, session.policy, requested=["L12"])
    assert result["infrastructure"] == "FAIL", result


def test_recorders_reject_gaps_changed_history_and_live_origins():
    lua, w = world(); w.object(0x100128); w.start(); w.until_state("MONITORING")
    snapshot = plain(w.loop.evidence())
    for change in ("dropped", "changed", "gap", "live", "secret"):
        recorder = CERecorder(Stream("SYNTHETIC-recorder", "ce"), enabled=True)
        recorder.capture(snapshot, run_id="r", scenario="L04")
        bad = deepcopy(snapshot)
        if change == "dropped": bad["dropped_events"] = 1
        if change == "changed": bad["events"][0]["state_after"] = "READBACK"
        if change == "gap": bad["events"].pop(0)
        if change == "live": bad["source"] = "CE"
        if change == "secret": bad["events"][0]["config_contents"] = "FORBIDDEN"
        with pytest.raises(EvidenceError): recorder.capture(bad, run_id="r", scenario="L04")
    w.loop.stop(); w.clean()


def test_identity_counter_and_anchor_corruption_cannot_pass(positive_bundle):
    session = positive_bundle
    for change in ("identity_incomplete", "counter", "checkpoint", "extra_read_after_cleanup", "actor", "clock_origin"):
        streams = session.streams()
        ce = streams["ce"]
        if change == "identity_incomplete":
            row = next(r for r in ce if r["kind"] == "ce_event" and r["data"]["diagnostic"]["event_type"] == "write_intent")
            row["data"]["diagnostic"]["identity"]["check_complete"] = False
        if change == "counter":
            for row in ce:
                if row["kind"] == "ce_event": row["data"]["diagnostic"]["counters"]["adapter_write_attempts"] += 1
        if change == "checkpoint":
            row = next(r for r in streams["budget"] if r["kind"] == "reservation")
            row["data"]["checkpoint"]["content_digest"] = "a" * 64
            rechain(streams["budget"])
        if change == "extra_read_after_cleanup":
            row = [r for r in ce if r["kind"] == "ce_event"][-1]
            row["data"]["diagnostic"]["counters"]["adapter_read_calls"] += 1
        if change == "actor": ce[0]["actor"] = "target-A"
        if change == "clock_origin": ce[-1]["clock"]["origin"] = "other-clock"
        rechain(ce)
        result = verify_streams(streams, session.policy, requested=["L04"])
        assert result["infrastructure"] == "FAIL", (change, result)


def test_target_b_never_inherits_a_write_scope(tmp_path):
    policy = policy_for([target_policy(8, "B")])
    gate, _, _ = gate_at(tmp_path, policy)
    with pytest.raises(GateError, match="SCENARIO"):
        begin(gate, policy, scenario="L04")
    begin(gate, policy, scenario="L11")
    with pytest.raises(GateError, match="ZERO_WRITE"):
        gate.dispatch(request_for(policy, scenario="L11"), lambda _: True)
    gate.close()


def test_retirement_survives_stop_and_reload(tmp_path):
    gate, policy, seal = gate_at(tmp_path); begin(gate, policy)
    gate.retire("run-1", 0x100128); gate.stop("run-1"); gate.close()
    gate = SessionGate(tmp_path / "authority", seal, enabled=True)
    begin(gate, policy, "run-2")
    with pytest.raises(GateError, match="RETIRED"):
        gate.dispatch(request_for(policy, run_id="run-2"), lambda _: True)
    gate.close()


def test_offline_cli_requires_external_policy_and_manifest_hashes(positive_bundle, tmp_path, capsys):
    from ce_qualification.verifier import main
    session = positive_bundle
    manifest, seal = export_bundle(tmp_path / "cli", session.streams())
    policy = tmp_path / "policy.json"; policy.write_bytes(canonical(session.policy))
    arguments = ["--manifest", str(manifest), "--manifest-sha256", seal,
                 "--policy", str(policy), "--policy-sha256", file_hash(policy), "--case", "L04"]
    assert main(arguments) == 0 and '"NOT_RUN"' in capsys.readouterr().out
    arguments[-3] = "0" * 64
    assert main(arguments) == 1 and "POLICY_FILE_DIGEST_MISMATCH" in capsys.readouterr().out


def test_checkpoint_replay_does_not_consume_second_reservation(tmp_path):
    gate, policy, _ = gate_at(tmp_path); begin(gate, policy)
    req = request_for(policy); gate.dispatch(req, lambda _: False)
    with pytest.raises(GateError, match="CHECKPOINT_REPLAY"):
        gate.dispatch(req, lambda _: True)
    assert len([r for r in gate.stream.rows if r["kind"] == "reservation"]) == 1
    gate.close()


def test_phase_window_and_successful_start_limits(tmp_path):
    gate, policy, _ = gate_at(tmp_path); begin(gate, policy)
    gate.stream.clock.wall += timedelta(minutes=5)
    with pytest.raises(GateError, match="PHASE_WINDOW"):
        gate.dispatch(request_for(policy), lambda _: True)
    gate.stop("run-1")
    for n in range(2, 10):
        begin(gate, policy, f"run-{n}"); gate.stop(f"run-{n}")
    with pytest.raises(GateError, match="START_BUDGET"): begin(gate, policy, "run-10")
    gate.close()


def test_boolean_schema_and_sequence_are_not_integers():
    stream = Stream("SYNTHETIC-schema", "ce"); stream.emit("load_observation", {})
    for key in ("schema", "sequence"):
        rows = deepcopy(stream.rows); rows[0][key] = True
        rows[0]["content_digest"] = digest({k: v for k, v in rows[0].items() if k != "content_digest"})
        with pytest.raises(EvidenceError): validate_chain(rows)
