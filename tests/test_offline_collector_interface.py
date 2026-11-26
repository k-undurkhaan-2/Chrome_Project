"""Reuse AC5 contract cases through the existing collector interface.

Only the existing synthetic Lua fixtures and fail-on-call native doubles run.
"""
import re

import pytest

import test_offline_full_population as ac5
from test_h3_a7_ce_mvp import ROOT, runtime  # noqa: F401
from test_stable_prescore_optimization import plain

# Same contracts at the connected boundary, without copying the AC5 cases.
from test_offline_full_population import (  # noqa: F401
    test_bounded_exact_reference_and_defaults,
    test_empty_filtered_and_duplicate_populations,
    test_exceptions_propagate_without_result_or_recommendation,
    test_full_exact_scores_context_order_recommendation_and_report,
    test_invalid_options_do_not_select_or_score,
    test_invalid_or_conflicting_records_are_errors,
    test_metadata_truth_cannot_influence_scores_and_native_config_stays_closed,
    test_partial_or_corrupt_results_never_return_success,
    test_small_allocator_failure_propagates_original_exception,
    test_ties_are_deterministic_across_source_order,
    test_unmapped_records_cannot_supply_missing_features,
)


def interface(lua, w):
    api = lua.execute((ROOT / "src/mvp0_foundlist_collector.lua").read_text(encoding="utf-8"))
    lua.globals().ac6_source = ac5.SOURCE.read_text(encoding="utf-8")
    loader = lua.eval("""function(name, env)
      if name == 'mvp0_offline_scoring.lua' then
        return assert(load(ac6_source, name, 't', env))()
      end
      return w.load(name, env)
    end""")
    return api, lua.table_from({"records": w.objects, "load_module": loader})


def connected(lua, w, **overrides):
    api, request = interface(lua, w)
    opts = lua.table_from({"target_value_pattern": 0x42C80000,
        "target_value_float": 100.0, **overrides})
    return api.run(opts, request)


@pytest.fixture(autouse=True)
def use_connected_interface(monkeypatch):
    monkeypatch.setattr(ac5, "offline", connected)


def test_handoff_is_once_isolated_and_preserves_the_entire_ac5_return(runtime):
    lua, w = runtime
    ac5.records(w, good=(17,))
    api, request = interface(lua, w)
    lua.globals().request = request
    lua.execute("""
      local loader=request.load_module
      request.load_module=function(name,env)
        assert(getmetatable(env)==nil and env.python==nil and env.io==nil and env.w==nil)
        assert(env.require==nil and env.loadfile==nil and env.os.execute==nil)
        assert(env.openProcess==nil and env.writeInteger==nil and env.createTimer==nil)
        local m=loader(name,env)
        if name=='mvp0_offline_scoring.lua' then
          local run=m.run
          m.run=function(records,opts,load_module)
            w.ac6_calls=(w.ac6_calls or 0)+1
            w.ac6_return=run(records,opts,load_module)
            return w.ac6_return
          end
        end
        return m
      end
      readInteger=function() error('AMBIENT_READ') end
      getCurrentMemscan=function() error('AMBIENT_SCAN') end
    """)
    opts = lua.table_from({"population_mode": "full", "target_value_pattern": 0x42C80000})
    before = plain(opts), plain(w.objects)
    actual = api.run(opts, request)
    assert w.ac6_calls == 1
    assert lua.eval("function(a,b) return rawequal(a,b) end")(actual, w.ac6_return)
    assert before == (plain(opts), plain(w.objects))
    assert actual.result.recommendation.manual_review_required is False
    ac5.no_native(w)


