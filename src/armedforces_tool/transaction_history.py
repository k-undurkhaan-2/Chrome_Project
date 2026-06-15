from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .logs import DEFAULT_LOG_ROOT, LogParseError, parse_latest_summaries
from .registry_status import DEFAULT_REGISTRY_PATH, RegistryRecord, parse_registry, validate_known_true_addr
from .safety import DEFAULT_PROJECT_ROOT

KNOWN_TRANSACTION_TYPES = {
    "detect_only",
    "dry_run",
    "write_success",
    "write_blocked",
    "restore_success",
    "restore_blocked",
    "unknown",
}


class TransactionHistoryError(RuntimeError):
    """Raised for user-facing transaction history errors."""


@dataclass(frozen=True)
class TransactionRecord:
    index: int
    batch_id: str | None
    known_true_addr: str | None
    profile: str
    classification: str
    baseline_eligible: str | None
    execution_outcome: str
    transaction_type: str
    transaction_status: str
    created_at: str | None
    source: str
    source_log: str | None
    source_registry_line: int | None
    execution_enabled: str | None
    write_enabled: str | None
    execution_confirm: str | None
    execution_write_request_id: str | None
    execution_armed_at_utc: str | None
    execution_arm_expires_at_utc: str | None
    restore_source_batch_execution_addr: str | None
    warnings: list[str]

    def to_dict(self) -> dict[str, object | None]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class TransactionSummaryResult:
    project_root: str
    log_root: str
    registry_path: str
    latest_n: int
    profile_filter: str
    transaction_type_filter: str
    parsed_batches: int
    parsed_registry_records: int
    transaction_record_count: int
    transaction_type_counts: dict[str, int]
    execution_outcome_counts: dict[str, int]
    write_success_count: int
    write_blocked_count: int
    restore_success_count: int
    restore_blocked_count: int
    dry_run_count: int
    detect_only_count: int
    unknown_transaction_count: int
    latest_transaction_batch_id: str | None
    latest_transaction_type: str | None
    latest_known_true_addr: str | None
    conclusion: str
    recommendation: str
    warnings: list[str]

    def to_dict(self) -> dict[str, object | None]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class TransactionListResult:
    project_root: str
    log_root: str
    registry_path: str
    latest_n: int
    profile_filter: str
    transaction_type_filter: str
    limit: int
    parsed_batches: int
    parsed_registry_records: int
    transaction_record_count: int
    conclusion: str
    recommendation: str
    records: list[TransactionRecord]
    warnings: list[str]

    def to_dict(self) -> dict[str, object | None]:
        return {
            "project_root": self.project_root,
            "log_root": self.log_root,
            "registry_path": self.registry_path,
            "latest_n": self.latest_n,
            "profile_filter": self.profile_filter,
            "transaction_type_filter": self.transaction_type_filter,
            "limit": self.limit,
            "parsed_batches": self.parsed_batches,
            "parsed_registry_records": self.parsed_registry_records,
            "transaction_record_count": self.transaction_record_count,
            "conclusion": self.conclusion,
            "recommendation": self.recommendation,
            "records": [record.to_dict() for record in self.records],
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class TransactionShowResult:
    project_root: str
    log_root: str
    registry_path: str
    query_type: str
    query_value: str
    profile_filter: str
    transaction_type_filter: str
    matched_count: int
    conclusion: str
    recommendation: str
    latest_matching_record: dict[str, object | None] | None
    records: list[dict[str, object | None]]
    warnings: list[str]

    def to_dict(self) -> dict[str, object | None]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class _TransactionData:
    project_root: str
    log_root: str
    registry_path: str
    latest_n: int
    profile_filter: str
    transaction_type_filter: str
    parsed_batches: int
    parsed_registry_records: int
    records: list[TransactionRecord]
    warnings: list[str]


def analyze_transaction_summary(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    log_root: Path = DEFAULT_LOG_ROOT,
    registry: Path = DEFAULT_REGISTRY_PATH,
    latest: int = 100,
    profile: str = "all",
    transaction_type: str = "all",
) -> TransactionSummaryResult:
    data = _load_transaction_data(
        project_root=project_root,
        log_root=log_root,
        registry=registry,
        latest=latest,
        profile=profile,
        transaction_type=transaction_type,
    )
    latest_record = data.records[-1] if data.records else None
    transaction_counts = _counter_dict(record.transaction_status for record in data.records)
    outcome_counts = _counter_dict(record.execution_outcome for record in data.records)
    conclusion = _history_conclusion(data)
    return TransactionSummaryResult(
        project_root=data.project_root,
        log_root=data.log_root,
        registry_path=data.registry_path,
        latest_n=data.latest_n,
        profile_filter=data.profile_filter,
        transaction_type_filter=data.transaction_type_filter,
        parsed_batches=data.parsed_batches,
        parsed_registry_records=data.parsed_registry_records,
        transaction_record_count=len(data.records),
        transaction_type_counts=transaction_counts,
        execution_outcome_counts=outcome_counts,
        write_success_count=transaction_counts.get("write_success", 0),
        write_blocked_count=transaction_counts.get("write_blocked", 0),
        restore_success_count=transaction_counts.get("restore_success", 0),
        restore_blocked_count=transaction_counts.get("restore_blocked", 0),
        dry_run_count=transaction_counts.get("dry_run", 0),
        detect_only_count=transaction_counts.get("detect_only", 0),
        unknown_transaction_count=transaction_counts.get("unknown", 0),
        latest_transaction_batch_id=latest_record.batch_id if latest_record else None,
        latest_transaction_type=latest_record.transaction_status if latest_record else None,
        latest_known_true_addr=latest_record.known_true_addr if latest_record else None,
        conclusion=conclusion,
        recommendation=_recommendation(conclusion),
        warnings=data.warnings,
    )


def analyze_transaction_list(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    log_root: Path = DEFAULT_LOG_ROOT,
    registry: Path = DEFAULT_REGISTRY_PATH,
    latest: int = 100,
    profile: str = "all",
    transaction_type: str = "all",
    limit: int = 20,
) -> TransactionListResult:
    if limit < 1:
        raise TransactionHistoryError("--limit must be greater than 0")
    data = _load_transaction_data(
        project_root=project_root,
        log_root=log_root,
        registry=registry,
        latest=latest,
        profile=profile,
        transaction_type=transaction_type,
    )
    records = [
        TransactionRecord(
            index=index,
            batch_id=record.batch_id,
            known_true_addr=record.known_true_addr,
            profile=record.profile,
            classification=record.classification,
            baseline_eligible=record.baseline_eligible,
            execution_outcome=record.execution_outcome,
            transaction_type=record.transaction_type,
            transaction_status=record.transaction_status,
            created_at=record.created_at,
            source=record.source,
            source_log=record.source_log,
            source_registry_line=record.source_registry_line,
            execution_enabled=record.execution_enabled,
            write_enabled=record.write_enabled,
            execution_confirm=record.execution_confirm,
            execution_write_request_id=record.execution_write_request_id,
            execution_armed_at_utc=record.execution_armed_at_utc,
            execution_arm_expires_at_utc=record.execution_arm_expires_at_utc,
            restore_source_batch_execution_addr=record.restore_source_batch_execution_addr,
            warnings=record.warnings,
        )
        for index, record in enumerate(data.records[-limit:], start=1)
    ]
    conclusion = _history_conclusion(data)
    return TransactionListResult(
        project_root=data.project_root,
        log_root=data.log_root,
        registry_path=data.registry_path,
        latest_n=data.latest_n,
        profile_filter=data.profile_filter,
        transaction_type_filter=data.transaction_type_filter,
        limit=limit,
        parsed_batches=data.parsed_batches,
        parsed_registry_records=data.parsed_registry_records,
        transaction_record_count=len(data.records),
        conclusion=conclusion,
        recommendation=_recommendation(conclusion),
        records=records,
        warnings=data.warnings,
    )


def analyze_transaction_show(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    log_root: Path = DEFAULT_LOG_ROOT,
    registry: Path = DEFAULT_REGISTRY_PATH,
    latest: int = 100,
    profile: str = "all",
    transaction_type: str = "all",
    known_true_addr: str | None = None,
    batch_id: str | None = None,
) -> TransactionShowResult:
    query_type, query_value = _normalize_show_query(known_true_addr=known_true_addr, batch_id=batch_id)
    data = _load_transaction_data(
        project_root=project_root,
        log_root=log_root,
        registry=registry,
        latest=latest,
        profile=profile,
        transaction_type=transaction_type,
    )
    if query_type == "known_true_addr":
        matched = [record for record in data.records if _same_addr(record.known_true_addr, query_value)]
    else:
        matched = [record for record in data.records if record.batch_id == query_value]
    if not data.records and any("missing" in warning.lower() for warning in data.warnings):
        conclusion = "TRANSACTION_HISTORY_MISSING"
    elif data.warnings and not matched:
        conclusion = "TRANSACTION_HISTORY_WARN"
    elif matched:
        conclusion = "TRANSACTION_MATCH_FOUND"
    else:
        conclusion = "TRANSACTION_NO_MATCH"
    latest_record = matched[-1].to_dict() if matched else None
    return TransactionShowResult(
        project_root=data.project_root,
        log_root=data.log_root,
        registry_path=data.registry_path,
        query_type=query_type,
        query_value=query_value,
        profile_filter=data.profile_filter,
        transaction_type_filter=data.transaction_type_filter,
        matched_count=len(matched),
        conclusion=conclusion,
        recommendation=_show_recommendation(conclusion),
        latest_matching_record=latest_record,
        records=[record.to_dict() for record in matched],
        warnings=data.warnings,
    )


def validate_transaction_type(value: str | None) -> str:
    normalized = (value or "all").strip().lower()
    if normalized in {"", "all"}:
        return "all"
    if normalized not in KNOWN_TRANSACTION_TYPES - {"unknown"}:
        raise TransactionHistoryError(
            "--transaction-type must be one of detect_only, dry_run, write_success, "
            "write_blocked, restore_success, restore_blocked"
        )
    return normalized


def _load_transaction_data(
    *,
    project_root: Path,
    log_root: Path,
    registry: Path,
    latest: int,
    profile: str,
    transaction_type: str,
) -> _TransactionData:
    if latest < 1:
        raise TransactionHistoryError("--latest must be greater than 0")
    normalized_profile = _normalize_profile(profile)
    normalized_transaction_type = validate_transaction_type(transaction_type)
    warnings: list[str] = []
    records_by_batch: dict[str, TransactionRecord] = {}
    parsed_batches = 0

    try:
        batch_records = parse_latest_summaries(log_root, latest=latest, profile=normalized_profile)
    except LogParseError as exc:
        batch_records = []
        warnings.append(str(exc))
    parsed_batches = len(batch_records)

    registry_data = parse_registry(project_root=project_root, registry=registry)
    parsed_registry_records = len(registry_data.parsed_records)
    if registry_data.malformed_lines:
        warnings.extend(
            f"registry line {line.line_number}: {line.message}" for line in registry_data.malformed_lines
        )
    registry_by_batch = {
        record.batch_id: record
        for record in registry_data.parsed_records
        if record.batch_id and _profile_matches(record.validation_profile, normalized_profile)
    }

    for batch in batch_records:
        registry_record = registry_by_batch.get(batch.batch_id)
        record = _record_from_batch(batch, registry_record=registry_record)
        if _transaction_matches(record.transaction_status, normalized_transaction_type):
            records_by_batch[record.batch_id or f"log:{record.source_log}"] = record

    for registry_record in registry_data.parsed_records:
        if not registry_record.batch_id or registry_record.batch_id in records_by_batch:
            continue
        if not _profile_matches(registry_record.validation_profile, normalized_profile):
            continue
        record = _record_from_registry(registry_record)
        if _transaction_matches(record.transaction_status, normalized_transaction_type):
            records_by_batch[registry_record.batch_id] = record

    records = sorted(records_by_batch.values(), key=lambda record: record.batch_id or "")
    return _TransactionData(
        project_root=str(project_root),
        log_root=str(log_root),
        registry_path=str(registry),
        latest_n=latest,
        profile_filter=normalized_profile,
        transaction_type_filter=normalized_transaction_type,
        parsed_batches=parsed_batches,
        parsed_registry_records=parsed_registry_records,
        records=records,
        warnings=warnings,
    )


def _record_from_batch(batch: object, *, registry_record: RegistryRecord | None) -> TransactionRecord:
    extra = _parse_summary_fields(Path(batch.source_log))
    registry_raw = registry_record.raw_fields if registry_record else {}
    transaction_type = _normalize_transaction_type(
        _first_value(
            batch.transaction_type,
            _as_str(registry_raw.get("transaction_type")),
            _derive_transaction_type(extra, batch.execution_outcome),
        )
    )
    transaction_status = _transaction_status(transaction_type)
    return TransactionRecord(
        index=0,
        batch_id=batch.batch_id,
        known_true_addr=_first_value(batch.known_true_addr, _as_str(registry_raw.get("known_true_addr"))),
        profile=_first_value(batch.validation_profile, _as_str(registry_raw.get("validation_profile")), "unknown") or "unknown",
        classification=_first_value(batch.classification, _as_str(registry_raw.get("classification")), "unknown") or "unknown",
        baseline_eligible=_first_value(batch.baseline_eligible, _as_str(registry_raw.get("baseline_eligible"))),
        execution_outcome=_first_value(batch.execution_outcome, _as_str(registry_raw.get("execution_outcome")), "unknown") or "unknown",
        transaction_type=transaction_type,
        transaction_status=transaction_status,
        created_at=_first_value(_as_str(registry_raw.get("recorded_at")), _as_str(registry_raw.get("created_at"))),
        source="log+registry" if registry_record else "log",
        source_log=batch.source_log,
        source_registry_line=registry_record.line_number if registry_record else None,
        execution_enabled=_first_value(extra.get("execution_enabled"), _as_str(registry_raw.get("execution_enabled"))),
        write_enabled=_first_value(extra.get("write_enabled"), _as_str(registry_raw.get("write_enabled"))),
        execution_confirm=_first_value(extra.get("execution_confirm"), _as_str(registry_raw.get("execution_confirm"))),
        execution_write_request_id=_first_value(
            extra.get("execution_write_request_id"), _as_str(registry_raw.get("execution_write_request_id"))
        ),
        execution_armed_at_utc=_first_value(
            extra.get("execution_armed_at_utc"), _as_str(registry_raw.get("execution_armed_at_utc"))
        ),
        execution_arm_expires_at_utc=_first_value(
            extra.get("execution_arm_expires_at_utc"), _as_str(registry_raw.get("execution_arm_expires_at_utc"))
        ),
        restore_source_batch_execution_addr=_first_value(
            extra.get("restore_source_batch_execution_addr"),
            extra.get("restore_execution_addr"),
            _as_str(registry_raw.get("restore_source_batch_execution_addr")),
            _as_str(registry_raw.get("restore_execution_addr")),
        ),
        warnings=[],
    )


def _record_from_registry(record: RegistryRecord) -> TransactionRecord:
    raw = record.raw_fields
    transaction_type = _normalize_transaction_type(
        _first_value(record.transaction_type, _as_str(raw.get("transaction_type")), _derive_transaction_type_from_raw(raw))
    )
    return TransactionRecord(
        index=0,
        batch_id=record.batch_id,
        known_true_addr=record.known_true_addr,
        profile=record.validation_profile or "unknown",
        classification=record.classification or "unknown",
        baseline_eligible=_as_str(record.baseline_eligible),
        execution_outcome=record.execution_outcome or _as_str(raw.get("execution_outcome")) or "unknown",
        transaction_type=transaction_type,
        transaction_status=_transaction_status(transaction_type),
        created_at=record.created_at,
        source="registry",
        source_log=None,
        source_registry_line=record.line_number,
        execution_enabled=_as_str(raw.get("execution_enabled")),
        write_enabled=_as_str(raw.get("write_enabled")),
        execution_confirm=_as_str(raw.get("execution_confirm")),
        execution_write_request_id=_as_str(raw.get("execution_write_request_id")),
        execution_armed_at_utc=_as_str(raw.get("execution_armed_at_utc")),
        execution_arm_expires_at_utc=_as_str(raw.get("execution_arm_expires_at_utc")),
        restore_source_batch_execution_addr=_first_value(
            _as_str(raw.get("restore_source_batch_execution_addr")),
            _as_str(raw.get("restore_execution_addr")),
        ),
        warnings=record.warnings,
    )


def _parse_summary_fields(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return fields
    for raw_line in lines:
        line = raw_line.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized = _normalize_nullable(value.strip())
        if normalized is not None:
            fields[key.strip()] = normalized
    return fields


def _derive_transaction_type(fields: dict[str, str], execution_outcome: str | None) -> str:
    mode = (fields.get("execution_mode") or "").strip().lower()
    restore_source = _first_value(fields.get("restore_source_batch_id"), fields.get("restore_source_batch_execution_addr"))
    has_restore_source = restore_source is not None
    outcome = (execution_outcome or "").strip().lower()
    if mode in {"", "disabled", "nil", "none"}:
        return "detect_only"
    if mode == "dry_run":
        return "dry_run"
    if outcome == "execution_write_ok" and has_restore_source:
        return "restore_success"
    if outcome == "execution_write_ok":
        return "write_success"
    if outcome == "execution_write_blocked" and has_restore_source:
        return "restore_blocked"
    if outcome == "execution_write_blocked":
        return "write_blocked"
    return "unknown"


def _derive_transaction_type_from_raw(raw: dict[str, object]) -> str:
    mode = (_as_str(raw.get("execution_mode")) or "").strip().lower()
    outcome = (_as_str(raw.get("execution_outcome")) or "").strip().lower()
    has_restore_source = _first_value(_as_str(raw.get("restore_source_batch_id")), _as_str(raw.get("restore_execution_addr"))) is not None
    if mode in {"", "disabled", "nil", "none"}:
        return "detect_only"
    if mode == "dry_run":
        return "dry_run"
    if outcome == "execution_write_ok" and has_restore_source:
        return "restore_success"
    if outcome == "execution_write_ok":
        return "write_success"
    if outcome == "execution_write_blocked" and has_restore_source:
        return "restore_blocked"
    if outcome == "execution_write_blocked":
        return "write_blocked"
    return "unknown"


def _transaction_status(transaction_type: str | None) -> str:
    normalized = _normalize_transaction_type(transaction_type)
    return normalized if normalized in KNOWN_TRANSACTION_TYPES else "unknown"


def _normalize_transaction_type(transaction_type: str | None) -> str:
    normalized = _normalize_nullable(transaction_type)
    if normalized is None:
        return "unknown"
    normalized = normalized.strip().lower()
    return normalized if normalized in KNOWN_TRANSACTION_TYPES else "unknown"


def _transaction_matches(transaction_status: str, filter_value: str) -> bool:
    return filter_value == "all" or transaction_status == filter_value


def _normalize_profile(profile: str | None) -> str:
    normalized = (profile or "all").strip().lower()
    if normalized in {"", "all"}:
        return "all"
    if normalized not in {"full", "quick"}:
        raise TransactionHistoryError("--profile must be one of all, full, quick")
    return normalized


def _profile_matches(record_profile: str | None, filter_profile: str) -> bool:
    if filter_profile == "all":
        return True
    return (record_profile or "").strip().lower() == filter_profile


def _normalize_show_query(*, known_true_addr: str | None, batch_id: str | None) -> tuple[str, str]:
    if known_true_addr and batch_id:
        raise TransactionHistoryError("provide either --known-true-addr or --batch-id, not both")
    if known_true_addr:
        try:
            return "known_true_addr", validate_known_true_addr(known_true_addr)
        except Exception as exc:
            raise TransactionHistoryError(str(exc)) from exc
    if batch_id:
        value = batch_id.strip()
        if not value:
            raise TransactionHistoryError("batch_id must not be empty")
        return "batch_id", value
    raise TransactionHistoryError("provide --known-true-addr or --batch-id")


def _same_addr(left: str | None, right: str) -> bool:
    if left is None:
        return False
    candidate = left.strip()
    if not re.fullmatch(r"0x[0-9A-Fa-f]+", candidate):
        return False
    return ("0x" + candidate[2:].upper()) == right


def _counter_dict(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items(), key=lambda item: item[0]))


def _history_conclusion(data: _TransactionData) -> str:
    if not data.records and any("does not exist" in warning or "missing" in warning.lower() for warning in data.warnings):
        return "TRANSACTION_HISTORY_MISSING"
    if not data.records:
        return "TRANSACTION_HISTORY_EMPTY"
    if data.warnings:
        return "TRANSACTION_HISTORY_WARN"
    return "TRANSACTION_HISTORY_OK"


def _recommendation(conclusion: str) -> str:
    if conclusion == "TRANSACTION_HISTORY_OK":
        return "Transaction history parsed successfully."
    if conclusion == "TRANSACTION_HISTORY_EMPTY":
        return "No transaction records found in the selected read-only sources."
    if conclusion == "TRANSACTION_HISTORY_WARN":
        return "Transaction history parsed with warnings; review source availability and malformed records."
    if conclusion == "TRANSACTION_HISTORY_MISSING":
        return "No readable transaction sources were found."
    return "Review transaction history state."


def _show_recommendation(conclusion: str) -> str:
    if conclusion == "TRANSACTION_MATCH_FOUND":
        return "Matching transaction record(s) found."
    if conclusion == "TRANSACTION_NO_MATCH":
        return "No matching transaction record found for the query."
    if conclusion == "TRANSACTION_HISTORY_WARN":
        return "Transaction history parsed with warnings; query did not produce a clean match."
    return _recommendation(conclusion)


def _first_value(*values: object | None) -> str | None:
    for value in values:
        normalized = _normalize_nullable(value)
        if normalized is not None:
            return normalized
    return None


def _normalize_nullable(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "-", "nil", "None", "null"}:
        return None
    return text


def _as_str(value: object | None) -> str | None:
    return _normalize_nullable(value)
