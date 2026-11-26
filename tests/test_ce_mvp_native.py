"""Standalone CT tests using the original Lua ranker and CE API doubles."""
from importlib import import_module
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pytest

from prepare_ce_mvp import MODULES, lua_path, prepare

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def blocks(root, record_id):
    record = next(e for e in root.findall("./CheatEntries/CheatEntry") if e.findtext("ID") == str(record_id))
    return re.findall(r"\{\$lua\}\s*(.*?)\{\$asm\}", record.findtext("AssemblerScript"), re.S)


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    return prepare(SRC, tmp_path_factory.mktemp("product") / "ce_mvp.local.CT")


@pytest.fixture(params=["lua53", "lua54"])
def native(request, prepared):
    lua = import_module("lupa." + request.param).LuaRuntime(unpack_returned_tuples=True)
    w = lua.execute((ROOT / "tests/fixtures/ce_mvp_product_mock.lua").read_text(encoding="utf-8"))()
    root = ET.parse(prepared).getroot()
    w.scripts = lua.table_from({i: lua.table_from(blocks(root, i)) for i in (1, 2)})
    yield lua, w
    if w.env.CE_MVP_PRODUCT:
        w.env.CE_MVP_PRODUCT.stop()


def monitoring(w):
    address = w.object()
    w.start()
    w.until_state("MONITORING")
    return address


def test_ct_inert_and_embedded_sources_identical(native, prepared):
    lua, w = native
    root = ET.parse(prepared).getroot()
    assert root.find("LuaScript") is None
    assert [e.findtext("ID") for e in root.findall("./CheatEntries/CheatEntry")] == ["1", "2", "3"]
    script = blocks(root, 1)[0]
    w.env.syntaxcheck = True
    lua.eval("function(code, env) return assert(load(code, '@syntax', 't', env))() end")(script, w.env)
    assert w.opens == 0 and w.env.CE_MVP_PRODUCT is None
    prefix = script[script.index("local sources="):script.index("assert(config_path")]
    embedded = lua.execute(prefix + "\nreturn sources")
    assert set(embedded) == set(MODULES)
    for name in MODULES:
        assert embedded[name] == (SRC / name).read_text(encoding="utf-8")
    w.env.syntaxcheck = None


@pytest.mark.parametrize("pid", [37, 20560, 654321, 0xFFFFFFFF])
def test_numeric_pid_from_config_without_allowlist(native, pid):
    _, w = native
    w.cfg.target_pid = pid
    monitoring(w)
    assert w.opened == w.status().pid == pid and w.opens == 1
    assert w.scans[1].args[4] == "42C80000"
    assert w.scans[1].OnlyOneResult is False and w.scans[1].IsUnique is False


def test_full_pool_over_old_budgets_selects_last_candidate(native):
    _, w = native
    for i in range(2101):
        address = w.object(None, i == 2100)
    w.cfg.scan.scan_budget = 2
    w.cfg.scan.max_candidates = 1
    w.start()
    s = w.until_state("MONITORING")
    assert s.raw_count == s.inspected_count == s.filtered_count == s.scored_count == 2101
    assert s.address == address == w.writes[1].address
    assert w.found.destroyed and w.scans[1].destroyed
    assert w.records[3].Address == f"{address:X}"
    w.records[3].Active = True
    assert w.records[3].Active is False


def test_review_top_rank_written(native):
    _, w = native
    w.object(); w.object()
    w.start(); s = w.until_state("MONITORING")
    assert s.recommendation == "REVIEW" and len(w.writes) == 1 and s.readback_verified


def test_only_original_hard_filter_gates_rank_one(native):
    _, w = native
    w.object(None, False)
    w.start(); s = w.until_state("MONITORING")
    assert s.recommendation == "REJECT" and len(w.writes) == 1


