"""H1: real Lua 5.4 ranking and publication against synthetic memory/files.

The only OS-backed test uses pytest's external temporary directory to qualify
Windows no-replace rename. No local case config, CE or target memory is used.
"""

import re
import subprocess

import pytest

from test_screening_single_mode import BATCH, TRUTH, array, assert_no_execution, runtime
from test_screening_truth_isolation import freeze
from test_write_usability import (  # reuse the isolated executor fixture
    LOG_ROOT, SOURCE_BATCH, env, full_main_runtime, prepare_restore, restore_main_api,
)


HANDOFF = BATCH.with_name("mvp0_single_handoff.lua")
BATCH_ID = "synthetic-single"
STEM = BATCH_ID + "__synthetic__synthetic"
COMPANION = STEM + "__single_handoff.txt"


VIRTUAL_FILES = r'''
    package = {config = string.char(92)}
    directories = {}; file_operations = {}; handoff_loads = 0
    dofile = function(path)
        assert(path:match('mvp0_single_handoff%.lua$'), 'unexpected module load')
        handoff_loads = handoff_loads + 1
        if module_failure then error('synthetic module failure') end
        return handoff_module
    end
    local function fault(path, kind)
        return file_fault == kind and path:find(fault_suffix or '__single_handoff.txt', 1, true)
    end
    io = {open = function(path, mode)
        file_operations[#file_operations + 1] = {'open', path, mode}
        assert(mode == 'rb' or mode == 'wb')
        if fault(path, 'exception') then error('synthetic I/O exception') end
        if mode == 'rb' then
            if fault(path, 'check') then return nil, 'denied', 13 end
            if written_logs[path] == nil then return nil, 'missing', 2 end
        else
            assert(path:match('%.pending\\content%.tmp$'), 'direct final-file write forbidden')
            if fault(path, 'open') then return nil, 'denied', 13 end
            assert(written_logs[path] == nil, 'staged overwrite forbidden')
            written_logs[path] = ''
        end
        return {
            write = function(self, text)
                if fault(path, 'write') then written_logs[path] = text:sub(1, 20); return nil end
                written_logs[path] = fault(path, 'corrupt') and text:sub(1, 20) or text
                return self
            end,
            read = function(self, size)
                if fault(path, 'read') then return nil end
                return written_logs[path]:sub(1, size)
            end,
            close = function() return not fault(path, 'close') end,
        }
    end}
    os.execute = function(command)
        file_operations[#file_operations + 1] = {'execute', command}
        local dir = command:match('^mkdir "([^"]+)" >nul 2>&1$')
        if dir then
            if directories[dir] or fault(dir, 'reserve') then return nil, 'exit', 1 end
            directories[dir] = true
            return true, 'exit', 0
        end
        dir = assert(command:match('^rmdir "([^"]+)" >nul 2>&1$'), 'unexpected command')
        directories[dir] = nil
        return true, 'exit', 0
    end
    os.remove = function(path) written_logs[path] = nil; return true end
    os.rename = function(source, target)
        file_operations[#file_operations + 1] = {'rename', source, target}
        if fault(target, 'race') then written_logs[target] = 'existing concurrent evidence' end
        if written_logs[target] ~= nil or fault(target, 'rename') then return nil, 'exists' end
        written_logs[target], written_logs[source] = assert(written_logs[source]), nil
        return true
    end
'''


def handoff_runtime(*, enabled=True, profile="single", **kwargs):
    source = kwargs.pop("batch_source", None) or BATCH.read_text(encoding="utf-8")
    source = source.replace("local original_print = print", """
        local original_print = print
        console_lines = {}
        local output = original_print
        original_print = function(...)
            local words = {}
            for i = 1, select('#', ...) do words[i] = tostring(select(i, ...)) end
            console_lines[#console_lines + 1] = table.concat(words, '\\t')
            output(...)
        end
    """, 1)
    lua, api, cfg = runtime(profile, batch_source=source, **kwargs)
    cfg.single_handoff_enabled = enabled
    lua.globals().handoff_module = lua.execute(HANDOFF.read_text(encoding="utf-8"))
    lua.execute(VIRTUAL_FILES)
    return lua, api, cfg


