# Python Tooling Phase 5 Plan Selector

## Purpose

This document is the Phase 5 entry planning gate / next-work selector for Python tooling.

It does not implement functionality. It only selects the next priority direction and records safety boundaries before any Phase 5 work begins.

## Current Baseline

Current checkpoints:

- `python-tooling-phase3-final-checkpoint-20260616`
- `python-tooling-powershell-wrapper-readonly-checkpoint-20260616`

Current stable state:

- command inventory: about `49` commands
- `writes_files_count = 2`
- `runs_ce_count = 0`
- write-capable Python commands:
  - `report export`
  - `report bundle export`
- read-only wrapper commands:
  - `status`
  - `inventory`
  - `report-status`
  - `manifest-verify`
  - `bundle-verify`
- no CE/runtime mutation exists in Python tooling
- no log/config/session/intake/baseline/registry writes have been introduced

## Frozen Phase 4 Boundary

The Phase 4 boundary remains frozen:

- read-only wrapper boundary remains frozen
- wrapper must not gain write-capable commands without new policy / contract / dry-run / smoke / checkpoint
- Phase 5 work must not silently expand write surface
- CE/runtime mutation remains out of Python tooling unless separately planned
- legacy PowerShell mutation workflows remain unchanged

## Phase 5 Candidate Options

### Option A: Write-Capable Wrapper Policy Planning

Goal:

- plan whether wrapper may later wrap write-capable commands
- do not implement
- require policy / contract / dry-run / smoke / checkpoint

Risk:

- high, because it may expand write surface

Suitable when:

- operator explicitly needs wrapper convenience for `report export` / `report bundle export`
- dry-run-first, explicit confirmation, and approved roots are ready

### Option B: Runtime Write/Restore Migration Planning

Goal:

- plan Python migration for runtime write / restore
- do not implement
- focus on CE-adjacent boundary, rollback, local config, and log safety

Risk:

- high, because it is close to runtime mutation / restore

Suitable when:

- legacy PowerShell mutation workflow needs to be migrated into Python
- stricter transaction / rollback model is ready

### Option C: Operator Quick Reference / Troubleshooting Consolidation

Goal:

- docs-only
- consolidate common commands, `ExecutionPolicy`, `SAFE`, `NO_MANIFEST`, `BAD_PATH`, wrapper usage, and direct Python usage
- do not modify code

Risk:

- low

Suitable when:

- usability should be improved before new feature development
- operator mistakes should be reduced

### Option D: Read-Only Wrapper Test Hardening

Goal:

- add more systematic read-only boundary tests for wrapper
- may touch tests only
- do not change wrapper behavior

Risk:

- low to medium

Suitable when:

- wrapper will be maintained further
- regression protection should be strengthened before expanding features

### Option E: Report/Bundle Export UX Polish

Goal:

- improve report export / bundle export prompts, error messages, or preview clarity
- may touch Python source
- must not expand write surface

Risk:

- medium

Suitable when:

- report/bundle functionality is usable but operator UX needs polish

## Evaluation Matrix

| Option | Implementation scope | Write-surface risk | CE/runtime risk | Likely files touched | Validation required | Checkpoint/tag needed? | Recommended priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A: Write-capable wrapper policy planning | docs only | high future risk | low now | `docs/architecture/*`, operator docs | diff check, status check | checkpoint doc yes; tag only after milestone | 4 |
| B: Runtime write/restore migration planning | docs only | high future risk | high future risk | architecture docs | diff check, safety confirmation | checkpoint doc yes; tag only after milestone | 5 |
| C: Operator quick reference / troubleshooting consolidation | docs only | low | low | operator docs, usage docs | diff check, optional read-only status | no tag required | 1 |
| D: Read-only wrapper test hardening | tests only, possibly docs | low | low | tests, maybe docs | pytest, wrapper smoke, artifact checks | tag only if boundary checkpoint | 2 |
| E: Report/bundle export UX polish | Python source, tests, docs | medium | low | `src/armedforces_tool`, tests, docs | pytest, report/bundle smoke, artifact cleanup | checkpoint if behavior changes | 3 |

