"""Focused, synthetic Lua checks. No CE, process access, filesystem I/O or main().

Uses optional lupa.lua54 in the test environment; production dependencies and
runtime configuration are unchanged. All durations below are fake-clock values.
"""

from pathlib import Path
import re
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "src/execute_module-v5.2.0_batch.lua"
REPORT = ROOT / "src/mvp0_candidate_report.lua"
COLLECTOR = ROOT / "src/mvp0_foundlist_collector.lua"
MODES = ("no_probe_A", "with_probe", "no_probe_B", "stable_no_probe_intersection")


@pytest.fixture
def runtime():
    lua54 = pytest.importorskip("lupa.lua54", reason="synthetic checks require optional lupa.lua54")
    lua = lua54.LuaRuntime(register_eval=False, register_builtins=False)
    lua.execute("""
        python = nil; io = nil; package = nil; require = nil
        loadfile = nil; dofile = nil
        tick = 0; output_cost = 100; report_cost = 200
        written_logs = {}; rank_callbacks = 0
        os = {clock = function() return tick / 1000 end}
        getTickCount = function() return tick end
        print = function(...) tick = tick + output_cost end
        -- No CE functions are installed in this independent Lua runtime.
    """)
    lua.execute(REPORT.read_text(encoding="utf-8"))
    lua.execute(COLLECTOR.read_text(encoding="utf-8"))
    # Compile the actual complete batch, then load definitions without its two
    # startup side effects: local config I/O and main(). Production files stay intact.
    batch = BATCH.read_text(encoding="utf-8")
    lua.compile(batch)
    batch = batch.replace(
        "RUN_CASES = apply_local_case_config(RUN_CASES, LOCAL_CASE_CONFIG_PATH)",
        "-- Synthetic test: do not read local runtime configuration.",
    )
    batch, invocation = batch.rsplit("\nmain()", 1)
    assert not invocation.strip()
    api = lua.execute(batch + """
        load_modules = function() tick = tick + 500 end
        write_text_file = function(path, text)
            written_logs[path] = text; tick = tick + 700
        end
        evaluate_value_execution = function() return {} end
        local original_analysis = build_no_probe_snapshot_intersection_analysis
        build_no_probe_snapshot_intersection_analysis = function(a, b)
            tick = tick + 13
            return original_analysis(a, b)
        end
        return {
            diagnostics = build_runtime_empty_diagnostics,
            aggregate = build_case_runtime_diagnostics,
            validate = validate_collector_bundle,
            mode = run_case_mode,
            stable = run_stable_intersection_mode,
            summary = render_summary_file,
            diff = render_diagnostic_diff_file,
        }
    """)
    lua.execute("""
        real_collector_run = MVP0FoundList.run
        MVP0.build_candidate = function(addr)
            tick = tick + 2
            return {value_addr = addr, base_addr = addr - 0x28}
        end
        MVP0.score_candidate = function(candidate)
            tick = tick + 3
            return {candidate = candidate, score = 0x3000 - candidate.value_addr}
        end
        MVP0.rank_candidates = function(scored)
            tick = tick + 7
            table.sort(scored, function(a, b) return a.score > b.score end)
            for i, candidate in ipairs(scored) do candidate.rank_position = i end
            return {ranked = scored, best = scored[1], second = scored[2], score_gap = 1}
        end
        MVP0.recommend_action = function()
            tick = tick + 23
            return {recommendation = 'REVIEW', rationale = {}}
        end
        MVP0.render_report = function()
            tick = tick + report_cost
            return 'synthetic report'
        end
        make_bundle = function()
            return {
                raw_count = 2, unique_count = 2, filtered_count = 2, selected_count = 2,
                candidate_value_addrs = {0x2000, 0x1000}, target_value_pattern = 0x42C80000,
                matched_addresses = {0x1000, 0x2000}, known_true_addr = 0x1000,
                true_in_filtered = true, true_in_selected = true,
            }
        end
        MVP0FoundList.run = function(opts)
            tick = tick + 11
            print('synthetic collector output')
            local bundle = make_bundle()
            MVP0FoundList.LAST_FILTER_DEBUG = {matched_addresses = bundle.matched_addresses}
            bundle.result = MVP0.run(MVP0.make_input(
                bundle.candidate_value_addrs, bundle.target_value_pattern), opts.on_rank_complete)
            bundle.known_true_rank_position = 1
            bundle.stable_intersection_known_true_rank_position = 1
            bundle.stable_intersection_true_in_filtered = true
            tick = tick + 17 -- post-ranking annotation, excluded from screening
            return bundle
        end
        case_cfg = {
            case_id = 'synthetic', session_id = 'synthetic', known_true_addr = 0x1000,
            target_value_pattern = 0x42C80000, target_value_float = 100.0,
            validation_profile = 'full', diagnostic_level = 'basic',
            execution_mode = 'disabled', write_enabled = false,
        }
    """)
    return lua, api


