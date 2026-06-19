from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .report_manifest import REQUIRED_FIELDS
from .report_output_messages import bundle_export_complete_message, bundle_export_dry_run_message
from .safety import DEFAULT_PROJECT_ROOT

DEFAULT_BUNDLE_MANIFEST_PATH = Path("reports/python_tooling/manifest.jsonl")
PLANNED_BUNDLE_ROOT = Path("reports/python_tooling/bundles")
PLANNED_BUNDLE_MANIFEST_NAME = "bundle_manifest.json"
PLANNED_BUNDLE_INDEX_NAME = "index.md"


@dataclass(frozen=True)
class BundleManifestEntry:
    line_number: int
    report_id: str | None
    report_type: str | None
    output_path: str | None
    valid: bool
    errors: list[str]
    data: dict[str, object]

    def to_dict(self) -> dict[str, object | None]:
        return {
            "line_number": self.line_number,
            "report_id": self.report_id,
            "report_type": self.report_type,
            "output_path": self.output_path,
            "valid": self.valid,
            "errors": self.errors,
            "data": self.data,
        }


@dataclass(frozen=True)
class ReportBundleResult:
    action: str
    project_root: str
    status: str
    source_manifest_path: str
    manifest_exists: bool
    manifest_valid: bool
    manifest_entry_count: int
    candidate_report_count: int
    missing_report_count: int
    referenced_reports_checked: int
    missing_reports: list[str]
    duplicate_report_ids: list[str]
    invalid_entries: list[dict[str, object | None]]
    records: list[BundleManifestEntry]
    planned_bundle_id: str | None
    planned_bundle_root: str | None
    planned_bundle_files: list[str]
    planned_bundle_manifest: str | None
    bundle_ready: bool
    would_write_bundle: bool
    read_only: bool
    writes_files: bool
    runs_ce: bool
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "project_root": self.project_root,
            "status": self.status,
            "source_manifest_path": self.source_manifest_path,
            "manifest_exists": self.manifest_exists,
            "manifest_valid": self.manifest_valid,
            "manifest_entry_count": self.manifest_entry_count,
            "candidate_report_count": self.candidate_report_count,
            "missing_report_count": self.missing_report_count,
            "referenced_reports_checked": self.referenced_reports_checked,
            "missing_reports": self.missing_reports,
            "duplicate_report_ids": self.duplicate_report_ids,
            "invalid_entries": self.invalid_entries,
            "records": [record.to_dict() for record in self.records],
            "planned_bundle_id": self.planned_bundle_id,
            "planned_bundle_root": self.planned_bundle_root,
            "planned_bundle_files": self.planned_bundle_files,
            "planned_bundle_manifest": self.planned_bundle_manifest,
            "bundle_ready": self.bundle_ready,
            "would_write_bundle": self.would_write_bundle,
            "read_only": self.read_only,
            "writes_files": self.writes_files,
            "runs_ce": self.runs_ce,
            "warnings": self.warnings,
            "errors": self.errors,
        }


@dataclass(frozen=True)
class ReportBundleExportPlanResult:
    action: str
    dry_run: bool
    project_root: str
    status: str
    source_manifest_path: str
    manifest_exists: bool
    manifest_valid: bool
    manifest_entry_count: int
    candidate_report_count: int
    missing_report_count: int
    planned_bundle_id: str | None
    planned_output_path: str | None
    planned_output_root: str | None
    planned_bundle_type: str | None
    would_create_bundle: bool
    would_write_files: bool
    planned_files: list[str]
    planned_bundle_manifest: str | None
    planned_index: str | None
    bundle_ready: bool
    real_export_supported: bool
    bundle_written: bool
    bundle_path: str | None
    read_only: bool
    writes_files: bool
    runs_ce: bool
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "dry_run": self.dry_run,
            "project_root": self.project_root,
            "status": self.status,
            "source_manifest_path": self.source_manifest_path,
            "manifest_exists": self.manifest_exists,
            "manifest_valid": self.manifest_valid,
            "manifest_entry_count": self.manifest_entry_count,
            "candidate_report_count": self.candidate_report_count,
            "missing_report_count": self.missing_report_count,
            "planned_bundle_id": self.planned_bundle_id,
            "planned_output_path": self.planned_output_path,
            "planned_output_root": self.planned_output_root,
            "planned_bundle_type": self.planned_bundle_type,
            "would_create_bundle": self.would_create_bundle,
            "would_write_files": self.would_write_files,
            "writes_files": self.writes_files,
            "planned_files": self.planned_files,
            "planned_bundle_manifest": self.planned_bundle_manifest,
            "planned_index": self.planned_index,
            "bundle_ready": self.bundle_ready,
            "real_export_supported": self.real_export_supported,
            "bundle_written": self.bundle_written,
            "bundle_path": self.bundle_path,
            "read_only": self.read_only,
            "runs_ce": self.runs_ce,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def analyze_report_bundle(
    *,
    action: str,
    manifest: str | None = None,
    limit: int | None = None,
    project_root: Path = DEFAULT_PROJECT_ROOT,
) -> ReportBundleResult:
    normalized_action = (action or "").strip().lower()
    project_root_resolved = project_root.resolve()
    manifest_path, path_errors = _resolve_bundle_manifest_path(manifest, project_root_resolved)

    if normalized_action not in {"preview", "verify"}:
        return _empty_result(
            action=normalized_action,
            project_root=project_root_resolved,
            manifest_path=manifest_path,
            status="BAD_ACTION",
            errors=[f"unsupported bundle action: {action}"],
        )

    if path_errors:
        return _empty_result(
            action=normalized_action,
            project_root=project_root_resolved,
            manifest_path=manifest_path,
            status="BAD_PATH",
            errors=path_errors,
        )

    if manifest_path.suffix.lower() != ".jsonl":
        return _empty_result(
            action=normalized_action,
            project_root=project_root_resolved,
            manifest_path=manifest_path,
            status="UNSUPPORTED_FORMAT",
            errors=["bundle preview/verify only supports manifest.jsonl"],
        )

    if not manifest_path.exists():
        return _empty_result(
            action=normalized_action,
            project_root=project_root_resolved,
            manifest_path=manifest_path,
            status="NO_MANIFEST",
            warnings=["No runtime report manifest found at reports/python_tooling/manifest.jsonl."],
        )

    if limit is not None and limit < 0:
        return _empty_result(
            action=normalized_action,
            project_root=project_root_resolved,
            manifest_path=manifest_path,
            status="BAD_PATH",
            manifest_exists=True,
            errors=["--limit must be zero or greater"],
        )

    return _analyze_existing_manifest(
        action=normalized_action,
        manifest_path=manifest_path,
        project_root=project_root_resolved,
        limit=limit,
    )


