"""Existing QSG/table facilities only; no CE/native qualification or target access.

The real default ID1 refusal is tested in test_ce_mvp_readonly. These tests
exercise the shared acquisition/full-evaluation integration behind that gate;
they cannot establish a successful native standard product run.
"""
import pytest

from qsg_support import Model
from support import ROOT, SOURCES, plain


@pytest.fixture
def model(tmp_path, monkeypatch):
    monkeypatch.setitem(SOURCES, "mvp0_offline_scoring.lua",
                        (ROOT / "src/mvp0_offline_scoring.lua").read_text(encoding="utf-8"))
    m = Model(tmp_path)
    # The existing independent bytearray and CE tables contain identical words.
    for address in (0x100328, 0x100528):
        m.w.locate(address).memory[address] = 0x42C80000
        m.target.memory.write_word(address, 0x42C80000)
    yield m
    m.close()


def start_full(m):
    cfg = m.w.core.validate(m.w.cfg)
    m.run = m.factory.prepare_start(cfg)
    m.w.adapter = m.w.adapter_module.new(cfg, m.w.ce, m.w.load, "synthetic", m.run, "full")
    m.w.loop = m.w.core.new(m.w.cfg, m.w.adapter, None, "ALPHA_STOP_ONLY")
    m.run.bind_core(m.w.loop)
    m.api = m.w.loop
    assert m.api.start() is True


def test_existing_acquisition_full_scoring_guarded_operation_and_stop(model):
    m = model
    start_full(m); m.until("MONITORING")
    s, e = m.api.status(), m.api.evaluation()
    assert e.status == "COMPLETE" and e.population_mode == "full" and e.population_complete
    assert plain(e.counts) == dict(supplied=3, distinct=3, duplicates=0, eligible=3,
                                  excluded=0, selected=3, fully_scored=3, ranked=3)
    expected = {0x100128, 0x100328, 0x100528}
    assert set(e.identities.eligible.values()) == expected
    assert {r.candidate.value_addr for r in e.result.ranked.values()} == expected
    assert s.raw_inspected_count == 3 and s.identity_reconciled
    assert not s.acquisition_complete
    assert s.decision_scope == "QSG_FULL_POPULATION" and s.data_provenance == "synthetic"
    assert s.acquisition_evidence == "SYNTHETIC_SCAN_OBSERVATIONS_ONLY"
    assert (s.operation_status, s.readback_status) == ("API_SUCCEEDED", "VERIFIED")
    assert len(m.raw_calls) == len(m.broker.events("reserve")) == len(m.broker.events("claim")) == 1
    before = (m.w.reads, len(m.raw_calls), len(m.w.scans), m.w.open_calls)
    for _ in range(3): m.api.status(); m.api.evaluation()
    assert before == (m.w.reads, len(m.raw_calls), len(m.w.scans), m.w.open_calls)
    m.w.objects[1].mapped = False
    m.w.step(40)
    assert m.api.status().stop_reason == "ALPHA_STOP:MAPPING_CHANGED"
    assert m.api.status().cleanup_ok and m.api.status().rescan_attempts == 0
    before = (m.w.reads, len(m.raw_calls), len(m.w.scans), m.w.open_calls)
    m.w.step(100)
    assert before == (m.w.reads, len(m.raw_calls), len(m.w.scans), m.w.open_calls)


@pytest.mark.parametrize("fault,reason", [
    ("progress", "SCAN_COMPLETION_UNCERTAIN"),
    ("read", "SCREENING_READ_FAILED"),
    ("source_changed", "FOUNDLIST_ADDRESS_CHANGED"),
    ("incomplete", "OFFLINE_INCOMPLETE_RESULT"),
    ("identity_substitution", "OFFLINE_INCOMPLETE_RESULT"),
])
def test_acquisition_and_evaluation_failure_never_publish_or_operate(model, fault, reason):
    m = model
    if fault == "progress": m.w.fail.progress = True
    elif fault == "read": m.w.fail.unreadable = 0x100108
    else:
        m.lua.globals().product_fault = fault
        m.lua.execute("""
          local load=w.load
          w.load=function(name,env)
            local module=load(name,env)
            if name=='mvp0_offline_scoring.lua' then
              local run=module.run
              module.run=function(...)
                local e=run(...)
                if product_fault=='source_changed' then w.latest_foundlist.Address[0]='100928'
                elseif product_fault=='incomplete' then e.completed=false
                else e.identities.supplied[1]=0x100928 end
                return e
              end
            end
            return module
          end
        """)
    start_full(m); m.w.step(100)
    assert reason in m.api.status().stop_reason
    assert m.api.evaluation() is None and not m.api.status().evaluation_completed
    assert len(m.raw_calls) == len(m.broker.events("reserve")) == 0
    assert m.api.status().cleanup_ok


def test_full_snapshot_retains_identical_duplicates_and_exact_membership(model):
    m = model
    m.lua.execute("""
      w.hook=function(event)
        if event=='initialize' then
          w.hook=nil
          local fl=w.latest_foundlist
          fl.Address[fl.Count]=fl.Address[0]; fl.Count=fl.Count+1
          local ms=w.scans[#w.scans]; ms.addresses[#ms.addresses+1]=ms.addresses[1]
        end
      end
    """)
    start_full(m); m.w.step(100)
    e = m.api.evaluation()
    assert e is not None and e.counts.supplied == 4 and e.counts.duplicates == 1
    assert e.counts.distinct == e.counts.eligible == e.counts.ranked == 3
    assert m.api.status().raw_inspected_count == 4


def test_full_does_not_raise_original_qsg_population_limits(model):
    m = model
    for i in range(129):
        address = 0x100600 + i * 4
        m.w.locate(address).memory[address] = 0x42C80000
    start_full(m); m.w.step(100)
    assert "INCOMPLETE_CANDIDATE_POPULATION" in m.api.status().stop_reason
    assert m.api.evaluation() is None and len(m.raw_calls) == 0
    assert m.api.status().cleanup_ok


@pytest.mark.parametrize("kind", ["empty", "excluded", "review", "cancelled"])
def test_full_empty_excluded_review_and_cancelled_remain_distinct(model, kind):
    m = model
    if kind == "empty":
        for addr in (0x100128, 0x100328, 0x100528): m.w.locate(addr).memory[addr] = 0
    elif kind == "excluded":
        m.lua.execute("""
          w.hook=function(event)
            if event=='initialize' then
              w.hook=nil
              for _,addr in ipairs({0x100128,0x100328,0x100528}) do w.locate(addr).memory[addr]=0 end
            end
          end
        """)
    elif kind == "review":
        m.lua.execute("""
          local words=w.locate(0x100128).memory
          for _,offset in ipairs({-0x20,-0x10,-8,0x30,0x40,0x48,0x50}) do
            words[0x100328+offset]=words[0x100128+offset]
          end
        """)
    start_full(m)
    if kind == "cancelled":
        m.lua.execute("w.hook=function(event) if event=='read' then w.hook=nil;w.loop.stop() end end")
    m.w.step(100)
    e = m.api.evaluation()
    if kind == "cancelled":
        assert e is None and m.api.status().stop_reason == "OPERATOR_STOP"
    elif kind == "review":
        assert e.status == "COMPLETE" and e.result.recommendation.recommendation == "REVIEW"
    else:
        assert e.status == "EMPTY" and e.counts.eligible == e.counts.ranked == 0
        assert e.counts.excluded == e.counts.supplied == (3 if kind == "excluded" else 0)
    assert len(m.raw_calls) == len(m.broker.events("reserve")) == 0
    assert not m.api.status().running and m.api.status().cleanup_ok
