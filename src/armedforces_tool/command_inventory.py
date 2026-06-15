from __future__ import annotations

from dataclasses import dataclass


class CommandInventoryError(RuntimeError):
    """Raised for user-facing command inventory errors."""


@dataclass(frozen=True)
class CommandDescriptor:
    command: str
    category: str
    purpose: str
    read_only: bool
    writes_files: bool
    runs_ce: bool
    replacement_for_powershell: bool
    related_powershell_command: str | None
    typical_use: str
    risk_level: str
    parameters: list[str]
    examples: list[str]
    safety_notes: list[str]
    related_commands: list[str]

    def to_dict(self) -> dict[str, object | None]:
        return {
            "command": self.command,
            "category": self.category,
            "purpose": self.purpose,
            "read_only": self.read_only,
            "writes_files": self.writes_files,
            "runs_ce": self.runs_ce,
            "replacement_for_powershell": self.replacement_for_powershell,
            "related_powershell_command": self.related_powershell_command,
            "typical_use": self.typical_use,
            "risk_level": self.risk_level,
            "parameters": self.parameters,
            "examples": self.examples,
            "safety_notes": self.safety_notes,
            "related_commands": self.related_commands,
        }


@dataclass(frozen=True)
class CommandInventoryResult:
    category: str | None
    total_count: int
    records: list[CommandDescriptor]

    def to_dict(self) -> dict[str, object]:
        return {
            "summary": {
                "category": self.category,
                "total_count": self.total_count,
                "read_only_count": sum(1 for record in self.records if record.read_only),
                "writes_files_count": sum(1 for record in self.records if record.writes_files),
                "runs_ce_count": sum(1 for record in self.records if record.runs_ce),
                "replacement_for_powershell_count": sum(
                    1 for record in self.records if record.replacement_for_powershell
                ),
            },
            "records": [record.to_dict() for record in self.records],
        }


@dataclass(frozen=True)
class QuickstartStep:
    step: int
    command: str
    purpose: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        return {
            "step": self.step,
            "command": self.command,
            "purpose": self.purpose,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class CommandQuickstartResult:
    summary: str
    read_only: bool
    runs_ce: bool
    writes_files: bool
    steps: list[QuickstartStep]

    def to_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "read_only": self.read_only,
            "runs_ce": self.runs_ce,
            "writes_files": self.writes_files,
            "steps": [step.to_dict() for step in self.steps],
        }


VALID_CATEGORIES = ("logs", "case", "safety", "status", "baseline", "registry")


def list_commands(category: str | None = None) -> CommandInventoryResult:
    normalized = _normalize_category(category)
    records = [record for record in COMMANDS if normalized is None or record.category == normalized]
    return CommandInventoryResult(category=normalized, total_count=len(records), records=records)


def show_command(command: str) -> CommandDescriptor:
    normalized = _normalize_command(command)
    for descriptor in COMMANDS:
        if descriptor.command == normalized:
            return descriptor
    raise CommandInventoryError(
        f"unknown command: {command}; run `python -m armedforces_tool commands list` to list commands"
    )


def quickstart() -> CommandQuickstartResult:
    return CommandQuickstartResult(
        summary=(
            "Daily read-only Python sidecar sequence. These commands do not run CE and do not write "
            "config/log/session/intake/baseline files."
        ),
        read_only=True,
        runs_ce=False,
        writes_files=False,
        steps=[
            QuickstartStep(
                step=1,
                command="python -m armedforces_tool status overview",
                purpose="Check total project status first.",
                notes="Aggregates safety, workflow status, baseline, and coverage checks.",
            ),
            QuickstartStep(
                step=2,
                command="python -m armedforces_tool safety doctor",
                purpose="Inspect run-preflight safety status.",
                notes="Use before any manual CE decision; read-only.",
            ),
            QuickstartStep(
                step=3,
                command="python -m armedforces_tool baseline compare",
                purpose="Compare current baseline-eligible logs against the default baseline.",
                notes="Read-only comparison; does not save or update baselines.",
            ),
            QuickstartStep(
                step=4,
                command="python -m armedforces_tool case summary --latest 20 --profile full",
                purpose="Review case coverage and repeated known_true_addr counts.",
                notes="Read-only coverage summary for baseline planning.",
            ),
        ],
    )


