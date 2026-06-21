# Python Tooling Source Manifest Behavior Policy

## Purpose

This policy records the Phase 10.2 STOP finding:

```text
--source-manifest content is not parsed in isolated bundle mode today.
```

It is documentation only. It does not change command behavior, add commands or options, modify Python source, modify tests, change wrapper behavior, run CE, or authorize report/bundle writes.

## Current Behavior Inventory

`report bundle export --source-manifest` exists as an isolated bundle-mode option.

Current isolated source mode behavior:

- validates `--source-manifest` path safety
- validates that the path exists
- validates that the path is a file
- validates that the path is under the approved `reports/python_tooling` root
- rejects the production/default `reports/python_tooling/manifest.jsonl` path for isolated validation
- does not read or parse `--source-manifest` file content
- constructs a synthetic single source-report manifest record from `--source-report`
- preserves the source report and source manifest as read inputs

Current rejection behavior:

- missing `--source-manifest` -> `SOURCE_MISSING`
- non-file `--source-manifest` -> `SOURCE_INVALID`
- guard-rejected `--source-manifest` -> `BAD_PATH` / `PATH_GUARD_REJECTED` / `PATH_REJECTED`
- existing malformed `--source-manifest` content -> no parse/invalid rejection surface, because content is not parsed in isolated source mode

Default manifest parsing is separate:

```text
_analyze_existing_manifest()
_parse_manifest_line()
INVALID_MANIFEST
```

Malformed default manifest content can return `INVALID_MANIFEST`. That surface is not the same as isolated `--source-manifest`.

## Near-Term Policy

Preserve current isolated source-manifest behavior:

```text
In isolated bundle mode, --source-manifest remains path/file validated but content-unparsed for now.
```

Reasons:

- current source does not parse the file content in isolated mode
- current behavior has been validated by previous phases
- adding content parsing would be behavior expansion, not wording cleanup
- adding content parsing could change success/rejection behavior for existing users
- wording implementation must not silently introduce a new rejection surface
- parse validation for isolated source manifests requires a separate behavior/surface contract

## Token Policy Correction

`MANIFEST_PARSE_FAILED` must not be implemented for isolated `--source-manifest` until a real content-parse rejection surface exists.

`MANIFEST_INVALID` must not be implemented for isolated `--source-manifest` until a real semantic-validation rejection surface exists.

Existing token scopes remain:

- `SOURCE_MISSING` for missing source manifest path
- `SOURCE_INVALID` for non-file source manifest path
- `BAD_PATH` / `PATH_REJECTED` / `PATH_GUARD_REJECTED` for guard-rejected source manifest path
- `INVALID_MANIFEST` for existing default manifest parse/validation failures

## Existing Parse Surface

The existing parse surface is default manifest parsing:

```text
reports/python_tooling/manifest.jsonl
_analyze_existing_manifest()
_parse_manifest_line()
INVALID_MANIFEST
```

This is a better near-term wording target because it already exists.

Potential future tokens for a separate default-manifest parse wording slice:

```text
INVALID_MANIFEST
MANIFEST_PARSE_FAILED
MANIFEST_INVALID
NO_FILES_WRITTEN
```

That future slice must inspect the current status/schema first and preserve JSON / `to_dict()` compatibility unless separately contracted.

## Future Behavior Option

If future product direction requires isolated `--source-manifest` content parsing, create a separate behavior contract such as:

```text
Phase 10.x - isolated source-manifest content validation surface contract
```

That contract must decide:

- what schema `--source-manifest` should use in isolated mode
- whether malformed content should reject
- whether empty manifest should reject or be valid
- whether records should be dereferenced
- compatibility and migration behavior
- tests and validation boundaries

Do not implement this in the current rejection wording track.

## Recommended Next Phase

Safer wording-only next step:

```text
Phase 10.3-contract - default manifest parse rejection wording contract
```

Alternative behavior-expansion path:

```text
Phase 10.x-contract - isolated source-manifest validation surface contract
```

The default manifest parse rejection contract is preferred because it targets an existing parser surface.
