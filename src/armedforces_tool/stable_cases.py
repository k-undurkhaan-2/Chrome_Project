from __future__ import annotations

import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .case_library import (
    DEFAULT_SESSION_TOOL_PATH,
    _baseline_eligible_true,
    _discover_batch_ids,
    _has_write_dependency,
    _is_execution_batch,
    _parse_batch_record,
)
from .logs import BatchSummaryRecord, LogParseError

KNOWN_TRUE_ADDR_RE = re.compile(r"^0x[0-9A-Fa-f]+$")

QUALITY_REASONS = {
    "latest_full_not_success",
    "latest_final_hit_false",
    "latest_rank_not_1_1_1",
    "latest_stable_rank_not_1",
    "has_invalid_config_mismatch",
    "has_known_true_value_mismatch",
    "has_ranking_issue",
    "has_selected_quota_issue",
}
CLEAN_RUN_REASONS = {"full_success_lt_min", "baseline_eligible_lt_min", "no_full_success"}


@dataclass(frozen=True)
class StableCaseReasonCount:
    rejection_reason: str
    affected_addr_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "rejection_reason": self.rejection_reason,
            "affected_addr_count": self.affected_addr_count,
        }


@dataclass(frozen=True)
class StableCaseAddressRecord:
    known_true_addr: str
    full_success_count: int
    baseline_eligible_count: int
    quick_success_count: int
    first_seen_batch: str
    last_seen_batch: str
    latest_full_batch: str
    latest_classification: str
    latest_best_candidate: str
    latest_rank_AWB: str
    latest_stable_rank: str
    stable_candidate: bool
    rejection_reasons: list[str]
    recommended_action: str
    total_cases: int

    def to_dict(self) -> dict[str, object]:
        return {
            "known_true_addr": self.known_true_addr,
            "full_success_count": self.full_success_count,
            "baseline_eligible_count": self.baseline_eligible_count,
            "quick_success_count": self.quick_success_count,
            "first_seen_batch": self.first_seen_batch,
            "last_seen_batch": self.last_seen_batch,
            "latest_full_batch": self.latest_full_batch,
            "latest_classification": self.latest_classification,
            "latest_best_candidate": self.latest_best_candidate,
            "latest_rank_AWB": self.latest_rank_AWB,
            "latest_stable_rank": self.latest_stable_rank,
            "stable_candidate": self.stable_candidate,
            "rejection_reasons": self.rejection_reasons,
            "recommended_action": self.recommended_action,
            "total_cases": self.total_cases,
        }


@dataclass(frozen=True)
class StableCasesResult:
    latest_n: int
    profile: str
    min_full_success: int
    target_unique: int
    total_unique_addr: int
    stable_candidate_count: int
    rejected_address_count: int
    addresses_needing_only_more_clean_full_runs: int
    addresses_blocked_by_quality_issues: int
    duplicate_heavy_top_addr: str
    duplicate_heavy_warning: bool
    coverage_readiness: str
    recommended_action: str
    reason_summary: list[StableCaseReasonCount]
    addresses: list[StableCaseAddressRecord]

    def to_dict(self) -> dict[str, object]:
        return {
            "latest_n": self.latest_n,
            "profile": self.profile,
            "min_full_success": self.min_full_success,
            "target_unique": self.target_unique,
            "total_unique_addr": self.total_unique_addr,
            "stable_candidate_count": self.stable_candidate_count,
            "rejected_address_count": self.rejected_address_count,
            "addresses_needing_only_more_clean_full_runs": self.addresses_needing_only_more_clean_full_runs,
            "addresses_blocked_by_quality_issues": self.addresses_blocked_by_quality_issues,
            "duplicate_heavy_top_addr": self.duplicate_heavy_top_addr,
            "duplicate_heavy_warning": self.duplicate_heavy_warning,
            "coverage_readiness": self.coverage_readiness,
            "recommended_action": self.recommended_action,
            "reason_summary": [item.to_dict() for item in self.reason_summary],
            "addresses": [record.to_dict() for record in self.addresses],
        }


@dataclass(frozen=True)
class StableCasesMismatch:
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
class StableCasesParityResult:
    parity_status: str
    mismatch_count: int
    mismatches: list[StableCasesMismatch]

    def to_dict(self) -> dict[str, object]:
        return {
            "parity_status": self.parity_status,
            "mismatch_count": self.mismatch_count,
            "mismatches": [mismatch.to_dict() for mismatch in self.mismatches],
        }


