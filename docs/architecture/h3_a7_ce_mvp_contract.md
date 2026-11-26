# Standard CT product and retained engineering contract

**BLOCKED_G1_ALPHA_PRODUCT_CLOSURE / IMPLEMENTED_PENDING_CE_QUALIFICATION.**
The intended workflow is original configuration -> exact authorized identity ->
authorized acquisition -> AC6/AC5 full evaluation -> guarded admission/operation ->
independent readback -> stop-only monitoring/cleanup. The native workflow is not
established. Existing QSG accepts synthetic provenance only; configuration cannot
supply native authority. Standard admission refuses before acquiring target APIs.

This English contract supersedes the standard-product portions of the
[committed pre-closure contract](https://github.com/k-undurkhaan-2/Chrome_Project/blob/baaed5c0fad4e07e88ef877398c48f62373f8952/docs/architecture/h3_a7_ce_mvp_contract.md).
That revision preserves original engineering design and evidence. Uncommitted
operator edits remain local and are not incorporated into official documents.

## Runtime and integration

Windows x64 / CE 7.6 / Lua 5.3 and the normal prepared src/ce_mvp.local.CT remain
the surface. The singleton loader and CT syntax check are inert until explicit
ID1 Start. One-time Python preparation only binds paths. ID2 reads caches; ID3
is independent and read-only. No new algorithm, GUI, CLI, launcher, native backend
or mandatory application SDK is introduced.

ID1 reads the bound sibling original config. Contract validation, Alpha profile,
safe-default checks and actual adapter admission are separate. Original values
reach ce_mvp_adapter.new with the internal full-evaluation selection. The adapter
refuses QSG_NATIVE_BACKEND_NOT_QUALIFIED when the existing execution dependency
is absent or provenance is not synthetic. config_application=NOT_APPLIED is
therefore correct on native refusal; passing values to admission is not execution.

The table selector remains compatibility/test-only and is never implicit.
Engineering retains its bounded adapter; qualification retains its factory and
strict rules. Neither is a standard fallback. Config cannot inject callbacks,
factories, providers or writers.

## State and ownership

For an admitted Alpha run, the existing core follows:

```text
STOPPED -> ATTACHING -> SCREENING -> CANDIDATE_CHECK -> WRITING
                                                       |
                                                       v
                                                   READBACK -> MONITORING
terminal error / observed invalidity -> ERROR + cleanup
explicit operator Stop -> STOPPED + cleanup
```

ALPHA_STOP_ONLY also stops on EMPTY with ALPHA_STOP:NO_CANDIDATE. No automatic
rescan, reselection, reattachment, restart or restore occurs. A new explicit Start
requires confirmed cleanup and creates fresh caches. Running/cleanup locks precede
new config reading/resource acquisition; uncertain cleanup remains poisoned.

One 50 ms timer drives the core. Reentrant entry is terminal. Scan callbacks mark
completion only. Stop revokes operations, destroys its timer, removes callback,
disposes owned FoundLists/MemScan and closes only owned query/scratch resources.
It never closes CE's borrowed handle. Uncertain disposal is not retried blindly.
Native destruction may block; no measured latency, hard timeout or UI SLA exists.
Engineering alone retains bounded backoff, retirement, retry limits and configured
invalid confirmations.

## Process binding

The existing adapter opens the exact configured numeric PID with query/synchronize
rights 0x101400. GetProcessId, creation FILETIME and WaitForSingleObject correlate
the owned query handle and CE-reported handle. PID/handle selection is checked
around observations, each tick and before guarded memory operations. Missing
APIs, invalid/backward clocks, identity changes, exit and uncertainty reject.

This is sampled local consistency, not independent kernel-object equality,
an atomic target lock or semantic identity. Races, switch-away/back and
indistinguishable reuse remain limitations. ATTACHMENT_HANDLE_UNVERIFIED remains.
A configured PID establishes neither ownership nor authority. No native binding
was performed or qualified for this candidate.

The original CE-local Win32 bridge, GetSystemInfo process envelope, exact Dword
bit-pattern discovery, alignment 4, +W-X-C and mapping eligibility are retained.
No process-name discovery, target injection, privilege expansion, driver fallback
or replacement native implementation is added.

## Single candidate policy

Standard design retains Single scoring semantics with full supplied distinct
eligible evaluation through AC6/AC5. It never uses a large-budget bounded
approximation or independent batch winners.

The shared adapter now snapshots every admitted owned FoundList index using
existing guarded readers, mapping checks and structural words. It rechecks
observed source indices/addresses/counts before and after scoring, and invokes
the existing full overload. Missing reads, mapping changes, incomplete scan
evidence, changed identities, cancellation or invalid envelopes stop with zero
operation. AC5 reconciles identical duplicates and rejects conflicting duplicates
or words. Historical bounded native duplicate rejection is unchanged.

Only the existing QSG synthetic construction currently admits this bridge.
Its frozen 128/128 qualification limits remain binding: above-limit input fails
before scoring, without truncation or increased limits. This is not a qualified
arbitrary-size native full service. Ordinary process-scope product admission is
still blocked.

A scan callback or readable list does not establish native terminal success or
complete acquisition. Configured scope, observed list completeness and supplied
full scoring are separate. acquisition_complete remains false. The bridge's
SYNTHETIC_SCAN_OBSERVATIONS_ONLY and the selector's SUPPLIED_RECORDS_ONLY explicitly
state provenance; neither establishes independently complete native acquisition.

Existing common context, feature extraction, family adjustments, comparator,
ties, confidence, recommendation and report remain unchanged. Full completion
requires supplied=distinct+duplicates, distinct=eligible+excluded and
eligible=selected=fully_scored=ranked plus exact membership reconciliation.
Legal EMPTY differs from failure. Completed REVIEW/REJECT denies operation.
No stale completion, fabricated coverage or bounded fallback is allowed.

Strict QSG retains complete scoped evidence and exactly one independent qualifier.
Its historical global_uniqueness_proven field describes its scoped synthetic
admission contract, not a new global/native claim. NORMAL's scoped ACCEPT remains
engineering-only. Rank-1 or ACCEPT is never permission.

## Float32 transaction and monitoring

Standard full construction cannot acquire NORMAL's unqualified raw writer.
The existing guarded QSG port retains reservation/claim, exact identity/candidate,
phase/session ceilings, scope rechecks, revocation and independent target readback.
The legacy Full A/W/B executor is not substituted and no evidence is fabricated.

One operation attempt is followed immediately by integer-bit and Float32 readback
in the same tick. Only Boolean true is API success; both readback forms must match
the exact rounded write bits. Cached operation_status, readback_status and
monitor_status are independent. API_SUCCEEDED is not VERIFIED; absent/non-finite
readback is FAILED, disagreement MISMATCH and an exception ATTEMPTED_UNCONFIRMED.
No automatic rollback follows uncertainty.

The unchanged monitor checks mapping/allocation, seven structural words and a
readable finite Float32. Finite drift alone remains allowed. Alpha stops on the
first observed failure; engineering keeps its own confirmation/recovery rules.
No semantic-liveness or freeze algorithm is introduced.

## Configuration and optional engineering interfaces

The [canonical inventory](../ce_mvp_quickstart.md#original-configuration-contract)
documents every original field, safe defaults, optionality and incompatibility.
Returned public-template data is unchanged. Bounded scope and L10 cleanup probe
remain incompatible with standard Alpha. Recovery fields are engineering-only;
full scoring receives no count-budget truncation. Independent qualification
ceilings still bind. Logging and diagnostics remain bounded/private.

Empty-environment Lua evaluation is a trusted-data convention, not an untrusted
sandbox or hard execution limit. Unknown executable/provider fields reject.
Invalid/blocked selection latches; cleanup uncertainty cannot be bypassed by
new config or singleton reload.

## Observation, qualification and evidence

ID2 is cached and inert, separating configuration/application, acquisition,
evaluation, recommendation, operation/readback, terminal reason and cleanup.
Original-config status sanitizes private identifiers/values/log errors.
evidence() is a separate private diagnostic snapshot. Standard native operation
and readback remain NOT_RUN; model activity remains labelled synthetic.

[AC5-AC9 decisions](../algorithm_a_offline_scoring.md),
[QSG contract](../qualification/h3_a7_q1_qsg_contract.md),
[R1 plan](../ce_mvp_q1_r1_plan.md) and
[M6 registration](../../reports/2026-11-26/g1-alpha-prep-3-r1-manual-acceptance.md)
retain original candidates and authority. M6 is only the recorded PREP-3-R1
synthetic CE-host acceptance. AC8 100/100, AC9 and AC/PAIR are historical, not
new observations. G1 remains 0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN.

ATTACHMENT_HANDLE_UNVERIFIED, QSG_NATIVE_BACKEND_NOT_QUALIFIED,
NOT_PRODUCTION_AUTHORIZED and IMPLEMENTED_PENDING_CE_QUALIFICATION remain.
L01/L12, original resource limits, A6/R3 independent qualification, N0/MIN/LOCAL
suspension and P4-R2 applicability/acceptance remain separate. Historical R2
T1_FAILED_NOT_QUALIFIED is unchanged.

A missing application exporter is not a mandatory prerequisite. The concrete
blocker is absence of an independently qualified, authorized native
identity/acquisition/execution facility within existing scope. This task grants
no new live testing authority. Effectiveness acceptance belongs to the maintainer;
no follow-up is scheduled. No version field, Tag or Release changes.
