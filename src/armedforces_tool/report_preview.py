from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .baseline_status import analyze_baseline_compare
from .case_summary import DEFAULT_BASELINE_PATH, analyze_case_summary
from .logs import DEFAULT_LOG_ROOT
from .registry_status import analyze_registry_summary
from .safety import DEFAULT_PROJECT_ROOT, analyze_safety_doctor
from .status_overview import analyze_status_overview
from .transaction_history import analyze_transaction_summary

REPORT_TYPES = (
    "status-overview",
    "safety-doctor",
    "baseline-compare",
    "case-summary",
    "registry-summary",
    "transaction-summary",
    "full-status",
)


class ReportPreviewError(RuntimeError):
    """Raised for user-facing report preview errors."""


@dataclass(frozen=True)
class ReportPreviewResult:
    report_type: str
    markdown: str
    component_statuses: list[dict[str, object]]
    warnings: list[str]
    errors: list[str]
    cli_text: str | None = None
    read_only: bool = True
    writes_files: bool = False
    runs_ce: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "report_type": self.report_type,
            "markdown": self.markdown,
            "component_statuses": self.component_statuses,
            "warnings": self.warnings,
            "errors": self.errors,
            "read_only": self.read_only,
            "writes_files": self.writes_files,
            "runs_ce": self.runs_ce,
        }


def preview_report(*, report_type: str = "status-overview", latest: int = 20, profile: str = "full") -> ReportPreviewResult:
    normalized = _normalize_report_type(report_type)
    if latest < 1:
        raise ReportPreviewError("--latest must be greater than 0")
    if profile not in {"full", "quick"}:
        raise ReportPreviewError("--profile must be one of full, quick")

    generated_at = _generated_at()
    if normalized == "status-overview":
        result = analyze_status_overview(project_root=DEFAULT_PROJECT_ROOT, latest=latest, profile=profile)
        return _single_report(
            report_type=normalized,
            markdown=_render_status_overview(
                result,
                generated_at=generated_at,
                heading_level=1,
            ),
            status=str(result.overall_status),
        )
    if normalized == "safety-doctor":
        result = analyze_safety_doctor(project_root=DEFAULT_PROJECT_ROOT)
        return _single_report(
            report_type=normalized,
            markdown=_render_safety_doctor(result, generated_at=generated_at, heading_level=1),
            status=str(result.overall_status),
        )
    if normalized == "baseline-compare":
        result = analyze_baseline_compare(
            baseline=DEFAULT_BASELINE_PATH,
            latest=latest,
            profile=profile,
            log_root=DEFAULT_LOG_ROOT,
        )
        return _single_report(
            report_type=normalized,
            markdown=_render_baseline_compare(result, generated_at=generated_at, heading_level=1),
            status=str(result.conclusion),
        )
    if normalized == "case-summary":
        result = analyze_case_summary(
            log_root=DEFAULT_LOG_ROOT,
            latest=latest,
            profile=profile,
            baseline=DEFAULT_BASELINE_PATH,
        )
        return _single_report(
            report_type=normalized,
            markdown=_render_case_summary(result, generated_at=generated_at, heading_level=1),
            status=str(result.conclusion),
        )
    if normalized == "registry-summary":
        result = analyze_registry_summary(project_root=DEFAULT_PROJECT_ROOT)
        return _single_report(
            report_type=normalized,
            markdown=_render_registry_summary(result, generated_at=generated_at, heading_level=1),
            status=str(result.conclusion),
        )
    if normalized == "transaction-summary":
        result = analyze_transaction_summary(project_root=DEFAULT_PROJECT_ROOT)
        return _single_report(
            report_type=normalized,
            markdown=_render_transaction_summary(result, generated_at=generated_at, heading_level=1),
            status=str(result.conclusion),
        )
    return _render_full_status(generated_at=generated_at, latest=latest, profile=profile)


