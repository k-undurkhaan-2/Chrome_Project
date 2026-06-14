from pathlib import Path

from armedforces_tool.case_summary import analyze_case_summary, parse_baseline_unique_count


def _write_success_summary(root: Path, batch_id: str, known_true_addr: str) -> None:
    template = (Path(__file__).parent / "fixtures" / "sample_summary_success.txt").read_text(encoding="utf-8")
    text = template.replace("0xABC061C7D48", known_true_addr)
    (root / f"{batch_id}__summary.txt").write_text(text, encoding="utf-8")


def test_parse_baseline_unique_count() -> None:
    baseline = Path(__file__).parent / "fixtures" / "baseline_case_summary.md"

    assert parse_baseline_unique_count(baseline) == 3


def test_case_summary_repeated_delta_and_rolling_estimate(tmp_path: Path) -> None:
    baseline = Path(__file__).parent / "fixtures" / "baseline_case_summary.md"
    _write_success_summary(tmp_path, "20260614-000004", "0xAAA061C7D48")
    _write_success_summary(tmp_path, "20260614-000003", "0xAAA061C7D48")
    _write_success_summary(tmp_path, "20260614-000002", "0xAAA061C7D48")
    _write_success_summary(tmp_path, "20260614-000001", "0xBBB061C7D48")

    result = analyze_case_summary(
        log_root=tmp_path,
        latest=4,
        profile="full",
        baseline=baseline,
    )

    assert result.current_eligible_batch_count == 4
    assert result.current_success_count == 4
    assert result.current_unique_known_true_addr_count == 2
    assert result.coverage_delta == -1
    assert result.repeated_known_true_addr[0].known_true_addr == "0xAAA061C7D48"
    assert result.repeated_known_true_addr[0].count == 3
    assert result.estimated_new_distinct_addr_needed == 2
    assert result.conclusion == "COVERAGE_WARN"
