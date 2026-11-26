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
    """Prepared ID1 + real loader; every ambient target primitive is forbidden."""
    import shutil
    from test_h3_a7_ce_mvp import ROOT

    source_dir = portable_source(tmp_path, request.param)
    fixture_path = source_dir.parent / "tests/fixtures/ce_mvp_mock.lua"
    fixture_path.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "tests/fixtures/ce_mvp_mock.lua", fixture_path)
    path = prepare(source_dir, alpha_controlled=request.param == "controlled")
    lua = import_module("lupa.lua53").LuaRuntime(unpack_returned_tuples=True,
                                                max_memory=256 * 1024 * 1024)
    lua.execute("""
      h={forbidden=0,loaded={},lines={},evaluations=0}
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
    lua.globals().test_entry_mode = request.param
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
    lua, _, _ = controlled_ct
    api = lua.execute("return dofile(test_entry_path)")
    accepted, reason = api.configure_execution(lua.table_from(selection))
    assert accepted is False
    assert api.start()[0] is False
    assert reason in api.status().startup_error
    assert api.controlled_fixture() is None and api.evaluation() is None
    assert api.configure_execution(lua.table_from({"mode": "QUALIFICATION"})) == (False, "QSG_MODE_LOCKED")
    assert len(lua.globals().h.loaded) == 0


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
