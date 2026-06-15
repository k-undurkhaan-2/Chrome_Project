from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .case_summary import DEFAULT_BASELINE_PATH, _latest_baseline_eligible_records, analyze_case_summary
from .logs import DEFAULT_LOG_ROOT, LogParseError
from .safety import DEFAULT_PROJECT_ROOT, DEFAULT_SESSION_TOOL_PATH

DEFAULT_BASELINE_DIR = DEFAULT_PROJECT_ROOT / "log" / "baselines"


@dataclass(frozen=True)
class BaselineMarkdown:
    path: str
    exists: bool
    parse_status: str
    parse_warnings: list[str]
    profile: str | None
    latest_n: int | None
    unique_known_true_addr_count: int | None
    baseline_eligible_count: int | None
    success_count: int | None
    created_at: str | None
    known_true_addrs: list[str]

    def to_dict(self) -> dict[str, object | None]:
        return {
            "path": self.path,
            "exists": self.exists,
            "parse_status": self.parse_status,
            "parse_warnings": self.parse_warnings,
            "profile": self.profile,
            "latest_n": self.latest_n,
            "unique_known_true_addr_count": self.unique_known_true_addr_count,
            "baseline_eligible_count": self.baseline_eligible_count,
            "success_count": self.success_count,
            "created_at": self.created_at,
            "known_true_addrs": self.known_true_addrs,
        }


@dataclass(frozen=True)
class BaselineListRecord:
    path: str
    filename: str
    exists: bool
    parsed_profile: str | None
    parsed_latest_n: int | None
    unique_known_true_addr_count: int | None
    created_at: str | None
    is_current_default: bool
    parse_status: str
    parse_warnings: list[str]

    def to_dict(self) -> dict[str, object | None]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class BaselineListResult:
    project_root: str
    baseline_dir: str
    baseline_dir_exists: bool
    baseline_count: int
    current_baseline_path: str
    current_baseline_exists: bool
    latest_baseline_path: str | None
    conclusion: str
    recommendation: str
    records: list[BaselineListRecord]

    def to_dict(self) -> dict[str, object | None]:
        return {
            "project_root": self.project_root,
            "baseline_dir": self.baseline_dir,
            "baseline_dir_exists": self.baseline_dir_exists,
            "baseline_count": self.baseline_count,
            "current_baseline_path": self.current_baseline_path,
            "current_baseline_exists": self.current_baseline_exists,
            "latest_baseline_path": self.latest_baseline_path,
            "conclusion": self.conclusion,
            "recommendation": self.recommendation,
            "records": [record.to_dict() for record in self.records],
        }


@dataclass(frozen=True)
class BaselineCurrentResult:
    baseline_path: str
    baseline_exists: bool
    parse_status: str
    profile: str | None
    latest_n: int | None
    unique_known_true_addr_count: int | None
    baseline_eligible_count: int | None
    success_count: int | None
    created_at: str | None
    known_true_addrs: list[str]
    conclusion: str
    recommendation: str
    parse_warnings: list[str]

    def to_dict(self) -> dict[str, object | None]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class BaselineCompareResult:
    baseline_path: str
    baseline_exists: bool
    latest_n: int
    profile: str
    baseline_unique_known_true_addr_count: int | None
    current_eligible_batch_count: int
    current_success_count: int
    current_unique_known_true_addr_count: int
    coverage_delta: int | None
    repeated_known_true_addr: list[dict[str, object]]
    missing_from_current: list[str]
    new_in_current: list[str]
    conclusion: str
    recommendation: str

    def to_dict(self) -> dict[str, object | None]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class BaselineParityMismatch:
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
class BaselineParityResult:
    parity_status: str
    mismatch_count: int
    mismatches: list[BaselineParityMismatch]
    unparseable_fields: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "parity_status": self.parity_status,
            "mismatch_count": self.mismatch_count,
            "mismatches": [mismatch.to_dict() for mismatch in self.mismatches],
            "unparseable_fields": self.unparseable_fields,
        }


