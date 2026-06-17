from __future__ import annotations

import json
from pathlib import Path

from armedforces_tool.command_inventory import list_commands, show_command
from armedforces_tool.report_bundle import analyze_report_bundle, plan_report_bundle_export


def _manifest_path(project_root: Path) -> Path:
    return project_root / "reports" / "python_tooling" / "manifest.jsonl"


def _write_report(project_root: Path, name: str = "full_status_fixture.md") -> str:
    report = project_root / "reports" / "python_tooling" / name
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("# report\n", encoding="utf-8")
    return f"reports/python_tooling/{name}"


def _manifest_entry(*, report_id: str = "full-status-1", output_path: str) -> dict[str, object]:
    return {
        "report_id": report_id,
        "report_type": "full-status",
        "created_at": "2026-06-16T12:00:00Z",
        "output_path": output_path,
        "output_root": "reports/python_tooling",
        "file_size": 9,
        "sha256": "0" * 64,
        "command": "python -m armedforces_tool report export --type full-status --out reports/python_tooling/full_status_fixture.md",
        "dry_run": False,
        "status": "written",
    }


def _write_manifest(project_root: Path, entries: list[dict[str, object]] | None = None, raw: str | None = None) -> Path:
    manifest = _manifest_path(project_root)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        manifest.write_text(raw, encoding="utf-8")
        return manifest
    text = "\n".join(json.dumps(entry) for entry in entries or [])
    manifest.write_text(text + ("\n" if text else ""), encoding="utf-8")
    return manifest


def test_bundle_preview_no_manifest_returns_no_manifest_and_writes_nothing(tmp_path: Path) -> None:
    result = analyze_report_bundle(action="preview", project_root=tmp_path)

    assert result.status == "NO_MANIFEST"
    assert result.manifest_exists is False
    assert result.would_write_bundle is False
    assert result.writes_files is False
    assert result.runs_ce is False
    assert not (tmp_path / "reports").exists()


def test_bundle_verify_no_manifest_returns_no_manifest_and_writes_nothing(tmp_path: Path) -> None:
    result = analyze_report_bundle(action="verify", project_root=tmp_path)

    assert result.status == "NO_MANIFEST"
    assert result.manifest_valid is False
    assert result.bundle_ready is False
    assert result.writes_files is False
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_verify_valid_manifest_ok(tmp_path: Path) -> None:
    output_path = _write_report(tmp_path)
    _write_manifest(tmp_path, [_manifest_entry(output_path=output_path)])

    result = analyze_report_bundle(action="verify", manifest=str(_manifest_path(tmp_path)), project_root=tmp_path)

    assert result.status == "OK"
    assert result.manifest_valid is True
    assert result.bundle_ready is True
    assert result.referenced_reports_checked == 1
    assert result.missing_reports == []
    assert result.planned_bundle_id
    assert result.planned_bundle_manifest and result.planned_bundle_manifest.endswith("bundle_manifest.json")
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_preview_valid_manifest_ok(tmp_path: Path) -> None:
    output_path = _write_report(tmp_path)
    _write_manifest(tmp_path, [_manifest_entry(output_path=output_path)])

    result = analyze_report_bundle(action="preview", project_root=tmp_path)
    data = result.to_dict()

    assert result.status == "OK"
    assert data["status"] == "OK"
    assert data["source_manifest_path"] == str(_manifest_path(tmp_path).resolve(strict=False))
    assert data["manifest_entry_count"] == 1
    assert data["candidate_report_count"] == 1
    assert data["planned_bundle_files"] == [output_path]
    assert data["would_write_bundle"] is False
    assert data["writes_files"] is False


def test_bundle_valid_manifest_missing_report_returns_missing_reports(tmp_path: Path) -> None:
    output_path = "reports/python_tooling/missing_full_status.md"
    _write_manifest(tmp_path, [_manifest_entry(output_path=output_path)])

    result = analyze_report_bundle(action="verify", project_root=tmp_path)

    assert result.status == "MISSING_REPORTS"
    assert result.manifest_valid is True
    assert result.bundle_ready is False
    assert result.missing_report_count == 1
    assert result.missing_reports == [output_path]


def test_bundle_corrupt_manifest_returns_invalid_manifest(tmp_path: Path) -> None:
    _write_manifest(tmp_path, raw="{not json}\n")

    result = analyze_report_bundle(action="verify", project_root=tmp_path)

    assert result.status == "INVALID_MANIFEST"
    assert result.manifest_valid is False
    assert result.invalid_entries
    assert "invalid JSON" in "; ".join(result.invalid_entries[0]["errors"])  # type: ignore[index]


