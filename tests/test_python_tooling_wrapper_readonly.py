from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = PROJECT_ROOT / "src" / "python_tooling_wrapper.ps1"

ARTIFACT_PATHS = (
    PROJECT_ROOT / "reports" / "python_tooling" / "full_status.md",
    PROJECT_ROOT / "reports" / "python_tooling" / "manifest.jsonl",
    PROJECT_ROOT / "reports" / "python_tooling" / "bundles",
    PROJECT_ROOT / "docs" / "reports" / "python_tooling",
    PROJECT_ROOT / "log" / "case_registry.jsonl",
)


@dataclass(frozen=True)
class ArtifactState:
    exists: bool
    is_file: bool
    sha256: str | None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _artifact_snapshot() -> dict[Path, ArtifactState]:
    snapshot: dict[Path, ArtifactState] = {}
    for path in ARTIFACT_PATHS:
        exists = path.exists()
        is_file = path.is_file()
        snapshot[path] = ArtifactState(
            exists=exists,
            is_file=is_file,
            sha256=_sha256(path) if exists and is_file else None,
        )
    return snapshot


def _assert_snapshot_unchanged(before: dict[Path, ArtifactState]) -> None:
    after = _artifact_snapshot()
    assert after == before


def _powershell() -> str:
    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell is not available for wrapper boundary tests.")
    return powershell


def _run_wrapper(command: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src_path = str(PROJECT_ROOT / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing_pythonpath else f"{src_path}{os.pathsep}{existing_pythonpath}"

    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(WRAPPER),
            command,
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


@pytest.mark.parametrize(
    ("command", "expected_fragments"),
    [
        ("status", ("overall_status", "SAFE")),
        ("inventory", ("writes_files_count", "2", "runs_ce_count", "0")),
        ("report-status", ("Full Status Preview", "read_only", "true")),
        ("manifest-verify", ("Report Manifest", "read_only", "true", "writes_files", "false")),
        ("bundle-verify", ("Report Bundle", "read_only", "true", "writes_files", "false")),
    ],
)
def test_allowed_wrapper_commands_are_read_only(command: str, expected_fragments: tuple[str, ...]) -> None:
    before = _artifact_snapshot()

    result = _run_wrapper(command)
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    for fragment in expected_fragments:
        assert fragment in output
    _assert_snapshot_unchanged(before)


@pytest.mark.parametrize(
    "command",
    [
        "report-export",
        "report-export-manifest",
        "bundle-export",
        "bundle-export-dry-run",
        "safe-reset",
        "set-diagnostic",
        "prepare-current-case",
        "collect-prepare",
        "case-intake-abandon",
        "unknown-command",
    ],
)
def test_forbidden_wrapper_commands_are_rejected_without_writes(command: str) -> None:
    before = _artifact_snapshot()

    result = _run_wrapper(command)
    output = result.stdout + result.stderr
    lowered_output = output.lower()

    assert result.returncode != 0
    assert (
        "forbidden wrapper command" in lowered_output
        or "unsupported wrapper command" in lowered_output
        or "read-only python commands only" in lowered_output
    )
    _assert_snapshot_unchanged(before)


def test_wrapper_rejects_extra_arguments_without_writes() -> None:
    before = _artifact_snapshot()
    env = os.environ.copy()
    src_path = str(PROJECT_ROOT / "src")
    env["PYTHONPATH"] = src_path if "PYTHONPATH" not in env else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"

    result = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(WRAPPER),
            "status",
            "--json",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "does not accept extra arguments" in output
    _assert_snapshot_unchanged(before)
