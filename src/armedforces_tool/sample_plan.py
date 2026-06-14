from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .case_library import DEFAULT_SESSION_TOOL_PATH
from .logs import DEFAULT_LOG_ROOT, LogParseError
from .stable_cases import (
    StableCaseAddressRecord,
    StableCasesResult,
    analyze_stable_cases,
)

DEFAULT_ACTIVE_SESSION_PATH = Path(r"D:\armedforces.io-v2\log\active_test_session.local.json")
DEFAULT_CASE_INTAKE_PATH = Path(r"D:\armedforces.io-v2\log\case_intake.local.jsonl")

BLOCKED_REASONS = {
    "has_invalid_config_mismatch",
    "has_known_true_value_mismatch",
    "has_ranking_issue",
    "has_selected_quota_issue",
    "latest_final_hit_false",
    "latest_rank_not_1_1_1",
    "latest_stable_rank_not_1",
    "latest_full_not_success",
    "no_full_success",
}
CLEAN_COUNT_REASONS = {"full_success_lt_min", "baseline_eligible_lt_min"}
PRIORITY_RANK = {"HIGH": 1, "MEDIUM": 2, "LOW": 3, "BLOCKED": 4, "OTHER": 5}


@dataclass(frozen=True)
class ActiveSessionInfo:
    detected: bool
    active: bool
    session_id: str | None
    started_at_utc: str | None
    status: str
    reusable_addresses: dict[str, str]

    def to_dict(self) -> dict[str, object | None]:
        return {
            "detected": self.detected,
            "active": self.active,
            "session_id": self.session_id,
            "started_at_utc": self.started_at_utc,
            "status": self.status,
            "reusable_addresses": self.reusable_addresses,
        }


@dataclass(frozen=True)
class RetestQueueRecord:
    known_true_addr: str
    priority: str
    full_success_count: int
    baseline_eligible_count: int
    quick_success_count: int
    latest_batch: str
    latest_classification: str
    latest_rank_AWB: str
    latest_stable_rank: str
    missing_clean_full_runs: int
    rejection_reasons: list[str]
    recommended_action: str
    active_session_addr: bool
    active_session_source: str
    active_session_prepare: str

    def to_dict(self) -> dict[str, object]:
        return {
            "known_true_addr": self.known_true_addr,
            "priority": self.priority,
            "full_success_count": self.full_success_count,
            "baseline_eligible_count": self.baseline_eligible_count,
            "quick_success_count": self.quick_success_count,
            "latest_batch": self.latest_batch,
            "latest_classification": self.latest_classification,
            "latest_rank_AWB": self.latest_rank_AWB,
            "latest_stable_rank": self.latest_stable_rank,
            "missing_clean_full_runs": self.missing_clean_full_runs,
            "rejection_reasons": self.rejection_reasons,
            "recommended_action": self.recommended_action,
            "active_session_addr": self.active_session_addr,
            "active_session_source": self.active_session_source,
            "active_session_prepare": self.active_session_prepare,
        }


@dataclass(frozen=True)
class RetestQueueResult:
    latest_n: int
    profile: str
    target_unique: int
    min_full_success: int
    limit: int
    total_unique_addr: int
    stable_candidate_count: int
    queue_size: int
    need_more_clean_full_runs_count: int
    blocked_by_quality_issues_count: int
    duplicate_heavy_top_addr: str
    conclusion: str
    recommendation: str
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int
    blocked_count: int
    active_session_detected: bool
    active_session_id: str | None
    current_session_reusable_address_count: int
    active_session_prepare_command_count: int
    records: list[RetestQueueRecord]

    def to_dict(self) -> dict[str, object | None]:
        return {
            "latest_n": self.latest_n,
            "profile": self.profile,
            "target_unique": self.target_unique,
            "min_full_success": self.min_full_success,
            "limit": self.limit,
            "total_unique_addr": self.total_unique_addr,
            "stable_candidate_count": self.stable_candidate_count,
            "queue_size": self.queue_size,
            "need_more_clean_full_runs_count": self.need_more_clean_full_runs_count,
            "blocked_by_quality_issues_count": self.blocked_by_quality_issues_count,
            "duplicate_heavy_top_addr": self.duplicate_heavy_top_addr,
            "conclusion": self.conclusion,
            "recommendation": self.recommendation,
            "high_priority_count": self.high_priority_count,
            "medium_priority_count": self.medium_priority_count,
            "low_priority_count": self.low_priority_count,
            "blocked_count": self.blocked_count,
            "active_session_detected": self.active_session_detected,
            "active_session_id": self.active_session_id,
            "current_session_reusable_address_count": self.current_session_reusable_address_count,
            "active_session_prepare_command_count": self.active_session_prepare_command_count,
            "records": [record.to_dict() for record in self.records],
        }


