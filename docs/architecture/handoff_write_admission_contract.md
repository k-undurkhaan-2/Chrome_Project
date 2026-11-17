# H3-A1: independent, non-authorizing admission review

A1 reviews the structure and internal value consistency of supplied H2 report
bytes. Its strongest result is `SOURCE_REVIEWABLE_NOT_AUTHORIZED`. This means
that a source document is suitable for a separate owner's review; it never
means that its candidate is correct, current, owned by the operator, or writable.
H1 ranking, H2 value consistency and A1 review cannot substitute for permission.
All three are untrusted local evidence. A coordinated forgery, including a
different canonical candidate address, can pass structural checks.

The implementation is staged in `src/mvp0_handoff_write_admission.lua`. It is
pure Lua 5.4, with no module imports, file publication, clock, process discovery,
CE attachment, memory access, write/restore handle, runtime configuration or
runner dispatch. There is no operational `handoff_admission_only` switch.
Existing H1/H2/Single/Full/restore routes and their defaults remain unchanged.

## API and trust boundary

`Admission.evaluate(report_text, review_context)` returns a new scalar-only Lua
table. `report_text` is the exact H2 `Verify.render` byte string, supplied by the
caller. `review_context` is optional, separately supplied review metadata with
the complete whitelist below. There are no injected callbacks. Extra positional
arguments are rejected, including a third candidate override or live handle.

`Admission.render(result)` produces a fixed-order CRLF record, including a final
CRLF and literal `nil` for unavailable fields. Only an unchanged result table
returned by this same module instance is rendered as that review. A private
weak-key snapshot detects changed, removed or added fields; arbitrary copies,
foreign tables, metatables and extra render arguments produce a fresh
`REJECTED/invalid_result` record. A rejected result cannot be promoted by editing
its status. This is a render-integrity check inside a trusted Lua runtime, not
cryptographic authentication or protection against an actor controlling that
runtime. No input report text or caller-owned context table is retained.

The report is evaluated without reopening H1 files or rerunning H2. Source
lengths, observations and attestation declarations remain claims by H2. A1
cannot detect a consistent fabricated document, verify an external identity
record, establish scene semantics, or authenticate a hash supplied by a caller.
It is not a replacement for H2's original four-file reconciliation. Rendered
records are portable review data, never executor configuration or a receipt.

## Exact H2 input schema

The maximum input is 16,384 bytes. Empty, oversized and non-string input fails.
Only printable ASCII within records is accepted; CRLF is the only framing and
the final CRLF is mandatory. Blank lines, BOM, control bytes, bare CR/LF, mixed
newlines, unknown/renamed/duplicate/missing fields, whitespace around keys or
`=`, empty values and reordered records fail. There is no last-key-wins rule.
The complete sequence is derived from the current `Verify.render` v1:

```text
verification_schema_version, verification_kind, verification_batch_id, verification_case_id,
source_batch_id, source_case_id, source_session_id, source_log_filename, source_log_size_bytes,
source_summary_filename, source_diagnostic_filename, source_companion_filename,
source_consistency_status, source_cryptographic_authentication, candidate_address,
expected_search_float, expected_search_pattern, operator_attestation_status, process_identity_basis,
process_identity_os_measured, source_process_identity_status, confirmed_at_utc, observed_at_utc,
observed_float, observed_integer_pattern, observed_float_pattern, candidate_value_consistent,
verification_status, failure_class, memory_read_attempts, memory_write_attempts,
semantic_correctness_established, ownership_established, authorization_status, handoff_write_ready,
write_ready, write_attempted, baseline_eligible, independent_review_required, next_action, warning
```

H2's internal `output_filename` is not in its rendered schema and is rejected
as an extra field. A1 does not infer that the supplied bytes came from a file
with any particular name or were ever published successfully.

