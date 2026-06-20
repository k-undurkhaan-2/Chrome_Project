from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from armedforces_tool import report_export
from armedforces_tool.command_inventory import list_commands
from armedforces_tool.report_export import format_report_export_dry_run, plan_report_export
from armedforces_tool.report_manifest import analyze_report_manifest


@pytest.fixture(autouse=True)
def _fake_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        report_export,
        "preview_report",
        lambda **kwargs: SimpleNamespace(markdown="# Fake Report\n\nbody\n"),
    )


def _ts() -> datetime:
    return datetime(2026, 6, 15, 12, 34, 56, tzinfo=timezone.utc)


def test_real_export_writes_approved_markdown_file(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/full_status.md",
        project_root=tmp_path,
    )

    target = tmp_path / "reports" / "python_tooling" / "full_status.md"
    assert result.conclusion == "REPORT_EXPORT_OK"
    assert result.would_write is True
    assert result.wrote_file is True
    assert result.writes_files is True
    assert result.read_only is False
    assert result.bytes_written == len("# Fake Report\n\nbody\n".encode("utf-8"))
    assert target.read_text(encoding="utf-8") == "# Fake Report\n\nbody\n"


def test_real_export_writes_docs_approved_root(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="status-overview",
        dry_run=False,
        out="docs/reports/python_tooling/status.md",
        project_root=tmp_path,
    )

    target = tmp_path / "docs" / "reports" / "python_tooling" / "status.md"
    assert result.conclusion == "REPORT_EXPORT_OK"
    assert result.wrote_file is True
    assert target.exists()


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


def test_record_manifest_dry_run_plans_manifest_and_writes_nothing(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=True,
        out="reports/python_tooling/full_status_manifest.md",
        project_root=tmp_path,
        record_manifest=True,
    )

    assert result.conclusion == "REPORT_EXPORT_DRY_RUN_OK"
    assert result.record_manifest is True
    assert result.would_write_report is True
    assert result.would_write_manifest is True
    assert result.planned_report_path is not None
    assert result.planned_manifest_path == "reports/python_tooling/manifest.jsonl"
    assert result.planned_manifest_entry is not None
    assert result.planned_manifest_entry["schema_version"] == "1"
    assert result.planned_manifest_entry["report_type"] == "full-status"
    assert result.planned_manifest_entry["output_path"] == "reports/python_tooling/full_status_manifest.md"
    assert result.planned_manifest_entry["output_root"] == "reports/python_tooling"
    assert result.planned_manifest_entry["dry_run"] is False
    assert result.planned_manifest_entry["status"] == "planned_success"
    assert result.planned_manifest_entry["planned_file_size"] == len("# Fake Report\n\nbody\n".encode("utf-8"))
    assert result.read_only is True
    assert result.writes_files is False
    assert not (tmp_path / "reports").exists()


def test_record_manifest_dry_run_json_shape_contains_entry(tmp_path: Path) -> None:
    data = plan_report_export(
        report_type="full-status",
        dry_run=True,
        out="reports/python_tooling/full_status_manifest.md",
        project_root=tmp_path,
        record_manifest=True,
    ).to_dict()

    assert data["record_manifest"] is True
    assert data["would_write_report"] is True
    assert data["would_write_manifest"] is True
    assert data["planned_manifest_path"] == "reports/python_tooling/manifest.jsonl"
    assert data["planned_manifest_entry"]["report_id"].startswith("planned-")
    assert data["planned_manifest_entry"]["planned_sha256"] == "would_compute_after_write"
    assert not (tmp_path / "reports").exists()


