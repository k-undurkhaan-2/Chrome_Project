from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from armedforces_tool.command_inventory import list_commands


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"


def _run_help(tmp_path: Path, *args: str) -> str:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_ROOT) if not existing else f"{SRC_ROOT}{os.pathsep}{existing}"
    result = subprocess.run(
        [sys.executable, "-m", "armedforces_tool", *args, "--help"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert not (tmp_path / "reports").exists()
    assert not (tmp_path / "docs" / "reports").exists()
    return result.stdout


def _assert_contains_all(text: str, phrases: list[str]) -> None:
    lowered = text.lower()
    missing = [phrase for phrase in phrases if phrase.lower() not in lowered]
    assert not missing, f"Missing help phrase(s): {missing}\n\n{text}"


def test_report_export_help_explains_write_boundary(tmp_path: Path) -> None:
    help_text = _run_help(tmp_path, "report", "export")

    _assert_contains_all(
        help_text,
        [
            "write-capable",
            "writes a .md report",
            "dry-run",
            "no-write",
            "record-manifest",
            "manifest.jsonl",
            "approved output roots",
            "protected or unapproved paths",
            "bad_path",
            "default overwrite is rejected",
            "--force must be explicit",
            "powershell wrapper does not support report export",
            "direct python only",
            "ce is not run",
            "does not create bundles",
        ],
    )


def test_report_bundle_export_help_explains_write_boundary(tmp_path: Path) -> None:
    help_text = _run_help(tmp_path, "report", "bundle", "export")

    _assert_contains_all(
        help_text,
        [
            "write-capable",
            "directory-only",
            "dry-run",
            "no-write",
            "approved output root",
            "protected or unapproved paths",
            "bad_path",
            "zip export is unsupported",
            "bundle_manifest.json",
            "index.md",
            "source reports",
            "manifest.jsonl are read, not mutated",
            "overwrite and --force are unsupported",
            "powershell wrapper does not support report bundle export",
            "direct python only",
            "ce is not run",
        ],
    )


def test_report_help_polish_does_not_change_inventory_invariants() -> None:
    result = list_commands(category="report")
    records = {record.command: record for record in result.records}
    summary = result.to_dict()["summary"]

    assert summary["writes_files_count"] == 2
    assert summary["runs_ce_count"] == 0
    assert records["report export"].writes_files is True
    assert records["report bundle export"].writes_files is True
    assert records["report export"].runs_ce is False
    assert records["report bundle export"].runs_ce is False
    assert records["report export --dry-run"].writes_files is False
    assert records["report bundle export --dry-run"].writes_files is False
