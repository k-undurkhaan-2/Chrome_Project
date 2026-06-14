from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .logs import DEFAULT_LOG_ROOT, LogParseError, parse_latest_summaries


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


def format_records_table(records: Sequence[object]) -> str:
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