@dataclass(frozen=True)
class SamplePlanRecord:
    known_true_addr: str
    plan_type: str
    priority: str
    reason: str
    command_hint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "known_true_addr": self.known_true_addr,
            "plan_type": self.plan_type,
            "priority": self.priority,
            "reason": self.reason,
            "command_hint": self.command_hint,
        }


@dataclass(frozen=True)
class SamplePlanResult:
    latest_n: int
    profile: str
    target_unique: int
    min_full_success: int
    limit: int
    current_stable_candidate_count: int
    estimated_new_stable_candidates_needed: int
    recommended_sample_count: int
    active_session_detected: bool
    active_session_requested: bool
    active_session_id: str | None
    current_session_reusable_address_count: int
    conclusion: str
    recommendation: str
    plan_item_count: int
    records: list[SamplePlanRecord]

    def to_dict(self) -> dict[str, object | None]:
        return {
            "latest_n": self.latest_n,
            "profile": self.profile,
            "target_unique": self.target_unique,
            "min_full_success": self.min_full_success,
            "limit": self.limit,
            "current_stable_candidate_count": self.current_stable_candidate_count,
            "estimated_new_stable_candidates_needed": self.estimated_new_stable_candidates_needed,
            "recommended_sample_count": self.recommended_sample_count,
            "active_session_detected": self.active_session_detected,
            "active_session_requested": self.active_session_requested,
            "active_session_id": self.active_session_id,
            "current_session_reusable_address_count": self.current_session_reusable_address_count,
            "conclusion": self.conclusion,
            "recommendation": self.recommendation,
            "plan_item_count": self.plan_item_count,
            "records": [record.to_dict() for record in self.records],
        }


@dataclass(frozen=True)
class PlanningMismatch:
    field: str
    python_value: object | None
    powershell_value: object | None
    status: str = "FAIL"

    def to_dict(self) -> dict[str, object | None]:
        return {
            "field": self.field,
            "python_value": self.python_value,
            "powershell_value": self.powershell_value,
            "status": self.status,
        }


@dataclass(frozen=True)
class PlanningParityResult:
    parity_status: str
    mismatch_count: int
    mismatches: list[PlanningMismatch]

    def to_dict(self) -> dict[str, object]:
        return {
            "parity_status": self.parity_status,
            "mismatch_count": self.mismatch_count,
            "mismatches": [mismatch.to_dict() for mismatch in self.mismatches],
        }


