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

This document describes the **machine-stable** JSON and NDJSON formats emitted by TopMark.

It is intended for integrators and tooling authors who consume TopMark programmatically.

Covered command groups:

- **Processing commands**: `check`, `strip`
- **Registry commands**: `filetypes`, `processors`
- **Configuration commands**: `config check`, `config init`, `config defaults`, `config dump`
- **Version reporting**: `version`

This page is the canonical reference for TopMark’s machine output shapes. Usage guides for individual commands (for example, [`check`](../usage/commands/check.md) and [`strip`](../usage/commands/strip.md)) provide task-oriented examples consistent with this schema.

## Output formats

TopMark exposes four `--output-format` values:

- human-oriented formats (not machine-stable):
  - `text`: default human-oriented text.
  - `markdown`: human-oriented Markdown.
- machine formats (schema described in this document):
  - `json`: a single JSON document per invocation.
  - `ndjson`: a newline-delimited JSON stream.

The schemas below only apply to **`json`** and **`ndjson`**.

Notes:

- Machine formats never include ANSI color codes and are **not affected** by `--color`.
- Verbosity flags may change *which records are emitted* (e.g. detail vs summary),
  but they do not change the schema shape of a given record type (`kind`).

______________________________________________________________________

## Shared concepts

### MetaPayload

All machine outputs include a small metadata block, either:

- as the top-level `meta` key in JSON, or
- as the top-level `meta` key in every NDJSON record.

Shape:

```jsonc
{
  "meta": {
    "tool": "topmark",
    "version": "<package version>",
    "platform": "darwin" // optional
  }
}
```

Notes:

- `version` reflects the installed TopMark package version (PEP 440). Examples are illustrative only.
- `platform` is a short runtime identifier (e.g., from `sys.platform`).

Canonical keys are defined in \[`topmark.core.machine.schemas`\][topmark.core.machine.schemas].

### NDJSON record contract

NDJSON output is a stream of JSON objects (“records”). Each record:

- MUST include:
  - `kind` (string)
  - `meta` (MetaPayload)
- MUST store its payload under a **container key that matches** `kind`.

Example:

```json
{"kind":"config","meta":{...},"config":{...}}
```

Consumers should switch on the `kind` field rather than relying on ordering, though TopMark does emit a stable prefix for some command families (see below).

Record construction and serialization helpers live under \[`topmark.core.machine`\][topmark.core.machine].

Canonical `kind` strings are defined in \[`topmark.core.machine.schemas.MachineKind`\][topmark.core.machine.schemas.MachineKind].

______________________________________________________________________

## Processing commands (`check`, `strip`)

Processing commands produce either **detail** output (per-file results) or **summary** output (bucket counts), depending on whether the CLI is in `--summary` mode.

### JSON schema (detail mode)

Detail mode corresponds to `summary_mode = false`.

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "results": [
    { /* per-file result payload */ }
  ]
}
```

- `meta`: small metadata block, including tool name and TopMark version.
- `config`: snapshot of the effective config as emitted by
  \[`topmark.config.machine.payloads.build_config_payload`\][topmark.config.machine.payloads.build_config_payload].
- `config_diagnostics`: full diagnostics payload including counts and the list of config diagnostics as emitted by
  \[`topmark.config.machine.payloads.build_config_diagnostics_payload`\][topmark.config.machine.payloads.build_config_diagnostics_payload].
- `results`: one entry per processed file (see **Per-file result payload** below).

### JSON schema (summary mode)

Summary mode corresponds to `summary_mode = true`.

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "summary": {
    /* aggregated counts per outcome bucket */
  }
}
```

- `summary`: mapping of bucket key → `{count, label}`:

  ```jsonc
  "summary": {
    "unchanged":    { "count": 30, "label": "up-to-date" },
    "would insert": { "count":  1, "label": "header missing, changes found" }
  }
  ```

The JSON envelopes and summary payload shapes are built in:

- \[`topmark.pipeline.machine.shapes.build_processing_results_json_envelope`\][topmark.pipeline.machine.shapes.build_processing_results_json_envelope]
- \[`topmark.pipeline.machine.payloads`\][topmark.pipeline.machine.payloads] (summary payload helpers)

### NDJSON schema (detail and summary)

NDJSON output is a stream with a stable prefix and then either result records (detail) or summary records (summary).

Example stream:

