# Python Tooling Phase 6 Plan Selector

## Purpose

This document is the Phase 6 entry planning gate after the Phase 5 output wording checkpoint.

It does not implement functionality. It evaluates next-work options and selects the safest next direction. It does not add commands, options, Python behavior, wrapper behavior, CE execution, report export execution, bundle export execution, or runtime state changes.

## Current Baseline

Checkpoint tags:

- `python-tooling-phase3-final-checkpoint-20260616`
- `python-tooling-powershell-wrapper-readonly-checkpoint-20260616`
- `python-tooling-output-wording-checkpoint-20260618`

Current command inventory:

- commands = `49`
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

Current safety boundary:

- no CE/runtime mutation in Python tooling
- no log/config/session/intake/baseline/registry writes introduced
- wrapper remains read-only
- wrapper does not wrap write-capable commands
- zip export remains unsupported / fail-closed
- `--force` / overwrite remains unsupported

Phase 5 output wording covers:

- report/bundle help text
- output message helpers
- dry-run output wording
- Candidate A real report export human-readable success wording
- Candidate B `report export --record-manifest` human-readable success wording
- Candidate C real bundle export human-readable success wording

Important limitation: the Phase 5 output wording checkpoint does not mean manual real-write validation was performed. Candidate A/B/C used helper/unit tests and boundary inspections. Manual real report export, `--record-manifest`, and real bundle export still require a separately authorized task.

## Frozen Boundaries From Previous Phases

- wrapper remains read-only
- wrapper must not gain write-capable commands without a separate policy, contract, smoke, and checkpoint
- output wording changes must not expand write surface
- real-write validation must not be treated as already completed
- CE/runtime migration remains out of scope unless separately planned
- zip export remains unsupported
- `--force` remains unsupported
- approved roots/path guards remain unchanged

## Phase 6 Candidate Options

### Option A: Real-Write Output Validation Policy Planning

Goal:

- create a docs-only policy for manual real-write validation of Candidate A/B/C output wording
- define approved output paths, artifact snapshots, cleanup policy, and stop conditions
- do not execute real writes yet

Risk:

- high, because later phases may execute real write-capable commands

Suitable when:

- output wording checkpoint is complete
- operator wants manual validation of actual written output text
- cleanup and artifact safety policy are ready

### Option B: Candidate A Real Report Export Validation Contract

Goal:

- write a narrower contract for validating real `report export` output only
- no `--record-manifest`
- no bundle export
- no implementation changes

Risk:

- medium-high due real write validation in a future task

Suitable when:

- you want the smallest real-write validation slice first

### Option C: BAD_PATH / Overwrite / Zip Unsupported Runtime Wording Planning

Goal:

- plan runtime wording polish for rejection paths
- no real write needed
- could later improve `BAD_PATH`, overwrite, and zip unsupported messages

Risk:

- medium

Suitable when:

- rejection clarity is more important than real-write success validation

### Option D: Write-Capable Wrapper Policy Planning

Goal:

- plan whether wrapper should ever support write-capable commands
- no implementation
- no wrapper changes

Risk:

- high, because it expands operator access to write-capable actions

Suitable when:

- wrapper convenience is needed for exports
- explicit confirmation / dry-run-first / approved roots policy is ready

### Option E: Runtime Write/Restore Migration Planning

Goal:

- plan Python migration for runtime write/restore workflows
- no implementation
- no CE
- no state mutation

Risk:

- very high, because it approaches CE/runtime mutation

Suitable when:

- report/export tooling line is fully closed
- project is ready to discuss runtime transaction/rollback model

### Option F: Output Wording Documentation Freeze / Maintenance

Goal:

- no new feature
- freeze the output wording line and focus on docs maintenance only

Risk:

- low

Suitable when:

- current workstream is complete and you want a development pause

## Evaluation Matrix

| Option | Implementation scope | Write-surface risk | CE/runtime risk | Likely files touched | Validation required | Checkpoint/tag needed? | Recommended priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A: Real-write output validation policy planning | docs only | high future risk | low now | architecture docs, operator docs | diff check, status check, boundary review | checkpoint doc yes; tag only after milestone | 1 |
| B: Candidate A real report export validation contract | docs only | medium-high future risk | low now | architecture docs, operator docs | diff check, status check, contract review | checkpoint doc optional; tag only after validation milestone | 2 |
| C: BAD_PATH / overwrite / zip unsupported runtime wording planning | docs only | medium future risk | low now | architecture docs, quick reference | diff check, wording contract review | no tag required unless boundary changes | 3 |
| D: Write-capable wrapper policy planning | docs only | high future risk | low now | wrapper contract docs, operator docs | diff check, wrapper boundary review | checkpoint doc yes before implementation | 4 |
| E: Runtime write/restore migration planning | docs only | very high future risk | high future risk | architecture docs | diff check, safety review, rollback model review | checkpoint doc yes before implementation | 5 |
| F: Output wording documentation freeze / maintenance | docs only | low | low | operator docs, quick reference | diff check only | no tag required | 6 |

## Recommendation

Recommended order:

1. Option A: Real-write output validation policy planning
2. Option B: Candidate A real report export validation contract
3. Option C: BAD_PATH / overwrite / zip unsupported runtime wording planning
4. Option D: Write-capable wrapper policy planning
5. Option E: Runtime write/restore migration planning
6. Option F: Output wording documentation freeze / maintenance

Rationale:

- Phase 5 output wording line is complete at source/test/boundary-smoke level.
- The remaining gap is explicit real-write validation policy.
- Do not jump directly into real writes.
- Do not jump into write-capable wrapper or runtime mutation before a validation policy exists.

## Next Concrete Phase Proposal

Recommended next concrete phase:

```text
Phase 6.1: real-write output validation policy contract
```

Scope:

- docs-only
- no source changes
- no tests
- no CE
- no real write
- define policy for artifact snapshots, approved output path selection, cleanup, and stop conditions
- no tag

Alternative:

```text
Phase 6.1b: Candidate A real report export validation contract
```

Use only if the operator wants a narrower first real-write validation slice.

## Phase 6.1 Status

`docs/architecture/python_tooling_real_write_output_validation_policy.md` defines the real-write output validation policy.

Real-write validation remains deferred. The next recommended step is Candidate A contract planning only, not execution smoke.

## Phase 6.2A Status

`docs/architecture/python_tooling_candidate_a_real_report_export_validation_contract.md` defines the Candidate A contract.

The next phase may be Candidate A execution smoke only if explicitly authorized. Do not treat this contract as permission to run `report export`.

## Phase 6.3A-R2 Status

Candidate A real report export validation smoke: PASS.

The R2 smoke validated one direct Python real `report export` under the declared Candidate A validation path, confirmed the expected human-readable success tokens, confirmed unrelated manifest/bundle tokens were absent, cleaned the task-created artifact, and ended with clean git status.

## Phase 6.2B Status

`docs/architecture/python_tooling_candidate_b_report_export_manifest_validation_contract.md` defines the Candidate B report export manifest validation contract.

The next phase may be Candidate B execution smoke only if explicitly authorized and only if an isolated manifest path option is confirmed from the existing CLI/source. If no isolated manifest path support exists, Candidate B execution must stop before running `report export --record-manifest`.

## Stop Conditions

Stop before continuing if:

- working tree is dirty with unexpected files
- any source/runtime/log/report/config file would be changed
- any real write would be required in this selector phase
- any CE command would be required
- any request adds `--force`
- any request adds zip export
- any request adds wrapper export shortcuts
- any request weakens path guards or expands approved roots