def _render_full_status(*, generated_at: str, latest: int, profile: str) -> ReportPreviewResult:
    component_statuses: list[dict[str, object]] = []
    warnings: list[str] = []
    errors: list[str] = []
    component_data: dict[str, dict[str, object]] = {}

    components: list[tuple[str, Callable[[], object], str]] = [
        (
            "status-overview",
            lambda: analyze_status_overview(project_root=DEFAULT_PROJECT_ROOT, latest=latest, profile=profile),
            "overall_status",
        ),
        (
            "safety-doctor",
            lambda: analyze_safety_doctor(project_root=DEFAULT_PROJECT_ROOT),
            "overall_status",
        ),
        (
            "baseline-compare",
            lambda: analyze_baseline_compare(
                baseline=DEFAULT_BASELINE_PATH,
                latest=latest,
                profile=profile,
                log_root=DEFAULT_LOG_ROOT,
            ),
            "conclusion",
        ),
        (
            "case-summary",
            lambda: analyze_case_summary(
                log_root=DEFAULT_LOG_ROOT,
                latest=latest,
                profile=profile,
                baseline=DEFAULT_BASELINE_PATH,
            ),
            "conclusion",
        ),
        (
            "registry-summary",
            lambda: analyze_registry_summary(project_root=DEFAULT_PROJECT_ROOT),
            "conclusion",
        ),
        (
            "transaction-summary",
            lambda: analyze_transaction_summary(project_root=DEFAULT_PROJECT_ROOT),
            "conclusion",
        ),
    ]

    for component, analyze, status_attr in components:
        try:
            result = analyze()
            status = str(getattr(result, status_attr))
            component_data[component] = result.to_dict()
        except Exception as exc:  # noqa: BLE001 - full-status must degrade gracefully.
            message = f"{component}: {exc}"
            errors.append(message)
            component_statuses.append({"component": component, "status": "ERROR"})
            continue
        component_statuses.append({"component": component, "status": status})
        if status not in {"OK", "SAFE", "BASELINE_COMPARE_PASS", "COVERAGE_OK", "REGISTRY_OK", "TRANSACTION_HISTORY_OK"}:
            warnings.append(f"{component}: {status}")

    markdown = _render_full_status_compact(
        generated_at=generated_at,
        latest=latest,
        profile=profile,
        component_data=component_data,
        component_statuses=component_statuses,
        warnings=warnings,
        errors=errors,
    )
    cli_text = _render_full_status_cli_text(
        component_data=component_data,
        component_statuses=component_statuses,
        warnings=warnings,
        errors=errors,
    )

    return ReportPreviewResult(
        report_type="full-status",
        markdown=markdown,
        component_statuses=component_statuses,
        warnings=warnings,
        errors=errors,
        cli_text=cli_text,
    )