def analyze_stable_cases(
    *,
    log_root: Path,
    latest: int,
    profile: str = "full",
    min_full_success: int = 2,
    target_unique: int = 13,
) -> StableCasesResult:
    if latest < 1:
        raise LogParseError("--latest must be greater than 0")
    if min_full_success < 1:
        raise LogParseError("--min-full-success must be greater than 0")
    if target_unique < 1:
        raise LogParseError("--target-unique must be greater than 0")

    records = [
        record
        for record in _latest_profile_records(log_root=log_root, latest=latest, profile=profile)
        if record.known_true_addr
    ]
    rows = _stable_case_rows(records, min_full_success=min_full_success)
    stable_rows = [row for row in rows if row.stable_candidate]
    rejected_rows = [row for row in rows if not row.stable_candidate]
    reason_summary = _reason_summary(rejected_rows)
    only_more_clean_runs = sum(1 for row in rejected_rows if _only_needs_clean_runs(row.rejection_reasons))
    quality_issues = sum(1 for row in rejected_rows if _has_quality_issue(row.rejection_reasons))
    top_repeated = _top_repeated_addr(rows)
    readiness = _coverage_readiness(stable_count=len(stable_rows), target_unique=target_unique)

    return StableCasesResult(
        latest_n=latest,
        profile=profile,
        min_full_success=min_full_success,
        target_unique=target_unique,
        total_unique_addr=len(rows),
        stable_candidate_count=len(stable_rows),
        rejected_address_count=len(rejected_rows),
        addresses_needing_only_more_clean_full_runs=only_more_clean_runs,
        addresses_blocked_by_quality_issues=quality_issues,
        duplicate_heavy_top_addr=top_repeated,
        duplicate_heavy_warning=_duplicate_heavy_warning(rows),
        coverage_readiness=readiness,
        recommended_action=_stable_case_recommendation(readiness),
        reason_summary=reason_summary,
        addresses=rows,
    )


def validate_known_true_addr(value: str | None) -> str:
    if value is None or not str(value).strip():
        raise LogParseError("invalid known_true_addr: value is empty; expected 0x-prefixed hex address")
    text = str(value).strip()
    if text in {"0x", "0x..."} or "..." in text:
        raise LogParseError("invalid known_true_addr: placeholder values such as 0x... are not allowed")
    if re.fullmatch(r"[0-9A-Fa-f]+", text):
        raise LogParseError(f"invalid known_true_addr: {text}; add the 0x prefix")
    if not KNOWN_TRUE_ADDR_RE.fullmatch(text):
        raise LogParseError(f"invalid known_true_addr: {text}; expected ^0x[0-9A-Fa-f]+$")
    return text


def filter_stable_case_result(result: StableCasesResult, known_true_addr: str) -> StableCasesResult:
    addr = validate_known_true_addr(known_true_addr)
    rows = [row for row in result.addresses if row.known_true_addr.lower() == addr.lower()]
    if not rows:
        raise LogParseError(
            f"known_true_addr not found in latest {result.latest_n} {result.profile} records: {known_true_addr}"
        )
    return StableCasesResult(
        latest_n=result.latest_n,
        profile=result.profile,
        min_full_success=result.min_full_success,
        target_unique=result.target_unique,
        total_unique_addr=result.total_unique_addr,
        stable_candidate_count=result.stable_candidate_count,
        rejected_address_count=result.rejected_address_count,
        addresses_needing_only_more_clean_full_runs=result.addresses_needing_only_more_clean_full_runs,
        addresses_blocked_by_quality_issues=result.addresses_blocked_by_quality_issues,
        duplicate_heavy_top_addr=result.duplicate_heavy_top_addr,
        duplicate_heavy_warning=result.duplicate_heavy_warning,
        coverage_readiness=result.coverage_readiness,
        recommended_action=result.recommended_action,
        reason_summary=_reason_summary(rows if not rows[0].stable_candidate else []),
        addresses=rows,
    )


def stable_cases_parity(
    *,
    log_root: Path,
    latest: int,
    profile: str = "full",
    min_full_success: int = 2,
    target_unique: int = 13,
    session_tool_path: Path = DEFAULT_SESSION_TOOL_PATH,
) -> StableCasesParityResult:
    python_result = analyze_stable_cases(
        log_root=log_root,
        latest=latest,
        profile=profile,
        min_full_success=min_full_success,
        target_unique=target_unique,
    )
    powershell_result = _run_powershell_stable_cases(
        latest=latest,
        profile=profile,
        min_full_success=min_full_success,
        target_unique=target_unique,
        session_tool_path=session_tool_path,
    )
    fields = [
        "stable_candidate_count",
        "target_unique",
        "total_unique_addr",
        "coverage_readiness",
    ]
    python_data = python_result.to_dict()
    mismatches: list[StableCasesMismatch] = []
    for field in fields:
        left = _normalize_parity_value(python_data.get(field))
        right = _normalize_parity_value(powershell_result.get(field))
        if left != right:
            mismatches.append(StableCasesMismatch(field=field, python_value=left, powershell_value=right))
    return StableCasesParityResult(
        parity_status="PASS" if not mismatches else "FAIL",
        mismatch_count=len(mismatches),
        mismatches=mismatches,
    )


