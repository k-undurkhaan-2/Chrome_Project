# Frozen choice model: Lua 5.3 trial preparation

Disposition: **PURE_MODEL_PARITY_ESTABLISHED; APPLICATION_TRIAL_UNAVAILABLE**.
The pure predictor is available for finite, explicitly authorized test tables.
No native application trial was run or made available by this change.

## Identity and scope

- Trial branch: `codex/temp-ce-native-id1-auto`, starting at
  `c1a96d715f886828200214e1a958141f116a85d9`.
- Frozen candidate: `conditional_choice_linear_ridge_0.1`, source/model commit
  `36eabba2a2cdbd4b26fc5bf09532f9eb51eb9744`.
- Research handoff: `d377c637edb915b7dcf675c2794517957c5fbea1`.
- Frozen model SHA-256: `b8ff942bca7aaac2160d54b69c5999b259ba7b974aebbf057f792ceadb25ed50`.
- Handoff freeze-manifest SHA-256:
  `546ddb8fe8db310039939fbd593f9fb72727dd15ef119f7eb23311ef91f2f596`.

All 23 canonical UTF-8/LF digests in the handoff's `candidate-freeze.json`
matched the frozen Git objects before implementation. The local and remote
trial, research and mainline references matched the requested identities.
Mainline was `1c183c6d2ad3a920c6ef40407c8928903b2b757f`.

Only `src/mvp0_frozen_choice.lua`, its focused pytest test, and this report are
added. The original Native MVP, eligibility, collector, baseline scorer,
offline branch, datasets and evaluation evidence are unchanged. There is no
training, new model selection, heuristic exception, integration, adapter,
configuration, GUI, CLI, telemetry, or additional qualification system.

## Pure prediction contract

The Lua module exposes `features(words, components)`, `predict(scores, rows)`
and `leaders(scores)`. The seven observation slots are `f08, f18, f20, f58,
f68, f70, f78`; Lua `nil` represents missingness, including trailing slots.
Present observations are Lua integers in `[0, 2^32)`. Components retain the
13-column `mvp0_residual_rank.COMPONENTS` order. All 86 feature columns retain
the frozen order and definitions. Inputs are plain tables; dense score and
feature arrays must be finite and aligned.

The private linear coefficients are the exact frozen binary64 values. Every
frozen quadratic coefficient is zero. Prediction computes
`baseline_score / 8 + sum(linear[j] * feature[j])`, using compensated summation.
It accepts no model, reference label, process identity, address, or action
callback. It has no process, file, scan, timer, write, or fitting operations.

The caller must supply all eligible rows from a complete existing baseline
evaluation. The training-only 12-point competitor window is never applied to
prediction. `leaders` returns **all** maxima within the unchanged absolute
`1e-10` tie tolerance, using one-based Lua indices. Multiple leaders remain
ambiguous; identity ordering cannot establish correctness. Invalid/empty
prediction input raises an error, with no partial or cached result.

## Numerical evidence

Environment: Windows x64, Python 3.14.3, Lupa 2.8, **Lua 5.3**, eight-byte Lua
numbers, unchanged 256 MiB Lua allocator limit. This validates the embedded
Lua 5.3 runtime, not a live CE host or application session.

The test loads the immutable Python feature, choice and moment definitions
and model directly from Git, verifies their frozen hashes, and calls only
feature extraction, prediction and leaders. It never fits. The Lua predictor
runs with only arithmetic/table primitives available and global writes denied.

| Check | Result |
| --- | --- |
| 86 coefficient unit vectors | Exact binary64 equality; maximum score error 0 |
| 262 finite word/component rows, including all 128 missingness masks, zero/constant and uint32 boundaries | Maximum feature error `1.1102230246251565e-16` |
| Same feature rows scored in Python and Lua | Maximum score arithmetic error 0 |
| Lua features plus Lua prediction versus Python reference | Maximum combined score error `8.8817841970012523e-16` |
| Existing table fixture: 37 weak / 37 unique / 37 ambiguous candidates | All 111 eligible rows scored; maximum combined score error 0; 37 / 1 / 2 leaders respectively |
| Exact/near ties, adjacent binary64 values at the tie boundary, population reversal, rows below the training window | Reference leader sets and complete output membership preserved |
| Focused tests | 29 passed |
| Existing `test_ce_mvp_native.py` mock regressions, Lua 5.3/5.4 | 75 passed |

