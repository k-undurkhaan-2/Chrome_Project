# Algorithm A offline population scoring

`src/mvp0_offline_scoring.lua` provides `run(records, options, load_module)` for
finite synthetic table records in Lua 5.3/5.4. It reuses the existing
`MVP0FoundList.build_input` and `MVP0.run` pipeline in an isolated table-backed
environment. The scorer, weights, cohort context, final comparator, confidence,
recommendation and ordinary report are unchanged. Product configuration does not
accept `population_mode`; the explicit table-only collector overload below is
the engineering connection to this API.

## Connected read-only collector interface (AC6)

Call `MVP0FoundList.run(options, {records=records, load_module=load_module})`.
This overload of the existing collector interface loads AC5 in an isolated
environment and returns its entire completion envelope unchanged. Unlike the
raw AC5 call, the caller loads the collector and supplies a loader for all three
modules. The interface checks completion status, mode, counts and ordinary result
structure before returning. AC5 retains responsibility for validating options,
records, feature words, selected/ranked identities, ordering and cohort context.
There is no second scorer and no result cache.

The second argument must be a plain table containing only `records` and
`load_module`. The records and options use the AC5 contracts below. The trusted,
caller-owned `load_module(name, env)` must load the named repository module into
the supplied environment; it must not substitute ambient process readers or
actions. Only these three module names are needed. Truth metadata on records is
ignored; truth, live/action settings and unknown options are rejected. An
explicit `population_mode` without the synthetic request is an error before any
collection. Existing single-argument calls without that option retain their
original behavior. Within the synthetic overload, omitted mode and explicit
`bounded` retain AC5 defaults and bounded budget semantics.

Run this example from the repository root using Lua 5.3 or 5.4:

<!-- AC6 example -->
```lua
local collector = assert(loadfile('src/mvp0_foundlist_collector.lua'))()
local function load_module(name, env)
  assert(name == 'mvp0_offline_scoring.lua'
    or name == 'mvp0_candidate_report.lua' or name == 'mvp0_foundlist_collector.lua')
  return assert(loadfile('src/' .. name, 't', env))()
end
local records = {{
  addr=0x100128, mapped=true, protect=4,
  memory={
    [0x100108]=0x10011200, [0x100118]=0x10013800, [0x100120]=0x10042100,
    [0x100128]=0x42C80000, [0x100158]=0x10060000,
    [0x100168]=0x10025600, [0x100170]=0x10028400, [0x100178]=0x10086300,
  },
}}
local completed = collector.run({
  population_mode='full', target_value_pattern=0x42C80000, target_value_float=100.0,
}, {records=records, load_module=load_module})
assert(completed.completed and completed.population_complete)
assert(completed.counts.fully_scored == 1 and completed.counts.ranked == 1)
print(completed.status, completed.counts.fully_scored, completed.counts.ranked)
print(completed.result.report_text)
```

Full mode succeeds only with consistent completed population coverage. An empty
eligible set returns `EMPTY` with the ordinary no-candidate recommendation.
Bounded subset completion remains distinguishable by `population_mode`,
`population_complete` and the counts. Invalid requests raise
`OFFLINE_INVALID_REQUEST`; malformed completion envelopes raise
`OFFLINE_INCOMPLETE_RESULT`. AC5 validation errors and original loader/scoring/
resource errors propagate without a successful return, fallback, replacement
recommendation or stale prior result. Caller-aborted workers remain unsuccessful.

All recommendation fields, including `manual_review_required`, are preserved.
An observed ACCEPT grants no action or automatic execution authority. This
interface has no action port, starts no product loop, and reads only the supplied
synthetic tables. It does not attach to processes or collect real memory.
The caller retains the Lua allocator and existing worker time, sampled memory,
output and host-commit protections described below; this overload creates no
worker or supervisor. The existing runtime and trusted loader are caller-owned.

Connected regression: `.venv/Scripts/python.exe -B -m pytest
tests/test_offline_collector_interface.py tests/test_offline_full_population.py`.
The connected suite reuses the AC5 cases in both supported Lua versions, adds
boundary failure checks, and executes the example above.

