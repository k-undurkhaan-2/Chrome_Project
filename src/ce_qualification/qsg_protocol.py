"""Versioned bounded mock RPC, including byte framing; no native pipe backend.

All deadlines are absolute milliseconds in one synthetic host clock domain.
Native peer attestation, DACLs and CE timeout units remain NOT_RUN. The mock's
peer object is supplied by its test host, never taken from a request body.
"""
from copy import deepcopy
import struct

from .evidence import canonical, decode, digest
from .qsg_store import require, QSGError


def frame(value):
    raw = canonical(value)
    require(1 <= len(raw) <= 65536, "QSG_FRAME_LENGTH")
    return struct.pack("<I", len(raw)) + raw


class Decoder:
    def __init__(self, deadline_ms, clock_ms):
        self.deadline, self.clock = deadline_ms, clock_ms
        self.raw, self.done = bytearray(), False

    def feed(self, chunk, *, final=False):
        require(not self.done and self.clock() < self.deadline, "QSG_FRAME_LATE_OR_DUPLICATE")
        require(isinstance(chunk, bytes) and len(self.raw)+len(chunk) <= 65540, "QSG_FRAME_LENGTH")
        self.raw.extend(chunk)
        if len(self.raw) < 4:
            require(not final, "QSG_FRAME_TRUNCATED")
            return None
        length = struct.unpack_from("<I", self.raw)[0]
        require(1 <= length <= 65536 and len(self.raw) <= length+4, "QSG_FRAME_LENGTH")
        if len(self.raw) < length+4:
            require(not final, "QSG_FRAME_TRUNCATED")
            return None
        self.done = True
        value = decode(bytes(self.raw[4:]).decode("utf-8", errors="strict"))
        require(canonical(value) == bytes(self.raw[4:]), "QSG_FRAME_NONCANONICAL")
        return value


class MockChannel:
    version = "qsg.mock.v1"

    def __init__(self, broker, peer, *, epoch="mock-channel-1", hook=None):
        require(peer == broker.policy["peer"], "QSG_PEER_UNTRUSTED")
        self.broker, self.peer, self.epoch = broker, deepcopy(peer), epoch
        self.clock = broker.clock_ms
        self.sequence, self.received_sequence, self.closed = 0, 0, False
        self.hook = hook or (lambda stage, packet: None)

    def dispatch(self, kind, body):
        b = self.broker
        if kind == "begin": return b.begin(body)
        if kind == "reserve": return b.reserve(body)
        if kind == "ready":
            require(set(body) == {"lease"}, "QSG_REQUEST_SCHEMA")
            with b.store.exclusive(): b._phase(body["lease"])
            return {"receipt_kind": "READ_ONLY"}
        methods = {"claim": b.claim, "outcome": b.outcome, "verified": b.verified, "retire": b.retire,
                   "monitor": b.monitor, "phase": b.phase, "end": b.end}
        require(kind in methods, "QSG_MESSAGE_TYPE")
        return methods[kind](**body)

    def request(self, kind, body, deadline_ms):
        require(not self.closed, "QSG_CHANNEL_CLOSED")
        now = self.clock()
        require(type(deadline_ms) is int and now < deadline_ms <= now+250, "QSG_RPC_DEADLINE")
        self.sequence += 1
        packet = {"schema": "qsg.rpc.v1", "origin": "SYNTHETIC", "session_id": self.broker.policy["session_id"],
            "policy_digest": digest(self.broker.policy), "epoch": self.epoch, "sequence": str(self.sequence),
            "message_type": kind, "deadline_ms": str(deadline_ms), "body": deepcopy(body)}
        try:
            self.hook("before_request", packet)
            request = Decoder(deadline_ms, self.clock).feed(frame(packet), final=True)
            require(request == packet, "QSG_REQUEST_MISMATCH")
            require(set(request) == {"schema", "origin", "session_id", "policy_digest", "epoch", "sequence", "message_type", "deadline_ms", "body"}
                and request["schema"] == "qsg.rpc.v1" and request["origin"] == "SYNTHETIC"
                and request["session_id"] == self.broker.policy["session_id"] and request["policy_digest"] == digest(self.broker.policy)
                and request["epoch"] == self.epoch and request["sequence"] == str(self.received_sequence+1)
                and request["message_type"] == kind and request["deadline_ms"] == str(deadline_ms), "QSG_ENVELOPE")
            self.received_sequence += 1
            self.hook("before_dispatch", request)
            require(not self.closed and self.clock() < deadline_ms, "QSG_CANCELLED_OR_TIMEOUT")
            reply_body = self.dispatch(kind, request["body"])
            self.hook("after_dispatch", request)
            reply = {"schema": "qsg.rpc.v1", "origin": "SYNTHETIC", "session_id": packet["session_id"],
                "policy_digest": packet["policy_digest"], "epoch": self.epoch, "sequence": str(self.sequence),
                "message_type": kind + ".ACK", "request_digest": digest(packet), "body": reply_body}
            self.hook("response", reply)
            response = Decoder(deadline_ms, self.clock).feed(frame(reply), final=True)
            require(not self.closed and self.clock() < deadline_ms, "QSG_CANCELLED_OR_TIMEOUT")
            require(set(response) == {"schema", "origin", "session_id", "policy_digest", "epoch", "sequence", "message_type", "request_digest", "body"}
                and all(response[k] == packet[k] for k in ("schema", "origin", "session_id", "policy_digest", "epoch", "sequence"))
                and response["message_type"] == kind+".ACK" and response["request_digest"] == digest(packet), "QSG_ACK_MISMATCH")
            return response["body"]
        except Exception:
            self.closed = True
            self.broker.abort("QSG_CHANNEL_UNCERTAIN")
            raise

    def cancel(self):
        self.closed = True
        self.broker.abort("QSG_CANCELLED")
