from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .report_preview import REPORT_TYPES, preview_report
from .safety import DEFAULT_PROJECT_ROOT

APPROVED_OUTPUT_ROOTS = (
    Path("reports/python_tooling"),
    Path("docs/reports/python_tooling"),
)

PROTECTED_PATHS = (
    Path("log"),
    Path("src"),
    Path("tests"),
    Path("docs/codex_tasks"),
    Path(".git"),
    Path(".codex"),
    Path("src/run_case_config.local.lua"),
    Path("src/run_case_config.local.lua.bak"),
    Path("log/case_registry.jsonl"),
    Path("log/case_intake.local.jsonl"),
    Path("log/active_test_session.local.json"),
    Path("log/test_session_history.local.jsonl"),
    Path("log/baselines"),
)


@dataclass(frozen=True)
class ReportExportDryRunResult:
    report_type: str
    dry_run: bool
    would_write: bool
    wrote_file: bool
    target_path: str | None
    output_path: str | None
    approved_output_root: str | None
    target_exists: bool
    target_exists_before: bool
    would_overwrite: bool
    overwritten: bool
    force: bool
    path_safety_status: str
    conclusion: str
    recommendation: str
    warnings: list[str]
    errors: list[str]
    content_line_count: int | None = None
    content_size_bytes: int | None = None
    bytes_written: int | None = None
    read_only: bool = True
    writes_files: bool = False
    runs_ce: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "report_type": self.report_type,
            "dry_run": self.dry_run,
            "would_write": self.would_write,
            "wrote_file": self.wrote_file,
            "target_path": self.target_path,
            "output_path": self.output_path,
            "approved_output_root": self.approved_output_root,
            "target_exists": self.target_exists,
            "target_exists_before": self.target_exists_before,
            "would_overwrite": self.would_overwrite,
            "overwritten": self.overwritten,
            "force": self.force,
            "path_safety_status": self.path_safety_status,
            "conclusion": self.conclusion,
            "recommendation": self.recommendation,
            "warnings": self.warnings,
            "errors": self.errors,
            "content_line_count": self.content_line_count,
            "content_size_bytes": self.content_size_bytes,
            "bytes_written": self.bytes_written,
            "read_only": self.read_only,
            "writes_files": self.writes_files,
            "runs_ce": self.runs_ce,
        }


