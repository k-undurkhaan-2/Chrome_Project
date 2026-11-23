"""Test-only layer analysis; never changes QSG-R2 serializers or payload caps."""
from pathlib import Path

from ce_qualification.evidence import Stream, EvidenceError, canonical as evidence_json
from ce_qualification.native_probe_protocol import Decoder, ProbeError, canonical, frame
from native_probe_suite import packet


def boundary_measurements(base):
    rows = []
    for label, path in (("short", str(Path(base).resolve() / "p")),
                        ("long", str(Path(base).resolve() / ("long-path-" * 10) / "配置🙂"))):
        for length in (65535, 65536, 65537):
            data = {"path": path, "payload": ""}
            data["payload"] = "x" * (length - len(evidence_json(data)))
            stream = Stream("b1-boundary", "observer")
            try:
                record = stream.emit("boundary", data); status = "ACCEPTED"
            except EvidenceError as exc:
                assert str(exc) == "PAYLOAD_BOUND"; status = str(exc)
                tb = exc.__traceback__; record = None
                while tb:
                    if tb.tb_frame.f_code.co_name == "validate_chain": record = tb.tb_frame.f_locals["row"]
                    tb = tb.tb_next
                assert not stream.rows and record is not None
            request = packet(method="ECHO", payload=path)
            request["payload"] += "x" * (length - len(canonical(request)))
            raw_body = canonical(request)
            try:
                wire = frame(request); transport = "ACCEPTED"
                assert len(wire) == length + 4
            except ProbeError as exc:
                assert str(exc) == "FRAME_LENGTH"; transport = str(exc)
            decoder = Decoder(250, lambda: 0)
            if length == 65537:
                try: decoder.feed(length.to_bytes(4, "little"))
                except ProbeError as exc: assert str(exc) == "FRAME_LENGTH" and len(decoder.body) == 0
                else: raise AssertionError("oversize header allocated a body")
            rows.append({"path_case": label, "absolute_path": path, "path_characters": len(path),
                "path_utf8_bytes": len(path.encode("utf-8")), "payload_utf8_bytes": len(evidence_json(data)),
                "serialized_envelope_bytes": len(evidence_json(record)), "evidence_result": status,
                "transport_body_bytes": len(raw_body), "framed_bytes": length + 4, "transport_result": transport,
                "oversize_header_body_allocated": False})
    return rows


def reproduce_legacy(directory):
    from qsg_session import FullSession
    directory = Path(directory).resolve(); directory.mkdir(parents=True, exist_ok=False)
    session = FullSession(directory)
    result = {"path": str(directory), "path_characters": len(str(directory)),
              "path_utf8_bytes": len(str(directory).encode("utf-8")), "source_changes": []}
    captured = None
    try:
        bundle = session.execute(); result["status"] = "SYNTHETIC_PASS"
        captured = next(row for row in bundle["ce"] if row["scenario"] == "L12-MISSING" and row["kind"] == "config_rejected")
    except EvidenceError as exc:
        result.update(status="BLOCKED_LONG_PATH_FIX_OUT_OF_SCOPE", exception=str(exc))
        tb = exc.__traceback__
        while tb:
            if tb.tb_frame.f_code.co_name == "validate_chain":
                captured = tb.tb_frame.f_locals["row"]
                result.update(kind=captured["kind"], scenario=captured["scenario"],
                    payload_utf8_bytes=len(evidence_json(captured["data"])),
                    serialized_envelope_bytes=len(evidence_json(captured)),
                    field_utf8_bytes={k: len(evidence_json(v)) for k, v in captured["data"].items()})
            tb = tb.tb_next
        assert str(exc) == "PAYLOAD_BOUND" and result["payload_utf8_bytes"] > 65536
    finally:
        session.close()
    if captured is not None:
        result.update(kind=captured["kind"], scenario=captured["scenario"],
            payload_utf8_bytes=len(evidence_json(captured["data"])),
            serialized_envelope_bytes=len(evidence_json(captured)),
            diagnostic=captured["data"]["diagnostic"],
            field_utf8_bytes={k: len(evidence_json(v)) for k, v in captured["data"].items()})
    return result, captured
