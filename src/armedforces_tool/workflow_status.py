from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .logs import LogParseError
from .safety import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_PROJECT_ROOT,
    DEFAULT_SESSION_TOOL_PATH,
    analyze_safety_plan,
    analyze_safety_status,
)

DEFAULT_CASE_INTAKE_PATH = DEFAULT_PROJECT_ROOT / "log" / "case_intake.local.jsonl"
DEFAULT_ACTIVE_SESSION_PATH = DEFAULT_PROJECT_ROOT / "log" / "active_test_session.local.json"
DEFAULT_SESSION_HISTORY_PATH = DEFAULT_PROJECT_ROOT / "log" / "test_session_history.local.jsonl"


@dataclass(frozen=True)
class DiagnosticStatusResult:
    project_root: str
    config_path: str
    config_exists: bool
    diagnostic_level: str
    diagnostic_status: str
    validation_profile: object | None
    execution_enabled: bool
    write_enabled: bool
    safety_state: str
    next_run_type: str
    recommendation: str

    def to_dict(self) -> dict[str, object | None]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class CaseIntakeRecord:
    intake_id: str | None
    action: str
    status: str
    known_true_addr: str | None
    profile: str | None
    batch_id: str | None
    timestamp: str | None
    reason: str | None
    is_open: bool
    active_session_related: bool

    def to_dict(self) -> dict[str, object | None]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class CaseIntakeStatusResult:
    project_root: str
    intake_journal_path: str
    intake_journal_exists: bool
    active_session_file_exists: bool
    active_session_detected: bool
    active_session_id: str | None
    active_session_label: str | None
    active_session_started_at: str | None
    prepared_count: int
    completed_count: int
    abandoned_count: int
    open_count: int
    latest_prepared_intake_id: str | None
    latest_completed_intake_id: str | None
    latest_abandoned_intake_id: str | None
    latest_completed_batch_id: str | None
    latest_known_true_addr: str | None
    invalid_json_line_count: int
    conclusion: str
    recommendation: str
    records: list[CaseIntakeRecord]

    def to_dict(self) -> dict[str, object | None]:
        return {
            "project_root": self.project_root,
            "intake_journal_path": self.intake_journal_path,
            "intake_journal_exists": self.intake_journal_exists,
            "active_session_file_exists": self.active_session_file_exists,
            "active_session_detected": self.active_session_detected,
            "active_session_id": self.active_session_id,
            "active_session_label": self.active_session_label,
            "active_session_started_at": self.active_session_started_at,
            "prepared_count": self.prepared_count,
            "completed_count": self.completed_count,
            "abandoned_count": self.abandoned_count,
            "open_count": self.open_count,
            "latest_prepared_intake_id": self.latest_prepared_intake_id,
            "latest_completed_intake_id": self.latest_completed_intake_id,
            "latest_abandoned_intake_id": self.latest_abandoned_intake_id,
            "latest_completed_batch_id": self.latest_completed_batch_id,
            "latest_known_true_addr": self.latest_known_true_addr,
            "invalid_json_line_count": self.invalid_json_line_count,
            "conclusion": self.conclusion,
            "recommendation": self.recommendation,
            "records": [record.to_dict() for record in self.records],
        }


@dataclass(frozen=True)
class WorkflowStatusMismatch:
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
class WorkflowStatusParityResult:
    parity_status: str
    mismatch_count: int
    mismatches: list[WorkflowStatusMismatch]
    unparseable_fields: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "parity_status": self.parity_status,
            "mismatch_count": self.mismatch_count,
            "mismatches": [mismatch.to_dict() for mismatch in self.mismatches],
            "unparseable_fields": self.unparseable_fields,
        }