def _descriptor(
    command: str,
    category: str,
    purpose: str,
    typical_use: str,
    *,
    related_powershell_command: str | None = None,
    parameters: list[str] | None = None,
    examples: list[str] | None = None,
    related_commands: list[str] | None = None,
) -> CommandDescriptor:
    example = f"python -m armedforces_tool {command}"
    return CommandDescriptor(
        command=command,
        category=category,
        purpose=purpose,
        read_only=True,
        writes_files=False,
        runs_ce=False,
        replacement_for_powershell=False,
        related_powershell_command=related_powershell_command,
        typical_use=typical_use,
        risk_level="READ_ONLY",
        parameters=parameters or ["--json"],
        examples=examples or [example, f"{example} --json"],
        safety_notes=[
            "Python sidecar command only.",
            "Read-only; does not run CE.",
            "Does not write config, logs, registry, baselines, session state, or intake journal files.",
            "Does not replace the related PowerShell workflow.",
        ],
        related_commands=related_commands or [],
    )


def _normalize_category(category: str | None) -> str | None:
    if category is None:
        return None
    normalized = category.strip().lower()
    if normalized not in VALID_CATEGORIES:
        raise CommandInventoryError(
            f"unknown category: {category}; expected one of {', '.join(VALID_CATEGORIES)}"
        )
    return normalized


def _normalize_command(command: str) -> str:
    return " ".join(command.strip().split()).lower()


