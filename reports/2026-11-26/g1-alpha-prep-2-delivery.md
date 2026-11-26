# G1-ALPHA-PREP-2 delivery record

> Historical evidence only; not current operating instructions. Original recorded values and authority are unchanged. [Immutable original](https://github.com/k-undurkhaan-2/Chrome_Project/blob/3a8fa0876fcb0e972af6e657693948207484ec86/reports/2026-11-26/g1-alpha-prep-2-delivery.md). Current product guidance: [English Quickstart](../../docs/ce_mvp_quickstart.md).

Status: **READY_G1_ALPHA_PREP_2_CE_CT_READONLY_MANUAL_ACCEPTANCE**.
This is the implemented, scoped read-only CT/Lua candidate and its manual
acceptance handoff. CE-host observation remains NOT_RUN. It is not overall Alpha
acceptance, native action qualification, or release approval.

## Authority and signed implementation

- Authority: `APPROVE_G1_ALPHA_PREP_2_CE_CT_HOSTED_SCORING`.
- Existing branch: `armedforces.io-v2`; repository: `k-undurkhaan-2/Chrome_Project`.
- Confirmed baseline: `f67c2b1ab619b4a03fa6e8ce055ea4a3fe3b5b5b`, parent
  `bbc92001814e118206852eb65399a28d2673f617`. Local and remote baseline matched;
  GPG verification succeeded, including the recent PREP-1 parent chain.
- Implementation: [`b86c226e2b0b90f3da2ebf79fcafc1f595c996c1`](https://github.com/k-undurkhaan-2/Chrome_Project/commit/b86c226e2b0b90f3da2ebf79fcafc1f595c996c1),
  `feat(mvp0): integrate read-only full scoring into CE table`.
- Its direct parent is the approved baseline. Local GPG reported a good signature
  from key `86D51BCDBC946CF1389969D530479D840D9D562B`. The verified change was
  immediately committed and pushed non-force over HTTPS using the local gh
  credential helper. Independent GitHub API reads returned the exact SHA,
  expected parent, branch HEAD, `verified=true` and `reason=valid`.
- This delivery documentation is a separate coherent change. Its signed commit
  and independent remote verification are recorded in the final task completion
  record; no self-referential commit identity is embedded here.

## Implementation and preserved behavior

The maintained CT adds record 3, **G1 Full population - READ ONLY synthetic
example (check once; uncheck is inert)**. The existing preparation script binds
it to the new sibling `ce_mvp_readonly.lua`; records 1 and 2 retain their original
scripts. The new module exposes `evaluate(records, options)` and `run_example()`.
It supplies a fixed sibling-module loader to the existing AC6 table overload,
with no ambient CE, file, process or action capabilities in scoring environments.

The entry requires Lua 5.3 and explicit full mode. AC5 still forbids count-budget
fields, reconciles exact identities, performs complete ordinary feature/scoring/
cohort/ranking work in one common population and preserves the normal report.
The complete AC6 envelope is returned unchanged at `outcome.evaluation`.
Only completed, nonempty full evaluations receive a Rank-1 proposal. Empty
populations retain EMPTY and ordinary REJECT. Recommendations grant no authority.

Import, CT load, syntax checking and new-record disable are inert. Deliberate
enable runs one synchronous evaluation of the public example. BEGIN separates
invocations; only a successful evaluation and rendering emits the final COMPLETE
marker. Errors, cancellation signals, corrupt/incomplete evidence and allocator
failure propagate without a success result, stale result cache, retry, fallback,
automatic recovery or fabricated REJECT/EMPTY.

The runtime bytes of `ce_mvp.lua`, `ce_mvp_core.lua`, `ce_mvp_adapter.lua`,
`mvp0_foundlist_collector.lua`, `mvp0_candidate_report.lua` and
`run_alpha_candidate.py` are unchanged relative to baseline. The sole AC5 edit
corrects its now-obsolete opening comment. No scoring, eligibility, comparison,
recommendation, native config, bounded interface, execution/qualification gate,
liveness or recovery policy changed. Existing source/docs/tests/private files
outside this task were hash-checked for preservation; the original generated
`src/ce_mvp.local.CT` was also preserved.

## Verification actually performed

Windows x64, CPython 3.14.3, pytest 9.1.0, Lupa 2.8; existing Lua 5.3/5.4 test
runtimes. The new hosted evaluation runs on real Lua 5.3. A real Lua 5.4 check
confirms rejection before module/file acquisition; inert import remains valid.
The existing synthetic fixture retains its 256 MiB Lua allocator ceiling.

Targeted command (a new short local `--basetemp` was supplied):

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/test_ce_mvp_readonly.py tests/test_h3_a7_ce_mvp.py -k 'readonly or portable or table_has_no_open_time or loader_is_inert or actual_loader_and_ct_start_stop' -q
```

**66 passed, 871 deselected, 4.56 seconds** in the final targeted run. These cover:

- Real Lua compilation, inert import/load/syntaxcheck/disable, exact prepared
  routing and missing/unprepared files; private config is not loaded.
- Parity with the original ordinary result for ACCEPT, REVIEW and REJECT,
  including order, scores, cohort adjustments, review flags and report; unchanged
  input and truth isolation.
- Exact duplicate/excluded/empty membership and count reconciliation. Equal
  ranked counts with replaced identity membership fail.
- Explicit full mode, prohibited budgets, truth/action/live options, incomplete
  completion evidence and corrupt score/feature evidence.
- Success followed by failure without stale output, preserved non-string
  cancellation cause, injected resource/cancellation errors, and an actual tiny
  Lua allocator exhaustion that propagates `LuaMemoryError`.
- No native reads, attachment, writes, timers, adapters or product loop on the new
  path. Existing portable preparation and native entry wiring were checked only
  with the maintained synthetic doubles; their existing restrictions remain.

The newly generated package was also exercised once in fresh Lupa Lua 5.3 with
fail-on-call native stubs: syntaxcheck emitted nothing; one deliberate enable
completed the three-record example with exact counts/identities, Rank-1
`0x100128`, score 46, ACCEPT and `manual_review_required=false`. The observed
single-call elapsed time was about 0.064 seconds; it is an offline local
observation, not a CE latency guarantee. No Python auxiliary-launcher run was
repeated. Documentation examples were checked separately with the same public
package and offline Lua facilities.

No CE process was launched or operated. No target was attached, scanned or
modified. Actual AA Boolean values, CE rendering/host behavior, operator
cancellation and native qualification were **NOT_RUN**. No AC8, F2/F3, AC9,
G1-N1/N2, PAIR, L01 or full G1 matrix was repeated. No testing framework was added.

## Delivered file identities

Maintained changes:

- Added `src/ce_mvp_readonly.lua`.
- Added `src/examples/g1_alpha_population.example.lua` (parity with the existing
  public JSON fixture).
- Modified `src/ce_mvp.CT` and `src/prepare_ce_mvp.py` for the actual new entry.
- Modified the opening comment only in `src/mvp0_offline_scoring.lua`.
- Added `tests/test_ce_mvp_readonly.py`; adjusted maintained fixture/preparation
  helpers and assertions in `tests/test_h3_a7_ce_mvp.py`.
- Updated `docs/algorithm_a_offline_scoring.md` and the existing Chinese
  `docs/g1_alpha_manual_acceptance.md`.
- Added this delivery record.

The generated public manual package is local, not committed. Its exact entry is
`D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-prep-2-manual\src\ce_mvp.local.CT`.
Its `file-identities.json` and ignored `offline-package-smoke.log` are in the
parent directory. No private settings, raw target inputs or runtime logs are
committed. These SHA-256 values identify the actual prepared bytes on this host:

| File relative to the package `src/` | SHA-256 |
| --- | --- |
| `ce_mvp.CT` | `b4dff061b5828a24452dbf0e9905de162f13c8a0285795950a43f2589ece3de0` |
| `ce_mvp.local.CT` | `c7d93bd95b6830d59f279b5db164593cc645348ce7283d484d3adfb93f94da4a` |
| `ce_mvp.lua` | `dd4e66b4437f5aa93f9b32b4f822aa18c3321dee235f93fba74436b56dba67dd` |
| `ce_mvp_adapter.lua` | `cbcde01443fe82d4fcfc7ba70bb03c3727ebede5942a4f1d6493fbcb257649c9` |
| `ce_mvp_core.lua` | `aee32e3ac598c3d1fed73001b657b4976d088157c79b11623d1933a2f22f8f0f` |
| `ce_mvp_readonly.lua` | `37cdc21c4474dc4f9d9c855eb873f6a593d7d35065eb7195fbdda63a010de625` |
| `examples/g1_alpha_population.example.lua` | `73713925da9b0cc484eb5fcfed79a12b72e2f8656f5b9e0c77068c0350b12e02` |
| `mvp0_candidate_report.lua` | `2fa9d93ba34ff140aead6e87c1d59a5e149720d894bb0f7bd14267ab10182694` |
| `mvp0_foundlist_collector.lua` | `b0b56f2e5a8fd0de1b8aaef774f8d69f1777682055ff8eace7c041c1da110d14` |
| `mvp0_offline_scoring.lua` | `4e3677c62b5cbe3a2ee9b827f6f76cece688e8fdda870315b773eb8f81c55f50` |
| `prepare_ce_mvp.py` | `45b9256d21912ebde39cadd1b483ad46799a6d138dbd192f846256af4cbde2b5` |

The CT embeds absolute installation paths; relocation requires the maintained
preparer and produces a different CT hash. Git checkout line-ending conversion
can also change local byte hashes. The signed commit identifies maintained source.

## Manual handoff and remaining limitations

Follow the [Chinese operation sheet](https://github.com/k-undurkhaan-2/Chrome_Project/blob/3a8fa0876fcb0e972af6e657693948207484ec86/docs/g1_alpha_manual_acceptance.md).
Use a fresh dedicated CE 7.6 / Lua 5.3 session with no target. Open the exact
prepared CT and invoke only record 3. Record file identities, actual runtime,
current-invocation completion fields, counts and membership, proposal, ordinary
recommendation/review flag, errors or NOT_RUN observations. Native Start and other
action controls are outside this acceptance. The sheet includes small public
empty/invalid-budget examples and stop conditions; all CE expectations are
labelled as expectations.

Action/readback and application identity/exit/lifecycle interfaces remain
UNSUPPORTED. There is no application exporter or semantic object-validity proof.
File accessibility and read-only rank success do not establish semantic validity.
The new entry has no preemptive cancel control, worker, PID monitor, hard timeout,
CE allocator ceiling, host-memory supervisor or established CE size/latency SLA.
An in-flight synchronous call must finish or fail; unchecking is not a cancel
mechanism. Resource failure is unsuccessful, with no retry or bounded fallback.

The 256 MiB small offline fixture is not an 18,498–20,000-record capacity claim;
F1 demonstrated failure at that limit in the tested worker. The historical
AC8/AC9 4 GiB Lua / sampled 8 GiB worker and other resource guards remain offline
test limits, not CE guarantees. The auxiliary Python launcher retains its own
8 MiB input, 256 MiB Lua, 256 MiB output and 240-second cooperative deadline.
No limit was silently raised or population truncated.

Preserve all historic AC and PAIR conclusions. AC8 remains 100/100 in its limited
synthetic domain; AC9 remains an offline worker optimization. Native L03/L09/L12
obligations and the qualification block are unchanged. G1 remains **0 PASS /
0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**; L01 is not retrospectively passed and
L02–L12 remain paused. Preserve `IMPLEMENTED_PENDING_CE_QUALIFICATION`,
`ATTACHMENT_HANDLE_UNVERIFIED`, `NOT_PRODUCTION_AUTHORIZED`,
`QSG_NATIVE_BACKEND_NOT_QUALIFIED`, `HISTORICAL_ROOT_CAUSE=INDETERMINATE`,
N0/MIN/LOCAL publishing suspension and Alpha Pre-release BLOCKED. Generation 2
remains separate. The maintainer decides scoped acceptance from actual results;
future release is a separate decision and no later phase is launched.

**No new version tag recommended**: scoped manual acceptance and native
qualification remain distinct. No tag, release, branch or PR was created.
