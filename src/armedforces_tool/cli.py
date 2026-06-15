from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .baseline_status import (
    DEFAULT_BASELINE_DIR,
    analyze_baseline_compare,
    analyze_baseline_current,
    analyze_baseline_list,
    baseline_compare_parity,
    baseline_current_parity,
    baseline_list_parity,
)
from .case_library import analyze_case_library, case_library_parity
from .case_summary import DEFAULT_BASELINE_PATH, analyze_case_summary, case_summary_parity
from .logs import DEFAULT_LOG_ROOT, BatchSummaryRecord, LogParseError, parse_batch_summary, parse_latest_summaries
from .parity import parity_latest
from .sample_plan import analyze_retest_queue, analyze_sample_plan, retest_queue_parity, sample_plan_parity
from .safety import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_PROJECT_ROOT,
    analyze_safety_doctor,
    analyze_safety_execution_status,
    analyze_safety_plan,
    analyze_safety_status,
    safety_doctor_parity,
    safety_execution_status_parity,
    safety_plan_parity,
    safety_status_parity,
)
from .stable_cases import analyze_stable_cases, filter_stable_case_result, stable_cases_parity
from .status_overview import analyze_status_overview
from .workflow_status import (
    DEFAULT_ACTIVE_SESSION_PATH,
    DEFAULT_CASE_INTAKE_PATH,
    DEFAULT_SESSION_HISTORY_PATH,
    analyze_case_intake_status,
    analyze_diagnostic_status,
    case_intake_status_parity,
    diagnostic_status_parity,
)


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


def _add_case_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    case_parser = subparsers.add_parser("case", help="Read-only case analysis helpers")
    case_subparsers = case_parser.add_subparsers(dest="case_command", required=True)

    summary = case_subparsers.add_parser(
        "summary",
        help="Summarize baseline-eligible case coverage without writing files",
    )
    _add_case_summary_args(summary)
    summary.set_defaults(func=_run_case_summary)

    parity = case_subparsers.add_parser(
        "summary-parity",
        help="Compare Python case summary output with the read-only PowerShell case-summary command",
    )
    _add_case_summary_args(parity)
    parity.set_defaults(func=_run_case_summary_parity)

    library = case_subparsers.add_parser(
        "library",
        help="Summarize historical known_true_addr evidence without writing files",
    )
    _add_case_library_args(library)
    library.set_defaults(func=_run_case_library)

    library_parity = case_subparsers.add_parser(
        "library-parity",
        help="Compare Python case library output with the read-only PowerShell case-library command",
    )
    _add_case_library_args(library_parity)
    library_parity.set_defaults(func=_run_case_library_parity)

    stable = case_subparsers.add_parser(
        "stable-cases",
        help="List stable baseline candidate evidence without writing files",
    )
    _add_stable_cases_args(stable, include_detail_filters=True)
    stable.set_defaults(func=_run_case_stable_cases)

    stable_alias = case_subparsers.add_parser(
        "baseline-candidates",
        help="Alias for stable-cases",
    )
    _add_stable_cases_args(stable_alias, include_detail_filters=True)
    stable_alias.set_defaults(func=_run_case_stable_cases)

    stable_parity = case_subparsers.add_parser(
        "stable-cases-parity",
        help="Compare Python stable-cases output with the read-only PowerShell stable-cases command",
    )
    _add_stable_cases_args(stable_parity, include_detail_filters=False)
    stable_parity.set_defaults(func=_run_case_stable_cases_parity)

    retest = case_subparsers.add_parser(
        "retest-queue",
        help="Plan read-only retests from rejected stable-case evidence",
    )
    _add_sample_plan_args(retest)
    retest.set_defaults(func=_run_case_retest_queue)

    sample = case_subparsers.add_parser(
        "sample-plan",
        help="Build a read-only current-session sample acquisition plan",
    )
    _add_sample_plan_args(sample)
    sample.set_defaults(func=_run_case_sample_plan)

    retest_parity = case_subparsers.add_parser(
        "retest-queue-parity",
        help="Compare Python retest queue output with the read-only PowerShell retest-queue command",
    )
    _add_sample_plan_args(retest_parity, include_active_session=False)
    retest_parity.set_defaults(func=_run_case_retest_queue_parity)

    sample_parity = case_subparsers.add_parser(
        "sample-plan-parity",
        help="Compare Python sample-plan output with the read-only PowerShell sample-plan command",
    )
    _add_sample_plan_args(sample_parity, include_active_session=False)
    sample_parity.set_defaults(func=_run_case_sample_plan_parity)


