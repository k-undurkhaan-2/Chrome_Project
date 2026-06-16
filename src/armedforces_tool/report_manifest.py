from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .report_export import APPROVED_OUTPUT_ROOTS, PROTECTED_PATHS
from .safety import DEFAULT_PROJECT_ROOT

DEFAULT_MANIFEST_CANDIDATES = (
    Path("reports/python_tooling/manifest.jsonl"),
    Path("reports/python_tooling/manifest.json"),
    Path("docs/reports/python_tooling/manifest.jsonl"),
    Path("docs/reports/python_tooling/manifest.json"),
)

ALLOWED_MANIFEST_FILENAMES = {"manifest.jsonl", "manifest.json", "report_index.md"}
REQUIRED_FIELDS = (
    "report_id",
    "report_type",
    "created_at",
    "output_path",
    "output_root",
    "file_size",
    "sha256",
    "command",
    "dry_run",
    "status",
)


@dataclass
class ManifestRecord:
    line_number: int
    report_id: str | None
    report_type: str | None
    created_at: str | None
    output_path: str | None
    output_root: str | None
    file_size: int | None
    sha256: str | None
    command: str | None
    dry_run: bool | None
    status: str | None
    valid: bool
    errors: list[str]

    def to_dict(self) -> dict[str, object | None]:
        return {
            "line_number": self.line_number,
            "report_id": self.report_id,
            "report_type": self.report_type,
            "created_at": self.created_at,
            "output_path": self.output_path,
            "output_root": self.output_root,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "command": self.command,
            "dry_run": self.dry_run,
            "status": self.status,
            "valid": not self.errors,
            "errors": self.errors,
        }


@dataclass(frozen=True)
class ReportManifestResult:
    action: str
    project_root: str
    manifest_path: str | None
    manifest_exists: bool
    manifest_format: str | None
    candidate_paths: list[str]
    explicit_path: bool
    status: str
    entry_count: int
    valid_count: int
    invalid_count: int
    duplicate_report_id_count: int
    missing_report_count: int
    missing_report_refs: list[str]
    records: list[ManifestRecord]
    warnings: list[str]
    errors: list[str]
    read_only: bool = True
    writes_files: bool = False
    runs_ce: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "project_root": self.project_root,
            "manifest_path": self.manifest_path,
            "manifest_exists": self.manifest_exists,
            "manifest_format": self.manifest_format,
            "candidate_paths": self.candidate_paths,
            "explicit_path": self.explicit_path,
            "status": self.status,
            "entry_count": self.entry_count,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "duplicate_report_id_count": self.duplicate_report_id_count,
            "missing_report_count": self.missing_report_count,
            "missing_report_refs": self.missing_report_refs,
            "records": [record.to_dict() for record in self.records],
            "warnings": self.warnings,
            "errors": self.errors,
            "read_only": self.read_only,
            "writes_files": self.writes_files,
            "runs_ce": self.runs_ce,
        }


def analyze_report_manifest(
    *,
    action: str,
    path: str | None = None,
    project_root: Path = DEFAULT_PROJECT_ROOT,
) -> ReportManifestResult:
    normalized_action = (action or "").strip().lower()
    if normalized_action not in {"preview", "list", "verify"}:
        return _empty_result(
            action=normalized_action,
            project_root=project_root,
            status="BAD_ACTION",
            errors=[f"unsupported manifest action: {action}"],
        )

    project_root_resolved = project_root.resolve()
    candidates = [(project_root_resolved / candidate).resolve(strict=False) for candidate in DEFAULT_MANIFEST_CANDIDATES]
    candidate_paths = [str(candidate) for candidate in candidates]

    if path:
        manifest_path, path_errors = _resolve_manifest_path(path, project_root_resolved)
        if path_errors:
            return _empty_result(
                action=normalized_action,
                project_root=project_root_resolved,
                manifest_path=str(manifest_path) if manifest_path is not None else None,
                explicit_path=True,
                candidate_paths=candidate_paths,
                status="BAD_PATH",
                errors=path_errors,
            )
        assert manifest_path is not None
    else:
        manifest_path = next((candidate for candidate in candidates if candidate.exists()), None)
        if manifest_path is None:
            return _empty_result(
                action=normalized_action,
                project_root=project_root_resolved,
                candidate_paths=candidate_paths,
                status="NO_MANIFEST",
                warnings=["No report manifest found under approved report roots."],
            )

    if not manifest_path.exists():
        return _empty_result(
            action=normalized_action,
            project_root=project_root_resolved,
            manifest_path=str(manifest_path),
            explicit_path=bool(path),
            candidate_paths=candidate_paths,
            status="NO_MANIFEST",
            errors=["Manifest path does not exist."] if path else [],
            warnings=[] if path else ["No report manifest found under approved report roots."],
        )

    manifest_format = _manifest_format(manifest_path)
    if manifest_format != "jsonl":
        return _empty_result(
            action=normalized_action,
            project_root=project_root_resolved,
            manifest_path=str(manifest_path),
            explicit_path=bool(path),
            candidate_paths=candidate_paths,
            status="UNSUPPORTED_FORMAT",
            manifest_format=manifest_format,
            errors=[f"Manifest format is planned but not supported in this phase: {manifest_path.name}"],
        )

    return _analyze_jsonl_manifest(
        action=normalized_action,
        manifest_path=manifest_path,
        project_root=project_root_resolved,
        explicit_path=bool(path),
        candidate_paths=candidate_paths,
    )


