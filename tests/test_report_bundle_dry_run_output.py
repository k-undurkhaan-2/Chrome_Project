from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from armedforces_tool.command_inventory import list_commands


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"


def _run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_ROOT) if not existing else f"{SRC_ROOT}{os.pathsep}{existing}"
    return subprocess.run(
        [sys.executable, "-m", "armedforces_tool", *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _assert_tokens(text: str, tokens: list[str]) -> None:
    missing = [token for token in tokens if token not in text]
    assert not missing, f"Missing token(s): {missing}\n\n{text}"


def _hash_if_exists(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_report_export_dry_run_output_uses_stable_tokens_and_writes_nothing() -> None:
    target = PROJECT_ROOT / "reports" / "python_tooling" / f"phase5_10_report_{uuid4().hex}.md"
    manifest = PROJECT_ROOT / "reports" / "python_tooling" / "manifest.jsonl"
    manifest_hash_before = _hash_if_exists(manifest)
    assert not target.exists()

    result = _run_tool(
        "report",
        "export",
        "--dry-run",
        "--type",
        "full-status",
        "--out",
        target.relative_to(PROJECT_ROOT).as_posix(),
    )

    assert result.returncode == 0, result.stderr
    _assert_tokens(result.stdout, ["DRY_RUN", "NO_FILES_WRITTEN", "APPROVED_ROOT", "WRAPPER_UNSUPPORTED", "CE_NOT_RUN"])
    assert target.relative_to(PROJECT_ROOT).as_posix() in result.stdout or str(target) in result.stdout
    assert "Dry-Run Details" in result.stdout
    assert "REPORT_EXPORT_DRY_RUN_OK" in result.stdout
    assert not target.exists()
    assert _hash_if_exists(manifest) == manifest_hash_before


def test_report_bundle_export_dry_run_output_uses_stable_tokens_and_writes_nothing() -> None:
    target = PROJECT_ROOT / "reports" / "python_tooling" / "bundles" / f"phase5_10_bundle_{uuid4().hex}"
    manifest = PROJECT_ROOT / "reports" / "python_tooling" / "manifest.jsonl"
    manifest_hash_before = _hash_if_exists(manifest)
    assert not target.exists()

    result = _run_tool(
        "report",
        "bundle",
        "export",
        "--dry-run",
        "--out",
        target.relative_to(PROJECT_ROOT).as_posix(),
    )

    assert result.returncode == 0, result.stderr
    _assert_tokens(
        result.stdout,
        ["DRY_RUN", "NO_FILES_WRITTEN", "APPROVED_ROOT", "ZIP_UNSUPPORTED", "WRAPPER_UNSUPPORTED", "CE_NOT_RUN"],
    )
    assert target.relative_to(PROJECT_ROOT).as_posix() in result.stdout or str(target) in result.stdout
    assert "bundle_manifest.json" in result.stdout
    assert "index.md" in result.stdout
    assert "Dry-Run Details" in result.stdout
    assert not target.exists()
    assert not (target / "bundle_manifest.json").exists()
    assert not (target / "index.md").exists()
    assert not target.with_suffix(".zip").exists()
    assert _hash_if_exists(manifest) == manifest_hash_before


def test_dry_run_output_integration_keeps_inventory_invariants() -> None:
    result = list_commands(category="report")
    records = {record.command: record for record in result.records}
    summary = result.to_dict()["summary"]

    assert summary["writes_files_count"] == 2
    assert summary["runs_ce_count"] == 0
    assert records["report export --dry-run"].writes_files is False
    assert records["report bundle export --dry-run"].writes_files is False
    assert records["report export"].writes_files is True
    assert records["report bundle export"].writes_files is True
