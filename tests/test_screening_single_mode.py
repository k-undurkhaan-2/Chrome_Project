"""Single-profile checks using real Lua 5.4 collection, scoring and batch code.

Reuses the stable suite's table-backed foundlists/reads. Startup config I/O is
removed in memory; main() is invoked only with synthetic UI, module loading and
in-memory output sinks. No CE process, target memory or real executor is used.
"""

import re

import pytest

from test_stable_prescore_optimization import (
    BATCH, COLLECTOR, TRUTH, array, new_runtime, plain,
)


SKIPPED = "with_probe, no_probe_B, stable_no_probe_intersection"
FULL_MODES = ["no_probe_A", "with_probe", "no_probe_B", "stable_no_probe_intersection"]


def runtime(profile="single", *, scenario="identical", count=120, budget=2000, truth=None):
    lua = new_runtime(COLLECTOR.read_text(encoding="utf-8"), scenario, count)
    source = BATCH.read_text(encoding="utf-8")
    lua.compile(source)
    startup = "RUN_CASES = apply_local_case_config(RUN_CASES, LOCAL_CASE_CONFIG_PATH)"
    assert source.count(startup) == 1
    source = source.replace(startup, "-- Synthetic test: no local config I/O.")
    source, tail = source.rsplit("\nmain()", 1)
    assert not tail.strip()
    api = lua.execute(source + """
        written_logs = {}; captured_runs = {}; execution_calls = {}
        directory_calls = 0; ui_calls = 0; executor_loads = 0; write_calls = 0
        file_cost = 700; module_loads = 0
        os.date = function() return 'synthetic-single' end
        ensure_directory = function() directory_calls = directory_calls + 1 end
        getLuaEngine = function()
            ui_calls = ui_calls + 1
            return {show = function() end}
        end
        load_modules = function()
            module_loads = module_loads + 1
            -- Each mode receives the same synthetic snapshot pair. Stable still
            -- obtains two fresh foundlists within its one collector invocation.
            active_snapshot = 0
        end
        write_text_file = function(path, text)
            written_logs[path] = text; tick = tick + file_cost
        end
        load_value_executor = function()
            executor_loads = executor_loads + 1
            error('real executor loading is forbidden in synthetic tests')
        end
        local function forbidden_write()
            write_calls = write_calls + 1
            error('memory writes are forbidden in synthetic tests')
        end
        writeFloat = forbidden_write; writeInteger = forbidden_write
        writeBytes = forbidden_write; writeDouble = forbidden_write
        evaluate_value_execution = function(cfg, summary, guard)
            execution_calls[#execution_calls + 1] = {mode = summary.mode, guard = guard}
            return build_default_execution_result(cfg, summary)
        end
        local run = MVP0FoundList.run
        MVP0FoundList.run = function(opts)
            local entry = {options = opts}
            captured_runs[#captured_runs + 1] = entry
            entry.bundle = run(opts)
            return entry.bundle
        end
        local render = render_summary_file
        render_summary_file = function(batch_id, summaries)
            captured_summaries = summaries
            return render(batch_id, summaries)
        end
        return {
            main = main, cases = RUN_CASES, mode = run_case_mode,
            normalize = normalize_validation_profile, modes = get_case_mode_entries,
            aggregate = build_case_runtime_diagnostics,
            rank_guard = build_execution_rank_guard,
        }
    """)
    cfg = api.cases[1]
    cfg.validation_profile = profile
    cfg.case_id = cfg.session_id = "synthetic"
    cfg.scan_budget = budget
    cfg.known_true_addr = truth
    _, cfg.skipped_modes = api.modes(cfg)
    return lua, api, cfg


def outputs(lua):
    return {path: re.sub(r"[ \t]+=", " =", text)
            for path, text in lua.globals().written_logs.items()}


def assert_no_execution(lua):
    g = lua.globals()
    assert len(g.execution_calls) == g.executor_loads == g.write_calls == 0


def assert_no_truth_probe(bundle):
    assert bundle.raw_probe_full_foundlist_enabled is False
    assert bundle.raw_probe_quota == bundle.raw_probe_used == 0
    assert bundle.true_foundlist_index is None
    assert bundle.known_true_raw_admission_path != "probe_window"
    # Full-budget A observes truth while admitting every address normally.
    # This legacy diagnostic flag does not imply a truth-directed scan/probe.
    assert bundle.true_in_full_foundlist_checked is (
        bundle.known_true_addr is not None and bundle.scan_budget >= bundle.raw_count
    )


