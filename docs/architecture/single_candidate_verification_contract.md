# Independent Single candidate verification (H2-V1)

H2 validates the internal consistency of four local H1 artifacts, an explicit
operator reconfirmation, and one current Float32/pattern observation. It does not
establish source authenticity, OS process identity, ownership, semantic target
correctness, or permission to write. Rank 1, `HIGH`, `ACCEPT`, and a value match
remain observations. H2 never loads a collector, ranker, guarded-write executor,
restore executor, or Write Arm. Its only target-memory interfaces are one
`readInteger(address)` and one `readFloat(address)`; there are no retries.

## Entry and configuration

`handoff_verify_only` defaults to the literal boolean `false`. A number, string,
or table is rejected. With H2 disabled, the existing output and I/O paths are
unchanged. Configuration still loads once from the existing local configuration
file. The H2 module is loaded only when opted in, before UI or collection.

Use exactly one case, `validation_profile="single"`,
`execution_mode="disabled"`, `write_enabled=false`, and
`single_handoff_enabled=false`. Full, Quick, H1 export, explicit `modes`, restore
metadata, write values, confirmation, and arm fields cannot accompany H2. Use a
fresh minimal configuration in a separately authorized manual node; the current
local configuration and backup are not changed by development. H2 does not
convert a failed verification into a screening run.

There are two H2 configuration keys: the opt-in and `handoff_verify_request`.
The latter is one table, not a list, with exactly these keys:

| Key | Contract |
| --- | --- |
| `case_id` | New verification case ID, different from the H1 source case |
| `source` | Exactly `batch_id`, `case_id`, `session_id`, copied from the original H1 batch |
| `attestation` | Operator-controlled context described below |

Identifiers are 1–80 ASCII characters, begin with an alphanumeric character,
and contain only alphanumerics, hyphens, and single underscores. No trailing
underscore, `__`, `nil`, dots, separators, or absolute paths are accepted. Unknown
request/source keys are errors, including evidence roots or candidate overrides.
Legacy Known True/search-address fields are not consulted by H2. Truth is allowed
only in separate post-run analysis, never as a verifier success condition.

The runner generates `verification_batch_id` as `h2-<UTC YYYYMMDD-HHMMSS>`.
The batch must differ from the source batch; a repeated output identity fails
publication without overwriting anything. Choose a distinct verification case
for another attempt. No automatic retry or suffix guessing occurs.

## Source evidence and parser

The only evidence root is `D:\armedforces.io-v2\log\auto_output`. H2 opens exactly:

1. `<batch>__<session>__<case>__single_handoff.txt` (maximum 16 KiB).
2. `<batch>__<session>__<case>__no_probe_A.log` (maximum 2 MiB).
3. `<batch>__summary.txt` (maximum 2 MiB).
4. `<batch>__diagnostic_diff.txt` (maximum 2 MiB).

Each binary read requests at most its limit plus one byte. Missing, unreadable,
empty, oversized, failed-read/close, and exceptional I/O are rejected. No directory
enumeration, alternative root, or fallback file lookup is performed.

The companion must be the deterministic H1 schema-v1 key sequence with unique,
exact fields and CRLF, including its final CRLF. Only confidence/recommendation
may be omitted. Required declarations are checked verbatim. Numeric values must
be canonical, finite and coherent; addresses are positive exact integers through
`0x1FFFFFFFFFFFFF`, written as uppercase hex without leading zeroes. Patterns
are eight uppercase hex digits and must represent a finite Float32. The search
float and pattern must agree when both exist; either representation can supply
the expected bits when the other is `nil`.

The original log, summary, and diagnostic are checked for section identity,
duplicate keys within a section, source batch/case/session, fixed log path,
byte length, validity, Single/detect-only declarations, execution declarations,
candidate address/count, scores/gap, summary confidence, available counts and
search inputs. Multi-case/extra-mode sections are rejected. Legacy `tostring`
score rendering is compared at its actual printed precision, without a tolerance
or confidence threshold. Basic/debug compact logs and trace logs are supported.
The trace ranker report legitimately uses LF inside the CRLF outer log; H2 checks
its summary, recommendation and dense, unique, sorted candidate entries. LF is
not accepted in the companion or the surrounding structured reports.

Only the H1 `no_probe_A.log` may begin with the CE diagnostics emitted by
`load_modules()`. Header-first logs remain valid. When present, the prologue is
exactly six CRLF-terminated lines, in this order (no leading/intervening blank
lines, additional text, or extra diagnostics):

