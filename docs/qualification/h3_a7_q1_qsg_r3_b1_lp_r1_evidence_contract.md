# H3-A7-Q1-QSG-R3-B1-LP-R1 evidence contract

Authorization: `APPROVE_H3_A7_Q1_QSG_R3_B1_LP_R1_TEN_FILE_OFFLINE_REMEDIATION`.
This contract describes offline synthetic evidence only. R3-B native IPC remains
`R3_B_NOT_AUTHORIZED`; G1 live remains `G1_LIVE_NOT_APPROVED`. Native N01–N09
and live L01–L12 remain NOT_RUN. No product, native provider, write budget,
reserve/claim, scoring, or collector change is part of this representation fix.

## Boundary and verified cause

The limit is **65,536 bytes of canonical `record.data`**, independently of the
larger JSON record envelope. Canonical JSON uses sorted keys, compact separators,
`ensure_ascii=True`, and rejects non-finite numbers. The transport body limit is
also still 65,536 bytes; its four-byte frame prefix is a separate layer.

The original B1 L12-MISSING record contains 32,433-byte retained-before and
retained-after observations. The non-diagnostic contribution is 65,312 bytes.
The diagnostic contributes 186 bytes on the original 81-character short path,
225 bytes on the 119-character B0-equivalent hierarchy, and 249 bytes on the
170-character path. The corresponding bodies are 65,498 / **65,537** / 65,561
bytes. The path occurs once in the diagnostic; this is not nested JSON
double-encoding. Equal retained content represents two separate observations.

`Stream.emit` prechecks the direct body before deep copying, clock sampling,
hashing, or publishing a record. 65,535 and 65,536 pass; 65,537 fails with
`PAYLOAD_BOUND`. The normal chain validator retains the same canonical digest,
predecessor, identity, ordering, origin, and clock rules.

## Opt-in formats and compatibility

Record envelopes remain schema 1. Legacy `CERecorder.rejection` calls remain
inline and retain their original diagnostic and body bounds. Historical
manifests, chains, and bundles are not rewritten. Unknown versions and mixtures
that omit the explicit version/seal fail closed.

New `config_rejected.data` includes `evidence_schema_version: 2` and a fresh
32-hex `bundle_id`. It retains `accepted`, both guard-counter snapshots,
`guard_restored`, and `retained_origin`. Three role fields hold references:

| Role | Normalized type | Content |
| --- | --- | --- |
| `retained_before` | `retained_snapshot` | Complete canonical prior observation |
| `retained_after` | `retained_snapshot` | Complete canonical subsequent observation |
| `diagnostic` | `loader_diagnostic` | Exact path and full/returned error bytes |

Each reference has exactly `artifact_id` (`sha256:` plus 64 lowercase hex),
`sha256`, `byte_length`, `normalized_type`, and `evidence_schema_version: 2`.
The filename is derived solely as `<sha256>.json` under the separately designated
evidence root. No diagnostic/source path is used to open a sidecar. Before and
after may reference the same blob only when canonical bytes match; both role
bindings remain explicit. The verifier independently reads and compares both
contents. A producer-supplied equality flag is not accepted.

QSG bundles opt in with `schema: "qsg.bundle.v2"` and a `sidecars` seal alongside
the six unchanged legacy bundle fields. The separately retained canonical QSG
bundle SHA-256 covers the policy, every stream, the raw spy observations, and the
sidecar-manifest seal. Generic JSONL exports use bundle manifest schema 2 and
copy the verified blobs into `sidecars/`; legacy exports stay schema 1.

## Full diagnostics and actual product returns

The mock loader's capture is explicitly enabled only for v2 FullSession. The
fixture wraps `loadfile` and `pcall` with `table.pack`/`table.unpack` so return
values, nil slots, and arity are preserved. Default mock behavior is unchanged.
Each L12 attempt clears the previous observation before calling the public API.

The diagnostic blob uses schema `ce.loader-diagnostic.v2`, origin `SYNTHETIC`,
source `g1_mock_loader`, and records:

- `path_utf8_hex`: exact original UTF-8 path bytes, without Unicode normalization.
- `loader_error_hex` and `loader_return_arity`: complete original loadfile error
  and its observed return count, or `false` and 0 when no loader error occurred.
