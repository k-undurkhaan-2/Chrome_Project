from __future__ import annotations

import json
import hashlib
from pathlib import Path

from armedforces_tool.command_inventory import list_commands, show_command
from armedforces_tool.report_bundle import analyze_report_bundle, format_report_bundle_export_plan, plan_report_bundle_export


SOURCE_INPUT_FAILURE_FORBIDDEN_TOKENS = [
    "BUNDLE_EXPORT_COMPLETE",
    "BUNDLE_EXPORT_OK",
    "SOURCE_UNCHANGED",
    "REPORT_EXPORT_OK",
    "WRITE_COMPLETE",
    "MANIFEST_RECORDED",
]


def _manifest_path(project_root: Path) -> Path:
    return project_root / "reports" / "python_tooling" / "manifest.jsonl"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


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


def _relative(project_root: Path, path: Path) -> str:
    return path.relative_to(project_root).as_posix()


def _write_isolated_source_report(
    project_root: Path,
    name: str = "candidate_c_source_report.md",
    text: str = "# isolated source report\n",
) -> Path:
    report = project_root / "reports" / "python_tooling" / "validation" / "candidate_c" / name
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(text, encoding="utf-8")
    return report


def _write_isolated_source_manifest(project_root: Path, name: str = "manifest.jsonl") -> Path:
    manifest = project_root / "reports" / "python_tooling" / "validation" / "candidate_c" / name
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"status": "fixture"}) + "\n", encoding="utf-8")
    return manifest


def _assert_source_input_failure_output(text: str, required_tokens: list[str]) -> None:
    for token in [*required_tokens, "NO_FILES_WRITTEN"]:
        assert token in text
    for token in SOURCE_INPUT_FAILURE_FORBIDDEN_TOKENS:
        assert token not in text


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


def test_bundle_inventory_flags_read_only_and_marks_real_export_writer() -> None:
    result = list_commands(category="report")
    records = {record.command: record for record in result.records}

    for command in ["report bundle preview", "report bundle verify", "report bundle export --dry-run"]:
        assert command in records
        assert records[command].read_only is True
        assert records[command].writes_files is False
        assert records[command].runs_ce is False
        assert records[command].risk_level == "READ_ONLY"

    summary = result.to_dict()["summary"]
    assert summary["writes_files_count"] == 2
    assert summary["runs_ce_count"] == 0
    assert records["report export"].writes_files is True
    assert records["report bundle export"].writes_files is True
    assert records["report bundle export"].read_only is False
    assert show_command("report bundle preview").read_only is True


def test_global_inventory_marks_report_and_bundle_export_write_capable() -> None:
    result = list_commands()
    data = result.to_dict()["summary"]
    write_capable = [record.command for record in result.records if record.writes_files]

    assert data["total_count"] == 49
    assert data["writes_files_count"] == 2
    assert data["runs_ce_count"] == 0
    assert write_capable == ["report bundle export", "report export"]


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


def test_bundle_export_real_without_manifest_writes_nothing(tmp_path: Path) -> None:
    result = plan_report_bundle_export(
        dry_run=False,
        out="reports/python_tooling/bundles/bundle_real_blocked/",
        project_root=tmp_path,
    )

    assert result.status == "NO_MANIFEST"
    assert result.dry_run is False
    assert result.would_create_bundle is False
    assert result.writes_files is False
    assert not (tmp_path / "reports").exists()


