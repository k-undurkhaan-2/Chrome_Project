"""Small reproducible experiment recipe for existing authorized frozen exports.

No CLI, acquisition, production integration, or new validation service.
All ten historical sessions remain in the accounting, including failures.
SPDX-License-Identifier: GPL-3.0-only
"""
from __future__ import annotations

import gc
import hashlib
import re
from itertools import combinations
from math import fsum
from pathlib import Path
from statistics import median
from time import perf_counter

from lupa.lua54 import LuaRuntime

from mvp0_export_loader import load_inventory, load_replay, _check_replay_records
from mvp0_residual_rank import (
    COMPONENTS, features, leaders, predict, _statistics, _fit_statistics,
)
from mvp0_moment_rank import _moment_statistics, _fit_moments, predict_moments
from mvp0_choice_rank import _choice_statistics, _fit_choice, predict_choice

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('f08', 'f18', 'f20', 'f58', 'f68', 'f70', 'f78')
SPECS = [('baseline', None, None), ('contrast', None, None)] + [
    (f'{representation}_{ridge:g}', representation, ridge)
    for representation in ('components', 'geometry', 'combined') for ridge in (10.0, 1.0, 0.1)
]
MOMENT_SPECS = [('baseline', None, None), ('contrast', None, None)] + [
    (f'{variance}_{amplitude:g}', variance, amplitude)
    for variance in ('shared', 'shrunk') for amplitude in (0.25, 1.0, 4.0)
]
CHOICE_SPECS = [('baseline', None, None), ('contrast', None, None)] + [
    (f'{representation}_{ridge:g}', representation, ridge)
    for representation in ('linear', 'quadratic') for ridge in (10.0, 1.0, 0.1)
]


def fingerprints(paths):
    return {str(p.resolve()): [hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns]
            for p in paths}


def load_development(manifests, mapping_path):
    """Extract full-population features, then join independent labels separately.

    The unchanged loader and Lua scorer retain all original integrity checks.
    The conditional route preserves its ordinary replay rejection explicitly.
    Returned populations contain local research data and must not be published.
    """
    mapping_path = Path(mapping_path)
    paths = [mapping_path]
    for p in map(Path, manifests.values()):
        paths.extend(q for q in p.parent.glob(p.name.removesuffix('.manifest.json') + '.*') if q.is_file())
    before = fingerprints(paths)
    sources = {n: (ROOT / 'src' / n).read_text(encoding='utf-8-sig')
               for n in ('mvp0_candidate_report.lua', 'mvp0_foundlist_collector.lua', 'mvp0_offline_scoring.lua')}
    fixture = (ROOT / 'tests/fixtures/offline_population.lua').read_text(encoding='utf-8-sig')
    populations, sessions, pending = {}, [], []
    try:
        for name, path in manifests.items():
            manifest, inventory = load_inventory(path)
            if manifest.get('authorized_owned') is not True or manifest.get('permission_disposition') != 'EXPRESSLY_APPROVED':
                raise ValueError('explicitly authorized owned exports required')
            output = dict(dataset=name, supplied=len(inventory), original_outcome=manifest['outcome'],
                          completed=False, conflict_events=manifest['counts']['conflicting_observations'])
            sessions.append(output)
            membership = {r['addr'] for r in inventory}
            identities = []
            lua = world = api = records = opts = result = ranked = None
            try:
                _check_replay_records(inventory, manifest['counts'])
                lua = LuaRuntime(unpack_returned_tuples=True, max_memory=256 * 1024 * 1024)
                world = lua.execute(fixture).new(lua.table_from(sources))
                api = lua.execute(sources['mvp0_offline_scoring.lua'])
                try:
                    records, opts, _ = load_replay(path, lua)
                    output['route'] = 'ordinary_replay'
                except ValueError as error:
                    if str(error) != 'export is not replay-ready':
                        raise
                    output['route'] = 'conditional_frozen_tables'
                    output['ordinary_replay_rejection'] = str(error)
                    records = lua.table_from([lua.table_from({
                        k: lua.table_from(r[k]) if k == 'memory' else r[k]
                        for k in ('addr', 'mapped', 'protect', 'memory')}) for r in inventory])
                    opts = lua.table_from(manifest['evaluation_options'])
                opts['population_mode'] = 'full'
                assert opts['scan_budget'] is None and opts['max_candidates'] is None
                start = perf_counter()
                result = api.run(records, opts, world.load)
                baseline_ms = (perf_counter() - start) * 1000
                assert result.completed and result.population_complete
                counts = dict(result.counts.items())
                assert counts['eligible'] == counts['selected'] == counts['fully_scored'] == counts['ranked']
                start = perf_counter()
                ranked = [result.result.ranked[i] for i in range(1, len(result.result.ranked) + 1)]
                identities = [r.candidate.value_addr for r in ranked]
                words = [tuple(r.candidate[k] for k in FIELDS) for r in ranked]
                scores = [r.final_score for r in ranked]
                rows = [features(w, tuple(r[k] for k in COMPONENTS)) for w, r in zip(words, ranked)]
                populations[name] = dict(scores=scores, rows=rows,
                                         contrast=[score + row[-1] for score, row in zip(scores, rows)])
                output.update(completed=True, counts=counts, baseline_ms=baseline_ms,
                              feature_extraction_ms=(perf_counter() - start) * 1000,
                              lua_mib_at_return=lua.get_memory_used(total=True) / 1024**2)
            except ValueError as error:
                output['computation_error'] = str(error)
            finally:
                lua = world = api = records = opts = result = ranked = inventory = None
                gc.collect()
            pending.append((output, manifest, membership, identities))
        mapping = mapping_path.read_text(encoding='utf-8-sig')
        for output, manifest, membership, identities in pending:
            matches = re.findall(r'manual-export-' + re.escape(manifest['dataset_id'])
                                 + r'\s+PID=(0x[0-9A-Fa-f]+)\s+true_addr=(0x[0-9A-Fa-f]+)', mapping)
            if len(matches) != 1:
                raise ValueError('ambiguous or missing independent mapping')
            pid, reference = (int(x, 16) for x in matches[0])
            assert pid == manifest['ce_capture']['process_id']
            output['reference_member'] = reference in membership
            output['reference_eligible'] = reference in identities if output['completed'] else None
            if output['completed']:
                if not output['reference_eligible']:
                    raise ValueError('completed training population lacks reference')
                populations[output['dataset']]['reference'] = identities.index(reference)
    finally:
        assert before == fingerprints(paths), 'input content or modification time changed'
    return populations, dict(planned=len(manifests), computed=len(populations),
                             historical_development_only=True, input_preservation=True, sessions=sessions)