def parse_baseline_markdown(path: Path) -> BaselineMarkdown:
    if not path.exists():
        return BaselineMarkdown(
            path=str(path),
            exists=False,
            parse_status="MISSING",
            parse_warnings=["baseline file does not exist"],
            profile=None,
            latest_n=None,
            unique_known_true_addr_count=None,
            baseline_eligible_count=None,
            success_count=None,
            created_at=None,
            known_true_addrs=[],
        )
    if not path.is_file():
        raise LogParseError(f"baseline path is not a file: {path}")

    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return BaselineMarkdown(
            path=str(path),
            exists=True,
            parse_status="EMPTY",
            parse_warnings=["baseline file is empty"],
            profile=None,
            latest_n=None,
            unique_known_true_addr_count=None,
            baseline_eligible_count=None,
            success_count=None,
            created_at=None,
            known_true_addrs=[],
        )

    fields = _parse_markdown_field_rows(text)
    profile = _as_text(fields.get("validation_profile")) or _infer_profile(path.name)
    latest_n = _parse_int(fields.get("latest n")) or _infer_latest_n(path.name)
    created_at = _as_text(fields.get("generated_at")) or _mtime_text(path)
    unique_count = _extract_int(r"unique\s+known_true_addr\s+count\s*:\s*(\d+)", text)
    baseline_eligible_count = _extract_int(r"total\s+batch\s+count\s*:\s*(\d+)", text)
    if baseline_eligible_count is None:
        baseline_eligible_count = _parse_int(fields.get("full_success count"))
    success_count = _extract_success_count(text)
    known_true_addrs = _extract_known_true_addr_list(text)

    warnings: list[str] = []
    if profile is None:
        warnings.append("profile not found")
    if latest_n is None:
        warnings.append("latest N not found")
    if unique_count is None:
        warnings.append("unique known_true_addr count not found")
    if not known_true_addrs:
        warnings.append("known_true_addr list not found")

    return BaselineMarkdown(
        path=str(path),
        exists=True,
        parse_status="WARN" if warnings else "OK",
        parse_warnings=warnings,
        profile=profile,
        latest_n=latest_n,
        unique_known_true_addr_count=unique_count,
        baseline_eligible_count=baseline_eligible_count,
        success_count=success_count,
        created_at=created_at,
        known_true_addrs=known_true_addrs,
    )


