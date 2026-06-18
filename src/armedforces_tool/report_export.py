from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .report_output_messages import report_export_dry_run_message
from .report_preview import REPORT_TYPES, preview_report
from .safety import DEFAULT_PROJECT_ROOT

APPROVED_OUTPUT_ROOTS = (
    Path("reports/python_tooling"),
    Path("docs/reports/python_tooling"),
)
REPORT_MANIFEST_PATH = Path("reports/python_tooling/manifest.jsonl")
REPORT_MANIFEST_SCHEMA_VERSION = "1"

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
    record_manifest: bool = False
    would_write_report: bool | None = None
    would_write_manifest: bool | None = None
    planned_report_path: str | None = None
    planned_manifest_path: str | None = None
    planned_manifest_entry: dict[str, object | None] | None = None
    manifest_written: bool = False
    manifest_path: str | None = None
    manifest_entry: dict[str, object | None] | None = None
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
            "record_manifest": self.record_manifest,
            "would_write_report": self.would_write_report,
            "would_write_manifest": self.would_write_manifest,
            "planned_report_path": self.planned_report_path,
            "planned_manifest_path": self.planned_manifest_path,
            "planned_manifest_entry": self.planned_manifest_entry,
            "manifest_written": self.manifest_written,
            "manifest_path": self.manifest_path,
            "manifest_entry": self.manifest_entry,
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
    record_manifest: bool = False,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    generated_at: datetime | None = None,
) -> ReportExportDryRunResult:
    normalized_report_type = _normalize_report_type(report_type)
    planned_at = generated_at or datetime.now(timezone.utc)
    target, target_errors = _target_from_args(
        report_type=normalized_report_type,
        output_dir=output_dir,
        out=out,
        generated_at=planned_at,
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
            record_manifest=record_manifest,
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
            record_manifest=record_manifest,
        )

    warnings = list(safety["warnings"])
    target_exists = target.exists()
    would_overwrite = bool(target_exists and force)
    path_safety_status = "PATH_OK"
    if record_manifest and safety["approved_output_root_relative"] != "reports/python_tooling":
        return _result(
            report_type=normalized_report_type,
            dry_run=dry_run,
            target_path=str(target),
            approved_output_root=safety["approved_output_root"],
            target_exists=target_exists,
            target_exists_before=target_exists,
            would_overwrite=would_overwrite,
            force=force,
            conclusion="MANIFEST_OUTPUT_ROOT_UNSUPPORTED",
            path_safety_status="PATH_REJECTED",
            errors=["--record-manifest only supports report outputs under reports/python_tooling in this version"],
            recommendation="Use reports/python_tooling for manifest-recorded exports, or omit --record-manifest.",
            record_manifest=True,
            would_write_report=False,
            would_write_manifest=False,
            planned_report_path=str(target),
            planned_manifest_path=REPORT_MANIFEST_PATH.as_posix(),
        )

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
                record_manifest=record_manifest,
            )

    preview = preview_report(report_type=normalized_report_type, latest=latest, profile=profile)
    content = preview.markdown
    content_size_bytes = len(content.encode("utf-8"))
    content_line_count = len(content.splitlines())

    if not dry_run:
        manifest_path = (project_root.resolve() / REPORT_MANIFEST_PATH).resolve(strict=False)
        manifest_entry: dict[str, object | None] | None = None
        if record_manifest:
            planned_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
            manifest_entry = _real_manifest_entry(
                report_type=normalized_report_type,
                target=target,
                project_root=project_root,
                output_root=str(safety["approved_output_root_relative"] or ""),
                created_at=planned_at,
                file_size=content_size_bytes,
                sha256=planned_sha256,
                output_dir=output_dir,
                out=out,
                force=force,
            )
            preflight_errors = _preflight_manifest_for_append(
                manifest_path=manifest_path,
                report_id=str(manifest_entry["report_id"]),
            )
            if preflight_errors:
                return _result(
                    report_type=normalized_report_type,
                    dry_run=False,
                    target_path=str(target),
                    approved_output_root=safety["approved_output_root"],
                    target_exists=target_exists,
                    target_exists_before=target_exists,
                    force=force,
                    conclusion="MANIFEST_PREFLIGHT_REJECTED",
                    path_safety_status="PATH_OK",
                    errors=preflight_errors,
                    recommendation="Fix or verify the existing manifest before retrying manifest recording.",
                    content_line_count=content_line_count,
                    content_size_bytes=content_size_bytes,
                    record_manifest=True,
                    would_write_report=False,
                    would_write_manifest=False,
                    planned_report_path=str(target),
                    planned_manifest_path=REPORT_MANIFEST_PATH.as_posix(),
                    planned_manifest_entry=manifest_entry,
                )
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
                record_manifest=record_manifest,
            )
        bytes_written = target.stat().st_size
        sha256 = _sha256_file(target)
        if record_manifest and manifest_entry is not None:
            manifest_entry = dict(manifest_entry)
            manifest_entry["file_size"] = bytes_written
            manifest_entry["sha256"] = sha256
            try:
                with manifest_path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(json.dumps(manifest_entry, sort_keys=True, separators=(",", ":")))
                    handle.write("\n")
            except OSError as exc:
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
                    conclusion="REPORT_EXPORT_MANIFEST_APPEND_FAILED",
                    path_safety_status=path_safety_status,
                    errors=[f"report was written but manifest append failed: {exc}"],
                    recommendation="Report exists but manifest is incomplete. Inspect the report and manifest before retrying.",
                    content_line_count=content_line_count,
                    content_size_bytes=content_size_bytes,
                    bytes_written=bytes_written,
                    record_manifest=True,
                    manifest_written=False,
                    manifest_path=REPORT_MANIFEST_PATH.as_posix(),
                    manifest_entry=manifest_entry,
                    read_only=False,
                    writes_files=True,
                )
            verify_errors = _preflight_manifest_for_append(manifest_path=manifest_path, report_id="__no_duplicate_check_after_append__")
            if verify_errors:
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
                    conclusion="REPORT_EXPORT_MANIFEST_VERIFY_FAILED",
                    path_safety_status=path_safety_status,
                    errors=verify_errors,
                    recommendation="Report and manifest were written, but manifest verification failed. Inspect before retrying.",
                    content_line_count=content_line_count,
                    content_size_bytes=content_size_bytes,
                    bytes_written=bytes_written,
                    record_manifest=True,
                    manifest_written=True,
                    manifest_path=REPORT_MANIFEST_PATH.as_posix(),
                    manifest_entry=manifest_entry,
                    read_only=False,
                    writes_files=True,
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
            bytes_written=bytes_written if record_manifest else content_size_bytes,
            read_only=False,
            writes_files=True,
            record_manifest=record_manifest,
            manifest_written=bool(record_manifest),
            manifest_path=REPORT_MANIFEST_PATH.as_posix() if record_manifest else None,
            manifest_entry=manifest_entry,
        )

    planned_manifest_entry = None
    if record_manifest:
        planned_manifest_entry = _planned_manifest_entry(
            report_type=normalized_report_type,
            target=target,
            project_root=project_root,
            output_root=str(safety["approved_output_root_relative"] or ""),
            planned_at=planned_at,
            content_size_bytes=content_size_bytes,
            output_dir=output_dir,
            out=out,
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
        recommendation=(
            "Dry-run only. No report or manifest file was written."
            if record_manifest
            else "Dry-run only. No report file was written."
        ),
        content_line_count=content_line_count,
        content_size_bytes=content_size_bytes,
        record_manifest=record_manifest,
        would_write_report=True if record_manifest else None,
        would_write_manifest=True if record_manifest else None,
        planned_report_path=str(target) if record_manifest else None,
        planned_manifest_path=REPORT_MANIFEST_PATH.as_posix() if record_manifest else None,
        planned_manifest_entry=planned_manifest_entry,
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
    if result.record_manifest:
        rows.extend(
            [
                ("record_manifest", result.record_manifest),
                ("would_write_report", result.would_write_report),
                ("would_write_manifest", result.would_write_manifest),
                ("planned_report_path", result.planned_report_path),
                ("planned_manifest_path", result.planned_manifest_path),
                ("manifest_written", result.manifest_written),
                ("manifest_path", result.manifest_path),
            ]
        )
    width = max(len(label) for label, _ in rows)
    if result.dry_run:
        lines = [
            report_export_dry_run_message(
                report_path=_display(result.target_path),
                approved_root=_display(result.approved_output_root),
                manifest_would_write=bool(result.would_write_manifest),
            ),
            "",
            "Dry-Run Details",
            "Field".ljust(width) + "  Value",
            "-".ljust(width, "-") + "  -----",
        ]
    else:
        lines = [title, "Field".ljust(width) + "  Value", "-".ljust(width, "-") + "  -----"]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {_display(value)}")
    if result.warnings:
        lines.extend(["", "Warnings"])
        lines.extend(f"- {warning}" for warning in result.warnings)
    if result.errors:
        lines.extend(["", "Errors"])
        lines.extend(f"- {error}" for error in result.errors)
    if result.planned_manifest_entry:
        lines.extend(["", "Planned Manifest Entry"])
        entry_rows = [(key, _display(value)) for key, value in result.planned_manifest_entry.items()]
        entry_width = max(len(label) for label, _ in entry_rows)
        lines.append("Field".ljust(entry_width) + "  Value")
        lines.append("-".ljust(entry_width, "-") + "  -----")
        for label, value in entry_rows:
            lines.append(f"{label.ljust(entry_width)}  {value}")
    if result.manifest_entry:
        lines.extend(["", "Manifest Entry"])
        entry_rows = [(key, _display(value)) for key, value in result.manifest_entry.items()]
        entry_width = max(len(label) for label, _ in entry_rows)
        lines.append("Field".ljust(entry_width) + "  Value")
        lines.append("-".ljust(entry_width, "-") + "  -----")
        for label, value in entry_rows:
            lines.append(f"{label.ljust(entry_width)}  {value}")
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
    approved_root = None
    approved_root_relative = None
    for root_index, root in enumerate(approved_roots):
        if _is_relative_to(target_resolved, root):
            approved_root = root
            approved_root_relative = APPROVED_OUTPUT_ROOTS[root_index]
            break

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
        "approved_output_root_relative": approved_root_relative.as_posix() if approved_root_relative is not None else None,
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
    record_manifest: bool = False,
    would_write_report: bool | None = None,
    would_write_manifest: bool | None = None,
    planned_report_path: str | None = None,
    planned_manifest_path: str | None = None,
    planned_manifest_entry: dict[str, object | None] | None = None,
    manifest_written: bool = False,
    manifest_path: str | None = None,
    manifest_entry: dict[str, object | None] | None = None,
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
        record_manifest=record_manifest,
        would_write_report=would_write_report,
        would_write_manifest=would_write_manifest,
        planned_report_path=planned_report_path,
        planned_manifest_path=planned_manifest_path,
        planned_manifest_entry=planned_manifest_entry,
        manifest_written=manifest_written,
        manifest_path=manifest_path,
        manifest_entry=manifest_entry,
        read_only=read_only,
        writes_files=writes_files,
    )


