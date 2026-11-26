# G1-ALPHA-PREP-3-R1 M6 controlled manual acceptance registration

> Historical evidence only; not current operating instructions. Original recorded values and authority are unchanged. [Immutable original](https://github.com/k-undurkhaan-2/Chrome_Project/blob/4aed7bc48202271e5d08400d53511cf4828cbf01/reports/2026-11-26/g1-alpha-prep-3-r1-manual-acceptance.md). Current product guidance: [English Quickstart](../../docs/ce_mvp_quickstart.md).

Maintainer decision (2026-11-26, Asia/Singapore):
`APPROVE_G1_ALPHA_PREP_3_R1_CONTROLLED_MANUAL_ACCEPTANCE`.

Scoped result: **PASS_G1_ALPHA_PREP_3_R1_CONTROLLED_MANUAL_ACCEPTANCE**.

This registers the maintainer's already completed owned synthetic CE-host test.
Codex did not run or independently observe that manual session. It neither
qualifies a native backend nor accepts the default standard runtime.

## Immutable candidate and registration baseline

- Tested source: `d3aadb33aab01f77bd9e45479975b5421188825c`.
- Registration starting local and remote HEAD: `ef8f70d4732834667cce48f257771708afc8f5c2`;
  branch `armedforces.io-v2`, repository `k-undurkhaan-2/Chrome_Project`.
- Local candidate: `D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-prep-3-r1-manual\src\ce_mvp.local.CT`.
- Generated CT SHA-256: `2e6d3d5403d9ed5f156d313998ef3ac867b4735b77a67b920d8ac34cad5439a8`.
- [Historical delivery](g1-alpha-prep-3-r1-delivery.md),
  [13-file identity manifest](g1-alpha-prep-3-r1-file-identities.json), and
  [historical operator sheet](https://github.com/k-undurkhaan-2/Chrome_Project/blob/4aed7bc48202271e5d08400d53511cf4828cbf01/docs/g1_alpha_manual_acceptance.md)
  retain their original pre-acceptance observations.
- Read-only registration checks reconfirmed all 12 maintained Git blobs against
  the manifest and the generated local CT hash. The starting HEAD is exactly one
  documentation-only descendant of the tested source, changing only the operator
  sheet, delivery report and identity manifest. No equivalent acceptance receipt
  was present. GitHub reported the starting commit verified=true/reason=valid;
  configured-host GPG verification of both commits returned Good signature.
- Windows x64 / CE 7.6 / Lua 5.3; no selected process; ID1 `ALPHA_CONTROLLED`;
  existing owned fixture only. ID3 was not rerun. The CT is a path-bound local
  artifact, not a committed file or a portable hash for other installations.

## M1–M6 evidence and provenance

| Step | Status | Evidence basis and scoped result |
| --- | --- | --- |
| M1 candidate/host admission | PASS | Direct console: `CE_LUA_VERSION=Lua 5.3`, `EXISTING_SINGLETON=false`; supplied PowerShell CT hash matches above. Screenshot showed No Process Selected and three initially unchecked entries. Full-package identity comparison and CE 7.6 version are **maintainer-confirmed**, without separately captured per-file/version transcripts. |
| M2 full evaluation/ranking | PASS | Direct CE transcript and follow-up: COMPLETE, completed=true, population_mode=full, population_complete=true. supplied=distinct=eligible=selected=fully_scored=ranked=3; duplicates=excluded=0. All count equations and exact supplied/distinct/eligible/selected/ranked membership reconcile. Ordered identities `0x100128`, `0x100328`, `0x100528` match independent fixture truth. Rank-1 score 46; other scores -36/-36, gap 82; ACCEPT/HIGH, manual_review_required=false. One scene, not a new accuracy estimate. |
| M3 simulated operation/readback/monitoring | PASS | Direct transcript: ATTACHING → SCREENING → CANDIDATE_CHECK → WRITING → READBACK → MONITORING; running=true, scan_count=1, write_count=1, monitor_checks=2, invalid_count=0, rescan_attempts=0, retry_at=nil. One simulated write attempt/success/verified write; simulated bits `0x42FA0000` (125.0) match. 23 sequential synthetic events plus snapshot, dropped_events=0. Direct follow-up fixture_native_scan_objects=0; adapter_scan_invocations=0. |
| M4 detectable mapping failure/cleanup | PASS | Direct output: ERROR, running=false, `ALPHA_STOP:MAPPING_CHANGED`, cleanup_ok=true, candidate_address=nil, rescan_attempts=0, retry_at=nil, no_recovery=true, fixture_cleanup_check_returned=true. After the table mapping fault, adding a synthetic replacement and advancing 200 ticks caused no further read/write/open/scan activity. No semantic-liveness or real process detector claim. |
| M5 explicit operator stop | PASS (maintainer-confirmed) | Maintainer confirmed a separate explicit restart to MONITORING and operator-stop test passed. Expected scope: STOPPED/OPERATOR_STOP, cleanup and no activity after 200 fixture ticks. Detailed actual fields/raw logs were not separately supplied and are not reconstructed here. |
| M6 final decision | APPROVED | The exact decision above accepts M1–M5 within their distinct evidence bases and the residual unknowns below. No retest was performed for registration. |

M2 also directly reported coverage=full_population,
collection_phase=supplied_full_complete, raw admission/ranking complete and both
relevant budgets nil; global_uniqueness_proven=false. Supplied-population coverage
does not establish complete external acquisition or global uniqueness.

M3 scope: execution_mode=ALPHA_CONTROLLED, decision_scope=OWNED_SYNTHETIC_FULL,
write_admission_basis=SYNTHETIC_ONLY_SCOPE_ACCEPT, lifecycle_policy=ALPHA_STOP_ONLY,
automatic_recovery=false, action_permitted=false. Native operation/readback remain
UNSUPPORTED / NOT_RUN; semantic_validity=UNVERIFIED_SYNTHETIC_ONLY. Simulated
identities, API names, clocks and operations are not native evidence or authority.

## Measurements and remaining unknowns

The directly supplied single ten-fixture-tick invocation measured **63 ms** wall
time; Lua occupancy before/after **2447.638671875 / 3411.5986328125 KiB** (net
963.9599609375 KiB, approximately 0.941367 MiB). These are CE-host before/after
Lua readings, not process peak memory, native performance, an isolated scorer
benchmark or a capacity SLA. Fixture 50 ms steps and relative event time are
simulated. Process peak, separately confirmed UI responsiveness, cancellation
latency, hard timeout and native capacity remain UNKNOWN/NOT_RUN as applicable.

The observed `scan_mode=bounded` alongside `population_mode=full` remains an
outstanding diagnostic interpretation matter for this registration. It is not
evidence of bounded scoring and is not declared a proven legacy label here.
Optional manual WRITE_FAILED, READBACK_MISMATCH, PID_EXITED and
PID_IDENTITY_MISMATCH cases remain NOT_RUN in this manual session; earlier
regressions do not become new CE observations.

## Separate conclusions and retained gates

1. Remote maintained source inclusion/equivalence to the tested source is
   established at the registration baseline; all 12 manifest blobs match.
2. Controlled manual acceptance is PASS only for the exact candidate and scope.
3. Default standard runtime/native full end-to-end acceptance is **NOT ESTABLISHED**.
   At the baseline the standard CT has controlled=false, preparation does not
   select controlled mode by default, and the loader defaults to NORMAL. Only the
   explicitly controlled constructor selects the owned fixture and ALPHA_STOP_ONLY.
   Ordinary and strict qualification constructors remain separate; ID3 is read-only.
4. Production/publishing authorization is absent. No Tag, Release, PR, new branch,
   permission change or automatic follow-up was created by this registration.

`ATTACHMENT_HANDLE_UNVERIFIED`, `QSG_NATIVE_BACKEND_NOT_QUALIFIED`,
`NOT_PRODUCTION_AUTHORIZED`, `IMPLEMENTED_PENDING_CE_QUALIFICATION` remain in force.
Original G1 matrix: **0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**.
AC8 >=95% of planned positive pools and historical 100/100 in the original finite
domain remain unchanged; no new accuracy campaign or pooled metric. L01/L12,
historical AC/PAIR, N0/MIN/LOCAL suspension, Generation 2, native qualification,
resource limits and release conditions are unchanged. No external discovery,
acquisition, writing, injection, privileges or third-party application access is
authorized by this receipt.

## Registration validation and signed receipt

Documentation links, decision/status tokens, evidence provenance, retained gates,
exact changed paths and `git diff --check` were checked for this documentation-only
unit. No functional tests were rerun. Historical delivery/manifest and runtime
files are unchanged. Original user changes and local outputs are excluded.

The signed registration commit is the commit introducing this receipt, whose
parent must be `ef8f70d4732834667cce48f257771708afc8f5c2`. Its exact SHA, normal
HTTPS push and independent remote HEAD/parent/paths/signature readback are recorded
in the successor integration receipt and final delivery; they are not inferred
from the presence of this text.
