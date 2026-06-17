# Tooling Migration and Runtime Adapter Roadmap

## Current Engineering State

The active project path is:

```text
D:\armedforces.io-v2
```

The project is currently driven by a PowerShell engineering harness and a CE Lua runtime environment.

PowerShell owns the operator workflow today. The main local tools are:

```text
src/test_session_tool.ps1
src/case_config_tool.ps1
src/batch_log_classifier.ps1
src/classifier_preset.ps1
```

CE Lua remains the runtime execution environment. It performs the live scan, collection, guarded runtime read/write behavior, and emits local runtime logs.

The current data interface is file-based:

- text summaries under `log/auto_output`
- local config in `src/run_case_config.local.lua`
- append-only local JSONL files under `log/`
- baseline Markdown snapshots under `log/baselines`

The current workflow is safety-oriented and checkpointed. It includes guarded write, restore planning, transaction tracking, active session tracking, case intake journaling, baseline management, doctor/preflight checks, and case-library planning. That makes the current engineering setup usable and safe, but it is not the intended final architecture.

## Why PowerShell Exists Today

PowerShell is useful in the current phase because the project is Windows-local and operator-driven.

It is good at:

- launching CE-related helper commands from Windows
- editing ignored local config files
- checking local logs
- wrapping Git hygiene checks
- presenting aligned console summaries
- coordinating manual runtime workflows

PowerShell also allowed rapid development of workflow safety features while the runtime behavior was still evolving. It was the right engineering harness for quick iteration around CE, local config, logs, baseline snapshots, and operator safety checks.

## Problems With Long-Term PowerShell Growth

PowerShell should not keep growing indefinitely.

`src/test_session_tool.ps1` is becoming too large. It now contains command routing, workflow orchestration, log parsing, report rendering, baseline logic, case-library logic, transaction checks, session handling, and local JSONL journal analysis.

That concentration of logic creates long-term problems:

- maintenance becomes harder as command count grows
- automated testing is more awkward than it needs to be
- parsing and reporting code is difficult to reuse outside Windows
- behavior changes are harder to isolate
- duplicated parsing logic is easier to introduce
- portability is limited

Long term, PowerShell should become a thin Windows operator wrapper over stable CLI modules. Reporting, parsing, registry, baseline, case-library, and intake/session analysis should move into a more testable implementation layer.

## Target Architecture

The intended long-term architecture is layered:

```text
PowerShell layer:
  Windows operator wrapper only

Python CLI layer:
  command routing
  log parsing
  report generation
  baseline comparison
  case-library
  registry/outlier analysis
  intake/session local journal handling

CE Lua runtime adapter:
  current scanning / runtime execution
  readFloat / writeFloat guarded path
  compact JSON/text summary output

Future native backend:
  optional C/C++ or Rust backend for direct process/memory operations
```

The key design goal is separation of responsibility.

PowerShell should remain convenient for local Windows operation, but it should not own the core analysis domain.

Python should own structured analysis and command behavior that can be tested without CE.

CE Lua should focus on runtime operations and emit stable result summaries.

A native backend should remain optional and future-only until the runtime request/result contracts are stable.

## Proposed Module Boundaries

A future Python CLI could use a layout similar to:

```text
armedforces_tool/
  cli.py
  config.py
  logs.py
  baseline.py
  case_library.py
  intake.py
  session.py
  execution.py
  adapters/
    ce_lua.py
    native_memory_future.py
```

High-level ownership:

- `cli.py`: command routing, argument parsing, top-level exit codes, console output mode selection
- `config.py`: local config schema, validation, safe updates, target float/pattern consistency checks
- `logs.py`: batch discovery, summary parsing, diagnostic parsing, structured log records
- `baseline.py`: baseline loading, baseline comparison, baseline save metadata, baseline eligibility rules
- `case_library.py`: case-summary, stable-cases, sample-plan, retest-queue, active-session address lifetime rules
- `intake.py`: case intake JSONL parsing, open/completed/abandoned event state, post-current-case matching rules
- `session.py`: active session marker parsing, session history, process tracking summaries
- `execution.py`: transaction classification, unpaired write detection, restore planning, execution safety summaries
- `adapters/ce_lua.py`: CE Lua request generation and result summary parsing
- `adapters/native_memory_future.py`: placeholder boundary for a possible future native backend