def analyze_retest_queue(
    *,
    log_root: Path = DEFAULT_LOG_ROOT,
    latest: int = 100,
    profile: str = "full",
    target_unique: int = 13,
    min_full_success: int = 2,
    limit: int = 10,
    active_session: bool = False,
    active_session_path: Path = DEFAULT_ACTIVE_SESSION_PATH,
    case_intake_path: Path = DEFAULT_CASE_INTAKE_PATH,
) -> RetestQueueResult:
    if limit < 1:
        raise LogParseError("--limit must be greater than 0")
    stable = analyze_stable_cases(
        log_root=log_root,
        latest=latest,
        profile=profile,
        min_full_success=min_full_success,
        target_unique=target_unique,
    )
    session = read_active_session_context(
        active_session_path=active_session_path,
        case_intake_path=case_intake_path,
        stable=stable,
        log_root=log_root,
    )
    active_reuse_allowed = active_session and session.active
    all_records = _queue_records(stable=stable, active_reuse_allowed=active_reuse_allowed, session=session)
    ordered = sorted(
        all_records,
        key=lambda record: (
            PRIORITY_RANK.get(record.priority, 5),
            record.missing_clean_full_runs,
            -record.baseline_eligible_count,
            record.latest_batch if record.latest_batch != "-" else "",
            record.known_true_addr,
        ),
        reverse=False,
    )
    # latest_batch should be newest first within the same priority/score group.
    ordered = sorted(
        ordered,
        key=lambda record: (
            PRIORITY_RANK.get(record.priority, 5),
            record.missing_clean_full_runs,
            -record.baseline_eligible_count,
            _reverse_batch_sort_key(record.latest_batch),
            record.known_true_addr,
        ),
    )
    high_count = sum(1 for record in all_records if record.priority == "HIGH")
    medium_count = sum(1 for record in all_records if record.priority == "MEDIUM")
    low_count = sum(1 for record in all_records if record.priority == "LOW")
    blocked_count = sum(1 for record in all_records if record.priority == "BLOCKED")
    clean_count = sum(1 for record in all_records if _only_clean_count_reasons(record.rejection_reasons))
    active_prepare_count = sum(1 for record in all_records if record.active_session_prepare != "-")
    current_reusable_count = sum(1 for record in all_records if record.active_session_addr)
    conclusion = _retest_conclusion(
        stable_count=stable.stable_candidate_count,
        target_unique=target_unique,
        queue_size=len(all_records),
    )
    return RetestQueueResult(
        latest_n=latest,
        profile=profile,
        target_unique=target_unique,
        min_full_success=min_full_success,
        limit=limit,
        total_unique_addr=stable.total_unique_addr,
        stable_candidate_count=stable.stable_candidate_count,
        queue_size=len(all_records),
        need_more_clean_full_runs_count=clean_count,
        blocked_by_quality_issues_count=blocked_count,
        duplicate_heavy_top_addr=stable.duplicate_heavy_top_addr,
        conclusion=conclusion,
        recommendation=_retest_recommendation(conclusion, high_count, medium_count, blocked_count),
        high_priority_count=high_count,
        medium_priority_count=medium_count,
        low_priority_count=low_count,
        blocked_count=blocked_count,
        active_session_detected=session.active,
        active_session_id=session.session_id,
        current_session_reusable_address_count=current_reusable_count,
        active_session_prepare_command_count=active_prepare_count,
        records=ordered[:limit],
    )


def analyze_sample_plan(
    *,
    log_root: Path = DEFAULT_LOG_ROOT,
    latest: int = 100,
    profile: str = "full",
    target_unique: int = 13,
    min_full_success: int = 2,
    limit: int = 10,
    active_session: bool = False,
    active_session_path: Path = DEFAULT_ACTIVE_SESSION_PATH,
    case_intake_path: Path = DEFAULT_CASE_INTAKE_PATH,
) -> SamplePlanResult:
    queue = analyze_retest_queue(
        log_root=log_root,
        latest=latest,
        profile=profile,
        target_unique=target_unique,
        min_full_success=min_full_success,
        limit=limit,
        active_session=active_session,
        active_session_path=active_session_path,
        case_intake_path=case_intake_path,
    )
    needed = max(target_unique - queue.stable_candidate_count, 0)
    if queue.stable_candidate_count >= target_unique:
        conclusion = "SAMPLE_PLAN_READY"
    elif not queue.total_unique_addr:
        conclusion = "INSUFFICIENT_DATA"
    elif active_session and not queue.active_session_detected:
        conclusion = "SAMPLE_PLAN_NO_ACTIVE_SESSION"
    else:
        conclusion = "SAMPLE_PLAN_NEEDS_COLLECTION"

    records = _sample_plan_records(queue=queue, needed=needed, active_session_requested=active_session)
    return SamplePlanResult(
        latest_n=latest,
        profile=profile,
        target_unique=target_unique,
        min_full_success=min_full_success,
        limit=limit,
        current_stable_candidate_count=queue.stable_candidate_count,
        estimated_new_stable_candidates_needed=needed,
        recommended_sample_count=min(limit, needed) if needed else 0,
        active_session_detected=queue.active_session_detected,
        active_session_requested=active_session,
        active_session_id=queue.active_session_id,
        current_session_reusable_address_count=queue.current_session_reusable_address_count,
        conclusion=conclusion,
        recommendation=_sample_plan_recommendation(conclusion),
        plan_item_count=len(records),
        records=records[:limit],
    )