def _add_case_summary_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--latest", type=int, default=20, help="Number of baseline-eligible batches to inspect")
    parser.add_argument(
        "--profile",
        choices=("all", "full", "quick"),
        default="full",
        help="Validation profile filter",
    )
    parser.add_argument(
        "--baseline",
        default=str(DEFAULT_BASELINE_PATH),
        help="Baseline Markdown file used to infer target unique known_true_addr count",
    )
    parser.add_argument(
        "--target-unique",
        type=int,
        default=None,
        help="Target unique known_true_addr count when no baseline count is available",
    )
    parser.add_argument(
        "--log-root",
        default=str(DEFAULT_LOG_ROOT),
        help="Directory containing *_summary.txt batch logs",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON object")


def _add_case_library_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--latest", type=int, default=100, help="Number of latest batches to inspect")
    parser.add_argument(
        "--profile",
        choices=("all", "full", "quick"),
        default="all",
        help="Validation profile filter",
    )
    parser.add_argument(
        "--log-root",
        default=str(DEFAULT_LOG_ROOT),
        help="Directory containing batch log artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON object")


def _add_stable_cases_args(parser: argparse.ArgumentParser, *, include_detail_filters: bool) -> None:
    parser.add_argument("--latest", type=int, default=100, help="Number of latest profile-matching batches to inspect")
    parser.add_argument(
        "--profile",
        choices=("full", "quick"),
        default="full",
        help="Validation profile filter",
    )
    parser.add_argument(
        "--min-full-success",
        type=int,
        default=2,
        help="Minimum full success count required for a stable candidate",
    )
    parser.add_argument(
        "--target-unique",
        type=int,
        default=13,
        help="Target stable unique known_true_addr count",
    )
    parser.add_argument(
        "--log-root",
        default=str(DEFAULT_LOG_ROOT),
        help="Directory containing batch log artifacts",
    )
    if include_detail_filters:
        parser.add_argument("--show-rejected", action="store_true", help="Include rejected addresses in the table")
        parser.add_argument("--known-true-addr", default=None, help="Show detailed evaluation for one address")
    parser.add_argument("--json", action="store_true", help="Emit JSON object")


def _add_sample_plan_args(parser: argparse.ArgumentParser, *, include_active_session: bool = True) -> None:
    parser.add_argument("--latest", type=int, default=100, help="Number of latest profile-matching batches to inspect")
    parser.add_argument(
        "--profile",
        choices=("full", "quick"),
        default="full",
        help="Validation profile filter",
    )
    parser.add_argument(
        "--target-unique",
        type=int,
        default=13,
        help="Target stable unique known_true_addr count",
    )
    parser.add_argument(
        "--min-full-success",
        type=int,
        default=2,
        help="Minimum full success count required for a stable candidate",
    )
    parser.add_argument("--limit", type=int, default=10, help="Maximum rows to display")
    parser.add_argument(
        "--log-root",
        default=str(DEFAULT_LOG_ROOT),
        help="Directory containing batch log artifacts",
    )
    if include_active_session:
        parser.add_argument(
            "--active-session",
            action="store_true",
            help="Allow current-session reuse hints from read-only session/intake files",
        )
    parser.add_argument("--json", action="store_true", help="Emit JSON object")


def _add_safety_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    safety_parser = subparsers.add_parser("safety", help="Read-only safety and next-run status helpers")
    safety_subparsers = safety_parser.add_subparsers(dest="safety_command", required=True)

    status = safety_subparsers.add_parser("status", help="Read local config safety state without writing files")
    _add_safety_common_args(status)
    status.set_defaults(func=_run_safety_status)

    doctor = safety_subparsers.add_parser(
        "doctor",
        help="Aggregate read-only Python safety, log, baseline, and parser checks",
    )
    _add_safety_doctor_args(doctor)
    doctor.set_defaults(func=_run_safety_doctor)

    plan = safety_subparsers.add_parser("plan", help="Infer next-run risk from local config without writing files")
    _add_safety_common_args(plan)
    plan.set_defaults(func=_run_safety_plan)

    execution_status = safety_subparsers.add_parser(
        "execution-status",
        help="Read execution arm and write guard state without writing files",
    )
    _add_safety_common_args(execution_status)
    execution_status.set_defaults(func=_run_safety_execution_status)

    status_parity = safety_subparsers.add_parser(
        "status-parity",
        help="Coarsely compare Python safety status with read-only PowerShell doctor",
    )
    _add_safety_common_args(status_parity)
    status_parity.set_defaults(func=_run_safety_status_parity)

    doctor_parity = safety_subparsers.add_parser(
        "doctor-parity",
        help="Coarsely compare Python safety doctor with read-only PowerShell doctor",
    )
    _add_safety_doctor_args(doctor_parity)
    doctor_parity.set_defaults(func=_run_safety_doctor_parity)

    plan_parity = safety_subparsers.add_parser(
        "plan-parity",
        help="Coarsely compare Python safety plan with read-only PowerShell plan",
    )
    _add_safety_common_args(plan_parity)
    plan_parity.set_defaults(func=_run_safety_plan_parity)

    execution_parity = safety_subparsers.add_parser(
        "execution-status-parity",
        help="Coarsely compare Python execution safety status with read-only PowerShell execution-status",
    )
    _add_safety_common_args(execution_parity)
    execution_parity.set_defaults(func=_run_safety_execution_status_parity)


def _add_safety_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-root",
        default=str(DEFAULT_PROJECT_ROOT),
        help="Active project root used for safety summaries",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Local run_case_config.local.lua path to parse read-only",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON object")


def _add_status_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    status_parser = subparsers.add_parser("status", help="Read-only workflow status helpers")
    status_subparsers = status_parser.add_subparsers(dest="status_command", required=True)

    diagnostic = status_subparsers.add_parser(
        "diagnostic",
        help="Read diagnostic level and safety context without writing config",
    )
    _add_status_common_args(diagnostic)
    diagnostic.set_defaults(func=_run_status_diagnostic)

    case_intake = status_subparsers.add_parser(
        "case-intake",
        help="Read local case intake journal state without writing files",
    )
    _add_status_common_args(case_intake)
    _add_case_intake_args(case_intake)
    case_intake.set_defaults(func=_run_status_case_intake)

    diagnostic_parity = status_subparsers.add_parser(
        "diagnostic-parity",
        help="Coarsely compare Python diagnostic status with read-only PowerShell diagnostic-status",
    )
    _add_status_common_args(diagnostic_parity)
    diagnostic_parity.set_defaults(func=_run_status_diagnostic_parity)

    case_intake_parity = status_subparsers.add_parser(
        "case-intake-parity",
        help="Coarsely compare Python case intake status with read-only PowerShell case-intake-status",
    )
    _add_status_common_args(case_intake_parity)
    _add_case_intake_args(case_intake_parity, include_limit=False)
    case_intake_parity.set_defaults(func=_run_status_case_intake_parity)

    overview = status_subparsers.add_parser(
        "overview",
        help="Aggregate read-only project status across safety, workflow, baseline, and coverage checks",
    )
    _add_status_overview_args(overview)
    overview.set_defaults(func=_run_status_overview)


def _add_baseline_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    baseline_parser = subparsers.add_parser("baseline", help="Read-only baseline status helpers")
    baseline_subparsers = baseline_parser.add_subparsers(dest="baseline_command", required=True)

    list_parser = baseline_subparsers.add_parser("list", help="List local baseline Markdown files without writing files")
    _add_baseline_list_args(list_parser)
    list_parser.set_defaults(func=_run_baseline_list)

    current = baseline_subparsers.add_parser("current", help="Parse the current baseline without writing files")
    _add_baseline_current_args(current)
    current.set_defaults(func=_run_baseline_current)

    compare = baseline_subparsers.add_parser(
        "compare",
        help="Compare latest baseline-eligible logs against a baseline without writing files",
    )
    _add_baseline_compare_args(compare)
    compare.set_defaults(func=_run_baseline_compare)

    list_parity = baseline_subparsers.add_parser(
        "list-parity",
        help="Coarsely compare Python baseline list output with read-only PowerShell baseline-list",
    )
    _add_baseline_list_args(list_parity)
    list_parity.set_defaults(func=_run_baseline_list_parity)

    current_parity = baseline_subparsers.add_parser(
        "current-parity",
        help="Coarsely compare Python baseline current output with read-only PowerShell baseline-current",
    )
    _add_baseline_current_args(current_parity)
    current_parity.set_defaults(func=_run_baseline_current_parity)

    compare_parity = baseline_subparsers.add_parser(
        "compare-parity",
        help="Coarsely compare Python baseline compare output with read-only PowerShell baseline-compare",
    )
    _add_baseline_compare_args(compare_parity)
    compare_parity.set_defaults(func=_run_baseline_compare_parity)


def _add_baseline_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-root",
        default=str(DEFAULT_PROJECT_ROOT),
        help="Active project root used for baseline summaries",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON object")


def _add_baseline_list_args(parser: argparse.ArgumentParser) -> None:
    _add_baseline_common_args(parser)
    parser.add_argument(
        "--baseline-dir",
        default=str(DEFAULT_BASELINE_DIR),
        help="Directory containing baseline Markdown files",
    )
    parser.add_argument(
        "--baseline",
        default=str(DEFAULT_BASELINE_PATH),
        help="Current/default baseline Markdown path",
    )


def _add_baseline_current_args(parser: argparse.ArgumentParser) -> None:
    _add_baseline_common_args(parser)
    parser.add_argument(
        "--baseline",
        default=str(DEFAULT_BASELINE_PATH),
        help="Baseline Markdown path to parse",
    )


def _add_baseline_compare_args(parser: argparse.ArgumentParser) -> None:
    _add_baseline_current_args(parser)
    parser.add_argument("--latest", type=int, default=20, help="Number of baseline-eligible batches to inspect")
    parser.add_argument(
        "--profile",
        choices=("full", "quick"),
        default="full",
        help="Validation profile filter",
    )
    parser.add_argument(
        "--log-root",
        default=str(DEFAULT_LOG_ROOT),
        help="Directory containing *_summary.txt batch logs",
    )