def test_bundle_export_real_directory_writes_bundle_and_preserves_sources(tmp_path: Path) -> None:
    output_path = _write_report(tmp_path)
    report_path = tmp_path / output_path
    report_before = report_path.read_bytes()
    _write_manifest(tmp_path, [_manifest_entry(output_path=output_path)])
    manifest = _manifest_path(tmp_path)
    manifest_before = manifest.read_bytes()

    result = plan_report_bundle_export(
        dry_run=False,
        out="reports/python_tooling/bundles/bundle_real/",
        project_root=tmp_path,
    )
    data = result.to_dict()

    bundle_root = tmp_path / "reports" / "python_tooling" / "bundles" / "bundle_real"
    copied_report = bundle_root / "reports" / "full_status_fixture.md"
    bundle_manifest = bundle_root / "bundle_manifest.json"
    index = bundle_root / "index.md"

    assert result.status == "BUNDLE_EXPORT_OK"
    assert result.bundle_written is True
    assert data["bundle_written"] is True
    assert data["bundle_path"] == str(bundle_root.resolve(strict=False))
    assert result.writes_files is True
    assert result.read_only is False
    assert bundle_root.is_dir()
    assert bundle_manifest.is_file()
    assert index.is_file()
    assert copied_report.read_bytes() == report_before
    assert report_path.read_bytes() == report_before
    assert manifest.read_bytes() == manifest_before

    manifest_data = json.loads(bundle_manifest.read_text(encoding="utf-8"))
    assert manifest_data["schema_version"] == 1
    assert manifest_data["bundle_id"] == "bundle_real"
    assert manifest_data["bundle_type"] == "directory"
    assert manifest_data["status"] == "success"
    assert manifest_data["included_reports"][0]["bundle_path"] == "reports/full_status_fixture.md"
    assert manifest_data["per_file_hashes"]["reports/full_status_fixture.md"] == _sha256(copied_report)
    assert "`bundle_manifest.json` is the source of truth" in index.read_text(encoding="utf-8")


def test_bundle_export_real_isolated_source_report_writes_bundle_and_preserves_source(tmp_path: Path) -> None:
    source_report = _write_isolated_source_report(tmp_path, text="# isolated candidate c\nbody\n")
    report_before = source_report.read_bytes()

    result = plan_report_bundle_export(
        dry_run=False,
        source_report=_relative(tmp_path, source_report),
        out="reports/python_tooling/validation/candidate_c/bundle_source_report",
        project_root=tmp_path,
    )

    bundle_root = tmp_path / "reports" / "python_tooling" / "validation" / "candidate_c" / "bundle_source_report"
    copied_report = bundle_root / "reports" / source_report.name
    bundle_manifest = bundle_root / "bundle_manifest.json"
    index = bundle_root / "index.md"

    assert result.status == "BUNDLE_EXPORT_OK"
    assert result.bundle_written is True
    assert result.writes_files is True
    assert result.planned_output_root == str((tmp_path / "reports" / "python_tooling").resolve(strict=False))
    assert bundle_root.is_dir()
    assert bundle_manifest.is_file()
    assert index.is_file()
    assert copied_report.read_bytes() == report_before
    assert source_report.read_bytes() == report_before
    assert not (tmp_path / "reports" / "python_tooling" / "full_status.md").exists()
    assert not _manifest_path(tmp_path).exists()
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()

    manifest_data = json.loads(bundle_manifest.read_text(encoding="utf-8"))
    assert manifest_data["schema_version"] == 1
    assert manifest_data["bundle_id"] == "bundle_source_report"
    assert manifest_data["bundle_type"] == "directory"
    assert manifest_data["included_reports"][0]["source_path"] == _relative(tmp_path, source_report)
    assert manifest_data["included_reports"][0]["bundle_path"] == f"reports/{source_report.name}"
    assert manifest_data["per_file_hashes"][f"reports/{source_report.name}"] == _sha256(copied_report)

    formatted = format_report_bundle_export_plan(result)
    for token in ["BUNDLE_EXPORT_COMPLETE", "SOURCE_UNCHANGED", "APPROVED_ROOT", "CE_NOT_RUN", "WRAPPER_UNSUPPORTED", "BUNDLE_EXPORT_OK"]:
        assert token in formatted
    for token in ["NO_FILES_WRITTEN", "REPORT_EXPORT_OK", "MANIFEST_RECORDED", "MANIFEST_NOT_WRITTEN", "BUNDLE_NOT_CREATED", "ZIP_UNSUPPORTED"]:
        assert token not in formatted


