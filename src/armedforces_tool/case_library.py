from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .logs import (
    BatchSummaryRecord,
    LogParseError,
    _address_equal,
    _normalize_value,
    parse_summary_file,
)

DEFAULT_SESSION_TOOL_PATH = Path(r"D:\armedforces.io-v2\src\test_session_tool.ps1")
BATCH_ARTIFACT_RE = re.compile(r"^(?P<batch_id>\d{8}-\d{6})__")


@dataclass(frozen=True)
class CaseLibraryAddressRecord:
    known_true_addr: str
    cases: int
    success: int
    full_succ: int
    quick_succ: int
    first_seen: str
    last_seen: str
    profiles: str
    baseline_eligible_count: int
    execution_batches_count: int
    invalid_config_count: int
    stable_candidate: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "known_true_addr": self.known_true_addr,
            "cases": self.cases,
            "success": self.success,
            "full_succ": self.full_succ,
            "quick_succ": self.quick_succ,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "profiles": self.profiles,
            "baseline_eligible_count": self.baseline_eligible_count,
            "execution_batches_count": self.execution_batches_count,
            "invalid_config_count": self.invalid_config_count,
            "stable_candidate": self.stable_candidate,
        }


@dataclass(frozen=True)
class CaseLibraryResult:
    latest_n: int
    profile: str
    total_cases: int
    unique_known_true_addr_count: int
    baseline_eligible_count: int
    execution_batches_count: int
    invalid_config_count: int
    stable_case_candidate_count: int
    current_recommended_baseline_candidates: list[str]
    conclusion: str
    recommendation: str
    addresses: list[CaseLibraryAddressRecord]

    def to_dict(self) -> dict[str, object]:
        return {
            "latest_n": self.latest_n,
            "profile": self.profile,
            "total_cases": self.total_cases,
            "unique_known_true_addr_count": self.unique_known_true_addr_count,
            "baseline_eligible_count": self.baseline_eligible_count,
            "execution_batches_count": self.execution_batches_count,
            "invalid_config_count": self.invalid_config_count,
            "stable_case_candidate_count": self.stable_case_candidate_count,
            "current_recommended_baseline_candidates": self.current_recommended_baseline_candidates,
            "conclusion": self.conclusion,
            "recommendation": self.recommendation,
            "addresses": [record.to_dict() for record in self.addresses],
        }


@dataclass(frozen=True)
class CaseLibraryMismatch:
    field: str
    python_value: object | None
    powershell_value: object | None

    def to_dict(self) -> dict[str, object | None]:
        return {
            "field": self.field,
            "python_value": self.python_value,
            "powershell_value": self.powershell_value,
        }


@dataclass(frozen=True)
class CaseLibraryParityResult:
    parity_status: str
    mismatch_count: int
    mismatches: list[CaseLibraryMismatch]

    def to_dict(self) -> dict[str, object]:
        return {
            "parity_status": self.parity_status,
            "mismatch_count": self.mismatch_count,
            "mismatches": [mismatch.to_dict() for mismatch in self.mismatches],
        }


def analyze_case_library(*, log_root: Path, latest: int, profile: str = "all") -> CaseLibraryResult:
    if latest < 1:
        raise LogParseError("--latest must be greater than 0")

    records = [
        record
        for record in _latest_batch_records(log_root=log_root, latest=latest)
        if (profile == "all" or record.validation_profile == profile) and record.known_true_addr
    ]
    address_rows = _address_rows(records)
    stable_rows = [row for row in address_rows if row.stable_candidate]
    recommended = [
        row.known_true_addr
        for row in sorted(
            stable_rows,
            key=lambda row: (-row.baseline_eligible_count, -row.full_succ, row.known_true_addr),
        )
    ]
    conclusion = _case_library_conclusion(records, address_rows)
    return CaseLibraryResult(
        latest_n=latest,
        profile=profile,
        total_cases=len(records),
        unique_known_true_addr_count=len(address_rows),
        baseline_eligible_count=sum(1 for record in records if _baseline_eligible_true(record)),
        execution_batches_count=sum(1 for record in records if _is_execution_batch(record)),
        invalid_config_count=sum(1 for record in records if record.classification == "invalid_config_mismatch"),
        stable_case_candidate_count=len(stable_rows),
        current_recommended_baseline_candidates=recommended,
        conclusion=conclusion,
        recommendation=_case_library_recommendation(conclusion),
        addresses=address_rows,
    )


