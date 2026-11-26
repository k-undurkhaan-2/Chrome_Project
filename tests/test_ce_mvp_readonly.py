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


@pytest.fixture(params=["controlled", "standard"])
def controlled_ct(tmp_path, request):
    yield from prepared_ct(tmp_path, request.param)


@pytest.fixture
def standard_ct(tmp_path):
    yield from prepared_ct(tmp_path, "standard")


def prepared_ct(tmp_path, mode):
    """Prepared ID1 + real loader; every ambient target primitive is forbidden."""
    import shutil
    from test_h3_a7_ce_mvp import ROOT

    source_dir = portable_source(tmp_path, mode)
    fixture_path = source_dir.parent / "tests/fixtures/ce_mvp_mock.lua"
    fixture_path.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "tests/fixtures/ce_mvp_mock.lua", fixture_path)
    path = prepare(source_dir, alpha_controlled=mode == "controlled")
    lua = import_module("lupa.lua53").LuaRuntime(unpack_returned_tuples=True,
                                                max_memory=256 * 1024 * 1024)
    lua.execute("""
      h={forbidden=0,loaded={},lines={},evaluations=0,config_reads=0}
      local open=io.open
      io.open=function(path,...)
        if path:match('ce_mvp_config%.local%.lua$') then
          h.config_reads=h.config_reads+1; h.config_path=path
        end
        return open(path,...)
      end
      for name in ('openProcess getOpenedProcessID getOpenedProcessHandle getAddressSafe '
          ..'executeCodeLocalEx createMemoryStream readIntegerLocal readQwordLocal '
          ..'createMemScan createFoundList createTimer readInteger readFloat writeFloat '
          ..'getProcessIDFromProcessName AOBScan executeCode executeCodeEx'):gmatch('%S+') do
        _G[name]=function() h.forbidden=h.forbidden+1; error('AMBIENT_TARGET_API:'..name) end
      end
      print=function(line) h.lines[#h.lines+1]=line end
      local original=loadfile
      loadfile=function(path,mode,env)
        local name=path:match('[^/\\\\]+$')
        assert(name~='ce_mvp_config.local.lua','PRIVATE_CONFIG_MUST_NOT_BE_READ')
        h.loaded[#h.loaded+1]=name
        local chunk,err=original(path,mode,env)
        if not chunk then return nil,err end
        return function()
          local m=chunk()
          if name=='mvp0_offline_scoring.lua' then
            local run=m.run
            m.run=function(...) h.evaluations=h.evaluations+1; return run(...) end
          end
          if h.inject then h.inject(name,m) end
          return m
        end
      end
    """)
    lua.globals().test_entry_mode = mode
    lua.globals().test_entry_path = (source_dir / "ce_mvp.lua").as_posix()
    yield lua, table_lua(path), source_dir
    api = lua.globals().H3A7_CE_MVP
    if api:
        api.stop()
        w = api.controlled_fixture()
        if w: w.clean()
    assert lua.globals().h.forbidden == 0


def start_controlled(lua, scripts):
    if lua.globals().test_entry_mode == "standard":
        lua.execute("""
          local m=dofile(test_entry_path)
          assert(m.configure_execution({mode='ALPHA_STANDARD',input_source='OWNED_SYNTHETIC'}))
        """)
    lua.execute(scripts[0])
    api = lua.globals().H3A7_CE_MVP
    w = api.controlled_fixture()
    lua.globals().cw = w
    return api, w


def test_controlled_id1_full_result_original_gates_and_no_native_calls(controlled_ct):
    lua, scripts, _ = controlled_ct
    lua.globals().syntaxcheck = True
    for code in scripts: lua.execute(code)
    assert lua.globals().H3A7_CE_MVP is None and len(lua.globals().h.loaded) == 0
    lua.globals().syntaxcheck = False
    api, w = start_controlled(lua, scripts)
    assert api.evaluation() is None
    w.until_state("MONITORING")
    e = api.evaluation()
    assert e.status == "COMPLETE" and e.population_complete
    assert e.result.best.candidate.value_addr == 0x100128
    assert e.result.best.final_score == 46 and e.result.second.final_score == -36
    assert e.result.recommendation.recommendation == "ACCEPT" and e.result.confidence == "HIGH"
    assert [r.candidate.value_addr for r in array(e.result.ranked)] == [0x100128, 0x100328, 0x100528]
    assert e.counts.eligible == e.counts.selected == e.counts.fully_scored == e.counts.ranked == 3
    assert len(w.writes) == 1 and len(w.scans) == 0
    assert w.loop.status().last_written_bits == w.loop.status().last_readback_bits == 0x42FA0000
    s = api.status()
    expected_mode = "ALPHA_STANDARD" if lua.globals().test_entry_mode == "standard" else "ALPHA_CONTROLLED"
    assert s.execution_mode == expected_mode and s.lifecycle_policy == "ALPHA_STOP_ONLY"
    assert s.product_profile == "ALPHA_FULL" and s.data_provenance == "synthetic"
    assert s.input_source == "OWNED_SYNTHETIC"
    assert s.action_permitted is False and s.automatic_recovery is False
    assert s.native_operation_status == s.native_readback_status == "NOT_RUN"
    assert s.native_qualification == "QSG_NATIVE_BACKEND_NOT_QUALIFIED"
    assert s.authorization_status == "NOT_PRODUCTION_AUTHORIZED"
    assert s.attachment_handle_status == "ATTACHMENT_HANDLE_UNVERIFIED"
    assert not s.global_uniqueness_proven and s.decision_scope == "OWNED_SYNTHETIC_FULL"
    assert s.write_admission_basis == "SYNTHETIC_ONLY_SCOPE_ACCEPT"
    assert s.scan_mode == "bounded" and s.scan_mode_domain == "configured_address_scope"
    assert s.acquisition_mode == "supplied_records" and s.external_acquisition_status == "NOT_RUN"
    assert s.scoring_mode == s.population_mode == "full"
    assert s.evaluation_status == "COMPLETE" and s.evaluation_completed and s.identity_reconciled
    assert s.population_complete and s.coverage_scope == "supplied_distinct_eligible_only"
    for key, value in e.counts.items(): assert s["evaluation_" + key] == value
    assert s.ranking_best_address == 0x100128 and s.ranking_best_score == 46
    assert s.ranking_second_score == -36 and s.ranking_score_gap == 82
    assert s.ranking_recommendation == "ACCEPT" and s.ranking_confidence == "HIGH"
    assert s.ranking_manual_review_required is False
    before = plain(api.evaluation()); e.result.best.final_score = -999
    assert plain(api.evaluation()) == before
    assert lua.globals().h.evaluations == 1
    assert "ce_mvp_readonly.lua" not in array(lua.globals().h.loaded)
    lua.execute(scripts[1]); w.clean()
    frozen = plain(w.loop.evidence()); w.step(200)
    assert plain(w.loop.evidence()) == frozen and not w.loop.status().running


