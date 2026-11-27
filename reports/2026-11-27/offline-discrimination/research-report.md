# Offline contrast candidate: reproducible research handoff

**Deliverable:** a frozen offline ranking candidate with a complete experimental
record and independent evaluation. **Top-1 improvement was not demonstrated.**
The candidate reduced some ties and improved reference midranks, but none of
the three computable independent sessions had a correct first choice.
It remains a research artifact, not an accepted replacement for the default
scorer. No production integration, release, tag or pull request was created.

Baseline: `1c183c6d2ad3a920c6ef40407c8928903b2b757f`.
Algorithm source: `b44d985992cade1a42ff2c3313372b500e067942`.
Pre-evaluation freeze: `294dd33d53bb75d904413155318097c904273635`.
Branch: `codex/temp-offline-discrimination-20261127`.

## Candidate and research basis

The candidate adds a bounded, unit-amplitude continuous distance contrast to
the unchanged full baseline score. It uses the existing three front and three
tail observations. The middle/status observation does not enter the supplement.
Let C be the sum of the nine absolute cross-group distances and F,T the
within-group spans. The supplement is:

`q = C / (C + 3*(F+T))`, or zero for an all-constant or missing-observation row.

The final score is `baseline_score + q`. No reference identity, sample identity,
absolute candidate address, reference template or fitted label-dependent weight
enters this calculation. Existing baseline cohort contributions are unchanged.
The score is continuous and invariant to a common translation and positive
scaling of the six observations. Equal scores retain original baseline ordering
only for deterministic reporting; they are never counted as unique maxima.

