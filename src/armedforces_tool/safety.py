from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from .case_summary import DEFAULT_BASELINE_PATH, analyze_case_summary
from .logs import DEFAULT_LOG_ROOT, LogParseError, parse_latest_summaries

DEFAULT_PROJECT_ROOT = Path(r"D:\armedforces.io-v2")
DEFAULT_CONFIG_PATH = DEFAULT_PROJECT_ROOT / "src" / "run_case_config.local.lua"
DEFAULT_SESSION_TOOL_PATH = DEFAULT_PROJECT_ROOT / "src" / "test_session_tool.ps1"
DEFAULT_PROTECTED_LOCAL_FILES = (
    Path("src/run_case_config.local.lua"),
    Path("src/run_case_config.local.lua.bak"),
    Path("log/active_test_session.local.json"),
    Path("log/case_intake.local.jsonl"),
    Path("log/test_session_history.local.jsonl"),
)

EXECUTION_CONFIRM_VALUE = "I_ACCEPT_WRITE_TO_LIVE_MEMORY"


@dataclass(frozen=True)
class LuaConfig:
    path: str
    exists: bool
    raw_fields: dict[str, object | None]

    def to_dict(self) -> dict[str, object | None]:
        return {
            "path": self.path,
            "exists": self.exists,
            "raw_fields": self.raw_fields,
        }


@dataclass(frozen=True)
class SafetyStatusResult:
    project_root: str
    config_path: str
    config_exists: bool
    validation_profile: object | None
    diagnostic_level: object | None
    known_true_addr: object | None
    target_value_float: object | None
    target_value_pattern: object | None
    write_value_float: object | None
    execution_mode: str | None
    execution_enabled: bool
    write_enabled: bool
    execution_confirm: object | None
    execution_confirm_present: bool
    execution_write_request_id: object | None
    execution_armed_at_utc: object | None
    execution_arm_expires_at_utc: object | None
    execution_arm_present: bool
    execution_arm_state: str
    safety_state: str
    recommendation: str

    def to_dict(self) -> dict[str, object | None]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class SafetyPlanResult:
    project_root: str
    config_path: str
    config_exists: bool
    next_run_type: str
    danger_level: str
    reason: str
    recommendation: str
    validation_profile: object | None
    diagnostic_level: object | None
    target_value_float: object | None
    target_value_pattern: object | None
    execution_mode: str | None
    write_enabled: bool
    execution_confirm_present: bool
    execution_write_request_id: object | None
    execution_arm_state: str
    restore_source_batch_id: object | None
    restore_source_batch_execution_addr: object | None
    key_config_fields: dict[str, object | None]

    def to_dict(self) -> dict[str, object | None]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class SafetyExecutionStatusResult:
    project_root: str
    config_path: str
    config_exists: bool
    execution_enabled: bool
    write_enabled: bool
    execution_mode: str | None
    execution_confirm: object | None
    execution_confirm_present: bool
    execution_write_request_id: object | None
    execution_armed_at_utc: object | None
    execution_arm_expires_at_utc: object | None
    arm_state: str
    arm_seconds_remaining: int | None
    restore_source_batch_execution_addr: object | None
    recommendation: str

    def to_dict(self) -> dict[str, object | None]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class SafetyParityMismatch:
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
class SafetyParityResult:
    parity_status: str
    mismatch_count: int
    mismatches: list[SafetyParityMismatch]
    unparseable_fields: list[str] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "parity_status": self.parity_status,
            "mismatch_count": self.mismatch_count,
            "mismatches": [mismatch.to_dict() for mismatch in self.mismatches],
            "unparseable_fields": self.unparseable_fields or [],
        }