def files(lua):
    return dict(lua.globals().written_logs.items())


def companions(lua):
    return {p: text for p, text in files(lua).items() if p.endswith("__single_handoff.txt")}


def fields(text):
    result = dict(line.split("=", 1) for line in text.splitlines())
    assert len(result) == len(text.splitlines())
    return result


def collection_evidence(value):
    # Callback identities belong to separate Lua runtimes; compare every data
    # field and assert callback/collector behavior separately through counters.
    if hasattr(value, "items"):
        return {key: collection_evidence(item) for key, item in value.items() if key != "on_rank_complete"}
    return value


def assert_detect_only(lua):
    assert_no_execution(lua)
    g = lua.globals()
    assert len(g.captured_runs) == len(g.snapshots) == g.rank_calls == 1
    assert g.captured_runs[1].options.probe_full_foundlist is False
    assert g.captured_runs[1].options.known_true_addr is None
    assert g.captured_summaries[1].write_ready is False
    assert g.captured_summaries[1].execution_success is False


def prepared():
    lua, api, cfg = handoff_runtime()
    summary = api.mode(cfg, "no_probe_A", BATCH_ID)
    result = lua.globals().captured_runs[1].bundle.result
    source = lua.table_from({
        "batch_id": BATCH_ID, "case_id": "synthetic", "session_id": "synthetic",
        "log_filename": STEM + "__no_probe_A.log", "log_published": True,
        "log_size_bytes": summary.log_size_bytes,
    })
    lua.globals().summary, lua.globals().result, lua.globals().source = summary, result, source
    assert summary.single_handoff_status == "VALIDATED_PENDING_OUTPUT", summary.single_handoff_failure_class
    return lua, summary, result, source


def test_default_false_and_disabled_outputs_match_exact_head_bytes():
    published = subprocess.check_output(
        ["git", "show", "fd1ba14cb218bae13066575bc61422f38c70c598:src/execute_module-v5.2.0_batch.lua"],
        cwd=BATCH.parent.parent, text=True, encoding="utf-8",
    )
    lua, _, cfg = runtime()
    assert cfg.single_handoff_enabled is False
    states = []
    for source in (published, BATCH.read_text(encoding="utf-8")):
        lua, api, _ = handoff_runtime(enabled=False, batch_source=source)
        api.main()
        g = lua.globals()
        assert_detect_only(lua)
        assert len(files(lua)) == 3 and not companions(lua)
        assert g.handoff_loads == len(g.file_operations) == 0
        states.append(freeze(collection_evidence({"files": g.written_logs, "runs": g.captured_runs,
                              "reads": g.collection_reads, "summary": g.captured_summaries})))
    assert states[0] == states[1]


def test_valid_handoff_is_canonical_non_authorizing_and_linked_to_exact_log():
    lua, api, cfg = handoff_runtime()
    cfg.write_value_float, cfg.write_value_pattern = 999.0, 0x4479C000
    api.main()
    assert_detect_only(lua)
    g = lua.globals()
    assert g.handoff_loads == 1 and len(files(lua)) == 4 and len(companions(lua)) == 1
    assert not list(g.directories.items())
    path, text = next(iter(companions(lua).items()))
    record = fields(text)
    assert path == LOG_ROOT + "\\" + COMPANION
    assert record["source_log_filename"] == STEM + "__no_probe_A.log"
    source_text = files(lua)[LOG_ROOT + "\\" + record["source_log_filename"]]
    assert record["source_log_size_bytes"] == str(len(source_text.encode()))
    assert record.items() >= {
        "handoff_schema_version": "1", "handoff_kind": "single_candidate_proposal",
        "authorization_status": "NOT_AUTHORIZED", "handoff_write_ready": "false",
        "write_attempted": "false", "baseline_eligible": "false", "candidate_rank": "1",
        "candidate_address": f"0x{TRUTH:X}", "run_valid": "true", "error": "nil",
        "failure_class": "nil", "probe_full_foundlist": "false",
        "source_mode": "no_probe_A", "source_validation_profile": "single",
        "source_batch_id": BATCH_ID, "source_session_id": "synthetic", "source_case_id": "synthetic",
        "search_target_float": "100", "search_target_pattern": "0x42C80000",
        "operator_process_identity_verified": "false", "independent_review_required": "true",
        "next_action": "independent_candidate_and_process_verification",
    }.items()
    assert "NOT A WRITE GRANT" in record["warning"]
    assert "Windows process instance" in record["session_identity_note"]
    assert not re.search(r"known_true|true_in_|truth_probe|true_foundlist|PID|executable|restore_|arm_|write_value|999|D:\\", text)
    assert g.captured_summaries[1].single_handoff_status == "PUBLISHED_NOT_AUTHORIZED"
    assert array(g.file_operations)[-2][1] == "rename"  # publication then reservation cleanup


