# Standard CT installation and use

**BLOCKED_G1_ALPHA_PRODUCT_CLOSURE.** Ordinary original configuration reaches the
existing adapter, but the complete authorized target workflow is unavailable.
The existing execution dependency admits synthetic provenance only. With a valid,
compatible positive PID and write intent, Start returns
`QSG_NATIVE_BACKEND_NOT_QUALIFIED` before acquiring CE/target APIs.
Native binding, acquisition, operation and readback remain **NOT_RUN /
NOT_ESTABLISHED**. A synthetic selector or engineering mode cannot substitute
for the intended product.

This is the sole current official English product guide. See the
[contract](architecture/h3_a7_ce_mvp_contract.md) and
[unpublished release notes](../reports/2026-11-26/g1-alpha-pre-release-prep-1-release-notes-draft.md).
Independent effectiveness acceptance belongs to the maintainer; no new session
or repeated historical campaign is scheduled here.

## Environment and preparation

The design environment is Windows x64 / CE 7.6 / embedded Lua 5.3. Keep the
maintained `src/` tree together. Python is used only by the existing offline
preparation tool. No new launcher, GUI, CLI, application exporter or mandatory SDK
is required.

Use a fresh isolated installation when existing private files must be preserved.
These checks refuse to overwrite either file. Change sourceDir to the actual
installation; this does not start CE or authorize any target access.

```powershell
$sourceDir = 'D:\armedforces.io-v2\src'
$localConfig = Join-Path $sourceDir 'ce_mvp_config.local.lua'
$localTable = Join-Path $sourceDir 'ce_mvp.local.CT'
if (Test-Path -LiteralPath $localConfig) { throw 'Preserve existing config; use an isolated installation' }
if (Test-Path -LiteralPath $localTable) { throw 'Preserve existing CT; use an isolated installation' }
[System.IO.File]::Copy((Join-Path $sourceDir 'ce_mvp_config.example.lua'), $localConfig, $false)
& 'D:\armedforces.io-v2\.venv\Scripts\python.exe' (Join-Path $sourceDir 'prepare_ce_mvp.py')
```

The preparation function itself can overwrite an existing CT; preserve the checks
above. The loader never creates or overwrites config. Both files remain local.
The generated CT encodes absolute sibling Lua paths. Moving the installation
requires preparation at the new location and a new artifact identity.

## Standard controls

Load the prepared `src/ce_mvp.local.CT`. Loading, inspection and syntax checking
are inert. Explicit **ID1 Start** reads one config snapshot beside the bound
`ce_mvp.lua`, independent of the working directory. The original public template
is the official config: safe PID 0 and writes false are structurally valid and
refuse Start with `ALPHA_CONFIG_TARGET_REQUIRED`.

**ID2** prints cached state. Unchecking **ID1** calls Stop. **ID3** runs the
independent public read-only synthetic example once; it neither provisions ID1
nor authorizes an operation. Standard configuration requires no recurring Lua
Console selection. Prepare without `--alpha-controlled` and use the original
template without a synthetic input_source selector.

Editing the PID, write intent, budgets or process selection cannot resolve the
native qualification blocker. This guide provides no unsupported live procedure.
A successful native standard run is not established.

## Original configuration contract

Unknown fields, metatables, invalid types/ranges, inconsistent bits and enabled
extensions reject. Config is trusted operator-owned Lua data evaluated with an
empty environment, not an untrusted-code sandbox or hard execution/time limit.
Returned callbacks/factories never confer authorization.

The consumers below exist in the shared core/adapter, but their native use is
blocked. Parsing and passing parameters to admission are not actual application.