def plan_report_export(
    *,
    report_type: str,
    dry_run: bool,
    output_dir: str | None = None,
    out: str | None = None,
    force: bool = False,
    latest: int = 20,
    profile: str = "full",
    project_root: Path = DEFAULT_PROJECT_ROOT,
    generated_at: datetime | None = None,
) -> ReportExportDryRunResult:
    normalized_report_type = _normalize_report_type(report_type)
    target, target_errors = _target_from_args(
        report_type=normalized_report_type,
        output_dir=output_dir,
        out=out,
        generated_at=generated_at or datetime.now(timezone.utc),
        project_root=project_root,
    )
    if target_errors:
        return _result(
            report_type=normalized_report_type,
            dry_run=dry_run,
            target_path=str(target) if target is not None else None,
            conclusion=_rejected_conclusion(dry_run),
            path_safety_status="PATH_REJECTED",
            errors=target_errors,
            recommendation="Use --out or --output-dir under reports/python_tooling or docs/reports/python_tooling.",
        )

    assert target is not None
    safety = _validate_target_path(target=target, project_root=project_root)
    if safety["errors"]:
        return _result(
            report_type=normalized_report_type,
            dry_run=dry_run,
            target_path=str(target),
            approved_output_root=safety["approved_output_root"],
            target_exists=target.exists(),
            conclusion=_rejected_conclusion(dry_run),
            path_safety_status="PATH_REJECTED",
            errors=safety["errors"],
            recommendation="Choose a .md path under reports/python_tooling or docs/reports/python_tooling.",
        )

    warnings = list(safety["warnings"])
    target_exists = target.exists()
    would_overwrite = bool(target_exists and force)
    path_safety_status = "PATH_OK"
    if target_exists and not force:
        if dry_run:
            warnings.append("target exists; real export would require --force")
            path_safety_status = "PATH_WARN"
        else:
            return _result(
                report_type=normalized_report_type,
                dry_run=False,
                target_path=str(target),
                approved_output_root=safety["approved_output_root"],
                target_exists=target_exists,
                target_exists_before=target_exists,
                force=force,
                conclusion="REPORT_EXPORT_OVERWRITE_REJECTED",
                path_safety_status="PATH_REJECTED",
                errors=["target exists; rerun with --force to overwrite"],
                recommendation="Choose a new .md target path or rerun with --force after reviewing the existing file.",
            )

    preview = preview_report(report_type=normalized_report_type, latest=latest, profile=profile)
    content = preview.markdown
    content_size_bytes = len(content.encode("utf-8"))
    content_line_count = len(content.splitlines())

    if not dry_run:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return _result(
                report_type=normalized_report_type,
                dry_run=False,
                target_path=str(target),
                approved_output_root=safety["approved_output_root"],
                target_exists=target_exists,
                target_exists_before=target_exists,
                force=force,
                conclusion="REPORT_EXPORT_WRITE_FAILED",
                path_safety_status="PATH_OK",
                errors=[f"failed to write report: {exc}"],
                recommendation="Inspect filesystem permissions and rerun only after the target path is safe.",
                content_line_count=content_line_count,
                content_size_bytes=content_size_bytes,
            )
        return _result(
            report_type=normalized_report_type,
            dry_run=False,
            would_write=True,
            wrote_file=True,
            target_path=str(target),
            approved_output_root=safety["approved_output_root"],
            target_exists=True,
            target_exists_before=target_exists,
            would_overwrite=would_overwrite,
            overwritten=bool(target_exists and force),
            force=force,
            conclusion="REPORT_EXPORT_OK",
            path_safety_status=path_safety_status,
            recommendation="Report file written under an approved output root.",
            content_line_count=content_line_count,
            content_size_bytes=content_size_bytes,
            bytes_written=content_size_bytes,
            read_only=False,
            writes_files=True,
        )

    return _result(
        report_type=normalized_report_type,
        dry_run=True,
        target_path=str(target),
        approved_output_root=safety["approved_output_root"],
        target_exists=target_exists,
        would_overwrite=would_overwrite,
        force=force,
        conclusion="REPORT_EXPORT_DRY_RUN_OK",
        path_safety_status=path_safety_status,
        warnings=warnings,
        recommendation="Dry-run only. No report file was written.",
        content_line_count=content_line_count,
        content_size_bytes=content_size_bytes,
    )


def format_report_export_dry_run(result: ReportExportDryRunResult) -> str:
    title = "Report Export Dry Run" if result.dry_run else "Report Export"
    rows = [
        ("report_type", result.report_type),
        ("dry_run", result.dry_run),
        ("would_write", result.would_write),
        ("wrote_file", result.wrote_file),
        ("target_path", result.target_path),
        ("approved_output_root", result.approved_output_root),
        ("target_exists", result.target_exists),
        ("target_exists_before", result.target_exists_before),
        ("would_overwrite", result.would_overwrite),
        ("overwritten", result.overwritten),
        ("force", result.force),
        ("path_safety_status", result.path_safety_status),
        ("conclusion", result.conclusion),
        ("content_line_count", result.content_line_count),
        ("content_size_bytes", result.content_size_bytes),
        ("bytes_written", result.bytes_written),
        ("read_only", result.read_only),
        ("writes_files", result.writes_files),
        ("runs_ce", result.runs_ce),
    ]
    width = max(len(label) for label, _ in rows)
    lines = [title, "Field".ljust(width) + "  Value", "-".ljust(width, "-") + "  -----"]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {_display(value)}")
    if result.warnings:
        lines.extend(["", "Warnings"])
        lines.extend(f"- {warning}" for warning in result.warnings)
    if result.errors:
        lines.extend(["", "Errors"])
        lines.extend(f"- {error}" for error in result.errors)
    lines.extend(["", "Recommendation", result.recommendation])
    return "\n".join(lines)