## Raw AC5 API and shared contracts

```lua
local offline = assert(loadfile('src/mvp0_offline_scoring.lua'))()
local function load_module(name, env)
  assert(name == 'mvp0_candidate_report.lua' or name == 'mvp0_foundlist_collector.lua')
  return assert(loadfile('src/' .. name, 't', env))()
end
local records = {{
  addr=0x100128, mapped=true, protect=4,
  memory={
    [0x100108]=0x10011200, [0x100118]=0x10013800, [0x100120]=0x10042100,
    [0x100128]=0x42C80000, [0x100158]=0x10060000,
    [0x100168]=0x10025600, [0x100170]=0x10028400, [0x100178]=0x10086300,
  },
}}
local completed = offline.run(records, {
  population_mode='full', target_value_pattern=0x42C80000, target_value_float=100.0,
}, load_module)
assert(completed.completed and completed.population_complete)
print(completed.status, completed.counts.fully_scored, completed.counts.ranked)
print(completed.result.report_text)
```

The numbers and `memory` table are ordinary synthetic fixture data. The module
does not read any process or host memory. Records use the existing offline
fixture shape: a dense array of plain tables with a positive integral `addr`
(at most `2^53-1`), boolean `mapped`, uint32 `protect`, and plain `memory` table
mapping numeric identities to uint32 words. Only mapped records supply lookup
words; missing words remain ordinary missing features. Other record metadata is
ignored. Metatables, sparse arrays,
malformed words, conflicting duplicate identities and conflicting overlapping
words are rejected. Identical duplicates retain source order and are reconciled
by the existing collector. The frozen reference eligibility predicate is
`mapped and protect == 4 and memory[addr] == target_value_pattern`, followed by
the unchanged ordinary exact-pattern filter.

`population_mode` is exactly `bounded` or `full`; omission means `bounded`.
Bounded defaults remain `scan_budget=2000`, `max_candidates=20`; integer ranges
remain 1–65536 and 1–128, with `max_candidates <= scan_budget`, matching existing
validated scan settings. Full mode **forbids both budget fields**, including
zero, false and large values. It derives exact finite capacities internally and
evaluates every distinct eligible record together in one ordinary scoring call.
No absent/invalid budget or large sentinel opts into full evaluation.

`target_value_pattern` is required and must be uint32. Optional
`target_value_float` must be finite; `session_id` must be a string. Optional
`filter_target_match` and `use_prescore_selection` must be true (their defaults).
All other options, including truth labels, probes and live settings, are errors.
The caller's records/options and the existing product defaults are not changed.

A normal return is a completed evaluation. `status` is `COMPLETE` for a nonempty
ranking or `EMPTY` for a legitimate empty/filtered-out population. Check
`population_mode` and `population_complete` separately: a bounded result can be
complete for its selected subset without covering the eligible population.
`population_complete` is established only after verifying every returned final
record, selected identity, rank position, context family size and global order.
The `counts` table reconciles `supplied`, `distinct`, `duplicates`, `eligible`,
`excluded`, `selected`, `fully_scored` and `ranked`. `identities` contains source,
distinct and eligible sequences; selected identities remain in
`collection.candidate_value_addrs`, and ranked identities in `result.ranked`.
`collection`, `filter` and `result` preserve the ordinary evidence. The new
completion envelope is reporting only; empty results retain the ordinary REJECT
recommendation and its rationale.

Failure has **no successful return value**. Invalid inputs raise
`OFFLINE_INVALID_OPTIONS`/`OFFLINE_INVALID_RECORDS`; an incomplete result raises
`OFFLINE_INCOMPLETE_RESULT`. Loader, scoring, ranking and report exceptions
propagate unchanged, including Lupa's `LuaMemoryError`. There is no partial
ranking, replacement REJECT or bounded fallback on error. Callers must retain
the exception/traceback; a worker killed by an external resource guard is an
aborted evaluation, never an empty result. Do not reuse a prior successful
result as the outcome of a failed call.

