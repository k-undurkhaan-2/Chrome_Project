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

### Phase 3: Thin PowerShell Wrapper

- PowerShell becomes a thin command launcher.
- Python CLI owns most non-runtime logic.
- PowerShell remains useful for Windows entry points, ExecutionPolicy-safe examples, and local operator convenience.
- Command names should remain stable unless there is a deliberate migration notice.

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
