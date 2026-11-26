"""Focused CT-host integration in the existing small synthetic Lua test envelope.

No CE host, native target or historical qualification campaign is executed.
"""
from importlib import import_module
import json

import pytest

from prepare_ce_mvp import prepare
from test_h3_a7_ce_mvp import SRC, legacy_reference, make_runtime, portable_source, table_lua
from test_offline_full_population import no_native
from test_stable_prescore_optimization import array, plain


ENTRY = SRC / "ce_mvp_readonly.lua"
EXAMPLE = SRC / "examples/g1_alpha_population.example.lua"


@pytest.fixture
def runtime():
    return make_runtime("lua53")


@pytest.fixture
def host(runtime):
    lua, w = runtime
    lua.execute("""
      for k,v in pairs(w.ce) do _G[k]=v end
      w.loaded={}; w.evaluations=0
      local original=loadfile
      loadfile=function(path,mode,env)
        local name=path:match('[^/\\\\]+$')
        w.loaded[#w.loaded+1]=name
        if name~='ce_mvp_readonly.lua' then
          assert(env and getmetatable(env)==nil and env.python==nil and env.io==nil)
          assert(env.require==nil and env.loadfile==nil and env.openProcess==nil)
          assert(env.writeFloat==nil and env.createTimer==nil)
          assert(env.readInteger==nil or name=='mvp0_candidate_report.lua'
            or name=='mvp0_foundlist_collector.lua')
          assert(env.os==nil or env.os.execute==nil)
          assert(name=='g1_alpha_population.example.lua' or name=='mvp0_offline_scoring.lua'
            or name=='mvp0_candidate_report.lua' or name=='mvp0_foundlist_collector.lua')
        end
        local chunk,err=original(path,mode,env)
        if not chunk then return nil,err end
        return function()
          local m=chunk()
          if name=='mvp0_offline_scoring.lua' then
            local run=m.run
            m.run=function(...) w.evaluations=w.evaluations+1; return run(...) end
          end
          if w.inject then w.inject(name,m) end
          return m
        end
      end
    """)
    api = lua.execute(ENTRY.read_text(encoding="utf-8"), name="@" + ENTRY.as_posix())
    yield lua, w, api
    no_native(w)
    assert lua.globals().MVP0 is None and lua.globals().MVP0FoundList is None
    assert lua.globals().H3A7_CE_MVP is None


def example(lua):
    return lua.execute(EXAMPLE.read_text(encoding="utf-8"))


def test_import_is_inert_and_host_version_is_checked_before_file_access(runtime):
    lua, w = runtime
    for engine in (lua, import_module("lupa.lua54").LuaRuntime(unpack_returned_tuples=True)):
        engine.execute("loadfile=function() error('UNEXPECTED_FILE_ACCESS') end")
        api = engine.execute(ENTRY.read_text(encoding="utf-8"), name="@" + ENTRY.as_posix())
        options = engine.table_from({"population_mode": "full"})
        reason = "UNEXPECTED_FILE_ACCESS" if engine.eval("_VERSION") == "Lua 5.3" else "CE_ENTRYPOINT_REQUIRES_LUA_5_3"
        with pytest.raises(Exception, match=reason):
            api.evaluate(engine.table(), options)
    no_native(w)


@pytest.mark.parametrize("kind", ["accept", "review", "reject"])
def test_host_preserves_ordinary_scores_order_cohort_recommendation_and_truth_isolation(host, kind):
    lua, w, api = host
    data = example(lua)
    w.objects = data.records
    lua.globals().population_kind = kind
    lua.execute("""
      if population_kind=='review' then
        local good=w.objects[1]
        for addr,bits in pairs(good.memory) do w.objects[2].memory[addr+0x200]=bits end
      elseif population_kind=='reject' then
        for addr in pairs(w.objects[1].memory) do
          if addr~=w.objects[1].addr then w.objects[1].memory[addr]=0 end
        end
      end
    """)
    before = plain(data)
    reference = legacy_reference(lua, w)
    actual = api.evaluate(data.records, data.options)
    assert plain(actual.evaluation.result) == plain(reference.result)
    assert actual.evaluation.result.recommendation.recommendation == kind.upper()
    assert plain(data) == before
    assert actual.proposed_rank1 == actual.evaluation.result.best.candidate.value_addr
    assert actual.action_permitted is False and actual.automatic_recovery is False
    assert actual.action_status.startswith("UNSUPPORTED") and actual.lifecycle_status.startswith("UNSUPPORTED")
    assert actual.semantic_validity == "UNVERIFIED_SYNTHETIC_SNAPSHOT_ONLY"
    lua.execute("for _,r in ipairs(w.objects) do r.known_true=true; r.expected='ACCEPT' end")
    assert plain(api.evaluate(data.records, data.options).evaluation) == plain(actual.evaluation)
    assert w.evaluations == 2


