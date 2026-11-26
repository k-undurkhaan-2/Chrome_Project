"""AC5 table-only regression; reuse the existing Lua fixtures and reference.

No adapter, loop, native calls, files, or truth labels enter the scoring path.
"""
from importlib import import_module
from pathlib import Path

import pytest

from test_stable_prescore_optimization import array, plain


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {name: (ROOT / "src" / name).read_text(encoding="utf-8")
           for name in ("mvp0_candidate_report.lua", "mvp0_foundlist_collector.lua",
                        "mvp0_offline_scoring.lua")}


@pytest.fixture(params=["lua53", "lua54"])
def runtime(request):
    # Missing interpreters are failures, not synthetic compatibility skips.
    module = import_module("lupa." + request.param)
    lua = module.LuaRuntime(unpack_returned_tuples=True, max_memory=256 * 1024 * 1024)
    assert lua.eval("_VERSION") == {"lua53": "Lua 5.3", "lua54": "Lua 5.4"}[request.param]
    factory = lua.execute((ROOT / "tests/fixtures/offline_population.lua").read_text(encoding="utf-8"))
    w = factory.new(lua.table_from(SOURCES))
    lua.globals().w = w
    return lua, w


def legacy_reference(lua, w):
    """Run the original Single pipeline over the same table-backed population."""
    return lua.execute("""
      local env={}; for k,v in pairs(_G) do env[k]=v end; env._G=env; env.print=function() end
      env.readInteger=function(addr) return assert(w.locate(addr)).memory[addr] end
      env.readFloat=function(addr) return string.unpack('<f',string.pack('<I4',env.readInteger(addr))) end
      env.getAddress=function(addr) return type(addr)=='number' and addr or tonumber(addr,16) end
      env.getCurrentMemscan=function() return {} end
      env.createFoundList=function()
        local fl={Count=0,Address={}}
        for _,o in ipairs(w.objects) do
          if o.mapped and o.protect==4 and o.memory[o.addr]==0x42C80000 then
            fl.Address[fl.Count]=o.addr; fl.Count=fl.Count+1
          end
        end
        fl.initialize=function() end; fl.destroy=function() end; return fl
      end
      local report=w.load('mvp0_candidate_report.lua',env)
      local collector=w.load('mvp0_foundlist_collector.lua',env)
      local settings=w.cfg.scan
      return collector.run({scan_budget=settings.scan_budget,max_candidates=settings.max_candidates,
        target_value_pattern=0x42C80000,target_value_float=100.0,filter_target_match=true,
        use_prescore_selection=true,probe_full_foundlist=false,stable_filter_intersection_enabled=false})
    """)


SOURCE = ROOT / "src/mvp0_offline_scoring.lua"


def offline(lua, w, **overrides):
    api = lua.execute(SOURCE.read_text(encoding="utf-8"))
    opts = {"target_value_pattern": 0x42C80000, "target_value_float": 100.0, **overrides}
    return api.run(w.objects, lua.table_from(opts), w.load)


def records(w, count=37, *, good=()):
    for index in range(1, count + 1):
        w.object(0x100128 + index * 0x200, None if index in good else "weak")


def no_native(w):
    assert w.open_calls == w.reads == w.forbidden == 0
    assert len(w.native_calls) == len(w.writes) == len(w.scans) == len(w.timers) == 0
    assert w.adapter is None and w.loop is None


@pytest.mark.parametrize("opts", [{}, {"population_mode": "bounded"},
    {"scan_budget": 9, "max_candidates": 4}, {"scan_budget": 37, "max_candidates": 37}])
def test_bounded_exact_reference_and_defaults(runtime, opts):
    lua, w = runtime
    records(w, good=(17,))
    before = plain(w.objects)
    w.cfg.scan.scan_budget = opts.get("scan_budget", 2000)
    w.cfg.scan.max_candidates = opts.get("max_candidates", 20)
    reference = legacy_reference(lua, w)
    actual = offline(lua, w, **opts)
    assert plain(actual.result) == plain(reference.result)
    assert plain(actual.collection) == {k: v for k, v in plain(reference).items() if k != "result"}
    assert actual.population_mode == "bounded" and actual.completed
    assert actual.counts.eligible == 37
    assert actual.counts.fully_scored == len(reference.result.ranked)
    assert actual.population_complete is (actual.counts.ranked == 37)
    assert plain(w.objects) == before
    no_native(w)


