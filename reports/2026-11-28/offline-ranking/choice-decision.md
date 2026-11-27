# Conditional choice model selection

Select the linear conditional-choice residual with ridge 0.1 for final
stability assessment and freezing. Its leave-one-session-out development
result is 5/8 correct unique Top-1, with reference ranks
`[1, 2, 2, 1, 1, 1, 3, 1]` for D01/D02/D03/D04/D05/D06/D08/D09.
All 48 fitted outer choice models met the stated gradient convergence check.

The quadratic variant at ridge 0.1 also scored 5/8, so retain the simpler
linear representation. This decision prioritizes unique first choices; it
does not count a midrank improvement as success. Other choice configurations
produced 2/8 to 4/8. The choice family's nested selection scored 4/8, choosing
an unsuccessful configuration for D09. The full six-variant evidence, including
that selection failure and all wrong leaders, is in `choice-results.json`.

Relative to the previous contrast candidate, the selected fixed specification
gains D01/D06/D09 without losing D04/D05 in these leave-one-session-out runs.
D02/D03/D08 remain incorrectly identified. D07/D10 remain membership-valid
but uncomputed due to original observation conflicts. Thus the planned-ten
accounting is five demonstrated successes, three demonstrated errors and two
unknown computations; the computed-only development fraction is 5/8.

These are model-selection results on reused historical data, not independent
validation. Neither the selected 5/8 nor nested 4/8 demonstrates reliable
deployment accuracy. The final fixed coefficients will be fitted only after
this selection, using all eight computable development sessions. Their fit
on these same sessions must be labeled resubstitution, separately from the
excluded-session results. Leave-two-session-out stability must retain its
eight-session denominator: 56 correlated predictions are not 56 new samples.

The previous provisional moment candidate's leave-two-out check produced
27/56 correct predictions across 28 omitted pairs, with per-session success
counts `[7, 0, 0, 7, 6, 7, 0, 0]` out of seven. This result is preserved in
`moment-stability.json`, not silently discarded after choosing another model.

596 tests passed across the new mathematical/exclusion checks and existing
Lua 5.3/5.4 full-population, collector-interface and manual-export contracts.
No baseline scoring or integrity implementation was modified.