def format_report_manifest(result: ReportManifestResult) -> str:
    rows = [
        ("action", result.action),
        ("manifest_path", result.manifest_path),
        ("manifest_exists", result.manifest_exists),
        ("manifest_format", result.manifest_format),
        ("explicit_path", result.explicit_path),
        ("status", result.status),
        ("entry_count", result.entry_count),
        ("valid_count", result.valid_count),
        ("invalid_count", result.invalid_count),
        ("duplicate_report_id_count", result.duplicate_report_id_count),
        ("missing_report_count", result.missing_report_count),
        ("read_only", result.read_only),
        ("writes_files", result.writes_files),
        ("runs_ce", result.runs_ce),
    ]
    width = max(len(label) for label, _ in rows)
    lines = ["Report Manifest", "Field".ljust(width) + "  Value", "-".ljust(width, "-") + "  -----"]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {_display(value)}")

    if result.candidate_paths:
        lines.append("")
        lines.append("Candidate Paths")
        lines.extend(f"- {path}" for path in result.candidate_paths)

    if result.missing_report_refs:
        lines.append("")
        lines.append("Missing Report References")
        lines.extend(f"- {ref}" for ref in result.missing_report_refs)

    if result.records and result.action in {"list", "verify"}:
        lines.append("")
        lines.append("Manifest Entries")
        headers = ["line", "report_id", "report_type", "status", "valid", "errors"]
        table_rows = [
            [
                str(record.line_number),
                _display(record.report_id),
                _display(record.report_type),
                _display(record.status),
                _display(not record.errors),
                "; ".join(record.errors) if record.errors else "-",
            ]
            for record in result.records
        ]
        lines.extend(_format_table(headers, table_rows))

    if result.warnings:
        lines.append("")
        lines.append("Warnings")
        lines.extend(f"- {warning}" for warning in result.warnings)

    if result.errors:
        lines.append("")
        lines.append("Errors")
        lines.extend(f"- {error}" for error in result.errors)

    return "\n".join(lines)


def _analyze_jsonl_manifest(
    *,
    action: str,
    manifest_path: Path,
    project_root: Path,
    explicit_path: bool,
    candidate_paths: list[str],
) -> ReportManifestResult:
    records: list[ManifestRecord] = []
    warnings: list[str] = []
    errors: list[str] = []
    try:
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return _empty_result(
            action=action,
            project_root=project_root,
            manifest_path=str(manifest_path),
            manifest_format="jsonl",
            manifest_exists=True,
            explicit_path=explicit_path,
            candidate_paths=candidate_paths,
            status="INVALID_MANIFEST",
            errors=[f"Failed to read manifest: {exc}"],
        )

    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        records.append(_parse_jsonl_record(raw_line, line_number=line_number))

    report_id_counts = Counter(record.report_id for record in records if record.report_id)
    duplicate_ids = {report_id for report_id, count in report_id_counts.items() if count > 1}
    duplicate_report_id_count = sum(report_id_counts[report_id] - 1 for report_id in duplicate_ids)
    if duplicate_ids:
        for record in records:
            if record.report_id in duplicate_ids:
                record.errors.append("duplicate_report_id")
                record.valid = False

    missing_refs = _missing_report_refs(records, project_root=project_root)
    invalid_count = sum(1 for record in records if record.errors)
    valid_count = len(records) - invalid_count

    status = "OK"
    if invalid_count or duplicate_report_id_count or missing_refs:
        status = "INVALID_MANIFEST"
    if not records:
        warnings.append("Manifest exists but contains no JSONL entries.")

    return ReportManifestResult(
        action=action,
        project_root=str(project_root),
        manifest_path=str(manifest_path),
        manifest_exists=True,
        manifest_format="jsonl",
        candidate_paths=candidate_paths,
        explicit_path=explicit_path,
        status=status,
        entry_count=len(records),
        valid_count=valid_count,
        invalid_count=invalid_count,
        duplicate_report_id_count=duplicate_report_id_count,
        missing_report_count=len(missing_refs),
        missing_report_refs=missing_refs,
        records=records,
        warnings=warnings,
        errors=errors,
    )


