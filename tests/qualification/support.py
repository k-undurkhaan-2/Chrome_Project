"""Synthetic scenarios: frozen Lua, table-backed CE, bytearray target only."""
from copy import deepcopy
from importlib import import_module, util
from pathlib import Path
import hashlib
import uuid
import xml.etree.ElementTree as ET

from ce_qualification.budget import SessionGate, provision_synthetic
from ce_qualification.evidence import Stream, SyntheticClock
from ce_qualification.recorder import CERecorder
from ce_qualification.target import Instance, SyntheticMemory, TargetRecorder

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "src").glob("*.lua")
           if p.name.startswith("ce_mvp") or p.name in ("mvp0_candidate_report.lua", "mvp0_foundlist_collector.lua")}
spec = util.spec_from_file_location("qualification_pure_layout", ROOT / "tests/fixtures/ce_mvp_target_layout.py")
layout = util.module_from_spec(spec)
spec.loader.exec_module(layout)  # Pure offsets only; never import native target.
TARGET_HASH = hashlib.sha256((ROOT / "src/ce_qualification/target.py").read_bytes()).hexdigest()


def plain(value):
    if hasattr(value, "items") and type(value) is not dict:
        pairs = dict(value.items())
        if pairs and all(type(k) is int for k in pairs) and set(pairs) == set(range(1, len(pairs) + 1)):
            return [plain(pairs[k]) for k in sorted(pairs)]
        return {k: plain(v) for k, v in pairs.items()}
    return value


def world(backend="lua53"):
    lua = import_module("lupa." + backend).LuaRuntime(unpack_returned_tuples=True)
    factory = lua.execute((ROOT / "tests/fixtures/ce_mvp_mock.lua").read_text())
    w = factory.new(lua.table_from(SOURCES))
    lua.globals().w = w
    w.cfg.diagnostics = lua.table_from({"enabled": True, "session_token": "SYNTHETIC-run", "event_limit": 2048})
    return lua, w


def policy_for(targets, session="SYNTHETIC-G1"):
    return {"origin": "SYNTHETIC", "session_id": session,
        "window_start": "2026-11-20T00:00:00+00:00", "window_end": "2026-11-20T01:00:00+00:00", "targets": targets}


def target_policy(index=0, designation="A"):
    return {"identity": Instance(designation, 101 + index, f"{0x10000005B + index:016X}", TARGET_HASH).record(),
            "allocation_id": f"alloc-{index}", "base": 0x100000, "size": 65536,
            "allowed_scenarios": ["L11"] if designation == "B" else [f"L{i:02}" for i in range(1, 13)]}


def request_for(policy, *, scenario="L04", run_id="run-1", index=0, address=0x100128):
    t = policy["targets"][index]
    request = {"run_id": run_id, "scenario": scenario, "identity": deepcopy(t["identity"]),
        "ce_identity": deepcopy(t["identity"]), "allocation_id": t["allocation_id"],
        "address": address, "bits": "0x42FA0000", "anchor_id": "prewrite-" + uuid.uuid4().hex,
        "candidate": {"raw_count": 1, "qualified_count": 1, "complete": True,
                      "hard_limit": 128, "structure_valid": True}}
    request["checkpoint"] = Stream(policy["session_id"], "target-" + t["identity"]["designation"]).emit("checkpoint",
        {k: request[k] for k in ("identity", "allocation_id", "address", "anchor_id")} |
        {"bits": "0x42C80000", "read_kind": "TARGET_SELF_SAMPLE"}, run_id=run_id, scenario=scenario)
    return request


def gate_at(tmp_path, policy=None, enabled=True):
    policy = policy or policy_for([target_policy()])
    directory = tmp_path / "authority"
    seal = provision_synthetic(directory, tmp_path / "private" / "budget.jsonl", policy)
    return SessionGate(directory, seal, enabled=enabled), policy, seal