def test_record_manifest_real_export_writes_report_and_manifest(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/full_status_manifest.md",
        project_root=tmp_path,
        record_manifest=True,
    )

    target = tmp_path / "reports" / "python_tooling" / "full_status_manifest.md"
    manifest = tmp_path / "reports" / "python_tooling" / "manifest.jsonl"
    assert result.conclusion == "REPORT_EXPORT_OK"
    assert result.wrote_file is True
    assert result.manifest_written is True
    assert result.manifest_path == "reports/python_tooling/manifest.jsonl"
    assert result.writes_files is True
    assert result.read_only is False
    assert target.read_text(encoding="utf-8") == "# Fake Report\n\nbody\n"
    assert manifest.exists()

    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["schema_version"] == "1"
    assert entry["report_type"] == "full-status"
    assert entry["output_path"] == "reports/python_tooling/full_status_manifest.md"
    assert entry["output_root"] == "reports/python_tooling"
    assert entry["file_size"] == target.stat().st_size
    assert entry["sha256"]
    assert entry["dry_run"] is False
    assert entry["status"] == "success"

    verify = analyze_report_manifest(action="verify", project_root=tmp_path)
    assert verify.status == "OK"
    assert verify.entry_count == 1
    assert verify.missing_report_count == 0


def test_record_manifest_with_manifest_out_writes_isolated_manifest_only(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/full_status_manifest.md",
        project_root=tmp_path,
        record_manifest=True,
        manifest_out="reports/python_tooling/custom_manifest.jsonl",
    )

    target = tmp_path / "reports" / "python_tooling" / "full_status_manifest.md"
    custom_manifest = tmp_path / "reports" / "python_tooling" / "custom_manifest.jsonl"
    default_manifest = tmp_path / "reports" / "python_tooling" / "manifest.jsonl"
    assert result.conclusion == "REPORT_EXPORT_OK"
    assert result.wrote_file is True
    assert result.manifest_written is True
    assert result.manifest_path == "reports/python_tooling/custom_manifest.jsonl"
    assert result.writes_files is True
    assert target.exists()
    assert custom_manifest.exists()
    assert not default_manifest.exists()

    text = format_report_export_dry_run(result)
    assert "REPORT_EXPORT_OK" in text
    assert "WRITE_COMPLETE" in text
    assert "MANIFEST_RECORDED" in text
    assert "APPROVED_ROOT" in text
    assert "CE_NOT_RUN" in text
    assert "WRAPPER_UNSUPPORTED" in text
    assert "NO_FILES_WRITTEN" not in text
    assert "MANIFEST_NOT_WRITTEN" not in text
    assert "BUNDLE_EXPORT_COMPLETE" not in text
    assert "BUNDLE_NOT_CREATED" not in text
    assert "ZIP_UNSUPPORTED" not in text

    lines = custom_manifest.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["command"].endswith("--record-manifest --manifest-out reports/python_tooling/custom_manifest.jsonl")
    assert entry["output_path"] == "reports/python_tooling/full_status_manifest.md"


def test_manifest_out_without_record_manifest_rejects_before_write(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/full_status.md",
        project_root=tmp_path,
        manifest_out="reports/python_tooling/custom_manifest.jsonl",
    )

    assert result.conclusion == "REPORT_EXPORT_REJECTED"
    assert any("--manifest-out requires --record-manifest" in error for error in result.errors)
    assert result.wrote_file is False
    assert result.manifest_written is False
    assert result.would_write_report is False
    assert result.would_write_manifest is False
    assert not (tmp_path / "reports").exists()
    assert not (tmp_path / "reports" / "python_tooling" / "full_status.md").exists()
    assert not (tmp_path / "reports" / "python_tooling" / "custom_manifest.jsonl").exists()
    assert not (tmp_path / "reports" / "python_tooling" / "manifest.jsonl").exists()

    text = format_report_export_dry_run(result)
    assert "Invalid Option Combination" in text
    assert "INVALID_OPTION_COMBINATION" in text
    assert "NO_FILES_WRITTEN" in text
    assert "--manifest-out" in text
    assert "--record-manifest" in text
    assert "REPORT_EXPORT_REJECTED" in text
    for forbidden in [
        "REPORT_EXPORT_OK",
        "WRITE_COMPLETE",
        "MANIFEST_RECORDED",
        "BUNDLE_EXPORT_COMPLETE",
        "BUNDLE_EXPORT_OK",
        "SOURCE_UNCHANGED",
        "APPROVED_ROOT",
    ]:
        assert forbidden not in text