def _target_from_args(
    *,
    report_type: str,
    output_dir: str | None,
    out: str | None,
    generated_at: datetime,
    project_root: Path,
) -> tuple[Path | None, list[str]]:
    if output_dir and out:
        return None, ["use either --output-dir or --out, not both"]
    if not output_dir and not out:
        return None, ["one of --output-dir or --out is required for report export"]
    if out:
        return _resolve_user_path(out, project_root), []
    timestamp = generated_at.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"{report_type.replace('-', '_')}_{timestamp}.md"
    return _resolve_user_path(str(Path(output_dir or "") / filename), project_root), []


def _validate_target_path(*, target: Path, project_root: Path) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    project_root_resolved = project_root.resolve()
    target_resolved = target.resolve(strict=False)
    approved_roots = [(project_root_resolved / root).resolve(strict=False) for root in APPROVED_OUTPUT_ROOTS]
    approved_root = next((root for root in approved_roots if _is_relative_to(target_resolved, root)), None)

    if ".." in target.parts:
        errors.append("path traversal is not allowed")
    if target_resolved.suffix.lower() != ".md":
        errors.append("target path must use the .md extension")
    if approved_root is None:
        errors.append("target path must be under reports/python_tooling or docs/reports/python_tooling")

    for protected in PROTECTED_PATHS:
        protected_resolved = (project_root_resolved / protected).resolve(strict=False)
        if target_resolved == protected_resolved or _is_relative_to(target_resolved, protected_resolved):
            errors.append(f"target path is protected: {protected.as_posix()}")
            break

    return {
        "approved_output_root": str(approved_root) if approved_root is not None else None,
        "warnings": warnings,
        "errors": errors,
    }


def _resolve_user_path(value: str, project_root: Path) -> Path:
    raw = Path(value)
    return raw if raw.is_absolute() else project_root / raw


def _normalize_report_type(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in REPORT_TYPES:
        expected = ", ".join(REPORT_TYPES)
        raise ValueError(f"unknown report type: {value}; expected one of {expected}")
    return normalized


def _result(
    *,
    report_type: str,
    dry_run: bool,
    conclusion: str,
    path_safety_status: str,
    recommendation: str,
    target_path: str | None = None,
    approved_output_root: str | None = None,
    target_exists: bool = False,
    target_exists_before: bool | None = None,
    would_overwrite: bool = False,
    overwritten: bool = False,
    would_write: bool = False,
    wrote_file: bool = False,
    force: bool = False,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    content_line_count: int | None = None,
    content_size_bytes: int | None = None,
    bytes_written: int | None = None,
    read_only: bool = True,
    writes_files: bool = False,
) -> ReportExportDryRunResult:
    return ReportExportDryRunResult(
        report_type=report_type,
        dry_run=dry_run,
        would_write=would_write,
        wrote_file=wrote_file,
        target_path=target_path,
        output_path=target_path,
        approved_output_root=approved_output_root,
        target_exists=target_exists,
        target_exists_before=target_exists if target_exists_before is None else target_exists_before,
        would_overwrite=would_overwrite,
        overwritten=overwritten,
        force=force,
        path_safety_status=path_safety_status,
        conclusion=conclusion,
        recommendation=recommendation,
        warnings=warnings or [],
        errors=errors or [],
        content_line_count=content_line_count,
        content_size_bytes=content_size_bytes,
        bytes_written=bytes_written,
        read_only=read_only,
        writes_files=writes_files,
    )


def _rejected_conclusion(dry_run: bool) -> str:
    return "REPORT_EXPORT_DRY_RUN_REJECTED" if dry_run else "REPORT_EXPORT_REJECTED"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _display(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
