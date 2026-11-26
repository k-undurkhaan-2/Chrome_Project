# G1-ALPHA-PREP-3-R1 controlled candidate delivery

Status: **READY_G1_ALPHA_PREP_3_R1_CONTROLLED_MANUAL_ACCEPTANCE**.

This status covers the integrated ID1 path using the existing explicitly owned table fixture. It does not mean native qualification, CE-host manual acceptance, production authorization or release readiness. The maintainer retains the final manual acceptance decision.

## Authority and baseline

- Decision: `APPROVE_G1_ALPHA_PREP_3_R1_REMOVE_MANDATORY_COOPERATIVE_INTERFACE`.
- Starting branch: `armedforces.io-v2`; exact starting HEAD: `f1a3cc2132e41c0b334089e340e774fdcf488dda`.
- A dedicated application exporter, operation/readback API or lifecycle API is no longer mandatory. No missing cooperative API is reported as a blocker.
- The architecture remains CE 7.6 + Lua 5.3 + CT. Python is an optional preparation/engineering utility.
- PREP-3, PREP-2, AC5–AC9, G1-N1/N2, PAIR, L01 and L12 remain historical evidence in their original scopes. No retrospective PASS or new accuracy campaign was created.

## Actual integration

The prepared candidate's existing ID1 calls `ce_mvp.lua.start()` in the explicitly latched `ALPHA_CONTROLLED` mode. The fixed controlled constructor uses the existing `tests/fixtures/ce_mvp_mock.lua` table CE/Win32 implementation and public `src/examples/g1_alpha_population.example.lua` data. It does not read private native configuration or accept an application SDK, caller-supplied native API table, custom writer or arbitrary factory.

The existing adapter calls the AC6 explicit-record overload, which uses AC5 full scoring and its existing common-context ranking, comparator, tie, confidence and recommendation contracts. Full completion, counts and exact eligible/selected/ranked identities are checked in the existing scorer contracts and the integration regressions. The integration rejects missing mapped source words rather than turning incomplete input into an ordinary low-scoring result. Original scorer implementations and strict qualification code were not changed.

The core receives the original selected-candidate shape and retains the existing identity, structural, recommendation/admission, prewrite, immediate readback and cleanup checks. Mock writes affect only the owned fixture tables. Full input is never passed into the native constructor: the new controlled constructor creates the fixture internally. The ordinary native constructor and QSG writer gates remain in place. Full supplied-population coverage is not external acquisition coverage; `global_uniqueness_proven` remains false in the controlled mode.

`ALPHA_STOP_ONLY` is a construction policy, not a native operator-config bypass. A first observed invalidity, no candidate, identity/exit failure, operation/readback failure or operator stop terminates the controlled run through existing cleanup. No rescan backoff, fresh selection, reattachment or restart occurs automatically. Existing engineering recovery outside this Alpha mode remains compatible. No validity-detection algorithm was changed.

ID3 remains read-only and unchanged. The integration tests assert that ID1 does not load the ID3 module. The controlled fixture's existing `step` and fault fields are used directly; no launcher, adapter framework, test framework, worker, supervisor or new preparation phase was introduced.

## Signed implementation commits and independent remote verification

Each row was validated, immediately GPG-signed, normally pushed to the authorized existing branch using the local `gh` HTTPS credential helper, and independently read back through `gh api repos/k-undurkhaan-2/Chrome_Project/commits/armedforces.io-v2` before subsequent delivery work.

| Commit | Exact parent | Changed paths verified remotely | Signature |
| --- | --- | --- | --- |
| `8c37b57e22c13f0a9fb91119be81146c2a201400` | `f1a3cc2132e41c0b334089e340e774fdcf488dda` | `README.md`; `docs/g1_alpha_manual_acceptance.md` | verified=true, reason=valid |
| `225218156e3b252789eece3708955b8579d8ead9` | `8c37b57e22c13f0a9fb91119be81146c2a201400` | `src/ce_mvp_core.lua`; `tests/test_h3_a7_ce_mvp.py` | verified=true, reason=valid |
| `d3aadb33aab01f77bd9e45479975b5421188825c` | `225218156e3b252789eece3708955b8579d8ead9` | `src/ce_mvp.CT`; `src/ce_mvp.lua`; `src/ce_mvp_adapter.lua`; `src/ce_mvp_core.lua`; `src/prepare_ce_mvp.py`; `tests/fixtures/ce_mvp_mock.lua`; `tests/test_ce_mvp_readonly.py` | verified=true, reason=valid |

