"""Independent replay, schema, loss and tampering checks on isolated copies."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from ce_qualification.native_ipc_probe import Coordinator
from ce_qualification.native_probe_evidence import Recorder
from ce_qualification.native_probe_protocol import ProbeError, canonical, decode, sha256
from ce_qualification.native_probe_schema import validate_event
from ce_qualification.native_probe_verifier import verify, main
from native_probe_fakes import Clock, LuaTransport, ROOT
from native_probe_suite import PLAN, build

CANDIDATE, AUTH = "c" * 64, "a" * 64


@pytest.fixture(scope="module")
def evidence(tmp_path_factory):
    path = tmp_path_factory.mktemp("probe-matrix") / "pristine"
    seal, observations = build(path, CANDIDATE, AUTH)
    return path, seal, observations


def replay(path, seal=None, **overrides):
    args = dict(manifest_path=path / "evidence.json", manifest_sha256=seal or sha256((path / "evidence.json").read_bytes()),
                plan_path=PLAN, plan_sha256=sha256(PLAN.read_bytes()), candidate_sha256=CANDIDATE, authorization_sha256=AUTH)
    args.update(overrides)
    return verify(**args)


def altered_copy(evidence, tmp_path):
    path = tmp_path / "tampered-test-copy"
    shutil.copytree(evidence[0], path)
    return path


def reseal(path, actor, rows):
    previous = "0" * 64
    for n, row in enumerate(rows, 1):
        row.update(sequence=n, event_id=f"{actor}:{n}", previous_sha256=previous)
        row["content_sha256"] = sha256(canonical({k: v for k, v in row.items() if k != "content_sha256"}))
        previous = row["content_sha256"]
    raw = b"".join(canonical(r) + b"\n" for r in rows)
    filename = actor.lower() + ".jsonl"
    (path / filename).write_bytes(raw)
    m = decode((path / "evidence.json").read_bytes())
    entry = next(e for e in m["streams"] if e["actor"] == actor)
    entry.update(raw_sha256=sha256(raw), event_count=len(rows), terminal_sequence=len(rows), terminal_head=previous)
    (path / "evidence.json").write_bytes(canonical(m))


def rows_for(path, actor):
    return [decode(line) for line in (path / (actor.lower() + ".jsonl")).read_bytes().splitlines()]


def test_N01_N09_independent_full_matrix(evidence):
    path, seal, observations = evidence
    result = replay(path, seal)
    assert result["status"] == "SYNTHETIC_PASS", result
    assert result["cleanup_cycles"] == 20 and result["exchanges"] == 46
    assert set(result["native"].values()) == set(result["g1_live"].values()) == {"NOT_RUN"}
    expected = json.loads(PLAN.read_text())["checks"]
    assert observations == {(c, k): v for c, checks in expected.items() for k, v in checks.items()}


@pytest.mark.parametrize("actor", ["HOST", "LUA_MODEL", "WATCHDOG", "OBSERVER"])
def test_N09_missing_actor_is_indeterminate(evidence, tmp_path, actor):
    path = altered_copy(evidence, tmp_path)
    (path / (actor.lower() + ".jsonl")).unlink()
    result = replay(path)
    assert result["status"] == "SYNTHETIC_INDETERMINATE", result


def test_N09_missing_terminal_even_rehashed_is_indeterminate(evidence, tmp_path):
    path = altered_copy(evidence, tmp_path)
    rows = rows_for(path, "OBSERVER")[:-1]
    reseal(path, "OBSERVER", rows)
    result = replay(path)
    assert result["status"] == "SYNTHETIC_INDETERMINATE"


def test_N09_missing_check_even_rehashed_is_indeterminate(evidence, tmp_path):
    path = altered_copy(evidence, tmp_path)
    rows = rows_for(path, "OBSERVER")[1:]
    reseal(path, "OBSERVER", rows)
    assert replay(path)["status"] == "SYNTHETIC_INDETERMINATE"


def test_N09_worker_cleanup_witness_is_required(evidence, tmp_path):
    path = altered_copy(evidence, tmp_path)
    rows = rows_for(path, "LUA_MODEL")
    del rows[next(i for i, r in enumerate(rows) if r["kind"] == "CLOSE")]
    reseal(path, "LUA_MODEL", rows)
    assert replay(path)["status"] == "SYNTHETIC_INDETERMINATE"


def test_N06_cutoff_cannot_be_relabelled_completed(evidence, tmp_path):
    path = altered_copy(evidence, tmp_path)
    rows = rows_for(path, "WATCHDOG")
    row = next(r for r in rows if r["kind"] == "CLEANUP_OBSERVED")
    row["data"] = {"io_completed": True, "resources_closed": True, "state": "COMPLETE"}
    reseal(path, "WATCHDOG", rows)
    assert replay(path)["status"] == "SYNTHETIC_FAIL"


def test_N05_hash_chain_without_watchdog_observations_is_not_complete(evidence, tmp_path):
    path = altered_copy(evidence, tmp_path)
    rows = rows_for(path, "WATCHDOG")[-1:]
    reseal(path, "WATCHDOG", rows)
    assert replay(path)["status"] == "SYNTHETIC_INDETERMINATE"


@pytest.mark.parametrize("edit", ["origin", "candidate", "authorization", "time", "clock", "trial", "unknown", "false_observation", "duplicate_check"])
def test_N08_rehashed_contradictions_still_fail(evidence, tmp_path, edit):
    path = altered_copy(evidence, tmp_path)
    rows = rows_for(path, "OBSERVER")
    if edit == "origin": rows[0]["origin"] = "NATIVE"
    elif edit == "candidate": rows[0]["candidate_sha256"] = "f" * 64
    elif edit == "authorization": rows[0]["authorization_sha256"] = "f" * 64
    elif edit == "time": rows[0]["utc"] = "2026-11-20T00:00:00"
    elif edit == "clock": rows[1]["elapsed_ms"] = 0
    elif edit == "trial": rows[0]["trial_id"] = "another-trial"
    elif edit == "unknown": rows[0]["data"]["authenticated"] = True
    elif edit == "false_observation": rows[0]["data"]["observed"] = False
    elif edit == "duplicate_check": rows.insert(1, deepcopy(rows[0]))
    reseal(path, "OBSERVER", rows)
    result = replay(path)
    assert result["status"] == "SYNTHETIC_FAIL", result


@pytest.mark.parametrize("edit", ["length", "digest", "missing_chunk", "duplicate_frame", "accept_after_close", "late_response", "wrong_case"])
def test_N04_frame_replay_detects_forgery(evidence, tmp_path, edit):
    path = altered_copy(evidence, tmp_path)
    rows = rows_for(path, "HOST")
    index = next(i for i, r in enumerate(rows) if r["kind"] == "RX")
    if edit == "length": rows[index]["frame_length"] -= 1
    elif edit == "digest": rows[index]["frame_sha256"] = "f" * 64
    elif edit == "missing_chunk": del rows[next(i for i, r in enumerate(rows) if r["kind"] == "RX_CHUNK")]
    elif edit == "duplicate_frame": rows.insert(index + 1, deepcopy(rows[index]))
    elif edit == "accept_after_close": rows[index]["kind"] = "CLOSE"; rows[index]["data"] = {}; rows[index]["frame_length"] = 0; rows[index]["frame_sha256"] = ""
    elif edit == "late_response":
        for row in rows[index:]: row["elapsed_ms"] += 250
    elif edit == "wrong_case": rows[index]["case_id"] = "N08"
    reseal(path, "HOST", rows)
    assert replay(path)["status"] == "SYNTHETIC_FAIL"


def test_N08_changed_external_anchor_or_log_fails(evidence, tmp_path):
    path = altered_copy(evidence, tmp_path)
    assert replay(path, "0" * 64)["status"] == "SYNTHETIC_FAIL"
    (path / "host.jsonl").write_bytes((path / "host.jsonl").read_bytes() + b"\n")
    assert replay(path)["status"] == "SYNTHETIC_FAIL"


def test_N08_rejects_manifest_path_traversal(evidence, tmp_path):
    path = altered_copy(evidence, tmp_path)
    m = decode((path / "evidence.json").read_bytes()); m["streams"][0]["file"] = "../host.jsonl"
    (path / "evidence.json").write_bytes(canonical(m))
    assert replay(path)["status"] == "SYNTHETIC_FAIL"


def recorder(**kwargs):
    return Recorder("OBSERVER", CANDIDATE, AUTH, Clock(), lambda: "2026-11-20T00:00:00+00:00", enabled=True, **kwargs)


def test_N09_recorder_bounds_poisoning_and_exclusive_export(tmp_path):
    r = recorder(max_events=1)
    r.append("N01", "CHECK", data={"check_id": "one", "observed": True})
    with pytest.raises(ProbeError, match="RECORDER_FULL"): r.finish()
    with pytest.raises(ProbeError, match="UNSEALED_STREAM"): r.export(tmp_path)
    r = recorder(); r.finish(); r.export(tmp_path)
    with pytest.raises(FileExistsError): r.export(tmp_path)
    with pytest.raises(ProbeError, match="RECORDER_CLOSED"): r.append("N01", "CHECK")


def test_N09_sink_failure_closes_host_without_fallback():
    t = LuaTransport({"session_id": "offline", "channel_id": "fake", "epoch": 1})
    def unavailable(*_a, **_kw): raise OSError("test evidence sink unavailable")
    h = Coordinator(t, Clock(), unavailable, enabled=True)
    with pytest.raises(OSError): h.exchange("HELLO", "hello")
    assert h.closed and t.resources == 0
    before = t.sent_bytes
    with pytest.raises(OSError): h.exchange("PING", "retry")
    assert t.sent_bytes == before


@pytest.mark.parametrize("mutation", ["extra", "bool_sequence", "bad_digest", "unknown_payload", "oversize"])
def test_N08_json_schema_rejects_invalid_records(mutation):
    r = recorder(); r.append("N01", "CHECK", data={"check_id": "one", "observed": True})
    row = r.rows[0]
    if mutation == "extra": row["secret"] = "not-allowed"
    elif mutation == "bool_sequence": row["sequence"] = True
    elif mutation == "bad_digest": row["content_sha256"] = "bad"
    elif mutation == "unknown_payload": row["data"]["code"] = "arbitrary"
    elif mutation == "oversize": row["data"]["check_id"] = "x" * 1000
    with pytest.raises(ProbeError): validate_event(row, r.schema)


def test_N09_cli_replay_exit_semantics(evidence, capsys):
    path, seal, _ = evidence
    args = ["--manifest", str(path / "evidence.json"), "--manifest-sha256", seal,
            "--plan", str(PLAN), "--plan-sha256", sha256(PLAN.read_bytes()),
            "--candidate-sha256", CANDIDATE, "--authorization-sha256", AUTH]
    assert main(args) == 0
    assert '"N09": "NOT_RUN"' in capsys.readouterr().out
    args[3] = "0" * 64
    assert main(args) == 1
