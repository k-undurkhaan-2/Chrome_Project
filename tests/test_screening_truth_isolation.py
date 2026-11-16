"""SCREENING-TRUTH-01: blind Single, with a separate frozen-output evaluator.

Only the existing isolated Lua 5.4 table-backed fixture runs. The evaluator is
testing-only: it accepts an immutable, completed result and an independent label,
has no Lua/config/collector reference, and never annotates the production result.
"""

from dataclasses import dataclass, FrozenInstanceError
from pathlib import Path
import subprocess

import pytest

from test_screening_single_mode import (
    BATCH, TRUTH, array, assert_no_execution, outputs, plain, runtime,
)
from test_screening_validity_timing import (
    _with_write_b1_safety_hunks,
    test_scoring_collection_policy_and_write_controls_are_unchanged as check_static_guard,
)


def freeze(value):
    if hasattr(value, "items"):
        return tuple(sorted((str(key), freeze(item)) for key, item in value.items()))
    return value


@dataclass(frozen=True)
class FrozenScreening:
    run_valid: bool
    ranked: tuple
    evidence: tuple


def screening_state(lua, summary):
    """All collector outputs, reads, diagnostics, saved text and fake-clock times."""
    g = lua.globals()
    return freeze({
        "bundle": g.captured_runs[1].bundle,
        "summary": summary,
        "filter_debug": g.MVP0FoundList.LAST_FILTER_DEBUG,
        "reads": g.collection_reads,
        "lifecycle": g.lifecycle,
        "logs": g.written_logs,
        "tick": g.tick,
        "build_calls": g.build_calls,
        "score_calls": g.score_calls,
        "rank_calls": g.rank_calls,
    })


def freeze_screening(lua, summary):
    bundle = lua.globals().captured_runs[1].bundle
    # Invalid runs may have no usable ranking; retain their invalid status and
    # freeze no candidates instead of fabricating a completed screening result.
    ranked = ()
    if summary.run_valid is True:
        ranked = tuple((entry.candidate.value_addr, entry.rank_position)
                       for entry in array(bundle.result.ranked))
    return FrozenScreening(summary.run_valid, ranked, screening_state(lua, summary))


def compare_development_truth(frozen, independently_confirmed_addr):
    """Pure post-run evaluation; no label is sent back to the screening runtime."""
    rank = None
    if independently_confirmed_addr is None:
        status = "no_label"
    elif not frozen.run_valid:
        status = "invalid_screening"
    else:
        rank = next((rank for addr, rank in frozen.ranked
                     if addr == independently_confirmed_addr), None)
        status = "matched" if rank is not None else "absent"
    return {"scope": "development_post_run", "status": status, "rank_position": rank}


@pytest.mark.parametrize("scenario,count,budget", [
    ("identical", 80, 2000), ("identical", 360, 2000),
    ("identical", 800, 240), ("identical", 1500, 2000),
    ("mismatch_retry", 360, 2000), ("empty_a", 120, 2000),
    ("all_mismatch", 120, 2000),
])
@pytest.mark.parametrize("level", ["basic", "debug", "trace"])
def test_truth_labels_cannot_change_any_single_output_or_timing(scenario, count, budget, level):
    states = []
    for truth in (None, TRUTH, 0x7FFFFFFF):
        lua, api, cfg = runtime(scenario=scenario, count=count, budget=budget, truth=truth)
        cfg.diagnostic_level = level
        cfg.known_true_addr_source = "local" if truth is not None else "default"
        # Legacy requests and the collector fallback cannot enable Single probes.
        cfg.probe_full_foundlist = True
        lua.globals().MVP0FoundList.CONFIG.default_probe_full_foundlist = True
        before = plain(cfg)
        api.main()
        g = lua.globals()
        summary = g.captured_summaries[1]
        entry = g.captured_runs[1]
        assert plain(cfg) == before
        assert entry.options.known_true_addr is None and entry.bundle.known_true_addr is None
        assert entry.options.probe_full_foundlist is False
        assert entry.bundle.raw_probe_full_foundlist_enabled is False
        assert entry.bundle.raw_probe_used == entry.bundle.raw_probe_quota == 0
        assert entry.bundle.true_foundlist_index is None
        assert summary.known_true_addr is summary.known_true_rank_position is None
        assert summary.true_in_selected is None
        assert summary.known_true_addr_source == "not_evaluated"
        assert summary.baseline_eligible is False and summary.write_attempted is False
        if scenario == "empty_a":
            assert summary.run_valid is False and summary.failure_class == "collector_runtime_empty"
        elif scenario == "all_mismatch":
            assert summary.run_valid is False and summary.failure_class == "collector_invalid_result"
        else:
            assert summary.run_valid is True and summary.failure_class is summary.error is None
            assert entry.bundle.selected_count == min(100, entry.bundle.filtered_count)
            assert len(entry.bundle.result.ranked) == entry.bundle.selected_count
        for text in outputs(lua).values():
            assert "known_true_addr_source = not_evaluated" in text
            assert "known_true_rank_position = nil" in text
            assert "true_in_selected = nil" in text
            assert "known_true_rank_position = 1" not in text
            assert "true_in_raw = false" not in text and "true_in_filtered = false" not in text
        states.append(screening_state(lua, summary))
        assert_no_execution(lua)
    assert states[0] == states[1] == states[2]


