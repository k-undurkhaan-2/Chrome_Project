"""Versioned target recorder v2, using only owned Python bytearrays this round.

Future native providers/transport are deliberately absent. Importing this module
does not reserve native memory, start a process, query a PID or access CE.
"""
from dataclasses import asdict, dataclass
import re
import struct
from typing import Protocol

from .evidence import EvidenceError, Stream, bits, digest, identifier

SIZE, PAGE = 65536, 4096
MODES = {"baseline_unique": "unique", "zero_match": "zero", "ambiguous": "ambiguous",
         "over_limit": "129_plus", "incomplete_structure": "incomplete",
         "invalid_structure": "invalid", "value_drift": "drift", "relocate": "relocate"}


@dataclass(frozen=True)
class Instance:
    designation: str
    pid: int
    creation: str
    target_sha256: str

    def record(self):
        if self.designation not in ("A", "B") or type(self.pid) is not int or self.pid <= 0:
            raise EvidenceError("INVALID_TARGET_IDENTITY")
        if not re.fullmatch(r"[0-9A-F]{16}", self.creation) or int(self.creation, 16) == 0:
            raise EvidenceError("CREATION_IDENTITY_REQUIRED")
        if not re.fullmatch(r"[0-9a-f]{64}", self.target_sha256):
            raise EvidenceError("TARGET_FILE_IDENTITY_REQUIRED")
        return asdict(self)

    @property
    def token(self):
        self.record()
        return f"{self.pid}:{self.creation}"


class MemoryProvider(Protocol):
    """Future target-self interface, never a cross-process reader/writer."""
    base: int
    size: int
    def read_word(self, address: int) -> int: ...
    def write_word(self, address: int, word: int) -> None: ...


