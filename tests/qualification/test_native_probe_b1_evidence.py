import json
import pytest

from ce_qualification.native_probe_protocol import canonical, sha256
from ce_qualification.native_probe_b1_verifier import verify
from native_probe_b1_suite import build


@pytest.fixture(scope="module")
def traces(tmp_path_factory):
    path = tmp_path_factory.mktemp("b1-traces") / "traces.json"
    seal = build(path, "c" * 64, "a" * 64)
    return path, seal


def test_independent_provider_replay(traces):
    path, seal = traces
    result = verify(path, seal, "c" * 64, "a" * 64)
    assert result["status"] == "SYNTHETIC_PASS", result
    assert set(result["native"].values()) == set(result["live"].values()) == {"NOT_RUN"}


@pytest.mark.parametrize("mutation", ["native", "os_call", "chain", "session", "epoch", "clock", "cross_actor", "count", "cancel", "cleanup", "late", "identity", "watchdog", "anchor"])
def test_independent_replay_rejects_forged_or_missing_evidence(traces, tmp_path, mutation):
    source, _ = traces; bundle = json.loads(source.read_bytes()); session = bundle["sessions"][20]
    events = session["events"]
    if mutation == "native": events[0]["origin"] = "native"
    elif mutation == "os_call": events[0]["os_observed"] = True
    elif mutation == "chain": events.pop(1)
    elif mutation == "session": session["binding"]["session_id"] = "stale"
    elif mutation == "epoch": session["binding"]["epoch"] = 1
    elif mutation == "clock": events[-1]["at_ms"] = -1
    elif mutation == "cross_actor": events[-1]["clock_id"] = "external-watchdog-model"
    elif mutation == "count": events[2]["data"]["count"] = 1
    elif mutation == "cancel": events[:] = [r for r in events if r["event"] != "CANCEL_REQUEST"]
    elif mutation == "cleanup": events.pop()
    elif mutation == "late": events[-2]["data"]["status"] = "COMPLETE"
    elif mutation == "identity": events[3]["data"]["server_identity"] = "PASS"
    elif mutation == "watchdog": session["watchdog"]["cutoff_observed_ms"] = 2000
    # Re-seal all altered records to test semantics beyond hashes.
    for n, row in enumerate(events, 1):
        row.update(sequence=n, previous_sha256=events[n-2]["sha256"] if n > 1 else "0" * 64)
        row["sha256"] = sha256(canonical({k: v for k, v in row.items() if k != "sha256"}))
    raw = canonical(bundle); path = tmp_path / "mutated.json"; path.write_bytes(raw)
    result = verify(path, "0" * 64 if mutation == "anchor" else sha256(raw), "c" * 64, "a" * 64)
    assert result["status"] == "SYNTHETIC_FAIL", result