def _render_full_status_compact(
    *,
    generated_at: str,
    latest: int,
    profile: str,
    component_data: dict[str, dict[str, object]],
    component_statuses: list[dict[str, object]],
    warnings: list[str],
    errors: list[str],
) -> str:
    status_summary = _as_dict(component_data.get("status-overview", {}).get("summary"))
    status_components = component_data.get("status-overview", {}).get("components")
    safety = component_data.get("safety-doctor", {})
    baseline = component_data.get("baseline-compare", {})
    case = component_data.get("case-summary", {})
    registry = component_data.get("registry-summary", {})
    transactions = component_data.get("transaction-summary", {})

    lines = [
        "# Full Status Preview",
        "",
        f"- generated_at: `{_escape_inline(generated_at)}`",
        f"- latest: `{latest}`",
        f"- profile: `{_escape_inline(profile)}`",
        "- read_only: `true`",
        "- writes_files: `false`",
        "- runs_ce: `false`",
        "",
        "## Overall",
        "",
        _field_table(
            [
                ("overall_status", status_summary.get("overall_status")),
                ("safety_status", status_summary.get("safety_status")),
                ("next_run_type", status_summary.get("next_run_type")),
                ("execution_arm_state", safety.get("arm_state")),
                ("diagnostic_status", status_summary.get("diagnostic_status")),
                ("case_intake_status", status_summary.get("case_intake_status")),
                ("baseline_compare_status", status_summary.get("baseline_compare_status")),
                ("case_summary_status", status_summary.get("case_summary_status")),
            ]
        ),
        "",
        "## Components",
        "",
        _markdown_table(
            ["component", "status", "key result"],
            [
                ["status", _component_status(component_statuses, "status-overview"), _status_key_result(status_summary)],
                ["safety", _component_status(component_statuses, "safety-doctor"), _safety_key_result(safety)],
                ["baseline", _component_status(component_statuses, "baseline-compare"), _baseline_key_result(baseline)],
                ["case", _component_status(component_statuses, "case-summary"), _case_key_result(case)],
                ["registry", _component_status(component_statuses, "registry-summary"), _registry_key_result(registry)],
                [
                    "transactions",
                    _component_status(component_statuses, "transaction-summary"),
                    _transaction_key_result(transactions),
                ],
            ],
        ),
        "",
        "## Coverage",
        "",
        _field_table(
            [
                ("current_unique_known_true_addr_count", case.get("current_unique_known_true_addr_count")),
                ("baseline_unique_known_true_addr_count", baseline.get("baseline_unique_known_true_addr_count")),
                ("coverage_delta", case.get("coverage_delta")),
                ("current_eligible_batch_count", case.get("current_eligible_batch_count")),
                ("current_success_count", case.get("current_success_count")),
                ("estimated_new_distinct_addr_needed", case.get("estimated_new_distinct_addr_needed")),
            ]
        ),
        "",
        "## Registry / Transactions",
        "",
        _field_table(
            [
                ("registry_status", registry.get("conclusion")),
                ("registry_records", registry.get("parsed_records")),
                ("registry_unique_known_true_addr_count", registry.get("unique_known_true_addr_count")),
                ("registry_baseline_eligible_count", registry.get("baseline_eligible_count")),
                ("registry_execution_batch_count", registry.get("execution_batch_count")),
                ("transaction_status", transactions.get("conclusion")),
                ("detect_only", transactions.get("detect_only_count")),
                ("dry_run", transactions.get("dry_run_count")),
                ("write_success", transactions.get("write_success_count")),
                ("write_blocked", transactions.get("write_blocked_count")),
                ("restore_success", transactions.get("restore_success_count")),
                ("restore_blocked", transactions.get("restore_blocked_count")),
            ]
        ),
        "",
        "## Recommendations",
        "",
        _recommendations_block(component_data, warnings, errors),
        "",
        "## Details",
        "",
        _field_table(
            [
                ("baseline_file", _basename(baseline.get("baseline_path") or case.get("baseline_path"))),
                ("registry_file", _basename(registry.get("registry_path"))),
                ("latest_transaction_batch", transactions.get("latest_transaction_batch_id")),
                ("latest_transaction_type", transactions.get("latest_transaction_type")),
            ]
        ),
    ]
    return "\n".join(lines).strip() + "\n"


def _render_component_with_status(result: object, renderer: Callable[..., str], generated_at: str, status_attr: str) -> tuple[str, str]:
    return renderer(result, generated_at=generated_at, heading_level=2), str(getattr(result, status_attr))