def test_controlled_id1_full_exceeds_legacy_budget_without_changing_it(controlled_ct):
    lua, scripts, _ = controlled_ct
    api, w = start_controlled(lua, scripts)
    lua.execute("for i=4,129 do cw.object(0x100128+(i-1)*0x200,'weak') end")
    assert w.cfg.scan.scan_budget == w.cfg.scan.max_candidates == 128
    w.until_state("MONITORING")
    e = api.evaluation(); expected = {0x100128 + i * 0x200 for i in range(129)}
    assert e.counts.supplied == e.counts.ranked == 129
    for values in (e.identities.supplied, e.identities.distinct,
                   e.identities.eligible, e.collection.candidate_value_addrs):
        assert set(array(values)) == expected and len(values) == 129
    assert {r.candidate.value_addr for r in array(e.result.ranked)} == expected
    assert e.result.best.candidate.value_addr == 0x100128
    assert w.loop.status().raw_admission_budget is None and w.loop.status().ranking_budget is None
    assert lua.globals().h.evaluations == 1


@pytest.mark.parametrize("kind", ["review", "reject", "empty", "duplicates"])
def test_controlled_id1_complete_ranking_is_separate_from_operation_admission(controlled_ct, kind):
    lua, scripts, _ = controlled_ct
    lua.globals().kind = kind
    lua.execute("""
      h.inject=function(name,m)
        if name~='g1_alpha_population.example.lua' then return end
        if kind=='empty' then m.records={}
        elseif kind=='duplicates' then m.records[4]=m.records[1]; m.records[2].mapped=false
        elseif kind=='review' then
          for addr,bits in pairs(m.records[1].memory) do m.records[2].memory[addr+0x200]=bits end
        else
          for addr in pairs(m.records[1].memory) do
            if addr~=m.records[1].addr then m.records[1].memory[addr]=0 end
          end
        end
      end
    """)
    api, w = start_controlled(lua, scripts)
    w.until_state("MONITORING" if kind == "duplicates" else "ERROR")
    e = api.evaluation(); c = e.counts
    s = api.status()
    assert s.evaluation_status == e.status and s.evaluation_completed and s.identity_reconciled
    assert s.collection_phase == "supplied_full_complete"
    assert s.ranking_recommendation == e.result.recommendation.recommendation
    assert s.ranking_manual_review_required == e.result.recommendation.manual_review_required
    assert e.completed and e.population_complete
    assert c.supplied == c.distinct + c.duplicates and c.distinct == c.eligible + c.excluded
    assert c.eligible == c.selected == c.fully_scored == c.ranked
    if kind == "duplicates":
        assert (c.supplied, c.distinct, c.duplicates, c.eligible, c.excluded) == (4, 3, 1, 2, 1)
        assert set(array(e.identities.eligible)) == {0x100128, 0x100528}
    else:
        assert e.status == ("EMPTY" if kind == "empty" else "COMPLETE")
        assert e.result.recommendation.recommendation == ("REJECT" if kind == "empty" else kind.upper())
        if kind == "review": assert e.result.best.candidate.value_addr == 0x100128
        assert len(w.writes) == 0
        assert w.loop.status().stop_reason == ("ALPHA_STOP:NO_CANDIDATE" if kind == "empty" else "SCREENING_CALLBACK:CANDIDATE_NOT_QUALIFIED")
        w.clean()
    assert w.loop.status().rescan_attempts == 0


@pytest.mark.parametrize("fault", [
    "error('SYNTHETIC_RESOURCE_EXHAUSTED',0)", "error('SYNTHETIC_SCORING_EXCEPTION',0)",
    "r.ranked[2]=r.ranked[1]", "r.ranked[1].local_features=nil",
    "r.ranked[1].final_score=0/0", "H3A7_CE_MVP.stop()",
])
def test_controlled_id1_failure_cannot_publish_partial_or_stale_ranking(controlled_ct, fault):
    lua, scripts, _ = controlled_ct
    api, w = start_controlled(lua, scripts)
    w.until_state("MONITORING"); lua.execute(scripts[1]); w.clean()
    lua.execute("""
      h.inject=function(name,m)
        if name=='mvp0_candidate_report.lua' then
          local run=m.run
          m.run=function(...)
            local r=run(...)
            do """ + fault + """ end
            return r
          end
        end
      end
    """)
    api, w = start_controlled(lua, scripts)
    assert api.evaluation() is None
    w.step(40)
    assert not w.loop.status().running and w.loop.status().state in ("STOPPED", "ERROR")
    assert api.evaluation() is None and len(w.writes) == 0 and w.loop.status().result_ready is False
    assert api.status().evaluation_status == ("CANCELLED" if fault == "H3A7_CE_MVP.stop()" else "ERROR")
    assert not api.status().evaluation_completed and not api.status().identity_reconciled
    assert lua.globals().h.evaluations == 2
    w.step(200)
    assert lua.globals().h.evaluations == 2 and len(w.scans) == 0
    w.clean()


@pytest.mark.parametrize("fault", ["counts", "completion", "budget", "missing_word", "missing_input",
                                  "identity", "selected_identity", "nonfinite_score", "invalid_row"])
def test_controlled_id1_incomplete_or_invalid_input_never_operates(controlled_ct, fault):
    lua, scripts, _ = controlled_ct
    lua.globals().fault = fault
    lua.execute("""
      h.inject=function(name,m)
        if name=='g1_alpha_population.example.lua' then
          if fault=='budget' then m.options.scan_budget=1000000 end
          if fault=='missing_word' then m.records[1].memory[0x100158]=nil end
          if fault=='missing_input' then m.records=nil end
        elseif name=='mvp0_offline_scoring.lua' then
          local run=m.run
          m.run=function(...)
            local r=run(...)
            if fault=='counts' then r.counts.ranked=2
            elseif fault=='completion' then r.population_complete=false
            elseif fault=='identity' then r.identities.eligible[2]=r.identities.eligible[1]
            elseif fault=='selected_identity' then r.collection.candidate_value_addrs[2]=r.collection.candidate_value_addrs[1]
            elseif fault=='nonfinite_score' then r.result.ranked[1].final_score=0/0
            elseif fault=='invalid_row' then r.result.ranked[1].hard_pass=nil end
            return r
          end
        end
      end
    """)
    if fault == "missing_input":
        with pytest.raises(Exception, match="CONTROLLED_INPUT_MISSING"): start_controlled(lua, scripts)
        assert lua.globals().H3A7_CE_MVP.evaluation() is None
        return
    api, w = start_controlled(lua, scripts); w.step(40)
    assert w.loop.status().state == "ERROR" and not w.loop.status().running
    assert api.evaluation() is None and len(w.writes) == 0 and w.loop.status().result_ready is False
    assert api.status().evaluation_status == "ERROR" and not api.status().population_complete
    w.clean()


