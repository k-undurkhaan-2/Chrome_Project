"""Numerical loss, convergence and exclusion checks for conditional choice."""
import pytest

from mvp0_choice_rank import _objective, fit_choice, predict_choice
from mvp0_residual_rank import COMPONENTS, FEATURE_NAMES, leaders
from mvp0_residual_study import cross_validate


def vector(x):
    row = [0.0] * len(FEATURE_NAMES)
    row[len(COMPONENTS)] = x
    return row


def test_gradient_matches_finite_differences():
    training = [[(0.0, (0.0, 0.0)), (0.2, (0.3, -0.1))],
                [(0.0, (0.0, 0.0)), (-0.1, (-0.2, 0.4))]]
    weights = [0.1, -0.2]
    _, gradient = _objective(weights, training, 0.4)
    for j in range(2):
        plus, minus = list(weights), list(weights)
        plus[j] += 1e-5
        minus[j] -= 1e-5
        numerical = (_objective(plus, training, 0.4)[0] - _objective(minus, training, 0.4)[0]) / 2e-5
        assert gradient[j] == pytest.approx(numerical, abs=1e-9)


def test_quadratic_choice_learns_interior_and_converges():
    training = [([0, 0, 0], [vector(0), vector(0.5), vector(1)], 1)]
    for ridge in (0.1, 1, 10):
        model = fit_choice(training, 'quadratic', ridge)
        assert model['converged']
        assert leaders(predict_choice([0, 0, 0], [vector(0.2), vector(0.4), vector(0.8)], model)) == (1,)


def test_choice_nested_selection_and_training_are_outer_label_independent():
    pops = {name: dict(scores=[0, 0, 0], rows=[vector(0), vector(0.5), vector(1)],
                       contrast=[0, 0, 0], reference=1) for name in ('a', 'b', 'c')}
    first, models = cross_validate(pops, 'choice')
    pops['a']['reference'] = 0
    second, changed = cross_validate(pops, 'choice')
    assert first['nested']['a']['chosen'] == second['nested']['a']['chosen']
    assert first['nested']['a']['inner_unique_top1'] == second['nested']['a']['inner_unique_top1']
    for key in models:
        if key[0] == 'a':
            assert models[key] == changed[key]
