"""Frozen final ranking through the existing owned-table entry, without a target."""
from importlib import import_module
import subprocess

import pytest
from lupa.lua53 import LuaRuntime

from test_frozen_choice_lua import ROOT, FIELDS, ABS_TOL, array, reference  # noqa: F401

PARENT = "ce36bc95c92c7b5f77d3dfe6022aef5f80baccc3"
ENTRY = ROOT / "src/ce_mvp_readonly.lua"
EXAMPLE = ROOT / "src/examples/g1_alpha_population.example.lua"


def plain(value):
    if hasattr(value, "items"):
        return {key: plain(item) for key, item in value.items()}
    return value


@pytest.fixture
def host():
    lua = LuaRuntime(unpack_returned_tuples=True, max_memory=256 * 1024 * 1024)
    lua.execute("""
      t={lines={},loads={},events={},clock_calls=0,target_calls=0}
      os.clock=function() return 0 end -- deterministic unchanged baseline evidence
      getTickCount=function()
        t.clock_calls=t.clock_calls+1
        return t.ticks and assert(t.ticks[t.clock_calls]) or 0
      end
      print=function(text) t.lines[#t.lines+1]=text end
      for _,name in ipairs({'openProcess','readInteger','readFloat','writeFloat',
          'writeInteger','createMemScan','createFoundList','createTimer',
          'getOpenedProcessID','getOpenedProcessHandle','executeCodeLocalEx'}) do
        _G[name]=function() t.target_calls=t.target_calls+1; error('TARGET_API:'..name) end
      end
      local original=loadfile
      loadfile=function(path,mode,env)
        local name=path:match('[^/\\\\]+$')
        assert(name=='mvp0_foundlist_collector.lua' or name=='mvp0_offline_scoring.lua'
          or name=='mvp0_candidate_report.lua' or name=='mvp0_frozen_choice.lua'
          or name=='g1_alpha_population.example.lua')
        assert(env and getmetatable(env)==nil and env.io==nil and env.require==nil)
        assert(env.openProcess==nil and env.writeFloat==nil and env.createTimer==nil)
        assert(env.getTickCount==nil and (env.os==nil or env.os.execute==nil))
        t.loads[#t.loads+1]=name
        t.events[#t.events+1]={phase='load:'..name,clock_calls=t.clock_calls}
        local chunk,err=original(path,mode,env)
        if not chunk then return nil,err end
        return function()
          local m=chunk()
          local methods=name=='mvp0_frozen_choice.lua' and {'features','predict','leaders'}
            or name=='mvp0_candidate_report.lua' and {'run'} or {}
          for _,method in ipairs(methods) do
            local f=m[method]
            m[method]=function(...)
              t.events[#t.events+1]={phase=name..':'..method,clock_calls=t.clock_calls}
              return f(...)
            end
          end
          if t.inject then t.inject(name,m) end
          return m
        end
      end
    """)
    api = lua.execute(ENTRY.read_text(encoding="utf-8"), name="@" + ENTRY.as_posix())
    yield lua, lua.globals().t, api
    assert lua.globals().t.target_calls == 0
    assert lua.globals().CE_MVP_PRODUCT is None
    assert lua.globals().MVP0 is None and lua.globals().MVP0FoundList is None


def example(lua, kind="ordinary"):
    data = lua.execute(EXAMPLE.read_text(encoding="utf-8"))
    lua.globals().data = data
    if kind in ("ambiguous", "changed_winner"):
        lua.execute("for a,b in pairs(data.records[1].memory) do data.records[2].memory[a+0x200]=b end")
    if kind == "changed_winner":
        lua.execute("data.records[2].memory[data.records[2].addr+0x30]=0")
    elif kind == "weak":
        lua.execute("for _,r in ipairs(data.records) do for a in pairs(r.memory) do if a~=r.addr then r.memory[a]=0 end end end")
    elif kind == "missing":
        lua.execute("data.records[1].memory[data.records[1].addr-0x20]=nil")
    elif kind == "float_words":
        lua.execute("for _,r in ipairs(data.records) do for a,b in pairs(r.memory) do r.memory[a]=b+0.0 end end")
    elif kind == "reversed":
        lua.execute("data.records[1],data.records[3]=data.records[3],data.records[1]")
    elif kind == "empty":
        data.records = lua.table()
    elif kind == "excluded":
        lua.execute("for _,r in ipairs(data.records) do r.mapped=false end")
    elif kind == "duplicates":
        lua.execute("data.records[4]=data.records[1]; data.records[2].mapped=false")
    elif kind == "137_rows":
        lua.execute("""
          local original=data.records[1]
          for i=4,137 do
            local shift=(i-1)*0x200
            local r={addr=original.addr+shift,mapped=true,protect=4,memory={}}
            for a,b in pairs(original.memory) do r.memory[a+shift]=b end
            data.records[i]=r
          end
        """)
    return data


