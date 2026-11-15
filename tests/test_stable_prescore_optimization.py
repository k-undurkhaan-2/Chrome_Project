"""Differential tests and an opt-in benchmark for stable snapshot prescoring.

Run with optional lupa.lua54, as in test_screening_validity_timing.py. The real
collector, candidate reader, scorer, selector and ranker run against Lua tables;
there is no CE, target process, runtime config I/O, or memory-write API. The
baseline reverses only this round's three added lines in the LOCAL source, so
it retains the pre-existing validity/timing fixes rather than using Git HEAD.

Benchmark: python tests/test_stable_prescore_optimization.py --benchmark
It alternates before/after order, warms both variants, checks equivalence on
every pair, and reports medians. Wall time ends at the actual rank callback,
before recommendation/report rendering; module loading/fixture setup are outside
the measurement. These synthetic timings are not real CE performance evidence.
"""

from collections import Counter
from pathlib import Path
from statistics import median
from time import perf_counter
import argparse
import json

import pytest


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "src/mvp0_foundlist_collector.lua"
REPORT = ROOT / "src/mvp0_candidate_report.lua"
BATCH = ROOT / "src/execute_module-v5.2.0_batch.lua"
BASE = 0x10000000
STRIDE = 0x200
TRUTH = BASE + STRIDE + 0x28
MODES = ("no_probe_A", "with_probe", "no_probe_B")
ADDED_LINES = (
    "  -- Only complete filtered lists feed the intersection; prescore its result once.\n",
    "  snapshot_a_opts.use_prescore_selection = false\n",
    "  snapshot_b_opts.use_prescore_selection = false\n",
)


def collector_sources():
    after = COLLECTOR.read_text(encoding="utf-8")
    before = after
    for line in ADDED_LINES:
        assert before.count(line) == 1
        before = before.replace(line, "", 1)
    return before, after