def _add_status_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-root",
        default=str(DEFAULT_PROJECT_ROOT),
        help="Active project root used for status summaries",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Local run_case_config.local.lua path to parse read-only",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON object")


def _add_case_intake_args(parser: argparse.ArgumentParser, *, include_limit: bool = True) -> None:
    parser.add_argument(
        "--intake-journal",
        default=str(DEFAULT_CASE_INTAKE_PATH),
        help="Local case intake JSONL journal path",
    )
    parser.add_argument(
        "--session-file",
        default=str(DEFAULT_ACTIVE_SESSION_PATH),
        help="Local active session JSON path",
    )
    parser.add_argument(
        "--session-history",
        default=str(DEFAULT_SESSION_HISTORY_PATH),
        help="Local test session history JSONL path",
    )
    if include_limit:
        parser.add_argument("--limit", type=int, default=20, help="Maximum recent intake records to display")


def _add_status_overview_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-root",
        default=str(DEFAULT_PROJECT_ROOT),
        help="Active project root used for consolidated status",
    )
    parser.add_argument("--latest", type=int, default=20, help="Number of baseline-eligible batches to inspect")
    parser.add_argument(
        "--profile",
        choices=("full", "quick"),
        default="full",
        help="Validation profile filter",
    )
    parser.add_argument(
        "--baseline",
        default=str(DEFAULT_BASELINE_PATH),
        help="Baseline Markdown path used for baseline and coverage checks",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON object")


def _add_safety_doctor_args(parser: argparse.ArgumentParser) -> None:
    _add_safety_common_args(parser)
    parser.add_argument(
        "--log-root",
        default=str(DEFAULT_LOG_ROOT),
        help="Directory containing batch summary logs",
    )
    parser.add_argument(
        "--baseline",
        default=str(DEFAULT_BASELINE_PATH),
        help="Baseline Markdown path used by case summary availability checks",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="armedforces_tool",
        description="Read-only Python CLI skeleton for armedforces.io-v2 tooling migration.",
    )
    parser.add_argument("--version", action="version", version="armedforces-tool 0.1.0")

    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_logs_parser(subparsers)
    _add_case_parser(subparsers)
    _add_baseline_parser(subparsers)
    _add_safety_parser(subparsers)
    _add_status_parser(subparsers)
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


def _run_case_summary(args: argparse.Namespace) -> int:
    result = analyze_case_summary(
        log_root=Path(args.log_root),
        latest=args.latest,
        profile=args.profile,
        baseline=Path(args.baseline),
        target_unique=args.target_unique,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_case_summary(result))
    return 0


def _run_case_summary_parity(args: argparse.Namespace) -> int:
    result = case_summary_parity(
        log_root=Path(args.log_root),
        latest=args.latest,
        profile=args.profile,
        baseline=Path(args.baseline),
        target_unique=args.target_unique,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_case_summary_parity(result))
    return 0 if result.parity_status == "PASS" else 1


def _run_case_library(args: argparse.Namespace) -> int:
    result = analyze_case_library(
        log_root=Path(args.log_root),
        latest=args.latest,
        profile=args.profile,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_case_library(result))
    return 0


def _run_case_library_parity(args: argparse.Namespace) -> int:
    result = case_library_parity(
        log_root=Path(args.log_root),
        latest=args.latest,
        profile=args.profile,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_case_library_parity(result))
    return 0 if result.parity_status == "PASS" else 1


def _run_case_stable_cases(args: argparse.Namespace) -> int:
    result = analyze_stable_cases(
        log_root=Path(args.log_root),
        latest=args.latest,
        profile=args.profile,
        min_full_success=args.min_full_success,
        target_unique=args.target_unique,
    )
    known_true_addr = getattr(args, "known_true_addr", None)
    if known_true_addr:
        result = filter_stable_case_result(result, known_true_addr)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        include_rejected = bool(getattr(args, "show_rejected", False) or known_true_addr)
        title = "Stable Case Detail" if known_true_addr else (
            "Stable and Rejected Cases" if include_rejected else "Stable Cases"
        )
        print(format_stable_cases(result, include_rejected=include_rejected, title=title))
    return 0


def _run_case_stable_cases_parity(args: argparse.Namespace) -> int:
    result = stable_cases_parity(
        log_root=Path(args.log_root),
        latest=args.latest,
        profile=args.profile,
        min_full_success=args.min_full_success,
        target_unique=args.target_unique,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_stable_cases_parity(result))
    return 0 if result.parity_status == "PASS" else 1


def _run_case_retest_queue(args: argparse.Namespace) -> int:
    result = analyze_retest_queue(
        log_root=Path(args.log_root),
        latest=args.latest,
        profile=args.profile,
        target_unique=args.target_unique,
        min_full_success=args.min_full_success,
        limit=args.limit,
        active_session=bool(getattr(args, "active_session", False)),
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_retest_queue(result))
    return 0


def _run_case_sample_plan(args: argparse.Namespace) -> int:
    result = analyze_sample_plan(
        log_root=Path(args.log_root),
        latest=args.latest,
        profile=args.profile,
        target_unique=args.target_unique,
        min_full_success=args.min_full_success,
        limit=args.limit,
        active_session=bool(getattr(args, "active_session", False)),
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_sample_plan(result))
    return 0


def _run_case_retest_queue_parity(args: argparse.Namespace) -> int:
    result = retest_queue_parity(
        log_root=Path(args.log_root),
        latest=args.latest,
        profile=args.profile,
        target_unique=args.target_unique,
        min_full_success=args.min_full_success,
        limit=args.limit,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_planning_parity(result, title="Retest Queue Parity"))
    return 0 if result.parity_status in {"PASS", "WARN"} else 1


def _run_case_sample_plan_parity(args: argparse.Namespace) -> int:
    result = sample_plan_parity(
        log_root=Path(args.log_root),
        latest=args.latest,
        profile=args.profile,
        target_unique=args.target_unique,
        min_full_success=args.min_full_success,
        limit=args.limit,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_planning_parity(result, title="Sample Plan Parity"))
    return 0 if result.parity_status in {"PASS", "WARN"} else 1


def _run_safety_status(args: argparse.Namespace) -> int:
    result = analyze_safety_status(project_root=Path(args.project_root), config_path=Path(args.config))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_safety_status(result))
    return 0


def _run_safety_doctor(args: argparse.Namespace) -> int:
    result = analyze_safety_doctor(
        project_root=Path(args.project_root),
        config_path=Path(args.config),
        log_root=Path(args.log_root),
        baseline=Path(args.baseline),
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_safety_doctor(result))
    return 0 if result.overall_status in {"SAFE", "WARN"} else 1


def _run_safety_plan(args: argparse.Namespace) -> int:
    result = analyze_safety_plan(project_root=Path(args.project_root), config_path=Path(args.config))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_safety_plan(result))
    return 0


def _run_safety_execution_status(args: argparse.Namespace) -> int:
    result = analyze_safety_execution_status(project_root=Path(args.project_root), config_path=Path(args.config))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_safety_execution_status(result))
    return 0


