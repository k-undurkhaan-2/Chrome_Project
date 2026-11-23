"""Persistent, split reserve/claim broker for the QSG synthetic protocol.

No writer callback is accepted here. A reservation permanently spends a slot;
a claim permanently spends its dispatch right. Repeated requests never replay a
grant. Existing G1 infrastructure remains unchanged.
"""
from copy import deepcopy
import re

from .evidence import digest, finite_bits, identifier, decode
from .target import Instance
from .qsg_store import Store, QSGError, require

PHASES = {f"L{i:02}" for i in range(1, 13)} | {"L12-MISSING", "L12-DISABLED", "L12-INVALID"}
PHASES |= {"L09-zero", "L09-ambiguous", "L09-129_plus", "L09-incomplete", "L09-invalid"}
POSITIVE = ["L02", "L03", "L04", "L05", "L06", "L07", "L08"]
PROVENANCE = {"image_sha256", "script_sha256", "layout_sha256", "provider_sha256"}


def sha(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "QSG_HASH")


def number(value):
    require(isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]{0,15}", value), "QSG_INTEGER_STRING")
    return int(value)


def validate_policy(p):
    require(set(p) == {"origin", "authorization_id", "session_id", "approval_sha256", "candidate_sha256",
        "peer", "start_ms", "end_ms", "targets"}, "QSG_POLICY_SCHEMA")
    require(p["origin"] == "SYNTHETIC", "QSG_LIVE_NOT_IMPLEMENTED")
    identifier(p["authorization_id"]); identifier(p["session_id"])
    sha(p["approval_sha256"]); sha(p["candidate_sha256"])
    require(set(p["peer"]) == {"pid", "creation", "image_sha256", "component_sha256", "channel"}, "QSG_PEER")
    require(type(p["peer"]["pid"]) is int and p["peer"]["pid"] > 0, "QSG_PEER")
    require(re.fullmatch(r"[0-9A-F]{16}", p["peer"]["creation"]) and int(p["peer"]["creation"], 16) > 0, "QSG_PEER")
    sha(p["peer"]["image_sha256"]); sha(p["peer"]["component_sha256"])
    identifier(p["peer"]["channel"])
    require(0 < number(p["end_ms"]) - number(p["start_ms"]) <= 3600000, "QSG_WINDOW")
    require(isinstance(p["targets"], list) and 1 <= len(p["targets"]) <= 9, "QSG_TARGET_LIMIT")
    seen, allocations = set(), set()
    for target in p["targets"]:
        require(set(target) == {"identity", "provenance", "allocation_id", "generation", "base", "size", "owned", "fresh", "phases"}, "QSG_SCOPE_SCHEMA")
        token = Instance(**target["identity"]).token
        require(token not in seen and target["allocation_id"] not in allocations, "QSG_TARGET_DUPLICATE")
        seen.add(token); allocations.add(identifier(target["allocation_id"]))
        require(set(target["provenance"]) == PROVENANCE, "QSG_PROVENANCE")
        for value in target["provenance"].values(): sha(value)
        base = number(target["base"])
        require(0x10000 <= base <= 0x7FFFFFFE0000 and base % 65536 == 0 and target["size"] == "65536"
                and type(target["generation"]) is int and target["generation"] > 0
                and target["owned"] is True and target["fresh"] is True, "QSG_ALLOCATION")
        require(isinstance(target["phases"], list) and bool(target["phases"]) and set(target["phases"]) <= PHASES, "QSG_PHASE")
        if target["identity"]["designation"] == "B": require(target["phases"] == ["L11"], "QSG_TARGET_B")


