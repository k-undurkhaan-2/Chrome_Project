from __future__ import annotations

from pathlib import Path

from armedforces_tool.report_export import ReportExportDryRunResult, format_report_export_dry_run


REPO_ROOT = Path(__file__).resolve().parents[1]


def _manifest_success_result(
    *,
    dry_run: bool = False,
    record_manifest: bool = True,
    conclusion: str = "REPORT_EXPORT_OK",
    wrote_file: bool = True,
    manifest_written: bool = True,
) -> ReportExportDryRunResult:
    return ReportExportDryRunResult(
        report_type="full-status",
        dry_run=dry_run,
        would_write=True,
        wrote_file=wrote_file,
        target_path=str(REPO_ROOT / "reports" / "python_tooling" / "phase5_20_unit.md"),
        output_path=str(REPO_ROOT / "reports" / "python_tooling" / "phase5_20_unit.md"),
        approved_output_root=str(REPO_ROOT / "reports" / "python_tooling"),
        target_exists=True,
        target_exists_before=False,
        would_overwrite=False,
        overwritten=False,
        force=False,
        path_safety_status="PATH_OK",
        conclusion=conclusion,
        recommendation="Report file written under an approved output root.",
        warnings=[],
        errors=[],
        content_line_count=10,
        content_size_bytes=100,
        bytes_written=100,
        record_manifest=record_manifest,
        would_write_report=True if record_manifest else None,
        would_write_manifest=True if record_manifest else None,
        manifest_written=manifest_written,
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


def test_manifest_success_format_uses_candidate_b_helper_tokens() -> None:
    text = format_report_export_dry_run(_manifest_success_result())

    assert "Report Export Manifest Complete" in text
    assert "WRITE_COMPLETE" in text
    assert "APPROVED_ROOT" in text
    assert "MANIFEST_RECORDED" in text
    assert "BUNDLE_NOT_CREATED" in text
    assert "CE_NOT_RUN" in text
    assert "WRAPPER_UNSUPPORTED" in text
    assert "phase5_20_unit.md" in text
    assert "reports/python_tooling/manifest.jsonl" in text
    assert "Manifest Export Details" in text
    assert "REPORT_EXPORT_OK" in text
    assert "python -m armedforces_tool report manifest verify" in text
    _assert_no_unsafe_suggestions(text)


def test_manifest_helper_predicate_excludes_dry_run_non_manifest_non_success_and_unwritten() -> None:
    rejected_results = [
        _manifest_success_result(dry_run=True),
        _manifest_success_result(record_manifest=False),
        _manifest_success_result(conclusion="REPORT_EXPORT_REJECTED"),
        _manifest_success_result(wrote_file=False),
        _manifest_success_result(manifest_written=False),
    ]

    for result in rejected_results:
        text = format_report_export_dry_run(result)
        assert "Report Export Manifest Complete" not in text


def test_candidate_b_helper_not_wired_into_wrapper_or_bundle_export() -> None:
    wrapper_source = (REPO_ROOT / "src" / "python_tooling_wrapper.ps1").read_text(encoding="utf-8")
    bundle_source = (REPO_ROOT / "src" / "armedforces_tool" / "report_bundle.py").read_text(encoding="utf-8")

    assert "report_export_manifest_complete_message" not in wrapper_source
    assert "report_export_manifest_complete_message" not in bundle_source
    assert "MANIFEST_RECORDED" not in wrapper_source
    assert "MANIFEST_RECORDED" not in bundle_source


def test_report_export_imports_candidate_b_helper_without_bundle_helper() -> None:
    source = (REPO_ROOT / "src" / "armedforces_tool" / "report_export.py").read_text(encoding="utf-8")

    assert "report_export_manifest_complete_message" in source
    assert "bundle_export_complete_message" not in source
    assert "_uses_report_export_manifest_success_message" in source
    assert "result.record_manifest" in source
    assert "result.manifest_written" in source