def _run_safety_status_parity(args: argparse.Namespace) -> int:
    result = safety_status_parity(project_root=Path(args.project_root), config_path=Path(args.config))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_safety_parity(result, title="Safety Status Parity"))
    return 0 if result.parity_status in {"PASS", "WARN"} else 1


def _run_safety_doctor_parity(args: argparse.Namespace) -> int:
    result = safety_doctor_parity(
        project_root=Path(args.project_root),
        config_path=Path(args.config),
        log_root=Path(args.log_root),
        baseline=Path(args.baseline),
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_safety_parity(result, title="Safety Doctor Parity"))
    return 0 if result.parity_status in {"PASS", "WARN"} else 1


def _run_safety_plan_parity(args: argparse.Namespace) -> int:
    result = safety_plan_parity(project_root=Path(args.project_root), config_path=Path(args.config))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_safety_parity(result, title="Safety Plan Parity"))
    return 0 if result.parity_status in {"PASS", "WARN"} else 1


def _run_safety_execution_status_parity(args: argparse.Namespace) -> int:
    result = safety_execution_status_parity(project_root=Path(args.project_root), config_path=Path(args.config))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_safety_parity(result, title="Safety Execution Status Parity"))
    return 0 if result.parity_status in {"PASS", "WARN"} else 1


def _run_status_diagnostic(args: argparse.Namespace) -> int:
    result = analyze_diagnostic_status(project_root=Path(args.project_root), config_path=Path(args.config))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_diagnostic_status(result))
    return 0


def _run_status_case_intake(args: argparse.Namespace) -> int:
    result = analyze_case_intake_status(
        project_root=Path(args.project_root),
        intake_journal=Path(args.intake_journal),
        session_file=Path(args.session_file),
        session_history=Path(args.session_history),
        limit=args.limit,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_case_intake_status(result))
    return 0


def _run_status_diagnostic_parity(args: argparse.Namespace) -> int:
    result = diagnostic_status_parity(project_root=Path(args.project_root), config_path=Path(args.config))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_workflow_status_parity(result, title="Diagnostic Status Parity"))
    return 0 if result.parity_status in {"PASS", "WARN"} else 1


def _run_status_case_intake_parity(args: argparse.Namespace) -> int:
    result = case_intake_status_parity(
        project_root=Path(args.project_root),
        intake_journal=Path(args.intake_journal),
        session_file=Path(args.session_file),
        session_history=Path(args.session_history),
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_workflow_status_parity(result, title="Case Intake Status Parity"))
    return 0 if result.parity_status in {"PASS", "WARN"} else 1


def _run_status_overview(args: argparse.Namespace) -> int:
    result = analyze_status_overview(
        project_root=Path(args.project_root),
        latest=args.latest,
        profile=args.profile,
        baseline=Path(args.baseline),
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_status_overview(result))
    return 0 if result.overall_status in {"SAFE", "WARN"} else 1


def _run_baseline_list(args: argparse.Namespace) -> int:
    result = analyze_baseline_list(
        project_root=Path(args.project_root),
        baseline_dir=Path(args.baseline_dir),
        current_baseline=Path(args.baseline),
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_baseline_list(result))
    return 0


def _run_baseline_current(args: argparse.Namespace) -> int:
    result = analyze_baseline_current(baseline=Path(args.baseline))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_baseline_current(result))
    return 0


def _run_baseline_compare(args: argparse.Namespace) -> int:
    result = analyze_baseline_compare(
        baseline=Path(args.baseline),
        latest=args.latest,
        profile=args.profile,
        log_root=Path(args.log_root),
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_baseline_compare(result))
    return 0 if result.conclusion in {"BASELINE_COMPARE_PASS", "BASELINE_COMPARE_WARN"} else 1


def _run_baseline_list_parity(args: argparse.Namespace) -> int:
    result = baseline_list_parity(
        project_root=Path(args.project_root),
        baseline_dir=Path(args.baseline_dir),
        current_baseline=Path(args.baseline),
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_baseline_parity(result, title="Baseline List Parity"))
    return 0 if result.parity_status in {"PASS", "WARN"} else 1


def _run_baseline_current_parity(args: argparse.Namespace) -> int:
    result = baseline_current_parity(baseline=Path(args.baseline))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_baseline_parity(result, title="Baseline Current Parity"))
    return 0 if result.parity_status in {"PASS", "WARN"} else 1


def _run_baseline_compare_parity(args: argparse.Namespace) -> int:
    result = baseline_compare_parity(
        baseline=Path(args.baseline),
        latest=args.latest,
        profile=args.profile,
        log_root=Path(args.log_root),
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_baseline_parity(result, title="Baseline Compare Parity"))
    return 0 if result.parity_status in {"PASS", "WARN"} else 1


def format_baseline_list(result: object) -> str:
    data = result.to_dict()
    field_labels = [
        ("project_root", "project_root"),
        ("baseline_dir", "baseline_dir"),
        ("baseline_dir_exists", "baseline_dir_exists"),
        ("baseline_count", "baseline_count"),
        ("current_baseline_path", "current_baseline_path"),
        ("current_baseline_exists", "current_baseline_exists"),
        ("latest_baseline_path", "latest_baseline_path"),
        ("conclusion", "conclusion"),
        ("recommendation", "recommendation"),
    ]
    lines = [_format_field_block("Baseline List Summary", field_labels, data)]
    records = data.get("records") or []
    lines.append("")
    lines.append("Baseline Files")
    if not records:
        lines.append("No baseline Markdown files found.")
        return "\n".join(lines)
    headers = [
        "filename",
        "current",
        "profile",
        "latest_n",
        "unique",
        "created_at",
        "parse_status",
        "warnings",
    ]
    rows = [
        [
            str(item.get("filename") or "-"),
            str(item.get("is_current_default")),
            _display_value(item.get("parsed_profile")),
            _display_value(item.get("parsed_latest_n")),
            _display_value(item.get("unique_known_true_addr_count")),
            _display_value(item.get("created_at")),
            str(item.get("parse_status") or "-"),
            "; ".join(item.get("parse_warnings") or []) or "-",
        ]
        for item in records
    ]
    lines.extend(_format_table(headers, rows))
    return "\n".join(lines)


def format_baseline_current(result: object) -> str:
    data = result.to_dict()
    field_labels = [
        ("baseline_path", "baseline_path"),
        ("baseline_exists", "baseline_exists"),
        ("parse_status", "parse_status"),
        ("profile", "profile"),
        ("latest_n", "latest_n"),
        ("unique_known_true_addr_count", "unique_known_true_addr_count"),
        ("baseline_eligible_count", "baseline_eligible_count"),
        ("success_count", "success_count"),
        ("created_at", "created_at"),
        ("known_true_addr list", "known_true_addrs"),
        ("parse_warnings", "parse_warnings"),
        ("conclusion", "conclusion"),
        ("recommendation", "recommendation"),
    ]
    return _format_field_block("Baseline Current", field_labels, data)


