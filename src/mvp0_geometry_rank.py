"""Continuous, identity-free geometry for the existing offline field groups.

The silhouette formula follows Rousseeuw (1987), doi:10.1016/0377-0427(87)90125-7.
These are ranking hypotheses, not evidence that unusual records are references.
SPDX-License-Identifier: GPL-3.0-only
"""
from math import fsum

from mvp0_frequency_rank import combine


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
        if method == 'contrast':
            front, tail = values[:3], values[3:]
            cross = sum(abs(a - b) for a in front for b in tail)
            spans = max(front) - min(front) + max(tail) - min(tail)
            # For three points, the three unordered distances sum to 2*span.
            # Integer-word sums are exact; no distance matrix is needed.
            score = cross / (cross + 3 * spans)
        else:
            distances = [[abs(x - y) for y in values] for x in values]
            parts = []
            for i in range(6):
                own, other = (range(3), range(3, 6)) if i < 3 else (range(3, 6), range(3))
                a = fsum(distances[i][j] for j in own if j != i) / 2
                b = fsum(distances[i][j] for j in other) / 3
                parts.append((b - a) / max(a, b) if max(a, b) else 0.0)
            score = (1 + fsum(parts) / 6) / 2
        output.append(score)
    return output


def contrast_rank(baseline_scores, rows):
    """Frozen candidate: baseline + unit contrast, with full-population ranking.

    Inputs must be aligned in the original baseline comparator order. Scores
    use no identities. Equal new scores retain that order for reporting only;
    equal scores are not unique identification. Returns scores and input indices.
    No live integration or action/recommendation envelope is created.
    """
    scores = combine(baseline_scores, geometry(rows, 'contrast'), 1)
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    return scores, order
