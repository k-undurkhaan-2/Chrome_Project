"""Real candidate Lua + unchanged ranker/core; synthetic CE and bytearray only."""
from copy import deepcopy
from pathlib import Path

from ce_qualification.evidence import Stream, digest, canonical
from ce_qualification.target import TargetRecorder, Instance, SyntheticMemory
from ce_qualification.qsg_broker import Broker
from ce_qualification.qsg_protocol import MockChannel
from ce_qualification.qsg_recorder import Recorder
from support import ROOT, SOURCES, layout, plain, world, target_policy


def policy():
    old = target_policy()
    return {"origin": "SYNTHETIC", "authorization_id": "SYNTHETIC-R2-AUTH", "session_id": "SYNTHETIC-R2",
        "approval_sha256": "a"*64, "candidate_sha256": digest(SOURCES),
        "peer": {"pid": 501, "creation": "0000000100000001", "image_sha256": "b"*64,
                 "component_sha256": "c"*64, "channel": "synthetic-owned-channel"},
        "start_ms": "0", "end_ms": "3600000", "targets": [{"identity": old["identity"],
        "provenance": {k: digest(k) for k in ("image_sha256", "script_sha256", "layout_sha256", "provider_sha256")},
        "allocation_id": "owned-allocation", "generation": 1, "base": "1048576", "size": "65536",
        "owned": True, "fresh": True, "phases": [f"L{i:02}" for i in range(1, 13)] +
        ["L09-zero", "L09-ambiguous", "L09-129_plus", "L09-incomplete", "L09-invalid"]}]}