SYNTHETIC_IO = """
    local original_clock = os.clock
    python = nil; io = nil; package = nil; require = nil
    loadfile = nil; dofile = nil
    tick = 0; report_cost = 200; output_cost = 0
    os = {clock = function() return fake_clock and tick / 1000 or original_clock() end}
    getTickCount = function() return tick end
    print = function() tick = tick + output_cost end

    function configure(scenario, count)
        tick = 0; active_snapshot = 0; collect_depth = 0; build_depth = 0
        rank_callbacks = 0; build_calls = 0; score_calls = 0; rank_calls = 0
        snapshots = {}; lifecycle = {}; collection_reads = {}; filter_reads = {}
        snapshot_lists = {{}, {}}; memory = {{}, {}}; rules = {{}, {}}
        fault = nil; fault_snapshot = nil
        local base, stride, pattern = 0x10000000, 0x200, 0x42C80000
        for s = 1, 2 do
            for id = 1, count * 2 + 60 do
                local addr = base + id * stride + 0x28
                local included = id <= count
                if s == 2 and scenario == 'changing' then
                    included = id == 1 or (id > 60 and id <= count + 60)
                elseif s == 2 and scenario == 'disjoint' then
                    included = id > count and id <= count * 2
                elseif s == 2 and scenario == 'truth_missing' and id == 1 then
                    included = false
                end
                if scenario == 'empty_both' or (scenario == 'empty_a' and s == 1)
                    or (scenario == 'empty_b' and s == 2) then included = false end
                if included then table.insert(snapshot_lists[s], 1, addr) end
                local kind = id % 6
                if scenario == 'changing' and id % 5 == 0 then kind = (id + s) % 6 end
                local fields
                if id == 1 then
                    fields = {base+0x10100, base+0x10180, base+0x10200,
                              7, base+0x20100, base+0x20180, base+0x20200}
                elseif kind == 0 then fields = {0, 0, 0, 0, 0, 0, 0}
                elseif kind == 1 then fields = {0x3F800000, 0x3F800000, 0, 0, 0x43300000, 0, 0}
                elseif kind == 2 then fields = {1, 2, 3, 4, 5, 6, 7}
                elseif kind == 3 then fields = {0x10040000, 0x10040000, 0x10040000,
                                              1, 0x10040000, 0x10040000, 0x10040000}
                elseif kind == 4 then fields = {0x41424344, 0x45464748, 0x494A4B4C,
                                              0, 0x51525354, 0x55565758, 0x595A3031}
                else fields = {base+0x30100, base+0x30180, base+0x30200, 1, 0, 0, 0} end
                for i, offset in ipairs({0x08, 0x18, 0x20, 0x58, 0x68, 0x70, 0x78}) do
                    memory[s][addr - 0x28 + offset] = fields[i]
                end
                memory[s][addr] = pattern
                if scenario == 'mismatch_retry' then
                    if id == 1 or id % 13 == 0 then rules[s][addr] = 'recover'
                    elseif id % (s == 1 and 11 or 7) == 0 then rules[s][addr] = 'mismatch'
                    elseif id % 17 == 0 then rules[s][addr] = 'unreadable'
                    elseif id % 19 == 0 then rules[s][addr] = 'retry_unreadable' end
                elseif scenario == 'all_mismatch' then rules[s][addr] = 'mismatch' end
            end
            -- Unsorted input and duplicate addresses exercise real deduplication.
            if #snapshot_lists[s] > 0 then
                table.insert(snapshot_lists[s], snapshot_lists[s][1])
            end
        end
    end

    getCurrentMemscan = function()
        active_snapshot = active_snapshot + 1
        assert(active_snapshot <= 2, 'unexpected extra collection')
        filter_reads = {}; tick = tick + 1
        table.insert(lifecycle, {'memscan', active_snapshot})
        if fault == 'memscan' and fault_snapshot == active_snapshot then return nil end
        return {synthetic_snapshot = active_snapshot}
    end
    createFoundList = function(scan)
        assert(scan.synthetic_snapshot == active_snapshot)
        local index = active_snapshot
        local addresses = snapshot_lists[index]
        local list = {Count = #addresses, Address = {}}
        for i, addr in ipairs(addresses) do list.Address[i - 1] = addr end
        tick = tick + 1; table.insert(lifecycle, {'create', index})
        list.initialize = function()
            if fault == 'initialize' and fault_snapshot == index then
                error('synthetic initialization failure', 0)
            end
            tick = tick + 1; table.insert(lifecycle, {'initialize', index})
        end
        list.destroy = function()
            tick = tick + 1; table.insert(lifecycle, {'destroy', index})
        end
        return list
    end
    readInteger = function(addr)
        tick = tick + 0.25
        local value = memory[active_snapshot][addr]
        if collect_depth > 0 and build_depth == 0 then
            local rule = rules[active_snapshot][addr]
            filter_reads[addr] = (filter_reads[addr] or 0) + 1
            local n = filter_reads[addr]
            if rule == 'mismatch' or (rule == 'recover' and n == 1) then value = 0x3F800000
            elseif rule == 'unreadable' then value = nil
            elseif rule == 'retry_unreadable' then value = n == 1 and 0x3F800000 or nil end
            table.insert(collection_reads, {active_snapshot, addr, value or 'nil'})
        end
        return value
    end
    readFloat = function() tick = tick + 0.25; return 100.0 end
"""


