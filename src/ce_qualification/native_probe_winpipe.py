"""Injected host-server adapter for reviewed Win32 byte-pipe operations.

NativeProvider implements the Win32 function-table backend with a closed native
loader and injected virtual APIs for B1. SyntheticServer accepts trusted
in-memory test equipment only, not arbitrary untrusted provider implementations.
"""
from copy import deepcopy
import re

from .native_probe_admission import exact, require_native_activation
from .native_probe_peer import CLIENT_ACCESS, SERVER_ACCESS, validate_connection_model, verify_mutual_model
from .native_probe_protocol import ProbeError, canonical, require, sha256
from .native_probe_win32 import Win32Provider

PIPE_ACCESS_DUPLEX = 0x00000003
FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
FILE_FLAG_OVERLAPPED = 0x40000000
PIPE_REJECT_REMOTE_CLIENTS = 0x00000008


def pipe_spec(endpoint, expected):
    require(type(endpoint) is str and re.fullmatch(r"\\\\\.\\pipe\\qsg-r3-[0-9a-f]{32}", endpoint), "LOCAL_ENDPOINT")
    client, server = expected["client"]["sid"], expected["server"]["sid"]
    # Explicit DACL, no default descriptor, inheritance, Everyone or anonymous ACE.
    return {"endpoint": endpoint, "open_mode": PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE | FILE_FLAG_OVERLAPPED,
            "pipe_mode": PIPE_REJECT_REMOTE_CLIENTS,  # BYTE / READMODE_BYTE / WAIT are zero.
            "max_instances": 1, "input_bytes": 4096, "output_bytes": 4096,
            "inheritable": False, "client_access": CLIENT_ACCESS,
            "sddl": f"O:{server}D:P(A;;0x{SERVER_ACCESS:x};;;{server})(A;;0x{CLIENT_ACCESS:x};;;{client})"}


class NativeProvider(Win32Provider):
    """Actual Win32 implementation; default instance is inert and denied.

    B1 can exercise the implementation only with a trusted synthetic WinAPI table.
    Native DLL loading, client-handle proof and runtime secret provisioning remain
    blocked. A model result never grants the public native entry authority.
    """
    # Gate before even argument binding in the implementation: fake flags cannot
    # enter a default provider. Injected equipment delegates to the actual body.
    def create(self, *args, **kwargs):
        self._access(); return super().create(*args, **kwargs)
    def start_io(self, *args, **kwargs):
        self._access(); return super().start_io(*args, **kwargs)
    def poll_io(self, *args, **kwargs):
        self._access(); return super().poll_io(*args, **kwargs)
    def cancel_io(self, *args, **kwargs):
        self._access(); return super().cancel_io(*args, **kwargs)
    def query_connection(self, *args, **kwargs):
        self._access(); return super().query_connection(*args, **kwargs)
    def challenge(self, *args, **kwargs):
        self._access(); return super().challenge(*args, **kwargs)
    def close(self, *args, **kwargs):
        self._access(); return super().close(*args, **kwargs)
    # Gate before even argument binding in the implementation: fake flags cannot
    # enter a default provider. Injected equipment delegates to the actual body.
    def create(self, *args, **kwargs):
        self._access(); return super().create(*args, **kwargs)
    def start_io(self, *args, **kwargs):
        self._access(); return super().start_io(*args, **kwargs)
    def poll_io(self, *args, **kwargs):
        self._access(); return super().poll_io(*args, **kwargs)
    def cancel_io(self, *args, **kwargs):
        self._access(); return super().cancel_io(*args, **kwargs)
    def query_connection(self, *args, **kwargs):
        self._access(); return super().query_connection(*args, **kwargs)
    def challenge(self, *args, **kwargs):
        self._access(); return super().challenge(*args, **kwargs)
    def close(self, *args, **kwargs):
        self._access(); return super().close(*args, **kwargs)


def open_native(record=None, *, provider_factory=NativeProvider):
    # Sole future activation seam. Admission currently ALWAYS raises, including
    # valid-looking records or injected verifiers. Factory is never invoked.
    require_native_activation(record)
    # A patched/injected model admission callback still cannot dispatch native.
    raise ProbeError("BLOCKED_NATIVE_ACTIVATION_UNPROVEN")