def test_bundle_duplicate_report_id_detected(tmp_path: Path) -> None:
    first = _write_report(tmp_path, "one.md")
    second = _write_report(tmp_path, "two.md")
    _write_manifest(
        tmp_path,
        [
            _manifest_entry(report_id="duplicate", output_path=first),
            _manifest_entry(report_id="duplicate", output_path=second),
        ],
    )

    result = analyze_report_bundle(action="verify", project_root=tmp_path)

    assert result.status == "INVALID_MANIFEST"
    assert result.duplicate_report_ids == ["duplicate"]
    assert len(result.invalid_entries) == 2


def test_bundle_bad_manifest_paths_are_rejected(tmp_path: Path) -> None:
    for value in [
        "../log/case_registry.jsonl",
        "log/case_registry.jsonl",
        "src/armedforces_tool/report_export.py",
        "tests/fixtures/python_report_bundle/valid.jsonl",
        "docs/codex_tasks/x.md",
        "docs/reports/python_tooling/manifest.jsonl",
        "log/baselines/baseline_x.md",
    ]:
        result = analyze_report_bundle(action="verify", manifest=value, project_root=tmp_path)
        assert result.status == "BAD_PATH", value
        assert result.errors, value


def test_bundle_output_path_must_stay_under_runtime_reports(tmp_path: Path) -> None:
    _write_manifest(tmp_path, [_manifest_entry(output_path="docs/reports/python_tooling/full_status.md")])

    result = analyze_report_bundle(action="verify", project_root=tmp_path)

    assert result.status == "INVALID_MANIFEST"
    assert any("under reports/python_tooling" in error for entry in result.invalid_entries for error in entry["errors"])  # type: ignore[index]


def test_bundle_limit_reduces_candidate_count(tmp_path: Path) -> None:
    first = _write_report(tmp_path, "one.md")
    second = _write_report(tmp_path, "two.md")
    _write_manifest(
        tmp_path,
        [
            _manifest_entry(report_id="one", output_path=first),
            _manifest_entry(report_id="two", output_path=second),
        ],
    )

    result = analyze_report_bundle(action="preview", limit=1, project_root=tmp_path)

    assert result.status == "OK"
    assert result.manifest_entry_count == 1
    assert result.candidate_report_count == 1
    assert result.planned_bundle_files == [first]


def test_bundle_inventory_flags_read_only_and_keeps_export_only_writer() -> None:
    result = list_commands(category="report")
    records = {record.command: record for record in result.records}

    for command in ["report bundle preview", "report bundle verify", "report bundle export --dry-run"]:
        assert command in records
        assert records[command].read_only is True
        assert records[command].writes_files is False
        assert records[command].runs_ce is False
        assert records[command].risk_level == "READ_ONLY"

    summary = result.to_dict()["summary"]
    assert summary["writes_files_count"] == 1
    assert summary["runs_ce_count"] == 0
    assert records["report export"].writes_files is True
    assert show_command("report bundle preview").read_only is True


def test_global_inventory_keeps_only_report_export_write_capable_after_bundle_commands() -> None:
    result = list_commands()
    data = result.to_dict()["summary"]
    write_capable = [record.command for record in result.records if record.writes_files]

    assert data["total_count"] == 48
    assert data["writes_files_count"] == 1
    assert data["runs_ce_count"] == 0
    assert write_capable == ["report export"]