def prior_evaluation(lua, data):
    source = subprocess.check_output(["git", "show", PARENT + ":src/ce_mvp_readonly.lua"], cwd=ROOT)
    previous = lua.execute(source.decode(), name="@" + ENTRY.as_posix())
    return previous.evaluate(data.records, data.options).evaluation


@pytest.mark.parametrize("kind", ["ordinary", "changed_winner", "ambiguous", "weak", "missing",
                                  "float_words", "reversed", "duplicates", "137_rows"])
def test_final_ranking_matches_frozen_reference_and_preserves_baseline(host, reference, kind):
    lua, t, api = host
    data = example(lua, kind)
    before = plain(data)
    prior = plain(prior_evaluation(lua, data))
    outcome = api.evaluate(data.records, data.options)
    evaluation = plain(outcome.evaluation)
    actual_result = evaluation.pop("result")
    evaluation["result"] = evaluation.pop("baseline_result")
    assert evaluation == prior  # counts, identities, baseline scores/features/report unchanged
    assert plain(data) == before
    baseline = array(outcome.evaluation.baseline_result.ranked)
    rows = [reference.features(tuple(r.candidate[k] if r.candidate[k] is None else int(r.candidate[k])
                                     for k in FIELDS),
                               tuple(r[k] for k in reference.components)) for r in baseline]
    expected = reference.predict([r.final_score for r in baseline], rows, reference.model)
    score_by_id = {r.candidate.value_addr: s for r, s in zip(baseline, expected)}
    ranked = array(outcome.evaluation.result.ranked)
    assert len(ranked) == len(score_by_id) == outcome.evaluation.counts.eligible
    assert {r.candidate.value_addr for r in ranked} == set(score_by_id)
    for index, row in enumerate(ranked, 1):
        assert row.rank_position == index
        assert abs(row.final_score - score_by_id[row.candidate.value_addr]) <= ABS_TOL
        assert row.baseline_final_score == baseline[row.baseline_rank - 1].final_score
    assert [r.final_score for r in ranked] == sorted((r.final_score for r in ranked), reverse=True)
    expected_leaders = {baseline[i].candidate.value_addr for i in reference.leaders(expected)}
    assert {r.candidate.value_addr for r in array(outcome.evaluation.result.leaders)} == expected_leaders
    assert outcome.proposed_rank1 == (next(iter(expected_leaders)) if len(expected_leaders) == 1 else None)
    assert actual_result["status"] == ("UNIQUE" if len(expected_leaders) == 1 else "AMBIGUOUS")
    assert outcome.action_permitted is False and outcome.automatic_recovery is False
    assert outcome.evaluation.result.recommendation is None  # no baseline thresholds applied to model scores
    if kind == "changed_winner":
        assert outcome.evaluation.baseline_result.best.candidate.value_addr == 0x100128
        assert outcome.proposed_rank1 == 0x100328
    if kind in ("ambiguous", "weak"):
        assert outcome.evaluation.result.best is None and len(expected_leaders) > 1
    # Truth-like metadata never affects the model's prediction.
    lua.execute("for _,r in ipairs(data.records) do r.known_true=true; r.expected='ACCEPT' end")
    assert plain(api.evaluate(data.records, data.options).evaluation) == plain(outcome.evaluation)


@pytest.mark.parametrize("kind", ["empty", "excluded"])
def test_empty_eligible_population_has_no_fabricated_prediction(host, kind):
    lua, t, api = host
    data = example(lua, kind)
    outcome = api.evaluate(data.records, data.options)
    assert outcome.evaluation.status == outcome.evaluation.result.status == "EMPTY"
    assert outcome.evaluation.counts.eligible == outcome.evaluation.counts.ranked == 0
    assert len(outcome.evaluation.result.ranked) == len(outcome.evaluation.result.leaders) == 0
    assert outcome.proposed_rank1 is None
    assert not any(e.phase.endswith(":predict") for e in t.events.values())


