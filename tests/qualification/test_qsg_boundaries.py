"""Remaining lifecycle, framing, enrollment and scenario boundary checks."""
from copy import deepcopy
import threading
import pytest

from ce_qualification.evidence import digest, canonical
from ce_qualification.qsg_broker import Broker
from ce_qualification.qsg_protocol import MockChannel
from ce_qualification.qsg_store import QSGError
from qsg_support import Model, policy, table, layout, plain, ROOT, SOURCES


@pytest.mark.parametrize('field,value',[('schema','bad'),('origin','LIVE'),('session_id','other'),('epoch','old'),
    ('sequence','0'),('deadline_ms','999999'),('policy_digest','0'*64),('extra','secret')])
def test_request_envelope_is_validated_by_receiver(tmp_path,field,value):
    m=Model(tmp_path)
    m.channel.hook=lambda stage,p: p.update({field:value}) if stage=='before_request' else None
    with pytest.raises(Exception): m.start()
    assert not m.raw_calls and not m.broker.events('reserve')
    m.close()


@pytest.mark.parametrize('mutation',['live','window','targets','creation','image','range','owned','b_scope','peer','approval'])
def test_bad_enrollment_or_peer_fails_before_adapter(tmp_path,mutation):
    p=policy()
    if mutation=='live': p['origin']='LIVE'
    if mutation=='window': p['end_ms']='3600001'
    if mutation=='targets': p['targets']*=10
    if mutation=='creation': p['targets'][0]['identity']['creation']='0000000000000000'
    if mutation=='image': p['targets'][0]['provenance']['image_sha256']=''
    if mutation=='range': p['targets'][0]['size']='65540'
    if mutation=='owned': p['targets'][0]['owned']=False
    if mutation=='b_scope': p['targets'][0]['identity']['designation']='B'
    if mutation=='approval': p['approval_sha256']='invalid'
    if mutation=='peer':
        seal=Broker.provision(tmp_path/'authority',p)
        with pytest.raises(QSGError,match='PEER'):
            Broker(tmp_path/'authority',seal,clock_ms=lambda:0,peer={**p['peer'],'creation':'0000000100000002'},enabled=True)
    else:
        with pytest.raises(Exception): Broker.provision(tmp_path/'authority',p)


@pytest.mark.parametrize('fault',['gap','changed','counter','capacity'])
def test_recorder_history_fault_cancels_before_reserve(tmp_path,fault):
    m=Model(tmp_path); m.start(); m.until('WRITING')
    original=m.host.recorder.capture
    def capture(s,r,p,a):
        if fault=='capacity': m.recorder.maximum=1
        snap=plain(s)
        if fault=='gap': snap['dropped_events']=1
        if fault=='changed': snap['events'][0]['state_after']='MONITORING'
        if fault=='counter': snap['counters']['adapter_read_calls']=0
        return m.recorder.capture(snap,r,p,plain(a))
    m.host.recorder.capture=m.wrap(capture)
    m.w.step(20)
    assert not m.api.status().running and not m.raw_calls and not m.broker.events('reserve')
    m.close()


def test_l10_second_start_zero_match_and_late_callbacks_do_not_reset_budget(tmp_path):
    m=Model(tmp_path,phase='L10'); m.w.cfg.diagnostics.cleanup_start_probe=True
    assert m.start(loader=True)==(True,None); m.until('MONITORING')
    callback=m.w.timers[1].OnTimer; m.stop(); before=len(m.raw_calls)
    p=layout.plan('zero_match'); m.w.use_layout(table(m.lua,p['pages']),table(m.lua,p['words']))
    m.target.memory.write_word(0x100128,0x42280000)
    m.w.cfg.diagnostics.session_token='SYNTHETIC-second'; m.w.cfg.diagnostics.cleanup_start_probe=False
    assert m.api.start()==(True,None)
    callback(); m.w.step(50); m.stop(); m.w.step(60)
    assert len(m.raw_calls)==before==len(m.broker.events('reserve'))==1
    assert len(m.broker.events('start'))==2
    m.close()