@pytest.mark.parametrize("value,expected", [
    (None, "full"), ("full", "full"), ("FULL", "full"),
    ("quick", "quick"), ("Quick", "quick"), ("single", "single"), ("SINGLE", "single"),
])
def test_normalization_preserves_defaults_and_accepts_single(value, expected):
    _, api, _ = runtime()
    assert api.normalize(value) == expected


@pytest.mark.parametrize("value", ["", "basic", "single_pass", " full ", 1])
def test_invalid_profiles_remain_errors(value):
    _, api, _ = runtime()
    with pytest.raises(Exception, match="invalid validation_profile"):
        api.normalize(value)


@pytest.mark.parametrize("profile,expected_modes,probe_flags,snapshots,evaluated_mode", [
    ("single", ["no_probe_A"], [False], 1, None),
    ("quick", ["no_probe_A"], [False], 1, "no_probe_A"),
    ("full", FULL_MODES, [False, True, False, False], 5, "stable_no_probe_intersection"),
])
def test_actual_main_dispatch_and_legacy_execution_evaluation(
    profile, expected_modes, probe_flags, snapshots, evaluated_mode,
):
    lua, api, cfg = runtime(profile, truth=TRUTH)
    assert cfg.execution_mode == "disabled" and cfg.write_enabled is False
    assert cfg.require_full_profile is cfg.require_known_true_match is cfg.require_old_value_match is True
    if profile == "single":
        # User-supplied mode entries cannot enable W/probing or add another A.
        cfg.modes = lua.eval("{{name='with_probe', probe_full_foundlist=true}, 'no_probe_A'}")
    api.main()
    g = lua.globals()
    summaries = array(g.captured_summaries)
    assert [s.mode for s in summaries] == expected_modes
    assert [r.options.probe_full_foundlist for r in array(g.captured_runs)] == probe_flags
    assert len(g.snapshots) == snapshots
    assert g.rank_calls == len(expected_modes)
    for summary in summaries:
        assert summary.run_valid is True, summary.error
        assert summary.validation_profile == profile
        assert summary.baseline_eligible is (profile == "full")
        assert summary.skipped_modes == ("none" if profile == "full" else SKIPPED)
        assert summary.profile_note == {
            "full": "baseline_eligible", "quick": "smoke_test_only", "single": "single_pass_detect_only",
        }[profile]
        assert summary.write_attempted is False
    if evaluated_mode is None:
        assert_no_execution(lua)
        assert g.captured_runs[1].options.stable_no_probe_intersection_enabled is None
    else:
        assert len(g.execution_calls) == 1
        assert g.execution_calls[1].mode == evaluated_mode
        if profile == "quick":
            assert g.execution_calls[1].guard is None
        else:
            guard = g.execution_calls[1].guard
            assert guard.rank_A == guard.rank_W == guard.rank_B == 1 and guard.ok is True
    assert g.executor_loads == g.write_calls == 0


@pytest.mark.parametrize("execution_mode,write_enabled", [
    ("dry_run", False), ("write", False), ("write", True), ("disabled", True),
    (None, False), ("disabled", None), ("disabled", 0), ("disabled", "false"),
])
def test_incompatible_single_rejected_before_any_collection_or_output(execution_mode, write_enabled):
    lua, api, cfg = runtime()
    cfg.execution_mode, cfg.write_enabled = execution_mode, write_enabled
    cfg.execution_confirm = "WRITE_ONCE"
    cfg.execution_write_request_id = "synthetic-arm"
    cfg.require_full_profile = cfg.require_known_true_match = False
    cfg.restore_execution_addr = TRUTH
    before = plain(cfg)
    with pytest.raises(Exception, match='single requires execution_mode="disabled" and write_enabled=false'):
        api.main()
    g = lua.globals()
    assert len(g.captured_runs) == len(g.snapshots) == g.module_loads == 0
    assert g.directory_calls == g.ui_calls == len(g.written_logs) == 0
    assert plain(cfg) == before  # Never silently reset execution/write settings.
    assert_no_execution(lua)


def test_all_cases_preflight_before_an_earlier_full_case_can_collect():
    lua, api, cfg = runtime("full")
    second = lua.table_from(plain(cfg))
    second.validation_profile = "single"
    second.write_enabled = True
    api.cases[2] = second
    with pytest.raises(Exception, match="single requires"):
        api.main()
    assert len(lua.globals().captured_runs) == 0
    assert_no_execution(lua)


@pytest.mark.parametrize("entry", [
    "'with_probe'", "'no_probe_B'", "{name='no_probe_A', probe_full_foundlist=true}",
])
def test_single_mode_entry_cannot_bypass_no_probe_boundary(entry):
    lua, api, cfg = runtime()
    with pytest.raises(Exception, match="single requires no_probe_A"):
        api.mode(cfg, lua.eval(entry), "synthetic-single")
    assert len(lua.globals().captured_runs) == 0
    assert_no_execution(lua)


