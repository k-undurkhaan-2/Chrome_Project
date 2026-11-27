"""Pure offline residual ranking; no identities, file access, or target APIs.

Training references are indices in explicitly supplied training populations.
Predict accepts only observations, baseline components and fitted coefficients.
SPDX-License-Identifier: GPL-3.0-only
"""
from __future__ import annotations

from itertools import combinations
from math import fsum, isfinite, log2, sqrt


COMPONENTS = (
    'base_score', 'pointer_reward', 'strong_structure_bonus',
    'sparse_anchor_tail_penalty', 'anchored_fragmented_split_penalty',
    'one_sided_anchorless_split_penalty', 'anchorless_partial_split_penalty',
    'isolated_split_penalty', 'code_blob_penalty', 'scalar_block_penalty',
    'text_block_penalty', 'clone_penalty', 'mirrored_penalty',
)
PAIRS = tuple(combinations(range(7), 2))
FEATURE_NAMES = (
    tuple('component_' + name for name in COMPONENTS)
    + tuple(f'{kind}_{i}' for kind in ('missing', 'zero', 'aligned4', 'aligned8') for i in range(7))
    + tuple(f'relative_distance_{i}_{j}' for i, j in PAIRS)
    + tuple(f'log_distance_{i}_{j}' for i, j in PAIRS)
    + ('front_span', 'tail_span', 'contrast')
)
TEMPERATURE = 8.0
COMPETITOR_WINDOW = 12.0


def features(words, components):
    """Fixed bounded features; excludes raw words and candidate addresses.

    Relative distances retain field positions without retaining absolute word
    values. Missingness has its own indicator and is never imputed as a word.
    Absolute distance magnitudes and divisibility are structural hypotheses,
    so only the relative-distance subvector is affine invariant.
    """
    if len(words) != 7 or len(components) != len(COMPONENTS):
        raise ValueError('invalid feature dimensions')
    if any(x is not None and (type(x) is not int or not 0 <= x < 2**32) for x in words):
        raise ValueError('observations must be uint32 or missing')
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not isfinite(x) for x in components):
        raise ValueError('components must be finite numbers')
    result = [x / 64.0 for x in components]
    for predicate in (lambda x: x is None, lambda x: x == 0,
                      lambda x: x is not None and x > 0 and x % 4 == 0,
                      lambda x: x is not None and x > 0 and x % 8 == 0):
        result.extend(float(predicate(x)) for x in words)
    present = [x for x in words if x is not None]
    span = max(present) - min(present) if present else 0
    distances = [abs(words[i] - words[j]) if words[i] is not None and words[j] is not None
                 else None for i, j in PAIRS]
    result.extend(d / span if d is not None and span else 0.0 for d in distances)
    result.extend(log2(1 + d) / 32 if d is not None else 0.0 for d in distances)
    front, tail = words[:3], words[4:]
    if any(x is None for x in (*front, *tail)):
        result.extend((0.0, 0.0, 0.0))
    else:
        fs, ts = max(front) - min(front), max(tail) - min(tail)
        cross = sum(abs(a - b) for a in front for b in tail)
        result.extend((fs / span if span else 0.0, ts / span if span else 0.0,
                       cross / (cross + 3 * (fs + ts)) if cross else 0.0))
    return tuple(result)


def feature_indices(representation):
    n = len(COMPONENTS)
    if representation == 'components':
        return tuple(range(n))
    if representation == 'geometry':
        return tuple(range(n, len(FEATURE_NAMES)))
    if representation == 'combined':
        return tuple(range(len(FEATURE_NAMES)))
    raise ValueError('unknown representation')


def _solve_spd(matrix, rhs):
    """Cholesky solve for the small ridge system, using only the standard library."""
    n = len(rhs)
    lower = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            value = matrix[i][j] - fsum(lower[i][k] * lower[j][k] for k in range(j))
            lower[i][j] = sqrt(value) if i == j else value / lower[j][j]
    forward = []
    for i in range(n):
        forward.append((rhs[i] - fsum(lower[i][j] * forward[j] for j in range(i))) / lower[i][i])
    solution = [0.0] * n
    for i in reversed(range(n)):
        solution[i] = (forward[i] - fsum(lower[j][i] * solution[j] for j in range(i + 1, n))) / lower[i][i]
    return solution