def case_library_parity(
    *,
    log_root: Path,
    latest: int,
    profile: str = "all",
    session_tool_path: Path = DEFAULT_SESSION_TOOL_PATH,
) -> CaseLibraryParityResult:
    python_result = analyze_case_library(log_root=log_root, latest=latest, profile=profile)
    powershell_result = _run_powershell_case_library(
        latest=latest,
        profile=profile,
        session_tool_path=session_tool_path,
    )
    fields = [
        "total_cases",
        "unique_known_true_addr_count",
        "baseline_eligible_count",
        "execution_batches_count",
        "invalid_config_count",
        "stable_case_candidate_count",
        "conclusion",
    ]
    python_data = python_result.to_dict()
    mismatches: list[CaseLibraryMismatch] = []
    for field in fields:
        left = _normalize_parity_value(python_data.get(field))
        right = _normalize_parity_value(powershell_result.get(field))
        if left != right:
            mismatches.append(CaseLibraryMismatch(field=field, python_value=left, powershell_value=right))

    return CaseLibraryParityResult(
        parity_status="PASS" if not mismatches else "FAIL",
        mismatch_count=len(mismatches),
        mismatches=mismatches,
    )


def _latest_batch_records(*, log_root: Path, latest: int) -> list[BatchSummaryRecord]:
    if not log_root.exists():
        raise LogParseError(f"log root does not exist: {log_root}")
    if not log_root.is_dir():
        raise LogParseError(f"log root is not a directory: {log_root}")

    records: list[BatchSummaryRecord] = []
    for batch_id in _discover_batch_ids(log_root)[:latest]:
        records.append(_parse_batch_record(log_root, batch_id))
    return records


def _discover_batch_ids(log_root: Path) -> list[str]:
    batch_ids = set()
    for path in log_root.iterdir():
        if not path.is_file():
            continue
        match = BATCH_ARTIFACT_RE.match(path.name)
        if match:
            batch_ids.add(match.group("batch_id"))
    return sorted(batch_ids, reverse=True)


def _parse_batch_record(log_root: Path, batch_id: str) -> BatchSummaryRecord:
    summary = log_root / f"{batch_id}__summary.txt"
    if summary.exists():
        return parse_summary_file(summary)
    return _parse_legacy_incomplete_record(log_root, batch_id)


def _parse_legacy_incomplete_record(log_root: Path, batch_id: str) -> BatchSummaryRecord:
    mode_files = sorted(log_root.glob(f"{batch_id}__*.log"))
    if not mode_files:
        raise LogParseError(f"no readable batch artifact found for {batch_id}")
    mode_sections = [_parse_simple_key_values(path) for path in mode_files]
    first = mode_sections[0]
    known_true_addr = _first_present(*(section.get("known_true_addr") for section in mode_sections))
    target_pattern = _first_present(*(section.get("target_value_pattern") for section in mode_sections))
    target_float = _first_present(*(section.get("target_value_float") for section in mode_sections))
    best_candidate = _first_present(*(section.get("best_candidate") for section in reversed(mode_sections)))
    ranks = []
    for marker in ("no_probe_A", "with_probe", "no_probe_B"):
        section = next((values for path, values in zip(mode_files, mode_sections) if marker in path.name), None)
        ranks.append(_normalize_value(section.get("known_true_rank_position") if section else None) or "nil")

    classification = "incomplete_output"
    if len(mode_files) >= 3 and _address_equal(best_candidate, known_true_addr):
        classification = "success"

    return BatchSummaryRecord(
        batch_id=batch_id,
        classification=classification,
        validation_profile="full",
        known_true_addr=known_true_addr,
        target_value_float=_normalize_value(target_float),
        target_value_pattern=_normalize_value(target_pattern),
        final_hit=_address_equal(best_candidate, known_true_addr),
        rank_AWB="/".join(ranks),
        stable_rank=None,
        best_candidate=best_candidate,
        baseline_eligible=None,
        execution_outcome="execution_disabled",
        transaction_type="detect_only",
        recommendation="not an algorithm failure; rerun or inspect output persistence",
        source_log=str(mode_files[0]),
    )


def _parse_simple_key_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        if key and key not in values:
            values[key] = value.strip()
    return values