INSTRUMENTATION = """
    local build = MVP0.build_candidate
    MVP0.build_candidate = function(...)
        build_calls = build_calls + 1; build_depth = build_depth + 1
        local candidate = build(...)
        build_depth = build_depth - 1
        return candidate
    end
    local score = MVP0.score_candidate
    MVP0.score_candidate = function(...)
        score_calls = score_calls + 1; tick = tick + 1
        if fault == 'final_score' and collect_depth == 0 then
            error('synthetic final scoring failure', 0)
        end
        return score(...)
    end
    local rank = MVP0.rank_candidates
    MVP0.rank_candidates = function(...)
        rank_calls = rank_calls + 1; tick = tick + 3
        if fault == 'final_rank' then error('synthetic final ranking failure', 0) end
        local result = rank(...)
        rank_finished_at = tick
        return result
    end
    local recommend = MVP0.recommend_action
    MVP0.recommend_action = function(...)
        tick = tick + 7
        return recommend(...)
    end
    local render = MVP0.render_report
    MVP0.render_report = function(...)
        render_started_at = tick; tick = tick + report_cost
        return render(...)
    end
    local collect = MVP0FoundList.collect
    MVP0FoundList.collect = function(opts)
        collect_depth = collect_depth + 1
        local builds_before, scores_before = build_calls, score_calls
        local bundle = collect(opts)
        snapshots[#snapshots + 1] = {
            options = opts, bundle = bundle, debug = MVP0FoundList.LAST_FILTER_DEBUG,
            builds = build_calls - builds_before, scores = score_calls - scores_before,
        }
        collect_depth = collect_depth - 1
        if active_snapshot == fault_snapshot then
            if fault == 'missing' then return nil
            elseif fault == 'invalid_count' then bundle.raw_count = nil
            elseif fault == 'error' then bundle.error = 'synthetic snapshot failure'
            elseif fault == 'empty_with_error' then
                bundle.failure_class = 'collector_runtime_empty'
                bundle.error = 'synthetic snapshot failure'
            elseif fault == 'explicit_failure' then bundle.failure_class = 'specific_snapshot_failure'
            elseif fault == 'invalid_run' then bundle.run_valid = false end
        end
        return bundle
    end
    function synthetic_run(opts)
        collectgarbage('collect')
        local start_tick, start_wall = tick, wall_time()
        opts.on_rank_complete = function()
            rank_callbacks = rank_callbacks + 1
            screening_compute_ms = tick - start_tick
            screening_wall_ms = (wall_time() - start_wall) * 1000
        end
        return MVP0FoundList.run(opts)
    end
"""


def new_runtime(source, scenario="identical", count=360, *, fake_clock=True):
    lua54 = pytest.importorskip("lupa.lua54", reason="synthetic checks require optional lupa.lua54")
    lua = lua54.LuaRuntime(register_eval=False, register_builtins=False)
    lua.globals().fake_clock = fake_clock
    lua.globals().wall_time = perf_counter
    lua.execute(SYNTHETIC_IO)
    lua.execute(REPORT.read_text(encoding="utf-8"))
    lua.execute(source)
    lua.execute(INSTRUMENTATION)
    lua.globals().configure(scenario, count)
    return lua


def options(lua, *, mode="stable_no_probe_intersection", prescore=True, budget=2000,
            bucket_shift=12):
    return lua.table_from({
        "max_candidates": 100, "scan_budget": budget,
        "target_value_pattern": 0x42C80000, "target_value_float": 100.0,
        "known_true_addr": TRUTH, "filter_target_match": True,
        "use_prescore_selection": prescore, "bucket_shift": bucket_shift, "max_per_bucket": 3,
        "probe_full_foundlist": mode == "with_probe", "session_mode": mode,
        "stable_no_probe_intersection_enabled": mode == "stable_no_probe_intersection",
    })


def plain(value, *, omit_timings=True):
    """Compare all nested scoring features, penalties, tie vectors and report text."""
    if hasattr(value, "items"):
        return {key: plain(item, omit_timings=omit_timings) for key, item in value.items()
                if not (omit_timings and isinstance(key, str) and key.endswith("_ms"))}
    return value


def array(value):
    return [value[i] for i in range(1, len(value) + 1)]


def batch_api(lua):
    source = BATCH.read_text(encoding="utf-8")
    lua.compile(source)
    startup = "RUN_CASES = apply_local_case_config(RUN_CASES, LOCAL_CASE_CONFIG_PATH)"
    assert source.count(startup) == 1
    source = source.replace(startup, "-- Synthetic test: no runtime config I/O.")
    source, tail = source.rsplit("\nmain()", 1)
    assert not tail.strip()
    return lua.execute(source + """
        load_modules = function() end
        write_text_file = function() end
        evaluate_value_execution = function() return {} end
        return {validate = validate_collector_bundle, mode = run_case_mode,
                stable = run_stable_intersection_mode, aggregate = build_case_runtime_diagnostics}
    """)