This tests whether continuous within/between-group geometry recovers information
lost by the baseline's coarse structural summaries. The initial geometry study
also tested the [silhouette coefficient of Rousseeuw (1987)](https://doi.org/10.1016/0377-0427(87)90125-7).
The chosen ratio is a simpler alternative, not a claim that the paper establishes
identification accuracy. The sum of pair distances within three points is twice
their span, giving the optimized equivalent formula above.

All 18 current alternatives and all outcomes are retained:

- Nine frequency variants: no reference-rank or unique-maximum improvement;
  rejected. See `frequency-research.json` and `frequency-decision.md`.
- Six continuous geometry variants: identical reference outcomes, partial
  improvement; select unit-amplitude contrast for simplicity and bounded impact.
  See `geometry-research.json` and `geometry-decision.md`.
- Three ordinal-family variants: substantial regressions, including lost Top-3
  coverage; all rejected. See `ordinal-research.json` and `ordinal-decision.md`.

The prior failed complete cohort ablation and scalar-penalty interpolation are
acknowledged in the protocol; they were not counted as new independent trials.
Selection used D01-D05 only. Eighteen comparisons on five sessions do not form
90 independent trials. No further algorithm or parameter changes followed the
freeze or either independent evaluation.

## Complete sample accounting

All ten references belong to their original supplied populations under the
maintainer's sample-validity definition. Across all ten, 110,604 original
occurrences remain accounted for. Eight analytical evaluations completed,
covering 63,061/63,061 eligible candidates in those eight populations. Two
planned samples remain uncomputed; they are neither successful nor demonstrated
ranking errors. Original files, statuses and observations were not repaired.

D02/D03/D05/D08/D09 used ordinary replay. D01/D04/D06 used separately identified
conditional frozen-table analysis after the unchanged observation checks;
their original exports remain rejected by ordinary replay. D07 and D10 failed
the existing conflicting-observation check. Their independent references are
present, and their manifests report 13 and 3 conflict events respectively.
No conflicting word was chosen, imputed, dropped or reconciled.

Accuracy fractions below use the stated computed-session denominator. Planned
and uncomputed counts are shown explicitly to prevent denominator substitution.

| Group | Planned / computed / uncomputed | Top-1 A -> B | Unique highest A -> B | Top-3 A -> B | Mean midrank A -> B |
|---|---|---|---|---|---|
| Research D01-D05 | 5 / 5 / 0 | 2/5 -> 2/5 | 1/5 -> 2/5 | 5/5 -> 5/5 | 2.10 -> 1.80 |
| Validation D06-D08 | 3 / 2 / 1 | 0/2 -> 0/2 | 0/2 -> 0/2 | 2/2 -> 2/2 | 3.25 -> 2.50 |
| Held-out D09-D10 | 2 / 1 / 1 | 0/1 -> 0/1 | 0/1 -> 0/1 | 0/1 -> 0/1 | 5.00 -> 4.00 |

A is baseline; B is the frozen candidate. For the five planned independent
sessions, there are zero demonstrated first-choice successes, three computed
outcomes and two unknown outcomes. Conditional accuracy is 0/3, not evidence
that the two uncomputed samples are incorrect. This very small independent
sample does not establish a population accuracy rate or successful generalization.

| Session | Route | Eligible scored | Deterministic rank A -> B | Midrank A -> B | Unique highest A -> B |
|---|---|---:|---|---|---|
| D01 | Conditional | 6408 | 2 -> 2 | 2.5 -> 2.0 | 0 -> 0 |
| D02 | Ordinary | 8005 | 3 -> 2 | 2.5 -> 2.0 | 0 -> 0 |
| D03 | Ordinary | 5708 | 2 -> 3 | 3.0 -> 3.0 | 0 -> 0 |
| D04 | Conditional | 8278 | 1 -> 1 | 1.0 -> 1.0 | 1 -> 1 |
| D05 | Ordinary | 11091 | 1 -> 1 | 1.5 -> 1.0 | 0 -> 1 |
| D06 | Conditional | 7255 | 2 -> 2 | 2.5 -> 2.0 | 0 -> 0 |
| D07 | Rejected: conflicting observations | Uncomputed | Unknown | Unknown | Unknown |
| D08 | Ordinary | 8588 | 3 -> 3 | 4.0 -> 3.0 | 0 -> 0 |
| D09 | Ordinary | 7728 | 5 -> 4 | 5.0 -> 4.0 | 0 -> 0 |
| D10 | Rejected: conflicting observations | Uncomputed | Unknown | Unknown | Unknown |

D03's deterministic rank regressed from 2 to 3 although its midrank stayed 3.
D01's leading four-way tie became a unique but incorrect leader; reducing the
leading tie size alone is not accurate identification. D05 gained a genuine
unique maximum, with a 0.067882-point margin. The three computable independent
midranks improved from [2.5,4,5] to [2,3,4], but no first-choice match resulted.

Reference-versus-unlabeled separation counts equal scores as one-half. Other
records lack independent negative labels, so this is not AUROC or specificity.

- Research: mean half-credit separation 99.983659% -> 99.987371% on 5 computed sessions.
- Validation: mean half-credit separation 99.972193% -> 99.981462% on 2 computed sessions.
- Held-out: mean half-credit separation 99.948233% -> 99.961175% on 1 computed sessions.

## Computational cost and verification

Python 3.14.3, Lupa 2.8, Lua 5.4; unchanged 256 MiB Lua allocator ceiling.
Research timing used one warm-up and three measured repetitions per session.
Twenty baseline calls reproduced identical predictions and the pre-optimization
metrics. Repetitions do not increase the five-session denominator.

Baseline timing includes the ordinary full evaluator's internal loading,
validation, feature/scoring work, sorting, report generation and completion
checks. It excludes disk reading, runtime setup, table conversion, explicit
pre-call garbage collection, extraction and subsequent label-based metrics.
Candidate extra timing includes contrast, score addition and an additional
full-population sort; extraction is separately recorded in the JSON evidence.
This is an additive offline cost comparison, not a speedup or native benchmark.

| Session | Baseline median ms | Candidate extra median ms | Extra / baseline |
|---|---:|---:|---:|
| D01 | 740.67 | 14.89 | 2.01% |
| D02 | 966.38 | 18.45 | 1.91% |
| D03 | 690.43 | 13.82 | 2.00% |
| D04 | 955.23 | 19.35 | 2.03% |
| D05 | 1349.18 | 25.18 | 1.87% |

The supplement is O(N) and the additional sort O(N log N); there is no
all-pairs comparison across candidates. Observed overhead is about 2%, so
strictly unchanged runtime or improved speed has not been demonstrated.
Peak memory and native latency were not measured.

594 relevant tests passed, including the existing export integrity and Lua
5.3/5.4 offline contracts, frequency/ordinal invariances, geometry invariances,
1,000 independent synthetic formula comparisons, and unresolved-tie handling.
The original three Lua sources and Python loader remain content-identical to
the baseline. All nine frozen source digests still match.

Execution failures are retained separately from algorithm outcomes. The first
frequency invocation stopped before scoring because a directory entered its
fingerprint file list. A later regression invocation encountered an existing
inaccessible pytest temporary directory and was interrupted; the same 594 tests
then passed using a fresh checkout-local temporary directory. Neither event
changed a dataset, scoring outcome or protection.

Content digests and modification times matched for all 45 top-level input
files, including the independent RTF mapping. Existing local edits were retained.
Mainline remains `1c183c6d2ad3a920c6ef40407c8928903b2b757f`, and Native MVP remains
`c1a96d715f886828200214e1a958141f116a85d9`, locally and remotely.
Every completed logical change was signed, normally pushed over HTTPS and
remotely checked for exact SHA, parent, changed paths and valid GitHub signature.
No original snapshot, mapping, historical evidence or integrity protection was
modified; no live process operation or target-access capability was introduced.

## Reproduction and independent use

Run from this experimental checkout with the existing Python/Lupa environment.
The candidate itself is `src/mvp0_geometry_rank.py::contrast_rank`. Supply the
complete baseline score vector and seven observation columns in corresponding
baseline-comparator order. It returns scores and ordered input indices; it does
not read references or create a production action/recommendation envelope.

The small experiment recipe is `src/mvp0_frequency_study.py::evaluate`. The
following Python reproduces the already consumed groups on the original local
inventory. It creates no new source data and prints aggregate results only:

```python
import sys
from pathlib import Path
sys.path.insert(0, 'src')
from mvp0_frequency_study import evaluate, summarize

data = Path('OPERATOR_OWNED_DATA_DIRECTORY')
all_manifests = sorted(data.glob('*.manifest.json'))
assert len(all_manifests) == 11  # ten study sessions and the earlier diagnostic
study = all_manifests[-10:]     # original outcome-independent frozen assignment
model = {'contrast_1': ('contrast', 1)}
for start, stop in ((0, 5), (5, 8), (8, 10)):
    group = {f'D{i+1:02d}': study[i] for i in range(start, stop)}
    result = evaluate(group, data / 'mapping-table.rtf', model)
    print(summarize(result))
```

Check the canonical LF-normalized SHA-256 values in `candidate-freeze.json`
against the listed files before reproduction. Disk-loading/conversion time is
not included in the reported algorithm timings. For other independently
supplied authorized populations, pass explicit manifest paths and their own
independent mapping rather than reusing these labels. The pure candidate can
also be evaluated directly by a separate evaluator.

Repeating D06-D10 reproduces consumed evidence; it is not another blind test.
Do not use their outcomes for further model selection while claiming they
remain independent. Future claims of improved first-choice generalization
would need independent offline evidence beyond this consumed evaluation.
No new acquisition or live workflow is requested by this report.

Existing regression command (choose a new, empty local temporary directory):

```text
python -B -m pytest -q --basetemp log/fresh-test-run tests/test_frequency_rank.py tests/test_geometry_rank.py tests/test_ordinal_rank.py tests/test_offline_full_population.py tests/test_offline_collector_interface.py tests/test_manual_export.py
```

## File inventory

All changes in this experiment are additions relative to the frozen baseline.
Failed experiment implementations are retained solely for reproducibility.

- `reports/2026-11-27/offline-discrimination/candidate-freeze.json`
- `reports/2026-11-27/offline-discrimination/candidate-research.json`
- `reports/2026-11-27/offline-discrimination/frequency-decision.md`
- `reports/2026-11-27/offline-discrimination/frequency-research.json`
- `reports/2026-11-27/offline-discrimination/geometry-decision.md`
- `reports/2026-11-27/offline-discrimination/geometry-research.json`
- `reports/2026-11-27/offline-discrimination/held-out.json`
- `reports/2026-11-27/offline-discrimination/ordinal-decision.md`
- `reports/2026-11-27/offline-discrimination/ordinal-research.json`
- `reports/2026-11-27/offline-discrimination/protocol.md`
- `reports/2026-11-27/offline-discrimination/research-report.md`
- `reports/2026-11-27/offline-discrimination/validation.json`
- `src/mvp0_frequency_rank.py`
- `src/mvp0_frequency_study.py`
- `src/mvp0_geometry_rank.py`
- `src/mvp0_ordinal_rank.py`
- `tests/test_frequency_rank.py`
- `tests/test_geometry_rank.py`
- `tests/test_ordinal_rank.py`

## Disposition

Retain the candidate and complete evidence on the isolated experimental branch.
It offers a limited ranking-resolution improvement, not demonstrated Top-1
improvement. No new version tag recommended: this is an exploratory candidate
with unsuccessful independent first-choice identification and two uncomputed
independent sessions. No merge, production release or promotion is justified
by this study.
