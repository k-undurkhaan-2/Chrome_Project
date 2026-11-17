# H3-A3 isolated Windows evidence-store prototype

This is a default-inactive Python 3.14 standard-library prototype. It has no CE
adapter, target-process API, Write Arm, production constructor, Lua dispatch,
approval verifier or deployment route. `synthetic_only` remains a restriction,
not authentication. H3-A4/A5/A6 and production use remain unqualified. The existing
H3-A2 write/restore modules and their contracts are unchanged.

## Interfaces and states

Only the trusted test bootstrap supplies `EvidenceStore(backend)`. Importing the
module performs no filesystem, process, clock, network or Win32 activity.
The explicit native backend requires `approved_test_root=True`; it is a storage
test bootstrap, not a production authorization constructor. Never construct it
from protocol approval bytes. There is no implicit/default backend or root.

| Method | Successful return | Required behavior |
| --- | --- | --- |
| `reserve(id, "reservation", bytes)` | literal `True` | Atomically consume ID; publish/independently reopen exact immutable reservation. |
| `publish(id, kind, bytes)` | literal `True` | `kind` is preparation or receipt; check predecessors and no-replace publication. |
| `read_record(id, kind)` | exact `bytes` | Reopen committed records and verify claim, schema and chain; never expose staged bytes. |
| `finalize_receipt(id, sha256)` | literal `True` | Only confirmed API/dual-readback success with intact preparation and reservation can finalize. |
| `read_finalized(id)` | exact receipt `bytes` | Reopen finalization metadata and every predecessor; verify all links again. |

Every unsuccessful call raises `StoreError`; no truthy status string represents
success. `True` describes verified storage visibility within the qualified scope,
not guaranteed survival of unexpected machine power loss. A future production
adapter must resolve that durability gap before satisfying the full A2 promise.

The namespace is shared across write/restore, objects and processes. A trusted
bootstrap initializes exactly one fresh empty root, writing `namespace` with the
root's volume serial and 128-bit file ID. Reopening never initializes it; missing,
different or malformed namespace bytes fail. The operator must retain that root
identity externally and pass it as `expected_identity` on native reopen. Replacing
the entire root or losing all storage cannot be solved by an internal marker.

Each operation has `r-<id>.claim`, `.gate`, `.reservation`, `.preparation`,
`.receipt`, and `.finalized`. Claim is `CREATE_NEW` before reservation publication.
Even an empty/partial claim consumes the ID. Its immutable body binds the exact
reservation digest and namespace digest. No operation deletes, replaces or frees
a claim. A crash-released OS sharing lock on `.gate` serializes stage changes;
the persistent claim, not this lock, provides anti-replay. The gate's immutable
bytes are checked on every acquisition. A busy gate fails without waiting/retry.

Each record is created exclusively as `<name>.stage`, written once with exact
byte-count verification, flushed, closed and independently reopened/compared.
It is then renamed within the pinned root with no replace/copy/reboot flags and
independently reopened/compared at its published name. Stage bytes never satisfy
`read_record`. Fixed stage names prevent retry after an incomplete publication.
No cleanup occurs. The next transition rejects remaining stage artifacts.

Order is reservation, preparation, receipt, finalization. A2's prewrite rejection
may publish an `UNCONFIRMED`, non-attempted receipt with no preparation and a `nil`
preparation hash. This closes the operation: a preparation cannot subsequently
be added. Confirmed receipts always require preparation. Publication after an
ambiguous storage failure is conservatively blocked, even if a failure receipt
would otherwise be useful. Existing immutable predecessors remain evidence.

Finalization is a separate immutable store metadata record binding the namespace,
ID, action and all three exact digests. It is constructed internally; the public
API never accepts caller-supplied finalization bytes. Merely finding a receipt,
or changing its success flag, is insufficient. A process crash after a complete
finalization rename can leave a retrievable confirmed chain despite a lost caller
acknowledgement. It does not permit replay or imply production restore authority.

## Exact A2 record contract

Records use the unchanged ordered 28 fields from
`handoff_write_restore_protocol_contract.md`, printable ASCII `key=value\r\n`,
mandatory final CRLF, maximum 16,384 bytes and maximum 512 bytes per value.
Unknown, missing, duplicated, reordered, LF-only, control/BOM/Unicode, mixed
source, noncanonical numeric or wrong-action records fail. A2 write and restore
share the reservation schema and have distinct preparation/receipt schemas.

Validation includes canonical uppercase address/pattern syntax, finite exact
Float32 and Lua-compatible `%.17g` text (including negative zero/subnormals),
Gregorian UTC windows, nondecreasing UTC/monotonic measurements, elapsed limits,
all immutable common fields and predecessor hashes. H1, H2, A1 and Full text
cannot substitute for H3 records. The tests also consume bytes emitted by the
actual A2 synthetic Lua producers, without changing fixtures or host
`debug.traceback`.