The separate handoff commit contains this report, the completed Chinese operator sheet and the identity manifest. Its exact signed SHA and independent remote verification are supplied in the final delivery response; the immutable candidate source remains `d3aadb33aab01f77bd9e45479975b5421188825c`.

## Validation commands and actual outcomes

Host: Windows 11 x64; Python 3.14.3, Lupa 2.8. Existing tests used genuine Lua 5.3/5.4 as specified by their fixtures; the ID1/CT controlled tests used Lua 5.3. Existing 256 MiB test allocator cap was retained. These are owned synthetic tests, not observations of a real target or a CE-host manual session.

1. Acceptance-scope correction: `git diff --check`, required-decision/gate/AC8/G1-status text checks and historical-link existence check passed before commit `8c37b57`.
2. Stop-only change:

   ```powershell
   & '.venv/Scripts/python.exe' -m pytest -q tests/test_h3_a7_ce_mvp.py -k 'alpha_stop_policy or confirmed_invalidation_rescans or finite_numeric_drift or cleanup_uncertainty_blocks_restart or stop_and_repeated_start' --basetemp=reports/2026-11-26/g1r1-stop-temp
   ```

   **46 passed, 885 deselected, 2.31 s**. This covered first-failure stopping, identity/exit, write/readback failure, cancellation, cleanup, no further activity after 200 fixture ticks, and retained engineering recovery.
3. Initial ID1 smoke returned ERROR because the adapter's module environment lacked `getmetatable`, required by the reused AC6 overload. The needed Lua base functions were added; the actual ID1 smoke then reached MONITORING with COMPLETE / 3 ranked.
4. First selected controlled regressions:

   ```powershell
   & '.venv/Scripts/python.exe' -m pytest -q tests/test_ce_mvp_readonly.py -k controlled --basetemp=reports/2026-11-26/g1r1-integration-temp2
   ```

   **25 passed, 1 failed, 26 deselected, 3.29 s**. The missing-word case exposed a completed low-scoring envelope for incomplete source data. The controlled input boundary now rejects it before scoring. The next run of that complete test file passed **52 tests in 3.11 s**. Additional allocator, restart, mode-latch and packaging checks were then added.
5. Final scoring, ID1/ID3 and QSG compatibility set:

   ```powershell
   & '.venv/Scripts/python.exe' -m pytest -q tests/test_ce_mvp_readonly.py tests/test_offline_full_population.py tests/qualification/test_qsg_integration.py --basetemp=reports/2026-11-26/g1r1-integration-final
   ```

   **199 passed in 26.33 s**. This includes actual CT ID1 execution, forbidden ambient target APIs, full 129-member coverage with unchanged legacy 128 budget, exact membership, ACCEPT/REVIEW/REJECT/EMPTY separation, duplicate/excluded records, corrupt results, cancellation, scoring errors, actual Lua allocator failure, absent input, stale-result prevention, mode locks, original operation gates, failure cleanup and no recovery. The allocator test lowers its local test limit to induce a real memory error and restores the original cap; it does not increase product resources.
6. Final native-interface/loader/core compatibility subset, using existing CE/Win32 doubles only:

   ```powershell
   & '.venv/Scripts/python.exe' -m pytest -q tests/test_h3_a7_ce_mvp.py -k 'portable or actual_loader or loader_is_inert or alpha_stop_policy or config_rejects or confirmed_invalidation_rescans or happy_path_complete or cleanup_uncertainty_blocks_restart or strict_missing_policy or rev1_malformed_or_nonaccept' --basetemp=reports/2026-11-26/g1r1-compat-final
   ```

   **184 passed, 747 deselected, 7.18 s**. Together with the prior command, the final two suites passed **383 tests**. The earlier 46 checks overlap this subset and must not be counted as additional distinct final tests.
