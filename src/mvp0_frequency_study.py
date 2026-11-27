"""Reproducible paired calculations for authorized frozen records, no CLI.

Call evaluate with explicitly selected manifest paths and the existing mapping.
Only aggregate metrics leave the calculation. Inputs and original loader remain
unchanged. This is an experiment recipe, not a capture or validation service.
SPDX-License-Identifier: GPL-3.0-only
"""
from __future__ import annotations

import gc
import hashlib
import re
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from lupa.lua54 import LuaRuntime

from mvp0_export_loader import load_inventory, load_replay, _check_replay_records
from mvp0_frequency_rank import novelty, combine
from mvp0_geometry_rank import geometry
from mvp0_ordinal_rank import refine_clones

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('f08', 'f18', 'f20', 'f58', 'f68', 'f70', 'f78')
INITIAL_MODELS = {f'frequency_{order}_{amplitude}': (order, amplitude)
                  for order in (1, 2, 7) for amplitude in (1, 3, 6)}


def fingerprints(paths):
    return {str(p): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            for p in paths}


def metrics(scores, reference_index):
    """Tie tolerance prevents machine roundoff being credited as information."""
    tolerance = 1e-12
    s = scores[reference_index]
    above = sum(x > s + tolerance for x in scores)
    equal = sum(abs(x - s) <= tolerance for x in scores)
    other = scores[:reference_index] + scores[reference_index + 1:]
    # Input sequence is the unchanged baseline comparator's order. It is used
    # only to report deterministic ranks, never to construct statistical scores.
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    rank = order.index(reference_index) + 1
    top = max(scores)
    return dict(rank=rank, top1=rank == 1, top3=rank <= 3,
                unique_highest=above == 0 and equal == 1, strictly_above=above,
                equal_interval=[above + 1, above + equal],
                midrank=above + (equal + 1) / 2,
                leading_tie=sum(abs(x - top) <= tolerance for x in scores),
                separation=(len(scores) - above - equal + .5 * (equal - 1)) / len(other)
                if other else None,
                margin_to_best=s - max(other) if other else None,
                margin_to_median=s - median(other) if other else None)