Only `CONFIRMED`, attempted/api-result/api-ok/readback-ok/execution-success all
`true`, failure `nil`, complete consistent records can finalize. Unconfirmed A2
failure receipts can be retained but never promoted. Digests and consistent
records do not authenticate their origin, scene, authority or memory claims.
Coherent forgery by an actor controlling the root/runtime remains unqualified.

IDs use lowercase `[a-z][a-z0-9-]{0,63}`, no trailing hyphen and no Windows device
names. The reserved-name exclusion is a deliberately stricter storage subset of
the A2 token grammar. No case folding, Unicode normalization or input repair is
performed. Uppercase, Unicode, ADS, slash/backslash, drive/device/UNC, dot or space
aliases are rejected before filesystem activity. Callers never supply filenames.

## Native trust and API boundary

The operator explicitly approves a dedicated disposable parent under the actual
product/test Windows SID. It must contain no production data. The probe creates
one new UUID child; all stores, signals, crash artifacts and reports stay inside
it. There is no recursion outside the child and no deletion at all. No ACL,
registry, Defender, firewall, elevation, installer or privileged service changes
are made. The Codex sandbox principal cannot qualify the operator's principal.

The supported root subset is an existing uppercase drive-letter absolute path,
at most 160 characters, ASCII components up to 80 characters with no ambiguous
dot, trailing dot/space, reserved device, stream, short-name tilde or reparse
syntax. Long-path, UNC, remote, FAT/ReFS and case-sensitive-directory variants
are deliberately unsupported. The suggested `%LOCALAPPDATA%` parent is only an
example; do not switch to an unapproved root after failure.
The probe rejects drive roots, the repository, `D:\H1_evidence`, Windows and
Program Files subtrees before creating its child, and validates its longest
planned child path before any scratch mutation.

At runtime every component from drive root to store root is opened with
`CreateFileW(FILE_READ_ATTRIBUTES, FILE_SHARE_READ, OPEN_EXISTING,
FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT)`. These handles remain
open without write/delete sharing until shutdown. This may fail on a busy root;
the program must report that failure, never widen sharing as a fallback. No
ownership or ACL modification is required, but the principal must have the
inspection rights needed for this conservative security argument.

Handle metadata rejects reparse/type mismatches, verifies normalized final path,
and pins volume serial + 128-bit file ID using `FileIdInfo`. Directory case
sensitivity must be readable and disabled. Each critical operation rechecks all
held identities and independently reopens their named paths. Root errors retain
the exact component and Win32 error; sanitized reports publish the component's
depth/hash, while the local console shows its full diagnostic path. An inability
to inspect an ancestor is `ROOT_TRUST_UNPROVEN`, not proof of root safety.

Files are opened with `FILE_FLAG_OPEN_REPARSE_POINT`; metadata rejects directories,
reparse objects and link count other than one. Reopened read handles deny
write/delete sharing. Reads bound the byte count and compare identity, size,
attributes and last-write metadata around the read. Critical paths are strict
basenames in the pinned root. No existence-check-then-overwrite primitive exists.

The injectable Win32 boundary uses explicit `WinDLL` calling conventions and
pointer-width `HANDLE` types. Relevant primary API specifications:

- [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew): exclusive `CREATE_NEW`; no `CREATE_ALWAYS` or truncating open.
- [FileIdInfo](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info): file identifier combined with volume serial.
- [GetFinalPathNameByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew): normalized final path check.
- [FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers): flush successful complete writes; propagate failures.
- [MoveFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw): use only `MOVEFILE_WRITE_THROUGH`; omit replace and cross-volume copy flags.

Flush and write-through rename are not experimental evidence of power-fail
metadata ordering or hardware-cache survival. No volume flush or administrator
handle is used. Cross-process exclusion is ultimately qualified by the native
probe, not inferred from a fake filesystem or documentation.

## Failures and quarantine

`INVALID_REQUEST_ID`, `INVALID_KIND`, `INVALID_RECORD`, `CHAIN_MISMATCH`,
`CHAIN_TIME`, `INCOMPLETE_CHAIN`, `NOT_CONFIRMED`, `STAGE_ORDER`, `COLLISION`,
`BUSY`, `MISSING` and `REQUEST_QUARANTINED` are fail-closed caller/state results.
An ambiguous native I/O, short write, readback, identity or trust error poisons
the live store and attempts an exclusive namespace-wide `quarantine` marker.
Any such marker, even partial/empty, blocks later opens. All original artifacts
are retained. No automatic retry, reconstruction, deletion or recovery promotion
is supported. Inspection is read-only through the backend in an approved context.

