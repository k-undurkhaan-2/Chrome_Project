from __future__ import annotations

import json
from pathlib import Path

import pytest

from armedforces_tool.command_inventory import list_commands
from armedforces_tool.transaction_history import (
    TransactionHistoryError,
    analyze_transaction_list,
    analyze_transaction_show,
    analyze_transaction_summary,
)


def _write_summary(
    log_root: Path,
    batch_id: str,
    addr: str,
    *,
    profile: str = "full",
    mode: str = "disabled",
    preconditions_ok: str = "false",
    write_attempted: str = "false",
    write_ok: str = "false",
    readback_ok: str = "false",
    restore_source_batch_id: str = "nil",
    execution_write_request_id: str = "nil",
) -> Path:
    log_root.mkdir(parents=True, exist_ok=True)
    text = f"""
--- no_probe_A ---
validation_profile = {profile}
known_true_addr = {addr}
known_true_rank_position = 1
baseline_eligible = true

--- with_probe ---
known_true_rank_position = 1

--- no_probe_B ---
known_true_rank_position = 1

--- stable_no_probe_intersection ---
validation_profile = {profile}
known_true_addr = {addr}
stable_intersection_best_candidate = {addr}
stable_intersection_known_true_rank_position = 1
best_candidate = {addr}
target_value_pattern = 0x42C80000
target_value_float = 100.0
run_valid = true
collector_empty = false
baseline_eligible = true
execution_enabled = {"true" if mode != "disabled" else "false"}
execution_mode = {mode}
write_enabled = {"true" if mode == "write" else "false"}
execution_confirm = nil
execution_write_request_id = {execution_write_request_id}
execution_armed_at_utc = nil
execution_arm_expires_at_utc = nil
execution_preconditions_ok = {preconditions_ok}
write_attempted = {write_attempted}
write_ok = {write_ok}
readback_ok = {readback_ok}
restore_source_batch_id = {restore_source_batch_id}
restore_source_batch_execution_addr = nil
"""
    path = log_root / f"{batch_id}__summary.txt"
    path.write_text(text.strip(), encoding="utf-8")
    return path


def _write_registry(path: Path, rows: list[dict[str, object] | str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) if isinstance(row, dict) else row for row in rows),
        encoding="utf-8",
    )
    return path


def test_transaction_summary_counts_all_statuses(tmp_path: Path) -> None:
    log_root = tmp_path / "logs"
    registry = tmp_path / "case_registry.jsonl"
    _write_summary(log_root, "20260615-000001", "0xAAA")
    _write_summary(log_root, "20260615-000002", "0xBBB", mode="dry_run", preconditions_ok="true")
    _write_summary(log_root, "20260615-000003", "0xCCC", mode="write", write_attempted="false")
    _write_summary(log_root, "20260615-000004", "0xDDD", mode="write", write_attempted="true", write_ok="true", readback_ok="true")
    _write_summary(log_root, "20260615-000005", "0xEEE", mode="write", write_attempted="false", restore_source_batch_id="20260615-000004")
    _write_summary(
        log_root,
        "20260615-000006",
        "0xFFF",
        mode="write",
        write_attempted="true",
        write_ok="true",
        readback_ok="true",
        restore_source_batch_id="20260615-000004",
    )
    _write_registry(registry, [])

    result = analyze_transaction_summary(project_root=tmp_path, log_root=log_root, registry=registry, latest=10)

    assert result.conclusion == "TRANSACTION_HISTORY_OK"
    assert result.detect_only_count == 1
    assert result.dry_run_count == 1
    assert result.write_blocked_count == 1
    assert result.write_success_count == 1
    assert result.restore_blocked_count == 1
    assert result.restore_success_count == 1
    assert result.transaction_type_counts["detect_only"] == 1


def test_transaction_list_limit_and_profile_filter(tmp_path: Path) -> None:
    log_root = tmp_path / "logs"
    registry = _write_registry(tmp_path / "case_registry.jsonl", [])
    _write_summary(log_root, "20260615-000001", "0xAAA", profile="quick")
    _write_summary(log_root, "20260615-000002", "0xBBB", profile="full")
    _write_summary(log_root, "20260615-000003", "0xCCC", profile="full")

    result = analyze_transaction_list(project_root=tmp_path, log_root=log_root, registry=registry, latest=10, profile="full", limit=1)

    assert result.transaction_record_count == 2
    assert len(result.records) == 1
    assert result.records[0].batch_id == "20260615-000003"


