from mvp0_ordinal_rank import clone_penalty, ordinal_pattern, refine_clones
import pytest


def test_ordinal_pattern_preserves_order_without_values():
    row = (1, 1, 2, 3, 5, 8, 13)
    assert ordinal_pattern(row) == ordinal_pattern(tuple(x**3 + 19 for x in row))
    assert ordinal_pattern((None, *row[1:])) != ordinal_pattern(row)


def test_refinement_preserves_repeated_relations():
    family = 'layout:front_tail_split|scalar:0|text:0'
    rows = [(1, 2, 3, 4, 5, 6, 7), (2, 4, 6, 8, 10, 12, 14), (7, 6, 5, 4, 3, 2, 1)]
    assert refine_clones(rows, [family] * 3, [5] * 3, [3] * 3) == [0, 0, 3]
    assert refine_clones(rows[::-1], [family] * 3, [5] * 3, [3] * 3) == [3, 0, 0]
    with pytest.raises(ValueError, match='baseline clone formula mismatch'):
        refine_clones(rows, [family] * 3, [5] * 3, [0] * 3)


def test_original_surcharges_remain_distinct():
    props = dict(layout='scattered', scalar='medium', text='0')
    assert clone_penalty(2, props, 2) == 7
    assert clone_penalty(1, props, 2) == 0