1. `[MVP0] REPORT_BUILD_TAG = probe-20260321-v1`
2. `[MVP0] REPORT_SOURCE = @D:\armedforces.io-v2\src\mvp0_candidate_report.lua`
3. `[FUNC] MVP0.score_base_candidate -> source=<report-source> line=<line>`
4. `[FUNC] MVP0.apply_rank_adjustments -> source=<report-source> line=<line>`
5. `[FUNC] MVP0.render_report -> source=<report-source> line=<line>`
6. `[FUNC] MVP0.compute_one_sided_anchorless_split_penalty -> source=<report-source> line=<line>`

`<report-source>` is exactly `D:\armedforces.io-v2\src\mvp0_candidate_report.lua`
(without `@` in the function diagnostics). `<line>` is canonical positive ASCII
decimal, 1 through 2147483647, at most ten digits, with no leading zero, sign,
whitespace or suffix. Function line numbers may change between builds. Each
diagnostic line is at most 160 bytes excluding CRLF. The next line must be
`=== compact_report ===` for basic/debug or `=== run_config ===` for trace;
the existing report grammar and checks still apply. Unknown, missing, duplicated,
reordered, malformed or oversized diagnostics are rejected. Banners inside the
structured body cannot reset sections or hide duplicate keys.

H2 removes this prefix only from a derived source-log parser view. It never
normalizes or rewrites the four original artifacts, and compares the companion,
summary and diagnostic byte-size declarations against the entire original log,
including the prologue. For the archived `20261117-020344` parsing sample, this
means 5,251 original bytes, a 558-byte prologue and a 4,693-byte parser view.
The allowance does not apply to the companion, summary, diagnostic, H2 result,
or restore-source parser. The trace LF-within-CRLF rule remains unchanged.

These startup diagnostics are untrusted format metadata. Their paths, build tag
and line numbers establish no source authenticity, process identity, historical
continuity or write permission. The archived batch still lacks contemporaneous
H1 process-identity evidence and must reach `source_process_identity_unavailable`
before either candidate read. Portable regression tests reproduce the six-line
format with synthetic artifacts and explicitly mock identity/memory; optional
historical-byte replay is read-only and kept outside the repository.

H1's `VALIDATED_PENDING_OUTPUT` in summary/diagnostic is the expected historical
publication ordering. It is accepted only alongside the physical, validated
companion. It is never evidence of publication by itself. H1's compact log uses
the legacy decision `action` field and ordinarily prints `recommendation=nil`;
the companion's actual recommendation is validated as an enum, not inferred from
that nil. Trace reports expose the recommendation and are cross-checked.

These checks detect internal inconsistency, not coordinated editing or a forged
artifact set. No cryptographic authentication is provided. A changed set of
locally consistent files cannot independently prove their origin or age.

## Operator reconfirmation

All of the following attestation fields are required. Unknown fields are rejected.
The verifier trusts none of these as an OS measurement.

| Fields | Required value or meaning |
| --- | --- |
| `identity_basis` | `"operator_reconfirmed"` |
| `permitted_disposable_environment` | Literal `true` |
| `h1_did_not_measure_identity` | Literal `true`; explicitly acknowledges the H1 limitation |
| `source_identity_status` | `"operator_recorded_at_h1"`; an actual external record must already exist |
| `continuity_confirmed` | Literal `true` |
| `continuity_basis` | 12–512 characters describing the external record and continuity check; no control characters |
| `verification_case_id` | Exact H2 request case ID |
| `source_batch_id`, `source_case_id`, `source_session_id` | Exact H1 source binding |
| `requested_process_name` | Explicit executable name ending in `.exe` |
| `confirmed_at_utc` | Fresh operator confirmation, `YYYY-MM-DDTHH:MM:SSZ` |
| `source_recorded_at_utc` | When the source identity was externally recorded during H1 |
| `source`, `current` | Separate process-context tables with the exact five fields below |

Both process-context tables contain `process_name`, `executable`, `pid`,
`started_at_utc`, and `scene`. The executable must be a complete drive-qualified
Windows path whose basename equals the requested process name, with no traversal,
alternate stream, UNC/device path, or ambiguous trailing dot/space. PID is an
integer from 1 through `0xFFFFFFFF`; scene uses the identifier grammar. All five
source/current fields must match exactly, including executable case and spelling.
This conservative comparison rejects ambiguity; matching still does not prove
the same process instance or the process currently attached to CE.

UTC dates are checked using Gregorian arithmetic. Confirmation must be no more
than 120 seconds before the clock sampled immediately before observation, and
cannot be in the future. Source start must precede or equal the external source
record time, which must precede or equal confirmation. A fresh timestamp is only
an expiry check on a claim. It does not authenticate that claim or establish the
age of H1 evidence.

