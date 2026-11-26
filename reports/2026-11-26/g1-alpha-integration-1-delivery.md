# G1-ALPHA-INTEGRATION-1 standard ID1 delivery and verification receipt

Status: **READY_G1_ALPHA_INTEGRATION_1_CONTROLLED_MANUAL_ACCEPTANCE**.

Authority: `APPROVE_G1_ALPHA_INTEGRATION_1_STANDARD_ID1_FULL_POPULATION`.
This covers source integration, owned synthetic automated verification and the
standard candidate handoff. The new candidate's CE-host manual acceptance is
**NOT_RUN**; standard native runtime acceptance/qualification is **NOT ESTABLISHED**.
No release decision is implied or exercised.

## Admission and immutable historical binding

- Repository: `k-undurkhaan-2/Chrome_Project`; existing branch `armedforces.io-v2`.
- Initial local/remote HEAD: `ef8f70d4732834667cce48f257771708afc8f5c2`.
- M6 was outstanding. The separately supplied M6 authority was completed first:
  [acceptance receipt](g1-alpha-prep-3-r1-manual-acceptance.md), commit
  `4aed7bc48202271e5d08400d53511cf4828cbf01`. It registers
  `APPROVE_G1_ALPHA_PREP_3_R1_CONTROLLED_MANUAL_ACCEPTANCE` and
  `PASS_G1_ALPHA_PREP_3_R1_CONTROLLED_MANUAL_ACCEPTANCE`, retaining the direct
  observations versus maintainer confirmations for M1–M6.
- Before any integration edit, remote API readback verified M6's exact HEAD,
  parent, two paths, verified=true/reason=valid, receipt content and all 12
  historical maintained blobs. **Actual integration starting HEAD:**
  `4aed7bc48202271e5d08400d53511cf4828cbf01`.
- Historical accepted source remains `d3aadb33aab01f77bd9e45479975b5421188825c`;
  historical generated CT SHA-256 remains
  `2e6d3d5403d9ed5f156d313998ef3ac867b4735b77a67b920d8ac34cad5439a8`.
  Its delivery report, identity manifest and package are preserved. The new
  candidate does not inherit that manual PASS, 63 ms observation or Lua readings.
- New candidate source HEAD: `398b3dad7b41dacd893d376625404d26c71b6b3f`.
  The subsequent documentation-only handoff commit introduces this report; its
  exact final remote SHA and independent readback are provided in the final
  response and local `g1-alpha-integration-1-verification-receipt.local.json`.

## Standard entry, full handoff and gates

Default preparation still creates `src/ce_mvp.local.CT` from the maintained
template. It does not select `ALPHA_CONTROLLED`, generate private configuration
or select a mock automatically. The loader defaults to `ALPHA_STANDARD`, with
product_profile=ALPHA_FULL. Loading and configuration selection are inert.
An explicit Start without an allowed input fails `ALPHA_INPUT_REQUIRED` before
config/module/target access, with evaluation incomplete and no operation.

For this controlled standard-profile test, the existing `configure_execution`
interface explicitly accepts `{mode='ALPHA_STANDARD', input_source='OWNED_SYNTHETIC'}`
before Start. It reuses the existing public fixture constructor and exposes its
existing step/fault controls via `controlled_fixture()`. This accessor's historical
name does not change the selected mode: status remains ALPHA_STANDARD, with
synthetic provenance and action_permitted=false. No arbitrary CE APIs, factory,
writer, records source, native acquisition or application SDK was added.

The only existing permitted supplied-input seam is the owned table fixture.
There is no authorized non-synthetic standard input source; its absence fails
closed instead of enabling discovery or falling back to bounded scoring. This is
the explicit standard-path limitation, not a missing cooperative-API prerequisite.

The same AC6 explicit-record overload calls AC5 and the original scorer, common
cohort context, comparator, tie handling, confidence and recommendation logic.
AC6's result boundary now also reconciles exact supplied/distinct/eligible/selected/
ranked membership against the actual supplied records. Counts alone could previously
miss a same-size identity substitution after AC5 returned. Dense arrays, duplicate
multiplicity, selected uniqueness and exact full coverage are checked without
changing scoring, thresholds or eligibility rules. A full result must satisfy:

`supplied = distinct + duplicates`; `distinct = eligible + excluded`;
`eligible = selected = fully_scored = ranked`.

The existing selected-candidate interface feeds the original core. Identity,
structural, recommendation/admission, prewrite, immediate readback and cleanup
checks remain effective. Completed REVIEW/REJECT and legal EMPTY retain their
complete ranking result while admission denies an operation. Missing input,
incomplete words, identity inconsistency, scoring/resource failure and cancellation
remain unsuccessful without stale results or bounded fallback. The 129-member
regression uses the existing full API while the fixture's legacy budget remains
128; this is not a new budget or a bounded sentinel.

