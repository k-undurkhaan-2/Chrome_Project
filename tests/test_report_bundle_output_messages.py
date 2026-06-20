from __future__ import annotations

from armedforces_tool.report_output_messages import (
    bad_path_message,
    bundle_export_complete_message,
    bundle_export_dry_run_message,
    overwrite_rejection_message,
    path_guard_rejection_message,
    report_export_complete_message,
    report_export_dry_run_message,
    report_export_manifest_complete_message,
    source_input_rejection_message,
    wrapper_unsupported_message,
    zip_unsupported_message,
)


def _assert_tokens(text: str, tokens: list[str]) -> None:
    missing = [token for token in tokens if token not in text]
    assert not missing, f"Missing token(s): {missing}\n\n{text}"


def _assert_no_unsafe_suggestions(text: str) -> None:
    lowered = text.lower()
    assert "--force" not in lowered
    assert "disable guard" not in lowered
    assert "bypass" not in lowered or "do not bypass" in lowered
    assert "zip export is available" not in lowered
    assert "python_tooling_wrapper.ps1 report export" not in lowered
    assert "python_tooling_wrapper.ps1 bundle export" not in lowered


def _assert_field_value(text: str, field: str, value: str) -> None:
    assert field in text
    assert value in text


def test_report_export_dry_run_message_tokens_and_paths() -> None:
    text = report_export_dry_run_message(
        report_path="reports/python_tooling/full_status.md",
        approved_root="reports/python_tooling",
        manifest_would_write=True,
    )

    _assert_tokens(text, ["DRY_RUN", "NO_FILES_WRITTEN", "APPROVED_ROOT", "WRAPPER_UNSUPPORTED", "CE_NOT_RUN"])
    assert "reports/python_tooling/full_status.md" in text
    assert "manifest_would_write" in text
    _assert_no_unsafe_suggestions(text)


def test_bundle_export_dry_run_message_tokens_and_paths() -> None:
    text = bundle_export_dry_run_message(
        bundle_dir="reports/python_tooling/bundles/bundle_1",
        bundle_manifest_path="reports/python_tooling/bundles/bundle_1/bundle_manifest.json",
        index_path="reports/python_tooling/bundles/bundle_1/index.md",
        approved_root="reports/python_tooling/bundles",
    )

    _assert_tokens(text, ["DRY_RUN", "NO_FILES_WRITTEN", "APPROVED_ROOT", "ZIP_UNSUPPORTED", "WRAPPER_UNSUPPORTED", "CE_NOT_RUN"])
    assert "reports/python_tooling/bundles/bundle_1" in text
    assert "bundle_manifest.json" in text
    assert "index.md" in text
    assert "directory-only" in text
    _assert_no_unsafe_suggestions(text)


def test_report_export_complete_message_tokens() -> None:
    text = report_export_complete_message(
        report_path="reports/python_tooling/full_status.md",
        approved_root="reports/python_tooling",
        next_verification_command="python -m armedforces_tool report preview --type full-status",
    )

    _assert_tokens(
        text,
        [
            "WRITE_COMPLETE",
            "APPROVED_ROOT",
            "WRAPPER_UNSUPPORTED",
            "CE_NOT_RUN",
        ],
    )
    assert "MANIFEST_NOT_WRITTEN" not in text
    assert "BUNDLE_NOT_CREATED" not in text
    assert "NO_FILES_WRITTEN" not in text
    assert "MANIFEST_RECORDED" not in text
    assert "BUNDLE_EXPORT_COMPLETE" not in text
    assert "ZIP_UNSUPPORTED" not in text
    assert "reports/python_tooling/full_status.md" in text
    assert "python -m armedforces_tool report preview --type full-status" in text
    _assert_no_unsafe_suggestions(text)


def test_report_export_manifest_complete_message_tokens() -> None:
    text = report_export_manifest_complete_message(
        report_path="reports/python_tooling/full_status.md",
        manifest_path="reports/python_tooling/manifest.jsonl",
        approved_root="reports/python_tooling",
        next_verification_command="python -m armedforces_tool report manifest verify",
    )

    _assert_tokens(
        text,
        [
            "WRITE_COMPLETE",
            "APPROVED_ROOT",
            "MANIFEST_RECORDED",
            "WRAPPER_UNSUPPORTED",
            "CE_NOT_RUN",
        ],
    )
    assert "BUNDLE_NOT_CREATED" not in text
    assert "reports/python_tooling/manifest.jsonl" in text
    assert "python -m armedforces_tool report manifest verify" in text
    _assert_no_unsafe_suggestions(text)