def format_baseline_compare(result: object) -> str:
    data = result.to_dict()
    field_labels = [
        ("baseline_path", "baseline_path"),
        ("baseline_exists", "baseline_exists"),
        ("latest N", "latest_n"),
        ("profile", "profile"),
        ("baseline unique known_true_addr count", "baseline_unique_known_true_addr_count"),
        ("current eligible batch count", "current_eligible_batch_count"),
        ("current success count", "current_success_count"),
        ("current unique known_true_addr count", "current_unique_known_true_addr_count"),
        ("coverage delta", "coverage_delta"),
        ("repeated known_true_addr list", "repeated_known_true_addr"),
        ("missing_from_current", "missing_from_current"),
        ("new_in_current", "new_in_current"),
        ("conclusion", "conclusion"),
        ("recommendation", "recommendation"),
    ]
    return _format_field_block("Baseline Compare", field_labels, data)


def format_baseline_parity(result: object, *, title: str) -> str:
    data = result.to_dict()
    rows = [
        ("parity_status", data["parity_status"]),
        ("mismatch_count", data["mismatch_count"]),
        ("unparseable_fields", data.get("unparseable_fields") or []),
    ]
    width = max(len(label) for label, _ in rows)
    lines = [title, "-" * len(title)]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {_display_value(value)}")

    mismatches = data["mismatches"]
    if mismatches:
        headers = ["field", "status", "python", "powershell"]
        table_rows = [
            [
                str(item.get("field") or "-"),
                str(item.get("status") or "-"),
                _display_value(item.get("python_value")),
                _display_value(item.get("powershell_value")),
            ]
            for item in mismatches
        ]
        lines.append("")
        lines.append("Mismatches")
        lines.append("----------")
        lines.extend(_format_table(headers, table_rows))
    return "\n".join(lines)


def format_status_overview(result: object) -> str:
    data = result.to_dict()
    summary = data["summary"]
    field_labels = [
        ("project_root", "project_root"),
        ("overall_status", "overall_status"),
        ("safety_status", "safety_status"),
        ("next_run_type", "next_run_type"),
        ("danger_level", "danger_level"),
        ("execution_arm_state", "execution_arm_state"),
        ("diagnostic_status", "diagnostic_status"),
        ("case_intake_status", "case_intake_status"),
        ("baseline_status", "baseline_status"),
        ("baseline_compare_status", "baseline_compare_status"),
        ("case_summary_status", "case_summary_status"),
        ("latest_n", "latest_n"),
        ("profile", "profile"),
        ("current_unique_known_true_addr_count", "current_unique_known_true_addr_count"),
        ("baseline_unique_known_true_addr_count", "baseline_unique_known_true_addr_count"),
        ("coverage_delta", "coverage_delta"),
        ("warning_count", "warning_count"),
        ("danger_count", "danger_count"),
        ("recommendation", "recommendation"),
    ]
    lines = [_format_field_block("Status Overview", field_labels, summary)]
    components = data.get("components") or []
    lines.append("")
    lines.append("Components")
    if not components:
        lines.append("No component records emitted.")
    else:
        headers = ["component_name", "status", "summary", "recommendation"]
        rows = [
            [
                str(item.get("component_name") or "-"),
                str(item.get("status") or "-"),
                str(item.get("summary") or "-"),
                str(item.get("recommendation") or "-"),
            ]
            for item in components
        ]
        lines.extend(_format_table(headers, rows))
    return "\n".join(lines)


def format_diagnostic_status(result: object) -> str:
    data = result.to_dict()
    field_labels = [
        ("project_root", "project_root"),
        ("config_path", "config_path"),
        ("config_exists", "config_exists"),
        ("diagnostic_level", "diagnostic_level"),
        ("diagnostic_status", "diagnostic_status"),
        ("validation_profile", "validation_profile"),
        ("execution_enabled", "execution_enabled"),
        ("write_enabled", "write_enabled"),
        ("safety_state", "safety_state"),
        ("next_run_type", "next_run_type"),
        ("recommendation", "recommendation"),
    ]
    return _format_field_block("Diagnostic Status", field_labels, data)


def format_case_intake_status(result: object) -> str:
    data = result.to_dict()
    field_labels = [
        ("project_root", "project_root"),
        ("intake_journal_path", "intake_journal_path"),
        ("intake_journal_exists", "intake_journal_exists"),
        ("active_session_file_exists", "active_session_file_exists"),
        ("active_session_detected", "active_session_detected"),
        ("active_session_id", "active_session_id"),
        ("active_session_label", "active_session_label"),
        ("active_session_started_at", "active_session_started_at"),
        ("prepared_count", "prepared_count"),
        ("completed_count", "completed_count"),
        ("abandoned_count", "abandoned_count"),
        ("open_count", "open_count"),
        ("latest_prepared_intake_id", "latest_prepared_intake_id"),
        ("latest_completed_intake_id", "latest_completed_intake_id"),
        ("latest_abandoned_intake_id", "latest_abandoned_intake_id"),
        ("latest_completed_batch_id", "latest_completed_batch_id"),
        ("latest_known_true_addr", "latest_known_true_addr"),
        ("invalid_json_line_count", "invalid_json_line_count"),
        ("conclusion", "conclusion"),
        ("recommendation", "recommendation"),
    ]
    lines = [_format_field_block("Case Intake Status", field_labels, data)]
    records = data.get("records") or []
    lines.append("")
    lines.append("Recent Intake Records")
    if not records:
        lines.append("No intake records found.")
    else:
        headers = [
            "intake_id",
            "action",
            "status",
            "known_true_addr",
            "profile",
            "batch_id",
            "timestamp",
            "reason",
            "is_open",
            "active_session_related",
        ]
        table_rows = [
            [
                str(item.get("intake_id") or "-"),
                str(item.get("action") or "-"),
                str(item.get("status") or "-"),
                str(item.get("known_true_addr") or "-"),
                str(item.get("profile") or "-"),
                str(item.get("batch_id") or "-"),
                str(item.get("timestamp") or "-"),
                str(item.get("reason") or "-"),
                str(item.get("is_open")),
                str(item.get("active_session_related")),
            ]
            for item in records
        ]
        lines.extend(_format_table(headers, table_rows))
    return "\n".join(lines)


def format_workflow_status_parity(result: object, *, title: str) -> str:
    data = result.to_dict()
    rows = [
        ("parity_status", data["parity_status"]),
        ("mismatch_count", data["mismatch_count"]),
    ]
    width = max(len(label) for label, _ in rows)
    lines = [title, "-" * len(title)]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {_display_value(value)}")

    mismatches = data.get("mismatches") or []
    if mismatches:
        headers = ["field", "status", "python", "powershell"]
        table_rows = [
            [
                str(item.get("field") or "-"),
                str(item.get("status") or "-"),
                _display_value(item.get("python_value")),
                _display_value(item.get("powershell_value")),
            ]
            for item in mismatches
        ]
        lines.append("")
        lines.append("Mismatches")
        lines.append("----------")
        lines.extend(_format_table(headers, table_rows))

    unparseable = data.get("unparseable_fields") or []
    if unparseable:
        lines.append("")
        lines.append("Unparseable Fields")
        lines.append("------------------")
        for field in unparseable:
            lines.append(str(field))
    return "\n".join(lines)


