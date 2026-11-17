"""H3-A2, genuine Lua 5.4; every memory/identity/authority/store is synthetic.

No CE, host process measurement, production approval, filesystem receipt store,
or runtime dispatch is available. The authentication registry below is a test
double, not cryptography. Host debug.traceback is retained (H3-A1-R1).
"""

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import re
import struct

import pytest
from lupa.lua54 import LuaRuntime

from test_handoff_candidate_verify import evidence_sets, NAMES, setup, mutate, sync_log_size
from test_single_handoff import files
from test_write_usability import env, prepare_restore, SOURCE_BATCH, LOG_ROOT


ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "h3-synthetic-tests-v1"
AUTHORITY = "synthetic-authority"
PRIVATE = "private callback exception with PID and secret; never public"
SOURCE_NAMES = ("h1_log", "h1_summary", "h1_diagnostic", "h1_companion", "h2", "a1")
WRITE_SOURCE_FIELDS = ["source_batch_id", "source_case_id", "source_session_id"] + [
    key for name in SOURCE_NAMES for key in (name + "_id", name + "_sha256")
]
RESTORE_SOURCE_FIELDS = ["source_request_id", "source_preparation_sha256", "source_receipt_sha256"]
COMMON_FIELDS = [
    "schema", "source_kind", "environment", "request_id", "authority", "trust_domain", "action",
    "case_id", "session_id", "candidate_address", "current_float", "current_pattern", "target_float", "target_pattern", "pid",
    "process_created_utc", "executable", "architecture", "attachment_id", "scene_id",
    "issued_utc", "expires_utc", "max_elapsed_ms",
]
IDENTITY_FIELDS = ["pid", "process_created_utc", "executable", "architecture", "attachment_id"]
DEPENDENCIES = [
    "verify_approval", "sha256", "identity", "scene", "clock", "reserve", "publish", "read_record",
    "finalize_receipt", "read_finalized", "read_integer", "read_float", "write_float",
]


def sha(text):
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def decode(text):
    assert isinstance(text, str) and text.endswith("\r\n")
    lines = text[:-2].split("\r\n")
    result = dict(line.split("=", 1) for line in lines)
    assert len(result) == len(lines)
    return result


def encode(values, fields=None):
    return "".join(f"{key}={values[key]}\r\n" for key in (fields or values))


def change(text, key, value):
    fields = decode(text)
    assert key in fields
    fields[key] = value
    return encode(fields)


def float32(bits):
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def pattern(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]


