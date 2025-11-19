<!--
topmark:header:start

  project      : TopMark
  file         : machine-output.md
  file_relpath : docs/dev/machine-output.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Machine output schema (JSON & NDJSON)

This document describes the JSON and NDJSON formats emitted by TopMark
for commands such as `check` and `strip`. It is intended for integrators
and tooling authors who consume TopMark programmatically.

This document is the canonical reference for TopMark's JSON and NDJSON schemas. The
usage guides for individual commands (for example, [`check`](../usage/commands/check.md)
and [`strip`](../usage/commands/strip.md)) provide task-oriented examples that are
consistent with this schema.

## Output formats

TopMark exposes four `--output-format` values:

- `default`: human-oriented text (not machine-stable).
- `markdown`: human-oriented Markdown (not machine-stable).
- `json`: single JSON document per invocation.
- `ndjson`: newline-delimited JSON stream.

The schemas below only apply to `json` and `ndjson`.

______________________________________________________________________

## JSON schema for processing commands

For processing commands (`check`, `strip`), JSON output follows one of
two shapes depending on whether the CLI is in *detail* or *summary* mode.

### Detail mode (`summary_mode = false`)

```json
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "results": [
    { /* per-file result entries */ }
  ]
}
```

- `meta`: small metadata block, including tool name and TopMark version.
- `config`: snapshot of the effective config as emitted by
  `build_config_payload` in `topmark.cli_shared.machine_output`.
- `config_diagnostics`: aggregate counts plus individual diagnostics
  originating from config load/merge/sanitize steps.
- `results`: one entry per processed file (see inline docs in
  `topmark.cli_shared.machine_output` for the exact per-file fields).

### Summary mode (`summary_mode = true`)

```json
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "summary": {
    /* aggregated counts per result bucket, etc. */
  }
}
```

- `summary`: aggregated view of per-file results, keyed by bucket name
  (for example `"unchanged"`, `"skipped"`, `"would strip"`). Each entry
  is an object with `count` and `label`, for example:

  ```jsonc
  "summary": {
    "unchanged": { "count": 30, "label": "[13] up-to-date" },
    "skipped":   { "count": 1,  "label": "[01] known file type, headers not supported" }
  }
  ```

The `config` and `config_diagnostics` envelopes are the same in both
detail and summary modes.

______________________________________________________________________

## NDJSON schema for processing commands

NDJSON output is a stream of records, each tagged with a `kind` field:

```json
{"kind": "config", "meta": { /* MetaPayload */ }, "config": { /* ConfigPayload */ }}
{"kind": "config_diagnostics", "config_diagnostics": { /* ConfigDiagnosticsPayload */ }}
{"kind": "result", "path": "README.md", "file_type": "markdown", /* per-file result fields */ }
{"kind": "summary", "key": "unchanged", "count": 30, "label": "[13] up-to-date"}
{"kind": "summary", "key": "skipped", "count": 1, "label": "[01] known file type, headers not supported"}
```

- The `config` record is always emitted first and includes the `meta` block.
- The `config_diagnostics` record follows immediately afterwards.
- Zero or more `result` records follow (one per processed file).
- In summary mode, one `summary` record per bucket, each with `key`, `count`, and `label` (no nested summary object).

Consumers are expected to switch on the `kind` field rather than relying
on positional assumptions.

______________________________________________________________________

## ConfigPayload

`ConfigPayload` is a JSON-safe representation of the effective `Config`,
as produced by `build_config_payload` in `topmark.cli_shared.machine_output`.

High-level structure:

- `fields`: header fields and their values.
- `header`: header-specific config such as:
  - `header_fields`
  - `field_values`
  - `align_fields`
  - `header_format`
- `formatting`: options that affect formatting behavior.
- `writer`: file write strategy and related options:
  - `strategy` (e.g. `"ATOMIC"`), serialized as a string.
  - `output_target` (if present).
- `files`: file resolution and filtering configuration:
  - `files`
  - `include_from`
  - `exclude_from`
  - `files_from`
  - `include_patterns`
  - `exclude_patterns`
  - `file_types`
  - `relative_to`

All values are normalized to JSON-safe types:

- `Path` values are rendered as strings.
- Enum values are rendered as their `.name` or equivalent string token.
- Nested mappings and lists are represented using standard JSON objects
  and arrays.

For the exact schema, see the implementation and type hints of
`ConfigPayload` and `build_config_payload` in `topmark.cli_shared.machine_output`.

______________________________________________________________________

## ConfigDiagnosticsPayload

`ConfigDiagnosticsPayload` summarizes configuration diagnostics that
were collected during config discovery, merge, and sanitization.

High-level structure:

- `level_counts`: a mapping from diagnostic level to integer count, for
  example:

  ```json
  {
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 0
  }
  ```

- `messages` (optional, depending on implementation and verbosity):
  a list of individual diagnostics, each typically containing:

  - `level` (e.g. `"WARNING"`)
  - `message`
  - optional metadata (e.g. codes, paths)