def test_manifest_out_outside_root_rejects_before_write(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/full_status.md",
        project_root=tmp_path,
        record_manifest=True,
        manifest_out="outside/custom_manifest.jsonl",
    )

    assert result.conclusion == "REPORT_EXPORT_REJECTED"
    assert any("manifest path must be under reports/python_tooling" in error for error in result.errors)
    assert result.wrote_file is False
    assert result.manifest_written is False
    assert not (tmp_path / "reports").exists()
    assert not (tmp_path / "outside").exists()

    text = format_report_export_dry_run(result)
    assert "PATH_GUARD_REJECTED" in text
    assert "OUTSIDE_APPROVED_ROOT" in text
    assert "NO_FILES_WRITTEN" in text
    assert "--manifest-out" in text
    assert "manifest path must be under reports/python_tooling" in text
    for forbidden in [
        "REPORT_EXPORT_OK",
        "WRITE_COMPLETE",
        "MANIFEST_RECORDED",
        "BUNDLE_EXPORT_COMPLETE",
        "BUNDLE_EXPORT_OK",
        "SOURCE_MISSING",
        "SOURCE_INVALID",
        "OVERWRITE_UNSUPPORTED",
        "ZIP_UNSUPPORTED",
    ]:
        assert forbidden not in text


def test_manifest_out_protected_path_rejects_before_write(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/full_status.md",
        project_root=tmp_path,
        record_manifest=True,
        manifest_out="log/custom_manifest.jsonl",
    )

    assert result.conclusion == "REPORT_EXPORT_REJECTED"
    assert any("manifest path is protected" in error for error in result.errors)
    assert result.wrote_file is False
    assert result.manifest_written is False
    assert not (tmp_path / "reports").exists()
    assert not (tmp_path / "log").exists()


def test_manifest_out_default_manifest_path_rejects_before_write(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/full_status.md",
        project_root=tmp_path,
        record_manifest=True,
        manifest_out="reports/python_tooling/manifest.jsonl",
    )

    assert result.conclusion == "REPORT_EXPORT_REJECTED"
    assert any("must not target the default" in error for error in result.errors)
    assert result.wrote_file is False
    assert result.manifest_written is False
    assert not (tmp_path / "reports").exists()


def test_record_manifest_does_not_change_non_record_export_behavior(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/full_status.md",
        project_root=tmp_path,
    )

    target = tmp_path / "reports" / "python_tooling" / "full_status.md"
    assert result.conclusion == "REPORT_EXPORT_OK"
    assert result.record_manifest is False
    assert result.wrote_file is True
    assert result.writes_files is True
    assert target.read_text(encoding="utf-8") == "# Fake Report\n\nbody\n"


def test_record_manifest_bad_path_rejected(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=True,
        out="outside/full_status.md",
        project_root=tmp_path,
        record_manifest=True,
    )

    assert result.conclusion == "REPORT_EXPORT_DRY_RUN_REJECTED"
    assert result.record_manifest is True
    assert result.planned_manifest_entry is None
    assert not (tmp_path / "outside").exists()


def test_record_manifest_traversal_rejected(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=True,
        out="../full_status.md",
        project_root=tmp_path,
        record_manifest=True,
    )

    assert result.conclusion == "REPORT_EXPORT_DRY_RUN_REJECTED"
    assert any("path traversal" in error for error in result.errors)
    assert result.planned_manifest_entry is None


def test_record_manifest_protected_path_rejected(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=True,
        out="log/full_status.md",
        project_root=tmp_path,
        record_manifest=True,
    )

    assert result.conclusion == "REPORT_EXPORT_DRY_RUN_REJECTED"
    assert any("protected" in error for error in result.errors)
    assert result.planned_manifest_entry is None


