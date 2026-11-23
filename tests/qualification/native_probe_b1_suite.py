"""Reproducible API-level traces; real N01-N09 and L01-L12 stay NOT_RUN."""
from pathlib import Path

from ce_qualification.native_probe_protocol import canonical, sha256
from ce_qualification.native_probe_watchdog import Watchdog
from ce_qualification import native_probe_win32 as w
from native_probe_b1_fakes import EXPECTED, equipment
from native_probe_fakes import Clock


def build(path, candidate, authorization):
    sessions = []
    for vector, count in (("cleanup", 20), ("cancel", 3), ("timeout", 3), ("late", 3)):
        for repetition in range(1, count + 1):
            p, f, handle = equipment(); p.query_client(handle, EXPECTED, deadline_ms=250)
            if vector != "cleanup":
                f.pending_direction = "READ"
                p.start_io(handle, "probe", "READ", maximum=3, deadline_ms=250)
                if vector == "cancel": p.cancel_io(handle, "probe")
                elif vector == "timeout": p.await_io(handle, "probe")
                else: f.clock.advance(250)
                f.completion = 0 if vector == "late" else w.OPERATION_ABORTED
                assert p.poll_io(handle, "probe")["status"] != "COMPLETE"
            assert p.close()
            # Independent failure model: watchdog reaches its own hard cutoff.
            # This is not measured OS termination or owner-clock latency.
            clock = Clock(); clock.advance(9000); events = []
            watchdog = Watchdog(clock, lambda *event: events.append(event), enabled=True)
            operation = "probe" if vector != "cleanup" else "connect"
            watchdog.arm(operation); clock.advance(2000); assert watchdog.poll() == "INDETERMINATE"
            ordinal = len(sessions) + 1
            sessions.append({"binding": {"session_id": "B1-OFFLINE", "channel_id": f"channel-{ordinal}",
                "epoch": ordinal, "connection_id": f"connection-{ordinal}", "candidate_sha256": candidate,
                "authorization_sha256": authorization}, "vector": vector, "repetition": repetition,
                "events": p.trace, "watchdog": {"origin": "SYNTHETIC", "clock_id": "external-watchdog-model",
                    "operation": operation, "started_ms": 9000, "cutoff_observed_ms": clock(), "state": watchdog.state}})
    raw = canonical({"schema": "qsg.native-probe.b1-traces.v1", "origin": "SYNTHETIC",
        "candidate_sha256": candidate, "authorization_sha256": authorization, "sessions": sessions})
    with Path(path).open("xb") as out: out.write(raw)
    return sha256(raw)
