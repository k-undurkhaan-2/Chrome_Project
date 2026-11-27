# Moment model decision and final model-family hypothesis

The fixed shrunk-variance, unit-amplitude discriminant achieved 4/8 correct
unique Top-1 choices in historical leave-one-session-out development. It
correctly identified D01/D04/D05/D06, versus D04/D05 for the prior contrast.
Its remaining reference ranks were D02=2, D03=3, D08=3 and D09=3. There are
still ten planned, membership-valid sessions and two uncomputed sessions.

This is a promising development result, not reliable generalization evidence:
the nested selector achieved only 2/8, and other amplitudes achieved 3/8.
Keep the unit-amplitude quadratic model as a provisional candidate while
retaining all six outcomes in `moment-results.json`. The model has four wrong
unique leaders on the eight computations; it is not ready for promotion.

Thirteen mathematical, invariance and exclusion tests passed. The quadratic
test separates an interior feature concentration that the linear discriminant
cannot distinguish. Outer-label changes leave moment models and nested choices
unchanged. Eight references have distinct complete feature vectors; therefore
these failures do not establish an information-theoretic impossibility.

## Next hypothesis, registered before its outcomes

Equal averaging over competitors may underweight the few highest-scoring
alternatives that determine Top-1. Test a regularized conditional softmax
choice loss over each training session's existing 12-point baseline window,
always including its training reference. Weight sessions equally. Continue
to predict every eligible candidate in the full population.

Compare linear geometry features and geometry plus bounded quadratic terms
`4*x*(1-x)`. Compare ridge strengths 0.1, 1 and 10: six alternatives. Retain
baseline/8 as a fixed offset. Use deterministic full-batch gradients with
backtracking and a convergence check, never sample identities, addresses or
order-dependent negative sampling. Report all six outer and nested outcomes.
This loss addresses first-choice competition directly rather than fitting
an arbitrary pairwise target margin. Selection remains development-only.

After this family, examine the strongest fixed candidate's leave-two-session-
out stability, training-fit versus excluded-session performance, runtime and
invariance. Freeze the best justified candidate or report that no convincing
improvement was demonstrated. No new data collection or live operation is part
of this work.
