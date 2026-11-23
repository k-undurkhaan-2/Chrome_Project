"""Offline evidence verifier, independent of target, CE recorder and gate logic.

Consumes raw observations, never their PASS flags. Cross-actor correlation uses
explicit event digests/attempt IDs/checkpoint anchors, not clock subtraction.
Always returns NOT_RUN on the live axis; physical integration is not implemented.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
from pathlib import Path
import re

from .evidence import (EvidenceError, decode, digest, file_hash, finite_bits,
                       read_rows, utc, validate_chain, canonical, bounded_read,
                       directory_stamp, BLOB_LIMIT, BLOB_COUNT_LIMIT, BLOB_TOTAL_LIMIT,
                       MANIFEST_LIMIT, SIDECAR_ROLES)

LIVE = {f"L{i:02}": "NOT_RUN" for i in range(1, 13)}
L12 = ("L12-MISSING", "L12-DISABLED", "L12-INVALID")
LIMITATIONS = ["SYNTHETIC_ONLY; CE embedded Lua NOT_RUN",
    "BLOCKED_WRITE_GUARD_WIRING", "ATTACHMENT_HANDLE_UNVERIFIED",
    "Target samples cannot identify the writer or exclude transient writes between samples",
    "Adapter counters are not OS syscall counts",
    "Digest chains require independently retained trustworthy anchors; not tamper-proof",
    "No physical power-loss durability or hostile simultaneous file replacement proof"]
COUNTERS = ("adapter_scan_invocations", "adapter_write_attempts", "adapter_read_calls")


def need(condition, reason):
    if not condition:
        raise EvidenceError(reason)


def load_bundle(manifest_path, expected_sha256, *, sidecar_directory=None, include_sidecars=False):
    manifest_path = Path(manifest_path)
    need(file_hash(manifest_path) == expected_sha256, "BUNDLE_DIGEST_MISMATCH")
    manifest = decode(manifest_path.read_bytes())
    need(type(manifest.get("schema")) is int and manifest["schema"] in (1, 2) and manifest.get("watermark") == "SYNTHETIC"
         and manifest.get("live") == "NOT_RUN", "LIVE_PROMOTION_REJECTED")
    if manifest["schema"] == 2:
        need(set(manifest) == {"schema", "watermark", "live", "files", "sidecars"}, "BUNDLE_SCHEMA")
    else:
        need("sidecars" not in manifest, "SIDECAR_VERSION_REQUIRED")
    files = manifest["files"]
    need(set(files) == {p.name for p in manifest_path.parent.glob("*.jsonl")}, "UNMANIFESTED_OR_MISSING_STREAM")
    streams = {}
    for name, entry in files.items():
        need(Path(name).name == name and name.endswith(".jsonl"), "UNSAFE_STREAM_PATH")
        rows = read_rows(manifest_path.parent / name, entry["sha256"])
        need(len(rows) == entry["records"] and rows[-1]["content_digest"] == entry["head"], "STREAM_SEAL_MISMATCH")
        source = entry["source"]
        need(source not in streams and all(r["source"] == source for r in rows), "SOURCE_MISMATCH")
        streams[source] = rows
    reference = manifest.get("sidecars")
    root = sidecar_directory if sidecar_directory is not None else manifest_path.parent / "sidecars"
    load_sidecars([r for rows in streams.values() for r in rows], reference, root)
    return (streams, reference, root) if include_sidecars else streams


def _sidecar_ref(ref):
    need(isinstance(ref, dict) and set(ref) == {"artifact_id", "sha256", "byte_length", "normalized_type", "evidence_schema_version"}, "SIDECAR_REF_SCHEMA")
    need(type(ref["evidence_schema_version"]) is int and ref["evidence_schema_version"] == 2, "SIDECAR_VERSION")
    need(isinstance(ref["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]), "SIDECAR_SHA256")
    need(ref["artifact_id"] == "sha256:" + ref["sha256"], "SIDECAR_UNSAFE_ID")
    need(type(ref["byte_length"]) is int and 0 < ref["byte_length"] <= BLOB_LIMIT, "SIDECAR_BLOB_BOUND")
    need(ref["normalized_type"] in set(SIDECAR_ROLES.values()), "SIDECAR_TYPE")


def load_sidecars(records, reference, directory):
    """Independent closure/digest check; imports no recorder or store writer."""
    versioned = [r for r in records if r["kind"] == "config_rejected" and "evidence_schema_version" in r["data"]]
    if reference is None:
        need(not versioned, "SIDECAR_SEAL_REQUIRED")
        return {}
    need(bool(versioned) and directory is not None, "SIDECAR_ROOT_OR_RECORDS_REQUIRED")
    need(isinstance(reference, dict) and set(reference) == {"schema", "bundle_id", "sha256", "byte_length"}, "SIDECAR_SEAL_SCHEMA")
    need(type(reference["schema"]) is int and reference["schema"] == 2, "SIDECAR_VERSION")
    need(isinstance(reference["bundle_id"], str) and re.fullmatch(r"[0-9a-f]{32}", reference["bundle_id"]), "SIDECAR_BUNDLE_ID")
    need(type(reference["byte_length"]) is int and 0 < reference["byte_length"] <= MANIFEST_LIMIT, "SIDECAR_MANIFEST_BOUND")
    root = Path(directory); stamp = directory_stamp(root)
    raw = bounded_read(root / "sidecars.json", MANIFEST_LIMIT)
    need(len(raw) == reference["byte_length"] and hashlib.sha256(raw).hexdigest() == reference["sha256"], "SIDECAR_MANIFEST_SEAL")
    manifest = decode(raw)
    need(canonical(manifest) == raw, "SIDECAR_NONCANONICAL")
    need(isinstance(manifest, dict) and set(manifest) == {"schema", "bundle_id", "session_id", "artifacts", "bindings"}, "SIDECAR_MANIFEST_SCHEMA")
    need(manifest["schema"] == "ce.sidecars.v2" and manifest["bundle_id"] == reference["bundle_id"], "SIDECAR_MANIFEST_CONTEXT")
    entries = manifest["artifacts"]
    need(isinstance(entries, list) and 1 <= len(entries) <= BLOB_COUNT_LIMIT, "SIDECAR_COUNT_BOUND")
    by_id, total = {}, 0
    for entry in entries:
        _sidecar_ref(entry)
        aid = entry["artifact_id"]
        need(aid not in by_id, "SIDECAR_DUPLICATE_ID")
        by_id[aid] = entry; total += entry["byte_length"]
    need(total <= BLOB_TOTAL_LIMIT, "SIDECAR_TOTAL_BOUND")
    names = {"sidecars.json"} | {e["sha256"] + ".json" for e in entries}
    need({p.name for p in root.iterdir()} == names, "SIDECAR_CLOSURE")
    bindings, used, seen = [], set(), set()
    for row in versioned:
        d = row["data"]
        need(type(d["evidence_schema_version"]) is int and d["evidence_schema_version"] == 2, "L12_VERSION")
        need(row["session_id"] == manifest["session_id"] and d["bundle_id"] == manifest["bundle_id"], "SIDECAR_CONTEXT")
        need(row["event_id"] not in seen, "SIDECAR_DUPLICATE_EVENT")
        seen.add(row["event_id"])
        roles = {}
        for role, kind in SIDECAR_ROLES.items():
            ref = d[role]; _sidecar_ref(ref)
            need(ref["normalized_type"] == kind and by_id.get(ref["artifact_id"]) == ref, "SIDECAR_REFERENCE")
            roles[role] = ref["artifact_id"]; used.add(ref["artifact_id"])
        bindings.append({**{k: row[k] for k in ("source", "session_id", "event_id", "run_id", "scenario", "sequence", "content_digest")}, "roles": roles})
    need(manifest["bindings"] == bindings and used == set(by_id), "SIDECAR_BINDING_OR_CLOSURE")
    values = {}
    for aid, entry in by_id.items():
        blob = bounded_read(root / (entry["sha256"] + ".json"), BLOB_LIMIT)
        need(len(blob) == entry["byte_length"] and hashlib.sha256(blob).hexdigest() == entry["sha256"], "SIDECAR_CONTENT_DIGEST")
        value = decode(blob)
        need(canonical(value) == blob and isinstance(value, dict), "SIDECAR_NONCANONICAL")
        values[aid] = value
    need(directory_stamp(root) == stamp and {p.name for p in root.iterdir()} == names, "SIDECAR_ROOT_CHANGED")
    return {r["event_id"]: l12_payload(r, values) for r in versioned}


def l12_payload(row, values=None):
    """Resolve both retained roles and validate the independently read bytes."""
    d = deepcopy(row["data"])
    legacy = {"accepted", "diagnostic", "guard_before", "guard_after", "guard_restored", "retained_before", "retained_after", "retained_origin"}
    v2 = "evidence_schema_version" in d
    need(set(d) == legacy | ({"evidence_schema_version", "bundle_id"} if v2 else set()), "L12_PAYLOAD_SCHEMA")
    if v2:
        need(type(d["evidence_schema_version"]) is int and d["evidence_schema_version"] == 2 and values is not None, "L12_VERSION_OR_SIDECARS")
        for role in SIDECAR_ROLES:
            d[role] = deepcopy(values[d[role]["artifact_id"]])
        obs = d["diagnostic"]
        need(set(obs) == {"schema", "origin", "source", "path_utf8_hex", "returned_error_hex", "full_error_hex",
                         "loader_error_hex", "loader_return_arity", "full_error_source", "return_arity", "truncation_bytes"}, "L12_DIAGNOSTIC_SCHEMA")
        need(obs["schema"] == "ce.loader-diagnostic.v2" and obs["origin"] == "SYNTHETIC" and obs["source"] == "g1_mock_loader", "L12_DIAGNOSTIC_ORIGIN")
        need(type(obs["return_arity"]) is int and obs["return_arity"] == 2
             and type(obs["truncation_bytes"]) is int and obs["truncation_bytes"] == 240, "L12_RETURN_CONTRACT")
        def raw_field(name):
            text = obs[name]
            need(isinstance(text, str) and re.fullmatch(r"(?:[0-9a-f]{2})+", text), "L12_DIAGNOSTIC_HEX")
            return bytes.fromhex(text)
        path, full, returned = (raw_field(k) for k in ("path_utf8_hex", "full_error_hex", "returned_error_hex"))
        path.decode("utf-8")  # Never normalize separators, Unicode or combining characters.
        need(path.replace(b"\\", b"/").endswith(b"/ce_mvp_config.local.lua") and b"\x00" not in path, "L12_PATH_PROVENANCE")
        need(returned == full[:240], "L12_ACTUAL_RETURN_MISMATCH")
        if row["scenario"] == "L12-MISSING":
            loader = raw_field("loader_error_hex")
            need(type(obs["loader_return_arity"]) is int and obs["loader_return_arity"] == 2 and obs["full_error_source"] == "PCALL_ERROR", "L12_LOADER_OBSERVATION")
            need(loader.startswith(b"cannot open " + path + b": ") and full.endswith(loader)
                 and re.fullmatch(rb"SYNTHETIC/ce_mvp\.lua:[1-9][0-9]*: ", full[:-len(loader)]), "L12_RAW_ERROR_BINDING")
        else:
            need(obs["loader_error_hex"] is False and type(obs["loader_return_arity"]) is int and obs["loader_return_arity"] == 0
                 and obs["full_error_source"] in {"PCALL_ERROR", "API_RETURN"}, "L12_UNEXPECTED_LOADER_ERROR")
        d["diagnostic"] = full.decode("utf-8")
    need(row["scenario"] in L12 and row["origin"] == "SYNTHETIC" and row["actor"] == row["source"] == "ce", "L12_CONTEXT")
    need(d["accepted"] is False and d["guard_restored"] is True, "L12_ACCEPTED_OR_UNRESTORED")
    guards = {"openProcess", "createMemScan", "readInteger", "readFloat", "writeFloat", "createTimer", "executeCodeLocalEx", "createMemoryStream"}
    need(all(isinstance(d[k], dict) and set(d[k]) == guards and all(type(v) is int and v == 0 for v in d[k].values())
             for k in ("guard_before", "guard_after")), "L12_ACTIVITY_OR_COUNTER_GAP")
    need(isinstance(d["retained_before"], dict) and isinstance(d["retained_after"], dict)
         and canonical(d["retained_before"]) == canonical(d["retained_after"])
         and d["retained_origin"] == "PRIOR_RUN_OR_NO_RUN", "L12_RETAINED_EVIDENCE_CHANGED")
    message = d["diagnostic"]
    need(isinstance(message, str), "L12_DIAGNOSTIC_TYPE")
    if row["scenario"] == "L12-MISSING":
        need("ce_mvp_config.local.lua" in message and ("No such file" in message or "cannot find" in message)
             and "MISSING_CONFIG" not in message, "L12_MISSING_FILE_DIAGNOSTIC_REQUIRED")
    else:
        need(message == ("WRITE_DISABLED" if row["scenario"] == "L12-DISABLED" else "INVALID_SCAN_SETTINGS"), "L12_WRONG_DIAGNOSTIC")
    return d


def _identity(value):
    need(isinstance(value, dict) and set(value) == {"designation", "pid", "creation", "target_sha256"}, "IDENTITY_SCHEMA")
    need(value["designation"] in ("A", "B") and type(value["pid"]) is int and value["pid"] > 0, "IDENTITY_PID")
    need(isinstance(value["creation"], str) and re.fullmatch(r"[0-9A-F]{16}", value["creation"])
         and int(value["creation"], 16) > 0, "CREATION_IDENTITY_UNVERIFIABLE")
    need(isinstance(value["target_sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", value["target_sha256"]), "TARGET_HASH")
    return f"{value['pid']}:{value['creation']}"


def _bounds(target, address):
    need(type(address) is int and address % 4 == 0 and target["base"] <= address <= target["base"] + 65532,
         "ADDRESS_BOUND_OR_ALIGNMENT")


def _counter(row, key):
    value = row.get("counters", {}).get(key)
    need(type(value) is int and value >= 0, "MISSING_OR_INVALID_COUNTER")
    return value


def verify_streams(streams, policy, *, requested=None, sidecar_reference=None, sidecar_directory=None):
    requested = list(requested or LIVE)
    result = {"schema": 1, "origin": "DERIVED", "infrastructure": "BLOCKED",
        "synthetic": {name: "INCONCLUSIVE_NOT_OBSERVED" for name in requested},
        "live": dict(LIVE), "l12_live": {name: "NOT_RUN" for name in L12},
        "g1_live": "NOT_APPROVED", "wiring": "BLOCKED_WRITE_GUARD_WIRING",
        "errors": [], "missing": [], "consumed_attempts": 0, "limitations": LIMITATIONS}
    try:
        need(policy.get("origin") == "SYNTHETIC", "LIVE_PROMOTION_REJECTED")
        need(set(policy) == {"origin", "session_id", "window_start", "window_end", "targets"}, "POLICY_SCHEMA")
        need(0 < (utc(policy["window_end"]) - utc(policy["window_start"])).total_seconds() <= 3600
             and 1 <= len(policy["targets"]) <= 9, "POLICY_WINDOW_OR_INSTANCE_BOUND")
        need(all(name in LIVE for name in requested), "UNKNOWN_REQUESTED_SCENARIO")
        rows, ids = [], set()
        for source, records in streams.items():
            need(source in {"ce", "budget", "target-A", "target-B"}, "UNEXPECTED_SOURCE")
            validate_chain(records, source=source, session_id=policy["session_id"])
            for row in records:
                need(row["origin"] == "SYNTHETIC" and row["actor"] == source, "LIVE_PROMOTION_OR_ACTOR")
                need(row["event_id"] not in ids, "DUPLICATE_GLOBAL_EVENT")
                ids.add(row["event_id"]); rows.append(row)
        resolved_l12 = load_sidecars(rows, sidecar_reference, sidecar_directory)
        if not all(streams.get(s) for s in ("budget", "ce", "target-A")):
            result["missing"].append("CE_TARGET_BUDGET_STREAM_REQUIRED")
            if not streams.get("budget"):
                return result
        targets = {}
        tokens = set()
        for target in policy["targets"]:
            token = _identity(target["identity"])
            need(token not in tokens, "DUPLICATE_TARGET_INSTANCE")
            tokens.add(token)
            need(set(target) == {"identity", "allocation_id", "base", "size", "allowed_scenarios"}
                 and bool(target["allowed_scenarios"]) and set(target["allowed_scenarios"]) <= set(LIVE), "TARGET_POLICY_SCHEMA")
            if target["identity"]["designation"] == "B":
                need(target["allowed_scenarios"] == ["L11"], "TARGET_B_SCOPE")
            need(target["size"] == 65536 and type(target["base"]) is int and target["base"] % 65536 == 0, "ALLOCATION_POLICY")
            need(target["allocation_id"] not in targets, "ALLOCATION_ID_REUSED")
            targets[target["allocation_id"]] = target
        target_rows = [r for r in rows if r["source"].startswith("target-")]
        allocations, checkpoints, target_retired = {}, {}, set()
        for row in target_rows:
            need(row["kind"] in {"allocation", "commit", "retire", "decommit", "reallocate", "mode", "planned_drift",
                 "checkpoint", "checkpoint_missing", "shutdown", "exception", "cleanup"}, "UNKNOWN_TARGET_EVENT")
            d = row["data"]; identity = d.get("identity")
            _identity(identity)
            allocation = d.get("allocation_id")
            need(allocation in targets and targets[allocation]["identity"] == identity, "TARGET_IDENTITY_MISMATCH")
            need(row["source"] == "target-" + identity["designation"], "TARGET_ACTOR_MISMATCH")
            if row["kind"] == "allocation":
                need(allocation not in allocations and d["base"] == targets[allocation]["base"]
                     and d["size"] == 65536 and d["owner"] == _identity(identity)
                     and d["protection"] == "PAGE_READWRITE", "ALLOCATION_EVIDENCE")
                allocations[allocation] = row
            else:
                need(allocation in allocations, "ALLOCATION_NOT_OBSERVED")
            if "address" in d:
                _bounds(targets[allocation], d["address"])
            if row["kind"] == "retire":
                need(d.get("permanent") is True, "RETIREMENT_NOT_PERMANENT")
                target_retired.add((allocation, d["address"]))
            if row["kind"] == "checkpoint":
                finite_bits(d["bits"])
                need((allocation, d["address"]) not in target_retired, "RETIRED_TARGET_SAMPLED")
                key = (row["run_id"], d["anchor_id"])
                need(key not in checkpoints, "DUPLICATE_CHECKPOINT_ANCHOR")
                checkpoints[key] = row
        budget = streams["budget"]
        need(budget[0]["kind"] == "enrollment" and budget[0]["data"].get("policy_digest") == digest(policy), "BUDGET_POLICY_MISMATCH")
        starts, stopped, reservations, dispatched, outcomes, retired = {}, set(), {}, {}, {}, set()
        totals, reserved_checkpoints = Counter(), set()
        for row in budget[1:]:
            kind, d, run, scenario = row["kind"], row["data"], row["run_id"], row["scenario"]
            need(kind in {"start", "stop", "reservation", "dispatch", "outcome", "retire"}, "UNKNOWN_BUDGET_EVENT")
            if kind == "start":
                need(run not in starts and not set(starts) - stopped, "RUN_REUSED_OR_OVERLAPPING")
                need(len(starts) < 9, "SUCCESSFUL_START_BUDGET")
                need(d["allocation_id"] in targets and d["identity"] == targets[d["allocation_id"]]["identity"], "START_TARGET_MISMATCH")
                need(scenario in targets[d["allocation_id"]]["allowed_scenarios"], "START_SCENARIO_NOT_APPROVED")
                starts[run] = row
            elif kind == "stop":
                need(run in starts and run not in stopped, "UNMATCHED_STOP")
                stopped.add(run)
            else:
                need(run in starts and run not in stopped, "ATTEMPT_AFTER_STOP")
                if kind == "retire":
                    need(d["identity"] == starts[run]["data"]["identity"], "RETIREMENT_IDENTITY")
                    retired.add((d["allocation_id"], d["address"]))
                elif kind == "reservation":
                    need(scenario in {"L04", "L07", "L10"}, "ZERO_BUDGET_SCENARIO_WRITE")
                    need(scenario == starts[run]["scenario"] or (scenario == "L07" and starts[run]["scenario"] == "L04"), "SCENARIO_SWAP")
                    need(d["scenario"] == scenario and d["run_id"] == run, "RESERVATION_CONTEXT")
                    target = targets[d["allocation_id"]]
                    need(scenario in target["allowed_scenarios"] and target["identity"]["designation"] == "A", "RESERVATION_SCENARIO_NOT_APPROVED")
                    need(d["identity"] == d["ce_identity"] == target["identity"] == starts[run]["data"]["identity"], "CE_TARGET_SWAP")
                    need(d["allocation_id"] == starts[run]["data"]["allocation_id"], "ALLOCATION_SWAP")
                    _bounds(target, d["address"])
                    need((d["allocation_id"], d["address"]) not in retired, "RETIRED_ADDRESS_WRITE")
                    need(finite_bits(d["bits"]) == "0x42FA0000", "WRITE_INTENT_BITS")
                    need(utc(policy["window_start"]) <= utc(row["clock"]["utc"]) < utc(policy["window_end"]), "ATTEMPT_AFTER_EXPIRY")
                    need(0 <= (utc(row["clock"]["utc"]) - utc(starts[run]["clock"]["utc"])).total_seconds() < 300, "PHASE_EXPIRED")
                    c = d["candidate"]
                    need(type(c["raw_count"]) is int and 1 <= c["raw_count"] <= 128 and c["qualified_count"] == 1
                         and c["complete"] is True and c["hard_limit"] == 128 and c["structure_valid"] is True, "UNQUALIFIED_RESERVATION")
                    pre = checkpoints.get((run, d["anchor_id"]))
                    checkpoint_digest = d["checkpoint"]["content_digest"]
                    need(checkpoint_digest not in reserved_checkpoints, "PREWRITE_CHECKPOINT_REPLAY")
                    reserved_checkpoints.add(checkpoint_digest)
                    if pre is None:
                        result["missing"].append("RESERVATION_CHECKPOINT_NOT_OBSERVED")
                    else:
                        need(d["checkpoint"] == pre, "RESERVATION_CHECKPOINT_BINDING_MISMATCH")
                    aid = d["attempt_id"]
                    need(aid not in reservations, "DUPLICATE_ATTEMPT")
                    reservations[aid] = row; totals[scenario] += 1
                    need(len(reservations) <= 3 and totals["L04"] + totals["L07"] <= 2 and totals["L10"] <= 1, "BUDGET_EXCEEDED")
                else:
                    aid = d["attempt_id"]
                    need(aid in reservations and reservations[aid]["run_id"] == run and reservations[aid]["scenario"] == scenario, "UNRESERVED_DISPATCH")
                    if kind == "dispatch":
                        need(aid not in dispatched and d["reservation_digest"] == reservations[aid]["content_digest"], "DUPLICATE_OR_UNBOUND_DISPATCH")
                        need(utc(policy["window_start"]) <= utc(row["clock"]["utc"]) < utc(policy["window_end"]), "DISPATCH_AFTER_EXPIRY")
                        dispatched[aid] = row
                    else:
                        need(aid in dispatched and aid not in outcomes and d["result"] in {"SUCCESS", "FAILED", "INDETERMINATE"}, "INVALID_OUTCOME")
                        outcomes[aid] = d["result"]
        result["consumed_attempts"] = len(reservations)
        result["attempt_totals"] = dict(totals)
        if set(reservations) != set(dispatched) or set(dispatched) != set(outcomes):
            result["missing"].append("RESERVED_OR_DISPATCHED_ATTEMPT_WITHOUT_COMPLETE_OUTCOME_CONSUMED")
        if set(requested) == set(LIVE):
            if set(starts) != stopped:
                result["missing"].append("FINAL_STOP_NOT_OBSERVED")
            cleaned = {r["data"]["allocation_id"] for r in target_rows if r["kind"] == "cleanup" and r["data"].get("released") is True}
            if set(allocations) != cleaned:
                result["missing"].append("TARGET_FINAL_CLEANUP_NOT_OBSERVED")
        ce = streams.get("ce", [])
        diagnostics, by_run, by_scenario = [], defaultdict(list), defaultdict(list)
        ce_dispatches, ce_points = {}, {}
        for row in ce:
            kind, d = row["kind"], row["data"]
            if kind == "ce_event":
                e = d["diagnostic"]
                need(e.get("source") == "synthetic", "DIAGNOSTIC_ORIGIN")
                diagnostics.append(row); by_run[row["run_id"]].append(row); by_scenario[row["scenario"]].append(row)
                for key, val in e.items():
                    if key.endswith("_bits"):
                        finite_bits(val)
            elif kind == "ce_dispatch":
                aid = d["attempt_id"]
                need(aid in dispatched and aid not in ce_dispatches, "CE_WRITE_BYPASS_OR_DUPLICATE")
                r = reservations[aid]
                need(d["reservation_digest"] == r["content_digest"] and row["run_id"] == r["run_id"] and row["scenario"] == r["scenario"], "CE_RESERVATION_BINDING")
                for key in ("identity", "allocation_id", "address", "bits"):
                    need(d[key] == r["data"][key], "CE_DISPATCH_TARGET_OR_VALUE")
                ce_dispatches[aid] = row
            elif kind == "ce_checkpoint":
                aid = d["attempt_id"]
                need(aid in ce_dispatches and aid not in ce_points, "UNBOUND_OR_DUPLICATE_READBACK")
                need(row["run_id"] == reservations[aid]["run_id"], "READBACK_RUN_MISMATCH")
                ce_points[aid] = row
            elif kind == "ce_snapshot":
                need(d["ce_embedded_lua"] == "NOT_RUN", "LIVE_PROMOTION_REJECTED")
            else:
                need(kind in {"config_rejected", "load_observation", "os_identity", "target_switch", "phase_boundary"}, "UNKNOWN_CE_EVENT")
        if set(ce_dispatches) != set(dispatched):
            result["missing"].append("CE_DISPATCH_TRACE_MISSING")
        # State and counter evolution is evaluated per Start, not per capture.
        write_intents = []
        allowed = {"STOPPED": {"ATTACHING"}, "ATTACHING": {"SCREENING"},
            "SCREENING": {"CANDIDATE_CHECK", "RESCAN_BACKOFF"}, "CANDIDATE_CHECK": {"WRITING"},
            "WRITING": {"READBACK"}, "READBACK": {"MONITORING"},
            "MONITORING": {"RESCAN_BACKOFF"}, "RESCAN_BACKOFF": {"SCREENING"}}
        for run, events in by_run.items():
            state, previous, cleanup_complete = "STOPPED", {}, False
            for number, row in enumerate(events, 1):
                e = row["data"]["diagnostic"]
                need(e["sequence"] == number, "DIAGNOSTIC_ORDER_OR_GAP")
                for key in ("adapter_scan_invocations", "adapter_write_attempts", "adapter_read_calls", "monitor_checks"):
                    value = _counter(e, key)
                    need(value >= previous.get(key, 0), "COUNTER_ROLLBACK")
                    if cleanup_complete and key in COUNTERS:
                        need(value == previous.get(key, value), "ACCESS_AFTER_CLEANUP")
                    previous[key] = value
                if e["event_type"] == "cleanup_complete":
                    cleanup_complete = True
                if e["event_type"] == "state_transition":
                    before, after = e["state_before"], e["state_after"]
                    need(before == state and (after in allowed.get(state, set()) or after in {"STOPPED", "ERROR"}), "INVALID_STATE_TRANSITION")
                    state = after
                if e["event_type"] == "write_intent":
                    need(state == "WRITING", "WRITE_OUTSIDE_WRITING_STATE")
                    write_intents.append(row)
                identity = e.get("identity", {})
                binding = row["data"].get("bindings", {})
                if e["event_type"] in {"write_intent", "readback_verified", "monitor_result"}:
                    if not identity or not binding.get("identity") or not binding.get("allocation_id"):
                        result["missing"].append("MEMORY_EVENT_IDENTITY_BINDING_REQUIRED")
                    else:
                        need(identity.get("check_complete") is True, "MEMORY_EVENT_IDENTITY_UNVERIFIED")
                if identity.get("check_complete") is True:
                    token = identity.get("query_token")
                    need(token == identity.get("ce_reported_token"), "CE_IDENTITY_DISAGREEMENT")
                    if "identity" in binding:
                        need(token == _identity(binding["identity"]), "CE_TARGET_CREATION_MISMATCH")
                        allocation = binding.get("allocation_id")
                        need(allocation in targets and targets[allocation]["identity"] == binding["identity"], "CE_ALLOCATION_BINDING")
            final = events[-1]["data"]["diagnostic"]
            for event_name, counter in (("write_intent", "adapter_write_attempts"),
                    ("scan_invocation", "adapter_scan_invocations"), ("readback_verified", "verified_writes")):
                need(sum(r["data"]["diagnostic"]["event_type"] == event_name for r in events) == _counter(final, counter), "UNEXPLAINED_ADAPTER_COUNTER")
        need(len(write_intents) == len(ce_dispatches), "WRITE_INTENT_DISPATCH_COUNT_MISMATCH")
        for intent, dispatch in zip(write_intents, ce_dispatches.values()):
            e, binding, d = intent["data"]["diagnostic"], intent["data"].get("bindings", {}), dispatch["data"]
            need(intent["run_id"] == dispatch["run_id"] and binding.get("addresses", {}).get(e.get("address_label")) == d["address"]
                 and e["write_intent_bits"] == d["bits"], "WRITE_INTENT_BINDING_MISSING_OR_WRONG")
        agreed = set()
        for aid, r in reservations.items():
            if outcomes.get(aid) != "SUCCESS":
                continue
            if aid not in ce_points:
                result["missing"].append("CE_READBACK_NOT_OBSERVED"); continue
            p = ce_points[aid]; d = p["data"]
            target_point = checkpoints.get((p["run_id"], d["anchor_id"]))
            if target_point is None:
                result["missing"].append("TARGET_READBACK_NOT_OBSERVED"); continue
            td = target_point["data"]
            for key in ("identity", "allocation_id", "address", "bits"):
                need(d[key] == td[key] == r["data"][key], "TWO_SIDED_READBACK_DISAGREEMENT")
            need(td["attempt_id"] == aid, "TARGET_ATTEMPT_ANCHOR_MISMATCH")
            pre = checkpoints.get((r["run_id"], r["data"]["anchor_id"]))
            if pre is None:
                result["missing"].append("PREWRITE_TARGET_CHECKPOINT_REQUIRED")
                continue
            need(pre["sequence"] < target_point["sequence"] and pre["data"]["bits"] == "0x42C80000"
                 and all(pre["data"][key] == r["data"][key] for key in ("identity", "allocation_id", "address")), "PREWRITE_CHECKPOINT_DISAGREEMENT")
            verified = [x for x in by_run[p["run_id"]] if x["data"]["diagnostic"]["sequence"] == d["diagnostic_sequence"]]
            need(len(verified) == 1, "READBACK_EVENT_ANCHOR_MISSING")
            e = verified[0]["data"]["diagnostic"]
            need(e["event_type"] == "readback_verified" and e["readback_bits"] == e["float_bits"] == e["write_intent_bits"] == d["bits"], "READBACK_BITS_MISMATCH")
            agreed.add(aid)
        def events(case, kind=None):
            return [r["data"]["diagnostic"] for r in by_scenario[case]
                    if kind is None or r["data"]["diagnostic"]["event_type"] == kind]
        def prove(case, ok):
            if ok:
                result["synthetic"][case] = "SYNTHETIC_PASS"
        def stable(case, minimum):
            es = events(case)
            checks = [e for e in es if e["event_type"] == "monitor_result"]
            if len(checks) < minimum:
                return False
            need(len({r["run_id"] for r in by_scenario[case]}) == 1, "MONITORS_SPAN_RESTART")
            need(all(e.get("valid") is True and e["state_after"] == "MONITORING" for e in checks), "INVALID_MONITOR_CYCLE")
            counts = [_counter(e, "monitor_checks") for e in checks]
            need(counts == list(range(counts[0], counts[0] + len(counts))), "NONCONTIGUOUS_MONITORS")
            valid_counts = [_counter(e, "valid_monitor_checks") for e in checks]
            need(valid_counts == list(range(valid_counts[0], valid_counts[0] + len(valid_counts)))
                 and len({_counter(e, "invalid_monitor_checks") for e in es}) == 1, "MONITOR_VALIDITY_COUNTERS")
            for key in ("adapter_scan_invocations", "adapter_write_attempts", "scan_count", "write_count", "verified_writes"):
                need(len({_counter(e, key) for e in es}) == 1, "MONITOR_EXTRA_SCAN_OR_WRITE")
            return True
        for case in requested:
            if case in {"L04", "L07"}:
                aa = [a for a in agreed if reservations[a]["scenario"] == case]
                ok = len(aa) == 1
                if case == "L07" and ok:
                    r = reservations[aa[0]]; new = r["data"]["address"]
                    old = [x for x in reservations.values() if x["scenario"] == "L04" and x["run_id"] == r["run_id"]]
                    ok = len(old) == 1 and old[0]["data"]["identity"] == r["data"]["identity"] and old[0]["data"]["address"] != new
                    if ok:
                        address = old[0]["data"]["address"]; allocation = r["data"]["allocation_id"]
                        ce_retirements = [x for x in by_scenario[case] if x["data"]["diagnostic"]["event_type"] == "address_retired"]
                        retire_matches = [x for x in ce_retirements if x["data"]["bindings"]["addresses"].get(x["data"]["diagnostic"]["address_label"]) == address]
                        ok = ((allocation, address) in retired and (allocation, address) in target_retired
                              and len(retire_matches) == 1
                              and any(t["kind"] == "decommit" and t["data"]["allocation_id"] == allocation
                                      and t["data"]["base"] <= address < t["data"]["base"] + t["data"]["size"] for t in target_rows))
                prove(case, ok)
            elif case == "L05":
                prove(case, stable(case, 20))
            elif case == "L06":
                prove(case, stable(case, 3) and sum(e.get("value_bits") == "0x42280000" for e in events(case, "valid_value_observed")) >= 3
                      and any(r["kind"] == "planned_drift" and r["scenario"] == case for r in target_rows)
                      and any(r["kind"] == "checkpoint" and r["scenario"] == case and r["data"]["bits"] == "0x42280000" for r in target_rows))
            elif case == "L12":
                rejected = [r for r in ce if r["kind"] == "config_rejected"]
                ok = len(rejected) == 3 and {r["scenario"] for r in rejected} == set(L12) and len({r["run_id"] for r in rejected}) == 3
                for row in rejected:
                    d = resolved_l12[row["event_id"]] if "evidence_schema_version" in row["data"] else l12_payload(row)
                    need(d["accepted"] is False and d["guard_restored"] is True, "L12_ACCEPTED_OR_UNRESTORED")
                    names = {"openProcess", "createMemScan", "readInteger", "readFloat", "writeFloat", "createTimer", "executeCodeLocalEx", "createMemoryStream"}
                    need(all(set(d[k]) == names and all(type(v) is int and v == 0 for v in d[k].values()) for k in ("guard_before", "guard_after")), "L12_ACTIVITY_OR_COUNTER_GAP")
                    need(d["retained_before"] == d["retained_after"] and d["retained_origin"] == "PRIOR_RUN_OR_NO_RUN", "L12_RETAINED_EVIDENCE_CHANGED")
                    message = d["diagnostic"]
                    if row["scenario"] == "L12-MISSING":
                        need("ce_mvp_config.local.lua" in message and ("No such file" in message or "cannot find" in message)
                             and "MISSING_CONFIG" not in message, "L12_MISSING_FILE_DIAGNOSTIC_REQUIRED")
                    else:
                        expected = "WRITE_DISABLED" if row["scenario"] == "L12-DISABLED" else "INVALID_SCAN_SETTINGS"
                        need(message == expected, "L12_WRONG_DIAGNOSTIC")
                prove(case, ok)
            elif case == "L09":
                ok = True
                for mode, count in (("zero", 0), ("ambiguous", 2), ("129_plus", 129), ("incomplete", 1), ("invalid", 1)):
                    sub = "L09-" + mode
                    es = events(sub); populations = events(sub, "scan_population")
                    modes = [r for r in target_rows if r["scenario"] == sub and r["kind"] == "mode" and r["data"]["mode"] == mode]
                    if not es or not populations or not modes:
                        ok = False; continue
                    need(all(_counter(e, "adapter_write_attempts") == 0 for e in es), "L09_WRITE")
                    need(populations[0]["raw_match_count"] == count and populations[0]["hard_limit"] == populations[0]["configured_limit"] == 128
                         and modes[0]["data"]["synthetic_match_count"] == count, "L09_POPULATION_OR_CAP")
                    if mode == "ambiguous": need(any(e.get("qualified_count") == 2 for e in events(sub, "ranking_summary")), "L09_NOT_TWO_QUALIFIERS")
                    if mode == "incomplete": need(any(e.get("read_failure") is True for e in events(sub, "candidate_population")), "L09_INCOMPLETE_NOT_OBSERVED")
                    if mode == "invalid": need(any(e.get("qualified_count") == 0 for e in events(sub, "ranking_summary")), "L09_INVALID_NOT_OBSERVED")
                    if mode == "129_plus": need(bool(events(sub, "scan_population_blocked")), "L09_OVERFLOW_NOT_BLOCKED")
                prove(case, ok)
            elif case == "L03":
                prove(case, any(e.get("raw_match_count") == 1 and e.get("scan_complete") is True for e in events(case, "scan_population_complete"))
                      and any(e.get("qualified_count") == 1 and e.get("recommendation") == "ACCEPT" and e.get("hard_pass") is True for e in events(case, "ranking_summary"))
                      and any(e.get("collection_complete") is True for e in events(case, "candidate_population")))
            elif case == "L01":
                loads = [r["data"] for r in ce if r["kind"] == "load_observation"]
                prove(case, len(loads) == 1 and loads[0].get("state") == "STOPPED" and loads[0].get("guard_restored") is True
                      and loads[0].get("ct_lua_syntax_blocks") == 4 and loads[0].get("config_loaded") is False
                      and loads[0].get("ce_embedded_lua") == "NOT_RUN"
                      and set(loads[0].get("attempted_calls", {})) == {"openProcess", "createMemScan", "readInteger", "readFloat", "writeFloat", "createTimer", "executeCodeLocalEx", "createMemoryStream"}
                      and all(type(v) is int and v == 0 for v in loads[0]["attempted_calls"].values()))
            elif case == "L02":
                observed = [r["data"] for r in ce if r["kind"] == "os_identity"]
                bound = events(case, "identity_bound")
                prove(case, bool(bound) and any(_identity(o["identity"]) == bound[0].get("identity_token")
                      and any(t["identity"] == o["identity"] for t in targets.values()) for o in observed))
            elif case == "L08":
                endings = events(case, "cleanup_complete")
                prove(case, any(e.get("cleanup_ok") is True and e.get("reason") in {"PID_EXITED", "PID_EXITED_OR_UNCERTAIN", "IDENTITY_UNCERTAIN", "PID_IDENTITY_MISMATCH"} for e in endings)
                      and len({_counter(e, "adapter_write_attempts") for e in events(case)}) == 1
                      and not events(case, "write_intent"))
            elif case == "L10":
                rejects = {e.get("reason") for e in events(case, "start_rejected")}
                probes = events(case, "cleanup_start_probe")
                snaps = [r for r in ce if r["kind"] == "ce_snapshot" and r["scenario"] == case]
                last_snaps = {r["run_id"]: r for r in snaps}
                boundaries = [r for r in ce if r["kind"] == "phase_boundary" and r["scenario"] == case]
                waits_ok = len(boundaries) == 2 and all(r["data"].get("phase") == "after_stop"
                    and r["data"].get("completed_wait_intervals", 0) >= 3
                    and r["data"]["before"] == r["data"]["after"] for r in boundaries)
                prove(case, {"ALREADY_RUNNING", "CLEANUP_IN_PROGRESS"} <= rejects
                      and any(p.get("call_ok") is True and p.get("accepted") is False and p.get("reason") == "CLEANUP_IN_PROGRESS" for p in probes)
                      and waits_ok and len(last_snaps) == 2 and all(r["data"]["cleanup_ok"] is True and r["data"]["running"] is False for r in last_snaps.values())
                      and len(events(case, "timer_disposed")) == 2 and len(events(case, "query_handle_close")) == 2
                      and len(events(case, "local_stream_dispose")) == 2
                      and any(e.get("raw_match_count") == 0 for e in events(case, "scan_population"))
                      and len([a for a in agreed if reservations[a]["scenario"] == case]) == 1)
            elif case == "L11":
                switches = [r["data"] for r in ce if r["kind"] == "target_switch"]
                if switches:
                    need(len(switches) == 1, "L11_DUPLICATE_SWITCH")
                    sw = switches[0]
                    need(_identity(sw["from"]) != _identity(sw["to"]) and sw["from"]["designation"] == "A" and sw["to"]["designation"] == "B", "L11_CONFLATED_TARGETS")
                    need(all(any(t["identity"] == identity for t in targets.values()) for identity in (sw["from"], sw["to"])), "L11_UNREGISTERED_TARGET")
                    need(all(sw["before"][k] == sw["after"][k] for k in COUNTERS), "L11_ACCESS_AFTER_SWITCH")
                    run = next(r["run_id"] for r in ce if r["kind"] == "target_switch")
                    anchors = {r["data"]["diagnostic"]["sequence"]: r["data"]["diagnostic"] for r in by_run[run]}
                    need(sw["before_sequence"] < sw["after_sequence"] and sw["before_sequence"] in anchors and sw["after_sequence"] in anchors, "L11_SWITCH_ANCHORS_REQUIRED")
                    need(all(anchors[sw[which + "_sequence"]]["counters"][k] == sw[which][k] for which in ("before", "after") for k in COUNTERS), "L11_COUNTER_ANCHORS_DISAGREE")
                    modes = [r for r in target_rows if r["scenario"] == case and r["kind"] == "mode"]
                    prove(case, any(r["data"]["identity"] == sw["from"] and r["data"]["mode"] == "zero" for r in modes)
                          and any(r["data"]["identity"] == sw["to"] and r["data"]["mode"] == "unique" for r in modes)
                          and any(e.get("reason") == "CE_TARGET_CHANGED" and e.get("cleanup_ok") is True for e in events(case, "cleanup_complete"))
                          and all(_counter(e, "adapter_write_attempts") == 0 for e in events(case))
                          and any(r["kind"] == "checkpoint" and r["scenario"] == case and r["data"]["identity"] == sw["to"] and r["data"]["bits"] == "0x42C80000" for r in target_rows))
        if not result["missing"] and all(v == "SYNTHETIC_PASS" for v in result["synthetic"].values()):
            result["infrastructure"] = "PASS"
        return result
    except (OSError, EvidenceError, KeyError, TypeError, ValueError, IndexError) as exc:
        result["infrastructure"] = "FAIL"
        result["errors"].append(str(exc))
        # Integrity failures invalidate the whole supplied evidence set.
        result["synthetic"] = {name: "SYNTHETIC_FAIL" for name in requested}
        return result


def verify_bundle(manifest_path, expected_sha256, policy, *, requested=None, sidecar_directory=None):
    try:
        streams, reference, root = load_bundle(manifest_path, expected_sha256,
            sidecar_directory=sidecar_directory, include_sidecars=True)
    except (OSError, EvidenceError, KeyError, TypeError, ValueError) as exc:
        return {"infrastructure": "FAIL", "errors": [str(exc)], "live": dict(LIVE),
                "l12_live": {name: "NOT_RUN" for name in L12}, "g1_live": "NOT_APPROVED"}
    return verify_streams(streams, policy, requested=requested, sidecar_reference=reference, sidecar_directory=root)


def main(argv=None):
    """Offline only; all input digests must be supplied explicitly."""
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Verify SYNTHETIC G1 evidence; never qualifies live CE")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--policy-sha256", required=True)
    parser.add_argument("--case", action="append", choices=list(LIVE))
    parser.add_argument("--sidecar-directory", type=Path, help="Designated v2 evidence root; fixed content-addressed filenames only")
    args = parser.parse_args(argv)
    try:
        need(file_hash(args.policy) == args.policy_sha256, "POLICY_FILE_DIGEST_MISMATCH")
        result = verify_bundle(args.manifest, args.manifest_sha256, decode(args.policy.read_bytes()),
            requested=args.case, sidecar_directory=args.sidecar_directory)
    except (OSError, EvidenceError, ValueError) as exc:
        result = {"infrastructure": "FAIL", "errors": [str(exc)], "live": dict(LIVE), "g1_live": "NOT_APPROVED"}
    print(json.dumps(result, sort_keys=True, indent=2))
    return {"PASS": 0, "BLOCKED": 2, "FAIL": 1}[result["infrastructure"]]


if __name__ == "__main__":
    raise SystemExit(main())
