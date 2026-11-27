"""Unsupervised frequency supplements for frozen offline ranking only.

No I/O, identities, labels, fitting, or target access. Rows contain seven
anonymous categorical observations in their existing field order.
SPDX-License-Identifier: GPL-3.0-only
"""
from collections import Counter
from itertools import combinations
from math import fsum, isfinite, log


def novelty(rows, order=1):
    """Mean smoothed self-information, normalized to [0, 1].

    order=1 uses marginal values, 2 all unordered field pairs, 7 whole rows.
    A bijection of values within any field leaves every score unchanged.
    None is an explicit missing category. No word is imputed.
    """
    if order not in (1, 2, 7):
        raise ValueError('order must be 1, 2 or 7')
    rows = [tuple(row) for row in rows]
    if any(len(row) != 7 for row in rows):
        raise ValueError('seven observations required')
    n = len(rows)
    if n < 2:
        return [0.0] * n
    columns = tuple(combinations(range(7), order))
    totals = [[] for _ in rows]
    denominator = log((n + 1) / 2)
    for fields in columns:
        keys = [tuple(row[j] for j in fields) for row in rows]
        counts = Counter(keys)
        # Cache by count: at most n distinct values, usually far fewer.
        information = {c: log((n + 1) / (c + 1)) / denominator
                       for c in set(counts.values())}
        for parts, key in zip(totals, keys):
            parts.append(information[counts[key]])
    return [fsum(parts) / len(columns) for parts in totals]


def combine(baseline, supplement, amplitude):
    """Keep the baseline contribution; add a bounded statistical supplement."""
    if len(baseline) != len(supplement):
        raise ValueError('population size mismatch')
    if not isfinite(amplitude) or amplitude < 0:
        raise ValueError('amplitude must be finite and nonnegative')
    if any(not isfinite(x) for x in baseline):
        raise ValueError('nonfinite baseline score')
    if any(not isfinite(x) or not 0 <= x <= 1 for x in supplement):
        raise ValueError('supplement outside [0, 1]')
    return [base + amplitude * extra for base, extra in zip(baseline, supplement)]
