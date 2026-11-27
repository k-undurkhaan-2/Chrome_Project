# Frozen offline choice candidate

**Deliverable:** a frozen linear conditional-choice ranking candidate for a
subsequent independent offline evaluation. The selected specification achieved
5/8 correct unique first choices in historical leave-one-session-out development,
compared with 2/8 for the previous contrast candidate and 1/8 for the baseline's
strict unique maximum. Across-family nested selection achieved 4/8. This is
meaningful development evidence, but it does not establish reliable accuracy
on new sessions. Three computed sessions still fail and two remain uncomputed.

Branch: `codex/experimental-offline-ranking`.
Reference baseline: `1c183c6d2ad3a920c6ef40407c8928903b2b757f`.
Frozen source and coefficients: `36eabba2a2cdbd4b26fc5bf09532f9eb51eb9744`.
Parameters: `candidate-model.json`. Digests and reproduction checks:
`candidate-freeze.json`. No production integration, release, merge or tag.

## Candidate and selection

The candidate scores each eligible record as

`baseline_score / 8 + sum(weight[j] * feature[j])`.

The fixed feature representation uses the seven already exported observations:
`f08, f18, f20, f58, f68, f70, f78`. Geometry features describe missingness,
zeros, positive-word alignment to 4/8 bytes, normalized pairwise distances,
logarithmic pairwise distances, front/tail spans and continuous contrast.
No absolute candidate address, address ordering, session ID, raw observation
identity or stored reference template is a predictor. The feature vector also
reserves baseline-component columns for other research variants; their frozen
candidate weights are zero. All quadratic coefficients are zero.

Training minimizes the equal-session average conditional softmax choice loss
plus `0.1 * ||weights||^2 / 2`. A training session contributes its reference
and every candidate within 12 baseline points of its leading score, including
every tie. The reference is always included even if below that window.
Baseline/8 is a fixed offset. This training window does not filter prediction:
every eligible candidate receives a final score. Competitors are unlabeled
choice alternatives, not independently verified negative examples.

The solver uses deterministic full-batch gradients and backtracking. The final
eight-session fit converged in 35 updates, with maximum absolute gradient
`4.4915472613900145e-08` against a `1e-7` tolerance. Final parameters contain
aggregate coefficients only. The prediction function has no reference argument.
Returned scores are not calibrated probabilities or execution permission.
`leaders` returns all maxima within `1e-10`; it never breaks ties by address
or input position to manufacture unique identification.

All 21 new alternatives were evaluated and retained:

| Family | Variants | Fixed-specification unique Top-1 range | Family nested unique Top-1 |
|---|---:|---:|---:|
| Pairwise ridge residual | 9 | 1/8 to 2/8 | 2/8 |
| Shared/shrunk moment discriminant | 6 | 3/8 to 4/8 | 2/8 |
| Conditional choice loss | 6 | 2/8 to 5/8 | 4/8 |

The quadratic choice model at ridge 0.1 also scored 5/8. Select the simpler
linear model on that tie; do not credit average-rank gains as additional
identification successes. Residual models failed to improve Top-1 over the
previous contrast candidate. Moment models improved fixed-specification
outcomes, but their nested selection was unstable. The original unsuccessful
frequency/ordinal experiments and prior cohort-ablation findings remain intact
on the previous experimental branch.

## Ten-session accounting

All ten references belong to their original supplied populations. All ten are
historical development data, including the former validation and held-out
groups. There is no fresh independent validation in this report.

The 110,604 original occurrences remain accounted for. Eight computations
score all 63,061 eligible candidates in those populations. D07 and D10 remain
uncomputed because the unchanged observation check rejects conflicting words
(13 and 3 recorded conflict events). They are valid samples, not discarded
samples or demonstrated prediction failures. No conflicting word was selected,
imputed, removed or reconciled.

D02/D03/D05/D08/D09 use ordinary replay. D01/D04/D06 use the prior conditional
frozen-table analysis after the original consistency checks; their ordinary
export rejection remains explicitly recorded. This does not change export
status or grant ordinary replay eligibility.

