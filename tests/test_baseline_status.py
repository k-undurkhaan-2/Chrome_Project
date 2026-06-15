from __future__ import annotations

from pathlib import Path

from armedforces_tool import baseline_status
from armedforces_tool.baseline_status import (
    analyze_baseline_compare,
    analyze_baseline_current,
    analyze_baseline_list,
    baseline_current_parity,
    parse_baseline_markdown,
)


def _write_success_summary(root: Path, batch_id: str, known_true_addr: str) -> None:
    template = (Path(__file__).parent / "fixtures" / "sample_summary_success.txt").read_text(encoding="utf-8")
    text = template.replace("0xABC061C7D48", known_true_addr)
    (root / f"{batch_id}__summary.txt").write_text(text, encoding="utf-8")


def _write_baseline(path: Path, unique_count: int = 2) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# Baseline Batch Log Classification Report

| field | value |
|---|---|
| generated_at | 2026-06-13 01:35:19 +08:00 |
| latest N | 2 |
| validation_profile | full |
| full_success count | 2 |

## Classification Summary

| classification | count |
|---|---:|
| success | 2 |

## Coverage

- unique known_true_addr count: {unique_count}
- total batch count: 2
- clean baseline status: CLEAN

## Correctness Table

| batch_id | known_true_addr | classification |
|---|---|---|
| 20260613-000001 | 0xAAA061C7D48 | success |
| 20260613-000002 | 0xCCC061C7D48 | success |
""",
        encoding="utf-8",
    )
    return path


def test_baseline_markdown_unique_count_and_fields(tmp_path: Path) -> None:
    baseline = _write_baseline(tmp_path / "baseline_full_latest2.md")

    parsed = parse_baseline_markdown(baseline)

    assert parsed.parse_status == "OK"
    assert parsed.profile == "full"
    assert parsed.latest_n == 2
    assert parsed.unique_known_true_addr_count == 2
    assert parsed.known_true_addrs == ["0xAAA061C7D48", "0xCCC061C7D48"]


def test_baseline_missing_behavior(tmp_path: Path) -> None:
    result = analyze_baseline_current(baseline=tmp_path / "missing.md")

    assert result.baseline_exists is False
    assert result.conclusion == "BASELINE_MISSING"


def test_baseline_list_empty_dir(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baselines"
    baseline_dir.mkdir()

    result = analyze_baseline_list(
        project_root=tmp_path,
        baseline_dir=baseline_dir,
        current_baseline=baseline_dir / "baseline.md",
    )

    assert result.baseline_dir_exists is True
    assert result.baseline_count == 0
    assert result.conclusion == "NO_BASELINES_FOUND"


def test_baseline_current_parse_warning(tmp_path: Path) -> None:
    baseline = tmp_path / "partial.md"
    baseline.write_text("# Partial baseline\n\nNo known coverage fields here.\n", encoding="utf-8")

    result = analyze_baseline_current(baseline=baseline)

    assert result.baseline_exists is True
    assert result.parse_status == "WARN"
    assert result.conclusion == "BASELINE_PARSE_WARN"
    assert "unique known_true_addr count not found" in result.parse_warnings


def test_baseline_compare_pass_and_delta(tmp_path: Path) -> None:
    baseline = _write_baseline(tmp_path / "baseline_full_latest2.md")
    _write_success_summary(tmp_path, "20260614-000002", "0xAAA061C7D48")
    _write_success_summary(tmp_path, "20260614-000001", "0xBBB061C7D48")

    result = analyze_baseline_compare(baseline=baseline, latest=2, profile="full", log_root=tmp_path)

    assert result.conclusion == "BASELINE_COMPARE_PASS"
    assert result.baseline_unique_known_true_addr_count == 2
    assert result.current_eligible_batch_count == 2
    assert result.current_success_count == 2
    assert result.current_unique_known_true_addr_count == 2
    assert result.coverage_delta == 0
    assert result.missing_from_current == ["0xCCC061C7D48"]
    assert result.new_in_current == ["0xBBB061C7D48"]


def test_baseline_compare_missing_baseline(tmp_path: Path) -> None:
    result = analyze_baseline_compare(baseline=tmp_path / "missing.md", latest=2, profile="full", log_root=tmp_path)

    assert result.conclusion == "BASELINE_MISSING"
    assert result.baseline_exists is False


def test_baseline_parity_marks_unparseable_fields_warn(monkeypatch, tmp_path: Path) -> None:
    baseline = _write_baseline(tmp_path / "baseline_full_latest2.md")
    monkeypatch.setattr(
        baseline_status,
        "_run_powershell_baseline_command",
        lambda args, session_tool_path: "Current Baseline\nField  Value\n-----  -----\nbaseline exists  True\nlatest count  2\n",
    )

    result = baseline_current_parity(baseline=baseline, session_tool_path=tmp_path / "test_session_tool.ps1")

    assert result.parity_status == "WARN"
    assert "unique_known_true_addr_count" in result.unparseable_fields
    assert "profile" in result.unparseable_fields


def test_baseline_json_shape(tmp_path: Path) -> None:
    baseline = _write_baseline(tmp_path / "baseline_full_latest2.md")
    data = analyze_baseline_current(baseline=baseline).to_dict()

    assert {"baseline_path", "baseline_exists", "unique_known_true_addr_count", "known_true_addrs", "conclusion"}.issubset(data)
