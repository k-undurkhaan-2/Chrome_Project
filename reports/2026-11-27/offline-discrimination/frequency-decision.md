# Initial frequency experiment: rejected

All nine preregistered models completed all five research sessions, preserving
39,490 eligible candidates from 54,952 supplied occurrences. D01/D04 remain
conditional analyses; ordinary replay still rejects their original exports.

Every model retained baseline ranks [2,3,2,1,1], midranks [2.5,2.5,3,1,1.5],
Top-1 2/5, Top-3 5/5 and unique maximum 1/5. Frequency supplements did not
resolve reference ambiguity. Full per-session results, timing and unsuccessful
variants are in `frequency-research.json`; no outcome was omitted.

An initial invocation failed before scoring because its fingerprint input list
included a directory. Restricting that invocation to files fixed the invocation;
no input, loader, integrity check or algorithm was changed. This is an execution
failure, not an accuracy trial. The subsequent computation preserved input
bytes and modification times. Reserved feature/prediction outcomes remain unopened.

Frequency-based unusualness is a plausible generic hypothesis, not an identity
model. Das and Schneider's original research explicitly distinguishes rare
values from meaningful anomalies: [Detecting Anomalous Records in Categorical
Data Sets](https://publications.ri.cmu.edu/detecting-anomalous-records-in-categorical-data-sets).
Our simple bounded supplement is not a reproduction of their method, and the
paper does not support any accuracy claim for these data.

## Next preregistered hypotheses

Before any alternative geometry outcomes, test two continuous versions of
existing front/tail structural relations, using their six recorded words only.
The middle/status field and the complete baseline score remain unchanged.
No raw-value exemplars, reference identities or fitted reference templates.

1. The ordinary silhouette coefficient for the existing three-field front and
   three-field tail partition, averaged over six fields and mapped from [-1,1]
   to [0,1]. Absolute pairwise distance is the metric. This asks whether the
   two existing groups are internally close and mutually separated.
2. A distance contrast: cross-group mean distance divided by the sum of that
   distance and mean within-group distance (all six within-group pairs). This
   tests the same general structural hypothesis with a simpler aggregation.

Equal observations have zero dissimilarity. An all-constant record or missing
observation receives zero supplement, without imputation. Both methods are
invariant to uniform translation and positive scaling of observations, as well
as permutations within each group and exchanging groups. They are not expected
to be invariant to arbitrary nonlinear renaming, unlike the frequency models.

For each formula retain the same amplitudes 1,3,6. These six fixed variants are
selected before evaluation. Use the same population, metrics and advancement
criteria from `protocol.md`. These are further research-set comparisons, not new
independent sessions. Record every failure and per-session regression.
