# G1-ALPHA-PRE-RELEASE-PREP-1 readiness inventory

> Historical evidence only; not current operating instructions. Original recorded values and authority are unchanged. [Immutable original](https://github.com/k-undurkhaan-2/Chrome_Project/blob/309fa3a99115b4a32f980752d874a9116cc64660/reports/2026-11-26/g1-alpha-pre-release-prep-1-readiness.md). Current product guidance: [English Quickstart](../../docs/ce_mvp_quickstart.md).

Date: 2026-11-26 (UTC+08:00). **Engineering inventory complete; release eligibility
NOT ESTABLISHED. Alpha Pre-release remains BLOCKED.** This is a documentation
handoff for the existing controlled synthetic evaluation candidate, not a release
PASS, a new effectiveness result, or permission to operate on a real target.
The maintainer will arrange independent effectiveness acceptance and decide any
later release separately. No testing campaign or follow-up is scheduled here.

## 1. Admission and evidence hierarchy

Repository: `k-undurkhaan-2/Chrome_Project`; authorized existing branch:
`armedforces.io-v2`. Initial local HEAD, upstream, HTTPS remote ref and GitHub
branch API all resolved to `603f3b420e7fefe027981aa64f6c2f0d2a7c7e7e`.
Its parent and final executable source are
`6190a9f93ec72560ca5db5e616bc4cd411795efc`. The baseline index was empty;
pre-existing worktree changes and unrelated local outputs are excluded.

The seven commits from M6 registration `4aed7bc48202271e5d08400d53511cf4828cbf01`
through the baseline were checked with the configured OpenPGP verifier:
all returned good signatures using
`86D51BCDBC946CF1389969D530479D840D9D562B`. Independent GitHub API reads confirmed
each exact SHA, parent and changed-path set with `verified=true / reason=valid`.
No credentials, signing settings, protection or branch identity changed.

Sources below are committed records at the baseline unless explicitly described
as local artifacts. Later dated decisions govern their stated scope; earlier
reports retain their original outcomes and are not silently rewritten.

| Source | Authority and evidence use |
| --- | --- |
| [Repository policy](../../AGENTS.md) and [README](../../README.md) | Layout, minimal signed documentation history, milestone nomenclature, separate maintainer release decision and applicable technical qualifications. |
| [M6 registration](g1-alpha-prep-3-r1-manual-acceptance.md) | `APPROVE_G1_ALPHA_PREP_3_R1_CONTROLLED_MANUAL_ACCEPTANCE`; `PASS_G1_ALPHA_PREP_3_R1_CONTROLLED_MANUAL_ACCEPTANCE`, registered by `4aed7bc48202271e5d08400d53511cf4828cbf01`. Applies only to PREP-3-R1 source `d3aadb33aab01f77bd9e45479975b5421188825c`. |
| [Standard integration delivery](g1-alpha-integration-1-delivery.md) | `APPROVE_G1_ALPHA_INTEGRATION_1_STANDARD_ID1_FULL_POPULATION`; final source `6190a9f93ec72560ca5db5e616bc4cd411795efc`, handoff `603f3b420e7fefe027981aa64f6c2f0d2a7c7e7e`; actual failures, corrections, retests and package smoke. |
| [Standard manual sheet](https://github.com/k-undurkhaan-2/Chrome_Project/blob/309fa3a99115b4a32f980752d874a9116cc64660/docs/g1_alpha_integration_1_manual_acceptance.md) and [13-file manifest](g1-alpha-integration-1-file-identities.json) | Exact current path-bound candidate, explicit owned synthetic input, host requirements and pending candidate-specific manual acceptance. |
| [Registered algorithm decisions](../../docs/algorithm_a_offline_scoring.md) | G1-S2 clauses and later G1-S3 D2.1-D2.4; full supplied-population evidence, AC8 criterion, resource policy, historical AC/PAIR and current G1 state. |
| [Historical manual sheet](https://github.com/k-undurkhaan-2/Chrome_Project/blob/309fa3a99115b4a32f980752d874a9116cc64660/docs/g1_alpha_manual_acceptance.md) | Maintainer's PREP-3-R1 scope correction removes a mandatory cooperative application API prerequisite; it does not supply a non-synthetic standard input source. |
| [Quickstart release condition](https://github.com/k-undurkhaan-2/Chrome_Project/blob/309fa3a99115b4a32f980752d874a9116cc64660/docs/ce_mvp_quickstart.md#automatic-process-mode-operator-retest-p4-r2), [R1 plan](../../docs/ce_mvp_q1_r1_plan.md), [product contract](https://github.com/k-undurkhaan-2/Chrome_Project/blob/309fa3a99115b4a32f980752d874a9116cc64660/docs/architecture/h3_a7_ce_mvp_contract.md) | Retained P4-R2 manual prerequisite and separate release transaction; strict native qualification, ownership, identity, exact readback and cleanup requirements. Historical NORMAL instructions are not the current standard candidate's operating instructions. |
| [L12 prospective erratum](../../docs/qualification/h3_a7_q1_qsg_synthetic_test_plan.md#g1-s3-d24-prospective-l12-erratum-2026-11-26), [native activation contract](../../docs/qualification/h3_a7_q1_qsg_r3_b_p0_activation_contract.md#qualification-and-remaining-native-gates) | Current L12 example and separately authorized native evidence requirements. Neither document supplies a new live PASS. |

## 2. Exact package identity and reproducible preparation

Evidence basis, retained in place:
`D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-integration-1-manual-final`.
Generated CT: `src\ce_mvp.local.CT`, **3003 bytes**, SHA-256
`023ed8e3d1a41841b3f22e826a55f2e23f3860d2ef73c6859079123d4797f4d6`.

Read-only verification compared the exact recursive file set, all 13 byte lengths
and SHA-256 values, and all 12 maintained Git blobs to the existing manifest and
source commit. All matched; those 12 blobs also match the handoff HEAD. The local
manifest itself is 8572 bytes, SHA-256
`7ea786da9f8ccd77d06c4f2dbab7de2b30fc62ac1ab7af3ca3f287d605373451`.
Git blob IDs and per-file SHA-256 values remain in the linked manifest.

| Exact package member | Bytes | Role |
| --- | ---: | --- |
| `src/ce_mvp.lua` | 10779 | Standard loader and explicit mode/input selection |
| `src/ce_mvp_core.lua` | 19762 | Existing lifecycle and operation/cleanup checks |
| `src/ce_mvp_adapter.lua` | 36236 | Existing adapter and cached full diagnostics |
| `src/mvp0_foundlist_collector.lua` | 96505 | AC6 handoff, full result and identity validation |
| `src/mvp0_candidate_report.lua` | 107482 | Existing scorer and ordinary report |
| `src/ce_mvp_readonly.lua` | 4648 | Independent ID3 read-only entry |
| `src/mvp0_offline_scoring.lua` | 10760 | AC5 supplied-record full evaluation |
| `src/examples/g1_alpha_population.example.lua` | 929 | Public three-record synthetic example |
| `src/ce_mvp_config.example.lua` | 2659 | Maintained example, not private runtime configuration |
| `src/ce_mvp.CT` | 2306 | Maintained CT template |
| `src/prepare_ce_mvp.py` | 3248 | Existing offline path-binding preparation |
| `tests/fixtures/ce_mvp_mock.lua` | 13188 | Existing owned table fixture |
| `src/ce_mvp.local.CT` | 3003 | Generated, installation-bound local CT |

The original preparation command and exit 0 are preserved in the manifest:

```powershell
& 'D:\armedforces.io-v2\.venv\Scripts\python.exe' 'D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-integration-1-manual-final\src\prepare_ce_mvp.py'
```

This is recorded provenance, not an instruction to overwrite the candidate.
Preparation used no mode flags and retained `controlled=false`. For this handoff,
the existing preparation module's path-encoding function and template markers
were evaluated in memory; the default rendering at the same absolute path was
byte-for-byte identical to the existing CT. XML parsing confirmed ID1/ID2/ID3.
The write-producing `prepare()` function was not called. No CT was generated,
overwritten, relocated or executed. This establishes same-source/same-path
reproducibility only: the CT hash is **not portable to another installation path**.

The superseded `g1-alpha-integration-1-manual` candidate remains historical:
source `398b3dad7b41dacd893d376625404d26c71b6b3f`, CT SHA-256
`3bdab824338de25b487c2be78379532a350ad942646ffdc4342dfa40d44e6069`.
It is not a substitute for `manual-final`. Historical PREP-3-R1's accepted CT
hash remains `2e6d3d5403d9ed5f156d313998ef3ac867b4735b77a67b920d8ac34cad5439a8`.

### Review inventory and exclusions

The existing package can serve local review: its exact file set consists of the
12 public committed blobs and generated CT, with no extra private configuration,
credentials, signing keys, target identifiers or raw logs. Public synthetic
identities do not identify a real target. The CT embeds its installation path;
it is not a distributable or relocatable release asset.

Use this inventory and existing manifest instead of building a ZIP, installer or
second executable package. A later review collection, if separately approved,
would need only this fixed inventory plus the manual sheet and scoped draft
documents. Exclude `.git`, task prompts, local configuration/backups, auto-save
CTs, unrelated untracked sources, historical/superseded packages, runtime/test
logs, private receipts and signing material. Do not copy the worktree wholesale.
No new executable review artifact is needed or created by this preparation.

## 3. Delivered architecture and supported scope

Standard CT preparation selects the existing `ALPHA_STANDARD` loader default
and `ALPHA_FULL` profile. Loading and input selection are inert. Start requires
an explicit allowed input; otherwise it returns `ALPHA_INPUT_REQUIRED` before
dependent configuration/module/target access. There is no implicit mock choice.
The implemented standard full-path input is only `OWNED_SYNTHETIC`, explicitly
selected through the existing interface in the standard manual sheet.

| Entry | Current supported behavior and boundary |
| --- | --- |
| ID1 Start/Stop | Existing adapter/core and AC6/AC5 evaluate the supplied distinct eligible population together. The existing owned fixture supplies table-only operation/readback. `ALPHA_STOP_ONLY` stops and cleans up on detectable failure; no automatic rescan, reselection, reattachment or restart. A new run needs explicit operator Start. |
| ID2 Status | Observes cached evaluation, counts, identity reconciliation, rank/recommendation, provenance, authorization and lifecycle/cleanup. It does not initiate evaluation or target activity. `scan_mode_domain=configured_address_scope` distinguishes scan scope from `scoring_mode=full`. |
| ID3 READ ONLY | Independent, explicit, one-shot public synthetic example; not a prerequisite for ID1 and not its implementation. Synchronous execution; unchecking is not in-flight cancellation. |

Full completion requires `supplied = distinct + duplicates`,
`distinct = eligible + excluded`, and
`eligible = selected = fully_scored = ranked`, plus exact identity reconciliation.
The original scorer, eligibility, common cohort, order/ties, confidence,
recommendation and review semantics remain unchanged. COMPLETE/EMPTY are distinct
from malformed input, incomplete results, cancellation, resource and scoring
errors. Errors do not publish a stale successful result or fall back to bounded.
Completed REVIEW/REJECT does not authorize an operation.

Coverage is limited to the supplied distinct eligible population. It proves no
complete external acquisition, global uniqueness, real-world accuracy or semantic
liveness. `action_permitted=false`; native operation/readback are
**UNSUPPORTED / NOT_RUN** for this candidate. No non-synthetic full acquisition
or operation is delivered; an ordinary preconfigured target workflow is therefore
**NOT ESTABLISHED**. This is not a fully functioning native product.
Historical engineering and strict qualification modes retain their contracts;
neither is offered as a way around the standard input gate.

## 4. Reused evidence, including failures and corrections

| Evidence | Actual recorded result and limits |
| --- | --- |
| Historical AC8 | >=95% of all planned positive pools remains the criterion, with all planned positives completed and coverage reconciled. Original 100/100 Rank-1; 48 ACCEPT / 52 REVIEW; 3/3 independent NO_ACCEPT controls. Correct Rank-1 REVIEW counts as a ranking match, not action permission. Finite synthetic domain only; no new campaign or pooled accuracy. |
| Historical AC9 | 103/103 fixed-case parity and 424 tests; offline worker conversion optimization. Not native acceleration or a new observation. AC2/AC3 FAIL, F1 resource failure, AC7 INDETERMINATE and historical PAIR remain unchanged. |
| PREP-3-R1 CE M6 | Scoped PASS registered by the maintainer. M1 includes maintainer-confirmed full-package/version checks; M2-M4 have direct scoped observations; M5 is maintainer-confirmed without a separately supplied detailed transcript. Codex did not independently observe that session. No transfer to the standard candidate. |
| Standard integration regression | Final **349 passed** for `test_offline_collector_interface.py` and `test_ce_mvp_readonly.py`. Earlier 214, 184, 5, 339, 103, 84 and 1 passed sets overlap; they are not added. Exact commands, deselections and durations remain in the integration delivery. |
| Standard final package smoke | Historical `PASS_STANDARD_PACKAGE_SMOKE`: Python 3.14.3 / Lupa 2.8 / Lua 5.3, six CT syntax blocks and four manual Lua blocks; exact counts/identities, Rank-1 46 versus -36, table-only operation/readback, stop/cleanup, ID2 inertness and ID3 separation. Zero ambient target calls. Not CE-host acceptance. |
| New preparation checks | Only read-only Git/signature/identity, in-memory package rendering/XML and documentation checks. No scorer, fixture, CE host, native target or pytest campaign executed. |

The integration receipt preserves the initial **87 passed / 13 failed** entry
run (input selection and `dofile` test-wiring expectations), and **183 passed /
1 failed** compatibility run (former-default config expectation), followed by
corrected 214/184 passed runs. The four failing identity-substitution regressions
exposed a real AC6 defect, corrected before 339 passed. A later injected NaN probe
exposed ERROR/zero writes but an invalid published COMPLETE; the final row check
fixed that publication defect before **349 passed** and the final package smoke.
These failures are not erased or counted as independent successes. No unresolved
failure is recorded within those completed scoped checks.

The old controlled CE observation of 63 ms and before/after Lua occupancy belongs
only to PREP-3-R1. The standard package's 120 ms observation is **Lupa-only**.
Neither establishes standard-candidate CE UI response, process peak memory,
cancellation latency, hard timeout, native capacity, SLA or semantic liveness.
Those remain UNKNOWN/NOT_RUN as applicable. Existing 256 MiB fixture allocation
and historical 4 GiB Lua / sampled 8 GiB worker / 240 s / 256 MiB output /
512 MiB available host-commit policies retain their original distinct scopes;
none becomes a CE/native service guarantee or a raised product limit.

## 5. Readiness checklist and unresolved gates

Owners identify decision responsibility, not a scheduled task or fresh authority.

| Condition | Source/evidence | Outcome | Owner |
| --- | --- | --- | --- |
| Source, branch and signed history integrity | Section 1; local OpenPGP plus independent GitHub SHA/parent/path/signature reads | ESTABLISHED at the admitted baseline; documentation commits require the same checks | Engineering handoff |
| Exact candidate identity and reproducible preparation | Section 2; existing 13-file manifest, 12 source blobs and same-path rendering | ESTABLISHED; local, path-bound only | Engineering handoff |
| Architecture and explicit input documented | Section 3; standard manual sheet and integration receipt | ESTABLISHED for owned synthetic use; default input gate retained | Engineering handoff |
| Historical synthetic evidence and controlled CE M6 | Section 4; registered AC8/AC9 and M6 | REUSED within original scope; no new results | Maintainer/evidence owners |
| Standard final automated checks | Integration delivery and final manifest | Recorded 349 passed and package smoke; no rerun needed for this documentation change | Engineering handoff |
| Standard candidate CE manual acceptance | Standard manual sheet; manifest `ce_host_manual_acceptance=NOT_RUN` | **NOT_RUN / NOT_ESTABLISHED**; no separately bound acceptance found | Maintainer |
| Actual product effectiveness acceptance | No separately authorized, candidate-bound evidence | **NOT_RUN / NOT_ESTABLISHED**, independent of preparation and CE M6 | Maintainer, arranged independently |
| Non-synthetic standard full input/operation | Integration receipt and current approved scope | **NOT DELIVERED / BLOCKED** for an ordinary real-target product scope | Maintainer scope disposition |
| Strict native qualification | G1-S3 D2.2, R1 and product contract | **NOT ESTABLISHED**; complete <=128 L03 population, unchanged thresholds, exactly one independent qualifier and five zero-write L09 controls retained; synthetic full mode above 128 does not replace them | Qualification owner under separate authority |
| G1 historical live state | Registered algorithm decisions and integration handoff | **0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**; L01 `INDETERMINATE_G1_L01_LAZY_LOAD_QUALIFICATION`, L02-L12 NOT_RUN/PAUSED | Maintainer/qualification owner |
| L12 independent rejection requirements | G1-S3 D2.4 prospective erratum | MISSING/DISABLED/INVALID remain **NOT_RUN/PAUSED**; current INVALID example is 65537/128, not obsolete 129/128. Actual diagnostics, eight zero-activity counters, retained-evidence distinction and restoration still required within their original scope | Qualification owner under separate authority |
| Legacy P4-R2 release prerequisite | Quickstart: manual process-mode test must pass before a separate signed Alpha release decision | **NOT ESTABLISHED for this standard full candidate**; no candidate-bound evidence resolves this distinct prerequisite. Applicability/scope reconciliation remains a maintainer decision, not a waiver or a request to run it | Maintainer |
| Attachment, backend and production gates | Integration/M6 receipts and native contracts | `ATTACHMENT_HANDLE_UNVERIFIED`, `QSG_NATIVE_BACKEND_NOT_QUALIFIED`, `NOT_PRODUCTION_AUTHORIZED`, `IMPLEMENTED_PENDING_CE_QUALIFICATION` all retained | Maintainer/qualification owner |
| Native IPC/activation evidence | Native activation contract | NOT established by synthetic preparation: exact candidate/runtime/host/principal binding, dedicated clean CE startup, handle provenance, bilateral OS identity, DACL/negative permissions, bootstrap, measured timeout/UI/cancel, external watchdog and narrowly authorized cleanup remain separate requirements | Native qualification owner |
| Session and resource protections | R1, G1-S3 D2.3, product and QSG contracts | Existing identity/completeness, per-phase/session write ceilings, exact readback, cancellation, cleanup and mode locks unchanged. R1's aggregate three write attempts, frozen range and 128/128 qualification regime are not raised | Maintainer/qualification owner |
| Other historical decisions | Registered algorithm decisions, quickstart and integration receipt | AC/PAIR, `HISTORICAL_ROOT_CAUSE=INDETERMINATE`, N0/MIN/LOCAL publication suspension, A6/R3 independent T1 pending and historical R2 `T1_FAILED_NOT_QUALIFIED` unchanged; Generation 2 and new liveness/recovery work not opened | Maintainer |
| Maintainer candidate acceptance | Current standard manual sheet and this evidence inventory | **PENDING**, separate from both historical M6 and independent product effectiveness acceptance | Maintainer |
| Release decision and publication authorization | README, quickstart, retained suspension and current preparation scope | **NOT AUTHORIZED / BLOCKED**; no Tag, Release, PR, new branch, distribution or version-field change | Maintainer/release owner |

The registered G1-S3 decisions supersede earlier D2/L12 documentation deferrals
only within their explicit prospective scope. Older runbooks' all-NOT_RUN wording
does not erase the subsequently registered L01 INDETERMINATE. The PREP-3-R1
cooperative-API scope correction does not remove the current missing input
capability or native/publishing obligations. Preparation, a controlled evaluation
candidate, effectiveness acceptance, native qualification and publication are
five separate conclusions.

### Bounded finding for maintainer disposition

**PRE-RELEASE-INPUT-1 — Standard real-target workflow unavailable.** Evidence:
the admitted integration source/receipt and final manifest only offer explicit
`OWNED_SYNTHETIC`; absent input returns `ALPHA_INPUT_REQUIRED`. Impact: any intended
release promising ordinary non-synthetic full acquisition/operation is blocked.
Disposition: record the limitation and leave a later scope/capability decision
to the maintainer. This preparation adds no adapter, launcher, workaround,
native capability, issue, effectiveness campaign or automatic next task.

## 6. Proposed designation, not a tag transaction

Read-only `git tag --list`, HTTPS `git ls-remote` and paginated GitHub tags/releases
lookups found 38 remote checkpoint tags and **zero GitHub Releases**. Relevant
remote names include `ce-mvp-offline-checkpoint-20261123`,
`qsg-synthetic-checkpoint-20261123` and `native-ipc-offline-checkpoint-20261123`.
The 41 local tags also include local-only legacy `debug_tools-beta`, `v0.1.2` and
`v0.1.2_packaged`; they do not establish a current standard Alpha release series.
The Python tooling's `0.1.0` metadata describes that separate tooling package.

**Suggested future nomenclature: `v2.0.0-alpha.1` — controlled synthetic
evaluation candidate.** This is a proposal based on the repository's milestone
examples (`v2.0.0-alpha`, beta, stable), with an explicit first-candidate suffix;
it is not a claimed existing tag convention, an approved version, or a native
product claim. No version field changes. **No new version tag recommended now**:
the candidate acceptance, applicable technical gates and publication decision
remain unresolved. Even a narrower publication needs the maintainer's explicit
decision; this draft does not waive the existing release conditions.

## 7. Handoff validation boundary

Actual checks were read-only repository/status/history and remote identity reads,
OpenPGP verification, the 13-file/12-blob comparison, default in-memory CT render
comparison, XML structure and documentation consistency/link/diff checks. The
existing command for package preparation and historical test commands above are
provenance, not new executions. Historical reports and candidate bytes remain
unchanged. No functional, accuracy, effectiveness, CE or native testing ran.

Each new documentation unit is to be reviewed as its exact diff, checked with
`git diff --check`, staged by explicit path, committed with `git commit -S`,
locally verified and normally pushed over the existing gh-backed HTTPS remote.
The completion receipt binds the actual resulting SHAs, parents, changed paths
and independent GitHub `verified=true / reason=valid` readbacks. This file does
not infer successful publication or delivery from its own presence. Stop at the
preparation handoff; independent effectiveness acceptance remains with the maintainer.