@pytest.mark.parametrize("scenario,count,budget", [
    ("identical", 80, 2000), ("identical", 360, 2000),
    ("mismatch_retry", 360, 2000), ("identical", 800, 240), ("identical", 1500, 2000),
])
@pytest.mark.parametrize("truth", [None, TRUTH, 0x7FFFFFFF])
def test_single_and_full_a_have_identical_admission_scores_ties_and_ranking(scenario, count, budget, truth):
    runs = []
    for profile in ("single", "full"):
        lua, api, cfg = runtime(profile, scenario=scenario, count=count, budget=budget, truth=truth)
        summary = api.mode(cfg, "no_probe_A", "synthetic-single")
        assert summary.run_valid is True, summary.error
        g = lua.globals()
        bundle = g.captured_runs[1].bundle
        assert len(g.captured_runs) == len(g.snapshots) == 1
        assert_no_truth_probe(bundle)
        assert bundle.selected_count == min(100, bundle.filtered_count)
        assert len(bundle.result.ranked) == bundle.selected_count
        assert g.captured_runs[1].options.scan_budget == budget
        assert g.captured_runs[1].options.max_candidates == 100
        assert g.captured_runs[1].options.use_prescore_selection is True
        if scenario == "mismatch_retry":
            debug = g.MVP0FoundList.LAST_FILTER_DEBUG
            assert debug.retry_recovered_count > 0 and debug.retry_still_mismatch_count > 0
            assert debug.read_failed_count > 0 and debug.retry_read_failed_count > 0
        if bundle.filtered_count > 100:
            scores = [item.final_score for item in array(bundle.result.ranked)]
            assert len(set(scores)) < len(scores)
            assert bundle.selection_strategy == "prescore_diverse_top_scored"
        runs.append((plain(bundle), plain(g.MVP0FoundList.LAST_FILTER_DEBUG),
                     plain(g.collection_reads), plain(g.lifecycle), summary.screening_compute_ms))
        assert_no_execution(lua)
    assert runs[0] == runs[1]


@pytest.mark.parametrize("count,budget", [(360, 2000), (800, 240), (1500, 2000)])
def test_truth_is_optional_and_cannot_change_candidate_admission_or_ranking(count, budget):
    runs = []
    for truth in (None, TRUTH, 0x7FFFFFFF):
        lua, api, cfg = runtime(count=count, budget=budget, truth=truth)
        summary = api.mode(cfg, "no_probe_A", "synthetic-single")
        bundle = lua.globals().captured_runs[1].bundle
        runs.append((plain(bundle.candidate_value_addrs), plain(bundle.result.ranked),
                     plain(lua.globals().MVP0FoundList.LAST_FILTER_DEBUG.matched_addresses)))
        assert_no_truth_probe(bundle)
        if truth is None or truth == 0x7FFFFFFF:
            assert summary.known_true_rank_position is None
        if count == 1500 and truth == TRUTH:
            assert bundle.true_in_filtered is True and bundle.true_in_selected is False
            assert summary.known_true_rank_position is None
    assert runs[0] == runs[1] == runs[2]


@pytest.mark.parametrize("mutation,expected", [
    ("return nil", "collector_missing_summary"),
    ("bundle.raw_count = nil", "collector_invalid_raw_count"),
    ("bundle.raw_count = 0", "collector_runtime_empty"),
    ("bundle.result = nil", "collector_invalid_result"),
    ("bundle.result.ranked = false", "collector_invalid_result"),
    ("bundle.result.ranked = {}", "collector_invalid_result"),
    ("bundle.result.best = nil", "collector_invalid_result"),
    ("bundle.result.best = 42", "collector_invalid_result"),
    ("bundle.result.ranked[1].candidate = nil", "collector_invalid_result"),
    ("bundle.result.ranked[1].score = 0/0", "collector_invalid_result"),
    ("bundle.result.ranked[1] = 42", "collector_invalid_result"),
    ("bundle.error = 'explicit failure'", "collector_error"),
    ("bundle.raw_count = 0; bundle.error = 'explicit failure'", "collector_error"),
    ("bundle.failure_class = 'specific_failure'; bundle.error = 'explicit failure'", "specific_failure"),
    ("bundle.run_valid = false", "collector_invalid_result"),
])
def test_invalid_a_is_invalid_in_log_summary_and_aggregate(mutation, expected):
    lua, api, _ = runtime()
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
    assert summary.run_valid is False and summary.failure_class == expected
    assert summary.screening_compute_ms is None and summary.write_attempted is False
    assert summary.validation_profile == "single" and summary.baseline_eligible is False
    aggregate = api.aggregate(lua.table_from({"no_probe_A": summary}))
    assert aggregate.run_valid is False and aggregate.failure_class == expected
    for text in outputs(lua).values():
        assert f"failure_class = {expected}" in text
        assert "run_valid = false" in text and "run_valid = true" not in text
        assert "screening_compute_ms = nil" in text and "write_attempted = false" in text
    assert_no_execution(lua)