def plan_report_bundle_export(
    *,
    dry_run: bool,
    out: str | None = None,
    zip_output: bool = False,
    manifest: str | None = None,
    source_report: str | None = None,
    source_manifest: str | None = None,
    limit: int | None = None,
    project_root: Path = DEFAULT_PROJECT_ROOT,
) -> ReportBundleExportPlanResult:
    project_root_resolved = project_root.resolve()
    isolated_source_mode = bool(source_report or source_manifest)
    if isolated_source_mode:
        manifest_path, manifest_errors, isolated_analysis = _analyze_isolated_source_inputs(
            source_report=source_report,
            source_manifest=source_manifest,
            manifest=manifest,
            project_root=project_root_resolved,
        )
    else:
        manifest_path, manifest_errors = _resolve_bundle_manifest_path(manifest, project_root_resolved)
        isolated_analysis = None
    output_path, output_errors, bundle_type = _resolve_bundle_output_path(
        out,
        zip_output,
        project_root_resolved,
        isolated_mode=isolated_source_mode,
    )
    planned_bundle_id = _bundle_id_from_output(output_path, bundle_type)
    planned_bundle_manifest = _planned_bundle_manifest(output_path, bundle_type)
    planned_index = _planned_index(output_path, bundle_type)
    planned_output_root = _planned_output_root(output_path, project_root_resolved, isolated_mode=isolated_source_mode)

    path_errors = output_errors + manifest_errors
    if path_errors:
        return _empty_export_result(
            project_root=project_root_resolved,
            manifest_path=manifest_path,
            status="BAD_PATH",
            dry_run=dry_run,
            planned_bundle_id=planned_bundle_id,
            planned_output_path=str(output_path) if output_path is not None else None,
            planned_output_root=planned_output_root,
            planned_bundle_type=bundle_type,
            planned_bundle_manifest=planned_bundle_manifest,
            planned_index=planned_index,
            errors=path_errors,
            read_only=dry_run,
        )

    if output_path is None:
        return _empty_export_result(
            project_root=project_root_resolved,
            manifest_path=manifest_path,
            status="BAD_PATH",
            dry_run=dry_run,
            planned_output_root=planned_output_root,
            planned_bundle_type=bundle_type,
            errors=["--out is required for report bundle export"],
            read_only=dry_run,
        )

    if not dry_run and zip_output:
        return _empty_export_result(
            project_root=project_root_resolved,
            manifest_path=manifest_path,
            status="BUNDLE_ZIP_EXPORT_NOT_IMPLEMENTED",
            dry_run=False,
            planned_bundle_id=planned_bundle_id,
            planned_output_path=str(output_path),
            planned_output_root=planned_output_root,
            planned_bundle_type=bundle_type,
            planned_bundle_manifest=planned_bundle_manifest,
            planned_index=planned_index,
            errors=["Real zip report bundle export is not implemented. Use directory output without --zip."],
            read_only=False,
        )

    if not dry_run and output_path.exists():
        return _empty_export_result(
            project_root=project_root_resolved,
            manifest_path=manifest_path,
            status="OUTPUT_EXISTS",
            dry_run=False,
            planned_bundle_id=planned_bundle_id,
            planned_output_path=str(output_path),
            planned_output_root=planned_output_root,
            planned_bundle_type=bundle_type,
            planned_bundle_manifest=planned_bundle_manifest,
            planned_index=planned_index,
            errors=["bundle output directory already exists; overwrite/--force is not supported"],
            read_only=False,
        )

    if isolated_analysis is None and manifest_path.suffix.lower() != ".jsonl":
        return _empty_export_result(
            project_root=project_root_resolved,
            manifest_path=manifest_path,
            status="UNSUPPORTED_FORMAT",
            dry_run=dry_run,
            planned_bundle_id=planned_bundle_id,
            planned_output_path=str(output_path),
            planned_output_root=planned_output_root,
            planned_bundle_type=bundle_type,
            planned_bundle_manifest=planned_bundle_manifest,
            planned_index=planned_index,
            errors=["bundle export only supports manifest.jsonl"],
            read_only=dry_run,
        )

    if limit is not None and limit < 0:
        return _empty_export_result(
            project_root=project_root_resolved,
            manifest_path=manifest_path,
            status="BAD_PATH",
            dry_run=dry_run,
            planned_bundle_id=planned_bundle_id,
            planned_output_path=str(output_path),
            planned_output_root=planned_output_root,
            planned_bundle_type=bundle_type,
            planned_bundle_manifest=planned_bundle_manifest,
            planned_index=planned_index,
            errors=["--limit must be zero or greater"],
            read_only=dry_run,
        )

    if isolated_analysis is None and not manifest_path.exists():
        return _empty_export_result(
            project_root=project_root_resolved,
            manifest_path=manifest_path,
            status="NO_MANIFEST",
            dry_run=dry_run,
            planned_bundle_id=planned_bundle_id,
            planned_output_path=str(output_path),
            planned_output_root=planned_output_root,
            planned_bundle_type=bundle_type,
            planned_bundle_manifest=planned_bundle_manifest,
            planned_index=planned_index,
            warnings=["No runtime report manifest found at reports/python_tooling/manifest.jsonl."],
            read_only=dry_run,
        )

    analysis = isolated_analysis or _analyze_existing_manifest(
        action="export",
        manifest_path=manifest_path,
        project_root=project_root_resolved,
        limit=limit,
    )
    planned_files = _planned_bundle_files(analysis.planned_bundle_files, bundle_type=bundle_type)
    if planned_bundle_manifest:
        planned_files.insert(0, _internal_or_path(planned_bundle_manifest, output_path, bundle_type))
    if planned_index:
        planned_files.insert(1, _internal_or_path(planned_index, output_path, bundle_type))

    if dry_run:
        return ReportBundleExportPlanResult(
            action="export",
            dry_run=True,
            project_root=str(project_root_resolved),
            status=analysis.status,
            source_manifest_path=str(manifest_path),
            manifest_exists=analysis.manifest_exists,
            manifest_valid=analysis.manifest_valid,
            manifest_entry_count=analysis.manifest_entry_count,
            candidate_report_count=analysis.candidate_report_count,
            missing_report_count=analysis.missing_report_count,
            planned_bundle_id=planned_bundle_id,
            planned_output_path=str(output_path),
            planned_output_root=planned_output_root,
            planned_bundle_type=bundle_type,
            would_create_bundle=analysis.status == "OK",
            would_write_files=False,
            planned_files=planned_files,
            planned_bundle_manifest=planned_bundle_manifest,
            planned_index=planned_index,
            bundle_ready=analysis.status == "OK",
            real_export_supported=True,
            bundle_written=False,
            bundle_path=None,
            read_only=True,
            writes_files=False,
            runs_ce=False,
            warnings=analysis.warnings,
            errors=analysis.errors,
        )

    if analysis.status != "OK":
        return ReportBundleExportPlanResult(
            action="export",
            dry_run=False,
            project_root=str(project_root_resolved),
            status=analysis.status,
            source_manifest_path=str(manifest_path),
            manifest_exists=analysis.manifest_exists,
            manifest_valid=analysis.manifest_valid,
            manifest_entry_count=analysis.manifest_entry_count,
            candidate_report_count=analysis.candidate_report_count,
            missing_report_count=analysis.missing_report_count,
            planned_bundle_id=planned_bundle_id,
            planned_output_path=str(output_path),
            planned_output_root=planned_output_root,
            planned_bundle_type=bundle_type,
            would_create_bundle=False,
            would_write_files=False,
            planned_files=planned_files,
            planned_bundle_manifest=planned_bundle_manifest,
            planned_index=planned_index,
            bundle_ready=False,
            real_export_supported=True,
            bundle_written=False,
            bundle_path=None,
            read_only=False,
            writes_files=False,
            runs_ce=False,
            warnings=analysis.warnings,
            errors=analysis.errors,
        )

    duplicate_bundle_names = _duplicate_bundle_report_names(analysis.records)
    if duplicate_bundle_names:
        return _empty_export_result(
            project_root=project_root_resolved,
            manifest_path=manifest_path,
            status="INVALID_MANIFEST",
            dry_run=False,
            planned_bundle_id=planned_bundle_id,
            planned_output_path=str(output_path),
            planned_output_root=planned_output_root,
            planned_bundle_type=bundle_type,
            planned_bundle_manifest=planned_bundle_manifest,
            planned_index=planned_index,
            manifest_exists=True,
            errors=[f"duplicate bundle report filename: {name}" for name in duplicate_bundle_names],
            read_only=False,
        )

    return _write_directory_bundle(
        project_root=project_root_resolved,
        manifest_path=manifest_path,
        output_path=output_path,
        planned_output_root=planned_output_root,
        planned_bundle_id=planned_bundle_id,
        planned_bundle_manifest=planned_bundle_manifest,
        planned_index=planned_index,
        analysis=analysis,
        planned_files=planned_files,
    )