Standard Alpha and the historical controlled selection use ALPHA_STOP_ONLY.
Existing detectable failures stop/error and clean up; no automatic reselection,
rescan, reattachment or restart occurs. A fresh run requires explicit operator
Start; mode latches, installation binding and cleanup-uncertain restart rejection
are retained. `ENGINEERING_BOUNDED` explicitly selects the former NORMAL path and
its historical recovery behavior. `QUALIFICATION` retains its original required
factory, strict validation and guarded writer. Private data-only config is used
only by those explicitly selected paths and its schema/values were not changed.

The original scorer, AC5 module, ID3 module, public fixture/data, config example,
QSG writer/qualification implementation and resource limits were not changed.
No process was selected, opened, attached, discovered or written by native APIs
during this task; all operation/readback tests used the existing table doubles.

## ID2 diagnostic finding and ID3

`scan_mode` comes from validated `cfg.scan.mode`, whose bounded/process alternatives
describe configured address scope. It is not the scoring population mode. The old
manual `scan_mode=bounded` / `population_mode=full` combination was therefore not
bounded scoring. Historical fields and receipts are unchanged.

ID2 now makes `scan_mode_domain=configured_address_scope`, `scoring_mode=full`,
`acquisition_mode=supplied_records`, external_acquisition_status=NOT_RUN and
coverage_scope=supplied_distinct_eligible_only explicit. It reports cached completion,
all eight counts, identity reconciliation, Rank-1/runner-up scores, confidence,
recommendation/review, provenance, authorization, qualification, lifecycle and
cleanup. It initiates no scoring, clocks, target reads or operations. A second
diagnostic issue was corrected: completed full REVIEW/REJECT now retains
collection_phase=supplied_full_complete even when subsequent admission rejects it.
Error/cancel status remains distinct from completed ranking.

ID3's source and CT behavior remain independent, one-shot and read-only. ID1 does
not load ID3. The candidate's ID3 smoke used its own explicit entry after ID1 had
stopped and caused no fixture operation or loop activity.

## Signed commits, immediate pushes and independent readback

All commits used existing OpenPGP configuration and fingerprint
`86D51BCDBC946CF1389969D530479D840D9D562B`. Each unit was reviewed and validated,
then immediately `git commit -S`, locally `git verify-commit` (Good signature), and
normally `git push origin HEAD:refs/heads/armedforces.io-v2` through the configured
local gh HTTPS credential helper. Each push returned success. No validated
independent unit was held for a later bulk push.

Before the next mutation, `gh api repos/k-undurkhaan-2/Chrome_Project/commits/armedforces.io-v2`
independently returned the exact HEAD, parent, changed-path set and
**verified=true / reason=valid** for each row:

| Commit | Parent | Exact changed paths |
| --- | --- | --- |
| `4aed7bc48202271e5d08400d53511cf4828cbf01` | `ef8f70d4732834667cce48f257771708afc8f5c2` | `docs/g1_alpha_manual_acceptance.md`; `reports/2026-11-26/g1-alpha-prep-3-r1-manual-acceptance.md` |
| `a2c2783a0023481842d39c45ea6641f1698981c4` | `4aed7bc48202271e5d08400d53511cf4828cbf01` | `src/ce_mvp.CT`; `src/ce_mvp.lua`; `src/prepare_ce_mvp.py`; `tests/qualification/support.py`; `tests/qualification/test_l12_evidence_v2.py`; `tests/test_ce_mvp_readonly.py`; `tests/test_h3_a7_ce_mvp.py` |
| `29ae0763a5f93a48cf7f326325ca26144edacc53` | `a2c2783a0023481842d39c45ea6641f1698981c4` | `src/mvp0_foundlist_collector.lua`; `tests/test_ce_mvp_readonly.py`; `tests/test_offline_collector_interface.py` |
| `398b3dad7b41dacd893d376625404d26c71b6b3f` | `29ae0763a5f93a48cf7f326325ca26144edacc53` | `src/ce_mvp.lua`; `src/ce_mvp_adapter.lua`; `src/ce_mvp_core.lua`; `tests/test_ce_mvp_readonly.py`; `tests/test_h3_a7_ce_mvp.py` |

One local verification command incorrectly compared a PowerShell culture-sorted
path list to a Git-ordered string. Work paused; direct remote readback confirmed
the same HEAD, valid signature and five expected files. An exact case-sensitive
set comparison then passed before candidate preparation. This was a verification
script ordering error, not signature failure or remote drift. Initial sandbox
GPG/keyring and Schannel checks were unavailable; the already-authorized standard
host (SID `S-1-5-21-1353174265-123074972-3048594297-1001`) verified and signed normally.
No identity, credentials, signing configuration, remote or protection was changed.