def _planned_manifest_entry(
    *,
    report_type: str,
    target: Path,
    project_root: Path,
    output_root: str,
    planned_at: datetime,
    content_size_bytes: int,
    output_dir: str | None,
    out: str | None,
) -> dict[str, object | None]:
    relative_output = _relative_display_path(target, project_root)
    created_at = planned_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    command = _planned_manifest_command(
        report_type=report_type,
        output_dir=output_dir,
        out=out,
    )
    report_id_source = f"{relative_output}|{report_type}|{command}"
    report_id = f"planned-{hashlib.sha256(report_id_source.encode('utf-8')).hexdigest()[:16]}"
    return {
        "schema_version": REPORT_MANIFEST_SCHEMA_VERSION,
        "report_id": report_id,
        "report_type": report_type,
        "planned_created_at": created_at,
        "created_at": None,
        "output_path": relative_output,
        "output_root": output_root,
        "file_size": None,
        "planned_file_size": content_size_bytes,
        "sha256": None,
        "planned_sha256": "would_compute_after_write",
        "command": command,
        "dry_run": False,
        "status": "planned_success",
    }


def _real_manifest_entry(
    *,
    report_type: str,
    target: Path,
    project_root: Path,
    output_root: str,
    created_at: datetime,
    file_size: int,
    sha256: str,
    output_dir: str | None,
    out: str | None,
    force: bool,
) -> dict[str, object | None]:
    relative_output = _relative_display_path(target, project_root)
    created_at_text = created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    command = _planned_manifest_command(
        report_type=report_type,
        output_dir=output_dir,
        out=out,
        force=force,
    )
    report_id_source = f"{relative_output}|{created_at_text}|{sha256}"
    report_id = hashlib.sha256(report_id_source.encode("utf-8")).hexdigest()
    return {
        "schema_version": REPORT_MANIFEST_SCHEMA_VERSION,
        "report_id": report_id,
        "report_type": report_type,
        "created_at": created_at_text,
        "output_path": relative_output,
        "output_root": output_root,
        "file_size": file_size,
        "sha256": sha256,
        "command": command,
        "dry_run": False,
        "status": "success",
    }