def _render_full_status_cli_text(
    *,
    component_data: dict[str, dict[str, object]],
    component_statuses: list[dict[str, object]],
    warnings: list[str],
    errors: list[str],
) -> str:
    status_summary = _as_dict(component_data.get("status-overview", {}).get("summary"))
    status_components = component_data.get("status-overview", {}).get("components")
    safety = component_data.get("safety-doctor", {})
    baseline = component_data.get("baseline-compare", {})
    case = component_data.get("case-summary", {})
    registry = component_data.get("registry-summary", {})
    transactions = component_data.get("transaction-summary", {})
    lines = [
        "Full Status Preview",
        "===================",
        "",
        "Overall",
        "-------",
        _aligned_pairs(
            [
                ("overall_status", status_summary.get("overall_status")),
                ("safety_status", status_summary.get("safety_status")),
                ("next_run_type", status_summary.get("next_run_type")),
                ("danger_level", status_summary.get("danger_level")),
                ("execution_arm_state", safety.get("arm_state")),
                ("diagnostic_status", status_summary.get("diagnostic_status")),
                ("case_intake_status", status_summary.get("case_intake_status")),
            ]
        ),
        "",
        "Coverage",
        "--------",
        _aligned_pairs(
            [
                ("baseline_compare", baseline.get("conclusion")),
                ("case_summary", case.get("conclusion")),
                ("current_unique", case.get("current_unique_known_true_addr_count")),
                ("baseline_unique", baseline.get("baseline_unique_known_true_addr_count")),
                ("coverage_delta", _signed(case.get("coverage_delta"))),
            ]
        ),
        "",
        "Registry / Transactions",
        "-----------------------",
        _aligned_pairs(
            [
                ("registry", registry.get("conclusion")),
                ("transaction_history", transactions.get("conclusion")),
                ("detect_only", transactions.get("detect_only_count")),
                ("dry_run", transactions.get("dry_run_count")),
                ("write_success", transactions.get("write_success_count")),
                ("write_blocked", transactions.get("write_blocked_count")),
                ("restore_success", transactions.get("restore_success_count")),
                ("restore_blocked", transactions.get("restore_blocked_count")),
            ]
        ),
        "",
        "Components",
        "----------",
        _aligned_pairs(
            [
                ("safety_doctor", _status_to_pass_fail(_overview_component_status(status_components, "safety_doctor"))),
                ("diagnostic", _status_to_pass_fail(_overview_component_status(status_components, "diagnostic"))),
                ("case_intake", _status_to_pass_fail(_overview_component_status(status_components, "case_intake"))),
                ("baseline_current", _status_to_pass_fail(_overview_component_status(status_components, "baseline_current"))),
                ("baseline_compare", _status_to_pass_fail(_overview_component_status(status_components, "baseline_compare"))),
                ("case_summary", _status_to_pass_fail(_overview_component_status(status_components, "case_summary"))),
                ("registry_summary", _status_to_pass_fail(_component_status(component_statuses, "registry-summary"))),
                ("transaction_summary", _status_to_pass_fail(_component_status(component_statuses, "transaction-summary"))),
            ]
        ),
        "",
        "Recommendations",
        "---------------",
        _recommendations_text(component_data, warnings, errors),
        "",
        "Safety",
        "------",
        _aligned_pairs(
            [
                ("read_only", True),
                ("writes_files", False),
                ("runs_ce", False),
            ]
        ),
    ]
    return "\n".join(lines).strip() + "\n"


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _component_status(component_statuses: list[dict[str, object]], component: str) -> str:
    for item in component_statuses:
        if item.get("component") == component:
            return _display(item.get("status"))
    return "ERROR"


def _overview_component_status(components: object, component_name: str) -> str:
    if isinstance(components, list):
        for item in components:
            if isinstance(item, dict) and item.get("component_name") == component_name:
                return _display(item.get("status"))
    return "ERROR"


def _status_key_result(summary: dict[str, object]) -> str:
    return f"overall={_display(summary.get('overall_status'))}; danger={_display(summary.get('danger_level'))}"


def _safety_key_result(data: dict[str, object]) -> str:
    return f"state={_display(data.get('safety_state'))}; arm={_display(data.get('arm_state'))}"


def _baseline_key_result(data: dict[str, object]) -> str:
    return f"result={_display(data.get('conclusion'))}; delta={_display(data.get('coverage_delta'))}"


def _case_key_result(data: dict[str, object]) -> str:
    current = _display(data.get("current_unique_known_true_addr_count"))
    target = _display(data.get("target_unique_known_true_addr_count"))
    return f"result={_display(data.get('conclusion'))}; unique={current}/{target}"


def _registry_key_result(data: dict[str, object]) -> str:
    return f"records={_display(data.get('parsed_records'))}; unique={_display(data.get('unique_known_true_addr_count'))}"


