# G1-ALPHA-F01-R1 configuration contract correction and verification receipt

> Historical evidence only; not current operating instructions. Original recorded values and authority are unchanged. [Immutable original](https://github.com/k-undurkhaan-2/Chrome_Project/blob/baaed5c0fad4e07e88ef877398c48f62373f8952/reports/2026-11-26/g1-alpha-f01-r1-delivery.md). Current product guidance: [English Quickstart](../../docs/ce_mvp_quickstart.md).

Scoped status: **READY_G1_ALPHA_F01_R1_CONFIG_CONTRACT_ACCEPTANCE**.
Actual standard product readiness: **BLOCKED**; F01 product completion is **OPEN**.
Maintainer acceptance is separate. CE-host acceptance, real-target effectiveness,
native operation/readback and native qualification are **NOT_RUN / NOT_ESTABLISHED**.

The original configuration is recognized through the ordinary ID1 entry. Its
applicable parameters reach the existing explicitly selected owned table consumer.
No external target consumer was added. This result is more than parser admission,
but the table consumer is not evidence that the actual standard product works.
The prior F01 receipt remains valid evidence for its narrower selection seam.

## Authority, baseline and decisions

Authority is the maintainer's complete F01-R1 corrective specification and explicit
implementation/sign/push request. Existing repository and branch are
`k-undurkhaan-2/Chrome_Project`, `armedforces.io-v2`.
Initial local HEAD, independent GitHub API HEAD and HTTPS remote ref all matched
the specified reference `9574ef9b83b29e603d1e067486f846a1c4bad59f`.
The initial index was empty. The original example's Git blob matched
`46b80ccfc4164025778cb5e527202cd8ff1f30c8`.

The specification, actual example, original validator/core, loader, adapter,
standard CT and preparation tool, existing architecture/qualification constraints,
F01 delivery, INTEGRATION-1, PRE-RELEASE-PREP-1 and historical M6 records were read.
Existing user edits and local outputs were preserved. They were not interpreted
as new authority or included in staging.

Implementation decisions within the corrective scope:

- Share the original validator rather than introduce another product schema.
  `validate_contract` recognizes PID 0 / boolean false as safe data placeholders;
  the original executing `validate` and `core.new` still require a positive PID
  and enabled operation intent, with their original rejection order.
- Keep the original example's entire returned data unchanged; amend comments only.
  Standard configuration uses the existing sibling local filename and original
  fields. Optional existing `input_source` selection is extracted by the standard
  loader before invoking the shared validator.
- Bind explicit `OWNED_SYNTHETIC` only to the existing fixed table identity 101.
  Pass the original config to that consumer, including search options to AC6.
  Never replace parameters with fixture defaults, rebind a different PID, rewrite
  supplied records to fit search values, or silently select synthetic input.
- Keep the old three-field selector and explicit API routes for compatibility;
  report `FIXTURE_DEFAULTS_ONLY` so they cannot represent original product settings.
- Classify historical count budgets and recovery/confirmation settings as
  engineering-only. Reject bounded address scope and the L10 cleanup probe as
  standard-profile conflicts. Preserve Alpha first-fault Stop and no recovery.
- Report file recognition, contract validation, profile compatibility, application,
  capability and execution conditions independently. `config_admission=ACCEPTED`
  is not execution permission. ID2 returns cached applicability labels without
  private PID/address/value/token/log-path/event disclosure or target activity.

No algorithm, score/ranking rule, native discovery/acquisition, writer, GUI, CLI,
SDK, framework, resource ceiling or authorization change was introduced.

## F01.1–F01.7 reconciliation

| Requirement | Correction and observed evidence | Scoped outcome |
| --- | --- | --- |
| F01.1 bound config recognition | Ordinary ID1 reads only its sibling config at explicit Start. Original fields and nested tables now reach the shared validator. Missing/unreadable, syntax/evaluation and unknown-field cases remain distinct. | PASS, original contract recognition; real runtime separately blocked |
| F01.2 public contract | Original returned data compares equal to the specified starting blob, including PID 0 and writes false. The three-field example is labelled historical synthetic selection, not the product contract. Full field inventory and actual consumer limits are in the Chinese guide. | PASS |
| F01.3 ordinary entry and effective application | Actual default generated CT scripts, with no preceding selection API call, admitted a complete original config explicitly selecting the owned table environment. Observed write/readback 137.25, 250 ms monitoring, changed search filtering, configured timeout, bounded diagnostics/logging and full 3-member ranking despite count budgets 1/1. | PASS in existing owned Lua test environment; CE-host NOT_RUN |
| F01.4 safe refusal and capability distinction | Safe template reports ORIGINAL / VALID / ACCEPTED but NOT_APPLIED / BLOCKED_SAFE_DEFAULT. Positive PID and true intent without an input consumer report ALPHA_STANDARD_INPUT_UNAVAILABLE. Wrong synthetic identity, unsupported input and profile conflicts block before adapter construction. Invalid original fields use original validator codes. | PASS; no target/fixture/scoring on rejected admission |
| F01.5 inert, sanitized ID2 | Status snapshots changed no config-read, scoring, open/read/write/scan, diagnostic or log-file counters. Copies cannot mutate applicability. Private sentinels, configured values, event bodies, budgets and OS/path errors are absent from original-config status. | PASS |
| F01.6 engineering/qualification and cleanup | Original executing validation remains unchanged; selected engineering, strict QSG, explicit selection precedence, latch, stale-result, Stop and cleanup-uncertain regressions passed. ID3 stays independent and read-only. | PASS within existing safe doubles; no native qualification |
| F01.7 preservation | 31 pre-existing inventoried files, including installed private config/CT, retained their initial sizes and SHA-256 identities. Historical F01, INTEGRATION-1 and PREP-3-R1 packages retained all 15 + 13 + 13 manifest identities. Private/config/generated evidence was excluded from commits. | PASS |

The original contract has no `schema` or `mode` requirement. A safe placeholder is
structurally recognized yet cannot execute. Original settings with no approved
consumer remain unapplied; they are not rejected merely for being absent from
the old three-field selector. Non-operative engineering fields are reported as
such instead of being silently claimed effective.

## Product readiness and residual consumers

| Requirement / feature | Existing consumer and this correction | Remaining dependency / disposition |
| --- | --- | --- |
| F01 target identity and configured scanning | Original PID/range/type/search semantics validated. Fixed synthetic identity and search bits are checked in the owned model. No native target is attached by standard admission. | **OPEN/BLOCKED:** standard external input/identity/acquisition consumer is unavailable. Positive PID is not evidence of identity or access authority. |
| F01 configured operation, monitoring, logging and diagnostics | Applicable values reach the existing model's original core/adapter; file logging and passive diagnostics are verified only for that explicit environment. Historical invalid-confirmation and recovery knobs remain engineering-only. | **OPEN at product level:** actual standard operation and monitor consumers require F02–F04 and retained gates. No blanket product PASS. |
| F02 complete supplied candidate population handoff | Existing AC6 full membership/scoring path preserved; budgets 1/1 do not truncate the 3 supplied eligible records. | **OPEN:** real standard input population and its complete handoff are not delivered or accepted. No new discovery or research stage was authorized. |
| F03 readback/monitoring failure stop | Existing stop-only, readback, cleanup and uncertain-restart protections retained. The model stops on first detected mapping failure even with invalid_confirmations=20. | **OPEN:** actual runtime consumer and its readback/monitoring failure semantics and acceptance remain missing. Model fault handling does not establish real-target liveness. |
| F04 authorized automated operation/readback | Existing table operation and original QSG writer contracts preserved. No native writer activated. | **BLOCKED:** qualified standard native operation consumer, independently verified identity/attachment and explicit operation authorization remain required. |
| Ordinary CE entry and installation | Original config loading via default CT is verified in Lua 5.3/Lupa; path binding and no recurring Console selection hold there. Installed private config and CT were not overwritten. | **CE-host NOT_RUN:** no new host/manual/effectiveness acceptance or claim that the table simulator advances as a real product. |
| Qualification / release | Existing four blocking statuses and historical evidence remain unchanged. | **BLOCKED/NOT_AUTHORIZED:** attachment proof, native backend qualification, production authorization, applicable P4-R2 prerequisites and separate maintainer release decision remain. |

Retained statuses are `ATTACHMENT_HANDLE_UNVERIFIED`,
`QSG_NATIVE_BACKEND_NOT_QUALIFIED`, `NOT_PRODUCTION_AUTHORIZED`, and
`IMPLEMENTED_PENDING_CE_QUALIFICATION`. G1 remains
**0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**. N0/MIN/LOCAL publication
suspensions, AC/PAIR decisions, resource limits and historical M6 scope are not
upgraded. A missing application-side cooperative API is not invented as a new
prerequisite; the actual missing standard input/operation consumers are the blockers.

## Focused verification, commands and failure history

Environment: Windows x64, existing `.venv`, Python **3.14.3**, pytest **9.1.0**,
Lupa **2.8**. Entry tests use real Lua **5.3**; selected core/engineering tests also
use Lua **5.4**. The existing 256 MiB allocator limit remains. These are owned
tables and safe doubles, not CE-host observations or native operations.

Commands ran from `D:\armedforces.io-v2`. `P` below means the exact command prefix
`& '.venv/Scripts/python.exe' -m pytest -q`; `R` means
`reports/2026-11-26/g1-alpha-f01-r1-local`. Each row gives its literal suffix.
Raw runtime logs and JUnit output remain in ignored local directories.

| Run | Command suffix after P | Observed result / exit |
| --- | --- | --- |
| Baseline | `tests/test_ce_mvp_readonly.py -k 'f01 or standard_default' --basetemp=reports/2026-11-26/g1-alpha-f01-r1-local/baseline --junitxml=reports/2026-11-26/g1-alpha-f01-r1-local/baseline.xml` | 36 passed, 105 deselected, 2.96 s; shell exit not separately retained |
| Initial entry | `tests/test_ce_mvp_readonly.py --basetemp=reports/2026-11-26/g1-alpha-f01-r1-local/entry-1 --junitxml=reports/2026-11-26/g1-alpha-f01-r1-local/entry-1.xml` | JUnit: 140 passed, 1 failed, 12.636 s; final shell exit not captured |
| Expanded entry | `tests/test_ce_mvp_readonly.py --basetemp=reports/2026-11-26/g1-alpha-f01-r1-local/entry-2 --junitxml=reports/2026-11-26/g1-alpha-f01-r1-local/entry-2.xml` | 173 passed, 1 failed, 12.36 s; exit 1 |
| Initial compatibility | `tests/test_h3_a7_ce_mvp.py -k 'portable or actual_loader or loader_is_inert or config_rejects or alpha_stop_policy or cleanup_uncertainty_blocks_restart or strict_missing_policy' --basetemp=reports/2026-11-26/g1-alpha-f01-r1-local/compat-1 --junitxml=reports/2026-11-26/g1-alpha-f01-r1-local/compat-1.xml` | 129 passed, 1 failed, 801 deselected, 2.36 s; exit 1 |
| Final compatibility | `tests/test_h3_a7_ce_mvp.py -k 'portable or actual_loader or loader_is_inert or config_rejects or alpha_stop_policy or cleanup_uncertainty_blocks_restart or strict_missing_policy' --basetemp=reports/2026-11-26/g1-alpha-f01-r1-c --junitxml=reports/2026-11-26/g1-alpha-f01-r1-local/compat-2.xml` | 130 passed, 801 deselected, 2.97 s; exit 0 |
| Strict QSG | `tests/qualification/test_qsg_integration.py::test_public_loader_start_stop_latches_and_preserves_cleanup_probes tests/qualification/test_qsg_acceptance.py -k 'public_loader or mandatory_plugin or qualified_public_l12 or stale_timer_and_direct_adapter' --basetemp=reports/2026-11-26/g1-alpha-f01-r1-q --junitxml=reports/2026-11-26/g1-alpha-f01-r1-local/qsg-1.xml` | 14 passed, 66 deselected, 8.84 s; exit 0 |
| Final entry | `tests/test_ce_mvp_readonly.py --basetemp=reports/2026-11-26/g1-alpha-f01-r1-e3 --junitxml=reports/2026-11-26/g1-alpha-f01-r1-local/entry-3.xml` | 177 passed, 29.97 s; exit 0 |

Actual corrections, without hiding unsuccessful checks:

1. The first entry failure was the old expectation that an incomplete original
   table `{target_pid=101,write_enabled=true}` must be an unknown synthetic field.
   It now reaches the original validator and rejects `UNSUPPORTED_PROFILE`.
   That obsolete expectation was removed and original-contract invalid/missing/
   nested-field checks were added. No runtime gate was relaxed to pass it.
2. The new consumer observation hook initially read the first argument of
   `mvp0_offline_scoring.run(records, options, load_module)` as options. The test
   hook was corrected to observe the second argument. Actual 137.25 operation
   and full ranking had already been observed before that assertion failed.
3. The first compatibility temporary directory was long enough for the unchanged
   240-character engineering startup error limit to truncate the filename that
   an old test matches. Repeating that same suite in the shorter ignored path
   passed. No production error length or engineering behavior was changed.

Final selected pytest suites contain **177 + 130 + 14 = 321 distinct cases**.
The baseline and unsuccessful iterations overlap and are not added to that count.
No broad repository suite, new native campaign, historical accuracy/effectiveness
campaign or maintainer test was run or scheduled. Lint was not run separately.

Additional completed read-only checks used the existing Python interpreter with
inline scripts: public-template Lua data equality against the starting Git blob;
eight protected source/template blobs unchanged; 31 pre-existing file identities
preserved; three historical package manifests verified (41 files); original-field
inventory/document links; and maintained file/commit identities. The local
`R/verify_handoff.py` records the final reproducible handoff checks and emits the
local receipt. `git diff --check` and exact staged-path review passed per unit.
No installed private value is printed or included in the published report.

Initial sandbox read-only discovery included an HTTPS credential-context failure
and inaccessible historical-output paths. Remote baseline verification was
repeated successfully on the already authorized standard host; tracked-file
inventory replaced the broad history search. These were local inspection issues,
not product failures, new authorizations or reasons to change credentials.

## Signed chain and source identities

Implementation commit: **`41a0a47ee2515eeaa7531f1f67d80307448f69fe`**.
Parent: **`9574ef9b83b29e603d1e067486f846a1c4bad59f`**.
Message: `fix(mvp0): restore original Alpha configuration contract`.

Exact seven-path staged diff was reviewed and checked before `git commit -S`.
`git verify-commit HEAD` returned Good signature with the unchanged key
`86D51BCDBC946CF1389969D530479D840D9D562B`.
Normal `git push origin HEAD:refs/heads/armedforces.io-v2` succeeded through the
existing gh-backed HTTPS setup. Before any subsequent source/document mutation,
independent `gh api repos/k-undurkhaan-2/Chrome_Project/commits/armedforces.io-v2`
and `git ls-remote origin refs/heads/armedforces.io-v2` confirmed the exact SHA,
single parent, exact changed paths and **verified=true / reason=valid**.
The standard host SID matched `S-1-5-21-1353174265-123074972-3048594297-1001`.

| Implementation path | Maintained Git blob |
| --- | --- |
| `src/ce_mvp.lua` | `88a02c09043946964f23aec0ee1b973e0c15627b` |
| `src/ce_mvp_core.lua` | `bb5d37213439dccc0493f6ab9c153786b9c84f7a` |
| `src/ce_mvp_adapter.lua` | `24eae701bde39287d114e0ff41c8647d1cc4722b` |
| `src/ce_mvp_config.example.lua` | `d21e7d2271a2fd70abd85a5a030f5e2629481fe3` |
| `src/ce_mvp_alpha_config.example.lua` | `7ab9570993a590a7734f4a39a6d3c51bd07b90bf` |
| `src/prepare_ce_mvp.py` | `13d4725d20492541a8ba3ac07f0d1a380fe73a94` |
| `tests/test_ce_mvp_readonly.py` | `58533994c70bd2171bb7a0292695e15f925c23c8` |

The final independently committable handoff unit contains this report,
[`docs/g1_alpha_f01_r1_config_zh.md`](https://github.com/k-undurkhaan-2/Chrome_Project/blob/baaed5c0fad4e07e88ef877398c48f62373f8952/docs/g1_alpha_f01_r1_config_zh.md) and
the README pointer. Its parent is the implementation commit above. It uses the
same exact-diff review, focused document checks, immediate signing, local
verification, normal push and independent remote SHA/parent/path/signature
readback. The final response and ignored local
`reports/2026-11-26/g1-alpha-f01-r1-local/verification-receipt.json` bind that
unit's actual SHA, final local/remote HEAD and complete two-commit linear chain,
avoiding a self-referential hash inside this committed report.

No new packaged candidate was generated for delivery. Existing installed and
historical CT files are retained. Temporary isolated CT/config copies were used
only by the focused tests, with public-template or explicit test-data provenance;
none is presented as the actual product. No Tag, Release, PR, new branch,
automation, publication authorization or follow-on F02–F04 implementation exists.
**No new version tag recommended:** actual product prerequisites remain open.
Stop after this corrected F01-R1 handoff.
