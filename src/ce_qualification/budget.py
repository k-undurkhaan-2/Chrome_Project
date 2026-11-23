"""Synthetic pre-dispatch gate with retained enrollment and a durable journal.

No live authorization parser or CE hook exists. Exclusive ownership is fail-closed:
a crash leaves the lock in place; stale locks are never automatically reclaimed.
fsync + atomic head replacement is tested with injected failures, not certified
against physical Windows power loss. Enrollment/head must be retained separately.
"""
from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import threading
import uuid

from .evidence import (EvidenceError, Stream, SyntheticClock, canonical, decode,
                       digest, encode_rows, file_hash, finite_bits, identifier,
                       read_rows, utc, validate_chain)
from .target import Instance, SIZE


class GateError(EvidenceError):
    pass


def durable_new(path, raw):
    with Path(path).open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def replace_head(path, value):
    temporary = path.with_name(path.name + ".pending")
    # A prior incomplete replacement is evidence of uncertainty, not disposable.
    durable_new(temporary, canonical(value) + b"\n")
    os.replace(temporary, path)


def validate_policy(policy):
    if set(policy) != {"origin", "session_id", "window_start", "window_end", "targets"}:
        raise GateError("POLICY_SCHEMA")
    if policy["origin"] != "SYNTHETIC":
        raise GateError("LIVE_NOT_IMPLEMENTED_OR_APPROVED")
    identifier(policy["session_id"])
    start, end = utc(policy["window_start"]), utc(policy["window_end"])
    if not 0 < (end - start).total_seconds() <= 3600:
        raise GateError("WINDOW_BOUND")
    if not 1 <= len(policy["targets"]) <= 9:
        raise GateError("TARGETS_REQUIRED")
    ids, identities = set(), set()
    for target in policy["targets"]:
        if set(target) != {"identity", "allocation_id", "base", "size", "allowed_scenarios"}:
            raise GateError("TARGET_POLICY_SCHEMA")
        token = Instance(**target["identity"]).token
        identifier(target["allocation_id"])
        if target["allocation_id"] in ids or token in identities:
            raise GateError("DUPLICATE_TARGET")
        ids.add(target["allocation_id"]); identities.add(token)
        scenarios = target["allowed_scenarios"]
        if (not isinstance(scenarios, list) or not scenarios or len(set(scenarios)) != len(scenarios)
                or not set(scenarios) <= {f"L{i:02}" for i in range(1, 13)}
                or (target["identity"]["designation"] == "B" and scenarios != ["L11"])):
            raise GateError("TARGET_SCENARIO_SCOPE")
        if target["size"] != SIZE or type(target["base"]) is not int or target["base"] <= 0 or target["base"] % SIZE:
            raise GateError("REGION_BOUND")


def provision_synthetic(authority_directory, journal_path, policy):
    """One enrollment per retained authority root. Never called by open/reload.

Deleting or replacing the authority root is outside the trusted storage model;
no claim of rollback resistance against an actor controlling all files is made.
"""
    validate_policy(policy)
    authority_directory, journal_path = Path(authority_directory), Path(journal_path).resolve()
    authority_directory.mkdir(parents=True, exist_ok=False)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    enrollment = {"schema": 1, "origin": "SYNTHETIC", "policy": deepcopy(policy),
                  "journal_path": str(journal_path)}
    enrollment_path = authority_directory / "enrollment.json"
    durable_new(enrollment_path, canonical(enrollment) + b"\n")
    stream = Stream(policy["session_id"], "budget")
    stream.emit("enrollment", {"policy_digest": digest(policy), "live": "NOT_APPROVED"})
    durable_new(journal_path, encode_rows(stream.rows))
    durable_new(authority_directory / "head.json", canonical({"sha256": file_hash(journal_path),
        "head": stream.rows[-1]["content_digest"], "records": len(stream.rows),
        "enrollment_sha256": file_hash(enrollment_path)}) + b"\n")
    return file_hash(enrollment_path)


