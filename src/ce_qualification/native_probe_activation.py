"""P0 test-only activation bridge. No OS, filesystem, DLL or process capability.

The injected immutable environment is trusted test equipment, not authentication
of an operator or Windows peer. Native execution is unconditionally unavailable.
"""
from dataclasses import dataclass

from .native_probe_admission import (P0_CAPS, activation_utc, bind_activation_authority,
    bind_activation_candidate, check_activation_technical, parse_activation_record)
from .native_probe_protocol import (Decoder, ProbeError, canonical, frame, reply_to,
                                     require, sha256)
from .native_probe_watchdog import Watchdog


class ReplayRegistry:
    """Injected suite-lifetime tombstones; denial/close never restores authority."""
    def __init__(self):
        self.used, self.cases, self.started = set(), set(), None
        self.evidence_bytes, self.evidence_limit = 0, P0_CAPS["evidence_bytes"]
        self.clock, self.last = None, -1
        self.active = None

    def check_time(self, now, clock):
        require(self.clock is None or self.clock is clock, "P0_SUITE_CLOCK")
        require(now >= self.last, "P0_SUITE_CLOCK")
        self.clock, self.last = clock, now

    def charge(self, size, limit):
        self.evidence_limit = min(self.evidence_limit, limit)
        require(self.evidence_bytes+size <= self.evidence_limit, "P0_EVIDENCE_OVERFLOW")
        self.evidence_bytes += size

    def release(self, owner):
        if self.active is owner: self.active = None

    def consume(self, session, caps, now, clock, owner):
        self.check_time(now, clock)
        require(self.active is None, "P0_SUITE_CONNECTION_ACTIVE")
        keys = {("epoch", session["session_id"], session["epoch"]),
                ("channel", session["channel_id"]), ("nonce", session["nonce"]),
                ("trial", session["session_id"], session["case_id"], session["trial"])}
        require(not self.used.intersection(keys), "P0_ACTIVATION_REPLAY")
        self.used.update(keys)  # failed capacity checks consume the attempted binding
        self.cases.add(session["case_id"])
        require(len(self.cases) <= caps["cases"], "P0_CASE_BUDGET")
        if self.started is None: self.started = now
        self.active = owner


@dataclass(frozen=True)
class OfflineEnvironment:
    """Pins are fixed before untrusted input; no CLI/env-var policy overrides.

    candidate_sha256 is an independently retained harness seal, never a digest
    taken from the approval being checked. It does not install a native policy.
    """
    candidate: bytes
    candidate_sha256: str
    policy: bytes
    technical: bytes
    clock_ms: object
    utc_now: object
    watchdog_clock_ms: object
    registry: ReplayRegistry


_ISSUER = object()


class _OfflinePermit:
    def __init__(self, issuer, bridge):
        require(issuer is _ISSUER, "P0_PERMIT")
        self.bridge, self.used = bridge, False

    def consume(self, provider):
        require(not self.used and self.bridge.state == "TECHNICAL_ADMISSION", "P0_PERMIT")
        self.used = True
        require(type(provider) is FakeProvider, "P0_FAKE_PROVIDER_REQUIRED")
        self.bridge._runtime_check()
        provider._open(self.bridge._runtime_check)
        return provider


class FakeProvider:
    """Finite in-memory echo/fault equipment. No user supplied provider factory.

    Public fault settings are synthetic fault injection, not native overrides.
    Pending completion holds its buffer; requesting cancel does not release it.
    """
    origin = "SYNTHETIC"
    os_evidence = "NOT_PROVEN"

    def __init__(self, *, fault="none", fragment=4096, advance=None):
        require(type(fragment) is int and 1 <= fragment <= 4096, "P0_FRAGMENT")
        require(advance is None or callable(advance), "P0_CLOCK_EQUIPMENT")
        self.fault, self.fragment, self.advance = fault, fragment, advance
        self.open_calls, self.close_calls, self.cancel_calls = 0, 0, 0
        self.calls, self.requests, self.responses = [], [], []
        self.check, self.decoder, self.pending = None, None, None
        self.response, self.previous, self.buffer = b"", b"", b""
        self.closed, self.used = False, False

    def _open(self, check):
        require(not self.used and not self.closed, "P0_PROVIDER_REUSE")
        self.used = True
        self.check = check
        self.open_calls += 1
        self.calls.append("OPEN")

    def send(self, chunk):
        require(self.used and not self.closed, "P0_PROVIDER_CLOSED")
        self.check()
        self.calls.append("WRITE")
        if self.fault == "crash": raise ProbeError("P0_BROKER_CRASH")
        if self.decoder is None: self.decoder = Decoder(250, lambda: 0)
        amount = min(len(chunk), self.fragment)
        self.buffer += chunk[:amount]
        request = self.decoder.feed(chunk[:amount])
        if request is not None:
            self.requests.append(self.buffer)
            response = reply_to(request)
            if self.fault == "epoch": response["epoch"] += 1
            if self.fault == "session": response["session_id"] = "wrong-session"
            if self.fault == "digest": response["request_sha256"] = "0"*64
            self.response = frame(response)
            if self.fault == "replay": self.response = self.previous
            if self.fault == "duplicate": self.response += self.response
            if self.fault == "malformed": self.response = b'\x01\0\0\0\xff'
            self.responses.append(self.response)
            self.previous = self.response
            self.decoder, self.buffer = None, b""
        self.check()
        return amount

    def receive(self, maximum):
        self.check()
        self.calls.append("READ")
        if self.fault in ("late", "slow"):
            require(self.advance is not None, "P0_CLOCK_EQUIPMENT")
            self.advance(250 if self.fault == "late" else 100)
        if self.fault == "pending":
            self.pending, self.buffer = "fake-operation-1", self.response
            raise ProbeError("P0_IO_COMPLETION_UNKNOWN")
        if self.fault == "cancel": raise ProbeError("P0_CANCELLED")
        if self.fault == "disconnect": self.response = b""
        size = min(maximum, self.fragment)
        chunk, self.response = self.response[:size], self.response[size:]
        self.check()
        return chunk

    def close(self):
        if self.closed: return self.fault != "cleanup"
        if self.pending is not None:
            if not self.cancel_calls:
                self.cancel_calls += 1
                self.calls.append("CANCEL_REQUESTED")
            return False
        self.closed = True
        self.close_calls += 1
        self.calls.append("CLOSE")
        return self.fault != "cleanup"

    def observe_completion(self, operation):
        require(self.pending is not None and operation == self.pending, "P0_HANDLE_OWNERSHIP")
        self.pending, self.buffer = None, b""
        return self.close()  # cleanup observation never restores a bridge permit


