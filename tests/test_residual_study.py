"""Verify that nested selection never consumes its outer reference label."""
from copy import deepcopy

from mvp0_residual_rank import FEATURE_NAMES, fit, leaders, predict
from mvp0_residual_study import cross_validate, metrics


def vector(x):
    return (x,) + (0.0,) * (len(FEATURE_NAMES) - 1)


def test_learning_transfers_a_known_preference_to_unseen_features():
    model = fit([([0, 0, 0], [vector(1), vector(3), vector(2)], 1)], ridge=0.1)
    assert leaders(predict([0, 0, 0], [vector(7), vector(6), vector(8)], model)) == (2,)


def test_outer_label_changes_metrics_but_not_model_or_nested_selection():
    pops = {name: dict(scores=[0.0, 0.0, 0.0],
                       rows=[vector(i), vector(i + 1), vector(i + 2)],
                       contrast=[0.0, 0.0, 0.0], reference=2)
            for i, name in enumerate(('a', 'b', 'c', 'd'))}
    original, models = cross_validate(pops)
    changed = deepcopy(pops)
    changed['a']['reference'] = 0
    other, other_models = cross_validate(changed)
    assert original['nested']['a']['chosen'] == other['nested']['a']['chosen']
    assert original['nested']['a']['inner_unique_top1'] == other['nested']['a']['inner_unique_top1']
    for key, model in models.items():
        if key[0] == 'a':
            assert model == other_models[key]
    for test, alternatives in original['outer'].items():
        for result in alternatives.values():
            assert test not in result['training_sessions']
    assert original['outer']['a']['combined_0.1']['unique_top1']
    assert not other['outer']['a']['combined_0.1']['unique_top1']


def test_metrics_never_credit_tie_breaking_as_identification():
    outcome = metrics([10, 10, 9], 0)
    assert outcome['reference_is_leader']
    assert not outcome['unique_top1']
    assert outcome['rank_interval'] == [1, 2]
