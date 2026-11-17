# H3-A2 paired write and independent restore: synthetic contract v1

Status: implementation for simulated dependencies only. Neither this contract,
an A1 review, a test PASS, nor a constructed Lua engine is a production write
grant. There is no CE/Windows adapter, production signer, durable OS store or
runner dispatch in this node. Existing H1/H2/A1 and Full protocols are unchanged.

## Composition and authority boundary

`mvp0_handoff_write_protocol.lua` and `mvp0_handoff_restore_protocol.lua` are
standalone pure modules. Load them through the test host, then call
`Protocol.new_synthetic(dependencies)` and `engine.run(approval_bytes, proof)`.
`Protocol.render(result)` produces a bounded public result. No input selects a
module, path or code to load. No module directly accesses files, stdout, clocks,
processes, CE globals, networking, Python or debug facilities. The restore
module contains its own strict H3 source parser and never calls the write
engine, A1, H2, H1, a collector, ranking, known-true logic or Full restore.

The two modules deliberately keep their small codec/transaction primitives
private, avoiding runtime module discovery or an injected mutable common-code
object. Tests exercise the same fault classes against both siblings.

The composition root is trusted **only within the simulation**. Its dependency
table must have no metatable, exactly the allowed keys and real Lua functions;
functions are captured once. There are no per-request callbacks. Adapters
receive immutable strings and scalar arguments, never internal transaction
tables. The constructor requires `environment=synthetic_only`. This marker is
an explicit restriction, **not authentication**. A malicious host can replace
code or inject dishonest adapters; a Lua module cannot authenticate its own
host. In particular, an arbitrary callback returning success, `{approved=true}`,
a config switch, a digest or the synthetic test proof is not valid production
authority. There is intentionally no production constructor or activation path.

The test verifier maintains a separate registry of exact immutable approval
bytes. The fixed authority `synthetic-authority`, domain
`h3-synthetic-tests-v1` and `synthetic-proof-*` labels are test fixtures, not
keys, signatures, secrets or actual operator approvals. A production adapter
would require separately approved trust roots, signer policy, signature
verification, immutable artifact retrieval, key rotation/revocation and access
control. All of those remain unqualified.

## Injected interfaces

All methods are functions without implicit `self`. Exceptions are caught and
mapped to bounded statuses; no underlying exception text is published.

| Interface | Contract |
| --- | --- |
| `verify_approval(bytes, proof, action)` | Return the exact authenticated `bytes`, domain and authority as three strings. Any other shape or value fails. The adapter must verify the complete artifact, action, trust domain and approved authority independently of caller claims. |
| `sha256(bytes)` | Independently hash exact bytes; return 64 lowercase hexadecimal characters. Hashes bind content but do not establish origin or permission. |
| `read_evidence(id)` | Write only: resolve an opaque approved artifact ID inside the trusted immutable evidence inventory; return actual bytes, bounded to 2 MiB each. IDs are never filesystem paths. |
| `revalidate_sources(approval, log, summary, diagnostic, companion, h2, a1)` | Write only: independently reconcile real source bytes, published schemas, nonauthorizing statuses, candidate, search bits and source identities. Return the exact source-binding record described below, never a Boolean. |
| `identity()` | Return the exact seven-field measurement record described below. It represents a simulated independent measurement, never a production operator-input claim. |
| `scene()` | Return the separately operator-affirmed scene token; scene is not claimed OS-measured. |
| `clock()` | Return canonical UTC text and a nonnegative integer monotonic millisecond count, at most `2^53-1`. Production UTC integrity, monotonic continuity and suspend behavior require qualification. |
| `reserve(id, "reservation", bytes)` | Atomically, exclusively and durably consume the ID before returning literal `true`; create an immutable reservation. The same ID namespace covers both operations, engines, processes and reloads. |
| `publish(id, kind, bytes)` | For `preparation` or `receipt`: exclusive no-replace durable publication, including complete write, flush, close, independent byte verification and protected-store commit. Return literal `true` only after all succeed. |
| `read_record(id, kind)` | Independently reopen the committed immutable record; return exact bytes. Never expose incomplete or uncommitted staged bytes as durable records. |
| `finalize_receipt(id, receipt_hash)` | Irreversibly mark the exact durable, independently read-verified successful receipt as finalized. Requires a consumed ID, durable preparation and intact receipt chain; never replace an earlier finalization. Only called after confirmed API and dual readback. |
| `read_finalized(id)` | Return the exact receipt from protected, durable finalization metadata. An ordinary file or unfinalized outcome record is insufficient. Restore uses this method for its source write receipt. |
| `read_integer(address)` | Read a simulated 32-bit word, either unsigned `[0, 2^32-1]` or signed `[-2^31, 2^31-1]`; malformed/nonintegral/nonfinite results fail. |
| `read_float(address)` | Read a finite, already exact Float32 numeric value. Its packed bits must exactly match the integer word and approved pattern, including zero sign. |
| `write_float(address, value)` | One simulated mutation attempt. Only literal `true` counts as API success. False, nil, other types and exceptions remain potentially mutating outcomes. |

