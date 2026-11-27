"""Moment-based offline ranking of existing bounded, identity-free features.

These are ranking discriminants, not calibrated reference probabilities.
Only aggregate coefficients are retained; no reference templates are stored.
SPDX-License-Identifier: GPL-3.0-only
"""
from math import fsum, isfinite

from mvp0_residual_rank import (
    COMPONENTS, COMPETITOR_WINDOW, FEATURE_NAMES, TEMPERATURE, _validate,
)


def _moment_statistics(scores, rows, reference):
    _validate(scores, rows)
    if type(reference) is not int or not 0 <= reference < len(scores):
        raise ValueError('invalid training reference index')
    threshold = max(scores) - COMPETITOR_WINDOW
    rivals = [row for i, row in enumerate(rows) if i != reference and scores[i] >= threshold]
    if not rivals:
        raise ValueError('training session has no competitors')
    return (rows[reference],
            tuple(fsum(row[j] for row in rivals) / len(rivals) for j in range(len(FEATURE_NAMES))),
            tuple(fsum(row[j] ** 2 for row in rivals) / len(rivals) for j in range(len(FEATURE_NAMES))))


def _fit_moments(statistics, variance='shrunk', amplitude=1.0):
    if not statistics or variance not in ('shared', 'shrunk') or not isfinite(amplitude) or amplitude <= 0:
        raise ValueError('nonempty training, known variance model and positive amplitude required')
    linear, quadratic = [0.0] * len(FEATURE_NAMES), [0.0] * len(FEATURE_NAMES)
    active = []
    for j in range(len(COMPONENTS), len(FEATURE_NAMES)):
        mp = fsum(p[j] for p, _, _ in statistics) / len(statistics)
        mn = fsum(m[j] for _, m, _ in statistics) / len(statistics)
        vp = max(0.0, fsum(p[j] ** 2 for p, _, _ in statistics) / len(statistics) - mp ** 2)
        vn = max(0.0, fsum(s[j] for _, _, s in statistics) / len(statistics) - mn ** 2)
        if vp + vn + (mp - mn) ** 2 <= 1e-12:
            continue
        shared = (vp + vn) / 2
        if variance == 'shared':
            vp = vn = max(0.01, shared)
        else:
            vp, vn = max(0.01, (vp + shared) / 2), max(0.01, (vn + shared) / 2)
        active.append(j)
        quadratic[j] = 0.5 * (1 / vn - 1 / vp)
        linear[j] = mp / vp - mn / vn
    if active:
        linear = [amplitude * x / len(active) for x in linear]
        quadratic = [amplitude * x / len(active) for x in quadratic]
    return dict(variance=variance, amplitude=amplitude, variance_floor=0.01,
                temperature=TEMPERATURE, competitor_window=COMPETITOR_WINDOW,
                feature_names=list(FEATURE_NAMES), linear=linear, quadratic=quadratic,
                active_features=len(active))


def fit_moments(training, variance='shrunk', amplitude=1.0):
    return _fit_moments([_moment_statistics(*session) for session in training], variance, amplitude)


def predict_moments(scores, rows, model):
    _validate(scores, rows)
    linear, quadratic = model['linear'], model['quadratic']
    if (model['feature_names'] != list(FEATURE_NAMES) or model['temperature'] != TEMPERATURE
            or len(linear) != len(FEATURE_NAMES) or len(quadratic) != len(FEATURE_NAMES)
            or any(not isfinite(x) for x in (*linear, *quadratic))):
        raise ValueError('incompatible moment model')
    return [score / TEMPERATURE + fsum(a * x + b * x * x for a, b, x in zip(linear, quadratic, row))
            for score, row in zip(scores, rows)]