| Input fields | Required representation |
| --- | --- |
| `verification_schema_version`, `verification_kind` | `1`, `readonly_candidate_verification` |
| `verification_status`, `failure_class` | `VALUE_CONSISTENT_NOT_AUTHORIZED`, `nil` |
| `candidate_value_consistent`, `source_consistency_status` | `true`, `consistent_local_evidence_only` |
| `operator_attestation_status`, `process_identity_basis` | Both `operator_reconfirmed` |
| `source_process_identity_status` | `operator_recorded_at_h1_not_measured` |
| `authorization_status` | `NOT_AUTHORIZED` |
| `write_ready`, `handoff_write_ready`, `write_attempted`, `baseline_eligible` | All `false` |
| `memory_read_attempts`, `memory_write_attempts` | Exactly `2`, `0` |
| `source_cryptographic_authentication`, `process_identity_os_measured` | Both `false` |
| `semantic_correctness_established`, `ownership_established` | Both `false` |
| `independent_review_required` | `true` |
| `next_action` | `independent_owner_decision_in_future_phase` |
| `warning` | `NOT A WRITE GRANT; not a signed permission or WRITE/RESTORE receipt` |

The five source/verification identifiers are 1–80 ASCII characters, beginning
with an alphanumeric character, followed only by alphanumerics, hyphens and
single underscores. `nil`, trailing underscore, `__`, spaces, separators, dots
and path/stream syntax fail. H1 and H2 case IDs and batch IDs must differ even
under case folding. Filenames must equal these exact, case-sensitive basenames:

| Field | Required name |
| --- | --- |
| `source_log_filename` | `<source_batch>__<source_session>__<source_case>__no_probe_A.log` |
| `source_companion_filename` | `<source_batch>__<source_session>__<source_case>__single_handoff.txt` |
| `source_summary_filename` | `<source_batch>__summary.txt` |
| `source_diagnostic_filename` | `<source_batch>__diagnostic_diff.txt` |

`source_log_size_bytes` is canonical positive decimal, at most 2,097,152. No
sign, leading zero, decimal point or exponent is accepted. Its relationship to
actual bytes was H2's responsibility; A1 cannot verify it without those bytes.

`candidate_address` must be `0x` plus uppercase hexadecimal with no leading
zeros, from `0x1` through `0x1FFFFFFFFFFFFF`. Length is bounded before conversion
to a Lua integer, preventing overflow/wrap and floating precision loss. Decimal,
signed, fractional, exponent, lowercase and padded representations fail.

All three patterns are `0x` plus exactly eight uppercase hex digits, represent
finite Float32 values, and must be identical. Signed decimal integer readings
are not report patterns: H2 already normalizes signed reads to unsigned bits.
Both float texts must use H2's canonical rendering: integers use `tostring`,
floating numbers use `%.17g`. H2 may receive an integer-valued mock/read result;
both producer number types are supported without accepting alternate spellings
such as `100.0`, `+100`, or `1e2` for `100`. Negative zero is preserved explicitly.
Each decoded number must already equal the Float32 decoded from the bits, and
packing that number back to Float32 must yield the exact same bits. Merely
rounding a nearby double to the expected pattern is insufficient. NaNs,
infinities, overflows, signed-zero differences and noncanonical forms fail.
Subnormals and the largest finite Float32 values are valid observations.

Both UTC fields use `YYYY-MM-DDTHH:MM:SSZ`, Gregorian dates from 1970 through
9999, hours 00–23 and minutes/seconds 00–59. Offsets, fractional seconds and
leap seconds fail. Require `0 <= observed - confirmed <= 120` seconds using
calendar arithmetic without host timezone, DST or a clock API. This describes
only an interval inside historical evidence. A decades-old valid report can be
reviewable; no current-time comparison or freshness claim is made. H2's earlier
five-second real observation interval is not a later live-write arm.

## Optional separate review context

Omit the argument or pass `nil` when no context is available. When supplied, it
must be a plain table with exactly all six keys below. An empty/partial table,
unknown key, non-string value or any metatable fails without executing callbacks.

| Key | Contract |
| --- | --- |
| `review_record_id` | Opaque reference using the same safe identifier grammar; no private prose or path |
| `h2_report_sha256` | Declared SHA-256 of the exact H2 CRLF bytes |
| `h1_companion_sha256` | Declared SHA-256 of the original H1 companion bytes |
| `h1_log_sha256` | Declared SHA-256 of the entire original log, including any CE prologue |
| `h1_summary_sha256`, `h1_diagnostic_sha256` | Declared SHA-256 of the two original batch reports |

