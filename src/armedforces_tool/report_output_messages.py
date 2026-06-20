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
    next_verification_command: str | None = None,
) -> str:
    notes = [
        "The read-only PowerShell wrapper does not support report export.",
    ]
    if next_verification_command:
        notes.append(f"Next safe read-only check: {next_verification_command}")
    return _format_message(
        "Report Export Complete",
        [
            ("status", "WRITE_COMPLETE"),
            ("report_path", report_path),
            ("approved_root", f"APPROVED_ROOT {approved_root}"),
            ("ce_status", "CE_NOT_RUN"),
            ("wrapper_status", "WRAPPER_UNSUPPORTED"),
        ],
        notes,
    )


def report_export_manifest_complete_message(
    *,
    report_path: str,
    manifest_path: str,
    approved_root: str,
    next_verification_command: str | None = None,
) -> str:
    notes = [
        "Manifest record was appended by the explicitly requested record-manifest behavior.",
        "No bundle was created by report export.",
        "The read-only PowerShell wrapper does not support report export.",
    ]
    if next_verification_command:
        notes.append(f"Next safe read-only check: {next_verification_command}")
    return _format_message(
        "Report Export Manifest Complete",
        [
            ("status", "WRITE_COMPLETE"),
            ("report_path", report_path),
            ("manifest_path", manifest_path),
            ("manifest_record", "MANIFEST_RECORDED"),
            ("approved_root", f"APPROVED_ROOT {approved_root}"),
            ("ce_status", "CE_NOT_RUN"),
            ("wrapper_status", "WRAPPER_UNSUPPORTED"),
        ],
        notes,
    )


def bundle_export_complete_message(
    *,
    bundle_dir: str,
    bundle_manifest_path: str,
    index_path: str,
    approved_root: str,
    copied_report_count: int | None = None,
    next_verification_command: str | None = None,
) -> str:
    notes = [
        "Bundle export remains directory-only.",
        "Source reports and manifest are unchanged by bundle export.",
        "The read-only PowerShell wrapper does not support report bundle export.",
    ]
    if next_verification_command:
        notes.append(f"Next safe read-only check: {next_verification_command}")
    return _format_message(
        "Report Bundle Export Complete",
        [
            ("status", "BUNDLE_EXPORT_COMPLETE"),
            ("bundle_dir", bundle_dir),
            ("bundle_manifest", bundle_manifest_path),
            ("index_path", index_path),
            ("copied_report_count", "not_available" if copied_report_count is None else copied_report_count),
            ("source_status", "SOURCE_UNCHANGED"),
            ("approved_root", f"APPROVED_ROOT {approved_root}"),
            ("ce_status", "CE_NOT_RUN"),
            ("wrapper_status", "WRAPPER_UNSUPPORTED"),
        ],
        notes,
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


def path_guard_rejection_message(
    *,
    rejected_path: str,
    reason: str,
    output_option: str,
    conclusion: str,
    approved_root_guidance: str,
    legacy_status: str | None = None,
    detail: str | None = None,
) -> str:
    fields: list[tuple[str, object]] = [
        ("status", "PATH_GUARD_REJECTED"),
        ("reason", reason),
        ("write_status", "NO_FILES_WRITTEN"),
        ("output_option", output_option),
        ("rejected_path", rejected_path),
        ("approved_root", f"APPROVED_ROOT {approved_root_guidance}"),
        ("conclusion", conclusion),
    ]
    if legacy_status:
        fields.insert(1, ("legacy_status", legacy_status))
    notes = ["No report, manifest, bundle directory, bundle_manifest.json, index.md, or copied report was written."]
    if detail:
        notes.insert(0, detail)
    notes.append("Use an approved output root; protected paths and traversal remain blocked.")
    return _format_message("Path Guard Rejected", fields, notes)


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


def invalid_option_combination_message(
    *,
    invalid_option: str,
    requires: str,
    conclusion: str,
) -> str:
    return _format_message(
        "Invalid Option Combination",
        [
            ("status", "INVALID_OPTION_COMBINATION"),
            ("invalid_option", invalid_option),
            ("requires", requires),
            ("write_status", "NO_FILES_WRITTEN"),
            ("conclusion", conclusion),
        ],
        [
            f"{invalid_option} requires {requires}.",
            "No report file, custom manifest, or default manifest was written.",
        ],
    )


def source_input_rejection_message(
    *,
    status: str,
    conclusion: str,
    source_kind: str | None = None,
    source_option: str | None = None,
    invalid_option: str | None = None,
    requires: str | None = None,
    detail: str,
) -> str:
    fields: list[tuple[str, object]] = [("status", status)]
    if source_kind:
        fields.append(("source_kind", source_kind))
    if source_option:
        fields.append(("source_option", source_option))
    if invalid_option:
        fields.append(("invalid_option", invalid_option))
    if requires:
        fields.append(("requires", requires))
    fields.extend(
        [
            ("write_status", "NO_FILES_WRITTEN"),
            ("conclusion", conclusion),
        ]
    )
    return _format_message(
        "Bundle Export Rejected",
        fields,
        [
            detail,
            "No bundle directory, bundle_manifest.json, index.md, or copied report was written.",
        ],
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
    "invalid_option_combination_message",
    "overwrite_rejection_message",
    "path_guard_rejection_message",
    "report_export_complete_message",
    "report_export_dry_run_message",
    "report_export_manifest_complete_message",
    "source_input_rejection_message",
    "wrapper_unsupported_message",
    "zip_unsupported_message",
]