```jsonc
{"kind": "config", "meta": { /* MetaPayload */ }, "config": { /* ConfigPayload */ }}

{"kind": "config_diagnostics",
 "meta": { /* MetaPayload */ },
 "config_diagnostics": { "diagnostic_counts": {"info": 0, "warning": 1, "error": 0} } }

{"kind": "diagnostic",
 "meta": { /* MetaPayload */ },
 "diagnostic": { "domain": "config", "level": "warning", "message": "..." } }

{"kind": "result",
 "meta": { /* MetaPayload */ },
 "result": { /* per-file result payload */ } }
```

In summary mode, per-file `result` records are replaced by one `summary` record per bucket:

```jsonc
{"kind": "summary", "meta": { /* MetaPayload */ }, "summary": {"key": "unchanged", "count": 30, "label": "up-to-date"}}
{"kind": "summary", "meta": { /* MetaPayload */ }, "summary": {"key": "skipped", "count": 1, "label": "known file type, headers not supported"}}
```

NDJSON rules for processing commands:

- Every record includes `kind` and `meta`.
- Payload container key matches `kind`.
- The stream begins with:
  1. `config`
  1. `config_diagnostics` (**counts-only**)
  1. zero or more `diagnostic` records (each with `domain="config"`)
- Then either:
  - detail mode: one `result` record per file
  - summary mode: one `summary` record per bucket

The NDJSON record stream is produced by:

- \[`topmark.pipeline.machine.shapes.iter_processing_results_ndjson_records`\][topmark.pipeline.machine.shapes.iter_processing_results_ndjson_records]
- serialization helpers in \[`topmark.pipeline.machine.serializers`\][topmark.pipeline.machine.serializers]

______________________________________________________________________

## Per-file result payload

Each element of the JSON `results` array (detail mode) and each NDJSON `result` record contains a **per-file processing result payload**.

The exact field set can evolve over time, but the payload is intended to be:

- JSON-safe (no ANSI / terminal formatting),
- stable enough for CI/tooling integration,
- tolerant of additive changes.

The canonical builders and typing live under:

- \[`topmark.pipeline.machine.schemas`\][topmark.pipeline.machine.schemas] (TypedDict schemas / payload shapes)
- \[`topmark.pipeline.machine.payloads`\][topmark.pipeline.machine.payloads] (payload builders)
- \[`topmark.pipeline.machine.serializers`\][topmark.pipeline.machine.serializers] (JSON/NDJSON serialization)

At a high level, per-file results include:

- identity:
  - `path`
  - `file_type` (resolved TopMark file type key)
- pipeline execution:
  - executed step names
  - per-axis status objects (`axis`, `name`, `label`)
- derived intent/outcome helpers:
  - change intent / feasibility booleans
  - strip/insert/update intent summaries
- optional diagnostics (per-file):
  - list of diagnostics (when requested / enabled)
  - pre-computed diagnostic counts

> [!NOTE]
> Diffs (`--diff`) and any ANSI coloring are **human-only** and are not included in machine payloads.

______________________________________________________________________

## ConfigPayload

`ConfigPayload` is a JSON-safe representation of the effective `Config`,
as produced by \[`topmark.config.machine.payloads.build_config_payload`\][topmark.config.machine.payloads.build_config_payload].

High-level structure (keys may be extended over time):

- `fields`: header fields and their effective values.
- `header`: header-related configuration.
- `formatting`: formatting-related configuration.
- `writer`: write strategy and related options (enums serialized to strings).
- `files`: file resolution/filtering options (paths serialized to strings).
- `policy`: global resolved policy flags (booleans).
- `policy_by_type`: per-file-type resolved policy overrides.

Normalization rules:

- `Path` → string
- `Enum` → string token (typically `.name`)
- nested mappings/sequences → standard JSON objects/arrays

For the current exact fields, see:

- \[`topmark.config.machine.schemas.ConfigPayload`\][topmark.config.machine.schemas.ConfigPayload]
- \[`topmark.config.machine.payloads.build_config_payload`\][topmark.config.machine.payloads.build_config_payload]

______________________________________________________________________

## ConfigDiagnosticsPayload

`ConfigDiagnosticsPayload` summarizes configuration diagnostics collected during config discovery/merge/sanitization.

JSON shape:

```jsonc
{
  "diagnostic_counts": { "info": 1, "warning": 2, "error": 0 },
  "diagnostics": [
    { "level": "warning", "message": "..." },
    { "level": "info", "message": "..." }
  ]
}
```

- `diagnostic_counts`: counts per level (`info`, `warning`, `error`)
- `diagnostics`: list of individual diagnostics (stable `{level, message}` entries; see \[`topmark.diagnostic.machine.schemas`\][topmark.diagnostic.machine.schemas])

