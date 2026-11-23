"""Deterministic pre/post reservation, storage, IPC and scope fault injection."""
from copy import deepcopy
import struct
import threading

import pytest

from ce_qualification.evidence import canonical, decode, digest
from ce_qualification.qsg_broker import Broker
from ce_qualification.qsg_protocol import Decoder, MockChannel, frame
from ce_qualification.qsg_store import QSGError
from ce_qualification.qsg_verifier import verify
from qsg_support import Model, policy, table, layout, plain


def writing(m):
    assert m.start() is True
    m.until("WRITING")


def ended(m, raw, reserved=None):
    m.w.step(10)
    assert len(m.raw_calls) == raw
    if reserved is not None: assert len(m.broker.events("reserve")) == reserved
    assert not m.api.status().running
    m.w.step(100)
    assert len(m.raw_calls) == raw
    m.close()


@pytest.mark.parametrize("phase", [f"L{i:02}" for i in (1,5,6,8,9,11,12)] +
    ["L09-zero","L09-ambiguous","L09-129_plus","L09-incomplete","L09-invalid"])
def test_zero_budget_phases_refuse_forced_unique_candidate(tmp_path, phase):
    m = Model(tmp_path, phase=phase)
    writing(m); ended(m, 0, 0)


@pytest.mark.parametrize("phase", ["L02","L03"])
def test_prewrite_phase_hold_does_not_relabel_or_spend(tmp_path, phase):
    m=Model(tmp_path,phase=phase); writing(m)
    m.w.step(20)
    assert m.api.status().state=="WRITING" and not m.raw_calls
    m.now_value=300001; m.w.time=300001
    ended(m,0,0)


@pytest.mark.parametrize("stage", ["before_transaction","before_commit","after_commit","before_head","after_head_fsync","after_head_replace","before_ack"])
@pytest.mark.parametrize("operation", ["reserve","claim"])
def test_every_durable_boundary_denies_raw_and_keeps_crash_lock(tmp_path, stage, operation):
    m=Model(tmp_path); writing(m)
    def hook(where,packet):
        if where=="before_dispatch" and packet["message_type"]==operation:
            def fault(point):
                if point==stage: raise OSError("synthetic disk-full/crash")
            m.broker.store.fault=fault
    m.channel.hook=hook
    ended(m,0)
    assert (tmp_path/"authority/owner.lock").exists()
    with pytest.raises(QSGError,match="LOCKED"):
        Broker(tmp_path/"authority",m.seal,clock_ms=m.clock,peer=m.policy["peer"],enabled=True)


@pytest.mark.parametrize("operation,stage,expected", [
    ("reserve","before_request",0),("reserve","before_dispatch",0),("reserve","after_dispatch",1),
    ("reserve","response",1),("claim","before_request",1),("claim","before_dispatch",1),
    ("claim","after_dispatch",1),("claim","response",1),
])
def test_rpc_timeout_or_crash_at_every_grant_boundary(tmp_path,operation,stage,expected):
    m=Model(tmp_path); writing(m)
    def hook(where,packet):
        if where==stage and packet["message_type"].split('.')[0]==operation:
            raise TimeoutError("synthetic timeout")
    m.channel.hook=hook
    ended(m,0,expected)


@pytest.mark.parametrize("field,value", [("epoch","stale"),("sequence","0"),("request_digest","a"*64),
    ("message_type","ready.ACK"),("session_id","other"),("policy_digest","b"*64),("origin","CE_LIVE")])
def test_wrong_or_replayed_pipe_response_cannot_grant(tmp_path,field,value):
    m=Model(tmp_path); writing(m)
    def hook(stage,response):
        if stage=="response" and response["message_type"]=="claim.ACK": response[field]=value
    m.channel.hook=hook
    ended(m,0,1)


@pytest.mark.parametrize("stage", ["PERMIT_REQUEST","RESERVATION","RAW_DISPATCH","RAW_RETURN","VERIFIED"])
def test_critical_recorder_failure_never_allows_later_writes(tmp_path,stage):
    m=Model(tmp_path); writing(m)
    def fault(kind):
        if kind==stage: raise OSError("synthetic sink full")
    m.recorder.fault=fault
    ended(m,1 if stage in {"RAW_RETURN","VERIFIED"} else 0)