def test_bundle_export_real_isolated_source_report_and_manifest_preserves_inputs(tmp_path: Path) -> None:
    source_report = _write_isolated_source_report(tmp_path, "candidate_c_with_manifest.md", "# source with manifest\n")
    source_manifest = _write_isolated_source_manifest(tmp_path)
    report_before = source_report.read_bytes()
    manifest_before = source_manifest.read_bytes()

    result = plan_report_bundle_export(
        dry_run=False,
        source_report=_relative(tmp_path, source_report),
        source_manifest=_relative(tmp_path, source_manifest),
        out="reports/python_tooling/validation/candidate_c/bundle_source_manifest",
        project_root=tmp_path,
    )

    bundle_root = tmp_path / "reports" / "python_tooling" / "validation" / "candidate_c" / "bundle_source_manifest"
    copied_report = bundle_root / "reports" / source_report.name
    bundle_manifest = bundle_root / "bundle_manifest.json"
    index = bundle_root / "index.md"

    assert result.status == "BUNDLE_EXPORT_OK"
    assert result.source_manifest_path == str(source_manifest.resolve(strict=True))
    assert result.manifest_exists is True
    assert bundle_root.is_dir()
    assert bundle_manifest.is_file()
    assert index.is_file()
    assert copied_report.read_bytes() == report_before
    assert source_report.read_bytes() == report_before
    assert source_manifest.read_bytes() == manifest_before
    assert not _manifest_path(tmp_path).exists()
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()

    manifest_data = json.loads(bundle_manifest.read_text(encoding="utf-8"))
    assert manifest_data["source_manifest_path"] == str(source_manifest.resolve(strict=True))
    assert manifest_data["included_reports"][0]["source_path"] == _relative(tmp_path, source_report)


def test_bundle_export_real_zip_is_rejected_without_writing(tmp_path: Path) -> None:
    output_path = _write_report(tmp_path)
    _write_manifest(tmp_path, [_manifest_entry(output_path=output_path)])

    result = plan_report_bundle_export(
        dry_run=False,
        zip_output=True,
        out="reports/python_tooling/bundles/bundle_real.zip",
        project_root=tmp_path,
    )

    assert result.status == "BUNDLE_ZIP_EXPORT_NOT_IMPLEMENTED"
    assert result.writes_files is False
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_export_real_existing_output_is_rejected_without_overwrite(tmp_path: Path) -> None:
    output_path = _write_report(tmp_path)
    _write_manifest(tmp_path, [_manifest_entry(output_path=output_path)])
    existing = tmp_path / "reports" / "python_tooling" / "bundles" / "bundle_existing"
    existing.mkdir(parents=True)
    marker = existing / "keep.txt"
    marker.write_text("do not overwrite", encoding="utf-8")

    result = plan_report_bundle_export(
        dry_run=False,
        out="reports/python_tooling/bundles/bundle_existing/",
        project_root=tmp_path,
    )

    assert result.status == "OUTPUT_EXISTS"
    assert result.writes_files is False
    assert marker.read_text(encoding="utf-8") == "do not overwrite"