> [!NOTE]
> **NDJSON difference**
>
> In NDJSON, `config_diagnostics` is **counts-only** and each individual config diagnostic is emitted as a separate `diagnostic` record with `domain="config"` (one record per diagnostic).

See:

- \[`topmark.config.machine.schemas.ConfigDiagnosticsPayload`\][topmark.config.machine.schemas.ConfigDiagnosticsPayload]
- \[`topmark.config.machine.payloads.build_config_diagnostics_payload`\][topmark.config.machine.payloads.build_config_diagnostics_payload]

______________________________________________________________________

## Config-only commands (`config dump`, `config defaults`, `config init`)

These commands produce a config snapshot without running the processing pipeline.

### JSON shape

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ }
}
```

### NDJSON shape

A single record:

```jsonc
{"kind": "config", "meta": { /* MetaPayload */ }, "config": { /* ConfigPayload */ }}
```

______________________________________________________________________

## `topmark config check`

This command validates configuration and emits diagnostics plus a summary.

### JSON shape

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "config_check": {
    "ok": true,
    "strict": false,
    "diagnostic_counts": { "info": 0, "warning": 1, "error": 0 },
    "config_files": ["..."]
  }
}
```

### NDJSON shape

Stream prefix:

```jsonc
{"kind":"config","meta":{...},"config":{...}}
{"kind":"config_diagnostics","meta":{...},"config_diagnostics":{"diagnostic_counts":{...}}}
{"kind":"diagnostic","meta":{...},"diagnostic":{"domain":"config","level":"warning","message":"..."}}
{"kind":"config_check","meta":{...},"config_check":{...}}
```

Notes:

- NDJSON follows the same **counts-only + one diagnostic per line** model for config diagnostics.

(See `topmark.config.machine.*` for canonical builders/serializers.)

______________________________________________________________________

## `topmark version`

### JSON shape

```jsonc
{
  "meta": { /* MetaPayload */ },
  "version_info": {
    "version": "<package version>",
    "version_format": "pep440"
  }
}
```

### NDJSON shape

```jsonc
{"kind":"version","meta":{ /* MetaPayload */ },"version_info":{ "version":"<package version>", "version_format":"pep440" }}
```

Notes:

- `version_format` may be `"pep440"` or `"semver"` depending on `--semver`.
- If SemVer conversion is requested and fails, TopMark falls back to PEP 440 output.

______________________________________________________________________

## Registry commands

### `topmark filetypes`

JSON envelope:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "filetypes": [ /* FileTypeEntry ... */ ]
}
```

Brief entry (default):

```json
{ "name": "python", "description": "Python source file" }
```

Detailed entry (`--show-details`):

```jsonc
{
  "name": "python",
  "description": "Python source file",
  "extensions": [".py"],
  "filenames": [],
  "patterns": [],
  "skip_processing": false,
  "has_content_matcher": false,
  "has_insert_checker": false,
  "header_policy": "DefaultHeaderPolicy"
}
```

NDJSON emits one record per file type:

```jsonc
{"kind":"filetype","meta":{...},"filetype":{ /* FileTypeEntry */ }}
```

Canonical schemas/builders live in `topmark.registry.machine.*`.

### `topmark processors`

JSON envelope:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "processors": {
    "processors": [ /* ProcessorEntry ... */ ],
    "unbound_filetypes": [ /* FileTypeRef ... */ ]
  }
}
```

Processor entry (brief):

```jsonc
{
  "module": "topmark.pipeline.processors.python",
  "class_name": "PythonHeaderProcessor",
  "filetypes": ["python", "python-script"]
}
```

Processor entry (detailed, `--show-details`):

```jsonc
{
  "module": "topmark.pipeline.processors.python",
  "class_name": "PythonHeaderProcessor",
  "filetypes": [
    { "name": "python", "description": "Python source file" },
    { "name": "python-script", "description": "Python executable script" }
  ]
}
```

NDJSON emits one record per processor and per unbound file type:

```jsonc
{"kind":"processor","meta":{...},"processor":{ /* ProcessorEntry */ }}
{"kind":"unbound_filetype","meta":{...},"unbound_filetype":{ /* FileTypeRef */ }}
```

Canonical schemas/builders live in `topmark.registry.machine.*`.

______________________________________________________________________

## Backwards compatibility and evolution

TopMark’s machine-output schema is part of its integration surface and may change between pre-1.0 releases.

Consumers should:

- Rely on `kind` for NDJSON.
- Treat unknown fields as optional/ignorable.
- Prefer parsing and schema-tolerant logic over strict string matching.
- Assume additive fields may appear over time.

Breaking changes should be signaled via Conventional Commits (using the `!` marker) and documented in the changelog.