def timestamp(seconds):
    return (datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_module(lua, name):
    # Load is held by the host, never supplied to the module. Its _G, debug,
    # python, IO, time, networking and actual CE names are poisoned in _ENV.
    load = lua.eval("load")
    module_env = lua.execute("""
        local env = {}
        for _,key in ipairs({'assert','error','getmetatable','setmetatable','rawget','next',
          'pairs','ipairs','pcall','select','tonumber','tostring','type','math','string','table'}) do
          env[key] = _G[key]
        end
        local function forbidden()
          forbidden_calls = (forbidden_calls or 0) + 1
          error('forbidden external API')
        end
        for _,key in ipairs({'io','os','debug','package','python','socket','http'}) do
          env[key] = setmetatable({}, {__index=forbidden,__newindex=forbidden,__call=forbidden})
        end
        env._G=env
        return setmetatable(env,{__index=forbidden,__newindex=forbidden})
    """)
    source = (ROOT / "src" / name).read_text(encoding="utf-8")
    return load(source, "@" + name, "t", module_env)()


class Upstream:
    def __init__(self, evidence, bits=0x42C80000):
        lua, api, _ = setup(evidence)
        if bits != 0x42C80000:
            lua.globals().test_bits = bits
            lua.execute("test_value = string.unpack('<f',string.pack('<I4',test_bits))")
            exact = lua.eval("string.format('%.17g',test_value)")
            legacy = lua.eval("tostring(test_value)")
            for artifact in NAMES:
                prefix = "search_target_" if artifact == "companion" else "target_value_"
                mutate(lua, artifact, prefix + "float", exact if artifact == "companion" else legacy)
                mutate(lua, artifact, prefix + "pattern", f"0x{bits:08X}" if artifact == "companion" else f"0x{bits:X}")
            lua.execute("""
                readInteger=function() return test_bits >= 0x80000000 and test_bits-0x100000000 or test_bits end
                readFloat=function() return test_value end
            """)
            sync_log_size(lua)
        result, failure = api.main()
        assert failure is None and result.verification_status == "VALUE_CONSISTENT_NOT_AUTHORIZED"
        self.bodies = {"h1_" + name: files(lua)[LOG_ROOT + "\\" + filename] for name, filename in NAMES.items()}
        self.bodies["h2"] = lua.globals().verify_module.render(result)
        self.review_lua = LuaRuntime(register_eval=False, register_builtins=False, unpack_returned_tuples=True)
        self.admission = safe_module(self.review_lua, "mvp0_handoff_write_admission.lua")
        self.bodies["a1"] = self.review(self.bodies)
        self.h2 = decode(self.bodies["h2"])
        self.bits = bits
        assert decode(self.bodies["a1"])["review_status"] == "SOURCE_REVIEWABLE_NOT_AUTHORIZED"

    def review(self, bodies):
        context = {"review_record_id": "synthetic-a2-review", "h2_report_sha256": sha(bodies["h2"])}
        context.update({name + "_sha256": sha(bodies[name]) for name in SOURCE_NAMES[:4]})
        result = self.admission.evaluate(bodies["h2"], self.review_lua.table_from(context))
        return self.admission.render(result)


@pytest.fixture(scope="module")
def upstream(evidence_sets):
    return Upstream(evidence_sets)


class Simulation:
    def __init__(self, upstream):
        self.upstream = upstream
        self.lua = LuaRuntime(register_eval=False, register_builtins=False, unpack_returned_tuples=True)
        assert self.lua.eval("_VERSION") == "Lua 5.4"
        self.modules = {kind: safe_module(self.lua, f"mvp0_handoff_{kind}_protocol.lua") for kind in ("write", "restore")}
        self.address = int(upstream.h2["candidate_address"], 16)
        self.memory = self.lua.table_from({self.address: upstream.bits})
        self.sources = {name.replace("_", "-"): body for name, body in upstream.bodies.items()}
        self.approvals = {}
        self.consumed = set()
        self.records, self.pending, self.finalized = {}, {}, {}
        self.events, self.writes, self.reads = [], [], []
        self.faults = {}
        self.read_faults, self.identity_faults, self.scene_faults, self.clock_faults = {}, {}, {}, {}
        self.identity_count = self.scene_count = self.clock_count = self.source_calls = 0
        self.verify_fault = None
        self.write_behavior = "true"
        self.before_write = None
        self.on_publish = self.on_reserve = None
        self.dep_tables = {}
        self.identity_values = dict(pid="1234", process_created_utc=timestamp(-3600),
                                    executable=r"C:\Synthetic\target.exe", architecture="x64", attachment_id="synthetic-attachment")
        self.scene_value = "synthetic-scene"
        self.engines = {kind: self.new_engine(kind) for kind in ("write", "restore")}

    def wrap(self, function):
        return self.lua.eval("function(f) return function(...) return f(...) end end")(function)

    def new_engine(self, kind):
        names = DEPENDENCIES + (["read_evidence", "revalidate_sources"] if kind == "write" else [])
        deps = self.lua.table_from({name: self.wrap(getattr(self, name)) for name in names})
        deps.environment = "synthetic_only"
        self.dep_tables[kind] = deps
        result = self.modules[kind].new_synthetic(deps)
        assert not isinstance(result, tuple), result
        return result

    def issue(self, kind="write", request_id=None, **overrides):
        a = dict(schema=f"h3_{kind}_approval_v1", source_kind="h3_single", environment="synthetic_only",
                 request_id=request_id or ("write-one" if kind == "write" else "restore-one"),
                 authority=AUTHORITY, trust_domain=DOMAIN, action=f"single_float32_{kind}_once",
                 case_id="synthetic-case", session_id="synthetic-session", candidate_address=f"0x{self.address:X}",
                 current_float=format(float32(self.upstream.bits), ".17g"), current_pattern=f"0x{self.upstream.bits:08X}",
                 target_float="200", target_pattern="0x43480000", **self.identity_values,
                 scene_id=self.scene_value, issued_utc=timestamp(40), expires_utc=timestamp(160), max_elapsed_ms="5000")
        if kind == "write":
            a.update({key: self.upstream.h2[key] for key in WRITE_SOURCE_FIELDS[:3]})
            for name in SOURCE_NAMES:
                a[name + "_id"] = name.replace("_", "-")
                a[name + "_sha256"] = sha(self.sources[a[name + "_id"]])
            fields = COMMON_FIELDS + WRITE_SOURCE_FIELDS
        else:
            a.update(source_request_id="write-one", issued_utc=timestamp(41), expires_utc=timestamp(161),
                     current_float="200", current_pattern="0x43480000", target_float=format(float32(self.upstream.bits), ".17g"),
                     target_pattern=f"0x{self.upstream.bits:08X}",
                     source_preparation_sha256=sha(self.records[("write-one", "preparation")]),
                     source_receipt_sha256=sha(self.records[("write-one", "receipt")]))
            fields = COMMON_FIELDS + RESTORE_SOURCE_FIELDS
        for prefix in ("current", "target"):
            bits = overrides.get(prefix + "_pattern")
            if isinstance(bits, str) and re.fullmatch(r"0x[0-9A-F]{8}", bits) and prefix + "_float" not in overrides:
                a[prefix + "_float"] = format(float32(int(bits, 16)), ".17g")
        a.update(overrides)
        return self.register(encode(a, fields))

    def register(self, body):
        # Exact immutable registry entries stand in for an independently verified
        # approval channel. These labels are not keys, signatures or real arms.
        proof = f"synthetic-proof-{len(self.approvals)}"
        self.approvals[proof] = body
        return body, proof

    def verify_approval(self, body, proof, action):
        self.events.append("verify")
        if self.verify_fault == "exception":
            raise RuntimeError(PRIVATE)
        if self.verify_fault == "assertion":
            return True
        if self.approvals.get(proof) != body or decode(body)["action"] != action:
            return None
        return (body if self.verify_fault != "bytes" else body + "x",
                DOMAIN if self.verify_fault != "domain" else "untrusted-domain",
                AUTHORITY if self.verify_fault != "authority" else "untrusted-authority")

    def sha256(self, body):
        return sha(body)

    def read_evidence(self, artifact_id):
        self.source_calls += 1
        return self.sources.get(artifact_id)

    def revalidate_sources(self, approval, *artifacts):
        a = decode(approval)
        bodies = dict(zip(SOURCE_NAMES, artifacts, strict=True))
        self.source_calls += 1
        h1, h2, a1 = (decode(bodies[name]) for name in ("h1_companion", "h2", "a1"))
        # Reconcile exact generated H1 log/summary/diagnostic bytes against the
        # fixture's trusted immutable evidence inventory, independently of the
        # supplied approval hashes. Invalid coherent variants are not registered.
        if any(bodies[name] != self.upstream.bodies[name] for name in SOURCE_NAMES[:4]):
            return None
        if self.upstream.review(bodies) != bodies["a1"]:
            return None
        required = ((h1, "authorization_status", "NOT_AUTHORIZED"),
                    (h1, "handoff_kind", "single_candidate_proposal"),
                    (h2, "verification_status", "VALUE_CONSISTENT_NOT_AUTHORIZED"),
                    (h2, "process_identity_os_measured", "false"),
                    (h2, "source_cryptographic_authentication", "false"),
                    (a1, "review_status", "SOURCE_REVIEWABLE_NOT_AUTHORIZED"),
                    (a1, "review_context_binding_verified", "false"),
                    (a1, "current_target_freshness", "not_evaluated"))
        if any(record.get(key) != value for record, key, value in required):
            return None
        if any(h2[key] != a[key] or h1[key] != a[key] or a1[key] != a[key] for key in WRITE_SOURCE_FIELDS[:3]):
            return None
        if any(f["candidate_address"] != a["candidate_address"] for f in (h1, h2, a1)):
            return None
        if h1["search_target_pattern"] != a["current_pattern"] or h2["expected_search_pattern"] != a["current_pattern"]:
            return None
        return encode(a, WRITE_SOURCE_FIELDS) + encode(a, ["candidate_address", "current_pattern"])

    def identity(self):
        self.identity_count += 1
        self.events.append("identity")
        result = encode(self.identity_values, IDENTITY_FIELDS) + "attachment_verified=true\r\nmeasurement_basis=synthetic_os_measurement\r\n"
        return self.deliver(self.identity_faults.get(self.identity_count, result))

    def scene(self):
        self.scene_count += 1
        return self.deliver(self.scene_faults.get(self.scene_count, self.scene_value))

    def clock(self):
        self.clock_count += 1
        return self.deliver(self.clock_faults.get(self.clock_count, (timestamp(41), 1000)))

    @staticmethod
    def deliver(value):
        if value == "exception":
            raise RuntimeError(PRIVATE)
        return value() if callable(value) else value

    def reserve(self, request, kind, body):
        assert kind == "reservation"
        self.events.append("reserve")
        if request in self.consumed:
            return False
        self.consumed.add(request)  # Atomic no-replace tombstone before any simulated I/O fault.
        if self.on_reserve:
            self.on_reserve()
        return self.persist(request, kind, body)

    def publish(self, request, kind, body):
        assert request in self.consumed and kind in ("preparation", "receipt")
        if self.on_publish:
            self.on_publish(kind)
        return self.persist(request, kind, body)

    def persist(self, request, kind, body):
        key = request, kind
        self.events.append("publish-" + kind)
        if key in self.pending or key in self.records:
            return False
        fault = self.faults.get(kind)
        self.pending[key] = body[:20] if fault == "partial" else body
        if fault in ("fail", "partial", "flush", "close", "verify", "powerloss"):
            return False
        if fault == "exception":
            raise RuntimeError(PRIVATE)
        self.records[key] = self.pending.pop(key)
        self.events.append("durable-" + kind)
        return True

    def read_record(self, request, kind):
        self.events.append("read-" + kind)
        fault = self.faults.get(kind + "-read")
        if fault == "exception":
            raise RuntimeError(PRIVATE)
        if fault == "missing":
            return None
        body = self.records.get((request, kind))
        return body + "corrupt" if fault == "corrupt" and body is not None else body

    def finalize_receipt(self, request, expected_hash):
        self.events.append("finalize")
        if self.faults.get("finalize") == "exception":
            raise RuntimeError(PRIVATE)
        if self.faults.get("finalize"):
            return False
        body = self.records[(request, "receipt")]
        assert sha(body) == expected_hash
        receipt = decode(body)
        assert receipt["execution_success"] == "true" and receipt["api_result"] == "true"
        assert request not in self.finalized
        self.finalized[request] = body
        return True

    def read_finalized(self, request):
        fault = self.faults.get("finalized-read")
        if fault is True or fault == request:
            return None
        return self.finalized.get(request)

    def read(self, address, floating):
        assert address == self.address
        self.reads.append("float" if floating else "integer")
        self.events.append(self.reads[-1])
        bits = self.memory[address]
        value = float32(bits) if floating else (bits - 0x100000000 if bits >= 0x80000000 else bits)
        return self.deliver(self.read_faults.get(len(self.reads), value))

    def read_integer(self, address):
        return self.read(address, False)

    def read_float(self, address):
        return self.read(address, True)

    def write_float(self, address, value):
        assert address == self.address
        # The event ordering assertion is independent of the engine's flags.
        assert self.events.count("durable-preparation") == len(self.writes) + 1
        assert self.events.count("read-preparation") >= len(self.writes) + 1
        self.events.append("write")
        self.writes.append((address, pattern(value)))
        if self.before_write:
            self.before_write()
        if self.write_behavior != "exception-before":
            self.memory[address] = pattern(value)
        if self.write_behavior.startswith("exception"):
            raise RuntimeError(PRIVATE)
        return {"true": True, "false": False, "nil": None, "nonboolean": 1}[self.write_behavior]

    def run(self, kind="write", approval=None):
        return self.engines[kind].run(*(approval or self.issue(kind)))

    def restore_ready(self):
        result = self.run()
        assert result.execution_success is True, self.modules["write"].render(result)
        self.reads.clear()
        self.identity_count = self.scene_count = self.clock_count = 0
        return self.issue("restore")


@pytest.fixture
def sim(upstream):
    instance = Simulation(upstream)
    yield instance
    assert not instance.lua.globals().forbidden_calls
    assert not upstream.review_lua.globals().forbidden_calls


def assert_rejected(sim, result, kind, writes=0):
    assert result.execution_success is False
    assert result.memory_write_attempts == writes
    assert result[kind + "_attempted"] is bool(writes)
    text = sim.modules[kind].render(result)
    assert decode(text)["authorization_status"] == "NOT_PRODUCTION_AUTHORIZED"
    for secret in (PRIVATE, r"C:\Synthetic", "pid=", "synthetic-proof-"):
        assert secret not in text


@pytest.mark.parametrize("bits", [0, 0x80000000, 1, 0x80000001, 0x007FFFFF, 0x00800000,
                                  0x3DCCCCCD, 0xC1480000, 0x42C80000, 0x7F7FFFFF, 0xFF7FFFFF])
def test_separate_authorized_write_and_restore_exact_cycle(evidence_sets, bits):
    s = Simulation(Upstream(evidence_sets, bits))
    approval = s.issue()
    written = s.run(approval=approval)
    assert written.execution_success is True, s.modules["write"].render(written)
    assert written.write_api_ok is written.write_readback_ok is written.receipt_finalized is True
    assert written.memory_read_attempts == 6 and written.memory_write_attempts == 1
    assert s.memory[s.address] == 0x43480000
    prep = decode(s.records[("write-one", "preparation")])
    receipt = decode(s.finalized["write-one"])
    assert prep["current_pattern"] == f"0x{bits:08X}" and prep["attempted"] == "false"
    assert receipt["preparation_sha256"] == sha(s.records[("write-one", "preparation")])
    assert receipt["approval_sha256"] == sha(approval[0])
    assert s.events.index("read-preparation") < s.events.index("write") < s.events.index("durable-receipt")
    source_calls = s.source_calls
    restored = s.run("restore")
    assert restored.execution_success is True, s.modules["restore"].render(restored)
    assert restored.restore_api_ok is restored.restore_readback_ok is restored.receipt_finalized is True
    assert restored.memory_read_attempts == 6 and restored.memory_write_attempts == 1
    assert s.memory[s.address] == bits and len(s.writes) == 2
    assert s.source_calls == source_calls  # No H1/H2/ranking/collector on independent restore.
    assert s.consumed == {"write-one", "restore-one"}
    assert not s.lua.globals().forbidden_calls


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("dependency", DEPENDENCIES + ["environment"])
def test_missing_or_nonfunction_dependency_never_constructs(sim, kind, dependency):
    deps = sim.dep_tables[kind]
    deps[dependency] = None
    engine, failure = sim.modules[kind].new_synthetic(deps)
    assert engine is None and failure in ("invalid_dependencies", "synthetic_only")
    assert not sim.writes


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("fault", ["assertion", "bytes", "domain", "authority", "exception", "unsigned"])
def test_verifier_must_authenticate_exact_artifact_and_authority(sim, kind, fault):
    approval = sim.restore_ready() if kind == "restore" else sim.issue()
    sim.verify_fault = fault
    if fault == "unsigned":
        approval = approval[0], "unregistered-proof"
    result = sim.run(kind, approval)
    assert result.failure_class == "approval_untrusted"
    assert_rejected(sim, result, kind)


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("field,value", [
    ("schema", "h3_write_approval_v99"), ("source_kind", "full"), ("environment", "production"),
    ("authority", "owner"), ("trust_domain", "production"), ("action", "single_float32_other_once"),
    ("request_id", "../unsafe"), ("request_id", "Write-one"), ("request_id", "a" * 65),
    ("case_id", ""), ("session_id", "nil/path"), ("scene_id", "bad\nline"),
    ("candidate_address", "0x0001"), ("candidate_address", "0x20000000000000"),
    ("current_pattern", "0x7F800000"), ("current_pattern", "0xFFC00000"),
    ("target_pattern", "0x7F800001"), ("target_pattern", "0xFF800000"),
    ("target_pattern", "0x4348000a"), ("target_pattern", "200"),
    ("pid", "01234"), ("pid", "4294967296"), ("architecture", "arm64"),
    ("executable", "../target.exe"), ("executable", r"C:\Synthetic\..\target.exe"),
    ("process_created_utc", "2026-02-29T00:00:00Z"), ("issued_utc", timestamp(42)),
    ("expires_utc", timestamp(40)), ("expires_utc", timestamp(162)),
    ("max_elapsed_ms", "120001"), ("max_elapsed_ms", "0"), ("max_elapsed_ms", "1e3"),
])
def test_invalid_signed_approval_bindings_fail_closed(sim, kind, field, value):
    if kind == "restore":
        sim.restore_ready()
    approval = sim.issue(kind, **{field: value})
    result = sim.run(kind, approval)
    assert_rejected(sim, result, kind)
    assert result.reservation_status == "not_attempted"


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("field", COMMON_FIELDS)
@pytest.mark.parametrize("damage", ["missing", "duplicate", "reordered"])
def test_strict_approval_field_inventory(sim, kind, field, damage):
    body, _ = sim.restore_ready() if kind == "restore" else sim.issue()
    lines = body[:-2].split("\r\n")
    index = next(i for i, line in enumerate(lines) if line.startswith(field + "="))
    if damage == "missing":
        lines.pop(index)
    elif damage == "duplicate":
        lines.insert(index, lines[index])
    else:
        other = (index + 1) % len(lines)
        lines[index], lines[other] = lines[other], lines[index]
    result = sim.run(kind, sim.register("\r\n".join(lines) + "\r\n"))
    assert result.failure_class == "approval_invalid"
    assert_rejected(sim, result, kind)


@pytest.mark.parametrize("damage", ["lf", "bare-cr", "nul", "unicode", "truncated", "oversize", "unknown", "empty"])
@pytest.mark.parametrize("kind", ["write", "restore"])
def test_strict_approval_framing(sim, kind, damage):
    body, _ = sim.restore_ready() if kind == "restore" else sim.issue()
    body = {"lf": body.replace("\r\n", "\n"), "bare-cr": body + "\r", "nul": body + "\0",
            "unicode": body + "中\r\n", "truncated": body[:-1], "oversize": body * 20,
            "unknown": body + "approved=true\r\n", "empty": ""}[damage]
    result = sim.run(kind, sim.register(body))
    assert result.failure_class == "approval_invalid"
    assert_rejected(sim, result, kind)


@pytest.mark.parametrize("field,value", [("candidate_address", "0x1234"), ("current_pattern", "0x42C80001"),
    ("source_case_id", "different-case"), ("source_session_id", "different-session"), ("source_batch_id", "other-batch")])
def test_approval_must_match_independently_revalidated_source(sim, field, value):
    result = sim.run(approval=sim.issue(**{field: value}))
    assert result.failure_class == "source_revalidation_failed"
    assert_rejected(sim, result, "write")


@pytest.mark.parametrize("name", SOURCE_NAMES)
@pytest.mark.parametrize("damage", ["missing", "bytes", "hash", "signed-invalid-source"])
def test_exact_source_bytes_rehashed_and_invalid_upstream_never_authorizes(sim, name, damage):
    approval = sim.issue()
    artifact_id = name.replace("_", "-")
    if damage == "missing":
        del sim.sources[artifact_id]
    elif damage in ("bytes", "signed-invalid-source"):
        sim.sources[artifact_id] += "authorization_status=AUTHORIZED\r\n"
        if damage == "signed-invalid-source":
            approval = sim.issue()
    else:
        approval = sim.issue(**{name + "_sha256": "0" * 64})
    result = sim.run(approval=approval)
    assert_rejected(sim, result, "write")
    assert result.reservation_status == "not_attempted"


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("check", [1, 2, 3])
@pytest.mark.parametrize("fault", ["missing", "pid-reuse", "executable", "architecture", "attachment", "unmeasured", "exit", "scene"])
def test_identity_and_scene_rechecked_before_mutation(sim, kind, check, fault):
    approval = sim.restore_ready() if kind == "restore" else sim.issue()
    base = encode(sim.identity_values, IDENTITY_FIELDS) + "attachment_verified=true\r\nmeasurement_basis=synthetic_os_measurement\r\n"
    values = {"missing": None, "pid-reuse": change(base, "process_created_utc", timestamp(-3599)),
              "executable": change(base, "executable", r"C:\Synthetic\other.exe"),
              "architecture": change(base, "architecture", "x86"),
              "attachment": change(base, "attachment_verified", "false"),
              "unmeasured": change(base, "measurement_basis", "operator_claim"), "exit": "exception"}
    if fault == "scene":
        sim.scene_faults[check] = "changed-scene"
    else:
        sim.identity_faults[check] = values[fault]
    result = sim.run(kind, approval)
    assert_rejected(sim, result, kind)
    assert result.failure_class in ("identity_mismatch", "scene_mismatch")


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("check", [1, 2, 3, 4])
@pytest.mark.parametrize("clock_value", [(timestamp(39), 1000), (timestamp(161), 1000),
    (timestamp(41), 999), (timestamp(47), 7001), (timestamp(43), 1000), ("bad", 1000),
    (timestamp(41), -1), (timestamp(41), 1.5)])
def test_expiry_rollback_pause_and_invalid_clocks(sim, kind, check, clock_value):
    approval = sim.restore_ready() if kind == "restore" else sim.issue()
    # A first reading establishes the monotonic epoch; 999 is not a rollback
    # until a previous observation exists, and a six-second first age is legal.
    if check == 1 and clock_value in ((timestamp(41), 999), (timestamp(47), 7001), (timestamp(43), 1000)):
        sim.clock_faults[1] = (timestamp(41), 1000)
        sim.clock_faults[2] = clock_value
    else:
        sim.clock_faults[check] = clock_value
    result = sim.run(kind, approval)
    assert_rejected(sim, result, kind)


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("read", [1, 2, 3, 4])
@pytest.mark.parametrize("fault", [None, True, "exception", "100", float("inf"), float("nan"), -1.25, 0])
def test_dual_observations_fail_before_write(sim, kind, read, fault):
    approval = sim.restore_ready() if kind == "restore" else sim.issue()
    sim.read_faults[read] = fault
    result = sim.run(kind, approval)
    assert_rejected(sim, result, kind)
    assert result.failure_class in ("initial_value_mismatch", "prewrite_value_mismatch")
    assert result.memory_read_attempts in (2, 4)
    assert decode(sim.records[(decode(approval[0])["request_id"], "receipt")])["execution_success"] == "false"


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("stage", ["reservation", "preparation", "receipt"])
@pytest.mark.parametrize("fault", ["fail", "partial", "flush", "close", "verify", "powerloss", "exception"])
def test_durable_failure_and_crash_tombstone_survive_engine_reload(sim, kind, stage, fault):
    approval = sim.restore_ready() if kind == "restore" else sim.issue()
    request = decode(approval[0])["request_id"]
    sim.faults[stage] = fault
    result = sim.run(kind, approval)
    assert_rejected(sim, result, kind, writes=int(stage == "receipt"))
    assert request in sim.consumed and request not in sim.finalized
    sim.pending.clear()  # Power loss discards non-durable data, never the tombstone.
    sim.faults.clear()
    sim.engines[kind] = sim.new_engine(kind)
    retried = sim.run(kind, approval)
    assert_rejected(sim, retried, kind)
    assert retried.reservation_status == "uncertain"


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("stage", ["reservation", "preparation", "receipt"])
@pytest.mark.parametrize("fault", ["missing", "corrupt", "exception"])
def test_independent_storage_readback_required(sim, kind, stage, fault):
    approval = sim.restore_ready() if kind == "restore" else sim.issue()
    sim.faults[stage + "-read"] = fault
    result = sim.run(kind, approval)
    assert_rejected(sim, result, kind, writes=int(stage == "receipt"))
    assert result.receipt_finalized is False


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("behavior", ["false", "nil", "nonboolean", "exception-before", "exception-after"])
def test_mutation_failure_is_one_attempt_and_no_rollback(sim, kind, behavior):
    approval = sim.restore_ready() if kind == "restore" else sim.issue()
    before = len(sim.writes)
    sim.write_behavior = behavior
    result = sim.run(kind, approval)
    assert_rejected(sim, result, kind, writes=1)
    assert len(sim.writes) == before + 1 and result.memory_read_attempts == 6
    assert result.status == "UNCERTAIN" and result.receipt_published is True
    receipt = decode(sim.records[(decode(approval[0])["request_id"], "receipt")])
    assert receipt["attempted"] == "true" and receipt["execution_success"] == "false"
    assert result.receipt_finalized is False


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("read", [5, 6])
@pytest.mark.parametrize("fault", [None, "exception", 0, float("inf"), float("nan")])
def test_readback_mismatch_never_retries_or_confirms(sim, kind, read, fault):
    approval = sim.restore_ready() if kind == "restore" else sim.issue()
    sim.read_faults[read] = fault
    result = sim.run(kind, approval)
    assert_rejected(sim, result, kind, writes=1)
    assert result.memory_read_attempts == 6 and result.receipt_finalized is False
    assert result[kind + "_api_ok"] is True


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("fault", ["identity", "expiry", "slow-readback", "finalize", "finalize-exception", "finalized-read"])
def test_postwrite_uncertainty_never_becomes_execution_success(sim, kind, fault):
    approval = sim.restore_ready() if kind == "restore" else sim.issue()
    if fault == "identity":
        sim.identity_faults[4] = None
    elif fault == "expiry":
        sim.clock_faults[5] = (timestamp(200), 1000)
    elif fault == "slow-readback":
        sim.clock_faults[6] = (timestamp(47), 7001)
    elif fault == "finalized-read":
        sim.faults["finalized-read"] = decode(approval[0])["request_id"]
    else:
        sim.faults["finalize" if fault.startswith("finalize-") else fault] = "exception" if fault.endswith("exception") else True
    result = sim.run(kind, approval)
    assert_rejected(sim, result, kind, writes=1)
    assert result.memory_read_attempts == (4 if fault in ("identity", "expiry") else 6)


@pytest.mark.parametrize("kind", ["write", "restore"])
def test_duplicate_concurrent_and_reentrant_ids_cannot_replace_evidence(sim, kind):
    approval = sim.restore_ready() if kind == "restore" else sim.issue()
    second_engine = sim.new_engine(kind)
    outcomes = []
    sim.on_reserve = lambda: outcomes.extend([second_engine.run(*approval), sim.engines[kind].run(*approval)])
    result = sim.run(kind, approval)
    assert result.execution_success is True
    assert len(outcomes) == 2 and all(not r.execution_success for r in outcomes)
    assert outcomes[0].reservation_status == "uncertain" and outcomes[1].failure_class == "engine_busy"
    before = dict(sim.records)
    repeated = sim.run(kind, approval)
    assert_rejected(sim, repeated, kind)
    assert sim.records == before


@pytest.mark.parametrize("source", ["h1_companion", "h2", "a1", "full", "write-approval", "result-table", "approved-table"])
def test_non_authorizing_artifacts_and_tables_are_not_approval(sim, source):
    if source in sim.upstream.bodies:
        body = sim.upstream.bodies[source]
    elif source == "full":
        body = "execution_success=true\r\nvalidation_profile=full\r\n"
    elif source == "write-approval":
        body = sim.issue()[0]
    elif source == "result-table":
        body = sim.modules["write"].render(sim.run(approval=("", "x")))
    else:
        body = sim.lua.table_from({"approved": True})
    # Cross-route write approval is rejected by restore without source loading.
    for kind in (["restore"] if source == "write-approval" else ["write", "restore"]):
        result = sim.engines[kind].run(body, "synthetic-proof")
        assert_rejected(sim, result, kind)


@pytest.mark.parametrize("field,value", [
    ("schema", "h3_single_write_receipt_v2"), ("source_kind", "full"), ("request_id", "other-write"),
    ("action", "single_float32_restore_once"), ("approval_sha256", "0" * 64),
    ("sources_sha256", "0" * 64), ("process_sha256", "0" * 64), ("scope_sha256", "0" * 64),
    ("candidate_address", "0x1234"), ("current_pattern", "0x42C80001"), ("target_pattern", "0x43480001"),
    ("reservation_sha256", "0" * 64), ("preparation_sha256", "0" * 64), ("state", "UNCONFIRMED"),
    ("attempted", "false"), ("api_result", "exception"), ("api_ok", "false"), ("readback_ok", "false"),
    ("execution_success", "false"), ("failure_class", "mutation_api_exception"),
    ("last_checked_utc", timestamp(39)), ("last_checked_monotonic_ms", "999"),
])
def test_restore_rejects_even_signed_corrupt_or_unconfirmed_source(sim, field, value):
    sim.restore_ready()
    body = change(sim.records[("write-one", "receipt")], field, value)
    sim.records[("write-one", "receipt")] = sim.finalized["write-one"] = body
    result = sim.run("restore", sim.issue("restore"))
    assert_rejected(sim, result, "restore")
    assert result.reservation_status == "not_attempted"


@pytest.mark.parametrize("artifact", ["reservation", "preparation", "receipt"])
@pytest.mark.parametrize("damage", ["missing", "truncated", "duplicate", "reordered", "unknown", "h1", "h2", "a1", "full", "swap"])
def test_restore_strict_h3_source_parser(sim, artifact, damage):
    sim.restore_ready()
    key = "write-one", artifact
    body = sim.records[key]
    if damage == "missing":
        approval = sim.issue("restore")
        del sim.records[key]
        if artifact == "receipt":
            sim.finalized.clear()
    else:
        lines = body[:-2].split("\r\n")
        if damage == "duplicate":
            body += lines[0] + "\r\n"
        elif damage == "reordered":
            lines[0], lines[1] = lines[1], lines[0]
            body = "\r\n".join(lines) + "\r\n"
        elif damage == "unknown":
            body += "known_true_addr=0x1234\r\n"
        elif damage == "truncated":
            body = body[:-1]
        elif damage in ("h1", "h2", "a1"):
            body = sim.upstream.bodies["h1_companion" if damage == "h1" else damage]
        elif damage == "full":
            body = "execution_success=true\r\nsource_kind=full\r\n"
        else:
            body = sim.records[("write-one", "receipt" if artifact != "receipt" else "preparation")]
        sim.records[key] = body
        if artifact == "receipt":
            sim.finalized["write-one"] = body
        approval = sim.issue("restore")
    result = sim.run("restore", approval)
    assert_rejected(sim, result, "restore")
    assert result.reservation_status == "not_attempted"


@pytest.mark.parametrize("field,value", [("source_request_id", "other-write"), ("source_request_id", "restore-one"),
    ("source_preparation_sha256", "0" * 64), ("source_receipt_sha256", "0" * 64),
    ("candidate_address", "0x1234"), ("current_pattern", "0x43480001"), ("target_pattern", "0x42C80001"),
    ("case_id", "other-case"), ("session_id", "other-session"), ("scene_id", "other-scene"),
    ("process_created_utc", timestamp(-3599))])
def test_restore_approval_cannot_swap_source_or_process(sim, field, value):
    sim.restore_ready()
    result = sim.run("restore", sim.issue("restore", **{field: value}))
    assert_rejected(sim, result, "restore")
    assert result.reservation_status == "not_attempted"


def test_failed_write_view_mutation_cannot_create_restore_source(sim):
    sim.write_behavior = "false"
    result = sim.run()
    result.execution_success = True
    result.write_api_ok = True
    assert decode(sim.modules["write"].render(result))["failure_class"] == "invalid_result"
    assert "write-one" not in sim.finalized
    sim.write_behavior = "true"
    rejected = sim.run("restore", sim.issue("restore"))
    assert_rejected(sim, rejected, "restore")


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("damage", ["change", "delete", "add", "copy", "metatable", "extra"])
def test_public_results_are_nontransferable_sealed_snapshots(sim, kind, damage):
    result = sim.engines[kind].run("", "x")
    if damage == "change":
        result.execution_success = True
    elif damage == "delete":
        result.failure_class = None
    elif damage == "add":
        result.private_text = PRIVATE
    elif damage == "copy":
        result = sim.lua.table_from(dict(result.items()))
    elif damage == "metatable":
        sim.lua.eval("function(t) return setmetatable(t,{__metatable=false}) end")(result)
    text = sim.modules[kind].render(result, True) if damage == "extra" else sim.modules[kind].render(result)
    assert decode(text)["failure_class"] == "invalid_result" and PRIVATE not in text


def test_callback_table_mutation_does_not_replace_captured_authority(sim):
    sim.dep_tables["write"].verify_approval = sim.wrap(lambda *_: True)
    sim.dep_tables["write"].write_float = sim.wrap(lambda *_: True)
    approval = sim.issue()
    bad = change(change(approval[0], "target_pattern", "0x43490000"), "target_float", "201"), approval[1]
    result = sim.run(approval=bad)
    assert result.failure_class == "approval_untrusted" and not sim.writes
    assert sim.run(approval=approval).execution_success is True and len(sim.writes) == 1


def test_value_drift_during_preparation_and_exhausted_id(sim):
    approval = sim.issue()
    sim.on_publish = lambda kind: sim.memory.__setitem__(sim.address, 0x42C80001) if kind == "preparation" else None
    result = sim.run(approval=approval)
    assert_rejected(sim, result, "write")
    assert result.failure_class == "prewrite_value_mismatch" and result.preparation_published is True
    assert sim.run(approval=approval).failure_class == "request_reused"


def test_actual_legacy_full_parser_rejects_h3_receipt(env, sim):
    assert sim.run().execution_success is True
    lua, executor, opts = env
    prepare_restore(env)
    lua.globals().files[LOG_ROOT + "\\" + SOURCE_BATCH + "__summary.txt"] = sim.records[("write-one", "receipt")]
    result = executor.evaluate(opts)
    assert result.execution_failure_class == "restore_source_evidence_malformed"
    assert lua.globals().reads == len(lua.globals().writes) == 0


def test_no_runtime_dispatch_or_live_defaults_and_unchanged_non_authorization(upstream):
    runner = (ROOT / "src/execute_module-v5.2.0_batch.lua").read_text(encoding="utf-8")
    for kind in ("write", "restore"):
        assert f"mvp0_handoff_{kind}_protocol" not in runner
        source = (ROOT / f"src/mvp0_handoff_{kind}_protocol.lua").read_text(encoding="utf-8")
        assert not re.search(r"\b(?:dofile|loadfile|require|print|readInteger|readFloat|writeFloat)\s*\(", source)
    assert decode(upstream.bodies["a1"])["authorization_status"] == "NOT_AUTHORIZED"
    assert decode(upstream.bodies["h2"])["write_ready"] == "false"


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("value", [None, False, True, 42, "private text"])
def test_foreign_result_types_are_safe_rejections(sim, kind, value):
    text = sim.modules[kind].render(value)
    assert decode(text)["failure_class"] == "invalid_result"


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("field", ["current_float", "target_float"])
@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "-0", "100.000000001", "200.0", "2e2", "0xC8"])
def test_float_text_must_be_canonical_finite_and_exact_pair(sim, kind, field, value):
    if kind == "restore":
        sim.restore_ready()
    result = sim.run(kind, sim.issue(kind, **{field: value}))
    assert result.failure_class == "approval_invalid"
    assert_rejected(sim, result, kind)


