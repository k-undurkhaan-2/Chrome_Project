"""B0 trusted in-memory equipment. No CE, Win32, process or production ledger."""
from copy import deepcopy

from ce_qualification.native_ipc_probe import AdapterCoordinator
from ce_qualification.native_probe_admission import CAPS, ZERO, canonical, sha256
from ce_qualification.native_probe_peer import CLIENT_ACCESS, SERVER_ACCESS, response
from ce_qualification.native_probe_watchdog import Limits
from ce_qualification.native_probe_winpipe import EpochRegistry, SyntheticServer
from native_probe_fakes import Clock, LuaTransport, table

SECRET = b"public-synthetic-key-not-a-native-secret"
CHALLENGES = {"client": "1" * 64, "server": "2" * 64}
ENDPOINT = "\\\\.\\pipe\\qsg-r3-" + "a" * 32
NOW = "2026-11-20T12:00:01+00:00"


def approval_fixture():
    freeze = {k: chr(ord('a') + n) * 64 for n, k in enumerate(("manifest", "patch", "source", "probe", "ce_exe", "ce_dll"))}
    expected = {"freeze": freeze, "approver": "approver-model", "operator": "operator-model", "host": "host-model",
                "principal": "S-1-5-21-1-1001", "workspace": "D:\\model-workspace",
                "evidence_dir": "D:\\model-evidence\\unique", "isolation_digest": "9" * 64}
    record = {"schema": "qsg.r3-b.approval-model.v1", "origin": "SYNTHETIC",
        "purpose": "R3-B transport test only, NOT G1 LIVE", "approval_id": "model-approval",
        **{k: deepcopy(v) for k, v in expected.items() if k != "isolation_digest"},
        "window": {"start": "2026-11-20T12:00:00+00:00", "end": "2026-11-20T12:15:00+00:00"},
        "cases": [f"N{i:02}" for i in range(1, 10)], "vectors": {f"N{i:02}": ["model-vector"] for i in range(1, 10)},
        "caps": dict(CAPS), "zero": {k: 0 for k in ZERO},
        "isolation": {"method": "INDEPENDENT_SUPPORTED_STARTUP_PROOF", "proof_sha256": "9" * 64,
                      **{k: "PROVEN_DISABLED" for k in ("reuse", "autorun", "restore", "autoattach")}},
        "cleanup": {"cancel_io": False, "terminate": False, "instance_policy": "EXACT_INDEPENDENTLY_SPAWNED_HANDLE",
                    "helpers": [], "principal_negatives": []},
        "signature": {"key_id": "test-key", "value": "synthetic-signature"}}
    observations = {"origin": "SYNTHETIC", "evidence_fresh": True, "evidence_writable": True,
                    "startup_proof_sha256": "9" * 64, "watchdog_independent": True, "target_absent": True}
    payload = canonical({k: v for k, v in record.items() if k != "signature"})
    pinned_signature = deepcopy(record["signature"])
    def verifier(raw, sig, approver):
        if raw != payload or sig != pinned_signature: return None
        return {"origin": "SYNTHETIC", "verified_payload_sha256": sha256(raw), "approver": approver,
                "status": "MODEL_SIGNATURE_MATCH"}
    return record, expected, observations, verifier


def peer_fixture():
    client = {"pid": 101, "creation": "0000000000000001", "image_sha256": "a" * 64,
              "component_sha256": "b" * 64, "sid": "S-1-5-21-1-1001"}
    server = {"pid": 102, "creation": "0000000000000002", "image_sha256": "c" * 64,
              "component_sha256": "d" * 64, "sid": "S-1-5-21-1-1002"}
    expected = {"session_id": "b0", "channel_id": "channel", "epoch": 1, "connection_id": "connection",
                "client": client, "server": server, "dacl_sha256": "e" * 64,
                "candidate_sha256": "f" * 64, "authorization_sha256": "0" * 64}
    queries = {}
    for peer, observer, api in (("client", server, "GetNamedPipeClientProcessId"), ("server", client, "GetNamedPipeServerProcessId")):
        queries[peer] = {"api": api, "handle_ref": "model-handle-server" if peer == "client" else "model-handle-client",
            "connection_id": "connection", "observer": deepcopy(observer), "peer_pid": expected[peer]["pid"],
            "process_handle_ref": "model-process-" + peer, "creation_api": "GetProcessTimes(held-process-handle)",
            "token_api": "GetTokenInformation(TokenUser,held-process-token)", "image_api": "QueryFullProcessImageName+file-sha256",
            "component_source": "PINNED_LOADED_COMPONENT_MODEL"}
    proof = {"origin": "SYNTHETIC", "os_evidence": "NOT_RUN", "binding": {k: expected[k] for k in
             ("session_id", "channel_id", "epoch", "connection_id")}, "client": deepcopy(client), "server": deepcopy(server),
             "queries": queries, "client_handle": "PROCESS_OWNED_VERIFIED_MODEL", "local_only": True, "inheritable": False,
             "security": {"api": "GetSecurityInfo(SE_KERNEL_OBJECT)", "handle_ref": "model-handle-server", "connection_id": "connection",
                "owner_sid": server["sid"], "dacl_present": True, "null_dacl": False, "protected": True, "descriptor_sha256": "e" * 64,
                "client_requested_access": CLIENT_ACCESS,
                "aces": [{"sid": server["sid"], "mask": SERVER_ACCESS, "type": "ALLOW", "inherited": False},
                         {"sid": client["sid"], "mask": CLIENT_ACCESS, "type": "ALLOW", "inherited": False}]}}
    return expected, proof