def test_single_never_looks_up_the_legacy_truth_label():
    lua, api, cfg = runtime()
    lua.globals().guarded_cfg = cfg
    lua.execute("""
        guarded_cfg.known_true_addr = nil
        guarded_cfg.known_true_addr_source = nil
        setmetatable(guarded_cfg, {__index = function(_, key)
            if key == 'known_true_addr' or key == 'known_true_addr_source' then
                error('Single consulted the legacy truth label')
            end
        end})
    """)
    before = plain(cfg)
    summary = api.mode(cfg, "no_probe_A", "synthetic-single")
    assert summary.run_valid is True, summary.error
    assert plain(cfg) == before
    assert lua.globals().captured_runs[1].options.known_true_addr is None
    assert_no_execution(lua)


def test_truth_omitted_from_raw_sampling_is_not_injected_but_full_probe_still_works():
    lua, api, cfg = runtime(count=800, budget=240)
    summary = api.mode(cfg, "no_probe_A", "synthetic-single")
    g = lua.globals()
    admitted = set(array(g.MVP0FoundList.LAST_FILTER_DEBUG.matched_addresses))
    # Every synthetic value matches: the complete filtered set is exactly the
    # deduplicated raw admission set, before Top-100 selection.
    assert g.MVP0FoundList.LAST_FILTER_DEBUG.value_mismatch_count == 0
    assert g.captured_runs[1].bundle.unique_count == len(admitted)
    omitted = next(addr for addr in array(g.snapshot_lists[1]) if addr not in admitted)
    before = screening_state(lua, summary)

    labelled, labelled_api, labelled_cfg = runtime(count=800, budget=240, truth=omitted)
    labelled_summary = labelled_api.mode(labelled_cfg, "no_probe_A", "synthetic-single")
    assert screening_state(labelled, labelled_summary) == before
    assert omitted not in array(labelled.globals().MVP0FoundList.LAST_FILTER_DEBUG.matched_addresses)
    assert omitted not in array(labelled.globals().captured_runs[1].bundle.candidate_value_addrs)
    assert labelled.globals().captured_runs[1].bundle.raw_probe_used == 0
    assert_no_execution(labelled)

    development, dev_api, dev_cfg = runtime("full", count=800, budget=240, truth=omitted)
    dev_summary = dev_api.mode(dev_cfg, "with_probe", "synthetic-development")
    dev_bundle = development.globals().captured_runs[1].bundle
    assert dev_summary.run_valid is True
    assert dev_bundle.known_true_addr == omitted and dev_bundle.true_in_raw is True
    assert dev_bundle.raw_probe_full_foundlist_enabled is True and dev_bundle.raw_probe_used > 0
    assert dev_bundle.true_foundlist_index is not None
    assert omitted in array(development.globals().MVP0FoundList.LAST_FILTER_DEBUG.matched_addresses)
    assert dev_cfg.validation_profile == "full"  # Truth-assisted development diagnostic only.