@pytest.mark.parametrize("fault", ["memscan", "initialize", "final_score", "final_rank"])
def test_real_pipeline_exceptions_are_logged_without_completed_time(fault):
    lua, api, _ = runtime()
    lua.globals().fault = fault
    lua.globals().fault_snapshot = 1
    api.main()
    summary = lua.globals().captured_summaries[1]
    assert summary.run_valid is False and summary.failure_class == "collector_exception"
    assert summary.error and summary.screening_compute_ms is None
    for text in outputs(lua).values():
        assert "failure_class = collector_exception" in text
        assert "validation_profile = single" in text
        assert "profile_note = single_pass_detect_only" in text
        assert f"skipped_modes = {SKIPPED}" in text
        assert "write_attempted = false" in text and "rank_guard_ok = false" in text
    assert_no_execution(lua)


@pytest.mark.parametrize("scenario,expected", [
    ("empty_a", "collector_runtime_empty"), ("all_mismatch", "collector_invalid_result"),
])
def test_actual_empty_collection_and_empty_final_ranking_are_invalid(scenario, expected):
    lua, api, _ = runtime(scenario=scenario)
    api.main()
    summary = lua.globals().captured_summaries[1]
    assert summary.run_valid is False and summary.failure_class == expected
    assert summary.screening_compute_ms is None and summary.write_attempted is False
    assert_no_execution(lua)


def test_required_modes_remain_fail_closed_without_fabricating_full_guard():
    lua, api, cfg = runtime()
    summary = api.mode(cfg, "no_probe_A", "synthetic-single")
    group = lua.table_from({"no_probe_A": summary})
    assert api.aggregate(group).run_valid is True
    assert api.aggregate(lua.table()).failure_class == "collector_missing_summary"
    assert api.rank_guard(summary, None, None).ok is False
    summary.validation_profile = "full"
    assert api.aggregate(group).failure_class == "collector_missing_summary"
    summary.validation_profile = "quick"
    assert api.aggregate(group).run_valid is True
    for mode in FULL_MODES:
        complete = lua.table_from({name: lua.table_from({"raw_count": 1}) for name in FULL_MODES})
        complete[mode] = None
        result = api.aggregate(complete)
        assert result.run_valid is False and result.failure_class == "collector_missing_summary"
        assert mode in result.error


@pytest.mark.parametrize("level", ["basic", "debug", "trace"])
def test_single_timing_and_saved_outputs_exclude_reporting_and_file_delays(level):
    times = []
    for report_cost, output_cost, file_cost in ((200, 0, 700), (9000, 3000, 11000)):
        lua, api, cfg = runtime(truth=TRUTH)
        cfg.diagnostic_level = level
        g = lua.globals()
        g.report_cost, g.output_cost, g.file_cost = report_cost, output_cost, file_cost
        api.main()
        summary = g.captured_summaries[1]
        assert summary.run_valid is True and summary.known_true_rank_position == 1
        assert summary.best_candidate_addr == TRUTH
        assert summary.screening_compute_ms > 0
        assert summary.collector_call_ms > summary.screening_compute_ms
        assert summary.total_ms > summary.screening_compute_ms
        times.append(summary.screening_compute_ms)
        saved = outputs(lua)
        assert len(saved) == 3
        assert sum(path.endswith('__no_probe_A.log') for path in saved) == 1
        assert sum(path.endswith('__summary.txt') for path in saved) == 1
        assert sum(path.endswith('__diagnostic_diff.txt') for path in saved) == 1
        for text in saved.values():
            for expected in (
                "validation_profile = single", "baseline_eligible = false",
                "profile_note = single_pass_detect_only", f"skipped_modes = {SKIPPED}",
                "run_valid = true", "failure_class = nil", "error = nil",
                f"screening_compute_ms = {summary.screening_compute_ms}",
                "execution_mode = disabled", "write_enabled = false", "write_attempted = false",
                "execution_arm_valid = false", "execution_preconditions_ok = false", "rank_guard_ok = false",
                "known_true_rank_position = 1",
            ):
                assert expected in text
            assert "[with_probe]" not in text and "[no_probe_B]" not in text
            assert " / stable_no_probe_intersection ---" not in text
        assert_no_execution(lua)
    assert times[0] == times[1]