- `full_error_hex` and `full_error_source`: the complete pre-truncation pcall
  error, or an API return if the product returned directly.
- `returned_error_hex`, `return_arity`, and `truncation_bytes`: the actual API
  return bytes, observed return count 2, and the unchanged product limit 240.

Lowercase hex represents bytes losslessly, including a product return cut in the
middle of a UTF-8 character. The full error is **not** described as the product's
actual return. The verifier checks the actual returned bytes against the first
240 bytes of the full error, binds the complete loader error to the exact path
and source-location prefix, and independently checks MISSING / DISABLED /
INVALID diagnostics. The product's `:sub(1,240)` is unchanged.

## Storage, sealing, and independent verification

Additional sidecar limits are 1 MiB per blob, 32 blobs, 8 MiB aggregate, and
65,536 bytes for the sidecar manifest. These never replace the direct body
limit. `sidecars.json` contains schema `ce.sidecars.v2`, bundle/session IDs,
unique artifact entries, and ordered event bindings. Each binding includes the
source, session, event ID, run, scenario, sequence, content digest, and role IDs.
The record digest binds the actor, origin, timestamps, and predecessor as well.

The writer exclusively creates files, flushes and fsyncs blobs, and only then
writes and rereads the manifest. It refuses an existing root, unexpected files,
type/digest collisions, unreferenced blobs, and modifications after sealing.
A crash leaves partial/unsealed evidence that cannot pass verification; it does
not create a resumable or implicitly trusted bundle. This is not a physical
power-loss durability claim.

The independent verifier imports no recorder, broker, gate, or native provider.
It checks the independently supplied seal, strict shape/version, canonical bytes,
declared and actual size, digest, unique IDs, exact reference and event closure,
and before/after semantics. Missing, truncated, oversize, stale, tampered,
non-canonical, duplicate, cross-bundle replay, and unmanifested content fail.
Unknown or missing sidecar roots also fail. All content comes from bounded reads.

Directory components and files must not be symbolic links or Windows reparse
points; hardlinked files are rejected. Reads compare directory/file identities
before opening and after reading, and verify the opened file identity. On this
Python/Windows runtime, `lstat` and `fstat` expose different legacy `st_ctime`
meanings, so the comparison uses device/file ID, size, write time, and available
creation time. Cryptographic byte checks remain mandatory. This is conservative
offline verification, not a claim of atomic protection from a privileged attacker
able to replace both evidence and its independently retained trust anchor.

## Offline verification interfaces

`ce_qualification.qsg_verifier.verify` accepts an optional keyword
`sidecar_directory`. V2 requires that designated root and a separately retained
bundle digest; legacy callers need no new argument. Its CLI adds
`--sidecar-directory` to the existing `--bundle`, `--canonical-sha256`, and
`--case` options.

`ce_qualification.verifier.verify_bundle` supports the same directory option;
generic v2 exports default to their fixed `sidecars/` child. `verify_streams`
requires an explicit `sidecar_reference` and directory for v2 observations.
No interface enables CE, native IPC, memory operations, or live qualification.

## Acceptance and limits

LP01 retains the exact failing baseline. LP02–LP04 require complete synthetic
sessions on the original hierarchy, short paths, longer paths, and Unicode paths.
LP05 checks direct and transport boundaries. LP06 covers closure, content,
replay, traversal, links, and crash remnants. LP07 checks the three negative
scenarios with zero guarded activity. LP08 preserves the three-attempt budget,
nine Starts, nine allocations, no refund/retry, and NORMAL trace equivalence.
LP09 requires full ordinary and long-path repository regression. LP10 requires
preservation, isolated byte-exact patch replay, independently pinned verification,
and `git diff --check`.

The new dated report records actual commands, path lengths, exit codes, hashes,
all intermediate failures, and the completed matrix. This contract alone is not
a PASS result. Synthetic success cannot promote any native or live status.
`IMPLEMENTED_PENDING_CE_QUALIFICATION`, `ATTACHMENT_HANDLE_UNVERIFIED`,
`NOT_PRODUCTION_AUTHORIZED`, and unrelated A6/R3/T1 statuses remain unchanged.