def format_safety_doctor(result: object) -> str:
    data = result.to_dict()
    field_labels = [
        ("project_root", "project_root"),
        ("overall_status", "overall_status"),
        ("safety_state", "safety_state"),
        ("next_run_type", "next_run_type"),
        ("danger_level", "danger_level"),
        ("arm_state", "arm_state"),
        ("config_exists", "config_exists"),
        ("log_root_exists", "log_root_exists"),
        ("latest_log_available", "latest_log_available"),
        ("baseline_exists", "baseline_exists"),
        ("python_tooling_available", "python_tooling_available"),
        ("protected_local_files_present", "protected_local_files_present"),
        ("warning_count", "warning_count"),
        ("danger_count", "danger_count"),
        ("recommendation", "recommendation"),
    ]
    lines = [_format_field_block("Safety Doctor", field_labels, data)]
    checks = data.get("checks") or []
    lines.append("")
    lines.append("Checks")
    if not checks:
        lines.append("No checks were emitted.")
    else:
        headers = ["check_name", "status", "detail", "recommendation"]
        table_rows = [
            [
                str(item.get("check_name") or "-"),
                str(item.get("status") or "-"),
                str(item.get("detail") or "-"),
                str(item.get("recommendation") or "-"),
            ]
            for item in checks
        ]
        lines.extend(_format_table(headers, table_rows))
    return "\n".join(lines)


def format_safety_status(result: object) -> str:
    data = result.to_dict()
    field_labels = [
        ("project_root", "project_root"),
        ("config_path", "config_path"),
        ("config_exists", "config_exists"),
        ("validation_profile", "validation_profile"),
        ("diagnostic_level", "diagnostic_level"),
        ("known_true_addr", "known_true_addr"),
        ("target_value_float", "target_value_float"),
        ("target_value_pattern", "target_value_pattern"),
        ("write_value_float", "write_value_float"),
        ("execution_mode", "execution_mode"),
        ("execution_enabled", "execution_enabled"),
        ("write_enabled", "write_enabled"),
        ("execution_confirm", "execution_confirm"),
        ("execution_confirm_present", "execution_confirm_present"),
        ("execution_write_request_id", "execution_write_request_id"),
        ("execution_armed_at_utc", "execution_armed_at_utc"),
        ("execution_arm_expires_at_utc", "execution_arm_expires_at_utc"),
        ("execution_arm_present", "execution_arm_present"),
        ("execution_arm_state", "execution_arm_state"),
        ("safety_state", "safety_state"),
        ("recommendation", "recommendation"),
    ]
    return _format_field_block("Safety Status", field_labels, data)


def format_safety_plan(result: object) -> str:
    data = result.to_dict()
    field_labels = [
        ("project_root", "project_root"),
        ("config_path", "config_path"),
        ("config_exists", "config_exists"),
        ("next_run_type", "next_run_type"),
        ("danger_level", "danger_level"),
        ("reason", "reason"),
        ("recommendation", "recommendation"),
        ("validation_profile", "validation_profile"),
        ("diagnostic_level", "diagnostic_level"),
        ("target_value_float", "target_value_float"),
        ("target_value_pattern", "target_value_pattern"),
        ("execution_mode", "execution_mode"),
        ("write_enabled", "write_enabled"),
        ("execution_confirm_present", "execution_confirm_present"),
        ("execution_write_request_id", "execution_write_request_id"),
        ("execution_arm_state", "execution_arm_state"),
        ("restore_source_batch_id", "restore_source_batch_id"),
        ("restore_source_batch_execution_addr", "restore_source_batch_execution_addr"),
    ]
    return _format_field_block("Safety Plan", field_labels, data)


def format_safety_execution_status(result: object) -> str:
    data = result.to_dict()
    field_labels = [
        ("project_root", "project_root"),
        ("config_path", "config_path"),
        ("config_exists", "config_exists"),
        ("execution_enabled", "execution_enabled"),
        ("write_enabled", "write_enabled"),
        ("execution_mode", "execution_mode"),
        ("execution_confirm", "execution_confirm"),
        ("execution_confirm_present", "execution_confirm_present"),
        ("execution_write_request_id", "execution_write_request_id"),
        ("execution_armed_at_utc", "execution_armed_at_utc"),
        ("execution_arm_expires_at_utc", "execution_arm_expires_at_utc"),
        ("arm_state", "arm_state"),
        ("arm_seconds_remaining", "arm_seconds_remaining"),
        ("restore_source_batch_execution_addr", "restore_source_batch_execution_addr"),
        ("recommendation", "recommendation"),
    ]
    return _format_field_block("Safety Execution Status", field_labels, data)


def format_safety_parity(result: object, *, title: str) -> str:
    data = result.to_dict()
    rows = [
        ("parity_status", data["parity_status"]),
        ("mismatch_count", data["mismatch_count"]),
    ]
    width = max(len(label) for label, _ in rows)
    lines = [title, "-" * len(title)]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {_display_value(value)}")

    mismatches = data["mismatches"]
    if mismatches:
        headers = ["field", "status", "python", "powershell"]
        table_rows = [
            [
                str(item.get("field") or "-"),
                str(item.get("status") or "-"),
                _display_value(item.get("python_value")),
                _display_value(item.get("powershell_value")),
            ]
            for item in mismatches
        ]
        lines.append("")
        lines.append("Mismatches")
        lines.append("----------")
        lines.extend(_format_table(headers, table_rows))
    unparseable = data.get("unparseable_fields") or []
    if unparseable:
        lines.append("")
        lines.append("Unparseable Fields")
        lines.append("------------------")
        for field in unparseable:
            lines.append(str(field))
    return "\n".join(lines)


def _format_field_block(title: str, field_labels: Sequence[tuple[str, str]], data: dict[str, object | None]) -> str:
    rows = [(label, _display_value(data.get(key))) for label, key in field_labels]
    width = max(len(label) for label, _ in rows)
    lines = [title, "Field".ljust(width) + "  Value", "-".ljust(width, "-") + "  -----"]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {value}")
    return "\n".join(lines)


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


def format_case_summary(result: object) -> str:
    data = result.to_dict()
    field_labels = [
        ("latest N", "latest_n"),
        ("profile", "profile"),
        ("baseline path", "baseline_path"),
        ("baseline exists", "baseline_exists"),
        ("baseline unique known_true_addr count", "baseline_unique_known_true_addr_count"),
        ("target unique source", "target_unique_source"),
        ("target unique known_true_addr count", "target_unique_known_true_addr_count"),
        ("current eligible batch count", "current_eligible_batch_count"),
        ("current success count", "current_success_count"),
        ("current unique known_true_addr count", "current_unique_known_true_addr_count"),
        ("coverage delta", "coverage_delta"),
        ("repeated known_true_addr list with counts", "repeated_known_true_addr"),
        ("top repeated addr", "top_repeated_addr"),
        ("estimated new distinct addr needed under rolling latest-N window", "estimated_new_distinct_addr_needed"),
        ("conclusion", "conclusion"),
        ("recommendation", "recommendation"),
    ]
    rows = []
    for label, key in field_labels:
        value = data.get(key)
        if key == "repeated_known_true_addr":
            value = _format_repeated_addr_inline(value)
        rows.append((label, _display_value(value)))

    width = max(len(label) for label, _ in rows)
    lines = ["Case Coverage Summary", "Field".ljust(width) + "  Value", "-".ljust(width, "-") + "  -----"]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {value}")

    repeated = data.get("repeated_known_true_addr") or []
    if repeated:
        lines.append("")
        lines.append("Repeated known_true_addr")
        lines.append("known_true_addr  count")
        lines.append("---------------  -----")
        for item in repeated:
            lines.append(f"{str(item['known_true_addr']).ljust(15)}  {item['count']}")
    return "\n".join(lines)