def group(lua):
    return lua.table_from({mode: lua.globals().make_bundle() for mode in MODES})


def run_mode(lua, api, mode):
    return api.mode(lua.globals().case_cfg, mode, "synthetic-batch")


def run_stable(lua, api, summaries):
    return api.stable(lua.globals().case_cfg, *(summaries[m] for m in MODES[:3]), "synthetic-batch")


def assert_logged(lua, summary):
    log = re.sub(r"[ \t]+=", " =", lua.globals().written_logs[summary.log_path])
    for key in ("run_valid", "failure_class", "error", "screening_compute_ms"):
        value = lua.eval("tostring")(summary[key])
        assert f"{key} = {value}" in log


def test_positive_and_empty_required_modes(runtime):
    lua, api = runtime
    summaries = group(lua)
    result = api.aggregate(summaries)
    assert result.run_valid is True
    assert result.failure_class is None and result.error is None
    for mode in MODES:
        summaries[mode].raw_count = 0
    result = api.aggregate(summaries)
    assert result.run_valid is False and result.collector_empty is True
    assert result.failure_class == "collector_runtime_empty"
    assert result.error is None


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("kind, expected", [
    ("missing", "collector_missing_summary"),
    ("nil_count", "collector_invalid_raw_count"),
    ("error", "collector_error"),
    ("exception", "collector_exception"),
])
def test_any_failed_or_missing_required_mode_invalidates_aggregate(runtime, mode, kind, expected):
    lua, api = runtime
    summaries = group(lua)
    if kind == "missing":
        summaries[mode] = None
    elif kind == "nil_count":
        summaries[mode].raw_count = None
    else:
        summaries[mode].error = "synthetic failure details"
        if kind == "exception":
            summaries[mode].failure_class = "collector_exception"
    result = api.aggregate(summaries)
    assert result.run_valid is False and result.collector_empty is False
    assert result.failure_class == expected
    assert mode in result.error
    if kind in ("error", "exception"):
        assert "synthetic failure details" in result.error


@pytest.mark.parametrize("raw_count", ["2", False, -1, 1.5, float("nan"), float("inf")])
def test_invalid_raw_count_is_not_a_positive_collection(runtime, raw_count):
    lua, api = runtime
    bundle = lua.table_from({"raw_count": raw_count})
    result = api.validate(bundle, "no_probe_A")
    assert result.run_valid is False
    assert result.failure_class == "collector_invalid_raw_count"
    assert result.error and result.screening_compute_ms is None


def test_invalid_ranking_and_existing_failure_class_are_preserved(runtime):
    lua, api = runtime
    bundle = lua.table_from({"raw_count": 2})
    result = api.validate(bundle, "no_probe_A")
    assert result.failure_class == "collector_invalid_result"
    summaries = group(lua)
    summaries.no_probe_A.raw_count = 0
    summaries.with_probe.failure_class = "specific_collector_failure"
    summaries.with_probe.error = "original detail"
    result = api.aggregate(summaries)
    assert result.failure_class == "specific_collector_failure"
    assert result.collector_empty is False and "original detail" in result.error


@pytest.mark.parametrize("expression, expected", [
    ("nil", "collector_missing_summary"),
    ("{}", "collector_invalid_raw_count"),
    ("{raw_count = 0}", "collector_runtime_empty"),
    ("{raw_count = 2}", "collector_invalid_result"),
    ("{raw_count = 2, error = 'explicit error'}", "collector_error"),
    ("{raw_count = 0, failure_class = 'collector_runtime_empty', error = 'explicit error'}", "collector_error"),
])
def test_unusable_bundle_agrees_in_mode_log_return_and_batch(runtime, expression, expected):
    lua, api = runtime
    lua.execute(f"MVP0FoundList.run = function() return {expression} end")
    result = run_mode(lua, api, MODES[0])
    assert result.run_valid is False and result.failure_class == expected
    assert result.screening_compute_ms is None
    assert_logged(lua, result)
    output = api.summary("synthetic-batch", lua.table_from([result]))
    assert f"failure_class = {expected}" in output
    assert "run_valid = true" not in output