Each digest is exactly 64 lowercase hexadecimal characters. They are immutable
references to claimed byte versions, copied with a `declared_` prefix, not
computed or verified by A1. Even a well-formed wrong digest cannot establish
binding; `review_context_binding_verified=false` always. A future trusted
reviewer must independently hash the actual files and bind them to an approval
record. A plain digest is not a signature or proof of origin. Context cannot
change the address, supply known-true/rank/confidence/ACCEPT, private process
data, a current clock, permission booleans, requested write values or a handle.

## A1 result schema v1 and rejection behavior

Output has the following fixed order. Every key is always rendered; unavailable
values use `nil`. The serialized record is bounded below 8 KiB by the validated
field limits. No PID, executable path, private attestation text or truth address
is exported. Source fields are copied only after the entire report and context
validate; any rejection clears all source/context provenance.

```text
admission_schema_version, admission_kind, review_status, failure_class,
verification_batch_id, verification_case_id, source_batch_id, source_case_id, source_session_id,
source_log_filename, source_log_size_bytes, source_summary_filename, source_diagnostic_filename,
source_companion_filename, candidate_address, expected_search_float, expected_search_pattern,
observed_float, observed_integer_pattern, observed_float_pattern, confirmed_at_utc, observed_at_utc,
source_memory_read_attempts, source_consistency_status, operator_attestation_status,
source_process_identity_status, source_temporal_scope, current_target_freshness,
review_record_id, declared_h2_report_sha256, declared_h1_companion_sha256, declared_h1_log_sha256,
declared_h1_summary_sha256, declared_h1_diagnostic_sha256, review_context_binding_verified,
authorization_status, write_ready, handoff_write_ready, write_attempted,
memory_read_attempts, memory_write_attempts, process_identity_os_measured,
source_cryptographic_authentication, semantic_correctness_established, ownership_established,
independent_review_required, baseline_eligible, next_action, warning
```

`admission_schema_version=1`, `admission_kind=handoff_source_review`.
`review_status` is only `SOURCE_REVIEWABLE_NOT_AUTHORIZED` or `REJECTED`.
Success has `failure_class=nil`. Source numeric values, addresses, patterns,
IDs, basenames and timestamps remain exact immutable H2 strings in the Lua
table as well as the output; they are never current execution inputs.
`source_memory_read_attempts=2` describes H2; A1's own `memory_read_attempts=0`.
Source consistency/attestation declarations are copied verbatim, with no claim
that A1 independently measured them.

Every outcome retains `authorization_status=NOT_AUTHORIZED`,
`write_ready=false`, `handoff_write_ready=false`, `write_attempted=false`,
`memory_write_attempts=0`, `process_identity_os_measured=false`,
`source_cryptographic_authentication=false`, `semantic_correctness_established=false`,
`ownership_established=false`, `independent_review_required=true`,
`baseline_eligible=false`, `review_context_binding_verified=false`,
`source_temporal_scope=historical_observation_only`,
`current_target_freshness=not_evaluated`, and
`next_action=separate_owner_review_required`.
The warning is `NOT A WRITE GRANT; historical local evidence only; not a write or restore receipt`.

Validation proceeds through framing/schema, H2 success, limitations,
attestation, identifiers/filenames/size, address/value, historical time and
context. The first failed stage yields a concise constant failure class:

| Failure classes | Meaning |
| --- | --- |
| `report_type_invalid`, `report_size_invalid`, `report_framing_invalid`, `report_fields_invalid` | Input envelope or field sequence invalid |
| `h2_schema_invalid`, `h2_not_successful`, `h2_limitations_invalid`, `h2_attestation_invalid` | Required H2 identity, success or non-authorizing declarations absent/altered |
| `source_identity_invalid`, `source_identity_reused`, `source_filename_mismatch`, `source_log_size_invalid` | Source identity/filename/size relationship invalid |
| `candidate_address_invalid`, `candidate_pattern_invalid`, `candidate_pattern_mismatch`, `candidate_value_invalid` | Canonical address or finite exact Float32 consistency failed |
| `source_time_invalid`, `source_interval_invalid` | Calendar or historical interval invalid |
| `review_context_invalid`, `unexpected_arguments` | Unapproved input fields, types, callbacks or extra arguments |
| `admission_exception`, `invalid_result` | Unexpected internal evaluation error, or foreign/mutated render input |

Raw exception messages and input strings never enter a failure record. Constant
limitation checks may use table iteration, but all failures in that group have
the same code; externally visible failure selection remains deterministic.

