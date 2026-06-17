from __future__ import annotations

import shutil
from pathlib import Path

from armedforces_tool.command_inventory import list_commands, show_command
from armedforces_tool.report_manifest import analyze_report_manifest


FIXTURES = Path(__file__).parent / "fixtures" / "python_report_manifest"


def _install_manifest(tmp_path: Path, fixture_name: str, *, filename: str = "manifest.jsonl") -> Path:
    manifest = tmp_path / "reports" / "python_tooling" / filename
    manifest.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURES / fixture_name, manifest)
    return manifest


def test_no_manifest_preview_and_list_are_clear_and_write_nothing(tmp_path: Path) -> None:
    preview = analyze_report_manifest(action="preview", project_root=tmp_path)
    list_result = analyze_report_manifest(action="list", project_root=tmp_path)

    assert preview.status == "NO_MANIFEST"
    assert list_result.status == "NO_MANIFEST"
    assert preview.read_only is True
    assert preview.writes_files is False
    assert preview.runs_ce is False
    assert not (tmp_path / "reports").exists()
    assert not (tmp_path / "docs" / "reports").exists()


def test_valid_jsonl_verify_ok(tmp_path: Path) -> None:
    manifest = _install_manifest(tmp_path, "valid.jsonl")
    report = tmp_path / "reports" / "python_tooling" / "full_status_fixture.md"
    report.write_text("# report\n", encoding="utf-8")

    result = analyze_report_manifest(action="verify", path=str(manifest), project_root=tmp_path)

    assert result.status == "OK"
    assert result.entry_count == 1
    assert result.valid_count == 1
    assert result.invalid_count == 0
    assert result.duplicate_report_id_count == 0
    assert result.missing_report_count == 0


def test_invalid_jsonl_detected(tmp_path: Path) -> None:
    manifest = _install_manifest(tmp_path, "invalid.jsonl")

    result = analyze_report_manifest(action="verify", path=str(manifest), project_root=tmp_path)

    assert result.status == "INVALID_MANIFEST"
    assert result.invalid_count == 1
    assert any("missing required field: sha256" in error for error in result.records[0].errors)
    assert any("file_size must be an integer" in error for error in result.records[0].errors)
    assert any("dry_run must be a boolean" in error for error in result.records[0].errors)


def test_duplicate_report_id_detected(tmp_path: Path) -> None:
    manifest = _install_manifest(tmp_path, "duplicate.jsonl")
    for name in ["duplicate_one.md", "duplicate_two.md"]:
        (tmp_path / "reports" / "python_tooling" / name).write_text("x", encoding="utf-8")

    result = analyze_report_manifest(action="verify", path=str(manifest), project_root=tmp_path)

    assert result.status == "INVALID_MANIFEST"
    assert result.duplicate_report_id_count == 1
    assert all("duplicate_report_id" in record.errors for record in result.records)


def test_missing_report_reference_detected(tmp_path: Path) -> None:
    manifest = _install_manifest(tmp_path, "valid.jsonl")

    result = analyze_report_manifest(action="verify", path=str(manifest), project_root=tmp_path)

    assert result.status == "INVALID_MANIFEST"
    assert result.missing_report_count == 1
    assert result.missing_report_refs == ["reports/python_tooling/full_status_fixture.md"]


def test_bad_manifest_path_rejected(tmp_path: Path) -> None:
    result = analyze_report_manifest(action="verify", path="reports/python_tooling/not_manifest.jsonl", project_root=tmp_path)

    assert result.status == "BAD_PATH"
    assert any("manifest path must be named" in error for error in result.errors)


def test_traversal_path_rejected(tmp_path: Path) -> None:
    result = analyze_report_manifest(action="verify", path="../reports/python_tooling/manifest.jsonl", project_root=tmp_path)

    assert result.status == "BAD_PATH"
    assert any("path traversal" in error for error in result.errors)


def test_protected_path_rejected(tmp_path: Path) -> None:
    result = analyze_report_manifest(action="verify", path="log/case_registry.jsonl", project_root=tmp_path)

    assert result.status == "BAD_PATH"
    assert any("approved report roots" in error or "reports/python_tooling" in error for error in result.errors)


def test_tests_fixture_path_rejected_as_runtime_cli_path(tmp_path: Path) -> None:
    result = analyze_report_manifest(
        action="verify",
        path="tests/fixtures/python_report_manifest/valid.jsonl",
        project_root=tmp_path,
    )

    assert result.status == "BAD_PATH"
    assert result.errors


def test_unsupported_json_and_markdown_formats_do_not_crash(tmp_path: Path) -> None:
    json_manifest = _install_manifest(tmp_path, "unsupported.json", filename="manifest.json")
    markdown_manifest = tmp_path / "reports" / "python_tooling" / "report_index.md"
    markdown_manifest.write_text("# index\n", encoding="utf-8")

    json_result = analyze_report_manifest(action="verify", path=str(json_manifest), project_root=tmp_path)
    markdown_result = analyze_report_manifest(action="verify", path=str(markdown_manifest), project_root=tmp_path)

    assert json_result.status == "UNSUPPORTED_FORMAT"
    assert markdown_result.status == "UNSUPPORTED_FORMAT"


def test_command_inventory_flags_manifest_commands_read_only() -> None:
    result = list_commands(category="report")
    records = {record.command: record for record in result.records}

    for command in ["report manifest preview", "report manifest list", "report manifest verify"]:
        assert command in records
        assert records[command].read_only is True
        assert records[command].writes_files is False
        assert records[command].runs_ce is False
        assert records[command].risk_level == "READ_ONLY"

    assert result.to_dict()["summary"]["writes_files_count"] == 2
    assert result.to_dict()["summary"]["runs_ce_count"] == 0
    assert records["report export"].writes_files is True


def test_global_inventory_keeps_only_report_export_write_capable() -> None:
    result = list_commands()
    data = result.to_dict()["summary"]
    write_capable = [record.command for record in result.records if record.writes_files]

    assert data["writes_files_count"] == 2
    assert data["runs_ce_count"] == 0
    assert write_capable == ["report bundle export", "report export"]
    assert show_command("report manifest verify").read_only is True
