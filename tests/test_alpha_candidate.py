"""Small source-launcher regressions; reuse the maintained AC6 table fixtures."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

import run_alpha_candidate as alpha
from test_h3_a7_ce_mvp import runtime  # noqa: F401
from test_offline_collector_interface import connected
from test_offline_full_population import no_native, records
from test_stable_prescore_optimization import plain


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "src/examples/g1_alpha_population.example.json"
TIMINGS = {"filter_ms", "prescore_ms", "prescore_read_ms", "prescore_score_ms",
           "prescore_sort_ms", "prescore_select_ms", "prescore_detail_ms"}


def example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def decoded(document):
    return alpha.decode_input(json.dumps(document).encode())


def stable(envelope):
    result = deepcopy(envelope)
    for field in ("collection", "filter"):
        for key in TIMINGS:
            result[field].pop(key, None)
    return result


def test_full_population_launcher_matches_ac6_above_128(runtime):
    lua, w = runtime
    records(w, 137, good=(129,))
    reference = connected(lua, w, population_mode="full")
    document = example()
    document["records"] = [
        {key: value for key, value in plain(row).items() if key in {"addr", "mapped", "protect", "memory"}}
        for _, row in w.objects.items()]
    document["supplied_identities"] = [row["addr"] for row in document["records"]]
    document["supplied_count"] = len(document["records"])
    version = "lua53" if lua.eval("_VERSION") == "Lua 5.3" else "lua54"
    outcome = alpha.evaluate(decoded(document), lua_version=version)
    actual = outcome["evaluation"]
    # JSON object keys normalize the same numeric Lua keys in both paths.
    expected = json.loads(json.dumps(plain(reference)))
    assert stable(actual) == stable(expected)
    assert actual["counts"]["fully_scored"] == actual["counts"]["ranked"] == 137
    assert set(actual["identities"]["eligible"].values()) == {
        row["candidate"]["value_addr"] for row in actual["result"]["ranked"].values()}
    assert outcome["proposed_rank1"] == w.objects[129].addr
    assert outcome["action_permitted"] is False and outcome["automatic_recovery"] is False
    no_native(w)


@pytest.mark.parametrize("version", ["lua53", "lua54"])
@pytest.mark.parametrize("kind", ["normal", "empty", "weak", "ambiguous", "bounded", "duplicates"])
def test_example_controls_never_permit_action(version, kind):
    document = example()
    if kind == "empty":
        document["records"] = []
    elif kind == "weak":
        document["records"] = document["records"][1:]
    elif kind == "ambiguous":
        strong = document["records"][0]
        other = document["records"][1]
        offset = other["addr"] - strong["addr"]
        other["memory"] = {str(int(key) + offset): value for key, value in strong["memory"].items()}
    elif kind == "bounded":
        document["options"].update(population_mode="bounded", scan_budget=3, max_candidates=1)
    elif kind == "duplicates":
        document["records"].append(deepcopy(document["records"][0]))
    document["supplied_count"] = len(document["records"])
    document["supplied_identities"] = [row["addr"] for row in document["records"]]
    outcome = alpha.evaluate(decoded(document), lua_version=version)
    result = outcome["evaluation"]
    assert outcome["action_permitted"] is False
    assert outcome["lifecycle_status"].startswith("UNSUPPORTED")
    if kind in ("normal", "duplicates"):
        assert result["result"]["best"]["final_score"] == 46
        assert outcome["proposed_rank1"] == 1048872
        assert result["result"]["recommendation"]["recommendation"] == "ACCEPT"
        assert result["counts"]["ranked"] == 3 and result["population_complete"] is True
    elif kind == "bounded":
        assert result["population_mode"] == "bounded" and result["population_complete"] is False
        assert result["counts"]["ranked"] == 1 and outcome["proposed_rank1"] is None
    elif kind == "empty":
        assert result["status"] == "EMPTY" and result["result"]["recommendation"]["recommendation"] == "REJECT"
        assert outcome["proposed_rank1"] is None
    else:
        assert result["result"]["recommendation"]["recommendation"] in ("REVIEW", "REJECT")


@pytest.mark.parametrize("change,reason", [
    ({"complete": False}, "NOT_DECLARED_COMPLETE"),
    ({"supplied_count": 2}, "COUNT_MISMATCH"),
    ({"supplied_identities": [1048872, 1049896, 1049384]}, "IDENTITIES_MISMATCH"),
    ({"known_true_addr": 1048872}, "INPUT_SCHEMA"),
    ({"options": {"population_mode": "full", "scan_budget": None}}, "SCALARS"),
    ({"options": {"population_mode": "full", "target_value_pattern": 1120403456, "scan_budget": 3}}, "OFFLINE_INVALID_OPTIONS"),
    ({"options": {"population_mode": "full", "target_value_pattern": 1120403456, "write_enabled": True}}, "OFFLINE_INVALID_OPTIONS"),
])
def test_invalid_or_incomplete_input_has_no_success(change, reason):
    document = example()
    document.update(change)
    with pytest.raises(Exception, match=reason):
        alpha.evaluate(decoded(document))


def test_json_keys_and_truth_are_not_silently_discarded():
    with pytest.raises(alpha.AlphaInputError, match="DUPLICATE_JSON_KEY"):
        alpha.decode_input(b'{"schema":1,"schema":1}')
    with pytest.raises(alpha.AlphaInputError, match="NONFINITE_JSON"):
        alpha.decode_input(b'{"number":NaN}')
    document = example()
    document["records"][0]["truth"] = True
    with pytest.raises(alpha.AlphaInputError, match="RECORD_SCHEMA"):
        decoded(document)


@pytest.mark.parametrize("fault", [KeyboardInterrupt, RuntimeError, TimeoutError])
def test_cancellation_and_errors_during_lua_evaluation_propagate_once(fault):
    calls = 0

    def guard():
        nonlocal calls
        calls += 1
        if calls == 2:  # First check passes; the next is inside the Lua hook.
            raise fault("OWNED_TEST_STOP")

    with pytest.raises(fault, match="OWNED_TEST_STOP"):
        alpha.evaluate(decoded(example()), guard=guard)
    assert calls == 2


@pytest.mark.parametrize("fault,code", [(KeyboardInterrupt, 130), (RuntimeError, 1), (TimeoutError, 1)])
def test_cli_stops_without_success_output_or_retry(monkeypatch, capsys, fault, code):
    calls = []

    def failed(*args, **kwargs):
        calls.append(1)
        raise fault("ORIGINAL_FAILURE")

    monkeypatch.setattr(alpha, "evaluate", failed)
    assert alpha.main(["--input", str(EXAMPLE), "--json"]) == code
    captured = capsys.readouterr()
    assert captured.out == "" and "STOPPED" in captured.err
    assert calls == [1]
    if code == 1:
        assert "ORIGINAL_FAILURE" in captured.err


def test_changed_input_is_stopped_before_publishing(monkeypatch, capsys):
    original = EXAMPLE.read_bytes()
    calls = []

    def changed(path):
        calls.append(path)
        return original if len(calls) == 1 else original + b"\n"

    monkeypatch.setattr(alpha, "read_input", changed)
    assert alpha.main(["--input", str(EXAMPLE), "--json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "ALPHA_INPUT_CHANGED" in captured.err


@pytest.mark.parametrize("limit,reason", [("INPUT_BYTES", "INPUT_RESOURCE_LIMIT"),
                                         ("OUTPUT_BYTES", "OUTPUT_RESOURCE_LIMIT")])
def test_size_limits_fail_without_truncation(monkeypatch, capsys, limit, reason):
    monkeypatch.setattr(alpha, limit, 1)
    assert alpha.main(["--input", str(EXAMPLE), "--json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and reason in captured.err


def test_documented_source_entry_point_runs_outside_repository(tmp_path):
    result = subprocess.run([sys.executable, "-B", str(ROOT / "src/run_alpha_candidate.py"),
                             "--input", str(EXAMPLE), "--json"], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    outcome = json.loads(result.stdout)
    assert outcome["proposed_rank1"] == 1048872
    assert outcome["evaluation"]["completed"] is True
    assert outcome["action_permitted"] is False