def table(lua, obj):
    if isinstance(obj, dict): return lua.table_from({k: table(lua, v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple, set)): return lua.table_from([table(lua, v) for v in obj])
    return obj


class Model:
    def __init__(self, directory, backend="lua53", *, phase="L04", mode="baseline_unique", policy_value=None):
        self.directory = Path(directory)
        self.policy = policy_value or policy()
        self.lua, self.w = world(backend)
        self.w.cfg.diagnostics.event_limit = 512
        self.w.cfg.monitor_interval_ms = 1000
        self.w.cfg.invalid_confirmations = 2
        self.w.cfg.rescan_backoff_ms = 1000
        self.w.cfg.max_backoff_ms = 30000
        self.w.cfg.min_rescan_spacing_ms = 2000
        self.w.cfg.max_rescan_attempts = 5
        self.w.cfg.scan_timeout_ms = 120000
        self.time_offset = 0
        self.now_value = 0
        self.clock = lambda: self.now_value
        self.seal = Broker.provision(self.directory / "authority", self.policy)
        self.broker = Broker(self.directory / "authority", self.seal, clock_ms=self.clock, peer=self.policy["peer"], enabled=True)
        self.channel = MockChannel(self.broker, self.policy["peer"])
        self.recorder = Recorder(self.policy["session_id"], self.clock, enabled=True)
        self.target_stream = Stream(self.policy["session_id"], "target-A")
        scope = self.policy["targets"][0]
        self.target = TargetRecorder(self.target_stream, Instance(**scope["identity"]), SyntheticMemory(int(scope["base"])), scope["allocation_id"], enabled=True)
        self.target.apply(layout.plan(mode))
        self.w.use_layout(table(self.lua, layout.plan(mode)["pages"]), table(self.lua, layout.plan(mode)["words"]))
        self.phase, self.starts, self.operation, self.checkpoints = phase, 0, 0, 0
        self.lease = None
        self.scope_override = None
        self.raw_calls = []
        self.errors = []
        self.run = None
        self.api = None
        wrap = self.lua.eval("function(f) return function(...) return f(...) end end")
        self.wrap = wrap
        raw = self.w.ce.writeFloat
        def spy(address, value):
            self.raw_calls.append({"address": int(address), "value": value, "reserves": len(self.broker.events('reserve')),
                "claims": len(self.broker.events('claim'))})
            result = raw(address, value)
            if result is True:
                self.target.memory.write_word(int(address), int(self.w.locate(address).memory[address]))
            return result
        self.w.ce.writeFloat = wrap(spy)
        def call(kind, data, deadline):
            try:
                result = self.channel.request(kind, plain(data), int(deadline))
            except Exception as exc:
                self.errors.append((kind, repr(exc)))
                raise
            if kind == "begin":
                self.lease = result["lease"]
                self.target.context(self.lease["run_id"], result["phase"])
            if kind == "phase":
                self.phase = result["phase"]
                self.target.context(self.lease["run_id"], self.phase)
            return table(self.lua, result)
        def start_request():
            self.starts += 1
            return table(self.lua, {"run_id": f"run-{self.starts}", "writer_id": f"writer-{self.starts}",
                "epoch": f"epoch-{self.starts}", "target": 0, "phase": self.phase})
        def operation():
            self.operation = max(self.operation+1, len(self.broker.store.rows)+1)
            return self.operation
        def sample_clock(value):
            self.now_value = self.time_offset + int(value)
            return self.now_value
        lua_clock = self.lua.eval('function(w,f) return function() return f(w.time) end end')(self.w, sample_clock)
        def checkpoint(address, lease, current_phase, nonce):
            self.checkpoints += 1
            return canonical(self.target.sample(int(address), nonce)).decode()
        def post(address, attempt, lease, current_phase):
            row = self.target.sample(int(address), f"post-{attempt}", attempt_id=attempt)
            return table(self.lua, {"bits": row["data"]["bits"], "record": canonical(row).decode()})
        def retirement(address):
            return canonical(next(r for r in reversed(self.target_stream.rows)
                if r["kind"] == "retire" and r["data"]["address"] == address)).decode()
        self.host = table(self.lua, {"enabled": True, "origin": "SYNTHETIC", "session_id": self.policy["session_id"],
            "authorization_id": self.policy["authorization_id"], "transport": {"version": "qsg.mock.v1", "bounded": True,
            "authenticated": True, "timeout_unit": "ms", "request": wrap(call)},
            "now_ms": lua_clock, "hash": wrap(lambda obj: digest(plain(obj))), "next_operation": wrap(operation),
            "start_request": wrap(start_request), "current_scope": wrap(lambda: table(self.lua, self.current_scope())),
            "checkpoint": wrap(checkpoint), "post_checkpoint": wrap(post), "retirement": wrap(retirement),
            "recorder": {"append": wrap(lambda kind, obj: self.recorder.append(kind, plain(obj))),
                "capture": wrap(lambda s, r, p, a: self.recorder.capture(plain(s), r, p, plain(a)))}})
        self.module = self.lua.execute((ROOT / "src/qualification/qsg.lua").read_text())
        self.factory = self.module.new(self.host)

    def current_scope(self):
        if self.scope_override is not None: return deepcopy(self.scope_override)
        return {"scope": deepcopy(self.policy["targets"][0]), "alive": bool(self.w.alive), "alive_instances": 1,
            "ce_token": f"{int(self.w.opened or self.w.pid)}:{0x100000000+int(self.w.creation):016X}",
            "retired": {str(a): True for a in self.target.retired},
            "pages": {str(p): True for p in self.target.memory.pages}}

    def start(self, *, loader=False):
        if loader:
            code = (ROOT / "tests/fixtures/qualification/g1_mock_loader.lua").read_text()
            code = code.replace("function(cfg,ce,loader) return new(cfg,ce,loader,'synthetic') end",
                "function(cfg,ce,loader,source,execution) return new(cfg,ce,loader,'synthetic',execution) end")
            self.api, self.env = self.lua.execute(code)(self.w, table(self.lua, SOURCES), str(self.directory / "missing/ce_mvp_config.local.lua"))
            assert self.api.configure_execution(table(self.lua, {"mode": "QUALIFICATION", "factory": self.factory})) is True
            return self.api.start()
        self.run = self.factory.prepare_start(self.w.core.validate(self.w.cfg))
        self.w.adapter = self.w.adapter_module.new(self.w.core.validate(self.w.cfg), self.w.ce, self.w.load, "synthetic", self.run)
        self.w.loop = self.w.core.new(self.w.cfg, self.w.adapter)
        self.run.bind_core(self.w.loop)
        self.api = self.w.loop
        return self.api.start()

    def until(self, state):
        for _ in range(2000):
            s = self.api.status()
            if s.state == state: return
            if not s.running:
                raise AssertionError(f"terminal {s.state}: {s.stop_reason}; {self.errors}")
            self.w.step()
        raise AssertionError("model timeout")

    def phase_to(self, phase):
        self.factory.enter_phase(phase)

    def monitors(self, count):
        for _ in range(count):
            self.w.time += 950
            self.w.step()

    def relocate(self):
        plan = layout.plan("relocate", 1)
        self.target.apply(plan)
        self.w.use_layout(table(self.lua, plan["pages"]), table(self.lua, plan["words"]))

    def positive(self, cycles=20):
        assert self.start() is True
        self.until("MONITORING")
        self.phase_to("L05"); self.monitors(cycles)
        self.phase_to("L06")
        self.target.apply(layout.transition("drift", "baseline_unique", 0))
        self.w.locate(0x100128).memory[0x100128] = 0x42280000
        self.monitors(3)
        self.phase_to("L07"); self.relocate()
        self.until("RESCAN_BACKOFF"); self.until("MONITORING")
        self.phase_to("L08")

    def stop(self):
        if self.run: self.run.revoke("OPERATOR_STOP")
        self.api.stop()
        if self.run: self.run.finish()
        self.w.clean()

    def close(self):
        if self.api: self.stop()
        self.broker.close()

    def bundle(self):
        return {"policy": deepcopy(self.policy), "broker": deepcopy(self.broker.store.rows),
                "qsg": deepcopy(self.recorder.rows), "ce": deepcopy(self.recorder.core_stream.rows),
                "target": deepcopy(self.target_stream.rows), "raw_spy": deepcopy(self.raw_calls)}