7. `git diff --check` passed for the exact implementation paths before signing. Existing native config limits, original scorer files, ID3 module and QSG strict implementation were unchanged.
8. Candidate assembly used the existing `prepare(source_dir, alpha_controlled=True)` function in a new isolated output directory. Each maintained file matched its committed Git blob before copying. All **13 SHA-256 identities** were read back. The actual generated CT's syntax-check blocks, ID1 Start and Stop blocks, package-local loader, scorer, core and fixture were executed in Lua 5.3 with ambient target primitives forbidden. No ID3 invocation was used.

## Actual candidate and package smoke

- Local package: `D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-prep-3-r1-manual\`.
- Actual CT: `src\ce_mvp.local.CT` inside that package.
- CT SHA-256: `2e6d3d5403d9ed5f156d313998ef3ac867b4735b77a67b920d8ac34cad5439a8`.
- [Identity manifest and package validation data](g1-alpha-prep-3-r1-file-identities.json).
- [Chinese operator instructions and independent expected observations](../../docs/g1_alpha_manual_acceptance.md).

The package smoke observed COMPLETE, all supplied/distinct/eligible/selected/fully_scored/ranked counts equal to 3, duplicates/excluded equal to 0, exact identities `0x100128, 0x100328, 0x100528`, Rank-1 46, runner-up -36, ACCEPT/HIGH, one simulated operation with matching `0x42FA0000` readback, zero ambient target calls and zero native scan objects. A mapped=false event stopped with `ALPHA_STOP:MAPPING_CHANGED`, cleanup succeeded, and 200 further fixture ticks with a replacement object caused no additional activity. A separate explicit restart and CT disable produced STOPPED / OPERATOR_STOP with cleanup.

Measured in this single **Lupa package smoke**, advancing ten fixture ticks took **6.012 ms** wall time; Lua allocator usage immediately before/after was **836,073 / 1,554,414 bytes**. These are not CE measurements, process peak memory, a capacity guarantee or an SLA. Fixture 50 ms ticks are simulated time. Actual CE elapsed time, resource usage and UI responsiveness remain **NOT_RUN / UNKNOWN**, for the maintainer to record.

## Retained limitations and handoff

- Only the explicitly owned synthetic full path is integrated and executable here. Native external full acquisition/action is not delivered or authorized; no third-party application or game was accessed.
- Real operation/readback: **UNSUPPORTED / NOT_RUN**. Simulated operation results cannot qualify a real writer, attachment or lifecycle observation.
- `ATTACHMENT_HANDLE_UNVERIFIED`, `QSG_NATIVE_BACKEND_NOT_QUALIFIED`, `NOT_PRODUCTION_AUTHORIZED` and `IMPLEMENTED_PENDING_CE_QUALIFICATION` remain in force. The native strict contract and publishing restrictions were not relaxed.
- Readability and successful access do not establish semantic object identity. Alpha stops on existing observable signals; no automatic reacquisition/recovery or replacement liveness algorithm is provided.
- Full evaluation applies to the supplied finite population. Synchronous scoring is not preemptively cancellable through the CE checkbox; native capacity, hard timeout and responsiveness guarantees remain unestablished. This task did not raise resource limits.
- AC8 remains at least 95% of planned positive pools with completed reconciled coverage, preserving the historical 100/100. Correct Rank-1 with REVIEW is a ranking match and still does not authorize an operation.
- G1 stays **0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**. L01/L12, N0/MIN/LOCAL suspension, historical AC/PAIR records and Generation 2 are unchanged.
- The original modified/untracked worktree files, private configuration and historical packages were excluded from all staging. Runtime logs and generated test directories were not committed. The new local package is an output artifact with committed source identities, not a release publication.
- No tag, Release, PR, new branch, automatic next task or native/production test was created. The maintainer's manual review and separate release decision remain outstanding.
