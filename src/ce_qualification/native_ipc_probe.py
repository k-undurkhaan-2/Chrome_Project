"""Opt-in offline host coordinator. Native command is unconditionally blocked.

Injected transports are cooperative test fakes. Timing parameters in this file
are model units, never values passed to a CE API. No retries or process controls.
"""
from .native_probe_protocol import Decoder, ProbeError, Session, decode, native_admission, require


class Coordinator:
    def __init__(self, transport, clock_ms, emit, *, session_id="offline", channel_id="fake",
                 epoch=1, enabled=False, mode="offline"):
        require(enabled is True and mode == "offline", "OFFLINE_PROBE_DISABLED")
        self.transport, self.clock, self.emit = transport, clock_ms, emit
        self.session = Session(session_id, channel_id, epoch, clock_ms)
        self.closed, self.busy, self.cancelled = False, False, False
        self.cleanup = "NOT_OBSERVED"

    def _check(self):
        require(not self.cancelled and not self.closed, "CANCELLED")
        require(self.session.now() < self.session.deadline, "REQUEST_TIMEOUT")

    def exchange(self, method, request_id, payload=""):
        if self.busy:
            self.cancel()
            raise ProbeError("REENTRANT_REQUEST")
        self.busy = True
        try:
            require(not self.closed and not self.cancelled, "CANCELLED")
            raw = self.session.begin(method, request_id, payload)
            request = decode(raw[4:])
            sent = 0
            # Bounded progress, no empty-write or implicit reconnection loops.
            while sent < len(raw):
                self._check()
                part = raw[sent:sent + 4096]
                amount = self.transport.send(part)
                require(type(amount) is int and 0 < amount <= min(4096, len(raw) - sent), "SHORT_OR_INVALID_SEND")
                self.emit("TX_CHUNK", request=request, raw=part[:amount])
                self._check()
                sent += amount
            self.emit("TX", request=request, raw=raw)
            decoder = Decoder(self.session.deadline, self.clock)
            received = bytearray()
            for _ in range(65540):
                self._check()
                chunk = self.transport.receive(4096)
                if type(chunk) is bytes and 0 < len(chunk) <= 4096:
                    self.emit("RX_CHUNK", raw=chunk)
                self._check()
                require(type(chunk) is bytes and 0 < len(chunk) <= 4096, "DISCONNECTED_OR_NO_PROGRESS")
                received.extend(chunk)
                response = decoder.feed(chunk)
                if response is not None:
                    self.emit("RX", request=response, raw=bytes(received))
                    accepted = self.session.accept(response)
                    self.emit("ACCEPT", request=accepted, response=accepted["result"])
                    if method in ("CANCEL", "CLOSE"):
                        self.close()
                    return accepted
            raise ProbeError("RECEIVE_BOUND")
        except Exception as exc:
            self.session.invalidate("FAILED")
            try:
                self.emit("REJECT", error=str(exc) if isinstance(exc, ProbeError) else "COMPONENT_FAILURE")
            finally:
                self.close()
            raise
        finally:
            self.busy = False

    def cancel(self):
        self.cancelled = True
        self.session.invalidate("CANCELLED")
        try:
            self.emit("CANCEL", cancel_stage="REQUESTED")
        finally:
            self.close()

    def close(self):
        if self.closed:
            return self.cleanup
        self.closed = True
        self.session.invalidate("CLOSED")
        self.cleanup = "INDETERMINATE"
        try:
            if self.transport.close() is True:
                self.cleanup = "CLOSED"
        except Exception:
            pass
        self.emit("CLOSE", response=self.cleanup, cancel_stage="OBSERVED" if self.cleanup == "CLOSED" else "UNCERTAIN")
        return self.cleanup


class AdapterCoordinator(Coordinator):
    """B0 transport wiring; separate owner/watchdog clocks, synthetic only."""
    def __init__(self, transport, clock_ms, emit, watchdog_clock_ms, watchdog_emit, limits, **kwargs):
        from .native_probe_winpipe import SyntheticServer
        require(isinstance(transport, SyntheticServer), "SYNTHETIC_PROVIDER_REQUIRED")
        super().__init__(transport, clock_ms, emit, **kwargs)
        self.watchdog_clock, self.watchdog_emit, self.limits = watchdog_clock_ms, watchdog_emit, limits
        self.watchdog = None

    def exchange(self, method, request_id, payload=""):
        from .native_probe_watchdog import Watchdog
        if self.busy:
            return super().exchange(method, request_id, payload)
        self.watchdog = Watchdog(self.watchdog_clock, self.watchdog_emit, enabled=True)
        try:
            self.limits.check()
            self.watchdog.arm(request_id)
            self.transport.begin_request(self.session.now() + 250, self.watchdog)
            result = super().exchange(method, request_id, payload)
            self.limits.check()
            if not self.closed:
                self.watchdog.observe_reply()
            else:
                self.watchdog.observe_completion(io_completed=self.transport.pending is None,
                                                 resources_closed=self.transport.cleanup == "CLOSED")
            return result
        except Exception:
            self.watchdog.cancel()
            self.close()
            raise


def activate_offline(raw=None, *, environment=None, provider=None):
    """Explicit P0 test entry; admission completes before any fake is opened."""
    from .native_probe_activation import ActivationBridge
    return ActivationBridge(environment).activate(raw, provider=provider)


def main(argv=None):
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Standalone test-only IPC model; no native backend")
    parser.add_argument("command", choices=("offline", "native"))
    args = parser.parse_args(argv)
    if args.command == "native":
        try:
            native_admission()
            # Defense in depth: no replaced model gate can fall into offline CLI.
            raise ProbeError("R3_B_NOT_AUTHORIZED")
        except ProbeError as exc:
            print(json.dumps({"status": str(exc), "native": "NOT_RUN", "g1_live": "NOT_APPROVED",
                              "activation": "BLOCKED_NATIVE_ACTIVATION_UNPROVEN"}))
            return 3
    # Deterministic in-memory smoke. Full adversarial evidence uses the runbook.
    from .native_probe_protocol import frame, reply_to
    class EchoFake:
        def __init__(self):
            self.request, self.response = bytearray(), b""
            self.decoder = Decoder(250, lambda: 0)

        def send(self, chunk):
            message = self.decoder.feed(chunk)
            if message is not None:
                self.response = frame(reply_to(message))
                self.decoder = Decoder(250, lambda: 0)
            return len(chunk)

        def receive(self, size):
            chunk, self.response = self.response[:size], self.response[size:]
            return chunk

        def close(self):
            return True
    host = Coordinator(EchoFake(), lambda: 0, lambda *_a, **_k: None, enabled=True)
    host.exchange("HELLO", "hello")
    host.exchange("ECHO", "echo", "offline-smoke")
    host.exchange("CLOSE", "close")
    print(json.dumps({"schema": "qsg.native-probe.v1", "origin": "SYNTHETIC", "status": "SYNTHETIC_SMOKE_PASS",
                      "native": "NOT_RUN", "g1_live": "NOT_APPROVED"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
