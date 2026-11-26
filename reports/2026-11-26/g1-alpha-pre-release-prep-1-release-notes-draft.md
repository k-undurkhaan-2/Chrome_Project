# DRAFT release notes — standard Alpha controlled synthetic evaluation candidate

**DRAFT / UNPUBLISHED / NOT RELEASE-AUTHORIZED.** Prepared 2026-11-26 for
maintainer review under G1-ALPHA-PRE-RELEASE-PREP-1. Release eligibility is
**NOT ESTABLISHED**; Alpha Pre-release remains **BLOCKED**. These notes do not
announce a release, distribute a package or authorize operation on a real target.

Proposed future designation: **`v2.0.0-alpha.1` — controlled synthetic evaluation
candidate**. This is a naming suggestion, not an existing or approved tag.
The repository's milestone examples and read-only tag/release lookup are recorded
in the [readiness inventory](g1-alpha-pre-release-prep-1-readiness.md).
No tag, Release or version-field update is recommended for this handoff.

## Candidate covered by this draft

| Item | Binding |
| --- | --- |
| Repository / branch | `k-undurkhaan-2/Chrome_Project` / `armedforces.io-v2` |
| Final executable source | `6190a9f93ec72560ca5db5e616bc4cd411795efc` |
| Original final handoff | `603f3b420e7fefe027981aa64f6c2f0d2a7c7e7e` |
| Existing local candidate | `D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-integration-1-manual-final` |
| Generated CT | `src/ce_mvp.local.CT`, 3003 bytes |
| CT SHA-256 | `023ed8e3d1a41841b3f22e826a55f2e23f3860d2ef73c6859079123d4797f4d6` |
| Full inventory | [Existing 13-file identity manifest](g1-alpha-integration-1-file-identities.json), including 12 exact maintained Git blobs |

The earlier `g1-alpha-integration-1-manual` package is superseded. The historical
PREP-3-R1 package has a separate identity and scoped manual acceptance. Neither
can replace this candidate. The generated CT embeds the fixed installation path;
its hash does not identify a portable package for another location.

## Delivered behavior described by these notes

These features were already delivered by standard integration; pre-release
preparation introduces **documentation only** and preserves runtime behavior.

- Standard ID1 defaults to `ALPHA_STANDARD` / `ALPHA_FULL`. Input must be selected
  explicitly before Start. Without an allowed input, `ALPHA_INPUT_REQUIRED`
  fails closed before dependent configuration/module/target activity.
- The implemented standard input source is the existing `OWNED_SYNTHETIC` table
  fixture. AC6/AC5 evaluate all supplied distinct eligible records together with
  the original scorer, common cohort, ordering, confidence and recommendations.
  Full completion validates both count equations and exact identity membership.
  Invalid returned scores or hard-pass fields cannot publish a successful result.
- ID1 retains existing admission, simulated operation/readback, monitoring and
  cleanup checks. `ALPHA_STOP_ONLY` stops on detectable failure; no automatic
  reselection, rescan, reattachment or restart. A new run requires explicit Start.
- ID2 observes cached status, counts, identity reconciliation, ranking, provenance
  and gates. Scan address scope is distinguished from full scoring population.
  ID2 does not trigger evaluation or target activity.
- ID3 remains an independent, explicit, one-shot read-only synthetic example.
  It is neither a prerequisite nor an implementation dependency for ID1.

## Supported installation and controlled use

The documented environment is **Windows x64, CE 7.6 and Lua 5.3**, with
**No Process Selected** for the existing owned synthetic procedure. Reuse the
fixed candidate after verifying all 13 file identities. Python was used only
for offline preparation; no new launcher, installer, SDK or target application
is required for the documented controlled use.

See the [Chinese installation and controlled-use guide](../../docs/g1_alpha_pre_release_controlled_use_zh.md)
and its authoritative [standard manual sheet](../../docs/g1_alpha_integration_1_manual_acceptance.md).
Those documents describe the existing approved scope; this draft does not start
or schedule another manual or effectiveness campaign. Keep the CT in its bound
directory and preserve historical outputs. No ZIP or distributable asset is
produced; review uses the manifest and documentation. Private configuration,
credentials, keys, real target identifiers, raw logs and unrelated untracked
files are excluded.