@pytest.mark.parametrize("fault", ["unmapped", "unreadable", "structure", "identity", "exit",
                                  "write", "readback", "prewrite", "cleanup"])
def test_controlled_id1_faults_preserve_gates_cleanup_and_stop_policy(controlled_ct, fault):
    lua, scripts, _ = controlled_ct
    api, w = start_controlled(lua, scripts)
    if fault == "write": w.fail.write_nil = True
    elif fault == "readback": w.fail.write_no_change = True
    if fault == "prewrite":
        w.until_state("WRITING"); w.objects[1].memory[0x100128] = 0x42280000
    elif fault not in ("write", "readback"):
        w.until_state("MONITORING")
        if fault == "unmapped": w.objects[1].mapped = False
        elif fault == "unreadable": w.objects[1].readable = False
        elif fault == "structure": w.objects[1].memory[0x100158] = 8
        elif fault == "identity": w.creation += 1
        elif fault == "exit": w.alive = False
        else: w.fail.close = True; api.stop()
    w.step(40); s = w.loop.status()
    assert s.state == "ERROR" and not s.running and s.rescan_attempts == 0
    assert s.retry_at is None and s.candidate_address is None
    if fault == "cleanup":
        assert not s.cleanup_ok and api.start() == (False, "CLEANUP_UNCERTAIN_RELOAD_CE")
    else: assert s.cleanup_ok
    if fault == "prewrite": assert len(w.writes) == 0 and s.stop_reason == "PREWRITE_CANDIDATE_CHANGED"
    before = (w.reads, len(w.writes), w.open_calls, len(w.scans))
    w.object(0x101128); w.step(200)
    assert (w.reads, len(w.writes), w.open_calls, len(w.scans)) == before
    w.clean()


@pytest.mark.parametrize("fault,operation,readback", [
    ("none", "API_SUCCEEDED", "VERIFIED"),
    ("write_false", "FAILED", "NOT_RUN"),
    ("write_throw", "ATTEMPTED_UNCONFIRMED", "NOT_RUN"),
    ("bits_mismatch", "API_SUCCEEDED", "MISMATCH"),
    ("float_mismatch", "API_SUCCEEDED", "MISMATCH"),
    ("missing", "API_SUCCEEDED", "FAILED"),
    ("read_throw", "API_SUCCEEDED", "ATTEMPTED_UNCONFIRMED"),
])
def test_id2_keeps_operation_readback_and_monitor_outcomes_independent(
        controlled_ct, fault, operation, readback):
    lua, scripts, _ = controlled_ct
    api, w = start_controlled(lua, scripts)
    assert api.status().operation_status == api.status().readback_status == "NOT_RUN"
    if fault == "write_false": w.fail.write_nil = True
    elif fault == "write_throw": w.fail.write = "throw"
    elif fault == "bits_mismatch": w.fail.write_no_change = True
    elif fault == "float_mismatch": w.fail.readback_float = 42.0
    elif fault in ("missing", "read_throw"):
        lua.globals().outcome_fault = fault
        lua.execute("""
          cw.hook=function(event)
            if #cw.writes>0 then
              if outcome_fault=='missing' then cw.fail.unreadable=0x100128
              elseif event=='read_float' then error('READBACK_TEST_FAILURE',0) end
            end
          end
        """)
    w.step(40)
    s = api.status()
    assert (s.operation_status, s.readback_status) == (operation, readback)
    if fault == "none":
        assert s.monitor_status == "VALID"
        w.objects[1].mapped = False
        w.step(40)
        assert api.status().monitor_status == "INVALID"
    assert not api.status().running and api.status().cleanup_ok
    before = (w.reads, len(w.writes), len(w.scans), w.open_calls)
    for code in scripts[2:4]: lua.execute(code)
    w.step(100)
    assert (w.reads, len(w.writes), len(w.scans), w.open_calls) == before
    assert api.status().readback_status == readback
    # Outcomes describe this run only; an explicit new Start has fresh caches.
    lua.execute(scripts[1]); lua.execute(scripts[0])
    assert api.status().operation_status == api.status().readback_status == "NOT_RUN"
    api.stop()
    w.clean()


def test_controlled_id1_actual_allocator_failure_does_not_report_completion(controlled_ct):
    lua, scripts, _ = controlled_ct
    original_limit = lua.get_max_memory()
    lua.globals().tight_limit = lambda: lua.set_max_memory(lua.get_memory_used() + 8192)
    lua.execute("""
      h.inject=function(name,m)
        if name=='mvp0_candidate_report.lua' then
          m.score_candidate=function() tight_limit(); string.rep('x',65536) end
        end
      end
    """)
    api, w = start_controlled(lua, scripts)
    try:
        w.step(4)
    finally:
        lua.set_max_memory(original_limit)
    assert w.loop.status().state == "ERROR" and not w.loop.status().running
    assert "memory" in w.loop.status().stop_reason.lower()
    assert api.evaluation() is None and len(w.writes) == 0
    assert not w.loop.status().result_ready and w.loop.status().cleanup_ok
    w.step(200); w.clean()


def test_controlled_id1_failed_restart_clears_previous_ranking(controlled_ct):
    lua, scripts, source_dir = controlled_ct
    api, w = start_controlled(lua, scripts)
    w.until_state("MONITORING"); lua.execute(scripts[1]); w.clean()
    (source_dir / "examples/g1_alpha_population.example.lua").unlink()
    with pytest.raises(Exception, match="g1_alpha_population.example.lua"):
        lua.execute(scripts[0])
    assert api.evaluation() is None and api.controlled_fixture() is None
    assert api.status().startup_error and not api.status().running


def test_controlled_mode_cannot_switch_to_native_or_qualification(controlled_ct):
    lua, scripts, _ = controlled_ct
    api, w = start_controlled(lua, scripts)
    api.stop(); w.clean()
    for mode in ("NORMAL", "QUALIFICATION", "ENGINEERING_BOUNDED"):
        assert api.configure_execution(lua.table_from({"mode": mode})) == (False, "QSG_MODE_LOCKED")


def test_controlled_preparation_requires_existing_fixture_without_overwriting(tmp_path):
    source_dir = portable_source(tmp_path)
    path = prepare(source_dir); previous = path.read_bytes()
    with pytest.raises(ValueError, match="MISSING_CONTROLLED_FIXTURE"):
        prepare(source_dir, alpha_controlled=True)
    assert path.read_bytes() == previous


