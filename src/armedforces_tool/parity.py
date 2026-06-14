from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .logs import BatchSummaryRecord, LogParseError, parse_latest_summaries

DEFAULT_CLASSIFIER_PATH = Path(r"D:\armedforces.io-v2\src\batch_log_classifier.ps1")

PARITY_FIELDS = [
    "batch_id",
    "classification",
    "validation_profile",
    "known_true_addr",
    "final_hit",
    "rank_AWB",
    "stable_rank",
    "best_candidate",
    "baseline_eligible",
    "execution_outcome",
    "transaction_type",
]


@dataclass(frozen=True)
class ParityMismatch:
    batch_id: str
    field: str
    python_value: object | None
    powershell_value: object | None

    def to_dict(self) -> dict[str, object | None]:
        return {
            "batch_id": self.batch_id,
            "field": self.field,
            "python_value": self.python_value,
            "powershell_value": self.powershell_value,
        }


@dataclass(frozen=True)
class ParityResult:
    parity_status: str
    compared_batch_count: int
    mismatch_count: int
    mismatches: list[ParityMismatch]

    def to_dict(self) -> dict[str, object]:
        return {
            "parity_status": self.parity_status,
            "compared_batch_count": self.compared_batch_count,
            "mismatch_count": self.mismatch_count,
            "mismatches": [mismatch.to_dict() for mismatch in self.mismatches],
        }


def parity_latest(
    *,
    log_root: Path,
    latest: int,
    profile: str,
    classifier_path: Path = DEFAULT_CLASSIFIER_PATH,
) -> ParityResult:
    python_records = parse_latest_summaries(log_root=log_root, latest=latest, profile=profile)
    powershell_records = _run_classifier_console_summary(
        latest=latest,
        profile=profile,
        classifier_path=classifier_path,
    )

    mismatches: list[ParityMismatch] = []
    compared = min(len(python_records), len(powershell_records))
    if len(python_records) != len(powershell_records):
        mismatches.append(
            ParityMismatch(
                batch_id="-",
                field="record_count",
                python_value=len(python_records),
                powershell_value=len(powershell_records),
            )
        )

    for index in range(compared):
        python_data = python_records[index].to_dict()
        powershell_data = powershell_records[index]
        batch_id = str(python_data.get("batch_id") or powershell_data.get("batch_id") or "-")
        for field in PARITY_FIELDS:
            left = _normalize_compare_value(field, python_data.get(field))
            right = _normalize_compare_value(field, powershell_data.get(field))
            if left != right:
                mismatches.append(
                    ParityMismatch(
                        batch_id=batch_id,
                        field=field,
                        python_value=left,
                        powershell_value=right,
                    )
                )

    status = "PASS" if not mismatches else "FAIL"
    return ParityResult(
        parity_status=status,
        compared_batch_count=compared,
        mismatch_count=len(mismatches),
        mismatches=mismatches,
    )


def _run_classifier_console_summary(*, latest: int, profile: str, classifier_path: Path) -> list[dict[str, object | None]]:
    if not classifier_path.exists():
        raise LogParseError(f"PowerShell classifier not found: {classifier_path}")

    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(classifier_path),
        "-Latest",
        str(latest),
        "-Profile",
        profile,
        "-ConsoleSummary",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise LogParseError("PowerShell executable was not found for parity check") from exc
    except subprocess.TimeoutExpired as exc:
        raise LogParseError("PowerShell classifier parity check timed out") from exc

    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        detail = f": {message}" if message else ""
        raise LogParseError(f"PowerShell classifier failed with exit code {completed.returncode}{detail}")

    return _parse_console_summary(completed.stdout)


def _parse_console_summary(text: str) -> list[dict[str, object | None]]:
    records: list[dict[str, object | None]] = []
    current: dict[str, object | None] | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.strip() == "Batch Summary":
            if current:
                _finalize_powershell_record(current)
                records.append(current)
            current = {}
            continue
        if current is None:
            continue
        match = re.match(r"^([A-Za-z0-9_/\-]+)\s{2,}(.*)$", line)
        if not match:
            continue
        key = match.group(1).strip()
        value = match.group(2).strip()
        current[_map_console_key(key)] = _normalize_console_value(value)

    if current:
        _finalize_powershell_record(current)
        records.append(current)
    return records


def _finalize_powershell_record(record: dict[str, object | None]) -> None:
    transaction_type = record.get("transaction_type")
    if record.get("execution_outcome") is None:
        if transaction_type == "detect_only":
            record["execution_outcome"] = "execution_disabled"
        elif transaction_type == "dry_run":
            record["execution_outcome"] = "execution_dry_run_ready"
        elif transaction_type in {"write_success", "restore_success"}:
            record["execution_outcome"] = "execution_write_ok"
        elif transaction_type in {"write_blocked", "restore_blocked"}:
            record["execution_outcome"] = "execution_write_blocked"
        else:
            record["execution_outcome"] = None


def _map_console_key(key: str) -> str:
    if key == "rank_A/W/B":
        return "rank_AWB"
    return key


def _normalize_console_value(value: str) -> object | None:
    if value in {"", "-", "nil"}:
        return None
    if value == "True":
        return True
    if value == "False":
        return False
    if value in {"true", "false"}:
        return value
    return value


def _normalize_compare_value(field: str, value: object | None) -> object | None:
    if value in {"", "-", "nil", "None"}:
        return None
    if field == "baseline_eligible" and isinstance(value, str):
        return value.lower()
    if field == "stable_rank" and value is None:
        return None
    return value