@dataclass(frozen=True)
class SafetyDoctorCheck:
    check_name: str
    status: str
    detail: str
    recommendation: str

    def to_dict(self) -> dict[str, object]:
        return {
            "check_name": self.check_name,
            "status": self.status,
            "detail": self.detail,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class SafetyDoctorResult:
    project_root: str
    overall_status: str
    safety_state: str
    next_run_type: str
    danger_level: str
    arm_state: str
    config_exists: bool
    log_root_exists: bool
    latest_log_available: bool
    baseline_exists: bool
    python_tooling_available: bool
    protected_local_files_present: int
    warning_count: int
    danger_count: int
    recommendation: str
    checks: list[SafetyDoctorCheck]

    def to_dict(self) -> dict[str, object]:
        return {
            "project_root": self.project_root,
            "overall_status": self.overall_status,
            "safety_state": self.safety_state,
            "next_run_type": self.next_run_type,
            "danger_level": self.danger_level,
            "arm_state": self.arm_state,
            "config_exists": self.config_exists,
            "log_root_exists": self.log_root_exists,
            "latest_log_available": self.latest_log_available,
            "baseline_exists": self.baseline_exists,
            "python_tooling_available": self.python_tooling_available,
            "protected_local_files_present": self.protected_local_files_present,
            "warning_count": self.warning_count,
            "danger_count": self.danger_count,
            "recommendation": self.recommendation,
            "checks": [check.to_dict() for check in self.checks],
        }


def parse_lua_config(path: Path) -> LuaConfig:
    if not path.exists():
        return LuaConfig(path=str(path), exists=False, raw_fields={})
    if not path.is_file():
        raise LogParseError(f"config path is not a file: {path}")

    raw_fields: dict[str, object | None] = {}
    text = path.read_text(encoding="utf-8", errors="replace")
    for raw_line in text.splitlines():
        line = _strip_lua_comment(raw_line).strip()
        if not line or line in {"return {", "{", "}"}:
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*,?\s*$", line)
        if not match:
            continue
        raw_fields[match.group(1)] = _parse_lua_value(match.group(2).strip())
    return LuaConfig(path=str(path), exists=True, raw_fields=raw_fields)


def analyze_safety_status(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    config_path: Path = DEFAULT_CONFIG_PATH,
    now: datetime | None = None,
) -> SafetyStatusResult:
    config = parse_lua_config(config_path)
    fields = config.raw_fields
    current_time = _utc_now(now)
    mode = _normalized_mode(fields.get("execution_mode"))
    write_enabled = _as_bool(fields.get("write_enabled"))
    execution_enabled = _derive_execution_enabled(fields)
    confirm = fields.get("execution_confirm")
    confirm_present = _present(confirm)
    arm_state, seconds_remaining = _arm_state(fields, current_time)
    arm_present = _arm_present(fields)
    write_capable = _write_capable(fields)

    if not config.exists:
        safety_state = "SAFE_NO_CONFIG"
    elif write_capable:
        if mode == "write" and write_enabled and confirm == EXECUTION_CONFIRM_VALUE and arm_state == "armed":
            safety_state = "WRITE_ARMED"
        else:
            safety_state = "EXECUTION_DANGER"
    elif mode == "dry_run":
        safety_state = "CONFIG_WARN"
    elif mode in {None, "", "disabled"}:
        safety_state = "SAFE_DETECT_ONLY"
    else:
        safety_state = "UNKNOWN"

    return SafetyStatusResult(
        project_root=str(project_root),
        config_path=str(config_path),
        config_exists=config.exists,
        validation_profile=fields.get("validation_profile"),
        diagnostic_level=fields.get("diagnostic_level"),
        known_true_addr=fields.get("known_true_addr"),
        target_value_float=fields.get("target_value_float"),
        target_value_pattern=fields.get("target_value_pattern"),
        write_value_float=fields.get("write_value_float"),
        execution_mode=mode,
        execution_enabled=execution_enabled,
        write_enabled=write_enabled,
        execution_confirm=confirm,
        execution_confirm_present=confirm_present,
        execution_write_request_id=fields.get("execution_write_request_id"),
        execution_armed_at_utc=fields.get("execution_armed_at_utc"),
        execution_arm_expires_at_utc=fields.get("execution_arm_expires_at_utc"),
        execution_arm_present=arm_present,
        execution_arm_state=arm_state,
        safety_state=safety_state,
        recommendation=_status_recommendation(safety_state, seconds_remaining),
    )


def analyze_safety_plan(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    config_path: Path = DEFAULT_CONFIG_PATH,
    now: datetime | None = None,
) -> SafetyPlanResult:
    config = parse_lua_config(config_path)
    fields = config.raw_fields
    current_time = _utc_now(now)
    mode = _normalized_mode(fields.get("execution_mode"))
    write_enabled = _as_bool(fields.get("write_enabled"))
    confirm_present = _present(fields.get("execution_confirm"))
    arm_state, _ = _arm_state(fields, current_time)
    restore_source_batch_id = fields.get("restore_source_batch_id")
    restore_addr = _restore_source_addr(fields)

    if not config.exists:
        next_run_type = "unknown"
        danger_level = "UNKNOWN"
        reason = "local config is missing"
    elif mode == "dry_run":
        next_run_type = "dry_run"
        danger_level = "WARN"
        reason = "execution_mode is dry_run"
    elif mode == "write" or write_enabled or confirm_present or _arm_present(fields):
        next_run_type = "restore_attempt" if _present(restore_source_batch_id) or _present(restore_addr) else "write_attempt"
        danger_level = "DANGER"
        reason = "write-capable execution fields are present"
    elif mode in {None, "", "disabled"}:
        next_run_type = "detect_only"
        danger_level = "SAFE"
        reason = "execution is disabled and no write-capable fields are present"
    else:
        next_run_type = "unknown"
        danger_level = "UNKNOWN"
        reason = f"unrecognized execution_mode: {mode}"

    key_fields = {
        "validation_profile": fields.get("validation_profile"),
        "diagnostic_level": fields.get("diagnostic_level"),
        "target_value_float": fields.get("target_value_float"),
        "target_value_pattern": fields.get("target_value_pattern"),
        "execution_mode": mode,
        "write_enabled": write_enabled,
        "execution_confirm_present": confirm_present,
        "execution_write_request_id": fields.get("execution_write_request_id"),
        "execution_arm_state": arm_state,
        "restore_source_batch_id": restore_source_batch_id,
        "restore_source_batch_execution_addr": restore_addr,
    }
    return SafetyPlanResult(
        project_root=str(project_root),
        config_path=str(config_path),
        config_exists=config.exists,
        next_run_type=next_run_type,
        danger_level=danger_level,
        reason=reason,
        recommendation=_plan_recommendation(next_run_type, danger_level, arm_state),
        validation_profile=fields.get("validation_profile"),
        diagnostic_level=fields.get("diagnostic_level"),
        target_value_float=fields.get("target_value_float"),
        target_value_pattern=fields.get("target_value_pattern"),
        execution_mode=mode,
        write_enabled=write_enabled,
        execution_confirm_present=confirm_present,
        execution_write_request_id=fields.get("execution_write_request_id"),
        execution_arm_state=arm_state,
        restore_source_batch_id=restore_source_batch_id,
        restore_source_batch_execution_addr=restore_addr,
        key_config_fields=key_fields,
    )


def analyze_safety_execution_status(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    config_path: Path = DEFAULT_CONFIG_PATH,
    now: datetime | None = None,
) -> SafetyExecutionStatusResult:
    config = parse_lua_config(config_path)
    fields = config.raw_fields
    current_time = _utc_now(now)
    arm_state, seconds_remaining = _arm_state(fields, current_time)
    mode = _normalized_mode(fields.get("execution_mode"))
    write_enabled = _as_bool(fields.get("write_enabled"))
    confirm = fields.get("execution_confirm")
    confirm_present = _present(confirm)
    return SafetyExecutionStatusResult(
        project_root=str(project_root),
        config_path=str(config_path),
        config_exists=config.exists,
        execution_enabled=_derive_execution_enabled(fields),
        write_enabled=write_enabled,
        execution_mode=mode,
        execution_confirm=confirm,
        execution_confirm_present=confirm_present,
        execution_write_request_id=fields.get("execution_write_request_id"),
        execution_armed_at_utc=fields.get("execution_armed_at_utc"),
        execution_arm_expires_at_utc=fields.get("execution_arm_expires_at_utc"),
        arm_state=arm_state,
        arm_seconds_remaining=seconds_remaining,
        restore_source_batch_execution_addr=_restore_source_addr(fields),
        recommendation=_execution_status_recommendation(mode, write_enabled, confirm_present, arm_state),
    )


def analyze_safety_doctor(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    config_path: Path = DEFAULT_CONFIG_PATH,
    log_root: Path = DEFAULT_LOG_ROOT,
    baseline: Path = DEFAULT_BASELINE_PATH,
    now: datetime | None = None,
) -> SafetyDoctorResult:
    current_time = _utc_now(now)
    protected_paths = [project_root / relative for relative in DEFAULT_PROTECTED_LOCAL_FILES]
    before_hashes = snapshot_protected_files(protected_paths)
    checks: list[SafetyDoctorCheck] = []

    status_result: SafetyStatusResult | None = None
    plan_result: SafetyPlanResult | None = None
    execution_result: SafetyExecutionStatusResult | None = None
    latest_log_available = False
    python_tooling_available = True

    try:
        config = parse_lua_config(config_path)
        checks.append(
            _check(
                "config file",
                "PASS" if config.exists else "WARN",
                f"exists={config.exists}; path={config_path}",
                "Create local config before CE runs." if not config.exists else "No action needed.",
            )
        )
        checks.append(
            _check(
                "config parse",
                "PASS",
                f"parsed_fields={len(config.raw_fields)}",
                "No action needed.",
            )
        )
    except LogParseError as exc:
        python_tooling_available = False
        checks.append(_check("config parse", "FAIL", str(exc), "Fix config path before running CE."))

    try:
        status_result = analyze_safety_status(project_root=project_root, config_path=config_path, now=current_time)
        checks.append(
            _check(
                "safety status state",
                _status_check_status(status_result.safety_state),
                status_result.safety_state,
                status_result.recommendation,
            )
        )
    except LogParseError as exc:
        python_tooling_available = False
        checks.append(_check("safety status state", "FAIL", str(exc), "Fix config before running CE."))

    try:
        plan_result = analyze_safety_plan(project_root=project_root, config_path=config_path, now=current_time)
        checks.append(
            _check(
                "next run plan state",
                _danger_level_to_check(plan_result.danger_level),
                f"next_run_type={plan_result.next_run_type}; danger_level={plan_result.danger_level}",
                plan_result.recommendation,
            )
        )
    except LogParseError as exc:
        python_tooling_available = False
        checks.append(_check("next run plan state", "FAIL", str(exc), "Fix config before running CE."))

    try:
        execution_result = analyze_safety_execution_status(project_root=project_root, config_path=config_path, now=current_time)
        checks.append(
            _check(
                "execution arm / write guard state",
                _execution_check_status(execution_result),
                f"mode={execution_result.execution_mode}; write_enabled={execution_result.write_enabled}; arm_state={execution_result.arm_state}",
                execution_result.recommendation,
            )
        )
    except LogParseError as exc:
        python_tooling_available = False
        checks.append(_check("execution arm / write guard state", "FAIL", str(exc), "Fix config before running CE."))

    log_root_exists = log_root.exists() and log_root.is_dir()
    checks.append(
        _check(
            "log root readable",
            "PASS" if log_root_exists else "WARN",
            f"exists={log_root_exists}; path={log_root}",
            "No action needed." if log_root_exists else "Run CE only when ready to generate logs.",
        )
    )

    try:
        latest_records = parse_latest_summaries(log_root=log_root, latest=1, profile="all")
        latest_log_available = bool(latest_records)
        checks.append(
            _check(
                "latest log parse",
                "PASS" if latest_records else "WARN",
                f"records={len(latest_records)}",
                "No action needed." if latest_records else "No parseable batch summary logs found.",
            )
        )
    except LogParseError as exc:
        python_tooling_available = False
        checks.append(_check("latest log parse", "WARN", str(exc), "Check log root if coverage analysis is needed."))

    baseline_exists = baseline.exists()
    checks.append(
        _check(
            "baseline path",
            "PASS" if baseline_exists else "WARN",
            f"exists={baseline_exists}; path={baseline}",
            "No action needed." if baseline_exists else "Provide a baseline or target unique count for coverage checks.",
        )
    )

    try:
        summary = analyze_case_summary(log_root=log_root, latest=20, profile="full", baseline=baseline)
        checks.append(
            _check(
                "case summary analysis",
                "PASS",
                f"conclusion={summary.conclusion}; eligible={summary.current_eligible_batch_count}",
                summary.recommendation,
            )
        )
    except LogParseError as exc:
        python_tooling_available = False
        checks.append(_check("case summary analysis", "WARN", str(exc), "Case summary unavailable until logs are readable."))

    checks.append(
        _check(
            "python safety internals",
            "PASS" if status_result and plan_result and execution_result else "FAIL",
            "status/plan/execution-status executed internally" if status_result and plan_result and execution_result else "one or more safety internals failed",
            "No action needed." if status_result and plan_result and execution_result else "Inspect failed safety check above.",
        )
    )

    after_hashes = snapshot_protected_files(protected_paths)
    present_count = sum(1 for value in after_hashes.values() if value is not None)
    changed = [
        str(path)
        for path in before_hashes
        if before_hashes.get(path) != after_hashes.get(path)
    ]
    checks.append(
        _check(
            "protected local files present",
            "INFO" if present_count else "WARN",
            f"present={present_count}; checked={len(protected_paths)}",
            "No action needed." if present_count else "Protected local files are optional for read-only doctor.",
        )
    )
    checks.append(
        _check(
            "protected local files unchanged",
            "PASS" if not changed else "FAIL",
            "hashes stable" if not changed else "changed=" + "; ".join(changed),
            "No action needed." if not changed else "Stop and inspect unexpected local file changes.",
        )
    )

    safety_state = status_result.safety_state if status_result else "UNKNOWN"
    next_run_type = plan_result.next_run_type if plan_result else "unknown"
    danger_level = plan_result.danger_level if plan_result else "UNKNOWN"
    arm_state = execution_result.arm_state if execution_result else "unknown"
    config_exists = status_result.config_exists if status_result else config_path.exists()
    warning_count = sum(1 for check in checks if check.status == "WARN")
    danger_count = sum(1 for check in checks if check.status == "FAIL")
    overall = _doctor_overall_status(
        checks=checks,
        safety_state=safety_state,
        danger_level=danger_level,
        arm_state=arm_state,
    )
    return SafetyDoctorResult(
        project_root=str(project_root),
        overall_status=overall,
        safety_state=safety_state,
        next_run_type=next_run_type,
        danger_level=danger_level,
        arm_state=arm_state,
        config_exists=config_exists,
        log_root_exists=log_root_exists,
        latest_log_available=latest_log_available,
        baseline_exists=baseline_exists,
        python_tooling_available=python_tooling_available,
        protected_local_files_present=present_count,
        warning_count=warning_count,
        danger_count=danger_count,
        recommendation=_doctor_recommendation(overall),
        checks=checks,
    )


def safety_status_parity(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    config_path: Path = DEFAULT_CONFIG_PATH,
    session_tool_path: Path = DEFAULT_SESSION_TOOL_PATH,
) -> SafetyParityResult:
    python_status = analyze_safety_status(project_root=project_root, config_path=config_path)
    powershell = _run_powershell_tool("doctor", session_tool_path)
    parsed = _parse_doctor_output(powershell)
    python_conclusion = _status_to_doctor_conclusion(python_status.safety_state)
    mismatches = _compare_fields(
        python_data={"doctor_conclusion": python_conclusion},
        powershell_data={"doctor_conclusion": parsed.get("conclusion")},
        fields=["doctor_conclusion"],
    )
    return _parity_result(mismatches)


def safety_plan_parity(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    config_path: Path = DEFAULT_CONFIG_PATH,
    session_tool_path: Path = DEFAULT_SESSION_TOOL_PATH,
) -> SafetyParityResult:
    python_plan = analyze_safety_plan(project_root=project_root, config_path=config_path)
    powershell = _run_powershell_tool("plan", session_tool_path)
    parsed = _parse_field_value_output(powershell)
    mismatches = _compare_fields(
        python_data={
            "next_run_type": python_plan.next_run_type,
            "danger_level": python_plan.danger_level,
            "execution_mode": python_plan.execution_mode,
            "write_enabled": python_plan.write_enabled,
        },
        powershell_data={
            "next_run_type": parsed.get("next_run_type"),
            "danger_level": parsed.get("danger_level"),
            "execution_mode": parsed.get("execution_mode"),
            "write_enabled": parsed.get("write_enabled"),
        },
        fields=["next_run_type", "danger_level", "execution_mode", "write_enabled"],
    )
    return _parity_result(mismatches)


def safety_execution_status_parity(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    config_path: Path = DEFAULT_CONFIG_PATH,
    session_tool_path: Path = DEFAULT_SESSION_TOOL_PATH,
) -> SafetyParityResult:
    python_status = analyze_safety_execution_status(project_root=project_root, config_path=config_path)
    powershell = _run_powershell_tool("execution-status", session_tool_path)
    parsed = _parse_field_value_output(powershell)
    mismatches = _compare_fields(
        python_data={
            "execution_mode": python_status.execution_mode,
            "write_enabled": python_status.write_enabled,
            "confirm_present": python_status.execution_confirm_present,
            "arm_present": python_status.arm_state in {"armed", "expired", "unknown"},
            "safety_conclusion": _execution_safe_conclusion(python_status),
        },
        powershell_data={
            "execution_mode": parsed.get("current_config_execution_mode"),
            "write_enabled": parsed.get("current_config_write_enabled"),
            "confirm_present": parsed.get("current_config_confirm_present"),
            "arm_present": parsed.get("current_config_arm_present"),
            "safety_conclusion": _normalize_execution_safety(parsed.get("safety_conclusion")),
        },
        fields=["execution_mode", "write_enabled", "confirm_present", "arm_present", "safety_conclusion"],
    )
    return _parity_result(mismatches)


def safety_doctor_parity(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    config_path: Path = DEFAULT_CONFIG_PATH,
    log_root: Path = DEFAULT_LOG_ROOT,
    baseline: Path = DEFAULT_BASELINE_PATH,
    session_tool_path: Path = DEFAULT_SESSION_TOOL_PATH,
) -> SafetyParityResult:
    python_doctor = analyze_safety_doctor(
        project_root=project_root,
        config_path=config_path,
        log_root=log_root,
        baseline=baseline,
    )
    powershell = _run_powershell_tool("doctor", session_tool_path)
    parsed = _parse_doctor_for_parity(powershell)
    python_next_risk = "detect_only" if python_doctor.next_run_type == "detect_only" else "write_risk"
    fields = ["overall_level", "execution_enabled", "write_enabled", "next_run_risk", "config_safety_conclusion"]
    mismatches = _compare_fields(
        python_data={
            "overall_level": python_doctor.overall_status,
            "execution_enabled": python_doctor.next_run_type != "detect_only",
            "write_enabled": python_doctor.danger_level == "DANGER",
            "next_run_risk": python_next_risk,
            "config_safety_conclusion": python_doctor.overall_status,
        },
        powershell_data={
            "overall_level": parsed.get("overall_level"),
            "execution_enabled": parsed.get("execution_enabled"),
            "write_enabled": parsed.get("write_enabled"),
            "next_run_risk": parsed.get("next_run_risk"),
            "config_safety_conclusion": parsed.get("config_safety_conclusion"),
        },
        fields=fields,
    )
    unparseable = [field for field in fields if field not in parsed or parsed.get(field) is None]
    result = _parity_result(mismatches)
    return SafetyParityResult(
        parity_status=result.parity_status,
        mismatch_count=result.mismatch_count,
        mismatches=result.mismatches,
        unparseable_fields=unparseable,
    )


def snapshot_protected_files(paths: list[Path]) -> dict[str, str | None]:
    snapshot: dict[str, str | None] = {}
    for path in paths:
        if not path.exists():
            snapshot[str(path)] = None
            continue
        if not path.is_file():
            snapshot[str(path)] = "<not_file>"
            continue
        digest = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        snapshot[str(path)] = digest.hexdigest().upper()
    return snapshot


def _check(check_name: str, status: str, detail: str, recommendation: str) -> SafetyDoctorCheck:
    return SafetyDoctorCheck(
        check_name=check_name,
        status=status,
        detail=detail,
        recommendation=recommendation,
    )


def _status_check_status(safety_state: str) -> str:
    if safety_state in {"SAFE_DETECT_ONLY", "SAFE_NO_CONFIG"}:
        return "PASS" if safety_state == "SAFE_DETECT_ONLY" else "WARN"
    if safety_state == "CONFIG_WARN":
        return "WARN"
    return "FAIL"


def _danger_level_to_check(danger_level: str) -> str:
    if danger_level == "SAFE":
        return "PASS"
    if danger_level in {"WARN", "UNKNOWN"}:
        return "WARN"
    return "FAIL"


def _execution_check_status(result: SafetyExecutionStatusResult) -> str:
    if result.execution_mode == "write" or result.write_enabled or result.execution_confirm_present:
        return "FAIL"
    if result.arm_state in {"expired", "unknown"}:
        return "WARN"
    return "PASS"


def _doctor_overall_status(
    *,
    checks: list[SafetyDoctorCheck],
    safety_state: str,
    danger_level: str,
    arm_state: str,
) -> str:
    if safety_state in {"WRITE_ARMED", "EXECUTION_DANGER"} or danger_level == "DANGER":
        return "DANGER"
    if any(check.status == "FAIL" for check in checks):
        return "DANGER"
    if safety_state == "UNKNOWN" or danger_level == "UNKNOWN":
        return "UNKNOWN"
    if arm_state == "expired":
        return "WARN"
    if any(check.status == "WARN" for check in checks):
        return "WARN"
    return "SAFE"


def _doctor_recommendation(overall_status: str) -> str:
    if overall_status == "SAFE":
        return "Python read-only doctor found no blocking safety issues."
    if overall_status == "WARN":
        return "Review warning checks before relying on coverage or baseline analysis."
    if overall_status == "DANGER":
        return "Do not run CE until danger checks are resolved."
    return "Review unknown checks before continuing."


def _parse_doctor_for_parity(text: str) -> dict[str, object | None]:
    parsed = _parse_doctor_output(text)
    result: dict[str, object | None] = {}
    conclusion = parsed.get("conclusion")
    if conclusion:
        text_conclusion = str(conclusion)
        result["overall_level"] = "DANGER" if text_conclusion == "FAIL" else text_conclusion
        result["config_safety_conclusion"] = result["overall_level"]

    execution_detail = _doctor_check_detail(text, "execution config is safe")
    if execution_detail:
        execution_fields = _parse_semicolon_fields(execution_detail)
        mode = str(execution_fields.get("execution_mode") or "").strip()
        write_enabled = _as_bool(execution_fields.get("write_enabled"))
        result["execution_enabled"] = mode not in {"", "disabled"} or write_enabled
        result["write_enabled"] = write_enabled or mode == "write"
        if mode == "disabled" and not write_enabled:
            result["next_run_risk"] = "detect_only"
        elif mode == "dry_run":
            result["next_run_risk"] = "dry_run"
        else:
            result["next_run_risk"] = "write_risk"
    return result


def _doctor_check_detail(text: str, check_name: str) -> str | None:
    normalized = check_name.lower()
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.lower().startswith(normalized):
            continue
        parts = re.split(r"\s{2,}", line.strip(), maxsplit=2)
        if len(parts) >= 3:
            return parts[2].strip()
    return None


def _parse_semicolon_fields(text: str) -> dict[str, object | None]:
    parsed: dict[str, object | None] = {}
    for part in text.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        parsed[key.strip()] = _parse_output_value(value.strip())
    return parsed


def _strip_lua_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        else:
            if char in {"'", '"'}:
                quote = char
            elif char == "-" and index + 1 < len(line) and line[index + 1] == "-":
                return line[:index]
        index += 1
    return line


def _parse_lua_value(value: str) -> object | None:
    text = value.strip().rstrip(",").strip()
    if text in {"nil", "NULL"}:
        return None
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return _unescape_lua_string(text[1:-1])
    if re.fullmatch(r"-?\d+", text):
        try:
            return int(text)
        except ValueError:
            return text
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?|-?\d+[eE][+-]?\d+", text):
        try:
            return float(text)
        except ValueError:
            return text
    return text


def _unescape_lua_string(value: str) -> str:
    return (
        value.replace(r"\\", "\\")
        .replace(r"\"", '"')
        .replace(r"\'", "'")
        .replace(r"\n", "\n")
        .replace(r"\t", "\t")
    )


def _derive_execution_enabled(fields: dict[str, object | None]) -> bool:
    explicit = fields.get("execution_enabled")
    if explicit is not None:
        return _as_bool(explicit)
    mode = _normalized_mode(fields.get("execution_mode"))
    return mode not in {None, "", "disabled"} or _as_bool(fields.get("write_enabled"))


def _write_capable(fields: dict[str, object | None]) -> bool:
    mode = _normalized_mode(fields.get("execution_mode"))
    return (
        mode == "write"
        or _as_bool(fields.get("write_enabled"))
        or _present(fields.get("execution_confirm"))
        or _arm_present(fields)
    )


def _arm_present(fields: dict[str, object | None]) -> bool:
    return any(
        _present(fields.get(key))
        for key in ("execution_write_request_id", "execution_armed_at_utc", "execution_arm_expires_at_utc")
    )


def _arm_state(fields: dict[str, object | None], now: datetime) -> tuple[str, int | None]:
    request = fields.get("execution_write_request_id")
    armed = fields.get("execution_armed_at_utc")
    expires = fields.get("execution_arm_expires_at_utc")
    if not any(_present(value) for value in (request, armed, expires)):
        return "not_armed", None
    if not all(_present(value) for value in (request, armed, expires)):
        return "unknown", None
    expires_at = _parse_utc(str(expires))
    if expires_at is None:
        return "unknown", None
    seconds = int((expires_at - now).total_seconds())
    return ("armed", seconds) if seconds >= 0 else ("expired", seconds)


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _restore_source_addr(fields: dict[str, object | None]) -> object | None:
    for key in (
        "restore_source_batch_execution_addr",
        "restore_execution_addr",
        "restore_source_execution_addr",
        "execution_restore_source_addr",
    ):
        value = fields.get(key)
        if _present(value):
            return value
    return None


def _normalized_mode(value: object | None) -> str | None:
    if not _present(value):
        return "disabled"
    return str(value).strip()


def _present(value: object | None) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in {"", "-", "nil", "None"}
    return True


def _as_bool(value: object | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() == "true"


def _status_recommendation(safety_state: str, seconds_remaining: int | None) -> str:
    if safety_state == "SAFE_DETECT_ONLY":
        return "Config is safe for detect-only runs."
    if safety_state == "SAFE_NO_CONFIG":
        return "No local config found; create one before running CE."
    if safety_state == "WRITE_ARMED":
        return f"Write arm is active for {seconds_remaining} second(s); run CE only if this is intentional."
    if safety_state == "EXECUTION_DANGER":
        return "Run safe-reset before detect-only work unless an intentional guarded write is in progress."
    if safety_state == "CONFIG_WARN":
        return "Execution dry-run is configured; reset to disabled for normal detect-only collection."
    return "Review local config before running CE."


def _plan_recommendation(next_run_type: str, danger_level: str, arm_state: str) -> str:
    if next_run_type == "detect_only":
        return "Run CE only for detect-only validation, then post-full/post-quick."
    if next_run_type == "dry_run":
        return "Dry-run execution is configured; run CE only for explicit execution validation."
    if next_run_type in {"write_attempt", "restore_attempt"}:
        if arm_state == "expired":
            return "Write arm is expired; do not run CE until re-armed or reset."
        return "Write-capable config detected; run CE only if the guarded write/restore is intentional."
    if danger_level == "UNKNOWN":
        return "Inspect config before running CE."
    return "Review next-run plan before continuing."


def _execution_status_recommendation(
    mode: str | None,
    write_enabled: bool,
    confirm_present: bool,
    arm_state: str,
) -> str:
    if mode == "write" or write_enabled or confirm_present:
        if arm_state == "expired":
            return "Write config is present but arm is expired; run safe-reset or re-arm intentionally."
        if arm_state == "armed":
            return "Write config is armed; run CE only for the intentional guarded write."
        return "Write-capable fields are present; run safe-reset before detect-only work."
    return "Execution config is not write-capable."


def _run_powershell_tool(command_name: str, session_tool_path: Path) -> str:
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
        raise LogParseError("PowerShell executable was not found for safety parity") from exc
    except subprocess.TimeoutExpired as exc:
        raise LogParseError(f"PowerShell {command_name} parity check timed out") from exc
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        detail = f": {message}" if message else ""
        raise LogParseError(f"PowerShell {command_name} failed with exit code {completed.returncode}{detail}")
    return completed.stdout


def _parse_doctor_output(text: str) -> dict[str, object | None]:
    parsed = _parse_field_value_output(text)
    for raw_line in text.splitlines():
        match = re.match(r"^\s*conclusion\s*=\s*(\S+)", raw_line, flags=re.IGNORECASE)
        if match:
            parsed["conclusion"] = match.group(1)
    return parsed


def _parse_field_value_output(text: str) -> dict[str, object | None]:
    parsed: dict[str, object | None] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("-") or line in {"Field  Value", "Check  Status  Details"}:
            continue
        parts = re.split(r"\s{2,}", line, maxsplit=1)
        if len(parts) != 2:
            continue
        key = _normalize_key(parts[0])
        if key in {"field", "check"}:
            continue
        parsed[key] = _parse_output_value(parts[1].strip())
    return parsed


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _parse_output_value(value: str) -> object | None:
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


def _compare_fields(
    *,
    python_data: dict[str, object | None],
    powershell_data: dict[str, object | None],
    fields: list[str],
) -> list[SafetyParityMismatch]:
    mismatches: list[SafetyParityMismatch] = []
    for field in fields:
        left = _normalize_compare_value(python_data.get(field))
        if field not in powershell_data or powershell_data.get(field) is None:
            mismatches.append(SafetyParityMismatch(field, left, None, status="WARN"))
            continue
        right = _normalize_compare_value(powershell_data.get(field))
        if left != right:
            mismatches.append(SafetyParityMismatch(field, left, right))
    return mismatches


def _parity_result(mismatches: list[SafetyParityMismatch]) -> SafetyParityResult:
    has_fail = any(mismatch.status == "FAIL" for mismatch in mismatches)
    has_warn = any(mismatch.status == "WARN" for mismatch in mismatches)
    status = "FAIL" if has_fail else ("WARN" if has_warn else "PASS")
    return SafetyParityResult(parity_status=status, mismatch_count=len(mismatches), mismatches=mismatches)


def _normalize_compare_value(value: object | None) -> object | None:
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


def _status_to_doctor_conclusion(safety_state: str) -> str:
    if safety_state in {"SAFE_DETECT_ONLY", "SAFE_NO_CONFIG"}:
        return "SAFE"
    if safety_state in {"CONFIG_WARN"}:
        return "ATTENTION"
    return "FAIL"


def _execution_safe_conclusion(status: SafetyExecutionStatusResult) -> str:
    if status.execution_mode == "write" or status.write_enabled or status.execution_confirm_present:
        return "WARNING"
    return "SAFE"


def _normalize_execution_safety(value: object | None) -> object | None:
    if value is None:
        return None
    text = str(value)
    if text.startswith("SAFE"):
        return "SAFE"
    if text.startswith("WARNING") or text.startswith("ATTENTION"):
        return "WARNING"
    return text