COMMANDS: list[CommandDescriptor] = [
    _descriptor(
        "logs parse-latest",
        "logs",
        "Parse latest batch summary logs.",
        "Quickly inspect recent parsed batch records.",
        related_powershell_command="batch_log_classifier.ps1 -Latest ... -ConsoleSummary",
        parameters=["--latest", "--profile", "--log-root", "--json"],
        related_commands=["logs parse-batch", "logs parity-latest"],
    ),
    _descriptor(
        "logs parse-batch",
        "logs",
        "Parse a single batch summary log by batch id.",
        "Inspect one known batch without running classifier side effects.",
        related_powershell_command="batch_log_classifier.ps1 -InspectBatch ...",
        parameters=["--batch-id", "--log-root", "--json"],
        examples=[
            'python -m armedforces_tool logs parse-batch --batch-id "20260614-232227"',
            'python -m armedforces_tool logs parse-batch --batch-id "20260614-232227" --json',
        ],
        related_commands=["logs parse-latest"],
    ),
    _descriptor(
        "logs parity-latest",
        "logs",
        "Compare Python log parsing with PowerShell classifier console summary.",
        "Parser regression smoke check.",
        related_powershell_command="batch_log_classifier.ps1 -Latest ... -ConsoleSummary",
        parameters=["--latest", "--profile", "--log-root", "--json"],
        related_commands=["logs parse-latest"],
    ),
    _descriptor(
        "case summary",
        "case",
        "Summarize baseline-eligible case coverage.",
        "Review latest full coverage and repeated known_true_addr counts.",
        related_powershell_command="test_session_tool.ps1 case-summary",
        parameters=["--latest", "--profile", "--baseline", "--target-unique", "--log-root", "--json"],
        examples=[
            "python -m armedforces_tool case summary --latest 20 --profile full",
            "python -m armedforces_tool case summary --latest 20 --profile full --json",
        ],
        related_commands=["baseline compare", "case library"],
    ),
    _descriptor(
        "case summary-parity",
        "case",
        "Compare Python case summary with PowerShell case-summary.",
        "Coverage analysis regression check.",
        related_powershell_command="test_session_tool.ps1 case-summary",
        parameters=["--latest", "--profile", "--baseline", "--target-unique", "--log-root", "--json"],
        related_commands=["case summary"],
    ),
    _descriptor(
        "case library",
        "case",
        "Aggregate historical known_true_addr evidence.",
        "Understand tested address history and stable candidate count.",
        related_powershell_command="test_session_tool.ps1 case-library",
        parameters=["--latest", "--profile", "--log-root", "--json"],
        related_commands=["case stable-cases", "case retest-queue"],
    ),
    _descriptor(
        "case library-parity",
        "case",
        "Compare Python case library with PowerShell case-library.",
        "Case-library regression smoke check.",
        related_powershell_command="test_session_tool.ps1 case-library",
        parameters=["--latest", "--profile", "--log-root", "--json"],
        related_commands=["case library"],
    ),
    _descriptor(
        "case stable-cases",
        "case",
        "List stable baseline candidate evidence.",
        "Find addresses that meet stable baseline evidence rules.",
        related_powershell_command="test_session_tool.ps1 stable-cases",
        parameters=["--latest", "--profile", "--min-full-success", "--target-unique", "--show-rejected", "--known-true-addr", "--log-root", "--json"],
        related_commands=["case baseline-candidates", "case retest-queue"],
    ),
    _descriptor(
        "case stable-cases-parity",
        "case",
        "Compare Python stable-cases with PowerShell stable-cases.",
        "Stable-candidate regression check.",
        related_powershell_command="test_session_tool.ps1 stable-cases",
        parameters=["--latest", "--profile", "--min-full-success", "--target-unique", "--log-root", "--json"],
        related_commands=["case stable-cases"],
    ),
    _descriptor(
        "case baseline-candidates",
        "case",
        "Alias for stable-cases baseline candidate analysis.",
        "Use stable-cases through the baseline-candidates alias.",
        related_powershell_command="test_session_tool.ps1 baseline-candidates",
        parameters=["--latest", "--profile", "--min-full-success", "--target-unique", "--show-rejected", "--known-true-addr", "--log-root", "--json"],
        related_commands=["case stable-cases"],
    ),
    _descriptor(
        "case retest-queue",
        "case",
        "Plan read-only retest priorities from stable-case evidence.",
        "Choose next historical retest candidates without preparing a case.",
        related_powershell_command="test_session_tool.ps1 retest-queue",
        parameters=["--latest", "--profile", "--target-unique", "--min-full-success", "--limit", "--log-root", "--active-session", "--json"],
        related_commands=["case sample-plan", "case stable-cases"],
    ),
    _descriptor(
        "case retest-queue-parity",
        "case",
        "Compare Python retest queue with PowerShell retest-queue.",
        "Retest planning regression check.",
        related_powershell_command="test_session_tool.ps1 retest-queue",
        parameters=["--latest", "--profile", "--target-unique", "--min-full-success", "--limit", "--log-root", "--json"],
        related_commands=["case retest-queue"],
    ),
    _descriptor(
        "case sample-plan",
        "case",
        "Build a read-only sample acquisition plan.",
        "Plan collection without preparing config or writing intake state.",
        related_powershell_command="test_session_tool.ps1 sample-plan",
        parameters=["--latest", "--profile", "--target-unique", "--min-full-success", "--limit", "--log-root", "--active-session", "--json"],
        related_commands=["case retest-queue"],
    ),
    _descriptor(
        "case sample-plan-parity",
        "case",
        "Compare Python sample-plan with PowerShell sample-plan.",
        "Sample planning regression check.",
        related_powershell_command="test_session_tool.ps1 sample-plan",
        parameters=["--latest", "--profile", "--target-unique", "--min-full-success", "--limit", "--log-root", "--json"],
        related_commands=["case sample-plan"],
    ),
    _descriptor(
        "safety status",
        "safety",
        "Read local config safety state.",
        "Check if current config is safe detect-only or write-capable.",
        related_powershell_command="test_session_tool.ps1 status",
        parameters=["--project-root", "--config", "--json"],
        related_commands=["safety plan", "safety doctor"],
    ),
    _descriptor(
        "safety plan",
        "safety",
        "Infer next-run risk from local config.",
        "Confirm next run is detect_only / SAFE before manual CE decisions.",
        related_powershell_command="test_session_tool.ps1 plan",
        parameters=["--project-root", "--config", "--json"],
        related_commands=["safety status", "safety execution-status"],
    ),
    _descriptor(
        "safety execution-status",
        "safety",
        "Read execution arm and write guard state.",
        "Confirm execution is disabled or not armed.",
        related_powershell_command="test_session_tool.ps1 execution-status",
        parameters=["--project-root", "--config", "--json"],
        related_commands=["safety status", "safety plan"],
    ),
    _descriptor(
        "safety doctor",
        "safety",
        "Aggregate read-only Python safety checks.",
        "Daily preflight safety check before manual runtime work.",
        related_powershell_command="test_session_tool.ps1 doctor",
        parameters=["--project-root", "--config", "--log-root", "--baseline", "--json"],
        related_commands=["status overview", "safety status", "safety plan"],
    ),
    _descriptor(
        "safety status-parity",
        "safety",
        "Compare Python safety status with PowerShell doctor output.",
        "Safety parser regression check.",
        related_powershell_command="test_session_tool.ps1 doctor",
        parameters=["--project-root", "--config", "--json"],
        related_commands=["safety status"],
    ),
    _descriptor(
        "safety plan-parity",
        "safety",
        "Compare Python safety plan with PowerShell plan output.",
        "Plan parser regression check.",
        related_powershell_command="test_session_tool.ps1 plan",
        parameters=["--project-root", "--config", "--json"],
        related_commands=["safety plan"],
    ),
    _descriptor(
        "safety execution-status-parity",
        "safety",
        "Compare Python execution status with PowerShell execution-status.",
        "Execution safety regression check.",
        related_powershell_command="test_session_tool.ps1 execution-status",
        parameters=["--project-root", "--config", "--json"],
        related_commands=["safety execution-status"],
    ),
    _descriptor(
        "safety doctor-parity",
        "safety",
        "Compare Python safety doctor with PowerShell doctor.",
        "Doctor regression check.",
        related_powershell_command="test_session_tool.ps1 doctor",
        parameters=["--project-root", "--config", "--log-root", "--baseline", "--json"],
        related_commands=["safety doctor"],
    ),
    _descriptor(
        "status diagnostic",
        "status",
        "Read diagnostic level and safety context.",
        "Confirm daily diagnostics are basic.",
        related_powershell_command="test_session_tool.ps1 diagnostic-status",
        parameters=["--project-root", "--config", "--json"],
        related_commands=["status overview"],
    ),
    _descriptor(
        "status diagnostic-parity",
        "status",
        "Compare Python diagnostic status with PowerShell diagnostic-status.",
        "Diagnostic status regression check.",
        related_powershell_command="test_session_tool.ps1 diagnostic-status",
        parameters=["--project-root", "--config", "--json"],
        related_commands=["status diagnostic"],
    ),
    _descriptor(
        "status case-intake",
        "status",
        "Read local case intake journal state.",
        "Confirm open prepared intake count is clear.",
        related_powershell_command="test_session_tool.ps1 case-intake-status",
        parameters=["--project-root", "--config", "--intake-journal", "--session-file", "--session-history", "--limit", "--json"],
        related_commands=["status overview"],
    ),
    _descriptor(
        "status case-intake-parity",
        "status",
        "Compare Python case-intake status with PowerShell case-intake-status.",
        "Case intake parser regression check.",
        related_powershell_command="test_session_tool.ps1 case-intake-status",
        parameters=["--project-root", "--config", "--intake-journal", "--session-file", "--session-history", "--json"],
        related_commands=["status case-intake"],
    ),
    _descriptor(
        "status overview",
        "status",
        "Aggregate safety, workflow status, baseline, and coverage checks.",
        "Daily first command for total project state.",
        related_powershell_command=None,
        parameters=["--project-root", "--latest", "--profile", "--baseline", "--json"],
        examples=[
            "python -m armedforces_tool status overview",
            "python -m armedforces_tool status overview --json",
        ],
        related_commands=["safety doctor", "baseline compare", "case summary"],
    ),
    _descriptor(
        "baseline list",
        "baseline",
        "List local baseline Markdown files.",
        "See baseline artifacts and current default baseline.",
        related_powershell_command="test_session_tool.ps1 baseline-list",
        parameters=["--project-root", "--baseline-dir", "--baseline", "--json"],
        related_commands=["baseline current", "baseline compare"],
    ),
    _descriptor(
        "baseline list-parity",
        "baseline",
        "Compare Python baseline list with PowerShell baseline-list.",
        "Baseline list regression check.",
        related_powershell_command="test_session_tool.ps1 baseline-list",
        parameters=["--project-root", "--baseline-dir", "--baseline", "--json"],
        related_commands=["baseline list"],
    ),
    _descriptor(
        "baseline current",
        "baseline",
        "Parse the current baseline Markdown file.",
        "Inspect baseline metadata and unique known_true_addr count.",
        related_powershell_command="test_session_tool.ps1 baseline-current",
        parameters=["--project-root", "--baseline", "--json"],
        related_commands=["baseline list", "baseline compare"],
    ),
    _descriptor(
        "baseline current-parity",
        "baseline",
        "Compare Python baseline current with PowerShell baseline-current.",
        "Baseline parser regression check.",
        related_powershell_command="test_session_tool.ps1 baseline-current",
        parameters=["--project-root", "--baseline", "--json"],
        related_commands=["baseline current"],
    ),
    _descriptor(
        "baseline compare",
        "baseline",
        "Compare current baseline-eligible logs against a baseline.",
        "Daily baseline coverage comparison.",
        related_powershell_command="test_session_tool.ps1 baseline-compare",
        parameters=["--project-root", "--baseline", "--latest", "--profile", "--log-root", "--json"],
        related_commands=["baseline current", "case summary"],
    ),
    _descriptor(
        "baseline compare-parity",
        "baseline",
        "Compare Python baseline compare with PowerShell baseline-compare.",
        "Baseline comparison regression check.",
        related_powershell_command="test_session_tool.ps1 baseline-compare",
        parameters=["--project-root", "--baseline", "--latest", "--profile", "--log-root", "--json"],
        related_commands=["baseline compare"],
    ),
    _descriptor(
        "registry summary",
        "registry",
        "Summarize the local case registry JSONL file.",
        "Inspect registry health, counts, profile coverage, and latest record without writing files.",
        related_powershell_command="batch_log_classifier.ps1 -RegistrySummary",
        parameters=["--project-root", "--registry", "--profile", "--json"],
        related_commands=["registry list", "registry show"],
    ),
    _descriptor(
        "registry list",
        "registry",
        "List recent local case registry records.",
        "Inspect recent registry records with optional profile filtering.",
        related_powershell_command="batch_log_classifier.ps1 -RegistryRecent ...",
        parameters=["--project-root", "--registry", "--limit", "--profile", "--json"],
        related_commands=["registry summary", "registry show"],
    ),
    _descriptor(
        "registry show",
        "registry",
        "Show registry records by known_true_addr or batch_id.",
        "Look up one address or batch in the local registry without writing files.",
        related_powershell_command="batch_log_classifier.ps1 -RegistryAddr ...",
        parameters=["--project-root", "--registry", "--known-true-addr", "--batch-id", "--profile", "--json"],
        examples=[
            'python -m armedforces_tool registry show --known-true-addr "0xCE061C7D48"',
            'python -m armedforces_tool registry show --batch-id "20260614-232227"',
        ],
        related_commands=["registry summary", "registry list"],
    ),
]
