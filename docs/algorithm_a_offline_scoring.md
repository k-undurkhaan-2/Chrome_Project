# Algorithm A offline population scoring

`src/mvp0_offline_scoring.lua` provides `run(records, options, load_module)` for
finite table records in Lua 5.3/5.4. It reuses the existing
`MVP0FoundList.build_input` and `MVP0.run` pipeline in an isolated table-backed
environment. The scorer, weights, cohort context, final comparator, confidence,
recommendation and ordinary report are unchanged. Use only artificial data or
explicitly owned, authorized research inputs in the documented record format.
The API reads supplied tables; it does not acquire data from a live process.

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
The caller retains its Lua allocator and host resource protections; this overload
creates no worker or supervisor. The runtime and trusted loader are caller-owned.

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
The caller's records/options and the existing bounded defaults are not changed.

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
`collection`, `filter` and `result` preserve the ordinary evidence. The
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

The caller owns the Lua allocator ceiling and any process time, memory and output
limits. This API neither raises limits nor creates workers or supervisors. The
regression fixture uses the existing 256 MiB Lua allocator limit; historical
large-worker limits are evidence about those runs, not an available service or
capacity guarantee.

Targeted regression: `python -m pytest -q tests/test_offline_full_population.py
tests/test_offline_collector_interface.py`. The suites use Lua 5.3/5.4,
small artificial populations, the original bounded/full reference, failure
doubles and a tiny allocator failure. They grant no native qualification or
automated-use authorization.

## Historical evidence and decisions

The following are preserved finite-domain synthetic observations, not current
product qualification or evidence of real-environment accuracy and performance.

AC8 remains `PASS_ALGORITHM_A_AC8_FINITE_SYNTHETIC_RANKING_ACCURACY` against the
approved **>=95% Rank-1 threshold over all planned positive pools**:
100/100 Rank-1, 100% complete and reconciled positive pools, 742,750 eligible
positive candidates completely scored/ranked, 48 ACCEPT and 52 REVIEW, and
3/3 independent control NO_ACCEPT. Completed-only Rank-1 accuracy is separately
100/100 (100%). Correct REVIEW results count as matches under that historical specification.
These observations are limited to the frozen C3-like/C4-like synthetic domain;
shared generators/templates do not prove statistical independence or real-world
accuracy. The controls retain their own denominator and protection result.

AC9 remains `PASS_ALGORITHM_A_AC9_OFFLINE_PERFORMANCE_OPTIMIZED`: 103/103
fixed-case parity and 424 tests passed. This was an offline test-worker
Lua-to-Python result-conversion optimization, not a native acceleration claim.
These are reused historical executions, not new independent observations.
AC2/AC3 FAIL, F1 resource failure, AC7 INDETERMINATE, historical PAIR conclusions,
and all AC8/AC9 evidence and receipts remain unchanged.

The [original offline specifications and decisions](https://github.com/k-undurkhaan-2/Chrome_Project/blob/8755ce4b8ad89b3d3a3f4cdb80652ddbea879a50/docs/algorithm_a_offline_scoring.md#g1-s2-registered-offline-specification-s1-d1)
preserve the approved scope, denominators, historical resource ceilings, G1-S2
registration and G1-S3 corrections. The [historical CE MVP contract](https://github.com/k-undurkhaan-2/Chrome_Project/blob/8755ce4b8ad89b3d3a3f4cdb80652ddbea879a50/docs/architecture/h3_a7_ce_mvp_contract.md),
[qualification records](https://github.com/k-undurkhaan-2/Chrome_Project/tree/8755ce4b8ad89b3d3a3f4cdb80652ddbea879a50/docs/qualification)
and [Alpha observations and receipts](https://github.com/k-undurkhaan-2/Chrome_Project/tree/8755ce4b8ad89b3d3a3f4cdb80652ddbea879a50/reports/2026-11-26)
remain in the signed historical tree, with their original PASS/FAIL and unresolved
outcomes. These links are historical evidence, not current operating instructions.
The Alpha delivery effort is discontinued; further research and independent
evaluation remain maintainer decisions.
