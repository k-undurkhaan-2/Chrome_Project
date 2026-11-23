"""Read-only evidence replay. No Coordinator, Watchdog, Recorder or Lua import.

Only the pure codec and schema validation are shared. Flow/correlation, expected
observations, terminal counts and cross-actor byte agreement are checked here.
Externally retained hashes are required; replacing every trusted anchor remains
outside the evidence model.
"""
from datetime import datetime
from collections import Counter
from pathlib import Path
import struct

from .native_probe_protocol import SCHEMA, canonical, decode, digest_string, require, sha256, validate_message
from .native_probe_schema import validate_event

CASES = tuple(f"N{i:02}" for i in range(1, 10))
ACTORS = {"HOST", "LUA_MODEL", "WATCHDOG", "OBSERVER"}
ROLE_KINDS = {"OBSERVER": {"CHECK", "TERMINAL"},
              "HOST": {"TX", "RX", "TX_CHUNK", "RX_CHUNK", "ACCEPT", "REJECT", "CANCEL", "CLOSE", "TERMINAL"},
              "LUA_MODEL": {"TX", "RX", "TX_CHUNK", "RX_CHUNK", "REJECT", "CLOSE", "TERMINAL"},
              "WATCHDOG": {"WATCHDOG_ARM", "CANCEL_REQUEST", "DEADLINE", "HARD_CUTOFF_MODEL", "CLEANUP_OBSERVED", "TERMINAL"}}