@pytest.mark.parametrize('backend',['lua53','lua54'])
def test_l11_target_switch_has_no_subsequent_mock_memory_access(tmp_path,backend):
    p=policy(); destination=deepcopy(p['targets'][0]); destination['identity']['designation']='B'
    destination['identity']['pid']=102; destination['identity']['creation']='000000010000005C'
    destination['allocation_id']='destination-allocation'; destination['phases']=['L11']; p['targets'].append(destination)
    m=Model(tmp_path,backend,phase='L11',mode='zero_match',policy_value=p)
    m.start(); m.until('RESCAN_BACKOFF')
    before=(int(m.w.reads),len(m.w.scans),len(m.raw_calls))
    m.w.opened=102; m.w.step()
    assert m.api.status().stop_reason=='CE_TARGET_CHANGED'
    assert (int(m.w.reads),len(m.w.scans),len(m.raw_calls))==before
    m.close()


def test_l08_target_exit_revokes_stale_callback(tmp_path):
    m=Model(tmp_path); m.start(); m.until('MONITORING'); callback=m.w.timers[1].OnTimer
    m.w.alive=False; m.w.step(); callback()
    assert m.api.status().stop_reason in {'PID_EXITED','PID_EXITED_OR_UNCERTAIN'} and len(m.raw_calls)==1
    m.close()


def test_successful_start_limit_and_session_expiry_persist(tmp_path):
    m=Model(tmp_path,phase='L09',mode='zero_match')
    for n in range(9):
        m.w.cfg.diagnostics.session_token=f'SYNTHETIC-start-{n}'
        m.start(); m.w.step(); m.stop()
    with pytest.raises(Exception): m.start()
    assert len(m.broker.events('start'))==9 and not m.raw_calls
    m.close()


def test_session_expiry_before_start_and_three_alive_targets_refuse(tmp_path):
    m=Model(tmp_path); m.w.time=3600000
    with pytest.raises(Exception): m.start()
    assert not m.raw_calls
    m.close()
    other=tmp_path/'other'; other.mkdir()
    m=Model(other); m.scope_override=m.current_scope(); m.scope_override['alive_instances']=3
    with pytest.raises(Exception): m.start()
    assert not m.raw_calls and not list(m.w.native_calls.values())
    m.close()


def test_concurrent_reservation_of_same_operation_spends_at_most_once(tmp_path):
    m=Model(tmp_path); m.start(); m.until('MONITORING')
    request=deepcopy(m.broker.events('reserve')[0]['data'])
    barrier=threading.Barrier(3); results=[]
    def worker():
        barrier.wait()
        try: m.broker.reserve(request); results.append('grant')
        except Exception: results.append('denied')
    a=threading.Thread(target=worker); b=threading.Thread(target=worker); a.start(); b.start(); barrier.wait(); a.join(5); b.join(5)
    assert results==['denied','denied'] and len(m.broker.events('reserve'))==1 and len(m.raw_calls)==1
    m.close()


def test_zero_scan_route_later_candidate_still_uses_guard(tmp_path):
    m=Model(tmp_path,mode='zero_match'); m.start(); m.until('RESCAN_BACKOFF')
    assert not m.raw_calls and not m.broker.events('reserve')
    # A new slot in the same owned allocation appears after the empty scan.
    p=layout.plan('relocate',1); m.target.apply(p); m.w.use_layout(table(m.lua,p['pages']),table(m.lua,p['words']))
    m.until('MONITORING')
    assert len(m.raw_calls)==len(m.broker.events('reserve'))==1
    m.close()


@pytest.mark.parametrize('field',['phase_sequence','lease.generation','lease.target','candidate.qualified_count','candidate.population_sequence'])
def test_boolean_does_not_impersonate_integer_in_write_request(tmp_path,field):
    m=Model(tmp_path); m.start(); m.until('WRITING')
    def hook(stage,packet):
        if stage!='before_dispatch' or packet['message_type']!='reserve': return
        d=packet['body']
        if '.' in field:
            parent,key=field.split('.'); d[parent][key]=False if key=='target' else True
        else: d[field]=True
    m.channel.hook=hook; m.w.step(10)
    assert not m.raw_calls and not m.broker.events('reserve')
    m.close()
