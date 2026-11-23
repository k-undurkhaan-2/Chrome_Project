"""Compatibility, persistence, qualification startup and independent mutations."""
from copy import deepcopy
from importlib import import_module
from pathlib import Path
import subprocess

import pytest

from ce_qualification.evidence import canonical, decode, digest
from ce_qualification.qsg_broker import Broker
from ce_qualification.qsg_protocol import MockChannel
from ce_qualification.qsg_store import QSGError
from ce_qualification.qsg_verifier import verify
from qsg_support import Model, ROOT, SOURCES, table, layout, plain, world


@pytest.mark.parametrize("backend", ["lua53","lua54"])
@pytest.mark.parametrize("mode", ["baseline_unique","zero_match","ambiguous","over_limit","incomplete_structure","invalid_structure"])
def test_normal_trace_matches_preserved_r1_bytes_without_qsg(tmp_path,backend,mode):
    traces=[]
    for baseline in (True,False):
        sources=dict(SOURCES)
        if baseline:
            for name in ("ce_mvp.lua","ce_mvp_adapter.lua"):
                sources[name]=subprocess.check_output(['git','show',
                    '33a9b33eecaf8b95b4c85b537c771c75073e538b:src/'+name],cwd=ROOT,text=True,encoding='utf-8')
        lua=import_module('lupa.'+backend).LuaRuntime(unpack_returned_tuples=True)
        factory=lua.execute((ROOT/'tests/fixtures/ce_mvp_mock.lua').read_text())
        w=factory.new(table(lua,sources))
        w.cfg.diagnostics=table(lua,{"enabled":True,"session_token":"SYNTHETIC-normal","event_limit":2048})
        p=layout.plan(mode); w.use_layout(table(lua,p['pages']),table(lua,p['words']))
        w.start(); w.step(100); w.loop.stop(); w.clean()
        # R1 changes cooperative scheduling and diagnostics, not safe outcomes.
        # Compare the same selected addresses/values and successful cleanup.
        writes=[{k:v for k,v in row.items() if k!='time'} for row in (plain(w.writes) or [])]
        traces.append({"raw":writes,"cleanup_ok":w.loop.status().cleanup_ok,
                       "scan_count":len(w.scans),"forbidden":w.forbidden})
    assert traces[0]==traces[1]


@pytest.mark.parametrize("mode,expected", [("zero_match",0),("ambiguous",2),("over_limit",129),("incomplete_structure",1),("invalid_structure",1)])
@pytest.mark.parametrize("backend", ["lua53","lua54"])
def test_qualified_l09_five_distinct_layouts_use_full_ranker(tmp_path,mode,expected,backend):
    m=Model(tmp_path,backend,phase="L09",mode=mode); m.start(); m.w.step(120)
    assert not m.raw_calls and not m.broker.events('reserve')
    populations=[e for e in plain(m.api.evidence())['events'] if e['event_type']=='scan_population']
    assert populations and populations[0]['raw_match_count']==expected
    population=populations[0]
    if population.get('native_count_limited') is False:
        assert population['raw_admission_budget']==population['ranking_budget']==128
        if mode=='over_limit': assert 'INCOMPLETE_CANDIDATE_POPULATION' in m.api.status().stop_reason
    else:
        assert population['hard_limit']==128
    if mode=='ambiguous': assert any(e.get('qualified_count')==2 for e in plain(m.api.evidence())['events'])
    if mode=='incomplete_structure': assert 'SCREENING_READ_FAILED' in m.api.status().stop_reason
    if mode=='invalid_structure': assert 'CANDIDATE_NOT_QUALIFIED' in m.api.status().stop_reason
    m.close()


