# CE-native MVP quick start

Status: **IMPLEMENTED_PENDING_CE_QUALIFICATION**. The code and synthetic tests
are delivered. Real CE 7.6 attachment, writes, readback and relocation have
**not** been tested by this task. The live procedure below requires separate
operator authorization for its fresh disposable target. Do not use a production
target or any historical PID/address from earlier A6 attempts.

## Configure once

Use **Windows x64 Cheat Engine 7.6 with Lua 5.3**. Keep the repository at
`D:\armedforces.io-v2`; the CT Start action points there. If you move the
repository, edit that one loader path inside the CT before use. The Lua module
finds its sibling files relative to its own saved path.

1. Copy `src\ce_mvp_config.example.lua` to `src\ce_mvp_config.local.lua`.
   Keep the local file private: it is ignored by Git and never overwritten by
   the loader. Do not edit the legacy `run_case_config.local.lua` for this tool.
2. Set `target_pid` to the current exact PID of the intended operator-owned
   target. Set `scan.start_address` and `scan.stop_address` to its permitted
   memory range. The scan range must include each candidate's entire surrounding
   structure, from value address minus 0x20 through plus 0x53.
3. Set `scan.target_value_float` and its matching `target_value_pattern` to the
   value used to discover new objects. Set `write_value` to the intended finite
   Float32. The example `100.0 / 0x42C80000 -> 125.0 / 0x42FA0000` is a test
   example, not an instruction to use those values on a real application.
4. Leave `screening_profile='single'`, `value_type='float32'`, both filter and
   prescore flags true, and all engineering extensions false. Keep
   `max_candidates == scan_budget`, at most 128. If there are more matches,
   narrow the range; the tool will not silently choose from a sampled list.
5. Adjust monitoring/retry limits if needed. `max_rescan_attempts` is the total
   retry/relocation budget for that Start. After obtaining the applicable target
   authorization, deliberately set `write_enabled=true` and save.

The shipped sample uses PID 0 and disables writes. It is intentionally rejected
before attachment. Numbers such as 0.1 round once to their binary32 representation;
the actual written/read-back bits are shown in status. Readback requires exact
bits, with no epsilon tolerance. Search float/pattern disagreement is rejected.

## Load, Start, inspect and Stop

Open `D:\armedforces.io-v2\src\ce_mvp.CT` in CE. Opening the table performs no
process/memory operation. Show CE's Lua Engine output, then enable the checkbox
**H3-A7 Start** once. It attaches to the configured PID automatically, starts an
asynchronous scan, applies the existing Single collector/ranker, writes one
uniquely qualified candidate, verifies it, and monitors. No pasted witnesses,
Python console, repeated prompts, or manual initial scan are required.

One-line fallback in the CE Lua Engine, with the same saved configuration:

```lua
dofile([[D:\armedforces.io-v2\src\ce_mvp.lua]]).start()
```

Expected state sequence:

```text
ATTACHING -> SCREENING -> CANDIDATE_CHECK -> WRITING -> READBACK -> MONITORING
```

Inspect the current state by toggling the table's **Status** record or executing:

```lua
H3A7_CE_MVP.status()
```

Status includes PID/creation-time identity token, current and last candidate
address, last written/read-back Float32 and bits, scan/write counts, completed
monitor checks, last check time, error, stop reason and cleanup status. Output
uses local nonsecret process identifiers, not signed authorization. The optional
`.log` path is disabled by default; set an absolute path under an existing local
directory if desired. History/output is bounded; status queries remain available.

**Stop immediately** by unchecking the Start record, or with:

```lua
H3A7_CE_MVP.stop()
```

Stop is safe to call repeatedly. It cancels the timer and scanner and closes its
owned resources. Native scan cleanup may briefly delay UI responsiveness; that
latency has not yet been measured in CE. The Start checkbox is an initiation
control, not a live state indicator: after an automatic error it can remain
checked. Check `status()`, uncheck it, correct the cause, then deliberately Start
again. If `cleanup_ok=false`, reload CE before another Start. Do not run other
attach/switching scripts concurrently with this tool.

A valid finite **value drift does not cause another write**. The monitoring
predicate is readable committed private writable memory plus seven unchanged
surrounding structural words. Confirmed loss of that predicate while the original
process lives retires the old address and starts a fresh bounded cycle. A new
object must again have the configured discovery value. PID exit, target switch,
identity uncertainty, ambiguity, write/readback error, timeout, or retry exhaustion
stops the run. There is no automatic rollback or process-name reattachment.

## Common outcomes