def _write_directory_bundle(
    *,
    project_root: Path,
    manifest_path: Path,
    output_path: Path,
    planned_output_root: str,
    planned_bundle_id: str | None,
    planned_bundle_manifest: str | None,
    planned_index: str | None,
    analysis: ReportBundleResult,
    planned_files: list[str],
) -> ReportBundleExportPlanResult:
    assert planned_bundle_id is not None
    output_parent = output_path.parent
    temp_dir = output_parent / f".{output_path.name}.tmp-{uuid4().hex}"
    temp_reports_dir = temp_dir / "reports"
    source_infos: list[dict[str, object]] = []
    warnings = list(analysis.warnings)
    errors: list[str] = []
    try:
        for record in _candidate_records(analysis.records):
            assert record.output_path is not None
            source_path = _resolve_report_path(record.output_path, project_root).resolve(strict=True)
            if not _is_relative_to(source_path, (project_root / "reports" / "python_tooling").resolve(strict=False)):
                errors.append(f"source report is outside reports/python_tooling: {record.output_path}")
                continue
            source_infos.append(
                {
                    "record": record,
                    "source_path": source_path,
                    "bundle_name": source_path.name,
                    "file_size": source_path.stat().st_size,
                    "sha256": _sha256_file(source_path),
                }
            )
    except OSError as exc:
        errors.append(f"failed to inspect source report: {exc}")

    if errors:
        return _empty_export_result(
            project_root=project_root,
            manifest_path=manifest_path,
            status="BUNDLE_EXPORT_FAILED",
            dry_run=False,
            planned_bundle_id=planned_bundle_id,
            planned_output_path=str(output_path),
            planned_output_root=planned_output_root,
            planned_bundle_type="directory",
            planned_bundle_manifest=planned_bundle_manifest,
            planned_index=planned_index,
            manifest_exists=True,
            errors=errors,
            read_only=False,
        )

    try:
        output_parent.mkdir(parents=True, exist_ok=True)
        temp_reports_dir.mkdir(parents=True, exist_ok=False)
        included_reports: list[dict[str, object]] = []
        per_file_hashes: dict[str, str] = {}
        for info in source_infos:
            record = info["record"]
            assert isinstance(record, BundleManifestEntry)
            source_path = info["source_path"]
            assert isinstance(source_path, Path)
            bundle_name = str(info["bundle_name"])
            destination = temp_reports_dir / bundle_name
            shutil.copy2(source_path, destination)
            copied_hash = _sha256_file(destination)
            expected_hash = str(info["sha256"])
            if copied_hash != expected_hash:
                raise RuntimeError(f"copied hash mismatch for {bundle_name}")
            bundle_path = f"reports/{bundle_name}"
            per_file_hashes[bundle_path] = copied_hash
            included_reports.append(
                {
                    "report_id": record.report_id,
                    "report_type": record.report_type,
                    "source_path": record.output_path,
                    "bundle_path": bundle_path,
                    "file_size": info["file_size"],
                    "sha256": copied_hash,
                }
            )

        created_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        bundle_manifest = {
            "schema_version": 1,
            "bundle_id": planned_bundle_id,
            "created_at": created_at,
            "bundle_type": "directory",
            "source_manifest_path": str(manifest_path),
            "included_reports": included_reports,
            "included_manifest_entries": [record.to_dict() for record in _candidate_records(analysis.records)],
            "output_path": str(output_path),
            "output_root": planned_output_root,
            "file_count": len(included_reports),
            "total_size": sum(int(report["file_size"]) for report in included_reports),
            "per_file_hashes": per_file_hashes,
            "command": f"python -m armedforces_tool report bundle export --out {output_path}",
            "status": "success",
        }
        (temp_dir / PLANNED_BUNDLE_MANIFEST_NAME).write_text(
            json.dumps(bundle_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (temp_dir / PLANNED_BUNDLE_INDEX_NAME).write_text(
            _render_bundle_index(
                bundle_id=planned_bundle_id,
                created_at=created_at,
                manifest_path=manifest_path,
                included_reports=included_reports,
            ),
            encoding="utf-8",
        )
        for info in source_infos:
            bundle_name = str(info["bundle_name"])
            copied = temp_reports_dir / bundle_name
            if _sha256_file(copied) != str(info["sha256"]):
                raise RuntimeError(f"post-write hash mismatch for {bundle_name}")
        temp_dir.rename(output_path)
    except Exception as exc:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        return _empty_export_result(
            project_root=project_root,
            manifest_path=manifest_path,
            status="BUNDLE_EXPORT_FAILED",
            dry_run=False,
            planned_bundle_id=planned_bundle_id,
            planned_output_path=str(output_path),
            planned_output_root=planned_output_root,
            planned_bundle_type="directory",
            planned_bundle_manifest=planned_bundle_manifest,
            planned_index=planned_index,
            manifest_exists=True,
            errors=[f"failed to write bundle: {exc}"],
            read_only=False,
        )

    return ReportBundleExportPlanResult(
        action="export",
        dry_run=False,
        project_root=str(project_root),
        status="BUNDLE_EXPORT_OK",
        source_manifest_path=str(manifest_path),
        manifest_exists=analysis.manifest_exists,
        manifest_valid=analysis.manifest_valid,
        manifest_entry_count=analysis.manifest_entry_count,
        candidate_report_count=analysis.candidate_report_count,
        missing_report_count=analysis.missing_report_count,
        planned_bundle_id=planned_bundle_id,
        planned_output_path=str(output_path),
        planned_output_root=planned_output_root,
        planned_bundle_type="directory",
        would_create_bundle=True,
        would_write_files=True,
        planned_files=planned_files,
        planned_bundle_manifest=planned_bundle_manifest,
        planned_index=planned_index,
        bundle_ready=True,
        real_export_supported=True,
        bundle_written=True,
        bundle_path=str(output_path),
        read_only=False,
        writes_files=True,
        runs_ce=False,
        warnings=warnings,
        errors=[],
    )


def format_report_bundle(result: ReportBundleResult) -> str:
    rows = [
        ("action", result.action),
        ("status", result.status),
        ("source_manifest_path", result.source_manifest_path),
        ("manifest_exists", result.manifest_exists),
        ("manifest_valid", result.manifest_valid),
        ("manifest_entry_count", result.manifest_entry_count),
        ("candidate_report_count", result.candidate_report_count),
        ("missing_report_count", result.missing_report_count),
        ("referenced_reports_checked", result.referenced_reports_checked),
        ("planned_bundle_id", result.planned_bundle_id),
        ("planned_bundle_root", result.planned_bundle_root),
        ("planned_bundle_manifest", result.planned_bundle_manifest),
        ("bundle_ready", result.bundle_ready),
        ("would_write_bundle", result.would_write_bundle),
        ("read_only", result.read_only),
        ("writes_files", result.writes_files),
        ("runs_ce", result.runs_ce),
    ]
    width = max(len(label) for label, _ in rows)
    lines = ["Report Bundle", "Field".ljust(width) + "  Value", "-".ljust(width, "-") + "  -----"]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {_display(value)}")

    if result.planned_bundle_files:
        lines.append("")
        lines.append("Planned Bundle Files")
        lines.extend(f"- {path}" for path in result.planned_bundle_files)

    if result.missing_reports:
        lines.append("")
        lines.append("Missing Reports")
        lines.extend(f"- {path}" for path in result.missing_reports)

    if result.duplicate_report_ids:
        lines.append("")
        lines.append("Duplicate Report IDs")
        lines.extend(f"- {report_id}" for report_id in result.duplicate_report_ids)

    if result.invalid_entries:
        lines.append("")
        lines.append("Invalid Entries")
        for entry in result.invalid_entries:
            line = entry.get("line_number")
            errors = "; ".join(str(error) for error in entry.get("errors", []))
            lines.append(f"- line {line}: {errors}")

    if result.warnings:
        lines.append("")
        lines.append("Warnings")
        lines.extend(f"- {warning}" for warning in result.warnings)

    if result.errors:
        lines.append("")
        lines.append("Errors")
        lines.extend(f"- {error}" for error in result.errors)

    return "\n".join(lines)


def format_report_bundle_export_plan(result: ReportBundleExportPlanResult) -> str:
    rows = [
        ("action", result.action),
        ("dry_run", result.dry_run),
        ("status", result.status),
        ("source_manifest_path", result.source_manifest_path),
        ("manifest_exists", result.manifest_exists),
        ("manifest_valid", result.manifest_valid),
        ("manifest_entry_count", result.manifest_entry_count),
        ("candidate_report_count", result.candidate_report_count),
        ("missing_report_count", result.missing_report_count),
        ("planned_bundle_id", result.planned_bundle_id),
        ("planned_output_path", result.planned_output_path),
        ("planned_output_root", result.planned_output_root),
        ("planned_bundle_type", result.planned_bundle_type),
        ("would_create_bundle", result.would_create_bundle),
        ("would_write_files", result.would_write_files),
        ("writes_files", result.writes_files),
        ("planned_bundle_manifest", result.planned_bundle_manifest),
        ("planned_index", result.planned_index),
        ("bundle_ready", result.bundle_ready),
        ("real_export_supported", result.real_export_supported),
        ("bundle_written", result.bundle_written),
        ("bundle_path", result.bundle_path),
        ("read_only", result.read_only),
        ("runs_ce", result.runs_ce),
    ]
    width = max(len(label) for label, _ in rows)
    if result.dry_run:
        lines = [
            bundle_export_dry_run_message(
                bundle_dir=_display(result.planned_output_path),
                bundle_manifest_path=_display(result.planned_bundle_manifest),
                index_path=_display(result.planned_index),
                approved_root=_display(result.planned_output_root),
            ),
            "",
            "Dry-Run Details",
            "Field".ljust(width) + "  Value",
            "-".ljust(width, "-") + "  -----",
        ]
    elif _uses_real_bundle_export_success_message(result):
        lines = [
            bundle_export_complete_message(
                bundle_dir=_display(result.planned_output_path),
                bundle_manifest_path=_display(result.planned_bundle_manifest),
                index_path=_display(result.planned_index),
                approved_root=_display(result.planned_output_root),
                copied_report_count=result.candidate_report_count,
                next_verification_command="python -m armedforces_tool report bundle verify",
            ),
            "",
            "Bundle Export Details",
            "Field".ljust(width) + "  Value",
            "-".ljust(width, "-") + "  -----",
        ]
    else:
        lines = ["Report Bundle Export Plan", "Field".ljust(width) + "  Value", "-".ljust(width, "-") + "  -----"]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {_display(value)}")

    if result.planned_files:
        lines.append("")
        lines.append("Planned Files")
        lines.extend(f"- {path}" for path in result.planned_files)

    if result.warnings:
        lines.append("")
        lines.append("Warnings")
        lines.extend(f"- {warning}" for warning in result.warnings)

    if result.errors:
        lines.append("")
        lines.append("Errors")
        lines.extend(f"- {error}" for error in result.errors)

    return "\n".join(lines)


def _uses_real_bundle_export_success_message(result: ReportBundleExportPlanResult) -> bool:
    return (
        not result.dry_run
        and result.status == "BUNDLE_EXPORT_OK"
        and result.bundle_written
        and result.writes_files
        and result.planned_bundle_type == "directory"
    )


def _analyze_existing_manifest(
    *,
    action: str,
    manifest_path: Path,
    project_root: Path,
    limit: int | None,
) -> ReportBundleResult:
    records: list[BundleManifestEntry] = []
    errors: list[str] = []
    warnings: list[str] = []
    try:
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return _empty_result(
            action=action,
            project_root=project_root,
            manifest_path=manifest_path,
            status="INVALID_MANIFEST",
            manifest_exists=True,
            errors=[f"failed to read manifest: {exc}"],
        )

    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        records.append(_parse_manifest_line(raw_line, line_number=line_number, project_root=project_root))

    if limit is not None:
        records = records[:limit]

    report_id_counts = Counter(record.report_id for record in records if record.report_id)
    duplicate_report_ids = sorted(report_id for report_id, count in report_id_counts.items() if count > 1)
    if duplicate_report_ids:
        duplicate_set = set(duplicate_report_ids)
        records = [
            (
                BundleManifestEntry(
                    line_number=record.line_number,
                    report_id=record.report_id,
                    report_type=record.report_type,
                    output_path=record.output_path,
                    valid=False,
                    errors=record.errors + ["duplicate_report_id"],
                    data=record.data,
                )
                if record.report_id in duplicate_set
                else record
            )
            for record in records
        ]

    invalid_entries = [
        {
            "line_number": record.line_number,
            "report_id": record.report_id,
            "output_path": record.output_path,
            "errors": record.errors,
        }
        for record in records
        if not record.valid
    ]
    candidate_records = [record for record in records if record.valid and record.output_path]
    missing_reports: list[str] = []
    planned_bundle_files: list[str] = []
    for record in candidate_records:
        assert record.output_path is not None
        planned_bundle_files.append(record.output_path)
        if not _resolve_report_path(record.output_path, project_root).exists():
            missing_reports.append(record.output_path)

    manifest_valid = not invalid_entries and not duplicate_report_ids
    status = "OK"
    if not records:
        warnings.append("Manifest exists but contains no JSONL entries.")
        status = "NOT_READY"
    elif not manifest_valid:
        status = "INVALID_MANIFEST"
    elif missing_reports:
        status = "MISSING_REPORTS"

    planned_bundle_id = _planned_bundle_id(manifest_path, planned_bundle_files) if records else None
    planned_bundle_root = None
    planned_bundle_manifest = None
    if planned_bundle_id:
        root = project_root / PLANNED_BUNDLE_ROOT / planned_bundle_id
        planned_bundle_root = str(root)
        planned_bundle_manifest = str(root / PLANNED_BUNDLE_MANIFEST_NAME)

    return ReportBundleResult(
        action=action,
        project_root=str(project_root),
        status=status,
        source_manifest_path=str(manifest_path),
        manifest_exists=True,
        manifest_valid=manifest_valid,
        manifest_entry_count=len(records),
        candidate_report_count=len(candidate_records),
        missing_report_count=len(missing_reports),
        referenced_reports_checked=len(candidate_records),
        missing_reports=missing_reports,
        duplicate_report_ids=duplicate_report_ids,
        invalid_entries=invalid_entries,
        records=records,
        planned_bundle_id=planned_bundle_id,
        planned_bundle_root=planned_bundle_root,
        planned_bundle_files=planned_bundle_files,
        planned_bundle_manifest=planned_bundle_manifest,
        bundle_ready=status == "OK",
        would_write_bundle=False,
        read_only=True,
        writes_files=False,
        runs_ce=False,
        warnings=warnings,
        errors=errors,
    )


def _parse_manifest_line(raw_line: str, *, line_number: int, project_root: Path) -> BundleManifestEntry:
    errors: list[str] = []
    data: dict[str, object] = {}
    try:
        parsed = json.loads(raw_line)
        if isinstance(parsed, dict):
            data = parsed
        else:
            errors.append("entry is not a JSON object")
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON: {exc.msg}")

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")

    report_id = _str_or_none(data.get("report_id"))
    report_type = _str_or_none(data.get("report_type"))
    output_path = _str_or_none(data.get("output_path"))

    if "report_id" in data and not report_id:
        errors.append("report_id must be a non-empty string")
    if "report_type" in data and not report_type:
        errors.append("report_type must be a non-empty string")
    if "output_path" in data and not output_path:
        errors.append("output_path must be a non-empty string")
    if output_path:
        path_errors = _validate_report_output_path(output_path, project_root)
        errors.extend(path_errors)

    return BundleManifestEntry(
        line_number=line_number,
        report_id=report_id,
        report_type=report_type,
        output_path=output_path,
        valid=not errors,
        errors=errors,
        data=data,
    )


def _analyze_isolated_source_inputs(
    *,
    source_report: str | None,
    source_manifest: str | None,
    manifest: str | None,
    project_root: Path,
) -> tuple[Path, list[str], ReportBundleResult | None]:
    manifest_path = _resolve_user_path(source_manifest, project_root) if source_manifest else project_root / DEFAULT_BUNDLE_MANIFEST_PATH
    errors: list[str] = []

    if manifest:
        errors.append("--manifest cannot be used with --source-report or --source-manifest")
    if source_manifest and not source_report:
        errors.append("--source-manifest requires --source-report")
    if not source_report:
        return manifest_path.resolve(strict=False), errors, None

    source_report_path = _resolve_user_path(source_report, project_root)
    errors.extend(_validate_source_report_input(source_report, source_report_path, project_root))

    if source_manifest:
        source_manifest_path = _resolve_user_path(source_manifest, project_root)
        manifest_path = source_manifest_path
        errors.extend(_validate_source_manifest_input(source_manifest, source_manifest_path, project_root))
    else:
        source_manifest_path = None
        manifest_path = source_report_path

    if errors:
        return manifest_path.resolve(strict=False), errors, None

    source_report_resolved = source_report_path.resolve(strict=True)
    source_report_display = _project_relative_path(source_report_resolved, project_root)
    file_size = source_report_resolved.stat().st_size
    sha256 = _sha256_file(source_report_resolved)
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    report_id = f"source-{sha256[:12]}"
    data: dict[str, object] = {
        "report_id": report_id,
        "report_type": "source-report",
        "created_at": created_at,
        "output_path": source_report_display,
        "output_root": "reports/python_tooling",
        "file_size": file_size,
        "sha256": sha256,
        "command": "python -m armedforces_tool report bundle export --source-report",
        "dry_run": False,
        "status": "success",
    }
    record = BundleManifestEntry(
        line_number=1,
        report_id=report_id,
        report_type="source-report",
        output_path=source_report_display,
        valid=True,
        errors=[],
        data=data,
    )
    manifest_display_path = source_manifest_path.resolve(strict=True) if source_manifest_path else source_report_resolved

    return (
        manifest_display_path,
        [],
        ReportBundleResult(
            action="export",
            project_root=str(project_root),
            status="OK",
            source_manifest_path=str(manifest_display_path),
            manifest_exists=bool(source_manifest_path),
            manifest_valid=True,
            manifest_entry_count=1,
            candidate_report_count=1,
            missing_report_count=0,
            referenced_reports_checked=1,
            missing_reports=[],
            duplicate_report_ids=[],
            invalid_entries=[],
            records=[record],
            planned_bundle_id=None,
            planned_bundle_root=None,
            planned_bundle_files=[source_report_display],
            planned_bundle_manifest=None,
            bundle_ready=True,
            would_write_bundle=False,
            read_only=True,
            writes_files=False,
            runs_ce=False,
            warnings=[],
            errors=[],
        ),
    )


def _resolve_bundle_manifest_path(value: str | None, project_root: Path) -> tuple[Path, list[str]]:
    approved = (project_root / DEFAULT_BUNDLE_MANIFEST_PATH).resolve(strict=False)
    if value is None:
        return approved, []

    raw = Path(value)
    target = raw if raw.is_absolute() else project_root / raw
    target_resolved = target.resolve(strict=False)
    errors: list[str] = []

    if any(part == ".." for part in raw.parts):
        errors.append("path traversal is not allowed")
    if target_resolved != approved:
        errors.append("bundle manifest path must be reports/python_tooling/manifest.jsonl")
    if target_resolved.suffix.lower() != ".jsonl":
        errors.append("bundle manifest path must be a .jsonl file")

    return target_resolved, errors


def _validate_source_report_input(raw_value: str, path: Path, project_root: Path) -> list[str]:
    errors = _validate_report_output_path(raw_value, project_root)
    resolved = path.resolve(strict=False)
    default_report = (project_root / "reports" / "python_tooling" / "full_status.md").resolve(strict=False)
    if resolved == default_report:
        errors.append("source report path must not target production/default reports/python_tooling/full_status.md")
    if not resolved.exists():
        errors.append("source report path does not exist")
    elif not resolved.is_file():
        errors.append("source report path must be a file")
    return errors


def _validate_source_manifest_input(raw_value: str, path: Path, project_root: Path) -> list[str]:
    errors: list[str] = []
    raw = Path(raw_value)
    resolved = path.resolve(strict=False)
    approved_root = (project_root / "reports" / "python_tooling").resolve(strict=False)
    default_manifest = (project_root / DEFAULT_BUNDLE_MANIFEST_PATH).resolve(strict=False)

    if any(part == ".." for part in raw.parts):
        errors.append("source manifest path traversal is not allowed")
    if not _is_relative_to(resolved, approved_root):
        errors.append("source manifest path must be under reports/python_tooling")
    if resolved == default_manifest:
        errors.append("source manifest path must not target production/default reports/python_tooling/manifest.jsonl")
    if resolved.suffix.lower() != ".jsonl":
        errors.append("source manifest path must be a .jsonl file")
    if not resolved.exists():
        errors.append("source manifest path does not exist")
    elif not resolved.is_file():
        errors.append("source manifest path must be a file")
    return errors


def _resolve_user_path(value: str | None, project_root: Path) -> Path:
    if not value:
        return project_root
    raw = Path(value)
    return raw if raw.is_absolute() else project_root / raw


def _project_relative_path(path: Path, project_root: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return str(path)


def _validate_report_output_path(value: str, project_root: Path) -> list[str]:
    errors: list[str] = []
    raw = Path(value)
    target = raw if raw.is_absolute() else project_root / raw
    target_resolved = target.resolve(strict=False)
    approved_root = (project_root / "reports" / "python_tooling").resolve(strict=False)

    if any(part == ".." for part in raw.parts):
        errors.append("report output path traversal is not allowed")
    if target_resolved.suffix.lower() != ".md":
        errors.append("report output path must be a .md file")
    if not _is_relative_to(target_resolved, approved_root):
        errors.append("report output path must be under reports/python_tooling")

    return errors


def _resolve_bundle_output_path(
    value: str | None,
    zip_output: bool,
    project_root: Path,
    *,
    isolated_mode: bool = False,
) -> tuple[Path | None, list[str], str | None]:
    if not value:
        return None, ["--out is required for report bundle export"], "zip" if zip_output else "directory"

    raw = Path(value)
    target = raw if raw.is_absolute() else project_root / raw
    target_resolved = target.resolve(strict=False)
    approved_root = (project_root / "reports" / "python_tooling").resolve(strict=False) if isolated_mode else (project_root / PLANNED_BUNDLE_ROOT).resolve(strict=False)
    production_bundle_root = (project_root / PLANNED_BUNDLE_ROOT).resolve(strict=False)
    errors: list[str] = []
    bundle_type = "zip" if zip_output else "directory"

    if any(part == ".." for part in raw.parts):
        errors.append("bundle output path traversal is not allowed")
    if not _is_relative_to(target_resolved, approved_root) or target_resolved == approved_root:
        errors.append(
            "isolated bundle output path must be under reports/python_tooling"
            if isolated_mode
            else "bundle output path must be under reports/python_tooling/bundles"
        )
    if isolated_mode and _is_relative_to(target_resolved, production_bundle_root):
        errors.append("isolated bundle output path must not target reports/python_tooling/bundles")

    bundle_id = _bundle_id_from_output(target_resolved, bundle_type)
    if bundle_id and not _is_safe_bundle_id(bundle_id):
        errors.append("bundle id must use only letters, numbers, '.', '_', or '-' and start with a letter or number")

    if zip_output:
        if target_resolved.suffix.lower() != ".zip":
            errors.append("zip bundle output must end with .zip")
    else:
        if target_resolved.suffix:
            errors.append("directory bundle output must be a directory path without a file extension")

    return target_resolved, errors, bundle_type


def _planned_output_root(output_path: Path | None, project_root: Path, *, isolated_mode: bool) -> str:
    if output_path is not None and isolated_mode:
        return str((project_root / "reports" / "python_tooling").resolve(strict=False))
    return str((project_root / PLANNED_BUNDLE_ROOT).resolve(strict=False))


def _bundle_id_from_output(output_path: Path | None, bundle_type: str | None) -> str | None:
    if output_path is None:
        return None
    if bundle_type == "zip":
        return output_path.stem
    return output_path.name


def _planned_bundle_manifest(output_path: Path | None, bundle_type: str | None) -> str | None:
    if output_path is None:
        return None
    if bundle_type == "zip":
        return PLANNED_BUNDLE_MANIFEST_NAME
    return str(output_path / PLANNED_BUNDLE_MANIFEST_NAME)


def _planned_index(output_path: Path | None, bundle_type: str | None) -> str | None:
    if output_path is None:
        return None
    if bundle_type == "zip":
        return PLANNED_BUNDLE_INDEX_NAME
    return str(output_path / PLANNED_BUNDLE_INDEX_NAME)


def _planned_bundle_files(source_report_paths: list[str], *, bundle_type: str | None) -> list[str]:
    report_files = [f"reports/{Path(path).name}" for path in source_report_paths]
    if bundle_type == "zip":
        return report_files
    return report_files


def _internal_or_path(value: str, output_path: Path | None, bundle_type: str | None) -> str:
    if bundle_type == "zip" or output_path is None:
        return value
    try:
        return str(Path(value).relative_to(output_path))
    except ValueError:
        return value


def _resolve_report_path(value: str, project_root: Path) -> Path:
    raw = Path(value)
    return raw if raw.is_absolute() else project_root / raw


def _planned_bundle_id(manifest_path: Path, planned_bundle_files: list[str]) -> str:
    digest = hashlib.sha256()
    try:
        digest.update(manifest_path.read_bytes())
    except OSError:
        digest.update(str(manifest_path).encode("utf-8"))
    for path in planned_bundle_files:
        digest.update(path.encode("utf-8"))
    return f"bundle-{digest.hexdigest()[:12]}"


def _candidate_records(records: list[BundleManifestEntry]) -> list[BundleManifestEntry]:
    return [record for record in records if record.valid and record.output_path]


def _duplicate_bundle_report_names(records: list[BundleManifestEntry]) -> list[str]:
    names = [Path(record.output_path).name for record in _candidate_records(records) if record.output_path]
    counts = Counter(names)
    return sorted(name for name, count in counts.items() if count > 1)


def _is_safe_bundle_id(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _render_bundle_index(
    *,
    bundle_id: str,
    created_at: str,
    manifest_path: Path,
    included_reports: list[dict[str, object]],
) -> str:
    lines = [
        f"# Report Bundle: {bundle_id}",
        "",
        "## Summary",
        "",
        f"- Created at: `{created_at}`",
        f"- Source manifest: `{manifest_path}`",
        f"- Included reports: `{len(included_reports)}`",
        "",
        "## Included Reports",
        "",
    ]
    for report in included_reports:
        lines.append(f"- `{report['bundle_path']}` from `{report['source_path']}`")
    lines.extend(
        [
            "",
            "## Source of Truth",
            "",
            "`bundle_manifest.json` is the source of truth for this bundle.",
            "",
        ]
    )
    return "\n".join(lines)


def _empty_result(
    *,
    action: str,
    project_root: Path,
    manifest_path: Path,
    status: str,
    manifest_exists: bool = False,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> ReportBundleResult:
    return ReportBundleResult(
        action=action,
        project_root=str(project_root),
        status=status,
        source_manifest_path=str(manifest_path),
        manifest_exists=manifest_exists,
        manifest_valid=False,
        manifest_entry_count=0,
        candidate_report_count=0,
        missing_report_count=0,
        referenced_reports_checked=0,
        missing_reports=[],
        duplicate_report_ids=[],
        invalid_entries=[],
        records=[],
        planned_bundle_id=None,
        planned_bundle_root=None,
        planned_bundle_files=[],
        planned_bundle_manifest=None,
        bundle_ready=False,
        would_write_bundle=False,
        read_only=True,
        writes_files=False,
        runs_ce=False,
        warnings=warnings or [],
        errors=errors or [],
    )


def _empty_export_result(
    *,
    project_root: Path,
    manifest_path: Path,
    status: str,
    dry_run: bool,
    planned_bundle_id: str | None = None,
    planned_output_path: str | None = None,
    planned_output_root: str | None = None,
    planned_bundle_type: str | None = None,
    planned_bundle_manifest: str | None = None,
    planned_index: str | None = None,
    manifest_exists: bool = False,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    read_only: bool = True,
) -> ReportBundleExportPlanResult:
    return ReportBundleExportPlanResult(
        action="export",
        dry_run=dry_run,
        project_root=str(project_root),
        status=status,
        source_manifest_path=str(manifest_path),
        manifest_exists=manifest_exists,
        manifest_valid=False,
        manifest_entry_count=0,
        candidate_report_count=0,
        missing_report_count=0,
        planned_bundle_id=planned_bundle_id,
        planned_output_path=planned_output_path,
        planned_output_root=planned_output_root,
        planned_bundle_type=planned_bundle_type,
        would_create_bundle=False,
        would_write_files=False,
        planned_files=[],
        planned_bundle_manifest=planned_bundle_manifest,
        planned_index=planned_index,
        bundle_ready=False,
        real_export_supported=False,
        bundle_written=False,
        bundle_path=None,
        read_only=read_only,
        writes_files=False,
        runs_ce=False,
        warnings=warnings or [],
        errors=errors or [],
    )


def _str_or_none(value: object) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _display(value: object | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