@pytest.mark.parametrize("label,status,rank", [
    (TRUTH, "matched", 1), (0x7FFFFFFF, "absent", None), (None, "no_label", None),
])
def test_development_comparison_uses_immutable_final_output_without_feedback(label, status, rank):
    lua, api, _ = runtime()
    api.main()
    g = lua.globals()
    summary = g.captured_summaries[1]
    frozen = freeze_screening(lua, summary)
    assert frozen.run_valid is True and g.rank_calls == 1
    assert summary.known_true_rank_position is None
    comparison = compare_development_truth(frozen, label)
    assert comparison == {"scope": "development_post_run", "status": status, "rank_position": rank}
    assert frozen.evidence == screening_state(lua, summary)
    assert g.captured_runs[1].options.known_true_addr is None
    with pytest.raises(FrozenInstanceError):
        frozen.run_valid = False
    with pytest.raises(TypeError):
        frozen.ranked[0] = (0x7FFFFFFF, 1)
    assert_no_execution(lua)


def test_post_run_comparison_does_not_invent_a_rank_for_invalid_screening():
    lua, api, _ = runtime(scenario="all_mismatch")
    api.main()
    summary = lua.globals().captured_summaries[1]
    frozen = freeze_screening(lua, summary)
    assert frozen.run_valid is False
    assert compare_development_truth(frozen, TRUTH) == {
        "scope": "development_post_run", "status": "invalid_screening", "rank_position": None,
    }
    assert frozen.evidence == screening_state(lua, summary)


@pytest.mark.parametrize("fault", ["memscan", "initialize", "final_score", "final_rank"])
def test_labels_cannot_change_failure_classification_or_restore_completed_time(fault):
    states = []
    for truth in (None, TRUTH, 0x7FFFFFFF):
        lua, api, _ = runtime(truth=truth)
        lua.globals().fault, lua.globals().fault_snapshot = fault, 1
        api.main()
        summary = lua.globals().captured_summaries[1]
        assert summary.run_valid is False and summary.failure_class == "collector_exception"
        assert summary.screening_compute_ms is summary.known_true_addr is None
        assert summary.known_true_addr_source == "not_evaluated"
        states.append(screening_state(lua, summary))
        assert_no_execution(lua)
    assert states[0] == states[1] == states[2]


@pytest.mark.parametrize("entry", ["nil", "false", "42", "{}", "'unknown'"])
def test_malformed_or_missing_modes_remain_fail_closed(entry):
    lua, api, cfg = runtime(truth=TRUTH)
    before = plain(cfg)
    with pytest.raises(Exception, match="unsupported mode entry|unknown mode preset"):
        api.mode(cfg, lua.eval(entry), "synthetic-single")
    g = lua.globals()
    assert len(g.captured_runs) == len(g.snapshots) == len(g.written_logs) == 0
    assert plain(cfg) == before
    assert_no_execution(lua)


def test_value_and_float32_pattern_remain_search_inputs_and_callback_marks_final_rank():
    states = []
    for truth in (None, TRUTH):
        lua, api, cfg = runtime(truth=truth)
        cfg.target_value_float, cfg.target_value_pattern = 50.0, 0x42480000
        lua.execute("""
            for s = 1, 2 do
                for _, addr in ipairs(snapshot_lists[s]) do memory[s][addr] = 0x42480000 end
            end
            readFloat = function() tick = tick + 0.25; return 50.0 end
            local run = MVP0FoundList.run
            MVP0FoundList.run = function(opts)
                assert(opts.known_true_addr == nil)
                assert(opts.target_value_pattern == 0x42480000 and opts.target_value_float == 50.0)
                local done = opts.on_rank_complete
                opts.on_rank_complete = function()
                    rank_callbacks = rank_callbacks + 1
                    assert(rank_calls == 1 and tick == rank_finished_at)
                    done()
                end
                return run(opts)
            end
        """)
        summary = api.mode(cfg, "no_probe_A", "synthetic-single")
        assert summary.run_valid is True, summary.error
        assert summary.target_value_float == 50.0 and summary.target_value_pattern == 0x42480000
        assert lua.globals().rank_callbacks == 1 and summary.screening_compute_ms > 0
        states.append(screening_state(lua, summary))
        assert_no_execution(lua)
    assert states[0] == states[1]