@pytest.mark.parametrize("level", ["basic", "debug", "trace"])
@pytest.mark.parametrize("scenario", ["identical", "mismatch_retry", "all_mismatch", "empty_a"])
def test_truth_changes_cannot_change_ranking_artifact_filename_or_errors(level, scenario):
    states = []
    for truth in (None, TRUTH, 0x7FFFFFFF):
        lua, api, cfg = handoff_runtime(truth=truth, scenario=scenario, count=360)
        cfg.diagnostic_level = level
        if truth is not None:
            for name in ("known_true_other", "true_in_filtered", "true_foundlist_index", "truth_probe_logs"):
                cfg[name] = truth
        api.main()
        g = lua.globals()
        assert_detect_only(lua)
        states.append(freeze({"files": g.written_logs, "summary": g.captured_summaries,
                              "ranking": g.captured_runs[1].bundle.result,
                              "reads": g.collection_reads, "console": g.console_lines}))
    assert states[0] == states[1] == states[2]


def test_opt_in_adds_no_collection_snapshot_or_memory_read():
    states = []
    for enabled in (False, True):
        lua, api, _ = handoff_runtime(enabled=enabled)
        api.main()
        g = lua.globals()
        states.append(freeze(collection_evidence({"reads": g.collection_reads, "snapshots": g.snapshots,
                              "runs": g.captured_runs, "builds": g.build_calls,
                              "scores": g.score_calls, "ranks": g.rank_calls,
                              "time": g.captured_summaries[1].screening_compute_ms})))
        assert_detect_only(lua)
    assert states[0] == states[1]


@pytest.mark.parametrize("profile", ["full", "quick"])
def test_other_profiles_ignore_opt_in_byte_for_byte(profile):
    states = []
    for enabled in (False, True):
        lua, api, _ = handoff_runtime(profile=profile, enabled=enabled)
        api.main()
        assert not companions(lua)
        assert lua.globals().handoff_loads == len(lua.globals().file_operations) == 0
        states.append(freeze(files(lua)))
    assert states[0] == states[1]


@pytest.mark.parametrize("mode", ["disabled", "dry_run", "write"])
def test_full_executor_behavior_and_bytes_unchanged_with_flag(mode):
    states = []
    for enabled in (False, True):
        lua, api, cfg = full_main_runtime(mode)
        cfg.single_handoff_enabled = enabled
        api.main()
        states.append(freeze({"files": lua.globals().saved, "writes": lua.globals().writes,
                              "result": lua.globals().execution_results}))
    assert states[0] == states[1]


@pytest.mark.parametrize("mode", ["disabled", "dry_run", "write"])
def test_restore_only_ignores_flag_and_never_loads_handoff(env, mode):
    prepare_restore(env)
    lua, _, opts = env
    opts.config.single_handoff_enabled = True
    opts.config.execution_mode, opts.config.write_enabled = mode, mode == "write"
    api = restore_main_api(env, missing_collectors=True)
    lua.execute("dofile = function() error('H1/collector loading is forbidden in restore') end")
    api.main()
    assert lua.globals().collector_calls == 0
    assert len(lua.globals().writes) == (1 if mode == "write" else 0)
    assert len(list(lua.globals().saved.items())) == 3
    assert not any("single_handoff" in text for text in lua.globals().saved.values())