def retest_queue_parity(
    *,
    log_root: Path = DEFAULT_LOG_ROOT,
    latest: int = 100,
    profile: str = "full",
    target_unique: int = 13,
    min_full_success: int = 2,
    limit: int = 10,
    session_tool_path: Path = DEFAULT_SESSION_TOOL_PATH,
) -> PlanningParityResult:
    python_result = analyze_retest_queue(
        log_root=log_root,
        latest=latest,
        profile=profile,
        target_unique=target_unique,
        min_full_success=min_full_success,
        limit=limit,
    )
    powershell = _run_powershell_planner(
        command_name="retest-queue",
        latest=latest,
        profile=profile,
        target_unique=target_unique,
        min_full_success=min_full_success,
        limit=limit,
        session_tool_path=session_tool_path,
    )
    return _compare_planner_fields(
        python_data={
            "queue_size": python_result.queue_size,
            "stable_candidate_count": python_result.stable_candidate_count,
            "target_unique": python_result.target_unique,
            "conclusion": python_result.conclusion,
        },
        powershell_data=powershell,
        plan_field_name="queue_size",
    )


def sample_plan_parity(
    *,
    log_root: Path = DEFAULT_LOG_ROOT,
    latest: int = 100,
    profile: str = "full",
    target_unique: int = 13,
    min_full_success: int = 2,
    limit: int = 10,
    session_tool_path: Path = DEFAULT_SESSION_TOOL_PATH,
) -> PlanningParityResult:
    python_result = analyze_sample_plan(
        log_root=log_root,
        latest=latest,
        profile=profile,
        target_unique=target_unique,
        min_full_success=min_full_success,
        limit=limit,
    )
    powershell = _run_powershell_planner(
        command_name="sample-plan",
        latest=latest,
        profile=profile,
        target_unique=target_unique,
        min_full_success=min_full_success,
        limit=limit,
        session_tool_path=session_tool_path,
    )
    return _compare_planner_fields(
        python_data={
            "plan_item_count": python_result.plan_item_count,
            "stable_candidate_count": python_result.current_stable_candidate_count,
            "target_unique": python_result.target_unique,
            "conclusion": python_result.conclusion,
        },
        powershell_data=powershell,
        plan_field_name="plan_item_count",
        allow_unparseable_plan_count=True,
    )


def read_active_session_context(
    *,
    active_session_path: Path,
    case_intake_path: Path,
    stable: StableCasesResult,
    log_root: Path,
) -> ActiveSessionInfo:
    session = _read_json_file(active_session_path)
    if not session:
        return ActiveSessionInfo(False, False, None, None, "none", {})
    status = str(session.get("status") or "unknown")
    session_id = _as_text(session.get("session_id"))
    started_at = _as_text(session.get("started_at_utc"))
    active = status == "active"
    reusable: dict[str, str] = {}
    if active and session_id:
        reusable.update(_current_session_intake_addresses(case_intake_path, session_id))
        reusable.update(_batch_after_session_start_addresses(stable=stable, log_root=log_root, started_at_utc=started_at))
    return ActiveSessionInfo(
        detected=True,
        active=active,
        session_id=session_id,
        started_at_utc=started_at,
        status=status,
        reusable_addresses=reusable,
    )