@pytest.mark.parametrize("diagnostic_level", ["basic", "trace"])
def test_four_paths_end_timing_at_rank_before_reports_output_and_writes(runtime, diagnostic_level):
    lua, api = runtime
    lua.globals().case_cfg.diagnostic_level = diagnostic_level
    summaries = lua.table()
    for mode in MODES[:3]:
        result = run_mode(lua, api, mode)
        summaries[mode] = result
        assert result.run_valid is True, result.error
        # Collection 11 + candidate reads 4 + scoring 6 + final ranking 7.
        assert result.screening_compute_ms == 28
        assert result.collector_call_ms > result.screening_compute_ms
        assert result.best_candidate_addr == 0x1000 and result.known_true_rank_position == 1
        assert_logged(lua, result)
    # Stable must not add these earlier durations.
    for mode in MODES[:3]:
        summaries[mode].screening_compute_ms = 999999
    stable = run_stable(lua, api, summaries)
    summaries[MODES[3]] = stable
    assert stable.run_valid is True, stable.error
    assert stable.screening_compute_ms == 41  # analysis 13 + own screening 28
    assert_logged(lua, stable)
    output = api.summary("synthetic-batch", lua.table_from([summaries[m] for m in MODES]))
    assert output.count("screening_compute_ms = ") == 4
    assert "screening_compute_ms = 41" in output
    lua.globals().report_cost = 9000
    lua.globals().output_cost = 3000
    repeat = run_mode(lua, api, MODES[0])
    assert repeat.screening_compute_ms == 28


@pytest.mark.parametrize("mode", MODES)
def test_exception_before_rank_has_no_completed_screening_time(runtime, mode):
    lua, api = runtime
    lua.execute("MVP0FoundList.run = function() error('synthetic collector exception') end")
    result = run_stable(lua, api, group(lua)) if mode == MODES[3] else run_mode(lua, api, mode)
    assert result.run_valid is False
    assert result.failure_class == "collector_exception"
    assert "synthetic collector exception" in result.error
    assert result.screening_compute_ms is None
    assert_logged(lua, result)


@pytest.mark.parametrize("mode", MODES[:3])
@pytest.mark.parametrize("missing", [False, True])
def test_successful_stable_ranking_cannot_hide_prior_mode_failure(runtime, mode, missing):
    lua, api = runtime
    summaries = group(lua)
    if missing:
        summaries[mode] = None
        expected = "collector_missing_summary"
    else:
        summaries[mode].error = "original mode error"
        summaries[mode].failure_class = "specific_collector_failure"
        expected = "specific_collector_failure"
    result = run_stable(lua, api, summaries)
    assert result.run_valid is False
    assert result.failure_class == expected and mode in result.error
    assert result.screening_compute_ms is None
    assert_logged(lua, result)


@pytest.mark.parametrize("stable", [False, True])
def test_real_collector_forwards_rank_callback(runtime, stable):
    lua, _ = runtime
    lua.execute("""
        MVP0FoundList.collect = function()
            local bundle = make_bundle()
            MVP0FoundList.LAST_FILTER_DEBUG = {matched_addresses = bundle.matched_addresses}
            return bundle
        end
    """)
    opts = lua.table_from({"stable_no_probe_intersection_enabled": stable,
                           "target_value_pattern": 0x42C80000, "use_prescore_selection": False})
    opts.on_rank_complete = lua.eval("function() rank_callbacks = rank_callbacks + 1; callback_tick = tick end")
    result = lua.globals().real_collector_run(opts)
    assert result.result.best.candidate.value_addr == 0x1000
    assert lua.globals().rank_callbacks == 1
    assert lua.globals().tick - lua.globals().callback_tick == 223


@pytest.mark.parametrize("snapshot", [1, 2])
@pytest.mark.parametrize("fault, expected", [
    ("return nil", "collector_missing_summary"),
    ("bundle.raw_count = nil; return bundle", "collector_invalid_raw_count"),
    ("bundle.error = 'snapshot failure'; return bundle", "collector_error"),
])
def test_failed_stable_snapshot_cannot_be_masked_by_other_snapshot(runtime, snapshot, fault, expected):
    lua, _ = runtime
    lua.execute(f"""
        snapshot_calls = 0
        MVP0FoundList.collect = function()
            snapshot_calls = snapshot_calls + 1
            local bundle = make_bundle()
            MVP0FoundList.LAST_FILTER_DEBUG = {{matched_addresses = bundle.matched_addresses}}
            if snapshot_calls == {snapshot} then {fault} end
            return bundle
        end
    """)
    opts = lua.table_from({"stable_no_probe_intersection_enabled": True})
    opts.on_rank_complete = lua.eval("function() rank_callbacks = rank_callbacks + 1 end")
    result = lua.globals().real_collector_run(opts)
    assert result.failure_class == expected
    assert result.result is None and lua.globals().rank_callbacks == 0


def test_full_profile_missing_mode_and_quick_profile_are_distinct(runtime):
    lua, api = runtime
    summary = run_mode(lua, api, MODES[0])
    summaries = lua.table_from([summary])
    assert "failure_class = collector_missing_summary" in api.summary("synthetic-batch", summaries)
    assert "failure_class = collector_missing_summary" in api.diff("synthetic-batch", summaries)
    summary.validation_profile = "quick"
    assert api.aggregate(lua.table_from({MODES[0]: summary})).run_valid is True


