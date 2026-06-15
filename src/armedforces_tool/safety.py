from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .logs import LogParseError

DEFAULT_PROJECT_ROOT = Path(r"D:\armedforces.io-v2")
DEFAULT_CONFIG_PATH = DEFAULT_PROJECT_ROOT / "src" / "run_case_config.local.lua"
DEFAULT_SESSION_TOOL_PATH = DEFAULT_PROJECT_ROOT / "src" / "test_session_tool.ps1"

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

    def to_dict(self) -> dict[str, object]:
        return {
            "parity_status": self.parity_status,
            "mismatch_count": self.mismatch_count,
            "mismatches": [mismatch.to_dict() for mismatch in self.mismatches],
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