The aggregated counts are meant to support quick triage; individual
messages can be used to drive more detailed tooling behavior. See
`ConfigDiagnosticsPayload` and `build_config_diagnostics_payload` in
`topmark.cli_shared.machine_output` for the current structure.

______________________________________________________________________

## Per-file result entries

Each `result` record in NDJSON and each element of the `results` array
in JSON represents a single processed file.

Exact fields may evolve, but currently include:

- `path`: file path (relative to CWD as seen by the CLI).

- `file_type`: resolved TopMark file type identifier (e.g., `"markdown"`, `"python"`).

- `steps`: ordered list of executed step names (e.g., `"ResolverStep"`, `"SnifferStep"`, …).

- `step_axes`: mapping from step name to the list of axes that step may write, e.g.:

  ```jsonc
  "step_axes": {
    "ResolverStep": ["resolve"],
    "SnifferStep": ["fs"],
    "ReaderStep": ["content"],
    "ScannerStep": ["header"],
    "BuilderStep": ["generation"],
    "RendererStep": ["render"],
    "ComparerStep": ["comparison"]
  }
  ```

- `step_axes`: mapping from step name to the list of axes that step may write, e.g.:

  ```jsonc
  "step_axes": {
    "ResolverStep": ["resolve"],
    "SnifferStep": ["fs"],
    "ReaderStep": ["content"],
    "ScannerStep": ["header"],
    "BuilderStep": ["generation"],
    "RendererStep": ["render"],
    "ComparerStep": ["comparison"]
  }
  ```

- `status`: mapping from axis name (`"resolve"`, `"fs"`, `"content"`, …) to an object of the
  form `{ "axis", "name", "label" }` as produced by `HeaderProcessingStatus.to_dict()`, for example:

  ```jsonc
  "status": {
    "resolve":   { "axis": "resolve",   "name": "RESOLVED", "label": "resolved" },
    "fs":        { "axis": "fs",        "name": "OK",       "label": "ok" },
    "content":   { "axis": "content",   "name": "OK",       "label": "ok" },
    "header":    { "axis": "header",    "name": "DETECTED", "label": "header detected" },
    "generation":{ "axis": "generation","name": "GENERATED","label": "header fields generated" },
    "render":    { "axis": "render",    "name": "RENDERED", "label": "header fields rendered" },
    "strip":     { "axis": "strip",     "name": "PENDING",  "label": "stripping pending" },
    "comparison":{ "axis": "comparison","name": "UNCHANGED","label": "no changes found" },
    "plan":      { "axis": "plan",      "name": "PENDING",  "label": "update pending" },
    "patch":     { "axis": "patch",     "name": "PENDING",  "label": "patch pending" },
    "write":     { "axis": "write",     "name": "PENDING",  "label": "write pending" }
  }
  ```

- `views`: view-related fields, such as:

  - `image_lines`
  - `header_range`
  - `header_fields`
  - `build_selected`
  - `render_line_count`
  - `updated_has_lines`
  - `diff_present`

- `diagnostics`: list of per-file diagnostics (if any).

- `diagnostic_counts`: summary counts per diagnostic level (`info`, `warning`, `error`).

- `pre_insert_check`: capability assessment for header insertion/stripping with:

  - `capability` (e.g., `"UNEVALUATED"`)
  - `reason`
  - `origin`

- `outcome`: outcome summary, including:

  - `would_change`, `can_change`, `permitted_by_policy`
  - nested `check` and `strip` objects (e.g., `would_add_or_update`, `effective_would_strip`).

The canonical reference is the type and builder used by
`build_processing_results_payload` in `topmark.cli_shared.machine_output`.

______________________________________________________________________

## Config-only commands

For config-only commands:

- `topmark config dump`
- `topmark config defaults`
- `topmark config init`

the JSON/NDJSON output is intentionally simpler.

### JSON

JSON output for config-only commands is just the `ConfigPayload`:

```json
{
  "meta": { /* MetaPayload */ },
  "config": {
    "fields": { /* ... */ },
    "header": { /* ... */ },
    "formatting": { /* ... */ },
    "writer": { /* ... */ },
    "files": { /* ... */ }
  }
}
```

No `config_diagnostics`, `results`, or `summary` fields are included,
because these commands do not run the processing pipeline.

### NDJSON

NDJSON output for config-only commands consists of a single record:

```json
{"kind": "config", "meta": { /* MetaPayload */ }, "config": { /* ConfigPayload */ }}
```

No `config_diagnostics` record is emitted for these commands; they are
intended for static config snapshots rather than full pipeline runs.

______________________________________________________________________

## Backwards compatibility and evolution

The machine-output schema described here is considered part of TopMark’s
integration surface and may change between pre-1.0 releases. When
breaking changes are introduced, they are announced via Conventional
Commits (using the `!` marker) and documented in the changelog.

Consumers should:

- Rely on the `kind` field for NDJSON decoding.
- Treat unknown fields as optional / ignorable.
- Prefer robust JSON parsing over strict string matching of text output.