@pytest.mark.parametrize("value", ["true", "false", "yes", 1, 0, "", {}])
def test_malformed_flag_rejected_before_collection(value):
    lua, api, cfg = handoff_runtime()
    cfg.single_handoff_enabled = lua.table() if value == {} else value
    with pytest.raises(Exception, match="single_handoff_enabled must be a boolean"):
        api.main()
    assert len(lua.globals().captured_runs) == len(files(lua)) == 0
    assert_no_execution(lua)


@pytest.mark.parametrize("mode,enabled", [("write", False), ("write", True), ("disabled", True), ("dry_run", False)])
def test_forged_single_write_settings_fail_before_collection(mode, enabled):
    lua, api, cfg = handoff_runtime()
    cfg.execution_mode, cfg.write_enabled = mode, enabled
    cfg.require_full_profile = cfg.require_known_true_match = cfg.require_old_value_match = False
    with pytest.raises(Exception, match="single requires"):
        api.main()
    assert len(lua.globals().captured_runs) == len(files(lua)) == 0
    assert_no_execution(lua)


@pytest.mark.parametrize("restore", [False, True])
def test_executor_rejects_single_with_flag_and_all_optional_guards_disabled(env, restore):
    lua, executor, opts = env
    opts.config.single_handoff_enabled = True
    opts.config.validation_profile = "single"
    opts.config.require_full_profile = opts.config.require_known_true_match = opts.config.require_old_value_match = False
    if restore:
        opts.config.execution_addr_source = "restore_source_batch_execution_addr"
    result = executor.evaluate(opts)
    assert result.execution_failure_class == "single_detect_only"
    assert result.write_attempted is result.write_ready is result.execution_success is False
    assert lua.globals().reads == len(lua.globals().writes) == 0


@pytest.mark.parametrize("mutation,failure", [
    ("summary.run_valid = false", "handoff_invalid_run"),
    ("summary.failure_class = 'collector_error'", "handoff_invalid_run"),
    ("summary.error = 'synthetic error'", "handoff_invalid_run"),
    ("summary.validation_profile = 'full'", "handoff_not_detect_only"),
    ("summary.write_ready = true", "handoff_not_detect_only"),
    ("summary.execution_success = true", "handoff_not_detect_only"),
    ("summary.probe_full_foundlist = true", "handoff_not_detect_only"),
    ("result.ranked = {}", "handoff_ranking_invalid"),
    ("result.best = {}", "handoff_ranking_invalid"),
    ("result.best.candidate = nil", "handoff_ranking_invalid"),
    ("result.best.rank_position = 2", "handoff_ranking_invalid"),
    ("result.second = result.best", "handoff_ranking_invalid"),
    ("result.ranked[2].rank_position = 1", "handoff_ranking_invalid"),
    ("result.ranked[999] = result.best", "handoff_ranking_invalid"),
    ("result.ranked[2].candidate.value_addr = result.best.candidate.value_addr", "handoff_ranking_invalid"),
    ("result.best.score = 0/0", "handoff_ranking_invalid"),
    ("result.second.score = math.huge", "handoff_ranking_invalid"),
    ("result.best.final_score = false", "handoff_ranking_invalid"),
    ("result.best.candidate.value_addr = 0", "handoff_ranking_invalid"),
    ("result.best.candidate.value_addr = -1", "handoff_ranking_invalid"),
    ("result.best.candidate.value_addr = math.huge", "handoff_ranking_invalid"),
    ("result.best.candidate.value_addr = 0/0", "handoff_ranking_invalid"),
    ("result.best.candidate.value_addr = 1.5", "handoff_ranking_invalid"),
    ("result.best.candidate.value_addr = 0x20000000000000", "handoff_ranking_invalid"),
    ("result.best.candidate.value_addr = '0x10000228'", "handoff_ranking_invalid"),
    ("summary.best_candidate_addr = 16", "handoff_candidate_mismatch"),
    ("summary.best_score = nil", "handoff_candidate_mismatch"),
    ("result.score_gap = -1; summary.score_gap = -1", "handoff_score_gap_invalid"),
    ("result.score_gap = math.huge; summary.score_gap = math.huge", "handoff_score_gap_invalid"),
    ("result.confidence = 'HIGH\\nauthorization_status=AUTHORIZED'; summary.confidence = result.confidence", "handoff_confidence_invalid"),
    ("result.final_decision.recommended_candidate = result.second", "handoff_recommendation_invalid"),
    ("result.final_decision.recommendation = 'AUTHORIZED'", "handoff_recommendation_invalid"),
    ("summary.target_value_pattern = 1", "handoff_search_target_mismatch"),
    ("summary.target_value_float = 1/0", "handoff_search_target_invalid"),
    ("summary.target_value_float = 1e100", "handoff_search_target_invalid"),
    ("summary.target_value_pattern = -1", "handoff_search_target_invalid"),
    ("summary.target_value_pattern = 0x7FC00000", "handoff_search_target_invalid"),
    ("summary.target_value_pattern = 0x100000000", "handoff_search_target_invalid"),
    ("summary.target_value_pattern = 1.5", "handoff_search_target_invalid"),
    ("summary.target_value_float = nil; summary.target_value_pattern = nil", "handoff_search_target_missing"),
    ("source.batch_id = nil", "handoff_source_identity_invalid"),
    ("source.batch_id = 'other'", "handoff_source_identity_invalid"),
    ("source.case_id = '../outside'", "handoff_source_identity_invalid"),
    ("source.session_id = 'other'", "handoff_source_identity_invalid"),
    ("summary.case_id = nil", "handoff_source_identity_invalid"),
    ("source.log_filename = 'D:/outside.log'", "handoff_source_identity_invalid"),
    ("source.log_filename = 'other__no_probe_A.log'", "handoff_source_identity_invalid"),
    ("source.log_published = false", "handoff_source_log_unavailable"),
    ("source.log_size_bytes = 1", "handoff_source_log_unavailable"),
])
def test_pure_validator_rejects_invalid_evidence_without_artifact(mutation, failure):
    lua, summary, result, source = prepared()
    before = files(lua)
    lua.execute(mutation)
    text, rejected = lua.globals().handoff_module.render(summary, result, source)
    assert text is None and rejected == failure
    assert files(lua) == before and not companions(lua)
    assert_no_execution(lua)


