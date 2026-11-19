# H3-A4-P1R approval authenticity: inactive review-only contract

This independent Python 3.14 standard-library component authenticates exact A2
approval bytes against a separately provisioned public-key policy. It has no
runner, CE interface, process attachment, memory API, Write Arm, production
constructor, automatic approval or A2/A3 integration. Import performs no file,
process, network or clock operations. Nothing is selected from the current
directory or from a request. The four A4 files are the entire implementation.

Successful authentication is `SIGNATURE_AND_POLICY_MATCH_REVIEW_ONLY`. Every
result has `authorization_status=NOT_PRODUCTION_AUTHORIZED`, `write_ready=false`,
`handoff_write_ready=false`, `write_attempted=false`, `restore_attempted=false`,
and zero memory read/write attempts. This is neither a source-authenticity
receipt nor permission to write or restore. Test public keys, A2's synthetic
authority/domain, a digest, `approved=true`, H2
`VALUE_CONSISTENT_NOT_AUTHORIZED`, A1 `SOURCE_REVIEWABLE_NOT_AUTHORIZED`, and an
A3 stored record cannot become operational authority.

## Explicit API and bootstrap

```python
auth = ApprovalAuthenticator(
    verifier_backend, canonical_policy_bytes,
    expected_policy_id=independently_pinned_id,
    expected_policy_sha256=independently_pinned_hash,
    clock=trusted_clock, replay_guard=trusted_review_ledger,
)
result = auth.evaluate(approval_bytes, detached_signature_bytes, action)
public_bytes = auth.render(result)
```

All arguments are required. The policy must come from a separately approved
bootstrap and custody channel, never the request, its directory, A3 or a
requesting process's writable policy inventory. The expected ID and hash must
come from that independent channel. Computing an expected hash from a supplied
request policy does not establish trust. The probe does this only to provision
its own expressly synthetic ephemeral test policy, not an owner trust root.

Dependencies are captured once as bound methods/functions. Policy JSON becomes
frozen scalar/tuple records; the original dict is not retained. A backend must
declare `review_only=True` and the exact pinned public-keyring digest. This
marker is a restriction, not authentication of Python code. A trusted native
bootstrap explicitly constructs `NativeGpgvBackend`; a fake backend exists only
in tests. No selector, environment switch or request field enables production.
Mutable or hostile bootstrap code is outside an in-process component's ability
to authenticate itself and blocks deployment.

`clock()` supplies `(canonical_utc, monotonic_integer_ms)`. It is called before
and after verification, never at import. Both readings must be in the approval,
policy, signer and revocation-freshness windows. Monotonic time cannot regress,
must fit the approval's elapsed bound, and must agree with UTC elapsed within
one second. This tests a clock boundary, not Windows clock integrity/continuity.

`replay_guard.claim(policy_id, request_id, approval_hash, signature_hash)` must
atomically return literal `True` once. A validly framed attempt consumes its ID
before invoking crypto; an uncertain verification cannot silently retry. The
included `ReviewReplayGuard` is a bounded process-local review ledger, shared
across authenticator instances, with one namespace across actions and policy
versions. It rejects duplicates and exhaustion at 4,096 IDs. It is deliberately
not a durable execution reservation. Cross-process/durable replay exclusion
requires a separately reviewed protected policy service; fresh-process native
verification is a read-only cryptographic recheck, never a fresh write grant.

Results are frozen slotted records. `render` checks object identity and an
internal immutable byte snapshot, rejecting copies, foreign objects and forced
attribute changes. Public bytes include only fixed statuses, nonoperational
flags and exact approval/signature/policy hashes, not raw approvals, addresses,
PIDs, executable paths, key UIDs, stderr or exception messages. Python code with
arbitrary access to the runtime can still replace the implementation; these
checks are not a sandbox. An A4 result does not implement A2's verifier return
triple and cannot be passed to `Protocol.new_synthetic` as a grant.

## Canonical approval bytes

The unchanged A2 contract is authoritative. A4 accepts ASCII `key=value\r\n`,
including final CRLF; 16,384 bytes maximum; 1-512 bytes per value; exact ordered
fields, no BOM, controls, Unicode, duplicate, missing, reordered or extra field.
There is no normalization or reserialization before verification. The original
`bytes` object and exact detached signature go to the verifier.

Common fields, in order:

