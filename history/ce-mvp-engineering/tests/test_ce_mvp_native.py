"""Standard ID1 pipeline with real Lua/scoring and deterministic CE API doubles."""
import xml.etree.ElementTree as ET

import pytest

from prepare_ce_mvp import prepare
from test_h3_a7_ce_mvp import make_runtime, portable_source, process_population, process_scope


@pytest.fixture(params=["lua53", "lua54"])
def native(request):
    lua, w = make_runtime(request.param)
    process_scope(w)
    w.cfg.scan.scan_budget = 2000
    w.cfg.scan.max_candidates = 20
    lua.execute("""
      w.start=function()
        w.adapter=w.adapter_module.new_native(w.core.validate(w.cfg),w.ce,w.load)
        w.loop=w.core.new(w.cfg,w.adapter,nil,'NATIVE_MAINTAIN')
        return w.loop.start()
      end
    """)
    yield lua, w
    if w.loop:
        w.loop.stop()
    w.clean()


def monitoring(w):
    obj = w.object(0x100128)
    assert w.start() is True
    w.until_state("MONITORING")
    return obj


def test_full_pool_exceeds_both_original_budgets_and_selects_last_candidate(native):
    lua, w = native
    process_population(lua, w, 2101, (2101,))
    # Native mode consumes all records even with deliberately tiny old budgets.
    w.cfg.scan.scan_budget = 2
    w.cfg.scan.max_candidates = 1
    w.start(); w.until_state("MONITORING")
    s, e = w.loop.status(), w.loop.evaluation()
    assert s.raw_match_count == s.raw_inspected_count == s.raw_admitted_count == 2101
    assert e.counts.supplied == e.counts.fully_scored == e.counts.ranked == 2101
    assert s.ranked_count == 2101 and s.coverage == "full_population"
    assert e.population_complete and s.acquisition_complete
    assert s.raw_admission_budget is None and s.ranking_budget is None
    assert w.writes[1].addr == w.objects[2101].addr == e.result.best.candidate.value_addr
    assert s.write_admission_basis == "FULL_POOL_RANK1_HARD_PASS"
    assert not s.global_uniqueness_proven


def test_review_rank_one_is_written_without_changing_scoring(native):
    lua, w = native
    process_population(lua, w, 2, (1, 2))
    w.start(); w.until_state("MONITORING")
    result = w.loop.evaluation().result
    assert result.recommendation.recommendation == "REVIEW"
    assert result.best.hard_pass and result.recommendation.manual_review_required
    assert len(w.writes) == 1 and w.writes[1].addr == result.best.candidate.value_addr


def test_rejected_ranking_never_writes(native):
    _, w = native
    w.object(0x100128, "weak")
    w.start(); w.until_state("ERROR")
    assert w.loop.evaluation().result.recommendation.recommendation == 'REJECT'
    assert "CANDIDATE_NOT_QUALIFIED" in w.loop.status().stop_reason
    assert len(w.writes) == 0


def test_mapping_exclusions_still_enter_complete_population(native):
    _, w = native
    edge = w.object(0x10000)
    edge.kind = 0x1000000
    w.object(0x100128)
    w.start(); w.until_state("MONITORING")
    s, e = w.loop.status(), w.loop.evaluation()
    assert s.raw_match_count == s.raw_inspected_count == s.raw_admitted_count == 2
    assert e.counts.supplied == e.counts.distinct == 2
    assert e.counts.excluded == 1 and e.counts.ranked == 1
    assert s.acquisition_complete and s.collection_complete
    assert len(w.writes) == 1 and w.writes[1].addr == 0x100128


def test_periodic_rewrites_use_config_interval_and_exact_float32(native):
    _, w = native
    w.cfg.monitor_interval_ms = 1000
    obj = monitoring(w)
    initial = w.writes[1].time
    obj.memory[obj.addr] = 0x42C80000  # 100 < 125
    w.step(19)
    assert w.time == initial + 950 and len(w.writes) == 1
    w.step(1)
    assert w.loop.status().state == "WRITING" and len(w.writes) == 1
    w.step(1)
    assert len(w.writes) == 2 and obj.memory[obj.addr] == 0x42FA0000
    obj.memory[obj.addr] = 0x42280000  # 42 < 125: repeat the same selected address
    w.step(21)
    assert len(w.writes) == 3 and w.loop.status().rewrite_count == 2
    assert len(w.scans) == w.open_calls == 1
    assert all(row.addr == obj.addr and row.value == 125 for row in w.writes.values())
    assert w.loop.status().readback_status == "VERIFIED"


@pytest.mark.parametrize("bits", [0x42FA0000, 0x43160000])  # equal (125), above (150)
def test_equal_or_higher_value_is_not_overwritten(native, bits):
    _, w = native
    obj = monitoring(w); obj.memory[obj.addr] = bits
    w.step(20)
    assert len(w.writes) == 1 and obj.memory[obj.addr] == bits
    assert w.loop.status().last_observed_bits == bits


@pytest.mark.parametrize("bits", [0x42FA0000, 0x43160000])
def test_recovery_between_check_and_rewrite_is_respected(native, bits):
    _, w = native
    obj = monitoring(w); obj.memory[obj.addr] = 0x42280000
    w.until_state("WRITING")
    obj.memory[obj.addr] = bits
    w.step(1)
    assert len(w.writes) == 1 and w.loop.status().state == "MONITORING"


