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
