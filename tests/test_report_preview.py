from __future__ import annotations

from types import SimpleNamespace

import pytest

from armedforces_tool import report_preview
from armedforces_tool.command_inventory import list_commands
from armedforces_tool.report_preview import ReportPreviewError, preview_report


class _FakeResult(SimpleNamespace):
    def __init__(self, data: dict[str, object], **attrs: object) -> None:
        super().__init__(**attrs)
        self._data = data

    def to_dict(self) -> dict[str, object]:
        return self._data


def _status_overview() -> _FakeResult:
    return _FakeResult(
        {
            "summary": {
                "overall_status": "SAFE",
                "safety_status": "SAFE",
                "next_run_type": "detect_only",
                "danger_level": "SAFE",
                "diagnostic_status": "DIAGNOSTIC_BASIC",
                "case_intake_status": "CASE_INTAKE_CLEAN",
                "baseline_compare_status": "BASELINE_COMPARE_PASS",
                "case_summary_status": "COVERAGE_OK",
                "warning_count": 0,
                "danger_count": 0,
                "recommendation": "all clear",
            },
            "components": [
                {
                    "component_name": "safety_doctor",
                    "status": "PASS",
                    "summary": "overall=SAFE",
                    "recommendation": "no action",
                }
            ],
            "warnings": [],
            "dangers": [],
        },
        overall_status="SAFE",
    )


def _safety_doctor() -> _FakeResult:
    return _FakeResult(
        {
            "overall_status": "SAFE",
            "safety_state": "SAFE_DETECT_ONLY",
            "next_run_type": "detect_only",
            "danger_level": "SAFE",
            "arm_state": "not_armed",
            "warning_count": 0,
            "danger_count": 0,
            "recommendation": "safe",
            "checks": [
                {
                    "check_name": "config file",
                    "status": "PASS",
                    "detail": "exists=True",
                    "recommendation": "no action",
                }
            ],
        },
        overall_status="SAFE",
    )


def _baseline_compare() -> _FakeResult:
    return _FakeResult(
        {
            "baseline_path": "baseline.md",
            "latest_n": 20,
            "profile": "full",
            "baseline_unique_known_true_addr_count": 13,
            "current_eligible_batch_count": 20,
            "current_success_count": 20,
            "current_unique_known_true_addr_count": 14,
            "coverage_delta": 1,
            "repeated_known_true_addr": [{"known_true_addr": "0xAAA", "count": 2}],
            "conclusion": "BASELINE_COMPARE_PASS",
            "recommendation": "coverage ok",
        },
        conclusion="BASELINE_COMPARE_PASS",
    )


def _case_summary() -> _FakeResult:
    return _FakeResult(
        {
            "latest_n": 20,
            "profile": "full",
            "baseline_path": "baseline.md",
            "target_unique_known_true_addr_count": 13,
            "current_eligible_batch_count": 20,
            "current_success_count": 20,
            "current_unique_known_true_addr_count": 14,
            "coverage_delta": 1,
            "repeated_known_true_addr": [{"known_true_addr": "0xAAA", "count": 2}],
            "estimated_new_distinct_addr_needed": 0,
            "conclusion": "COVERAGE_OK",
            "recommendation": "coverage ok",
        },
        conclusion="COVERAGE_OK",
    )


def _registry_summary() -> _FakeResult:
    return _FakeResult(
        {
            "registry_path": "case_registry.jsonl",
            "record_count": 39,
            "parsed_records": 39,
            "malformed_lines": 0,
            "unique_known_true_addr_count": 22,
            "baseline_eligible_count": 17,
            "execution_batch_count": 1,
            "latest_batch_id": "20260614-232227",
            "conclusion": "REGISTRY_OK",
            "recommendation": "registry ok",
            "classification_counts": {"success": 34},
            "profile_counts": {"full": 36, "quick": 3},
        },
        conclusion="REGISTRY_OK",
    )


