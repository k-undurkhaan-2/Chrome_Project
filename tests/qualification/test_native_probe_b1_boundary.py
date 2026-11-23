import ctypes as C
import pytest

from ce_qualification.native_probe_protocol import ProbeError
from native_probe_b1_boundary import boundary_measurements
from native_probe_b1_fakes import equipment


def test_exact_byte_boundaries_and_path_independent_layer_detection(tmp_path):
    rows = boundary_measurements(tmp_path)
    assert len(rows) == 6
    for row in rows:
        size = row["payload_utf8_bytes"]
        assert row["transport_body_bytes"] == size and row["framed_bytes"] == size + 4
        assert row["serialized_envelope_bytes"] > size
        assert row["evidence_result"] == ("PAYLOAD_BOUND" if size > 65536 else "ACCEPTED")
        assert row["transport_result"] == ("FRAME_LENGTH" if size > 65536 else "ACCEPTED")
        assert not row["oversize_header_body_allocated"]


@pytest.mark.parametrize("size", [0, 4097, 65537, 2 ** 32])
def test_oversize_winapi_buffer_rejected_before_allocation_or_io(size, monkeypatch):
    p, f, h = equipment(); before = list(f.calls)
    monkeypatch.setattr(C, "create_string_buffer", lambda *_: pytest.fail("allocated oversize buffer"))
    with pytest.raises(ProbeError): p.start_io(h, "read", "READ", maximum=size, deadline_ms=250)
    assert f.calls == before
    p.close()
