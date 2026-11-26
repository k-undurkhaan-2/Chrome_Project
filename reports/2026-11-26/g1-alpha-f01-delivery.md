# G1-ALPHA-F01-CONFIG delivery and verification receipt

> Historical evidence only; not current operating instructions. Original recorded values and authority are unchanged. [Immutable original](https://github.com/k-undurkhaan-2/Chrome_Project/blob/9574ef9b83b29e603d1e067486f846a1c4bad59f/reports/2026-11-26/g1-alpha-f01-delivery.md). Current product guidance: [English Quickstart](../../docs/ce_mvp_quickstart.md).

Status: **READY_G1_ALPHA_F01_CONFIG_CONTROLLED_ACCEPTANCE**.

Ordinary generated CT ID1 now admits a persistent, explicitly selected local
`ALPHA_STANDARD / OWNED_SYNTHETIC` configuration without a preceding Lua Console
or API selection. This is configuration-seam readiness in the authorized owned
synthetic domain. **Full product configuration usability for a real input path is
NOT ESTABLISHED.** F02–F04 remain OPEN, with no inherited PASS. No release artifact,
tag, release, PR, new branch or successor task is created.

## Admission and scope

The maintainer's 2026-11-26 F01 specification and explicit implementation request
authorize this work only. Repository `k-undurkhaan-2/Chrome_Project`, existing
branch `armedforces.io-v2`, initial local/remote HEAD
`d8f93d517c374a45cfcc62f8a44520ae67b09f35` matched exactly. The index was empty.
The remote remained at the expected baseline at admission; no divergence, reset,
overwrite, history rewrite or force-push was needed.

The delivered source `6190a9f93ec72560ca5db5e616bc4cd411795efc` and historical M6
`4aed7bc48202271e5d08400d53511cf4828cbf01` are exact ancestors. The source-to-baseline
delta consists only of six documentation/report files. Local OpenPGP verification
passed for the baseline and these source/M6 anchors using the existing key
`86D51BCDBC946CF1389969D530479D840D9D562B`. GitHub independently confirmed the exact
baseline, parent, changed path and `verified=true / reason=valid`.

The specification, repository policy, README, loader, CT, preparation mechanism,
engineering config example/validation, impacted tests, INTEGRATION-1 delivery and
manual sheet, and PRE-RELEASE-PREP-1 readiness inventory were read before editing.
Baseline checks observed ordinary Start fail with `ALPHA_INPUT_REQUIRED`, no
fixture/scoring/native activity, inert status and preserved explicit mode locks.
The actual CT template defaults to the standard profile.

Existing user architecture/workflow edits, unrelated sources, private local config,
actual local CT and historical packages were preserved. The two historical
13-file packages were checked against their exact manifests, hashes, lengths and
maintained Git blobs. They are not replaced by, or upgraded through, this F01 result.
PRE-RELEASE-PREP-1 remains an engineering handoff with release eligibility not
established.

## F01.1–F01.7 observed outcomes

| Requirement | Actual result and evidence | Scoped outcome |
| --- | --- | --- |
| F01.1 local standard config loading | `ce_mvp.lua` reads the sibling `ce_mvp_config.local.lua` at explicit Start. A deliberately wrong CWD config was ignored. Import, CT syntax checks and ID2 did not read the file. | PASS, synthetic configuration seam |
| F01.2 public example | New `src/ce_mvp_alpha_config.example.lua` contains exactly the three versioned standard fields. Original `ce_mvp_config.example.lua` remains unchanged and retains its engineering meaning. Both are in the candidate manifest. | PASS |
| F01.3 normal CT Start | Default generated CT with `controlled=false`, real loader and local public-example copy started through ID1 with no preceding selection call. Status was `LOCAL_CONFIG / ACCEPTED`, `ALPHA_STANDARD / OWNED_SYNTHETIC`, provenance `synthetic`. The actual packaged CT independently passed the same check. | PASS under Lua 5.3/Lupa; no CE-host claim |
| F01.4 fail-closed diagnostics | Missing file, syntax/evaluation/shape/type/required-field failures, unknown fields, unsupported schema/mode/input, callback/factory/write fields and conflicting explicit selections rejected without fixture construction, scoring or target calls. Open/read/close failures used deterministic safe I/O doubles. A bad/missing config after clean Stop cleared previous completion/ranking; repaired files could not bypass the failed-session latch. | PASS |
| F01.5 inert sanitized ID2 | Cached admission/source/error fields printed alongside existing evaluation, qualification and mode fields. Known private sentinels, file paths and raw OS/config errors were absent from configuration diagnostics. ID2 changed no config-read, scoring, target or evidence counters. | PASS |
| F01.6 preserved compatibility/protection | Standard explicit and historical controlled paths, engineering loader/config validation, stop policy, clean restart, mode lock, cleanup uncertainty and strict QSG factory/writer checks passed their selected existing suites. ID3 stayed independent/read-only. | PASS in existing safe doubles; no native qualification |
| F01.7 privacy/no overwrite | Preparation never changed a supplied existing private file. The operator's real config/CT and 58 inventoried pre-existing paths retained their baseline identities. Root local config and generated CT remain ignored; F01 candidate/test/local receipt trees have a scoped ignore rule. Only public maintained files and handoff documents are staged. | PASS |

These are separate F01 outcomes, not additions to any historical acceptance or
effectiveness matrix. The success token does not grant native or publication authority.

## Design and boundaries

The only standard configuration shape is:

```lua
return {
  schema = 'g1.alpha.config.v1',
  mode = 'ALPHA_STANDARD',
  input_source = 'OWNED_SYNTHETIC',
}
```

The distinct public example avoids interpreting an existing engineering file as
Alpha data. No PID, address, authorization, credential, factory, callback, writer,
custom records source or target capability is admitted. The returned table and
all three fields are checked before the existing fixture constructor or scorer.
Validated values determine the actual mode/input, and status records their source.

This uses the existing trusted-local-Lua convention, reading one installation-bound
file snapshot and compiling it with an empty environment. The returned data is
narrowly allowlisted; function/nested-table values are not accepted or invoked.
**An empty environment is not an arbitrary-Lua sandbox or a hard execution/resource
bound.** Only trusted operator-authored data files are supported. No external
dependency, parser framework, launcher or SDK was added.

Explicit API selections retain precedence and their original latch behavior.
Alpha explicit selections do not read local configuration, including when that
file is invalid or selects another mode. A rejected explicit selection cannot
fall back to a valid file. Explicit engineering/qualification selections retain
their separate legacy config loading and strict authorization contracts.

For the local standard route, only first Start or an explicit fresh Start after
successful cleanup reads configuration. Running, reentrant, cleanup-pending or
cleanup-uncertain Starts are rejected before reading. No file polling occurs.
A config error latches rejection until a fresh CE session, even after the file is
repaired; repeated dofile or selection calls cannot clear it. The mode cannot
change through config. A permitted fresh Start clears the previous instance and
completed evaluation before admitting new configuration, preventing stale success.

Missing config preserves `ALPHA_INPUT_REQUIRED` with `ALPHA_CONFIG_MISSING`;
other errors use fixed `ALPHA_CONFIG_*` codes. No original OS/parser/runtime error,
config text or unnecessary personal path enters the cached configuration diagnostic.
`config_admission=ACCEPTED` only means selection admission, never evaluation
completion or action authority. Existing ID2 fields and independent ID3 remain.

`ALPHA_STOP_ONLY`, existing core/adapter/scorer/collector, thresholds, coverage,
resource limits, operation/readback/cleanup checks and qualification implementation
were not changed. The new selection still constructs only the existing owned
fixture. No external process discovery, acquisition, injection, native backend,
new writer, native target parameter or operation authorization was introduced.

## Exact validation commands and correction history

Commands ran from `D:\armedforces.io-v2`, using the existing `.venv` Python
3.14.3, pytest 9.1.0 and Lupa 2.8. CT tests used genuine Lua 5.3; applicable
existing core tests also used Lua 5.4. The existing 256 MiB test allocator limit
was retained. These results are not CE-host observations. No historical AC8/PAIR,
G1 or previous manual acceptance/effectiveness campaign was rerun.

1. Baseline:
   `.venv/Scripts/python.exe -m pytest -q tests/test_ce_mvp_readonly.py -k 'standard_default_requires or id2_observes or invalid_explicit_selection' --basetemp=reports/2026-11-26/g1-alpha-f01-baseline`
   — **14 passed, 93 deselected, 10.40 s**.
2. First entry run:
   `.venv/Scripts/python.exe -m pytest -q tests/test_ce_mvp_readonly.py --basetemp=reports/2026-11-26/g1-alpha-f01-entry-1 --junitxml=reports/2026-11-26/g1-alpha-f01-local/entry-1.xml`
   — **1 collection error, 1.57 s**: duplicate `controlled_ct` parametrization.
   No tests executed in this run. The new standard-only cases were moved to a
   separate fixture using the same existing harness; no runtime workaround was made.
3. Corrected full entry/ID2/ID3 run:
   `.venv/Scripts/python.exe -m pytest -q tests/test_ce_mvp_readonly.py --basetemp=reports/2026-11-26/g1-alpha-f01-entry-2 --junitxml=reports/2026-11-26/g1-alpha-f01-local/entry-2.xml`
   — **141 passed, 17.81 s**. Includes 34 new F01 cases and the existing entry cases.
4. Impacted loader/config/lifecycle/engineering compatibility:
   `.venv/Scripts/python.exe -m pytest -q tests/test_h3_a7_ce_mvp.py -k 'portable or actual_loader or loader_is_inert or config_rejects or alpha_stop_policy or cleanup_uncertainty_blocks_restart' --basetemp=reports/2026-11-26/g1-alpha-f01-compat-1 --junitxml=reports/2026-11-26/g1-alpha-f01-local/compat-1.xml`
   — **122 passed, 809 deselected, 3.65 s**.
5. Impacted strict qualification/public-loader guards:
   `.venv/Scripts/python.exe -m pytest -q tests/qualification/test_qsg_integration.py::test_public_loader_start_stop_latches_and_preserves_cleanup_probes tests/qualification/test_qsg_acceptance.py -k 'public_loader or mandatory_plugin or qualified_public_l12 or stale_timer_and_direct_adapter' --basetemp=reports/2026-11-26/g1-alpha-f01-qsg-1 --junitxml=reports/2026-11-26/g1-alpha-f01-local/qsg-1.xml`
   — **14 passed, 66 deselected, 14.84 s**. Uses safe doubles only.
6. Actual candidate preparation and smoke:
   `.venv/Scripts/python.exe reports/2026-11-26/g1-alpha-f01-local/prepare_candidate.py`
   and `.venv/Scripts/python.exe reports/2026-11-26/g1-alpha-f01-local/verify_candidate.py`
   — both exit 0; **PASS_F01_ACTUAL_STANDARD_CANDIDATE_LUPA**. The scripts are
   local-only receipts using the existing preparation mechanism and test harness,
   not a new runtime launcher or test framework.
7. Handoff preservation/privacy/documentation:
   `.venv/Scripts/python.exe reports/2026-11-26/g1-alpha-f01-local/verify_handoff.py`
   — exit 0; **PASS_F01_HANDOFF_IDENTITY_PRIVACY_PRESERVATION**. All 58 inventoried
   paths and both historical 13-file packages matched. Ten protected source blobs,
   the ID2/ID3 CT scripts, ten local documentation links, public-example agreement,
   private-file ignore/exclusion and public-artifact visibility checks passed.

There are no unresolved failures in these scoped checks. The baseline and final
entry sets overlap and are **not summed**. Local XML receipts and package-smoke
JSON retain observed results; raw test/runtime output is not committed. No
unrelated broad regression or repeat effectiveness campaign was performed.

## Identifiable candidate and actual packaged result

- Source commit: `79c6a3dfadabfa66afb652dda4ea4c9535ee5388`.
- Candidate: `D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-f01-candidate`.
- [Complete file identities](g1-alpha-f01-file-identities.json): 13 maintained
  files exported from exact Git blobs, one generated CT and one local-only,
  byte-identical copy of the public Alpha example. No operator config was copied.
- Actual preparation command:
  `D:\armedforces.io-v2\.venv\Scripts\python.exe D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-f01-candidate\src\prepare_ce_mvp.py`
  — exit 0, default flags, `controlled=false`.
- Generated CT: **2909 bytes**, SHA-256
  **`76d966213fed39d27b491f86f3fc1af9d38ab97ea544a4f9a9b3db1ab85cb7d7`**.
  ID1/ID3 bind to the candidate's own Lua siblings; config resolves to that same
  installation. The CT is path-bound and not a relocatable/release artifact.
- All six CT syntax blocks and idle ID2 were inert. Actual packaged ID1 read the
  local config once, with no prior API selection, and reached the owned fixture.
  Existing fixture progression produced COMPLETE/full, all six applicable counts
  3, duplicates/excluded 0, identities `0x100128 / 0x100328 / 0x100528`, Rank-1 46
  versus runner-up -36 and ACCEPT. This synthetic recommendation grants no native
  action permission.
- Actual packaged ID2 left read/write/open/scan/config/scoring/evidence counters
  unchanged. Stop cleaned up and 200 later fixture ticks caused no activity.
  ID3 executed separately without touching the ID1 fixture or rereading config.
  Ambient target calls and fixture native scan objects were both **0**.
- The exact 15-file set, lengths, SHA-256 values and public-copy identity matched
  before and after execution. Existing accepted controlled and standard historical
  packages, their manifests and original results remain unchanged.

The [Chinese guide](https://github.com/k-undurkhaan-2/Chrome_Project/blob/9574ef9b83b29e603d1e067486f846a1c4bad59f/docs/g1_alpha_f01_config_zh.md) provides one-time
non-overwriting installation, schema/field meanings, precedence, error handling,
privacy and unsupported scope. The candidate is a local review/acceptance input;
it is not a distributed release and does not request a repeat manual campaign.

## Signed delivery sequence and independent readback

Each validated coherent unit used exact-path staging and staged `git diff --check`,
then `git commit -S`, local `git verify-commit` (Good signature), and immediate normal
`git push origin HEAD:refs/heads/armedforces.io-v2` through the existing gh HTTPS
credential helper. No broad staging or accumulated bulk push was used.

Before the next mutation, independent `gh api
repos/k-undurkhaan-2/Chrome_Project/commits/armedforces.io-v2` readback checked exact
SHA, parent, changed-path set and **verified=true / reason=valid**:

| Commit | Parent | Exact changed paths |
| --- | --- | --- |
| `79c6a3dfadabfa66afb652dda4ea4c9535ee5388` | `d8f93d517c374a45cfcc62f8a44520ae67b09f35` | `src/ce_mvp.lua`; `src/ce_mvp.CT`; `src/ce_mvp_alpha_config.example.lua`; `src/prepare_ce_mvp.py`; `tests/test_ce_mvp_readonly.py`; `tests/test_h3_a7_ce_mvp.py` |
| `034ad82cee542b59fdda0986a33def2e973e225a` | `79c6a3dfadabfa66afb652dda4ea4c9535ee5388` | `.gitignore` |

The final handoff unit adds this report, the Chinese guide and identity manifest,
and updates README. Its parent is `034ad82cee542b59fdda0986a33def2e973e225a`.
Its exact SHA and post-push signature/readback, final local/remote HEAD, complete
commit chain, test receipts and preservation results are bound in the local-only
`g1-alpha-f01-local/verification-receipt.json` and final response, avoiding a
self-referential commit identity in this report.

## Retained open conditions and stop

`ATTACHMENT_HANDLE_UNVERIFIED`, `QSG_NATIVE_BACKEND_NOT_QUALIFIED`,
`NOT_PRODUCTION_AUTHORIZED`, `IMPLEMENTED_PENDING_CE_QUALIFICATION` remain intact.
Original G1 stays **0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**. AC8's criterion
and historical finite-domain evidence, AC/PAIR, P4-R2 applicability, native
qualification, N0/MIN/LOCAL suspension, resource policy and release restrictions
are unchanged. No historical matrix row is upgraded.

Candidate-specific CE-host config I/O/UI observation, real-input usability,
independent effectiveness acceptance, native execution/readback/qualification and
release eligibility are NOT_RUN/NOT_ESTABLISHED as applicable. Lupa checks do not
establish CE timing, Unicode file-I/O behavior, cancellation latency, peak memory,
capacity/SLA or semantic liveness. If later host evidence is required, it must bind
this exact source/CT identity and independently observe ordinary ID1 configuration
admission and inert ID2; no such observation is fabricated or scheduled here.

**Stop after F01.** F02, F03 and F04 remain OPEN; no native scope expansion,
effectiveness campaign or automatic successor work is authorized by this handoff.