PowerShell commands can call the Python CLI during migration, preserving current operator command names while moving implementation details out of `.ps1` files.

## Python CLI Migration Path

Python should first take over read-only analysis and reporting tasks.

Good first candidates:

- batch log classification
- case-summary
- case-library
- stable-cases
- sample-plan
- baseline comparison
- registry / outlier analysis
- case-intake journal analysis

These areas are good migration targets because they mostly consume existing files and produce reports. They can be tested with fixture logs without running CE.

During transition:

- keep current PowerShell command names stable
- make PowerShell call the Python CLI internally
- preserve existing output fields before changing behavior
- add tests around Python parsing and classification behavior
- compare Python output against current PowerShell output before switching defaults

Behavior preservation matters more than speed of migration.

## CE Lua Runtime Adapter Strategy

CE dependency remains acceptable in the engineering build.

Long term, CE Lua should expose a narrow request/result contract. Python should generate or validate request config, then parse structured runtime summaries emitted by CE.

CE Lua should not own:

- case-library planning
- baseline comparison
- registry analysis
- transaction history interpretation
- operator workflow routing
- long-form report rendering

CE Lua should eventually focus on:

- scan / collect
- runtime memory reads
- `readFloat`
- guarded `writeFloat`
- compact runtime summary output

Runtime writes must remain guarded. Any migration must preserve the current safety gates around confirm text, arm expiry, full-profile requirement, rank guards, known-true checks, old-value checks, readback checks, and transaction logging.

## Future Native Backend Option

A native backend is not a current task.

It should only be considered after the JSON and runtime adapter contracts stabilize. A native backend would be a separate risk-managed project, not a shortcut around the current safety architecture.

A future native backend would require careful safety design for:

- process attach
- process identity and lifetime checks
- memory scanning
- read operations
- write operations
- permission handling
- rollback planning
- audit logs
- failure recovery
- operator confirmation gates

Do not jump into native backend development before the CE runtime adapter contract is stable.

## Data / Interface Contracts

The migration depends on stable file and interface contracts.

Current and future contracts to document and stabilize:

```text
summary txt or future JSON summary
local config schema
case intake JSONL
active session JSON
session history JSONL
registry JSONL
baseline markdown / future structured baseline
restore transaction fields
execution outcome fields
```

Stable contracts make it possible to move logic from PowerShell to Python without changing runtime behavior.

The most important rule is that migration should change implementation ownership before changing semantics. Existing logs, config fields, and output fields should remain readable during the transition.

## Migration Phases

### Phase 0: Current PowerShell Engineering Harness

- Keep current behavior stable.
- Use PowerShell for operator workflows.
- Avoid broad refactors during active workflow development.
- Keep CE manual-only.
- Do not commit local logs, local config, baselines, or local JSONL state.

### Phase 1: Document Contracts and Reduce Duplication

- Document current file schemas.
- Identify duplicated parsing logic in `test_session_tool.ps1`.
- Identify fields that should become structured JSON contracts.
- Keep behavior unchanged.
- Add fixture-based validation where possible.

### Phase 2: Migrate Analysis to Python

- Move classifier analysis into Python modules.
- Move case-library, case-summary, stable-cases, sample-plan, and retest-queue logic into Python modules.
- Move baseline comparison into Python modules.
- Move registry and outlier analysis into Python modules.
- Move case-intake journal analysis into Python modules.
- Keep PowerShell wrappers as compatibility commands.

Phase 2.4 adds read-only Python baseline status views for listing local baselines, parsing the current baseline, and comparing current baseline-eligible logs against a selected baseline. These commands are sidecar checks only; PowerShell baseline commands remain the operator workflow and baseline saving remains explicit.

Phase 2.5 adds a consolidated read-only Python status overview that aggregates existing safety, workflow status, baseline, and coverage helpers into one daily status entry point without replacing any PowerShell command.

Phase 2.6 adds a read-only Python command inventory and quickstart index. This is a static help layer for discovering Python sidecar commands, their safety properties, related PowerShell workflow command, and common examples; it does not replace argparse `--help` or any PowerShell operator workflow.

