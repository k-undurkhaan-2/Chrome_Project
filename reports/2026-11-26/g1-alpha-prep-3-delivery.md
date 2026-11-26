# G1-ALPHA-PREP-3 partial delivery

Status: **PARTIAL_G1_ALPHA_PREP_3**.

Authority: `APPROVE_G1_ALPHA_PREP_3_CONTROLLED_INTEGRATION`, followed by the
maintainer's explicit selection of PARTIAL delivery after interface inspection.

The approved integration cannot be completed through the established interfaces
in the supplied repository. After the missing interfaces were identified, the
maintainer explicitly selected delivery as PARTIAL. This record and the updated
[Chinese operator sheet](../../docs/g1_alpha_manual_acceptance.md) deliver the
actual disposition. They do not declare a new preparation milestone, integrated
ID1 candidate, qualification, or release.

## Actual code identity and integration boundary

The existing branch is `armedforces.io-v2`. The verified baseline is
`3a8fa0876fcb0e972af6e657693948207484ec86`, with parent
`b86c226e2b0b90f3da2ebf79fcafc1f595c996c1`. Local HEAD and the independent GitHub
commit API agreed. Local GPG verification succeeded using signing key
`86D51BCDBC946CF1389969D530479D840D9D562B`; GitHub reported `verified=true` and
`reason=valid`.

No runtime or test source changed. The actual CT/Lua implementation remains the
baseline version. There is no new ID1 full-population candidate or enabled Alpha
stop-without-recovery mode. The existing PREP-2 package is retained in place and
identified below, not repackaged or relabelled as PREP-3 product integration.

| Required capability | Inspected implementation | Actual disposition |
| --- | --- | --- |
| Product Start | `src/ce_mvp.CT` ID1 calls `ce_mvp.lua.start()`. The loader validates native config, constructs `ce_mvp_adapter.lua` and starts `ce_mvp_core.lua`. | Existing native orchestration only; no authorized application-data connection to AC6. |
| Owned complete-population acquisition | AC6 `MVP0FoundList.run(opts, offline_request)` requires explicitly supplied records and a trusted loader. Without that request, `population_mode` is rejected. `docs/algorithm_a_offline_scoring.md` documents synthetic scope and absence of an application exporter. | Missing a documented cooperative application exporter with source identity and acquisition-completeness evidence. The supplied-population contract cannot establish acquisition completeness. |
| Full scoring and proposal | `ce_mvp_readonly.lua.evaluate()` calls AC6 and retains the entire completion envelope; a completed nonempty result proposes only Rank-1. | Existing ID3/table capability; no new wrapper or alternate scorer. Scoring, eligibility, cohort, comparator, confidence, recommendations, review fields and full-budget validation remain unchanged. |
| Authorized operation/readback | The native adapter captures CE `writeFloat` and `readFloat`/`readInteger`. Synthetic handoff protocols have no production adapter. `qualification/qsg.lua` requires synthetic origin and mock transport. | Missing an established owner-authorized application operation/readback interface satisfying all existing identity, qualification, action and cleanup gates. Neither native primitives nor a synthetic model is substituted. |
| Application lifecycle and semantic validity | Native identity checks sample CE selection, PID/creation time and liveness; `a.valid()` checks mapping/fields. | Missing an application lifecycle/object-validity interface. These checks do not establish semantic identity of a stored object. |
| Alpha stop, no automatic recovery | The original core's `backoff()` and `MONITORING` paths preserve zero-candidate and confirmed-invalidity rescans. Native identity errors terminate through original cleanup. | Alpha disposition is not integrated. Historical engineering recovery remains unchanged; it is not claimed to satisfy the candidate requirement. |

The maintained source has no existing documented cooperative interface that can
be connected within this task's authorization. Building new external-process
acquisition, replacing the writer, extending qualification from synthetic models,
or merely routing ID1 to the read-only example would not close these gaps. No
such implementation was introduced. No native capacity or response-time policy
was inferred from offline ceilings.

## Retained usable artifact

- Runtime: Windows x64 CE 7.6 / Lua 5.3, as required by the existing implementation;
  no CE execution occurred in this task.
- Source identity: baseline `3a8fa0876fcb0e972af6e657693948207484ec86`.
- Existing generated CT:
  `reports/2026-11-26/g1-alpha-prep-2-manual/src/ce_mvp.local.CT`.
- Generated CT SHA-256:
  `c7d93bd95b6830d59f279b5db164593cc645348ce7283d484d3adfb93f94da4a`.