def _queue_records(
    *,
    stable: StableCasesResult,
    active_reuse_allowed: bool,
    session: ActiveSessionInfo,
) -> list[RetestQueueRecord]:
    rows = [row for row in stable.addresses if not row.stable_candidate]
    records: list[RetestQueueRecord] = []
    for row in rows:
        missing = _missing_clean_full_runs(row, stable.min_full_success)
        priority = _retest_priority(row, missing)
        source = session.reusable_addresses.get(row.known_true_addr.upper(), "-") if active_reuse_allowed else "-"
        active_addr = active_reuse_allowed and source != "-"
        prepare = (
            f'prepare-current-case -KnownTrueAddr "{row.known_true_addr}" -Profile full'
            if active_addr and priority in {"HIGH", "MEDIUM", "LOW"}
            else "-"
        )
        records.append(
            RetestQueueRecord(
                known_true_addr=row.known_true_addr,
                priority=priority,
                full_success_count=row.full_success_count,
                baseline_eligible_count=row.baseline_eligible_count,
                quick_success_count=row.quick_success_count,
                latest_batch=row.latest_full_batch,
                latest_classification=row.latest_classification,
                latest_rank_AWB=row.latest_rank_AWB,
                latest_stable_rank=row.latest_stable_rank,
                missing_clean_full_runs=missing,
                rejection_reasons=row.rejection_reasons,
                recommended_action=_retest_action(priority, missing, active_reuse_allowed, active_addr),
                active_session_addr=active_addr,
                active_session_source=source,
                active_session_prepare=prepare,
            )
        )
    return records


def _sample_plan_records(
    *,
    queue: RetestQueueResult,
    needed: int,
    active_session_requested: bool,
) -> list[SamplePlanRecord]:
    if needed <= 0:
        return []

    records: list[SamplePlanRecord] = []
    active_rows = [row for row in queue.records if row.active_session_addr and row.priority != "BLOCKED"]
    for row in active_rows:
        records.append(
            SamplePlanRecord(
                known_true_addr=row.known_true_addr,
                plan_type="active_session_reuse",
                priority=row.priority,
                reason="Current active-session evidence exists for this known_true_addr.",
                command_hint=row.active_session_prepare,
            )
        )

    for row in queue.records:
        if len(records) >= queue.limit:
            break
        if row.priority == "BLOCKED" or row.active_session_addr:
            continue
        records.append(
            SamplePlanRecord(
                known_true_addr=row.known_true_addr,
                plan_type="retest_existing",
                priority=row.priority,
                reason="Historical evidence suggests this address is close to stable, but it must be re-verified in the current session.",
                command_hint="Manually verify this address in the current session before any prepare command.",
            )
        )

    while len(records) < min(queue.limit, needed):
        records.append(
            SamplePlanRecord(
                known_true_addr="-",
                plan_type="collect_new_distinct",
                priority="MEDIUM" if records else "HIGH",
                reason="Additional distinct current-session known_true_addr evidence is needed.",
                command_hint=(
                    "Start an active session and manually verify a new current-session known_true_addr."
                    if not active_session_requested
                    else "Manually verify a new current-session known_true_addr before preparing the case."
                ),
            )
        )
    return records


def _missing_clean_full_runs(row: StableCaseAddressRecord, min_full_success: int) -> int:
    missing = max(min_full_success - row.full_success_count, min_full_success - row.baseline_eligible_count)
    return max(missing, 0)


def _retest_priority(row: StableCaseAddressRecord, missing: int) -> str:
    reasons = row.rejection_reasons
    if any(reason in BLOCKED_REASONS for reason in reasons):
        return "BLOCKED"
    if "has_execution_batch" in reasons:
        return "LOW"
    if _only_clean_count_reasons(reasons) and missing <= 1:
        return "HIGH"
    if _only_clean_count_reasons(reasons) and missing > 1:
        return "MEDIUM"
    if row.total_cases >= 5:
        return "LOW"
    return "MEDIUM"


def _only_clean_count_reasons(reasons: list[str]) -> bool:
    return bool(reasons) and all(reason in CLEAN_COUNT_REASONS for reason in reasons)


