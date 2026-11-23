"""Deterministic bytes/clock fakes. No CE, pipe, process or target is created."""
from importlib import import_module
from pathlib import Path

from ce_qualification.native_probe_protocol import ProbeError

ROOT = Path(__file__).resolve().parents[2]
LUA_SOURCE = ROOT / "src/qualification/native_ipc_probe.lua"


class Clock:
    def __init__(self, value=0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, amount):
        self.value += amount


def plain(value):
    if type(value) is bytes:
        return value.decode("utf-8")
    if hasattr(value, "items"):
        return {plain(k): plain(v) for k, v in value.items()}
    return value


def table(lua, values):
    return lua.table_from({k.encode(): v.encode() if type(v) is str else v for k, v in values.items()})


def load_probe(backend="lua53"):
    lua = import_module("lupa." + backend).LuaRuntime(encoding=None, unpack_returned_tuples=True)
    loader = lua.eval(b"""function(source)
      local attempted=0
      local env={error=error,type=type,pairs=pairs,ipairs=ipairs,pcall=pcall,
        math=math,string=string,table=table,utf8=utf8,tonumber=tonumber}
      setmetatable(env,{__index=function(_,key) attempted=attempted+1; error('AMBIENT_CAPABILITY:'..key,0) end,
        __newindex=function(_,key) attempted=attempted+1; error('GLOBAL_WRITE:'..key,0) end})
      local chunk=assert(load(source,'@standalone-native-probe','t',env))
      local first,second=chunk(),chunk()
      return first,second,function() return attempted end
    end""")
    first, second, attempts = loader(LUA_SOURCE.read_bytes())
    return lua, first, second, attempts


def error_code(action):
    try:
        action()
    except Exception as exc:
        return str(exc).splitlines()[0]
    return "ACCEPTED"


class LuaTransport:
    """Host sends into a queue; Lua worker steps consume/produce bounded bytes."""
    def __init__(self, binding, clock=None, emit=None, *, backend="lua53", read_size=4096, write_size=4096):
        self.clock = clock or Clock()
        self.binding, self.emit = dict(binding), emit or (lambda *_a, **_k: None)
        self.lua, self.module, self.second_module, self.load_attempts = load_probe(backend)
        self.input, self.output = bytearray(), bytearray()
        self.read_size, self.write_size = read_size, write_size
        self.cancelled, self.worker_closed, self.host_closed = False, False, False
        self.close_calls, self.steps, self.sent_bytes, self.received_bytes = 0, 0, 0, 0
        self.hook = lambda _stage: None
        wrap = self.lua.eval(b"function(f) return function(...) return f(...) end end")
        def read(size):
            amount = min(int(size), self.read_size, len(self.input))
            raw = bytes(self.input[:amount]); del self.input[:amount]
            return raw
        def write(raw):
            amount = min(len(raw), self.write_size)
            self.output.extend(raw[:amount])
            return amount
        def close():
            self.worker_closed = True
            return True
        def emit(kind, request, raw, status):
            kind, status = plain(kind), plain(status)
            kwargs = {"request": plain(request) if request else None}
            if raw is not None:
                kwargs["raw"] = raw
            elif kind == "CLOSE":
                kwargs.update(response=status, cancel_stage="OBSERVED" if status == "CLOSED" else "UNCERTAIN")
            elif kind == "REJECT":
                kwargs["error"] = status
            self.emit(kind, **kwargs)
        cap = table(self.lua, {"mode": "offline", "origin": "SYNTHETIC", "read_some": wrap(read),
                     "write_some": wrap(write), "close": wrap(close), "now_ms": wrap(self.clock),
                     "cancelled": wrap(lambda: self.cancelled), "emit": wrap(emit)})
        self.cap = cap
        self.worker = self.module[b"new_offline"](cap, table(self.lua, binding))

    @property
    def resources(self):
        return int(not self.host_closed) + int(not self.worker_closed)

    def send(self, chunk):
        self.hook("send")
        if self.host_closed:
            raise ProbeError("DISCONNECTED")
        self.input.extend(chunk)
        self.sent_bytes += len(chunk)
        return len(chunk)

    def receive(self, maximum):
        self.hook("receive")
        if self.host_closed:
            return b""
        for _ in range(65541):
            if self.output:
                raw = bytes(self.output[:maximum]); del self.output[:maximum]
                self.received_bytes += len(raw)
                return raw
            if self.worker_closed:
                return b""
            self.steps += 1
            state = self.worker[b"step"]()
            if state == b"WAIT":
                return b""
        raise ProbeError("FAKE_STEP_BOUND")

    def close(self):
        if not self.host_closed:
            self.close_calls += 1
            self.host_closed = True
            self.worker[b"close"]()
        return self.worker_closed


def peer_fixture():
    return {"origin": "SYNTHETIC", "principal": "SYNTHETIC-OPERATOR", "owner": "SYNTHETIC-OPERATOR",
            "client_pid": 101, "server_pid": 102, "client_creation": "0000000000000001",
            "server_creation": "0000000000000002", "dacl": "RESTRICTED_MODEL", "client_handle": "KNOWN_MODEL",
            "session_id": "SYNTHETIC-PEER", "channel_id": "fake", "epoch": 1,
            "client_challenge": "1" * 64, "server_challenge": "2" * 64, "os_evidence": "NOT_RUN"}
