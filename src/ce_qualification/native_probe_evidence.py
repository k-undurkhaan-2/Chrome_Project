"""Bounded append-only synthetic recorder, separate from every QSG ledger.

Snapshots are copies. Export is exclusive-create and never updates old logs.
The chain is an integrity check, not proof of completeness or OS identity.
"""
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from .native_probe_protocol import SCHEMA, canonical, decode, digest_string, require, sha256
from .native_probe_schema import validate_event

ACTORS = ("HOST", "LUA_MODEL", "WATCHDOG", "OBSERVER")


class Recorder:
    def __init__(self, actor, candidate_sha256, authorization_sha256, clock_ms, utc_now,
                 *, enabled=False, max_events=8192, max_bytes=8 * 1024 * 1024, fault=None):
        require(enabled is True, "RECORDER_DISABLED")
        require(actor in ACTORS, "ACTOR")
        digest_string(candidate_sha256); digest_string(authorization_sha256)
        self.actor, self.candidate, self.authorization = actor, candidate_sha256, authorization_sha256
        self.clock, self.utc = clock_ms, utc_now
        self.maximum, self.byte_limit, self.fault = max_events, max_bytes, fault
        self._rows, self._raw, self.last, self.closed, self.failed = [], bytearray(), -1, False, False
        self.schema = decode(Path(__file__).with_name("native_probe_evidence.schema.json").read_bytes().strip())

    @property
    def rows(self):
        return deepcopy(self._rows)

    def append(self, case_id, kind, *, binding=None, request=None, data=None, raw=None,
               error="", response="", cancel_stage="NONE"):
        try:
            require(not self.closed and not self.failed, "RECORDER_CLOSED")
            require(len(self._rows) < self.maximum, "RECORDER_FULL")
            now, utc = self.clock(), self.utc()
            require(type(now) is int and now >= 0 and now >= self.last, "RECORDER_CLOCK")
            require(type(utc) is str and datetime.fromisoformat(utc).utcoffset() is not None, "UTC_OFFSET_REQUIRED")
            number = len(self._rows) + 1
            binding = binding or {"session_id": "SYNTHETIC-MATRIX", "channel_id": "offline", "epoch": 1}
            request = request or {}
            row = {"schema": SCHEMA, "origin": "SYNTHETIC", "actor": self.actor,
                   "case_id": case_id, "trial_id": "offline-1", "event_id": f"{self.actor}:{number}",
                   "sequence": number, "utc": utc, "clock_id": "synthetic-" + self.actor,
                   "elapsed_ms": now, **binding, "request_id": request.get("request_id", ""),
                   "request_sequence": request.get("sequence", 0), "candidate_sha256": self.candidate,
                   "authorization_sha256": self.authorization, "kind": kind,
                   "frame_length": len(raw) if raw is not None else 0,
                   "frame_sha256": sha256(raw) if raw is not None else "", "response": response,
                   "error": error, "cancel_stage": cancel_stage,
                   "data": {"wire_hex": raw.hex()} if raw is not None else deepcopy(data or {}),
                   "previous_sha256": self._rows[-1]["content_sha256"] if self._rows else "0" * 64}
            row["content_sha256"] = sha256(canonical(row))
            validate_event(row, self.schema)
            encoded = canonical(row) + b"\n"
            require(len(self._raw) + len(encoded) <= self.byte_limit, "RECORDER_FULL")
            if self.fault:
                self.fault(kind)
            self._raw.extend(encoded)
            self._rows.append(row)
            self.last = now
            return row["content_sha256"]
        except Exception:
            self.failed = True
            raise

    def finish(self):
        self.append("N09", "TERMINAL")
        self.closed = True

    def export(self, directory):
        require(self.closed and not self.failed and self._rows, "UNSEALED_STREAM")
        filename = self.actor.lower() + ".jsonl"
        with (Path(directory) / filename).open("xb") as handle:
            require(handle.write(self._raw) == len(self._raw), "SHORT_EVIDENCE_WRITE")
        return {"actor": self.actor, "file": filename, "event_count": len(self._rows),
                "terminal_sequence": self._rows[-1]["sequence"], "terminal_head": self._rows[-1]["content_sha256"],
                "raw_sha256": sha256(self._raw)}


def export_bundle(directory, recorders, plan_raw, candidate_sha256, authorization_sha256):
    directory = Path(directory)
    directory.mkdir(parents=False, exist_ok=False)
    require({r.actor for r in recorders} == set(ACTORS) and len(recorders) == len(ACTORS), "STREAM_SET")
    manifest = {"schema": SCHEMA, "origin": "SYNTHETIC", "candidate_sha256": candidate_sha256,
                "authorization_sha256": authorization_sha256, "plan_sha256": sha256(plan_raw),
                "streams": [r.export(directory) for r in recorders]}
    raw = canonical(manifest)
    with (directory / "evidence.json").open("xb") as handle:
        require(handle.write(raw) == len(raw), "SHORT_EVIDENCE_WRITE")
    return sha256(raw)