Restore omits `read_evidence` and `revalidate_sources` entirely, including from
its dependency allowlist. Dependencies cannot be replaced by later changes to
the supplied table. Mutable state behind trusted adapters is part of their
explicit trust boundary, not something that function identity can authenticate.

The test evidence adapter uses actual synthetic H1 artifacts and H2 `run/render`
output, rehashes all six artifacts, reconciles its immutable H1 inventory, and
recomputes A1 through the unchanged `Admission.evaluate/render`. It preserves
H1 `single_candidate_proposal` / `NOT_AUTHORIZED`, H2
`VALUE_CONSISTENT_NOT_AUTHORIZED`, `process_identity_os_measured=false` and
`source_cryptographic_authentication=false`, and A1
`SOURCE_REVIEWABLE_NOT_AUTHORIZED`, `current_target_freshness=not_evaluated` and
`review_context_binding_verified=false`. This does not qualify a production
evidence inventory, semantic target correctness or source authentication.

## Canonical wire format

All approvals, measurement records, source bindings and output records use
ASCII `key=value\r\n` with the last CRLF mandatory. No BOM, LF-only framing,
bare CR, empty value, duplicate, reordered, missing or unknown field is allowed.
Approvals and transaction records are at most 16,384 bytes; each parsed value
is at most 512 bytes. Public results use fixed ordered fields and bounded
enums, counts and hashes. Each schema is version 1, with no implicit migration.

Operation, case, session, attachment and scene IDs are lowercase ASCII tokens:
`[a-z][a-z0-9-]*`, 1-64 bytes, with no trailing hyphen. Upstream IDs preserve
the published 1-80-byte H1/A1 token grammar: letters/digits first, then
letters/digits/underscore/hyphen, no `__`, trailing underscore or `nil`.
Six upstream artifact IDs must be distinct. Restore source request IDs use
the operation-ID grammar and must differ from the new restore ID.

SHA-256 text is exactly 64 lowercase hexadecimal characters. Addresses are
canonical uppercase `0x%X`, positive and at most `0x1FFFFFFFFFFFFF`. Patterns
are canonical uppercase `0x%08X`; all bit-to-float operations use little-endian
IEEE-754 Float32. Float texts must equal Lua `%.17g`, be finite and already
exact Float32, and pack to the companion pattern; `-0` is preserved. No tolerance
or silent rounding is used. Equal current/target bit patterns are rejected as
a no-op. Signed integer reads are normalized before comparison. Subnormals and
the largest finite positive/negative values are supported; NaN and infinity
are never accepted.

UTC is exactly `YYYY-MM-DDTHH:MM:SSZ`, years 1970-9999 with Gregorian calendar
validation. Integer strings have no sign, leading zero, exponent or decimal
point. PID is 1 through 4,294,967,295. Architectures are `x86` or `x64`.
Executable identity is an exact ASCII absolute drive path, at most 260 bytes,
without traversal, alternate separators, streams or wildcard characters.
Canonical executable measurement and Windows path equivalence are still a
mandatory production-adapter responsibility.

