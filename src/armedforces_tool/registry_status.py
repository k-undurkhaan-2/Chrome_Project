from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .safety import DEFAULT_PROJECT_ROOT

DEFAULT_REGISTRY_PATH = DEFAULT_PROJECT_ROOT / "log" / "case_registry.jsonl"


class RegistryStatusError(RuntimeError):
    """Raised for user-facing registry status errors."""


@dataclass(frozen=True)
class RegistryRecord:
    line_number: int
    raw_fields: dict[str, object]
    batch_id: str | None
    known_true_addr: str | None
    validation_profile: str | None
    classification: str | None
    baseline_eligible: bool | None
    execution_outcome: str | None
    transaction_type: str | None
    created_at: str | None
    parse_status: str
    warnings: list[str]

    def to_dict(self) -> dict[str, object | None]:
        return {
            "line_number": self.line_number,
            "batch_id": self.batch_id,
            "known_true_addr": self.known_true_addr,
            "validation_profile": self.validation_profile,
            "classification": self.classification,
            "baseline_eligible": self.baseline_eligible,
            "execution_outcome": self.execution_outcome,
            "transaction_type": self.transaction_type,
            "created_at": self.created_at,
            "parse_status": self.parse_status,
            "warnings": self.warnings,
            "raw_fields": self.raw_fields,
        }


@dataclass(frozen=True)
class RegistryMalformedLine:
    line_number: int
    message: str
    text_preview: str

    def to_dict(self) -> dict[str, object]:
        return {
            "line_number": self.line_number,
            "message": self.message,
            "text_preview": self.text_preview,
        }


@dataclass(frozen=True)
class RegistryData:
    project_root: str
    registry_path: str
    registry_exists: bool
    total_lines: int
    parsed_records: list[RegistryRecord]
    malformed_lines: list[RegistryMalformedLine]