def analyze_diagnostic_status(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> DiagnosticStatusResult:
    status = analyze_safety_status(project_root=project_root, config_path=config_path)
    plan = analyze_safety_plan(project_root=project_root, config_path=config_path)
    level = _normalize_diagnostic_level(status.diagnostic_level)
    diagnostic_status = _diagnostic_status(level, status.config_exists)
    recommendation = _diagnostic_recommendation(
        diagnostic_status=diagnostic_status,
        safety_state=status.safety_state,
        write_enabled=status.write_enabled,
        execution_enabled=status.execution_enabled,
    )
    return DiagnosticStatusResult(
        project_root=str(project_root),
        config_path=str(config_path),
        config_exists=status.config_exists,
        diagnostic_level=level,
        diagnostic_status=diagnostic_status,
        validation_profile=status.validation_profile,
        execution_enabled=status.execution_enabled,
        write_enabled=status.write_enabled,
        safety_state=status.safety_state,
        next_run_type=plan.next_run_type,
        recommendation=recommendation,
    )


def analyze_case_intake_status(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    intake_journal: Path = DEFAULT_CASE_INTAKE_PATH,
    session_file: Path = DEFAULT_ACTIVE_SESSION_PATH,
    session_history: Path = DEFAULT_SESSION_HISTORY_PATH,
    limit: int = 20,
) -> CaseIntakeStatusResult:
    if limit < 1:
        raise LogParseError("--limit must be greater than 0")

    session = _read_json_object(session_file)
    active_session_file_exists = session_file.exists()
    active_session_detected = bool(session and session.get("status") == "active")
    active_session_id = _as_text(session.get("session_id") if session else None)
    active_session_label = _as_text(session.get("label") if session else None)
    active_session_started = _as_text(session.get("started_at_utc") if session else None)
    _ = session_history.exists()  # Read-only path existence is intentionally harmless for future extension.

    events, invalid_lines = _read_intake_events(intake_journal)
    prepared_events = [event for event in events if event.get("event_type") == "prepared"]
    completed_events = [event for event in events if event.get("event_type") == "completed"]
    abandoned_events = [event for event in events if event.get("event_type") == "abandoned"]
    closed_ids = {
        str(event.get("intake_id"))
        for event in completed_events + abandoned_events
        if _present(event.get("intake_id"))
    }
    open_ids = {
        str(event.get("intake_id"))
        for event in prepared_events
        if _present(event.get("intake_id")) and str(event.get("intake_id")) not in closed_ids
    }

    latest_prepared = _last_event(prepared_events)
    latest_completed = _last_event(completed_events)
    latest_abandoned = _last_event(abandoned_events)
    latest_known = _last_value(events, "known_true_addr")
    records = [
        _event_to_record(
            event,
            open_ids=open_ids,
            active_session_id=active_session_id if active_session_detected else None,
        )
        for event in events[-limit:]
    ]
    conclusion = _intake_conclusion(
        journal_exists=intake_journal.exists(),
        open_count=len(open_ids),
        invalid_json_line_count=invalid_lines,
    )
    return CaseIntakeStatusResult(
        project_root=str(project_root),
        intake_journal_path=str(intake_journal),
        intake_journal_exists=intake_journal.exists(),
        active_session_file_exists=active_session_file_exists,
        active_session_detected=active_session_detected,
        active_session_id=active_session_id,
        active_session_label=active_session_label,
        active_session_started_at=active_session_started,
        prepared_count=len(prepared_events),
        completed_count=len(completed_events),
        abandoned_count=len(abandoned_events),
        open_count=len(open_ids),
        latest_prepared_intake_id=_as_text(latest_prepared.get("intake_id") if latest_prepared else None),
        latest_completed_intake_id=_as_text(latest_completed.get("intake_id") if latest_completed else None),
        latest_abandoned_intake_id=_as_text(latest_abandoned.get("intake_id") if latest_abandoned else None),
        latest_completed_batch_id=_as_text(latest_completed.get("batch_id") if latest_completed else None),
        latest_known_true_addr=latest_known,
        invalid_json_line_count=invalid_lines,
        conclusion=conclusion,
        recommendation=_intake_recommendation(conclusion),
        records=records,
    )


def diagnostic_status_parity(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    config_path: Path = DEFAULT_CONFIG_PATH,
    session_tool_path: Path = DEFAULT_SESSION_TOOL_PATH,
) -> WorkflowStatusParityResult:
    python_status = analyze_diagnostic_status(project_root=project_root, config_path=config_path)
    powershell = _run_powershell_command("diagnostic-status", session_tool_path)
    parsed = _parse_field_value_output(powershell)
    fields = ["diagnostic_level", "validation_profile", "execution_disabled"]
    python_data = {
        "diagnostic_level": python_status.diagnostic_level,
        "validation_profile": python_status.validation_profile,
        "execution_disabled": not python_status.execution_enabled and not python_status.write_enabled,
    }
    powershell_data = {
        "diagnostic_level": parsed.get("current_diagnostic_level"),
        "validation_profile": parsed.get("validation_profile"),
        "execution_disabled": None if "execution_mode" not in parsed else parsed.get("execution_mode") == "disabled",
    }
    return _compare_parity(python_data=python_data, powershell_data=powershell_data, fields=fields)


def case_intake_status_parity(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    intake_journal: Path = DEFAULT_CASE_INTAKE_PATH,
    session_file: Path = DEFAULT_ACTIVE_SESSION_PATH,
    session_history: Path = DEFAULT_SESSION_HISTORY_PATH,
    session_tool_path: Path = DEFAULT_SESSION_TOOL_PATH,
) -> WorkflowStatusParityResult:
    python_status = analyze_case_intake_status(
        project_root=project_root,
        intake_journal=intake_journal,
        session_file=session_file,
        session_history=session_history,
    )
    powershell = _run_powershell_command("case-intake-status", session_tool_path)
    parsed = _parse_field_value_output(powershell)
    fields = [
        "prepared_count",
        "completed_count",
        "abandoned_count",
        "open_count",
        "active_session_detected",
        "latest_completed_batch_id",
    ]
    python_data = {
        "prepared_count": python_status.prepared_count,
        "completed_count": python_status.completed_count,
        "abandoned_count": python_status.abandoned_count,
        "open_count": python_status.open_count,
        "active_session_detected": python_status.active_session_detected,
        "latest_completed_batch_id": python_status.latest_completed_batch_id,
    }
    powershell_data = {
        "prepared_count": parsed.get("prepared_event_count"),
        "completed_count": parsed.get("completed_event_count"),
        "abandoned_count": parsed.get("abandoned_event_count"),
        "open_count": parsed.get("open_prepared_case_count"),
        "active_session_detected": parsed.get("active_session_detected"),
        "latest_completed_batch_id": parsed.get("latest_completed_batch"),
    }
    return _compare_parity(python_data=python_data, powershell_data=powershell_data, fields=fields)


def _normalize_diagnostic_level(value: object | None) -> str:
    if value is None:
        return "unknown"
    text = str(value).strip().lower()
    return text if text in {"basic", "debug", "trace"} else "unknown"


def _diagnostic_status(level: str, config_exists: bool) -> str:
    if not config_exists:
        return "CONFIG_MISSING"
    if level == "basic":
        return "DIAGNOSTIC_BASIC"
    if level == "debug":
        return "DIAGNOSTIC_DEBUG"
    if level == "trace":
        return "DIAGNOSTIC_TRACE"
    return "CONFIG_WARN"


def _diagnostic_recommendation(
    *,
    diagnostic_status: str,
    safety_state: str,
    execution_enabled: bool,
    write_enabled: bool,
) -> str:
    if safety_state in {"WRITE_ARMED", "EXECUTION_DANGER"} or execution_enabled or write_enabled:
        return "Execution/write-capable config detected; run safe-reset before normal diagnostics."
    if diagnostic_status == "DIAGNOSTIC_BASIC":
        return "OK for daily runs."
    if diagnostic_status == "DIAGNOSTIC_DEBUG":
        return "Use debug only for targeted investigation; reset to basic afterward."
    if diagnostic_status == "DIAGNOSTIC_TRACE":
        return "Trace logs can be large; reset to basic after diagnosis."
    if diagnostic_status == "CONFIG_MISSING":
        return "Local config is missing; create or show config before running CE."
    return "Diagnostic level is unknown; set basic/debug/trace intentionally."


def _read_intake_events(path: Path) -> tuple[list[dict[str, object | None]], int]:
    if not path.exists():
        return [], 0
    events: list[dict[str, object | None]] = []
    invalid = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.lstrip("\ufeff")
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            continue
        if isinstance(event, dict):
            events.append(event)
        else:
            invalid += 1
    return events, invalid


def _read_json_object(path: Path) -> dict[str, object | None] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff"))
    except json.JSONDecodeError:
        return {"status": "invalid"}
    return data if isinstance(data, dict) else {"status": "invalid"}


def _event_to_record(
    event: dict[str, object | None],
    *,
    open_ids: set[str],
    active_session_id: str | None,
) -> CaseIntakeRecord:
    intake_id = _as_text(event.get("intake_id"))
    action = _as_text(event.get("event_type")) or "unknown"
    is_open = bool(intake_id and intake_id in open_ids and action == "prepared")
    return CaseIntakeRecord(
        intake_id=intake_id,
        action=action,
        status="open" if is_open else action,
        known_true_addr=_as_text(event.get("known_true_addr")),
        profile=_as_text(event.get("profile")),
        batch_id=_as_text(event.get("batch_id")),
        timestamp=_event_timestamp(event),
        reason=_as_text(event.get("reason")),
        is_open=is_open,
        active_session_related=bool(active_session_id and _as_text(event.get("session_id")) == active_session_id),
    )


def _event_timestamp(event: dict[str, object | None]) -> str | None:
    for key in ("prepared_at_utc", "completed_at_utc", "abandoned_at_utc", "recorded_at_utc"):
        value = _as_text(event.get(key))
        if value:
            return value
    return None


def _last_event(events: list[dict[str, object | None]]) -> dict[str, object | None] | None:
    return events[-1] if events else None


def _last_value(events: list[dict[str, object | None]], key: str) -> str | None:
    for event in reversed(events):
        value = _as_text(event.get(key))
        if value:
            return value
    return None


def _intake_conclusion(*, journal_exists: bool, open_count: int, invalid_json_line_count: int) -> str:
    if not journal_exists:
        return "CASE_INTAKE_NO_JOURNAL"
    if invalid_json_line_count:
        return "CASE_INTAKE_WARN"
    if open_count:
        return "CASE_INTAKE_OPEN_ITEMS"
    return "CASE_INTAKE_CLEAN"


def _intake_recommendation(conclusion: str) -> str:
    if conclusion == "CASE_INTAKE_CLEAN":
        return "No open prepared intake items."
    if conclusion == "CASE_INTAKE_OPEN_ITEMS":
        return "Run post-current-case after CE, or abandon the prepared case if CE was not run."
    if conclusion == "CASE_INTAKE_NO_JOURNAL":
        return "No local intake journal exists yet."
    if conclusion == "CASE_INTAKE_WARN":
        return "Inspect invalid local intake journal lines."
    return "Review local intake state."


def _run_powershell_command(command_name: str, session_tool_path: Path) -> str:
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
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=180)
    except FileNotFoundError as exc:
        raise LogParseError("PowerShell executable was not found for status parity") from exc
    except subprocess.TimeoutExpired as exc:
        raise LogParseError(f"PowerShell {command_name} parity check timed out") from exc
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        detail = f": {message}" if message else ""
        raise LogParseError(f"PowerShell {command_name} failed with exit code {completed.returncode}{detail}")
    return completed.stdout


