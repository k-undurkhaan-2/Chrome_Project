"""Bounded, chained evidence and offline file transport; no process APIs.

Digests detect alteration only relative to independently retained trusted heads.
An attacker able to replace both records and their anchors can forge a chain.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

ZERO = "0" * 64
ORIGINS = {"SYNTHETIC", "CE_DIAGNOSTIC_FUTURE", "TARGET_FUTURE", "DERIVED"}
RECORD_KEYS = {"schema", "origin", "source", "actor", "session_id", "run_id",
               "scenario", "sequence", "event_id", "clock", "kind", "data",
               "predecessor_digest", "content_digest"}
BODY_LIMIT = 65536
BLOB_LIMIT = 1024 * 1024
BLOB_COUNT_LIMIT = 32
BLOB_TOTAL_LIMIT = 8 * 1024 * 1024
MANIFEST_LIMIT = 65536
SIDECAR_ROLES = {"retained_before": "retained_snapshot", "retained_after": "retained_snapshot",
                 "diagnostic": "loader_diagnostic"}


class EvidenceError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise EvidenceError("DUPLICATE_JSON_KEY")
        out[key] = value
    return out


def decode(raw):
    try:
        return json.loads(raw, object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(EvidenceError("NONFINITE_JSON")))
    except (UnicodeError, ValueError) as exc:
        raise EvidenceError("INVALID_JSON") from exc


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", value):
        raise EvidenceError("INVALID_IDENTIFIER")
    return value


def bits(value):
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 0xFFFFFFFF:
        return f"0x{value:08X}"
    if isinstance(value, str) and re.fullmatch(r"0x[0-9A-F]{8}", value):
        return value
    raise EvidenceError("INVALID_FLOAT32_BITS")


def finite_bits(value):
    value = bits(value)
    if int(value, 16) & 0x7F800000 == 0x7F800000:
        raise EvidenceError("NONFINITE_FLOAT32")
    return value


def utc(value):
    if not isinstance(value, str):
        raise EvidenceError("INVALID_UTC")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timedelta(0):
        raise EvidenceError("UTC_OFFSET_REQUIRED")
    return parsed


class SyntheticClock:
    """Explicit simulated time, independent epochs per actor, never native time."""
    def __init__(self, origin, *, offset_ns=0, start="2026-11-20T00:00:00+00:00"):
        self.origin = identifier(origin)
        self.ns = offset_ns
        self.wall = utc(start)

    def sample(self):
        self.ns += 1_000_000
        self.wall += timedelta(milliseconds=1)
        return {"kind": "SYNTHETIC_MONOTONIC_NS", "origin": self.origin,
                "monotonic_ns": self.ns, "utc": self.wall.isoformat()}


def validate_chain(records, *, source=None, session_id=None, payload_only=False):
    head, seen, last_ns, clock_origin = ZERO, set(), -1, None
    for sequence, row in enumerate(records, 1):
        # Also used on an unsealed draft before copying, hashing or publishing it.
        if not isinstance(row["data"], dict) or len(canonical(row["data"])) > BODY_LIMIT:
            raise EvidenceError("PAYLOAD_BOUND")
        if payload_only:
            continue
        if set(row) != RECORD_KEYS or type(row["schema"]) is not int or row["schema"] != 1:
            raise EvidenceError("INVALID_RECORD_SCHEMA")
        if row["origin"] not in ORIGINS or type(row["sequence"]) is not int or row["sequence"] != sequence:
            raise EvidenceError("ORIGIN_OR_ORDER")
        for key in ("source", "actor", "session_id", "run_id", "scenario", "kind", "event_id"):
            identifier(row[key])
        source = source or row["source"]
        session_id = session_id or row["session_id"]
        if row["source"] != source or row["session_id"] != session_id:
            raise EvidenceError("STREAM_IDENTITY_CHANGED")
        if row["event_id"] in seen or row["event_id"] != f"{source}:{sequence}":
            raise EvidenceError("DUPLICATE_EVENT_ID")
        seen.add(row["event_id"])
        clock = row["clock"]
        if set(clock) != {"kind", "origin", "monotonic_ns", "utc"}:
            raise EvidenceError("INVALID_CLOCK_SCHEMA")
        identifier(clock["origin"])
        utc(clock["utc"])
        if clock["kind"] not in {"SYNTHETIC_MONOTONIC_NS", "MONOTONIC_NS"}:
            raise EvidenceError("CLOCK_KIND")
        if row["origin"] == "SYNTHETIC" and clock["kind"] != "SYNTHETIC_MONOTONIC_NS":
            raise EvidenceError("SYNTHETIC_CLOCK_REQUIRED")
        n = clock["monotonic_ns"]
        if type(n) is not int or n < last_ns or n < 0:
            raise EvidenceError("CLOCK_REVERSED")
        clock_origin = clock_origin or clock["origin"]
        if clock["origin"] != clock_origin:
            raise EvidenceError("CLOCK_ORIGIN_CHANGED")
        last_ns = n
        if row["predecessor_digest"] != head:
            raise EvidenceError("CHAIN_DISCONTINUITY")
        body = {k: v for k, v in row.items() if k != "content_digest"}
        if row["content_digest"] != digest(body):
            raise EvidenceError("CONTENT_DIGEST_MISMATCH")
        head = row["content_digest"]
    return head


class Stream:
    def __init__(self, session_id, source, clock=None):
        self.session_id, self.source = identifier(session_id), identifier(source)
        self.clock = clock or SyntheticClock(source)
        self.rows = []

    def emit(self, kind, data, *, run_id="session", scenario="SESSION", origin="SYNTHETIC"):
        validate_chain([{"data": data}], payload_only=True)
        sequence = len(self.rows) + 1
        row = {"schema": 1, "origin": origin, "source": self.source,
               "actor": self.source, "session_id": self.session_id, "run_id": run_id,
               "scenario": scenario, "sequence": sequence,
               "event_id": f"{self.source}:{sequence}", "clock": self.clock.sample(),
               "kind": kind, "data": deepcopy(data),
               "predecessor_digest": self.rows[-1]["content_digest"] if self.rows else ZERO}
        row["content_digest"] = digest(row)
        validate_chain(self.rows + [row])
        self.rows.append(row)
        return deepcopy(row)


def encode_rows(rows):
    validate_chain(rows)
    return b"".join(canonical(row) + b"\n" for row in rows)


def read_rows(path, expected_sha256):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise EvidenceError("FILE_DIGEST_MISMATCH")
    if not raw or not raw.endswith(b"\n") or len(raw) > 32 * 1024 * 1024:
        raise EvidenceError("MISSING_OR_TRUNCATED_STREAM")
    rows = [decode(line) for line in raw.splitlines()]
    validate_chain(rows)
    return rows


def export_bundle(directory, streams, *, sidecars=None):
    """New synthetic artifacts only. Caller must retain returned seal separately."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    files = {}
    for source, rows in streams.items():
        identifier(source)
        path = directory / f"{source}.jsonl"
        path.write_bytes(encode_rows(rows))
        files[path.name] = {"source": source, "sha256": file_hash(path),
                            "records": len(rows), "head": rows[-1]["content_digest"]}
    manifest = {"schema": 1, "watermark": "SYNTHETIC", "live": "NOT_RUN", "files": files}
    if sidecars is not None:
        manifest["schema"] = 2
        manifest["sidecars"] = sidecars.seal([r for rows in streams.values() for r in rows])
        destination = directory / "sidecars"
        destination.mkdir()
        for name in ["sidecars.json"] + [entry["sha256"] + ".json" for entry in sidecars.entries.values()]:
            raw = bounded_read(sidecars.root / name, BLOB_LIMIT if name != "sidecars.json" else MANIFEST_LIMIT)
            _exclusive_write(destination / name, raw)
    path = directory / "bundle.json"
    path.write_bytes(canonical(manifest) + b"\n")
    return path, file_hash(path)


