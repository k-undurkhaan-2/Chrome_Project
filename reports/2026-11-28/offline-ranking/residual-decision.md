# Residual linear model decision and next hypothesis

Reject all nine new residual configurations as replacement candidates. Across
eight computable historical sessions, components-only models produced 1/8
correct unique Top-1 choices, and geometry/combined models produced 2/8.
The prior contrast comparator also produced 2/8, with better reference
midranks than every fitted residual variant. Nested selection chose contrast
for every outer session and reproduced its 2/8 outcome. No genuine Top-1 gain
over that prior candidate was demonstrated. Ten sessions remain planned and
reference-valid; D07/D10 remain uncomputed, not invalid or proven errors.

The baseline's strict unique Top-1 is 1/8, distinct from its historical
deterministic Top-1 of 2/8 (one success depends on a tie-break). This study
does not credit that tie-break as identification. The full outcomes and
per-session regressions are in `residual-results.json`.

Ten regression tests passed, including an outer-label mutation check:
changing an outer session's label leaves its trained model and nested choice
unchanged, while its reported correctness can change. No test label enters
prediction or that session's training/configuration selection.

## Next hypothesis, registered before its outcomes

Linear preference directions may be inadequate when useful reference features
are concentrated around an interior range. Test a diagonal moment-based
discriminant using the same fixed, identity-free geometry features. Estimate
positive means/variances from training references, and competing-record
means/variances from baseline competitors within the same 12-point window.
Weight each training session equally. Competitors are choice alternatives,
not independently verified negative labels.

Compare a shared diagonal variance (linear discriminant) with separate
variances shrunk halfway toward the shared variance (quadratic discriminant).
Use a fixed variance floor of 0.01 on the bounded features and average the
log-density difference over the nonconstant training features. Compare residual
amplitudes 0.25, 1 and 4 around baseline/8: six finite alternatives. Only
aggregate moment coefficients are retained, never reference identities,
raw observations or individual reference templates. Preserve full-population
prediction, outer-session exclusion, nested selection, strict tie accounting,
and all original input checks. Report every alternative and regression.