def _with_write_b1_safety_hunks(expected):
    """Project only the reviewed WRITE-B1 guarded-region additions."""
    additions = {
        "execution_preconditions_ok": (
            ("execution_identity_ok", "false"), ("write_ready", "false"),
            ("write_readiness_failure_class", "nil"), ("execution_success", "false"),
        ),
        "write_attempted": (("write_api_ok", "false"),),
        "write_ok": (
            ("restore_attempted", "false"), ("restore_write_ok", "false"),
            ("restore_readback_ok", "false"),
        ),
    }
    replacements = []
    for anchor, fields in additions.items():
        for template in (
            '    {name} = {value},\n',
            '  print_kv("{name}", source and source.{name})\n',
            '  lines[#lines + 1] = "{name} = " .. tostring(source and source.{name})\n',
        ):
            old = template.format(name=anchor, value="false")
            new = old + "".join(template.format(name=name, value=value) for name, value in fields)
            replacements.append((old, new))
    replacements.extend((
        ('    executor_version = "guarded_write_v2",', '    executor_version = "guarded_write_v3",'),
        ('  if summary == nil then\n    return nil\n',
         '  if type(summary) ~= "table" then\n    return nil\n'),
        (
            '  local rank_b = rank_position(no_probe_b)\n  return {\n',
            '''  local rank_b = rank_position(no_probe_b)
  local source = type(no_probe_a) == "table" and no_probe_a or {}
  local context_ok = source.case_id ~= nil and source.session_id ~= nil
  for _, summary in pairs({A = no_probe_a or false, W = with_probe or false, B = no_probe_b or false}) do
    if type(summary) ~= "table" or summary.run_valid ~= true
        or summary.error ~= nil or summary.failure_class ~= nil or summary.collector_empty == true
        or summary.validation_profile ~= "full"
        or summary.case_id ~= source.case_id
        or summary.session_id ~= source.session_id then
      context_ok = false
    end
  end
  return {
    case_id = source.case_id,
    session_id = source.session_id,
    validation_profile = source.validation_profile,
''',
        ),
        ('    ok = rank_a == 1 and rank_w == 1 and rank_b == 1,',
         '    ok = context_ok and rank_a == 1 and rank_w == 1 and rank_b == 1,'),
    ))
    for old, new in replacements:
        # Idempotence supports the exact pending source as a synthetic fixture.
        if new not in expected:
            assert expected.count(old) == 1
            expected = expected.replace(old, new, 1)
        assert expected.count(new) == 1
    return expected


def test_scoring_collection_policy_and_write_controls_are_unchanged():
    def previous(path):
        return subprocess.check_output(
            ["git", "show", f"6cc848069e9001f98a8fe520182abc1e042d6671:{path.relative_to(ROOT).as_posix()}"],
            cwd=ROOT, text=True, encoding="utf-8",
        )

    def section(source, start, end):
        assert source.count(start) == source.count(end) == 1
        return source.split(start, 1)[1].split(end, 1)[0]

    report = REPORT.read_text(encoding="utf-8")
    assert report.split("function MVP0.run(", 1)[0] == previous(REPORT).split("function MVP0.run(", 1)[0]
    collector = COLLECTOR.read_text(encoding="utf-8")
    def collection_policy(source):
        # R1 removes one unused retained score tree; all policy code stays frozen.
        # Full output equivalence and 30k memory bounds have separate regressions.
        source = source.replace(
            "        -- Selection consumes only these compact keys, not the full score tree.\n",
            "        score_result = score_result,\n", 1)
        return source.split("local function snapshot_failure", 1)[0].split(
            "local function run_stable_no_probe_intersection", 1
        )[0]

    assert collection_policy(collector) == collection_policy(previous(COLLECTOR))
    batch = BATCH.read_text(encoding="utf-8")
    # The immutable signed Single checkpoint keeps this guard independent of
    # HEAD changes. Compare presets/config without removing the Single arm.
    published_batch = previous(BATCH)
    single_branch = 'if profile == "full" or profile == "quick" or profile == "single" then'
    assert batch.count(single_branch) == published_batch.count(single_branch) == 1
    start, end = "local MODE_PRESETS", "local original_print"
    assert section(batch, start, end) == section(published_batch, start, end)

    # Accept the checkpoint region or its complete, exact pending WRITE-B1
    # projection. Partial additions or changed safety controls fail in either
    # the isolated TRUTH-01 tree or the shared development worktree.
    start, end = "local function build_default_execution_result", "function load_value_executor"
    actual = section(batch, start, end)
    expected = section(published_batch, start, end)
    assert actual in (expected, _with_write_b1_safety_hunks(expected))
    assert 'execution_mode = "disabled"' in batch and 'write_enabled = false' in batch