def verify(manifest_path, manifest_sha256, plan_path, plan_sha256, candidate_sha256, authorization_sha256):
    result = {"schema": SCHEMA, "origin": "SYNTHETIC", "status": "SYNTHETIC_INDETERMINATE",
              "synthetic": {c: "SYNTHETIC_INDETERMINATE" for c in CASES},
              "native": {c: "NOT_RUN" for c in CASES}, "g1_live": {f"L{i:02}": "NOT_RUN" for i in range(1, 13)},
              "errors": [], "missing": [], "events": 0, "exchanges": 0, "cleanup_cycles": 0,
              "os_peer_identity": "NOT_RUN", "ce_embedded_lua": "NOT_RUN"}
    try:
        for digest in (manifest_sha256, plan_sha256, candidate_sha256, authorization_sha256):
            digest_string(digest)
        path = Path(manifest_path)
        require(not path.is_symlink() and path.stat().st_size <= 65536, "MANIFEST_PATH_OR_SIZE")
        raw = path.read_bytes()
        require(sha256(raw) == manifest_sha256, "MANIFEST_ANCHOR")
        m = decode(raw)
        require(set(m) == {"schema", "origin", "candidate_sha256", "authorization_sha256", "plan_sha256", "streams"}, "MANIFEST_FIELDS")
        require(m["schema"] == SCHEMA and m["origin"] == "SYNTHETIC", "ORIGIN_OR_VERSION")
        require(m["candidate_sha256"] == candidate_sha256 and m["authorization_sha256"] == authorization_sha256
                and m["plan_sha256"] == plan_sha256, "AUTHORITY_BINDING")
        require(Path(plan_path).stat().st_size <= 65536, "PLAN_SIZE")
        plan_raw = Path(plan_path).read_bytes()
        require(len(plan_raw) <= 65536 and sha256(plan_raw) == plan_sha256, "PLAN_ANCHOR")
        plan = decode(plan_raw.strip())
        require(set(plan) == {"schema", "origin", "checks"} and plan["schema"] == SCHEMA
                and plan["origin"] == "SYNTHETIC" and set(plan["checks"]) == set(CASES), "PLAN_FIELDS")
        require(type(m["streams"]) is list and len(m["streams"]) <= 4, "STREAM_SET")
        schema = decode(Path(__file__).with_name("native_probe_evidence.schema.json").read_bytes().strip())
        streams, all_rows = {}, []
        for entry in m["streams"]:
            require(set(entry) == {"actor", "file", "event_count", "terminal_sequence", "terminal_head", "raw_sha256"}, "SEAL_FIELDS")
            actor = entry["actor"]
            require(actor in ACTORS and actor not in streams and entry["file"] == actor.lower() + ".jsonl", "STREAM_PATH")
            p = path.parent / entry["file"]
            if not p.is_file():
                result["missing"].append("STREAM_MISSING:" + actor)
                continue
            require(not p.is_symlink() and p.stat().st_size <= 8 * 1024 * 1024, "STREAM_PATH_OR_SIZE")
            stream_raw = p.read_bytes()
            require(sha256(stream_raw) == entry["raw_sha256"], "RAW_LOG_HASH")
            require(stream_raw.endswith(b"\n"), "TRUNCATED_LOG")
            lines = stream_raw.splitlines()
            require(len(lines) <= 8192 and type(entry["event_count"]) is int and len(lines) == entry["event_count"], "EVENT_COUNT")
            previous, last, utc_last, rows = "0" * 64, -1, None, []
            for number, line in enumerate(lines, 1):
                row = decode(line)
                validate_event(row, schema)
                require(row["kind"] in ROLE_KINDS[actor], "EVENT_ACTOR_ROLE")
                require(row["actor"] == actor and row["event_id"] == f"{actor}:{number}"
                        and row["sequence"] == number and row["clock_id"] == "synthetic-" + actor, "STREAM_IDENTITY")
                require(row["candidate_sha256"] == candidate_sha256 and row["authorization_sha256"] == authorization_sha256, "EVENT_BINDING")
                require(row["previous_sha256"] == previous and row["content_sha256"] ==
                        sha256(canonical({k: v for k, v in row.items() if k != "content_sha256"})), "EVENT_CHAIN")
                stamp = datetime.fromisoformat(row["utc"])
                require(stamp.utcoffset() is not None and (utc_last is None or stamp >= utc_last), "UTC_ORDER")
                require(row["elapsed_ms"] >= last, "CLOCK_REVERSED")
                previous, last, utc_last = row["content_sha256"], row["elapsed_ms"], stamp
                require(row["kind"] != "TERMINAL" or number == len(lines), "EARLY_TERMINAL")
                rows.append(row)
            require(rows and type(entry["terminal_sequence"]) is int and entry["terminal_sequence"] == len(rows)
                    and entry["terminal_head"] == previous, "TERMINAL_SEAL")
            if rows[-1]["kind"] != "TERMINAL":
                result["missing"].append("TERMINAL_MISSING:" + actor)
            streams[actor] = rows
            all_rows.extend(rows)
        for actor in ACTORS - set(streams):
            result["missing"].append("ACTOR_MISSING:" + actor)
        result["events"] = len(all_rows)
        observations = {}
        wire, host_states, closed_cycles, max_response, crossing = {}, {}, set(), 0, False
        chunks, worker_states = {}, {}
        for actor, rows in streams.items():
            for row in rows:
                kind, case, data = row["kind"], row["case_id"], row["data"]
                require(row["trial_id"] == "offline-1", "TRIAL_BINDING")
                key = (row["session_id"], row["channel_id"], row["epoch"])
                if kind == "CHECK":
                    require(actor == "OBSERVER", "CHECK_ACTOR")
                    check = data["check_id"]
                    require(check in plan["checks"][case] and (case, check) not in observations, "CHECK_UNEXPECTED_OR_DUPLICATE")
                    observations[case, check] = data["observed"]
                    expected = plan["checks"][case][check]
                    require(type(expected) is type(data["observed"]) and expected == data["observed"], "OBSERVATION_MISMATCH:" + check)
                if kind in ("TX", "RX", "TX_CHUNK", "RX_CHUNK"):
                    require(actor in ("HOST", "LUA_MODEL"), "FRAME_ACTOR")
                    if actor == "LUA_MODEL":
                        require(not worker_states.setdefault(key, False), "WORKER_FRAME_AFTER_CLOSE")
                    frame_raw = bytes.fromhex(data["wire_hex"])
                    require(len(frame_raw) == row["frame_length"] and sha256(frame_raw) == row["frame_sha256"], "BYTE_COUNT_OR_DIGEST")
                    chunk_key = (actor, *key, kind.split("_")[0])
                    if kind.endswith("_CHUNK"):
                        require(1 <= len(frame_raw) <= 4096, "CHUNK_BOUND")
                        buffer = chunks.setdefault(chunk_key, bytearray())
                        require(len(buffer) + len(frame_raw) <= 65540, "CHUNK_ACCUMULATION_BOUND")
                        buffer.extend(frame_raw)
                        continue
                    require(bytes(chunks.pop(chunk_key, b"")) == frame_raw, "CHUNK_TOTAL_MISMATCH")
                    require(4 < len(frame_raw) <= 65540 and struct.unpack_from("<I", frame_raw)[0] == len(frame_raw) - 4, "FRAME_LENGTH")
                    message = validate_message(decode(frame_raw[4:]))
                    require(message["kind"] == ("REQUEST" if (actor, kind) in (("HOST", "TX"), ("LUA_MODEL", "RX")) else "RESPONSE"), "FRAME_DIRECTION")
                    require(all(message[k] == row[k] for k in ("session_id", "channel_id", "epoch", "request_id"))
                            and message["sequence"] == row["request_sequence"], "FRAME_EVENT_BINDING")
                    message_key = (*key, message["request_id"], message["sequence"], message["kind"])
                    slot = (actor, kind)
                    require(slot not in wire.setdefault(message_key, {}), "DUPLICATE_FRAME")
                    wire[message_key][slot] = (frame_raw, case, row["trial_id"])
                    if actor == "HOST":
                        state = host_states.setdefault(key, {"sequence": 0, "used": set(), "pending": None, "closed": False})
                        require(not state["closed"], "FRAME_AFTER_CLOSE")
                        if kind == "TX":
                            require(message["kind"] == "REQUEST" and state["pending"] is None
                                    and message["sequence"] == state["sequence"] + 1
                                    and message["request_id"] not in state["used"], "OUTSTANDING_OR_REPLAY")
                            require((message["method"] == "HELLO") == (state["sequence"] == 0), "HELLO_ORDER")
                            state.update(pending=message, sequence=message["sequence"], sent_ms=row["elapsed_ms"], received=False)
                            state["used"].add(message["request_id"])
                        else:
                            request = state["pending"]
                            require(request is not None and not state["received"] and message["kind"] == "RESPONSE", "ORPHAN_RESPONSE")
                            require(all(message[k] == request[k] for k in ("session_id", "channel_id", "epoch", "request_id", "sequence", "method", "payload"))
                                    and message["request_sha256"] == sha256(canonical(request)), "RESPONSE_CORRELATION")
                            require(row["elapsed_ms"] - state["sent_ms"] < 250, "LATE_RESPONSE")
                            state["received"] = True
                            if case == "N04":
                                max_response = max(max_response, len(frame_raw) - 4)
                                crossing |= len(frame_raw) > 4096
                elif actor == "HOST" and kind == "ACCEPT":
                    state = host_states[key]
                    request = state["pending"]
                    require(request is not None and state["received"] and row["request_id"] == request["request_id"]
                            and row["request_sequence"] == request["sequence"], "ACCEPT_WITHOUT_RESPONSE")
                    require(row["response"] == {"CANCEL": "CANCELLED", "CLOSE": "CLOSED"}.get(request["method"], "OK"), "ACCEPT_RESULT")
                    result["exchanges"] += 1
                    if case == "N09" and request["method"] == "CLOSE":
                        closed_cycles.add(key)
                    state["pending"] = None
                elif actor == "HOST" and kind in ("CLOSE", "CANCEL", "REJECT"):
                    if key in host_states:
                        host_states[key].update(pending=None, closed=True)
                    if kind == "CLOSE" and row["response"] != "CLOSED":
                        result["missing"].append("CLEANUP_UNCERTAIN")
                elif actor == "LUA_MODEL" and kind == "CLOSE":
                    require(key in worker_states and not worker_states[key], "WORKER_CLOSE_ORDER")
                    worker_states[key] = True
                    if row["response"] != "CLOSED":
                        result["missing"].append("WORKER_CLEANUP_UNCERTAIN")
        for key, slots in wire.items():
            expected = {("HOST", "TX"), ("LUA_MODEL", "RX")} if key[-1] == "REQUEST" else {("LUA_MODEL", "TX"), ("HOST", "RX")}
            if set(slots) != expected:
                result["missing"].append("FRAME_PEER_MISSING")
            require(len(set(slots.values())) == 1, "PEER_BYTES_DISAGREE")
        if any(s["pending"] is not None or not s["closed"] for s in host_states.values()):
            result["missing"].append("HOST_TERMINAL_MISSING")
        if any(chunks.values()):
            result["missing"].append("UNRESOLVED_PARTIAL_FRAME")
        if not all(worker_states.values()):
            result["missing"].append("WORKER_TERMINAL_MISSING")
        if not crossing or max_response != 65536:
            result["missing"].append("FRAME_BOUNDARY_WITNESS_MISSING")
        result["cleanup_cycles"] = len(closed_cycles)
        if len(closed_cycles) != 20:
            result["missing"].append("TWENTY_CYCLES_MISSING")
        # Replay watchdog only in its own monotonic clock domain.
        active, started, active_id = None, None, None
        watchdog_counts = Counter()
        for row in streams.get("WATCHDOG", []):
            kind, data = row["kind"], row["data"]
            if kind != "TERMINAL":
                watchdog_counts[row["case_id"], kind] += 1
                if kind != "WATCHDOG_ARM":
                    require(row["request_id"] == active_id, "WATCHDOG_REQUEST_BINDING")
            if kind == "WATCHDOG_ARM":
                require(active is None and data == {"deadline_ms": 250, "cutoff_ms": 2000}, "WATCHDOG_ARM")
                active, started = "ARMED", row["elapsed_ms"]
                active_id = row["request_id"]
            elif kind in ("DEADLINE", "HARD_CUTOFF_MODEL"):
                require(active is not None and row["elapsed_ms"] - started == data["elapsed_ms"], "WATCHDOG_TIME")
                require(kind != "DEADLINE" or active == "ARMED", "WATCHDOG_DEADLINE_ORDER")
                require(data["elapsed_ms"] >= (250 if kind == "DEADLINE" else 2000), "EARLY_WATCHDOG")
                active = "INDETERMINATE" if kind == "HARD_CUTOFF_MODEL" else "DEADLINE"
            elif kind == "CANCEL_REQUEST":
                require(active in ("ARMED", "DEADLINE"), "WATCHDOG_CANCEL_ORDER")
                active = "CANCEL_REQUESTED"
            elif kind == "CLEANUP_OBSERVED":
                require(active is not None, "WATCHDOG_CLEANUP_ORDER")
                expected = "COMPLETE" if data["io_completed"] and data["resources_closed"] and active != "INDETERMINATE" else "INDETERMINATE"
                require(data["state"] == expected, "WATCHDOG_COMPLETION")
                active = None
        if active is not None:
            result["missing"].append("WATCHDOG_TERMINAL_MISSING")
        expected_watchdog = {("N05", "WATCHDOG_ARM"), ("N05", "DEADLINE"), ("N05", "HARD_CUTOFF_MODEL"),
                             ("N05", "CLEANUP_OBSERVED"), ("N06", "WATCHDOG_ARM"),
                             ("N06", "CANCEL_REQUEST"), ("N06", "CLEANUP_OBSERVED")}
        require(set(watchdog_counts) <= expected_watchdog and all(n == 1 for n in watchdog_counts.values()), "WATCHDOG_UNEXPECTED_EVENT")
        if set(watchdog_counts) != expected_watchdog:
            result["missing"].append("WATCHDOG_EXPECTED_EVENT_MISSING")
        for case, checks in plan["checks"].items():
            if any((case, name) not in observations for name in checks):
                result["missing"].append("EXPECTED_CHECK_MISSING:" + case)
        if not result["missing"]:
            result["status"] = "SYNTHETIC_PASS"
            result["synthetic"] = {case: "SYNTHETIC_PASS" for case in CASES}
    except (OSError, ValueError, TypeError, KeyError, IndexError, OverflowError, struct.error) as exc:
        result["status"] = "SYNTHETIC_FAIL"
        result["synthetic"] = {case: "SYNTHETIC_FAIL" for case in CASES}
        result["errors"].append(str(exc))
    return result