class ActivationBridge:
    """One attempt, one fake connection, one outstanding request. Default COLD."""
    def __init__(self, environment=None):
        self.environment = environment
        self.state, self.reason = "COLD", ""
        self._record, self._host, self._provider, self._watchdog = None, None, None, None
        self._attempted, self._busy, self._closed_message = False, False, False
        self._events, self._bytes = [], 0
        self._last, self._started, self._request_started = -1, None, None
        self._messages = 0
        self._approval_digest, self._identity_digest = "0"*64, "0"*64
        self._limit = P0_CAPS["evidence_bytes"]

    @property
    def events(self):
        # Return decoded copies; callers cannot rewrite retained evidence.
        from .native_probe_protocol import decode
        return tuple(decode(row) for row in self._events)

    def _event(self, event, **data):
        row = {"schema":"qsg.p0.activation-event.v1", "origin":"SYNTHETIC",
               "os_evidence":"NOT_PROVEN", "native":"NOT_RUN", "state":self.state,
               "event":event, "sequence":len(self._events)+1, "data":data,
               "owner_ms":self._last,
               "request_deadline_ms":None if self._request_started is None else self._request_started+250,
               "approval_sha256":self._approval_digest, "identities_sha256":self._identity_digest,
               "previous_sha256":sha256(self._events[-1]) if self._events else "0"*64}
        raw = canonical(row)
        require(len(self._events) < 8192 and self._bytes+len(raw) <= self._limit, "P0_EVIDENCE_OVERFLOW")
        if type(self.environment) is OfflineEnvironment and type(self.environment.registry) is ReplayRegistry:
            self.environment.registry.charge(len(raw), self._limit)
        self._events.append(raw)
        self._bytes += len(raw)

    def _transition(self, state):
        self.state = state
        self._event("STATE")

    def _now(self):
        n = self.environment.clock_ms()
        require(type(n) is int and n >= 0 and n >= self._last, "P0_OWNER_CLOCK")
        self._last = n
        return n

    def _runtime_check(self):
        require(self.state in ("TECHNICAL_ADMISSION", "RUN_PERMITTED"), "P0_AUTHORITY_REVOKED")
        r, e = self._record, self.environment
        now = self._now()
        e.registry.check_time(now, e.clock_ms)
        require(activation_utc(r["window"]["start"]) <= activation_utc(e.utc_now())
                < activation_utc(r["window"]["end"]), "P0_APPROVAL_EXPIRED")
        require(now-self._started < r["caps"]["case_ms"]
                and now-e.registry.started < r["caps"]["suite_ms"], "P0_TOTAL_DEADLINE")
        if self._request_started is not None:
            require(now-self._request_started < r["caps"]["request_ms"], "REQUEST_TIMEOUT")
        if self._watchdog is not None:
            require(self._watchdog.poll() == "ARMED", "P0_WATCHDOG_CUTOFF")

    def _fail(self, code):
        self.reason = code
        cleanup = "CLOSED"
        if self._host is not None:
            try: cleanup = self._host.close()
            except Exception: cleanup = "INDETERMINATE"
        elif self._provider is not None:
            try: cleanup = "CLOSED" if self._provider.close() is True else "INDETERMINATE"
            except Exception: cleanup = "INDETERMINATE"
        self.state = "DENIED" if cleanup == "CLOSED" else "UNCERTAIN"
        if cleanup == "CLOSED" and type(self.environment) is OfflineEnvironment and type(self.environment.registry) is ReplayRegistry:
            self.environment.registry.release(self)
        try: self._event("REJECT", code=code, cleanup=cleanup)
        except Exception: self.state = "UNCERTAIN"

    def activate(self, raw=None, *, provider=None):
        try:
            require(not self._attempted and self.state == "COLD", "P0_ACTIVATION_REPLAY")
            self._attempted = True
            e = self.environment
            require(type(e) is OfflineEnvironment and type(e.registry) is ReplayRegistry,
                    "P0_OFFLINE_ENVIRONMENT_REQUIRED")
            self._record = parse_activation_record(raw)
            self._approval_digest = sha256(raw)
            self._identity_digest = sha256(canonical(self._record["identities"]))
            self._limit = self._record["caps"]["evidence_bytes"]
            self._transition("CONFIG_PARSED")
            assets = bind_activation_candidate(e.candidate, e.candidate_sha256)
            require(self._record["assets"] == assets
                    and self._record["candidate_sha256"] == e.candidate_sha256, "P0_ASSET_DRIFT")
            self._transition("CANDIDATE_BOUND")
            bind_activation_authority(self._record, raw, e.policy, candidate_sha256=e.candidate_sha256,
                                      assets=assets, now=e.utc_now())
            self._transition("AUTH_BOUND")
            check_activation_technical(e.technical, self._record)
            require(type(provider) is FakeProvider, "P0_FAKE_PROVIDER_REQUIRED")
            self._started = self._now()
            e.registry.consume(self._record["session"], self._record["caps"], self._started, e.clock_ms, self)
            self._transition("TECHNICAL_ADMISSION")
            from .native_probe_winpipe import open_activation_fake
            from .native_ipc_probe import Coordinator
            self._provider = open_activation_fake(_OfflinePermit(_ISSUER, self), provider)
            s = self._record["session"]
            self._host = Coordinator(self._provider, e.clock_ms, self._observe_host, enabled=True,
                session_id=s["session_id"], channel_id=s["channel_id"], epoch=s["epoch"])
            self._transition("RUN_PERMITTED")  # modeled fake permission ONLY
            return self
        except Exception as exc:
            code = str(exc) if isinstance(exc, ProbeError) else "P0_COMPONENT_FAILURE"
            self._fail(code)
            raise ProbeError(code) from None

    def _observe_host(self, kind, **data):
        raw = data.get("raw", b"")
        self._event("HOST_"+kind, bytes=len(raw), sha256=sha256(raw),
                    response=data.get("response", ""))
        if kind in ("TX_CHUNK", "RX_CHUNK", "TX", "RX", "ACCEPT"):
            self._runtime_check()

    def exchange(self, method, request_id, payload="", *, case_id, nonce):
        try:
            require(not self._busy, "P0_OUTSTANDING_REQUEST")
            self._runtime_check()
            s = self._record["session"]
            require(case_id == s["case_id"] and nonce == s["nonce"], "P0_CASE_NONCE")
            require(self._messages < self._record["caps"]["messages"], "P0_MESSAGE_BUDGET")
            self._messages += 1
            self._busy = True
            self._request_started = self._now()
            self._watchdog = Watchdog(self.environment.watchdog_clock_ms,
                                     lambda kind, data: self._event(kind, **data), enabled=True)
            self._watchdog.arm(sha256(request_id.encode("utf-8")))
            result = self._host.exchange(method, request_id, payload)
            self._runtime_check()
            if method == "CLOSE":
                require(self._host.cleanup == "CLOSED", "P0_CLEANUP_UNCERTAIN")
                self._watchdog.observe_completion(io_completed=self._provider.pending is None, resources_closed=True)
                self._closed_message = True
                self._transition("STOPPED")
                self.environment.registry.release(self)
            elif method == "CANCEL":
                raise ProbeError("P0_CANCELLED")
            else:
                self._watchdog.observe_reply()
            self._watchdog = None
            return result
        except Exception as exc:
            code = str(exc) if isinstance(exc, ProbeError) else "P0_COMPONENT_FAILURE"
            self._fail(code)
            raise ProbeError(code) from None
        finally:
            self._busy, self._request_started = False, None

    def stop(self):
        if self.state in ("STOPPED", "DENIED", "UNCERTAIN"): return self.result()
        self._fail("P0_MISSING_CLOSE")
        self.state = "UNCERTAIN"
        try: self._event("STATE")
        except Exception: pass
        return self.result()

    def result(self):
        return {"origin":"SYNTHETIC", "state":self.state, "reason":self.reason,
                "status":"SYNTHETIC_PASS" if self.state == "STOPPED" and self._closed_message else "NOT_PASS",
                "native_activation":"BLOCKED_NATIVE_ACTIVATION_UNPROVEN", "os_evidence":"NOT_PROVEN",
                "native":"NOT_RUN", "g1_live":"NOT_APPROVED"}