@pytest.mark.parametrize("bits,wrong", [(0, -0.0), (0x80000000, 0.0)])
@pytest.mark.parametrize("read", [2, 4])
def test_signed_zero_observation_must_match_integer_pattern(evidence_sets, bits, wrong, read):
    sim = Simulation(Upstream(evidence_sets, bits))
    sim.read_faults[read] = wrong
    result = sim.run()
    assert_rejected(sim, result, "write")
    assert sim.memory[sim.address] == bits


@pytest.mark.parametrize("kind,field", [("write", f) for f in WRITE_SOURCE_FIELDS] + [("restore", f) for f in RESTORE_SOURCE_FIELDS])
@pytest.mark.parametrize("damage", ["missing", "duplicate", "reordered"])
def test_source_approval_fields_are_exact_and_ordered(sim, kind, field, damage):
    body, _ = sim.restore_ready() if kind == "restore" else sim.issue()
    lines = body[:-2].split("\r\n")
    index = next(i for i, line in enumerate(lines) if line.startswith(field + "="))
    if damage == "missing":
        lines.pop(index)
    elif damage == "duplicate":
        lines.insert(index, lines[index])
    else:
        lines[index], lines[0] = lines[0], lines[index]
    result = sim.run(kind, sim.register("\r\n".join(lines) + "\r\n"))
    assert result.failure_class == "approval_invalid"
    assert_rejected(sim, result, kind)