Phase 2 wrap-up: the read-only Python sidecar status layer is complete for the current migration stage. Python now covers analysis, safety/status checks, baseline visibility, coverage planning, parity checks, and command inventory. PowerShell remains authoritative for workflow mutation and guarded runtime actions. Future Python work should stay read-only unless a separate write-capable contract is explicitly designed and reviewed.

### Phase 3: Thin PowerShell Wrapper

- PowerShell becomes a thin command launcher.
- Python CLI owns most non-runtime logic.
- PowerShell remains useful for Windows entry points, ExecutionPolicy-safe examples, and local operator convenience.
- Command names should remain stable unless there is a deliberate migration notice.

Phase 3 planning begins after the Phase 2 read-only Python sidecar checkpoint. Phase 2 is complete for analysis, safety/status, baseline visibility, coverage planning, parity checks, status overview, and command inventory. The next recommended implementation is a Python read-only registry view. Write-capable migration, guarded write / restore migration, and CE automation remain explicitly deferred until a separate contract and checkpoint are designed.

Phase 3.1 adds Python read-only registry views for summarizing, listing, and showing records from `log/case_registry.jsonl`. This does not replace PowerShell classifier append behavior and does not write registry data.

Phase 3.2 adds Python read-only transaction history views from existing batch summaries and registry records. These commands summarize/list/show historical detect-only, dry-run, write, and restore outcomes without generating or executing write/restore actions.

Phase 3.3 adds planning for future Python report export / Markdown rendering only. No write-capable Python command is implemented yet; any future report export must use a separate write-capable contract and an approved output directory.

Phase 3.4 adds Python `report preview` as a stdout-only Markdown renderer over existing read-only analysis/status helpers. It does not implement report export, does not accept output paths, and does not write files; report export remains deferred pending a separate write-capable contract.

Phase 3.5 defines the write-capable contract for future Python `report export` only. There is no implementation yet; file-writing report export remains gated behind approved output roots, path safety rules, dry-run behavior, overwrite policy, tests, and a separate checkpoint.

Phase 3.6 implements `report export --dry-run` only. The command validates future report paths under approved output roots and prints export metadata, but it does not create directories and does not write `.md` report files. Real report export writing remains deferred.

Phase 3.7 enables guarded Python `report export` writes. The command may create one `.md` report file only under `reports/python_tooling/` or `docs/reports/python_tooling/`, keeps `--dry-run` no-write behavior, rejects protected paths and path traversal, and refuses overwrite unless `--force` is supplied.

Phase 3.8 documents the write-capable report export boundary. The boundary keeps report export limited to approved report roots, confirms no CE/runtime/log/config/session/intake/baseline/registry writes, and establishes that future write-capable Python work must use a similarly strict contract, smoke check, cleanup rule, and checkpoint process.

Phase 3.10 records the current Phase 3 state. The read-only registry and transaction tracks are complete; report preview and guarded report export are complete; `report export` is the only write-capable Python command; and future write-capable commands must follow the same contract, validation, cleanup, and checkpoint process.

Phase 3.11 documents the Python write-capable feature policy. Future write-capable work must use the same planning, contract, dry-run, smoke-check, cleanup, command-inventory, and checkpoint process established by guarded `report export`. At this point, `report export` remains the only write-capable Python command.

Phase 3.12 adds planning for future Python report manifest / report index support. No implementation is added; `report export` remains the only write-capable Python command. Manifest support is treated as separate write-capable state and remains deferred until a dedicated contract, dry-run, validation, and checkpoint are defined.

Phase 3.13 adds read-only Python report manifest preview/list/verify commands. These commands discover approved manifest candidate paths, list and verify JSONL manifests when present, and report missing/unsupported manifests without creating or modifying files. Manifest writing remains deferred and `report export` remains the only write-capable Python command.

Phase 3.14 documents the Python report manifest write contract. The contract plans future `--record-manifest` behavior, append-only `reports/python_tooling/manifest.jsonl`, write ordering, failure handling, dry-run semantics, and cleanup policy. No implementation is added; `report export` remains the only write-capable Python command.

