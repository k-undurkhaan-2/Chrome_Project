from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_LOG_ROOT = Path(r"D:\armedforces.io-v2\log\auto_output")

SUMMARY_NAME_RE = re.compile(r"^(?P<batch_id>\d{8}-\d{6})__summary\.txt$")


class LogParseError(RuntimeError):
    """Raised for user-facing read-only log parsing errors."""


@dataclass(frozen=True)
class BatchSummaryRecord:
    batch_id: str
    classification: str
    validation_profile: str
    known_true_addr: str | None
    final_hit: bool | None
    rank_AWB: str
    stable_rank: str | None
    best_candidate: str | None
    baseline_eligible: str | None
    execution_outcome: str
    transaction_type: str

    def to_dict(self) -> dict[str, object | None]:
        return {
            "batch_id": self.batch_id,
            "classification": self.classification,
            "validation_profile": self.validation_profile,
            "known_true_addr": self.known_true_addr,
            "final_hit": self.final_hit,
            "rank_AWB": self.rank_AWB,
            "stable_rank": self.stable_rank,
            "best_candidate": self.best_candidate,
            "baseline_eligible": self.baseline_eligible,
            "execution_outcome": self.execution_outcome,
            "transaction_type": self.transaction_type,
        }


def discover_summary_files(log_root: Path) -> list[Path]:
    if not log_root.exists():
        raise LogParseError(f"log root does not exist: {log_root}")
    if not log_root.is_dir():
        raise LogParseError(f"log root is not a directory: {log_root}")

    files = [path for path in log_root.iterdir() if path.is_file() and SUMMARY_NAME_RE.match(path.name)]
    return sorted(files, key=lambda path: _batch_id_from_path(path), reverse=True)


def parse_latest_summaries(log_root: Path, latest: int, profile: str = "all") -> list[BatchSummaryRecord]:
    records: list[BatchSummaryRecord] = []
    for path in discover_summary_files(log_root):
        record = parse_summary_file(path)
        if profile != "all" and record.validation_profile != profile:
            continue
        records.append(record)
        if len(records) >= latest:
            break
    return records


def parse_summary_file(path: Path) -> BatchSummaryRecord:
    batch_id = _batch_id_from_path(path)
    sections = _parse_key_value_sections(path.read_text(encoding="utf-8", errors="replace").splitlines())

    stable = _find_section(sections, "stable_no_probe_intersection")
    no_probe_a = _find_section(sections, "no_probe_A")
    with_probe = _find_section(sections, "with_probe")
    no_probe_b = _find_section(sections, "no_probe_B")
    all_sections = [section for _, section in sections]

    validation_profile = _first_present(
        stable.get("validation_profile") if stable else None,
        no_probe_a.get("validation_profile") if no_probe_a else None,
        _find_first_value(all_sections, "validation_profile"),
    ) or "full"
    known_true_addr = _first_present(
        stable.get("known_true_addr") if stable else None,
        no_probe_a.get("known_true_addr") if no_probe_a else None,
        _find_first_value(all_sections, "known_true_addr"),
    )
    best_candidate = _first_present(
        stable.get("stable_intersection_best_candidate") if stable else None,
        stable.get("best_candidate") if stable else None,
        _find_last_value(all_sections, "best_candidate"),
    )
    stable_rank = _first_present(
        stable.get("stable_intersection_known_true_rank_position") if stable else None,
        stable.get("known_true_rank_position") if stable else None,
    )
    rank_awb = "/".join(
        _normalize_value(section.get("known_true_rank_position") if section else None) or "nil"
        for section in (no_probe_a, with_probe, no_probe_b)
    )

    execution_outcome = _execution_outcome(stable or no_probe_a or {})
    transaction_type = _transaction_type(stable or no_probe_a or {}, execution_outcome)
    final_hit = _address_equal(best_candidate, known_true_addr)

    target_pattern = _first_present(
        stable.get("target_value_pattern") if stable else None,
        _find_first_value(all_sections, "target_value_pattern"),
    )
    target_float = _first_present(
        stable.get("target_value_float") if stable else None,
        _find_first_value(all_sections, "target_value_float"),
    )
    config_mismatch = _target_config_mismatch(target_pattern, target_float)
    run_valid = _first_present(stable.get("run_valid") if stable else None, _find_first_value(all_sections, "run_valid"))
    collector_empty = _first_present(
        stable.get("collector_empty") if stable else None,
        _find_first_value(all_sections, "collector_empty"),
    )
    failure_class = _first_present(
        stable.get("failure_class") if stable else None,
        _find_first_value(all_sections, "failure_class"),
    )

    classification = _classify_summary(
        validation_profile=validation_profile,
        stable_rank=stable_rank,
        best_candidate=best_candidate,
        known_true_addr=known_true_addr,
        rank_awb=rank_awb,
        run_valid=run_valid,
        collector_empty=collector_empty,
        failure_class=failure_class,
        config_mismatch=config_mismatch,
        execution_outcome=execution_outcome,
    )

    baseline_eligible = _first_present(
        stable.get("baseline_eligible") if stable else None,
        no_probe_a.get("baseline_eligible") if no_probe_a else None,
        _find_first_value(all_sections, "baseline_eligible"),
    )
    if classification in {"invalid_config_mismatch", "stale_known_true_addr"} or execution_outcome != "execution_disabled":
        baseline_eligible = "false"

    return BatchSummaryRecord(
        batch_id=batch_id,
        classification=classification,
        validation_profile=validation_profile,
        known_true_addr=known_true_addr,
        final_hit=final_hit,
        rank_AWB=rank_awb,
        stable_rank=_normalize_value(stable_rank),
        best_candidate=best_candidate,
        baseline_eligible=_normalize_value(baseline_eligible),
        execution_outcome=execution_outcome,
        transaction_type=transaction_type,
    )