class SyntheticMemory:
    origin = "SYNTHETIC"
    size = SIZE

    def __init__(self, base):
        if type(base) is not int or base <= 0 or base % SIZE:
            raise EvidenceError("INVALID_SYNTHETIC_BASE")
        self.base, self.image, self.pages = base, bytearray(SIZE), set()
        self.reads = self.writes = 0
        self.released = False

    def offset(self, address):
        if (self.released or type(address) is not int or address % 4
                or not self.base <= address <= self.base + SIZE - 4
                or (address - self.base) // PAGE not in self.pages):
            raise EvidenceError("UNOWNED_OR_UNCOMMITTED_ADDRESS")
        return address - self.base

    def read_word(self, address):
        offset = self.offset(address)
        self.reads += 1
        return struct.unpack_from("<I", self.image, offset)[0]

    def write_word(self, address, word):
        offset = self.offset(address)
        bits(word)
        struct.pack_into("<I", self.image, offset, word)
        self.writes += 1

    def matches(self, word=0x42C80000):
        # A real scan of synthetic fixture bytes, never a claimed CE native scan.
        return [self.base + p * PAGE + off for p in sorted(self.pages)
                for off in range(0, PAGE, 4)
                if struct.unpack_from("<I", self.image, p * PAGE + off)[0] == word]


class TargetRecorder:
    version = "g1-target-recorder-v2-synthetic-only"

    def __init__(self, stream: Stream, instance: Instance, memory: SyntheticMemory,
                 allocation_id, *, enabled=False):
        if type(memory) is not SyntheticMemory:
            raise EvidenceError("NATIVE_PROVIDER_NOT_IMPLEMENTED")
        self.stream, self.instance, self.memory = stream, instance, memory
        self.identity = instance.record()
        self.allocation_id = identifier(allocation_id)
        self.enabled = enabled
        self.run_id, self.scenario = "session", "SESSION"
        self.active, self.retired, self.regions = [], set(), []
        self.mode = None
        if enabled:
            self.emit("allocation", {"base": memory.base, "size": SIZE,
                "protection": "PAGE_READWRITE", "owner": instance.token,
                "provider": "SYNTHETIC_BYTEARRAY", "recorder_version": self.version})

    def context(self, run_id, scenario):
        self.run_id, self.scenario = identifier(run_id), identifier(scenario)

    def emit(self, kind, data):
        if not self.enabled:
            raise EvidenceError("TARGET_RECORDER_DISABLED")
        return self.stream.emit(kind, {"identity": self.identity,
            "allocation_id": self.allocation_id, **data}, run_id=self.run_id, scenario=self.scenario)

    def apply(self, plan):
        if not self.enabled:
            raise EvidenceError("TARGET_RECORDER_DISABLED")
        mode = MODES.get(plan.get("mode"))
        if not mode:
            raise EvidenceError("UNKNOWN_MODE")
        pages, words = set(plan["pages"]), plan["words"]
        if (not pages or any(type(p) is not int or not 0 <= p < 16 for p in pages)
                or any(type(a) is not int or a % 4 or not 0 <= a <= SIZE - 4
                       or a // PAGE not in pages for a in words)):
            raise EvidenceError("LAYOUT_OUTSIDE_OWNED_REGION")
        if any(self.memory.base + a in self.retired for a in plan["positions"]):
            raise EvidenceError("RETIRED_ADDRESS_REUSE")
        for word in words.values():
            bits(word)
        if mode == "drift":
            if not self.active or pages != self.memory.pages:
                raise EvidenceError("DRIFT_REQUIRES_ACTIVE_REGION")
            self.emit("planned_drift", {"address": self.active[0], "bits": "0x42280000"})
        else:
            if mode == "relocate" and pages & self.memory.pages:
                raise EvidenceError("RELOCATION_REQUIRES_FRESH_PAGE")
            if mode == "relocate":
                self.emit("reallocate", {"old_regions": self.regions,
                    "new_regions": [f"{self.allocation_id}.p{p}" for p in sorted(pages)],
                    "same_process_token": self.instance.token})
            for address in self.active:
                self.retired.add(address)
                self.emit("retire", {"address": address, "permanent": True})
            for page in sorted(self.memory.pages):
                self.emit("decommit", {"region_id": f"{self.allocation_id}.p{page}",
                    "base": self.memory.base + page * PAGE, "size": PAGE})
            self.memory.pages = pages
            self.memory.image[:] = b"\0" * SIZE
            self.regions = [f"{self.allocation_id}.p{p}" for p in sorted(pages)]
            for page in sorted(pages):
                self.emit("commit", {"region_id": f"{self.allocation_id}.p{page}",
                    "base": self.memory.base + page * PAGE, "size": PAGE})
        for offset, word in words.items():
            self.memory.write_word(self.memory.base + offset, word)
        self.active = [self.memory.base + x for x in plan["positions"]]
        self.mode = mode
        return self.emit("mode", {"mode": mode, "active_addresses": self.active,
            "retired_addresses": sorted(self.retired), "active_regions": self.regions,
            "synthetic_match_count": len(self.memory.matches()), "hard_limit": 128})

    def sample(self, address, anchor_id, *, attempt_id=None):
        try:
            value = bits(self.memory.read_word(address))
        except EvidenceError:
            self.emit("checkpoint_missing", {"address": address, "anchor_id": identifier(anchor_id)})
            raise
        return self.emit("checkpoint", {"address": address, "bits": value,
            "anchor_id": identifier(anchor_id), "attempt_id": attempt_id,
            "read_kind": "TARGET_SELF_SAMPLE", "active_regions": self.regions,
            "retired_addresses": sorted(self.retired)})

    def shutdown(self, *, exception=False):
        if exception:
            self.emit("exception", {"reason": "SYNTHETIC_INJECTED_EXCEPTION"})
        self.emit("shutdown", {})
        self.memory.released = True
        self.memory.pages.clear()
        return self.emit("cleanup", {"released": True})


class MockTransport:
    """Sequenced checkpoint request/ack; no network, shell, paths or arbitrary code."""
    def __init__(self, target):
        self.target, self.sequence = target, 0

    def request(self, packet):
        required = {"schema", "session_id", "sequence", "command", "anchor_id", "address"}
        if set(packet) != required or packet["schema"] != 1 or packet["command"] != "checkpoint":
            raise EvidenceError("TRANSPORT_SCHEMA")
        if packet["session_id"] != self.target.stream.session_id or packet["sequence"] != self.sequence + 1:
            raise EvidenceError("TRANSPORT_REPLAY_OR_SESSION")
        row = self.target.sample(packet["address"], packet["anchor_id"])
        self.sequence += 1
        return {"origin": "SYNTHETIC", "request_digest": digest(packet),
                "event_id": row["event_id"], "content_digest": row["content_digest"]}