def test_standard_default_requires_explicit_input_without_config_or_native_fallback(controlled_ct):
    lua, scripts, source_dir = controlled_ct
    scripts = table_lua(prepare(source_dir))  # ordinary generation, no controlled flag
    assert "local controlled=false" in scripts[0]
    lua.globals().syntaxcheck = True
    for script in scripts: lua.execute(script)
    assert len(lua.globals().h.loaded) == 0
    lua.globals().syntaxcheck = False
    api = lua.execute("return dofile(test_entry_path)")
    before = len(lua.globals().h.loaded)
    assert api.status().execution_mode == "ALPHA_STANDARD"
    assert api.status().product_profile == "ALPHA_FULL"
    assert api.controlled_fixture() is None and api.evaluation() is None
    assert len(lua.globals().h.loaded) == before
    with pytest.raises(Exception, match="ALPHA_INPUT_REQUIRED"):
        lua.execute(scripts[0])
    s = api.status()
    assert s.state == "ERROR" and not s.running and s.data_provenance == "UNAVAILABLE"
    assert s.action_permitted is False and s.automatic_recovery is False
    assert s.evaluation_status == "ERROR" and not s.evaluation_completed and not s.identity_reconciled
    assert api.evaluation() is None and lua.globals().h.evaluations == 0
    assert len(lua.globals().h.loaded) == 0  # dofile itself does not call the loadfile hook
    assert s.config_source == "LOCAL_CONFIG" and s.config_admission == "REJECTED"
    assert s.config_error == "ALPHA_CONFIG_MISSING" and lua.globals().h.config_reads == 1
    for mode in ("ALPHA_CONTROLLED", "ENGINEERING_BOUNDED", "QUALIFICATION"):
        assert api.configure_execution(lua.table_from({"mode": mode})) == (False, "QSG_MODE_LOCKED")


@pytest.mark.parametrize("selection", [
    {"mode": "ALPHA_STANDARD"},
    {"mode": "ALPHA_STANDARD", "input_source": "native"},
    {"mode": "ALPHA_STANDARD", "input_source": "OWNED_SYNTHETIC", "factory": True},
    {"mode": "ALPHA_CONTROLLED", "input_source": "OWNED_SYNTHETIC"},
    {"mode": "ENGINEERING_BOUNDED", "input_source": "OWNED_SYNTHETIC"},
])
def test_invalid_explicit_selection_latches_fail_closed(controlled_ct, selection):
    lua, _, source_dir = controlled_ct
    alpha_config(source_dir)  # A valid local config must not repair an invalid API selection.
    api = lua.execute("return dofile(test_entry_path)")
    accepted, reason = api.configure_execution(lua.table_from(selection))
    assert accepted is False
    assert api.start()[0] is False
    assert reason in api.status().startup_error
    assert api.controlled_fixture() is None and api.evaluation() is None
    assert api.configure_execution(lua.table_from({"mode": "QUALIFICATION"})) == (False, "QSG_MODE_LOCKED")
    assert len(lua.globals().h.loaded) == 0
    assert lua.globals().h.config_reads == 0


def test_id2_observes_standard_or_controlled_state_without_work(controlled_ct):
    lua, scripts, _ = controlled_ct
    api, w = start_controlled(lua, scripts)
    for phase in ("pending", "completed", "stopped"):
        if phase == "completed": w.until_state("MONITORING")
        if phase == "stopped": lua.execute(scripts[1])
        before = (w.reads, len(w.writes), w.open_calls, len(w.scans), len(w.native_calls),
                  lua.globals().h.evaluations, plain(api.evidence()))
        lua.execute(scripts[2]); lua.execute(scripts[3])
        assert (w.reads, len(w.writes), w.open_calls, len(w.scans), len(w.native_calls),
                lua.globals().h.evaluations, plain(api.evidence())) == before
        s = api.status()
        assert s.evaluation_status == ("NOT_RUN" if phase == "pending" else "COMPLETE")
        assert s.evaluation_completed == (phase != "pending")
    lines = "\n".join(array(lua.globals().h.lines))
    for text in ("scoring_mode=full", "scan_mode_domain=configured_address_scope",
                 "evaluation_ranked=3", "ranking_recommendation=ACCEPT"):
        assert text in lines


def alpha_config(source_dir, text=None):
    path = source_dir / "ce_mvp_config.local.lua"
    if text is None:
        text = (source_dir / "ce_mvp_alpha_config.example.lua").read_text(encoding="utf-8")
    path.write_text(text, encoding="utf-8")
    return path