def test_three_attempt_cap_across_stop_reload_host_reopen_and_repeated_start(tmp_path):
    m=Model(tmp_path); m.positive(); m.stop()
    assert len(m.broker.events('reserve'))==2
    m.broker.close()
    m.broker=Broker(tmp_path/'authority',m.seal,clock_ms=m.clock,peer=m.policy['peer'],enabled=True)
    m.channel=MockChannel(m.broker,m.policy['peer'],epoch='reload-channel')
    m.factory=m.lua.execute((ROOT/'src/qualification/qsg.lua').read_text()).new(m.host)
    p=layout.plan('relocate',2); m.target.apply(p); m.w.use_layout(table(m.lua,p['pages']),table(m.lua,p['words']))
    m.phase='L10'; m.w.cfg.diagnostics.session_token='SYNTHETIC-restart'
    m.start(); m.until('MONITORING'); m.stop()
    assert len(m.raw_calls)==len(m.broker.events('reserve'))==3
    p=layout.plan('relocate',3); m.target.apply(p); m.w.use_layout(table(m.lua,p['pages']),table(m.lua,p['words']))
    m.w.cfg.diagnostics.session_token='SYNTHETIC-exhausted'
    m.start(); m.w.step(100)
    assert not m.api.status().running and len(m.raw_calls)==3 and len(m.broker.events('reserve'))==3
    assert any('CAP' in error for _,error in m.errors)
    m.close()


def test_duplicate_reservation_claim_and_outcome_never_return_new_grant(tmp_path):
    m=Model(tmp_path); m.start(); m.until('MONITORING')
    r=m.broker.events('reserve')[0]; request=deepcopy(r['data'])
    with pytest.raises(QSGError,match='REPLAY'): m.broker.reserve(request)
    with pytest.raises(QSGError,match='REPLAY'): m.broker.claim(r['digest'],digest(request),m.lease)
    out=m.broker.events('outcome')[0]['data']
    assert m.broker.outcome(**out)=={'receipt_kind':'READ_ONLY'}
    assert len(m.broker.events('reserve'))==len(m.raw_calls)==1
    m.close()


@pytest.mark.parametrize('change',['disabled','origin','transport_version','bounded','peer','units','recorder','hash'])
def test_missing_mandatory_plugin_components_fail_before_writer_acquisition(tmp_path,change):
    m=Model(tmp_path)
    if change=='disabled': m.host.enabled=False
    if change=='origin': m.host.origin='CE_LIVE'
    if change=='transport_version': m.host.transport.version='native.pipe'
    if change=='bounded': m.host.transport.bounded=False
    if change=='peer': m.host.transport.authenticated=False
    if change=='units': m.host.transport.timeout_unit='unknown'
    if change=='recorder': m.host.recorder=None
    if change=='hash': m.host.hash=None
    with pytest.raises(Exception): m.module.new(m.host)
    assert not list(m.w.native_calls.values()) and not m.raw_calls
    m.close()


def test_invalid_factory_selection_permanently_latches_public_loader(tmp_path):
    m=Model(tmp_path)
    loader=m.lua.execute((ROOT/'tests/fixtures/qualification/g1_mock_loader.lua').read_text())
    api,env=loader(m.w,table(m.lua,SOURCES),str(tmp_path/'missing'))
    assert api.configure_execution(table(m.lua,{'mode':'QUALIFICATION'}))==(False,'QSG_PLUGIN_MISSING')
    assert api.configure_execution(table(m.lua,{'mode':'NORMAL'}))==(False,'QSG_MODE_LOCKED')
    accepted,error=api.start()
    assert accepted is False and 'QSG_PLUGIN_MISSING' in error and not m.raw_calls
    assert not list(m.w.native_calls.values())
    reload=m.lua.eval("function(s,e) return assert(load(s,'@SYNTHETIC/ce_mvp.lua','t',e))() end")(SOURCES['ce_mvp.lua'],env)
    assert reload.configure_execution(table(m.lua,{'mode':'NORMAL'}))==(False,'QSG_MODE_LOCKED')
    m.close()