def open_activation_fake(permit, provider):
    """P0 has no native factory fallback, flags, DLL loader or duck-typed provider."""
    from .native_probe_activation import _OfflinePermit, FakeProvider
    require(type(permit) is _OfflinePermit and type(provider) is FakeProvider, "P0_FAKE_PROVIDER_REQUIRED")
    return permit.consume(provider)


class EpochRegistry:
    """Session-lifetime tombstones; close never frees a name/channel/epoch."""
    def __init__(self):
        self.endpoints, self.channels, self.epochs = set(), set(), set()

    def consume(self, endpoint, binding):
        channel = (binding["session_id"], binding["channel_id"])
        epoch = (binding["session_id"], binding["epoch"])
        require(endpoint not in self.endpoints and channel not in self.channels and epoch not in self.epochs, "EPOCH_REPLAY")
        self.endpoints.add(endpoint); self.channels.add(channel); self.epochs.add(epoch)


class SyntheticServer:
    """One server, one operation, bounded cooperative polling, no retry.

    An operation result has status/count/data/operation. PENDING is not a zero-byte
    completion; buffers and operation identity remain held until completion is
    observed. A cancellation request never certifies that buffers can be freed.
    """
    origin = "SYNTHETIC"

    def __init__(self, provider, clock_ms, emit, expected, registry, *, secret, challenges, allow_model_cancel=False):
        require(getattr(provider, "origin", None) == "SYNTHETIC", "SYNTHETIC_PROVIDER_REQUIRED")
        require(type(allow_model_cancel) is bool, "CANCEL_SCOPE")
        self.provider, self.clock, self.emit = provider, clock_ms, emit
        self.expected, self.registry = deepcopy(expected), registry
        require(type(secret) is bytes and len(secret) >= 32, "SECRET")
        self.secret, self.challenges = secret, deepcopy(challenges)
        self.allow_cancel = allow_model_cancel
        self.handle, self.pending, self.deadline, self.watchdog = None, None, None, None
        self.closed, self.revoked, self.ready, self.busy = False, False, False, False
        self.cleanup, self.last, self.ordinal = "NOT_OBSERVED", -1, 0
        self.proof_digest = None

    def _event(self, kind, **data):
        self.emit({"origin": "SYNTHETIC", "kind": kind, "connection_id": self.expected["connection_id"], **data})

    def _check(self):
        require(not self.closed and not self.revoked, "TRANSPORT_REVOKED")
        now = self.clock()
        require(type(now) is int and now >= 0 and now >= self.last, "CLOCK_REVERSED")
        self.last = now
        require(type(self.deadline) is int and now < self.deadline, "REQUEST_TIMEOUT")
        if self.watchdog is not None:
            require(self.watchdog.poll() == "ARMED", "WATCHDOG_CUTOFF")

    def open(self, endpoint, *, deadline_ms):
        require(self.handle is None and not self.closed and not self.revoked, "SERVER_ALREADY_USED")
        self.deadline = deadline_ms
        try:
            self._check()
            spec = pipe_spec(endpoint, self.expected)
            self.registry.consume(endpoint, self.expected)
            self.handle = self.provider.create(spec)
            require(type(self.handle) is str and re.fullmatch(r"model-handle-[A-Za-z0-9-]+", self.handle), "INVALID_HANDLE")
            self._event("CREATE", spec_sha256=sha256(canonical(spec)))
            self._io("CONNECT", b"", 0)
            proof = self.provider.query_connection(self.handle)
            result = validate_connection_model(proof, self.expected, handle_ref=self.handle)
            self.proof_digest = result["proof_sha256"]
            replies = self.provider.challenge(self.expected, self.proof_digest, self.challenges)
            verify_mutual_model(self.secret, self.expected, self.proof_digest, self.challenges, replies)
            self._check()
            self.ready = True
            self._event("PEER_BOUND", proof_sha256=self.proof_digest)
            return self
        except Exception:
            self.revoked = True
            self.close()
            raise

    def begin_request(self, deadline_ms, watchdog):
        require(self.ready and not self.busy and self.pending is None, "TRANSPORT_NOT_READY")
        require(type(deadline_ms) is int and 0 < deadline_ms - self.clock() <= 250, "REQUEST_BOUND")
        self.deadline, self.watchdog = deadline_ms, watchdog
        self._check()

    def _io(self, direction, data, maximum):
        if self.busy or self.pending is not None:
            self.revoked = True
            raise ProbeError("IO_OVERLAP")
        self.busy = True
        try:
            self._check()
            self.ordinal += 1
            operation = f"op-{self.ordinal}"
            # Retain data before calling the provider (also on exception/uncertainty).
            self.pending = {"operation": operation, "direction": direction, "data": data}
            result = self.provider.start_io(self.handle, operation, direction, data, maximum)
            for _ in range(128):
                exact(result, {"operation", "status", "count", "data"}, "IO_RESULT")
                require(result["operation"] == operation, "IO_OPERATION_BINDING")
                require(type(result["count"]) is int and type(result["data"]) is bytes, "IO_RESULT")
                if result["status"] == "PENDING":
                    require(result["count"] == 0 and result["data"] == b"", "PENDING_NOT_COMPLETED")
                    self._check()
                    result = self.provider.poll_io(self.handle, operation)
                    continue
                require(result["status"] in ("COMPLETE", "ABORTED", "FAILED"), "IO_STATUS")
                self.pending = None  # terminal completion observed, including failure
                require(result["status"] == "COMPLETE", "IO_FAILED")
                count, raw = result["count"], result["data"]
                if direction == "READ": require(0 < count <= maximum and len(raw) == count, "READ_COUNT")
                elif direction == "WRITE": require(0 < count <= len(data) and raw == b"", "WRITE_COUNT")
                else: require(count == 0 and raw == b"", "CONNECT_RESULT")
                transferred = raw if direction == "READ" else data[:count]
                # Preserve actual completion counts/digests even when the
                # following deadline/cancel check forbids accepting the reply.
                self._event(direction, operation=operation, returned_bytes=count, sha256=sha256(transferred))
                self._check()
                return raw if direction == "READ" else count
            raise ProbeError("IO_POLL_BOUND")
        except Exception:
            self.revoked = True
            # A cancel callback may already have closed the Coordinator while
            # this operation was pending. Finish local cleanup after a terminal
            # result; otherwise retain the operation for observe_cleanup().
            try:
                self.close()
            except Exception:
                pass
            raise
        finally:
            self.busy = False

    def _peer(self):
        require(self.ready, "PEER_NOT_BOUND")
        self._check()
        result = validate_connection_model(self.provider.query_connection(self.handle), self.expected, handle_ref=self.handle)
        require(result["proof_sha256"] == self.proof_digest, "PEER_CHANGED")

    def send(self, chunk):
        try:
            self._peer()
            require(type(chunk) is bytes and 1 <= len(chunk) <= 4096, "WRITE_BOUND")
            return self._io("WRITE", chunk, len(chunk))
        except Exception:
            self.revoked = True
            raise

    def receive(self, maximum):
        try:
            self._peer()
            require(type(maximum) is int and 1 <= maximum <= 4096, "READ_BOUND")
            return self._io("READ", b"", maximum)
        except Exception:
            self.revoked = True
            raise

    def close(self):
        if self.closed: return self.cleanup == "CLOSED"
        self.revoked, self.ready = True, False
        self.secret = None
        self.cleanup = "UNCERTAIN"
        if self.pending is not None:
            if self.allow_cancel:
                try:
                    self.provider.cancel_io(self.handle, self.pending["operation"])
                    self._event("CANCEL_REQUESTED", operation=self.pending["operation"])
                except Exception:
                    pass
                self.allow_cancel = False  # never repeat a possibly successful request
            return False  # do not free an OVERLAPPED/buffer or close its handle yet
        try:
            if self.handle is None or self.provider.close(self.handle) is True:
                self.cleanup = "CLOSED"
        except Exception:
            pass
        self.closed = True
        self._event("CLEANUP", result=self.cleanup)
        return self.cleanup == "CLOSED"

    def observe_cleanup(self):
        """External owner tick, no wait. A late result can only finish cleanup."""
        require(self.revoked, "CLEANUP_NOT_REQUESTED")
        if self.pending is not None:
            try:
                result = self.provider.poll_io(self.handle, self.pending["operation"])
                exact(result, {"operation", "status", "count", "data"}, "IO_RESULT")
                if result["operation"] != self.pending["operation"] or result["status"] not in ("COMPLETE", "ABORTED", "FAILED"):
                    return "UNCERTAIN"
                self.pending = None
            except Exception:
                return "UNCERTAIN"
        self.close()
        return self.cleanup


def terminate_native_process(*_args, **_kwargs):
    require_native_activation()  # no process-control capability in R3-B0