def test_bundle_export_complete_message_tokens() -> None:
    text = bundle_export_complete_message(
        bundle_dir="reports/python_tooling/bundles/bundle_1",
        bundle_manifest_path="reports/python_tooling/bundles/bundle_1/bundle_manifest.json",
        index_path="reports/python_tooling/bundles/bundle_1/index.md",
        approved_root="reports/python_tooling/bundles",
        copied_report_count=3,
        next_verification_command="python -m armedforces_tool report bundle verify",
    )

    _assert_tokens(
        text,
        [
            "BUNDLE_EXPORT_COMPLETE",
            "APPROVED_ROOT",
            "SOURCE_UNCHANGED",
            "WRAPPER_UNSUPPORTED",
            "CE_NOT_RUN",
        ],
    )
    _assert_field_value(text, "copied_report_count", "3")
    assert "reports/python_tooling/bundles/bundle_1" in text
    assert "bundle_manifest.json" in text
    assert "index.md" in text
    assert "python -m armedforces_tool report bundle verify" in text
    assert "ZIP_UNSUPPORTED" not in text
    _assert_no_unsafe_suggestions(text)


def test_bad_path_message_tokens_and_guidance() -> None:
    text = bad_path_message(
        rejected_path="log/full_status.md",
        reason="protected path",
        approved_root_guidance="reports/python_tooling or docs/reports/python_tooling",
    )

    _assert_tokens(text, ["BAD_PATH", "NO_FILES_WRITTEN", "APPROVED_ROOT"])
    assert "log/full_status.md" in text
    assert "protected path" in text
    assert "Do not bypass protected path checks." in text


def test_path_guard_rejection_message_tokens_and_no_success_tokens() -> None:
    text = path_guard_rejection_message(
        rejected_path="outside/full_status.md",
        reason="OUTSIDE_APPROVED_ROOT",
        output_option="--out",
        conclusion="REPORT_EXPORT_REJECTED",
        approved_root_guidance="reports/python_tooling or docs/reports/python_tooling",
        legacy_status="BAD_PATH",
        detail="target path must be under reports/python_tooling or docs/reports/python_tooling",
    )

    _assert_tokens(text, ["PATH_GUARD_REJECTED", "BAD_PATH", "OUTSIDE_APPROVED_ROOT", "NO_FILES_WRITTEN"])
    assert "--out" in text
    assert "outside/full_status.md" in text
    assert "target path must be under" in text
    for token in [
        "SOURCE_MISSING",
        "SOURCE_INVALID",
        "OVERWRITE_UNSUPPORTED",
        "ZIP_UNSUPPORTED",
        "SOURCE_UNCHANGED",
        "BUNDLE_EXPORT_OK",
        "BUNDLE_EXPORT_COMPLETE",
        "REPORT_EXPORT_OK",
        "MANIFEST_RECORDED",
        "WRITE_COMPLETE",
    ]:
        assert token not in text
    _assert_no_unsafe_suggestions(text)


def test_overwrite_rejection_message_tokens() -> None:
    text = overwrite_rejection_message(rejected_path="reports/python_tooling/existing.md")

    _assert_tokens(text, ["OVERWRITE_UNSUPPORTED", "NO_FILES_WRITTEN"])
    assert "output already exists" in text
    assert "Choose a different approved output path." in text
    _assert_no_unsafe_suggestions(text)


def test_zip_unsupported_message_tokens() -> None:
    text = zip_unsupported_message()

    _assert_tokens(text, ["ZIP_UNSUPPORTED", "NO_FILES_WRITTEN"])
    assert "directory-only" in text
    _assert_field_value(text, "zip_created", "False")
    _assert_no_unsafe_suggestions(text)


def test_wrapper_unsupported_message_tokens() -> None:
    text = wrapper_unsupported_message(command_name="report bundle export")

    _assert_tokens(text, ["WRAPPER_UNSUPPORTED", "CE_NOT_RUN"])
    _assert_field_value(text, "wrapper_status", "read-only")
    assert "report bundle export" in text
    assert "direct Python only" in text
    _assert_no_unsafe_suggestions(text)


def test_source_input_rejection_message_tokens() -> None:
    text = source_input_rejection_message(
        status="SOURCE_MISSING",
        source_kind="report",
        source_option="--source-report",
        conclusion="BUNDLE_EXPORT_REJECTED",
        detail="The --source-report path does not exist.",
    )

    _assert_tokens(text, ["SOURCE_MISSING", "NO_FILES_WRITTEN", "--source-report"])
    assert "No bundle directory" in text
    for token in [
        "BUNDLE_EXPORT_COMPLETE",
        "BUNDLE_EXPORT_OK",
        "SOURCE_UNCHANGED",
        "REPORT_EXPORT_OK",
        "WRITE_COMPLETE",
        "MANIFEST_RECORDED",
    ]:
        assert token not in text
    _assert_no_unsafe_suggestions(text)
