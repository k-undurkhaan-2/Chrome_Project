"""P0-01..12 offline activation and adversarial evidence; never native CE."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import struct

import pytest

from ce_qualification.native_ipc_probe import activate_offline, main
from ce_qualification.native_probe_activation import ActivationBridge, FakeProvider, OfflineEnvironment, ReplayRegistry
from ce_qualification.native_probe_admission import (ACTIVATION_FILES, ACTIVATION_SCHEMA, CE_DLL, CE_EXE,
    LP_MANIFEST, P0_CAPS, P0_ZERO, TECHNICAL_FIELDS, require_native_activation)
from ce_qualification.native_probe_protocol import Decoder, ProbeError, canonical, frame, reply_to, sha256
from native_probe_b0_fakes import peer_fixture
from native_probe_fakes import Clock, LuaTransport, ROOT, error_code, load_probe, table
from native_probe_suite import packet

NOW = "2026-11-20T17:30:01Z"


class Equipment:
    def __init__(self):
        self.c, self.w = Clock(), Clock(1000000)
        self.now = NOW
        self.manifest = {"schema":"qsg.p0.source.v1", "protocol":"qsg.native-probe.v1",
            "baseline_manifest_sha256":LP_MANIFEST, "files":{p:sha256((ROOT/p).read_bytes()) for p in ACTIVATION_FILES},
            "ce_exe":CE_EXE, "ce_dll":CE_DLL}
        self.record = {"schema":ACTIVATION_SCHEMA, "protocol":"qsg.native-probe.v1", "origin":"SYNTHETIC",
            "purpose":"P0_OFFLINE_ONLY", "authorization_sha256":sha256(b"public-P0-offline-fixture-approval"),
            "candidate_sha256":sha256(canonical(self.manifest)),
            "assets":{**self.manifest["files"], "ce_exe":CE_EXE, "ce_dll":CE_DLL},
            "identities":{role:{"id":role+"-model", "identity_sha256":sha256(role.encode())}
                          for role in ("host", "operator", "approver")},
            "window":{"start":"2026-11-20T17:30:00Z", "end":"2026-11-20T17:45:00Z"},
            "workspace":str(ROOT), "evidence_dir":str(ROOT/"reports"/"2026-11-21"/"synthetic-p0-unused"),
            "session":{"session_id":"p0", "channel_id":"p0-channel", "epoch":1, "nonce":"1"*64,
                       "case_id":"P0-01", "trial":1}, "cases":[f"P0-{i:02}" for i in range(1,13)],
            "caps":dict(P0_CAPS), "zero":{k:0 for k in P0_ZERO},
            "watchdog":{"mode":"INDEPENDENT_MODEL", "clock_domain":"watchdog", "cancel":"MODEL_ONLY", "terminate":False}}
        self.p = FakeProvider(advance=self.c.advance)
        self.registry = ReplayRegistry()
        self.reseal()

    def reseal(self):
        r = self.record
        self.raw = canonical(r)
        policy = {k:deepcopy(r[k]) for k in ("authorization_sha256", "identities", "window", "workspace",
                  "evidence_dir", "session", "cases", "caps", "zero", "watchdog")}
        policy["record_sha256"] = sha256(self.raw)
        pe, proof = peer_fixture()
        pe.update({k:r["session"][k] for k in ("session_id", "channel_id", "epoch")})
        pe.update(candidate_sha256=r["candidate_sha256"], authorization_sha256=r["authorization_sha256"],
                  connection_id=r["session"]["nonce"][:32])
        pe["client"].update(image_sha256=CE_EXE, component_sha256=CE_DLL)
        proof["binding"] = {k:pe[k] for k in ("session_id", "channel_id", "epoch", "connection_id")}
        for role, observer in (("client", "server"), ("server", "client")):
            proof[role] = deepcopy(pe[role])
            proof["queries"][role].update(observer=deepcopy(pe[observer]), connection_id=pe["connection_id"])
        proof["security"]["connection_id"] = pe["connection_id"]
        technical = {"origin":"SYNTHETIC", "os_evidence":"NOT_PROVEN", "checks":{k:"SYNTHETIC_MATCH" for k in TECHNICAL_FIELDS},
            **{k:deepcopy(r[k]) for k in ("assets", "identities", "session")},
            "peer_expected":pe, "peer_proof":proof, "handle_ref":"model-handle-server"}
        self.e = OfflineEnvironment(canonical(self.manifest), sha256(canonical(self.manifest)), canonical(policy),
            canonical(technical), self.c, lambda:self.now, self.w, self.registry)
        self.b = ActivationBridge(self.e)

    def start(self, raw=None):
        return self.b.activate(self.raw if raw is None else raw, provider=self.p)

    def exchange(self, method, request_id, payload="", **kw):
        return self.b.exchange(method, request_id, payload, **({"case_id":self.record["session"]["case_id"],
                    "nonce":self.record["session"]["nonce"]} | kw))

    def deny(self, raw=None):
        with pytest.raises(ProbeError): self.start(raw)
        assert self.p.open_calls == 0
        assert self.b.result()["status"] == "NOT_PASS"


@pytest.fixture
def equipment(tmp_path, request):
    observed = []
    def make():
        e = Equipment(); observed.append(e); return e
    yield make
    rows = []
    for e in observed:
        if e.b.state not in ("COLD", "STOPPED", "DENIED", "UNCERTAIN"): e.b.stop()
        rows.append({"events":e.b.events, "result":e.b.result(), "provider_calls":e.p.calls,
                     "open_calls":e.p.open_calls, "close_calls":e.p.close_calls,
                     "pending":e.p.pending, "cancel_calls":e.p.cancel_calls,
                     "requests":[v.hex() for v in e.p.requests], "responses":[v.hex() for v in e.p.responses],
                     "candidate_sha256":e.record["candidate_sha256"]})
    with (tmp_path/"p0-observation.json").open("x", encoding="utf-8") as f:
        json.dump({"test_id":request.node.nodeid, "origin":"SYNTHETIC", "observations":rows}, f, sort_keys=True)


@pytest.mark.parametrize("backend", ["lua53", "lua54"])
def test_P0_01_lazy_idempotent_load_and_default_cold(backend, equipment, monkeypatch):
    import ctypes
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_a, **_k: pytest.fail("DLL loader reached"), raising=False)
    _, one, two, calls = load_probe(backend)
    assert calls() == 0 and one[b"version"] == two[b"version"]
    assert error_code(one[b"start_native"]) == "R3_B_NOT_AUTHORIZED"
    e = equipment()
    assert e.b.state == "COLD" and e.b.events == () and not e.p.calls
    with pytest.raises(ProbeError): ActivationBridge().activate()
    with pytest.raises(ProbeError): activate_offline(e.raw)
    assert calls() == 0


def test_P0_01_complete_fake_flow_has_no_native_permission(equipment):
    e = equipment(); e.start()
    e.exchange("HELLO", "hello")
    assert e.exchange("ECHO", "echo", "配置e\u0301🙂")["payload"] == "配置e\u0301🙂"
    e.exchange("PING", "ping")
    e.exchange("CLOSE", "close")
    assert e.b.result()["status"] == "SYNTHETIC_PASS"
    assert e.b.result()["native"] == "NOT_RUN" and e.p.close_calls == 1
    assert [v["state"] for v in e.b.events if v["event"] == "STATE"] == [
        "CONFIG_PARSED", "CANDIDATE_BOUND", "AUTH_BOUND", "TECHNICAL_ADMISSION", "RUN_PERMITTED", "STOPPED"]


@pytest.mark.parametrize("raw", [b"", b"null", b"{}", b"{", b"\xff", b"x"*65537,
    b'{"schema":1,"schema":2}', b'{"a":{"b":1,"b":2}}'], ids=["empty","null","missing","malformed","utf8","oversize","duplicate","nested-duplicate"])
def test_P0_02_invalid_approval_denies_before_open(raw, equipment):
    equipment().deny(raw)


@pytest.mark.parametrize("now", ["2026-11-20T17:29:59Z", "2026-11-20T17:45:00Z", "2026-11-21T17:30:01Z"])
def test_P0_02_window_edges(now, equipment):
    e = equipment(); e.now = now; e.deny()


@pytest.mark.parametrize("asset", sorted(ACTIVATION_FILES | {"ce_exe", "ce_dll"}))
def test_P0_03_each_asset_drift(asset, equipment):
    e = equipment(); e.record["assets"][asset] = "0"*64; e.deny(canonical(e.record))


@pytest.mark.parametrize("kind", ["candidate", "manifest-bytes", "baseline", "protocol", "host", "observed-assets"])
def test_P0_03_independent_candidate_and_host_binding(kind, equipment):
    e = equipment()
    if kind == "candidate": e.record["candidate_sha256"] = "0"*64
    elif kind == "manifest-bytes": e.b.environment = replace(e.e, candidate=e.e.candidate+b" ")
    elif kind == "baseline":
        e.manifest["baseline_manifest_sha256"] = "0"*64; e.reseal()
    elif kind == "protocol": e.record["protocol"] = "qsg.mock.v1"
    elif kind == "host": e.record["identities"]["host"]["identity_sha256"] = "0"*64
    else:
        o=json.loads(e.e.technical); o["assets"]["ce_dll"] = "0"*64
        e.b.environment=replace(e.e, technical=canonical(o))
    e.deny(canonical(e.record))


@pytest.mark.parametrize("kind", ["same-person", "timezone", "offset", "session", "budget", "bool-budget",
    "raised-budget", "trial", "cases", "case", "workspace", "evidence", "zero", "watchdog", "extra",
    "signature", "authenticated", "authority", "fixed-deadline"])
def test_P0_04_ambiguous_or_unapproved_fields(kind, equipment):
    e=equipment(); r=e.record
    if kind == "same-person": r["identities"]["approver"]=deepcopy(r["identities"]["operator"])
    elif kind == "timezone": r["window"]["start"]="2026-11-20T17:30:00"
    elif kind == "offset": r["window"]["start"]="2026-11-21T01:30:00+08:00"
    elif kind == "session": del r["session"]["nonce"]
    elif kind == "budget": del r["caps"]["messages"]
    elif kind == "bool-budget": r["caps"]["messages"]=True
    elif kind == "raised-budget": r["caps"]["request_ms"]=251
    elif kind == "trial": r["session"]["trial"]=4
    elif kind == "cases": r["cases"].append("P0-01")
    elif kind == "case": r["session"]["case_id"]="N01"
    elif kind == "workspace": r["workspace"]="D:\\other"
    elif kind == "evidence": r["evidence_dir"]=str(ROOT/"reports"/"unapproved")
    elif kind == "zero": r["zero"]["target_read"]=1
    elif kind == "watchdog": r["watchdog"]["terminate"]=True
    elif kind == "extra": r["session"]["pid"]=123
    elif kind == "signature": r["signature"]="approved"
    elif kind == "authenticated": r["authenticated"]=True
    elif kind == "authority": r["authorization_sha256"]="0"*64
    elif kind == "fixed-deadline": r["caps"]["request_ms"]=249
    e.deny(canonical(r))


@pytest.mark.parametrize("path", [r"relative", r"\\server\share\evidence", r"\\?\D:\evidence",
    r"D:\reports\..\escape", r"D:\reports\x:stream", r"D:\reports\NUL", "D:\\reports\\trailing ",
    "D:\\reports\\dot.", r"D:\reports\.\alias", r"D:/reports/alias"], ids=range(10))
def test_P0_04_even_pinned_unsafe_path_rejects(path, equipment):
    e=equipment(); e.record["evidence_dir"]=path; e.reseal(); e.deny()


@pytest.mark.parametrize("kind", ["native-origin", "os-proof", "authenticated", "pid-only", "fake-provider"])
def test_P0_05_fake_cannot_become_os_evidence(kind, equipment):
    e=equipment(); o=json.loads(e.e.technical)
    if kind == "native-origin": o["origin"]="NATIVE"
    elif kind == "os-proof": o["os_evidence"]="VERIFIED"
    elif kind == "authenticated": o["authenticated"]=True
    elif kind == "pid-only": o["peer_proof"]={"pid":101, "authenticated":True}
    else:
        class Masquerade:
            origin="SYNTHETIC"
        with pytest.raises(ProbeError): e.b.activate(e.raw, provider=Masquerade())
        assert not e.p.calls; return
    e.b.environment=replace(e.e, technical=canonical(o)); e.deny()


@pytest.mark.parametrize("check", sorted(TECHNICAL_FIELDS))
def test_P0_06_each_missing_technical_prerequisite_denies(check, equipment):
    e=equipment(); o=json.loads(e.e.technical); o["checks"][check]="NOT_PROVEN"
    e.b.environment=replace(e.e, technical=canonical(o)); e.deny()


@pytest.mark.parametrize("kind", ["dacl", "principal", "creation", "handle", "loaded", "observer", "connection", "rights"])
def test_P0_06_connection_specific_negative_proofs(kind, equipment):
    e=equipment(); o=json.loads(e.e.technical); p=o["peer_proof"]
    if kind == "dacl": p["security"]["null_dacl"]=True
    elif kind == "principal": p["client"]["sid"]=p["server"]["sid"]
    elif kind == "creation": p["client"]["creation"]="0000000000000000"
    elif kind == "handle": o["handle_ref"]="unrelated-handle"
    elif kind == "loaded": p["client"]["component_sha256"]="0"*64
    elif kind == "observer": p["queries"]["client"]["observer"]=p["client"]
    elif kind == "connection": p["security"]["connection_id"]="other-connection"
    elif kind == "rights": p["security"]["client_requested_access"] |= 4
    e.b.environment=replace(e.e, technical=canonical(o)); e.deny()


@pytest.mark.parametrize("fault", ["epoch", "session", "digest", "replay", "duplicate"])
def test_P0_07_wire_response_rebinding_and_double_delivery(fault, equipment):
    e=equipment(); e.start(); e.exchange("HELLO", "hello"); e.p.fault=fault
    with pytest.raises(ProbeError): e.exchange("PING", "ping")
    assert e.b.state in ("DENIED", "UNCERTAIN") and e.p.open_calls == 1
    with pytest.raises(ProbeError): e.exchange("PING", "retry")
    assert e.p.open_calls == 1


@pytest.mark.parametrize("kind", ["nonce", "case", "request-replay", "activation-replay", "epoch-reuse"])
def test_P0_07_authority_and_request_replay(kind, equipment):
    e=equipment(); e.start(); e.exchange("HELLO", "hello")
    with pytest.raises(ProbeError):
        if kind == "nonce": e.exchange("PING", "ping", nonce="0"*64)
        elif kind == "case": e.exchange("PING", "ping", case_id="P0-02")
        elif kind == "request-replay": e.exchange("PING", "hello")
        elif kind == "activation-replay": e.start()
        else: ActivationBridge(e.e).activate(e.raw, provider=FakeProvider())
    assert e.p.open_calls == 1


@pytest.mark.parametrize("size", [65535,65536,65537])
def test_P0_08_exact_frame_body_boundaries(size):
    p=packet(method="ECHO"); p["payload"]="x"*(size-len(canonical(p)))
    raw=canonical(p); assert len(raw) == size
    wire=struct.pack("<I",len(raw))+raw
    d=Decoder(250,lambda:0)
    if size > 65536:
        with pytest.raises(ProbeError, match="FRAME_LENGTH"): d.feed(wire[:4])
        assert len(d.body) == 0
    else:
        assert d.feed(wire)["payload"] == p["payload"]


@pytest.mark.parametrize("size", [65535,65536,65537])
def test_P0_08_bridge_response_limit(size, equipment):
    e=equipment(); e.start(); e.exchange("HELLO","hello")
    request=packet(method="ECHO", session_id="p0", channel_id="p0-channel", request_id="echo", sequence=2)
    payload="x"*(size-len(canonical(reply_to(request))))
    if size > 65536:
        with pytest.raises(ProbeError, match="FRAME_LENGTH"): e.exchange("ECHO","echo",payload)
    else:
        e.exchange("ECHO","echo",payload)
        assert len(e.p.responses[-1])-4 == size
        e.exchange("CLOSE","close")
        assert e.b.result()["status"] == "SYNTHETIC_PASS"


@pytest.mark.parametrize("raw", [b"\xff", b"{", b'{"x":1,"x":2}', b"null", b"[]"], ids=["utf8","json","duplicate","null","array"])
def test_P0_08_malformed_payload_is_rejected(raw):
    with pytest.raises(ProbeError): Decoder(250,lambda:0).feed(struct.pack("<I",len(raw))+raw)


@pytest.mark.parametrize("field,value", [("method","claim"),("method","reserve"),("schema","qsg.mock.v1"),
    ("target_pid",1),("address","0x1000"),("lua","return 1"),("command","cmd"),("module","ctypes")])
def test_P0_08_target_and_executable_fields_reject(field,value):
    p=packet(); p[field]=value; raw=canonical(p)
    with pytest.raises(ProbeError): Decoder(250,lambda:0).feed(struct.pack("<I",len(raw))+raw)


@pytest.mark.parametrize("fault", ["late","slow","cancel","crash","disconnect","malformed"])
def test_P0_09_deadline_cancel_and_fault_no_retry(fault,equipment):
    e=equipment(); e.start(); e.exchange("HELLO","hello"); e.p.fault=fault
    if fault == "slow": e.p.fragment=1
    with pytest.raises(ProbeError): e.exchange("PING","ping")
    assert e.p.open_calls == 1 and e.b.result()["status"] == "NOT_PASS"
    if fault == "slow": assert e.c.value == 300
    if fault == "late": assert e.c.value == 250


@pytest.mark.parametrize("kind", ["expiry","case","owner-clock","watchdog","message-budget"])
def test_P0_09_authority_is_rechecked_during_runtime(kind,equipment):
    e=equipment()
    if kind == "message-budget": e.record["caps"]["messages"]=1; e.reseal()
    e.start(); e.exchange("HELLO","hello")
    if kind == "expiry": e.now="2026-11-20T17:45:00Z"
    elif kind == "case": e.c.value=60000
    elif kind == "owner-clock": e.c.value=-1
    elif kind == "watchdog":
        e.p.fault="late"; e.p.advance=lambda _:e.w.advance(2000)
    with pytest.raises(ProbeError): e.exchange("PING","ping")
    assert e.p.open_calls == 1


def test_P0_10_cancel_does_not_release_pending_buffer(equipment):
    e=equipment(); e.start(); e.exchange("HELLO","hello"); e.p.fault="pending"
    with pytest.raises(ProbeError): e.exchange("PING","ping")
    assert e.b.state == "UNCERTAIN" and e.p.pending and e.p.buffer
    assert e.p.cancel_calls == 1 and e.p.close_calls == 0
    with pytest.raises(ProbeError,match="P0_HANDLE_OWNERSHIP"): e.p.observe_completion("wrong-owner")
    assert e.p.buffer and e.p.pending
    assert e.p.observe_completion("fake-operation-1") is True
    assert e.p.close_calls == 1 and e.b.result()["status"] == "NOT_PASS"


@pytest.mark.parametrize("fault", ["cleanup","missing-close","overflow"])
def test_P0_10_cleanup_and_evidence_uncertainty_never_pass(fault,equipment):
    e=equipment()
    if fault == "overflow": e.record["caps"]["evidence_bytes"]=4096; e.reseal()
    if fault == "overflow":
        with pytest.raises(ProbeError): e.start(); e.exchange("HELLO","hello")
    else:
        e.start(); e.exchange("HELLO","hello")
        if fault == "cleanup":
            e.p.fault="cleanup"
            with pytest.raises(ProbeError): e.exchange("CLOSE","close")
        else: e.b.stop()
    assert e.b.state == "UNCERTAIN" and e.b.result()["status"] == "NOT_PASS"
    assert sum(len(canonical(v)) for v in e.b.events) <= e.record["caps"]["evidence_bytes"]


def test_P0_10_event_copy_and_sensitive_id_redaction(equipment):
    e=equipment(); e.start(); events=e.b.events; events[0]["state"]="forged"
    assert e.b.events[0]["state"] == "CONFIG_PARSED"
    raw=canonical(list(e.b.events))
    for role in ("host","operator","approver"): assert e.record["identities"][role]["id"].encode() not in raw
    assert e.record["session"]["nonce"].encode() not in raw


def test_P0_11_native_entry_denies_even_with_fake_approval_and_replaced_model_gate(monkeypatch,equipment,capsys):
    import ctypes
    import ce_qualification.native_probe_winpipe as pipe
    from ce_qualification.native_probe_win32 import load_native_api, Win32Provider
    calls=[]
    monkeypatch.setattr(ctypes,"WinDLL",lambda *_a,**_k:calls.append("DLL"),raising=False)
    for k in ("NATIVE_APPROVED","QSG_NATIVE","P0_ACTIVATE"): monkeypatch.setenv(k,"true")
    e=equipment(); e.start()
    assert main(["native"]) == 3
    assert "NOT_RUN" in capsys.readouterr().out
    for action in (load_native_api,require_native_activation,pipe.terminate_native_process,
                   lambda:pipe.open_native(e.record,provider_factory=lambda:calls.append("factory")),
                   lambda:pipe.NativeProvider().create({}),lambda:Win32Provider().create({})):
        with pytest.raises(ProbeError): action()
    monkeypatch.setattr(pipe,"require_native_activation",lambda *_a,**_k:None)
    with pytest.raises(ProbeError): pipe.open_native(e.record,provider_factory=lambda:calls.append("factory"))
    with pytest.raises(ProbeError): pipe.open_activation_fake({"approved":True},e.p)
    assert calls == []


def test_P0_11_protected_source_freezes_are_unchanged():
    base=ROOT/"reports/2026-11-20/qsg_r2_20261120T104655Z/manifest.json"
    m=json.loads(base.read_bytes()); hashes={p:v for p,v in m["candidate_sha256"].items() if p.startswith("src/")}
    hashes.update({p:v["after"] for p,v in m["protected_comparison"].items() if p.startswith("src/")})
    lp=json.loads((ROOT/"reports/2026-11-21/qsg_lp_r1_20261120T162401Z/manifest_final.json").read_bytes())
    hashes.update({p:v["new_hash"] for p,v in lp["candidate"]["files"].items() if p.startswith("src/")})
    for p,h in hashes.items(): assert sha256((ROOT/p).read_bytes()) == h, p


@pytest.mark.parametrize("backend", ["lua53","lua54"])
def test_P0_12_lua_binding_is_inert_and_pinned(backend,equipment):
    e=equipment(); e.start()
    t=LuaTransport({"session_id":"p0","channel_id":"p0-channel","epoch":1},backend=backend)
    m={"schema":ACTIVATION_SCHEMA,"origin":"SYNTHETIC","state":"RUN_PERMITTED",
       "native_activation":"BLOCKED_NATIVE_ACTIVATION_UNPROVEN","os_evidence":"NOT_PROVEN",
       "candidate_sha256":e.record["candidate_sha256"],"authorization_sha256":e.record["authorization_sha256"],
       **{k:e.record["session"][k] for k in ("session_id","channel_id","epoch","nonce")}}
    expected=table(t.lua,m)
    worker=t.module[b"bind_activation_model"](t.cap,table(t.lua,t.binding),table(t.lua,m),expected)
    assert t.steps == 0 and t.sent_bytes == 0 and t.received_bytes == 0 and t.load_attempts() == 0
    assert error_code(lambda:t.module[b"bind_activation_model"](t.cap,table(t.lua,t.binding),table(t.lua,m),expected)) == "P0_ACTIVATION_REPLAY"
    m["candidate_sha256"]="0"*64
    assert error_code(lambda:t.module[b"bind_activation_model"](t.cap,table(t.lua,t.binding),table(t.lua,m),expected)) == "P0_BINDING"
    assert error_code(t.module[b"start_native"]) == "R3_B_NOT_AUTHORIZED"
    worker[b"close"](); t.close()


@pytest.mark.parametrize("suffix", ["ordinary", "long_"+"x"*90, "配置e\u0301🙂"], ids=["ordinary","long","unicode"])
def test_P0_12_long_unicode_evidence_policy_and_complete_flow(suffix,equipment):
    e=equipment(); e.record["evidence_dir"] += "\\"+suffix; e.reseal(); e.start()
    e.exchange("HELLO","hello"); e.exchange("ECHO","echo",suffix); e.exchange("CLOSE","close")
    assert e.b.result()["status"] == "SYNTHETIC_PASS"


def test_P0_04_pinned_integer_is_not_a_boolean(equipment):
    e=equipment(); e.record["watchdog"]["terminate"]=0; e.reseal(); e.deny()


def test_P0_03_protocol_hash_cannot_be_replaced_by_new_test_pin(equipment):
    e=equipment(); key="src/ce_qualification/native_probe_protocol.py"
    e.manifest["files"][key]="0"*64; e.record["assets"][key]="0"*64
    e.record["candidate_sha256"]=sha256(canonical(e.manifest)); e.reseal(); e.deny()


def test_P0_09_nested_exchange_revokes_the_outer_request(equipment):
    e=equipment(); e.start(); e.exchange("HELLO","hello")
    e.p.fault="late"
    e.p.advance=lambda _:e.exchange("PING","nested")
    with pytest.raises(ProbeError,match="P0_OUTSTANDING_REQUEST"): e.exchange("PING","outer")
    assert e.b.result()["status"] == "NOT_PASS" and e.p.open_calls == 1


def test_P0_09_separate_watchdog_epoch_does_not_shorten_owner_window(equipment):
    e=equipment(); e.w.value=2**50; e.start()
    e.exchange("HELLO","hello"); e.c.advance(249)
    e.exchange("PING","ping"); e.exchange("CLOSE","close")
    assert e.b.result()["status"] == "SYNTHETIC_PASS"


def test_P0_06_technical_schema_success_is_not_native_approval(equipment):
    e=equipment(); e.start()
    assert e.b.result()["os_evidence"] == "NOT_PROVEN"
    with pytest.raises(ProbeError): require_native_activation(e.b.result())
    assert e.b.result()["native_activation"] == "BLOCKED_NATIVE_ACTIVATION_UNPROVEN"


def test_P0_10_shared_suite_evidence_budget_is_not_reset_by_new_bridge(equipment):
    first=equipment(); registry,clock=first.registry,first.c
    succeeded=0; denied=False
    for i in range(12):
        e=first if i == 0 else equipment()
        e.registry,e.c=registry,clock
        e.record["caps"]["evidence_bytes"]=60000
        e.record["session"].update(epoch=i+1,channel_id=f"channel-{i}",nonce=f"{i+1:064x}",case_id=f"P0-{i+1:02}")
        e.reseal()
        try:
            e.start(); e.exchange("HELLO","hello"); e.exchange("CLOSE","close"); succeeded+=1
        except ProbeError:
            assert e.b.state == "UNCERTAIN" and e.b.result()["status"] == "NOT_PASS"
            denied=True; break
    assert succeeded >= 1 and denied and registry.evidence_bytes <= 60000


def test_P0_09_suite_clock_domain_cannot_change_between_cases(equipment):
    first=equipment(); first.start(); first.exchange("HELLO","hello"); first.exchange("CLOSE","close")
    e=equipment(); e.registry=first.registry
    e.record["session"].update(epoch=2,channel_id="new-channel",nonce="2"*64,case_id="P0-02")
    e.reseal(); e.deny()
    assert e.b.reason == "P0_SUITE_CLOCK"


@pytest.mark.parametrize("uncertain", [False,True],ids=["active","uncertain-completion"])
def test_P0_10_suite_permits_only_one_active_connection(uncertain,equipment):
    first=equipment(); first.start(); first.exchange("HELLO","hello")
    if uncertain:
        first.p.fault="pending"
        with pytest.raises(ProbeError): first.exchange("PING","pending")
        assert first.b.state == "UNCERTAIN"
    second=equipment(); second.registry,second.c=first.registry,first.c
    second.record["session"].update(epoch=2,channel_id="second",nonce="2"*64,case_id="P0-02")
    second.reseal(); second.deny()
    assert second.b.reason == "P0_SUITE_CONNECTION_ACTIVE" and first.registry.active is first.b
    if uncertain:
        first.p.observe_completion("fake-operation-1")
        assert first.registry.active is first.b and first.b.result()["status"] == "NOT_PASS"
    else:
        first.exchange("CLOSE","close")
        assert first.registry.active is None and first.b.result()["status"] == "SYNTHETIC_PASS"


def test_P0_02_invalid_environment_registry_is_denied(equipment):
    e=equipment(); e.b.environment=replace(e.e,registry=None); e.deny()