@pytest.mark.parametrize('sub',['MISSING','DISABLED','INVALID'])
def test_qualified_public_l12_has_zero_guard_calls_and_retains_prior_evidence(tmp_path,sub):
    m=Model(tmp_path)
    loader=m.lua.execute((ROOT/'tests/fixtures/qualification/g1_mock_loader.lua').read_text())
    api,env=loader(m.w,table(m.lua,SOURCES),str(tmp_path/'absent/ce_mvp_config.local.lua'))
    assert api.configure_execution(table(m.lua,{'mode':'QUALIFICATION','factory':m.factory})) is True
    guard=m.lua.execute((ROOT/'tests/fixtures/ce_mvp_prestart_guard.lua').read_text()).new(env,'synthetic')
    guard.install(); before=plain(api.evidence())
    m.w.config_missing=sub=='MISSING'; m.w.cfg.write_enabled=sub!='DISABLED'; m.w.cfg.scan.scan_budget=65537 if sub=='INVALID' else 128
    accepted,error=api.start()
    assert accepted is False
    assert ('ce_mvp_config.local.lua' in error if sub=='MISSING' else error==('WRITE_DISABLED' if sub=='DISABLED' else 'INVALID_SCAN_SETTINGS'))
    assert all(v==0 for v in plain(guard.snapshot())['attempted_calls'].values())
    assert plain(api.evidence())==before and not m.broker.events('start') and not m.raw_calls
    guard.restore(); assert not guard.snapshot().installed
    m.close()


def test_stale_timer_and_direct_adapter_calls_cannot_bypass_port(tmp_path):
    m=Model(tmp_path); m.start(); m.until('MONITORING')
    callback=m.w.timers[1].OnTimer
    m.stop(); callback(); m.w.step(100)
    with pytest.raises(Exception): m.w.adapter.write_float(0x100128,125.0)
    assert len(m.raw_calls)==1
    m.close()


def test_nineteen_completed_cycles_cannot_enter_drift_phase(tmp_path):
    m=Model(tmp_path); m.start(); m.until('MONITORING'); m.phase_to('L05'); m.monitors(19)
    with pytest.raises(Exception): m.phase_to('L06')
    assert len(m.broker.events('monitor'))==19 and len(m.raw_calls)==1
    m.close()


@pytest.fixture(scope='module')
def sealed(tmp_path_factory):
    m=Model(tmp_path_factory.mktemp('qsg-sealed')); m.start(); m.until('MONITORING'); m.stop()
    bundle=m.bundle(); assert verify(bundle,digest(bundle))['status']=='SYNTHETIC_PASS'
    m.close(); return bundle


def rechain(rows,legacy=False):
    prior='0'*64
    for i,row in enumerate(rows,1):
        row['sequence']=i
        if legacy:
            row['event_id']=row['source']+':'+str(i); row['predecessor_digest']=prior
            row['content_digest']=digest({k:v for k,v in row.items() if k!='content_digest'}); prior=row['content_digest']
        else:
            row['previous']=prior; row['digest']=digest({k:v for k,v in row.items() if k!='digest'}); prior=row['digest']


@pytest.mark.parametrize('mutation',['target_bits','timestamp','operation','counts','source_hash','duplicate','gap','missing_ce','missing_target',
    'missing_broker','missing_outcome','wrong_receipt','raw_bypass','live','secret','readback','snapshot','external_anchor'])