def _transaction_key_result(data: dict[str, object]) -> str:
    latest = _display(data.get("latest_transaction_type"))
    writes = _display(data.get("write_success_count"))
    blocked = _display(data.get("write_blocked_count"))
    return f"latest={latest}; write_success={writes}; write_blocked={blocked}"


def _recommendations_block(component_data: dict[str, dict[str, object]], warnings: list[str], errors: list[str]) -> str:
    return "\n".join(f"- {_escape_text(value)}" for value in _collect_recommendations(component_data, warnings, errors))


def _recommendations_text(component_data: dict[str, dict[str, object]], warnings: list[str], errors: list[str]) -> str:
    return "\n".join(f"- {_escape_text(value)}" for value in _collect_recommendations(component_data, warnings, errors))


def _collect_recommendations(component_data: dict[str, dict[str, object]], warnings: list[str], errors: list[str]) -> list[str]:
    values: list[str] = []
    status_summary = _as_dict(component_data.get("status-overview", {}).get("summary"))
    recommendation_sources = [
        status_summary.get("recommendation"),
        component_data.get("safety-doctor", {}).get("recommendation"),
        component_data.get("baseline-compare", {}).get("recommendation"),
        component_data.get("case-summary", {}).get("recommendation"),
        component_data.get("registry-summary", {}).get("recommendation"),
        component_data.get("transaction-summary", {}).get("recommendation"),
    ]
    for value in recommendation_sources:
        text = _display(value).strip()
        if text and text != "-" and text not in values:
            values.append(text)
    for warning in warnings:
        values.append(f"Warning: {warning}")
    for error in errors:
        values.append(f"Error: {error}")
    if not values:
        return ["No action recommended."]
    return values


def _basename(value: object) -> str:
    text = _display(value)
    if text == "-":
        return text
    return Path(text.replace("\\", "/")).name or text


def _aligned_pairs(rows: list[tuple[str, object]]) -> str:
    width = max(len(label) for label, _ in rows) if rows else 0
    return "\n".join(f"{label.ljust(width)}  {_display(value)}" for label, value in rows)


def _signed(value: object) -> object:
    if isinstance(value, int | float) and value > 0:
        return f"+{value}"
    return value


def _status_to_pass_fail(value: object) -> str:
    text = _display(value)
    if text in {
        "SAFE",
        "PASS",
        "OK",
        "DIAGNOSTIC_BASIC",
        "CASE_INTAKE_CLEAN",
        "BASELINE_CURRENT_OK",
        "BASELINE_COMPARE_PASS",
        "COVERAGE_OK",
        "REGISTRY_OK",
        "TRANSACTION_HISTORY_OK",
    }:
        return "PASS"
    if text in {"WARN", "WARNING", "ATTENTION"} or "WARN" in text:
        return "WARN"
    if text in {"ERROR", "FAIL"} or "FAIL" in text:
        return "FAIL"
    return text


def _single_report(*, report_type: str, markdown: str, status: str) -> ReportPreviewResult:
    return ReportPreviewResult(
        report_type=report_type,
        markdown=markdown,
        component_statuses=[{"component": report_type, "status": status}],
        warnings=[],
        errors=[],
    )


def _render_status_overview(result: object, *, generated_at: str, heading_level: int) -> str:
    data = result.to_dict()
    summary = data["summary"]
    lines = [
        _heading("Status Overview Report", heading_level),
        "",
        f"- generated_at: `{_escape_inline(generated_at)}`",
        "",
        _field_table(
            [
                ("overall_status", summary.get("overall_status")),
                ("safety_status", summary.get("safety_status")),
                ("next_run_type", summary.get("next_run_type")),
                ("danger_level", summary.get("danger_level")),
                ("diagnostic_status", summary.get("diagnostic_status")),
                ("case_intake_status", summary.get("case_intake_status")),
                ("baseline_compare_status", summary.get("baseline_compare_status")),
                ("case_summary_status", summary.get("case_summary_status")),
                ("warning_count", summary.get("warning_count")),
                ("danger_count", summary.get("danger_count")),
            ]
        ),
        "",
        _heading("Components", heading_level + 1),
        "",
        _markdown_table(
            ["component", "status", "summary", "recommendation"],
            [
                [
                    item.get("component_name"),
                    item.get("status"),
                    item.get("summary"),
                    item.get("recommendation"),
                ]
                for item in data.get("components", [])
            ],
        ),
        "",
        _heading("Recommendation", heading_level + 1),
        "",
        str(summary.get("recommendation") or "-"),
    ]
    return "\n".join(lines)