def _address_rows(records: list[BatchSummaryRecord]) -> list[CaseLibraryAddressRecord]:
    by_addr: dict[str, list[BatchSummaryRecord]] = {}
    for record in records:
        if record.known_true_addr:
            by_addr.setdefault(record.known_true_addr, []).append(record)

    rows: list[CaseLibraryAddressRecord] = []
    for addr, addr_records in sorted(by_addr.items()):
        success_records = [record for record in addr_records if _classification_success(record)]
        full_success_records = [
            record
            for record in addr_records
            if record.validation_profile == "full" and record.classification == "success"
        ]
        quick_success_records = [
            record
            for record in addr_records
            if record.validation_profile == "quick" and record.classification == "quick_success"
        ]
        profiles = sorted({record.validation_profile for record in addr_records if record.validation_profile})
        batch_ids = sorted(record.batch_id for record in addr_records)
        baseline_count = sum(1 for record in addr_records if _baseline_eligible_true(record))
        execution_count = sum(1 for record in addr_records if _is_execution_batch(record))
        invalid_count = sum(1 for record in addr_records if record.classification == "invalid_config_mismatch")
        write_dependency_count = sum(1 for record in addr_records if _has_write_dependency(record))
        stable_candidate = len(full_success_records) >= 2 and invalid_count == 0 and write_dependency_count == 0
        rows.append(
            CaseLibraryAddressRecord(
                known_true_addr=addr,
                cases=len(addr_records),
                success=len(success_records),
                full_succ=len(full_success_records),
                quick_succ=len(quick_success_records),
                first_seen=batch_ids[0] if batch_ids else "-",
                last_seen=batch_ids[-1] if batch_ids else "-",
                profiles="/".join(profiles) if profiles else "-",
                baseline_eligible_count=baseline_count,
                execution_batches_count=execution_count,
                invalid_config_count=invalid_count,
                stable_candidate=stable_candidate,
            )
        )
    return sorted(rows, key=lambda row: (not row.stable_candidate, -row.full_succ, row.known_true_addr))


def _classification_success(record: BatchSummaryRecord) -> bool:
    return record.classification in {"success", "quick_success"}


def _baseline_eligible_true(record: BatchSummaryRecord) -> bool:
    return str(record.baseline_eligible).strip().lower() == "true"


def _is_execution_batch(record: BatchSummaryRecord) -> bool:
    return bool(record.transaction_type and record.transaction_type != "detect_only")


def _has_write_dependency(record: BatchSummaryRecord) -> bool:
    return record.transaction_type in {
        "write_success",
        "restore_success",
        "write_blocked",
        "restore_blocked",
        "execution_failed",
    }


def _case_library_conclusion(records: list[BatchSummaryRecord], rows: list[CaseLibraryAddressRecord]) -> str:
    if not records or not rows:
        return "INSUFFICIENT_DATA"
    if any(row.cases >= 5 or (row.cases - 1) >= 3 for row in rows):
        return "DUPLICATE_HEAVY"
    if sum(1 for row in rows if row.stable_candidate) < 3:
        return "NEED_MORE_FULL_CASES"
    return "CASE_LIBRARY_OK"


def _case_library_recommendation(conclusion: str) -> str:
    if conclusion == "CASE_LIBRARY_OK":
        return "Case library has stable full candidates for current planning."
    if conclusion == "NEED_MORE_FULL_CASES":
        return "Collect more distinct full success cases with at least two clean full runs per address."
    if conclusion == "DUPLICATE_HEAVY":
        return "Reduce repeated addresses and add new distinct full detect-only cases."
    if conclusion == "INSUFFICIENT_DATA":
        return "Not enough classified logs found for case library planning."
    return "Review case library output before changing baselines."


def _run_powershell_case_library(*, latest: int, profile: str, session_tool_path: Path) -> dict[str, object | None]:
    if not session_tool_path.exists():
        raise LogParseError(f"PowerShell session tool not found: {session_tool_path}")

    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(session_tool_path),
        "case-library",
        "-Latest",
        str(latest),
    ]
    if profile != "all":
        command.extend(["-Profile", profile])
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=180)
    except FileNotFoundError as exc:
        raise LogParseError("PowerShell executable was not found for case library parity") from exc
    except subprocess.TimeoutExpired as exc:
        raise LogParseError("PowerShell case-library parity check timed out") from exc

    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        detail = f": {message}" if message else ""
        raise LogParseError(f"PowerShell case-library failed with exit code {completed.returncode}{detail}")
    return _parse_powershell_case_library(completed.stdout)


def _parse_powershell_case_library(text: str) -> dict[str, object | None]:
    field_map = {
        "total cases": "total_cases",
        "unique known_true_addr count": "unique_known_true_addr_count",
        "baseline eligible count": "baseline_eligible_count",
        "execution batches count": "execution_batches_count",
        "invalid config count": "invalid_config_count",
        "stable case candidate count": "stable_case_candidate_count",
        "conclusion": "conclusion",
    }
    parsed: dict[str, object | None] = {}
    for raw_line in text.splitlines():
        parts = re.split(r"\s{2,}", raw_line.strip(), maxsplit=1)
        if len(parts) != 2:
            continue
        field = field_map.get(parts[0].strip())
        if field:
            parsed[field] = _parse_scalar(parts[1].strip())
    return parsed


def _parse_scalar(value: str) -> object | None:
    if value in {"", "-", "nil"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _first_present(*values: str | None) -> str | None:
    for value in values:
        if value is not None and str(value).strip() not in {"", "-", "nil", "None"}:
            return str(value).strip()
    return None


def _normalize_parity_value(value: object | None) -> object | None:
    if value in {"", "-", "nil", "None"}:
        return None
    return value
