from __future__ import annotations


def _format_message(title: str, fields: list[tuple[str, object]], notes: list[str] | None = None) -> str:
    lines = [title, "=" * len(title)]
    for key, value in fields:
        lines.append(f"{key:<24} {value}")
    if notes:
        lines.append("")
        lines.append("Notes")
        lines.append("-----")
        lines.extend(f"- {note}" for note in notes)
    return "\n".join(lines)


def report_export_dry_run_message(
    *,
    report_path: str,
    approved_root: str,
    manifest_would_write: bool,
) -> str:
    return _format_message(
        "Report Export Dry Run",
        [
            ("status", "DRY_RUN"),
            ("write_status", "NO_FILES_WRITTEN"),
            ("report_path", report_path),
            ("approved_root", f"APPROVED_ROOT {approved_root}"),
            ("manifest_would_write", manifest_would_write),
            ("wrapper_status", "WRAPPER_UNSUPPORTED"),
            ("ce_status", "CE_NOT_RUN"),
        ],
        [
            "Run the non-dry-run command only under an explicitly scoped write task.",
            "The read-only PowerShell wrapper does not support report export.",
        ],
    )


def bundle_export_dry_run_message(
    *,
    bundle_dir: str,
    bundle_manifest_path: str,
    index_path: str,
    approved_root: str,
) -> str:
    return _format_message(
        "Report Bundle Export Dry Run",
        [
            ("status", "DRY_RUN"),
            ("write_status", "NO_FILES_WRITTEN"),
            ("bundle_dir", bundle_dir),
            ("bundle_manifest", bundle_manifest_path),
            ("index_path", index_path),
            ("approved_root", f"APPROVED_ROOT {approved_root}"),
            ("bundle_mode", "directory-only"),
            ("zip_status", "ZIP_UNSUPPORTED"),
            ("wrapper_status", "WRAPPER_UNSUPPORTED"),
            ("ce_status", "CE_NOT_RUN"),
        ],
        [
            "The read-only PowerShell wrapper does not support report bundle export.",
            "Real zip bundle export is unsupported and fail-closed.",
        ],
    )


def report_export_complete_message(
    *,
    report_path: str,
    approved_root: str,
    manifest_written: bool = False,
) -> str:
    return _format_message(
        "Report Export Complete",
        [
            ("status", "WRITE_COMPLETE"),
            ("report_path", report_path),
            ("approved_root", f"APPROVED_ROOT {approved_root}"),
            ("manifest_written", manifest_written),
            ("bundle_created", False),
            ("ce_status", "CE_NOT_RUN"),
        ],
        [
            "Manifest is not written unless record-manifest behavior is explicitly enabled.",
            "No bundle was created by report export.",
        ],
    )


def report_export_manifest_complete_message(
    *,
    report_path: str,
    manifest_path: str,
    approved_root: str,
) -> str:
    return _format_message(
        "Report Export Manifest Complete",
        [
            ("status", "WRITE_COMPLETE"),
            ("report_path", report_path),
            ("manifest_path", manifest_path),
            ("manifest_record", "appended"),
            ("approved_root", f"APPROVED_ROOT {approved_root}"),
            ("bundle_created", False),
            ("ce_status", "CE_NOT_RUN"),
        ],
        ["No bundle was created by report export."],
    )


def bundle_export_complete_message(
    *,
    bundle_dir: str,
    bundle_manifest_path: str,
    index_path: str,
    approved_root: str,
    copied_report_count: int | None = None,
) -> str:
    return _format_message(
        "Report Bundle Export Complete",
        [
            ("status", "BUNDLE_EXPORT_COMPLETE"),
            ("bundle_dir", bundle_dir),
            ("bundle_manifest", bundle_manifest_path),
            ("index_path", index_path),
            ("copied_report_count", "not_available" if copied_report_count is None else copied_report_count),
            ("source_mutation", "source reports and manifest unchanged"),
            ("zip_status", "ZIP_UNSUPPORTED"),
            ("approved_root", f"APPROVED_ROOT {approved_root}"),
            ("ce_status", "CE_NOT_RUN"),
        ],
        ["Bundle export remains directory-only."],
    )


def bad_path_message(
    *,
    rejected_path: str,
    reason: str,
    approved_root_guidance: str,
) -> str:
    return _format_message(
        "Report Output Path Rejected",
        [
            ("status", "BAD_PATH"),
            ("write_status", "NO_FILES_WRITTEN"),
            ("rejected_path", rejected_path),
            ("reason", reason),
            ("approved_root", f"APPROVED_ROOT {approved_root_guidance}"),
        ],
        ["Use an approved output root. Do not bypass protected path checks."],
    )


def overwrite_rejection_message(*, rejected_path: str) -> str:
    return _format_message(
        "Report Output Overwrite Rejected",
        [
            ("status", "OVERWRITE_UNSUPPORTED"),
            ("write_status", "NO_FILES_WRITTEN"),
            ("rejected_path", rejected_path),
            ("reason", "output already exists"),
        ],
        ["Choose a different approved output path."],
    )


def zip_unsupported_message() -> str:
    return _format_message(
        "Report Bundle Zip Unsupported",
        [
            ("status", "ZIP_UNSUPPORTED"),
            ("write_status", "NO_FILES_WRITTEN"),
            ("bundle_mode", "directory-only"),
            ("zip_created", False),
        ],
        ["Directory bundle export is the only supported real bundle mode."],
    )


def wrapper_unsupported_message(*, command_name: str) -> str:
    return _format_message(
        "Wrapper Command Unsupported",
        [
            ("status", "WRAPPER_UNSUPPORTED"),
            ("wrapper_status", "read-only"),
            ("command", command_name),
            ("ce_status", "CE_NOT_RUN"),
        ],
        ["Use direct Python only under an explicitly scoped task for write-capable export."],
    )


__all__ = [
    "bad_path_message",
    "bundle_export_complete_message",
    "bundle_export_dry_run_message",
    "overwrite_rejection_message",
    "report_export_complete_message",
    "report_export_dry_run_message",
    "report_export_manifest_complete_message",
    "wrapper_unsupported_message",
    "zip_unsupported_message",
]