class SessionGate:
    def __init__(self, authority_directory, expected_enrollment_sha256, *, enabled=False, clock=None):
        self.directory = Path(authority_directory)
        self.enabled, self.poisoned, self.closed = enabled, False, False
        self._mutex = threading.Lock()
        self._owner = uuid.uuid4().hex
        self.lock_path = self.directory / "owner.lock"
        try:
            durable_new(self.lock_path, self._owner.encode())
        except OSError as exc:
            raise GateError("SESSION_CONCURRENT_OR_UNRECONCILED") from exc
        try:
            path = self.directory / "enrollment.json"
            if file_hash(path) != expected_enrollment_sha256:
                raise GateError("ENROLLMENT_IDENTITY_CHANGED")
            enrollment = decode(path.read_bytes())
            if enrollment["origin"] != "SYNTHETIC" or enrollment["schema"] != 1:
                raise GateError("LIVE_NOT_IMPLEMENTED_OR_APPROVED")
            self.policy = deepcopy(enrollment["policy"])
            validate_policy(self.policy)
            self.enrollment_sha256 = expected_enrollment_sha256
            self.path = Path(enrollment["journal_path"])
            self.stream = Stream(self.policy["session_id"], "budget", clock)
            self._reconcile()
            # Reload must not reset event clocks. Wall time stays caller-controlled.
            if clock is None:
                last = self.stream.rows[-1]["clock"]
                self.stream.clock = SyntheticClock("budget", offset_ns=last["monotonic_ns"], start=last["utc"])
        except Exception:
            # Leave lock behind: initialization uncertainty needs explicit review.
            self.poisoned = True
            raise

    def _reconcile(self):
        if self.closed or self.poisoned:
            raise GateError("GATE_UNAVAILABLE")
        if self.lock_path.read_text() != self._owner:
            raise GateError("SESSION_OWNERSHIP_LOST")
        if file_hash(self.directory / "enrollment.json") != self.enrollment_sha256:
            raise GateError("ENROLLMENT_IDENTITY_CHANGED")
        if (self.directory / "head.json.pending").exists():
            raise GateError("HEAD_REPLACEMENT_UNCERTAIN")
        head = decode((self.directory / "head.json").read_bytes())
        if head["enrollment_sha256"] != self.enrollment_sha256:
            raise GateError("HEAD_ENROLLMENT_MISMATCH")
        rows = read_rows(self.path, head["sha256"])
        if head["head"] != rows[-1]["content_digest"] or head["records"] != len(rows):
            raise GateError("HEAD_MISMATCH")
        validate_chain(rows, source="budget", session_id=self.policy["session_id"])
        if rows[0]["kind"] != "enrollment" or rows[0]["data"]["policy_digest"] != digest(self.policy):
            raise GateError("POLICY_CHANGED")
        self.stream.rows = rows

    def _emit(self, kind, data, run_id="session", scenario="SESSION"):
        row = self.stream.emit(kind, data, run_id=run_id, scenario=scenario)
        try:
            with self.path.open("ab") as handle:
                handle.write(canonical(row) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            replace_head(self.directory / "head.json", {"sha256": file_hash(self.path),
                "head": row["content_digest"], "records": len(self.stream.rows),
                "enrollment_sha256": self.enrollment_sha256})
        except Exception:
            self.poisoned = True
            raise
        return row

    def _enter(self):
        if not self._mutex.acquire(blocking=False):
            raise GateError("REENTRANT_OR_CONCURRENT_DISPATCH")
        try:
            self._reconcile()
            if not self.enabled:
                raise GateError("GATE_DISABLED")
        except Exception:
            self._mutex.release()
            raise

    def start(self, run_id, scenario, identity, allocation_id):
        self._enter()
        try:
            identifier(run_id); identifier(scenario)
            if scenario not in {f"L{i:02}" for i in range(1, 13)}:
                raise GateError("UNKNOWN_SCENARIO")
            starts = [r for r in self.stream.rows if r["kind"] == "start"]
            if len(starts) >= 9:
                raise GateError("SUCCESSFUL_START_BUDGET_EXHAUSTED")
            stopped = {r["run_id"] for r in self.stream.rows if r["kind"] == "stop"}
            if any(r["run_id"] == run_id for r in starts) or any(r["run_id"] not in stopped for r in starts):
                raise GateError("RUN_REUSED_OR_ACTIVE")
            target = self._target(identity, allocation_id)
            if scenario not in target["allowed_scenarios"]:
                raise GateError("TARGET_SCENARIO_NOT_APPROVED")
            return self._emit("start", {"identity": identity, "allocation_id": allocation_id}, run_id, scenario)
        finally:
            self._mutex.release()

    def stop(self, run_id):
        self._enter()
        try:
            start = self._active(run_id)
            return self._emit("stop", {}, run_id, start["scenario"])
        finally:
            self._mutex.release()

    def retire(self, run_id, address):
        self._enter()
        try:
            start = self._active(run_id)
            target = self._target(**start["data"])
            self._address(target, address)
            return self._emit("retire", {**start["data"], "address": address}, run_id, start["scenario"])
        finally:
            self._mutex.release()

    def _active(self, run_id):
        starts = [r for r in self.stream.rows if r["kind"] == "start" and r["run_id"] == run_id]
        if len(starts) != 1 or any(r["kind"] == "stop" and r["run_id"] == run_id for r in self.stream.rows):
            raise GateError("NO_ACTIVE_RUN")
        return starts[0]

    def _target(self, identity, allocation_id):
        Instance(**identity).record()
        targets = [t for t in self.policy["targets"] if t["identity"] == identity and t["allocation_id"] == allocation_id]
        if len(targets) != 1:
            raise GateError("TARGET_INSTANCE_MISMATCH")
        return targets[0]

    @staticmethod
    def _address(target, address):
        if type(address) is not int or address % 4 or not target["base"] <= address <= target["base"] + SIZE - 4:
            raise GateError("ADDRESS_BOUND_OR_ALIGNMENT")

    def dispatch(self, request, fake_write, *, crash_after_reserve=False):
        """fake_write is test-injected only. No live backend can be selected."""
        self._enter()
        try:
            required = {"run_id", "scenario", "identity", "ce_identity", "allocation_id",
                        "address", "bits", "candidate", "anchor_id", "checkpoint"}
            if set(request) != required:
                raise GateError("REQUEST_SCHEMA")
            run, scenario = request["run_id"], request["scenario"]
            start = self._active(run)
            if scenario not in {"L04", "L07", "L10"}:
                raise GateError("ZERO_WRITE_SCENARIO")
            if start["scenario"] != scenario and not (start["scenario"] == "L04" and scenario == "L07"):
                raise GateError("SCENARIO_SWAP")
            identity, allocation = request["identity"], request["allocation_id"]
            if start["data"] != {"identity": identity, "allocation_id": allocation} or request["ce_identity"] != identity:
                raise GateError("TARGET_SWAP")
            target = self._target(identity, allocation)
            if scenario not in target["allowed_scenarios"] or identity["designation"] != "A":
                raise GateError("TARGET_SCENARIO_NOT_APPROVED")
            self._address(target, request["address"])
            if finite_bits(request["bits"]) != "0x42FA0000":
                raise GateError("UNAPPROVED_WRITE_VALUE")
            identifier(request["anchor_id"])
            checkpoint = request["checkpoint"]
            if (not isinstance(checkpoint, dict) or checkpoint.get("origin") != "SYNTHETIC"
                    or checkpoint.get("schema") != 1 or checkpoint.get("kind") != "checkpoint"
                    or checkpoint.get("source") != "target-A" or checkpoint.get("session_id") != self.policy["session_id"]
                    or checkpoint.get("run_id") != run or checkpoint.get("scenario") != scenario
                    or checkpoint.get("content_digest") != digest({k: v for k, v in checkpoint.items() if k != "content_digest"})):
                raise GateError("PREWRITE_CHECKPOINT_REQUIRED")
            cd = checkpoint["data"]
            if (any(cd.get(k) != request[k] for k in ("identity", "allocation_id", "address", "anchor_id"))
                    or cd.get("bits") != "0x42C80000" or cd.get("read_kind") != "TARGET_SELF_SAMPLE"):
                raise GateError("PREWRITE_CHECKPOINT_MISMATCH")
            candidate = request["candidate"]
            if (set(candidate) != {"raw_count", "qualified_count", "complete", "hard_limit", "structure_valid"}
                    or type(candidate["raw_count"]) is not int or not 1 <= candidate["raw_count"] <= 128
                    or candidate["qualified_count"] != 1 or candidate["complete"] is not True
                    or candidate["hard_limit"] != 128 or candidate["structure_valid"] is not True):
                raise GateError("CANDIDATE_EVIDENCE_REQUIRED")
            for row in self.stream.rows:
                if row["kind"] == "retire" and row["data"]["identity"] == identity and row["data"]["address"] == request["address"]:
                    raise GateError("ADDRESS_RETIRED")
            now = self.stream.clock.sample()
            last = self.stream.rows[-1]["clock"]
            if (now["monotonic_ns"] < last["monotonic_ns"] or utc(now["utc"]) < utc(last["utc"])
                    or not utc(self.policy["window_start"]) <= utc(now["utc"]) < utc(self.policy["window_end"])):
                raise GateError("WINDOW_EXPIRED_OR_CLOCK_UNCERTAIN")
            if (utc(now["utc"]) - utc(start["clock"]["utc"])).total_seconds() >= 300:
                raise GateError("PHASE_WINDOW_EXPIRED")
            reservations = [r for r in self.stream.rows if r["kind"] == "reservation"]
            if any(r["data"]["checkpoint"]["content_digest"] == checkpoint["content_digest"] for r in reservations):
                raise GateError("PREWRITE_CHECKPOINT_REPLAY")
            if any(r["data"]["checkpoint"]["content_digest"] == checkpoint["content_digest"] for r in reservations):
                raise GateError("PREWRITE_CHECKPOINT_REPLAY")
            positive = sum(r["scenario"] in {"L04", "L07"} for r in reservations)
            l10 = sum(r["scenario"] == "L10" for r in reservations)
            if len(reservations) >= 3 or (scenario in {"L04", "L07"} and positive >= 2) or (scenario == "L10" and l10 >= 1):
                raise GateError("WRITE_BUDGET_EXHAUSTED")
            attempt = uuid.uuid4().hex
            reservation = self._emit("reservation", {**deepcopy(request), "attempt_id": attempt,
                "flush": "fsync_returned", "head_update": "atomic_replace_required_before_dispatch"}, run, scenario)
            if crash_after_reserve:
                self.poisoned = True
                raise GateError("SIMULATED_CRASH_RESERVATION_CONSUMED")
            # Durability may take time. Reconcile again and check the dispatch
            # timestamp; an expired reservation remains consumed, never refunded.
            self._reconcile()
            dispatch = self._emit("dispatch", {"attempt_id": attempt, "reservation_digest": reservation["content_digest"]}, run, scenario)
            self._reconcile()
            after_persist = self.stream.clock.sample()
            if (not utc(self.policy["window_start"]) <= utc(after_persist["utc"]) < utc(self.policy["window_end"])
                    or utc(after_persist["utc"]) < utc(dispatch["clock"]["utc"])
                    or after_persist["monotonic_ns"] < dispatch["clock"]["monotonic_ns"]
                    or (utc(after_persist["utc"]) - utc(start["clock"]["utc"])).total_seconds() >= 300):
                self.poisoned = True
                raise GateError("WINDOW_EXPIRED_AFTER_RESERVATION_CONSUMED")
            try:
                result = fake_write(deepcopy(reservation))
            except Exception:
                self._emit("outcome", {"attempt_id": attempt, "result": "INDETERMINATE"}, run, scenario)
                raise
            outcome = "SUCCESS" if result is True else "FAILED" if result is False else "INDETERMINATE"
            self._emit("outcome", {"attempt_id": attempt, "result": outcome}, run, scenario)
            return reservation, outcome
        finally:
            self._mutex.release()

    def close(self):
        if self.closed:
            return
        if not self._mutex.acquire(blocking=False):
            raise GateError("DISPATCH_IN_PROGRESS")
        try:
            if not self.poisoned and self.lock_path.read_text() == self._owner:
                self.lock_path.unlink()
            self.closed = True
        finally:
            self._mutex.release()
