"""Finite Lua 5.3 parity against immutable offline Python objects; never fit.

Uses the existing pytest/Lupa facilities and table-only population fixtures.
No native application, process API, adapter, writer, or new data collection.
"""
import hashlib
import json
import math
from pathlib import Path
import random
import struct
import subprocess
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest
from lupa.lua53 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/mvp0_frozen_choice.lua"
FROZEN = "36eabba2a2cdbd4b26fc5bf09532f9eb51eb9744"
HANDOFF = "d377c637edb915b7dcf675c2794517957c5fbea1"
FREEZE_PATH = "reports/2026-11-28/offline-ranking/candidate-freeze.json"
MODEL_PATH = "reports/2026-11-28/offline-ranking/candidate-model.json"
FREEZE_SHA256 = "546ddb8fe8db310039939fbd593f9fb72727dd15ef119f7eb23311ef91f2f596"
ABS_TOL = 1e-12  # Arithmetic comparison only; never widen the frozen 1e-10 tie rule.
FIELDS = ("f08", "f18", "f20", "f58", "f68", "f70", "f78")


def blob(revision, path):
    return subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT)


@pytest.fixture(scope="module")
def reference():
    manifest = blob(HANDOFF, FREEZE_PATH)
    assert hashlib.sha256(manifest).hexdigest() == FREEZE_SHA256
    freeze = json.loads(manifest)
    assert freeze["source_and_model_commit"] == FROZEN
    assert freeze["candidate"] == "conditional_choice_linear_ridge_0.1"

    def verified(path):
        raw = blob(FROZEN, path)
        assert hashlib.sha256(raw).hexdigest() == freeze["files"][path]
        return raw

    model = json.loads(verified(MODEL_PATH))
    assert model["representation"] == "linear" and model["ridge"] == 0.1
    assert model["temperature"] == 8.0 and model["competitor_window"] == 12.0
    assert len(model["linear"]) == len(model["quadratic"]) == 86
    assert all(x == 0 for x in model["quadratic"])
    for name in ("mvp0_candidate_report.lua", "mvp0_foundlist_collector.lua", "mvp0_offline_scoring.lua"):
        assert (ROOT / "src" / name).read_bytes().replace(b"\r\n", b"\n") == verified("src/" + name)

    # Execute the frozen definitions, never any fitting or evaluation driver.
    # Do not import mutable research checkout files or copy training into src/.
    with patch.dict(sys.modules):
        modules = {}
        for name in ("mvp0_residual_rank", "mvp0_moment_rank", "mvp0_choice_rank"):
            path = "src/" + name + ".py"
            module = ModuleType(name)
            sys.modules[name] = modules[name] = module
            exec(compile(verified(path), FROZEN + ":" + path, "exec"), module.__dict__)
        residual = modules["mvp0_residual_rank"]
        assert model["feature_names"] == list(residual.FEATURE_NAMES)
        yield SimpleNamespace(model=model, features=residual.features, leaders=residual.leaders,
                              predict=modules["mvp0_choice_rank"].predict_choice,
                              components=residual.COMPONENTS)


@pytest.fixture(scope="module")
def pure():
    lua = LuaRuntime(unpack_returned_tuples=True, max_memory=256 * 1024 * 1024)
    assert lua.eval("_VERSION") == "Lua 5.3"
    assert lua.eval("string.packsize('n')") == 8
    api = lua.eval("""function(source)
      local env = {assert=assert, type=type, pairs=pairs, getmetatable=getmetatable, math=math}
      setmetatable(env, {
        __index=function(_, key) error('UNAVAILABLE_GLOBAL:'..key) end,
        __newindex=function(_, key) error('GLOBAL_MUTATION:'..key) end,
      })
      return assert(load(source, '@mvp0_frozen_choice.lua', 't', env))()
    end""")(SOURCE.read_text(encoding="utf-8"))
    return lua, api


def array(value):
    return [value[i] for i in range(1, len(value) + 1)]


def lua_rows(lua, rows):
    return lua.table_from([lua.table_from(row) for row in rows])