def fit(training, representation='combined', ridge=1.0):
    """Fit equal-session-weighted pairwise residuals to a unit preference margin.

    Each training item is (baseline_scores, feature_rows, reference_index).
    All baseline competitors within 12 score points of the maximum are used,
    including all ties. The reference is included even if outside this window.
    The complete population must still be passed to predict. No fit-time
    statistics or coefficients are derived from a prediction population.
    """
    return _fit_statistics([_statistics(*session) for session in training], representation, ridge)


def _statistics(scores, rows, reference):
    """Per-session sufficient statistics, reusable across training-only folds."""
    _validate(scores, rows)
    if type(reference) is not int or not 0 <= reference < len(scores):
        raise ValueError('invalid training reference index')
    threshold = max(scores) - COMPETITOR_WINDOW
    rivals = [i for i, score in enumerate(scores) if i != reference and score >= threshold]
    n = len(FEATURE_NAMES)
    matrix = [[0.0] * n for _ in range(n)]
    rhs = [0.0] * n
    for rival in rivals:
        delta = [a - b for a, b in zip(rows[reference], rows[rival])]
        target = 1.0 - (scores[reference] - scores[rival]) / TEMPERATURE
        for j, value in enumerate(delta):
            rhs[j] += value * target / len(rivals)
            for k in range(j + 1):
                matrix[j][k] += value * delta[k] / len(rivals)
    for j in range(n):
        for k in range(j):
            matrix[k][j] = matrix[j][k]
    return matrix, rhs


def _fit_statistics(statistics, representation='combined', ridge=1.0):
    if not statistics or not isfinite(ridge) or ridge <= 0:
        raise ValueError('nonempty training and positive finite ridge required')
    selected = feature_indices(representation)
    n = len(selected)
    matrix = [[fsum(a[j][k] for a, _ in statistics) / len(statistics)
               for k in selected] for j in selected]
    rhs = [fsum(b[j] for _, b in statistics) / len(statistics) for j in selected]
    for j in range(n):
        matrix[j][j] += ridge
    weights = [0.0] * len(FEATURE_NAMES)
    for index, value in zip(selected, _solve_spd(matrix, rhs)):
        weights[index] = value
    return dict(representation=representation, ridge=ridge, temperature=TEMPERATURE,
                competitor_window=COMPETITOR_WINDOW, feature_names=list(FEATURE_NAMES), weights=weights)


def _validate(scores, rows):
    if not scores or len(scores) != len(rows):
        raise ValueError('nonempty aligned score and feature populations required')
    if any(not isfinite(x) for x in scores):
        raise ValueError('nonfinite baseline score')
    if any(len(row) != len(FEATURE_NAMES) or any(not isfinite(x) for x in row) for row in rows):
        raise ValueError('invalid feature row')


def predict(scores, rows, model):
    """Score every row without identities, ordering tie-breaks, or labels."""
    _validate(scores, rows)
    weights = model['weights']
    if (model['feature_names'] != list(FEATURE_NAMES) or len(weights) != len(FEATURE_NAMES)
            or any(not isfinite(x) for x in weights) or model['temperature'] != TEMPERATURE):
        raise ValueError('incompatible model')
    return [score / TEMPERATURE + fsum(w * x for w, x in zip(weights, row))
            for score, row in zip(scores, rows)]


def leaders(scores, tolerance=1e-10):
    """Return all tied maxima; no index or address selects among equal leaders."""
    if not scores or tolerance < 0 or not isfinite(tolerance) or any(not isfinite(x) for x in scores):
        raise ValueError('finite nonempty scores and nonnegative tolerance required')
    best = max(scores)
    return tuple(i for i, score in enumerate(scores) if best - score <= tolerance)