def test_independent_verifier_detects_mutated_or_incomplete_sources(sealed,mutation):
    b=deepcopy(sealed); external=digest(b)
    if mutation=='target_bits':
        b['target'][-1]['data']['bits']='0x42C80000'; rechain(b['target'],True)
    elif mutation=='timestamp':
        b['qsg'][-1]['clock_ms']='0'; rechain(b['qsg'])
    elif mutation=='operation':
        next(r for r in b['broker'] if r['kind']=='reserve')['data']['operation_id']='0'; rechain(b['broker'])
    elif mutation=='counts': b['raw_spy']*=2
    elif mutation=='source_hash': b['qsg'][0]['digest']='a'*64
    elif mutation=='duplicate': b['qsg'].insert(1,deepcopy(b['qsg'][1]))
    elif mutation=='gap': b['ce'].pop(3)
    elif mutation=='missing_ce': b['ce']=[]
    elif mutation=='missing_target': b['target']=[]
    elif mutation=='missing_broker': b['broker']=[]
    elif mutation=='missing_outcome': b['broker']=[r for r in b['broker'] if r['kind']!='outcome']; rechain(b['broker'])
    elif mutation=='wrong_receipt':
        next(r for r in b['qsg'] if r['kind']=='RAW_DISPATCH')['body']['data']['receipt']='a'*64; rechain(b['qsg'])
    elif mutation=='raw_bypass': b['raw_spy'].append(deepcopy(b['raw_spy'][0]))
    elif mutation=='live': b['qsg'][0]['origin']='CE_LIVE'; rechain(b['qsg'])
    elif mutation=='secret': b['qsg'][0]['body']['data']['config_contents']='forbidden'; rechain(b['qsg'])
    elif mutation=='readback':
        next(r for r in b['qsg'] if r['kind']=='VERIFIED')['body']['data']['readback']['value']=42; rechain(b['qsg'])
    elif mutation=='snapshot':
        [r for r in b['ce'] if r['kind']=='ce_snapshot'][-1]['data']['counters']['write_count']=0; rechain(b['ce'],True)
    elif mutation=='external_anchor': b['qsg'][0]['body']['data']['policy_digest']='b'*64; rechain(b['qsg'])
    checked=verify(b,external if mutation=='external_anchor' else digest(b))
    assert checked['status']!='SYNTHETIC_PASS', (mutation,checked)
    assert set(checked['live'].values())=={'NOT_RUN'}


def test_verifier_has_no_controller_imports():
    import ast
    tree=ast.parse((ROOT/'src/ce_qualification/qsg_verifier.py').read_text())
    assert all((n.module or '') not in {'qsg_broker','qsg_store','qsg_recorder','budget','target'} for n in ast.walk(tree) if isinstance(n,ast.ImportFrom))


@pytest.fixture(scope='module')
def r1_l09_evidence(tmp_path_factory):
    from qsg_session import FullSession
    session=FullSession(tmp_path_factory.mktemp('r1-l09'))
    bundle=session.execute()
    result=verify(bundle,digest(bundle),requested=['L09'],sidecar_directory=session.sidecar_directory)
    assert result['status']=='SYNTHETIC_PASS',result
    directory=session.sidecar_directory
    session.close()
    return bundle,directory


@pytest.mark.parametrize('mutation',['raw_count','raw_budget','rank_budget','coverage','complete','ranked','unique'])
def test_r1_sampled_population_cannot_be_relabelled_as_unique(r1_l09_evidence,mutation):
    source,directory=r1_l09_evidence
    bundle=deepcopy(source)
    diagnostics=[r['data']['diagnostic'] for r in bundle['ce']
                 if r['kind']=='ce_event' and r['scenario']=='L09-129_plus']
    kinds={e['event_type']:e for e in diagnostics}
    if mutation=='raw_count': kinds['scan_population']['raw_match_count']=128
    if mutation=='raw_budget': kinds['scan_population']['raw_admission_budget']=129
    if mutation=='rank_budget': kinds['scan_population']['ranking_budget']=129
    if mutation=='coverage': kinds['candidate_population']['coverage']='full_population'
    if mutation=='complete': kinds['candidate_population']['collection_complete']=True
    if mutation=='ranked': kinds['candidate_population']['ranked_count']=129
    if mutation=='unique': kinds['ranking_summary']['global_uniqueness_proven']=True
    rechain(bundle['ce'],True)
    result=verify(bundle,digest(bundle),requested=['L09'],sidecar_directory=directory)
    assert result['status']!='SYNTHETIC_PASS',result
    assert set(result['live'].values())=={'NOT_RUN'}