def _retest_action(priority: str, missing: int, active_session_confirmed: bool, current_session_addr: bool) -> str:
    if active_session_confirmed and not current_session_addr:
        return "Historical address only unless manually re-verified in the current session."
    if priority == "HIGH":
        if active_session_confirmed and current_session_addr:
            return "Reuse this active-session addr for 1 more full detect-only baseline-eligible run."
        return "If the same manual test session is still active, rerun this addr once; otherwise collect a new distinct current-session addr."
    if priority == "MEDIUM":
        return "Collect more full clean confirmations; reuse only if the same active session is still valid."
    if priority == "LOW":
        if active_session_confirmed and current_session_addr:
            return "Reuse only if additional active-session stability confirmation is needed."
        return "Collect a new current-session addr; keep this addr only as historical evidence unless the same session is still active."
    if priority == "BLOCKED":
        return "Use as diagnostic evidence first; do not reuse until issue is understood."
    return "Review this address before scheduling retest."


def _retest_conclusion(*, stable_count: int, target_unique: int, queue_size: int) -> str:
    if stable_count >= target_unique:
        return "RETEST_QUEUE_OK"
    if queue_size > 0:
        return "NEED_MORE_CANDIDATES"
    return "INSUFFICIENT_DATA"


def _retest_recommendation(conclusion: str, high_count: int, medium_count: int, blocked_count: int) -> str:
    if conclusion == "RETEST_QUEUE_OK":
        return "Stable candidate coverage is sufficient."
    if high_count > 0:
        return "Prioritize HIGH retest rows after current-session verification."
    if medium_count > 0:
        return "Collect more distinct current-session clean runs."
    if blocked_count > 0:
        return "Inspect BLOCKED rows before using them for baseline planning."
    return "Collect additional current-session samples."


def _sample_plan_recommendation(conclusion: str) -> str:
    if conclusion == "SAMPLE_PLAN_READY":
        return "Stable candidate coverage is sufficient."
    if conclusion == "SAMPLE_PLAN_NO_ACTIVE_SESSION":
        return "Start an active manual test session before reusing any known_true_addr."
    if conclusion == "INSUFFICIENT_DATA":
        return "Collect full detect-only logs before planning samples."
    return "Collect current-session samples; historical addresses require manual re-verification."


def _current_session_intake_addresses(path: Path, session_id: str) -> dict[str, str]:
    if not path.exists():
        return {}
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    closed = {
        str(event.get("intake_id"))
        for event in events
        if event.get("event_type") in {"completed", "abandoned"} and event.get("intake_id")
    }
    reusable: dict[str, str] = {}
    for event in events:
        if event.get("session_id") != session_id:
            continue
        if event.get("event_type") == "abandoned":
            continue
        if event.get("event_type") == "prepared" and str(event.get("intake_id")) in closed:
            continue
        if event.get("event_type") not in {"prepared", "completed"}:
            continue
        addr = _as_text(event.get("known_true_addr"))
        if not addr:
            continue
        reusable[addr.upper()] = f"intake_{event.get('event_type')}"
    return reusable


def _batch_after_session_start_addresses(
    *,
    stable: StableCasesResult,
    log_root: Path,
    started_at_utc: str | None,
) -> dict[str, str]:
    started = _parse_utc_timestamp(started_at_utc)
    if started is None:
        return {}
    reusable: dict[str, str] = {}
    for row in stable.addresses:
        batch_id = row.latest_full_batch
        if not re.fullmatch(r"\d{8}-\d{6}", batch_id or ""):
            continue
        summary = log_root / f"{batch_id}__summary.txt"
        if not summary.exists():
            continue
        modified = datetime.fromtimestamp(summary.stat().st_mtime, tz=timezone.utc)
        if modified >= started:
            reusable[row.known_true_addr.upper()] = "batch_after_session_start"
    return reusable