The common approval fields, in order, are:

```text
schema, source_kind, environment, request_id, authority, trust_domain, action,
case_id, session_id, candidate_address, current_float, current_pattern,
target_float, target_pattern, pid, process_created_utc, executable, architecture,
attachment_id, scene_id, issued_utc, expires_utc, max_elapsed_ms
```

Write appends, in order:

```text
source_batch_id, source_case_id, source_session_id,
h1_log_id, h1_log_sha256, h1_summary_id, h1_summary_sha256,
h1_diagnostic_id, h1_diagnostic_sha256, h1_companion_id, h1_companion_sha256,
h2_id, h2_sha256, a1_id, a1_sha256
```

Restore appends, in order:

```text
source_request_id, source_preparation_sha256, source_receipt_sha256
```

The schemas are respectively `h3_write_approval_v1` (38 fields) and
`h3_restore_approval_v1` (26 fields). Both require `source_kind=h3_single`,
`environment=synthetic_only`, the test authority/domain, and their distinct
`single_float32_write_once` or `single_float32_restore_once` action. No
cross-use, Full record, H1/H2/A1 report or returned result table is an approval.
Restore binds the same case/session/scene and process instance as its source
write, the source's new bits as current, and the source's original bits as its
target. It requires a new ID and newly authenticated exact approval bytes.

The identity record, in order, is:

```text
pid, process_created_utc, executable, architecture, attachment_id,
attachment_verified, measurement_basis
```

The last two values are exactly `true` and `synthetic_os_measurement`.
`process_sha256` hashes its first five fields only. `scope_sha256` hashes the
three-field record `case_id, session_id, scene_id` in that order. The write
source binding contains all 15 appended write fields followed by
`candidate_address, current_pattern`. `sources_sha256` hashes that record.
For restore it hashes the three appended restore fields; source links
transitively bind the original H1/H2/A1 identities and hashes. Exact Float32
texts are independently required to agree with their bound patterns.

## Durable record schemas and states

All five transaction schemas have the same 28-field ordered layout:

```text
schema, source_kind, environment, request_id, action, approval_sha256,
sources_sha256, process_sha256, scope_sha256, candidate_address,
current_float, current_pattern, target_float, target_pattern,
issued_utc, expires_utc, max_elapsed_ms, reservation_sha256, preparation_sha256,
state, attempted, api_result, api_ok, readback_ok, execution_success,
failure_class, last_checked_utc, last_checked_monotonic_ms
```

| Schema | State and meaning |
| --- | --- |
| `h3_operation_reservation_v1` | `RESERVED`: ID irrevocably consumed; both parent hashes `nil`; no attempt or API/readback success. |
| `h3_single_write_preparation_v1` | `PREPARED`: first exact original observation passed; bind reservation hash and approved original bytes; preparation hash `nil`; no mutation. |
| `h3_single_restore_preparation_v1` | `PREPARED`: first exact current observation passed; bind independent restore reservation and the separately approved source chain; no mutation. |
| `h3_single_write_receipt_v1` | `CONFIRMED` only when one API returned true and dual exact readback passed within checked identity/time. Otherwise `UNCONFIRMED`, including prewrite rejections. |
| `h3_single_restore_receipt_v1` | Same semantics for the single restore attempt and original target bits. |

All records require `source_kind=h3_single`, `environment=synthetic_only`.
Preparation references reservation bytes; receipts reference reservation and
preparation bytes. Missing preparation stays `nil` in a rejected outcome.
`approval_sha256` binds the entire independently authenticated approval,
including private process details, authority, source hashes and exact action.
The verifier must retain those exact approved bytes in its protected immutable
inventory; a digest alone is not a replacement for that evidence.