| Status/reason | Meaning and next action |
| --- | --- |
| `INVALID_TARGET_PID`, `WRITE_DISABLED`, missing local config | Finish the saved configuration; no attachment occurred. |
| `SCAN_PATTERN_MISMATCH`, `INVALID_SCAN_SETTINGS` | Correct the Float32 bits, range, or equal candidate/budget settings. |
| `UNSUPPORTED_ENGINEERING_EXTENSION` | This MVP only implements the disabled extension interfaces. Do not substitute an A4 review-only result. |
| `CE_API_MISSING`, `WIN32_API_MISSING`, `REQUIRES_CE_*` | Verify CE 7.6 x64/Lua 5.3 and ordinary Windows process access. There is no fallback to weaker identity checks. |
| `PROCESS_OPEN_FAILED`, `IDENTITY_UNCERTAIN`, `PID_*`, `CE_TARGET_CHANGED` | Stop; confirm the exact intended PID/instance and access. No automated reattachment follows. |
| `CANDIDATE_BUDGET_EXCEEDED` | More than the bounded complete population. Narrow the configured range before restarting. |
| `CANDIDATE_NOT_QUALIFIED`, `AMBIGUOUS_CANDIDATES` | Existing structural rules cannot establish a unique acceptable candidate. Inspect the profile/target; never force the first match. |
| `SCAN_COMPLETION_UNCERTAIN`, `SCREENING_READ_FAILED` | Incomplete scan/read observations. Check CE diagnostics and the stable test layout; no write follows. |
| `CANDIDATE_CHANGED`, `PREWRITE_CANDIDATE_CHANGED` | Value or structure changed after discovery. The transaction was abandoned. |
| `RESCAN_BACKOFF` | Waiting before a retry; identity checks continue. |
| `RESCAN_LIMIT_EXHAUSTED`, `SCAN_TIMEOUT` | The configured bound was reached. Inspect the target before any deliberate restart. |
| `WRITE_FAILED`, `READBACK_MISMATCH` | Memory might have changed. Stop and inspect it; no write retry or automatic restore occurs. |
| `RETIRED_CANDIDATE` | A previously invalidated address reappeared. It will not be reused in the same run. |
| `cleanup_ok=false` | Cleanup is uncertain. Reload CE; do not bypass the singleton/cleanup guard. |

## Separate manual CE acceptance procedure

**G1 is NOT AUTHORIZED / NOT RUN.** Follow the complete
[R1 fixture, diagnostics, configuration and controlled-session plan](ce_mvp_q1_r1_plan.md)
after new explicit authorization. The earlier shorter demonstration sequence is
superseded by the full L01–L12 matrix. All twelve live cases remain NOT_RUN.

The frozen qualification candidate supports baseline_unique, zero_match,
ambiguous, over_limit (129 actual aligned Float32 positions in one page),
incomplete_structure, invalid_structure, value_drift and decommit-based relocate.
The target is manual test equipment and never a runtime companion. R1 tests use
its separate pure layout module; they do not import or launch the native target.

For Q1 the scan range is **exactly the fresh target's 64 KiB reservation**;
scan_budget=max_candidates=128. Do not narrow/expand that range or lower the cap
to substitute for the 129-match observation. Search 100.0/0x42C80000, write
125.0/0x42FA0000, drift 42.0/0x42280000. Preserve Single thresholds and all
disabled engineering extensions. The example config is safe by default.

The optional diagnostics setting is disabled by default. For an approved Start,
use a fresh session_token, event_limit=512 and cleanup_start_probe=false except
for the specifically controlled L10 Stop. Inspect or print evidence with:

```lua
H3A7_CE_MVP.evidence()       -- deep copy; no native calls or printing
H3A7_CE_MVP.print_evidence() -- prints event/counter/identity snapshots
```

Evidence contains actual scan counts/completeness, ranking/uniqueness, adapter
read/write/readback counters, sampled process identity, state transitions and
cleanup. adapter_read_calls is **not an OS memory-read count**. Raw status and
helper addresses belong in private ignored .log files; diagnostic events use
A0/A1 labels. Stop qualification on dropped events or an observation error.

L05 requires **at least 20 consecutive completed valid monitor cycles** with no
extra scan/write; elapsed time alone is insufficient. L06 requires a separate
drift observation with no additional scan/write. The positive+relocation run
permits at most two write attempts. L10 permits one initial write, then a
zero-match restart after confirmed cleanup. All five L09 controls, both L11
targets, L01 and L12 permit zero writes; the aggregate session ceiling is three.

L10's one-shot diagnostic probe observes public Start rejection at the real
cleanup boundary without delaying cleanup. L11 requires two separately approved
owned helper instances and never an unrelated process. See the linked plan for
exact steps, finite instance/time limits, private configuration preparation,
the L01 load guard, and the **unapproved** future G1 scope template.

A pre-live readiness result does not qualify CE or authorize production use.
Only actual authorized L01–L12 observations can support Q1 live qualification;
operator acceptance is a separate scoped decision. Keep
ATTACHMENT_HANDLE_UNVERIFIED and NOT_PRODUCTION_AUTHORIZED. A6/R3 T1 remains
independent and pending; historical R2 remains T1_FAILED_NOT_QUALIFIED.

Implementation detail and limits:
[H3-A7 contract](architecture/h3_a7_ce_mvp_contract.md).
Historical automated commands/results:
[original verification record](../reports/2026-11-20/h3_a7_verification.md).