## Evidence reused, not newly executed

- The [standard integration receipt](g1-alpha-integration-1-delivery.md) records
  the final **349 passed** interface/entry regression and
  `PASS_STANDARD_PACKAGE_SMOKE` under Python/Lupa with genuine Lua 5.3.
  Earlier 214, 184, 5, 339, 103, 84 and 1 passed sets overlap and are not summed.
  Original failures, fixes and retests remain in that receipt and the readiness
  inventory; this draft does not erase them or claim new test executions.
- [Historical M6](g1-alpha-prep-3-r1-manual-acceptance.md) is
  `PASS_G1_ALPHA_PREP_3_R1_CONTROLLED_MANUAL_ACCEPTANCE` only for its bound
  PREP-3-R1 source/package. It does not accept this newer standard candidate.
- AC8's >=95% planned-positive threshold, original finite-domain 100/100 Rank-1
  and separate 3/3 NO_ACCEPT controls are retained. AC9, AC/PAIR and G1 evidence
  retain their original scope. No new accuracy estimate or campaign is claimed.
- This preparation checked signed history, independent remote identity, the
  existing file set/hashes/source blobs, in-memory same-path CT rendering/XML,
  document links and diffs. It ran no CE host, native target or functional suite.

## Known limitations and remaining release gates

**Only the owned synthetic standard full path is delivered.** Non-synthetic full
acquisition/operation and an ordinary preconfigured target workflow are not
established. This candidate is not a fully functioning native product. Full
coverage refers only to the supplied distinct eligible population; it does not
prove external acquisition completeness, global uniqueness or real-world
effectiveness. No engineering-mode alternative bypasses the standard input gate.

`action_permitted=false`. Native operation/readback are **UNSUPPORTED / NOT_RUN**.
Scoring ACCEPT, correct ranking and simulated readback confer no target authority.
Current-candidate CE manual acceptance and independent product effectiveness
acceptance remain **NOT_RUN / NOT_ESTABLISHED**. The maintainer arranges the
latter independently; no automatic follow-up is created.

The following remain separate from preparation completion:

| Outstanding condition | Release implication |
| --- | --- |
| Maintainer acceptance of the exact standard candidate | Pending; historical M6 and this documentation handoff do not substitute |
| Independent actual product effectiveness acceptance | Not established; no evidence or outcome is invented |
| Native input capability, strict qualification and authorization | Not established; a real-target product scope remains blocked |
| Legacy P4-R2 manual release prerequisite | Retained; its applicability and candidate binding are unresolved by this synthetic handoff, not waived |
| Publication suspension and separate release decision | N0/MIN/LOCAL suspension remains; no Tag/Release/distribution authorization |

`ATTACHMENT_HANDLE_UNVERIFIED`, `QSG_NATIVE_BACKEND_NOT_QUALIFIED`,
`NOT_PRODUCTION_AUTHORIZED` and `IMPLEMENTED_PENDING_CE_QUALIFICATION` remain in
force. G1 remains **0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**. L01/L12,
the prospective L12 erratum, strict bounded qualification, exact readback,
resource/cancellation/cleanup protections, historical AC/PAIR and Generation 2
decisions are unchanged. The [complete gate inventory with sources and owners](g1-alpha-pre-release-prep-1-readiness.md#5-readiness-checklist-and-unresolved-gates)
governs these qualifications; this draft supplies no waiver.

No standard-candidate CE UI responsiveness, process peak, cancellation latency,
hard timeout, native capacity/SLA or semantic-liveness guarantee is established.
Historical PREP-3-R1 CE measurements and standard-package Lupa timings retain
their distinct provenance and cannot be promoted into those claims.

**Maintainer disposition remains outstanding.** The prepared documents can be
reviewed as an engineering handoff while release eligibility remains blocked.
No runtime change, Tag, Release, PR, new branch, artifact publication or future
task is created by these draft notes.
