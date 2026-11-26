# armedforces.io-v2

An experimental candidate-ranking and evaluation project for algorithm research
with explicitly authorized, operator-owned datasets and environments. The Lua
modules evaluate candidate structure, rank candidates, and produce reports;
Python and PowerShell tools support case recording and analysis of existing logs.

## Features

- Candidate scoring, ranking, confidence, and recommendations through the
  existing collector and report modules.
- Offline evaluation of supplied finite record populations, with explicit
  bounded and full-population modes, coverage counts, and deterministic ordering.
- Case intake, session records, case-library summaries, and baseline comparisons.
- Log classification, transaction-history inspection, and guarded report,
  manifest, and directory-bundle exports.
- Offline regressions for scoring, collector interfaces, screening, case/log
  tooling, and the existing research workflow's safety boundaries.

Historical bounded reports describe the candidates evaluated in that run. They
do not establish coverage of an entire population. Offline full mode evaluates
every distinct eligible record supplied by the caller; it does not establish
that the supplied records represent a complete external environment.

## Requirements

- Python 3.10 or later for the Python tooling; `pytest` for regressions.
- Lua 5.3 and 5.4 through `lupa` for the offline scoring tests. The Lua API can
  also be called directly from a compatible standalone interpreter.
- Windows and PowerShell for the session scripts and Windows-specific workflow
  regressions. The separate manual CE research workflow uses Windows x64 and
  Cheat Engine 7.6 with Lua 5.3; offline scoring does not require CE.

The CE batch runner retains its existing local-path assumptions. See the
[research workflow guide](docs/execute_module_workflow.md) for configuration and
authorization requirements before using that workflow.

## Getting started

From the repository root, create and activate a Python virtual environment.
For example, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]" lupa
python -m pytest -q tests/test_offline_full_population.py tests/test_offline_collector_interface.py
python -m armedforces_tool --help
```

These tests use artificial records and no live target. Passing them checks the
offline contracts, not real-environment effectiveness. The
[offline scoring guide](docs/algorithm_a_offline_scoring.md) contains the Lua API,
record format, runnable example, and result semantics. For existing case and log
data, start with the [Python tooling guide](docs/python_tooling_operator_guide.md).

## Repository structure

| Path | Contents |
| --- | --- |
| `src/mvp0_*.lua` | Ranking, collection, offline evaluation, and retained research support |
| `src/execute_module-v5.2.0_batch.lua` | Existing CE research batch runner |
| `src/armedforces_tool/` | Case, log, workflow, and report tooling |
| `src/*.ps1` | Session, configuration, classification, and local utility scripts |
| `tests/` | Offline regressions and their fixtures |
| `docs/` | Research guides, contracts, and relevant historical references |
| `reports/`, `archive/` | Earlier research records and pre-existing legacy snapshots |

Private configuration, case journals, and runtime logs stay local and must not be
committed. Git history preserves retired implementations and their documentation.

## Documentation

- [Offline population scoring](docs/algorithm_a_offline_scoring.md)
- [Case collection and batch research workflow](docs/execute_module_workflow.md)
- [Python tooling operator guide](docs/python_tooling_operator_guide.md)
- [Tooling command reference](docs/python_tooling_quick_reference.md)
- [Report export guide](docs/report_export_operator_guide.md)

## Limitations

Real-environment ranking accuracy and performance remain under research and are
not qualified. Historical finite-domain synthetic results do not establish
external validity. A score, confidence label, recommendation, or value match
does not establish semantic correctness or permission to act on a target.

The native MVP experiment remains on `codex/temp-ce-native-id1-auto` and is not a
released product. Its [fixed experimental baseline](https://github.com/k-undurkhaan-2/Chrome_Project/tree/c1a96d715f886828200214e1a958141f116a85d9)
is separate from this research mainline.

## Contributing and authorized use

Follow [AGENTS.md](AGENTS.md): keep source in `src/`, keep generated logs out of
Git, make focused changes, and use descriptive conventional commit messages.
Check the relevant existing regressions when changing research code or tooling.

This non-profit project is for learning and research in explicitly authorized,
operator-owned environments. Unauthorized or unethical use is prohibited.
Configuration and tests do not confer permission to access a third-party
application or game.

Licensed under the [MIT License](LICENSE).