@pytest.mark.parametrize("gap", [0, 0.001, 1000000])
def test_ties_weak_gaps_and_strong_accept_always_require_independent_review(gap):
    lua, summary, result, source = prepared()
    lua.globals().gap = gap
    lua.execute("""
        result.ranked = {result.best, result.second}
        result.best.score = 1000000; result.best.final_score = 1000000
        result.second.score = 1000000 - gap; result.second.final_score = result.second.score
        result.score_gap = result.best.score - result.second.score
        summary.best_score = result.best.score; summary.second_score = result.second.score
        summary.score_gap = result.score_gap
        result.confidence = 'HIGH'; summary.confidence = 'HIGH'
        result.final_decision = {recommendation = 'ACCEPT', recommended_candidate = result.best}
    """)
    text, failure, _ = lua.globals().handoff_module.render(summary, result, source)
    assert failure is None
    record = fields(text)
    assert record["recommendation"] == "ACCEPT" and record["confidence"] == "HIGH"
    assert record["handoff_write_ready"] == "false" and record["independent_review_required"] == "true"
    assert summary.write_ready is summary.execution_success is False
    assert_no_execution(lua)


def test_missing_optional_scores_and_labels_are_not_invented_or_zero_filled():
    lua, summary, result, source = prepared()
    lua.execute("""
        result.ranked = {result.best}; result.second = nil; summary.second_score = nil
        result.confidence = nil; summary.confidence = nil; result.final_decision = nil
        result.score_gap = nil; summary.score_gap = nil; summary.target_value_float = nil
    """)
    text, failure, _ = lua.globals().handoff_module.render(summary, result, source)
    assert failure is None
    record = fields(text)
    assert record["second_score"] == record["score_gap"] == record["search_target_float"] == "nil"
    assert "confidence" not in record and "recommendation" not in record


