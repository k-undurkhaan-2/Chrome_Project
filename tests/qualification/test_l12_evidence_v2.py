"""Offline LP-R1 boundaries, independently read sidecars and adversarial closure."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from ce_qualification import evidence
from ce_qualification.evidence import (BLOB_LIMIT, EvidenceError, SidecarStore, Stream,
    canonical, export_bundle)
from ce_qualification.recorder import CERecorder, GUARD_NAMES
from ce_qualification.verifier import load_bundle, load_sidecars, l12_payload
from native_probe_b1_boundary import boundary_measurements
from support import ROOT, SOURCES, world


def observation(path, scenario='L12-MISSING'):
    path_bytes = path.encode('utf-8')
    loader = b'cannot open ' + path_bytes + b': No such file or directory'
    full = (b'SYNTHETIC/ce_mvp.lua:41: ' + loader if scenario == 'L12-MISSING'
            else b'WRITE_DISABLED' if scenario == 'L12-DISABLED' else b'INVALID_SCAN_SETTINGS')
    return {'schema':'ce.loader-diagnostic.v2','origin':'SYNTHETIC','source':'g1_mock_loader',
            'path_utf8_hex':path_bytes.hex(),'loader_error_hex':loader.hex() if scenario=='L12-MISSING' else False,
            'loader_return_arity':2 if scenario=='L12-MISSING' else 0,'full_error_hex':full.hex(),
            'returned_error_hex':full[:240].hex(),'full_error_source':'PCALL_ERROR',
            'return_arity':2,'truncation_bytes':240}


def make_case(tmp_path, *, scenario='L12-MISSING', after=None, obs=None):
    store = SidecarStore(tmp_path/'sidecars', 'SYNTHETIC-LP')
    stream = Stream('SYNTHETIC-LP', 'ce')
    obs = obs or observation('D:\\synthetic\\' + 'x'*180 + '\\配置e\u0301🙂\\ce_mvp_config.local.lua', scenario)
    before = {'enabled':False,'reason':'NO_RUN','preserved':'x'*32400}
    CERecorder(stream, enabled=True).rejection(run_id='rejected-'+scenario,scenario=scenario,accepted=False,
        diagnostic=bytes.fromhex(obs['returned_error_hex']),diagnostic_observation=obs,sidecars=store,
        guard_before=dict.fromkeys(GUARD_NAMES,0),guard_after=dict.fromkeys(GUARD_NAMES,0),restored=True,
        retained_before=before,retained_after=before if after is None else after)
    return stream, store, store.seal(stream.rows)


def rewrite_manifest(store, edit):
    path = store.root/'sidecars.json'
    manifest = json.loads(path.read_bytes()); edit(manifest)
    raw = canonical(manifest); path.write_bytes(raw)
    return {'schema':2,'bundle_id':manifest['bundle_id'],'sha256':hashlib.sha256(raw).hexdigest(),'byte_length':len(raw)}


def test_lp05_direct_body_precheck_before_copy_clock_or_publication(monkeypatch):
    for size in (65535,65536):
        data={'payload':''}; data['payload']='x'*(size-len(canonical(data)))
        stream=Stream('boundary','ce'); row=stream.emit('boundary',data)
        assert len(canonical(row['data']))==size and len(stream.rows)==1
    stream=Stream('boundary','ce'); data={'payload':'x'*(65537-len(canonical({'payload':''})))}
    monkeypatch.setattr(evidence,'deepcopy',lambda *_:pytest.fail('copied overbound body'))
    monkeypatch.setattr(stream.clock,'sample',lambda:pytest.fail('sampled clock for rejected body'))
    with pytest.raises(EvidenceError,match='PAYLOAD_BOUND'): stream.emit('boundary',data)
    assert not stream.rows


def test_lp05_wire_body_bound_remains_independent(tmp_path):
    for row in boundary_measurements(tmp_path):
        assert row['evidence_result']==('PAYLOAD_BOUND' if row['payload_utf8_bytes']==65537 else 'ACCEPTED')
        assert row['transport_result']==('FRAME_LENGTH' if row['payload_utf8_bytes']==65537 else 'ACCEPTED')
        assert not row['oversize_header_body_allocated']


@pytest.mark.parametrize('scenario',['L12-MISSING','L12-DISABLED','L12-INVALID'])
def test_lp07_distinct_negative_scenarios_and_deduplicated_roles(tmp_path,scenario):
    stream,store,seal=make_case(tmp_path,scenario=scenario)
    row=stream.rows[0]; d=row['data']; result=load_sidecars(stream.rows,seal,store.root)[row['event_id']]
    assert d['retained_before']==d['retained_after'] and len(store.entries)==2
    assert result['retained_before']==result['retained_after']
    assert len(canonical(d))<2000 and row['origin']=='SYNTHETIC'
    assert result['accepted'] is False and all(v==0 for v in result['guard_after'].values())


def test_lp06_verifier_compares_actual_independent_retained_roles(tmp_path):
    stream,store,seal=make_case(tmp_path,after={'enabled':False,'reason':'CHANGED'})
    assert stream.rows[0]['data']['retained_before']!=stream.rows[0]['data']['retained_after']
    with pytest.raises(EvidenceError,match='RETAINED_EVIDENCE_CHANGED'): load_sidecars(stream.rows,seal,store.root)


@pytest.mark.parametrize('path',[
    'D:\\a\\b\\ce_mvp_config.local.lua', 'D:/a/b/ce_mvp_config.local.lua',
    '\\\\?\\D:\\配置\\e\u0301\\ce_mvp_config.local.lua',
    '\\\\host\\share\\quoted"\\ce_mvp_config.local.lua',
    'D:\\'+('路e\u0301🙂'*70)+'\\ce_mvp_config.local.lua'])
def test_lp04_exact_unicode_and_escaped_path_bytes(tmp_path,path):
    obs=observation(path); stream,store,seal=make_case(tmp_path,obs=obs)
    load_sidecars(stream.rows,seal,store.root)
    blob=store.root/(stream.rows[0]['data']['diagnostic']['sha256']+'.json')
    assert json.loads(blob.read_bytes())==obs
    assert bytes.fromhex(obs['path_utf8_hex'])==path.encode('utf-8')


def test_lp04_product_return_may_end_inside_utf8_codepoint(tmp_path):
    prefix='SYNTHETIC/ce_mvp.lua:41: cannot open D:\\'
    path='D:\\'+'x'*(239-len(prefix.encode()))+'🙂\\ce_mvp_config.local.lua'
    obs=observation(path)
    with pytest.raises(UnicodeDecodeError): bytes.fromhex(obs['returned_error_hex']).decode('utf-8')
    stream,store,seal=make_case(tmp_path,obs=obs)
    assert load_sidecars(stream.rows,seal,store.root)


@pytest.mark.parametrize('mutation',['missing','changed','truncated','oversize','extra','partial','noncanonical','wrong_hash'])
def test_lp06_missing_corrupt_stale_and_unbounded_files_rejected(tmp_path,mutation):
    stream,store,seal=make_case(tmp_path)
    path=store.root/(stream.rows[0]['data']['retained_before']['sha256']+'.json')
    if mutation=='missing': path.unlink()
    elif mutation=='changed': path.write_bytes(b'{}')
    elif mutation=='truncated': path.write_bytes(path.read_bytes()[:-1])
    elif mutation=='oversize': path.write_bytes(b'x'*(BLOB_LIMIT+1))
    elif mutation=='extra': (store.root/('0'*64+'.json')).write_bytes(b'{}')
    elif mutation=='partial': (store.root/'write.pending').write_bytes(b'{')
    elif mutation=='noncanonical': path.write_bytes(b' '+path.read_bytes())
    elif mutation=='wrong_hash': seal['sha256']='0'*64
    with pytest.raises((EvidenceError,OSError)): load_sidecars(stream.rows,seal,store.root)


@pytest.mark.parametrize('mutation',['duplicate','traversal','absolute','type','bytes','version','extra_binding','replay','manifest_oversize','count','total'])
def test_lp06_resealed_manifest_still_requires_exact_closure(tmp_path,mutation):
    stream,store,seal=make_case(tmp_path)
    def edit(m):
        if mutation=='duplicate': m['artifacts'].append(deepcopy(m['artifacts'][0]))
        elif mutation in ('traversal','absolute'): m['artifacts'][0]['artifact_id']='../outside.json' if mutation=='traversal' else 'D:\\outside.json'
        elif mutation=='type': m['artifacts'][0]['normalized_type']='executable'
        elif mutation=='bytes': m['artifacts'][0]['byte_length']+=1
        elif mutation=='version': m['artifacts'][0]['evidence_schema_version']=True
        elif mutation=='extra_binding': m['bindings'].append(deepcopy(m['bindings'][0]))
        elif mutation=='replay': m['bindings'][0]['run_id']='different-run'
        elif mutation=='manifest_oversize': m['unexpected']='x'*65536
        elif mutation in ('count','total'):
            m['artifacts']=[{**m['artifacts'][0],'artifact_id':'sha256:'+f'{i:064x}', 'sha256':f'{i:064x}',
                'byte_length':BLOB_LIMIT} for i in range(33 if mutation=='count' else 9)]
    seal=rewrite_manifest(store,edit)
    with pytest.raises(EvidenceError): load_sidecars(stream.rows,seal,store.root)


@pytest.mark.parametrize('field',['path_utf8_hex','returned_error_hex','full_error_hex','loader_error_hex','return_arity','origin'])
def test_lp06_resealed_raw_diagnostic_contradictions_rejected(tmp_path,field):
    obs=observation('D:\\synthetic\\ce_mvp_config.local.lua')
    obs[field] = 3 if field=='return_arity' else 'CE_LIVE' if field=='origin' else b'wrong'.hex()
    stream,store,seal=make_case(tmp_path,obs=obs)
    with pytest.raises(EvidenceError): load_sidecars(stream.rows,seal,store.root)


def test_lp06_cross_bundle_replay_and_missing_seal_rejected(tmp_path):
    one=tmp_path/'one'; two=tmp_path/'two'; one.mkdir(); two.mkdir()
    stream,store,seal=make_case(one); stream2,store2,seal2=make_case(two)
    with pytest.raises(EvidenceError): load_sidecars(stream.rows,seal2,store2.root)
    with pytest.raises(EvidenceError): load_sidecars(stream.rows,None,store.root)
    with pytest.raises(EvidenceError): load_sidecars(stream2.rows,seal,store.root)


def test_lp06_symlink_or_windows_reparse_substitution_rejected(tmp_path,monkeypatch):
    stream,store,seal=make_case(tmp_path)
    path=store.root/(stream.rows[0]['data']['retained_before']['sha256']+'.json')
    outside=tmp_path/'outside.json'; outside.write_bytes(path.read_bytes()); path.unlink()
    try:
        path.symlink_to(outside)
    except OSError:
        # Without Windows symlink privilege inject a reparse observation.
        path.write_bytes(outside.read_bytes())
        original=Path.lstat
        def lstat(p,*a,**kw):
            info=original(p,*a,**kw)
            if p==path:
                return SimpleNamespace(st_mode=info.st_mode,st_nlink=1,st_size=info.st_size,st_file_attributes=0x400)
            return info
        monkeypatch.setattr(Path,'lstat',lstat)
    with pytest.raises(EvidenceError,match='LINK'): load_sidecars(stream.rows,seal,store.root)


def test_lp06_hardlink_substitution_rejected(tmp_path):
    stream,store,seal=make_case(tmp_path)
    path=store.root/(stream.rows[0]['data']['retained_before']['sha256']+'.json')
    os.link(path,tmp_path/'alias.json')
    with pytest.raises(EvidenceError,match='LINK'): load_sidecars(stream.rows,seal,store.root)


def test_lp06_linked_root_and_read_time_replacement_rejected(tmp_path,monkeypatch):
    stream,store,seal=make_case(tmp_path)
    original=evidence.directory_stamp; calls=[]
    def stamp(p):
        calls.append(p); value=original(p)
        return value if len(calls)%2 else (*value,(999,999))
    monkeypatch.setattr(evidence,'directory_stamp',stamp)
    with pytest.raises(EvidenceError,match='REPLACED'): load_sidecars(stream.rows,seal,store.root)


def test_lp06_bounded_writer_never_reuses_partial_or_sealed_files(tmp_path):
    stream,store,seal=make_case(tmp_path)
    with pytest.raises(EvidenceError,match='ALREADY_SEALED'): store.put({},'retained_snapshot')
    with pytest.raises(FileExistsError): SidecarStore(store.root,'SYNTHETIC-LP')
    extra=SidecarStore(tmp_path/'extra','SYNTHETIC-LP')
    with pytest.raises(EvidenceError,match='BLOB_BOUND'): extra.put({'x':'x'*BLOB_LIMIT},'retained_snapshot')
    for i in range(32): extra.put({'i':i},'retained_snapshot')
    with pytest.raises(EvidenceError,match='BUNDLE_BOUND'): extra.put({'i':32},'retained_snapshot')
    assert len(list(extra.root.iterdir()))==32


def test_lp03_legacy_call_and_manifest_remain_accepted(tmp_path):
    stream=Stream('legacy','ce')
    row=CERecorder(stream,enabled=True).rejection(run_id='old',scenario='L12-DISABLED',accepted=False,
        diagnostic='WRITE_DISABLED',guard_before=dict.fromkeys(GUARD_NAMES,0),guard_after=dict.fromkeys(GUARD_NAMES,0),
        restored=True,retained_before={},retained_after={})
    assert 'evidence_schema_version' not in row['data'] and l12_payload(row)['diagnostic']=='WRITE_DISABLED'
    manifest,seal=export_bundle(tmp_path/'legacy',{'ce':stream.rows})
    assert load_bundle(manifest,seal)=={'ce':stream.rows}


def test_lp10_versioned_export_binds_actual_sidecars(tmp_path):
    stream,store,seal=make_case(tmp_path)
    manifest,external_seal=export_bundle(tmp_path/'export',{'ce':stream.rows},sidecars=store)
    assert load_bundle(manifest,external_seal)=={'ce':stream.rows}
    (manifest.parent/'sidecars'/'unmanifested').write_bytes(b'{}')
    with pytest.raises(EvidenceError): load_bundle(manifest,external_seal)


@pytest.mark.parametrize('opt_in',[False,True])
def test_lp03_mock_capture_preserves_loader_and_product_return_arity(tmp_path,opt_in):
    lua,w=world('lua53'); w.config_missing=True; w.capture_loader_diagnostics=opt_in
    factory=lua.execute((ROOT/'tests/fixtures/qualification/g1_mock_loader.lua').read_text())
    api,env=factory(w,lua.table_from(SOURCES),str(tmp_path/'ce_mvp_config.local.lua'))
    assert api.configure_execution(lua.table_from({'mode':'ENGINEERING_BOUNDED'})) is True
    result=lua.eval("function(api) local r=table.pack(api.start()); return r.n,r[1],#r[2] end")(api)
    assert result[0:2]==(2,False) and result[2]<=240
    assert (w.raw_start_error is not None)==opt_in
    assert (w.loader_observation is not None)==opt_in
    if opt_in: assert w.loader_observation.return_arity==2
    assert not list(w.native_calls.values())


def test_lp06_noncanonical_manifest_and_duplicate_json_keys_rejected(tmp_path):
    stream,store,seal=make_case(tmp_path)
    path=store.root/'sidecars.json'; raw=path.read_bytes()
    for changed in [b' '+raw, raw.replace(b'"schema":"ce.sidecars.v2"', b'"schema":"ce.sidecars.v2","schema":"ce.sidecars.v2"')]:
        path.write_bytes(changed)
        ref={**seal,'sha256':hashlib.sha256(changed).hexdigest(),'byte_length':len(changed)}
        with pytest.raises(EvidenceError): load_sidecars(stream.rows,ref,store.root)


@pytest.mark.parametrize('mutation',['omitted','duplicated','run','session','role','unknown','version'])
def test_lp06_event_omission_replay_and_ambiguous_payload_rejected(tmp_path,mutation):
    stream,store,seal=make_case(tmp_path); rows=deepcopy(stream.rows)
    if mutation=='omitted': rows=[]
    elif mutation=='duplicated': rows+=deepcopy(rows)
    elif mutation=='run': rows[0]['run_id']='replayed'
    elif mutation=='session': rows[0]['session_id']='replayed'
    elif mutation=='role': rows[0]['data']['retained_before']=deepcopy(rows[0]['data']['diagnostic'])
    elif mutation=='unknown': rows[0]['data']['equal']=True
    elif mutation=='version': rows[0]['data']['evidence_schema_version']=True
    with pytest.raises(EvidenceError): load_sidecars(rows,seal,store.root)