@pytest.mark.parametrize("kind", ["weak", "mixed", "ambiguous", "unique"])
def test_full_exact_scores_context_order_recommendation_and_report(runtime, kind):
    lua, w = runtime
    records(w, 37, good=(17,) if kind == "unique" else (1, 37) if kind == "ambiguous" else ())
    if kind == "mixed":
        lua.execute("""
          local patterns={{1,2,3,4,5,6,7}, {0x3F800000,0x3F800000,0,0,0x43300000,0,0},
            {0x41424344,0x45464748,0x494A4B4C,0,0x51525354,0x55565758,0x595A3031}}
          for i,o in ipairs(w.objects) do
            for j,off in ipairs({-0x20,-0x10,-8,0x30,0x40,0x48,0x50}) do
              o.memory[o.addr+off]=patterns[(i%3)+1][j]
            end
          end
        """)
    before = plain(w.objects)
    w.cfg.scan.scan_budget = w.cfg.scan.max_candidates = 37
    reference = legacy_reference(lua, w)
    actual = offline(lua, w, population_mode="full")
    assert plain(actual.result) == plain(reference.result)
    assert actual.population_mode == "full" and actual.status == "COMPLETE"
    assert actual.completed and actual.population_complete
    assert plain(actual.counts) == dict(supplied=37, distinct=37, duplicates=0,
        eligible=37, excluded=0, selected=37, fully_scored=37, ranked=37)
    assert set(array(actual.identities.eligible)) == {
        r.candidate.value_addr for r in array(actual.result.ranked)}
    if kind == "unique":
        assert actual.result.best.candidate.value_addr == w.objects[17].addr
        assert actual.result.best.final_score == 46
        assert actual.result.recommendation.recommendation == "ACCEPT"
    elif kind in ("weak", "ambiguous"):
        assert actual.result.recommendation.recommendation != "ACCEPT"
    assert plain(w.objects) == before
    no_native(w)


def test_ties_are_deterministic_across_source_order(runtime):
    lua, w = runtime
    records(w, 8, good=(1, 8))
    first = offline(lua, w, population_mode="full")
    lua.execute("local t={}; for i=#w.objects,1,-1 do t[#t+1]=w.objects[i] end; w.objects=t")
    second = offline(lua, w, population_mode="full")
    assert plain(first.result) == plain(second.result)
    assert first.result.best.candidate.value_addr < first.result.second.candidate.value_addr
    assert first.result.score_gap == 0 and first.result.confidence == "LOW"
    assert first.result.recommendation.recommendation == "REVIEW"


def test_unmapped_records_cannot_supply_missing_features(runtime):
    lua, w = runtime
    records(w, 2, good=(1,))
    lua.execute("""
      local first,excluded=w.objects[1],w.objects[2]
      local field=first.addr-0x20
      excluded.memory[field]=first.memory[field]
      excluded.mapped=false
      first.memory[field]=nil
    """)
    reference = legacy_reference(lua, w)
    actual = offline(lua, w, population_mode="full")
    assert actual.counts.eligible == 1 and actual.counts.excluded == 1
    assert actual.result.best.candidate.f08 is None
    assert plain(actual.result) == plain(reference.result)
    no_native(w)


@pytest.mark.parametrize("mode", ["bounded", "full"])
@pytest.mark.parametrize("population", ["empty", "excluded", "duplicates"])
def test_empty_filtered_and_duplicate_populations(runtime, mode, population):
    lua, w = runtime
    if population != "empty":
        records(w, 4)
        lua.execute("""
          w.objects[2].mapped=false; w.objects[3].protect=2
          w.objects[4].memory[w.objects[4].addr]=0x3F800000
        """)
        if population == "excluded":
            w.objects[1].mapped = False
        else:
            lua.execute("w.objects[#w.objects+1]=w.objects[1]")
    actual = offline(lua, w, population_mode=mode)
    assert actual.completed and actual.population_complete
    expected = 1 if population == "duplicates" else 0
    assert actual.counts.eligible == actual.counts.fully_scored == actual.counts.ranked == expected
    assert actual.status == ("COMPLETE" if expected else "EMPTY")
    assert actual.counts.duplicates == (1 if expected else 0)
    if not expected:
        assert actual.result.best is None and actual.result.recommendation.recommendation == "REJECT"
    no_native(w)


@pytest.mark.parametrize("opts", [
    {"population_mode": v} for v in (False, 0, 1, "", "FULL", "unbounded")
] + [
    {"population_mode": "full", key: value}
    for key in ("scan_budget", "max_candidates") for value in (0, 1, 999999, False)
] + [
    {"scan_budget": 0}, {"scan_budget": 65537}, {"scan_budget": False},
    {"scan_budget": 1.5}, {"scan_budget": float("inf")}, {"scan_budget": float("nan")},
    {"max_candidates": 0}, {"max_candidates": 129}, {"max_candidates": False},
    {"scan_budget": 1, "max_candidates": 2}, {"filter_target_match": False},
    {"use_prescore_selection": False}, {"known_true_addr": 0x100128},
    {"probe_full_foundlist": True}, {"expected": "ACCEPT"}, {"target_value_pattern": -1},
])
def test_invalid_options_do_not_select_or_score(runtime, opts):
    lua, w = runtime
    records(w, 3)
    lua.execute("w.load=function() error('SHOULD_NOT_LOAD') end")
    with pytest.raises(Exception, match="OFFLINE_INVALID_OPTIONS"):
        offline(lua, w, **opts)
    no_native(w)