@pytest.mark.parametrize("ticks,compute,total", [
    ([1000, 1010, 1040, 1045], 30, 45),
    ([0xFFFFFFF0, 0xFFFFFFF5, 3, 9], 14, 25),
    ([0, 0, 0, 0], 0, 0),
])
def test_timing_scopes_and_tick_wrap_without_a_new_clock_interface(host, ticks, compute, total):
    lua, t, api = host
    t.ticks = lua.table_from(ticks)
    data = example(lua)
    outcome = api.evaluate(data.records, data.options)
    assert plain(outcome.timing) == {"clock": "getTickCount", "algorithm_compute_ms": compute,
                                     "total_evaluation_ms": total}
    assert t.clock_calls == 4
    events = array(t.events)
    assert [(e.phase, e.clock_calls) for e in events[:2]] == [
        ("load:mvp0_foundlist_collector.lua", 1), ("load:mvp0_frozen_choice.lua", 1)]
    computation = [e for e in events if not e.phase.startswith("load:")]
    assert {e.phase for e in computation} == {"mvp0_candidate_report.lua:run",
        "mvp0_frozen_choice.lua:features", "mvp0_frozen_choice.lua:predict", "mvp0_frozen_choice.lua:leaders"}
    assert all(e.clock_calls == 2 for e in computation)


@pytest.mark.parametrize("module,method", [
    ("mvp0_candidate_report.lua", "run"), ("mvp0_frozen_choice.lua", "features"),
    ("mvp0_frozen_choice.lua", "predict"), ("mvp0_frozen_choice.lua", "leaders"),
])
def test_errors_after_success_never_publish_partial_or_stale_success(host, module, method):
    lua, t, api = host
    previous = plain(api.run_example())
    t.lines = lua.table()
    lua.globals().fault_module, lua.globals().fault_method = module, method
    lua.execute("t.inject=function(name,m) if name==fault_module then m[fault_method]=function() error('TRIAL_UNCOMPUTED') end end end")
    with pytest.raises(Exception, match="TRIAL_UNCOMPUTED"):
        api.run_example()
    assert len(t.lines) == 1 and "invocation=BEGIN" in t.lines[1]
    assert previous["evaluation"]["completed"] is True
    assert set(api.keys()) == {"evaluate", "run_example"}


@pytest.mark.parametrize("options", [{}, {"population_mode": "bounded"},
    {"population_mode": "full", "target_pid": 101}, {"population_mode": "full", "action": True},
    {"population_mode": "full", "scan_budget": 1}, {"population_mode": "full", "max_candidates": 1}])
def test_existing_input_and_capability_rejections_remain(host, options):
    lua, t, api = host
    data = example(lua)
    with pytest.raises(Exception, match="G1_READONLY_EXPLICIT_FULL_REQUIRED|OFFLINE_INVALID_OPTIONS"):
        api.evaluate(data.records, lua.table_from({"target_value_pattern": 0x42C80000, **options}))
    assert not any(e.phase.endswith(":predict") for e in t.events.values())


def test_load_is_inert_runtime_and_host_clock_required_before_files(host):
    lua, t, api = host
    assert t.clock_calls == len(t.loads) == 0
    lua.execute("getTickCount=nil")
    with pytest.raises(Exception, match="G1_READONLY_HOST_CLOCK_REQUIRED"):
        api.evaluate(lua.table(), lua.table_from({"population_mode": "full"}))
    assert len(t.loads) == 0
    lua54 = import_module("lupa.lua54").LuaRuntime()
    other = lua54.execute(ENTRY.read_text(encoding="utf-8"), name="@" + ENTRY.as_posix())
    with pytest.raises(Exception, match="CE_ENTRYPOINT_REQUIRES_LUA_5_3"):
        other.evaluate(lua54.table(), lua54.table())


def test_existing_example_prints_model_ranking_and_both_timings(host):
    lua, t, api = host
    outcome = api.run_example()
    assert len(t.lines) == 2
    text = t.lines[2]
    assert "model=conditional_choice_linear_ridge_0.1" in text
    assert "prediction_status=UNIQUE" in text and "identities.leaders=0x100128" in text
    assert "rank.1=0x100128; choice_score=" in text and "baseline_score=46" in text
    assert "timing.algorithm_compute_ms=0" in text and "timing.total_evaluation_ms=0" in text
    assert "recommendation=ACCEPT" not in text
    assert outcome.evaluation.baseline_result.report_text not in text
    assert text.endswith("invocation=COMPLETE; prediction grants no action authority")


def test_frozen_model_and_native_entry_sources_unchanged():
    for path in ("src/mvp0_frozen_choice.lua", "src/ce_mvp.lua", "src/ce_mvp.CT",
                 "src/prepare_ce_mvp.py", "src/ce_mvp_adapter.lua", "src/ce_mvp_core.lua"):
        expected = subprocess.check_output(["git", "show", PARENT + ":" + path], cwd=ROOT)
        assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == expected