def test_bundle_export_real_isolated_existing_output_is_rejected_without_overwrite(tmp_path: Path) -> None:
    source_report = _write_isolated_source_report(tmp_path)
    existing = tmp_path / "reports" / "python_tooling" / "validation" / "candidate_c" / "bundle_existing"
    existing.mkdir(parents=True)
    marker = existing / "keep.txt"
    marker.write_text("do not overwrite", encoding="utf-8")

    result = plan_report_bundle_export(
        dry_run=False,
        source_report=_relative(tmp_path, source_report),
        out="reports/python_tooling/validation/candidate_c/bundle_existing",
        project_root=tmp_path,
    )

    assert result.status == "OUTPUT_EXISTS"
    assert result.writes_files is False
    assert marker.read_text(encoding="utf-8") == "do not overwrite"
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_export_real_missing_report_writes_nothing(tmp_path: Path) -> None:
    _write_manifest(tmp_path, [_manifest_entry(output_path="reports/python_tooling/missing.md")])

    result = plan_report_bundle_export(
        dry_run=False,
        out="reports/python_tooling/bundles/bundle_missing/",
        project_root=tmp_path,
    )

    assert result.status == "MISSING_REPORTS"
    assert result.writes_files is False
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_export_real_missing_source_report_writes_nothing(tmp_path: Path) -> None:
    result = plan_report_bundle_export(
        dry_run=False,
        source_report="reports/python_tooling/validation/candidate_c/missing.md",
        out="reports/python_tooling/validation/candidate_c/bundle_missing_source_report",
        project_root=tmp_path,
    )

    formatted = format_report_bundle_export_plan(result)

    assert result.status == "SOURCE_MISSING"
    assert result.writes_files is False
    assert any("source report path does not exist" in error for error in result.errors)
    _assert_source_input_failure_output(formatted, ["SOURCE_MISSING", "--source-report"])
    assert not (tmp_path / "reports" / "python_tooling" / "validation").exists()
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_export_real_invalid_source_report_writes_nothing(tmp_path: Path) -> None:
    source_report_dir = tmp_path / "reports" / "python_tooling" / "validation" / "candidate_c" / "source_report_dir.md"
    source_report_dir.mkdir(parents=True)

    result = plan_report_bundle_export(
        dry_run=False,
        source_report=_relative(tmp_path, source_report_dir),
        out="reports/python_tooling/validation/candidate_c/bundle_invalid_source_report",
        project_root=tmp_path,
    )

    formatted = format_report_bundle_export_plan(result)

    assert result.status == "SOURCE_INVALID"
    assert result.writes_files is False
    assert any("source report path must be a file" in error for error in result.errors)
    _assert_source_input_failure_output(formatted, ["SOURCE_INVALID", "--source-report"])
    assert source_report_dir.is_dir()
    assert not (tmp_path / "reports" / "python_tooling" / "validation" / "candidate_c" / "bundle_invalid_source_report").exists()
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_export_real_missing_source_manifest_writes_nothing(tmp_path: Path) -> None:
    source_report = _write_isolated_source_report(tmp_path)
    source_report_before = _sha256(source_report)

    result = plan_report_bundle_export(
        dry_run=False,
        source_report=_relative(tmp_path, source_report),
        source_manifest="reports/python_tooling/validation/candidate_c/missing_manifest.jsonl",
        out="reports/python_tooling/validation/candidate_c/bundle_missing_source_manifest",
        project_root=tmp_path,
    )

    formatted = format_report_bundle_export_plan(result)

    assert result.status == "SOURCE_MISSING"
    assert result.writes_files is False
    assert any("source manifest path does not exist" in error for error in result.errors)
    assert _sha256(source_report) == source_report_before
    _assert_source_input_failure_output(formatted, ["SOURCE_MISSING", "--source-manifest"])
    assert not (tmp_path / "reports" / "python_tooling" / "validation" / "candidate_c" / "bundle_missing_source_manifest").exists()
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_export_real_invalid_source_manifest_writes_nothing(tmp_path: Path) -> None:
    source_report = _write_isolated_source_report(tmp_path)
    source_report_before = _sha256(source_report)
    source_manifest_dir = tmp_path / "reports" / "python_tooling" / "validation" / "candidate_c" / "manifest_dir.jsonl"
    source_manifest_dir.mkdir(parents=True)

    result = plan_report_bundle_export(
        dry_run=False,
        source_report=_relative(tmp_path, source_report),
        source_manifest=_relative(tmp_path, source_manifest_dir),
        out="reports/python_tooling/validation/candidate_c/bundle_invalid_source_manifest",
        project_root=tmp_path,
    )

    formatted = format_report_bundle_export_plan(result)

    assert result.status == "SOURCE_INVALID"
    assert result.writes_files is False
    assert any("source manifest path must be a file" in error for error in result.errors)
    assert _sha256(source_report) == source_report_before
    _assert_source_input_failure_output(formatted, ["SOURCE_INVALID", "--source-manifest"])
    assert source_manifest_dir.is_dir()
    assert not (tmp_path / "reports" / "python_tooling" / "validation" / "candidate_c" / "bundle_invalid_source_manifest").exists()
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_export_real_source_manifest_requires_source_report(tmp_path: Path) -> None:
    source_manifest = _write_isolated_source_manifest(tmp_path)

    result = plan_report_bundle_export(
        dry_run=False,
        source_manifest=_relative(tmp_path, source_manifest),
        out="reports/python_tooling/validation/candidate_c/bundle_source_manifest_only",
        project_root=tmp_path,
    )

    formatted = format_report_bundle_export_plan(result)

    assert result.status == "INVALID_OPTION_COMBINATION"
    assert result.writes_files is False
    assert any("--source-manifest requires --source-report" in error for error in result.errors)
    _assert_source_input_failure_output(formatted, ["INVALID_OPTION_COMBINATION", "--source-manifest", "--source-report"])
    assert not (tmp_path / "reports" / "python_tooling" / "validation" / "candidate_c" / "bundle_source_manifest_only").exists()
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_export_real_default_mode_rejects_isolated_output_path(tmp_path: Path) -> None:
    output_path = _write_report(tmp_path)
    _write_manifest(tmp_path, [_manifest_entry(output_path=output_path)])

    result = plan_report_bundle_export(
        dry_run=False,
        out="reports/python_tooling/validation/candidate_c/bundle_default_rejected",
        project_root=tmp_path,
    )

    assert result.status == "BAD_PATH"
    assert result.writes_files is False
    assert any("reports/python_tooling/bundles" in error for error in result.errors)
    assert not (tmp_path / "reports" / "python_tooling" / "validation").exists()
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_export_real_bad_paths_are_rejected_without_writing(tmp_path: Path) -> None:
    output_path = _write_report(tmp_path)
    _write_manifest(tmp_path, [_manifest_entry(output_path=output_path)])

    for value in [
        "../bundle",
        "log/bundle",
        "src/bundle",
        "tests/bundle",
        "docs/codex_tasks/bundle",
        "docs/reports/python_tooling/bundle",
        "reports/python_tooling/bundles/bad name/",
    ]:
        result = plan_report_bundle_export(dry_run=False, out=value, project_root=tmp_path)
        assert result.status == "BAD_PATH", value
        assert result.writes_files is False


