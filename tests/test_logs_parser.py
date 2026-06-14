from pathlib import Path

from armedforces_tool.logs import parse_batch_summary, parse_summary_file


def _copy_fixture(tmp_path: Path, fixture_name: str, batch_id: str) -> Path:
    fixture = Path(__file__).parent / "fixtures" / fixture_name
    summary = tmp_path / f"{batch_id}__summary.txt"
    summary.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    return summary


def test_parse_summary_success_fixture(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "sample_summary_success.txt"
    summary = tmp_path / "20260614-010101__summary.txt"
    summary.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    record = parse_summary_file(summary)

    assert record.batch_id == "20260614-010101"
    assert record.classification == "success"
    assert record.validation_profile == "full"
    assert record.known_true_addr == "0xABC061C7D48"
    assert record.target_value_float == "100.0"
    assert record.target_value_pattern == "0x42C80000"
    assert record.final_hit is True
    assert record.rank_AWB == "1/1/1"
    assert record.stable_rank == "1"
    assert record.best_candidate == "0xABC061C7D48"
    assert record.baseline_eligible == "true"
    assert record.execution_outcome == "execution_disabled"
    assert record.transaction_type == "detect_only"
    assert record.recommendation is None
    assert record.source_log.endswith("20260614-010101__summary.txt")


def test_parse_batch_summary_finds_batch(tmp_path: Path) -> None:
    _copy_fixture(tmp_path, "sample_summary_success.txt", "20260614-010101")

    record = parse_batch_summary(tmp_path, "20260614-010101")

    assert record.batch_id == "20260614-010101"
    assert record.classification == "success"


def test_parse_summary_stale_known_true_fixture(tmp_path: Path) -> None:
    summary = _copy_fixture(tmp_path, "sample_summary_stale_known_true.txt", "20260614-020202")

    record = parse_summary_file(summary)

    assert record.classification == "stale_known_true_addr"
    assert record.known_true_addr == "0x111061C7D48"
    assert record.best_candidate == "0x222061C7D48"
    assert record.final_hit is False
    assert record.baseline_eligible == "false"
    assert record.recommendation == "verify current-session known_true_addr and rerun"


def test_parse_summary_write_success_fixture(tmp_path: Path) -> None:
    summary = _copy_fixture(tmp_path, "sample_summary_write_success.txt", "20260614-030303")

    record = parse_summary_file(summary)

    assert record.classification == "success"
    assert record.execution_outcome == "execution_write_ok"
    assert record.transaction_type == "write_success"
    assert record.baseline_eligible == "false"
