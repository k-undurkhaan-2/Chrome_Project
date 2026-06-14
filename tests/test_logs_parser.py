from pathlib import Path

from armedforces_tool.logs import parse_summary_file


def test_parse_summary_success_fixture(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "sample_summary_success.txt"
    summary = tmp_path / "20260614-010101__summary.txt"
    summary.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    record = parse_summary_file(summary)

    assert record.batch_id == "20260614-010101"
    assert record.classification == "success"
    assert record.validation_profile == "full"
    assert record.known_true_addr == "0xABC061C7D48"
    assert record.final_hit is True
    assert record.rank_AWB == "1/1/1"
    assert record.stable_rank == "1"
    assert record.best_candidate == "0xABC061C7D48"
    assert record.baseline_eligible == "true"
    assert record.execution_outcome == "execution_disabled"
    assert record.transaction_type == "detect_only"