```text
schema source_kind environment request_id authority trust_domain action
case_id session_id candidate_address current_float current_pattern
target_float target_pattern pid process_created_utc executable architecture
attachment_id scene_id issued_utc expires_utc max_elapsed_ms
```

Write appends these fifteen fields, totaling 38:

```text
source_batch_id source_case_id source_session_id
h1_log_id h1_log_sha256 h1_summary_id h1_summary_sha256
h1_diagnostic_id h1_diagnostic_sha256 h1_companion_id h1_companion_sha256
h2_id h2_sha256 a1_id a1_sha256
```

Restore appends these three fields, totaling 26:

```text
source_request_id source_preparation_sha256 source_receipt_sha256
```

Schemas are `h3_write_approval_v1` and `h3_restore_approval_v1`; actions are
`single_float32_write_once` and `single_float32_restore_once`. Both require
`source_kind=h3_single`, `environment=synthetic_only`,
`authority=synthetic-authority`, `trust_domain=h3-synthetic-tests-v1`. These are
preserved A2 test restrictions, never proposed production defaults.

Operation/scope IDs use `[a-z][a-z0-9-]{0,63}` without trailing hyphen. Upstream
IDs use the A2 1-80-character ASCII alphanumeric/underscore/hyphen grammar, no
`__`, trailing underscore or `nil`. Six upstream IDs must differ; restore's
source request must differ from its new ID. Digests are 64 lowercase hex digits.
Addresses are positive canonical uppercase `0x%X`, at most `0x1FFFFFFFFFFFFF`.
Float patterns are uppercase `0x%08X`; text must equal the exact finite
little-endian Float32 value rendered with Lua-compatible `%.17g`. Negative zero,
subnormals and maximum finite values are supported, without rounding or
tolerance. Equal current/target patterns are rejected.

PID is canonical decimal 1-4,294,967,295; architecture is x86/x64; executable
text follows A2's uppercase-drive absolute ASCII grammar (260 bytes maximum,
no alternate separators, traversal, streams, repeated separators or wildcards).
This field is only a declared binding, never an inspected executable or tool
path. UTC uses Gregorian `YYYY-MM-DDTHH:MM:SSZ`, years 1970-9999, no leap seconds.
Process creation cannot follow issue time; approval validity is positive and at
most 120 seconds with exclusive expiry; elapsed limit is 1-120,000 milliseconds.

## Independent public-key policy v1

Policy bytes are ASCII JSON from
`json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)` plus
LF. Maximum 16,384 bytes. Duplicate keys, noncanonical representations and
unknown/missing fields fail. The exact schema is:

```text
schema = h3_public_key_policy_v1
policy_id = independent lowercase token
purpose = TEST_ONLY_REVIEW
authority = synthetic-authority
trust_domain = h3-synthetic-tests-v1
valid_from, valid_until = canonical UTC, expiry exclusive
revocation_checked_utc, revocation_valid_until = canonical UTC
keyring_sha256 = exact public-only binary keyring digest
signers = list of one or two signer records
```

Each signer record has exactly `primary_fingerprint`, `signing_fingerprint`,
`role`, `valid_from`, `valid_until`, `revoked`. Fingerprints are complete,
nonzero, uppercase 40-hex v4 fingerprints. A signing subkey must be explicitly
named and must match gpgv's primary fingerprint too; no suffix matching or
automatic subkey acceptance. Each record has exactly one role, write or restore.
Primary fingerprints, signing fingerprints and roles must each be unique.
No implicit dual-role key, overlapping rollover or selection among policies is
allowed. Key rollover requires a newly independently pinned policy.

Signer validity must fit policy validity; `revoked` is an actual Boolean and a
revoked signer always fails. Revocation freshness must fit policy validity and
span no more than 24 hours. Current time must fall inside it. This is an
independently provisioned offline assertion, not evidence of a live revocation
lookup. Owner-to-key binding, custody, key metadata/algorithm vetting, policy
distribution, protection against rollback and renewal are deployment gates.

## Native detached OpenPGP boundary

`NativeGpgvBackend` requires a fixed absolute `gpgv.exe`, independently checked
SHA-256, immutable public-keyring bytes, a trusted existing disposable scratch
root, and explicit `approved_test_only=True`. Paths cannot come from an approval.
The narrow local Windows path guard rejects relative/UNC/device paths, streams,
aliases, traversal, reparse components, file hardlinks and unexpected types.
The root must remain controlled by the bootstrap; static checks and before/after
hashes do not solve adversarial replacement races, hostile DLL loading or an
attacker controlling the same OS identity. Such custody is unqualified for
production, not silently delegated to A3 or an ACL mutation.

