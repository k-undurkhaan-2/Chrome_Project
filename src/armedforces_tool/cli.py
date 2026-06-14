from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .logs import DEFAULT_LOG_ROOT, BatchSummaryRecord, LogParseError, parse_batch_summary, parse_latest_summaries
from .parity import parity_latest


def _add_logs_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    logs_parser = subparsers.add_parser("logs", help="Read-only batch log helpers")
    logs_subparsers = logs_parser.add_subparsers(dest="logs_command", required=True)

    parse_latest = logs_subparsers.add_parser(
        "parse-latest",
        help="Parse latest batch summary logs without writing files",
    )
    parse_latest.add_argument("--latest", type=int, default=5, help="Number of latest summary logs to inspect")
    parse_latest.add_argument(
        "--profile",
        choices=("all", "full", "quick"),
        default="all",
        help="Validation profile filter",
    )
    parse_latest.add_argument(
        "--log-root",
        default=str(DEFAULT_LOG_ROOT),
        help="Directory containing *_summary.txt batch logs",
    )
    parse_latest.add_argument("--json", action="store_true", help="Emit JSON array")
    parse_latest.set_defaults(func=_run_logs_parse_latest)

    parse_batch = logs_subparsers.add_parser(
        "parse-batch",
        help="Parse one batch summary log without writing files",
    )
    parse_batch.add_argument("--batch-id", required=True, help="Batch id in YYYYMMDD-HHMMSS format")
    parse_batch.add_argument(
        "--log-root",
        default=str(DEFAULT_LOG_ROOT),
        help="Directory containing *_summary.txt batch logs",
    )
    parse_batch.add_argument("--json", action="store_true", help="Emit JSON object")
    parse_batch.set_defaults(func=_run_logs_parse_batch)

    parity = logs_subparsers.add_parser(
        "parity-latest",
        help="Compare Python parser output with the read-only PowerShell classifier console summary",
    )
    parity.add_argument("--latest", type=int, default=5, help="Number of latest summary logs to inspect")
    parity.add_argument(
        "--profile",
        choices=("full", "quick"),
        default="full",
        help="Validation profile filter",
    )
    parity.add_argument(
        "--log-root",
        default=str(DEFAULT_LOG_ROOT),
        help="Directory containing *_summary.txt batch logs",
    )
    parity.add_argument("--json", action="store_true", help="Emit JSON object")
    parity.set_defaults(func=_run_logs_parity_latest)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="armedforces_tool",
        description="Read-only Python CLI skeleton for armedforces.io-v2 tooling migration.",
    )
    parser.add_argument("--version", action="version", version="armedforces-tool 0.1.0")

    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_logs_parser(subparsers)
    return parser


def _run_logs_parse_latest(args: argparse.Namespace) -> int:
    if args.latest < 1:
        raise LogParseError("--latest must be greater than 0")

    records = parse_latest_summaries(
        log_root=Path(args.log_root),
        latest=args.latest,
        profile=args.profile,
    )
    if args.json:
        print(json.dumps([record.to_dict() for record in records], indent=2))
    else:
        print(format_records_table(records))
    return 0


def _run_logs_parse_batch(args: argparse.Namespace) -> int:
    record = parse_batch_summary(log_root=Path(args.log_root), batch_id=args.batch_id)
    if args.json:
        print(json.dumps(record.to_dict(), indent=2))
    else:
        print(format_record_detail(record))
    return 0


def _run_logs_parity_latest(args: argparse.Namespace) -> int:
    if args.latest < 1:
        raise LogParseError("--latest must be greater than 0")

    result = parity_latest(
        log_root=Path(args.log_root),
        latest=args.latest,
        profile=args.profile,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_parity_result(result))
    return 0 if result.parity_status == "PASS" else 1


def format_records_table(records: Sequence[BatchSummaryRecord]) -> str:
    headers = [
        "batch_id",
        "classification",
        "profile",
        "baseline",
        "final_hit",
        "rank_AWB",
        "stable",
        "known_true_addr",
        "best_candidate",
        "transaction",
        "execution",
    ]
    rows = []
    for record in records:
        data = record.to_dict()
        rows.append(
            [
                str(data.get("batch_id") or "-"),
                str(data.get("classification") or "-"),
                str(data.get("validation_profile") or "-"),
                str(data.get("baseline_eligible") or "-"),
                str(data.get("final_hit") if data.get("final_hit") is not None else "-"),
                str(data.get("rank_AWB") or "-"),
                str(data.get("stable_rank") or "-"),
                str(data.get("known_true_addr") or "-"),
                str(data.get("best_candidate") or "-"),
                str(data.get("transaction_type") or "-"),
                str(data.get("execution_outcome") or "-"),
            ]
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    lines = [
        " ".join(header.ljust(widths[index]) for index, header in enumerate(headers)),
        " ".join("-" * widths[index] for index in range(len(headers))),
    ]
    for row in rows:
        lines.append(" ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
    if not rows:
        lines.append("(no records)")
    return "\n".join(lines)


def format_record_detail(record: BatchSummaryRecord) -> str:
    data = record.to_dict()
    rows = [(key, data.get(key)) for key in data]
    width = max(len(key) for key, _ in rows)
    lines = ["Batch Summary", "-------------"]
    for key, value in rows:
        lines.append(f"{key.ljust(width)}  {_display_value(value)}")
    return "\n".join(lines)


def format_parity_result(result: object) -> str:
    data = result.to_dict()
    summary_rows = [
        ("parity_status", data["parity_status"]),
        ("compared_batch_count", data["compared_batch_count"]),
        ("mismatch_count", data["mismatch_count"]),
    ]
    width = max(len(key) for key, _ in summary_rows)
    lines = ["Parser Parity", "-------------"]
    for key, value in summary_rows:
        lines.append(f"{key.ljust(width)}  {_display_value(value)}")

    mismatches = data["mismatches"]
    if mismatches:
        headers = ["batch_id", "field", "python", "powershell"]
        rows = [
            [
                str(item.get("batch_id") or "-"),
                str(item.get("field") or "-"),
                _display_value(item.get("python_value")),
                _display_value(item.get("powershell_value")),
            ]
            for item in mismatches
        ]
        widths = [len(header) for header in headers]
        for row in rows:
            for index, value in enumerate(row):
                widths[index] = max(widths[index], len(value))
        lines.append("")
        lines.append("Mismatches")
        lines.append("----------")
        lines.append(" ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
        lines.append(" ".join("-" * widths[index] for index in range(len(headers))))
        for row in rows:
            lines.append(" ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
    return "\n".join(lines)


def _display_value(value: object | None) -> str:
    return "-" if value is None else str(value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        return args.func(args)
    except LogParseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
