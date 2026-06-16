from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from armedforces_tool import report_export
from armedforces_tool.command_inventory import list_commands
from armedforces_tool.report_export import plan_report_export


@pytest.fixture(autouse=True)
def _fake_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        report_export,
        "preview_report",
        lambda **kwargs: SimpleNamespace(markdown="# Fake Report\n\nbody\n"),
    )


def _ts() -> datetime:
    return datetime(2026, 6, 15, 12, 34, 56, tzinfo=timezone.utc)


def test_export_without_dry_run_is_rejected(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/full_status.md",
        project_root=tmp_path,
    )

    assert result.conclusion == "REPORT_EXPORT_NOT_IMPLEMENTED"
    assert result.would_write is False
    assert result.writes_files is False
    assert result.errors


def test_dry_run_with_approved_output_dir_is_accepted(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="status-overview",
        dry_run=True,
        output_dir="reports/python_tooling",
        project_root=tmp_path,
        generated_at=_ts(),
    )

    assert result.conclusion == "REPORT_EXPORT_DRY_RUN_OK"
    assert result.path_safety_status == "PATH_OK"
    assert result.target_path is not None
    assert result.target_path.endswith("reports\\python_tooling\\status_overview_20260615-123456.md") or result.target_path.endswith(
        "reports/python_tooling/status_overview_20260615-123456.md"
    )
    assert result.would_write is False
    assert not (tmp_path / "reports" / "python_tooling").exists()


def test_dry_run_with_approved_out_is_accepted(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=True,
        out="docs/reports/python_tooling/full_status_test.md",
        project_root=tmp_path,
    )

    assert result.conclusion == "REPORT_EXPORT_DRY_RUN_OK"
    assert result.path_safety_status == "PATH_OK"
    assert result.approved_output_root is not None
    assert result.target_exists is False
    assert result.would_overwrite is False
    assert not (tmp_path / "docs" / "reports").exists()


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=True,
        out="../full_status.md",
        project_root=tmp_path,
    )

    assert result.conclusion == "REPORT_EXPORT_DRY_RUN_REJECTED"
    assert result.path_safety_status == "PATH_REJECTED"
    assert any("path traversal" in error for error in result.errors)


def test_outside_root_is_rejected(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=True,
        out=str(tmp_path / "outside" / "full_status.md"),
        project_root=tmp_path,
    )

    assert result.conclusion == "REPORT_EXPORT_DRY_RUN_REJECTED"
    assert any("approved" in error or "must be under" in error for error in result.errors)


def test_protected_path_is_rejected(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=True,
        out="log/full_status.md",
        project_root=tmp_path,
    )

    assert result.conclusion == "REPORT_EXPORT_DRY_RUN_REJECTED"
    assert any("protected" in error for error in result.errors)


def test_non_markdown_extension_is_rejected(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=True,
        out="reports/python_tooling/full_status.txt",
        project_root=tmp_path,
    )

    assert result.conclusion == "REPORT_EXPORT_DRY_RUN_REJECTED"
    assert any(".md" in error for error in result.errors)


def test_existing_target_without_force_warns_and_writes_nothing(tmp_path: Path) -> None:
    target = tmp_path / "reports" / "python_tooling" / "existing.md"
    target.parent.mkdir(parents=True)
    target.write_text("existing", encoding="utf-8")

    result = plan_report_export(
        report_type="full-status",
        dry_run=True,
        out="reports/python_tooling/existing.md",
        project_root=tmp_path,
        force=False,
    )

    assert result.conclusion == "REPORT_EXPORT_DRY_RUN_OK"
    assert result.path_safety_status == "PATH_WARN"
    assert result.target_exists is True
    assert result.would_overwrite is False
    assert target.read_text(encoding="utf-8") == "existing"


def test_force_changes_metadata_only_and_writes_nothing(tmp_path: Path) -> None:
    target = tmp_path / "reports" / "python_tooling" / "existing.md"
    target.parent.mkdir(parents=True)
    target.write_text("existing", encoding="utf-8")

    result = plan_report_export(
        report_type="full-status",
        dry_run=True,
        out="reports/python_tooling/existing.md",
        project_root=tmp_path,
        force=True,
    )

    assert result.conclusion == "REPORT_EXPORT_DRY_RUN_OK"
    assert result.path_safety_status == "PATH_OK"
    assert result.target_exists is True
    assert result.would_overwrite is True
    assert target.read_text(encoding="utf-8") == "existing"


def test_json_shape_reports_read_only_dry_run(tmp_path: Path) -> None:
    data = plan_report_export(
        report_type="full-status",
        dry_run=True,
        out="reports/python_tooling/full_status.md",
        project_root=tmp_path,
    ).to_dict()

    assert data["report_type"] == "full-status"
    assert data["dry_run"] is True
    assert data["would_write"] is False
    assert data["read_only"] is True
    assert data["writes_files"] is False
    assert data["runs_ce"] is False
    assert data["path_safety_status"] == "PATH_OK"


def test_command_inventory_includes_report_export_dry_run() -> None:
    result = list_commands(category="report")
    commands = {record.command for record in result.records}

    assert "report preview" in commands
    assert "report export --dry-run" in commands
    assert result.to_dict()["summary"]["writes_files_count"] == 0
    assert result.to_dict()["summary"]["runs_ce_count"] == 0