def test_pure_generation_is_deterministic_and_never_consults_truth_or_process_apis():
    lua, summary, result, source = prepared()
    render = lua.globals().handoff_module.render
    expected = render(summary, result, source)
    lua.execute("""
        local function forbidden() error('pure H1 consulted external state') end
        io = nil; os = nil; getCurrentMemscan = forbidden; createFoundList = forbidden
        readInteger = forbidden; readFloat = forbidden; writeFloat = forbidden
        MVP0ValueExecutor = setmetatable({}, {__index = forbidden})
        for _, item in ipairs({summary, result, result.best, result.best.candidate, result.final_decision, source}) do
            item.known_true_addr = 0x7FFFFFFF; item.known_true_rank_position = 99
            item.true_in_selected = true; item.truth_probe_logs = {'private oracle data'}
            setmetatable(item, {__index = function(_, key)
                if key:match('^known_true_') or key:match('^true_in_')
                    or key == 'true_foundlist_index' then forbidden() end
            end})
        end
    """)
    assert render(summary, result, source) == expected
    assert render(summary, result, source) == expected


def test_large_integer_scores_are_exact_and_wrapped_gap_is_rejected():
    lua, summary, result, source = prepared()
    lua.execute("""
        result.ranked = {result.best, result.second}; result.final_decision = nil
        result.best.score = math.maxinteger; result.best.final_score = math.maxinteger
        result.second.score = math.maxinteger - 1; result.second.final_score = math.maxinteger - 1
        summary.best_score = result.best.score; summary.second_score = result.second.score
        result.score_gap = 1; summary.score_gap = 1
    """)
    text, failure, _ = lua.globals().handoff_module.render(summary, result, source)
    assert failure is None and fields(text)["best_score"] == "9223372036854775807"
    assert fields(text)["second_score"] == "9223372036854775806"
    lua.execute("""
        result.second.score = math.mininteger; result.second.final_score = math.mininteger
        summary.second_score = result.second.score
        result.score_gap = result.best.score - result.second.score; summary.score_gap = result.score_gap
    """)
    assert lua.globals().handoff_module.render(summary, result, source) == (None, "handoff_score_gap_invalid")


@pytest.mark.parametrize("value,pattern", [(50.0, 0x42C80000), (float("inf"), 0x42C80000),
                                           (100.0, -1), (100.0, float("nan"))])
def test_runner_inconsistent_or_invalid_search_input_never_publishes(value, pattern):
    lua, api, cfg = handoff_runtime()
    cfg.target_value_float, cfg.target_value_pattern = value, pattern
    api.main()
    assert not companions(lua)
    assert lua.globals().captured_summaries[1].single_handoff_status == "REJECTED"
    assert_no_execution(lua)


@pytest.mark.parametrize("mutation,screening_failure", [
    ("return nil", "collector_missing_summary"),
    ("bundle.raw_count = 0", "collector_runtime_empty"),
    ("bundle.result.ranked = {}", "collector_invalid_result"),
    ("bundle.result.best = nil", "collector_invalid_result"),
    ("bundle.result.best.score = 0/0", "collector_invalid_result"),
    ("bundle.error = 'synthetic failure'; bundle.failure_class = 'specific_failure'", "specific_failure"),
    ("error('synthetic collector exception')", "collector_exception"),
    ("bundle.result.best.candidate.value_addr = 0", None),
    ("bundle.result.best.rank_position = 3", None),
    ("bundle.result.score_gap = -1", None),
])
def test_runner_rejects_unusable_results_preserving_screening_classification(mutation, screening_failure):
    lua, api, _ = handoff_runtime()
    lua.execute(f"""
        local run = MVP0FoundList.run
        MVP0FoundList.run = function(opts)
            local bundle = run(opts)
            do {mutation} end
            return bundle
        end
    """)
    api.main()
    summary = lua.globals().captured_summaries[1]
    assert summary.failure_class == screening_failure
    assert summary.run_valid is (screening_failure is None)
    assert summary.single_handoff_status == "REJECTED"
    assert not companions(lua) and len(files(lua)) == 3
    assert_no_execution(lua)