def directory_stamp(path):
    """Reject links/reparse points throughout a caller-designated evidence root."""
    path = Path(os.path.abspath(path))
    stamps = []
    for part in [*reversed(path.parents), path]:
        info = part.lstat()
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & 0x400):
            raise EvidenceError("SIDECAR_DIRECTORY_LINK")
        stamps.append((info.st_dev, info.st_ino))
    return tuple(stamps)


def bounded_read(path, maximum):
    """Bound reads before allocation; detect link, hardlink and replacement races."""
    path = Path(path)
    root_stamp = directory_stamp(path.parent)
    before = path.lstat()
    def regular(info):
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or getattr(info, "st_file_attributes", 0) & 0x400):
            raise EvidenceError("SIDECAR_FILE_LINK")
        if not 0 < info.st_size <= maximum:
            raise EvidenceError("SIDECAR_FILE_BOUND")
    def identity(info):
        # Windows lstat/fstat can expose different legacy st_ctime meanings.
        # Compare file identity, actual size/write time and creation time instead.
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
                getattr(info, "st_birthtime_ns", None))
    regular(before)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        opened = os.fstat(handle.fileno()); regular(opened)
        if identity(before) != identity(opened):
            raise EvidenceError("SIDECAR_REPLACED")
        raw = handle.read(maximum + 1)
        after = os.fstat(handle.fileno()); regular(after)
    final = path.lstat(); regular(final)
    if (identity(before) != identity(after) or identity(before) != identity(final)
            or root_stamp != directory_stamp(path.parent) or len(raw) != before.st_size):
        raise EvidenceError("SIDECAR_REPLACED")
    return raw


