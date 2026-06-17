# Python Tooling Phase 4 Roadmap

## Purpose

Phase 4 selects the next Python tooling development track after the Phase 3 final checkpoint.

This roadmap does not authorize immediate write surface expansion. It documents candidate tracks, risk boundaries, recommended ordering, and guardrails for future tasks.

## Phase 3 Baseline

Phase 3 final checkpoint:

- `python-tooling-phase3-final-checkpoint-20260616`

Current stable baseline:

- commands: about `49`
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable Python commands:
  - `report export`
  - `report bundle export`
- no CE/runtime mutation exists in Python tooling
- no log/config/session/intake/baseline/registry writes have been introduced

## Candidate Phase 4 Tracks

### Track A: Zip Bundle Export

Zip bundle export is a candidate future write-capable feature.

Requirements:

- separate contract
- dry-run behavior
- dry-run smoke/checkpoint
- real write implementation
- real write smoke/checkpoint
- cleanup policy for smoke-created archives

Risks:

- partial zip files
- atomic write requirements
- corrupted archive output
- cleanup after failed write
- accidental overwrite of pre-existing operator artifacts

### Track B: `--force` / Overwrite Policy

Overwrite support is high risk because it may delete or replace existing operator outputs.

Requirements:

- strict contract before implementation
- explicit output root boundaries
- clear pre-existing artifact detection
- protected path checks
- smoke validation for reject and overwrite paths

Recommendation: do not make this the first Phase 4 implementation.

### Track C: `docs/reports` Bundle Support

`docs/reports` bundle output would introduce a new output root.

Risks:

- can be confused with published documentation
- requires separate path policy
- may require different commit hygiene rules

Recommendation: keep deferred until explicitly contracted.

### Track D: PowerShell Thin Wrapper / Operator Bridge

This track can wrap selected read-only Python status/report commands from PowerShell.

Boundaries:

- must not replace PowerShell mutation workflows
- must not touch CE/runtime/local config
- must not run write/restore operations
- should begin with read-only commands only

This is a lower-risk Phase 4 starting point than new write surfaces.

Phase 4.3 status: read-only PowerShell thin wrapper planning is documented in `docs/architecture/python_tooling_powershell_wrapper_plan.md`. This is planning only: no wrapper is implemented, no `.ps1` file is added, no Python command is added, and no new write surface is introduced.

Phase 4.4 status: the read-only PowerShell wrapper contract is documented in `docs/architecture/python_tooling_powershell_wrapper_contract.md`. There is still no implementation, no `.ps1` file, no Python command, and no behavior change. Any future wrapper implementation must stay read-only first; write-capable wrapper behavior remains deferred.

### Track E: Native Backend Contract

Native backend planning is a long-term direction.

Boundaries:

- contract-only first
- no immediate native backend implementation
- no runtime replacement until JSON contracts and safety gates are stable
- high complexity and not a near-term dependency

### Track F: Phase 3 Operator Guide Hardening

This is docs-only and low risk.

Scope:

- consolidate daily usage flow
- clarify safe commands versus write-capable commands
- consolidate troubleshooting notes
- make Phase 3 operator boundaries easier to follow

Phase 4.2 status: operator guide hardening is documented through `docs/python_tooling_phase3_usage_guide.md`. This adds no implementation, no Python command, and no new write surface.

## Recommended Next Path

Recommended order:

1. Phase 4.2: operator guide hardening / Phase 3 usage guide
2. Phase 4.3: read-only PowerShell thin wrapper planning
3. Phase 4.4: read-only PowerShell thin wrapper contract
4. Phase 4.5: read-only PowerShell thin wrapper pilot, if explicitly scoped
5. Phase 4.6: zip bundle export contract
6. Phase 4.7: zip bundle export dry-run
7. Phase 4.8+: only then consider real zip export

Do not go directly into:

- `--force` / overwrite
- `docs/reports` bundle output
- CE/native runtime mutation

## Phase 4 Guardrails

Phase 4 guardrails:

- no CE unless a separate CE contract exists
- no runtime write/restore migration unless a separate contract exists
- no log/config/session/intake/baseline/registry writes unless explicitly contracted
- every new write-capable command requires:
  - planning
  - contract
  - dry-run
  - dry-run smoke/checkpoint
  - real implementation
  - final smoke
  - checkpoint
  - docs wrap-up

## Current Non-Goals

Phase 4 does not currently include:

- CE automation
- runtime write / restore
- PowerShell mutation replacement
- Lua/runtime modification
- algorithm rewrite
- zip export implementation yet
- `--force` / overwrite
- `docs/reports` bundle output