def analyze_baseline_list(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    baseline_dir: Path = DEFAULT_BASELINE_DIR,
    current_baseline: Path = DEFAULT_BASELINE_PATH,
) -> BaselineListResult:
    if not baseline_dir.exists():
        return BaselineListResult(
            project_root=str(project_root),
            baseline_dir=str(baseline_dir),
            baseline_dir_exists=False,
            baseline_count=0,
            current_baseline_path=str(current_baseline),
            current_baseline_exists=current_baseline.exists(),
            latest_baseline_path=None,
            conclusion="BASELINE_DIR_MISSING",
            recommendation="Create or point --baseline-dir at an existing ignored baseline directory.",
            records=[],
        )
    if not baseline_dir.is_dir():
        raise LogParseError(f"baseline dir is not a directory: {baseline_dir}")

    files = sorted(
        baseline_dir.glob("*.md"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    records = [_baseline_list_record(path, current_baseline) for path in files]
    if not records:
        conclusion = "NO_BASELINES_FOUND"
    elif not current_baseline.exists() or any(record.parse_status in {"EMPTY", "MISSING"} for record in records):
        conclusion = "BASELINE_WARN"
    else:
        conclusion = "BASELINE_LIST_OK"

    return BaselineListResult(
        project_root=str(project_root),
        baseline_dir=str(baseline_dir),
        baseline_dir_exists=True,
        baseline_count=len(records),
        current_baseline_path=str(current_baseline),
        current_baseline_exists=current_baseline.exists(),
        latest_baseline_path=str(files[0]) if files else None,
        conclusion=conclusion,
        recommendation=_baseline_list_recommendation(conclusion),
        records=records,
    )


def analyze_baseline_current(*, baseline: Path = DEFAULT_BASELINE_PATH) -> BaselineCurrentResult:
    parsed = parse_baseline_markdown(baseline)
    if not parsed.exists:
        conclusion = "BASELINE_MISSING"
    elif parsed.parse_status == "EMPTY":
        conclusion = "BASELINE_EMPTY"
    elif parsed.parse_status == "WARN":
        conclusion = "BASELINE_PARSE_WARN"
    else:
        conclusion = "BASELINE_CURRENT_OK"
    return BaselineCurrentResult(
        baseline_path=str(baseline),
        baseline_exists=parsed.exists,
        parse_status=parsed.parse_status,
        profile=parsed.profile,
        latest_n=parsed.latest_n,
        unique_known_true_addr_count=parsed.unique_known_true_addr_count,
        baseline_eligible_count=parsed.baseline_eligible_count,
        success_count=parsed.success_count,
        created_at=parsed.created_at,
        known_true_addrs=parsed.known_true_addrs,
        conclusion=conclusion,
        recommendation=_baseline_current_recommendation(conclusion),
        parse_warnings=parsed.parse_warnings,
    )


def analyze_baseline_compare(
    *,
    baseline: Path = DEFAULT_BASELINE_PATH,
    latest: int = 20,
    profile: str = "full",
    log_root: Path = DEFAULT_LOG_ROOT,
) -> BaselineCompareResult:
    if latest < 1:
        raise LogParseError("--latest must be greater than 0")

    parsed = parse_baseline_markdown(baseline)
    if not parsed.exists:
        return BaselineCompareResult(
            baseline_path=str(baseline),
            baseline_exists=False,
            latest_n=latest,
            profile=profile,
            baseline_unique_known_true_addr_count=None,
            current_eligible_batch_count=0,
            current_success_count=0,
            current_unique_known_true_addr_count=0,
            coverage_delta=None,
            repeated_known_true_addr=[],
            missing_from_current=[],
            new_in_current=[],
            conclusion="BASELINE_MISSING",
            recommendation="Provide an existing baseline file before comparing.",
        )

    summary = analyze_case_summary(log_root=log_root, latest=latest, profile=profile, baseline=baseline)
    current_records = _latest_baseline_eligible_records(log_root=log_root, latest=latest, profile=profile)
    current_addrs = {record.known_true_addr for record in current_records if record.known_true_addr}
    baseline_addrs = set(parsed.known_true_addrs)
    repeated = [item.to_dict() for item in summary.repeated_known_true_addr]
    conclusion = _baseline_compare_conclusion(
        target_unique=summary.target_unique_known_true_addr_count,
        eligible_count=summary.current_eligible_batch_count,
        success_count=summary.current_success_count,
        current_unique=summary.current_unique_known_true_addr_count,
    )
    return BaselineCompareResult(
        baseline_path=str(baseline),
        baseline_exists=True,
        latest_n=latest,
        profile=profile,
        baseline_unique_known_true_addr_count=summary.baseline_unique_known_true_addr_count,
        current_eligible_batch_count=summary.current_eligible_batch_count,
        current_success_count=summary.current_success_count,
        current_unique_known_true_addr_count=summary.current_unique_known_true_addr_count,
        coverage_delta=summary.coverage_delta,
        repeated_known_true_addr=repeated,
        missing_from_current=sorted(baseline_addrs - current_addrs),
        new_in_current=sorted(current_addrs - baseline_addrs),
        conclusion=conclusion,
        recommendation=_baseline_compare_recommendation(conclusion, summary.estimated_new_distinct_addr_needed),
    )


def baseline_list_parity(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    baseline_dir: Path = DEFAULT_BASELINE_DIR,
    current_baseline: Path = DEFAULT_BASELINE_PATH,
    session_tool_path: Path = DEFAULT_SESSION_TOOL_PATH,
) -> BaselineParityResult:
    python_result = analyze_baseline_list(
        project_root=project_root,
        baseline_dir=baseline_dir,
        current_baseline=current_baseline,
    )
    powershell = _run_powershell_baseline_command(["baseline-list"], session_tool_path)
    parsed = _parse_powershell_baseline_list(powershell)
    return _compare_parity(
        python_data=python_result.to_dict(),
        powershell_data=parsed,
        fields=["baseline_count", "current_baseline_exists"],
    )


def baseline_current_parity(
    *,
    baseline: Path = DEFAULT_BASELINE_PATH,
    session_tool_path: Path = DEFAULT_SESSION_TOOL_PATH,
) -> BaselineParityResult:
    python_result = analyze_baseline_current(baseline=baseline)
    powershell = _run_powershell_baseline_command(["baseline-current"], session_tool_path)
    parsed = _parse_powershell_baseline_current(powershell)
    return _compare_parity(
        python_data=python_result.to_dict(),
        powershell_data=parsed,
        fields=["baseline_exists", "unique_known_true_addr_count", "profile", "latest_n"],
    )


def baseline_compare_parity(
    *,
    baseline: Path = DEFAULT_BASELINE_PATH,
    latest: int = 20,
    profile: str = "full",
    log_root: Path = DEFAULT_LOG_ROOT,
    session_tool_path: Path = DEFAULT_SESSION_TOOL_PATH,
) -> BaselineParityResult:
    python_result = analyze_baseline_compare(baseline=baseline, latest=latest, profile=profile, log_root=log_root)
    powershell = _run_powershell_baseline_command(["baseline-compare", "-Baseline", str(baseline)], session_tool_path)
    parsed = _parse_powershell_baseline_compare(powershell)
    return _compare_parity(
        python_data=python_result.to_dict(),
        powershell_data=parsed,
        fields=[
            "baseline_unique_known_true_addr_count",
            "current_eligible_batch_count",
            "current_success_count",
            "current_unique_known_true_addr_count",
            "coverage_delta",
            "conclusion",
        ],
    )


def _baseline_list_record(path: Path, current_baseline: Path) -> BaselineListRecord:
    parsed = parse_baseline_markdown(path)
    return BaselineListRecord(
        path=str(path),
        filename=path.name,
        exists=path.exists(),
        parsed_profile=parsed.profile,
        parsed_latest_n=parsed.latest_n,
        unique_known_true_addr_count=parsed.unique_known_true_addr_count,
        created_at=parsed.created_at,
        is_current_default=_same_path(path, current_baseline),
        parse_status=parsed.parse_status,
        parse_warnings=parsed.parse_warnings,
    )


def _baseline_compare_conclusion(
    *,
    target_unique: int | None,
    eligible_count: int,
    success_count: int,
    current_unique: int,
) -> str:
    if target_unique is None:
        return "INSUFFICIENT_DATA"
    if eligible_count == 0:
        return "INSUFFICIENT_DATA"
    if success_count < eligible_count:
        return "BASELINE_COMPARE_FAIL"
    if current_unique >= target_unique:
        return "BASELINE_COMPARE_PASS"
    return "BASELINE_COMPARE_WARN"


def _baseline_list_recommendation(conclusion: str) -> str:
    if conclusion == "BASELINE_LIST_OK":
        return "Baselines are available; use baseline current or baseline compare for details."
    if conclusion == "BASELINE_DIR_MISSING":
        return "Create the ignored log/baselines directory or pass --baseline-dir."
    if conclusion == "NO_BASELINES_FOUND":
        return "No baseline Markdown files were found; save one with the existing PowerShell baseline-save workflow if needed."
    return "Review current baseline path and any empty/missing baseline files."


def _baseline_current_recommendation(conclusion: str) -> str:
    if conclusion == "BASELINE_CURRENT_OK":
        return "Current baseline is readable."
    if conclusion == "BASELINE_MISSING":
        return "Select an existing baseline or create one with the existing PowerShell baseline-save workflow."
    if conclusion == "BASELINE_EMPTY":
        return "Baseline file is empty; choose another baseline."
    return "Baseline is readable with warnings; inspect missing parse fields before relying on it."


def _baseline_compare_recommendation(conclusion: str, estimated_needed: int | None) -> str:
    if conclusion == "BASELINE_COMPARE_PASS":
        return "Current baseline-eligible full window satisfies the baseline coverage target."
    if conclusion == "BASELINE_COMPARE_WARN":
        needed = estimated_needed if estimated_needed is not None else "more"
        return f"Collect at least {needed} new distinct baseline-eligible full batch(es)."
    if conclusion == "BASELINE_COMPARE_FAIL":
        return "Inspect latest baseline-eligible records before refreshing baselines."
    if conclusion == "BASELINE_MISSING":
        return "Provide an existing baseline file."
    return "Not enough baseline or log data is available for comparison."


def _parse_markdown_field_rows(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) != 2:
            continue
        key, value = parts
        key_lower = key.lower()
        if key_lower in {"field", "metric", "classification"}:
            continue
        fields.setdefault(key_lower, value)
    return fields


def _extract_success_count(text: str) -> int | None:
    match = re.search(r"^\|\s*success\s*\|\s*(\d+)\s*\|", text, flags=re.IGNORECASE | re.MULTILINE)
    if match:
        return int(match.group(1))
    fields = _parse_markdown_field_rows(text)
    return _parse_int(fields.get("full_success count"))


def _extract_known_true_addr_list(text: str) -> list[str]:
    addrs: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not re.match(r"^\|\s*\d{8}-\d{6}\s*\|", line):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) < 2:
            continue
        addr = parts[1]
        if re.fullmatch(r"0x[0-9A-Fa-f]+", addr) and addr.lower() not in seen:
            addrs.append(addr)
            seen.add(addr.lower())
    return addrs


def _extract_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _infer_profile(filename: str) -> str | None:
    lowered = filename.lower()
    if "quick" in lowered:
        return "quick"
    if "full" in lowered or "compact_basic" in lowered:
        return "full"
    return None


def _infer_latest_n(filename: str) -> int | None:
    match = re.search(r"latest(\d+)", filename, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _mtime_text(path: Path) -> str | None:
    try:
        path.stat()
    except OSError:
        return None
    return _format_mtime(path)


def _format_mtime(path: Path) -> str:
    from datetime import datetime

    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def _parse_int(value: object | None) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    return int(text) if re.fullmatch(r"-?\d+", text) else None


def _as_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text not in {"-", "nil", "None"} else None


def _same_path(left: Path, right: Path) -> bool:
    return _path_key(left) == _path_key(right)


def _path_key(path: Path) -> str:
    return str(path).replace("/", "\\").rstrip("\\").lower()


def _run_powershell_baseline_command(args: list[str], session_tool_path: Path) -> str:
    if not session_tool_path.exists():
        raise LogParseError(f"PowerShell session tool not found: {session_tool_path}")
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(session_tool_path),
        *args,
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=180)
    except FileNotFoundError as exc:
        raise LogParseError("PowerShell executable was not found for baseline parity") from exc
    except subprocess.TimeoutExpired as exc:
        raise LogParseError(f"PowerShell {' '.join(args)} parity check timed out") from exc
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        detail = f": {message}" if message else ""
        raise LogParseError(f"PowerShell {' '.join(args)} failed with exit code {completed.returncode}{detail}")
    return completed.stdout


def _parse_powershell_baseline_list(text: str) -> dict[str, object | None]:
    count = 0
    current_exists = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("-"):
            continue
        parts = re.split(r"\s{2,}", line)
        if len(parts) < 2:
            continue
        if parts[0].lower().endswith(".md"):
            count += 1
            current_exists = current_exists or str(parts[1]).strip().lower() == "true"
    return {
        "baseline_count": count,
        "current_baseline_exists": current_exists if count else None,
    }


def _parse_powershell_baseline_current(text: str) -> dict[str, object | None]:
    parsed = _parse_field_value_output(text)
    return {
        "baseline_exists": parsed.get("baseline_exists"),
        "latest_n": parsed.get("latest_count"),
        "unique_known_true_addr_count": parsed.get("unique_known_true_addr_count"),
        "profile": parsed.get("profile"),
    }


def _parse_powershell_baseline_compare(text: str) -> dict[str, object | None]:
    parsed = _parse_field_value_output(text)
    return {
        "baseline_unique_known_true_addr_count": parsed.get("baseline_unique_known_true_addr_count"),
        "current_eligible_batch_count": parsed.get("current_eligible_batch_count"),
        "current_success_count": parsed.get("current_success_count"),
        "current_unique_known_true_addr_count": parsed.get("current_unique_known_true_addr_count"),
        "coverage_delta": parsed.get("coverage_delta"),
        "conclusion": _compare_status_to_conclusion(parsed.get("regression_status")),
    }


def _parse_field_value_output(text: str) -> dict[str, object | None]:
    parsed: dict[str, object | None] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("-"):
            continue
        parts = re.split(r"\s{2,}", line, maxsplit=1)
        if len(parts) != 2:
            continue
        key = re.sub(r"[^a-z0-9]+", "_", parts[0].strip().lower()).strip("_")
        if key in {"field", "filename"}:
            continue
        parsed[key] = _parse_scalar(parts[1])
    return parsed


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


def _compare_status_to_conclusion(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if text == "PASS":
        return "BASELINE_COMPARE_PASS"
    if text == "WARN":
        return "BASELINE_COMPARE_WARN"
    if text == "FAIL":
        return "BASELINE_COMPARE_FAIL"
    return text


def _compare_parity(
    *,
    python_data: dict[str, object | None],
    powershell_data: dict[str, object | None],
    fields: list[str],
) -> BaselineParityResult:
    mismatches: list[BaselineParityMismatch] = []
    unparseable: list[str] = []
    for field in fields:
        left = _normalize_parity_value(python_data.get(field))
        if field not in powershell_data or powershell_data.get(field) is None:
            unparseable.append(field)
            mismatches.append(BaselineParityMismatch(field, left, None, status="WARN"))
            continue
        right = _normalize_parity_value(powershell_data.get(field))
        if left != right:
            mismatches.append(BaselineParityMismatch(field, left, right, status="FAIL"))
    has_fail = any(mismatch.status == "FAIL" for mismatch in mismatches)
    has_warn = any(mismatch.status == "WARN" for mismatch in mismatches)
    return BaselineParityResult(
        parity_status="FAIL" if has_fail else ("WARN" if has_warn else "PASS"),
        mismatch_count=len(mismatches),
        mismatches=mismatches,
        unparseable_fields=unparseable,
    )


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