def _exclusive_write(path, raw):
    # A crash leaves unsealed/partial evidence. Never overwrite or reuse it.
    directory_stamp(Path(path).parent)
    with Path(path).open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


class SidecarStore:
    """Opt-in v2 evidence writer. All references are data, never source paths."""
    def __init__(self, directory, session_id):
        self.root = Path(os.path.abspath(directory))
        directory_stamp(self.root.parent)
        self.root.mkdir(exist_ok=False)
        self.session_id = identifier(session_id)
        self.bundle_id = uuid.uuid4().hex
        self.entries = {}
        self._sealed = None

    def put(self, value, normalized_type):
        if self._sealed is not None:
            raise EvidenceError("SIDECAR_ALREADY_SEALED")
        if normalized_type not in set(SIDECAR_ROLES.values()):
            raise EvidenceError("SIDECAR_TYPE")
        raw = canonical(value)
        if not 0 < len(raw) <= BLOB_LIMIT:
            raise EvidenceError("SIDECAR_BLOB_BOUND")
        sha = hashlib.sha256(raw).hexdigest()
        ref = {"artifact_id": "sha256:" + sha, "sha256": sha, "byte_length": len(raw),
               "normalized_type": normalized_type, "evidence_schema_version": 2}
        if ref["artifact_id"] in self.entries:
            if self.entries[ref["artifact_id"]] != ref or bounded_read(self.root / (sha + ".json"), BLOB_LIMIT) != raw:
                raise EvidenceError("SIDECAR_COLLISION_OR_CHANGE")
        else:
            if (len(self.entries) >= BLOB_COUNT_LIMIT
                    or sum(e["byte_length"] for e in self.entries.values()) + len(raw) > BLOB_TOTAL_LIMIT):
                raise EvidenceError("SIDECAR_BUNDLE_BOUND")
            _exclusive_write(self.root / (sha + ".json"), raw)
            self.entries[ref["artifact_id"]] = ref
        return deepcopy(ref)

    def seal(self, records):
        bindings, used = [], set()
        for row in records:
            if row["kind"] != "config_rejected" or row["data"].get("evidence_schema_version") != 2:
                continue
            if row["session_id"] != self.session_id or row["data"]["bundle_id"] != self.bundle_id:
                raise EvidenceError("SIDECAR_CONTEXT")
            roles = {}
            for role in SIDECAR_ROLES:
                ref = row["data"][role]
                if self.entries.get(ref["artifact_id"]) != ref:
                    raise EvidenceError("SIDECAR_REFERENCE")
                roles[role] = ref["artifact_id"]; used.add(ref["artifact_id"])
            bindings.append({**{k: row[k] for k in ("source", "session_id", "event_id", "run_id", "scenario", "sequence", "content_digest")},
                             "roles": roles})
        if not bindings or used != set(self.entries) or len({b["event_id"] for b in bindings}) != len(bindings):
            raise EvidenceError("SIDECAR_CLOSURE")
        manifest = {"schema": "ce.sidecars.v2", "bundle_id": self.bundle_id, "session_id": self.session_id,
                    "artifacts": sorted(self.entries.values(), key=lambda e: e["artifact_id"]), "bindings": bindings}
        raw = canonical(manifest)
        if len(raw) > MANIFEST_LIMIT:
            raise EvidenceError("SIDECAR_MANIFEST_BOUND")
        expected_names = {"sidecars.json"} | {e["sha256"] + ".json" for e in self.entries.values()}
        for entry in self.entries.values():
            blob = bounded_read(self.root / (entry["sha256"] + ".json"), BLOB_LIMIT)
            if len(blob) != entry["byte_length"] or hashlib.sha256(blob).hexdigest() != entry["sha256"]:
                raise EvidenceError("SIDECAR_CONTENT_CHANGED")
        if self._sealed is None:
            if {p.name for p in self.root.iterdir()} != expected_names - {"sidecars.json"}:
                raise EvidenceError("SIDECAR_CLOSURE")
            _exclusive_write(self.root / "sidecars.json", raw)
        if ({p.name for p in self.root.iterdir()} != expected_names
                or bounded_read(self.root / "sidecars.json", MANIFEST_LIMIT) != raw):
            raise EvidenceError("SIDECAR_SEAL_CHANGED")
        self._sealed = {"schema": 2, "bundle_id": self.bundle_id, "sha256": hashlib.sha256(raw).hexdigest(), "byte_length": len(raw)}
        return deepcopy(self._sealed)