def error_max(actual, expected):
    assert len(actual) == len(expected)
    error = max((abs(a - b) for a, b in zip(actual, expected)), default=0.0)
    assert error <= ABS_TOL, error
    return error


def compare_predictions(lua, api, reference, scores, rows):
    expected = reference.predict(scores, rows, reference.model)
    actual_table = api.predict(lua.table_from(scores), lua_rows(lua, rows))
    actual = array(actual_table)
    error = error_max(actual, expected)
    assert tuple(i - 1 for i in array(api.leaders(actual_table))) == reference.leaders(expected)
    return actual, error


def test_every_frozen_coefficient_and_offset(pure, reference):
    lua, api = pure
    rows = [tuple(float(i == j) for j in range(86)) for i in range(86)]
    actual, error = compare_predictions(lua, api, reference, [0.0] * 86, rows)
    assert [struct.pack('!d', x) for x in actual] == [
        struct.pack('!d', x) for x in reference.model["linear"]]
    compare_predictions(lua, api, reference, [64.0] * 86,
                        [tuple(2 * x for x in row) for row in rows])
    print(f"coefficients=86 binary64_exact; unit_vector_score_max_abs_error={error:.17g}")


def test_finite_feature_and_score_parity(pure, reference):
    lua, api = pure
    maximum = 2**32 - 1
    base = (0x10011200, 0x10013800, 0x10042100, 0x10060000,
            0x10025600, 0x10028400, 0x10086300)
    words = [(0,) * 7, (8,) * 7, (0, 1, 3, 4, 7, 8, maximum),
             (maximum, 2**31, 16, 8, 4, 1, 0), (8, 8, 8, maximum, 8, 8, 8), base]
    words += [tuple(None if mask & (1 << j) else base[j] for j in range(7))
              for mask in range(128)]
    rng = random.Random(20261128)
    words += [tuple(rng.choice((None, 0, 1, 3, 4, 7, 8, maximum, rng.randrange(2**32)))
                    for _ in range(7)) for _ in range(128)]
    components = [tuple(rng.randint(-4096, 4096) / 64 for _ in range(13)) for _ in words]
    expected_rows = [reference.features(w, c) for w, c in zip(words, components)]
    actual_rows = [array(api.features(lua.table_from(w), lua.table_from(c)))
                   for w, c in zip(words, components)]
    feature_error = max(error_max(a, e) for a, e in zip(actual_rows, expected_rows))
    scores = [rng.randint(-1024, 1024) / 8 for _ in words]
    expected = reference.predict(scores, expected_rows, reference.model)
    actual, arithmetic_error = compare_predictions(lua, api, reference, scores, expected_rows)
    actual_features, _ = compare_predictions(lua, api, reference, scores, actual_rows)
    combined_error = error_max(actual_features, expected)
    # Population reversal changes only row positions, never the numeric results.
    reversed_scores, _ = compare_predictions(lua, api, reference, scores[::-1], actual_rows[::-1])
    assert reversed_scores == actual_features[::-1]
    print(f"finite_rows={len(words)}; feature_max_abs_error={feature_error:.17g}; "
          f"score_arithmetic_max_abs_error={arithmetic_error:.17g}; "
          f"combined_score_max_abs_error={combined_error:.17g}")


@pytest.mark.parametrize("scores", [
    [0.0], [7.0, 7.0, 7.0], [0.0, 0.5e-10, 2e-10],
    [0.0, 1e-10], [0.0, math.nextafter(1e-10, 0.0)],
    [0.0, math.nextafter(1e-10, math.inf)], [-5.0, -5.0, -6.0],
    [-2**63, 2**63 - 1, 2**63 - 2],
])
def test_all_leaders_including_tolerance_boundary(pure, reference, scores):
    lua, api = pure
    assert tuple(i - 1 for i in array(api.leaders(lua.table_from(scores)))) == reference.leaders(scores)