def test_record_manifest_docs_reports_policy_rejects_before_write(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=True,
        out="docs/reports/python_tooling/full_status_manifest.md",
        project_root=tmp_path,
        record_manifest=True,
    )

    assert result.conclusion == "MANIFEST_OUTPUT_ROOT_UNSUPPORTED"
    assert result.would_write_report is False
    assert result.would_write_manifest is False
    assert result.planned_manifest_path == "reports/python_tooling/manifest.jsonl"
    assert result.planned_manifest_entry is None
    assert not (tmp_path / "docs" / "reports").exists()
    assert not (tmp_path / "reports").exists()


def test_record_manifest_real_docs_reports_rejects_before_write(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="docs/reports/python_tooling/full_status_manifest.md",
        project_root=tmp_path,
        record_manifest=True,
    )

    assert result.conclusion == "MANIFEST_OUTPUT_ROOT_UNSUPPORTED"
    assert result.wrote_file is False
    assert result.manifest_written is False
    assert not (tmp_path / "docs" / "reports").exists()
    assert not (tmp_path / "reports").exists()


def test_record_manifest_existing_corrupt_manifest_rejects_before_report_write(tmp_path: Path) -> None:
    manifest = tmp_path / "reports" / "python_tooling" / "manifest.jsonl"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{not json}\n", encoding="utf-8")

    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/full_status_manifest.md",
        project_root=tmp_path,
        record_manifest=True,
    )

    assert result.conclusion == "MANIFEST_PREFLIGHT_REJECTED"
    assert result.wrote_file is False
    assert result.manifest_written is False
    assert not (tmp_path / "reports" / "python_tooling" / "full_status_manifest.md").exists()
    assert manifest.read_text(encoding="utf-8") == "{not json}\n"


def test_record_manifest_duplicate_report_id_rejects_before_report_write(tmp_path: Path) -> None:
    target = tmp_path / "reports" / "python_tooling" / "full_status_manifest.md"
    first = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/full_status_manifest.md",
        project_root=tmp_path,
        record_manifest=True,
        generated_at=_ts(),
    )
    assert first.conclusion == "REPORT_EXPORT_OK"
    target.unlink()

    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/full_status_manifest.md",
        project_root=tmp_path,
        record_manifest=True,
        generated_at=_ts(),
    )

    assert result.conclusion == "MANIFEST_PREFLIGHT_REJECTED"
    assert result.wrote_file is False
    assert result.manifest_written is False
    assert not target.exists()


def test_record_manifest_force_appends_new_entry_without_mutating_old_entry(tmp_path: Path) -> None:
    target = tmp_path / "reports" / "python_tooling" / "full_status_manifest.md"
    target.parent.mkdir(parents=True)
    target.write_text("old", encoding="utf-8")
    old_entry = {
        "schema_version": "1",
        "report_id": "old-report",
        "report_type": "full-status",
        "created_at": "2026-06-15T00:00:00Z",
        "output_path": "reports/python_tooling/old.md",
        "output_root": "reports/python_tooling",
        "file_size": 3,
        "sha256": "old",
        "command": "old",
        "dry_run": False,
        "status": "success",
    }
    manifest = tmp_path / "reports" / "python_tooling" / "manifest.jsonl"
    manifest.write_text(json.dumps(old_entry, sort_keys=True) + "\n", encoding="utf-8")

    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/full_status_manifest.md",
        project_root=tmp_path,
        record_manifest=True,
        force=True,
    )

    assert result.conclusion == "REPORT_EXPORT_OK"
    assert result.overwritten is True
    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == old_entry
    assert json.loads(lines[1])["status"] == "success"
    assert target.read_text(encoding="utf-8") == "# Fake Report\n\nbody\n"


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="../full_status.md",
        project_root=tmp_path,
    )

    assert result.conclusion == "REPORT_EXPORT_REJECTED"
    assert result.path_safety_status == "PATH_REJECTED"
    assert any("path traversal" in error for error in result.errors)


