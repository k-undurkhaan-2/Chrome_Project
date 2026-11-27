"""Continuous, identity-free geometry for the existing offline field groups.

The silhouette formula follows Rousseeuw (1987), doi:10.1016/0377-0427(87)90125-7.
These are ranking hypotheses, not evidence that unusual records are references.
SPDX-License-Identifier: GPL-3.0-only
"""
from math import fsum


def geometry(rows, method='silhouette'):
    """Return [0,1] supplements without changing observations or the baseline.

    Three front fields and three tail fields retain their original grouping.
    Ignore the middle/status field. Missing or all-constant groups get zero.
    Cost is O(N) with a constant six-field workload; there is no model fitting.
    """
    if method not in ('silhouette', 'contrast'):
        raise ValueError('unknown geometry method')
    output = []
    for row in rows:
        if len(row) != 7:
            raise ValueError('seven observations required')
        values = (*row[:3], *row[4:])
        if any(x is None for x in values) or len(set(values)) == 1:
            output.append(0.0)
            continue
        distances = [[abs(x - y) for y in values] for x in values]
        if method == 'contrast':
            cross = fsum(distances[i][j] for i in range(3) for j in range(3, 6)) / 9
            within = fsum(distances[i][j] for group in (range(3), range(3, 6))
                          for i in group for j in group if i < j) / 6
            score = cross / (cross + within)
        else:
            parts = []
            for i in range(6):
                own, other = (range(3), range(3, 6)) if i < 3 else (range(3, 6), range(3))
                a = fsum(distances[i][j] for j in own if j != i) / 2
                b = fsum(distances[i][j] for j in other) / 3
                parts.append((b - a) / max(a, b) if max(a, b) else 0.0)
            score = (1 + fsum(parts) / 6) / 2
        output.append(score)
    return output