def test_bundle_export_real_isolated_output_rejects_production_bundle_root(tmp_path: Path) -> None:
    source_report = _write_isolated_source_report(tmp_path)

    result = plan_report_bundle_export(
        dry_run=False,
        source_report=_relative(tmp_path, source_report),
        out="reports/python_tooling/bundles/bundle_not_allowed",
        project_root=tmp_path,
    )

    assert result.status == "BAD_PATH"
    assert result.writes_files is False
    assert any("must not target reports/python_tooling/bundles" in error for error in result.errors)
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


def test_bundle_export_real_isolated_source_report_outside_runtime_root_rejected(tmp_path: Path) -> None:
    source_report = tmp_path / "docs" / "reports" / "python_tooling" / "outside.md"
    source_report.parent.mkdir(parents=True, exist_ok=True)
    source_report.write_text("# outside\n", encoding="utf-8")

    result = plan_report_bundle_export(
        dry_run=False,
        source_report=_relative(tmp_path, source_report),
        out="reports/python_tooling/validation/candidate_c/bundle_outside_source",
        project_root=tmp_path,
    )

    assert result.status == "BAD_PATH"
    assert result.writes_files is False
    assert any("under reports/python_tooling" in error for error in result.errors)
    assert not (tmp_path / "reports" / "python_tooling" / "validation").exists()


def test_bundle_export_real_source_report_outside_runtime_root_rejected(tmp_path: Path) -> None:
    report = tmp_path / "docs" / "reports" / "python_tooling" / "outside.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("# outside\n", encoding="utf-8")
    _write_manifest(tmp_path, [_manifest_entry(output_path="docs/reports/python_tooling/outside.md")])

    result = plan_report_bundle_export(
        dry_run=False,
        out="reports/python_tooling/bundles/bundle_outside/",
        project_root=tmp_path,
    )

    assert result.status == "INVALID_MANIFEST"
    assert result.writes_files is False
    assert not (tmp_path / "reports" / "python_tooling" / "bundles").exists()


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