@dataclass(frozen=True)
class RegistrySummaryResult:
    project_root: str
    registry_path: str
    registry_exists: bool
    total_lines: int
    parsed_records: int
    malformed_lines: int
    record_count: int
    profile_filter: str
    classification_counts: dict[str, int]
    profile_counts: dict[str, int]
    unique_known_true_addr_count: int
    baseline_eligible_count: int
    execution_batch_count: int
    latest_batch_id: str | None
    latest_known_true_addr: str | None
    latest_record_timestamp: str | None
    conclusion: str
    recommendation: str
    warnings: list[dict[str, object]]

    def to_dict(self) -> dict[str, object | None]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class RegistryListRecord:
    index: int
    line_number: int
    batch_id: str | None
    known_true_addr: str | None
    validation_profile: str | None
    classification: str | None
    baseline_eligible: bool | None
    execution_outcome: str | None
    transaction_type: str | None
    created_at: str | None
    parse_status: str
    warnings: list[str]

    def to_dict(self) -> dict[str, object | None]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class RegistryListResult:
    project_root: str
    registry_path: str
    registry_exists: bool
    total_lines: int
    parsed_records: int
    malformed_lines: int
    record_count: int
    profile_filter: str
    limit: int
    conclusion: str
    recommendation: str
    records: list[RegistryListRecord]
    warnings: list[dict[str, object]]

    def to_dict(self) -> dict[str, object | None]:
        return {
            "project_root": self.project_root,
            "registry_path": self.registry_path,
            "registry_exists": self.registry_exists,
            "total_lines": self.total_lines,
            "parsed_records": self.parsed_records,
            "malformed_lines": self.malformed_lines,
            "record_count": self.record_count,
            "profile_filter": self.profile_filter,
            "limit": self.limit,
            "conclusion": self.conclusion,
            "recommendation": self.recommendation,
            "records": [record.to_dict() for record in self.records],
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class RegistryShowResult:
    project_root: str
    registry_path: str
    registry_exists: bool
    query_type: str
    query_value: str
    profile_filter: str
    matched_count: int
    conclusion: str
    recommendation: str
    latest_matching_record: dict[str, object | None] | None
    records: list[dict[str, object | None]]
    malformed_lines: int
    warnings: list[dict[str, object]]

    def to_dict(self) -> dict[str, object | None]:
        return self.__dict__.copy()


def analyze_registry_summary(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    registry: Path = DEFAULT_REGISTRY_PATH,
    profile: str = "all",
) -> RegistrySummaryResult:
    data = parse_registry(project_root=project_root, registry=registry)
    records = _filter_by_profile(data.parsed_records, profile)
    latest = records[-1] if records else None
    classification_counts = _counter_dict(record.classification or "unknown" for record in records)
    profile_counts = _counter_dict(record.validation_profile or "unknown" for record in records)
    known_true_addrs = {record.known_true_addr for record in records if record.known_true_addr}
    conclusion = _summary_conclusion(data)
    return RegistrySummaryResult(
        project_root=data.project_root,
        registry_path=data.registry_path,
        registry_exists=data.registry_exists,
        total_lines=data.total_lines,
        parsed_records=len(data.parsed_records),
        malformed_lines=len(data.malformed_lines),
        record_count=len(records),
        profile_filter=_normalize_profile(profile),
        classification_counts=classification_counts,
        profile_counts=profile_counts,
        unique_known_true_addr_count=len(known_true_addrs),
        baseline_eligible_count=sum(1 for record in records if record.baseline_eligible is True),
        execution_batch_count=sum(1 for record in records if _is_execution_batch(record)),
        latest_batch_id=latest.batch_id if latest else None,
        latest_known_true_addr=latest.known_true_addr if latest else None,
        latest_record_timestamp=latest.created_at if latest else None,
        conclusion=conclusion,
        recommendation=_summary_recommendation(conclusion),
        warnings=[warning.to_dict() for warning in data.malformed_lines],
    )


def analyze_registry_list(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    registry: Path = DEFAULT_REGISTRY_PATH,
    limit: int = 20,
    profile: str = "all",
) -> RegistryListResult:
    if limit < 1:
        raise RegistryStatusError("--limit must be greater than 0")
    data = parse_registry(project_root=project_root, registry=registry)
    records = _filter_by_profile(data.parsed_records, profile)
    recent = records[-limit:]
    listed = [
        RegistryListRecord(
            index=index,
            line_number=record.line_number,
            batch_id=record.batch_id,
            known_true_addr=record.known_true_addr,
            validation_profile=record.validation_profile,
            classification=record.classification,
            baseline_eligible=record.baseline_eligible,
            execution_outcome=record.execution_outcome,
            transaction_type=record.transaction_type,
            created_at=record.created_at,
            parse_status=record.parse_status,
            warnings=record.warnings,
        )
        for index, record in enumerate(recent, start=1)
    ]
    conclusion = _summary_conclusion(data)
    return RegistryListResult(
        project_root=data.project_root,
        registry_path=data.registry_path,
        registry_exists=data.registry_exists,
        total_lines=data.total_lines,
        parsed_records=len(data.parsed_records),
        malformed_lines=len(data.malformed_lines),
        record_count=len(records),
        profile_filter=_normalize_profile(profile),
        limit=limit,
        conclusion=conclusion,
        recommendation=_summary_recommendation(conclusion),
        records=listed,
        warnings=[warning.to_dict() for warning in data.malformed_lines],
    )


def analyze_registry_show(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    registry: Path = DEFAULT_REGISTRY_PATH,
    known_true_addr: str | None = None,
    batch_id: str | None = None,
    profile: str = "all",
) -> RegistryShowResult:
    query_type, query_value = _normalize_show_query(known_true_addr=known_true_addr, batch_id=batch_id)
    data = parse_registry(project_root=project_root, registry=registry)
    records = _filter_by_profile(data.parsed_records, profile)
    if query_type == "known_true_addr":
        matched = [record for record in records if _same_addr(record.known_true_addr, query_value)]
    else:
        matched = [record for record in records if record.batch_id == query_value]

    if not data.registry_exists:
        conclusion = "REGISTRY_MISSING"
    elif data.malformed_lines:
        conclusion = "REGISTRY_PARSE_WARN" if matched else "REGISTRY_PARSE_WARN"
    elif matched:
        conclusion = "REGISTRY_MATCH_FOUND"
    else:
        conclusion = "REGISTRY_NO_MATCH"
    if data.registry_exists and not data.malformed_lines:
        conclusion = "REGISTRY_MATCH_FOUND" if matched else "REGISTRY_NO_MATCH"

    latest = matched[-1].to_dict() if matched else None
    return RegistryShowResult(
        project_root=data.project_root,
        registry_path=data.registry_path,
        registry_exists=data.registry_exists,
        query_type=query_type,
        query_value=query_value,
        profile_filter=_normalize_profile(profile),
        matched_count=len(matched),
        conclusion=conclusion,
        recommendation=_show_recommendation(conclusion),
        latest_matching_record=latest,
        records=[record.to_dict() for record in matched],
        malformed_lines=len(data.malformed_lines),
        warnings=[warning.to_dict() for warning in data.malformed_lines],
    )


def parse_registry(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    registry: Path = DEFAULT_REGISTRY_PATH,
) -> RegistryData:
    if not registry.exists():
        return RegistryData(
            project_root=str(project_root),
            registry_path=str(registry),
            registry_exists=False,
            total_lines=0,
            parsed_records=[],
            malformed_lines=[],
        )

    parsed: list[RegistryRecord] = []
    malformed: list[RegistryMalformedLine] = []
    lines = registry.read_text(encoding="utf-8-sig").splitlines()
    for line_number, line in enumerate(lines, start=1):
        text = line.strip()
        if not text:
            malformed.append(RegistryMalformedLine(line_number, "empty JSONL line", ""))
            continue
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            malformed.append(RegistryMalformedLine(line_number, f"invalid JSON: {exc.msg}", text[:120]))
            continue
        if not isinstance(raw, dict):
            malformed.append(RegistryMalformedLine(line_number, "JSONL line is not an object", text[:120]))
            continue
        parsed.append(_record_from_raw(line_number=line_number, raw=raw))
    return RegistryData(
        project_root=str(project_root),
        registry_path=str(registry),
        registry_exists=True,
        total_lines=len(lines),
        parsed_records=parsed,
        malformed_lines=malformed,
    )


def validate_known_true_addr(value: str) -> str:
    candidate = value.strip() if value else ""
    if not candidate:
        raise RegistryStatusError("known_true_addr is required and must look like 0xCE061C7D48")
    if not candidate.lower().startswith("0x"):
        if re.fullmatch(r"[0-9A-Fa-f]+", candidate):
            raise RegistryStatusError(
                f"known_true_addr must include the 0x prefix; try 0x{candidate}"
            )
        raise RegistryStatusError("known_true_addr must use 0x prefix and contain only hex digits")
    if not re.fullmatch(r"0x[0-9A-Fa-f]+", candidate):
        raise RegistryStatusError("known_true_addr must use 0x prefix and contain only hex digits")
    return "0x" + candidate[2:].upper()


def _record_from_raw(*, line_number: int, raw: dict[str, object]) -> RegistryRecord:
    warnings: list[str] = []
    known_true_addr = _as_str(_first_present(raw, ["known_true_addr", "known_true_address", "addr"]))
    normalized_addr = _normalize_addr_or_none(known_true_addr)
    if known_true_addr and normalized_addr is None:
        warnings.append("known_true_addr is not valid 0x hex")
    return RegistryRecord(
        line_number=line_number,
        raw_fields=dict(raw),
        batch_id=_as_str(_first_present(raw, ["batch_id"])),
        known_true_addr=normalized_addr or known_true_addr,
        validation_profile=_normalize_profile_value(_as_str(_first_present(raw, ["validation_profile", "profile"]))),
        classification=_as_str(_first_present(raw, ["classification"])),
        baseline_eligible=_as_bool(_first_present(raw, ["baseline_eligible"])),
        execution_outcome=_as_str(_first_present(raw, ["execution_outcome"])),
        transaction_type=_as_str(_first_present(raw, ["transaction_type"])),
        created_at=_as_str(_first_present(raw, ["recorded_at", "created_at", "timestamp"])),
        parse_status="WARN" if warnings else "OK",
        warnings=warnings,
    )


def _first_present(raw: dict[str, object], names: Iterable[str]) -> object | None:
    for name in names:
        if name in raw:
            return raw[name]
    return None


def _as_str(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _as_bool(value: object | None) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _normalize_profile(profile: str | None) -> str:
    if profile is None:
        return "all"
    normalized = profile.strip().lower()
    if normalized in {"", "all"}:
        return "all"
    if normalized not in {"full", "quick"}:
        raise RegistryStatusError("--profile must be one of all, full, quick")
    return normalized


def _normalize_profile_value(profile: str | None) -> str | None:
    if profile is None:
        return None
    normalized = profile.strip().lower()
    return normalized if normalized in {"full", "quick"} else profile


def _filter_by_profile(records: list[RegistryRecord], profile: str | None) -> list[RegistryRecord]:
    normalized = _normalize_profile(profile)
    if normalized == "all":
        return records
    return [record for record in records if record.validation_profile == normalized]


def _normalize_addr_or_none(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if not re.fullmatch(r"0x[0-9A-Fa-f]+", candidate):
        return None
    return "0x" + candidate[2:].upper()


def _same_addr(left: str | None, right: str) -> bool:
    left_normalized = _normalize_addr_or_none(left)
    right_normalized = _normalize_addr_or_none(right)
    return left_normalized is not None and right_normalized is not None and left_normalized == right_normalized


def _normalize_show_query(*, known_true_addr: str | None, batch_id: str | None) -> tuple[str, str]:
    if known_true_addr and batch_id:
        raise RegistryStatusError("provide either --known-true-addr or --batch-id, not both")
    if known_true_addr:
        return "known_true_addr", validate_known_true_addr(known_true_addr)
    if batch_id:
        value = batch_id.strip()
        if not value:
            raise RegistryStatusError("batch_id must not be empty")
        return "batch_id", value
    raise RegistryStatusError("provide --known-true-addr or --batch-id")


def _counter_dict(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items(), key=lambda item: item[0]))


def _is_execution_batch(record: RegistryRecord) -> bool:
    raw = record.raw_fields
    if _as_bool(raw.get("execution_batch")) is True:
        return True
    transaction_type = (record.transaction_type or "").strip().lower()
    if transaction_type and transaction_type != "detect_only":
        return True
    execution_outcome = (record.execution_outcome or "").strip().lower()
    if execution_outcome and execution_outcome not in {"execution_disabled", "none", "disabled"}:
        return True
    execution_mode = _as_str(raw.get("execution_mode"))
    if execution_mode and execution_mode.strip().lower() not in {"disabled", "none"}:
        return True
    return False


def _summary_conclusion(data: RegistryData) -> str:
    if not data.registry_exists:
        return "REGISTRY_MISSING"
    if data.total_lines == 0:
        return "REGISTRY_EMPTY"
    if data.malformed_lines:
        return "REGISTRY_PARSE_WARN"
    return "REGISTRY_OK"


def _summary_recommendation(conclusion: str) -> str:
    if conclusion == "REGISTRY_MISSING":
        return "Registry file does not exist; no read-only registry records are available."
    if conclusion == "REGISTRY_EMPTY":
        return "Registry file is empty; append records through the existing PowerShell classifier workflow when intentional."
    if conclusion == "REGISTRY_PARSE_WARN":
        return "Some registry JSONL lines could not be parsed; review warnings while using parsed records."
    if conclusion == "REGISTRY_OK":
        return "Registry parsed successfully."
    return "Review registry state."


def _show_recommendation(conclusion: str) -> str:
    if conclusion == "REGISTRY_MATCH_FOUND":
        return "Matching registry record(s) found."
    if conclusion == "REGISTRY_NO_MATCH":
        return "No matching registry record found for the query."
    return _summary_recommendation(conclusion)
