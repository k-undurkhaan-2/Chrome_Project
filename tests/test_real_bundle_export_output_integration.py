from __future__ import annotations

from pathlib import Path

from armedforces_tool.command_inventory import list_commands
from armedforces_tool.report_bundle import ReportBundleExportPlanResult, format_report_bundle_export_plan


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _successful_bundle_result(
    *,
    dry_run: bool = False,
    status: str = "BUNDLE_EXPORT_OK",
    bundle_written: bool = True,
    writes_files: bool = True,
    planned_bundle_type: str = "directory",
) -> ReportBundleExportPlanResult:
    return ReportBundleExportPlanResult(
        action="export",
        dry_run=dry_run,
        project_root=str(PROJECT_ROOT),
        status=status,
        source_manifest_path="reports/python_tooling/manifest.jsonl",
        manifest_exists=True,
        manifest_valid=True,
        manifest_entry_count=3,
        candidate_report_count=3,
        missing_report_count=0,
        planned_bundle_id="bundle_success_1",
        planned_output_path="reports/python_tooling/bundles/bundle_success_1",
        planned_output_root="reports/python_tooling/bundles",
        planned_bundle_type=planned_bundle_type,
        would_create_bundle=True,
        would_write_files=writes_files,
        planned_files=[
            "bundle_manifest.json",
            "index.md",
            "reports/full_status.md",
        ],
        planned_bundle_manifest="reports/python_tooling/bundles/bundle_success_1/bundle_manifest.json",
        planned_index="reports/python_tooling/bundles/bundle_success_1/index.md",
        bundle_ready=True,
        real_export_supported=True,
        bundle_written=bundle_written,
        bundle_path="reports/python_tooling/bundles/bundle_success_1",
        read_only=False,
        writes_files=writes_files,
        runs_ce=False,
        warnings=[],
        errors=[],
    )


def test_real_bundle_success_format_uses_candidate_c_helper_tokens() -> None:
    text = format_report_bundle_export_plan(_successful_bundle_result())

    assert "Report Bundle Export Complete" in text
    assert "BUNDLE_EXPORT_COMPLETE" in text
    assert "reports/python_tooling/bundles/bundle_success_1" in text
    assert "bundle_manifest.json" in text
    assert "index.md" in text
    assert "copied_report_count" in text
    assert "3" in text
    assert "SOURCE_UNCHANGED" in text
    assert "ZIP_UNSUPPORTED" not in text
    assert "APPROVED_ROOT" in text
    assert "CE_NOT_RUN" in text
    assert "WRAPPER_UNSUPPORTED" in text
    assert "Bundle Export Details" in text
    assert "BUNDLE_EXPORT_OK" in text
    assert "python -m armedforces_tool report bundle verify" in text
    assert "--force" not in text.lower()
    assert "zip file was created" not in text.lower()
    assert "python_tooling_wrapper.ps1" not in text


def test_candidate_c_predicate_excludes_dry_run_non_success_unwritten_and_zip() -> None:
    rejected_results = [
        _successful_bundle_result(dry_run=True),
        _successful_bundle_result(status="OUTPUT_EXISTS"),
        _successful_bundle_result(bundle_written=False),
        _successful_bundle_result(writes_files=False),
        _successful_bundle_result(planned_bundle_type="zip"),
    ]

    for result in rejected_results:
        text = format_report_bundle_export_plan(result)
        assert "Report Bundle Export Complete" not in text
        assert "BUNDLE_EXPORT_COMPLETE" not in text


def test_candidate_c_helper_not_wired_into_report_export_or_wrapper() -> None:
    report_export_source = (PROJECT_ROOT / "src" / "armedforces_tool" / "report_export.py").read_text(encoding="utf-8")
    wrapper_source = (PROJECT_ROOT / "src" / "python_tooling_wrapper.ps1").read_text(encoding="utf-8")

    assert "bundle_export_complete_message" not in report_export_source
    assert "BUNDLE_EXPORT_COMPLETE" not in report_export_source
    assert "bundle_export_complete_message" not in wrapper_source
    assert "BUNDLE_EXPORT_COMPLETE" not in wrapper_source


def test_report_bundle_imports_candidate_c_helper_without_candidate_a_or_b_helpers() -> None:
    source = (PROJECT_ROOT / "src" / "armedforces_tool" / "report_bundle.py").read_text(encoding="utf-8")

    assert "bundle_export_complete_message" in source
    assert "_uses_real_bundle_export_success_message" in source
    assert "result.status == \"BUNDLE_EXPORT_OK\"" in source
    assert "not result.dry_run" in source
    assert "result.bundle_written" in source
    assert "result.writes_files" in source
    assert "result.planned_bundle_type == \"directory\"" in source
    assert "report_export_complete_message" not in source
    assert "report_export_manifest_complete_message" not in source


def test_candidate_c_keeps_inventory_invariants() -> None:
    result = list_commands(category="report")
    records = {record.command: record for record in result.records}
    summary = result.to_dict()["summary"]

    assert summary["writes_files_count"] == 2
    assert summary["runs_ce_count"] == 0
    assert records["report export"].writes_files is True
    assert records["report bundle export"].writes_files is True
    assert records["report export --dry-run"].writes_files is False
    assert records["report bundle export --dry-run"].writes_files is False