def _read_json_file(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {"status": "invalid"}
    return data if isinstance(data, dict) else {"status": "invalid"}


def _parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        text = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _as_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text not in {"-", "nil", "None"} else None


def _reverse_batch_sort_key(batch_id: str) -> str:
    return "" if batch_id == "-" else "".join(chr(255 - ord(char)) for char in batch_id)


def _run_powershell_planner(
    *,
    command_name: str,
    latest: int,
    profile: str,
    target_unique: int,
    min_full_success: int,
    limit: int,
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
        command_name,
        "-Latest",
        str(latest),
        "-Profile",
        profile,
        "-MinFullSuccess",
        str(min_full_success),
        "-TargetUnique",
        str(target_unique),
        "-Limit",
        str(limit),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=180)
    except FileNotFoundError as exc:
        raise LogParseError("PowerShell executable was not found for planner parity") from exc
    except subprocess.TimeoutExpired as exc:
        raise LogParseError(f"PowerShell {command_name} parity check timed out") from exc
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        detail = f": {message}" if message else ""
        raise LogParseError(f"PowerShell {command_name} failed with exit code {completed.returncode}{detail}")
    return _parse_powershell_planner(completed.stdout)


def _parse_powershell_planner(text: str) -> dict[str, object | None]:
    field_map = {
        "target unique": "target_unique",
        "stable candidate count": "stable_candidate_count",
        "high priority retest count": "high_priority_count",
        "medium priority retest count": "medium_priority_count",
        "low priority retest count": "low_priority_count",
        "blocked address count": "blocked_count",
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
    if all(key in parsed for key in ("high_priority_count", "medium_priority_count", "low_priority_count", "blocked_count")):
        parsed["queue_size"] = sum(
            int(parsed[key] or 0)
            for key in ("high_priority_count", "medium_priority_count", "low_priority_count", "blocked_count")
        )
    if "conclusion" in parsed:
        parsed["normalized_retest_conclusion"] = _normalize_powershell_retest_conclusion(str(parsed["conclusion"]))
        parsed["normalized_sample_conclusion"] = _normalize_powershell_sample_conclusion(str(parsed["conclusion"]))
    return parsed


def _compare_planner_fields(
    *,
    python_data: dict[str, object | None],
    powershell_data: dict[str, object | None],
    plan_field_name: str,
    allow_unparseable_plan_count: bool = False,
) -> PlanningParityResult:
    fields = [plan_field_name, "stable_candidate_count", "target_unique", "conclusion"]
    mismatches: list[PlanningMismatch] = []
    for field in fields:
        ps_field = field
        right = powershell_data.get(ps_field)
        if field == "plan_item_count":
            right = powershell_data.get("plan_item_count")
            if right is None:
                if allow_unparseable_plan_count:
                    mismatches.append(
                        PlanningMismatch(
                            field=field,
                            python_value=python_data.get(field),
                            powershell_value=None,
                            status="WARN",
                        )
                    )
                    continue
                right = powershell_data.get("queue_size")
        if field == "conclusion":
            right = (
                powershell_data.get("normalized_sample_conclusion")
                if plan_field_name == "plan_item_count"
                else powershell_data.get("normalized_retest_conclusion")
            )
        left = _normalize_parity_value(python_data.get(field))
        right = _normalize_parity_value(right)
        if left != right:
            mismatches.append(PlanningMismatch(field=field, python_value=left, powershell_value=right))
    has_fail = any(mismatch.status == "FAIL" for mismatch in mismatches)
    has_warn = any(mismatch.status == "WARN" for mismatch in mismatches)
    status = "FAIL" if has_fail else ("WARN" if has_warn else "PASS")
    return PlanningParityResult(parity_status=status, mismatch_count=len(mismatches), mismatches=mismatches)


def _normalize_powershell_retest_conclusion(value: str) -> str:
    if value == "READY_FOR_BASELINE":
        return "RETEST_QUEUE_OK"
    if value in {"COLLECT_HIGH_PRIORITY_RETESTS", "COLLECT_MORE_DISTINCT_CASES", "INSPECT_BLOCKED_CASES"}:
        return "NEED_MORE_CANDIDATES"
    return value


def _normalize_powershell_sample_conclusion(value: str) -> str:
    if value == "READY_FOR_BASELINE":
        return "SAMPLE_PLAN_READY"
    if value in {"COLLECT_HIGH_PRIORITY_RETESTS", "COLLECT_MORE_DISTINCT_CASES", "INSPECT_BLOCKED_CASES"}:
        return "SAMPLE_PLAN_NEEDS_COLLECTION"
    return value


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