@pytest.mark.parametrize("field,value", [("case_id", "../unsafe"), ("session_id", "bad\nline"),
                                         ("case_id", "a__b"), ("case_id", None)])
def test_malformed_runner_identity_yields_no_proposal(field, value):
    lua, api, cfg = handoff_runtime()
    cfg[field] = value
    api.main()
    assert not companions(lua)
    assert lua.globals().captured_summaries[1].single_handoff_failure_class == "handoff_source_identity_invalid"
    assert_no_execution(lua)


@pytest.mark.parametrize("suffix", ["__no_probe_A.log", "__summary.txt", "__diagnostic_diff.txt", "__single_handoff.txt"])
@pytest.mark.parametrize("fault", ["check", "reserve", "open", "write", "close", "read", "corrupt", "rename", "exception"])
def test_each_output_failure_fails_closed_preserving_other_outputs(suffix, fault):
    lua, api, _ = handoff_runtime()
    lua.globals().fault_suffix, lua.globals().file_fault = suffix, fault
    api.main()
    assert_detect_only(lua)
    assert not companions(lua)
    summary = lua.globals().captured_summaries[1]
    assert summary.single_handoff_status == "REJECTED" and summary.run_valid is True
    assert summary.failure_class is summary.error is None
    assert all(".pending" not in path for path in files(lua))
    assert len(files(lua)) == (3 if suffix == "__single_handoff.txt" else 2)
    console = "\n".join(array(lua.globals().console_lines))
    assert "REJECTED" in console and "PUBLISHED_NOT_AUTHORIZED" not in console


@pytest.mark.parametrize("suffix", ["__no_probe_A.log", "__summary.txt", "__diagnostic_diff.txt", "__single_handoff.txt"])
@pytest.mark.parametrize("race", [False, True])
def test_existing_output_or_racing_publisher_is_never_overwritten(suffix, race):
    lua, api, _ = handoff_runtime()
    prefix = BATCH_ID if suffix in ("__summary.txt", "__diagnostic_diff.txt") else STEM
    path = LOG_ROOT + "\\" + prefix + suffix
    existing = "existing concurrent evidence" if race else "existing B3 evidence"
    if race:
        lua.globals().fault_suffix, lua.globals().file_fault = suffix, "race"
    else:
        lua.globals().written_logs[path] = existing
    api.main()
    assert files(lua)[path] == existing
    assert lua.globals().captured_summaries[1].single_handoff_status == "REJECTED"
    assert not any("handoff_schema_version=" in text for text in companions(lua).values())
    assert_detect_only(lua)


def test_second_same_batch_cannot_replace_any_original_evidence():
    lua, api, _ = handoff_runtime()
    api.main()
    before = files(lua)
    api.main()
    assert files(lua) == before
    assert lua.globals().captured_summaries[1].single_handoff_status == "REJECTED"
    assert_no_execution(lua)


def test_module_load_failure_preserves_original_single_outputs():
    lua, api, _ = handoff_runtime()
    lua.globals().module_failure = True
    api.main()
    assert len(files(lua)) == 3 and not companions(lua)
    assert lua.globals().captured_summaries[1].single_handoff_failure_class == "handoff_builder_failed"
    assert_detect_only(lua)


@pytest.mark.parametrize("mutation", ["package = nil", "package.config = '/'", "os.rename = nil", "io = nil"])
def test_missing_atomic_publication_support_is_explicitly_rejected(mutation):
    lua, api, _ = handoff_runtime()
    lua.execute(mutation)
    api.main()
    summary = lua.globals().captured_summaries[1]
    assert not files(lua)
    assert summary.single_handoff_status == "REJECTED"
    assert summary.single_source_log_failure_class == "output_atomic_publication_unavailable"
    assert_no_execution(lua)


