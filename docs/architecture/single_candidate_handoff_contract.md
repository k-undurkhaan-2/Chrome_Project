# Single candidate handoff contract (H1)

H1 exports a proposal from a completed blind Single screening run. It grants no
permission to write, supplies no process identity, and is not restore evidence.
The record is not cryptographically authenticated. A rank of 1, `HIGH` confidence
or an `ACCEPT` recommendation never establishes correctness or write readiness.

## Activation and isolation

`single_handoff_enabled` defaults to the literal boolean `false`. The runner
reads it from the same local configuration load already used by the batch.
Only literal `true` and `false` are accepted; numbers and strings are errors.
The option is effective only for `validation_profile="single"`. Single still
requires `execution_mode="disabled"` and `write_enabled=false`, with incompatible
settings rejected before collection. Full, Quick and `restore_only` ignore a
valid boolean H1 flag and retain their existing execution/output paths.

An enabled Single run uses its existing one `no_probe_A` collector invocation,
ranking and snapshots. H1 adds no process-memory reads or writes. The pure
`mvp0_single_handoff.lua` module receives the finalized summary and candidate
result after `single_blind_view`. It selects a fixed whitelist of fields and
does not consult oracle/truth labels, the expected address, the executor, or
external state. Search float/pattern values describe search inputs, not truth
labels or requested write values.

## Version 1 record

The companion is `<batch>__<session>__<case>__single_handoff.txt`, exclusively in
the runner's configured `log/auto_output` directory. Text is deterministic
`key=value` data in a fixed order with CRLF line endings. Its fixed fields include:

| Field | Value or meaning |
| --- | --- |
| `handoff_schema_version` | `1` |
| `handoff_kind` | `single_candidate_proposal` |
| `authorization_status` | `NOT_AUTHORIZED` |
| `handoff_write_ready`, `write_attempted`, `baseline_eligible` | Always `false` |
| `source_batch_id`, `source_case_id`, `source_session_id` | Exact run identities |
| `source_mode`, `source_validation_profile` | `no_probe_A`, `single` |
| `source_log_filename` | Exact emitted Single log basename; no absolute path |
| `source_log_size_bytes` | Byte count of the closed and verified source log |
| `run_valid`, `failure_class`, `error` | `true`, `nil`, `nil` for a published proposal |
| `probe_full_foundlist` | Always `false` |
| `candidate_rank`, `candidate_address`, `candidate_count` | Rank 1, canonical uppercase hex address, ranking count |
| `best_score`, `second_score`, `score_gap` | Existing ranker values; never authorization |
| `confidence`, `recommendation` | Existing supported labels, only when present |
| `search_target_float`, `search_target_pattern` | Available search inputs; pattern is eight-digit uppercase hex |
| `operator_process_identity_verified` | Always `false` |
| `session_identity_note` | Internal session label does not identify a Windows process instance |
| `independent_review_required` | Always `true`, including ties and `ACCEPT` |
| `next_action` | `independent_candidate_and_process_verification` |
| `warning`, `authentication_note` | Not a write grant; no live write can be triggered; not authenticated |

Unavailable required numeric fields are written as `nil`, not zero. Optional
confidence/recommendation labels are omitted when absent. Malformed present
values reject the proposal. Integers retain exact decimal digits; floating-point
numbers use 17 significant digits. At least one search input must be available;
if both exist, the float's Float32 representation must equal the pattern. NaN,
infinity, nonintegral patterns and nonfinite Float32 representations are rejected.

The best object must be the first ranking object, rank positions must be dense
and correct, addresses unique and positive exact integers within the existing
executor's safe numeric address range, and scores finite and sorted. The summary
must match the result's best address, scores, gap and confidence. When present,
the gap must agree with the ranker, and the recommendation must refer to that
same best object. No new statistical confidence threshold is introduced.

Identity tokens must remain unambiguous under the existing filename normalization
rules: start with an ASCII letter/digit, contain only ASCII letters/digits,
hyphens and single underscores, have no trailing underscore, no `__` delimiter,
no `nil` sentinel, and at most 80 characters each.
Ambiguous identities are rejected, not silently remapped into another record.

## Publication and failures

Opted-in Single output uses a Windows-specific no-replace publication path:

1. Check the final basename and fail closed on an existing or unreadable path.
2. Reserve `<filename>.pending` with exclusive directory creation under the
   same output directory; never reuse an existing reservation.
3. Write `content.tmp`, check write/close results, reopen and compare exact bytes.
4. Rename to the final path using Windows CRT `rename`, which refuses an existing
   destination, including a destination created after the initial check.
5. Remove only this invocation's staging file and empty reservation directory.

The Python/Lua synthetic suite qualifies the actual Windows rename and mkdir
behavior in an external temporary directory, in addition to an in-memory
filesystem with injected collisions and I/O faults. Other platforms or missing
publication APIs fail closed. A crash can leave a `.pending` reservation; it is
not a published artifact and is never automatically reused or cleared by a later
run. Preservation of existing evidence takes priority over retrying publication.

The original Single log must be successfully published before building evidence.
The batch summary and diagnostic report must also be successfully published
before the companion is published. Their validation section records
`VALIDATED_PENDING_OUTPUT` or `REJECTED`; it does not claim publication success.
Final console output reports `PUBLISHED_NOT_AUTHORIZED` or `REJECTED`, with
the safe source log basename and separate source-log, summary, diagnostic and
handoff failure codes. Failed or
partial staging never becomes a final companion. A collision preserves the
existing file, even if it belongs to B3 or an earlier run. The original screening
`run_valid`, `failure_class` and `error` are not reclassified by H1 failures.

No PID, executable, process start time, owner authorization, arm, restore request,
write value, absolute source path, memory dump or free-form recommendation
rationale is exported. The existing Full write guards and independent restore
receipt parser are unchanged. Even copying H1 text to a restore summary filename
fails the existing source-receipt validation before memory access.

## Verification and future manual step

Use the existing Python 3.14.x / isolated `lupa.lua54` environment. The dedicated
suite is `tests/test_single_handoff.py`; run it with the Single, Truth Isolation,
validity/timing, stable-prescore, WRITE and adjacent safety suites. Tests replace
startup configuration, collector memory and runtime output with synthetic data.
The OS-backed publication test writes only to pytest's external temporary folder.

A separately authorized future manual check uses `single/basic`, disabled
execution, `write_enabled=false` and `single_handoff_enabled=true`. An operator
runs CE manually and returns a ZIP containing the same batch's `no_probe_A.log`,
`summary.txt`, `diagnostic_diff.txt` and `single_handoff.txt`, plus console failure
details if publication is rejected. H1 development does not perform that check,
create an arm, or authorize any subsequent guarded write.
