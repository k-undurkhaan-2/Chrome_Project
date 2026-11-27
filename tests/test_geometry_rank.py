from mvp0_geometry_rank import geometry
import pytest


@pytest.mark.parametrize('method', ['silhouette', 'contrast'])
def test_geometry_uses_relations_not_absolute_values(method):
    rows = [(10, 11, 12, 999, 100, 101, 102), (0, 50, 100, 0, 1, 51, 101)]
    original = geometry(rows, method)
    assert original[0] > original[1]
    relocated = [tuple(3 * x + 12345 for x in row) for row in rows]
    assert geometry(relocated, method) == pytest.approx(original, abs=1e-15)
    exchanged = [(r[6], r[5], r[4], r[3], r[2], r[1], r[0]) for r in rows]
    assert geometry(exchanged, method) == pytest.approx(original, abs=1e-15)
    assert geometry(rows[::-1], method) == original[::-1]
    assert geometry([rows[0], rows[0]], method)[0] == geometry([rows[0], rows[0]], method)[1]


@pytest.mark.parametrize('method', ['silhouette', 'contrast'])
def test_missing_and_constant_observations_are_not_imputed(method):
    assert geometry([(1,) * 7, (None, 0, 1, 7, 2, 3, 4)], method) == [0, 0]
    assert geometry([], method) == []
    with pytest.raises(ValueError):
        geometry([(1, 2)], method)


def test_fast_contrast_matches_independent_pair_distance_definition():
    from itertools import combinations
    from random import Random
    from statistics import mean
    rng = Random(517)
    rows = [tuple(rng.randrange(2**32) for _ in range(7)) for _ in range(1000)]
    expected = []
    for row in rows:
        front, tail = row[:3], row[4:]
        cross = mean(abs(a - b) for a in front for b in tail)
        within = mean([abs(a - b) for a, b in combinations(front, 2)] +
                      [abs(a - b) for a, b in combinations(tail, 2)])
        expected.append(cross / (cross + within))
    assert geometry(rows, 'contrast') == pytest.approx(expected, abs=1e-15)


def test_frozen_candidate_ranking_reports_unresolved_ties():
    from mvp0_geometry_rank import contrast_rank
    coherent = (10, 11, 12, 0, 100, 101, 102)
    mixed = (0, 50, 100, 0, 1, 51, 101)
    scores, order = contrast_rank([40, 40, 40], [mixed, coherent, coherent])
    assert order == [1, 2, 0]
    assert scores[1] == scores[2] > scores[0]
    assert contrast_rank([], []) == ([], [])