| Session | Route / eligible count | Baseline deterministic rank | Baseline score-rank interval | Prior contrast rank | Selected leave-one-out rank | Correct unique Top-1 |
|---|---|---:|---|---:|---:|---|
| D01 | Conditional / 6,408 | 2 | 1-4 | 2 | 1 | Yes |
| D02 | Ordinary / 8,005 | 3 | 2-3 | 2 | 2 | No |
| D03 | Ordinary / 5,708 | 2 | 2-4 | 3 | 2 | No |
| D04 | Conditional / 8,278 | 1 | 1 | 1 | 1 | Yes |
| D05 | Ordinary / 11,091 | 1 | 1-2 | 1 | 1 | Yes |
| D06 | Conditional / 7,255 | 2 | 2-3 | 2 | 1 | Yes |
| D07 | Conflict / uncomputed | Unknown | Unknown | Unknown | Unknown | Unknown |
| D08 | Ordinary / 8,588 | 3 | 3-5 | 3 | 3 | No |
| D09 | Ordinary / 7,728 | 5 | 4-6 | 4 | 1 | Yes |
| D10 | Conflict / uncomputed | Unknown | Unknown | Unknown | Unknown | Unknown |

The planned-ten accounting is **5 demonstrated successes, 3 demonstrated
errors and 2 unknown computations**. The computed-only selected-development
fraction is **5/8**. The baseline's deterministic Top-1 was 2/8, but one of
those successes depends on a tie-break; its correct unique Top-1 was 1/8.
The prior contrast candidate had 2/8 unique successes and six wrong unique
leaders. The selected fixed specification has five successes and three wrong
unique leaders, with no ambiguous leading ties on these eight computations.

## Exclusion, stability and remaining limitations

Every outer prediction excludes its session's label from training. Each inner
configuration selection also excludes the outer session entirely. Combining
the saved inner comparisons across all 21 variants and the two comparators
produces **4/8**, not 5/8. D09 is a nested-selection failure. This distinction
is retained in `candidate-stability.json` and limits the interpretation of the
selected specification's better 5/8 result.

For the fixed candidate, leave-two-session-out fitting uses six training
sessions per pair. There are 28 omitted pairs and 56 correlated predictions:
**33 correct and 23 incorrect**. These remain observations on eight sessions,
not 56 independent samples. Per-session correct counts out of seven are:

| Session | Correct / seven omitted-pair predictions |
|---|---:|
| D01 | 7/7 |
| D02 | 0/7 |
| D03 | 0/7 |
| D04 | 7/7 |
| D05 | 7/7 |
| D06 | 7/7 |
| D08 | 0/7 |
| D09 | 5/7 |

All omitted-pair fits converged. The provisional moment candidate's weaker
27/56 result is preserved in `moment-stability.json`. It is not erased after
selecting the choice model.

The final coefficients are fitted on all eight computable development
sessions. Applying them to those same sessions produces 5/8, with the same
reference ranks as the selected leave-one-out specification. This is
**resubstitution**, not a new validation result. D02/D03/D08 fail even in this
fit, so the present representation/objective remains insufficient for reliable
identification. Distinct feature vectors exist for all eight references;
these failures do not prove that further improvement is impossible.

Model families were developed after studying reused outcomes. Nested exclusion
prevents a direct outer-label input to its fitted coefficients/configuration,
but it cannot undo that broader researcher adaptation or prove independence
between sessions. The small sample count and D09 instability preclude a strong
generalization claim. Fresh independent evaluation is still needed, and is
outside this development round. No additional manual collection is requested.

## Reproduction and cost

The final replay reloads all original manifests and frozen records through the
unchanged loader, reproduces every cached full-population feature and score,
re-fits exactly identical model coefficients and reproduces final predictions.
All 45 input hashes and modification times match the preserved pre-study
record. Four original source files (the three Lua scoring/collector modules
and Python export loader) remain identical to the specified baseline.