@pytest.mark.parametrize("mutation", [
    "return nil", "r.completed=false", "r.population_complete=false",
    "r.population_mode='bounded'", "r.status='EMPTY'", "r.counts=nil",
    "r.counts.ranked=1", "r.counts.selected=0", "r.counts.eligible=99",
    "r.counts.supplied=0/0", "r.result=nil", "r.result.ranked=nil",
    "r.result.recommendation=nil", "r.result.report_text=nil",
    "r.identities=nil", "r.identities.eligible={}",
    "r.collection.selected_count=0", "r.result.recommendation.manual_review_required=nil",
    "r.result.recommendation.recommendation=nil", "r.result.recommendation.confidence=nil",
    "r.result.recommendation.score_gap=nil", "r.result.recommendation.rationale=nil",
    "r.result.recommendation.rationale[1]=false", "r.result.manual_review=nil",
    "r.identities.supplied[2]=r.identities.supplied[1]",
    "r.identities.distinct[2]=r.identities.distinct[1]",
    "r.identities.eligible[2]=r.identities.eligible[1]",
    "r.collection.candidate_value_addrs[2]=r.collection.candidate_value_addrs[1]",
    "r.result.ranked[2]=r.result.ranked[1]",
    "r.identities.supplied[4]=999; r.counts.supplied=4; r.counts.duplicates=1",
    "r.identities.eligible.extra=999",
])
def test_incomplete_ac5_envelope_is_unsuccessful(runtime, mutation):
    lua, w = runtime
    ac5.records(w, 3)
    api, request = interface(lua, w)
    lua.globals().request = request
    lua.execute("""
      local loader=request.load_module
      request.load_module=function(name,env)
        local m=loader(name,env)
        if name=='mvp0_offline_scoring.lua' then
          local run=m.run
          m.run=function(...)
            local r=run(...)
            do """ + mutation + """ end
            return r
          end
        end
        return m
      end
    """)
    with pytest.raises(Exception, match="OFFLINE_INCOMPLETE_RESULT"):
        api.run(lua.table_from({"population_mode": "full", "target_value_pattern": 0x42C80000}), request)
    ac5.no_native(w)


@pytest.mark.parametrize("fault", ["error('SYNTHETIC_ABORT',0)", "error('SYNTHETIC_RESOURCE',0)",
    "error({cause='ORIGINAL_CAUSE'},0)"])
def test_success_then_failure_has_no_stale_result_and_retains_cause(runtime, fault):
    lua, w = runtime
    ac5.records(w, 3, good=(2,))
    api, request = interface(lua, w)
    lua.globals().request, lua.globals().api = request, api
    lua.execute("""
      local opts={population_mode='full',target_value_pattern=0x42C80000}
      local first=api.run(opts,request)
      assert(first.completed)
      request.load_module=function() """ + fault + """ end
      local ok,err=pcall(api.run,opts,request)
      assert(not ok)
      if type(err)=='table' then assert(err.cause=='ORIGINAL_CAUSE')
      else assert(err=='SYNTHETIC_ABORT' or err=='SYNTHETIC_RESOURCE') end
      assert(first.completed)
    """)
    ac5.no_native(w)


@pytest.mark.parametrize("request_code", ["nil", "false", "{}", "{records={}}",
    "{records={},load_module=function() end,action='execute'}", "setmetatable({},{})"])
def test_missing_or_invalid_request_never_falls_through_to_live_collection(runtime, request_code):
    lua, w = runtime
    api, _ = interface(lua, w)
    opts = lua.table_from({"population_mode": "full", "target_value_pattern": 0x42C80000})
    with pytest.raises(Exception, match="OFFLINE_INVALID_REQUEST"):
        api.run(opts, lua.eval(request_code))
    ac5.no_native(w)


@pytest.mark.parametrize("key", ["target_pid", "openProcess", "readInteger", "write_enabled",
    "action", "on_rank_complete", "execution_mode", "live"])
def test_live_and_action_options_are_rejected(runtime, key):
    lua, w = runtime
    ac5.records(w, 1)
    with pytest.raises(Exception, match="OFFLINE_INVALID_OPTIONS"):
        connected(lua, w, population_mode="full", **{key: True})
    ac5.no_native(w)


def test_documented_connected_example(runtime):
    lua, w = runtime
    text = (ROOT / "docs/algorithm_a_offline_scoring.md").read_text(encoding="utf-8")
    example = re.search(r"<!-- AC6 example -->\s*```lua\n(.*?)\n```", text, re.S).group(1)
    lua.execute(example)
    ac5.no_native(w)