@pytest.mark.parametrize("change", ["pid","creation","image","script","layout","provider","allocation","generation",
    "base","size","ownership","fresh","page","retired","ce_switch","dead"])
def test_scope_changes_before_reservation_fail_closed(tmp_path,change):
    m=Model(tmp_path); writing(m)
    witness=m.current_scope(); s=witness["scope"]
    if change=="pid": s["identity"]["pid"]+=1
    elif change=="creation": s["identity"]["creation"]="000000010000005C"
    elif change in {"image","script","layout","provider"}: s["provenance"][change+"_sha256"]="0"*64
    elif change=="allocation": s["allocation_id"]="unbound"
    elif change=="generation": s["generation"]+=1
    elif change=="base": s["base"]="1114112"
    elif change=="size": s["size"]="65532"
    elif change=="ownership": s["owned"]=False
    elif change=="fresh": s["fresh"]=False
    elif change=="page": witness["pages"]={}
    elif change=="retired": witness["retired"]={"1048872":True}
    elif change=="ce_switch": witness["ce_token"]="102:000000010000005B"
    elif change=="dead": witness["alive"]=False
    m.scope_override=witness
    ended(m,0,0)


@pytest.mark.parametrize("change", ["outside_low","outside_high","misaligned","edge_context","bits","bits_lowercase",
    "bits_nan","bits_infinity","operation","nonce","checkpoint","candidate","identity","scope","deadline","phase","unknown"])
def test_broker_independently_rejects_mutated_requests(tmp_path,change):
    m=Model(tmp_path); writing(m)
    def hook(stage,packet):
        if stage!="before_dispatch" or packet["message_type"]!="reserve": return
        d=packet["body"]
        if change.startswith("outside") or change in {"misaligned","edge_context"}:
            addr={"outside_low":1048572,"outside_high":1114112,"misaligned":1048873,"edge_context":1048576}[change]
            d["address"]=str(addr); d["offset"]=str(addr-1048576)
        elif change.startswith("bits"): d["bits"]={"bits":"0x42C80000","bits_lowercase":"0x42fa0000","bits_nan":"0x7FC00000","bits_infinity":"0x7F800000"}[change]
        elif change=="operation": d["operation_id"]="0"
        elif change=="nonce": d["nonce"]=""
        elif change=="checkpoint": d["checkpoint"]="{}"
        elif change=="candidate": d["candidate"]["qualified_count"]=2
        elif change=="identity": d["ce_token"]="101:000000010000005C"
        elif change=="scope": d["scope"]["provenance"]["image_sha256"]="a"*64
        elif change=="deadline": d["deadline_ms"]="0"
        elif change=="phase": d["phase"]="L10"
        elif change=="unknown": d["config_contents"]="forbidden"
    m.channel.hook=hook; ended(m,0,0)


@pytest.mark.parametrize("where", ["after_reserve","after_claim","final_boundary"])
@pytest.mark.parametrize("action", ["stop","switch","expired"])
def test_cancellation_and_identity_races_preserve_consumed_reservation(tmp_path,where,action):
    m=Model(tmp_path); writing(m)
    def act():
        if action=="stop": m.run.revoke("OPERATOR_STOP")
        elif action=="switch": m.w.opened=999
        else: m.w.time+=2000; m.now_value+=2000
    def hook(stage,packet):
        kind=packet["message_type"]
        if stage=="after_dispatch" and kind==("reserve" if where=="after_reserve" else "claim") and where!="final_boundary": act()
    m.channel.hook=hook
    if where=="final_boundary": m.recorder.fault=lambda k: act() if k=="RAW_DISPATCH" else None
    ended(m,0,1)


