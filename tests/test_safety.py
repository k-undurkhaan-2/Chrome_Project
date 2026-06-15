from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from armedforces_tool.safety import (
    analyze_safety_execution_status,
    analyze_safety_plan,
    analyze_safety_status,
    parse_lua_config,
)


NOW = datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc)


def _write_config(path: Path, body: str) -> Path:
    path.write_text(
        "return {\n" + body + "\n}\n",
        encoding="utf-8",
    )
    return path


def test_lua_config_parser_supports_common_value_types(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path / "run_case_config.local.lua",
        """
  case_id = "case_test",
  known_true_addr = "0xABC061C7D48", -- keep inline comment out
  target_value_float = 100.0,
  retry_count = 2,
  write_enabled = false,
  optional_value = nil,
  diagnostic_level = 'basic',
""",
    )

    parsed = parse_lua_config(config_path)

    assert parsed.exists is True
    assert parsed.raw_fields["case_id"] == "case_test"
    assert parsed.raw_fields["known_true_addr"] == "0xABC061C7D48"
    assert parsed.raw_fields["target_value_float"] == 100.0
    assert parsed.raw_fields["retry_count"] == 2
    assert parsed.raw_fields["write_enabled"] is False
    assert parsed.raw_fields["optional_value"] is None
    assert parsed.raw_fields["diagnostic_level"] == "basic"


def test_missing_config_is_safe_no_config(tmp_path: Path) -> None:
    missing = tmp_path / "missing.lua"

    result = analyze_safety_status(config_path=missing, project_root=tmp_path, now=NOW)

    assert result.config_exists is False
    assert result.safety_state == "SAFE_NO_CONFIG"


def test_safe_detect_only_state_and_plan(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path / "run_case_config.local.lua",
        """
  validation_profile = "full",
  diagnostic_level = "basic",
  target_value_float = 100.0,
  target_value_pattern = "0x42C80000",
  execution_mode = "disabled",
  write_enabled = false,
""",
    )

    status = analyze_safety_status(config_path=config_path, project_root=tmp_path, now=NOW)
    plan = analyze_safety_plan(config_path=config_path, project_root=tmp_path, now=NOW)

    assert status.safety_state == "SAFE_DETECT_ONLY"
    assert status.execution_enabled is False
    assert status.write_enabled is False
    assert plan.next_run_type == "detect_only"
    assert plan.danger_level == "SAFE"


def test_write_armed_state_detection(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path / "run_case_config.local.lua",
        """
  execution_mode = "write",
  write_enabled = true,
  execution_confirm = "I_ACCEPT_WRITE_TO_LIVE_MEMORY",
  execution_write_request_id = "request_test",
  execution_armed_at_utc = "2026-06-15T00:00:00Z",
  execution_arm_expires_at_utc = "2026-06-15T00:10:00Z",
  write_value_float = 999.0,
""",
    )

    status = analyze_safety_status(config_path=config_path, project_root=tmp_path, now=NOW)
    execution_status = analyze_safety_execution_status(config_path=config_path, project_root=tmp_path, now=NOW)

    assert status.safety_state == "WRITE_ARMED"
    assert status.execution_arm_state == "armed"
    assert execution_status.arm_state == "armed"
    assert execution_status.arm_seconds_remaining == 600


def test_expired_arm_is_dangerous_but_not_armed(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path / "run_case_config.local.lua",
        """
  execution_mode = "write",
  write_enabled = true,
  execution_confirm = "I_ACCEPT_WRITE_TO_LIVE_MEMORY",
  execution_write_request_id = "request_old",
  execution_armed_at_utc = "2026-06-14T23:00:00Z",
  execution_arm_expires_at_utc = "2026-06-14T23:10:00Z",
""",
    )

    status = analyze_safety_status(config_path=config_path, project_root=tmp_path, now=NOW)
    execution_status = analyze_safety_execution_status(config_path=config_path, project_root=tmp_path, now=NOW)

    assert status.safety_state == "EXECUTION_DANGER"
    assert status.execution_arm_state == "expired"
    assert execution_status.arm_state == "expired"
    assert execution_status.arm_seconds_remaining is not None
    assert execution_status.arm_seconds_remaining < 0


def test_plan_classifies_restore_attempt(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path / "run_case_config.local.lua",
        """
  execution_mode = "write",
  write_enabled = true,
  restore_source_batch_id = "20260613-225514",
  restore_source_batch_execution_addr = "0xABC061C7D48",
""",
    )

    plan = analyze_safety_plan(config_path=config_path, project_root=tmp_path, now=NOW)

    assert plan.next_run_type == "restore_attempt"
    assert plan.danger_level == "DANGER"
    assert plan.key_config_fields["restore_source_batch_execution_addr"] == "0xABC061C7D48"


def test_safety_json_shape(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path / "run_case_config.local.lua",
        """
  execution_mode = "disabled",
  write_enabled = false,
  validation_profile = "full",
""",
    )

    data = analyze_safety_status(config_path=config_path, project_root=tmp_path, now=NOW).to_dict()

    assert data["project_root"] == str(tmp_path)
    assert data["config_exists"] is True
    assert data["validation_profile"] == "full"
    assert data["safety_state"] == "SAFE_DETECT_ONLY"
