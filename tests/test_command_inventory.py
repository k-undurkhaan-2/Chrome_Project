from __future__ import annotations

import pytest

from armedforces_tool.command_inventory import (
    COMMANDS,
    CommandInventoryError,
    list_commands,
    quickstart,
    show_command,
)


def test_inventory_contains_daily_entry_points() -> None:
    commands = {descriptor.command for descriptor in COMMANDS}

    assert "status overview" in commands
    assert "safety doctor" in commands
    assert "baseline compare" in commands


def test_inventory_commands_have_expected_safety_metadata() -> None:
    assert COMMANDS
    for descriptor in COMMANDS:
        assert descriptor.runs_ce is False
        assert descriptor.replacement_for_powershell is False
        if descriptor.command == "report export":
            assert descriptor.read_only is False
            assert descriptor.writes_files is True
            assert descriptor.risk_level == "WRITE_CAPABLE"
        else:
            assert descriptor.read_only is True
            assert descriptor.writes_files is False
            assert descriptor.risk_level == "READ_ONLY"


def test_category_filter_returns_only_baseline_commands() -> None:
    result = list_commands(category="baseline")

    assert result.records
    assert all(descriptor.category == "baseline" for descriptor in result.records)
    assert "baseline compare" in {descriptor.command for descriptor in result.records}


def test_show_status_overview_descriptor() -> None:
    descriptor = show_command("status overview")

    assert descriptor.command == "status overview"
    assert descriptor.category == "status"
    assert "Aggregate" in descriptor.purpose
    assert "python -m armedforces_tool status overview" in descriptor.examples
    assert any("Read-only" in note for note in descriptor.safety_notes)


def test_show_unknown_command_raises_clear_error() -> None:
    with pytest.raises(CommandInventoryError) as exc_info:
        show_command("not-a-command")

    assert "unknown command" in str(exc_info.value)
    assert "commands list" in str(exc_info.value)


def test_quickstart_includes_status_overview() -> None:
    result = quickstart()

    commands = [step.command for step in result.steps]
    assert "python -m armedforces_tool status overview" in commands
    assert result.read_only is True
    assert result.runs_ce is False
    assert result.writes_files is False


def test_json_shapes() -> None:
    inventory_data = list_commands().to_dict()
    descriptor_data = show_command("baseline compare").to_dict()
    quickstart_data = quickstart().to_dict()

    assert {"summary", "records"}.issubset(inventory_data)
    assert {"total_count", "read_only_count", "writes_files_count", "runs_ce_count"}.issubset(
        inventory_data["summary"]
    )
    assert {"command", "category", "safety_notes", "examples"}.issubset(descriptor_data)
    assert {"summary", "read_only", "runs_ce", "writes_files", "steps"}.issubset(quickstart_data)