| Field | Meaning, validation and standard disposition |
| --- | --- |
| target_pid | Required integer 0..4294967295 for recognition; execution needs positive PID. Exact numeric identity only, no name fallback. Default 0. Passed to adapter admission; native binding unavailable. |
| screening_profile | Required single; existing scoring semantics. Full population is separate, not a new profile value. |
| value_type | Required float32; no new value types. |
| write_value | Required finite number, binary32-rounded by string.pack; overflow rejects. Default 125.0. Conditional operation/readback consumer. |
| write_enabled | Required Boolean; default false blocks execution. True is intent, never permission. |
| scan | Required plain table; inventory below. |
| monitor_interval_ms | Required integer 100..60000, default 1000; existing admitted-run schedule. |
| invalid_confirmations | Required 1..20, default 2; engineering-only. Alpha stops at first observed invalidity. |
| min_rescan_spacing_ms | Required 100..600000, default 2000; engineering recovery only, dormant in Alpha. |
| rescan_backoff_ms | Required 100..600000, default 1000; engineering recovery only. |
| max_backoff_ms | Same range, at least rescan_backoff_ms, default 30000; engineering recovery only. |
| max_rescan_attempts | Required 0..50, default 5; engineering recovery only. Alpha retries are zero. Does not raise qualification session limits. |
| scan_timeout_ms | Required 1000..600000, default 120000; cooperative scan/collection checks, not preemptive synchronous/native timeout. |
| log_limit | Required 16..2000, default 200; existing per-Start history and console/file line limits. ID2 printing is separate. |
| log_path | Optional absolute drive path ending .log, at most 512 characters, no controls; directory must exist. Append failure stops; omission disables file output. Private. |
| diagnostics | Optional plain table, default enabled=false; passive evidence only. Details below. |
| engineering_extensions | Required plain table; only h3_a3_store, h3_a4_approval, strict_attachment, all false if present. Empty table valid. Enabled extension rejects. |

All numeric ranges in the table require integers except write_value.

| scan field | Meaning and standard disposition |
| --- | --- |
| mode | Optional process/bounded. No bounds means process; paired legacy bounds mean bounded. Standard Alpha rejects bounded with ALPHA_PROFILE_BOUNDED_SCOPE. |
| start_address, stop_address | Optional paired integers or 0x strings in 0x10000..0x7FFFFFFFFFFF, span at least 128. Incompatible with process; engineering/qualification only. |
| target_value_float | Required finite Float32, default 100.0; existing acquisition/filter/precheck consumer. |
| target_value_pattern | Required uint32 matching rounded search bits, default 0x42C80000; never decimal integer-search reinterpretation. |
| scan_budget | Optional default 2000, integer 1..65536. Engineering admission budget, not Alpha full-scoring truncation. Independent strict QSG 128/128 limits remain binding. |
| max_candidates | Optional default 20, integer 1..128 and no greater than scan_budget. Engineering ranking budget, never passed as a full-scoring limit. Above-limit qualification rejects without truncation. |
| filter_target_match | Required true; existing exact match remains effective. |
| use_prescore_selection | Required true; full path retains all distinct eligible members, no hidden selection cap. |
| collection_batch_size | Optional 16..2048, default 256; existing address/read/score checkpoints, not AC5 preemption. |
| collection_slice_ms | Optional 1..25, default 10; existing cooperative timing, no UI SLA. |
| process_candidate_limit, process_chunk_candidates, process_slice_ms | Obsolete names: any non-nil value rejects OBSOLETE_PROCESS_BUDGET_USE_LEGACY_INTAKE_SETTINGS. |

Diagnostics permits enabled, session_token, event_limit and cleanup_start_probe.
Enabled must be Boolean. When true, token is 1..64 alphanumeric/underscore/hyphen
characters and event_limit is integer 32..2048. Optional cleanup_start_probe must
be Boolean; true requires enabled and is incompatible with Alpha
(ALPHA_PROFILE_QUALIFICATION_PROBE). This L10 probe remains qualification-only.
Private evidence may contain tokens/identities and is not the sanitized ID2 view.

## Cached state and refusal