def test_original_collector_and_product_rank_one_agree(native):
    lua, w = native
    w.object(None, False); w.object(); w.object()
    sources = lua.table_from({name: (SRC / name).read_text(encoding="utf-8") for name in MODULES})
    reference = lua.eval("""function(w, sources)
      local e=w.env
      local scan=e.createMemScan()
      scan.firstScan(0,2,0,'42C80000','',0,0x7FFFFFFFFFFF)
      e.getCurrentMemscan=function() return scan end
      e.getAddress=function(addr) return tonumber(addr,16) end
      assert(load(sources['mvp0_candidate_report.lua'],'@reference','t',e))()
      local collector=assert(load(sources['mvp0_foundlist_collector.lua'],'@reference','t',e))()
      local result=collector.run({scan_budget=3,max_candidates=3,target_value_float=100,
        target_value_pattern=0x42C80000,filter_target_match=true,use_prescore_selection=true,
        probe_full_foundlist=false,stable_filter_intersection_enabled=false})
      scan.destroy()
      return result.result
    end""")(w, sources)
    w.start(); s = w.until_state("MONITORING")
    assert s.address == reference.best.candidate.value_addr
    assert s.score == reference.best.final_score
    assert s.recommendation == reference.recommendation.recommendation


def test_config_period_and_repeated_rewrites(native):
    _, w = native
    w.cfg.monitor_interval_ms = 750
    address = monitoring(w)
    start = w.writes[1].time
    w.memory[address] = 0x42280000
    w.step(14)
    assert len(w.writes) == 1
    w.step()
    assert len(w.writes) == 2 and w.writes[2].time == start + 750
    assert w.memory[address] == 0x42FA0000
    w.memory[address] = 0x42C80000
    w.step(15)
    assert len(w.writes) == 3 and w.status().rewrite_count == 2
    assert len(w.scans) == w.opens == 1


@pytest.mark.parametrize("bits", [0x42FA0000, 0x43160000])
def test_equal_or_above_left_alone(native, bits):
    _, w = native
    address = monitoring(w); w.memory[address] = bits
    w.step(40)
    assert len(w.writes) == 1 and w.memory[address] == bits


@pytest.mark.parametrize("fault", ["nil", "???", "nan", "infinity", "target_switch"])
def test_first_invalid_read_stops_without_later_writes(native, fault):
    _, w = native
    monitoring(w)
    if fault == "nil": w.fail.unreadable = True
    elif fault == "???": w.fail.float = "???"
    elif fault == "nan": w.fail.float = float("nan")
    elif fault == "infinity": w.fail.float = float("inf")
    else: w.opened = 909
    w.until_state("ERROR")
    s = w.status()
    assert not s.running and s.cleanup_ok and w.records[1].Active is False
    assert ("CE_TARGET_CHANGED" if fault == "target_switch" else "VALUE_UNREADABLE") in s.stop_reason
    reads = w.reads
    w.fail.unreadable = False; w.fail.float = None; w.opened = w.cfg.target_pid
    w.step(100)
    assert w.reads == reads and len(w.writes) == 1 and len(w.scans) == 1


@pytest.mark.parametrize("phase", ["scan", "ranking", "monitor"])
def test_unchecking_id1_cancels_each_phase(native, phase):
    _, w = native
    w.object()
    if phase == "scan": w.fail.scan_pending = True
    if phase == "ranking": w.cfg.scan.collection_batch_size = 1
    w.start()
    if phase == "ranking": w.until_state("RANKING")
    if phase == "monitor": w.until_state("MONITORING")
    w.stop(); writes = len(w.writes); reads = w.reads
    w.step(100)
    assert w.status().state == "STOPPED" and w.status().cleanup_ok
    assert len(w.writes) == writes and w.reads == reads
    assert w.scans[1].destroyed and all(t.destroyed for t in w.timers.values())


@pytest.mark.parametrize("fault,reason", [("write", "WRITE_FAILED"), ("readback", "WRITE_READBACK_MISMATCH")])
def test_write_or_readback_failure_stops_without_retry(native, fault, reason):
    _, w = native
    address = monitoring(w); w.memory[address] = 0x42280000
    w.fail[fault] = True
    w.until_state("ERROR"); w.step(100)
    assert reason in w.status().stop_reason and len(w.writes) == 2


def test_reread_config_beside_relocated_table(native):
    _, w = native
    w.filename = "D:/portable product/ce_mvp.local.CT"
    address = monitoring(w)
    assert w.config_path == "D:/portable product/ce_mvp_config.local.lua"
    w.stop(); w.cfg.target_pid = 909; w.cfg.write_value = 150
    w.memory[address] = 0x42C80000
    w.start(); s = w.until_state("MONITORING")
    assert s.pid == 909 and s.target_value == 150 and w.opens == 2