def test_public_example_is_same_as_existing_json_and_prints_full_evidence_once(host):
    lua, w, api = host
    data = example(lua)
    document = json.loads((SRC / "examples/g1_alpha_population.example.json").read_text(encoding="utf-8"))
    for row in document["records"]:
        row["memory"] = {int(key): value for key, value in row["memory"].items()}
    assert plain(data.options) == document["options"]
    assert [plain(row) for row in array(data.records)] == document["records"]
    outcome = api.run_example()
    assert w.evaluations == 1 and len(w.lines) == 2
    text = w.lines[2]
    assert text.endswith("invocation=COMPLETE; recommendation grants no action authority")
    assert outcome.evaluation.result.report_text in text
    assert outcome.proposed_rank1 == 0x100128
    assert outcome.evaluation.result.best.final_score == 46
    assert outcome.evaluation.result.recommendation.manual_review_required is False
    for key in ("supplied", "distinct", "eligible", "selected", "ranked"):
        assert f"identities.{key}=0x100128,0x100328,0x100528" in text
    assert set(api.keys()) == {"evaluate", "run_example"}


@pytest.mark.parametrize("population", ["empty", "excluded", "duplicates"])
def test_exact_membership_and_legitimate_empty(host, population):
    lua, w, api = host
    data = example(lua)
    w.objects = data.records
    if population == "empty":
        data.records = lua.table()
    elif population == "excluded":
        lua.execute("for _,r in ipairs(w.objects) do r.mapped=false end")
    else:
        lua.execute("w.objects[4]=w.objects[1]; w.objects[2].mapped=false")
    actual = api.evaluate(data.records, data.options)
    result, counts = actual.evaluation, actual.evaluation.counts
    expected = {0x100128, 0x100528} if population == "duplicates" else set()
    assert set(array(result.identities.eligible)) == expected
    assert set(array(result.collection.candidate_value_addrs)) == expected
    ranked = [r.candidate.value_addr for r in array(result.result.ranked)]
    assert set(ranked) == expected and len(ranked) == len(expected)
    assert counts.eligible == counts.selected == counts.fully_scored == counts.ranked == len(expected)
    assert counts.supplied == counts.distinct + counts.duplicates
    assert counts.distinct == counts.eligible + counts.excluded
    if not expected:
        assert result.status == "EMPTY" and actual.proposed_rank1 is None
        assert result.result.recommendation.recommendation == "REJECT"


@pytest.mark.parametrize("options,reason", [
    ({}, "G1_READONLY_EXPLICIT_FULL_REQUIRED"),
    ({"population_mode": "bounded"}, "G1_READONLY_EXPLICIT_FULL_REQUIRED"),
    ({"population_mode": "full", "scan_budget": 3}, "OFFLINE_INVALID_OPTIONS"),
    ({"population_mode": "full", "max_candidates": False}, "OFFLINE_INVALID_OPTIONS"),
    ({"population_mode": "full", "action": True}, "OFFLINE_INVALID_OPTIONS"),
    ({"population_mode": "full", "target_pid": 101}, "OFFLINE_INVALID_OPTIONS"),
    ({"population_mode": "full", "known_true_addr": 0x100128}, "OFFLINE_INVALID_OPTIONS"),
])
def test_host_rejects_implicit_mode_count_budgets_truth_and_action(host, options, reason):
    lua, w, api = host
    with pytest.raises(Exception, match=reason):
        api.evaluate(example(lua).records, lua.table_from({"target_value_pattern": 0x42C80000, **options}))
    assert len(w.lines) == 0


@pytest.mark.parametrize("fault", [
    "error('SYNTHETIC_CANCELLED',0)",
    "error('SYNTHETIC_RESOURCE_EXHAUSTED',0)",
    "r.ranked[2]=r.ranked[1]",  # counts alone still match; identities do not
    "r.ranked[1].local_features=nil",
    "r.ranked[1].final_score=0/0",
])
def test_failure_after_success_has_no_stale_output_no_retry_and_no_fallback(host, fault):
    lua, w, api = host
    assert api.run_example().evaluation.completed
    lua.execute("""
      w.lines={}
      w.inject=function(name,m)
        if name=='mvp0_candidate_report.lua' then
          local original=m.run
          m.run=function(...)
            local r=original(...)
            do """ + fault + """ end
            return r
          end
        end
      end
    """)
    with pytest.raises(Exception, match="SYNTHETIC_|OFFLINE_INCOMPLETE_RESULT"):
        api.run_example()
    assert w.evaluations == 2
    assert len(w.lines) == 1 and "invocation=BEGIN" in w.lines[1]
    assert "invocation=COMPLETE" not in w.lines[1]
    assert set(api.keys()) == {"evaluate", "run_example"}


