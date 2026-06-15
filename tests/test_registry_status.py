from __future__ import annotations

import json
from pathlib import Path

import pytest

from armedforces_tool.command_inventory import list_commands
from armedforces_tool.registry_status import (
    RegistryStatusError,
    analyze_registry_list,
    analyze_registry_show,
    analyze_registry_summary,
    validate_known_true_addr,
)


def _write_jsonl(path: Path, rows: list[dict[str, object] | str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row) if isinstance(row, dict) else row for row in rows]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _record(
    batch_id: str,
    addr: str,
    *,
    profile: str = "full",
    classification: str = "success",
    baseline_eligible: object = "true",
    transaction_type: str = "detect_only",
) -> dict[str, object]:
    return {
        "recorded_at": f"2026-06-15T00:00:{batch_id[-2:]}Z",
        "batch_id": batch_id,
        "known_true_addr": addr,
        "validation_profile": profile,
        "classification": classification,
        "baseline_eligible": baseline_eligible,
        "execution_outcome": "execution_disabled",
        "transaction_type": transaction_type,
    }


def test_missing_registry_behavior(tmp_path: Path) -> None:
    result = analyze_registry_summary(project_root=tmp_path, registry=tmp_path / "missing.jsonl")

    assert result.registry_exists is False
    assert result.conclusion == "REGISTRY_MISSING"
    assert result.record_count == 0


def test_empty_registry_behavior(tmp_path: Path) -> None:
    registry = _write_jsonl(tmp_path / "case_registry.jsonl", [])

    result = analyze_registry_summary(project_root=tmp_path, registry=registry)

    assert result.registry_exists is True
    assert result.total_lines == 0
    assert result.conclusion == "REGISTRY_EMPTY"


def test_valid_jsonl_summary_counts(tmp_path: Path) -> None:
    registry = _write_jsonl(
        tmp_path / "case_registry.jsonl",
        [
            _record("20260615-000001", "0xAAA"),
            _record("20260615-000002", "0xBBB", profile="quick", classification="quick_success", baseline_eligible="false"),
            _record("20260615-000003", "0xAAA", transaction_type="write_success"),
        ],
    )

    result = analyze_registry_summary(project_root=tmp_path, registry=registry)

    assert result.conclusion == "REGISTRY_OK"
    assert result.record_count == 3
    assert result.classification_counts == {"quick_success": 1, "success": 2}
    assert result.profile_counts == {"full": 2, "quick": 1}
    assert result.unique_known_true_addr_count == 2
    assert result.baseline_eligible_count == 2
    assert result.execution_batch_count == 1
    assert result.latest_batch_id == "20260615-000003"


def test_malformed_line_warning(tmp_path: Path) -> None:
    registry = _write_jsonl(
        tmp_path / "case_registry.jsonl",
        [
            _record("20260615-000001", "0xAAA"),
            "{not json",
        ],
    )

    result = analyze_registry_summary(project_root=tmp_path, registry=registry)

    assert result.conclusion == "REGISTRY_PARSE_WARN"
    assert result.parsed_records == 1
    assert result.malformed_lines == 1
    assert result.warnings[0]["line_number"] == 2


def test_utf8_bom_line_is_parsed(tmp_path: Path) -> None:
    registry = tmp_path / "case_registry.jsonl"
    registry.write_text(json.dumps(_record("20260615-000001", "0xAAA")), encoding="utf-8-sig")

    result = analyze_registry_summary(project_root=tmp_path, registry=registry)

    assert result.conclusion == "REGISTRY_OK"
    assert result.record_count == 1
    assert result.malformed_lines == 0


def test_profile_filtering(tmp_path: Path) -> None:
    registry = _write_jsonl(
        tmp_path / "case_registry.jsonl",
        [
            _record("20260615-000001", "0xAAA", profile="full"),
            _record("20260615-000002", "0xBBB", profile="quick"),
            _record("20260615-000003", "0xCCC", profile="full"),
        ],
    )

    result = analyze_registry_summary(project_root=tmp_path, registry=registry, profile="full")

    assert result.profile_filter == "full"
    assert result.record_count == 2
    assert result.profile_counts == {"full": 2}


def test_recent_list_limit_preserves_recent_order(tmp_path: Path) -> None:
    registry = _write_jsonl(
        tmp_path / "case_registry.jsonl",
        [
            _record("20260615-000001", "0xAAA"),
            _record("20260615-000002", "0xBBB"),
            _record("20260615-000003", "0xCCC"),
        ],
    )

    result = analyze_registry_list(project_root=tmp_path, registry=registry, limit=2)

    assert [record.batch_id for record in result.records] == ["20260615-000002", "20260615-000003"]
    assert [record.index for record in result.records] == [1, 2]


def test_show_by_known_true_addr(tmp_path: Path) -> None:
    registry = _write_jsonl(
        tmp_path / "case_registry.jsonl",
        [
            _record("20260615-000001", "0xAAA"),
            _record("20260615-000002", "0xBBB"),
            _record("20260615-000003", "0xAAA"),
        ],
    )

    result = analyze_registry_show(project_root=tmp_path, registry=registry, known_true_addr="0xaaa")

    assert result.conclusion == "REGISTRY_MATCH_FOUND"
    assert result.matched_count == 2
    assert result.latest_matching_record is not None
    assert result.latest_matching_record["batch_id"] == "20260615-000003"


def test_show_by_batch_id(tmp_path: Path) -> None:
    registry = _write_jsonl(
        tmp_path / "case_registry.jsonl",
        [
            _record("20260615-000001", "0xAAA"),
            _record("20260615-000002", "0xBBB"),
        ],
    )

    result = analyze_registry_show(project_root=tmp_path, registry=registry, batch_id="20260615-000002")

    assert result.conclusion == "REGISTRY_MATCH_FOUND"
    assert result.matched_count == 1
    assert result.records[0]["known_true_addr"] == "0xBBB"


def test_show_no_match_is_clear_warn_result(tmp_path: Path) -> None:
    registry = _write_jsonl(tmp_path / "case_registry.jsonl", [_record("20260615-000001", "0xAAA")])

    result = analyze_registry_show(project_root=tmp_path, registry=registry, batch_id="20260615-999999")

    assert result.conclusion == "REGISTRY_NO_MATCH"
    assert result.matched_count == 0


def test_invalid_known_true_addr_validation() -> None:
    with pytest.raises(RegistryStatusError, match="try 0xCE061C7D48"):
        validate_known_true_addr("CE061C7D48")
    with pytest.raises(RegistryStatusError, match="0x prefix"):
        validate_known_true_addr("0x...")


def test_registry_json_shape(tmp_path: Path) -> None:
    registry = _write_jsonl(tmp_path / "case_registry.jsonl", [_record("20260615-000001", "0xAAA")])

    data = analyze_registry_summary(project_root=tmp_path, registry=registry).to_dict()

    assert {"project_root", "registry_path", "classification_counts", "conclusion", "warnings"}.issubset(data)


def test_command_inventory_includes_registry_commands() -> None:
    result = list_commands(category="registry")

    assert result.total_count == 3
    assert {record.command for record in result.records} == {
        "registry summary",
        "registry list",
        "registry show",
    }
    assert all(record.read_only and not record.writes_files and not record.runs_ce for record in result.records)
