# Continuous geometry: partial improvement, further research

All six fixed geometry variants completed the same five populations. Every
variant gave ranks [2,2,3,1,1], unique highest 2/5 (baseline 1/5), Top-1 2/5
(unchanged), Top-3 5/5 and mean midrank 1.8 (baseline 2.1). The reference became
uniquely highest in D05. D03 deterministic rank changed from 2 to 3; its
midrank remained 3. No score ties were credited as unique discrimination.
The session-average reference-versus-unlabeled separation improved slightly.

Full results are in `geometry-research.json`, including every variant and
per-session regression. This partial result does not establish improved Top-1
or generalization. Neither validation nor held-out predictions were inspected.

The silhouette definition is from [Rousseeuw (1987)](https://doi.org/10.1016/0377-0427(87)90125-7).
It measures within/between-group separation, not semantic identity. Its use
here is a new empirical ranking hypothesis. The contrast alternative is our
simpler ratio of the same distances. All amplitudes gave identical reference
outcomes; retain amplitude 1 as the conservative geometry comparator.

## Next preregistered hypothesis: ordinal refinement of clone summaries

The current family summary keeps qualitative proximity but loses direction
and detailed order. Test augmenting the existing clone-family key with the
ordinal pattern of all seven structural observations: the signs of all 21
pairwise differences. Missing values remain explicit categories. This retains
more relational information without raw values or candidate identities, and
is invariant to any common strictly increasing relabeling of observations.

Recount the resulting families across the unchanged entire eligible pool.
Apply the original clone-penalty formula, thresholds and surcharge conditions
to the refined count, leaving the mirror contribution and every other baseline
term unchanged. Verify the copied formula against every original clone
penalty before testing it. This refines, rather than abolishes, cohort evidence.

Test exactly three alternatives: ordinal clone refinement alone, plus the
already evaluated unit-amplitude silhouette, and plus unit-amplitude contrast.
No threshold search, raw-value templates or record-specific exceptions. These
three hypotheses are fixed before their outcomes. The same five-session
accounting and advancement metrics apply. If refinement destroys useful
cohort discrimination or Top-3 coverage, reject it and retain the geometry
candidate only as a partial, explicitly limited result.