def test_bundle_export_dry_run_no_manifest_returns_no_manifest_and_writes_nothing(tmp_path: Path) -> None:
    result = plan_report_bundle_export(
        dry_run=True,
        out="reports/python_tooling/bundles/bundle_dry_run/",
        project_root=tmp_path,
    )

    assert result.status == "NO_MANIFEST"
    assert result.dry_run is True
    assert result.would_create_bundle is False
    assert result.would_write_files is False
    assert result.writes_files is False
    assert result.planned_bundle_type == "directory"
    assert result.planned_bundle_id == "bundle_dry_run"
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_export_dry_run_directory_output_plans_bundle(tmp_path: Path) -> None:
    output_path = _write_report(tmp_path)
    _write_manifest(tmp_path, [_manifest_entry(output_path=output_path)])

    result = plan_report_bundle_export(
        dry_run=True,
        out="reports/python_tooling/bundles/bundle_dry_run/",
        project_root=tmp_path,
    )
    data = result.to_dict()

    assert result.status == "OK"
    assert result.bundle_ready is True
    assert result.would_create_bundle is True
    assert result.would_write_files is False
    assert result.planned_bundle_type == "directory"
    assert result.planned_bundle_id == "bundle_dry_run"
    assert result.candidate_report_count == 1
    assert "bundle_manifest.json" in result.planned_files
    assert "index.md" in result.planned_files
    assert "reports/full_status_fixture.md" in result.planned_files
    assert data["writes_files"] is False
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_export_dry_run_zip_output_plans_bundle(tmp_path: Path) -> None:
    output_path = _write_report(tmp_path)
    _write_manifest(tmp_path, [_manifest_entry(output_path=output_path)])

    result = plan_report_bundle_export(
        dry_run=True,
        zip_output=True,
        out="reports/python_tooling/bundles/bundle_dry_run.zip",
        project_root=tmp_path,
    )

    assert result.status == "OK"
    assert result.planned_bundle_type == "zip"
    assert result.planned_bundle_id == "bundle_dry_run"
    assert result.planned_output_path and result.planned_output_path.endswith("bundle_dry_run.zip")
    assert result.planned_bundle_manifest == "bundle_manifest.json"
    assert result.planned_index == "index.md"
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_export_dry_run_missing_report_returns_missing_reports(tmp_path: Path) -> None:
    _write_manifest(tmp_path, [_manifest_entry(output_path="reports/python_tooling/missing.md")])

    result = plan_report_bundle_export(
        dry_run=True,
        out="reports/python_tooling/bundles/bundle_dry_run/",
        project_root=tmp_path,
    )

    assert result.status == "MISSING_REPORTS"
    assert result.bundle_ready is False
    assert result.would_create_bundle is False
    assert result.missing_report_count == 1
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_export_real_without_dry_run_fails_closed(tmp_path: Path) -> None:
    result = plan_report_bundle_export(
        dry_run=False,
        out="reports/python_tooling/bundles/bundle_real_blocked/",
        project_root=tmp_path,
    )

    assert result.status == "BUNDLE_EXPORT_NOT_IMPLEMENTED"
    assert result.dry_run is False
    assert result.would_create_bundle is False
    assert result.writes_files is False
    assert result.errors
    assert not (tmp_path / "reports").exists()


def test_bundle_export_dry_run_bad_output_paths_are_rejected(tmp_path: Path) -> None:
    for value in [
        "../bundle.zip",
        "log/bundle.zip",
        "src/bundle.zip",
        "tests/bundle.zip",
        "docs/codex_tasks/bundle.zip",
        "docs/reports/python_tooling/bundle.zip",
        "reports/python_tooling/bundles/bundle.txt",
        "reports/python_tooling/bundles",
    ]:
        result = plan_report_bundle_export(dry_run=True, zip_output=True, out=value, project_root=tmp_path)
        assert result.status == "BAD_PATH", value
        assert result.errors, value


def test_bundle_export_dry_run_bad_manifest_paths_are_rejected(tmp_path: Path) -> None:
    for value in [
        "../log/case_registry.jsonl",
        "log/case_registry.jsonl",
        "tests/fixtures/python_report_bundle/valid.jsonl",
        "docs/reports/python_tooling/manifest.jsonl",
    ]:
        result = plan_report_bundle_export(
            dry_run=True,
            out="reports/python_tooling/bundles/bundle_dry_run/",
            manifest=value,
            project_root=tmp_path,
        )
        assert result.status == "BAD_PATH", value
        assert result.errors, value


def test_bundle_export_dry_run_json_shape_contains_required_fields(tmp_path: Path) -> None:
    result = plan_report_bundle_export(
        dry_run=True,
        zip_output=True,
        out="reports/python_tooling/bundles/bundle_dry_run.zip",
        project_root=tmp_path,
    )
    data = result.to_dict()

    expected = {
        "status",
        "source_manifest_path",
        "planned_bundle_id",
        "planned_output_path",
        "planned_output_root",
        "planned_bundle_type",
        "would_create_bundle",
        "would_write_files",
        "writes_files",
        "planned_files",
        "planned_bundle_manifest",
        "planned_index",
        "candidate_report_count",
        "missing_report_count",
        "manifest_entry_count",
        "bundle_ready",
    }
    assert expected.issubset(data)
    assert data["writes_files"] is False
    assert data["would_write_files"] is False
