from __future__ import annotations

from pathlib import Path

from armedforces_tool import safety
from armedforces_tool.safety import (
    analyze_safety_doctor,
    safety_doctor_parity,
    snapshot_protected_files,
)


def _write_config(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("return {\n" + body + "\n}\n", encoding="utf-8")
    return path


def _write_summary(root: Path, batch_id: str = "20260614-000001") -> None:
    root.mkdir(parents=True, exist_ok=True)
    fixture = Path(__file__).parent / "fixtures" / "sample_summary_success.txt"
    (root / f"{batch_id}__summary.txt").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")


def test_doctor_safe_when_detect_only_and_logs_parse(tmp_path: Path) -> None:
    project_root = tmp_path
    config = _write_config(
        project_root / "src" / "run_case_config.local.lua",
        """
  validation_profile = "full",
  diagnostic_level = "basic",
  target_value_float = 100.0,
  target_value_pattern = "0x42C80000",
  execution_mode = "disabled",
  write_enabled = false,
""",
    )
    log_root = project_root / "log" / "auto_output"
    _write_summary(log_root)
    baseline = Path(__file__).parent / "fixtures" / "baseline_case_summary.md"

    result = analyze_safety_doctor(
        project_root=project_root,
        config_path=config,
        log_root=log_root,
        baseline=baseline,
    )

    assert result.overall_status == "SAFE"
    assert result.safety_state == "SAFE_DETECT_ONLY"
    assert result.latest_log_available is True
    assert result.python_tooling_available is True
    assert all(check["status"] != "FAIL" for check in (item.to_dict() for item in result.checks))


def test_doctor_warn_when_baseline_missing(tmp_path: Path) -> None:
    project_root = tmp_path
    config = _write_config(
        project_root / "src" / "run_case_config.local.lua",
        """
  execution_mode = "disabled",
  write_enabled = false,
""",
    )
    log_root = project_root / "log" / "auto_output"
    _write_summary(log_root)

    result = analyze_safety_doctor(
        project_root=project_root,
        config_path=config,
        log_root=log_root,
        baseline=project_root / "log" / "baselines" / "missing.md",
    )

    assert result.overall_status == "WARN"
    assert result.baseline_exists is False
    assert any(check.check_name == "baseline path" and check.status == "WARN" for check in result.checks)


def test_doctor_unknown_when_config_missing(tmp_path: Path) -> None:
    project_root = tmp_path
    log_root = project_root / "log" / "auto_output"
    _write_summary(log_root)
    baseline = Path(__file__).parent / "fixtures" / "baseline_case_summary.md"

    result = analyze_safety_doctor(
        project_root=project_root,
        config_path=project_root / "src" / "run_case_config.local.lua",
        log_root=log_root,
        baseline=baseline,
    )

    assert result.overall_status in {"WARN", "UNKNOWN"}
    assert result.config_exists is False


def test_doctor_danger_when_write_armed(tmp_path: Path) -> None:
    project_root = tmp_path
    config = _write_config(
        project_root / "src" / "run_case_config.local.lua",
        """
  execution_mode = "write",
  write_enabled = true,
  execution_confirm = "I_ACCEPT_WRITE_TO_LIVE_MEMORY",
  execution_write_request_id = "request_test",
  execution_armed_at_utc = "2999-01-01T00:00:00Z",
  execution_arm_expires_at_utc = "2999-01-01T00:10:00Z",
""",
    )
    log_root = project_root / "log" / "auto_output"
    _write_summary(log_root)
    baseline = Path(__file__).parent / "fixtures" / "baseline_case_summary.md"

    result = analyze_safety_doctor(
        project_root=project_root,
        config_path=config,
        log_root=log_root,
        baseline=baseline,
    )

    assert result.overall_status == "DANGER"
    assert result.safety_state == "WRITE_ARMED"
    assert result.danger_count >= 1


def test_doctor_json_shape(tmp_path: Path) -> None:
    project_root = tmp_path
    config = _write_config(project_root / "src" / "run_case_config.local.lua", 'execution_mode = "disabled",')
    log_root = project_root / "log" / "auto_output"
    _write_summary(log_root)
    baseline = Path(__file__).parent / "fixtures" / "baseline_case_summary.md"

    data = analyze_safety_doctor(
        project_root=project_root,
        config_path=config,
        log_root=log_root,
        baseline=baseline,
    ).to_dict()

    assert {"project_root", "overall_status", "checks", "warning_count", "danger_count"}.issubset(data)
    assert data["checks"]
    assert {"check_name", "status", "detail", "recommendation"}.issubset(data["checks"][0])


def test_protected_file_snapshot_is_read_only(tmp_path: Path) -> None:
    protected = tmp_path / "protected.local"
    protected.write_text("keep me stable", encoding="utf-8")

    before = snapshot_protected_files([protected])
    after = snapshot_protected_files([protected])

    assert before == after
    assert protected.read_text(encoding="utf-8") == "keep me stable"


def test_doctor_parity_unparseable_fields_warn(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path
    config = _write_config(project_root / "src" / "run_case_config.local.lua", 'execution_mode = "disabled",')
    log_root = project_root / "log" / "auto_output"
    _write_summary(log_root)
    baseline = Path(__file__).parent / "fixtures" / "baseline_case_summary.md"

    monkeypatch.setattr(safety, "_run_powershell_tool", lambda command_name, session_tool_path: "Session Doctor\n")

    result = safety_doctor_parity(
        project_root=project_root,
        config_path=config,
        log_root=log_root,
        baseline=baseline,
        session_tool_path=project_root / "src" / "test_session_tool.ps1",
    )

    assert result.parity_status == "WARN"
    assert result.unparseable_fields
    assert all(mismatch.status == "WARN" for mismatch in result.mismatches)