@pytest.mark.parametrize("edit", [
    "w.objects[2]=nil", "w.objects.extra=w.objects[1]",
    "w.objects[1].memory=nil", "w.objects[1].addr=0/0",
    "w.objects[1].memory[w.objects[1].addr]=1.5",
    "setmetatable(w.objects[1],{})",
    "local o=w.object(w.objects[1].addr,'weak'); o.mapped=false",
    "local o=w.object(w.objects[1].addr); o.memory[o.addr]=100",
])
def test_invalid_or_conflicting_records_are_errors(runtime, edit):
    lua, w = runtime
    records(w, 3)
    lua.execute(edit)
    with pytest.raises(Exception, match="OFFLINE_INVALID_RECORDS"):
        offline(lua, w, population_mode="full")
    no_native(w)


@pytest.mark.parametrize("phase", ["build_input", "score_candidate", "rank_candidates",
    "recommend_action", "render_report"])
def test_exceptions_propagate_without_result_or_recommendation(runtime, phase):
    lua, w = runtime
    records(w, 3, good=(2,))
    lua.globals().fault_phase = phase
    lua.execute("""
      local load_original=w.load
      w.load=function(name,env)
        local m=load_original(name,env)
        if m[fault_phase] then m[fault_phase]=function() error('SYNTHETIC_'..fault_phase,0) end end
        return m
      end
    """)
    with pytest.raises(Exception, match="SYNTHETIC_" + phase):
        offline(lua, w, population_mode="full")
    no_native(w)


@pytest.mark.parametrize("mutation", [
    "table.remove(r.ranked)", "r.ranked[2]=r.ranked[1]", "r.ranked[3]=nil",
    "r.ranked[1].final_score=0/0", "r.ranked[1].local_features=nil",
    "r.ranked[1].rank_position=3", "r.ranked[1].template_family_size=999",
    "r.ranked[1].candidate.f08=nil",
])
def test_partial_or_corrupt_results_never_return_success(runtime, mutation):
    lua, w = runtime
    records(w, 4)
    lua.execute("""
      local load_original=w.load
      w.load=function(name,env)
        local m=load_original(name,env)
        if name=='mvp0_candidate_report.lua' then
          local run=m.run
          m.run=function(...) local r=run(...); """ + mutation + """; return r end
        end
        return m
      end
    """)
    with pytest.raises(Exception, match="OFFLINE_INCOMPLETE_RESULT"):
        offline(lua, w, population_mode="full")


def test_small_allocator_failure_propagates_original_exception(runtime):
    lua, w = runtime
    records(w, 3)
    original_limit = lua.get_max_memory()
    lua.globals().tight_limit = lambda: lua.set_max_memory(lua.get_memory_used() + 8192)
    lua.execute("""
      local load_original=w.load
      w.load=function(name,env)
        local m=load_original(name,env)
        if name=='mvp0_candidate_report.lua' then
          local score=m.score_candidate; local calls=0
          m.score_candidate=function(...)
            calls=calls+1
            if calls==2 then tight_limit(); string.rep('x',65536) end
            return score(...)
          end
        end
        return m
      end
    """)
    try:
        with pytest.raises(import_module(type(lua).__module__).LuaMemoryError):
            offline(lua, w, population_mode="full")
    finally:
        lua.set_max_memory(original_limit)
    no_native(w)


def test_options_are_not_mutated_and_environment_has_no_live_fallback(runtime):
    lua, w = runtime
    records(w, 3)
    api = lua.execute(SOURCE.read_text(encoding="utf-8"))
    opts = lua.table_from({"population_mode": "full", "target_value_pattern": 0x42C80000})
    before = plain(opts)
    lua.execute("""
      local load_original=w.load
      w.load=function(name,env)
        assert(getmetatable(env)==nil and env.python==nil and env.io==nil and env.w==nil)
        assert(env.require==nil and env.loadfile==nil and env.os.execute==nil)
        assert(env.openProcess==nil and env.writeInteger==nil and env.createTimer==nil)
        return load_original(name,env)
      end
      readInteger=function() error('AMBIENT_READ') end
      getCurrentMemscan=function() error('AMBIENT_SCAN') end
    """)
    assert api.run(w.objects, opts, w.load).completed
    assert plain(opts) == before
    no_native(w)


def test_metadata_truth_cannot_influence_scores(runtime):
    lua, w = runtime
    records(w, 3, good=(2,))
    first = offline(lua, w, population_mode="full")
    lua.execute("for _,o in ipairs(w.objects) do o.expected='ACCEPT'; o.known_true=true end")
    assert plain(offline(lua, w, population_mode="full").result) == plain(first.result)
    no_native(w)
