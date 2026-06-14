from pathlib import Path

import pytest

from armedforces_tool.logs import LogParseError
from armedforces_tool.stable_cases import analyze_stable_cases, filter_stable_case_result, validate_known_true_addr


def _write_summary(root: Path, batch_id: str, fixture_name: str, replacements: dict[str, str]) -> None:
    text = (Path(__file__).parent / "fixtures" / fixture_name).read_text(encoding="utf-8")
    for old, new in replacements.items():
        text = text.replace(old, new)
    (root / f"{batch_id}__summary.txt").write_text(text, encoding="utf-8")


def test_stable_candidate_detection_and_readiness(tmp_path: Path) -> None:
    _write_summary(tmp_path, "20260614-000001", "sample_summary_success.txt", {"0xABC061C7D48": "0xAAA061C7D48"})
    _write_summary(tmp_path, "20260614-000002", "sample_summary_success.txt", {"0xABC061C7D48": "0xAAA061C7D48"})

    result = analyze_stable_cases(log_root=tmp_path, latest=10, profile="full", min_full_success=2, target_unique=1)

    assert result.stable_candidate_count == 1
    assert result.coverage_readiness == "READY_FOR_BASELINE"
    assert result.addresses[0].known_true_addr == "0xAAA061C7D48"
    assert result.addresses[0].stable_candidate is True
    assert result.addresses[0].rejection_reasons == []


def test_rejection_reasons_for_clean_count_and_quality_issues(tmp_path: Path) -> None:
    _write_summary(tmp_path, "20260614-000001", "sample_summary_success.txt", {"0xABC061C7D48": "0xAAA061C7D48"})
    _write_summary(tmp_path, "20260614-000002", "sample_summary_stale_known_true.txt", {})
    _write_summary(tmp_path, "20260614-000003", "sample_summary_write_success.txt", {"0x333061C7D48": "0xBBB061C7D48"})

    result = analyze_stable_cases(log_root=tmp_path, latest=10, profile="full", min_full_success=2, target_unique=3)
    rows = {row.known_true_addr: row for row in result.addresses}

    assert rows["0xAAA061C7D48"].rejection_reasons == ["full_success_lt_min", "baseline_eligible_lt_min"]
    assert "latest_full_not_success" in rows["0x111061C7D48"].rejection_reasons
    assert "latest_final_hit_false" in rows["0x111061C7D48"].rejection_reasons
    assert "has_execution_batch" in rows["0xBBB061C7D48"].rejection_reasons
    assert result.addresses_blocked_by_quality_issues == 1
    assert result.coverage_readiness == "NEED_MORE_STABLE_CASES"


def test_known_true_addr_validation() -> None:
    assert validate_known_true_addr("0xABC123") == "0xABC123"
    with pytest.raises(LogParseError, match="placeholder"):
        validate_known_true_addr("0x...")
    with pytest.raises(LogParseError, match="add the 0x prefix"):
        validate_known_true_addr("ABC123")
    with pytest.raises(LogParseError, match="expected"):
        validate_known_true_addr("0xZZZ")


def test_filter_known_true_addr(tmp_path: Path) -> None:
    _write_summary(tmp_path, "20260614-000001", "sample_summary_success.txt", {"0xABC061C7D48": "0xAAA061C7D48"})
    result = analyze_stable_cases(log_root=tmp_path, latest=10, profile="full", min_full_success=2, target_unique=1)

    filtered = filter_stable_case_result(result, "0xAAA061C7D48")

    assert len(filtered.addresses) == 1
    assert filtered.addresses[0].known_true_addr == "0xAAA061C7D48"
    with pytest.raises(LogParseError, match="not found"):
        filter_stable_case_result(result, "0xBBB061C7D48")