Each verification creates a fresh scratch child, copies exact inputs and the
pinned public ring with exclusive creation, and supplies an empty explicit
`--homedir`. The only command is an argv array equivalent to:

```text
<pinned-gpgv.exe> --homedir <empty-home> --keyring <public.gpg>
  --status-fd 1 --weak-digest SHA1 -- <detached.sig> <approval.bin>
```

No shell, PowerShell/cmd interpolation, agent, secret key, import, personal
GNUPGHOME, trust-database mutation or network lookup is used by the product
backend. Environment is restricted to its own GNUPGHOME/TEMP/TMP and SystemRoot.
Explicit keyring selection prevents default keyring lookup. Binary and all
input bytes are checked before/after; unexpected home contents reject. Scratch
inputs remain for diagnosis and are never automatically deleted.

Only bounded definite-length binary OpenPGP packets are supported. An approval
signature must contain exactly one signature packet (tag 2), at most 16 KiB.
Public rings are at most 64 KiB and permit only public key/subkey, UID/attribute
and signature packets. Secret packets, compressed/encrypted/literal data,
armor, partial-length and concatenated signatures fail before tool invocation.
This envelope parser does not implement or substitute for cryptography.

Native subprocesses have a 10-second verification timeout, bounded argument
count/length, 16-KiB independent stdout/stderr limits enforced during reads, and
bounded termination/join. Nonzero exit, timeout, unavailable binary, output
overflow, changed input, malformed or unknown status always reject. Diagnostics
are not published. The synthetic suite uses a fake subprocess boundary;
its success never qualifies an actual executable.

Success requires exit zero AND exactly one NEWSIG, GOODSIG and VALIDSIG context,
consistent key ID, full signing and primary fingerprints, no conflicting
KEY_CONSIDERED (at most four), and a consistent optional SIG_ID. Unknown status,
failure/revocation/expiry status, a second signer/signature or malformed records
fail. The currently narrow crypto profile is v4 EdDSA (OpenPGP algorithm 22),
SHA-256/384/512 (8/9/10), and binary-document signature class 00. Native fixtures
use Ed25519/SHA-256; future algorithms/status variants require explicit review.
Signature creation must fall within the signed approval and signer windows,
cannot be in the future, and signature expiry, if present, must not have passed.
Signature time is a signer assertion, not a trusted timestamp service.

