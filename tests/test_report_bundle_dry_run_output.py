from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from armedforces_tool.command_inventory import list_commands
from armedforces_tool.safety import DEFAULT_PROJECT_ROOT


# cwd selects the test checkout; the report CLI still uses DEFAULT_PROJECT_ROOT.
CHECKOUT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = CHECKOUT_ROOT / "src"


def _run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_ROOT) if not existing else f"{SRC_ROOT}{os.pathsep}{existing}"
    return subprocess.run(
        [sys.executable, "-m", "armedforces_tool", *args],
        cwd=CHECKOUT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _assert_tokens(text: str, tokens: list[str]) -> None:
    missing = [token for token in tokens if token not in text]
    assert not missing, f"Missing token(s): {missing}\n\n{text}"


def _hash_if_exists(path: Path) -> str | None:
    import hashlib

    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def _manifest_snapshot() -> dict[Path, str | None]:
    manifests = {
        root / "reports" / "python_tooling" / "manifest.jsonl"
        for root in (CHECKOUT_ROOT, DEFAULT_PROJECT_ROOT)
    }
    return {path: _hash_if_exists(path) for path in manifests}


def _assert_absent(path: Path) -> None:
    # Permission errors must fail inspection; even dangling links count as existing.
    try:
        path.lstat()
    except FileNotFoundError:
        return
    raise AssertionError(f"Unexpected existing dry-run target: {path}")


def test_report_export_dry_run_output_uses_stable_tokens_and_writes_nothing() -> None:
    relative_target = Path("reports/python_tooling") / f"phase5_10_report_{uuid4().hex}.md"
    effective_target = DEFAULT_PROJECT_ROOT / relative_target
    targets = {CHECKOUT_ROOT / relative_target, effective_target}
    manifests_before = _manifest_snapshot()
    for target in targets:
        _assert_absent(target)

    result = _run_tool(
        "report",
        "export",
        "--dry-run",
        "--type",
        "full-status",
        "--out",
        relative_target.as_posix(),
    )

    for target in targets:
        _assert_absent(target)
    assert _manifest_snapshot() == manifests_before
    assert result.returncode == 0, result.stderr
    _assert_tokens(result.stdout, ["DRY_RUN", "NO_FILES_WRITTEN", "APPROVED_ROOT", "WRAPPER_UNSUPPORTED", "CE_NOT_RUN"])
    assert str(effective_target) in result.stdout
    assert "Dry-Run Details" in result.stdout
    assert "REPORT_EXPORT_DRY_RUN_OK" in result.stdout


def test_report_bundle_export_dry_run_output_uses_stable_tokens_and_writes_nothing() -> None:
    relative_target = Path("reports/python_tooling/bundles") / f"phase5_10_bundle_{uuid4().hex}"
    effective_target = DEFAULT_PROJECT_ROOT / relative_target
    targets = {CHECKOUT_ROOT / relative_target, effective_target}
    artifacts = {
        artifact
        for target in targets
        for artifact in (target, target / "bundle_manifest.json", target / "index.md", target.with_suffix(".zip"))
    }
    manifests_before = _manifest_snapshot()
    for artifact in artifacts:
        _assert_absent(artifact)

    result = _run_tool(
        "report",
        "bundle",
        "export",
        "--dry-run",
        "--out",
        relative_target.as_posix(),
    )

    for artifact in artifacts:
        _assert_absent(artifact)
    assert _manifest_snapshot() == manifests_before
    assert result.returncode == 0, result.stderr
    _assert_tokens(
        result.stdout,
        ["DRY_RUN", "NO_FILES_WRITTEN", "APPROVED_ROOT", "ZIP_UNSUPPORTED", "WRAPPER_UNSUPPORTED", "CE_NOT_RUN"],
    )
    assert str(effective_target) in result.stdout
    assert "bundle_manifest.json" in result.stdout
    assert "index.md" in result.stdout
    assert "Dry-Run Details" in result.stdout


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