def evaluate(manifests, mapping_path, models=None, repeats=1):
    """manifests maps anonymous session names to immutable, authorized files.

    Every model is computed without reference labels. Labels are joined only
    after all requested populations have been scored. No model fitting occurs.
    A rejected ordinary replay is separately reported; an analytical table
    comparison is attempted only when all original observations pass existing
    consistency checks. It never rewrites an export or bypasses AC5 checks.
    """
    models = INITIAL_MODELS if models is None else models
    mapping_path = Path(mapping_path)
    preserved = [mapping_path]
    for path in manifests.values():
        path = Path(path)
        preserved.extend(path.parent.glob(path.name.removesuffix('.manifest.json') + '.*'))
    before = fingerprints(preserved)
    sources = {name: (ROOT / 'src' / name).read_text(encoding='utf-8-sig')
               for name in ('mvp0_candidate_report.lua', 'mvp0_foundlist_collector.lua',
                            'mvp0_offline_scoring.lua')}
    fixture = (ROOT / 'tests/fixtures/offline_population.lua').read_text(encoding='utf-8-sig')
    pending = []
    outputs = []
    try:
        for name, path in manifests.items():
            lua = LuaRuntime(unpack_returned_tuples=True, max_memory=256 * 1024 * 1024)
            world = lua.execute(fixture).new(lua.table_from(sources))
            api = lua.execute(sources['mvp0_offline_scoring.lua'])
            manifest, inventory = load_inventory(path)
            output = dict(dataset=name, supplied=len(inventory),
                          original_outcome=manifest['outcome'], completed=False)
            outputs.append(output)
            try:
                _check_replay_records(inventory, manifest['counts'])
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
                baseline_times, extraction_times, model_times = [], [], {key: [] for key in models}
                last = None
                for repeat in range(repeats):
                    gc.collect()
                    lua.gccollect()
                    start = perf_counter()
                    result = api.run(records, opts, world.load)
                    baseline_times.append((perf_counter() - start) * 1000)
                    assert result.completed and result.population_complete
                    counts = dict(result.counts.items())
                    assert counts['eligible'] == counts['selected'] == counts['fully_scored'] == counts['ranked']
                    start = perf_counter()
                    ranked = [result.result.ranked[i] for i in range(1, len(result.result.ranked) + 1)]
                    identities = [r.candidate.value_addr for r in ranked]
                    words = [tuple(r.candidate[k] for k in FIELDS) for r in ranked]
                    base = [r.final_score for r in ranked]
                    clone_data = None
                    if any(str(v[0]).startswith('ordinal') for v in models.values()):
                        clone_data = ([r.clone_family_id for r in ranked],
                                      [r.local_features.advanced_layout.pointer_alignment_count for r in ranked],
                                      [r.clone_penalty for r in ranked])
                    extraction_times.append((perf_counter() - start) * 1000)
                    predicted = {'baseline': base}
                    for key, (order, amplitude) in models.items():
                        start = perf_counter()
                        if str(order).startswith('ordinal'):
                            delta = refine_clones(words, *clone_data)
                            newbase = [score + change for score, change in zip(base, delta)]
                            predicted[key] = newbase if order == 'ordinal' else combine(
                                newbase, geometry(words, order.removeprefix('ordinal_')), amplitude)
                        else:
                            extra = geometry(words, order) if isinstance(order, str) else novelty(words, order)
                            predicted[key] = combine(base, extra, amplitude)
                        model_times[key].append((perf_counter() - start) * 1000)
                    if last is not None:
                        assert last == predicted
                    last = predicted
                    output['lua_mib_at_return'] = lua.get_memory_used(total=True) / 1024**2
                    result = ranked = None
                output.update(completed=True, counts=counts,
                              timing_ms=dict(baseline=baseline_times, extraction=extraction_times,
                                             alternatives=model_times))
                pending.append((output, manifest, {r['addr'] for r in inventory}, identities, predicted))
            except ValueError as error:
                # Loader errors contain contract descriptions, never raw observations.
                output['error'] = str(error)
            finally:
                records = opts = world = api = lua = inventory = None
                gc.collect()
        mapping = mapping_path.read_text(encoding='utf-8-sig')
        for output, manifest, membership, identities, predictions in pending:
            matches = re.findall(r'manual-export-' + re.escape(manifest['dataset_id'])
                                 + r'\s+PID=(0x[0-9A-Fa-f]+)\s+true_addr=(0x[0-9A-Fa-f]+)', mapping)
            if len(matches) != 1:
                raise ValueError('ambiguous or missing independent mapping')
            pid, reference = map(lambda x: int(x, 16), matches[0])
            assert pid == manifest['ce_capture']['process_id']
            output['reference_member'] = reference in membership
            output['reference_eligible'] = reference in identities
            if not output['reference_eligible']:
                output['metrics'] = {key: dict(top1=False, top3=False, unique_highest=False,
                                               not_ranked=True) for key in predictions}
            else:
                index = identities.index(reference)
                output['metrics'] = {key: metrics(values, index) for key, values in predictions.items()}
    finally:
        assert before == fingerprints(preserved), 'input content or modification time changed'
    return dict(planned=len(manifests), computed=sum(o['completed'] for o in outputs),
                repeats=repeats, input_preservation=True, sessions=outputs)


def summarize(result):
    sessions = [x for x in result['sessions'] if x.get('metrics')]
    summary = {}
    for key in sessions[0]['metrics'] if sessions else []:
        rows = [s['metrics'][key] for s in sessions]
        ranked = [r for r in rows if not r.get('not_ranked')]
        summary[key] = dict(planned=result['planned'], evaluated=len(rows),
                            top1=sum(r['top1'] for r in rows),
                            top3=sum(r['top3'] for r in rows),
                            unique=sum(r['unique_highest'] for r in rows),
                            mean_midrank=mean(r['midrank'] for r in ranked) if ranked else None,
                            mean_separation=mean(r['separation'] for r in ranked) if ranked else None,
                            ranks=[r.get('rank') for r in rows],
                            midranks=[r.get('midrank') for r in rows])
    return summary