The caller owns the existing Lua allocator ceiling and process time/memory/output
guards. This API neither raises limits nor creates workers or supervisors.
Use the established offline fixture/worker and monitoring for large populations.
The AC5 validation ceilings (4 GiB Lua, sampled 8 GiB worker, 240 s, 256 MiB output,
512 MiB host available commit) are testing ceilings only, not product defaults.

Targeted regression: `.venv/Scripts/python.exe -B -m pytest
tests/test_offline_full_population.py`. The suite uses existing Lua 5.3/5.4
fixtures, small artificial populations, the original bounded/full reference,
failure doubles and a tiny allocator failure. F2 C3/C4 frozen inputs/complete
outputs supply the separate large regression reference; F3 evidence is reused.
No independent admission qualification, CE qualification, liveness change or
automated-use authorization follows from this offline option.

## G1-S2 registered offline specification (S1-D1)

**Effective scope: offline synthetic evaluation only.** Authority:
`APPROVE_G1_S1_D1_OFFLINE_SPECIFICATION_REGISTRATION`. G1-S2 registers the
approved G1-S1 clauses 1–6 and their offline acceptance correspondence below.
S1-D1 is `REGISTERED_OFFLINE_ONLY`; S1-D2 is
`DEFERRED_NOT_AUTHORIZED`. This amendment does not rename, replace, relax or
pass any native G1 requirement or live L row. It grants no action permission.

The reviewed G1-S1 package remains a historical `PROPOSED_NOT_REGISTERED`
artifact; this subsequent registration does not rewrite it or its receipt.
Its `specification-reconciliation.md` and `completion-receipt.json` are in
`C:/Users/llzz/.codex/visualizations/2026/11/25/01a21376-5b19-7a13-9fcd-b8b9c2513996/g1-s1-specification-reconciliation/`.
The proposal's clauses and "Affected G1 acceptance mapping" are registered here;
its "Resource policy and evidence limits" table and the receipt's source IDs
identify the applicable historical evidence.

### Approved clauses 1–6

1. **Domain and explicit selection.** For offline synthetic evaluation, use the existing AC6 `MVP0FoundList.run(options, {records=records, load_module=load_module})` or raw AC5 `run(records, options, load_module)`. Full evaluation requires explicit `population_mode='full'`; both `scan_budget` and `max_candidates` are forbidden, including zero, false or a large sentinel. Omitted/explicit `bounded` preserves its existing defaults, ranges and selected-subset semantics. Product configuration does not acquire this option. The trusted caller-owned loader and table-only environment remain unchanged; no action capability is added.

2. **Population and scoring completeness.** For the supplied finite synthetic records, reconcile identical duplicates and apply the frozen eligibility predicate `mapped and protect == 4 and memory[addr] == target_value_pattern`, followed by the ordinary exact-pattern filter. Only mapped records provide lookup words. Every distinct eligible identity must receive ordinary feature extraction, complete scoring, cohort/family adjustments and final ranking together in one scoring call, with the existing comparator and tie rules. Independently ranked batch winners are not a global result. Preserve scoring, weights, filtering, confidence, recommendation, manual-review fields and report semantics. Truth remains evaluation-only and cannot influence selection or scoring.

3. **Success and coverage evidence.** Successful full evaluation requires `completed=true`, `population_mode='full'`, `population_complete=true`, consistent ordinary result fields and all of:

   - `supplied = distinct + duplicates`;
   - `distinct = eligible + excluded`;
   - `eligible = selected = fully_scored = ranked`;
   - source/distinct/eligible identity reconciliation, exact selected/ranked membership without omissions or duplicate ranked identities, complete per-record fields, rank positions, cohort sizes and global order.

   Counts alone do not prove coverage. Coverage is relative to the supplied synthetic population; it proves neither completeness of an externally acquired input nor native scan scope, stable target state, process identity or independent safe admission. A bounded call can complete its subset, and can even cover a small entire population, but must remain labelled with its actual mode. No sampled, truncated, interrupted or unverified result may be labelled successful full evaluation.