def _latest_profile_records(*, log_root: Path, latest: int, profile: str) -> list[BatchSummaryRecord]:
    records: list[BatchSummaryRecord] = []
    for batch_id in _discover_batch_ids(log_root):
        record = _parse_batch_record(log_root, batch_id)
        if profile != "all" and record.validation_profile != profile:
            continue
        records.append(record)
        if len(records) >= latest:
            break
    return records


def _stable_case_rows(
    records: list[BatchSummaryRecord],
    *,
    min_full_success: int,
) -> list[StableCaseAddressRecord]:
    by_addr: dict[str, list[tuple[int, BatchSummaryRecord]]] = {}
    for scan_order, record in enumerate(records, start=1):
        if record.known_true_addr:
            by_addr.setdefault(record.known_true_addr, []).append((scan_order, record))

    rows: list[StableCaseAddressRecord] = []
    for addr, addr_records in sorted(by_addr.items()):
        ordered = sorted(addr_records, key=lambda item: item[0])
        record_values = [record for _, record in ordered]
        batch_ids = sorted(record.batch_id for record in record_values if record.batch_id)
        full_records = [(order, record) for order, record in ordered if record.validation_profile == "full"]
        latest_full = full_records[0][1] if full_records else None

        full_success_count = sum(1 for record in record_values if _record_full_success(record))
        baseline_eligible_count = sum(1 for record in record_values if _record_baseline_eligible_success(record))
        quick_success_count = sum(1 for record in record_values if record.classification == "quick_success")
        execution_count = sum(
            1 for record in record_values if _is_execution_batch(record) or _has_write_dependency(record)
        )

        reasons = _rejection_reasons(
            record_values=record_values,
            latest_full=latest_full,
            full_success_count=full_success_count,
            baseline_eligible_count=baseline_eligible_count,
            execution_count=execution_count,
            min_full_success=min_full_success,
        )
        stable_candidate = not reasons
        rows.append(
            StableCaseAddressRecord(
                known_true_addr=addr,
                full_success_count=full_success_count,
                baseline_eligible_count=baseline_eligible_count,
                quick_success_count=quick_success_count,
                first_seen_batch=batch_ids[0] if batch_ids else "-",
                last_seen_batch=batch_ids[-1] if batch_ids else "-",
                latest_full_batch=latest_full.batch_id if latest_full else "-",
                latest_classification=latest_full.classification if latest_full else "-",
                latest_best_candidate=latest_full.best_candidate if latest_full and latest_full.best_candidate else "-",
                latest_rank_AWB=latest_full.rank_AWB if latest_full else "-",
                latest_stable_rank=latest_full.stable_rank if latest_full and latest_full.stable_rank else "-",
                stable_candidate=stable_candidate,
                rejection_reasons=reasons,
                recommended_action=_recommended_action(
                    reasons=reasons,
                    stable_candidate=stable_candidate,
                    full_success_count=full_success_count,
                    baseline_eligible_count=baseline_eligible_count,
                    min_full_success=min_full_success,
                ),
                total_cases=len(record_values),
            )
        )
    return sorted(rows, key=lambda row: (not row.stable_candidate, -row.full_success_count, row.known_true_addr))


def _rejection_reasons(
    *,
    record_values: list[BatchSummaryRecord],
    latest_full: BatchSummaryRecord | None,
    full_success_count: int,
    baseline_eligible_count: int,
    execution_count: int,
    min_full_success: int,
) -> list[str]:
    reasons: list[str] = []
    if full_success_count < min_full_success:
        reasons.append("full_success_lt_min")
    if baseline_eligible_count < min_full_success:
        reasons.append("baseline_eligible_lt_min")
    if full_success_count == 0:
        reasons.append("no_full_success")

    if latest_full is not None:
        if not _record_full_success(latest_full):
            reasons.append("latest_full_not_success")
        if latest_full.final_hit is not True:
            reasons.append("latest_final_hit_false")
        if latest_full.rank_AWB != "1/1/1":
            reasons.append("latest_rank_not_1_1_1")
        if latest_full.stable_rank != "1":
            reasons.append("latest_stable_rank_not_1")

    if any(record.classification == "invalid_config_mismatch" for record in record_values):
        reasons.append("has_invalid_config_mismatch")
    if any(record.classification == "known_true_value_mismatch" for record in record_values):
        reasons.append("has_known_true_value_mismatch")
    if any(record.classification == "ranking_issue" for record in record_values):
        reasons.append("has_ranking_issue")
    if any(record.classification == "selected_quota_issue" for record in record_values):
        reasons.append("has_selected_quota_issue")
    if execution_count > 0:
        reasons.append("has_execution_batch")
    return reasons