| Axis | Interpretation |
| --- | --- |
| Configuration | config_file_status, config_contract, config_validation, config_admission, profile_compatibility, config_application and copied config_effects are independent. VALID/ACCEPTED is not applied or permitted. |
| Standard target preparation | Valid ordinary target config selects CONFIGURED_TARGET / configured_target_scan / STANDARD_ADAPTER_REQUIRES_QUALIFICATION. Current result: BLOCKED_QUALIFICATION, config_block=QSG_NATIVE_BACKEND_NOT_QUALIFIED, config_application=NOT_APPLIED. |
| Acquisition | Configured scope, readable results and independently established completeness differ. acquisition_complete=false and evidence NOT_ESTABLISHED remain truthful on refusal. |
| Evaluation | COMPLETE/EMPTY require full counts and exact membership. PENDING/ERROR/CANCELLED are not EMPTY. Full supplied scoring does not prove native coverage or global uniqueness. |
| Recommendation | ACCEPT/REVIEW/REJECT, confidence and manual review retain original rules; Rank-1 alone is not permission. |
| Operation | NOT_RUN, ATTEMPTED_UNCONFIRMED, FAILED or API_SUCCEEDED. Exceptions may leave effects uncertain. |
| Readback | NOT_RUN, ATTEMPTED_UNCONFIRMED, FAILED, MISMATCH or VERIFIED. Both integer bits and Float32 must match for VERIFIED. API success alone is insufficient. |
| Monitor | NOT_RUN, CHECK_UNCONFIRMED, VALID or INVALID describes the existing predicate, not semantic identity. |
| Terminal and cleanup | state, stop_reason, cleanup_pending, cleanup_ok and cleanup_error are separate. Earlier verified readback may coexist with later terminal failure. |

ID2 does not reread config, score, sample a clock/identity or operate on a target.
Original-config status suppresses PID, addresses, identity tokens, values and
private log errors. Diagnostic evidence remains private. Errors never reuse a
previous run's successful completion.

Running, reentrant, cleaning or uncertain-cleanup Starts reject before config
rereading. Confirmed cleanup permits a deliberate new Start with fresh caches.
Invalid/blocked config and invalid selection latch the session: correct saved
data and reload CE instead of deleting the singleton or switching modes around
the lock.

## Stop conditions and retained interfaces

Alpha stops and cleans up on observed identity/lifetime failure, access/operation
failure, abnormal readback, configured validity failure, incomplete evaluation
or terminal error. There is no automatic rescan, reselection, reattachment,
restart or rollback. Cleanup uncertainty blocks reuse until CE reload. Native
destruction may block; no hard timeout or cancellation/UI latency is established.

The unchanged monitor checks mapping/allocation, seven structural words and
readable finite Float32. Finite value drift alone is intentionally allowed.
Readability, PID liveness or matching words do not prove semantic identity.
No new liveness or freeze algorithm is introduced.

ENGINEERING_BOUNDED and QUALIFICATION remain explicit engineering interfaces
under their own contracts, not alternative standard instructions. The historical
ce_mvp_alpha_config.example.lua selector and OWNED_SYNTHETIC option remain
test-only, fixed identity 101. They are not the official product configuration
or a substitute candidate.

## Qualification and publication

ATTACHMENT_HANDLE_UNVERIFIED, QSG_NATIVE_BACKEND_NOT_QUALIFIED,
NOT_PRODUCTION_AUTHORIZED and IMPLEMENTED_PENDING_CE_QUALIFICATION remain.
G1 is **0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**. Historical AC8 100/100
is finite synthetic evidence; M6 acceptance is candidate-specific. Neither
transfers to this source.

### Automatic process-mode operator retest (P4-R2)

The historical P4-R2 prerequisite, its applicability to the full candidate and
its independent acceptance remain unresolved, not waived. The
[immutable original procedure](https://github.com/k-undurkhaan-2/Chrome_Project/blob/baaed5c0fad4e07e88ef877398c48f62373f8952/docs/ce_mvp_quickstart.md#automatic-process-mode-operator-retest-p4-r2)
records that requirement, not an instruction to run the old NORMAL procedure here.
L01/L12, AC/PAIR, original resource limits, N0/MIN/LOCAL suspension and separate
publication authority remain. No live test, repeat campaign, Tag or Release
is requested.