def test_predict_keeps_ties_near_ties_and_below_training_window(pure, reference):
    lua, api = pure
    row = reference.features((None,) * 7, (0.0,) * 13)
    scores = [64.0, 64.0, -128.0]
    actual, _ = compare_predictions(lua, api, reference, scores, [row] * 3)
    assert len(actual) == 3 and array(api.leaders(lua.table_from(actual))) == [1, 2]
    near = [0.0, 8 * 0.5e-10, 8 * 2e-10]
    actual, _ = compare_predictions(lua, api, reference, near, [row] * 3)
    assert array(api.leaders(lua.table_from(actual))) == [3]


@pytest.mark.parametrize("kind", ["weak", "unique", "ambiguous"])
def test_existing_full_population_fixture(pure, reference, kind):
    # Load the existing fixture directly: the historical Python wrapper imports
    # REQUIRED_FILES, which the native branch's builder no longer exports.
    lua = LuaRuntime(unpack_returned_tuples=True, max_memory=256 * 1024 * 1024)
    names = ("ce_mvp_core.lua", "ce_mvp_adapter.lua", "ce_mvp_config.example.lua",
             "mvp0_foundlist_collector.lua", "mvp0_candidate_report.lua")
    sources = lua.table_from({name: (ROOT / "src" / name).read_text(encoding="utf-8")
                              for name in names})
    factory = lua.execute((ROOT / "tests/fixtures/ce_mvp_mock.lua").read_text(encoding="utf-8"))
    w = factory.new(sources)
    good = (17,) if kind == "unique" else (1, 37) if kind == "ambiguous" else ()
    for index in range(1, 38):
        w.object(0x100128 + index * 0x200, None if index in good else "weak")
    offline = lua.execute((ROOT / "src/mvp0_offline_scoring.lua").read_text(encoding="utf-8"))
    before = offline.run(w.objects, lua.table_from({"population_mode": "full",
                         "target_value_pattern": 0x42C80000, "target_value_float": 100.0}), w.load)
    assert before.completed and before.population_complete and before.counts.eligible == 37
    ranked = array(before.result.ranked)
    words = [tuple(r.candidate[k] for k in FIELDS) for r in ranked]
    components = [tuple(r[k] for k in reference.components) for r in ranked]
    rows = [reference.features(w, c) for w, c in zip(words, components)]
    scores = [r.final_score for r in ranked]
    pure_lua, api = pure
    actual_rows = [array(api.features(pure_lua.table_from(w), pure_lua.table_from(c)))
                   for w, c in zip(words, components)]
    for actual, expected in zip(actual_rows, rows):
        error_max(actual, expected)
    actual, _ = compare_predictions(pure_lua, api, reference, scores, actual_rows)
    error = error_max(actual, reference.predict(scores, rows, reference.model))
    leaders = array(api.leaders(pure_lua.table_from(actual)))
    if kind != "unique":
        assert len(leaders) > 1  # Baseline identity ordering is not identification.
    assert w.open_calls == w.reads == w.forbidden == 0
    assert len(w.native_calls) == len(w.writes) == len(w.scans) == len(w.timers) == 0
    assert w.adapter is None and w.loop is None
    print(f"existing_fixture={kind}; eligible_scored=37; leaders={len(leaders)}; "
          f"combined_score_max_abs_error={error:.17g}; native_calls=0")


@pytest.mark.parametrize("word", [-1, 2**32, 1.5, 8.0, True, "8", math.nan, math.inf])
def test_invalid_observations_fail_without_a_prediction(pure, word):
    lua, api = pure
    with pytest.raises(Exception, match="observations must be uint32 or missing"):
        api.features(lua.table_from([word]), lua.table_from([0.0] * 13))


@pytest.mark.parametrize("scores,rows", [
    ([], []), ([0.0], []), ([math.nan], [[0.0] * 86]),
    ([math.inf], [[0.0] * 86]), ([0.0], [[0.0] * 85]),
    ([0.0], [[0.0] * 85 + [math.inf]]), ([0.0], [[0.0] * 85 + [math.nan]]),
])
def test_invalid_prediction_inputs_fail_without_partial_success(pure, scores, rows):
    lua, api = pure
    with pytest.raises(Exception):
        api.predict(lua.table_from(scores), lua_rows(lua, rows))
