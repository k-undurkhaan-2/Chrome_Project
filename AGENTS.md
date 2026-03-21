\# AGENTS.md



\## Purpose

This repository is managed as a structured codebase, not a dump folder.

Every change must preserve a clean repo layout, clear commit history, and explicit change reporting.



\## Repository layout rules

\- Keep the repo root clean.

\- Active source files belong in `src/`.

\- Reports and outputs belong in `reports/YYYY-MM-DD/`.

\- Legacy code and old versions belong in `history/`.

\- Runtime logs must not be committed.

\- Use `.gitignore` to exclude generated logs and other transient files.



\## File placement rules

\- Current active Lua modules go in `src/`.

\- Old `execute\_module` versions go in `history/execute-modules/`.

\- Legacy backup folders such as `pre\_fix` go in `history/pre-fix/`.

\- Regression and live-output text files go in `reports/YYYY-MM-DD/`.

\- Do not leave temporary, legacy, or generated files in the repo root unless explicitly required.



\## Commit policy

\- One logical change = one commit.

\- Do not use vague commit messages like `update`, `fix stuff`, `changes`, or `misc`.

\- Use this format:



`<type>(<scope>): <specific change>`



Examples:

\- `fix(mvp0): correct candidate ranking logic`

\- `refactor(mvp0): simplify report rendering flow`

\- `test(mvp0): add regression output samples`

\- `chore(repo): move legacy modules to history`

\- `docs(readme): clarify v2 branch structure`



\## Allowed commit types

\- `feat` = new feature

\- `fix` = bug fix

\- `refactor` = internal restructuring without behavior change

\- `test` = regression/test/output updates

\- `docs` = README, usage, comments, documentation

\- `chore` = repo cleanup, file moves, ignore rules, non-feature maintenance

\- `archive` = moving deprecated files into history



\## Scope rules

\- Use `mvp0` for changes to `mvp0\_candidate\_report.lua` and `mvp0\_foundlist\_collector.lua`

\- Use `execute-module` for execute module changes

\- Use `repo` for directory cleanup, renames, ignore rules, and structure changes

\- Use `readme` or `docs` for documentation work



\## Versioning policy

\- Do not create a version tag for every commit.

\- Suggest a version tag only when the repo reaches a milestone:

&#x20; - a stable runnable state

&#x20; - a completed migration

&#x20; - a cleanly verified regression checkpoint

&#x20; - a release-worthy snapshot

\- Use milestone-style tags such as:

&#x20; - `v2.0.0-alpha`

&#x20; - `v2.0.0-beta`

&#x20; - `v2.0.0`

&#x20; - `v2.0.1`



\## Required final response after every code change

After every implementation task, append a short structured report with exactly these sections:



\### Change Summary

\- What was changed

\- Why it was changed



\### Files Changed

\- List each added / modified / moved / deleted file



\### Suggested Commit Message

\- Provide exactly one recommended commit message

\- It must follow the repository commit policy



\### Version Tag Recommendation

\- State either:

&#x20; - `No new version tag recommended`

&#x20; - or `Recommended tag: <tag>`

\- Include one short reason



\### Validation

\- State what was checked

\- Example:

&#x20; - lint not run

&#x20; - tests not run

&#x20; - file structure verified

&#x20; - regression outputs updated



\### Notes

\- Mention any remaining risks, follow-up work, or manual steps



\## Behavior rules for Codex

\- Prefer minimal, clean changes over broad rewrites.

\- Preserve user intent and existing structure unless restructuring is explicitly needed.

\- When moving files, use the repository layout rules above.

\- When cleaning the repo, prefer moving legacy files into `history/` instead of deleting them, unless deletion is explicitly requested.

\- Do not commit generated logs.

\- If a task mixes code changes and repo cleanup, prefer separate commits unless the user explicitly asks for a single commit.



\## Definition of done

A task is not complete unless:

\- files are in the correct directories

\- legacy/generated files are handled correctly

\- a concrete commit message is proposed

\- version-tag advice is given

\- the final structured report is included