`attempted`, `api_ok`, `readback_ok`, `execution_success` are literal Boolean
texts. `api_result` is `not_called`, `true`, `false`, `nil`, `nonboolean` or
`exception`. `last_checked_*` records the last *successfully checked* clock,
not an invented receipt publication time. Failure codes never contain exception
strings. A source receipt must be retrieved through `read_finalized`, have
`CONFIRMED`, `attempted=true`, `api_result=true`, `api_ok=true`,
`readback_ok=true`, `execution_success=true`, `failure_class=nil`, correct hashes,
consistent record bindings and nondecreasing in-window source timestamps.

There are three deliberately distinct completion facts:

1. Memory was confirmed by API plus dual readback (`memory_confirmed` publicly,
   `execution_success` inside the immutable outcome receipt).
2. That receipt was durably published and independently read-verified
   (`receipt_published`). Its own bytes cannot certify their publication.
3. The protected store durably finalized that exact successful receipt and the
   engine independently retrieved it (`receipt_finalized`). Only all three
   make public `execution_success=true`.

An unfinalized file never suffices for restore. Finalization is protected store
metadata, not a caller-created flag or another permissive text schema. If a
crash loses an acknowledgement **after** a genuinely durable finalization,
the local return is uncertain; a future restore still requires a new authentic
approval and independent retrieval of the finalized chain. This cannot promote
an uncertain memory outcome: unsuccessful API/readback outcomes are never
eligible for finalization. There is no automatic reconciliation or retry.

All approvals, memory-bearing receipts, evidence and finalization metadata are
private artifacts for a future restricted OS store. Portable public rendering
contains only the following 25 fields and no PID, executable, candidate, raw
approval/proof or callback text:

```text
schema, environment, authorization_status, operation, status, failure_class,
operation_failure_class, persistence_failure_class,
reservation_status, preparation_published, write_attempted, restore_attempted,
write_api_ok, restore_api_ok, write_readback_ok, restore_readback_ok,
memory_confirmed, execution_success, receipt_published, receipt_finalized,
api_result, memory_read_attempts, memory_write_attempts, request_sha256, receipt_sha256
```

The public schema is `h3_synthetic_result_v1` and its authorization status is
always `NOT_PRODUCTION_AUTHORIZED`. Status is `REJECTED`, `UNCERTAIN` or
`SYNTHETIC_CONFIRMED`. A result view is checked against a private scalar snapshot
on rendering; mutation, copying, metatables and foreign results yield
`invalid_result`. A public view is never a receipt, capability or restore input.

## Transaction sequence and failure behavior

The write transaction authenticates approval bytes, independently reads/hashes
all six upstream artifacts, reconciles provenance, and verifies current scope,
process/attachment and time. It atomically reserves the request ID, performs
one integer and one Float32 old-value read, publishes/closes/independently
verifies preparation, rechecks identity/time, performs the second exact pair,
and rechecks identity/time again immediately before the mutation.

Only then may it make one `write_float` call, with the attempted flag set before
entering the callback. There is never a second attempt or automatic rollback.
After any callback return/exception, the engine rechecks identity/time. If safe,
it performs exactly one integer and one Float32 readback (even if the first
read fails), then checks the clock again. A failed API cannot become success
merely because memory happens to equal the request. Lost identity/attachment or
invalid time after an attempt prevents further memory reads and leaves an
uncertain outcome. The original durable preparation remains available.

Independent restore first verifies its separate approval and retrieves only
the H3 reservation, preparation and finalized successful write receipt.
It validates both hashes, exact schema/field order, immutable common bindings,
source chronology, process/scope and the reversed current/original value pair.
It then runs its own reservation, two prewrite dual observations, durable
preparation, final context check, single mutation and dual readback. Source
failures occur before the restore reservation and never invoke screening.

Approval UTC windows must be positive and at most 120 seconds; expiry is
exclusive. `max_elapsed_ms` is 1-120,000 and begins with the first clock
observation **before** verifier/evidence work. UTC and monotonic time must not
regress, monotonic elapsed must remain within the approved bound, and their
elapsed deltas must agree within 1,000 ms (UTC second resolution). Delays in
verification, storage and reads therefore count. H2's historical timestamp is
never used as a current arm.