def _planned_manifest_command(*, report_type: str, output_dir: str | None, out: str | None, force: bool = False) -> str:
    parts = ["python -m armedforces_tool report export", f"--type {report_type}"]
    if out:
        parts.append(f"--out {out}")
    if output_dir:
        parts.append(f"--output-dir {output_dir}")
    if force:
        parts.append("--force")
    parts.append("--record-manifest")
    return " ".join(parts)


def _relative_display_path(path: Path, project_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _preflight_manifest_for_append(*, manifest_path: Path, report_id: str) -> list[str]:
    if not manifest_path.exists():
        return []
    errors: list[str] = []
    seen_report_ids: set[str] = set()
    try:
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [f"failed to read existing manifest: {exc}"]

    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(record, dict):
            errors.append(f"line {line_number}: entry is not a JSON object")
            continue
        schema_version = record.get("schema_version")
        existing_report_id = record.get("report_id")
        if schema_version != REPORT_MANIFEST_SCHEMA_VERSION:
            errors.append(f"line {line_number}: unsupported schema_version: {schema_version}")
        if not isinstance(existing_report_id, str) or not existing_report_id:
            errors.append(f"line {line_number}: missing report_id")
            continue
        if existing_report_id in seen_report_ids:
            errors.append(f"line {line_number}: duplicate existing report_id: {existing_report_id}")
        seen_report_ids.add(existing_report_id)
        if existing_report_id == report_id:
            errors.append(f"duplicate report_id: {report_id}")
    return errors


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