def _record_full_success(record: BatchSummaryRecord) -> bool:
    return record.validation_profile == "full" and record.classification == "success"


def _record_baseline_eligible_success(record: BatchSummaryRecord) -> bool:
    return _record_full_success(record) and _baseline_eligible_true(record)


def _recommended_action(
    *,
    reasons: list[str],
    stable_candidate: bool,
    full_success_count: int,
    baseline_eligible_count: int,
    min_full_success: int,
) -> str:
    if stable_candidate:
        return "Ready as stable baseline candidate."
    if _has_quality_issue(reasons):
        return "Inspect failed batches before using this address as baseline candidate."
    if "has_execution_batch" in reasons:
        return "Do not use execution batches for baseline; collect clean detect-only confirmations."
    if _only_needs_clean_runs(reasons):
        needed = max(min_full_success - full_success_count, min_full_success - baseline_eligible_count)
        if needed < 1:
            needed = 1
        return f"Collect {needed} more full detect-only baseline-eligible success run(s)."
    return "Collect clean full detect-only confirmations and inspect latest failures before baseline use."


def _only_needs_clean_runs(reasons: list[str]) -> bool:
    return bool(reasons) and all(reason in CLEAN_RUN_REASONS for reason in reasons)


def _has_quality_issue(reasons: list[str]) -> bool:
    return any(reason in QUALITY_REASONS for reason in reasons)


def _reason_summary(rows: list[StableCaseAddressRecord]) -> list[StableCaseReasonCount]:
    counts = Counter(reason for row in rows for reason in row.rejection_reasons)
    return [
        StableCaseReasonCount(rejection_reason=reason, affected_addr_count=count)
        for reason, count in sorted(counts.items())
    ]


def _coverage_readiness(*, stable_count: int, target_unique: int) -> str:
    if stable_count >= target_unique:
        return "READY_FOR_BASELINE"
    return "NEED_MORE_STABLE_CASES"


def _stable_case_recommendation(readiness: str) -> str:
    if readiness == "READY_FOR_BASELINE":
        return "Use stable candidates to build/refresh baseline."
    return "Collect more distinct full detect-only clean runs."


def _top_repeated_addr(rows: list[StableCaseAddressRecord]) -> str:
    if not rows:
        return "none"
    top = sorted(rows, key=lambda row: (-row.total_cases, row.known_true_addr))[0]
    return f"{top.known_true_addr} count {top.total_cases}"


def _duplicate_heavy_warning(rows: list[StableCaseAddressRecord]) -> bool:
    if not rows:
        return False
    return max(row.total_cases for row in rows) >= 5


def _run_powershell_stable_cases(
    *,
    latest: int,
    profile: str,
    min_full_success: int,
    target_unique: int,
    session_tool_path: Path,
) -> dict[str, object | None]:
    if not session_tool_path.exists():
        raise LogParseError(f"PowerShell session tool not found: {session_tool_path}")

    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(session_tool_path),
        "stable-cases",
        "-Latest",
        str(latest),
        "-Profile",
        profile,
        "-MinFullSuccess",
        str(min_full_success),
        "-TargetUnique",
        str(target_unique),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=180)
    except FileNotFoundError as exc:
        raise LogParseError("PowerShell executable was not found for stable-cases parity") from exc
    except subprocess.TimeoutExpired as exc:
        raise LogParseError("PowerShell stable-cases parity check timed out") from exc

    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        detail = f": {message}" if message else ""
        raise LogParseError(f"PowerShell stable-cases failed with exit code {completed.returncode}{detail}")
    return _parse_powershell_stable_cases(completed.stdout)


def _parse_powershell_stable_cases(text: str) -> dict[str, object | None]:
    field_map = {
        "stable candidate count": "stable_candidate_count",
        "target unique": "target_unique",
        "total unique addr": "total_unique_addr",
        "coverage readiness": "coverage_readiness",
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
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    return value


def _normalize_parity_value(value: object | None) -> object | None:
    if value in {"", "-", "nil", "None"}:
        return None
    return value