Phase 3.15 implements dry-run planning for future report manifest writes through `report export --dry-run --record-manifest`. It plans the manifest path and entry fields without writing reports, manifests, directories, logs, registry, baseline, session, intake, or local config files. Real `--record-manifest` fails closed with no write; `report export` remains the only write-capable Python command.

Phase 3.16 implements controlled real manifest recording through `report export --record-manifest`. The only supported manifest location is `reports/python_tooling/manifest.jsonl`, and the report output must also be under `reports/python_tooling/`. Dry-run remains no-write, `docs/reports/python_tooling/` is still unsupported for manifest recording, `report export` remains the only write-capable Python command, and no CE/runtime/log/config/session/intake/baseline/registry writes are introduced.

Phase 3.18 records the manifest real-write boundary after final smoke validation. The validated state remains: command inventory about `45`, `writes_files_count = 1`, `runs_ce_count = 0`, `report export` as the only write-capable Python command, no CE/runtime mutation, and no log/config/session/intake/baseline/registry writes. Future expansion must not add new write surfaces without a new contract, dry-run behavior where applicable, smoke validation, cleanup rules, and a checkpoint.

Phase 3.19 adds planning for future Python report bundle / report package support. No implementation is added, no Python command is added, and no new write surface is authorized. Bundle directories, zip archives, copied reports, bundle manifests, and bundle indexes remain deferred until a separate contract, dry-run, smoke cleanup rules, and checkpoint are defined. `report export` remains the only write-capable Python command.

Phase 3.20 adds the read-only preview/verify contract for future Python report bundle support. No implementation is added, no Python command is added, and no new write surface is authorized. Future bundle preview/verify must remain read-only with `writes_files=false` and `runs_ce=false`; bundle export remains deferred until a separate write-capable contract and checkpoint are defined. `report export` remains the only write-capable Python command.

Phase 3.21 implements Python `report bundle preview` and `report bundle verify` as read-only views over `reports/python_tooling/manifest.jsonl`. The implementation does not create bundle directories, zip archives, copied reports, bundle manifests, indexes, reports, logs, registry files, baselines, session state, intake journals, or local config. No new write surface is added; `report export` remains the only write-capable Python command.

Phase 3.23 records the report bundle read-only boundary after final smoke validation. `report bundle preview` and `report bundle verify` remain read-only, final smoke passed, no new write surface was added, and `report export` remains the only write-capable Python command. Future bundle export must follow the write-capable feature policy with a separate contract, dry-run phase, smoke validation, cleanup rules, and checkpoint before any real bundle write behavior is implemented.

Phase 3.24 adds the Python report bundle export contract. This is documentation only: no bundle export implementation is added, no Python command is added, and no new write surface is enabled. `report export` remains the only write-capable Python command. Future bundle export must still proceed through dry-run implementation, smoke validation, cleanup rules, and checkpoint before any real bundle write behavior is allowed.

Phase 3.25 implements Python `report bundle export --dry-run` planning only. The dry-run validates future directory or zip bundle output paths, previews bundle metadata, and writes nothing. Real bundle export remains unimplemented and fails closed without `--dry-run`. No new write surface is added; `report export` remains the only write-capable Python command.

Phase 3.27 documents the report bundle export dry-run boundary after final smoke validation. Bundle export dry-run remains no-write, real bundle export remains deferred, `report export` remains the only write-capable Python command, `writes_files_count` remains `1`, and `runs_ce_count` remains `0`. Future real bundle export must follow the Python write-capable feature policy with a separate implementation, smoke validation, cleanup rules, and checkpoint process.

Phase 3.28 refines the future real bundle export contract to a directory-only first implementation. No implementation is added, no new write surface is enabled, zip export remains deferred, and `report export` remains the only write-capable Python command.

Phase 3.29 implements directory-only Python report bundle export. `report bundle export --out reports/python_tooling/bundles/<bundle_id>/` can write a guarded directory bundle with copied reports, `bundle_manifest.json`, and `index.md` under the approved bundle root. Zip export and `--force` remain unsupported, dry-run remains no-write, `writes_files_count` is expected to be `2`, write-capable commands are `report export` and `report bundle export`, and `runs_ce_count` remains `0`.