def _parse_key_value_sections(lines: Iterable[str]) -> list[tuple[str, dict[str, str]]]:
    sections: list[tuple[str, dict[str, str]]] = []
    current_name = "batch"
    current: dict[str, str] = {}

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("---") and line.endswith("---"):
            if current:
                sections.append((current_name, current))
            current_name = line.strip("- ").strip()
            current = {}
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            current[key.strip()] = value.strip()

    if current:
        sections.append((current_name, current))
    return sections


def _find_section(sections: list[tuple[str, dict[str, str]]], name_fragment: str) -> dict[str, str] | None:
    for name, values in sections:
        if name_fragment in name:
            return values
    return None


def _find_first_value(sections: list[dict[str, str]], key: str) -> str | None:
    for section in sections:
        value = section.get(key)
        if _present(value):
            return value
    return None


def _find_last_value(sections: list[dict[str, str]], key: str) -> str | None:
    for section in reversed(sections):
        value = section.get(key)
        if _present(value):
            return value
    return None


def _first_present(*values: str | None) -> str | None:
    for value in values:
        if _present(value):
            return value
    return None


def _present(value: str | None) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return text not in {"", "-", "nil", "None"}


def _normalize_value(value: str | None) -> str | None:
    return str(value).strip() if _present(value) else None


def _address_equal(left: str | None, right: str | None) -> bool | None:
    if not _present(left) or not _present(right):
        return None
    return str(left).strip().lower() == str(right).strip().lower()


def _text_true(value: str | None) -> bool:
    return str(value).strip().lower() == "true" if value is not None else False


def _execution_outcome(section: dict[str, str]) -> str:
    mode = section.get("execution_mode") or "disabled"
    if mode in {"", "nil", "disabled"}:
        return "execution_disabled"

    write_attempted = _text_true(section.get("write_attempted"))
    write_ok = _text_true(section.get("write_ok"))
    readback_ok = _text_true(section.get("readback_ok"))
    preconditions_ok = _text_true(section.get("execution_preconditions_ok"))
    failure_class = section.get("execution_failure_class")

    if mode == "dry_run" and preconditions_ok and not write_attempted:
        return "execution_dry_run_ready"
    if mode == "write" and not write_attempted:
        return "execution_write_blocked"
    if mode == "write" and write_attempted and write_ok and readback_ok:
        return "execution_write_ok"
    if write_attempted and not readback_ok:
        return "execution_readback_failed"
    if _present(failure_class):
        return "execution_failed"
    return "execution_unknown"


def _transaction_type(section: dict[str, str], execution_outcome: str) -> str:
    mode = section.get("execution_mode") or "disabled"
    restore_source = section.get("restore_source_batch_id")
    has_restore_source = _present(restore_source)

    if mode in {"", "nil", "disabled"}:
        return "detect_only"
    if mode == "dry_run":
        return "dry_run"
    if execution_outcome == "execution_write_ok" and has_restore_source:
        return "restore_success"
    if execution_outcome == "execution_write_ok":
        return "write_success"
    if execution_outcome == "execution_write_blocked" and has_restore_source:
        return "restore_blocked"
    if execution_outcome == "execution_write_blocked":
        return "write_blocked"
    return "unknown"


def _classify_summary(
    *,
    validation_profile: str,
    stable_rank: str | None,
    best_candidate: str | None,
    known_true_addr: str | None,
    rank_awb: str,
    run_valid: str | None,
    collector_empty: str | None,
    failure_class: str | None,
    config_mismatch: bool,
    execution_outcome: str,
) -> str:
    if config_mismatch:
        return "invalid_config_mismatch"
    if run_valid == "false" or collector_empty == "true" or failure_class == "collector_runtime_empty":
        return "collector_runtime_empty"
    if validation_profile == "quick":
        return "quick_success" if _address_equal(best_candidate, known_true_addr) else "quick_failure"
    if stable_rank == "1" and _address_equal(best_candidate, known_true_addr):
        return "success"
    if (
        execution_outcome == "execution_disabled"
        and _present(best_candidate)
        and _present(known_true_addr)
        and not _address_equal(best_candidate, known_true_addr)
    ):
        return "stale_known_true_addr"
    if rank_awb == "1/1/1" and not _address_equal(best_candidate, known_true_addr):
        return "ranking_issue"
    return "other"


def _target_config_mismatch(pattern: str | None, float_text: str | None) -> bool:
    if not _present(pattern) or not _present(float_text):
        return False
    expected = _float_to_u32_pattern(float_text)
    if expected is None:
        return False
    actual = str(pattern).strip().upper()
    if not actual.startswith("0X"):
        actual = "0x" + actual
    return actual.upper() != expected.upper()


def _float_to_u32_pattern(float_text: str) -> str | None:
    try:
        value = float(float_text)
    except ValueError:
        return None
    bits = struct.unpack(">I", struct.pack(">f", value))[0]
    return f"0x{bits:08X}"


def _batch_id_from_path(path: Path) -> str:
    match = SUMMARY_NAME_RE.match(path.name)
    if not match:
        raise LogParseError(f"not a batch summary file: {path}")
    return match.group("batch_id")