## Recommendation

Recommended order:

1. Option C: operator quick reference / troubleshooting consolidation
2. Option D: read-only wrapper test hardening
3. Option E: report/bundle export UX polish
4. Option A: write-capable wrapper policy planning
5. Option B: runtime write/restore migration planning

Rationale:

- Phase 4 was just completed.
- The safest next step is to consolidate operator docs and reduce misuse.
- Read-only regression protection should come before expanding write-capable behavior.
- Do not immediately start write-capable wrapper or runtime mutation work.

## Next Concrete Phase Proposal

Recommended next concrete phase:

```text
Phase 5.1: operator quick reference / troubleshooting consolidation
```

Scope:

- docs-only
- no source changes
- no CE
- no write-capable commands
- no tag

Phase 5.1 status: Option C has been selected and started as docs-only quick reference / troubleshooting consolidation in `docs/python_tooling_quick_reference.md`. It does not change source code, wrapper behavior, Python behavior, tests, or write surfaces.

Optional alternative:

```text
Phase 5.1b: read-only wrapper test hardening
```

Phase 5.2 status: Option D has been selected and completed as read-only wrapper test hardening. The test coverage is boundary-only and does not change wrapper behavior, Python behavior, or write surface.

Phase 5.3 status: Option E has been selected for report/bundle export UX polish planning. This is planning-only and does not expand write surface, modify Python source, modify wrapper behavior, add commands, or execute write-capable commands.

Phase 5.4 status: report/bundle export UX polish contract has been added. This remains docs-only and does not expand write surface, modify Python source, modify wrapper behavior, add commands, or execute report/bundle export commands.

Phase 5.5 status: Option E was selected for a narrow CLI/help text implementation slice. Only `report export --help` and `report bundle export --help` wording was clarified, with tests for help text and inventory invariants. No command, option, wrapper shortcut, approved root, path guard, or write behavior was added or changed.

Phase 5.6 status: Option E continues as a docs-only output wording contract. The contract covers future dry-run output, real-write output, rejection output, stable tokens, validation staging, and stop conditions. No write surface was expanded.

Phase 5.7 status: Option E continues with a helper-only implementation slice. The message helpers are unit-tested but not connected to report export or bundle export execution paths. No command, option, wrapper shortcut, approved root, path guard, or write behavior was added or changed.

Phase 5.9 status: Option E continues as a docs-only dry-run integration contract. The contract defines future integration targets, non-goals, artifact safety, test expectations, and stop conditions. No write surface was expanded.

Phase 5.10 status: Option E continues with dry-run wording implementation. Only dry-run output paths were integrated with the message helpers; real export behavior, wrapper behavior, commands, options, approved roots, and write surface remain unchanged.

Phase 5.12 status: Option E continues as a docs-only real-write output wording contract. The selected scope documents future real `report export`, `report export --record-manifest`, and real `report bundle export` output requirements without expanding write surface or changing behavior.

Phase 5.13 status: Option E continues with a helper-only real-write output extension. The helper functions and helper-only tests were updated, but helpers are not wired into real export paths and no write surface was expanded.

Phase 5.15 status: Option E continues as a docs-only real-write output integration planning gate. The gate documents candidates, staged order, implementation constraints, validation policy, and stop conditions without expanding write surface.

Phase 5.16 status: Option E continues as a docs-only real report export output integration contract. The contract covers Candidate A only and does not expand write surface.

Phase 5.17 status: Option E continues with Candidate A implementation. The change is limited to human-readable real report export success wording and does not expand write surface.

## Stop Conditions

Stop before starting a Phase 5 task if:

- working tree is dirty with unexpected files
- unexpected source/runtime file changes are present
- any report/log/config/session/baseline/intake/registry file would be written
- any CE command would be required
- any write-capable command would be required
- task scope mixes docs-only planning with implementation
- task scope expands wrapper write surface without a separate contract
