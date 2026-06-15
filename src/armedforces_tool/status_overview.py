from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .baseline_status import analyze_baseline_compare, analyze_baseline_current
from .case_summary import DEFAULT_BASELINE_PATH, analyze_case_summary
from .logs import DEFAULT_LOG_ROOT, LogParseError
from .safety import DEFAULT_CONFIG_PATH, DEFAULT_PROJECT_ROOT, analyze_safety_doctor
from .workflow_status import (
    DEFAULT_ACTIVE_SESSION_PATH,
    DEFAULT_CASE_INTAKE_PATH,
    DEFAULT_SESSION_HISTORY_PATH,
    analyze_case_intake_status,
    analyze_diagnostic_status,
)


@dataclass(frozen=True)
class StatusOverviewComponent:
    component_name: str
    status: str
    summary: str
    recommendation: str

    def to_dict(self) -> dict[str, object]:
        return {
            "component_name": self.component_name,
            "status": self.status,
            "summary": self.summary,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class StatusOverviewResult:
    project_root: str
    overall_status: str
    safety_status: str
    next_run_type: str
    danger_level: str
    execution_arm_state: str
    diagnostic_status: str
    case_intake_status: str
    baseline_status: str
    baseline_compare_status: str
    case_summary_status: str
    latest_n: int
    profile: str
    current_unique_known_true_addr_count: int | None
    baseline_unique_known_true_addr_count: int | None
    coverage_delta: int | None
    warning_count: int
    danger_count: int
    recommendation: str
    components: list[StatusOverviewComponent]
    warnings: list[str]
    dangers: list[str]

    def to_dict(self) -> dict[str, object | None]:
        return {
            "summary": {
                "project_root": self.project_root,
                "overall_status": self.overall_status,
                "safety_status": self.safety_status,
                "next_run_type": self.next_run_type,
                "danger_level": self.danger_level,
                "execution_arm_state": self.execution_arm_state,
                "diagnostic_status": self.diagnostic_status,
                "case_intake_status": self.case_intake_status,
                "baseline_status": self.baseline_status,
                "baseline_compare_status": self.baseline_compare_status,
                "case_summary_status": self.case_summary_status,
                "latest_n": self.latest_n,
                "profile": self.profile,
                "current_unique_known_true_addr_count": self.current_unique_known_true_addr_count,
                "baseline_unique_known_true_addr_count": self.baseline_unique_known_true_addr_count,
                "coverage_delta": self.coverage_delta,
                "warning_count": self.warning_count,
                "danger_count": self.danger_count,
                "recommendation": self.recommendation,
            },
            "components": [component.to_dict() for component in self.components],
            "warnings": self.warnings,
            "dangers": self.dangers,
        }


def analyze_status_overview(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    latest: int = 20,
    profile: str = "full",
    baseline: Path = DEFAULT_BASELINE_PATH,
    config_path: Path | None = None,
    log_root: Path | None = None,
    intake_journal: Path | None = None,
    session_file: Path | None = None,
    session_history: Path | None = None,
) -> StatusOverviewResult:
    if latest < 1:
        raise LogParseError("--latest must be greater than 0")

    config_path = config_path or project_root / "src" / "run_case_config.local.lua"
    log_root = log_root or project_root / "log" / "auto_output"
    intake_journal = intake_journal or project_root / "log" / "case_intake.local.jsonl"
    session_file = session_file or project_root / "log" / "active_test_session.local.json"
    session_history = session_history or project_root / "log" / "test_session_history.local.jsonl"

    components: list[StatusOverviewComponent] = []
    field_values: dict[str, object | None] = {
        "safety_status": "UNKNOWN",
        "next_run_type": "unknown",
        "danger_level": "UNKNOWN",
        "execution_arm_state": "unknown",
        "diagnostic_status": "UNKNOWN",
        "case_intake_status": "UNKNOWN",
        "baseline_status": "UNKNOWN",
        "baseline_compare_status": "UNKNOWN",
        "case_summary_status": "UNKNOWN",
        "current_unique_known_true_addr_count": None,
        "baseline_unique_known_true_addr_count": None,
        "coverage_delta": None,
    }

    doctor = _safe_component(
        "safety_doctor",
        lambda: analyze_safety_doctor(
            project_root=project_root,
            config_path=config_path,
            log_root=log_root,
            baseline=baseline,
        ),
        _doctor_component,
    )
    components.append(doctor.component)
    if doctor.data is not None:
        field_values.update(
            {
                "safety_status": doctor.data.overall_status,
                "next_run_type": doctor.data.next_run_type,
                "danger_level": doctor.data.danger_level,
                "execution_arm_state": doctor.data.arm_state,
            }
        )

    diagnostic = _safe_component(
        "diagnostic",
        lambda: analyze_diagnostic_status(project_root=project_root, config_path=config_path),
        _diagnostic_component,
    )
    components.append(diagnostic.component)
    if diagnostic.data is not None:
        field_values["diagnostic_status"] = diagnostic.data.diagnostic_status

    case_intake = _safe_component(
        "case_intake",
        lambda: analyze_case_intake_status(
            project_root=project_root,
            intake_journal=intake_journal,
            session_file=session_file,
            session_history=session_history,
        ),
        _case_intake_component,
    )
    components.append(case_intake.component)
    if case_intake.data is not None:
        field_values["case_intake_status"] = case_intake.data.conclusion

    baseline_current = _safe_component(
        "baseline_current",
        lambda: analyze_baseline_current(baseline=baseline),
        _baseline_current_component,
    )
    components.append(baseline_current.component)
    if baseline_current.data is not None:
        field_values["baseline_status"] = baseline_current.data.conclusion

    baseline_compare = _safe_component(
        "baseline_compare",
        lambda: analyze_baseline_compare(baseline=baseline, latest=latest, profile=profile, log_root=log_root),
        _baseline_compare_component,
    )
    components.append(baseline_compare.component)
    if baseline_compare.data is not None:
        field_values.update(
            {
                "baseline_compare_status": baseline_compare.data.conclusion,
                "baseline_unique_known_true_addr_count": baseline_compare.data.baseline_unique_known_true_addr_count,
                "current_unique_known_true_addr_count": baseline_compare.data.current_unique_known_true_addr_count,
                "coverage_delta": baseline_compare.data.coverage_delta,
            }
        )

    case_summary = _safe_component(
        "case_summary",
        lambda: analyze_case_summary(log_root=log_root, latest=latest, profile=profile, baseline=baseline),
        _case_summary_component,
    )
    components.append(case_summary.component)
    if case_summary.data is not None:
        field_values.update(
            {
                "case_summary_status": case_summary.data.conclusion,
                "baseline_unique_known_true_addr_count": case_summary.data.baseline_unique_known_true_addr_count,
                "current_unique_known_true_addr_count": case_summary.data.current_unique_known_true_addr_count,
                "coverage_delta": case_summary.data.coverage_delta,
            }
        )

    warnings = [
        f"{component.component_name}: {component.summary}"
        for component in components
        if component.status == "WARN"
    ]
    dangers = [
        f"{component.component_name}: {component.summary}"
        for component in components
        if component.status == "FAIL"
    ]
    overall = _overall_status(components, str(field_values.get("safety_status") or "UNKNOWN"))
    return StatusOverviewResult(
        project_root=str(project_root),
        overall_status=overall,
        safety_status=str(field_values["safety_status"]),
        next_run_type=str(field_values["next_run_type"]),
        danger_level=str(field_values["danger_level"]),
        execution_arm_state=str(field_values["execution_arm_state"]),
        diagnostic_status=str(field_values["diagnostic_status"]),
        case_intake_status=str(field_values["case_intake_status"]),
        baseline_status=str(field_values["baseline_status"]),
        baseline_compare_status=str(field_values["baseline_compare_status"]),
        case_summary_status=str(field_values["case_summary_status"]),
        latest_n=latest,
        profile=profile,
        current_unique_known_true_addr_count=_as_int(field_values["current_unique_known_true_addr_count"]),
        baseline_unique_known_true_addr_count=_as_int(field_values["baseline_unique_known_true_addr_count"]),
        coverage_delta=_as_int(field_values["coverage_delta"]),
        warning_count=len(warnings),
        danger_count=len(dangers),
        recommendation=_overview_recommendation(overall),
        components=components,
        warnings=warnings,
        dangers=dangers,
    )


@dataclass(frozen=True)
class _ComponentExecution:
    data: object | None
    component: StatusOverviewComponent


def _safe_component(
    component_name: str,
    run: Callable[[], object],
    build_component: Callable[[object], StatusOverviewComponent],
) -> _ComponentExecution:
    try:
        data = run()
    except Exception as exc:  # noqa: BLE001 - overview must degrade gracefully.
        return _ComponentExecution(
            data=None,
            component=StatusOverviewComponent(
                component_name=component_name,
                status="WARN",
                summary=f"unavailable: {exc}",
                recommendation="Review this component before relying on consolidated status.",
            ),
        )
    return _ComponentExecution(data=data, component=build_component(data))


def _doctor_component(data: object) -> StatusOverviewComponent:
    status = "PASS"
    if data.overall_status == "DANGER":
        status = "FAIL"
    elif data.overall_status != "SAFE":
        status = "WARN"
    return StatusOverviewComponent(
        component_name="safety_doctor",
        status=status,
        summary=(
            f"overall={data.overall_status}; safety_state={data.safety_state}; "
            f"next_run_type={data.next_run_type}; danger_level={data.danger_level}"
        ),
        recommendation=str(data.recommendation),
    )


def _diagnostic_component(data: object) -> StatusOverviewComponent:
    status = "PASS" if data.diagnostic_status == "DIAGNOSTIC_BASIC" else "WARN"
    return StatusOverviewComponent(
        component_name="diagnostic",
        status=status,
        summary=f"diagnostic_status={data.diagnostic_status}; level={data.diagnostic_level}",
        recommendation=str(data.recommendation),
    )


def _case_intake_component(data: object) -> StatusOverviewComponent:
    if data.conclusion == "CASE_INTAKE_CLEAN":
        status = "PASS"
    elif data.conclusion == "CASE_INTAKE_NO_JOURNAL":
        status = "INFO"
    else:
        status = "WARN"
    return StatusOverviewComponent(
        component_name="case_intake",
        status=status,
        summary=f"conclusion={data.conclusion}; open_count={data.open_count}",
        recommendation=str(data.recommendation),
    )


def _baseline_current_component(data: object) -> StatusOverviewComponent:
    status = "PASS" if data.conclusion == "BASELINE_CURRENT_OK" else "WARN"
    return StatusOverviewComponent(
        component_name="baseline_current",
        status=status,
        summary=(
            f"conclusion={data.conclusion}; exists={data.baseline_exists}; "
            f"unique={data.unique_known_true_addr_count}"
        ),
        recommendation=str(data.recommendation),
    )


def _baseline_compare_component(data: object) -> StatusOverviewComponent:
    status = "PASS" if data.conclusion == "BASELINE_COMPARE_PASS" else "WARN"
    return StatusOverviewComponent(
        component_name="baseline_compare",
        status=status,
        summary=(
            f"conclusion={data.conclusion}; eligible={data.current_eligible_batch_count}; "
            f"unique={data.current_unique_known_true_addr_count}; delta={data.coverage_delta}"
        ),
        recommendation=str(data.recommendation),
    )


def _case_summary_component(data: object) -> StatusOverviewComponent:
    status = "PASS" if data.conclusion == "COVERAGE_OK" else "WARN"
    return StatusOverviewComponent(
        component_name="case_summary",
        status=status,
        summary=(
            f"conclusion={data.conclusion}; eligible={data.current_eligible_batch_count}; "
            f"unique={data.current_unique_known_true_addr_count}; delta={data.coverage_delta}"
        ),
        recommendation=str(data.recommendation),
    )


def _overall_status(components: list[StatusOverviewComponent], safety_status: str) -> str:
    if safety_status == "DANGER" or any(component.component_name == "safety_doctor" and component.status == "FAIL" for component in components):
        return "DANGER"
    if safety_status == "UNKNOWN" and any(component.component_name == "safety_doctor" and component.status == "WARN" for component in components):
        return "UNKNOWN"
    if any(component.status == "WARN" for component in components):
        return "WARN"
    return "SAFE"


def _overview_recommendation(overall_status: str) -> str:
    if overall_status == "SAFE":
        return "Project state is safe for read-only daily status checks and detect-only planning."
    if overall_status == "WARN":
        return "Review warning components before continuing."
    if overall_status == "DANGER":
        return "Do not run CE until danger checks are resolved."
    return "Review unavailable status components before continuing."


def _as_int(value: object | None) -> int | None:
    if isinstance(value, int):
        return value
    if value is None:
        return None
    try:
        return int(str(value))
    except ValueError:
        return None
