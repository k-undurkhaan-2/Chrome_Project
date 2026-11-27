"""Check quadratic interior preference, symmetry, and model isolation."""
import pytest

from mvp0_moment_rank import fit_moments, predict_moments
from mvp0_residual_rank import COMPONENTS, FEATURE_NAMES, leaders
from mvp0_residual_study import cross_validate


def vector(value):
    row = [0.0] * len(FEATURE_NAMES)
    row[len(COMPONENTS)] = value
    return row


def test_quadratic_discerns_interior_concentration_linear_cannot():
    training = [([0, 0, 0], [vector(0), vector(0.5), vector(1)], 1)] * 3
    scores, rows = [0, 0, 0], [vector(0.25), vector(0.5), vector(0.75)]
    shared = fit_moments(training, 'shared')
    shrunk = fit_moments(training, 'shrunk')
    assert leaders(predict_moments(scores, rows, shared)) == (0, 1, 2)
    assert leaders(predict_moments(scores, rows, shrunk)) == (1,)
    assert set(shrunk) == {'variance', 'amplitude', 'variance_floor', 'temperature',
                           'competitor_window', 'feature_names', 'linear', 'quadratic', 'active_features'}


def test_population_and_session_permutation_invariance():
    rows = [vector(0), vector(0.3), vector(1)]
    training = [([0, 0, 0], rows, 1), ([0, 0, 0], list(reversed(rows)), 1)]
    model = fit_moments(training)
    assert model == fit_moments(list(reversed(training)))
    scores = predict_moments([0, 0, 0], rows, model)
    assert predict_moments([0, 0, 0], list(reversed(rows)), model) == pytest.approx(list(reversed(scores)))


def test_moment_nested_selection_excludes_outer_labels():
    pops = {name: dict(scores=[0, 0, 0], rows=[vector(0), vector(0.5), vector(1)],
                       contrast=[0, 0, 0], reference=1) for name in ('a', 'b', 'c')}
    first, models = cross_validate(pops, 'moments')
    pops['a']['reference'] = 0
    second, changed = cross_validate(pops, 'moments')
    assert first['nested']['a']['chosen'] == second['nested']['a']['chosen']
    assert first['nested']['a']['inner_unique_top1'] == second['nested']['a']['inner_unique_top1']
    for key in models:
        if key[0] == 'a':
            assert models[key] == changed[key]