GnuPG's primary documentation explicitly states that gpgv trusts its supplied
keyring and does not check key expiry/revocation. The independent policy checks
above are therefore mandatory, not inferred from exit zero or GOODSIG. See the
[gpgv manual](https://www.gnupg.org/documentation/manuals/gnupg/gpgv.html) and
[GnuPG status specification](https://github.com/gpg/gnupg/blob/master/doc/DETAILS).

## Failures and qualification

Construction errors include `UNPINNED_POLICY`, `POLICY_PIN_MISMATCH`,
`INVALID_POLICY`, `AMBIGUOUS_POLICY`, `UNPINNED_BACKEND`,
`PUBLIC_KEYRING_REQUIRED`, `INVALID_DEPENDENCIES` and native path/binary errors.
Evaluation returns bounded rejection classes for approval/action/packet schema,
inactive signer, stale policy, role mismatch, clock failures, replay, busy
instance, crypto failure, status ambiguity, signer mismatch, crypto/time policy,
timeout, tool availability, output limit or input mutation. Exceptions from
injected dependencies are sanitized to a fixed allowlist; unknown messages are
`DEPENDENCY_REJECTED`. No exception text can forge success.

P1R must run the new tests alone, the unchanged prior 2,958 tests from twelve
accepted modules, and the combined inventory. Require exact prior test IDs,
zero failed/errors/skipped/deselected/xfail, real subprocess exit zero and
independently reconciled JUnit totals. Use qualified Python 3.14.3, pytest 9.1.0,
Lupa 2.8/Lua 5.4 with bytecode, cache, plugin autoload and uncontrolled `.pth`
processing disabled. Keep scratch/logs/JUnit outside the repository. Compile/AST
check all three new Python files, inspect untracked whitespace, and review trust
bootstrap, test-key isolation, ambiguity and lack of production integration.

The synthetic suite checks every field's framing and inventory, canonical
values, all critical rejection boundaries, explicit subkeys, role separation,
policy pinning/rollover, immutable output, dependency failures and original
byte forwarding. It tests the actual A2 constructor/verifier refusal to accept
an A4 result as a grant, without changing A2. Fake gpgv/packet fixtures have no
cryptographic value and never create production permission.

## T1 operator procedure and evidence

The probe is `tests/h3_approval_native_probe.py`, deliberately outside pytest's
default naming. P1R's external receipt supplies a concrete PowerShell command,
four-source manifest, all four source hashes, interpreter hash and hashes of
fixed gpg/gpgv/gpg-agent/gpgconf binaries. Manifest encoding is sorted, indented
ASCII JSON plus LF, mapping each of the four source paths to bytes/SHA-256;
this differs deliberately from the compact policy encoding. Hashes belong in
the external receipt to avoid self-referential source hashes.

Run only in an ordinary non-administrator PowerShell session as the approved
Windows test principal, mode `approval-native-only`, diagnostic `debug`, with
`-I -B -S` and no optimization. The dedicated parent is exactly
`%LOCALAPPDATA%\ChromeProject-H3-Approval-Qualification`; the probe displays the
actual SID/path/manifest and requires interactive `APPROVE` before creating the
parent if missing and a new UUID child. It checks the expected SID, nonadmin
token, source/runtime/tool pins and parent path before mutation. Missing tools,
policy/root mismatch or inspection denial stop; no installer, elevation, ACL
change, alternate root or retry is authorized.

The R2/S1 operator amendment explicitly replaces the former **in-home-only
socket assertion**. The disposable test GNUPGHOME remains inside the new
`auth-<32 lowercase hex UUID>` child. For the pinned Windows GnuPG 2.4.8 profile,
the only socket directory is `%LOCALAPPDATA%\gnupg\d.<derived suffix>` for that
exact home. The primary `S.gpg-agent` and the separately approved
`S.gpg-agent.ssh` artifact must both belong to this launch. SSH connections are
forbidden. No personal home/key, existing Agent, commit-signing key, YubiKey or
smartcard is permitted. The old failure remains
`BLOCKED_HANDOFF_H3_A4_T1_AGENT_SOCKET_NOT_FRESH_ISOLATED`: the old parent-path
comparison short-circuited before the existence check, proving neither a stale
socket nor a personal-Agent connection.

### Windows socket mapping and freshness

`IsolatedAgent` is a probe-only state machine with injected filesystem/process
operations. It does not change the product verifier. Its independent derivation
uses ASCII lowercase home text, backslash-to-slash conversion, the first 80 bits
of SHA-1 and z-base-32, as implemented in
[GnuPG 2.4.8 homedir.c](https://github.com/gpg/gnupg/blob/gnupg-2.4.8/common/homedir.c).
The digest is a directory name, not identity or freshness evidence. A fresh UUID
home is required even though case variants can hash identically.

The Windows known-folder API supplies LocalAppData without a create flag; its
exact spelling must match the environment. The dedicated parent, newly planned
home and derived directory are displayed before interactive `APPROVE`.
Canonical inputs accept only bounded ASCII uppercase-drive absolute paths.
UNC/device paths, traversal, repeated separators, alternate separators, short
names, reserved names, streams, trailing dots/spaces and Unicode are rejected,
not repaired. Windows case-insensitive `Path` equality is not sufficient:
reported and handle-derived paths must match the original spelling exactly.
The existing native-path guard checks each component for reparse points. Handle
checks additionally bind final path, volume/file ID, creation time, object type,
single-link endpoint files, owner SID and DACL. Missing/inaccessible/ambiguous
metadata fails closed. The conservative DACL profile accepts ordinary allow/deny
ACEs only; write-granting ACEs must name the operator, SYSTEM or Administrators.
No ACL is changed to make a path qualify.

Before **any GnuPG metadata command**, the exact derived directory must be absent
according to `lstat`; permission errors are not absence. A pre-existing `d.*`
directory, even empty, always fails without inspecting its endpoints. The
shared `%LOCALAPPDATA%\gnupg` parent may exist if its canonical identity, owner
and DACL pass; it is never enumerated and no siblings/default socket are read.
If absent, that base is created exclusively. The derived directory is then
created exclusively by this run and its identity retained. A creation race is
a failure, never adoption. This is the sole accepted interpretation of a
directory that exists at the later launch check. It avoids attributing an
unobserved directory to `gpgconf --list-dirs`, which can create it as a side
effect. All relevant directory identities must remain unchanged. The test home
must still be empty before launch, and the socket directory must remain empty;
any stale primary/SSH socket or other entry rejects before activation.

Every metadata invocation has an explicit test `--homedir`. All four tools must
report version 2.4.8 and retain their independently pinned hashes. Named
`gpgconf --list-dirs` queries for homedir, socketdir, primary, SSH, extra and
browser paths must match independent expectations exactly. Named output in
2.4.8 is raw single-line text, so it is **not percent-decoded**; malformed or
multiple lines reject. The component report must still identify the pinned
Agent binary. Portable/redirected/alternate home or socket mappings fail rather
than gaining a new exception. No pathname report itself authorizes a connection.

### Launch, endpoint ownership and cleanup

The probe directly starts the pinned Agent with explicit home and isolated
environment, `--no-options --daemon --no-detach --disable-scdaemon`, external
cache disabled, loopback allowed, and **`--extra-socket none --browser-socket
none`**. It enables neither SSH, PuTTY nor Win32-OpenSSH support and does not
write an Agent configuration. Windows 2.4.8 keeps daemon execution in the
created process; the Unix fork behavior is not assumed. That version also
creates its SSH artifact independently of enabling SSH support. See the
[versioned Agent implementation](https://github.com/gpg/gnupg/blob/gnupg-2.4.8/agent/gpg-agent.c).

The retained `Popen`/CreateProcess handle must identify the exact launched PID,
pinned executable path, expected token SID and creation time within the launch
interval. No numeric foreign PID is opened. Read-only Windows TCP owner tables
then bind the freshly created primary and SSH descriptor ports to this exact
process **before any gpg connection**. Only two distinct IPv4 loopback listeners
are accepted; duplicate/competing listeners, additional owned IPv4/IPv6
listeners, unexpected directory entries, missing identity and inspection errors
reject. The table is transient metadata; unrelated Agent processes/endpoints
are never opened or probed. The primary descriptor must use decimal port/LF
plus 16 nonce bytes; the SSH artifact must use the Cygwin stream descriptor.
These formats follow
[libassuan's Windows socket implementation](https://github.com/gpg/libassuan/blob/libassuan-3.0.2/src/assuan-socket.c).
Unknown/redirected formats reject. Reading a descriptor does not send or use its
nonce; evidence retains its hash, never nonce bytes.

Startup waits only a bounded five seconds for missing artifacts. No SSH,
browser, extra or unproven primary connection is used for discovery or GETINFO.
All subsequent gpg calls retain the fixed `--no-options --homedir ...
--no-autostart` prefix, batch loopback and empty passphrase. Before and after
each such call, the probe rechecks directory/process identities, descriptor
identities and bytes, and listener ownership. Any failure stops further client
use; it never adopts a replacement. Test keys remain clearly marked TEST ONLY,
at example.invalid, one-day Ed25519 sign-only, with key retrieval disabled.

Cleanup never calls `gpgconf --kill`, performs a negative key-generation probe,
or deletes any path. Only a process whose launch identity was established may
be terminated through its retained handle, after rechecking that identity.
This remains safe if an endpoint is uncertain: Windows TerminateProcess does
not run Agent path-cleanup handlers. If process identity itself is uncertain,
no termination occurs and the run fails with retained evidence; an operator
must review the leftover launch under separate authorization. Successful
shutdown requires the retained process to have exited and no remaining owned
listener. All test directories, private test files and socket artifacts remain
local and cannot be reused. Shutdown is bounded and does not contact any socket.
The `isolated_agent_stopped` native check now records this handle-based method.

The handles/metadata are evidence under the approved ordinary operator's root
custody. They do not defeat a hostile same-identity process or administrator,
prove DLL provenance, or provide atomic isolation across all checks and gpg
connections. Such custody/races remain unqualified; an observed inconsistency
always blocks. No production constructor, authorization flag, signature schema,
policy check or public-only gpgv boundary changes.

The required native checks are exact-byte write/restore signatures, corrupted
signature, one-byte canonical approval mutation, wrong signer, absent signer,
role mismatch, malformed policy, duplicate signature packets, injected extra
status after real gpgv, fresh-process read-only verification, replay rejection,
revoked/expired independent policies, test-key nonauthorization, source
integrity and isolated-agent shutdown. Policy/status injections are labeled;
they do not claim that gpgv itself enforces policy expiry or that a native key
revocation certificate was issued. The fresh process rechecks retained files
without input writes. Every required check must explicitly PASS.

Native success is labeled only `NATIVE_TEST_SIGNATURE_VERIFICATION_ONLY` and
prints `native-parent-exit-code=0`, the exact ZIP path and ZIP SHA-256. Return
the original `native-auth-bundle.zip` bytes and those console lines. The ZIP
contains exactly these allowlisted files, never a recursive directory export:

```text
native-receipt.json
native-results.json
binary-identity.json
test-keyring.json
source-manifest.json
subprocess-summaries.json
agent-isolation.json
public.gpg
test-policy.json
synthetic-write.approval
synthetic-restore.approval
synthetic-write.sig
synthetic-restore.sig
synthetic-wrong-signer.sig
synthetic-absent-signer.sig
```

The receipt binds each other file by exact size/hash, the source manifest,
approved SID/parent hashes, required inventory and nonoperational flags. The
public fixtures permit independent offline signature verification of the exact
returned bytes; they disclose only fictional process/source values. Binary
identity includes fixed basenames, versions and hashes. Subprocess summaries
include exit codes and bounded output sizes/digests, not raw private output.
Every completed tool invocation, including product gpgv calls, retains its
bounded original stdout/stderr in the scratch child. Partial result/summary
files survive a failed check or shutdown; these never substitute for a PASS ZIP.
The directly launched Agent uses bounded pipe capture and a retained process
handle. `agent-isolation.json` binds the test home/derived directory, pre-start
absence, launch PID/time/binary hash, SID hash, endpoint metadata/digests and
shutdown method. `partial-agent-isolation.json` is retained even on failure;
neither private keys nor socket nonces are exported.
Keep original scratch data locally. Do not edit/repack the ZIP. If Codex cannot
read it, upload the exact bytes; never modify ACLs or substitute a new run.

## Conditional C1 and remaining deployment gates

R2-S1 is source-only while qualified Lupa is inaccessible. Its only completion
status is `PASS_HANDOFF_H3_A4_R2_S1_SOURCE_REPAIR_STATIC_READY_TESTS_PENDING`.
AST/compile/whitespace review and independent stdlib mock tests do not qualify
the Windows adapters or replace pytest/Lua validation. The added unittest block
in `test_h3_approval_auth.py` is also part of the future full pytest inventory;
all original 708 H3-A4 and 2,958 legacy identities must remain unchanged.
H3-A4, legacy and combined qualification are `NOT_RUN` until the qualified
Python 3.14.3 / pytest 9.1.0 / Lupa 2.8 genuine Lua 5.4 runner is available,
including backend SHA-256
`0b763f9765d059ebff66d11a2867176b263f7f6fbbb51cbdd876aa05f7f5c9b2`, or a
separately approved compatible runtime. No skip/deselection/xfailed replacement
is acceptable. Historical 3,666 tests cannot be counted as current runs.
S1 creates no operator wrapper and executes no native T1, staging, signing,
commit, push or tag. A new T1 wrapper with new pins follows only complete R2
qualification; the obsolete failed T1 wrapper must not be reused.

No staging/commit/push occurs before P1R and independent T1 acceptance, exact
four-source manifest agreement and resolved review findings. Failure stops at
the failed stage. A native test PASS is not owner authorization. After all gates,
C1 permits exactly four added files, one GPG-signed commit with subject
`feat(handoff): add nonoperational approval signature verifier`, exact committed
Git-Blob export and regression, then one ordinary non-force HTTPS push and
GitHub signature/tree/blob/tag readback. No new tag, amend, rebase, force push,
silent retry or inclusion of the four pre-existing D2 paths is authorized.

Production remains blocked on real owner-to-key/role policy and custody, pinned
binary/dependency provenance, protected root distribution/revocation freshness,
durable replay service, runtime integrity and race resistance. H3-A4-P2 must
authenticate actual H1/H2/A1 bytes and provenance inventory, not just declared
digests. H3-A5 must qualify actual process-instance/CE attachment identity and
clock continuity. H3-A6 must separately compose and review write/restore with
new explicit operational permission. A2 still has no production constructor.