def metrics(scores, reference):
    tolerance = 1e-10
    score = scores[reference]
    above = sum(x > score + tolerance for x in scores)
    equal = sum(abs(x - score) <= tolerance for x in scores)
    top = leaders(scores, tolerance)
    return dict(unique_top1=top == (reference,), unique_leader=len(top) == 1,
                reference_is_leader=reference in top, leading_tie=len(top),
                rank_interval=[above + 1, above + equal], midrank=above + (equal + 1) / 2,
                margin=score - max((x for i, x in enumerate(scores) if i != reference), default=score))


def cross_validate(populations, family='residual'):
    """Exhaustive nested session exclusion; no outer labels select their model.

    Sufficient statistics belong to one training session each. Every model is
    built from an explicit training-name tuple excluding its test session.
    Nested selection also excludes the outer session from every inner model.
    """
    if family not in ('residual', 'moments', 'choice'):
        raise ValueError('unknown model family')
    specs = SPECS if family == 'residual' else MOMENT_SPECS
    make_statistics = _statistics if family == 'residual' else _moment_statistics
    fit_model = _fit_statistics if family == 'residual' else _fit_moments
    predict_model = predict if family == 'residual' else predict_moments
    if family == 'choice':
        specs, make_statistics, fit_model, predict_model = (
            CHOICE_SPECS, _choice_statistics, _fit_choice, predict_choice)
    names = tuple(sorted(populations))
    if len(names) < 3:
        raise ValueError('at least three computed training sessions required')
    start = perf_counter()
    stats = {name: make_statistics(p['scores'], p['rows'], p['reference']) for name, p in populations.items()}
    stats_ms = (perf_counter() - start) * 1000
    cache = {}
    fold_models = {}

    def evaluate(train, test, spec):
        key = (train, test, spec[0])
        if key in cache:
            return cache[key]
        assert test not in train
        p = populations[test]
        start = perf_counter()
        if spec[0] in ('baseline', 'contrast'):
            scores = p['scores' if spec[0] == 'baseline' else 'contrast']
            fit_ms = 0.0
        else:
            model = fit_model([stats[n] for n in train], spec[1], spec[2])
            fit_ms = (perf_counter() - start) * 1000
            start = perf_counter()
            scores = predict_model(p['scores'], p['rows'], model)
            if len(train) == len(names) - 1:
                fold_models[(test, spec[0])] = model
        prediction_ms = (perf_counter() - start) * 1000
        result = metrics(scores, p['reference'])
        result.update(training_sessions=list(train), fit_ms=fit_ms, prediction_ms=prediction_ms)
        if family == 'choice' and spec[0] not in ('baseline', 'contrast'):
            result.update(converged=model['converged'], iterations=model['iterations'],
                          gradient_max=model['gradient_max'])
        cache[key] = result
        return result

    outer, nested = {}, {}
    for test in names:
        train = tuple(n for n in names if n != test)
        outer[test] = {spec[0]: evaluate(train, test, spec) for spec in specs}
        inner = {}
        for spec in specs:
            outcomes = [evaluate(tuple(n for n in train if n != inner_test), inner_test, spec)
                        for inner_test in train]
            inner[spec[0]] = sum(o['unique_top1'] for o in outcomes)
        # Fixed preference order: baseline, prior contrast, simpler representation,
        # then stronger regularization. No rank or margin chooses a tied model.
        chosen = max(specs, key=lambda spec: inner[spec[0]])
        nested[test] = dict(chosen=chosen[0], inner_unique_top1=inner,
                            result=outer[test][chosen[0]])
    summary = {}
    for spec in specs:
        rows = [outer[n][spec[0]] for n in names]
        summary[spec[0]] = summarize_metrics(rows)
    summary['nested_selection'] = summarize_metrics([nested[n]['result'] for n in names])
    return dict(computed=len(names), statistics_ms=stats_ms,
                total_ms=(perf_counter() - start) * 1000, specs=specs, family=family,
                outer=outer, nested=nested, summary=summary), fold_models


