from __future__ import annotations

from pathlib import Path

from armedforces_tool.report_export import ReportExportDryRunResult, format_report_export_dry_run


REPO_ROOT = Path(__file__).resolve().parents[1]


def _successful_report_export_result(*, record_manifest: bool = False) -> ReportExportDryRunResult:
    return ReportExportDryRunResult(
        report_type="full-status",
        dry_run=False,
        would_write=True,
        wrote_file=True,
        target_path=str(REPO_ROOT / "reports" / "python_tooling" / "phase5_17_unit.md"),
        output_path=str(REPO_ROOT / "reports" / "python_tooling" / "phase5_17_unit.md"),
        approved_output_root=str(REPO_ROOT / "reports" / "python_tooling"),
        target_exists=True,
        target_exists_before=False,
        would_overwrite=False,
        overwritten=False,
        force=False,
        path_safety_status="PATH_OK",
        conclusion="REPORT_EXPORT_OK",
        recommendation="Report file written under an approved output root.",
        warnings=[],
        errors=[],
        content_line_count=10,
        content_size_bytes=100,
        bytes_written=100,
        record_manifest=record_manifest,
        manifest_written=record_manifest,
        manifest_path="reports/python_tooling/manifest.jsonl" if record_manifest else None,
        read_only=False,
        writes_files=True,
        runs_ce=False,
    )


def _assert_no_unsafe_suggestions(text: str) -> None:
    lowered = text.lower()
    assert "python_tooling_wrapper.ps1 report export" not in lowered
    assert "--force" not in lowered
    assert "zip export is available" not in lowered
    assert "disable guard" not in lowered
    assert "unsafe path" not in lowered
    assert "ce was run" not in lowered


def test_real_report_export_success_format_uses_candidate_a_helper_tokens() -> None:
    text = format_report_export_dry_run(_successful_report_export_result())

    assert "Report Export Complete" in text
    assert "WRITE_COMPLETE" in text
    assert "APPROVED_ROOT" in text
    assert "MANIFEST_NOT_WRITTEN" in text
    assert "BUNDLE_NOT_CREATED" in text
    assert "CE_NOT_RUN" in text
    assert "WRAPPER_UNSUPPORTED" in text
    assert "phase5_17_unit.md" in text
    assert "Export Details" in text
    assert "REPORT_EXPORT_OK" in text
    assert "python -m armedforces_tool report preview --type full-status" in text
    _assert_no_unsafe_suggestions(text)


def test_record_manifest_success_path_does_not_use_candidate_a_helper() -> None:
    text = format_report_export_dry_run(_successful_report_export_result(record_manifest=True))

    assert "Report Export Complete" not in text
    assert "MANIFEST_NOT_WRITTEN" not in text
    assert "record_manifest" in text
    assert "manifest_written" in text


def test_candidate_a_helper_not_wired_into_wrapper_or_bundle_export() -> None:
    wrapper_source = (REPO_ROOT / "src" / "python_tooling_wrapper.ps1").read_text(encoding="utf-8")
    bundle_source = (REPO_ROOT / "src" / "armedforces_tool" / "report_bundle.py").read_text(encoding="utf-8")

    assert "report_export_complete_message" not in wrapper_source
    assert "report_export_complete_message" not in bundle_source
    assert "WRITE_COMPLETE" not in wrapper_source
    assert "WRITE_COMPLETE" not in bundle_source


def test_report_export_imports_candidate_a_helper_but_not_manifest_helper() -> None:
    source = (REPO_ROOT / "src" / "armedforces_tool" / "report_export.py").read_text(encoding="utf-8")

    assert "report_export_complete_message" in source
    assert "report_export_manifest_complete_message" not in source
    assert "bundle_export_complete_message" not in source
    assert "_uses_real_report_export_success_message" in source