@pytest.mark.parametrize("value", [None, False, True, "true", 1])
def test_mocked_startup_loads_config_once_and_parses_flag_fail_closed(value):
    from lupa.lua54 import LuaRuntime

    lua = LuaRuntime(register_eval=False, register_builtins=False)
    lua.globals().synthetic_config = lua.table_from({
        "validation_profile": "single", "execution_mode": "disabled", "write_enabled": False,
        "single_handoff_enabled": value,
    })
    lua.execute("""
        python = nil; loadfile = nil; package = nil; require = nil
        config_loads = 0
        io = {open = function(path, mode)
            assert(mode == 'r' and path:match('run_case_config%.local%.lua$'))
            return {close = function() return true end}
        end}
        dofile = function(path)
            assert(path:match('run_case_config%.local%.lua$'))
            config_loads = config_loads + 1
            return synthetic_config
        end
    """)
    source, tail = BATCH.read_text(encoding="utf-8").rsplit("\nmain()", 1)
    assert not tail.strip()
    source += "\nreturn RUN_CASES[1]"
    if value in ("true", 1) and value is not True:
        with pytest.raises(Exception, match="single_handoff_enabled must be a boolean"):
            lua.execute(source)
    else:
        assert lua.execute(source).single_handoff_enabled is (value is True)
    assert lua.globals().config_loads == 1


def test_h1_artifact_cannot_be_consumed_as_restore_source_receipt(env):
    source_lua, api, _ = handoff_runtime()
    api.main()
    artifact = next(iter(companions(source_lua).values()))
    prepare_restore(env)
    lua, executor, opts = env
    # Even deliberately placing it at the parser's expected summary path fails.
    lua.globals().files[LOG_ROOT + "\\" + SOURCE_BATCH + "__summary.txt"] = artifact
    result = executor.evaluate(opts)
    assert result.execution_failure_class == "restore_source_evidence_malformed"
    assert result.write_attempted is result.restore_attempted is result.execution_success is False
    assert lua.globals().reads == len(lua.globals().writes) == 0


def test_real_windows_publication_is_no_replace_and_leaves_no_staging(tmp_path):
    from lupa.lua54 import LuaRuntime

    lua = LuaRuntime(register_eval=False, register_builtins=False)
    assert lua.eval("package.config:sub(1, 1)") == "\\", "H1 Windows publication needs Windows qualification"
    source = BATCH.read_text(encoding="utf-8")
    source = source.replace("RUN_CASES = apply_local_case_config(RUN_CASES, LOCAL_CASE_CONFIG_PATH)", "")
    source, tail = source.rsplit("\nmain()", 1)
    assert not tail.strip()
    lua.globals().synthetic_root = str(tmp_path)
    api = lua.execute(source + """
        OUTPUT_DIR = synthetic_root
        return {write = write_single_new_file, config = apply_single_handoff_config}
    """)
    assert api.write("synthetic__single_handoff.txt", "synthetic proposal\r\n") is True
    assert api.write("synthetic__single_handoff.txt", "replacement") == (None, "output_exists")
    assert (tmp_path / "synthetic__single_handoff.txt").read_bytes() == b"synthetic proposal\r\n"
    # Qualify the exact Lua/CRT primitive against an already existing target.
    (tmp_path / "synthetic-source.tmp").write_bytes(b"source")
    lua.globals().rename_source = str(tmp_path / "synthetic-source.tmp")
    lua.globals().rename_target = str(tmp_path / "synthetic__single_handoff.txt")
    assert lua.eval("os.rename(rename_source, rename_target)")[0] is None
    assert (tmp_path / "synthetic__single_handoff.txt").read_bytes() == b"synthetic proposal\r\n"
    assert not list(tmp_path.glob("*.pending"))
    reservation = tmp_path / "reserved.txt.pending"
    reservation.mkdir()
    (reservation / "content.tmp").write_bytes(b"other publisher")
    assert api.write("reserved.txt", "replacement") == (None, "output_reservation_failed")
    assert (reservation / "content.tmp").read_bytes() == b"other publisher"
    assert not (tmp_path / "reserved.txt").exists()
    for value in (None, False, True):
        cfgs = lua.table_from([lua.table()])
        api.config(cfgs, lua.table_from({"single_handoff_enabled": value}))
        assert cfgs[1].single_handoff_enabled is (value is True)
    for value in ("true", "false", 0, 1):
        with pytest.raises(Exception, match="must be a boolean"):
            api.config(lua.table_from([lua.table()]), lua.table_from({"single_handoff_enabled": value}))