- Existing local manifest: the same package's `file-identities.json`, containing
  all 11 file hashes and the original PREP-2 implementation identity.
- All 11 hashes were recalculated and matched. The 10 maintained package files
  also matched working source bytes and baseline Git blob identities. CT XML IDs
  1/2/3 and the generated absolute-path substitutions matched the template. The
  package has no private `ce_mvp_config.local.lua`.
- No package was regenerated, no launcher was added, and private configuration
  and generated CT files were preserved. The operator sheet permits file
  inspection now; it does not request ID1 execution or an ID3 repetition.

## Evidence retained, not rerun

The maintainer-supplied task document records a subsequently provided real CE
console transcript under the designated CT / no-target / ID3-only conditions:
the public three-record positive observation completed with full coverage,
matching synthetic identities, Rank-1 score 46, runner-up -36, ACCEPT/HIGH,
`action_permitted=false` and `automatic_recovery=false`. This limited positive
observation is preserved as maintainer-confirmed evidence, not a newly executed
or independently replayed observation. No unseen AA return, failure-control,
large-pool or lifecycle result is inferred. The old PREP-2 NOT_RUN statements
remain historical statements at the time of that delivery.

AC5/AC6, AC8 (100/100 Rank-1; 48 ACCEPT / 52 REVIEW; 3/3 controls NO_ACCEPT),
AC9 (103-case output regression and offline conversion optimization), PREP-2's
66 checks, G1-S2/S3 and the L12 prospective erratum are reused as historical
evidence in their original scopes. No accuracy or live campaign was repeated.

## Verification for this documentation change

Only static, read-only inspection is applicable; there is no new runtime
implementation to exercise. No new tests or test framework were added.

- Inspected branch, HEAD, exact parent, tracked diff and empty initial index.
  Unrelated existing changes were excluded from the task.
- `git verify-commit 3a8fa0876fcb0e972af6e657693948207484ec86`: good GPG signature.
- `gh api repos/k-undurkhaan-2/Chrome_Project/commits/armedforces.io-v2`:
  exact baseline SHA/parent and valid GitHub signature verification.
- An inline invocation of the existing `.venv/Scripts/python.exe -B -` used
  `hashlib`, `json`, XML parsing, `git hash-object --path` and `git rev-parse` to
  verify the retained 11-file package, 10 baseline file identities, exact CT
  binding and absence of local config. Result: **PASS_STATIC_ONLY**. It did not
  execute Lua, score records, prepare a CT, import a target or start CE.
- Local documentation links, UTF-8 text, required scope/status statements and
  whitespace checks passed for all three changed documents. All 171 preservation
  hashes matched, covering existing tracked source/test files, the two
  pre-existing modified documents and selected local artifacts. Raw verification
  metadata remains in a local ignored log; it is not committed. The staged
  `git diff --cached --check` is checked immediately before signing.
- Runtime tests, new integration tests, CE/AA operations, production operations
  and historical campaigns: **NOT_RUN**. No new full-evaluation, bounded-parity,
  stop, action or lifecycle behavior is claimed verified by this task.

This is one coherent documentation change. Its signed commit, normal HTTPS push
to the existing branch, and independent GitHub HEAD/SHA/parent/signature checks
are reported in the final handoff after those operations complete; a file does
not embed its own future commit identity.

## Maintainer disposition and unchanged release constraints

The Chinese sheet identifies actual files, current safe file-inspection steps,
missing prerequisites and independent acceptance categories. Future full
evaluation, measured responsiveness, authorized action/readback, and reported
lifecycle clean-stop observations are separate results. The >=95% ranking
criterion remains scoped to a predeclared evaluable positive domain; unknown
truth is not a hit, and a small manual observation is not an accuracy campaign.
Unknown performance measurements stay unknown. There is no new numeric SLA.

The missing interfaces, actual ID1 integration, Alpha stop-without-recovery
behavior and applicable native/resource prerequisites remain release blockers.
The maintainer makes the final manual acceptance decision separately. G1 stays
at **0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**. L01, prospective L12,
AC/PAIR conclusions, strict qualification/attachment restrictions and N0/MIN/LOCAL
suspension remain unchanged. No historical row becomes PASS and no production
use is authorized. No new branch, PR, Tag or Release is created.

Version Tag Recommendation: **No new version tag recommended**. The integrated
candidate is unavailable and the maintainer's separate acceptance/release
decision and applicable constraints remain outstanding.