def test_legacy_fields_do_not_select_modes_or_gate_writes(native):
    lua, w = native
    w.cfg.engineering_extensions = lua.table_from({"strict_attachment": True})
    w.cfg.diagnostics = "ignored"
    w.cfg.max_rescan_attempts = "ignored"
    w.cfg.scan.scan_budget = "ignored"
    w.cfg.scan.max_candidates = 0
    w.cfg.input_source = "OWNED_SYNTHETIC"
    monitoring(w)
    assert w.opened == 101 and len(w.writes) == 1


@pytest.mark.parametrize("fault", ["pid", "disabled", "pattern", "interval", "attach", "config"])
def test_invalid_input_or_failed_attach_never_writes(native, fault):
    _, w = native
    if fault == "pid": w.cfg.target_pid = 0
    elif fault == "disabled": w.cfg.write_enabled = False
    elif fault == "pattern": w.cfg.scan.target_value_pattern = 0
    elif fault == "interval": w.cfg.monitor_interval_ms = 0
    else: w.fail[fault] = True
    with pytest.raises(Exception): w.start()
    assert w.status().state == "ERROR" and len(w.writes) == 0 and len(w.scans) == 0


def test_empty_pool_never_writes(native):
    _, w = native
    w.start(); w.until_state("ERROR")
    assert "NO_HARD_PASS_CANDIDATE" in w.status().stop_reason and len(w.writes) == 0


def test_timeout_never_writes_partial_ranking(native):
    _, w = native
    for _ in range(50): w.object()
    w.cfg.scan_timeout_ms = 250; w.cfg.scan.collection_batch_size = 1
    w.start(); w.until_state("ERROR")
    assert "SCAN_TIMEOUT" in w.status().stop_reason and len(w.writes) == 0


def test_builder_handles_paths_and_xml_delimiters(tmp_path):
    lua = import_module("lupa.lua53").LuaRuntime()
    path = "D:/表 ' quoted ]]> folder/config.lua"
    assert lua.eval(lua_path(path)) == path
    source = tmp_path / "source"; source.mkdir()
    (source / "ce_mvp.CT").write_bytes((SRC / "ce_mvp.CT").read_bytes())
    for name in MODULES:
        (source / name).write_text("-- ]]> and ]====] delimiters\nreturn {}\n", encoding="utf-8")
    table = prepare(source)
    script = blocks(ET.parse(table).getroot(), 1)[0]
    prefix = script[script.index("local sources="):script.index("assert(config_path")]
    embedded = lua.execute(prefix + "\nreturn sources")
    for name in MODULES:
        assert embedded[name] == (source / name).read_text(encoding="utf-8")


def test_search_and_write_values_are_not_fixed_to_test_examples(native):
    _, w = native
    address = w.object()
    w.memory[address] = 0x427E0000  # 63.5
    w.cfg.scan.target_value_float = 63.5
    w.cfg.scan.target_value_pattern = 0x427E0000
    w.cfg.write_value = 42.25
    w.start(); s = w.until_state("MONITORING")
    assert w.scans[1].args[4] == "427E0000"
    assert s.current_value == 42.25 and w.memory[address] == 0x42290000
    w.memory[address] = 0x41480000  # 12.5
    w.step(20)
    assert w.memory[address] == 0x42290000 and len(w.writes) == 2


@pytest.mark.parametrize("lo,hi", [("bad", "bad"), ("0x10000", None), (20, 10)])
def test_invalid_bounds_do_not_silently_become_process_scope(native, lo, hi):
    _, w = native
    w.cfg.scan.start_address = lo; w.cfg.scan.stop_address = hi
    with pytest.raises(Exception): w.start()
    assert w.opens == 0 and len(w.writes) == 0


def test_cleanup_failure_blocks_write_and_restart(native):
    _, w = native
    w.object(); w.fail.scan_destroy = True
    w.start(); w.until_state("ERROR")
    assert w.status().cleanup_ok is False and len(w.writes) == 0
    with pytest.raises(Exception, match="Restart CE after cleanup failure"):
        w.start()