@pytest.mark.parametrize('backend',['lua53','lua54'])
@pytest.mark.parametrize('delay',[100,101])
def test_claim_expiry_during_final_adapter_checks_refuses_raw(tmp_path,backend,delay):
    m=Model(tmp_path,backend); writing(m)
    def install(kind):
        if kind=='RAW_DISPATCH':
            m.lua.globals().final_check_delay=delay
            m.lua.execute("w.hook=function(event) if event=='read' and not w.expired_in_final then w.expired_in_final=true; w.time=w.time+final_check_delay end end")
    m.recorder.fault=install
    ended(m,0,1)


@pytest.mark.parametrize("failure", ["false","nil","number","throw","no_change","readback_float","reentrant","stop_inside_raw"])
def test_raw_failures_consume_once_and_never_retry(tmp_path,failure):
    m=Model(tmp_path); writing(m)
    if failure=="false": m.w.fail.write_return=False
    if failure=="nil": m.w.fail.write_nil=True
    if failure=="number": m.w.fail.write_return=1
    if failure=="throw": m.w.fail.write="throw"
    if failure=="no_change": m.w.fail.write_no_change=True
    if failure=="readback_float": m.w.fail.readback_float=42.0
    if failure=="reentrant": m.lua.execute("w.hook=function(e) if e=='write' then w.loop.tick() end end")
    if failure=="stop_inside_raw": m.lua.execute("w.hook=function(e) if e=='write' then w.loop.stop() end end")
    ended(m,1,1)


@pytest.mark.parametrize("damage", ["missing_db","missing_head","truncated_db","head","enrollment","pending"])
def test_missing_or_corrupt_ledger_never_reseeds(tmp_path,damage):
    m=Model(tmp_path); m.broker.close()
    root=tmp_path/"authority"
    if damage=="missing_db": (root/"ledger.sqlite").unlink()
    if damage=="missing_head": (root/"head.json").unlink()
    if damage=="truncated_db": (root/"ledger.sqlite").write_bytes(b"broken")
    if damage=="head": (root/"head.json").write_text('{}')
    if damage=="enrollment": (root/"enrollment.json").write_text('{}')
    if damage=="pending": (root/"head.pending").write_text('incomplete')
    with pytest.raises(Exception): Broker(root,m.seal,clock_ms=m.clock,peer=m.policy["peer"],enabled=True)
    assert (root/"owner.lock").exists()


def test_exclusive_ownership_and_concurrent_clients(tmp_path):
    m=Model(tmp_path); writing(m)
    with pytest.raises(QSGError,match="LOCKED"):
        Broker(tmp_path/"authority",m.seal,clock_ms=m.clock,peer=m.policy["peer"],enabled=True)
    entered,release=threading.Event(),threading.Event()
    def hold():
        with m.broker.store.exclusive():
            entered.set(); assert release.wait(5)
    t=threading.Thread(target=hold); t.start(); assert entered.wait(5)
    try:
        with pytest.raises(QSGError,match="CONCURRENT"):
            with m.broker.store.exclusive(): pass
    finally: release.set(); t.join(5)
    m.until("MONITORING"); assert len(m.raw_calls)==1; m.close()


@pytest.mark.parametrize("data", [b'',b'\x01',struct.pack('<I',0),struct.pack('<I',65537),frame({"x":1})+b'extra',
    struct.pack('<I',7)+b'{"x":1',struct.pack('<I',2)+b'\xff\xff',struct.pack('<I',13)+b'{"x":1,"x":2}'])
def test_malformed_frames_are_bounded_and_rejected(data):
    with pytest.raises(Exception): Decoder(250,lambda:0).feed(data,final=True)


def test_fragmentation_deadline_and_duplicate_response():
    now=[0]; d=Decoder(250,lambda:now[0]); value={"schema":"qsg.rpc.v1","x":1}; raw=frame(value)
    assert d.feed(raw[:2]) is None
    assert d.feed(raw[2:6]) is None
    assert d.feed(raw[6:],final=True)==value
    with pytest.raises(QSGError): d.feed(raw)
    d=Decoder(250,lambda:now[0]); d.feed(raw[:4]); now[0]=249; d.feed(raw[4:5]); now[0]=250
    with pytest.raises(QSGError): d.feed(raw[5:])