def test_actual_full_source_receipt_is_rejected_by_h3_restore(env, sim):
    sim.restore_ready()
    lua, _, _ = env
    prepare_restore(env)
    full_text = lua.globals().files[LOG_ROOT + "\\" + SOURCE_BATCH + "__summary.txt"]
    assert "execution_success = true" in full_text
    sim.records[("write-one", "receipt")] = sim.finalized["write-one"] = full_text
    result = sim.run("restore", sim.issue("restore"))
    assert_rejected(sim, result, "restore")
    assert result.failure_class == "restore_source_malformed"


@pytest.mark.parametrize("fault", ["fail", "corrupt-read", "finalize"])
def test_unfinalized_success_bytes_do_not_authorize_restore(sim, fault):
    sim.faults[{"fail": "receipt", "corrupt-read": "receipt-read", "finalize": "finalize"}[fault]] = "corrupt" if fault == "corrupt-read" else "fail"
    result = sim.run()
    assert result.memory_confirmed is True and result.execution_success is False
    assert "write-one" not in sim.finalized
    if ("write-one", "receipt") not in sim.records:
        # Retain the interrupted bytes as a hostile local file; this does not
        # create the independent store's protected finalization metadata.
        sim.records[("write-one", "receipt")] = sim.pending[("write-one", "receipt")]
    sim.faults.clear()
    result = sim.run("restore", sim.issue("restore"))
    assert_rejected(sim, result, "restore")
    assert result.failure_class == "restore_source_unavailable"


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("fault", ["identity", "api", "readback"])
def test_receipt_failure_preserves_original_uncertainty_cause(sim, kind, fault):
    approval = sim.restore_ready() if kind == "restore" else sim.issue()
    expected = {"identity": "identity_mismatch", "api": "mutation_api_false", "readback": "readback_mismatch"}[fault]
    if fault == "identity":
        sim.identity_faults[4] = None
    elif fault == "api":
        sim.write_behavior = "false"
    else:
        sim.read_faults[5] = None
    sim.faults["receipt"] = "flush"
    result = sim.run(kind, approval)
    assert_rejected(sim, result, kind, writes=1)
    assert result.operation_failure_class == expected
    assert result.persistence_failure_class == result.failure_class == "receipt_persistence_failed"
    assert result.receipt_published is result.receipt_finalized is False


@pytest.mark.parametrize("kind", ["write", "restore"])
@pytest.mark.parametrize("read", [2, 4])
def test_nearby_double_that_rounds_to_same_float32_is_rejected(sim, kind, read):
    approval = sim.restore_ready() if kind == "restore" else sim.issue()
    current = float(decode(approval[0])["current_float"])
    sim.read_faults[read] = current + 0.000000001
    assert pattern(current) == pattern(sim.read_faults[read])
    result = sim.run(kind, approval)
    assert_rejected(sim, result, kind)