## Required later H3 design: independent write and restore pair

The following is a future implementation contract, not an executable plan or
permission for a manual run. Both write and recovery must receive a separate
scope, implementation review and synthetic qualification before any live write.

1. **Independent owner decision.** An identified owner of the permitted
   disposable target environment approves one operation: exact evidence hashes,
   one candidate address, requested Float32 value and bits, expected old value
   and bits, exact current process instance and scene, case/session, unique
   operation ID and a short bounded validity window (propose at most 120
   seconds). Search value, old value and requested new value are distinct roles.
   The owner explicitly acknowledges that Single/H2 do not prove semantics or
   ownership. Use a separately produced approval record with its own version,
   identity and trusted signer/verification channel; H2/A1 have no approval
   field to copy. The trust anchor and operator permission to act must be
   established independently of the local evidence folder. Merely changing a
   status or appending `authorized=true` is invalid. If cryptographic approval
   verification is unavailable, stop the future automated route pending an
   explicitly reviewed alternative trust mechanism.
2. **New identity and freshness evidence.** Independently measure PID, OS
   process creation identity/time, canonical executable identity, architecture
   and the exact CE attachment in the current run. Recheck just before mutation;
   a reused PID, same address/name or internal session label is insufficient.
   Scene continuity is a separate operator attestation, not an OS measurement.
   Recompute actual immutable source hashes and reconcile H1/H2 before binding
   approval. Obtain fresh dual reads of the approved address. H2's timestamps
   must never be extended, replayed or converted into a current arm. Enforce
   both wall-clock expiration and a bounded monotonic elapsed interval to
   reject clock rollback/long pauses. A process or scene change aborts.
3. **Truth isolation and a dedicated route.** Keep Single collection and the
   source-to-write decision free of `known_true_addr`. Never manufacture Full
   A/W/B/Stable ranks, relabel Single as Full, or set `require_full_profile` /
   `require_known_true_match` false to call the old executor. Implement a sibling
   H3 executor and explicit source discriminator, proposed
   `h3_single_write_receipt` schema v1, with default-off mutually exclusive
   dispatch in a later node. Full guarded writing keeps all existing gates.
   H1/H2/A1 text must be rejected as operational receipts by both routes.
4. **Durable preparation and single attempt.** Before mutation, exclusively
   reserve and consume the new operation ID in a durable anti-replay journal.
   A crash, duplicate/concurrent call, uncertain API return, process change or
   expired approval never frees it for retry. Read the approved address with
   integer and Float32 APIs, require exact agreement with the independently
   approved original bits, then durably publish and read-verify a no-replace
   recovery-preparation record. Bind it to the approval, evidence manifest,
   measured process instance/scene, address, original/requested pairs, read
   timestamps and operation ID. Record storage failure aborts before writing.
   After persistence, repeat the two original-value reads and identity/time
   checks, then perform at most one Float32 write. Follow it with one integer
   and one Float32 readback; both must exactly match the requested bits, with
   no tolerance. The proposed successful path therefore has six target reads
   (four before, two after) and one write. Failure paths use a bounded prefix;
   a returned/raised uncertain write still triggers the two diagnostic reads
   when the verified process remains available, never a second write.
5. **Distinct evidence for recovery.** The current
   `mvp0_value_executor.lua:validate_source_evidence` requires matching Full
   summary and Stable log receipts, known-true identity/rank and successful
   write/readback fields. It cannot accept H3 sources. Before any H3 live-write
   node, implement a separate H3 receipt parser, independent restore entry and
   versioned `h3_single_restore_receipt`; an explicit dispatcher may choose a
   parser by schema, but must not weaken the old Full parser. H3 evidence needs
   both the durable preparation and a finalized write-attempt record, including
   write API outcome, attempt count, each readback's status/value/bits, source
   hashes, approval reference and process instance. Verify exact cross-record
   binding and immutable bytes, reject duplicate/mixed-source/unknown schema
   records, and keep incomplete or uncertain attempts distinct from success.
   A `rollback_available=true` flag alone is never recovery evidence.
