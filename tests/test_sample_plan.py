import json
from pathlib import Path

from armedforces_tool.sample_plan import analyze_retest_queue, analyze_sample_plan


def _write_summary(root: Path, batch_id: str, fixture_name: str, replacements: dict[str, str]) -> None:
    text = (Path(__file__).parent / "fixtures" / fixture_name).read_text(encoding="utf-8")
    for old, new in replacements.items():
        text = text.replace(old, new)
    (root / f"{batch_id}__summary.txt").write_text(text, encoding="utf-8")


def _write_active_session(path: Path, session_id: str = "session_test") -> None:
    path.write_text(
        json.dumps(
            {
                "session_id": session_id,
                "status": "active",
                "started_at_utc": "2999-01-01T00:00:00Z",
                "process_tracking_enabled": False,
            }
        ),
        encoding="utf-8",
    )


def test_retest_queue_priority_sorting(tmp_path: Path) -> None:
    _write_summary(tmp_path, "20260614-000003", "sample_summary_stale_known_true.txt", {})
    _write_summary(
        tmp_path,
        "20260614-000002",
        "sample_summary_success.txt",
        {
            "0xABC061C7D48": "0xBBB061C7D48",
            "baseline_eligible = true": "baseline_eligible = false",
        },
    )
    _write_summary(tmp_path, "20260614-000001", "sample_summary_success.txt", {"0xABC061C7D48": "0xAAA061C7D48"})

    result = analyze_retest_queue(log_root=tmp_path, latest=10, profile="full", target_unique=3, limit=10)

    assert [record.priority for record in result.records] == ["HIGH", "MEDIUM", "BLOCKED"]
    assert result.records[0].known_true_addr == "0xAAA061C7D48"
    assert result.records[0].missing_clean_full_runs == 1
    assert result.records[-1].known_true_addr == "0x111061C7D48"
    assert result.queue_size == 3


def test_sample_plan_no_active_session_behavior(tmp_path: Path) -> None:
    _write_summary(tmp_path, "20260614-000001", "sample_summary_success.txt", {"0xABC061C7D48": "0xAAA061C7D48"})

    result = analyze_sample_plan(
        log_root=tmp_path,
        latest=10,
        profile="full",
        target_unique=2,
        limit=5,
        active_session=True,
        active_session_path=tmp_path / "active_test_session.local.json",
        case_intake_path=tmp_path / "case_intake.local.jsonl",
    )

    assert result.conclusion == "SAMPLE_PLAN_NO_ACTIVE_SESSION"
    assert result.active_session_detected is False
    assert all(record.plan_type != "active_session_reuse" for record in result.records)
    assert all("prepare-current-case" not in record.command_hint for record in result.records)


def test_active_session_reuse_is_current_session_only(tmp_path: Path) -> None:
    session_path = tmp_path / "active_test_session.local.json"
    intake_path = tmp_path / "case_intake.local.jsonl"
    _write_active_session(session_path, session_id="session_current")
    intake_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_type": "prepared",
                        "intake_id": "intake_current",
                        "session_id": "session_current",
                        "known_true_addr": "0xBBB061C7D48",
                        "profile": "full",
                    }
                ),
                json.dumps(
                    {
                        "event_type": "prepared",
                        "intake_id": "intake_old",
                        "session_id": "session_old",
                        "known_true_addr": "0xAAA061C7D48",
                        "profile": "full",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    _write_summary(tmp_path, "20260614-000002", "sample_summary_success.txt", {"0xABC061C7D48": "0xBBB061C7D48"})
    _write_summary(tmp_path, "20260614-000001", "sample_summary_success.txt", {"0xABC061C7D48": "0xAAA061C7D48"})

    result = analyze_sample_plan(
        log_root=tmp_path,
        latest=10,
        profile="full",
        target_unique=3,
        limit=5,
        active_session=True,
        active_session_path=session_path,
        case_intake_path=intake_path,
    )
    records = {record.known_true_addr: record for record in result.records}

    assert result.active_session_detected is True
    assert result.current_session_reusable_address_count == 1
    assert records["0xBBB061C7D48"].plan_type == "active_session_reuse"
    assert 'prepare-current-case -KnownTrueAddr "0xBBB061C7D48"' in records["0xBBB061C7D48"].command_hint
    assert records["0xAAA061C7D48"].plan_type == "retest_existing"
    assert "prepare-current-case" not in records["0xAAA061C7D48"].command_hint


def test_sample_plan_json_shape(tmp_path: Path) -> None:
    _write_summary(tmp_path, "20260614-000001", "sample_summary_success.txt", {"0xABC061C7D48": "0xAAA061C7D48"})

    result = analyze_sample_plan(log_root=tmp_path, latest=10, profile="full", target_unique=2, limit=5)
    data = result.to_dict()

    assert data["latest_n"] == 10
    assert data["conclusion"] == "SAMPLE_PLAN_NEEDS_COLLECTION"
    assert isinstance(data["records"], list)
    assert {"known_true_addr", "plan_type", "priority", "reason", "command_hint"}.issubset(data["records"][0])