@pytest.mark.parametrize("profile", ["full", "quick"])
@pytest.mark.parametrize("truth", [None, TRUTH, 0x7FFFFFFF])
def test_development_collection_and_truth_diagnostics_match_published_behavior(profile, truth):
    published = subprocess.check_output(
        ["git", "show", "6cc848069e9001f98a8fe520182abc1e042d6671:src/execute_module-v5.2.0_batch.lua"],
        cwd=BATCH.parent.parent, text=True, encoding="utf-8",
    )
    runs = []
    for source in (published, None):
        lua, api, _ = runtime(profile, truth=truth, batch_source=source)
        api.main()
        g = lua.globals()
        runs.append(freeze({
            "bundles": {i: entry.bundle for i, entry in enumerate(array(g.captured_runs))},
            "reads": g.collection_reads, "lifecycle": g.lifecycle,
            "diagnostics": {
                i: {key: summary[key] for key in (
                    "known_true_addr", "known_true_rank_position", "true_in_selected",
                    "known_true_raw_admission_path", "screening_compute_ms", "run_valid",
                    "failure_class", "error", "best_candidate_addr", "best_score", "score_gap",
                )}
                for i, summary in enumerate(array(g.captured_summaries))
            },
        }))
        assert g.captured_runs[1].options.known_true_addr == truth
        if truth == TRUTH:
            assert g.captured_summaries[1].known_true_rank_position == 1
        if profile == "full":
            assert g.captured_runs[2].options.probe_full_foundlist is True
        else:
            assert len(g.captured_runs) == 1 and g.captured_runs[1].options.probe_full_foundlist is False
    assert runs[0] == runs[1]


def with_pending_write_guard_fixture(source):
    """Exercise pending safety hunks even when this tree excludes WRITE-B1."""
    start = "local function build_default_execution_result"
    end = "function load_value_executor"
    assert source.count(start) == source.count(end) == 1
    prefix, tail = source.split(start, 1)
    region, suffix = tail.split(end, 1)
    return prefix + start + _with_write_b1_safety_hunks(region) + end + suffix


@pytest.mark.parametrize("old,new", [
    ('or profile == "single" then', 'then'),
    ('    require_known_true_match = true,', '    require_known_true_match = false,'),
    ('    write_attempted = false,', '    write_attempted = true,'),
    ('    write_ready = false,', '    write_ready = true,'),
    ('    restore_attempted = false,', '    restore_attempted = true,'),
    ('summary.validation_profile ~= "full"', 'summary.validation_profile ~= "single"'),
    ('ok = context_ok and rank_a == 1', 'ok = rank_a == 1'),
])
def test_static_guard_still_rejects_protected_control_mutations_in_memory(monkeypatch, old, new):
    source = with_pending_write_guard_fixture(BATCH.read_text(encoding="utf-8"))
    assert source.count(old) == 1
    mutated = source.replace(old, new, 1)
    read_text = Path.read_text

    def in_memory_source(path, *args, **kwargs):
        return mutated if path == BATCH else read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", in_memory_source)
    with pytest.raises(AssertionError):
        check_static_guard()


def test_static_guard_handles_both_trees_without_following_head(monkeypatch):
    source = BATCH.read_text(encoding="utf-8")
    check_output = subprocess.check_output
    read_text = Path.read_text
    compared_refs = []

    def published_source(args, *positional, **kwargs):
        if args[:2] == ["git", "show"]:
            compared_refs.append(args[2].split(":", 1)[0])
            assert compared_refs[-1] == "6cc848069e9001f98a8fe520182abc1e042d6671"
        return check_output(args, *positional, **kwargs)

    # Exact current and pending-safety views are in-memory fixtures only. The
    # guard must use the immutable checkpoint even after this commit moves HEAD.
    monkeypatch.setattr(subprocess, "check_output", published_source)
    for guarded in (source, with_pending_write_guard_fixture(source)):
        def in_memory_source(path, *args, **kwargs):
            return guarded if path == BATCH else read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", in_memory_source)
        check_static_guard()
    assert len(compared_refs) == 6