def verify_adapter_traces(trace_path, trace_sha256, manifest_path, manifest_sha256, candidate_sha256, authorization_sha256):
    """Independent B0 count/digest/ordering replay. No adapter or peer imports.

    OS evidence is still NOT_RUN. This corroborates adapter byte observations
    against separately sealed host chunks; it does not authenticate native peers.
    """
    result = {"status": "SYNTHETIC_INDETERMINATE", "errors": [], "missing": [], "sessions": 0}
    try:
        raw = Path(trace_path).read_bytes()
        require(len(raw) <= 8388608 and sha256(raw) == trace_sha256, "ADAPTER_TRACE_ANCHOR")
        traces = decode(raw)
        require(set(traces) == {"schema", "origin", "candidate_sha256", "authorization_sha256", "sessions"}, "ADAPTER_TRACE_FIELDS")
        require(traces["schema"] == "qsg.native-probe.adapter-traces.v1" and traces["origin"] == "SYNTHETIC", "ADAPTER_ORIGIN")
        require(traces["candidate_sha256"] == candidate_sha256 and traces["authorization_sha256"] == authorization_sha256, "ADAPTER_FREEZE")
        manifest_raw = Path(manifest_path).read_bytes()
        require(sha256(manifest_raw) == manifest_sha256, "MANIFEST_ANCHOR")
        manifest = decode(manifest_raw)
        entry = next(e for e in manifest["streams"] if e["actor"] == "HOST")
        require(entry["file"] == "host.jsonl", "HOST_PATH")
        host_raw = Path(manifest_path).with_name("host.jsonl").read_bytes()
        require(len(host_raw) <= 8388608 and sha256(host_raw) == entry["raw_sha256"], "HOST_ANCHOR")
        host = [decode(line) for line in host_raw.splitlines()]
        required = {row["session_id"] for row in host if row["kind"] == "TX"}
        require(type(traces["sessions"]) is dict and set(traces["sessions"]) <= required, "ADAPTER_SESSION_SET")
        for sid in required - set(traces["sessions"]): result["missing"].append("ADAPTER_SESSION_MISSING:" + sid)
        endpoints = set()
        for sid, session in traces["sessions"].items():
            require(set(session) == {"events", "spec", "peer", "expected", "watchdog_events"}, "ADAPTER_SESSION_FIELDS")
            expected, peer, spec, events = session["expected"], session["peer"], session["spec"], session["events"]
            require(expected["session_id"] == sid and expected["candidate_sha256"] == candidate_sha256
                    and expected["authorization_sha256"] == authorization_sha256, "ADAPTER_SESSION_BINDING")
            require(peer["origin"] == "SYNTHETIC" and peer["os_evidence"] == "NOT_RUN", "ADAPTER_PEER_ORIGIN")
            require(spec["open_mode"] == 0x40080003 and spec["pipe_mode"] == 8 and spec["max_instances"] == 1
                    and spec["inheritable"] is False and spec["client_access"] == 0x120003, "ADAPTER_FLAGS")
            require(spec["endpoint"] not in endpoints, "ADAPTER_ENDPOINT_REPLAY"); endpoints.add(spec["endpoint"])
            require(type(events) is list and 3 <= len(events) <= 8192, "ADAPTER_EVENTS")
            state, ordinal, transferred = "NEW", 0, []
            for event in events:
                require(event["origin"] == "SYNTHETIC" and event["connection_id"] == expected["connection_id"], "ADAPTER_EVENT_BINDING")
                kind = event["kind"]
                common = {"origin", "kind", "connection_id"}
                if kind == "CREATE":
                    require(set(event) == common | {"spec_sha256"} and state == "NEW"
                            and event["spec_sha256"] == sha256(canonical(spec)), "ADAPTER_CREATE")
                    state = "CREATED"
                elif kind in ("CONNECT", "READ", "WRITE"):
                    require(set(event) == common | {"operation", "returned_bytes", "sha256"}, "ADAPTER_IO_FIELDS")
                    ordinal += 1
                    require(event["operation"] == f"op-{ordinal}" and type(event["returned_bytes"]) is int, "ADAPTER_OPERATION_REPLAY")
                    if kind == "CONNECT":
                        require(state == "CREATED" and event["returned_bytes"] == 0 and event["sha256"] == sha256(b""), "ADAPTER_CONNECT")
                        state = "CONNECTED"
                    else:
                        require(state == "BOUND" and 1 <= event["returned_bytes"] <= 4096, "ADAPTER_IO_ORDER")
                        digest_string(event["sha256"])
                        transferred.append(("TX_CHUNK" if kind == "WRITE" else "RX_CHUNK", event["returned_bytes"], event["sha256"]))
                elif kind == "PEER_BOUND":
                    require(set(event) == common | {"proof_sha256"} and state == "CONNECTED"
                            and event["proof_sha256"] == sha256(canonical(peer)), "ADAPTER_PEER_DIGEST")
                    state = "BOUND"
                elif kind == "CLEANUP":
                    require(set(event) == common | {"result"} and state == "BOUND", "ADAPTER_CLOSE_ORDER")
                    if event["result"] != "CLOSED": result["missing"].append("ADAPTER_CLEANUP_UNCERTAIN:" + sid)
                    state = "CLOSED"
                else:
                    raise ValueError("ADAPTER_UNKNOWN_EVENT")
            if state != "CLOSED": result["missing"].append("ADAPTER_TERMINAL_MISSING:" + sid)
            chunks = [(r["kind"], r["frame_length"], r["frame_sha256"]) for r in host
                      if r["session_id"] == sid and r["kind"] in ("TX_CHUNK", "RX_CHUNK")]
            require(chunks == transferred, "ADAPTER_BYTE_DISAGREEMENT")
            requests = [r["request_id"] for r in host if r["session_id"] == sid and r["kind"] == "TX"]
            active, completed = None, []
            for kind, data in session["watchdog_events"]:
                if kind == "WATCHDOG_ARM":
                    require(active is None and data == {"request_id": data["request_id"], "deadline_ms": 250, "cutoff_ms": 2000}, "ADAPTER_WATCHDOG_ARM")
                    active = data["request_id"]
                else:
                    require(active is not None and data["request_id"] == active, "ADAPTER_WATCHDOG_BINDING")
                    require((kind == "REPLY_OBSERVED" and data == {"request_id": active, "resources_closed": False})
                        or (kind == "CLEANUP_OBSERVED" and data == {"request_id": active, "io_completed": True,
                                                                  "resources_closed": True, "state": "COMPLETE"}), "ADAPTER_WATCHDOG_COMPLETE")
                    completed.append(active); active = None
            if active is not None or completed != requests: result["missing"].append("ADAPTER_WATCHDOG_MISSING:" + sid)
        result["sessions"] = len(traces["sessions"])
        if not result["missing"]: result["status"] = "SYNTHETIC_PASS"
    except (OSError, ValueError, TypeError, KeyError, IndexError, StopIteration) as exc:
        result["errors"].append(str(exc)); result["status"] = "SYNTHETIC_FAIL"
    return result