4. **Empty and failure states.** A fully evaluated empty eligible set is `EMPTY`, retains the ordinary no-candidate REJECT/rationale, and has eligible/selected/scored/ranked counts zero; supplied records may be nonzero if all are excluded. Nonempty completed ranking is `COMPLETE`, even if its ordinary recommendation is REVIEW or REJECT. Missing synthetic feature words retain ordinary missing-feature semantics; they are not automatically a schema error or proof of native unreadability. Malformed records/options, conflicting duplicates/words, incomplete envelopes or resource/loader/scoring/report failures are unsuccessful. Preserve actual `OFFLINE_INVALID_REQUEST`, `OFFLINE_INVALID_OPTIONS`, `OFFLINE_INVALID_RECORDS`, `OFFLINE_INVALID_LOADER` or `OFFLINE_INCOMPLETE_RESULT` as applicable and original exceptions, including `LuaMemoryError`. An externally aborted worker has no successful result. Retain cause/partial diagnostic evidence without returning a partial ranking as success, fabricated REJECT, EMPTY, stale result or bounded fallback. This specifies existing outcomes, not a new API error envelope.

5. **Separate cardinality from resources and authority.** Eligible count above 128 alone is not an offline full-mode rejection criterion. Full evaluation means all eligible records or an explicit unsuccessful outcome; it does not guarantee that every finite input fits available resources. Existing caller-owned allocator, time, sampled-memory, output and host-admission guards stay in force. Exhaustion/interruption cannot be repaired by silently dropping records, suppressing required output or raising limits. An offline ACCEPT is a recorded recommendation only. Preserve all existing qualification, identity, completeness, write-attempt, exact-readback, cancellation, cleanup, retry, liveness and recovery protections.

6. **Revised offline acceptance and evidence reuse.** Accept the existing AC5/AC6 contract evidence for full coverage, bounded compatibility, empty/duplicate/filtered inputs, deterministic order, truth isolation, unchanged recommendations and failure propagation. Preserve AC8's approved empirical Rank-1 threshold **>=95% of all planned positive pools**, requiring every planned positive to complete with reconciled coverage. Correct Rank-1 with REVIEW is a match. Wrong/absent/excluded truth is a miss; invalid/incomplete/aborted/unattempted pools stay in the planned denominator, never count as successes and are not invented observed mismatches. Report completed-only accuracy separately. Ambiguous/negative/empty controls have their own NO_ACCEPT denominator; unexpected ACCEPT is a separate protection finding. AC7 independent admission-positive qualification is not an added prerequisite for this ranking metric. No new 100-pool run, AC7 repetition or new framework is needed for this unchanged contract.

### Offline correspondence to G1 acceptance rows

This correspondence is effective only for the supplied synthetic population.
The original live matrix, [R1 plan](ce_mvp_q1_r1_plan.md), L12 three-case addendum
and [product contract](architecture/h3_a7_ce_mvp_contract.md) retain their native
qualification obligations. NORMAL scoped ACCEPT is not strict QUALIFICATION;
no full-population native adapter is established by this registration.

| Row | Registered offline correspondence | Native obligation/status retained |
| --- | --- | --- |
| L03 | Clauses 1–3 and 6 apply to all eligible synthetic records, including populations above 128. Rank accuracy, ordinary recommendation, and independent admission are separate results. AC5/AC6, AC8, and AC9 provide the existing scoped evidence. | Original complete <=128 candidate set, unchanged threshold, and unique qualified selection requirements remain effective in their native qualification scope. Native input completeness, strict selection, and direct observations are unproved. NOT_RUN/PAUSED. |
| L09 | Above 128 is not itself an offline full-mode failure. Preserve legitimate EMPTY, ordinary REVIEW/REJECT, NO_ACCEPT controls, and unsuccessful error/abort semantics. No action path. AC8/AC9 and existing failure regressions support this mapping. | Original five native negative controls and all no-write requirements remain in effect; historical overflow evidence stays unchanged. Offline controls do not prove native scan/progress, read-failure behavior, no writes, or cleanup. NOT_RUN/PAUSED. |
| L12 | Record the discovered stale example: `scan_budget=129,max_candidates=128` is within today's validated ranges. Existing offline validation still rejects mixed full/count options and invalid bounded budgets. Current synthetic tests use 65537. | Do not replace the live example, amend the invalid-input requirement, or authorize a live input. MISSING, DISABLED, and INVALID remain NOT_RUN/PAUSED; defer live-document reconciliation to a separately approved decision. |