class ScenarioSession:
    def __init__(self, tmp_path, backend="lua53"):
        self.tmp_path, self.backend = Path(tmp_path), backend
        self.policy = policy_for([target_policy(i, "B" if i == 8 else "A") for i in range(9)])
        for index, target in enumerate(self.policy["targets"]):
            target["allowed_scenarios"] = ([f"L{i:02}" for i in range(2, 9)] if index == 0 else
                ["L09"] if index <= 5 else ["L10"] if index == 6 else ["L11"])
        self.gate, _, self.seal = gate_at(self.tmp_path, self.policy)
        self.ce = Stream(self.policy["session_id"], "ce", SyntheticClock("ce", offset_ns=90_000_000_000))
        self.a = Stream(self.policy["session_id"], "target-A", SyntheticClock("target-A", offset_ns=5_000))
        self.b = Stream(self.policy["session_id"], "target-B", SyntheticClock("target-B", offset_ns=700_000))
        self.recorder = CERecorder(self.ce, enabled=True)
        self.targets = {}

    def target(self, index, run, scenario, mode="baseline_unique"):
        t = self.policy["targets"][index]
        recorder = TargetRecorder(self.b if t["identity"]["designation"] == "B" else self.a,
            Instance(**t["identity"]), SyntheticMemory(t["base"]), t["allocation_id"], enabled=True)
        recorder.context(run, scenario); recorder.apply(layout.plan(mode))
        self.targets[index] = recorder
        return recorder

    def model(self, index, run, scenario, *, mode="baseline_unique", loader=False):
        target = self.target(index, run, scenario, mode)
        lua, w = world(self.backend)
        w.pid = target.instance.pid; w.creation = int(target.instance.creation, 16) & 0xFFFFFFFF
        w.cfg.target_pid = w.pid; w.cfg.diagnostics.session_token = "SYNTHETIC-" + run
        if loader:
            w.cfg.diagnostics.cleanup_start_probe = True
        self.apply(lua, w, layout.plan(mode))
        state = {"scenario": scenario, "run": run, "target": target, "reservations": []}
        native_mock = w.ce.writeFloat

        def dispatch(address, value):
            req = request_for(self.policy, scenario=state["scenario"], run_id=state["run"], index=index, address=int(address))
            req["anchor_id"] = f"prewrite-{len(state['reservations']) + 1}"
            req["checkpoint"] = target.sample(int(address), req["anchor_id"])
            def fake(reservation):
                d = reservation["data"]
                self.ce.emit("ce_dispatch", {k: d[k] for k in ("attempt_id", "identity", "allocation_id", "address", "bits")} |
                    {"reservation_digest": reservation["content_digest"]}, run_id=state["run"], scenario=state["scenario"])
                outcome = native_mock(address, value)
                if outcome is True:
                    target.memory.write_word(int(address), 0x42FA0000)
                return outcome
            reservation, outcome = self.gate.dispatch(req, fake)
            state["reservations"].append(reservation)
            return outcome == "SUCCESS"
        # Inject into the MOCK table before adapter construction, never real CE.
        w.ce.writeFloat = lua.eval("function(f) return function(a,v) return f(a,v) end end")(dispatch)
        api = None
        if loader:
            factory = lua.execute((ROOT / "tests/fixtures/qualification/g1_mock_loader.lua").read_text())
            api, state["env"] = factory(w, lua.table_from(SOURCES), str(self.tmp_path / "absent" / "ce_mvp_config.local.lua"))
        self.gate.start(run, scenario, target.identity, target.allocation_id)
        if api:
            assert api.start() == (True, None)
        else:
            assert w.start() is True
            api = w.loop
        state["api"] = api
        return lua, w, state

    @staticmethod
    def apply(lua, w, plan):
        w.use_layout(lua.table_from(list(plan["pages"])), lua.table_from(plan["words"]))

    def capture(self, lua, state, scenario=None):
        target = state["target"]
        self.recorder.capture(plain(state["api"].evidence()), run_id=state["run"], scenario=scenario or state["scenario"],
            bindings={"identity": target.identity, "allocation_id": target.allocation_id,
                      "addresses": {"A0": 0x100128, "A1": 0x101128}}, model_lua=lua.eval("_VERSION"))

    def readback(self, state):
        reservation = state["reservations"][-1]; d = reservation["data"]
        anchor = "readback-" + d["attempt_id"]
        event = [e for e in plain(state["api"].evidence())["events"] if e["event_type"] == "readback_verified"][-1]
        state["target"].sample(d["address"], anchor, attempt_id=d["attempt_id"])
        self.ce.emit("ce_checkpoint", {k: d[k] for k in ("attempt_id", "identity", "allocation_id", "address", "bits")} |
            {"anchor_id": anchor, "diagnostic_sequence": event["sequence"]}, run_id=state["run"], scenario=state["scenario"])

    def stop(self, lua, w, state, *, shutdown=True):
        state["api"].stop(); self.capture(lua, state); w.clean()
        before = plain(state["api"].evidence())["counters"]
        w.step(6)
        after = plain(state["api"].evidence())["counters"]
        self.ce.emit("phase_boundary", {"phase": "after_stop", "completed_wait_intervals": 3,
            "before": before, "after": after}, run_id=state["run"], scenario=state["scenario"])
        self.gate.stop(state["run"])
        if shutdown:
            state["target"].shutdown()

    def positive(self, cycles=20):
        lua, w, state = self.model(0, "positive", "L04")
        w.until_state("SCREENING"); self.capture(lua, state, "L02")
        self.ce.emit("os_identity", {"identity": state["target"].identity, "method": "SYNTHETIC_OS_WITNESS"}, run_id="positive", scenario="L02")
        w.until_state("CANDIDATE_CHECK"); self.capture(lua, state, "L03")
        w.until_state("MONITORING"); self.capture(lua, state); self.readback(state)
        w.step(cycles * 2); self.capture(lua, state, "L05")
        target = state["target"]; target.context("positive", "L06")
        target.apply(layout.transition("drift", "baseline_unique", 0))
        w.locate(0x100128).memory[0x100128] = 0x42280000
        w.step(6); self.capture(lua, state, "L06"); target.sample(0x100128, "drift-observed")
        target.context("positive", "L07"); target.apply(layout.plan("relocate", 1))
        self.gate.retire("positive", 0x100128)
        self.apply(lua, w, layout.plan("relocate", 1)); state["scenario"] = "L07"
        w.until_state("RESCAN_BACKOFF"); w.until_state("MONITORING")
        self.capture(lua, state); self.readback(state)
        state["scenario"] = "L08"; target.context("positive", "L08")
        w.alive = False; w.step()
        self.stop(lua, w, state)

    def negative(self):
        for index, (mode, alias) in enumerate((("zero_match", "zero"), ("ambiguous", "ambiguous"),
                ("over_limit", "129_plus"), ("incomplete_structure", "incomplete"), ("invalid_structure", "invalid")), 1):
            lua, w, state = self.model(index, "negative-" + alias, "L09", mode=mode)
            state["scenario"] = "L09-" + alias
            t = state["target"]; t.context(state["run"], state["scenario"])
            t.emit("mode", {"mode": alias, "synthetic_match_count": len(t.memory.matches()), "hard_limit": 128})
            for _ in range(1000):
                w.step()
                if not w.loop.status().running or w.loop.status().state == "RESCAN_BACKOFF": break
            self.stop(lua, w, state)

    def l10(self):
        if self.backend != "lua53":
            return  # Frozen public entrypoint intentionally rejects Lua 5.4.
        lua, w, state = self.model(6, "cleanup-one", "L10", loader=True)
        api = state["api"]
        w.step(100)
        assert api.status().state == "MONITORING"
        assert api.start() == (False, "ALREADY_RUNNING")
        self.capture(lua, state); self.readback(state)
        self.stop(lua, w, state, shutdown=False)
        target = state["target"]
        w.cfg.diagnostics.session_token = "SYNTHETIC-cleanup-two"
        w.cfg.diagnostics.cleanup_start_probe = False
        self.apply(lua, w, layout.plan("zero_match"))
        target.context("cleanup-two", "L10")
        target.memory.write_word(0x100128, 0x42280000)
        state["run"] = "cleanup-two"
        self.gate.start(state["run"], "L10", target.identity, target.allocation_id)
        assert api.start() == (True, None)
        w.step(15); self.stop(lua, w, state)

    def switches(self):
        lua, w, state = self.model(7, "switch", "L11", mode="zero_match")
        destination = self.target(8, "switch", "L11")
        w.until_state("RESCAN_BACKOFF")
        before = plain(state["api"].evidence())["counters"]
        before_sequence = state["api"].evidence().last_sequence
        self.capture(lua, state)
        w.opened = destination.instance.pid; w.step()
        after = plain(state["api"].evidence())["counters"]
        self.ce.emit("target_switch", {"from": state["target"].identity, "to": destination.identity,
            "before": before, "after": after, "before_sequence": before_sequence,
            "after_sequence": state["api"].evidence().last_sequence}, run_id="switch", scenario="L11")
        destination.sample(0x100128, "switch-destination")
        self.stop(lua, w, state); destination.shutdown()

    def streams(self):
        streams = {"budget": deepcopy(self.gate.stream.rows), "ce": deepcopy(self.ce.rows), "target-A": deepcopy(self.a.rows)}
        if self.b.rows: streams["target-B"] = deepcopy(self.b.rows)
        return streams