class CePipeTransport(LuaTransport):
    def __init__(self, binding, *, backend="lua53", parameter=250, emit=None, endpoint=ENDPOINT):
        super().__init__(binding, backend=backend, emit=emit)
        self.connect_calls, self.destroy_calls = 0, 0
        self.read_override, self.write_override = None, None
        self.read_hook = lambda: None
        wrap = self.lua.eval(b"function(f) return function(...) return f(...) end end")
        def read(n):
            self.read_hook()
            if self.read_override: return self.read_override(n)
            amount = min(int(n), self.read_size, len(self.input))
            raw = bytes(self.input[:amount]); del self.input[:amount]
            return self.lua.table_from(list(raw))
        def write(values, size):
            if self.write_override: return self.write_override(values, size)
            raw = bytes(values[n] for n in range(1, int(size) + 1))
            amount = min(len(raw), self.write_size); self.output.extend(raw[:amount]); return amount
        def destroy():
            self.destroy_calls += 1; self.worker_closed = True; self.pipe[b"Connected"] = False
        self.pipe = table(self.lua, {"Connected": True, "readBytes": wrap(read), "writeBytes": wrap(write), "destroy": wrap(destroy)})
        def connect(name, value):
            self.connect_calls += 1
            assert name == endpoint.rsplit("\\", 1)[-1].encode() and value == parameter
            return self.pipe
        provider = table(self.lua, {"origin": "SYNTHETIC", "connectToPipe": wrap(connect),
            "observe_closed": wrap(lambda _p: self.worker_closed), "now_ms": wrap(self.clock),
            "cancelled": wrap(lambda: self.cancelled), "emit": self.cap[b"emit"]})
        self.worker = self.module[b"new_ce_pipe_model"](provider, table(self.lua, binding), table(self.lua,
            {"endpoint": endpoint.rsplit("\\", 1)[-1], "constructor_parameter": parameter, "timeout_property": 1, "units": "UNKNOWN_MODEL"}))

    def connect(self): return self.worker[b"connect"]()


class FakeWin32:
    origin = "SYNTHETIC"
    def __init__(self, client):
        self.client = client
        self.expected, self.proof = peer_fixture()
        self.calls, self.spec, self.pending = [], None, None
        self.short_write = 4096
        self.pending_direction = None
        self.poll_result = None
        self.hook = lambda *_: None
        self.close_result = True
        self.closed = False
    def create(self, spec):
        self.calls.append("create"); self.spec = deepcopy(spec)
        self.client.connect()
        return "model-handle-server"
    def query_connection(self, handle):
        self.calls.append("query"); return deepcopy(self.proof)
    def challenge(self, expected, proof_sha, challenges):
        self.calls.append("challenge")
        return {r: response(SECRET, expected, proof_sha, challenges["client"], challenges["server"], r) for r in ("CLIENT", "SERVER")}
    def start_io(self, handle, operation, direction, data, maximum):
        self.calls.append(direction); self.hook(direction)
        if self.closed: return {"operation": operation, "status": "FAILED", "count": 0, "data": b""}
        if self.pending_direction == direction:
            self.pending = operation
            return {"operation": operation, "status": "PENDING", "count": 0, "data": b""}
        raw, count = b"", 0
        if direction == "WRITE": count = self.client.send(data[:self.short_write])
        elif direction == "READ": raw = self.client.receive(maximum); count = len(raw)
        return {"operation": operation, "status": "COMPLETE", "count": count, "data": raw}
    def poll_io(self, handle, operation):
        self.calls.append("poll"); self.hook("POLL")
        return self.poll_result or {"operation": operation, "status": "PENDING", "count": 0, "data": b""}
    def cancel_io(self, handle, operation): self.calls.append("cancel"); return True
    def close(self, handle):
        self.calls.append("close"); self.closed = True
        self.client.close(); return self.close_result


def equipment(*, backend="lua53", parameter=250, open_now=True, allow_cancel=False,
              binding=None, emit_host=None, emit_lua=None, owner_clock=None, endpoint=ENDPOINT):
    expected, _ = peer_fixture()
    if binding:
        expected.update(binding)
        expected["connection_id"] = binding["session_id"] + ".connection"
    client = CePipeTransport({k: expected[k] for k in ("session_id", "channel_id", "epoch")},
                             backend=backend, parameter=parameter, emit=emit_lua, endpoint=endpoint)
    provider = FakeWin32(client)
    provider.proof["binding"] = {k: expected[k] for k in ("session_id", "channel_id", "epoch", "connection_id")}
    for query in provider.proof["queries"].values(): query["connection_id"] = expected["connection_id"]
    provider.proof["security"]["connection_id"] = expected["connection_id"]
    clock, watchdog_clock = owner_clock or Clock(), Clock(1000000)
    transport_events, host_events, watchdog_events = [], [], []
    server = SyntheticServer(provider, clock, transport_events.append, expected, EpochRegistry(),
                             secret=SECRET, challenges=CHALLENGES, allow_model_cancel=allow_cancel)
    host = AdapterCoordinator(server, clock, emit_host or (lambda kind, **kw: host_events.append((kind, kw))),
        watchdog_clock, lambda *args: watchdog_events.append(args), Limits(clock), enabled=True,
        **{k: expected[k] for k in ("session_id", "channel_id", "epoch")})
    if open_now: server.open(endpoint, deadline_ms=clock() + 250)
    return host, server, provider, client, clock, watchdog_clock, transport_events, host_events, watchdog_events
