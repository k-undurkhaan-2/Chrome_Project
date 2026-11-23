"""Strict QSG sidecar plus reuse of the independent, passive R1 CE normalizer."""
from copy import deepcopy

from .evidence import canonical, digest, Stream
from .recorder import CERecorder
from .qsg_store import require

FIELDS = {
    "READY": {"policy_digest"}, "CANDIDATE": {"address", "mapping", "fields", "rank_sequence", "population_sequence",
        "alias", "qualified_count", "hard_pass", "recommendation", "raw_count", "scanned_count", "filtered_count", "selected_count"},
    "PERMIT_REQUEST": {"request_digest", "operation_id"}, "RESERVATION": {"attempt", "request_digest", "receipt_kind"},
    "RAW_DISPATCH": {"attempt", "receipt", "address", "bits"}, "RAW_RETURN": {"attempt", "result"},
    "VERIFIED": {"attempt", "address", "bits", "core_sequence", "target", "readback"}, "FAILED_CLOSED": {"code"},
}


class Recorder:
    def __init__(self, session_id, clock_ms, *, enabled=False, maximum=8192, fault=None):
        self.session_id, self.clock = session_id, clock_ms
        self.enabled, self.maximum = enabled, maximum
        self.fault = fault or (lambda _: None)
        self.rows = []
        self.core_stream = Stream(session_id, "ce")
        self.legacy = CERecorder(self.core_stream, enabled=enabled)
        self.snapshots = {}

    def append(self, kind, body):
        require(self.enabled and len(self.rows) < self.maximum, "QSG_RECORDER_UNAVAILABLE")
        require(kind in FIELDS and set(body) == {"lease", "phase", "data"} and set(body["data"]) == FIELDS[kind], "QSG_EVENT_SCHEMA")
        self.fault(kind)
        now = self.clock()
        require(type(now) is int and (not self.rows or now >= int(self.rows[-1]["clock_ms"])), "QSG_CLOCK")
        row = {"schema": "qsg.event.v1", "origin": "SYNTHETIC", "source": "ce-qsg", "session_id": self.session_id,
            "sequence": len(self.rows)+1, "clock_origin": "synthetic-ce-ms", "clock_ms": str(now),
            "kind": kind, "body": deepcopy(body), "previous": self.rows[-1]["digest"] if self.rows else "0"*64}
        # Compare integers above; wire clocks remain canonical decimal strings.
        row["digest"] = digest(row)
        require(len(canonical(row)) <= 65536, "QSG_EVENT_BOUND")
        self.rows.append(row)
        return row["digest"]

    def capture(self, snapshot, run, phase, aliases):
        require(self.enabled and len(self.core_stream.rows) < self.maximum, "QSG_RECORDER_UNAVAILABLE")
        self.fault("capture")
        old = self.snapshots.get(run)
        require(len(self.core_stream.rows) + snapshot["last_sequence"] - (old["last_sequence"] if old else 0) + 1 <= self.maximum,
                "QSG_RECORDER_UNAVAILABLE")
        if old:
            require(snapshot["last_sequence"] >= old["last_sequence"], "QSG_SNAPSHOT_ROLLBACK")
            require(all(snapshot["counters"][k] >= v for k, v in old["counters"].items() if k != "invalid_count"), "QSG_COUNTER_ROLLBACK")
            if snapshot == old:
                return True
            if snapshot["last_sequence"] == old["last_sequence"]:
                # The unchanged core samples its tick clock / identity counters
                # without emitting an event. These are legitimate snapshots.
                for key in ("state", "running", "cleanup_ok", "events"):
                    require(snapshot[key] == old[key], "QSG_SNAPSHOT_CONTRADICTION")
                for key in ("write_count", "adapter_write_attempts", "verified_writes", "scan_count", "monitor_checks"):
                    require(snapshot["counters"][key] == old["counters"][key], "QSG_SNAPSHOT_CONTRADICTION")
        self.legacy.capture(snapshot, run_id=run, scenario=phase, bindings={"addresses": deepcopy(aliases)}, model_lua="MODEL_ONLY")
        self.snapshots[run] = deepcopy(snapshot)
        return True

    def seal(self):
        return digest({"qsg": self.rows, "ce": self.core_stream.rows})
