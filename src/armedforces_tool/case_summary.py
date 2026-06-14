from __future__ import annotations

import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .logs import BatchSummaryRecord, LogParseError, discover_summary_files, parse_summary_file

DEFAULT_BASELINE_PATH = Path(r"D:\armedforces.io-v2\log\baselines\baseline_compact_basic_20260613_latest20.md")
DEFAULT_SESSION_TOOL_PATH = Path(r"D:\armedforces.io-v2\src\test_session_tool.ps1")


@dataclass(frozen=True)
class RepeatedAddress:
    known_true_addr: str
    count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "known_true_addr": self.known_true_addr,
            "count": self.count,
        }


@dataclass(frozen=True)
class CaseSummaryResult:
    latest_n: int
    profile: str
    baseline_path: str
    baseline_exists: bool
    baseline_unique_known_true_addr_count: int | None
    target_unique_source: str
    target_unique_known_true_addr_count: int | None
    current_eligible_batch_count: int
    current_success_count: int
    current_unique_known_true_addr_count: int
    coverage_delta: int | None
    repeated_known_true_addr: list[RepeatedAddress]
    top_repeated_addr: str | None
    estimated_new_distinct_addr_needed: int | None
    conclusion: str
    recommendation: str

    def to_dict(self) -> dict[str, object | None]:
        return {
            "latest_n": self.latest_n,
            "profile": self.profile,
            "baseline_path": self.baseline_path,
            "baseline_exists": self.baseline_exists,
            "baseline_unique_known_true_addr_count": self.baseline_unique_known_true_addr_count,
            "target_unique_source": self.target_unique_source,
            "target_unique_known_true_addr_count": self.target_unique_known_true_addr_count,
            "current_eligible_batch_count": self.current_eligible_batch_count,
            "current_success_count": self.current_success_count,
            "current_unique_known_true_addr_count": self.current_unique_known_true_addr_count,
            "coverage_delta": self.coverage_delta,
            "repeated_known_true_addr": [item.to_dict() for item in self.repeated_known_true_addr],
            "top_repeated_addr": self.top_repeated_addr,
            "estimated_new_distinct_addr_needed": self.estimated_new_distinct_addr_needed,
            "conclusion": self.conclusion,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class CaseSummaryMismatch:
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
class CaseSummaryParityResult:
    parity_status: str
    mismatch_count: int
    mismatches: list[CaseSummaryMismatch]

    def to_dict(self) -> dict[str, object]:
        return {
            "parity_status": self.parity_status,
            "mismatch_count": self.mismatch_count,
            "mismatches": [item.to_dict() for item in self.mismatches],
        }


def analyze_case_summary(
    *,
    log_root: Path,
    latest: int,
    profile: str,
    baseline: Path,
    target_unique: int | None = None,
) -> CaseSummaryResult:
    if latest < 1:
        raise LogParseError("--latest must be greater than 0")
    if target_unique is not None and target_unique < 1:
        raise LogParseError("--target-unique must be greater than 0")

    baseline_exists = baseline.exists()
    baseline_unique = parse_baseline_unique_count(baseline) if baseline_exists else None
    if baseline_unique is not None:
        resolved_target = baseline_unique
        target_source = "baseline"
    elif target_unique is not None:
        resolved_target = target_unique
        target_source = "argument"
    else:
        resolved_target = None
        target_source = "none"

    records = _latest_baseline_eligible_records(log_root=log_root, latest=latest, profile=profile)
    known_true_addrs = [record.known_true_addr for record in records if record.known_true_addr]
    addr_counts = Counter(known_true_addrs)
    repeated = [
        RepeatedAddress(known_true_addr=addr, count=count)
        for addr, count in addr_counts.most_common()
        if count > 1
    ]
    top_repeated = f"{repeated[0].known_true_addr} count {repeated[0].count}" if repeated else None

    current_unique = len(addr_counts)
    coverage_delta = current_unique - resolved_target if resolved_target is not None else None
    estimated = _estimate_new_distinct_needed(known_true_addrs, latest, resolved_target)
    conclusion = _coverage_conclusion(
        target_unique=resolved_target,
        eligible_count=len(records),
        current_unique=current_unique,
    )
    recommendation = _coverage_recommendation(conclusion, estimated, bool(repeated))

    return CaseSummaryResult(
        latest_n=latest,
        profile=profile,
        baseline_path=str(baseline),
        baseline_exists=baseline_exists,
        baseline_unique_known_true_addr_count=baseline_unique,
        target_unique_source=target_source,
        target_unique_known_true_addr_count=resolved_target,
        current_eligible_batch_count=len(records),
        current_success_count=sum(1 for record in records if record.classification == "success"),
        current_unique_known_true_addr_count=current_unique,
        coverage_delta=coverage_delta,
        repeated_known_true_addr=repeated,
        top_repeated_addr=top_repeated,
        estimated_new_distinct_addr_needed=estimated,
        conclusion=conclusion,
        recommendation=recommendation,
    )


def parse_baseline_unique_count(path: Path) -> int | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"unique\s+known_true_addr\s+count\s*:\s*(\d+)", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def case_summary_parity(
    *,
    log_root: Path,
    latest: int,
    profile: str,
    baseline: Path,
    target_unique: int | None = None,
    session_tool_path: Path = DEFAULT_SESSION_TOOL_PATH,
) -> CaseSummaryParityResult:
    python_result = analyze_case_summary(
        log_root=log_root,
        latest=latest,
        profile=profile,
        baseline=baseline,
        target_unique=target_unique,
    )
    powershell_result = _run_powershell_case_summary(
        latest=latest,
        profile=profile,
        baseline=baseline,
        target_unique=target_unique,
        session_tool_path=session_tool_path,
    )

    fields = [
        "current_eligible_batch_count",
        "current_success_count",
        "current_unique_known_true_addr_count",
        "target_unique_known_true_addr_count",
        "coverage_delta",
        "conclusion",
    ]
    python_data = python_result.to_dict()
    mismatches: list[CaseSummaryMismatch] = []
    for field in fields:
        left = _normalize_parity_value(python_data.get(field))
        right = _normalize_parity_value(powershell_result.get(field))
        if left != right:
            mismatches.append(CaseSummaryMismatch(field=field, python_value=left, powershell_value=right))

    return CaseSummaryParityResult(
        parity_status="PASS" if not mismatches else "FAIL",
        mismatch_count=len(mismatches),
        mismatches=mismatches,
    )


def _latest_baseline_eligible_records(*, log_root: Path, latest: int, profile: str) -> list[BatchSummaryRecord]:
    records: list[BatchSummaryRecord] = []
    for path in discover_summary_files(log_root):
        record = parse_summary_file(path)
        if profile != "all" and record.validation_profile != profile:
            continue
        if not _is_case_summary_baseline_eligible(record):
            continue
        records.append(record)
        if len(records) >= latest:
            break
    return records


def _is_case_summary_baseline_eligible(record: BatchSummaryRecord) -> bool:
    if str(record.baseline_eligible).lower() == "true":
        return True
    return (
        record.baseline_eligible is None
        and record.classification == "success"
        and record.validation_profile == "full"
        and record.execution_outcome == "execution_disabled"
    )


def _estimate_new_distinct_needed(
    known_true_addrs_newest_first: list[str],
    latest: int,
    target_unique: int | None,
) -> int | None:
    if target_unique is None:
        return None
    window = known_true_addrs_newest_first[:latest]
    if len(set(window)) >= target_unique:
        return 0

    for new_count in range(1, latest + 1):
        kept = window[: max(latest - new_count, 0)]
        if len(set(kept)) + new_count >= target_unique:
            return new_count
    return None


def _coverage_conclusion(*, target_unique: int | None, eligible_count: int, current_unique: int) -> str:
    if target_unique is None:
        return "NO_BASELINE"
    if eligible_count == 0:
        return "INSUFFICIENT_DATA"
    if current_unique >= target_unique:
        return "COVERAGE_OK"
    return "COVERAGE_WARN"


def _coverage_recommendation(conclusion: str, estimated: int | None, has_repeats: bool) -> str:
    if conclusion == "COVERAGE_OK":
        message = "Coverage is sufficient for the selected baseline."
    elif conclusion == "COVERAGE_WARN":
        needed = estimated if estimated is not None else "more"
        message = f"Collect at least {needed} new distinct full detect-only baseline-eligible batch(es)."
    elif conclusion == "NO_BASELINE":
        message = "Provide --target-unique or a baseline with unique known_true_addr count."
    else:
        message = "Collect baseline-eligible batches before evaluating coverage."

    if has_repeats:
        message += " Avoid repeating top repeated addr unless intentionally checking stability."
    return message


def _run_powershell_case_summary(
    *,
    latest: int,
    profile: str,
    baseline: Path,
    target_unique: int | None,
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
        "case-summary",
        "-Latest",
        str(latest),
        "-Profile",
        profile,
        "-Baseline",
        str(baseline),
    ]
    if target_unique is not None:
        command.extend(["-TargetUnique", str(target_unique)])

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
    except FileNotFoundError as exc:
        raise LogParseError("PowerShell executable was not found for case summary parity") from exc
    except subprocess.TimeoutExpired as exc:
        raise LogParseError("PowerShell case summary parity check timed out") from exc

    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        detail = f": {message}" if message else ""
        raise LogParseError(f"PowerShell case-summary failed with exit code {completed.returncode}{detail}")
    return _parse_powershell_case_summary(completed.stdout)


def _parse_powershell_case_summary(text: str) -> dict[str, object | None]:
    field_map = {
        "current eligible batch count": "current_eligible_batch_count",
        "current success count": "current_success_count",
        "current unique known_true_addr count": "current_unique_known_true_addr_count",
        "target unique known_true_addr count": "target_unique_known_true_addr_count",
        "coverage delta": "coverage_delta",
        "conclusion": "conclusion",
    }
    parsed: dict[str, object | None] = {}
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
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


def _normalize_parity_value(value: object | None) -> object | None:
    if value in {"", "-", "nil", "None"}:
        return None
    return value