Prediction is invariant to candidate-row reversal. Repeated fitting and
prediction reproduce their results; reversing training-session order preserves
leaders. Test coverage includes numerical gradients, known linear systems,
convergence, missing/constant inputs, relative-geometry invariance, tied leaders,
and outer-label mutation that cannot change the outer model or nested choice.

596 relevant tests passed in the complete run, including the existing Lua
5.3/5.4 offline and export-integrity suites. After adding the fixed-candidate
assessment recipe, all 17 algorithm tests passed, including its new fold-
accounting regression. No live/native target test was run or needed.

Python 3.14.3, Lupa 2.8, Lua 5.4; unchanged 256 MiB Lua allocator ceiling.
On the eight recorded populations, the baseline calculation took approximately
699-1,692 ms and feature extraction took 189-411 ms. These are single-run
observations, not controlled speedup estimates. With precomputed features,
prediction medians were 51-98 ms after one warm-up and three measured runs.
The final model fit took about 475 ms, excluding sufficient-statistic creation.
Prediction is O(N*d) with 86 fixed feature columns; training uses the bounded
baseline-competitive subset. No candidate all-pairs distance matrix is built.
Peak Python memory and end-to-end disk-loading latency were not measured.

To repeat the consumed development experiment from this checkout:

```python
import json
from pathlib import Path
from mvp0_residual_study import load_development, cross_validate, assess_choice_candidate

data = Path('OPERATOR_OWNED_DATA_DIRECTORY')
paths = sorted(data.glob('*.manifest.json'))
assert len(paths) == 11  # ten study sessions plus the earlier diagnostic
manifests = {f'D{i+1:02d}': p for i, p in enumerate(paths[-10:])}
populations, inventory = load_development(manifests, data / 'mapping-table.rtf')
for family in ('residual', 'moments', 'choice'):
    outcomes, _ = cross_validate(populations, family)
    print(family, outcomes['summary'])
model, stability = assess_choice_candidate(populations)
frozen = json.loads(Path('reports/2026-11-28/offline-ranking/candidate-model.json').read_text())
assert model == frozen
```

Use the repository's existing Python environment and include `src` on
`PYTHONPATH` (the pytest configuration already does this). For independent
evaluation, use the frozen coefficients without fitting again. The pure
prediction path, after obtaining complete baseline results through the
existing authorized offline evaluator, is:

```python
import json
from pathlib import Path
from mvp0_residual_rank import COMPONENTS, features, leaders
from mvp0_choice_rank import predict_choice

model = json.loads(Path('reports/2026-11-28/offline-ranking/candidate-model.json').read_text())
# ranked contains every eligible baseline result, with aligned rows and scores.
fields = ('f08', 'f18', 'f20', 'f58', 'f68', 'f70', 'f78')
rows = [features(tuple(r.candidate[k] for k in fields),
                 tuple(r[k] for k in COMPONENTS)) for r in ranked]
scores = predict_choice([r.final_score for r in ranked], rows, model)
winner_indices = leaders(scores)
# One index is a unique prediction. Multiple indices mean unresolved ambiguity.
# Join independent reference labels only after preserving these predictions.
```

Before reproduction or independent use, verify the canonical LF-normalized
SHA-256 digests in `candidate-freeze.json`. Raw snapshots, labels, transient
caches and runtime logs remain local and are not committed.

## Repository disposition

The existing experimental branch was continued from the verified starting
revision. Each completed logical change was GPG-signed, normally pushed over
HTTPS through the configured gh credential helper, and checked independently
via GitHub for the exact SHA, parent, changed paths and valid signature.

Mainline remains `1c183c6d2ad3a920c6ef40407c8928903b2b757f`, the prior offline
branch remains `49956c900a05f6a6d5958ccafb8e1b8c8c5c6895`, and Native MVP remains
`c1a96d715f886828200214e1a958141f116a85d9`, locally and remotely. Existing
unrelated working files were retained. No source snapshot, independent mapping,
historical evidence or integrity protection was changed.

No new version tag recommended: this is a frozen experimental candidate with
improved historical development Top-1, unresolved errors and no fresh
independent validation. It is available for that later evaluation, not approved
for mainline, production operation or release.