def l12_evidence(session):
    lua, w = world("lua53")
    factory = lua.execute((ROOT / "tests/fixtures/qualification/g1_mock_loader.lua").read_text())
    api, env = factory(w, lua.table_from(SOURCES), str(session.tmp_path / "absent" / "ce_mvp_config.local.lua"))
    guard_module = lua.execute((ROOT / "tests/fixtures/ce_mvp_prestart_guard.lua").read_text())
    # A separate inert import under a fresh guard supplies L01's synthetic record.
    guard = guard_module.new(env, "synthetic"); guard.install()
    env.H3A7_CE_MVP = None
    lua.eval("function(s,e) return assert(load(s,'@SYNTHETIC/ce_mvp.lua','t',e))() end")(SOURCES["ce_mvp.lua"], env)
    env.syntaxcheck = True
    scripts = ET.parse(ROOT / "src/ce_mvp.CT").findall(".//AssemblerScript")
    count = 0
    for script in scripts:
        for chunk in script.text.split("{$lua}")[1:]:
            lua.eval("function(s,e) return assert(load(s,'@SYNTHETIC/ct-syntax','t',e))() end")(chunk.split("{$asm}")[0], env)
            count += 1
    env.syntaxcheck = False
    zero = plain(guard.snapshot())["attempted_calls"]; guard.restore()
    session.ce.emit("load_observation", {"state": env.H3A7_CE_MVP.status().state, "attempted_calls": zero,
        "guard_restored": True, "ct_lua_syntax_blocks": count, "config_loaded": False,
        "synthetic_lua": lua.eval("_VERSION"), "ce_embedded_lua": "NOT_RUN"}, run_id="load-only", scenario="L01")
    for sub in ("MISSING", "DISABLED", "INVALID"):
        guard = guard_module.new(env, "synthetic"); guard.install()
        before = plain(guard.snapshot())["attempted_calls"]
        retained = plain(api.evidence())
        w.config_missing = sub == "MISSING"
        w.cfg.write_enabled = sub != "DISABLED"
        w.cfg.scan.scan_budget = 65537 if sub == "INVALID" else 128
        accepted, diagnostic = api.start()
        after = plain(guard.snapshot())["attempted_calls"]; guard.restore()
        session.recorder.rejection(run_id="rejected-" + sub, scenario="L12-" + sub,
            accepted=accepted, diagnostic=diagnostic, guard_before=before, guard_after=after,
            restored=not guard.snapshot().installed, retained_before=retained, retained_after=plain(api.evidence()))
