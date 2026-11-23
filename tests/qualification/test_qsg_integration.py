"""Synthetic only. No native target imported, launched or attached."""
from copy import deepcopy
import pytest

from qsg_support import Model, table
from ce_qualification.evidence import digest
from ce_qualification.qsg_verifier import verify


@pytest.mark.parametrize("backend", ["lua53", "lua54"])
def test_initial_and_recovery_use_real_guarded_port(tmp_path, backend):
    m = Model(tmp_path, backend)
    m.positive()
    assert len(m.raw_calls) == len(m.broker.events("reserve")) == len(m.broker.events("claim")) == 2
    assert [x["reserves"] for x in m.raw_calls] == [1, 2]
    assert [x["claims"] for x in m.raw_calls] == [1, 2]
    assert m.raw_calls[0]["address"] != m.raw_calls[1]["address"]
    assert len(m.broker.events("monitor")) == 23
    m.stop()
    bundle=m.bundle()
    checked=verify(bundle,digest(bundle),requested=["L04","L05","L06","L07"])
    assert checked["status"] == "SYNTHETIC_PASS", checked
    m.close()


def test_public_loader_start_stop_latches_and_preserves_cleanup_probes(tmp_path):
    m = Model(tmp_path, phase="L10")
    m.w.cfg.diagnostics.cleanup_start_probe = True
    assert m.start(loader=True) == (True, None)
    m.until("MONITORING")
    assert m.api.start() == (False, "ALREADY_RUNNING")
    assert m.api.configure_execution(table(m.lua, {"mode": "NORMAL"})) == (False, "QSG_MODE_LOCKED")
    m.stop()
    events = m.api.evidence().events
    assert any(e.event_type == "cleanup_start_probe" and e.reason == "CLEANUP_IN_PROGRESS" for e in events.values())
    m.w.step(100)
    assert len(m.raw_calls) == 1
    m.close()