@pytest.mark.parametrize("fault", ["unreadable", "unmapped", "nan", "infinite", "structure", "pid", "exit"])
def test_first_invalid_observation_stops_all_later_writes(native, fault):
    _, w = native
    obj = monitoring(w)
    if fault == "unreadable": obj.readable = False
    elif fault == "unmapped": obj.mapped = False
    elif fault == "nan": obj.memory[obj.addr] = 0x7FC00000
    elif fault == "infinite": obj.memory[obj.addr] = 0x7F800000
    elif fault == "structure": obj.memory[obj.addr + 0x30] = 8
    elif fault == "pid": w.opened = 999
    else: w.alive = False
    w.until_state("ERROR")
    s = w.loop.status()
    assert not s.running and s.cleanup_ok and s.rescan_attempts == 0
    assert s.invalid_count <= 1 and len(w.writes) == len(w.scans) == 1
    before = w.reads
    obj.readable = obj.mapped = w.alive = True; w.opened = w.pid
    w.step(100)
    assert w.reads == before and len(w.writes) == len(w.scans) == 1


def test_unreadable_after_monitor_but_before_rewrite_never_writes(native):
    _, w = native
    obj = monitoring(w); obj.memory[obj.addr] = 0x42280000
    w.until_state("WRITING"); obj.readable = False
    w.until_state("ERROR")
    assert w.loop.status().stop_reason == "ADDRESS_UNREADABLE" and len(w.writes) == 1


def test_question_marks_float_read_stops_without_a_rewrite(native):
    _, w = native
    monitoring(w); w.fail.readback_float = '???'
    w.until_state('ERROR'); w.step(50)
    assert w.loop.status().stop_reason == 'ADDRESS_UNREADABLE' and len(w.writes) == 1


def test_operator_stop_cancels_pending_rewrite(native):
    _, w = native
    obj = monitoring(w); obj.memory[obj.addr] = 0x42280000
    w.until_state('WRITING'); w.loop.stop(); w.step(50)
    assert w.loop.status().stop_reason == 'OPERATOR_STOP' and len(w.writes) == 1


@pytest.mark.parametrize("fault,reason", [("write_nil", "WRITE_FAILED"), ("write_no_change", "READBACK_MISMATCH")])
def test_failed_rewrite_stops_instead_of_retrying(native, fault, reason):
    _, w = native
    obj = monitoring(w); obj.memory[obj.addr] = 0x42280000
    w.fail[fault] = True
    w.until_state("ERROR"); w.step(50)
    assert w.loop.status().stop_reason == reason
    assert len(w.writes) == 2 and len(w.scans) == 1


def test_stop_during_full_scoring_cancels_without_publishing_partial_result(native):
    lua, w = native
    process_population(lua, w, 300, (300,))
    w.cfg.scan.collection_batch_size = 16
    w.start()
    while (w.loop.status().raw_inspected_count or 0) < 30:
        w.step()
    w.loop.stop(); w.step(100)
    assert w.loop.evaluation() is None and not w.loop.status().acquisition_complete
    assert len(w.writes) == 0


@pytest.mark.parametrize('configured_pid', [20560, 45678])
def test_prepared_standard_id1_loads_original_config_and_runs_native_pipeline(tmp_path, configured_pid):
    lua, w = make_runtime("lua53")
    w.pid = configured_pid
    source = portable_source(tmp_path)
    path = prepare(source)
    config = source / "ce_mvp_config.local.lua"
    template = (source / "ce_mvp_config.example.lua").read_text(encoding="utf-8")
    config.write_text("local c=(function()\n" + template + "\nend)(); "
                      f"c.target_pid={configured_pid};c.write_enabled=true;return c", encoding="utf-8")
    before = config.read_bytes()
    lua.execute("for k,v in pairs(w.ce) do _G[k]=v end")
    obj = w.object(0x100128)
    script = ET.parse(path).find(".//AssemblerScript").text
    enable, disable = script.split("[DISABLE]")
    start = enable.split("{$lua}")[1].split("{$asm}")[0]
    stop = disable.split("{$lua}")[1].split("{$asm}")[0]
    lua.globals().syntaxcheck = True; lua.execute(start)
    assert w.open_calls == w.active_timers == 0
    lua.globals().syntaxcheck = False; lua.execute(start)
    api = lua.globals().H3A7_CE_MVP
    w.loop = api
    try:
        w.until_state("MONITORING")
        s = api.status()
        assert s.input_source == "CONFIGURED_TARGET" and s.product_profile == "CE_NATIVE_FULL"
        assert s.lifecycle_policy == "NATIVE_MAINTAIN" and s.maintain_value
        assert s.data_provenance == "CE_NATIVE" and s.acquisition_complete
        assert s.pid == configured_pid and s.candidate_address == obj.addr
        assert s.native_operation_status == "API_SUCCEEDED" and s.native_readback_status == "VERIFIED"
        assert api.controlled_fixture() is None and config.read_bytes() == before
        obj.memory[obj.addr] = 0x42280000
        w.step(21)
        assert len(w.writes) == 2
        lua.execute(stop); w.step(100)
        assert len(w.writes) == 2 and api.status().stop_reason == "OPERATOR_STOP"
        # A deliberate new Start reads a different PID without a new table,
        # construction-mode selection, synthetic selector or source edit.
        w.pid = configured_pid + 1
        config.write_text(config.read_text(encoding='utf-8').replace(
            f'c.target_pid={configured_pid};', f'c.target_pid={configured_pid + 1};'), encoding='utf-8')
        obj.memory[obj.addr] = 0x42C80000
        lua.execute(start); w.until_state('MONITORING')
        assert api.status().pid == configured_pid + 1 and w.open_calls == 2
        assert len(w.writes) == 3
    finally:
        api.stop(); w.clean()