If source identity was never recorded during H1, H2 fails before any candidate
read with `source_process_identity_unavailable`, reporting the historical binding
as unavailable. Do not reconstruct a historical binding from an unchanged PID,
address, process name, or the runner's internal session label. A future owner may
choose to obtain a new H1 batch with an accompanying external identity record.
No historical PID or candidate address is embedded as a configuration default.

## Observation and result

The candidate comes exclusively from the validated companion and matching
source files. `readInteger` accepts signed or unsigned 32-bit results and
normalizes them to unsigned. `readFloat` must return a finite Float32 value;
re-encoding it must equal both the integer observation and expected search bits.
Missing APIs, errors, nil/nonfinite results, out-of-range integer values, changed
memory between calls, and different values fail closed. The two reads cannot
prove atomicity, detect an ABA change, or bind the address to a semantic object.

H2 produces one CRLF `key=value` report:
`<verification_batch>__<verification_case>__handoff_verification.txt`.
It has unique schema fields, exact source filenames/IDs, candidate and expected
bits, available observations, operator/measurement limitations, and failure
class. It deliberately omits PID, executable path, requested process name,
scene, continuity prose, write request/confirmation/arm, and memory dumps.
Only confirmation/observation UTC timestamps from the attestation are exported.

Success is `VALUE_CONSISTENT_NOT_AUTHORIZED` with
`candidate_value_consistent=true`. It means only value consistency. Every result
has `authorization_status=NOT_AUTHORIZED`, `handoff_write_ready=false`,
`write_ready=false`, `write_attempted=false`, `baseline_eligible=false`,
`memory_write_attempts=0`, `independent_review_required=true`,
`source_cryptographic_authentication=false`, `process_identity_os_measured=false`,
`semantic_correctness_established=false`, and `ownership_established=false`.
Before any candidate-read attempt, consistency is `not_evaluated`; a failed read
or mismatch is `false`. `memory_read_attempts` records zero, one, or two.

Failure families are `verification_*` (entry/identity/mixed-operation guards),
`source_*` (I/O/schema/consistency/historical identity), `operator_*`
(reconfirmation/context/continuity/time), and `candidate_*` (read/value/bit errors).
Raw callback exception text is not exported. Invalid filename identities or a
missing verifier module produce console rejection without fabricating a report.

Publication reuses the unchanged H1 Windows no-replace writer: exclusive
`.pending` directory reservation, checked write/close, exact staged readback,
then Windows CRT rename that refuses an existing target. The existing output
directory must be present. H2 never rewrites source files or batch screening
reports. Console reports verification and publication failures separately;
`PUBLISHED_NOT_AUTHORIZED` means the report was saved, even if its verification
status is `REJECTED`. I/O failures are not retried. An abandoned reservation is
not a published report and is not automatically reused or cleared.

## Synthetic acceptance and future manual notice

Development uses Python 3.14.x with real `lupa.lua54` Lua 5.4, mocked configuration,
virtual source/output files and injected memory APIs. Run
`tests/test_handoff_candidate_verify.py`, plus the unchanged eight suites:
`test_single_handoff.py`, `test_screening_single_mode.py`,
`test_screening_truth_isolation.py`, `test_screening_validity_timing.py`,
`test_stable_prescore_optimization.py`, `test_write_usability.py`,
`test_safety.py`, and `test_safety_doctor.py`. The latter must collect exactly 659
tests. The existing H1 suite also qualifies the shared Windows publication
primitive against external temporary files. No real process memory is used.

Disable Python bytecode, pytest cache and plugin autoload. Keep pytest basetemp,
JUnit and any test transcripts outside the repository. Do not modify `.venv`,
ACLs, Registry/Baseline, local config/backup, original logs, index, HEAD or tags.
For an optional future committed-source test, use an external logical-path
adapter for the existing test harness's `LOG_ROOT`; do not rewrite production
paths, assertions or source origin, and never silently import worktree source.

A future manual test requires separate authorization. The operator must supply
the complete fields above from a permitted disposable environment and an actual
external H1-time record, confirm the current CE attachment, then reconfirm within
120 seconds. H2 will use only `readInteger` and `readFloat`, with no writes, arm,
scan or restore. A match still requires a separate owner decision in a future
phase. Return a ZIP containing the four exact H1 source files, the H2 report if
published, and console verification/publication output. Keep detailed process
attestation outside publicly portable reports; do not supply a truth address to
H2. When publication fails, return console failure evidence without inventing a
successful report. This notice itself grants no manual CE or write permission.