def _parse_jsonl_record(raw_line: str, *, line_number: int) -> ManifestRecord:
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
    created_at = _str_or_none(data.get("created_at"))
    output_path = _str_or_none(data.get("output_path"))
    output_root = _str_or_none(data.get("output_root"))
    sha256 = _str_or_none(data.get("sha256"))
    command = _str_or_none(data.get("command"))
    status = _str_or_none(data.get("status"))
    file_size = data.get("file_size") if isinstance(data.get("file_size"), int) and not isinstance(data.get("file_size"), bool) else None
    dry_run = data.get("dry_run") if isinstance(data.get("dry_run"), bool) else None

    if "file_size" in data and file_size is None:
        errors.append("file_size must be an integer")
    if "dry_run" in data and dry_run is None:
        errors.append("dry_run must be a boolean")
    for field_name, value in [
        ("report_id", report_id),
        ("report_type", report_type),
        ("created_at", created_at),
        ("output_path", output_path),
        ("output_root", output_root),
        ("sha256", sha256),
        ("command", command),
        ("status", status),
    ]:
        if field_name in data and not value:
            errors.append(f"{field_name} must be a non-empty string")

    return ManifestRecord(
        line_number=line_number,
        report_id=report_id,
        report_type=report_type,
        created_at=created_at,
        output_path=output_path,
        output_root=output_root,
        file_size=file_size,
        sha256=sha256,
        command=command,
        dry_run=dry_run,
        status=status,
        valid=not errors,
        errors=errors,
    )


def _missing_report_refs(records: list[ManifestRecord], *, project_root: Path) -> list[str]:
    missing: list[str] = []
    for record in records:
        if record.errors or not record.output_path:
            continue
        output_path = _resolve_output_ref(record.output_path, project_root)
        if not output_path.exists():
            missing.append(record.output_path)
    return missing


def _resolve_manifest_path(value: str, project_root: Path) -> tuple[Path | None, list[str]]:
    raw = Path(value)
    target = raw if raw.is_absolute() else project_root / raw
    target_resolved = target.resolve(strict=False)
    errors: list[str] = []

    if any(part == ".." for part in raw.parts):
        errors.append("path traversal is not allowed")
    if target_resolved.name not in ALLOWED_MANIFEST_FILENAMES:
        errors.append("manifest path must be named manifest.jsonl, manifest.json, or report_index.md")

    approved_roots = [(project_root / root).resolve(strict=False) for root in APPROVED_OUTPUT_ROOTS]
    if not any(_is_relative_to(target_resolved, root) for root in approved_roots):
        errors.append("manifest path must be under reports/python_tooling or docs/reports/python_tooling")

    for protected in PROTECTED_PATHS:
        protected_resolved = (project_root / protected).resolve(strict=False)
        if target_resolved == protected_resolved or _is_relative_to(target_resolved, protected_resolved):
            errors.append(f"manifest path is protected: {protected.as_posix()}")
            break

    return target_resolved, errors


def _resolve_output_ref(value: str, project_root: Path) -> Path:
    raw = Path(value)
    return raw if raw.is_absolute() else project_root / raw


def _manifest_format(path: Path) -> str:
    if path.name == "manifest.jsonl":
        return "jsonl"
    if path.name == "manifest.json":
        return "json"
    if path.name == "report_index.md":
        return "markdown"
    return "unknown"


def _empty_result(
    *,
    action: str,
    project_root: Path,
    status: str,
    manifest_path: str | None = None,
    manifest_exists: bool = False,
    manifest_format: str | None = None,
    explicit_path: bool = False,
    candidate_paths: list[str] | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> ReportManifestResult:
    return ReportManifestResult(
        action=action,
        project_root=str(project_root),
        manifest_path=manifest_path,
        manifest_exists=manifest_exists,
        manifest_format=manifest_format,
        candidate_paths=candidate_paths or [],
        explicit_path=explicit_path,
        status=status,
        entry_count=0,
        valid_count=0,
        invalid_count=0,
        duplicate_report_id_count=0,
        missing_report_count=0,
        missing_report_refs=[],
        records=[],
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


def _format_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    lines = [
        " ".join(header.ljust(widths[index]) for index, header in enumerate(headers)),
        " ".join("-" * widths[index] for index in range(len(headers))),
    ]
    for row in rows:
        lines.append(" ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
    return lines


def _display(value: object | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