def _parse_field_value_output(text: str) -> dict[str, object | None]:
    parsed: dict[str, object | None] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("-"):
            continue
        parts = re.split(r"\s{2,}", line, maxsplit=1)
        if len(parts) != 2:
            continue
        key = _normalize_key(parts[0])
        if key in {"field", "check"}:
            continue
        parsed[key] = _parse_scalar(parts[1])
    return parsed


def _compare_parity(
    *,
    python_data: dict[str, object | None],
    powershell_data: dict[str, object | None],
    fields: list[str],
) -> WorkflowStatusParityResult:
    mismatches: list[WorkflowStatusMismatch] = []
    unparseable: list[str] = []
    for field in fields:
        left = _normalize_parity_value(python_data.get(field))
        if field not in powershell_data or powershell_data.get(field) is None:
            unparseable.append(field)
            mismatches.append(WorkflowStatusMismatch(field, left, None, status="WARN"))
            continue
        right = _normalize_parity_value(powershell_data.get(field))
        if left != right:
            mismatches.append(WorkflowStatusMismatch(field, left, right))
    has_fail = any(mismatch.status == "FAIL" for mismatch in mismatches)
    has_warn = any(mismatch.status == "WARN" for mismatch in mismatches)
    status = "FAIL" if has_fail else ("WARN" if has_warn else "PASS")
    return WorkflowStatusParityResult(
        parity_status=status,
        mismatch_count=len(mismatches),
        mismatches=mismatches,
        unparseable_fields=unparseable,
    )


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _parse_scalar(value: str) -> object | None:
    text = value.strip()
    if text in {"", "-", "nil", "None"}:
        return None
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def _normalize_parity_value(value: object | None) -> object | None:
    if value in {"", "-", "nil", "None"}:
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        return value.strip()
    return value


def _as_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text not in {"-", "nil", "None"} else None


def _present(value: object | None) -> bool:
    return _as_text(value) is not None
