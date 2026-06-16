from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .report_manifest import REQUIRED_FIELDS
from .safety import DEFAULT_PROJECT_ROOT

DEFAULT_BUNDLE_MANIFEST_PATH = Path("reports/python_tooling/manifest.jsonl")
PLANNED_BUNDLE_ROOT = Path("reports/python_tooling/bundles")
PLANNED_BUNDLE_MANIFEST_NAME = "bundle_manifest.json"


@dataclass(frozen=True)
class BundleManifestEntry:
    line_number: int
    report_id: str | None
    report_type: str | None
    output_path: str | None
    valid: bool
    errors: list[str]

    def to_dict(self) -> dict[str, object | None]:
        return {
            "line_number": self.line_number,
            "report_id": self.report_id,
            "report_type": self.report_type,
            "output_path": self.output_path,
            "valid": self.valid,
            "errors": self.errors,
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