def summarize_metrics(rows):
    return dict(evaluated=len(rows), unique_top1=sum(r['unique_top1'] for r in rows),
                incorrect_unique_leaders=sum(r['unique_leader'] and not r['unique_top1'] for r in rows),
                ambiguous=sum(not r['unique_leader'] for r in rows),
                mean_midrank=fsum(r['midrank'] for r in rows) / len(rows),
                midranks=[r['midrank'] for r in rows])


def assess_choice_candidate(populations):
    """Assess the selected linear/ridge-0.1 specification, without retuning.

    Return its final all-development fit separately from excluded-pair evidence.
    Repeated predictions and overlapping folds never increase the sample count.
    The returned model contains coefficients, not training examples or labels.
    """
    names = tuple(sorted(populations))
    if len(names) < 3:
        raise ValueError('at least three computable sessions required')
    statistics = {n: _choice_statistics(p['scores'], p['rows'], p['reference'])
                  for n, p in populations.items()}
    outcomes = []
    for omitted in combinations(names, 2):
        train = tuple(n for n in names if n not in omitted)
        model = _fit_choice([statistics[n] for n in train], 'linear', 0.1)
        for test in omitted:
            p = populations[test]
            scores = predict_choice(p['scores'], p['rows'], model)
            outcomes.append(dict(omitted=list(omitted), test=test, converged=model['converged'],
                                 **metrics(scores, p['reference'])))
    start = perf_counter()
    model = _fit_choice([statistics[n] for n in names], 'linear', 0.1)
    fit_ms = (perf_counter() - start) * 1000
    repeated = _fit_choice([statistics[n] for n in names], 'linear', 0.1)
    assert repeated == model, 'nondeterministic final fit'
    reversed_model = _fit_choice([statistics[n] for n in reversed(names)], 'linear', 0.1)
    coefficient_difference = max(abs(a - b) for key in ('linear', 'quadratic')
                                 for a, b in zip(model[key], reversed_model[key]))
    fitted, timings = {}, {}
    for name in names:
        p = populations[name]
        times, previous = [], None
        for repeat in range(4):
            start = perf_counter()
            scores = predict_choice(p['scores'], p['rows'], model)
            elapsed = (perf_counter() - start) * 1000
            if repeat:
                times.append(elapsed)
                assert scores == previous, 'nondeterministic prediction'
            previous = scores
        reversed_scores = predict_choice(list(reversed(p['scores'])), list(reversed(p['rows'])), model)
        assert scores == list(reversed(reversed_scores)), 'row-order-dependent prediction'
        permuted_fit_scores = predict_choice(p['scores'], p['rows'], reversed_model)
        assert leaders(scores) == leaders(permuted_fit_scores), 'training-order-dependent leader'
        fitted[name] = metrics(scores, p['reference'])
        timings[name] = dict(measured_ms=times, median_ms=median(times), eligible=len(scores))
    return model, dict(candidate='choice_linear_0.1', historical_development_only=True,
                       computed_sessions=len(names), training_sessions_per_pair_fold=len(names) - 2,
                       omitted_pairs=len(outcomes) // 2, correlated_predictions=len(outcomes),
                       leave_two_out=summarize_metrics(outcomes),
                       by_session={n: summarize_metrics([r for r in outcomes if r['test'] == n]) for n in names},
                       outcomes=outcomes, final_fit_resubstitution=fitted,
                       resubstitution_summary=summarize_metrics(list(fitted.values())),
                       final_training_ms=fit_ms, prediction_timings=timings,
                       fit_reproduced=True, prediction_reproduced=True, row_permutation_invariant=True,
                       training_permutation_same_leaders=True,
                       training_permutation_max_coefficient_difference=coefficient_difference,
                       all_pair_fits_converged=all(r['converged'] for r in outcomes))