def format_case_summary_parity(result: object) -> str:
    data = result.to_dict()
    rows = [
        ("parity_status", data["parity_status"]),
        ("mismatch_count", data["mismatch_count"]),
    ]
    width = max(len(label) for label, _ in rows)
    lines = ["Case Summary Parity", "-------------------"]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {_display_value(value)}")

    mismatches = data["mismatches"]
    if mismatches:
        headers = ["field", "python", "powershell"]
        table_rows = [
            [
                str(item.get("field") or "-"),
                _display_value(item.get("python_value")),
                _display_value(item.get("powershell_value")),
            ]
            for item in mismatches
        ]
        widths = [len(header) for header in headers]
        for row in table_rows:
            for index, value in enumerate(row):
                widths[index] = max(widths[index], len(value))
        lines.append("")
        lines.append("Mismatches")
        lines.append("----------")
        lines.append(" ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
        lines.append(" ".join("-" * widths[index] for index in range(len(headers))))
        for row in table_rows:
            lines.append(" ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
    return "\n".join(lines)


def format_case_library(result: object) -> str:
    data = result.to_dict()
    field_labels = [
        ("latest N", "latest_n"),
        ("profile", "profile"),
        ("total cases", "total_cases"),
        ("unique known_true_addr count", "unique_known_true_addr_count"),
        ("baseline eligible count", "baseline_eligible_count"),
        ("execution batches count", "execution_batches_count"),
        ("invalid config count", "invalid_config_count"),
        ("stable case candidate count", "stable_case_candidate_count"),
        ("current recommended baseline candidates", "current_recommended_baseline_candidates"),
        ("conclusion", "conclusion"),
        ("recommendation", "recommendation"),
    ]
    rows = []
    for label, key in field_labels:
        value = data.get(key)
        if key == "current_recommended_baseline_candidates":
            value = "; ".join(value) if value else "none"
        rows.append((label, _display_value(value)))

    width = max(len(label) for label, _ in rows)
    lines = ["Case Library Summary", "Field".ljust(width) + "  Value", "-".ljust(width, "-") + "  -----"]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {value}")

    address_rows = data.get("addresses") or []
    lines.append("")
    lines.append("Case Library")
    if not address_rows:
        lines.append("No known_true_addr records found.")
        return "\n".join(lines)

    headers = [
        "known_true_addr",
        "cases",
        "success",
        "full_succ",
        "quick_succ",
        "first_seen",
        "last_seen",
        "profiles",
        "eligible",
        "exec",
        "invalid",
        "stable",
    ]
    table_rows = [
        [
            str(item["known_true_addr"]),
            str(item["cases"]),
            str(item["success"]),
            str(item["full_succ"]),
            str(item["quick_succ"]),
            str(item["first_seen"]),
            str(item["last_seen"]),
            str(item["profiles"]),
            str(item["baseline_eligible_count"]),
            str(item["execution_batches_count"]),
            str(item["invalid_config_count"]),
            str(item["stable_candidate"]),
        ]
        for item in address_rows
    ]
    widths = [len(header) for header in headers]
    for row in table_rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    lines.append(" ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    lines.append(" ".join("-" * widths[index] for index in range(len(headers))))
    for row in table_rows:
        lines.append(" ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
    return "\n".join(lines)


def format_case_library_parity(result: object) -> str:
    data = result.to_dict()
    rows = [
        ("parity_status", data["parity_status"]),
        ("mismatch_count", data["mismatch_count"]),
    ]
    width = max(len(label) for label, _ in rows)
    lines = ["Case Library Parity", "-------------------"]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {_display_value(value)}")

    mismatches = data["mismatches"]
    if mismatches:
        headers = ["field", "python", "powershell"]
        table_rows = [
            [
                str(item.get("field") or "-"),
                _display_value(item.get("python_value")),
                _display_value(item.get("powershell_value")),
            ]
            for item in mismatches
        ]
        widths = [len(header) for header in headers]
        for row in table_rows:
            for index, value in enumerate(row):
                widths[index] = max(widths[index], len(value))
        lines.append("")
        lines.append("Mismatches")
        lines.append("----------")
        lines.append(" ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
        lines.append(" ".join("-" * widths[index] for index in range(len(headers))))
        for row in table_rows:
            lines.append(" ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
    return "\n".join(lines)


def format_stable_cases(result: object, *, include_rejected: bool, title: str) -> str:
    data = result.to_dict()
    field_labels = [
        ("latest N", "latest_n"),
        ("profile", "profile"),
        ("min full success", "min_full_success"),
        ("target unique", "target_unique"),
        ("total unique addr", "total_unique_addr"),
        ("stable candidate count", "stable_candidate_count"),
        ("rejected address count", "rejected_address_count"),
        ("addresses needing only more clean full runs", "addresses_needing_only_more_clean_full_runs"),
        ("addresses blocked by quality issues", "addresses_blocked_by_quality_issues"),
        ("coverage readiness", "coverage_readiness"),
        ("top repeated addr", "duplicate_heavy_top_addr"),
        ("duplicate-heavy warning", "duplicate_heavy_warning"),
        ("recommended action", "recommended_action"),
    ]
    rows = [(label, _display_value(data.get(key))) for label, key in field_labels]
    width = max(len(label) for label, _ in rows)
    lines = ["Stable Baseline Candidates Summary", "Field".ljust(width) + "  Value", "-".ljust(width, "-") + "  -----"]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {value}")

    reason_rows = data.get("reason_summary") or []
    lines.append("")
    lines.append("Rejection Reason Summary")
    if not reason_rows:
        lines.append("No rejected addresses.")
    else:
        headers = ["rejection_reason", "addr_count"]
        table_rows = [
            [str(item["rejection_reason"]), str(item["affected_addr_count"])]
            for item in sorted(reason_rows, key=lambda item: (-int(item["affected_addr_count"]), item["rejection_reason"]))
        ]
        lines.extend(_format_table(headers, table_rows))

    address_rows = data.get("addresses") or []
    if not include_rejected:
        address_rows = [item for item in address_rows if item.get("stable_candidate") is True]

    lines.append("")
    lines.append(title)
    if not address_rows:
        lines.append("No matching known_true_addr rows found.")
        return "\n".join(lines)

    headers = [
        "known_true_addr",
        "full_succ",
        "eligible",
        "quick",
        "first_seen",
        "last_seen",
        "latest_full",
        "rank_AWB",
        "stable",
        "cand",
        "rejection_reasons",
        "recommended_action",
    ]
    table_rows = []
    for item in sorted(
        address_rows,
        key=lambda row: (row.get("stable_candidate") is not True, -int(row.get("full_success_count") or 0), row.get("known_true_addr") or ""),
    ):
        reasons = item.get("rejection_reasons") or []
        table_rows.append(
            [
                str(item.get("known_true_addr") or "-"),
                str(item.get("full_success_count") or 0),
                str(item.get("baseline_eligible_count") or 0),
                str(item.get("quick_success_count") or 0),
                str(item.get("first_seen_batch") or "-"),
                str(item.get("last_seen_batch") or "-"),
                str(item.get("latest_full_batch") or "-"),
                str(item.get("latest_rank_AWB") or "-"),
                str(item.get("latest_stable_rank") or "-"),
                str(item.get("stable_candidate")),
                "; ".join(str(reason) for reason in reasons) if reasons else "-",
                str(item.get("recommended_action") or "-"),
            ]
        )
    lines.extend(_format_table(headers, table_rows))
    return "\n".join(lines)


def format_stable_cases_parity(result: object) -> str:
    data = result.to_dict()
    rows = [
        ("parity_status", data["parity_status"]),
        ("mismatch_count", data["mismatch_count"]),
    ]
    width = max(len(label) for label, _ in rows)
    lines = ["Stable Cases Parity", "-------------------"]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {_display_value(value)}")

    mismatches = data["mismatches"]
    if mismatches:
        headers = ["field", "python", "powershell"]
        table_rows = [
            [
                str(item.get("field") or "-"),
                _display_value(item.get("python_value")),
                _display_value(item.get("powershell_value")),
            ]
            for item in mismatches
        ]
        lines.append("")
        lines.append("Mismatches")
        lines.append("----------")
        lines.extend(_format_table(headers, table_rows))
    return "\n".join(lines)


def format_retest_queue(result: object) -> str:
    data = result.to_dict()
    field_labels = [
        ("latest N", "latest_n"),
        ("profile", "profile"),
        ("target unique", "target_unique"),
        ("min full success", "min_full_success"),
        ("display limit", "limit"),
        ("total unique addr", "total_unique_addr"),
        ("stable candidate count", "stable_candidate_count"),
        ("queue size", "queue_size"),
        ("need more clean full runs count", "need_more_clean_full_runs_count"),
        ("blocked by quality issues count", "blocked_by_quality_issues_count"),
        ("high priority retest count", "high_priority_count"),
        ("medium priority retest count", "medium_priority_count"),
        ("low priority retest count", "low_priority_count"),
        ("blocked address count", "blocked_count"),
        ("duplicate-heavy top addr", "duplicate_heavy_top_addr"),
        ("active session detected", "active_session_detected"),
        ("active session id", "active_session_id"),
        ("current-session reusable address count", "current_session_reusable_address_count"),
        ("active-session prepare command count", "active_session_prepare_command_count"),
        ("conclusion", "conclusion"),
        ("recommendation", "recommendation"),
    ]
    rows = [(label, _display_value(data.get(key))) for label, key in field_labels]
    width = max(len(label) for label, _ in rows)
    lines = ["Retest Queue Summary", "Field".ljust(width) + "  Value", "-".ljust(width, "-") + "  -----"]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {value}")

    records = data.get("records") or []
    lines.append("")
    lines.append("Retest Queue")
    if not records:
        lines.append("No retest rows found.")
        return "\n".join(lines)

    show_active = any(item.get("active_session_addr") for item in records)
    headers = [
        "known_true_addr",
        "priority",
        "full",
        "eligible",
        "latest_batch",
        "latest_classification",
        "rank_AWB",
        "stable",
        "missing",
        "rejection_reasons",
        "recommended_action",
    ]
    if show_active:
        headers.extend(["active_session_source", "active_session_prepare"])
    table_rows = []
    for item in records:
        row = [
            str(item.get("known_true_addr") or "-"),
            str(item.get("priority") or "-"),
            str(item.get("full_success_count") or 0),
            str(item.get("baseline_eligible_count") or 0),
            str(item.get("latest_batch") or "-"),
            str(item.get("latest_classification") or "-"),
            str(item.get("latest_rank_AWB") or "-"),
            str(item.get("latest_stable_rank") or "-"),
            str(item.get("missing_clean_full_runs") or 0),
            "; ".join(item.get("rejection_reasons") or []) or "-",
            str(item.get("recommended_action") or "-"),
        ]
        if show_active:
            row.extend([str(item.get("active_session_source") or "-"), str(item.get("active_session_prepare") or "-")])
        table_rows.append(row)
    lines.extend(_format_table(headers, table_rows))
    return "\n".join(lines)


def format_sample_plan(result: object) -> str:
    data = result.to_dict()
    field_labels = [
        ("latest N", "latest_n"),
        ("profile", "profile"),
        ("target unique", "target_unique"),
        ("min full success", "min_full_success"),
        ("display limit", "limit"),
        ("current stable candidate count", "current_stable_candidate_count"),
        ("estimated new stable candidates needed", "estimated_new_stable_candidates_needed"),
        ("recommended sample count", "recommended_sample_count"),
        ("active session detected", "active_session_detected"),
        ("active session requested", "active_session_requested"),
        ("active session id", "active_session_id"),
        ("current-session reusable address count", "current_session_reusable_address_count"),
        ("plan item count", "plan_item_count"),
        ("conclusion", "conclusion"),
        ("recommendation", "recommendation"),
    ]
    rows = [(label, _display_value(data.get(key))) for label, key in field_labels]
    width = max(len(label) for label, _ in rows)
    lines = ["Sample Plan Summary", "Field".ljust(width) + "  Value", "-".ljust(width, "-") + "  -----"]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {value}")

    records = data.get("records") or []
    lines.append("")
    lines.append("Sample Plan")
    if not records:
        lines.append("No sample plan rows found.")
        return "\n".join(lines)
    headers = ["known_true_addr", "plan_type", "priority", "reason", "command_hint"]
    table_rows = [
        [
            str(item.get("known_true_addr") or "-"),
            str(item.get("plan_type") or "-"),
            str(item.get("priority") or "-"),
            str(item.get("reason") or "-"),
            str(item.get("command_hint") or "-"),
        ]
        for item in records
    ]
    lines.extend(_format_table(headers, table_rows))
    return "\n".join(lines)


def format_planning_parity(result: object, *, title: str) -> str:
    data = result.to_dict()
    rows = [
        ("parity_status", data["parity_status"]),
        ("mismatch_count", data["mismatch_count"]),
    ]
    width = max(len(label) for label, _ in rows)
    lines = [title, "-" * len(title)]
    for label, value in rows:
        lines.append(f"{label.ljust(width)}  {_display_value(value)}")

    mismatches = data["mismatches"]
    if mismatches:
        headers = ["field", "status", "python", "powershell"]
        table_rows = [
            [
                str(item.get("field") or "-"),
                str(item.get("status") or "-"),
                _display_value(item.get("python_value")),
                _display_value(item.get("powershell_value")),
            ]
            for item in mismatches
        ]
        lines.append("")
        lines.append("Mismatches")
        lines.append("----------")
        lines.extend(_format_table(headers, table_rows))
    return "\n".join(lines)


def _format_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    lines = [
        " ".join(header.ljust(widths[index]) for index, header in enumerate(headers)),
        " ".join("-" * widths[index] for index in range(len(headers))),
    ]
    for row in rows:
        lines.append(" ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)))
    return lines


def _format_repeated_addr_inline(value: object) -> str | None:
    if not value:
        return None
    return "; ".join(f"{item['known_true_addr']} count {item['count']}" for item in value)


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