Reentrancy in one engine is rejected. A local consumed-ID set is never cleared,
including failed reservations, but it is **not** the cross-process safety
mechanism. The store must provide atomic, durable exclusive consumption, valid
across engines and crashes. Read-then-open-`wb` is expressly inadequate.
No reservation, preparation, outcome or finalization may replace prior content.
Tests model a durable tombstone preceding every simulated reservation I/O
fault, discard partial staged bytes on power loss and test competing engines.

If storage is unavailable before even a tombstone can be proven durable, the
engine returns `reservation_status=uncertain`, never writes, and forbids local
reuse. A future production store must quarantine the operation/namespace until
durable recovery can prove its state; software cannot promise persistence
during complete storage loss. Failed persistence after an attempt cannot
guarantee a new durable failure receipt either. The original reservation and
verified preparation are the durable fallback, never a fabricated success.

Public failure classes distinguish approval/framing/trust, source availability,
hash/provenance, identity/scene, clocks, request reuse, initial/prewrite value
mismatch, reservation/preparation/receipt persistence or readback failure,
mutation API outcome, memory readback, and finalization failures. A post-attempt
failure remains uncertain. `operation_failure_class` retains the original
transaction failure even if receipt publication/finalization also fails;
`persistence_failure_class` records that additional failure. `failure_class`
names the last failed stage. Publication failure is separate from memory outcome.

## Qualification and production blockers

The Python suite runs genuine `lupa.lua54` with table-backed Float32 memory,
separate synthetic authority/identity/clock/store dependencies, real A1 review
generation, trapped external globals, and preserved host `debug.traceback`.
It exercises valid write/restore cycles, signed normalization, signed zeros and
subnormals; strict schemas; source substitution; bad authority and tampering;
identity/scene/time drift; dual-read failure; partial/flush/close/readback faults;
power loss, concurrency, ID replay, uncertain API outcomes, result mutation,
finalization and legacy Full/H3 rejection boundaries. These are protocol tests,
not CE, OS identity, actual cryptography or native storage qualification.

Acceptance requires the A2 suite independently, the ten unchanged suites
jointly (521 A1 plus 1,086 earlier tests = 1,607), and all eleven together.
The exact original test IDs must be preserved with no skip/deselection/failure.
Use Python 3.14.3, pytest 9.1.0, existing Lupa 2.8/Lua 5.4, isolated imports,
disabled bytecode/plugin autoload/cache, and external basetemp/JUnit/output.
Compile both Lua modules and the Python source, check whitespace and perform
focused review. Preserve the four D2 files, config/backup, logs, original
evidence, Registry/Baseline, `.venv`, ACLs, index, HEAD, refs and all tags.

Production activation is blocked on all of the following:

- A separately approved and independently qualified authentic signer/channel,
  trusted evidence inventory, immutable approval retention and verifier policy.
- Mandatory Windows PID plus process-creation measurement, canonical executable
  and architecture verification, authenticated CE attachment measurement, and
  separate operator-affirmed scene/case/session scope. Operator text alone does
  not meet this requirement.
- Native atomic no-replace ID reservation, durable flush/close/rename semantics,
  protected integrity/permissions, independently verified publication and
  finalization, crash recovery/quarantine and concurrent-process qualification.
- Trustworthy UTC/monotonic continuity and a policy for pause/suspend/restart.
- Independent qualification of both protocol siblings and the authority adapter;
  dual non-atomic reads cannot eliminate ABA or a concurrent change between the
  last observation and mutation. Production exclusivity/TOCTOU handling remains
  unresolved, and matching values do not establish semantic target correctness.
- A separately reviewed runner dispatch and explicit owner-approved target,
  environment, operation and manual handoff. No such dispatch or switch exists
  in this change.

After synthetic acceptance, the smallest next node is a separately authorized
selective GPG-signed commit and committed-snapshot validation/publication.
Only later consider production-adapter design and a manual **read-only** dry
run. Do not propose a live H3 write until the paired restore path and authority
adapter are independently qualified. No new version tag is recommended here.