The final handoff unit contains only `README.md`, the new Chinese manual sheet,
this report and the new identity manifest. Its parent is the candidate source
HEAD above; final-response verification binds its exact SHA without introducing a
self-referential commit hash into this file.

## Validation commands and actual failure history

Environment: Windows x64, Python **3.14.3**, Lupa **2.8**. ID1/CT tests execute genuine
**Lua 5.3**; existing interface/core fixtures additionally use Lua 5.4. Lupa is not
CE-host evidence. The existing **268435456-byte (256 MiB)** test allocator cap is
unchanged. Existing fault cases temporarily lower the allocator limit to induce
real failure, then restore it; no product allowance was increased.

Commands below ran from `D:\armedforces.io-v2`. Temporary output trees remain local
and are not committed. Repeated suites overlap and must not be added as independent
accuracy observations.

1. Initial entry/QSG run:
   `& '.venv/Scripts/python.exe' -m pytest -q tests/test_ce_mvp_readonly.py tests/qualification/test_qsg_integration.py --basetemp=reports/2026-11-26/g1i-entry-1`
   — **87 passed, 13 failed, 41.34 s**. One standard missing-input case omitted
   explicit input selection; 12 new assertions incorrectly expected Lua `dofile`
   to pass through an overridden `loadfile`. Test wiring/expectations were corrected.
2. Initial compatibility run used the selector in item 4 with
   `--basetemp=reports/2026-11-26/g1i-entry-compat-1` — **183 passed, 1 failed,
   747 deselected, 7.85 s**. The inert-loader test still expected the former default
   config access; it now expects ALPHA_INPUT_REQUIRED. No runtime workaround was used.
3. Completed entry and strict QSG checks:
   `& '.venv/Scripts/python.exe' -m pytest -q tests/test_ce_mvp_readonly.py tests/qualification/test_qsg_integration.py tests/qualification/test_qsg_acceptance.py tests/qualification/test_qsg_boundaries.py --basetemp=reports/2026-11-26/g1i-entry-2`
   — **214 passed, 144.58 s**.
4. Completed loader/config/lifecycle/engineering compatibility:
   `& '.venv/Scripts/python.exe' -m pytest -q tests/test_h3_a7_ce_mvp.py -k 'portable or actual_loader or loader_is_inert or alpha_stop_policy or config_rejects or confirmed_invalidation_rescans or happy_path_complete or cleanup_uncertainty_blocks_restart or strict_missing_policy or rev1_malformed_or_nonaccept' --basetemp=reports/2026-11-26/g1i-entry-compat-2`
   — **184 passed, 747 deselected, 6.93 s**.
5. Historical L12 callers now explicitly select engineering behavior; qualification
   callers still select QUALIFICATION:
   `& '.venv/Scripts/python.exe' -m pytest -q tests/qualification/test_g1_infra.py tests/qualification/test_l12_evidence_v2.py -k 'each_l12_wrong_diagnostic or lp03_mock_capture' --basetemp=reports/2026-11-26/g1i-entry-l12`
   — **5 passed, 155 deselected, 10.02 s**.
6. Identity-boundary regression before its fix:
   `& '.venv/Scripts/python.exe' -m pytest -q tests/test_ce_mvp_readonly.py -k 'incomplete_or_invalid and identity' --basetemp=reports/2026-11-26/g1i-membership-red`
   — **4 failed, 97 deselected, 2.52 s**. Same-count eligible/selected identity
   substitutions after AC5 returned were accepted in both standard and historical
   controlled paths. The AC6 handoff membership checks fixed this actual defect.
7. Completed identity/interface/ID1/ID3 checks:
   `& '.venv/Scripts/python.exe' -m pytest -q tests/test_offline_collector_interface.py tests/test_ce_mvp_readonly.py --basetemp=reports/2026-11-26/g1i-membership-1`
   — **339 passed, 12.61 s**. Covers exact identities, duplicate/excluded/empty
   cases, common scoring, 129 members, invalid envelopes, resource/error/cancel
   outcomes, stale-result prevention and original operation/cleanup guards.
8. Final ID2 and standard/controlled CT checks:
   `& '.venv/Scripts/python.exe' -m pytest -q tests/test_ce_mvp_readonly.py --basetemp=reports/2026-11-26/g1i-status-1`
   — **103 passed, 7.75 s**.
9. Final affected core/engineering diagnostics checks:
   `& '.venv/Scripts/python.exe' -m pytest -q tests/test_h3_a7_ce_mvp.py -k 'actual_loader or happy_path_complete or confirmed_invalidation_rescans or alpha_stop_policy or strict_missing_policy or rev1_malformed_or_nonaccept' --basetemp=reports/2026-11-26/g1i-status-compat`
   — **84 passed, 847 deselected, 5.94 s**.
