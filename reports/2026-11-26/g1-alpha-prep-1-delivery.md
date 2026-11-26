# G1-ALPHA-PREP-1 delivery

> Historical evidence only; not current operating instructions. Original recorded values and authority are unchanged. [Immutable original](https://github.com/k-undurkhaan-2/Chrome_Project/blob/f67c2b1ab619b4a03fa6e8ce055ea4a3fe3b5b5b/reports/2026-11-26/g1-alpha-prep-1-delivery.md). Current product guidance: [English Quickstart](../../docs/ce_mvp_quickstart.md).

Status: `PARTIAL_G1_ALPHA_PREP_1`.

The usable candidate evaluates an explicitly supplied owned table snapshot through
the existing AC6 full-population interface and emits the proposed Rank-1, the
ordinary recommendation/report and the complete completion envelope. It has no
application action/readback or live lifecycle interface. This is a read-only
candidate, not a completed action loop or an Alpha acceptance/release decision.

## Changes and delivery identity

- Baseline: `b13ea8b12b6b57f981227b06abf1a31a3a3907cd` on `armedforces.io-v2`.
- Implementation: `bbc92001814e118206852eb65399a28d2673f617`,
  `feat(mvp0): add read-only Alpha candidate launcher`.
- The baseline and its five preceding commits through the AC6 connection had
  locally valid GPG signatures. Before editing, the remote branch matched the
  baseline and GitHub reported its signature as verified/valid.
- The implementation was committed with GPG signing immediately after its
  targeted checks, pushed over HTTPS using the local gh credential helper, and
  independently read back through the GitHub API. The exact commit, sole parent
  (the baseline), verified/valid signature and branch HEAD matched.
- This follow-up documentation commit adds the operator sheet and this record.
  Its final commit identity and remote verification are reported in the task
  response; no self-referential commit hash is embedded here.

Files added: `src/run_alpha_candidate.py`,
`src/examples/g1_alpha_population.example.json`, `tests/test_alpha_candidate.py`,
`docs/g1_alpha_manual_acceptance.md`, and this report. `README.md` links the new
entry point and its scope. Existing AC5/AC6 scoring modules, native interfaces,
product configuration and historical qualification records are unchanged.

The launcher validates the provider's finite-population declaration and source
identity sequence, then delegates ordinary record validation, coverage,
eligibility, scoring, cohort context, global ranking and recommendation to AC6.
Truth is absent from the example and rejected by the JSON interface. Full mode
never changes to bounded on failure. Bounded remains explicitly labelled and
does not supply the full-population proposal. Action permission is always false.
Errors retain their original exception/traceback; cancellation and errors do not
retry or reuse a previous result.

## Actual validation

Environment: Windows 11 build 22631, PowerShell 7.6.9, CPython 3.14.3 x64,
Lupa 2.8 with Lua 5.3 and Lua 5.4.

Command executed:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/test_alpha_candidate.py -q --basetemp reports/2026-11-26/g1_alpha_pytest_tmp
```

Result: **32 passed in 3.28 seconds**, no failures or skips. These are small
launcher regressions in the existing pytest suite, not a new qualification
matrix or an accuracy campaign. They cover:

- A 137-record maintained fixture through each Lua version: complete AC6
  envelope parity, except the seven existing timing fields in collection/filter;
  137 fully scored/ranked records and exact eligible/ranked membership. The
  separately asserted expected Rank-1 is not supplied to the evaluator.
- The shipped example, empty, weak, ambiguous, bounded and duplicate controls;
  original recommendations and no action permission in every case.
- Invalid/incomplete declarations, mismatched count/identity sequence, truth,
  duplicate JSON keys, invalid full-mode budgets and attempted action options.
- Cancellation, deadline and operation-independent exception propagation through
  the Lua hook and CLI; one attempt only, with no successful stdout or restart.
- Input-file change before publication and input/output resource-limit refusal.
- The actual source entry point launched from outside the repository directory.

Actual ordinary invocations also ran the shipped example in both Lua versions,
including complete JSON output. Both returned:

| Field | Observed result |
| --- | --- |
| status / mode / completion | COMPLETE / full / completed=true / population_complete=true |
| supplied / distinct / eligible / selected / fully_scored / ranked | 3 / 3 / 3 / 3 / 3 / 3 |
| duplicates / excluded | 0 / 0 |
| proposed Rank-1 / score | 1048872 / 46 |
| ordinary recommendation | ACCEPT, HIGH, manual_review_required=false |
| action permission / recovery | false / false |

The exact PowerShell observation and incomplete-input blocks in the operator
sheet were executed against a disposable copy of the public example. Normal
exit was 0; the incomplete declaration exited 1 with
`ALPHA_POPULATION_NOT_DECLARED_COMPLETE` and empty stdout. The documented help
command, local documentation links and whitespace checks passed. New-environment
installation commands were not rerun because the dependencies already existed.

The 32 baseline hashes of existing modified, untracked source/document/test and
private-configuration files were unchanged before the implementation commit.
Only exact task paths were staged. Runtime evidence is local and uncommitted:
`g1_alpha_tests.log`, `g1_alpha_example_lua53.log`,
`g1_alpha_example_lua54.log`, and `g1_alpha_code_remote.log` under this report
directory. No runtime log or private configuration is part of the commit.

## Unsupported, not run, and retained state

Application action/readback, application-reported exit/identity changes and
object validity/operation failures are **UNSUPPORTED** by this candidate. The
repository has a table-only AC6 interface, CE-dependent operation paths and
synthetic qualification doubles; none supplies the required existing owned
application operation/lifecycle integration. File stability is not process or
semantic object identity. No simulated operation is labelled an integrated
cycle. The candidate remains unable to authorize any action on unknown state.

Maintainer manual real-machine acceptance, native/CE qualification and production or
third-party operation were **NOT_RUN**. AC8/AC9, F2/F3, N1/N2 and the full G1
matrix were not rerun. The N1/N2 completion receipts and the registered S2/S3
contract were read and reused: N1 includes two completed 18,498-record pools;
N2 records 364 passed tests. AC8's 100/100 Rank-1 and AC9's 103/103 parity remain
historical domain-limited evidence, not new independent observations.

The small launcher uses an 8 MiB input refusal limit, the existing small-test
256 MiB Lua allocator ceiling, a cooperative 240-second deadline and a 256 MiB
post-serialization output refusal limit. It does not reproduce the historical
large-worker supervisor, host-commit admission, hard process termination or
sampled private-memory guard. No large-input capacity, native performance or
universal semantic-validity claim follows. Existing historical resource policy
and native protections are unchanged.

G1 remains **0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**. Preserve historical
AC/PAIR conclusions, `IMPLEMENTED_PENDING_CE_QUALIFICATION`,
`ATTACHMENT_HANDLE_UNVERIFIED`, `NOT_PRODUCTION_AUTHORIZED`,
`QSG_NATIVE_BACKEND_NOT_QUALIFIED`, `HISTORICAL_ROOT_CAUSE=INDETERMINATE`, and
N0/MIN/LOCAL publishing suspension. Alpha Pre-release remains BLOCKED. No tag,
release, new branch or PR was created. No new version tag is recommended.

Next action: the maintainer can run the delivered
[Chinese operator sheet](https://github.com/k-undurkhaan-2/Chrome_Project/blob/f67c2b1ab619b4a03fa6e8ce055ea4a3fe3b5b5b/docs/g1_alpha_manual_acceptance.md) for the
read-only candidate now, retain actual observations including failures, and
decide its scoped acceptance. An action/lifecycle acceptance requires a suitable
existing owned application interface; this delivery does not claim it exists.
