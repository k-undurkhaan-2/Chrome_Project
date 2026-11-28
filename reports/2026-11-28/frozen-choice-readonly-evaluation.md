# Frozen final ranking in the owned-table evaluation path

Branch: `codex/temp-ce-native-id1-auto`.
Parent: `ce36bc95c92c7b5f77d3dfe6022aef5f80baccc3`.
Disposition: **OWNED_TABLE_EVALUATION_INTEGRATED; NO_APPLICATION_OPERATION_INTERFACE**.

This follow-up connects the existing frozen Lua predictor to the existing
`ce_mvp_readonly.lua` `evaluate(records, options)` / `run_example()` entry.
It supersedes the earlier pure-only availability statement for this read-only
test path. It does not make Native ID1 an authorized model trial or provide an
application operation interface.

## Behavior

Initial eligibility, complete-population screening, baseline scoring and its
integrity checks still run through the unchanged AC6/AC5 modules. The final
test result now uses `mvp0_frozen_choice.lua` for all eligible rows. The frozen
module, feature definitions and coefficients are byte-identical to the parent
after LF normalization. Source/model identity remains
`36eabba2a2cdbd4b26fc5bf09532f9eb51eb9744`; no fitting occurs.

- `outcome.evaluation.baseline_result` preserves the entire original baseline
  result, including its features, component scores, ordering and report.
- `outcome.evaluation.result` is the final frozen-model ranking. Each row has
  `candidate`, `final_score`, `baseline_final_score`, `baseline_rank` and
  `rank_position`. Counts and membership evidence are unchanged.
- `result.leaders` contains all maxima within the frozen `1e-10` tolerance.
  `result.status` is `UNIQUE`, `AMBIGUOUS` or `EMPTY`. `result.best` and
  `outcome.proposed_rank1` exist only for a unique model leader. Baseline order
  resolves exact-score display order only; it cannot create uniqueness.
- The console prints the model ranking and timings. Baseline ACCEPT/REVIEW
  thresholds and confidence labels are not applied to the model's score scale.
  Original baseline reporting remains available in `baseline_result`.

The existing table contract also accepts integral floating-point uint32 words.
The entry converts only their Lua numeric subtype with `math.tointeger` before
calling the frozen feature function; values and missingness are preserved.

## Timing scope

Both fields use the existing host `getTickCount` clock in milliseconds, as
documented in the [official CE Lua API](https://github.com/cheat-engine/cheat-engine/blob/master/Cheat%20Engine/bin/celua.txt).
There is no timer, polling loop, injected clock argument or new configuration.

- `outcome.timing.algorithm_compute_ms`: from immediately before the existing
  full table evaluation through frozen feature extraction, prediction, sorting
  and leader calculation. It includes screening, baseline computation and the
  existing evaluator's internal module loading, validation and baseline report
  construction. It is an elapsed algorithm-stage interval, not isolated CPU time.
- `outcome.timing.total_evaluation_ms`: from the first clock read inside
  `evaluate`, after its version/clock checks, through completed result assembly.
  It includes entry setup and initial module loading in addition to the above.
  It excludes loading the example input before `evaluate`, console rendering
  and printing after return, operator actions and application readback.

Elapsed differences handle a 32-bit tick wrap for evaluations shorter than one
wrap period. A short evaluation may report zero at the host clock's resolution.
The host clock is required; CPU time is not silently substituted. Errors propagate
without a completed result, cached result, partial prediction or success timing.

## Targeted validation

- 27 integration tests passed in Lua 5.3; 29 frozen parity tests passed.
- 75 existing Native mock regressions passed in Lua 5.3/5.4.
- The integration compares every score and the complete leader set against the
  hash-verified frozen Python reference, at the existing `1e-12` absolute score
  tolerance. The original full baseline envelope is compared with the parent
  entry's result, with a deterministic baseline test clock.
- Cases cover a changed winner, exact ambiguity, missing/integral-float words,
  input reversal, ignored truth metadata, duplicate/excluded/empty inputs and
  all 137 eligible rows of a larger finite fixture. No training window is used.
- The changed-winner fixture retains baseline leader `0x100128` (score 46),
  while the frozen result selects `0x100328` (baseline score 41). Thus the model
  replaces the final proposal rather than merely adding diagnostic scores.
- Deterministic clock tests verify both boundaries, zero-duration readings and
  wraparound. Faults during baseline calculation, features, prediction or leader
  calculation produce no completed output. Target-access functions fail on call
  in the test host and remain uncalled.

The pure parity maximum combined score error remains `8.8817841970012523e-16`;
all 86 linear coefficients retain exact binary64 parity. Timing tests verify
measurement placement, not real-world speed. No native application or CE live
session was run, and no full historical suite is claimed.

## Concise manual check

1. From this trial checkout, use the existing environment to run:
   `python -B -m pytest tests/test_frozen_choice_readonly.py tests/test_frozen_choice_lua.py -q`.
   Expect **56 passed**. Verify the frozen identity independently before use.
2. In the existing CE Lua 5.3 console, load the saved read-only entry from this
   checkout and run its existing public artificial example:

   ```lua
   local trial = dofile([[D:\armedforces.io-v2\reports\2026-11-28\native-controlled-trial-worktree\src\ce_mvp_readonly.lua]])
   local outcome = trial.run_example()
   ```

   Expect three eligible/scored rows, model `conditional_choice_linear_ridge_0.1`,
   `prediction_status=UNIQUE`, leader `0x100128`, `action_permitted=false` and both
   timing fields. These identities are table data. No attachment or ID1 activation
   is needed. For already authorized owned test tables, use the same existing
   `trial.evaluate(records, options)` call with `population_mode='full'`.
3. Independently check the expected reference and all returned leaders. Record
   revision/runtime, planned case, eligible count, prediction status, correct /
   incorrect / ambiguous / uncomputed outcome, both timings and their scope.
   Retain unsuccessful and uncomputed cases. Any separate application test value
   change must remain an explicit operator action through that owned application's
   existing dedicated interface; record operation, application state and readback
   separately. This entry provides no such operation interface. A successful
   readback alone is not identification correctness or a 95% success-rate claim.

Only the read-only entry, its focused integration tests and this report change.
The Native runner, CT, builder, adapters, core, frozen predictor, datasets and
research/mainline branches remain unchanged. No new interface, automatic memory
modification capability, merge, PR, tag or release is introduced.

No new version tag recommended: the result is an experimental read-only test
evaluation path with manual application validation still outstanding.