def test_original_allocator_failure_escapes_without_success_output(host):
    lua, w, api = host
    original_limit = lua.get_max_memory()
    lua.globals().tight_limit = lambda: lua.set_max_memory(lua.get_memory_used() + 8192)
    lua.execute("""
      w.inject=function(name,m)
        if name=='mvp0_candidate_report.lua' then
          m.score_candidate=function() tight_limit(); string.rep('x',65536) end
        end
      end
    """)
    try:
        with pytest.raises(import_module(type(lua).__module__).LuaMemoryError):
            api.run_example()
    finally:
        lua.set_max_memory(original_limit)
    assert w.evaluations == 1 and len(w.lines) == 1


def test_empty_prints_ordinary_reject_without_rank1(host):
    lua, w, api = host
    lua.execute("w.inject=function(name,m) if name=='g1_alpha_population.example.lua' then m.records={} end end")
    result = api.run_example()
    assert result.evaluation.status == "EMPTY" and result.proposed_rank1 is None
    assert "status=EMPTY" in w.lines[2] and "recommendation=REJECT" in w.lines[2]
    assert "proposed_rank1=nil" in w.lines[2] and "counts.fully_scored=0" in w.lines[2]
    assert result.evaluation.result.report_text in w.lines[2]


def test_incomplete_ac6_evidence_never_becomes_a_host_proposal(host):
    lua, w, api = host
    lua.execute("""
      w.inject=function(name,m)
        if name=='mvp0_offline_scoring.lua' then
          local original=m.run
          m.run=function(...) local r=original(...); r.population_complete=false; return r end
        end
      end
    """)
    with pytest.raises(Exception, match="OFFLINE_INCOMPLETE_RESULT"):
        api.run_example()
    assert len(w.lines) == 1 and w.evaluations == 1


def test_original_nonstring_cancellation_cause_is_preserved(host):
    lua, w, api = host
    lua.globals().readonly_api = api
    lua.execute("""
      local cause={reason='SYNTHETIC_CANCELLED'}
      w.inject=function(name) if name=='mvp0_offline_scoring.lua' then error(cause,0) end end
      local ok,err=pcall(readonly_api.run_example)
      assert(not ok and rawequal(err,cause))
    """)
    assert len(w.lines) == 1 and w.evaluations == 0


def test_prepared_ct_runs_only_the_new_entry_and_disable_is_inert(host, tmp_path):
    lua, w, _ = host
    source_dir = portable_source(tmp_path)
    path = prepare(source_dir)
    enable, disable = table_lua(path)[4:]
    lua.globals().syntaxcheck = True
    lua.execute(enable); lua.execute(disable)
    assert len(w.loaded) == len(w.lines) == 0
    lua.globals().syntaxcheck = False
    lua.execute(disable)
    assert len(w.loaded) == 0
    with pytest.raises(Exception, match="CE_MVP_TABLE_NOT_PREPARED"):
        lua.execute(table_lua(SRC / "ce_mvp.CT")[4])
    lua.execute(enable)
    assert w.evaluations == 1 and "invocation=COMPLETE" in w.lines[2]
    loaded = len(w.loaded)
    lua.execute(disable)
    assert len(w.loaded) == loaded and w.evaluations == 1
    assert not (source_dir / "ce_mvp_config.local.lua").exists()
    lua.execute("w.inject=function(name) if name=='mvp0_offline_scoring.lua' then error('SYNTHETIC_STOP',0) end end")
    with pytest.raises(Exception, match="SYNTHETIC_STOP"):
        lua.execute(enable)
    loaded = len(w.loaded)
    lua.execute(disable)
    assert len(w.loaded) == loaded and w.evaluations == 1


def test_example_cannot_use_ambient_apis_and_missing_files_do_not_fallback(host, tmp_path):
    lua, w, _ = host
    source_dir = portable_source(tmp_path)
    path = prepare(source_dir)
    enable = table_lua(path)[4]
    sample = source_dir / "examples/g1_alpha_population.example.lua"
    sample.write_text("return openProcess(101)", encoding="utf-8")
    with pytest.raises(Exception, match="openProcess"):
        lua.execute(enable)
    sample.unlink()
    with pytest.raises(Exception, match="g1_alpha_population.example.lua"):
        lua.execute(enable)
    assert w.evaluations == 0 and len(w.lines) == 2