def _render_safety_doctor(result: object, *, generated_at: str, heading_level: int) -> str:
    data = result.to_dict()
    lines = [
        _heading("Safety Doctor Report", heading_level),
        "",
        f"- generated_at: `{_escape_inline(generated_at)}`",
        "",
        _field_table(
            [
                ("overall_status", data.get("overall_status")),
                ("safety_state", data.get("safety_state")),
                ("next_run_type", data.get("next_run_type")),
                ("danger_level", data.get("danger_level")),
                ("arm_state", data.get("arm_state")),
                ("warning_count", data.get("warning_count")),
                ("danger_count", data.get("danger_count")),
            ]
        ),
        "",
        _heading("Checks", heading_level + 1),
        "",
        _markdown_table(
            ["check", "status", "detail", "recommendation"],
            [
                [item.get("check_name"), item.get("status"), item.get("detail"), item.get("recommendation")]
                for item in data.get("checks", [])
            ],
        ),
        "",
        _heading("Recommendation", heading_level + 1),
        "",
        str(data.get("recommendation") or "-"),
    ]
    return "\n".join(lines)


def _render_baseline_compare(result: object, *, generated_at: str, heading_level: int) -> str:
    data = result.to_dict()
    return "\n".join(
        [
            _heading("Baseline Compare Report", heading_level),
            "",
            f"- generated_at: `{_escape_inline(generated_at)}`",
            "",
            _field_table(
                [
                    ("baseline_path", data.get("baseline_path")),
                    ("latest N", data.get("latest_n")),
                    ("profile", data.get("profile")),
                    ("baseline_unique_count", data.get("baseline_unique_known_true_addr_count")),
                    ("current_eligible_count", data.get("current_eligible_batch_count")),
                    ("current_success_count", data.get("current_success_count")),
                    ("current_unique_count", data.get("current_unique_known_true_addr_count")),
                    ("coverage_delta", data.get("coverage_delta")),
                    ("repeated_addr_summary", _repeated_addr_summary(data.get("repeated_known_true_addr"))),
                    ("conclusion", data.get("conclusion")),
                    ("recommendation", data.get("recommendation")),
                ]
            ),
        ]
    )


def _render_case_summary(result: object, *, generated_at: str, heading_level: int) -> str:
    data = result.to_dict()
    return "\n".join(
        [
            _heading("Case Summary Report", heading_level),
            "",
            f"- generated_at: `{_escape_inline(generated_at)}`",
            "",
            _field_table(
                [
                    ("latest N", data.get("latest_n")),
                    ("profile", data.get("profile")),
                    ("baseline_path", data.get("baseline_path")),
                    ("target_unique_count", data.get("target_unique_known_true_addr_count")),
                    ("current_eligible_count", data.get("current_eligible_batch_count")),
                    ("current_success_count", data.get("current_success_count")),
                    ("current_unique_count", data.get("current_unique_known_true_addr_count")),
                    ("coverage_delta", data.get("coverage_delta")),
                    ("repeated_addr_summary", _repeated_addr_summary(data.get("repeated_known_true_addr"))),
                    ("estimated_new_distinct_addr_needed", data.get("estimated_new_distinct_addr_needed")),
                    ("conclusion", data.get("conclusion")),
                    ("recommendation", data.get("recommendation")),
                ]
            ),
        ]
    )