def main(argv=None):
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Read-only synthetic probe evidence replay")
    for name in ("manifest", "manifest-sha256", "plan", "plan-sha256", "candidate-sha256", "authorization-sha256"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--adapter-traces")
    parser.add_argument("--adapter-traces-sha256")
    args = parser.parse_args(argv)
    result = verify(args.manifest, args.manifest_sha256, args.plan, args.plan_sha256,
                    args.candidate_sha256, args.authorization_sha256)
    if args.adapter_traces or args.adapter_traces_sha256:
        adapter = verify_adapter_traces(args.adapter_traces, args.adapter_traces_sha256, args.manifest,
            args.manifest_sha256, args.candidate_sha256, args.authorization_sha256)
        result["adapter"] = adapter
        result["errors"].extend(adapter["errors"]); result["missing"].extend(adapter["missing"])
        if result["errors"]: result["status"] = "SYNTHETIC_FAIL"
        elif result["missing"]: result["status"] = "SYNTHETIC_INDETERMINATE"
        if result["status"] != "SYNTHETIC_PASS":
            result["synthetic"] = {case: result["status"] for case in CASES}
    print(json.dumps(result, indent=2, sort_keys=True))
    return {"SYNTHETIC_PASS": 0, "SYNTHETIC_FAIL": 1, "SYNTHETIC_INDETERMINATE": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