def _transaction_summary() -> _FakeResult:
    return _FakeResult(
        {
            "parsed_batches": 96,
            "parsed_registry_records": 39,
            "transaction_record_count": 96,
            "write_success_count": 3,
            "write_blocked_count": 6,
            "restore_success_count": 1,
            "restore_blocked_count": 1,
            "dry_run_count": 3,
            "detect_only_count": 82,
            "latest_transaction_batch_id": "20260614-232227",
            "latest_transaction_type": "detect_only",
            "latest_known_true_addr": "0xCE061C7D48",
            "conclusion": "TRANSACTION_HISTORY_OK",
            "recommendation": "transactions ok",
            "transaction_type_counts": {"detect_only": 82, "write_success": 3},
            "execution_outcome_counts": {"execution_disabled": 82},
        },
        conclusion="TRANSACTION_HISTORY_OK",
    )


def _install_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(report_preview, "analyze_status_overview", lambda **kwargs: _status_overview())
    monkeypatch.setattr(report_preview, "analyze_safety_doctor", lambda **kwargs: _safety_doctor())
    monkeypatch.setattr(report_preview, "analyze_baseline_compare", lambda **kwargs: _baseline_compare())
    monkeypatch.setattr(report_preview, "analyze_case_summary", lambda **kwargs: _case_summary())
    monkeypatch.setattr(report_preview, "analyze_registry_summary", lambda **kwargs: _registry_summary())
    monkeypatch.setattr(report_preview, "analyze_transaction_summary", lambda **kwargs: _transaction_summary())


def test_status_overview_markdown_includes_title_and_overall_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    result = preview_report(report_type="status-overview")

    assert "# Status Overview Report" in result.markdown
    assert "overall_status" in result.markdown
    assert "SAFE" in result.markdown


def test_baseline_compare_markdown_includes_coverage_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    result = preview_report(report_type="baseline-compare")

    assert "# Baseline Compare Report" in result.markdown
    assert "coverage_delta" in result.markdown
    assert "BASELINE_COMPARE_PASS" in result.markdown


def test_case_summary_markdown_includes_coverage_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    result = preview_report(report_type="case-summary")

    assert "# Case Summary Report" in result.markdown
    assert "COVERAGE_OK" in result.markdown


def test_registry_summary_markdown_includes_registry_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    result = preview_report(report_type="registry-summary")

    assert "# Registry Summary Report" in result.markdown
    assert "record_count" in result.markdown
    assert "Classification Counts" in result.markdown


def test_transaction_summary_markdown_includes_transaction_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    result = preview_report(report_type="transaction-summary")

    assert "# Transaction Summary Report" in result.markdown
    assert "write_success_count" in result.markdown
    assert "Transaction Type Counts" in result.markdown


def test_full_status_includes_multiple_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    result = preview_report(report_type="full-status")

    assert "# Full Status Report" in result.markdown
    assert "## Status Overview Report" in result.markdown
    assert "## Safety Doctor Report" in result.markdown
    assert "## Transaction Summary Report" in result.markdown
    assert len(result.component_statuses) == 6


def test_invalid_report_type_raises_clear_error() -> None:
    with pytest.raises(ReportPreviewError, match="unknown report type"):
        preview_report(report_type="not-a-report")


def test_json_shape_includes_markdown_and_read_only_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    data = preview_report(report_type="status-overview").to_dict()

    assert data["report_type"] == "status-overview"
    assert data["markdown"].startswith("# Status Overview Report")
    assert data["read_only"] is True
    assert data["writes_files"] is False
    assert data["runs_ce"] is False


def test_preview_does_not_create_output_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _install_fakes(monkeypatch)
    monkeypatch.chdir(tmp_path)

    preview_report(report_type="full-status")

    assert list(tmp_path.glob("*.md")) == []


def test_command_inventory_includes_report_preview_only() -> None:
    result = list_commands(category="report")

    assert result.total_count == 1
    assert result.records[0].command == "report preview"
    assert result.records[0].read_only is True
    assert result.records[0].writes_files is False
    assert result.records[0].runs_ce is False
    assert "report export" not in {record.command for record in list_commands().records}