def test_transaction_type_filter(tmp_path: Path) -> None:
    log_root = tmp_path / "logs"
    registry = _write_registry(tmp_path / "case_registry.jsonl", [])
    _write_summary(log_root, "20260615-000001", "0xAAA", mode="write", write_attempted="false")
    _write_summary(log_root, "20260615-000002", "0xBBB")

    result = analyze_transaction_list(
        project_root=tmp_path,
        log_root=log_root,
        registry=registry,
        transaction_type="write_blocked",
    )

    assert result.transaction_record_count == 1
    assert result.records[0].transaction_status == "write_blocked"


def test_transaction_show_by_batch_id(tmp_path: Path) -> None:
    log_root = tmp_path / "logs"
    registry = _write_registry(tmp_path / "case_registry.jsonl", [])
    _write_summary(log_root, "20260615-000001", "0xAAA")

    result = analyze_transaction_show(project_root=tmp_path, log_root=log_root, registry=registry, batch_id="20260615-000001")

    assert result.conclusion == "TRANSACTION_MATCH_FOUND"
    assert result.matched_count == 1
    assert result.latest_matching_record is not None
    assert result.latest_matching_record["batch_id"] == "20260615-000001"


def test_transaction_show_by_known_true_addr(tmp_path: Path) -> None:
    log_root = tmp_path / "logs"
    registry = _write_registry(tmp_path / "case_registry.jsonl", [])
    _write_summary(log_root, "20260615-000001", "0xAAA")
    _write_summary(log_root, "20260615-000002", "0xAAA")

    result = analyze_transaction_show(project_root=tmp_path, log_root=log_root, registry=registry, known_true_addr="0xaaa")

    assert result.conclusion == "TRANSACTION_MATCH_FOUND"
    assert result.matched_count == 2


def test_invalid_known_true_addr_validation(tmp_path: Path) -> None:
    with pytest.raises(TransactionHistoryError, match="try 0xCE061C7D48"):
        analyze_transaction_show(project_root=tmp_path, log_root=tmp_path / "logs", registry=tmp_path / "r.jsonl", known_true_addr="CE061C7D48")
    with pytest.raises(TransactionHistoryError, match="0x prefix"):
        analyze_transaction_show(project_root=tmp_path, log_root=tmp_path / "logs", registry=tmp_path / "r.jsonl", known_true_addr="0x...")


def test_missing_and_empty_source_behavior(tmp_path: Path) -> None:
    missing = analyze_transaction_summary(project_root=tmp_path, log_root=tmp_path / "missing", registry=tmp_path / "missing.jsonl")
    assert missing.conclusion == "TRANSACTION_HISTORY_MISSING"

    log_root = tmp_path / "logs"
    log_root.mkdir()
    empty = analyze_transaction_summary(project_root=tmp_path, log_root=log_root, registry=tmp_path / "missing.jsonl")
    assert empty.conclusion == "TRANSACTION_HISTORY_EMPTY"


def test_registry_only_unknown_transaction_is_tolerated(tmp_path: Path) -> None:
    registry = _write_registry(
        tmp_path / "case_registry.jsonl",
        [
            {
                "recorded_at": "2026-06-15T00:00:00Z",
                "batch_id": "20260615-000001",
                "known_true_addr": "0xAAA",
                "validation_profile": "full",
                "classification": "success",
                "transaction_type": "something_new",
            }
        ],
    )

    result = analyze_transaction_summary(project_root=tmp_path, log_root=tmp_path / "missing", registry=registry)

    assert result.conclusion == "TRANSACTION_HISTORY_WARN"
    assert result.unknown_transaction_count == 1


def test_transaction_json_shape(tmp_path: Path) -> None:
    log_root = tmp_path / "logs"
    registry = _write_registry(tmp_path / "case_registry.jsonl", [])
    _write_summary(log_root, "20260615-000001", "0xAAA")

    data = analyze_transaction_summary(project_root=tmp_path, log_root=log_root, registry=registry).to_dict()

    assert {"project_root", "transaction_type_counts", "conclusion", "recommendation"}.issubset(data)


def test_command_inventory_includes_transaction_commands() -> None:
    result = list_commands(category="transaction")

    assert result.total_count == 3
    assert {record.command for record in result.records} == {
        "transaction summary",
        "transaction list",
        "transaction show",
    }
    assert all(record.read_only and not record.writes_files and not record.runs_ce for record in result.records)
