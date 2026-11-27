"""Metamorphic checks on artificial categorical records, without a reference."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from mvp0_frequency_rank import combine, novelty


@pytest.mark.parametrize('order', [1, 2, 7])
def test_frequency_invariances(order):
    rows = [(i % 3, i % 4, None, i % 2, 7, i % 5, i % 3) for i in range(30)]
    scores = novelty(rows, order)
    permutation = list(reversed(range(len(rows))))
    assert novelty([rows[i] for i in permutation], order) == [scores[i] for i in permutation]
    renamed = [tuple((j, value) for j, value in enumerate(row)) for row in rows]
    assert novelty(renamed, order) == scores
    assert all(0 <= score <= 1 for score in scores)


def test_empirical_information_and_genuine_collisions():
    common = (0,) * 7
    rare = (1,) * 7
    scores = novelty([common, common, rare])
    assert scores[0] == scores[1] < scores[2]
    assert scores[2] == 1
    assert novelty([common] * 5) == [0.0] * 5
    assert novelty([]) == []
    assert novelty([rare]) == [0.0]


def test_combine_retains_baseline_and_checks_domain():
    assert combine([20, 19], [.2, .9], 0) == [20, 19]
    assert combine([20, 19], [.2, .9], 1) == [20.2, 19.9]
    with pytest.raises(ValueError):
        combine([1], [], 1)
    with pytest.raises(ValueError):
        combine([1], [float('nan')], 1)