class Broker:
    @staticmethod
    def provision(directory, policy):
        validate_policy(policy)
        return Store.provision(directory, policy)

    def __init__(self, directory, seal, *, clock_ms, peer, enabled=False, fault=None):
        require(enabled is True, "QSG_DISABLED")
        self.store = Store(directory, seal, clock_ms, fault)
        try:
            self.policy = deepcopy(self.store.enrollment["policy"])
            validate_policy(self.policy)
            require(peer == self.policy["peer"], "QSG_PEER_UNTRUSTED")
        except Exception:
            self.store.poisoned = True
            self.store.close()
            raise
        self.clock_ms = clock_ms

    def events(self, kind):
        return [r for r in self.store.rows if r["kind"] == kind]

    def _window(self):
        now = self.clock_ms()
        require(type(now) is int and number(self.policy["start_ms"]) <= now < number(self.policy["end_ms"]), "QSG_EXPIRED")
        require(not self.store.rows or now >= self.store.rows[-1]["clock_ms"], "QSG_CLOCK")
        require(not self.events("failed"), "QSG_FAILED_CLOSED")
        return now

    def _run(self, lease):
        require(isinstance(lease,dict) and set(lease)=={'run_id','writer_id','epoch','target','generation'}, 'QSG_LEASE_SCHEMA')
        require(type(lease['generation']) is int and lease['generation']>0 and type(lease['target']) is int and lease['target']>=0, 'QSG_LEASE_SCHEMA')
        for key in ('run_id','writer_id','epoch'): identifier(lease[key])
        self._window()
        starts = self.events("start")
        stopped = {r["data"]["run_id"] for r in self.events("stop")}
        active = [r for r in starts if r["data"]["run_id"] not in stopped]
        require(len(active) == 1 and active[0]["data"]["lease"] == lease, "QSG_GENERATION_REVOKED")
        return active[0]

    def _phase(self, lease):
        self._run(lease)
        phases = [r for r in self.events("phase") if r["data"]["lease"] == lease]
        require(bool(phases), "QSG_PHASE_REQUIRED")
        phase = phases[-1]
        require(self.clock_ms() - phase["clock_ms"] < 300000, "QSG_PHASE_EXPIRED")
        return phase

    def begin(self, request):
        with self.store.exclusive():
            self._window()
            require(set(request) == {"run_id", "writer_id", "epoch", "target", "phase"}, "QSG_START_SCHEMA")
            for k in ("run_id", "writer_id", "epoch"): identifier(request[k])
            starts = self.events("start"); stopped = {r["data"]["run_id"] for r in self.events("stop")}
            require(len(starts) < 9, "QSG_START_CAP")
            require(all(r["data"]["run_id"] in stopped for r in starts), "QSG_RUN_ACTIVE")
            require(not any(r["data"]["run_id"] == request["run_id"] or r["data"]["lease"]["epoch"] == request["epoch"] for r in starts), "QSG_REPLAY")
            require(type(request["target"]) is int and 0 <= request["target"] < len(self.policy["targets"]), "QSG_TARGET")
            scope = self.policy["targets"][request["target"]]
            require(request["phase"] in scope["phases"] and request["phase"] != "L07", "QSG_PHASE_SEQUENCE")
            lease = {k: request[k] for k in ("run_id", "writer_id", "epoch", "target")}
            lease["generation"] = len(starts) + 1
            self.store.append("start", {"run_id": request["run_id"], "lease": lease})
            self.store.append("phase", {"lease": lease, "phase": request["phase"], "phase_sequence": 1})
            return {"lease": lease, "scope": deepcopy(scope), "phase": request["phase"], "phase_sequence": 1,
                    "session_id": self.policy["session_id"], "policy_digest": digest(self.policy)}

    def phase(self, lease, phase, expected):
        with self.store.exclusive():
            old = self._phase(lease)
            require(type(expected) is int and old["data"]["phase_sequence"] == expected, "QSG_PHASE_SEQUENCE")
            prior = old["data"]["phase"]
            require(prior in POSITIVE[:-1] and phase == POSITIVE[POSITIVE.index(prior)+1], "QSG_PHASE_SEQUENCE")
            require(phase in self.policy["targets"][lease["target"]]["phases"], "QSG_PHASE")
            pending = {r["digest"] for r in self.events("reserve")} - {r["data"]["attempt"] for r in self.events("verified")}
            require(not pending, "QSG_OUTCOME_UNRESOLVED")
            # Boundary evidence is supplied by the supervisor before this call.
            if prior in {"L05", "L06"}:
                observations = [r for r in self.events("monitor") if r["data"]["lease"] == lease and r["data"]["phase"] == prior]
                require(len(observations) >= (20 if prior == "L05" else 3), "QSG_MONITOR_MINIMUM")
            row = self.store.append("phase", {"lease": lease, "phase": phase, "phase_sequence": expected+1})
            return row["data"]

    def retire(self, lease, address, target_event, core_sequence):
        with self.store.exclusive():
            target_event = decode(target_event)
            self._phase(lease)
            scope = self.policy["targets"][lease["target"]]
            require(type(core_sequence) is int and core_sequence > 0, "QSG_RETIRE_CORE")
            require(target_event.get("kind") == "retire" and target_event.get("origin") == "SYNTHETIC"
                and target_event["data"]["identity"] == scope["identity"] and target_event["data"]["allocation_id"] == scope["allocation_id"]
                and target_event["data"]["address"] == number(address), "QSG_RETIRE_TARGET")
            require(target_event["content_digest"] == digest({k:v for k,v in target_event.items() if k != "content_digest"}), "QSG_RETIRE_DIGEST")
            return self.store.append("retire", {"lease": lease, "address": address, "allocation_id": scope["allocation_id"],
                "target_digest": target_event["content_digest"], "core_sequence": core_sequence})

    def monitor(self, lease, phase, sequence, bits, counters):
        with self.store.exclusive():
            current = self._phase(lease)["data"]
            require(current["phase"] == phase and phase in {"L05", "L06"}, "QSG_MONITOR_PHASE")
            require(type(sequence) is int and sequence > 0 and finite_bits(bits), "QSG_MONITOR")
            require(set(counters) == {"monitor_checks", "valid_monitor_checks", "scan_count", "write_count", "verified_writes"}
                and all(type(v) is int and v >= 0 for v in counters.values()), "QSG_MONITOR_COUNTER")
            if phase == "L06": require(bits == "0x42280000", "QSG_DRIFT_BITS")
            prior = [r["data"] for r in self.events("monitor") if r["data"]["lease"] == lease and r["data"]["phase"] == phase]
            if prior:
                p = prior[-1]
                require(sequence > p["sequence"] and all(counters[k] == p["counters"][k] + (1 if k in {"monitor_checks", "valid_monitor_checks"} else 0) for k in counters), "QSG_MONITOR_DISCONTINUITY")
            return self.store.append("monitor", {"lease": lease, "phase": phase, "sequence": sequence, "bits": bits, "counters": counters})

    def _scope(self, request):
        require(set(request) == {"schema", "session_id", "authorization_id", "lease", "phase", "phase_sequence",
            "operation_id", "nonce", "deadline_ms", "scope", "address", "offset", "bits", "candidate", "checkpoint", "ce_token"}, "QSG_REQUEST_SCHEMA")
        require(request["schema"] == "qsg.write.v1" and request["session_id"] == self.policy["session_id"]
            and request["authorization_id"] == self.policy["authorization_id"], "QSG_SESSION")
        phase = self._phase(request["lease"])["data"]
        require(type(request['phase_sequence']) is int and request["phase"] == phase["phase"] and request["phase_sequence"] == phase["phase_sequence"], "QSG_PHASE_SEQUENCE")
        require(request["phase"] in {"L04", "L07", "L10"}, "QSG_ZERO_PHASE")
        scope = self.policy["targets"][request["lease"]["target"]]
        require(request["scope"] == scope and scope["identity"]["designation"] == "A", "QSG_SCOPE_CHANGED")
        require(request["ce_token"] == Instance(**scope["identity"]).token, "QSG_IDENTITY")
        address = number(request["address"]); base = number(scope["base"])
        require(32 <= address-base <= 65536-84 and address % 4 == 0 and number(request["offset"]) == address-base, "QSG_RANGE_ALIGNMENT")
        require(request["bits"] == "0x42FA0000", "QSG_BITS")
        now = self.clock_ms(); deadline = number(request["deadline_ms"])
        require(now < deadline <= now + 1000, "QSG_DEADLINE")
        number(request["operation_id"]); identifier(request["nonce"])
        candidate = request["candidate"]
        require(set(candidate) == {"address", "mapping", "fields", "rank_sequence", "population_sequence", "intent_sequence",
            "raw_count", "scanned_count", "filtered_count", "selected_count", "qualified_count", "hard_pass", "recommendation", "alias"}, "QSG_CANDIDATE_SCHEMA")
        require(all(type(candidate[k]) is int for k in ('address','rank_sequence','population_sequence','intent_sequence',
            'raw_count','scanned_count','filtered_count','selected_count','qualified_count')), 'QSG_CANDIDATE_TYPES')
        require(candidate["address"] == address and isinstance(candidate["mapping"], str) and candidate["mapping"]
            and set(candidate["fields"]) == {"f08", "f18", "f20", "f58", "f68", "f70", "f78"}
            and all(type(x) is int for x in candidate["fields"].values()), "QSG_CANDIDATE")
        require(type(candidate["raw_count"]) is int and 1 <= candidate["raw_count"] <= 128
            and candidate["scanned_count"] == candidate["raw_count"] and candidate["filtered_count"] == candidate["selected_count"]
            and candidate["qualified_count"] == 1 and candidate["hard_pass"] is True and candidate["recommendation"] == "ACCEPT"
            and 0 < candidate["population_sequence"] < candidate["rank_sequence"] < candidate["intent_sequence"], "QSG_CANDIDATE")
        cp = decode(request["checkpoint"])
        require(cp.get("origin") == "SYNTHETIC" and cp.get("kind") == "checkpoint" and cp.get("source") == "target-A"
            and cp["session_id"] == self.policy["session_id"] and cp["run_id"] == request["lease"]["run_id"] and cp["scenario"] == request["phase"]
            and cp["content_digest"] == digest({k:v for k,v in cp.items() if k != "content_digest"}), "QSG_CHECKPOINT")
        d = cp["data"]
        require(d["identity"] == scope["identity"] and d["allocation_id"] == scope["allocation_id"] and d["address"] == address
            and d["bits"] == "0x42C80000" and d["read_kind"] == "TARGET_SELF_SAMPLE" and d["anchor_id"] == request["nonce"]
            and address not in d["retired_addresses"], "QSG_CHECKPOINT_BINDING")
        require(not any(r["data"]["allocation_id"] == scope["allocation_id"] and r["data"]["address"] == request["address"] for r in self.events("retire")), "QSG_RETIRED")
        if request["phase"] == "L07":
            old = [r for r in self.events("reserve") if r["data"]["phase"] == "L04" and r["data"]["lease"] == request["lease"]]
            require(len(old) == 1 and old[0]["data"]["address"] != request["address"] and any(r["data"]["lease"] == request["lease"] and r["data"]["address"] == old[0]["data"]["address"] for r in self.events("retire")), "QSG_RECOVERY_RETIREMENT")

    def reserve(self, request):
        with self.store.exclusive():
            self._scope(request)
            prior = self.events("reserve")
            require(not any(r["data"]["nonce"] == request["nonce"] or decode(r["data"]["checkpoint"])["content_digest"] == decode(request["checkpoint"])["content_digest"] for r in prior), "QSG_REPLAY")
            require(number(request["operation_id"]) > max([number(r["data"]["operation_id"]) for r in prior] or [0]), "QSG_OPERATION_REPLAY")
            require(len(prior) < 3 and sum(r["data"]["phase"] in {"L04", "L07"} for r in prior) <= 2, "QSG_CAP")
            require(not any(r["data"]["phase"] == request["phase"] for r in prior), "QSG_STEP_CAP")
            row = self.store.append("reserve", request)
            self._window()
            require(self.clock_ms() < number(request["deadline_ms"]), "QSG_EXPIRED_AFTER_RESERVE")
            return {"attempt": row["digest"], "request_digest": digest(request), "receipt_kind": "RESERVATION"}

    def claim(self, attempt, request_digest, lease):
        with self.store.exclusive():
            self._run(lease)
            matches = [r for r in self.events("reserve") if r["digest"] == attempt]
            require(len(matches) == 1, "QSG_UNRESERVED")
            r = matches[0]
            require(r["data"]["lease"] == lease and digest(r["data"]) == request_digest, "QSG_CLAIM_BINDING")
            self._scope(r["data"])
            require(not any(x["data"]["attempt"] == attempt for x in self.events("claim")), "QSG_REPLAY")
            expires = min(number(r["data"]["deadline_ms"]), self.clock_ms() + 100)
            row = self.store.append("claim", {"attempt": attempt, "request_digest": request_digest, "lease": lease, "expires_ms": str(expires)})
            require(self.clock_ms() < expires, "QSG_EXPIRED_AFTER_CLAIM")
            return {**row["data"], "receipt": row["digest"], "receipt_kind": "DISPATCH"}

    def outcome(self, attempt, result, event_digest):
        with self.store.exclusive():
            require(result in {"TRUE", "FALSE", "NONBOOLEAN", "EXCEPTION"}, "QSG_OUTCOME")
            sha(event_digest)
            require(any(r["data"]["attempt"] == attempt for r in self.events("claim")), "QSG_UNCLAIMED")
            prior = [r for r in self.events("outcome") if r["data"]["attempt"] == attempt]
            value = {"attempt": attempt, "result": result, "event_digest": event_digest}
            if prior:
                require(prior[0]["data"] == value, "QSG_OUTCOME_CONFLICT")
                return {"receipt_kind": "READ_ONLY"}
            self.store.append("outcome", value)
            return {"receipt_kind": "READ_ONLY"}

    def verified(self, attempt, evidence_digest):
        with self.store.exclusive():
            require(any(r["data"]["attempt"] == attempt and r["data"]["result"] == "TRUE" for r in self.events("outcome")), "QSG_OUTCOME_REQUIRED")
            require(not any(r["data"]["attempt"] == attempt for r in self.events("verified")), "QSG_REPLAY")
            sha(evidence_digest)
            return self.store.append("verified", {"attempt": attempt, "evidence_digest": evidence_digest})

    def end(self, lease, clean):
        with self.store.exclusive():
            if any(r["data"]["run_id"] == lease["run_id"] for r in self.events("stop")): return
            require(any(r["data"]["lease"] == lease for r in self.events("start")), "QSG_GENERATION_REVOKED")
            self.store.append("stop", {"run_id": lease["run_id"], "lease": lease, "clean": clean is True})
            reserved = {r["digest"] for r in self.events("reserve")}
            verified = {r["data"]["attempt"] for r in self.events("verified")}
            if clean is not True or reserved != verified: self.store.append("failed", {"code": "QSG_UNRESOLVED_OR_UNCLEAN"})

    def close(self):
        self.store.close()

    def abort(self, code):
        # Best effort persistence; local channel/writer are already cancelled.
        # A broken store retains its owner lock and never grants further work.
        try:
            with self.store.exclusive():
                if not self.events("failed"):
                    self.store.append("failed", {"code": code})
        except Exception:
            self.store.poisoned = True