def _render_registry_summary(result: object, *, generated_at: str, heading_level: int) -> str:
    data = result.to_dict()
    lines = [
        _heading("Registry Summary Report", heading_level),
        "",
        f"- generated_at: `{_escape_inline(generated_at)}`",
        "",
        _field_table(
            [
                ("registry_path", data.get("registry_path")),
                ("record_count", data.get("record_count")),
                ("parsed_records", data.get("parsed_records")),
                ("malformed_lines", data.get("malformed_lines")),
                ("unique_known_true_addr_count", data.get("unique_known_true_addr_count")),
                ("baseline_eligible_count", data.get("baseline_eligible_count")),
                ("execution_batch_count", data.get("execution_batch_count")),
                ("latest_batch_id", data.get("latest_batch_id")),
                ("conclusion", data.get("conclusion")),
                ("recommendation", data.get("recommendation")),
            ]
        ),
        "",
        _heading("Classification Counts", heading_level + 1),
        "",
        _count_table(data.get("classification_counts")),
        "",
        _heading("Profile Counts", heading_level + 1),
        "",
        _count_table(data.get("profile_counts")),
    ]
    return "\n".join(lines)


def _render_transaction_summary(result: object, *, generated_at: str, heading_level: int) -> str:
    data = result.to_dict()
    lines = [
        _heading("Transaction Summary Report", heading_level),
        "",
        f"- generated_at: `{_escape_inline(generated_at)}`",
        "",
        _field_table(
            [
                ("parsed_batches", data.get("parsed_batches")),
                ("parsed_registry_records", data.get("parsed_registry_records")),
                ("transaction_record_count", data.get("transaction_record_count")),
                ("write_success_count", data.get("write_success_count")),
                ("write_blocked_count", data.get("write_blocked_count")),
                ("restore_success_count", data.get("restore_success_count")),
                ("restore_blocked_count", data.get("restore_blocked_count")),
                ("dry_run_count", data.get("dry_run_count")),
                ("detect_only_count", data.get("detect_only_count")),
                ("latest_transaction_batch_id", data.get("latest_transaction_batch_id")),
                ("latest_transaction_type", data.get("latest_transaction_type")),
                ("latest_known_true_addr", data.get("latest_known_true_addr")),
                ("conclusion", data.get("conclusion")),
                ("recommendation", data.get("recommendation")),
            ]
        ),
        "",
        _heading("Transaction Type Counts", heading_level + 1),
        "",
        _count_table(data.get("transaction_type_counts")),
        "",
        _heading("Execution Outcome Counts", heading_level + 1),
        "",
        _count_table(data.get("execution_outcome_counts")),
    ]
    return "\n".join(lines)


def _field_table(rows: list[tuple[str, object]]) -> str:
    return _markdown_table(["Field", "Value"], [[label, value] for label, value in rows])


def _count_table(counts: object) -> str:
    if not isinstance(counts, dict) or not counts:
        return "No counts."
    return _markdown_table(["Value", "Count"], [[key, value] for key, value in counts.items()])


def _markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = [
        "| " + " | ".join(_escape_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    if not rows:
        lines.append("| " + " | ".join("-" for _ in headers) + " |")
        return "\n".join(lines)
    for row in rows:
        lines.append("| " + " | ".join(_escape_cell(value) for value in row) + " |")
    return "\n".join(lines)


def _repeated_addr_summary(value: object) -> str:
    if not value:
        return "none"
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(f"{item.get('known_true_addr')} count {item.get('count')}")
        return "; ".join(parts) if parts else "none"
    return str(value)


def _normalize_report_type(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in REPORT_TYPES:
        raise ReportPreviewError(f"unknown report type: {value}; expected one of {', '.join(REPORT_TYPES)}")
    return normalized


def _heading(text: str, level: int) -> str:
    return f"{'#' * max(level, 1)} {text}"


def _title(value: str) -> str:
    return value.replace("-", " ").title()


def _escape_cell(value: object) -> str:
    return _escape_text(_display(value)).replace("|", "\\|")


def _escape_inline(value: object) -> str:
    return _display(value).replace("`", "\\`")


def _escape_text(value: object) -> str:
    return _display(value).replace("\r\n", " ").replace("\n", " ")


def _display(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _generated_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
