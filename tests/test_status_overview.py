from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from armedforces_tool import status_overview
from armedforces_tool.logs import LogParseError
from armedforces_tool.status_overview import analyze_status_overview


def _doctor(overall: str = "SAFE") -> SimpleNamespace:
    return SimpleNamespace(
        overall_status=overall,
        safety_state="SAFE_DETECT_ONLY" if overall != "DANGER" else "EXECUTION_DANGER",
        next_run_type="detect_only" if overall != "DANGER" else "write_attempt",
        danger_level="SAFE" if overall != "DANGER" else "DANGER",
        arm_state="not_armed",
        recommendation="doctor recommendation",
    )


def _diagnostic(status: str = "DIAGNOSTIC_BASIC") -> SimpleNamespace:
    return SimpleNamespace(
        diagnostic_status=status,
        diagnostic_level="basic" if status == "DIAGNOSTIC_BASIC" else "trace",
        recommendation="diagnostic recommendation",
    )


def _case_intake(conclusion: str = "CASE_INTAKE_CLEAN", open_count: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        conclusion=conclusion,
        open_count=open_count,
        recommendation="case intake recommendation",
    )


def _baseline_current(conclusion: str = "BASELINE_CURRENT_OK") -> SimpleNamespace:
    return SimpleNamespace(
        conclusion=conclusion,
        baseline_exists=True,
        unique_known_true_addr_count=13,
        recommendation="baseline current recommendation",
    )


def _baseline_compare(conclusion: str = "BASELINE_COMPARE_PASS") -> SimpleNamespace:
    return SimpleNamespace(
        conclusion=conclusion,
        current_eligible_batch_count=20,
        current_unique_known_true_addr_count=13,
        baseline_unique_known_true_addr_count=13,
        coverage_delta=0,
        recommendation="baseline compare recommendation",
    )


def _case_summary(conclusion: str = "COVERAGE_OK") -> SimpleNamespace:
    return SimpleNamespace(
        conclusion=conclusion,
        current_eligible_batch_count=20,
        current_unique_known_true_addr_count=13,
        baseline_unique_known_true_addr_count=13,
        coverage_delta=0,
        recommendation="case summary recommendation",
    )


def _install_safe_components(monkeypatch) -> None:
    monkeypatch.setattr(status_overview, "analyze_safety_doctor", lambda **kwargs: _doctor())
    monkeypatch.setattr(status_overview, "analyze_diagnostic_status", lambda **kwargs: _diagnostic())
    monkeypatch.setattr(status_overview, "analyze_case_intake_status", lambda **kwargs: _case_intake())
    monkeypatch.setattr(status_overview, "analyze_baseline_current", lambda **kwargs: _baseline_current())
    monkeypatch.setattr(status_overview, "analyze_baseline_compare", lambda **kwargs: _baseline_compare())
    monkeypatch.setattr(status_overview, "analyze_case_summary", lambda **kwargs: _case_summary())


def test_all_safe_overview_returns_safe(monkeypatch, tmp_path: Path) -> None:
    _install_safe_components(monkeypatch)

    result = analyze_status_overview(project_root=tmp_path, baseline=tmp_path / "baseline.md")

    assert result.overall_status == "SAFE"
    assert result.warning_count == 0
    assert result.danger_count == 0
    assert result.current_unique_known_true_addr_count == 13
    assert len(result.components) == 6


def test_baseline_compare_warning_causes_overall_warn(monkeypatch, tmp_path: Path) -> None:
    _install_safe_components(monkeypatch)
    monkeypatch.setattr(status_overview, "analyze_baseline_compare", lambda **kwargs: _baseline_compare("BASELINE_COMPARE_WARN"))

    result = analyze_status_overview(project_root=tmp_path, baseline=tmp_path / "baseline.md")

    assert result.overall_status == "WARN"
    assert result.baseline_compare_status == "BASELINE_COMPARE_WARN"
    assert result.warning_count == 1
    assert result.recommendation == "Review warning components before continuing."


def test_safety_danger_causes_overall_danger(monkeypatch, tmp_path: Path) -> None:
    _install_safe_components(monkeypatch)
    monkeypatch.setattr(status_overview, "analyze_safety_doctor", lambda **kwargs: _doctor("DANGER"))

    result = analyze_status_overview(project_root=tmp_path, baseline=tmp_path / "baseline.md")

    assert result.overall_status == "DANGER"
    assert result.danger_count == 1
    assert result.recommendation == "Do not run CE until danger checks are resolved."


def test_case_intake_open_items_causes_overall_warn(monkeypatch, tmp_path: Path) -> None:
    _install_safe_components(monkeypatch)
    monkeypatch.setattr(
        status_overview,
        "analyze_case_intake_status",
        lambda **kwargs: _case_intake("CASE_INTAKE_OPEN_ITEMS", open_count=1),
    )

    result = analyze_status_overview(project_root=tmp_path, baseline=tmp_path / "baseline.md")

    assert result.overall_status == "WARN"
    assert result.case_intake_status == "CASE_INTAKE_OPEN_ITEMS"
    assert result.warning_count == 1


def test_component_failure_does_not_crash_overview(monkeypatch, tmp_path: Path) -> None:
    _install_safe_components(monkeypatch)

    def _raise(**kwargs):
        raise LogParseError("baseline parse failed")

    monkeypatch.setattr(status_overview, "analyze_baseline_current", _raise)

    result = analyze_status_overview(project_root=tmp_path, baseline=tmp_path / "baseline.md")
    component = next(item for item in result.components if item.component_name == "baseline_current")

    assert result.overall_status == "WARN"
    assert component.status == "WARN"
    assert "unavailable: baseline parse failed" in component.summary


def test_status_overview_json_shape(monkeypatch, tmp_path: Path) -> None:
    _install_safe_components(monkeypatch)

    data = analyze_status_overview(project_root=tmp_path, baseline=tmp_path / "baseline.md").to_dict()

    assert {"summary", "components", "warnings", "dangers"}.issubset(data)
    assert {"overall_status", "safety_status", "recommendation"}.issubset(data["summary"])
    assert {"component_name", "status", "summary", "recommendation"}.issubset(data["components"][0])


def test_recommendation_aggregation_for_warnings(monkeypatch, tmp_path: Path) -> None:
    _install_safe_components(monkeypatch)
    monkeypatch.setattr(status_overview, "analyze_diagnostic_status", lambda **kwargs: _diagnostic("DIAGNOSTIC_TRACE"))

    result = analyze_status_overview(project_root=tmp_path, baseline=tmp_path / "baseline.md")

    assert result.overall_status == "WARN"
    assert result.warning_count == 1
    assert result.recommendation == "Review warning components before continuing."