def assert_equivalent(before, after):
    old_lua, old_bundle = before
    new_lua, new_bundle = after
    assert plain(old_bundle) == plain(new_bundle)
    assert plain(old_lua.globals().MVP0FoundList.LAST_FILTER_DEBUG) == plain(
        new_lua.globals().MVP0FoundList.LAST_FILTER_DEBUG)
    assert plain(old_lua.globals().lifecycle) == plain(new_lua.globals().lifecycle)
    assert plain(old_lua.globals().collection_reads) == plain(new_lua.globals().collection_reads)


@pytest.mark.parametrize("scenario,count,budget", [
    ("identical", 360, 2000), ("changing", 360, 2000),
    ("mismatch_retry", 360, 2000), ("truth_missing", 360, 2000),
    ("disjoint", 160, 2000), ("empty_a", 160, 2000),
    ("empty_b", 160, 2000), ("empty_both", 160, 2000),
    ("all_mismatch", 160, 2000), ("identical", 80, 2000),
    ("identical", 800, 240), ("identical", 1500, 2000),
])
def test_stable_exact_equivalence_and_two_fresh_collections(scenario, count, budget):
    runs = []
    for source in collector_sources():
        lua = new_runtime(source, scenario, count)
        opts = options(lua, budget=budget)
        bundle = lua.globals().synthetic_run(opts)
        runs.append((lua, bundle))
        g = lua.globals()
        assert g.active_snapshot == 2 and len(g.snapshots) == 2
        assert array(g.lifecycle[1]) == ["memscan", 1]
        assert array(g.lifecycle[5]) == ["memscan", 2]
        assert array(g.lifecycle[8]) == ["destroy", 2]
        a = array(g.snapshots[1].debug.matched_addresses)
        b = array(g.snapshots[2].debug.matched_addresses)
        a_set = set(a)
        expected = [addr for addr in b if addr in a_set]
        assert array(g.MVP0FoundList.LAST_FILTER_DEBUG.matched_addresses) == expected
        assert bundle.selected_count == min(100, len(expected))
        assert len(bundle.result.ranked) == bundle.selected_count
        if count == 1500:
            # This larger pool already excludes truth at the selected cap in the
            # baseline. Optimization must preserve that outcome and its reason.
            assert bundle.true_in_filtered is True and bundle.true_in_prescored is True
            assert bundle.true_in_selected is False and bundle.known_true_rank_position is None
            assert bundle.selected_drop_reason is not None
        else:
            assert bundle.known_true_rank_position == (1 if TRUTH in expected else None)
        assert opts.use_prescore_selection is True  # snapshot overrides never mutate caller
        assert g.rank_callbacks == 1 and g.rank_calls == 1
        assert g.screening_compute_ms == g.rank_finished_at
        assert g.render_started_at > g.rank_finished_at
        for snapshot in array(g.snapshots):
            assert snapshot.options.scan_budget == budget
            assert snapshot.options.max_candidates == 100
            assert snapshot.options.filter_target_match is True
            assert snapshot.options.probe_full_foundlist is False
            assert snapshot.options.stable_filter_intersection_enabled is False
            assert snapshot.options.delayed_recheck_enabled is False
        if scenario == "mismatch_retry":
            for snapshot in array(g.snapshots):
                for key in ("retry_recovered_count", "retry_still_mismatch_count",
                            "read_failed_count", "retry_read_failed_count"):
                    assert snapshot.debug[key] > 0
        if len(expected) > 100:
            assert bundle.selection_strategy == "prescore_diverse_top_scored"
            assert bundle.prescored_count == len(expected)
            assert bundle.prescore_tied_count > 1
            scores = [item.final_score for item in array(bundle.result.ranked)]
            assert len(set(scores)) < len(scores)  # final ties actually exercised
        for key in ("stable_snapshot_A_ms", "stable_snapshot_B_ms", "stable_intersection_build_ms",
                    "filter_ms", "prescore_ms", "prescore_read_ms", "prescore_score_ms",
                    "prescore_sort_ms", "prescore_select_ms", "prescore_detail_ms"):
            assert isinstance(bundle[key], (int, float)) and bundle[key] >= 0
        validated = batch_api(lua).validate(bundle, "stable_no_probe_intersection")
        assert validated.run_valid is (scenario not in {"empty_a", "empty_b", "empty_both"})
        assert validated.failure_class == (
            "collector_runtime_empty" if scenario in {"empty_a", "empty_b", "empty_both"} else None)
    assert_equivalent(*runs)
    old, new = (run[0].globals() for run in runs)
    removed = sum(s.scores for s in array(old.snapshots))
    assert new.score_calls == old.score_calls - removed
    assert new.build_calls == old.build_calls - removed
    filtered_count = runs[1][1].filtered_count
    assert new.score_calls == (filtered_count if filtered_count > 100 else 0) + runs[1][1].selected_count
    for snapshot in array(new.snapshots):
        assert snapshot.scores == snapshot.builds == 0
        assert snapshot.bundle.use_prescore_selection is False
        assert snapshot.bundle.selection_strategy == "evenly_spread"
        assert snapshot.bundle.prescored_count is None
        assert snapshot.debug.prescore_score_ms == snapshot.debug.prescore_read_ms == 0


