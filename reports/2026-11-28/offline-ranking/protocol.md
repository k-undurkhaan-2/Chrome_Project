# Offline ranking development protocol

The existing `codex/experimental-offline-ranking` branch started at
`1c183c6d2ad3a920c6ef40407c8928903b2b757f`, verified against HEAD and its
creation reflog before changes. It had no remote branch at the initial check.
The protected local and remote refs were mainline at that same commit,
`codex/temp-offline-discrimination-20261127` at
`49956c900a05f6a6d5958ccafb8e1b8c8c5c6895`, and Native MVP at
`c1a96d715f886828200214e1a958141f116a85d9`. Existing unrelated working files
are preserved. No branch reset, recreation, merge, release or promotion is planned.

All ten sessions D01-D10 from the previous chronological assignment are now
historical development data. Reference membership, computational feasibility
and prediction correctness are separate properties. The independent mapping
remains the membership authority, including for computations rejected by the
unchanged observation checks. Original exports, labels, integrity checks and
historical reports are immutable. Input content hashes and modification times
will be checked before and after the study. Raw identities and records stay local.

The prior contrast candidate improved some midranks but demonstrated only 2/8
computed first choices across the ten planned sessions. Two sessions were
uncomputed because of conflicting observations. Frequency and ordinal-family
variants failed; cohort removal and scalar-penalty interpolation also failed.
These are historical findings, not independent evidence for this round.

## Initial model hypotheses

The existing coarse score may weight useful structural evidence incorrectly.
Test a regularized linear residual model around the baseline, using relative
geometry and existing score contributions. Features may describe missingness,
zero values, word alignment, within-row normalized distances and ordering,
front/tail spans, and baseline structural contributions. Never use absolute
candidate addresses, address ordering, session identifiers, raw reference
templates or absolute observation identities as predictive features.

Fit pairwise score differences between a training reference and its competitors,
with equal total weight per training session and ridge regularization. Training
competitors are selected by baseline score, including every tie at a boundary;
predictions always cover the entire eligible population. Compare regularization
strengths 0.1, 1 and 10, baseline-only contributions, geometry-only residuals,
and their combination. Include the unchanged baseline and prior unit contrast
as comparators. Training labels are supplied only to the fit function; the pure
prediction function accepts features and frozen coefficients only.

Compute leave-one-session-out predictions: a session's label must never enter
the model, feature scaling or fit used to predict that session. Also use nested
leave-one-session-out selection if choosing among fitted variants, so outer
labels do not select their own hyperparameters. All resulting scores are
development diagnostics on repeatedly used historical data, not fresh validation.
If further hypotheses are warranted, record their rationale before evaluation.

## Decision and accounting

Prefer correct unique Top-1 identification. Tied leaders do not identify a
unique reference, and input order cannot resolve a predictive tie. Report
baseline deterministic Top-1 separately from strict unique Top-1, tie intervals,
coverage and incorrect unique leaders. Keep all ten sessions in the planned
denominator; provide computed-only figures with explicit denominators as well.
Report regressions and all tested variants. Do not treat non-reference records
as independently verified negative labels or claim specificity/AUROC.

Retain the existing 256 MiB Lua allocator bound and all original replay checks.
Consistent incomplete exports may use the previously established conditional
frozen-table analysis, with the ordinary rejection preserved. Conflicting
observations remain uncomputed; do not choose, repair or discard conflicting
words to obtain a favorable ranking.

Freeze a justified candidate's code, parameters, feature contract and hashes for
later independent evaluation. If the evidence does not justify an improvement,
document that limitation. No new data collection is required. Every completed
logical change is promptly GPG-signed, normally pushed through the configured
gh HTTPS credential helper, and independently checked through the GitHub API
for its SHA, parent, changed files and verified signature.
