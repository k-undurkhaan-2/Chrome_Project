from pathlib import Path

from armedforces_tool.case_library import analyze_case_library


def _write_summary(root: Path, batch_id: str, fixture_name: str, replacements: dict[str, str]) -> None:
    text = (Path(__file__).parent / "fixtures" / fixture_name).read_text(encoding="utf-8")
    for old, new in replacements.items():
        text = text.replace(old, new)
    (root / f"{batch_id}__summary.txt").write_text(text, encoding="utf-8")


def test_case_library_aggregates_per_address_and_stable_candidate(tmp_path: Path) -> None:
    _write_summary(tmp_path, "20260614-000001", "sample_summary_success.txt", {"0xABC061C7D48": "0xAAA061C7D48"})
    _write_summary(tmp_path, "20260614-000002", "sample_summary_success.txt", {"0xABC061C7D48": "0xAAA061C7D48"})
    _write_summary(
        tmp_path,
        "20260614-000003",
        "sample_summary_success.txt",
        {"0xABC061C7D48": "0xAAA061C7D48", "validation_profile = full": "validation_profile = quick"},
    )
    _write_summary(tmp_path, "20260614-000004", "sample_summary_write_success.txt", {"0x333061C7D48": "0xBBB061C7D48"})

    result = analyze_case_library(log_root=tmp_path, latest=10, profile="all")
    rows = {row.known_true_addr: row for row in result.addresses}

    assert result.total_cases == 4
    assert result.unique_known_true_addr_count == 2
    assert result.execution_batches_count == 1
    assert rows["0xAAA061C7D48"].cases == 3
    assert rows["0xAAA061C7D48"].success == 3
    assert rows["0xAAA061C7D48"].full_succ == 2
    assert rows["0xAAA061C7D48"].quick_succ == 1
    assert rows["0xAAA061C7D48"].first_seen == "20260614-000001"
    assert rows["0xAAA061C7D48"].last_seen == "20260614-000003"
    assert rows["0xAAA061C7D48"].profiles == "full/quick"
    assert rows["0xAAA061C7D48"].stable_candidate is True
    assert rows["0xBBB061C7D48"].stable_candidate is False


def test_case_library_duplicate_heavy_conclusion(tmp_path: Path) -> None:
    for index in range(5):
        _write_summary(
            tmp_path,
            f"20260614-00000{index}",
            "sample_summary_success.txt",
            {"0xABC061C7D48": "0xAAA061C7D48"},
        )

    result = analyze_case_library(log_root=tmp_path, latest=10, profile="full")

    assert result.conclusion == "DUPLICATE_HEAVY"
    assert result.addresses[0].cases == 5
    assert result.addresses[0].stable_candidate is True