10. Final strict public-loader probe:
    `& '.venv/Scripts/python.exe' -m pytest -q tests/qualification/test_qsg_integration.py::test_public_loader_start_stop_latches_and_preserves_cleanup_probes --basetemp=reports/2026-11-26/g1i-status-qsg`
    — **1 passed, 2.04 s**.
11. Each commit's exact diff/staged paths and `git diff --check` passed. Unrelated
    modified documents, untracked work, private config, historical packages,
    generated CT and runtime/test output trees were excluded from staging.

There are no unresolved failures in these scoped checks. The entire repository
suite and historical AC8/G1 campaigns were not rerun; their historical outcomes
remain scoped and unchanged.

## New candidate and actual package verification

- Package: `D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-integration-1-manual\`.
- Open its `src\ce_mvp.local.CT`, SHA-256
  **`3bdab824338de25b487c2be78379532a350ad942646ffdc4342dfa40d44e6069`**, **2955 bytes**.
- [13-file manifest](g1-alpha-integration-1-file-identities.json): every maintained
  file has source commit, Git blob, SHA-256 and byte length. Files were copied from
  exact committed blobs into a new directory, never over an existing local CT.
- Actual default preparation command:
  `& '.venv/Scripts/python.exe' 'D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-integration-1-manual\src\prepare_ce_mvp.py'`
  — exit 0, no mode flags, `controlled=false`, ALPHA_STANDARD default.
- Candidate verification used `& '.venv/Scripts/python.exe' -` with the existing
  `tests/test_ce_mvp_readonly.py` Lua 5.3 harness. It executed the **actual packaged**
  CT, all six syntax-check blocks, all four verbatim Lua blocks extracted from the
  [Chinese manual sheet](../../docs/g1_alpha_integration_1_manual_acceptance.md),
  ID2 toggles and the independent ID3 entry. No test launcher/framework was added.
- Result: **PASS_STANDARD_PACKAGE_SMOKE**. COMPLETE; all six applicable counts 3,
  duplicates/excluded 0; exact identities `0x100128`, `0x100328`, `0x100528`;
  independent Rank-1 46, runner-up -36; ACCEPT/HIGH/no review; one table-only
  operation/readback at `0x42FA0000`. Zero ambient target calls and zero fixture
  native scan objects. Default input omission separately failed ALPHA_INPUT_REQUIRED
  before any config/module/target call.
- Mapping fault: ERROR / ALPHA_STOP:MAPPING_CHANGED, cleanup_ok=true, no recovery
  after 200 fixture ticks with a replacement. Explicit restart produced a fresh
  evaluation; CT disable produced STOPPED/OPERATOR_STOP and no activity after
  200 ticks. ID2 observation caused no extra evaluation, read/write/open/scan or
  evidence mutation. ID3 remained independent/read-only. All 13 file hashes and
  the exact file set were reverified after execution.
- The first ten-tick **Lupa-only** smoke measured **6 ms**, Lua before/after
  **773.0712890625 / 1735.7509765625 KiB**. These are not CE measurements or process
  peak/capacity claims. The CE manual sheet uses the host's actual clock when the
  maintainer runs it; its future values must be recorded independently.

## Retained restrictions, unknowns and handoff

`ATTACHMENT_HANDLE_UNVERIFIED`, `QSG_NATIVE_BACKEND_NOT_QUALIFIED`,
`NOT_PRODUCTION_AUTHORIZED`, `IMPLEMENTED_PENDING_CE_QUALIFICATION` remain in force.
G1 historical matrix: **0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**.
AC8 >=95% of planned positive pools with reconciled completed coverage and the
original finite-domain 100/100 remain historical, without a new accuracy campaign.
Correct Rank-1 with REVIEW never grants operation authority.

L01/L12, AC/PAIR, N0/MIN/LOCAL suspension, Generation 2, existing native qualification,
resource limits and publishing conditions are unchanged. Full supplied coverage
does not establish complete external acquisition or global uniqueness. Native
operation/readback are **UNSUPPORTED / NOT_RUN** for this candidate; standard native
qualification remains **NOT ESTABLISHED**. New CE host measurements, UI response,
process peak, cancellation latency, hard timeout, capacity/SLA and semantic-liveness
guarantees are UNKNOWN/NOT_RUN as applicable. No live target/third-party test was run
or requested. No Tag, Release, PR, branch or automatic next task was created.

Implementation choices within the specification's delegated mechanism choice:
explicit ALPHA_STANDARD/OWNED_SYNTHETIC through the existing selection API;
ENGINEERING_BOUNDED for the previous optional path; a separate new manual sheet;
exact membership validation at AC6's existing interface. No additional maintainer
policy decision was inferred. The scoped handoff is ready; maintainer acceptance,
any non-synthetic input authorization, native qualification and publication remain
separate decisions.
