"""Regularized conditional choice loss for finite offline training populations.

No reference identities, templates, IO or live APIs enter the fitted model.
Prediction reuses the same full-population polynomial calculation as moments.
SPDX-License-Identifier: GPL-3.0-only
"""
from math import exp, fsum, isfinite, log

from mvp0_residual_rank import COMPONENTS, COMPETITOR_WINDOW, FEATURE_NAMES, TEMPERATURE, _validate
from mvp0_moment_rank import predict_moments as predict_choice

GEOMETRY_SIZE = len(FEATURE_NAMES) - len(COMPONENTS)


def _choice_statistics(scores, rows, reference):
    _validate(scores, rows)
    if type(reference) is not int or not 0 <= reference < len(scores):
        raise ValueError('invalid training reference index')
    threshold = max(scores) - COMPETITOR_WINDOW
    indices = [i for i, score in enumerate(scores) if i == reference or score >= threshold]
    def expanded(row):
        x = row[len(COMPONENTS):]
        return tuple(x) + tuple(4 * v * (1 - v) for v in x)
    target = expanded(rows[reference])
    return [( (scores[i] - scores[reference]) / TEMPERATURE,
              tuple(a - b for a, b in zip(expanded(rows[i]), target)) ) for i in indices]


def _objective(weights, training, ridge, gradient=True):
    loss = ridge * fsum(w * w for w in weights) / 2
    grad = [ridge * w for w in weights] if gradient else None
    for session in training:
        logits = [offset + fsum(w * x for w, x in zip(weights, row)) for offset, row in session]
        maximum = max(logits)
        values = [exp(x - maximum) for x in logits]
        total = fsum(values)
        loss += (maximum + log(total)) / len(training)
        if gradient:
            for value, (_, row) in zip(values, session):
                probability = value / (total * len(training))
                for j, x in enumerate(row):
                    grad[j] += probability * x
    return loss, grad


def _fit_choice(statistics, representation='quadratic', ridge=1.0):
    if not statistics or representation not in ('linear', 'quadratic') or not isfinite(ridge) or ridge <= 0:
        raise ValueError('nonempty training, known representation and positive ridge required')
    dimensions = GEOMETRY_SIZE * (2 if representation == 'quadratic' else 1)
    active = [j for j in range(dimensions) if any(abs(row[j]) > 1e-12
              for session in statistics for _, row in session)]
    training = [[(offset, tuple(row[j] for j in active)) for offset, row in session]
                for session in statistics]
    weights = [0.0] * len(active)
    step = 1.0 / ridge
    for iteration in range(501):
        loss, grad = _objective(weights, training, ridge)
        gradient_max = max(map(abs, grad), default=0.0)
        if gradient_max <= 1e-7 or iteration == 500:
            break
        norm2 = fsum(g * g for g in grad)
        for _ in range(60):
            proposed = [w - step * g for w, g in zip(weights, grad)]
            new_loss, _ = _objective(proposed, training, ridge, gradient=False)
            if new_loss <= loss - 1e-4 * step * norm2:
                weights = proposed
                step = min(1 / ridge, step * 1.5)
                break
            step /= 2
        else:
            raise ArithmeticError('choice-loss line search failed')
    full = [0.0] * (2 * GEOMETRY_SIZE)
    for j, w in zip(active, weights):
        full[j] = w
    linear, quadratic = [0.0] * len(COMPONENTS), [0.0] * len(COMPONENTS)
    for j in range(GEOMETRY_SIZE):
        linear.append(full[j] + 4 * full[j + GEOMETRY_SIZE])
        quadratic.append(-4 * full[j + GEOMETRY_SIZE])
    return dict(representation=representation, ridge=ridge, temperature=TEMPERATURE,
                competitor_window=COMPETITOR_WINDOW, feature_names=list(FEATURE_NAMES),
                linear=linear, quadratic=quadratic, iterations=iteration,
                objective=loss, gradient_max=gradient_max, converged=gradient_max <= 1e-7)


def fit_choice(training, representation='quadratic', ridge=1.0):
    return _fit_choice([_choice_statistics(*session) for session in training], representation, ridge)