@pytest.mark.parametrize("prescore", [None, False])
@pytest.mark.parametrize("bucket_shift", [12, 30])
def test_default_and_disabled_prescore_and_diversity_fallback(prescore, bucket_shift):
    runs = []
    for source in collector_sources():
        lua = new_runtime(source)
        bundle = lua.globals().synthetic_run(options(lua, prescore=prescore, bucket_shift=bucket_shift))
        runs.append((lua, bundle))
        assert bundle.selected_count == 100
        assert bundle.use_prescore_selection is (prescore is not False)
        buckets = Counter(addr // 2**bucket_shift for addr in array(bundle.candidate_value_addrs))
        if prescore is not False and bucket_shift == 12:
            assert max(buckets.values()) <= 3
        elif bucket_shift == 30:
            assert max(buckets.values()) == 100  # deferred fill still reaches the selected cap
    assert_equivalent(*runs)


@pytest.mark.parametrize("mode", MODES)
def test_normal_a_w_b_prescoring_unchanged(mode):
    runs = []
    for source in collector_sources():
        lua = new_runtime(source, count=800)
        bundle = lua.globals().synthetic_run(options(lua, mode=mode, budget=240))
        runs.append((lua, bundle))
        assert lua.globals().active_snapshot == 1
        assert lua.globals().snapshots[1].scores > 100
        assert bundle.use_prescore_selection is True and bundle.selected_count == 100
        assert bundle.raw_probe_full_foundlist_enabled is (mode == "with_probe")
    assert_equivalent(*runs)
    assert runs[0][0].globals().score_calls == runs[1][0].globals().score_calls


@pytest.mark.parametrize("snapshot", [1, 2])
@pytest.mark.parametrize("fault,expected", [
    ("missing", "collector_missing_summary"), ("invalid_count", "collector_invalid_raw_count"),
    ("error", "collector_error"), ("empty_with_error", "collector_error"),
    ("explicit_failure", "specific_snapshot_failure"), ("invalid_run", "collector_error"),
    ("memscan", "collector_exception"), ("initialize", "collector_exception"),
])
def test_snapshot_failures_still_invalidate_run(snapshot, fault, expected):
    results = []
    for source in collector_sources():
        lua = new_runtime(source, count=120)
        lua.globals().fault = fault
        lua.globals().fault_snapshot = snapshot
        api = batch_api(lua)
        cfg = options(lua)
        cfg.case_id = cfg.session_id = "synthetic"
        cfg.validation_profile = "full"; cfg.diagnostic_level = "basic"
        cfg.execution_mode = "disabled"; cfg.write_enabled = False
        prior = lua.table_from({"raw_count": 120})
        result = api.stable(cfg, prior, prior, prior, "synthetic")
        assert result.run_valid is False and result.failure_class == expected
        assert result.screening_compute_ms is None
        assert lua.globals().rank_calls == 0
        assert lua.globals().active_snapshot == snapshot
        results.append((result.failure_class, result.collector_empty))
        if fault in {"error", "empty_with_error"}:
            assert "synthetic snapshot failure" in result.error
        elif fault == "initialize":
            assert "synthetic initialization failure" in result.error
        elif fault == "memscan":
            assert "No active memscan" in result.error
    assert results[0] == results[1]


@pytest.mark.parametrize("fault", ["final_score", "final_rank"])
def test_final_scoring_and_ranking_failures_still_invalidate_run(fault):
    for source in collector_sources():
        lua = new_runtime(source, count=120)
        lua.globals().fault = fault
        api = batch_api(lua)
        cfg = options(lua)
        cfg.case_id = cfg.session_id = "synthetic"
        cfg.validation_profile = "full"; cfg.diagnostic_level = "basic"
        cfg.execution_mode = "disabled"; cfg.write_enabled = False
        prior = lua.table_from({"raw_count": 120})
        result = api.stable(cfg, prior, prior, prior, "synthetic")
        assert result.run_valid is False and result.failure_class == "collector_exception"
        assert "synthetic final" in result.error
        assert result.screening_compute_ms is None


@pytest.mark.parametrize("mode", (*MODES, "stable_no_probe_intersection"))
def test_real_pipeline_screening_timer_stops_before_rendering(mode):
    measurements = []
    for report_cost in (200, 9000):
        lua = new_runtime(collector_sources()[1], count=120)
        lua.globals().report_cost = report_cost
        api = batch_api(lua)
        cfg = options(lua, mode=mode)
        cfg.case_id = cfg.session_id = "synthetic"
        cfg.validation_profile = "full"; cfg.diagnostic_level = "basic"
        cfg.execution_mode = "disabled"; cfg.write_enabled = False
        if mode == "stable_no_probe_intersection":
            prior = lua.table_from({"raw_count": 120})
            result = api.stable(cfg, prior, prior, prior, "synthetic")
        else:
            result = api.mode(cfg, mode, "synthetic")
        assert result.run_valid is True, result.error
        assert result.screening_compute_ms == lua.globals().rank_finished_at
        assert result.collector_call_ms > result.screening_compute_ms
        measurements.append(result.screening_compute_ms)
    assert measurements[0] == measurements[1]


def benchmark(repeats=9, count=1500):
    sources = collector_sources()
    samples = [[], []]
    metric_names = ("stable_snapshot_A_ms", "stable_snapshot_B_ms", "stable_intersection_build_ms",
                    "prescore_ms", "prescore_read_ms", "prescore_score_ms", "prescore_sort_ms",
                    "prescore_select_ms")
    for repetition in range(repeats + 2):
        runs = [None, None]
        for variant in ((0, 1) if repetition % 2 == 0 else (1, 0)):
            lua = new_runtime(sources[variant], count=count, fake_clock=False)
            bundle = lua.globals().synthetic_run(options(lua))
            runs[variant] = (lua, bundle)
            if repetition >= 2:
                samples[variant].append({
                    "screening_wall_ms": lua.globals().screening_wall_ms,
                    "score_calls": lua.globals().score_calls,
                    **{key: bundle[key] for key in metric_names},
                })
        assert_equivalent(*runs)
        assert runs[1][1].selected_count == 100
    medians = [{key: round(median(sample[key] for sample in group), 3)
                for key in group[0]} for group in samples]
    print(json.dumps({
        "fixture": "identical fresh snapshots, duplicate raw entry, real scoring and ranking",
        "filtered_per_snapshot": count, "selected": 100, "warmups_per_variant": 2,
        "known_true_rank_position": runs[1][1].known_true_rank_position,
        "true_in_selected": runs[1][1].true_in_selected,
        "selected_drop_reason": runs[1][1].selected_drop_reason,
        "repeats_per_variant": repeats, "before_median": medians[0], "after_median": medians[1],
        "screening_reduction_percent": round(
            (1 - medians[1]["screening_wall_ms"] / medians[0]["screening_wall_ms"]) * 100, 2),
        "samples": samples,
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", action="store_true", required=True)
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--candidates", type=int, default=1500)
    arguments = parser.parse_args()
    if arguments.repeats < 3 or not 100 < arguments.candidates < 2000:
        parser.error("use at least 3 repeats and between 101 and 1999 candidates")
    benchmark(arguments.repeats, arguments.candidates)
