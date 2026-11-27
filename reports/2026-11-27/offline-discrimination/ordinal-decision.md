# Ordinal refinement: rejected; candidate selection

All three preregistered variants completed 39,490 eligible records in five
research sessions. Every copied original clone penalty matched the baseline
before refinement. Complete results are in `ordinal-research.json`.

| Variant | Top-1 | Unique maximum | Top-3 | Mean midrank | Deterministic ranks |
|---|---:|---:|---:|---:|---|
| Baseline | 2/5 | 1/5 | 5/5 | 2.1 | 2,3,2,1,1 |
| Ordinal | 1/5 | 0/5 | 4/5 | 10.3 | 2,15,2,2,1 |
| Ordinal + silhouette | 2/5 | 2/5 | 4/5 | 7.8 | 3,31,1,3,1 |
| Ordinal + contrast | 1/5 | 1/5 | 2/5 | 8.8 | 4,33,2,4,1 |

Reject all three: splitting families discarded useful cohort evidence and
worsened discrimination. Do not promote a successful individual session such
as D03 from the otherwise unsuccessful silhouette combination.

## Candidate chosen on research data only

Retain the existing full score plus unit-amplitude continuous distance contrast.
This preserves the full original cohort contribution. All six geometry variants
had the same reference outcomes; unit amplitude is the most conservative, and
contrast has fewer operations than silhouette. The choice is a partial advance:
research Top-1 remains 2/5, unique maximum improves 1/5 to 2/5, mean midrank
improves 2.1 to 1.8, and Top-3 remains 5/5. No improved Top-1 claim is justified.

There have been 18 current variants: nine frequency, six geometry and three
ordinal. They used the same five development sessions, not 90 independent
trials. Prior failed cohort ablation and scalar interpolation remain historical
evidence. Selection among these variants makes research results optimistic;
independent outcomes are still required.

Before freezing, implement the algebraically equivalent constant-work contrast
formula and check it against the original pair-distance formula on synthetic
inputs and the same research populations. For within-group spans F and T and
cross-distance sum C, contrast = C / (C + 3*(F+T)). This follows because the
three unordered distances in a three-point group sum to twice its span.
No thresholds, observations or predictions are changed intentionally.

Then freeze the final source hashes and evaluate D06-D08 once and D09-D10 once.
Do not tune any model or amplitude in response. Preserve all planned samples,
failed or conditional computation, and small-sample uncertainty in reporting.