Phase 3.31 documents the report bundle directory export boundary after final smoke validation. Directory export writes only under `reports/python_tooling/bundles/<bundle_id>/`, source reports and `reports/python_tooling/manifest.jsonl` remain read-only during bundle export, `writes_files_count = 2`, `runs_ce_count = 0`, and the write-capable Python commands are `report export` and `report bundle export`. Zip export, `--force` / overwrite, and `docs/reports` bundle output remain deferred. No log/config/session/intake/baseline/registry writes were introduced.

Phase 3.32 records the current Phase 3 report, manifest, and bundle state in `docs/architecture/python_tooling_phase3_summary.md`. The documented boundary remains `writes_files_count = 2`, `runs_ce_count = 0`, with write-capable commands limited to `report export` and `report bundle export`. No CE/runtime/log/config/session/intake/baseline/registry mutation is introduced by this documentation phase. Future write surfaces still require a separate contract, dry-run behavior where applicable, smoke validation, cleanup rules, and checkpoint.

Phase 4.1 adds the Python tooling Phase 4 roadmap in `docs/architecture/python_tooling_phase4_plan.md`. The Phase 3 final checkpoint is complete, and the recommended next path is operator guide hardening before any new write surface. There is no implementation in Phase 4.1; zip export, `--force` / overwrite, `docs/reports` bundle output, CE automation, and runtime mutation remain deferred.

Phase 4.2 hardens the operator documentation after the Phase 3 final checkpoint. `docs/python_tooling_phase3_usage_guide.md` records safe daily checks, read-only commands, dry-run no-write commands, write-capable boundaries, troubleshooting, and Git hygiene. This is documentation-only and does not change Python behavior.

Phase 4.3 adds planning for a future read-only PowerShell thin wrapper around selected Python sidecar commands. This is documentation-only: no wrapper is implemented, no `.ps1` file is added, no Python command is added, and no new write surface is introduced. Any future wrapper should start with read-only status, inventory, preview, manifest verify, and bundle verify commands only. Write-capable report export, manifest recording, bundle export, CE/runtime operations, and PowerShell mutation workflow replacement remain deferred.

Phase 4.4 adds the read-only PowerShell wrapper contract. This is documentation-only: no `.ps1` file is added, no implementation is added, no Python command is added, and no behavior changes. The contract keeps first-phase wrapper scope read-only and explicitly defers write-capable wrapper behavior, real report export, manifest recording, bundle export, CE/runtime operations, and PowerShell mutation workflow replacement.

Phase 4.5 implements the first read-only PowerShell thin wrapper at `src/python_tooling_wrapper.ps1`. The wrapper supports only `status`, `inventory`, `report-status`, `manifest-verify`, and `bundle-verify`; it calls existing Python read-only commands and does not expose report export, manifest recording, bundle export dry-run, real bundle export, CE/runtime operations, write / restore workflows, or local state mutation.

### Phase 4: Stabilize CE Runtime Adapter Contract

- Define request formats.
- Define result formats.
- Prefer structured JSON summaries where possible.
- Keep CE Lua focused on runtime operations only.
- Keep guarded write behavior intact.
- Keep runtime diagnostics available for investigation.

### Phase 5: Optional Native Backend Exploration

- Only after the adapter contract is stable.
- Treat as a separate risk-managed project.
- Preserve all write safety gates.
- Preserve auditability and rollback planning.
- Do not make native backend work a dependency for near-term case collection or baseline workflows.

## What Not To Do Yet

Do not:

- rewrite everything now
- add integer/bytes write
- automate CE blindly
- replace the CE backend before contracts are stable
- remove diagnostics
- commit local logs/config
- move guarded write logic without preserving safety gates
- collapse operator workflows into runtime code
- turn historical known-true addresses into reusable live-session inputs without active-session validation

## Near-Term Next Steps

Recommended near-term work:

- finish current case collection workflow validation
- add contract/schema notes for current local files
- identify duplicated parser logic in `test_session_tool.ps1`
- choose the first Python migration candidate, likely batch log classifier or case-library summary
- keep PowerShell commands stable while migrating internals
- avoid native backend work until adapter contracts are stable
- preserve CE manual-run behavior until request/result contracts are explicit
- keep local logs, local config, local JSONL files, and generated baselines out of commits
