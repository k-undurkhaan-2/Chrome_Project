"""Mathematical and leakage-boundary regressions for the offline ranker."""
import random

import pytest

from mvp0_residual_rank import (
    COMPONENTS, FEATURE_NAMES, features, fit, leaders, predict, _solve_spd,
)


def row(value):
    return features((value, 2 * value, 3 * value, 1, 7 * value, 8 * value, 9 * value),
                    (0,) * len(COMPONENTS))


def test_known_linear_system():
    assert _solve_spd([[4, 1], [1, 3]], [9, 7]) == pytest.approx([20 / 11, 19 / 11])


def test_missing_constant_and_invalid_observations():
    for words in ((None,) * 7, (0,) * 7, (10,) * 7):
        assert len(features(words, (0,) * len(COMPONENTS))) == len(FEATURE_NAMES)
    with pytest.raises(ValueError):
        features((-1,) * 7, (0,) * len(COMPONENTS))


def test_training_and_prediction_permutation_invariance():
    scores, rows = [6.0, 5.0, 4.0], [row(4), row(40), row(400)]
    model = fit([(scores, rows, 1)])
    original = predict(scores, rows, model)
    order = [2, 0, 1]
    perm_scores, perm_rows = [scores[i] for i in order], [rows[i] for i in order]
    perm_model = fit([(perm_scores, perm_rows, order.index(1))])
    assert perm_model['weights'] == pytest.approx(model['weights'], abs=1e-12)
    assert predict(perm_scores, perm_rows, model) == pytest.approx([original[i] for i in order])


def test_duplicate_features_cannot_create_unique_identification():
    model = fit([([0, 0], [row(4), row(4)], 0)])
    assert leaders(predict([2, 2], [row(8), row(8)], model)) == (0, 1)


def test_ridge_converges_to_baseline_and_fit_has_no_evaluation_label():
    training = [([0, 0], [row(4), row(400)], 1)]
    model = fit(training, ridge=1e12)
    assert predict([16, 8], [row(40), row(80)], model) == pytest.approx([2, 1], abs=1e-10)
    # The model and predictions have no reference argument or external state.
    assert fit(training) == fit(training)


def test_relative_geometry_is_translation_and_scale_invariant():
    rng = random.Random(813)
    indices = [i for i, name in enumerate(FEATURE_NAMES)
               if name.startswith('relative_distance') or name in ('front_span', 'tail_span', 'contrast')]
    for _ in range(30):
        words = tuple(rng.randrange(1, 100000) for _ in range(7))
        a = features(words, (0,) * len(COMPONENTS))
        b = features(tuple(5 * x + 120 for x in words), (0,) * len(COMPONENTS))
        assert [a[i] for i in indices] == pytest.approx([b[i] for i in indices])


def test_near_ties_and_incompatible_model_are_not_silent_successes():
    assert leaders([1.0, 1.0 + 1e-12, 0.0]) == (0, 1)
    model = fit([([0, 0], [row(4), row(400)], 1)])
    model['feature_names'] = list(reversed(model['feature_names']))
    with pytest.raises(ValueError, match='incompatible'):
        predict([1, 2], [row(4), row(40)], model)