If storage is so unavailable that neither the claim nor quarantine marker can
persist, the caller MUST quarantine the entire root externally and refuse any
automatic restart/reuse. This is an explicit limitation, not a claimed durable
consumption. The prototype cannot guarantee safety after total storage loss or
hostile coordinated removal of its journal. A root is never silently recreated.

## Qualification and operator T1 recipe

P1R consists of the new deterministic suite, the unchanged 2,386 tests in the
eleven baseline suites, their combined run, independent JUnit/count checks,
syntax/whitespace checks and focused source review. All run with Python 3.14.3,
pytest 9.1.0 and Lupa 2.8/Lua 5.4, bytecode/cache/plugin autoload disabled and all
outputs/temp roots outside the repository. No skip, xfail or deselection counts
as PASS. Synthetic tests are never reported as native qualification.

The standalone `tests/h3_windows_store_native_probe.py` is deliberately not
named `test_*.py` and is not automatically collected. `--help` needs no root.
The handoff receipt supplies exact four-source hashes, their canonical manifest
digest, probe SHA-256 and qualified interpreter SHA-256. The manifest digest is
SHA-256 of `json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=True)` plus
LF, encoded ASCII; each relative source entry has `bytes` and `sha256`. These
values stay outside this contract to avoid self-referential hashes.

Before executing, the operator confirms the ordinary non-elevated Windows
identity is the approved product/test principal using `whoami /user`, and
confirms the proposed disposable parent contains no production data. A later
different runtime account is not automatically equivalent. Do not change DACLs
to give Codex access. The provided copyable PowerShell handoff command uses:

```powershell
& 'D:\armedforces.io-v2\.venv\Scripts\python.exe' -I -B -S `
  'D:\armedforces.io-v2\tests\h3_windows_store_native_probe.py' `
  --mode storage-native-only --diagnostic debug `
  --scratch-parent '<approved-existing-parent>' --approve-disposable-parent `
  --expected-sid '<approved-runtime-SID>' `
  --expected-snapshot '<four-source-manifest-SHA256>' `
  --expected-python-sha256 '<qualified-interpreter-SHA256>'
```

Use the concrete command from the completion handoff, not these placeholders.
No PID, search value, single/full screening mode or private H1 identity is needed.
Native memory operations are exactly zero. All payloads are fabricated public
storage fixtures. Only bounded probe-owned helpers are spawned or terminated.

The native checks require a four-process start barrier and exactly one same-ID
winner, restart rejection, exact immutable-chain readback, native no-replace
rename, uncertain receipt rejection, partial-claim quarantine, actual child
process exits at publication boundaries, and fault-injected acknowledgement
loss around real native operations. Native injected failures are labeled as
injected; they are not claims that Windows itself returned a flush/close error.
All 34 feasible checks are explicitly enumerated in the probe; missing checks
or an unexpected `UNQUALIFIED` cannot produce PASS. The probe creates an owned
junction (through `FSCTL_SET_REPARSE_POINT`) and hardlink entirely inside its new
child, then requires actual native rejection of the junction root, junction
ancestor and linked file. It retains these fixtures without traversal/cleanup.
Malformed preparation/finalization fixtures are first written in isolated roots;
no previously published evidence is overwritten. Optimized Python (`-O`) is
rejected, so disabled assertions cannot turn an incomplete run into a PASS.

Stop for permission/root-trust errors, unexpected paths/collisions, unreadable
identity/filesystem metadata, less than 64 MiB free space, helper timeout or any
unhandled exception. Do not retry under elevation or use another root. Keep the
failed child and local console output. If root trust cannot be established, the
probe reports a sanitized failure on stdout and exact component locally on
stderr; it cannot safely promise to write a bundle into an untrusted directory.
When an independently revalidated child is available, `native-failure.json`
retains completed checks and the failure. No result from a nonzero parent exit
is accepted, even if an earlier partial report was written.

On success return only `native-bundle.zip` and its printed SHA-256. It contains
`native-receipt.json`, `native-results.json`, `process-race.json`,
`root-capability.json`, `file-integrity.json`, and `controlled-transcripts.json`.
Receipt hashes bind the sanitized reports and source/runtime snapshot. No raw
approval, credentials, private source logs or actual process data is exported.
Retain the original child locally for independent evidence inspection. Hashes
establish content consistency, not the operator's identity or authenticity by
themselves; the approved operator's handoff channel supplies that context.

Native PASS is limited to the recorded Windows build, architecture, filesystem,
root identity and SID. Required feasible checks must all pass; power-loss
durability, adversarial external concurrent modification and power-fail metadata
ordering remain explicitly `UNQUALIFIED`. No reboot/power cycle is requested.

Only accepted P1R and T1 evidence with these exact source hashes may unlock C1:
four explicit added files, one signed commit, isolated Git-Blob retesting, one
non-force HTTPS push and independent GitHub verification. Pending/failed T1 means
no staging, commit or push. No version tag is authorized by this work.