def test_outside_root_is_rejected(tmp_path: Path) -> None:
    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out=str(tmp_path / "outside" / "full_status.md"),
        project_root=tmp_path,
    )

    assert result.conclusion == "REPORT_EXPORT_REJECTED"
    assert any("approved" in error or "must be under" in error for error in result.errors)
    assert result.wrote_file is False
    assert not (tmp_path / "outside").exists()

    formatted = format_report_export_dry_run(result)
    assert "PATH_GUARD_REJECTED" in formatted
    assert "OUTSIDE_APPROVED_ROOT" in formatted
    assert "NO_FILES_WRITTEN" in formatted
    assert "--out" in formatted
    for forbidden in [
        "REPORT_EXPORT_OK",
        "WRITE_COMPLETE",
        "MANIFEST_RECORDED",
        "BUNDLE_EXPORT_COMPLETE",
        "BUNDLE_EXPORT_OK",
        "SOURCE_MISSING",
        "SOURCE_INVALID",
        "OVERWRITE_UNSUPPORTED",
        "ZIP_UNSUPPORTED",
    ]:
        assert forbidden not in formatted


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


def test_real_export_existing_target_without_force_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "reports" / "python_tooling" / "existing.md"
    target.parent.mkdir(parents=True)
    target.write_text("existing", encoding="utf-8")
    before = target.read_bytes()

    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/existing.md",
        project_root=tmp_path,
        force=False,
    )
    formatted = format_report_export_dry_run(result)

    assert result.conclusion == "REPORT_EXPORT_OVERWRITE_REJECTED"
    assert result.wrote_file is False
    assert result.writes_files is False
    assert "OVERWRITE_UNSUPPORTED" in formatted
    assert "NO_FILES_WRITTEN" in formatted
    assert "FORCE_UNSUPPORTED" not in formatted
    for token in ["REPORT_EXPORT_OK", "WRITE_COMPLETE", "MANIFEST_RECORDED", "BUNDLE_EXPORT_COMPLETE", "BUNDLE_EXPORT_OK"]:
        assert token not in formatted
    assert target.read_text(encoding="utf-8") == "existing"
    assert target.read_bytes() == before


def test_real_export_existing_target_with_force_overwrites(tmp_path: Path) -> None:
    target = tmp_path / "reports" / "python_tooling" / "existing.md"
    target.parent.mkdir(parents=True)
    target.write_text("existing", encoding="utf-8")

    result = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/existing.md",
        project_root=tmp_path,
        force=True,
    )

    assert result.conclusion == "REPORT_EXPORT_OK"
    assert result.target_exists_before is True
    assert result.overwritten is True
    assert result.wrote_file is True
    assert target.read_text(encoding="utf-8") == "# Fake Report\n\nbody\n"


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
    assert data["wrote_file"] is False
    assert data["read_only"] is True
    assert data["writes_files"] is False
    assert data["runs_ce"] is False
    assert data["path_safety_status"] == "PATH_OK"


def test_json_shape_reports_real_write_metadata(tmp_path: Path) -> None:
    data = plan_report_export(
        report_type="full-status",
        dry_run=False,
        out="reports/python_tooling/full_status.md",
        project_root=tmp_path,
    ).to_dict()

    assert data["report_type"] == "full-status"
    assert data["dry_run"] is False
    assert data["would_write"] is True
    assert data["wrote_file"] is True
    assert data["read_only"] is False
    assert data["writes_files"] is True
    assert data["runs_ce"] is False
    assert data["conclusion"] == "REPORT_EXPORT_OK"


def test_command_inventory_includes_report_export_modes() -> None:
    result = list_commands(category="report")
    commands = {record.command for record in result.records}
    records = {record.command: record for record in result.records}

    assert "report preview" in commands
    assert "report export --dry-run" in commands
    assert "report export" in commands
    assert records["report export --dry-run"].writes_files is False
    assert records["report export"].writes_files is True
    assert records["report bundle export"].writes_files is True
    assert records["report export"].read_only is False
    assert records["report export"].runs_ce is False
    assert "--record-manifest" in records["report export --dry-run"].parameters
    assert "--record-manifest" in records["report export"].parameters
    assert "--manifest-out" in records["report export --dry-run"].parameters
    assert "--manifest-out" in records["report export"].parameters
    assert result.to_dict()["summary"]["writes_files_count"] == 2
    assert result.to_dict()["summary"]["runs_ce_count"] == 0
