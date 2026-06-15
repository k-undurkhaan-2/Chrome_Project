from __future__ import annotations

import json
from pathlib import Path

import pytest

from armedforces_tool import workflow_status
from armedforces_tool.workflow_status import (
    analyze_case_intake_status,
    analyze_diagnostic_status,
    case_intake_status_parity,
    diagnostic_status_parity,
)


def _write_config(path: Path, diagnostic_level: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""return {{
  diagnostic_level = "{diagnostic_level}",
  validation_profile = "full",
  execution_mode = "disabled",
  write_enabled = false,
}}
""",
        encoding="utf-8",
    )
    return path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        ("basic", "DIAGNOSTIC_BASIC"),
        ("debug", "DIAGNOSTIC_DEBUG"),
        ("trace", "DIAGNOSTIC_TRACE"),
    ],
)
def test_diagnostic_status_levels(tmp_path: Path, level: str, expected: str) -> None:
    config = _write_config(tmp_path / "src" / "run_case_config.local.lua", level)

    result = analyze_diagnostic_status(project_root=tmp_path, config_path=config)

    assert result.diagnostic_level == level
    assert result.diagnostic_status == expected
    assert result.next_run_type == "detect_only"


def test_diagnostic_missing_config(tmp_path: Path) -> None:
    result = analyze_diagnostic_status(
        project_root=tmp_path,
        config_path=tmp_path / "src" / "run_case_config.local.lua",
    )

    assert result.config_exists is False
    assert result.diagnostic_status == "CONFIG_MISSING"


def test_diagnostic_invalid_level(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "src" / "run_case_config.local.lua", "verbose")

    result = analyze_diagnostic_status(project_root=tmp_path, config_path=config)

    assert result.diagnostic_level == "unknown"
    assert result.diagnostic_status == "CONFIG_WARN"


def test_case_intake_missing_journal_and_absent_session(tmp_path: Path) -> None:
    result = analyze_case_intake_status(
        project_root=tmp_path,
        intake_journal=tmp_path / "log" / "case_intake.local.jsonl",
        session_file=tmp_path / "log" / "active_test_session.local.json",
        session_history=tmp_path / "log" / "test_session_history.local.jsonl",
    )

    assert result.intake_journal_exists is False
    assert result.active_session_detected is False
    assert result.conclusion == "CASE_INTAKE_NO_JOURNAL"


def test_case_intake_counts_and_open_detection(tmp_path: Path) -> None:
    journal = _write_jsonl(
        tmp_path / "log" / "case_intake.local.jsonl",
        [
            {
                "event_type": "prepared",
                "intake_id": "intake_open",
                "session_id": "session_a",
                "known_true_addr": "0xAAA",
                "profile": "full",
                "prepared_at_utc": "2026-06-14T00:00:00Z",
            },
            {
                "event_type": "prepared",
                "intake_id": "intake_done",
                "session_id": "session_a",
                "known_true_addr": "0xBBB",
                "profile": "full",
                "prepared_at_utc": "2026-06-14T00:01:00Z",
            },
            {
                "event_type": "completed",
                "intake_id": "intake_done",
                "session_id": "session_a",
                "known_true_addr": "0xBBB",
                "profile": "full",
                "completed_at_utc": "2026-06-14T00:02:00Z",
                "batch_id": "20260614-000200",
            },
            {
                "event_type": "abandoned",
                "intake_id": "intake_old",
                "session_id": "session_a",
                "known_true_addr": "0xCCC",
                "profile": "full",
                "abandoned_at_utc": "2026-06-14T00:03:00Z",
                "reason": "test",
            },
        ],
    )

    result = analyze_case_intake_status(
        project_root=tmp_path,
        intake_journal=journal,
        session_file=tmp_path / "log" / "active_test_session.local.json",
        session_history=tmp_path / "log" / "test_session_history.local.jsonl",
    )

    assert result.prepared_count == 2
    assert result.completed_count == 1
    assert result.abandoned_count == 1
    assert result.open_count == 1
    assert result.latest_completed_batch_id == "20260614-000200"
    assert result.conclusion == "CASE_INTAKE_OPEN_ITEMS"
    assert any(record.intake_id == "intake_open" and record.is_open for record in result.records)


def test_case_intake_active_session_present(tmp_path: Path) -> None:
    session = tmp_path / "log" / "active_test_session.local.json"
    session.parent.mkdir(parents=True, exist_ok=True)
    session.write_text(
        json.dumps(
            {
                "session_id": "session_active",
                "status": "active",
                "label": "test session",
                "started_at_utc": "2026-06-14T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    journal = _write_jsonl(
        tmp_path / "log" / "case_intake.local.jsonl",
        [
            {
                "event_type": "prepared",
                "intake_id": "intake_current",
                "session_id": "session_active",
                "known_true_addr": "0xAAA",
                "profile": "full",
            }
        ],
    )

    result = analyze_case_intake_status(
        project_root=tmp_path,
        intake_journal=journal,
        session_file=session,
        session_history=tmp_path / "log" / "test_session_history.local.jsonl",
    )

    assert result.active_session_detected is True
    assert result.active_session_id == "session_active"
    assert result.records[0].active_session_related is True


def test_case_intake_json_shape(tmp_path: Path) -> None:
    journal = _write_jsonl(
        tmp_path / "log" / "case_intake.local.jsonl",
        [{"event_type": "prepared", "intake_id": "intake_shape", "known_true_addr": "0xAAA"}],
    )

    data = analyze_case_intake_status(
        project_root=tmp_path,
        intake_journal=journal,
        session_file=tmp_path / "log" / "active_test_session.local.json",
        session_history=tmp_path / "log" / "test_session_history.local.jsonl",
    ).to_dict()

    assert {"prepared_count", "completed_count", "open_count", "records", "conclusion"}.issubset(data)
    assert {"intake_id", "action", "is_open", "active_session_related"}.issubset(data["records"][0])


def test_diagnostic_parity_unparseable_fields_warn(monkeypatch, tmp_path: Path) -> None:
    config = _write_config(tmp_path / "src" / "run_case_config.local.lua", "basic")
    monkeypatch.setattr(workflow_status, "_run_powershell_command", lambda command_name, session_tool_path: "Diagnostic Status\n")

    result = diagnostic_status_parity(
        project_root=tmp_path,
        config_path=config,
        session_tool_path=tmp_path / "src" / "test_session_tool.ps1",
    )

    assert result.parity_status == "WARN"
    assert result.unparseable_fields
    assert all(mismatch.status == "WARN" for mismatch in result.mismatches)


def test_case_intake_parity_unparseable_fields_warn(monkeypatch, tmp_path: Path) -> None:
    journal = _write_jsonl(tmp_path / "log" / "case_intake.local.jsonl", [])
    monkeypatch.setattr(workflow_status, "_run_powershell_command", lambda command_name, session_tool_path: "Case Intake Status\n")

    result = case_intake_status_parity(
        project_root=tmp_path,
        intake_journal=journal,
        session_file=tmp_path / "log" / "active_test_session.local.json",
        session_history=tmp_path / "log" / "test_session_history.local.jsonl",
        session_tool_path=tmp_path / "src" / "test_session_tool.ps1",
    )

    assert result.parity_status == "WARN"
    assert result.unparseable_fields