The original matrix and L12 example are recorded in
`docs/codex_tasks/chrome_project_H3-A7-Q1_CE_live_qualification_codex_prompt.md`
(L03/L09) and `docs/codex_tasks/h3_a7_q1_l12_three_case_addendum.md` (L12).
The unchanged [configuration validation](../src/ce_mvp_core.lua) and
[synthetic L12 test](../tests/qualification/test_qsg_acceptance.py) corroborate
the example drift; 65537 is evidence, not an approved replacement live input.
AC5/AC6 evidence includes the existing
[full-population regressions](../tests/test_offline_full_population.py) and
[connected-interface regressions](../tests/test_offline_collector_interface.py).
The G1-S1 receipt resolves the AC8/AC9 historical summaries and receipts below.

### Resource boundary and accepted historical evidence

The G1-S1 proposal's "Resource policy and evidence limits" table remains the
applicable historical offline testing policy: 4 GiB Lua allocator ceiling,
8 GiB worker private-memory threshold sampled every 0.25 s, 240 s per case,
256 MiB uncompressed per-case output, at least 512 MiB available host commit,
serial workers, prior termination checks and the existing disk/admission guards.
These limits remain in force as testing policy; they are not production
settings, hard instantaneous peak guarantees or a native SLA. AC8 exercised
supplied sizes up to 20,000 records; this establishes no unlimited-size or
native-capacity guarantee. Existing native time, write, identity, completeness,
cancellation, cleanup, retry, liveness and recovery protections remain unchanged.

AC8 remains `PASS_ALGORITHM_A_AC8_FINITE_SYNTHETIC_RANKING_ACCURACY` against the
approved **>=95% Rank-1 threshold over all planned positive pools**:
100/100 Rank-1, 100% complete and reconciled positive pools, 742,750 eligible
positive candidates completely scored/ranked, 48 ACCEPT and 52 REVIEW, and
3/3 independent control NO_ACCEPT. Completed-only Rank-1 accuracy is separately
100/100 (100%). Correct REVIEW results count as matches under clause 6.
These observations are limited to the frozen C3-like/C4-like synthetic domain;
shared generators/templates do not prove statistical independence or real-world
accuracy. The controls retain their own denominator and protection result.

AC9 remains `PASS_ALGORITHM_A_AC9_OFFLINE_PERFORMANCE_OPTIMIZED`: 103/103
fixed-case parity and 424 tests passed. This was an offline test-worker
Lua-to-Python result-conversion optimization, not a native acceleration claim.
These are reused historical executions, not new independent observations.
AC2/AC3 FAIL, F1 resource failure, AC7 INDETERMINATE, historical PAIR conclusions,
and all AC8/AC9 evidence and receipts remain unchanged.

### Retained G1 and product state

L01 remains `INDETERMINATE_G1_L01_LAZY_LOAD_QUALIFICATION`. Preserve the observed
eight zero BEFORE/AFTER API counters, STOPPED/`running=false` checks, successful
guard restoration (`installed=false`) and 270-second observation. The four AA
Boolean returns and the unresolved runtime/session evidence remain unconfirmed.
There is no retry, reconstruction or retrospective PASS. L02–L12 remain
NOT_RUN/PAUSED; the G1 aggregate remains
**0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**.

Preserve `IMPLEMENTED_PENDING_CE_QUALIFICATION`,
`ATTACHMENT_HANDLE_UNVERIFIED`, `NOT_PRODUCTION_AUTHORIZED`,
`HISTORICAL_ROOT_CAUSE=INDETERMINATE`, `QSG_NATIVE_BACKEND_NOT_QUALIFIED`,
N0/MIN/LOCAL publishing suspension and Alpha Pre-release BLOCKED. Liveness and
recovery design stays frozen. S1-D2 remains deferred: no native implementation,
full-native specification, replacement of the <=128 qualification rule,
resource-policy revision or live L12 example amendment is authorized.
No Generation 2 work or additional offline test campaign follows from this
registration.
