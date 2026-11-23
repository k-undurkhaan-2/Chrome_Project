import json

import pytest

from ce_qualification.evidence import canonical
from ce_qualification.qsg_verifier import verify
from ce_qualification.verifier import load_sidecars
from qsg_session import FullSession


@pytest.mark.parametrize('path_case', ['ordinary', 'b0_equivalent', 'long', 'unicode'])
def test_complete_session_independently_verifies_all_twelve_synthetic_cases(tmp_path, path_case):
    directory = tmp_path
    if path_case == 'b0_equivalent':
        directory = directory / 'tmp_regression_probe' / 'test_complete_session_independ0'
    elif path_case == 'long':
        directory = directory / ('long-path-' * 8)
    elif path_case == 'unicode':
        directory = directory / ('unicode-' * 5) / '配置e\u0301🙂'
    directory.mkdir(parents=True, exist_ok=True)
    session=FullSession(directory)
    bundle=session.execute()
    result=verify(bundle,session.bundle_seal,requested=[f'L{i:02}' for i in range(1,13)],
                  sidecar_directory=session.sidecar_directory)
    assert result['status']=='SYNTHETIC_PASS',result
    assert len(session.broker.events('start'))==9
    assert len(session.raw_calls)==len(session.broker.events('reserve'))==3
    assert len({r['data']['allocation_id'] for r in bundle['target'] if r['kind']=='allocation'})==9
    assert set(result['live'].values())=={'NOT_RUN'}
    assert result['g1_live']=='NOT_APPROVED'
    rejected = [r for r in bundle['ce'] if r['kind']=='config_rejected']
    assert {r['scenario'] for r in rejected}=={'L12-MISSING','L12-DISABLED','L12-INVALID'}
    resolved = load_sidecars(bundle['ce'], bundle['sidecars'], session.sidecar_directory)
    for row in rejected:
        assert len(canonical(row['data'])) <= 65536
        assert resolved[row['event_id']]['retained_before']==resolved[row['event_id']]['retained_after']
        obs = json.loads((session.sidecar_directory / (row['data']['diagnostic']['sha256']+'.json')).read_bytes())
        assert bytes.fromhex(obs['path_utf8_hex'])==str(directory/'missing/ce_mvp_config.local.lua').encode('utf-8')
        assert bytes.fromhex(obs['returned_error_hex'])==bytes.fromhex(obs['full_error_hex'])[:240]
    counts = {phase:len([r for r in session.broker.events('reserve') if r['data']['phase']==phase])
              for phase in ('L04','L07','L10')}
    assert counts=={'L04':1,'L07':1,'L10':1}
    session.close()
