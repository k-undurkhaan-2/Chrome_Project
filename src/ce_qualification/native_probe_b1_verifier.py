"""Independent B1 evidence replay. No provider, recorder, watchdog or Lua imports."""
import hashlib
import json
from pathlib import Path


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(path, seal, candidate, authorization):
    result = {"status": "SYNTHETIC_FAIL", "origin": "DERIVED", "errors": [],
              "native": {f"N{n:02}": "NOT_RUN" for n in range(1, 10)},
              "live": {f"L{n:02}": "NOT_RUN" for n in range(1, 13)}}
    def need(ok, code):
        if not ok: raise ValueError(code)
    try:
        raw = Path(path).read_bytes()
        need(len(raw) <= 8 * 1024 * 1024 and digest(raw) == seal, "SEAL")
        def pairs(items):
            out = {}
            for key, value in items:
                need(key not in out, "DUPLICATE_KEY"); out[key] = value
            return out
        bundle = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
        need(encoded(bundle) == raw, "NONCANONICAL")
        need(set(bundle) == {"schema", "origin", "candidate_sha256", "authorization_sha256", "sessions"}, "BUNDLE_FIELDS")
        need(bundle["schema"] == "qsg.native-probe.b1-traces.v1" and bundle["origin"] == "SYNTHETIC", "ORIGIN")
        need(bundle["candidate_sha256"] == candidate and bundle["authorization_sha256"] == authorization, "IDENTITY")
        seen, totals, vectors = set(), 0, {}
        need(type(bundle["sessions"]) is list and len(bundle["sessions"]) == 29, "SESSION_COUNT")
        for session in bundle["sessions"]:
            need(set(session) == {"binding", "vector", "repetition", "events", "watchdog"}, "SESSION_FIELDS")
            binding = session["binding"]
            need(set(binding) == {"session_id", "channel_id", "epoch", "connection_id", "candidate_sha256", "authorization_sha256"}, "BINDING_FIELDS")
            need(binding["session_id"] == "B1-OFFLINE" and binding["candidate_sha256"] == candidate
                 and binding["authorization_sha256"] == authorization, "SESSION_IDENTITY")
            need(type(binding["epoch"]) is int and binding["epoch"] > 0, "EPOCH")
            for key in ("channel_id", "connection_id", "epoch"):
                need((key, binding[key]) not in seen, "SESSION_REPLAY"); seen.add((key, binding[key]))
            vector, repetition = session["vector"], session["repetition"]
            need(vector in ("cleanup", "cancel", "timeout", "late") and type(repetition) is int, "VECTOR")
            need(1 <= repetition <= (20 if vector == "cleanup" else 3), "REPETITIONS")
            need((vector, repetition) not in seen, "VECTOR_REPLAY"); seen.add((vector, repetition))
            vectors[vector] = vectors.get(vector, 0) + 1
            head, last, pending, operations = "0" * 64, -1, None, set()
            closed, created, connected, client, failed = False, False, False, False, False
            kinds = []
            for seq, row in enumerate(session["events"], 1):
                need(set(row) == {"origin", "os_observed", "actor", "clock_id", "at_ms", "event", "sequence", "previous_sha256", "data", "sha256"}, "EVENT_FIELDS")
                need(row["origin"] == "SYNTHETIC" and row["os_observed"] is False, "MOCK_IS_NOT_NATIVE")
                need(row["actor"] == "WIN32_MODEL" and row["clock_id"] == "win32-model", "ACTOR_CLOCK")
                need(type(row["at_ms"]) is int and row["at_ms"] >= last, "CLOCK_ORDER"); last = row["at_ms"]
                need(row["sequence"] == seq and row["previous_sha256"] == head, "EVENT_CHAIN")
                need(row["sha256"] == digest(encoded({k: v for k, v in row.items() if k != "sha256"})), "EVENT_HASH")
                head = row["sha256"]; event, data = row["event"], row["data"]; kinds.append(event)
                need(not closed, "AFTER_CLEANUP")
                if event == "CREATE":
                    need(seq == 1 and not created, "CREATE_ORDER"); created = True
                    security = data["security"]
                    need(security["handle"] == data["handle"] and security["protected"] is True, "DACL_HANDLE")
                    need(len(security["aces"]) == 2 and [a["mask"] for a in security["aces"]] == [0x12019F, 0x120003], "DACL_MASK")
                    need(security["aces"][0]["sid"] != security["aces"][1]["sid"], "DACL_PRINCIPALS")
                elif event == "IO_START":
                    need(created and pending is None and not failed and data["operation"] not in operations, "IO_ORDER")
                    need(data["direction"] in ("CONNECT", "READ", "WRITE"), "IO_DIRECTION")
                    need((data["direction"] == "CONNECT" and not connected and data["maximum"] == 0)
                         or (connected and data["direction"] != "CONNECT" and 1 <= data["maximum"] <= 4096), "IO_BOUND")
                    need(0 < data["deadline_ms"] - row["at_ms"] <= 250, "DEADLINE_BOUND")
                    operations.add(data["operation"]); pending = dict(data, cancelled=False)
                elif event == "CANCEL_REQUEST":
                    need(pending is not None and data["operation"] == pending["operation"] and not pending["cancelled"], "CANCEL_ORDER")
                    pending["cancelled"] = True
                elif event == "IO_COMPLETE":
                    need(pending is not None and data["operation"] == pending["operation"] and data["direction"] == pending["direction"], "COMPLETION_ORDER")
                    wire = bytes.fromhex(data["wire_hex"])
                    need(type(data["count"]) is int and len(wire) == data["count"] <= pending["maximum"], "BYTE_COUNT")
                    need(digest(wire) == data["sha256"] and data["event_closed"] is True, "BYTE_DIGEST_OR_CLOSE")
                    need(data["status"] in ("COMPLETE", "ABORTED", "FAILED", "REJECTED_LATE"), "IO_STATUS")
                    if data["status"] == "COMPLETE":
                        need(not pending["cancelled"] and row["at_ms"] < pending["deadline_ms"], "LATE_ACCEPTANCE")
                        if data["direction"] == "CONNECT": connected = True
                    else: failed = True
                    pending = None
                elif event == "CLIENT_IDENTITY":
                    need(connected and pending is None and not client, "PEER_ORDER"); client = True
                    need(data["server_identity"] == "BLOCKED_CLIENT_HANDLE_UNVERIFIED" and data["mapped_image"] == "NOT_PROVEN", "UNPROVEN_PEER")
                elif event == "CLEANUP":
                    need(created and pending is None and data["pending"] is False, "PENDING_CLEANUP")
                    need(data["result"] == "CLOSED" and data["owned"] == data["closed"] > 0, "CLEANUP_UNCERTAIN"); closed = True
                else: raise ValueError("EVENT_KIND")
            need(closed and connected and client and pending is None, "INCOMPLETE_SESSION")
            if vector == "cleanup": need(not failed and "CANCEL_REQUEST" not in kinds, "POSITIVE_FAILED")
            else: need(failed, "NEGATIVE_ACCEPTED")
            if vector in ("cancel", "timeout"): need("CANCEL_REQUEST" in kinds, "CANCEL_MISSING")
            # Never compare these timestamps to WIN32_MODEL timestamps. Watchdog
            # state is checked only in its own clock domain and operation binding.
            watchdog = session["watchdog"]
            need(set(watchdog) == {"origin", "clock_id", "operation", "started_ms", "cutoff_observed_ms", "state"}, "WATCHDOG_FIELDS")
            need(watchdog["origin"] == "SYNTHETIC" and watchdog["clock_id"] == "external-watchdog-model", "WATCHDOG_ORIGIN")
            need(watchdog["operation"] == ("probe" if vector != "cleanup" else "connect"), "WATCHDOG_BINDING")
            need(type(watchdog["started_ms"]) is int and type(watchdog["cutoff_observed_ms"]) is int, "WATCHDOG_CLOCK")
            need(watchdog["cutoff_observed_ms"] - watchdog["started_ms"] == 2000 and watchdog["state"] == "INDETERMINATE", "WATCHDOG_CUTOFF")
            totals += len(session["events"])
        need(vectors == {"cleanup": 20, "cancel": 3, "timeout": 3, "late": 3}, "VECTOR_COVERAGE")
        result.update(status="SYNTHETIC_PASS", sessions=29, events=totals, vectors=vectors,
                      os_identity="NOT_RUN", client_handle="BLOCKED_CLIENT_HANDLE_UNVERIFIED")
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        result["errors"].append(str(exc))
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    for name in ("path", "seal", "candidate", "authorization"): parser.add_argument("--" + name, required=True)
    args = parser.parse_args(); result = verify(args.path, args.seal, args.candidate, args.authorization)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "SYNTHETIC_PASS" else 1


if __name__ == "__main__": raise SystemExit(main())