The preselected arithmetic acceptance tolerance is **absolute error <= 1e-12**
for each feature and score in these finite fixtures; no relative allowance.
Leader index sets must agree exactly after converting Lua's one-based indices.
The arithmetic tolerance never widens the model's tie tolerance. This is finite
numerical evidence, not a guarantee for every possible floating-point input,
identification accuracy, native timing, or production stability.

The existing Lua fixture is reused directly because its historical Python
wrapper imports `REQUIRED_FILES`, which this branch's builder no longer exports.
That unrelated wrapper is unchanged. No full historical suite is claimed.

## Application interface limitation

`src/ce_mvp.lua` takes a configured PID, assigns the ranked address and
immediately calls `write_value(true)` / `writeFloat`, then monitors and rewrites
the value. Its ID1 path cannot isolate prediction from arbitrary-process writes.
The model is not loaded by that module, its CT, or its builder.

`src/ce_mvp_readonly.lua` evaluates supplied synthetic tables and explicitly
reports `UNSUPPORTED_NO_COOPERATIVE_OPERATION_INTERFACE`. The historical
`new_controlled` seam uses mock tables, not an owned application's interface.
`tests/ce_mvp_disposable_target.py` has existing local stdin commands such as
`status` and `value_drift`, but no existing path supplies its complete baseline
population to this model or consumes predictions through that interface.
The native smoke driver still exercises the automatic CE writer.

Therefore no existing end-to-end application path satisfies this trial's
boundary. Preparation stops at pure parity as requested. Do not use Native ID1
or the native smoke driver as the model trial. No application is launched and
no interface is added to bridge the gap.

## Concise maintainer checks

1. Use this trial revision with its Git history, the existing Python environment,
   pytest and Lupa's `lua53` runtime. Independently verify the frozen commit and
   model digest above. From the trial checkout run:
   `python -B -m pytest tests/test_frozen_choice_lua.py -q -s`.
   Expect 29 passes and the numerical limits shown above. This is an offline
   manual rerun, with no target attachment or application value modification.
2. For a hand-checked pure-model example in an existing Lua 5.3 test console,
   load only the module and evaluate the finite tables below. Expected scores
   are exactly `2, 2, 1` and leaders are `1, 2` (ambiguous). Changing the second
   baseline to `24` gives `2, 3, 1`, with sole leader `2`.

   ```lua
   local model = dofile('src/mvp0_frozen_choice.lua')
   local components = {}
   for i = 1, 13 do components[i] = 0.0 end
   local row = model.features({}, components) -- seven missing words
   local scores = model.predict({16.0, 16.0, 8.0}, {row, row, row})
   print(table.concat(scores, ', '))
   print(table.concat(model.leaders(scores), ', '))
   ```

3. Application testing remains **not available**. Before any later manual
   application trial, an explicitly authorized operator-owned application and
   an already existing dedicated interface must support it. Only the operator
   may change its designated test value through that interface. Independently
   establish the expected reference, preserve predictions, then separately
   observe correctness, manual operation, application state, numeric readback
   and elapsed time. A successful readback alone is not correct identification.

Return concise fields in the existing notes: revision/runtime, planned case,
computed/uncomputed/error status, full candidate count, all leader indices,
independent expected reference, correct/incorrect/ambiguous/unknown result,
manual operation and application state, before/after/readback value, elapsed
time and its measurement scope. Use `not run` for application fields in this
delivery. Retain unsuccessful, ambiguous and uncomputed cases in the planned
accounting. A small manual series cannot establish 95% population success.

No new version tag recommended. This is temporary experimental preparation,
with no mainline merge, PR, tag, release or production promotion.