def test_f01_normal_id1_uses_bound_config_without_api_selection(standard_ct, tmp_path, monkeypatch):
    lua, scripts, source_dir = standard_ct
    private = alpha_config(source_dir); original = private.read_bytes()
    # A different CWD, containing an invalid decoy, must not select the config.
    (tmp_path / private.name).write_text("PRIVATE_CWD_DECOY", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    lua.globals().syntaxcheck = True
    for script in scripts: lua.execute(script)
    lua.globals().syntaxcheck = False
    lua.execute(scripts[2]); lua.execute(scripts[3])
    assert lua.globals().H3A7_CE_MVP is None and lua.globals().h.config_reads == 0
    # Actual default generated CT ID1, no preceding configure_execution call.
    assert "local controlled=false" in scripts[0]
    lua.execute(scripts[0])
    api = lua.globals().H3A7_CE_MVP; w = api.controlled_fixture()
    assert lua.globals().h.config_reads == 1
    assert lua.globals().h.config_path == private.as_posix()
    w.until_state("MONITORING")
    s = api.status(); e = api.evaluation()
    assert s.config_source == "LOCAL_CONFIG" and s.config_admission == "ACCEPTED" and s.config_error is None
    assert s.execution_mode == "ALPHA_STANDARD" and s.input_source == "OWNED_SYNTHETIC"
    assert s.data_provenance == "synthetic" and s.lifecycle_policy == "ALPHA_STOP_ONLY"
    assert e.completed and e.population_mode == "full" and e.counts.ranked == 3
    assert e.result.best.final_score == 46 and e.result.second.final_score == -36
    assert s.action_permitted is False and s.native_operation_status == "NOT_RUN"
    assert s.native_readback_status == "NOT_RUN" and s.external_acquisition_status == "NOT_RUN"
    before = (w.reads, len(w.writes), w.open_calls, len(w.scans), lua.globals().h.evaluations)
    for script in scripts[2:4]: lua.execute(script)
    assert before == (w.reads, len(w.writes), w.open_calls, len(w.scans), lua.globals().h.evaluations)
    assert api.start() == (False, "ALREADY_RUNNING") and lua.globals().h.config_reads == 1
    for mode in ("ALPHA_CONTROLLED", "ENGINEERING_BOUNDED", "QUALIFICATION"):
        assert api.configure_execution(lua.table_from({"mode": mode})) == (False, "QSG_MODE_LOCKED")
    lua.execute(scripts[1]); w.clean()
    lua.execute(scripts[0])  # An explicit clean restart revalidates the same permitted selection.
    fresh = api.controlled_fixture(); fresh.until_state("MONITORING")
    assert lua.globals().h.config_reads == 2 and lua.globals().h.evaluations == 2
    lua.execute(scripts[1]); fresh.clean()
    prior = (fresh.reads, len(fresh.writes), fresh.open_calls, len(fresh.scans))
    lua.execute(scripts[4]); lua.execute(scripts[5])  # ID3 stays independent/read-only.
    assert prior == (fresh.reads, len(fresh.writes), fresh.open_calls, len(fresh.scans))
    assert lua.globals().h.config_reads == 2 and private.read_bytes() == original


@pytest.mark.parametrize("text,reason", [
    ("return nil", "SHAPE"), ("return function() end", "SHAPE"),
    ("return 'PRIVATE_VALUE'", "SHAPE"), ("return {", "SYNTAX"),
    ("return missing.PRIVATE_VALUE", "EVALUATION_FAILED"),
    ("return {}", "REQUIRED_FIELD"),
    ("return {schema='g1.alpha.config.v1',mode='ALPHA_STANDARD'}", "REQUIRED_FIELD"),
    ("return {mode='ALPHA_STANDARD',input_source='OWNED_SYNTHETIC'}", "REQUIRED_FIELD"),
    ("return {schema='g1.alpha.config.v1',input_source='OWNED_SYNTHETIC'}", "REQUIRED_FIELD"),
    ("return {schema=1,mode='ALPHA_STANDARD',input_source='OWNED_SYNTHETIC'}", "FIELD_TYPE"),
    ("return {schema='g1.alpha.config.v1',mode={},input_source='OWNED_SYNTHETIC'}", "FIELD_TYPE"),
    ("return {schema='g1.alpha.config.v1',mode='ALPHA_STANDARD',input_source=function() end}", "FIELD_TYPE"),
    ("return {schema='v2',mode='ALPHA_STANDARD',input_source='OWNED_SYNTHETIC'}", "SCHEMA"),
    ("return {schema='g1.alpha.config.v1',mode='ENGINEERING_BOUNDED',input_source='OWNED_SYNTHETIC'}", "MODE"),
    ("return {schema='g1.alpha.config.v1',mode='QUALIFICATION',input_source='OWNED_SYNTHETIC'}", "MODE"),
    ("return {schema='g1.alpha.config.v1',mode='ALPHA_CONTROLLED',input_source='OWNED_SYNTHETIC'}", "MODE"),
    ("return {schema='g1.alpha.config.v1',mode='ALPHA_STANDARD',input_source='PRIVATE_VALUE'}", "INPUT"),
    ("return {schema='g1.alpha.config.v1',mode='ALPHA_STANDARD',input_source='OWNED_SYNTHETIC',PRIVATE_FIELD='PRIVATE_VALUE'}", "UNKNOWN_FIELD"),
    ("return {schema='g1.alpha.config.v1',mode='ALPHA_STANDARD',input_source='OWNED_SYNTHETIC',factory=function() end}", "UNKNOWN_FIELD"),
    ("return {schema='g1.alpha.config.v1',mode='ALPHA_STANDARD',input_source='OWNED_SYNTHETIC',write_enabled=true}", "UNKNOWN_FIELD"),
])
def test_f01_invalid_config_rejects_before_fixture_and_sanitizes_id2(standard_ct, text, reason):
    lua, scripts, source_dir = standard_ct
    private = alpha_config(source_dir, text); original = private.read_bytes()
    api = lua.execute("return dofile(test_entry_path)")
    assert api.status().config_admission == "NOT_CHECKED" and lua.globals().h.config_reads == 0
    reason = "ALPHA_CONFIG_" + reason
    with pytest.raises(Exception, match=reason): lua.execute(scripts[0])
    s = api.status()
    assert s.config_admission == "REJECTED" and s.config_source == "LOCAL_CONFIG" and s.config_error == reason
    assert s.startup_error == reason and s.input_source is None and s.data_provenance == "UNAVAILABLE"
    assert s.evaluation_status == "ERROR" and not s.evaluation_completed and not s.running
    assert api.controlled_fixture() is None and api.evaluation() is None
    assert lua.globals().h.evaluations == 0 and len(lua.globals().h.loaded) == 0
    for script in scripts[2:4]: lua.execute(script)
    assert lua.globals().h.config_reads == 1 and private.read_bytes() == original
    lines = "\n".join(array(lua.globals().h.lines))
    assert "PRIVATE_" not in lines and source_dir.as_posix() not in lines
    assert "config_error=" + reason in lines
    alpha_config(source_dir)  # Repair on disk cannot bypass the failed selection latch.
    assert api.start()[0] is False and lua.globals().h.config_reads == 1
    assert api.configure_execution(lua.table_from({"mode": "ALPHA_STANDARD", "input_source": "OWNED_SYNTHETIC"})) == (False, "QSG_MODE_LOCKED")


@pytest.mark.parametrize("fault", ["denied", "open_throws", "read_nil", "read_throws", "close_nil"])
def test_f01_unreadable_config_has_no_path_or_os_error_leak(standard_ct, fault):
    lua, scripts, source_dir = standard_ct
    private = alpha_config(source_dir); original = private.read_bytes()
    lua.globals().config_fault = fault
    lua.execute("""
      io.open=function()
        h.config_reads=h.config_reads+1
        if config_fault=='denied' then return nil,'PRIVATE_OS_PATH',13 end
        if config_fault=='open_throws' then error('PRIVATE_OS_PATH') end
        return {
          read=function()
            if config_fault=='read_throws' then error('PRIVATE_OS_PATH') end
            if config_fault=='close_nil' then return 'return {}' end
            return nil,'PRIVATE_OS_PATH'
          end,
          close=function() h.closed=true; if config_fault~='close_nil' then return true end end
        }
      end
    """)
    with pytest.raises(Exception, match="ALPHA_CONFIG_UNREADABLE"): lua.execute(scripts[0])
    api = lua.globals().H3A7_CE_MVP
    assert api.status().config_error == "ALPHA_CONFIG_UNREADABLE"
    assert api.controlled_fixture() is None and len(lua.globals().h.loaded) == 0
    assert lua.globals().h.evaluations == 0 and private.read_bytes() == original
    if fault not in ("denied", "open_throws"): assert lua.globals().h.closed
    assert "PRIVATE_OS_PATH" not in "\n".join(array(lua.globals().h.lines))


@pytest.mark.parametrize("missing", [False, True])
def test_f01_config_error_after_clean_stop_clears_completed_result(standard_ct, missing):
    lua, scripts, source_dir = standard_ct
    private = alpha_config(source_dir)
    lua.execute(scripts[0]); api = lua.globals().H3A7_CE_MVP; w = api.controlled_fixture()
    w.until_state("MONITORING"); assert api.evaluation().completed
    if missing: private.unlink()
    else: private.write_text("return {}", encoding="utf-8")
    # Edits are not evaluated by ID2 or by a rejected running Start.
    lua.execute(scripts[2]); assert api.start() == (False, "ALREADY_RUNNING")
    assert lua.globals().h.config_reads == 1
    lua.execute(scripts[1]); w.clean()
    loaded = len(lua.globals().h.loaded)
    with pytest.raises(Exception, match="ALPHA_INPUT_REQUIRED" if missing else "ALPHA_CONFIG_REQUIRED_FIELD"):
        lua.execute(scripts[0])
    assert lua.globals().h.config_reads == 2 and len(lua.globals().h.loaded) == loaded
    assert lua.globals().h.evaluations == 1 and api.evaluation() is None and api.controlled_fixture() is None
    s = api.status()
    assert s.evaluation_status == "ERROR" and not s.evaluation_completed and not s.identity_reconciled
    assert s.ranking_best_address is None and s.config_admission == "REJECTED"
    alpha_config(source_dir)
    with pytest.raises(Exception, match="ALPHA_"): lua.execute(scripts[0])
    assert lua.globals().h.config_reads == 2  # Reloading the same singleton cannot repair the latch.


def test_f01_cleanup_uncertainty_precedes_config_read(standard_ct):
    lua, scripts, source_dir = standard_ct
    alpha_config(source_dir)
    lua.execute(scripts[0]); api = lua.globals().H3A7_CE_MVP; w = api.controlled_fixture()
    w.until_state("MONITORING"); w.fail.close = True; api.stop()
    alpha_config(source_dir, "return {}")
    assert api.start() == (False, "CLEANUP_UNCERTAIN_RELOAD_CE")
    assert lua.globals().h.config_reads == 1 and not api.status().cleanup_ok
    assert api.status().config_admission == "ACCEPTED"


@pytest.mark.parametrize("text", ["return {}", "return {schema='g1.alpha.config.v1',mode='QUALIFICATION'}"])
def test_f01_explicit_selection_takes_precedence_without_reading_config(controlled_ct, text):
    lua, scripts, source_dir = controlled_ct
    private = alpha_config(source_dir, text)
    api, w = start_controlled(lua, scripts); w.until_state("MONITORING")
    assert api.status().config_source == "EXPLICIT_API" and api.status().config_admission == "ACCEPTED"
    assert lua.globals().h.config_reads == 0 and private.read_text(encoding="utf-8") == text


def original_config(source_dir, edit="", *, owned=False):
    # Exercise the maintained original template, not a parallel test schema.
    template = (source_dir / "ce_mvp_config.example.lua").read_text(encoding="utf-8")
    selection = "c.input_source='OWNED_SYNTHETIC';" if owned else ""
    return alpha_config(source_dir, "local c=(function()\n" + template
                        + "\nend)(); " + selection + edit + "; return c")


@pytest.mark.parametrize("version", ["lua53", "lua54"])
def test_f01_r1_contract_validation_keeps_original_execution_guards(version):
    lua, w = make_runtime(version)
    c = lua.execute((SRC / "ce_mvp_config.example.lua").read_text(encoding="utf-8"))
    validated = w.core.validate_contract(c)
    assert validated.target_pid == 0 and validated.write_enabled is False
    with pytest.raises(Exception, match="INVALID_TARGET_PID"): w.core.validate(c)
    c.target_pid = 101
    with pytest.raises(Exception, match="WRITE_DISABLED"): w.core.validate(c)
    c.write_enabled = True
    assert plain(w.core.validate(c)) == plain(w.core.validate_contract(c))


def test_standard_original_config_reaches_full_adapter_but_never_unqualified_ce(standard_ct):
    lua, scripts, source_dir = standard_ct
    original_config(source_dir, "c.target_pid=7654321;c.write_enabled=true;c.write_value=137.25;c.monitor_interval_ms=250")
    lua.execute("""
      h.inject=function(name,m)
        if name=='ce_mvp_adapter.lua' then
          local new=m.new
          m.new=function(cfg,ce,loader,source,execution,mode)
            assert(cfg.target_pid==7654321 and cfg.write_value==137.25)
            assert(cfg.monitor_interval_ms==250 and cfg.scan.mode=='process')
            assert(cfg.scan.target_bits==0x42C80000 and mode=='full')
            assert(source==nil and execution==nil)
            h.standard_adapter_calls=(h.standard_adapter_calls or 0)+1
            return new(cfg,ce,loader,source,execution,mode)
          end
        end
      end
    """)
    with pytest.raises(Exception, match="QSG_NATIVE_BACKEND_NOT_QUALIFIED"):
        lua.execute(scripts[0])
    api = lua.globals().H3A7_CE_MVP
    assert lua.globals().h.standard_adapter_calls == 1
    s = api.status()
    assert s.input_source == "CONFIGURED_TARGET" and s.acquisition_mode == "configured_target_scan"
    assert s.config_application == "NOT_APPLIED" and not s.acquisition_complete
    assert s.acquisition_evidence == "NOT_ESTABLISHED" and s.operation_status == "NOT_RUN"
    assert s.readback_status == "NOT_RUN" and s.native_operation_status == "NOT_RUN"
    for code in scripts[2:4]: lua.execute(code)
    assert lua.globals().h.standard_adapter_calls == 1 and lua.globals().h.config_reads == 1
    assert api.controlled_fixture() is None and lua.globals().h.forbidden == 0


@pytest.mark.parametrize("source", [None, "CE", "synthetic"])
def test_full_adapter_requires_existing_qualified_execution_before_ce_api_access(source):
    lua, w = make_runtime("lua53")
    with pytest.raises(Exception, match="QSG_NATIVE_BACKEND_NOT_QUALIFIED"):
        w.adapter_module.new(w.core.validate(w.cfg), w.ce, w.load, source, None, "full")
    assert w.open_calls == w.reads == len(w.native_calls) == len(w.writes) == 0


@pytest.mark.parametrize("edit,reason,readiness", [
    ("", "ALPHA_CONFIG_TARGET_REQUIRED", "BLOCKED_SAFE_DEFAULT"),
    ("c.target_pid=101", "WRITE_DISABLED", "BLOCKED_CONFIGURED_INTENT"),
    ("c.target_pid=7654321;c.write_enabled=true", "QSG_NATIVE_BACKEND_NOT_QUALIFIED", "BLOCKED_QUALIFICATION"),
    ("c.target_pid=7654321;c.write_enabled=true;c.input_source='OWNED_SYNTHETIC'",
     "ALPHA_SYNTHETIC_IDENTITY_MISMATCH", "BLOCKED_CAPABILITY"),
    ("c.target_pid=101;c.write_enabled=true;c.input_source='PRIVATE_VALUE'",
     "ALPHA_CONFIG_INPUT_UNSUPPORTED", "BLOCKED_CAPABILITY"),
    ("c.scan.start_address='0x100000';c.scan.stop_address='0x11FFFF'",
     "ALPHA_PROFILE_BOUNDED_SCOPE", "BLOCKED_PROFILE"),
    ("c.diagnostics={enabled=true,session_token='PRIVATE_VALUE',event_limit=32,cleanup_start_probe=true}",
     "ALPHA_PROFILE_QUALIFICATION_PROBE", "BLOCKED_PROFILE"),
])
def test_f01_r1_valid_contract_is_not_capability_or_authorization(standard_ct, edit, reason, readiness):
    lua, scripts, source_dir = standard_ct
    private = original_config(source_dir, edit); before = private.read_bytes()
    for code in scripts[2:4]: lua.execute(code)
    assert lua.globals().h.config_reads == 0
    with pytest.raises(Exception, match=reason): lua.execute(scripts[0])
    api = lua.globals().H3A7_CE_MVP; s = api.status()
    assert s.config_file_status == "READ" and s.config_contract == "ORIGINAL"
    assert s.config_validation == "VALID" and s.config_admission == "ACCEPTED"
    assert s.config_application == "NOT_APPLIED" and s.execution_readiness == readiness
    assert s.config_error is None and s.config_block == reason
    assert s.authorization_status == "NOT_PRODUCTION_AUTHORIZED" and not s.action_permitted
    assert s.native_qualification == "QSG_NATIVE_BACKEND_NOT_QUALIFIED"
    assert s.qualification == "IMPLEMENTED_PENDING_CE_QUALIFICATION"
    assert s.attachment_handle_status == "ATTACHMENT_HANDLE_UNVERIFIED"
    assert api.controlled_fixture() is None and api.evaluation() is None
    assert ("ce_mvp_adapter.lua" in array(lua.globals().h.loaded)) == (readiness == "BLOCKED_QUALIFICATION")
    assert lua.globals().h.evaluations == 0
    for code in scripts[2:4]: lua.execute(code)
    assert lua.globals().h.config_reads == 1 and private.read_bytes() == before
    lines = "\n".join(array(lua.globals().h.lines))
    assert "PRIVATE_VALUE" not in lines and "7654321" not in lines and source_dir.as_posix() not in lines
    original_config(source_dir, "c.target_pid=101;c.write_enabled=true", owned=True)
    assert api.start() == (False, reason) and lua.globals().h.config_reads == 1


@pytest.mark.parametrize("edit,reason", [
    ("c.PRIVATE_FIELD='PRIVATE_VALUE'", "UNKNOWN_CONFIG_FIELD"),
    ("c.scan.PRIVATE_FIELD='PRIVATE_VALUE'", "UNKNOWN_SCAN_FIELD"),
    ("c.diagnostics.PRIVATE_FIELD='PRIVATE_VALUE'", "UNKNOWN_DIAGNOSTICS_FIELD"),
    ("c.engineering_extensions.PRIVATE_FIELD=false", "UNKNOWN_EXTENSION_FIELD"),
    ("c.engineering_extensions.strict_attachment=true", "UNSUPPORTED_ENGINEERING_EXTENSION"),
    ("c.target_pid=nil", "INVALID_TARGET_PID"),
    ("c.target_pid='PRIVATE_VALUE'", "INVALID_TARGET_PID"),
    ("c.write_enabled='PRIVATE_VALUE'", "INVALID_WRITE_ENABLED"),
    ("c.screening_profile='full'", "UNSUPPORTED_PROFILE"),
    ("c.value_type='double'", "UNSUPPORTED_VALUE_TYPE"),
    ("c.write_value=0/0", "INVALID_FLOAT32"),
    ("c.scan={}", "INVALID_FLOAT32"),
    ("c.scan.target_value_pattern=0", "SCAN_PATTERN_MISMATCH"),
    ("c.scan.scan_budget=65537", "INVALID_SCAN_SETTINGS"),
    ("c.scan.max_candidates=129", "INVALID_SCAN_SETTINGS"),
    ("c.scan.process_candidate_limit=128", "OBSOLETE_PROCESS_BUDGET_USE_LEGACY_INTAKE_SETTINGS"),
    ("c.scan.collection_slice_ms=26", "INVALID_COLLECTION_BUDGET"),
    ("c.max_rescan_attempts=-1", "INVALID_MAX_RESCAN_ATTEMPTS"),
    ("c.monitor_interval_ms=0", "INVALID_MONITOR_INTERVAL_MS"),
    ("c.scan_timeout_ms=0", "INVALID_SCAN_TIMEOUT_MS"),
    ("c.log_path='PRIVATE_VALUE'", "INVALID_LOG_PATH"),
    ("c.diagnostics={enabled=true}", "INVALID_DIAGNOSTICS"),
    ("c.input_source=function() end", "ALPHA_CONFIG_FIELD_TYPE"),
])
def test_f01_r1_original_validator_rejections_are_sanitized(standard_ct, edit, reason):
    lua, scripts, source_dir = standard_ct
    original_config(source_dir, edit)
    with pytest.raises(Exception, match=reason): lua.execute(scripts[0])
    api = lua.globals().H3A7_CE_MVP; s = api.status()
    assert s.config_contract == "ORIGINAL" and s.config_validation == "INVALID"
    assert s.config_error == reason and s.config_application == "NOT_APPLIED"
    assert api.controlled_fixture() is None and lua.globals().h.evaluations == 0
    assert "ce_mvp_adapter.lua" not in array(lua.globals().h.loaded)
    assert "PRIVATE_" not in "\n".join(array(lua.globals().h.lines))


def test_f01_r1_original_fields_reach_existing_consumers_without_fixture_defaults(standard_ct):
    lua, scripts, source_dir = standard_ct
    log = source_dir.parent / "owned-runtime.log"
    private = original_config(source_dir, """
      c.target_pid=101;c.write_enabled=true;c.write_value=137.25
      c.monitor_interval_ms=250;c.invalid_confirmations=20
      c.scan.scan_budget=1;c.scan.max_candidates=1
      c.scan.collection_batch_size=16;c.scan.collection_slice_ms=1
      c.log_limit=16;c.log_path=[[%s]]
      c.diagnostics={enabled=true,session_token='PRIVATE_VALUE',event_limit=32}
    """ % log, owned=True)
    before = private.read_bytes()
    lua.execute("""
      h.inject=function(name,m)
        if name=='mvp0_offline_scoring.lua' then
          local run=m.run
          m.run=function(records,opts,...) h.consumer_options=opts; return run(records,opts,...) end
        end
      end
    """)
    lua.execute(scripts[0]); api = lua.globals().H3A7_CE_MVP; w = api.controlled_fixture()
    assert api.status().raw_admission_budget is None and api.status().ranking_budget is None
    w.until_state("MONITORING")
    # Observe actual downstream operations/results, separately from admission labels.
    assert w.loop.status().last_written == w.loop.status().last_readback == 137.25
    assert len(w.writes) == 1 and len(w.scans) == 0
    assert api.evaluation().counts.ranked == 3  # no bounded fallback to 1
    opts = lua.globals().h.consumer_options
    assert opts.population_mode == "full" and opts.scan_budget is None and opts.max_candidates is None
    assert opts.target_value_pattern == 0x42C80000 and opts.target_value_float == 100.0
    assert opts.filter_target_match and opts.use_prescore_selection
    w.step(4); assert w.loop.status().monitor_checks == 0
    w.step(1); assert w.loop.status().monitor_checks == 1
    assert api.evidence().session_token == "PRIVATE_VALUE" and len(api.evidence().events) <= 32
    assert log.exists() and "written=137.25" in log.read_text()
    frozen = (w.reads, len(w.writes), w.open_calls, len(w.scans), lua.globals().h.evaluations,
              lua.globals().h.config_reads, plain(api.evidence()), log.read_bytes())
    s = api.status()
    assert s.config_application == "APPLIED_OWNED_SYNTHETIC" and s.runtime_capability == "OWNED_SYNTHETIC_ONLY"
    assert s.config_effects.invalid_confirmations == "ENGINEERING_ONLY_STOP_FIRST"
    assert s.config_effects["scan.scan_budget"] == "ENGINEERING_ONLY_FULL_POPULATION"
    assert s.pid is None and s.events is None and s.last_written is None
    s.config_effects.write_value = "FORGED"
    for code in scripts[2:4]: lua.execute(code)
    assert api.status().config_effects.write_value == "APPLIED_OWNED_SYNTHETIC"
    assert frozen == (w.reads, len(w.writes), w.open_calls, len(w.scans), lua.globals().h.evaluations,
                      lua.globals().h.config_reads, plain(api.evidence()), log.read_bytes())
    lines = "\n".join(array(lua.globals().h.lines))
    assert "PRIVATE_VALUE" not in lines and "137.25" not in lines and str(log) not in lines
    # Alpha ignores historical delay/recovery knobs explicitly: stop on first fault.
    w.objects[1].mapped = False; w.step(5)
    assert not w.loop.status().running and w.loop.status().invalid_count == 1
    assert w.loop.status().rescan_attempts == 0 and not w.loop.status().automatic_recovery
    assert len(w.lines) <= 16 and len(log.read_text().splitlines()) <= 16
    w.clean(); assert private.read_bytes() == before
    prior = (w.reads, len(w.writes), w.open_calls, lua.globals().h.config_reads)
    lua.execute(scripts[4]); lua.execute(scripts[5])
    assert prior == (w.reads, len(w.writes), w.open_calls, lua.globals().h.config_reads)


def test_f01_r1_configured_search_bits_filter_unchanged_owned_records(standard_ct):
    lua, scripts, source_dir = standard_ct
    original_config(source_dir, """
      c.target_pid=101;c.write_enabled=true
      c.scan.target_value_float=42;c.scan.target_value_pattern=0x42280000
    """, owned=True)
    lua.execute(scripts[0]); api = lua.globals().H3A7_CE_MVP; w = api.controlled_fixture()
    w.step(20)
    assert api.evaluation().counts.eligible == api.evaluation().counts.ranked == 0
    assert api.evaluation().status == "EMPTY" and len(w.writes) == 0
    assert w.objects[1].memory[w.objects[1].addr] == 0x42C80000  # never rewrite input to fit config
    assert "NO_CANDIDATE" in w.loop.status().stop_reason
    assert not api.status().running and not api.status().action_permitted
    w.clean()


def test_f01_r1_configured_timeout_and_checkpoint_budget_are_effective(standard_ct):
    lua, scripts, source_dir = standard_ct
    original_config(source_dir, """
      c.target_pid=101;c.write_enabled=true;c.scan_timeout_ms=1000
      c.scan.collection_batch_size=16;c.scan.collection_slice_ms=1
    """, owned=True)
    lua.execute(scripts[0]); api = lua.globals().H3A7_CE_MVP; w = api.controlled_fixture()
    w.step(3)  # supplied evaluation + qualifier checks yield at the configured checkpoint
    assert w.loop.status().state == "SCREENING" and len(w.writes) == 0
    w.time = w.time + 1000; w.step()
    assert w.loop.status().stop_reason == "SCAN_TIMEOUT" and len(w.writes) == 0
    w.clean()


def test_f01_r1_clean_restart_revalidates_original_and_clears_applied_state(standard_ct):
    lua, scripts, source_dir = standard_ct
    original_config(source_dir, "c.target_pid=101;c.write_enabled=true", owned=True)
    lua.execute(scripts[0]); api = lua.globals().H3A7_CE_MVP
    api.controlled_fixture().until_state("MONITORING"); api.stop()
    original_config(source_dir)  # safe original template; cannot retain successful application
    with pytest.raises(Exception, match="ALPHA_CONFIG_TARGET_REQUIRED"): lua.execute(scripts[0])
    s = api.status()
    assert s.config_validation == "VALID" and s.config_application == "NOT_APPLIED"
    assert s.runtime_capability == "STANDARD_ADAPTER_REQUIRES_QUALIFICATION"
    assert api.evaluation() is None and not s.evaluation_completed and s.ranking_best_score is None
    assert api.controlled_fixture() is None and lua.globals().h.config_reads == 2


def test_f01_r1_private_log_failure_is_sanitized_and_cannot_start(standard_ct):
    lua, scripts, source_dir = standard_ct
    log = source_dir / "PRIVATE_DIRECTORY" / "PRIVATE_VALUE.log"
    original_config(source_dir, "c.target_pid=101;c.write_enabled=true;c.log_path=[[%s]]" % log, owned=True)
    with pytest.raises(Exception, match="LOG_OUTPUT_FAILED"): lua.execute(scripts[0])
    api = lua.globals().H3A7_CE_MVP
    assert not api.status().running and api.status().cleanup_ok
    for code in scripts[2:4]: lua.execute(code)
    assert "PRIVATE_" not in "\n".join(array(lua.globals().h.lines))
    assert not log.exists()
