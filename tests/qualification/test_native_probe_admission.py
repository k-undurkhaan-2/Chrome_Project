"""R3-B0 approval, startup, resource and activation negatives; mocks only."""
from copy import deepcopy
import pytest

from ce_qualification.native_probe_admission import evaluate_model, require_native_activation
from ce_qualification.native_probe_protocol import ProbeError, canonical
from ce_qualification.native_probe_winpipe import NativeProvider, open_native, terminate_native_process
from native_probe_b0_fakes import NOW, approval_fixture


def test_N01_model_is_never_native_authority():
    record, expected, observations, verifier = approval_fixture()
    result = evaluate_model(canonical(record), expected, observations, verifier, now=NOW, case_id="N01")
    assert result["status"] == "SYNTHETIC_ADMISSION_ONLY"
    assert result["native_activation"] == "BLOCKED_NATIVE_ACTIVATION_UNPROVEN"
    calls = []
    with pytest.raises(ProbeError, match="BLOCKED_NATIVE_ACTIVATION_UNPROVEN"):
        open_native(record, provider_factory=lambda: calls.append("native"))
    assert calls == []


@pytest.mark.parametrize("field", ["manifest", "patch", "source", "probe", "ce_exe", "ce_dll"])
def test_N01_every_frozen_identity_must_match(field):
    record, expected, observations, verifier = approval_fixture()
    record["freeze"][field] = "0" * 64
    with pytest.raises(ProbeError, match="FREEZE_MISMATCH"):
        evaluate_model(canonical(record), expected, observations, verifier, now=NOW, case_id="N01")


@pytest.mark.parametrize("mutation", ["missing", "approved", "native", "signature", "verifier", "expiry", "timezone",
    "case", "retries", "zero_bool", "cap_bool", "unbounded", "isolation", "file_listing", "directory", "watchdog", "target",
    "helper", "principal", "window", "vector", "duplicate_case", "unknown", "host", "path"])
def test_N01_N02_N08_admission_denies_before_any_provider(mutation):
    r, e, o, v = approval_fixture(); now, case = NOW, "N01"
    if mutation == "missing": del r["signature"]
    elif mutation == "approved": r["approved"] = True
    elif mutation == "native": r["origin"] = "NATIVE"
    elif mutation == "signature": r["signature"]["value"] = "forged"
    elif mutation == "verifier": v = None
    elif mutation == "expiry": now = r["window"]["end"]
    elif mutation == "timezone": r["window"]["start"] = "2026-11-20T12:00:00"
    elif mutation == "case": case = "L01"
    elif mutation == "retries": r["zero"]["automatic_retries"] = 1
    elif mutation == "zero_bool": r["zero"]["target_read"] = False
    elif mutation == "cap_bool": r["caps"]["servers"] = True
    elif mutation == "unbounded": r["caps"]["repetitions"] = 0
    elif mutation == "isolation": r["isolation"]["autorun"] = "UNKNOWN"
    elif mutation == "file_listing": r["isolation"]["method"] = "FILES_ENUMERATED"
    elif mutation == "directory": o["evidence_fresh"] = False
    elif mutation == "watchdog": o["watchdog_independent"] = False
    elif mutation == "target": o["target_absent"] = False
    elif mutation == "helper": r["cleanup"]["helpers"] = ["unapproved"]
    elif mutation == "principal": r["cleanup"]["principal_negatives"] = ["other-user"]
    elif mutation == "window": r["window"]["end"] = "2026-11-20T13:00:00+00:00"
    elif mutation == "vector": r["vectors"]["N01"] = []
    elif mutation == "duplicate_case": r["cases"].append("N01")
    elif mutation == "unknown": r["freeze"]["extra"] = "0" * 64
    elif mutation == "host": r["host"] = "wrong-host"
    elif mutation == "path": r["evidence_dir"] = e["evidence_dir"] = "D:\\evidence\\..\\other"
    with pytest.raises(ProbeError): evaluate_model(canonical(r), e, o, v, now=now, case_id=case)


@pytest.mark.parametrize("raw", [b"", b"null", b"{}", b"{", b"x" * 65537], ids=["empty", "null", "object", "truncated", "oversize"])
def test_N08_invalid_approval_document(raw):
    _, e, o, v = approval_fixture()
    with pytest.raises(ProbeError): evaluate_model(raw, e, o, v, now=NOW, case_id="N01")


@pytest.mark.parametrize("method", ["create", "start_io", "poll_io", "query_connection", "challenge", "cancel_io", "close"])
def test_N02_all_native_provider_operations_stay_closed(method):
    with pytest.raises(ProbeError, match="BLOCKED_NATIVE_ACTIVATION_UNPROVEN"):
        getattr(NativeProvider(), method)(approved=True, origin="SYNTHETIC")


def test_N06_native_process_control_is_never_authorized_by_mock():
    for action in (require_native_activation, terminate_native_process):
        with pytest.raises(ProbeError, match="BLOCKED_NATIVE_ACTIVATION_UNPROVEN"):
            action({"approved": True, "terminate": True, "pid": 101})