6. **Independent restore authorization.** A new owner-approved restore record
   and unused operation ID must bind the exact H3 write/preparation receipts,
   same still-live OS process instance and scene, original value/bits to restore,
   and newly observed current value/bits. Reconfirm attachment/identity and
   dual-read current state, persist the restore reservation, then re-read and
   recheck approval/time before at most one restore write and dual exact-bit
   readback. Successful recovery likewise proposes six reads and one write.
   Reject process restarts, source swaps, mismatched original values, arbitrary
   target overrides and replay. Never rediscover an address or consult ranking
   during recovery. Write approval cannot serve as restore approval.
7. **Uncertain writes and authentication limits.** Preserve original sources,
   preparation, API failure/exception classification and all observed bits,
   including partial/inconsistent readbacks. There is no automatic write retry
   or automatic rollback. If final receipt publication fails, the independent
   preparation and consumed operation journal must still identify an uncertain
   attempt; absence of a final receipt cannot be treated as proof of no write.
   A separately authorized recovery decision must explicitly bind that
   uncertainty and fresh current-state evidence. Unknown current state, lost
   identity or missing preparation blocks automated recovery. Exact dual reads
   are non-atomic and cannot eliminate ABA or concurrent mutation; restrict the
   future test environment accordingly and disclose residual risk. Local H1/H2
   hashes cannot retroactively authenticate their origin, and H2 operator
   attestation must never be labeled OS-verified.

Required future synthetic gates include genuine H3 write-to-restore success;
rejection of H1/H2/A1/Full receipts on the H3 route and H3 receipts on the old
Full route; altered hashes/approval/address/value/scene/process identity;
signed/unsigned and negative-zero bit consistency; restart/PID reuse; expired,
reused, concurrent or cross-operation approval; clock rollback; value changes
during persistence; journal collisions; storage/readback failures; false/nil/
exceptional write returns; every interruption before/after a possible write;
incomplete receipt publication; and refusal to retry or restore without new
independent permission. Qualify the durable platform primitives and recovery
parser together before considering a separately authorized CE qualification.

## Validation and manual notice

`tests/test_handoff_write_admission.py` uses actual `Verify.run` and
`Verify.render` over synthetic H1 evidence in separate Lua runtimes. Its A1
module environment poisons H1/H2 loading, collector, executor, memory, process,
filesystem, clock, debug and Python bridge access. Host `debug.traceback` remains
intact for Lupa's protected-call setup; the module's `debug` and `_G.debug`
still trap access. It covers parser ambiguity, every required key,
Float32/calendar boundaries, altered authority claims, context whitelisting,
render mutation, coherent-forgery limitations and Full/restore rejection.
Mocked success establishes no real CE integration qualification.

Run this suite first, then all nine unchanged legacy suites (1,086 tests):
`test_handoff_candidate_verify`, `test_single_handoff`,
`test_screening_single_mode`, `test_screening_truth_isolation`,
`test_screening_validity_timing`, `test_stable_prescore_optimization`,
`test_write_usability`, `test_safety`, and `test_safety_doctor`.
Use Python 3.14.x, real isolated `lupa.lua54` / Lua 5.4 and the existing pytest;
disable bytecode, plugin autoload and caches. Keep basetemp/JUnit/transcripts
outside the repository. Any previously qualified path adapter may change only
virtual filesystem path keys, never source, assertions, values or source origin.
Check Lua compilation, Python syntax, whitespace and data/authority boundaries.
Stop on a failed gate. No package installation or persistent environment change.

Before any future CE run, deliver a Chinese notice containing all of these:

> 本次目标 PID／进程启动标识、可执行文件及场景：由本次独立验证填写；
> case／session：填写本次新标识；搜索值、预期原值及拟写值／位模式：分别列明；
> 精确模式：填写 single/basic 或经独立批准的新 H3 模式；
> 范围：明确只读、dry-run、单次写入或独立恢复；
> 内存操作：分别列出预期及上限读取／写入次数、失败分支与停止条件；
> 输出：逐一列明本次 ZIP 名称、来源文件、审批引用、准备记录、尝试回执及日志；
> 写入与恢复分别授权，H2／A1 成功不授予写入权限。

A1 needs no operator process data and authorizes no manual run, arm, real CE,
target-memory read/write, restore, publication, Git staging/commit/push/tag or
historical rewrite. A later H3-A1-C1 may separately arrange a selective signed
commit and committed-source validation. No new version tag is recommended until
the independent H3 write-and-restore pair reaches a separately validated live
milestone.
