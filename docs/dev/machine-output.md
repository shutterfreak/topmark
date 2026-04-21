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
- **Registry commands**: `registry filetypes`, `registry processors`, `registry bindings`
- **Configuration commands**: `config check`, `config init`, `config defaults`, `config dump`
- **Version reporting**: `version`

This page is the canonical reference for TopMark’s machine output shapes. Usage guides for
individual commands (for example, [`check`](../usage/commands/check.md) and
[`strip`](../usage/commands/strip.md)) provide task-oriented examples consistent with this schema.

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
- Verbosity flags may change *which records are emitted* (e.g. detail vs summary), but they do not
  change the schema shape of a given record type (`kind`).

______________________________________________________________________

## Shared concepts

### MetaPayload

All machine outputs include a small metadata block, either:

- as the top-level `meta` key in JSON documents, or
- as the top-level `meta` key in every NDJSON record.

Shape:

```jsonc
{
  "meta": {
    "tool": "topmark",
    "version": "<package version>",
    "platform": "darwin",
    "detail_level": "brief" // or "long"
  }
}
```

Notes:

- `version` reflects the resolved TopMark package version (normally PEP 440), derived from Git tags
  via `setuptools-scm`. Examples are illustrative only.
- `platform` is a short runtime identifier (e.g., from `sys.platform`).
- `detail_level` is machine-facing and distinguishes the default projection (`"brief"`) from the
  expanded projection requested via `--long` (`"long"`) when a command surface emits that field.
  Registry machine output currently includes `detail_level`; other command families may omit it.

Shared metadata keys are defined in
\[`topmark.core.machine.schemas.MachineMetaKey`\][topmark.core.machine.schemas.MachineMetaKey].
Diagnostic-domain identifiers used in diagnostic payloads are defined in
\[`topmark.core.machine.schemas.MachineDomain`\][topmark.core.machine.schemas.MachineDomain].

Canonical keys are defined in \[`topmark.core.machine.schemas`\][topmark.core.machine.schemas].

For version-reporting commands, the machine-output metadata reflects the same runtime-resolved
package version used by `topmark version`, which is sourced from generated package version metadata
rather than a static config field.

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

Consumers should switch on the `kind` field rather than relying on ordering, though TopMark does
emit a stable prefix for some command families (see below).

Shared record construction and envelope serialization helpers live under
\[`topmark.core.machine`\][topmark.core.machine]. Domain-specific payload builders and record kinds
live in the corresponding `*.machine` packages.

Canonical `kind` strings are now owned by the schema module for the corresponding machine-output
package rather than a single monolithic core namespace. Shared envelope keys remain in
\[`topmark.core.machine.schemas`\][topmark.core.machine.schemas], while record kinds are defined in
package-local schema modules such as:

- \[`topmark.config.machine.schemas.ConfigKind`\][topmark.config.machine.schemas.ConfigKind]
- \[`topmark.pipeline.machine.schemas.PipelineKind`\][topmark.pipeline.machine.schemas.PipelineKind]
- \[`topmark.diagnostic.machine.schemas.DiagnosticKind`\][topmark.diagnostic.machine.schemas.DiagnosticKind]
- \[`topmark.registry.machine.schemas.RegistryKind`\][topmark.registry.machine.schemas.RegistryKind]
- \[`topmark.version.machine.schemas.VersionKind`\][topmark.version.machine.schemas.VersionKind]

______________________________________________________________________

## Processing commands (`check`, `strip`)

Processing commands produce either **detail** output (per-file results) or **summary** output
(bucket counts), depending on whether the CLI is in `--summary` mode.

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
- `config_diagnostics`: full diagnostics payload including counts and the list of config diagnostics
  as emitted by
  \[`topmark.config.machine.payloads.build_config_diagnostics_payload`\][topmark.config.machine.payloads.build_config_diagnostics_payload].
- `results`: one entry per processed file (see **Per-file result payload** below).

### JSON schema (summary mode)

Summary mode corresponds to `summary_mode = true`.

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "summary": [
    { "outcome": "unchanged", "reason": "up-to-date", "count": 30 },
    { "outcome": "would insert", "reason": "header missing, changes found", "count": 1 }
  ]
}
```

- `summary`: a **flat list of summary rows**, each representing a unique `(outcome, reason)` bucket
  with the number of files that produced that pair. This row shape corresponds to
  `OutcomeSummaryRow` in \[`topmark.pipeline.machine.schemas`\][topmark.pipeline.machine.schemas].

Important characteristics:

- The summary is **not nested by outcome**.
- Each row has three stable fields:
  - `outcome` — pipeline outcome (e.g. `inserted`, `replaced`, `unchanged`).
  - `reason` — short lowercase bucket reason used for grouping.
  - `count` — number of files in that bucket.
- Ordering is deterministic: outcomes follow the internal `Outcome` ordering and reasons are
  alphabetically sorted within each outcome.

### NDJSON schema (detail and summary)

NDJSON output is a stream with a stable prefix and then either result records (detail) or summary
records (summary).

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

In summary mode, per-file `result` records are replaced by one `summary` record per
`(outcome, reason)` bucket:

```jsonc
{"kind":"summary","meta":{ /* MetaPayload */ },"summary":{"outcome":"unchanged","reason":"up-to-date","count":30}}
{"kind":"summary","meta":{ /* MetaPayload */ },"summary":{"outcome":"skipped","reason":"known file type, headers not supported","count":1}}
```

NDJSON rules for processing commands:

- Every record includes `kind` and `meta`.
- Payload container key matches `kind`.
- The stream begins with:
  1. `config`
  1. `config_diagnostics` (**counts-only**)
  1. zero or more `diagnostic` records (each with `domain="config"`, using the shared
     diagnostic-domain value from
     \[`topmark.core.machine.schemas.MachineDomain`\][topmark.core.machine.schemas.MachineDomain])
- Then either:
  - detail mode: one `result` record per file
  - summary mode: one `summary` record per `(outcome, reason)` bucket

The NDJSON record stream is produced by:

- \[`topmark.pipeline.machine.envelopes.iter_processing_results_ndjson_records`\][topmark.pipeline.machine.envelopes.iter_processing_results_ndjson_records]
- serialization helpers in
  \[`topmark.pipeline.machine.serializers`\][topmark.pipeline.machine.serializers]

______________________________________________________________________

## Per-file result payload

Each element of the JSON `results` array (detail mode) and each NDJSON `result` record contains a
**per-file processing result payload**.

The exact field set can evolve over time, but the payload is intended to be:

- JSON-safe (no ANSI / terminal formatting),
- stable enough for CI/tooling integration,
- tolerant of additive changes.

The canonical builders and typing live under:

- \[`topmark.pipeline.machine.schemas`\][topmark.pipeline.machine.schemas] (TypedDict schemas /
  payload shapes)
- \[`topmark.pipeline.machine.payloads`\][topmark.pipeline.machine.payloads] (payload builders)
- \[`topmark.pipeline.machine.serializers`\][topmark.pipeline.machine.serializers] (JSON/NDJSON
  serialization)

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

> [!NOTE] Diffs (`--diff`) and any ANSI coloring are **human-only** and are not included in machine
> payloads.

______________________________________________________________________

## ConfigPayload

`ConfigPayload` is a JSON-safe representation of the effective `Config`, as produced by
\[`topmark.config.machine.payloads.build_config_payload`\][topmark.config.machine.payloads.build_config_payload].

High-level structure (keys may be extended over time):

- `fields`: header fields and their effective values.
- `header`: header-related configuration.
- `formatting`: formatting-related configuration.
- `writer`: persisted writer options and related settings (enums serialized to strings).
- `files`: file resolution/filtering options (paths serialized to strings).
- `policy`: global resolved policy flags (booleans).
- `policy_by_type`: per-file-type resolved policy overrides.

Normalization rules:

- `Path` → string
- `str`-backed `Enum` / `StrEnum` → string value (`.value`)
- other `Enum` values → enum member name (`.name`)
- nested mappings/sequences → standard JSON objects/arrays

For the current exact fields, see:

- \[`topmark.config.machine.schemas.ConfigPayload`\][topmark.config.machine.schemas.ConfigPayload]
- \[`topmark.config.machine.payloads.build_config_payload`\][topmark.config.machine.payloads.build_config_payload]

______________________________________________________________________

## ConfigDiagnosticsPayload

`ConfigDiagnosticsPayload` summarizes the flattened compatibility view derived from staged
config-validation logs.

These diagnostics may originate from staged validation logs for:

- TOML-source diagnostics
- merged-config diagnostics
- runtime-applicability diagnostics

For 1.0, the machine contract for config-validation diagnostics is this flattened compatibility
shape. Stage-local validation structure remains internal and is not serialized directly.

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

The individual diagnostic entry shape is intentionally fixed at `{level, message}` for 1.0.

Example JSON diagnostics payload:

```jsonc
{
  "diagnostic_counts": { "info": 0, "warning": 2, "error": 0 },
  "diagnostics": [
    { "level": "warning", "message": "Duplicate included file types found in config" },
    { "level": "warning", "message": "Unknown included file types specified" }
  ]
}
```

- `diagnostic_counts`: counts per level (`info`, `warning`, `error`)
- `diagnostics`: list of individual diagnostics (stable `{level, message}` entries; see
  \[`topmark.diagnostic.machine.schemas.DiagnosticKey`\][topmark.diagnostic.machine.schemas.DiagnosticKey])

> [!NOTE] In NDJSON, `config_diagnostics` is **counts-only** and each individual config diagnostic
> is emitted as a separate `diagnostic` record with `domain="config"` (one record per diagnostic).

Example NDJSON diagnostics records:

```jsonc
{"kind":"config_diagnostics","meta":{...},"config_diagnostics":{"diagnostic_counts":{"info":0,"warning":2,"error":0}}}
{"kind":"diagnostic","meta":{...},"diagnostic":{"domain":"config","level":"warning","message":"Duplicate included file types found in config"}}
{"kind":"diagnostic","meta":{...},"diagnostic":{"domain":"config","level":"warning","message":"Unknown included file types specified"}}
```

See:

- \[`topmark.config.machine.schemas.ConfigDiagnosticsPayload`\][topmark.config.machine.schemas.ConfigDiagnosticsPayload]
- \[`topmark.config.machine.payloads.build_config_diagnostics_payload`\][topmark.config.machine.payloads.build_config_diagnostics_payload]

______________________________________________________________________

## Config snapshot commands (`config dump`, `config defaults`, `config init`)

These commands produce a config snapshot without running the processing pipeline.

Notes:

- `config dump` emits the resolved config snapshot after discovery and merge.
- `config dump --show-layers` additionally emits a machine-readable `config_provenance` payload
  before the final flattened config snapshot.
- `config defaults` emits the built-in default configuration snapshot.
- `config init` emits the same built-in default configuration snapshot in machine formats, even
  though its human-facing output is the bundled example TopMark TOML resource with comments.

### JSON shape for `config dump`, `config defaults`, `config init`

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ }
}
```

When `config dump` is invoked with `--show-layers`, the JSON envelope becomes:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config_provenance": {
    "layers": [
      {
        "origin": "<defaults>",
        "kind": "default",
        "precedence": 0,
        "toml": {
          "config": { "strict_config_checking": false },
          "writer": { "strategy": "atomic" }
        }
      }
    ]
  },
  "config": { /* ConfigPayload */ }
}
```

`config_provenance` is an inspection-oriented payload. Each layer contains:

- `origin` — provenance origin label
- `kind` — resolved config layer kind
- `precedence` — numeric layer precedence
- `scope_root` — optional scope root for discovered layers
- `toml` — the source-local TopMark TOML fragment contributed by that layer

### NDJSON shape for `config dump`, `config defaults`, `config init`

Default mode emits a single record:

```jsonc
{"kind": "config", "meta": { /* MetaPayload */ }, "config": { /* ConfigPayload */ }}
```

When `config dump` is invoked with `--show-layers`, NDJSON emits two records in order:

```jsonc
{"kind": "config_provenance", "meta": { /* MetaPayload */ }, "config_provenance": { /* TomlProvenancePayload */ }}
{"kind": "config", "meta": { /* MetaPayload */ }, "config": { /* ConfigPayload */ }}
```

## TomlProvenancePayload

`TomlProvenancePayload` is a machine-readable layered provenance export used by
`topmark config dump --show-layers`.

JSON shape:

```jsonc
{
  "layers": [
    {
      "origin": "<defaults>",
      "kind": "default",
      "precedence": 0,
      "toml": {
        "config": { "strict_config_checking": false },
        "header": { "fields": ["file", "file_relpath"] },
        "writer": { "strategy": "atomic" }
      }
    },
    {
      "origin": "/repo/pyproject.toml",
      "kind": "discovered",
      "precedence": 1,
      "scope_root": "/repo",
      "toml": {
        "fields": { "project": "TopMark" },
        "writer": { "strategy": "atomic" }
      }
    }
  ]
}
```

The payload is inspection-oriented rather than a loadable `topmark.toml` document. It mirrors the
human-facing layered TOML export by preserving ordered layers and the corresponding source-local
TopMark TOML fragments.

The outer `config_layers` container key belongs to the config machine-output domain, while the inner
provenance-layer fragment keys (`origin`, `kind`, `precedence`, `toml`, `scope_root`) are owned by
\[`topmark.toml.machine.schemas.TomlKey`\][topmark.toml.machine.schemas.TomlKey].

______________________________________________________________________

## `topmark config check`

This command validates configuration and emits the resolved config snapshot, configuration
diagnostics, and a `config_check` status payload.

### JSON shape for `config check`

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "config_check": {
    "ok": true,
    "strict_config_checking": false,
    "diagnostic_counts": { "info": 0, "warning": 1, "error": 0 },
    "config_files": ["..."]
  }
}
```

- `config`: resolved configuration snapshot.
- `config_diagnostics`: full diagnostics payload, including counts and the list of individual config
  diagnostics.
- `config_check`: command-status payload containing:
  - `ok` — whether validation succeeded
  - `strict_config_checking` — whether strict config-checking mode was enabled
  - `diagnostic_counts` — counts by diagnostic level
  - `config_files` — config files that contributed to the resolved config

The `strict_config_checking` field reflects the **effective validation strictness** used for the
run. It is derived from TOML source configuration (`[config].strict_config_checking`) and may be
overridden by CLI or API inputs. This strictness is evaluated across staged config-loading/preflight
validation, while `config_diagnostics` remains the flattened compatibility view exposed in machine
output.

For 1.0, this is the explicit contract decision: staged validation remains primarily internal, and
machine output serializes only the flattened compatibility diagnostics surface.

### NDJSON shape for `config check`

Stream prefix:

```jsonc
{"kind":"config","meta":{...},"config":{...}}
{"kind":"config_diagnostics","meta":{...},"config_diagnostics":{"diagnostic_counts":{...}}}
{"kind":"diagnostic","meta":{...},"diagnostic":{"domain":"config","level":"warning","message":"..."}}
{"kind":"config_check","meta":{...},"config_check":{...}}
```

The NDJSON stream follows the same stable prefix pattern used by processing commands:

1. `config`
1. `config_diagnostics` (counts-only)
1. zero or more `diagnostic` records
1. one final `config_check` record

Notes:

- NDJSON follows the same **counts-only + one diagnostic per line** model for the flattened
  compatibility diagnostics view.

(See `topmark.config.machine.*` for canonical builders/serializers.)

Config-specific JSON payload keys and NDJSON kinds are defined in
\[`topmark.config.machine.schemas.ConfigKey`\][topmark.config.machine.schemas.ConfigKey] and
\[`topmark.config.machine.schemas.ConfigKind`\][topmark.config.machine.schemas.ConfigKind]. Shared
config diagnostic entry/count keys are defined in
\[`topmark.diagnostic.machine.schemas`\][topmark.diagnostic.machine.schemas].

______________________________________________________________________

## `topmark version`

### JSON shape for `version`

```jsonc
{
  "meta": { /* MetaPayload */ },
  "version_info": {
    "version": "<package version>",
    "version_format": "pep440"
  }
}
```

### NDJSON shape for `version`

```jsonc
{"kind":"version","meta":{ /* MetaPayload */ },"version_info":{ "version":"<package version>", "version_format":"pep440" }}
```

The NDJSON `version` record kind is defined in
\[`topmark.version.machine.schemas.VersionKind`\][topmark.version.machine.schemas.VersionKind],
while JSON payload keys such as `version_info` are defined in
\[`topmark.version.machine.schemas.VersionKey`\][topmark.version.machine.schemas.VersionKey].

The version reported in machine output is derived from the installed package metadata / generated
version module, not from a manually maintained static field in `pyproject.toml`.

Notes:

- `version_format` may be `"pep440"` or `"semver"` depending on `--semver`.
- PEP 440 output is the canonical packaging version form used by Python packaging tools.
- If SemVer conversion is requested and fails, TopMark falls back to PEP 440 output.
- The machine envelope `kind` for this command is `version`, while the JSON payload container key is
  `version_info`.
- For development builds between release tags, the reported version may include SCM-derived
  dev/local segments such as commit identifiers.

______________________________________________________________________

## Registry commands

### `topmark registry filetypes`

JSON envelope:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "filetypes": [ /* FileTypeEntry ... */ ]
}
```

Brief entry (default):

```jsonc
{
  "local_key": "python",
  "namespace": "topmark",
  "qualified_key": "topmark:python",
  "description": "Python source file"
}
```

Detailed entry (`--long`):

```jsonc
{
  "local_key": "python",
  "namespace": "topmark",
  "qualified_key": "topmark:python",
  "description": "Python source file",
  "bound": true,
  "extensions": [".py"],
  "filenames": [],
  "patterns": [],
  "skip_processing": false,
  "has_content_matcher": false,
  "has_insert_checker": false,
  "policy": {
    "supports_shebang": true,
    "encoding_line_regex": null,
    "pre_header_blank_after_block": 1,
    "ensure_blank_after_header": true,
    "blank_collapse_mode": "strict",
    "blank_collapse_extra": ""
  }
}
```

NDJSON emits one record per file type:

```jsonc
{"kind":"filetype","meta":{...},"filetype":{ /* FileTypeEntry */ }}
```

Canonical schemas/builders live in `topmark.registry.machine.*`.

The corresponding NDJSON record kind is owned by
\[`topmark.registry.machine.schemas.RegistryKind`\][topmark.registry.machine.schemas.RegistryKind].

### `topmark registry processors`

JSON envelope:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "processors": [ /* ProcessorEntry ... */ ]
}
```

Processor entry (brief):

```jsonc
{
  "local_key": "python",
  "namespace": "topmark",
  "qualified_key": "topmark:python",
  "description": "Python-style line comment processor"
}
```

Processor entry (detailed, `--long`):

```jsonc
{
  "local_key": "python",
  "namespace": "topmark",
  "qualified_key": "topmark:python",
  "description": "Python-style line comment processor",
  "bound": true,
  "line_indent": "",
  "line_prefix": "# ",
  "line_suffix": "",
  "block_prefix": "",
  "block_suffix": ""
}
```

NDJSON emits one record per processor:

```jsonc
{"kind":"processor","meta":{...},"processor":{ /* ProcessorEntry */ }}
```

Canonical schemas/builders live in `topmark.registry.machine.*`.

The corresponding NDJSON record kind is owned by
\[`topmark.registry.machine.schemas.RegistryKind`\][topmark.registry.machine.schemas.RegistryKind].

### `topmark registry bindings`

JSON envelope:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "bindings": [ /* BindingEntry ... */ ],
  "unbound_filetypes": [ /* FileTypeRef ... */ ],
  "unused_processors": [ /* ProcessorRef ... */ ]
}
```

Binding entry (brief):

```jsonc
{
  "file_type_key": "topmark:python",
  "processor_key": "topmark:python"
}
```

Binding entry (detailed, `--long`):

```jsonc
{
  "file_type_key": "topmark:python",
  "file_type_local_key": "python",
  "file_type_namespace": "topmark",
  "processor_key": "topmark:python",
  "processor_local_key": "python",
  "processor_namespace": "topmark",
  "file_type_description": "Python source file",
  "processor_description": "Python-style line comment processor"
}
```

Auxiliary lists:

- `unbound_filetypes` contains file types that currently have no effective processor binding.
  - brief mode: qualified file type keys as strings
  - long mode: expanded `FileTypeRefEntry` objects
- `unused_processors` contains registered processors that do not currently participate in any
  effective binding.
  - brief mode: qualified processor keys as strings
  - long mode: expanded processor reference objects containing identity and description fields

NDJSON emits:

```jsonc
{"kind":"binding","meta":{...},"binding":{ /* BindingEntry */ }}
{"kind":"unbound_filetype","meta":{...},"unbound_filetype":"topmark:some_unbound_filetype"}
{"kind":"unused_processor","meta":{...},"unused_processor":"topmark:some_unused_processor"}
```

In brief mode, `unbound_filetype` and `unused_processor` NDJSON records carry qualified-key strings
as their payloads. In `--long` mode, those same record kinds carry expanded reference objects.

Canonical schemas/builders live in `topmark.registry.machine.*`.

The corresponding JSON payload keys and NDJSON record kinds are owned by
\[`topmark.registry.machine.schemas.RegistryKind`\][topmark.registry.machine.schemas.RegistryKind].

______________________________________________________________________

## Backwards compatibility and evolution

TopMark’s machine-output schema is part of its integration surface and may change between pre-1.0
releases.

Consumers should:

- Rely on `kind` for NDJSON.
- Treat unknown fields as optional/ignorable.
- Prefer parsing and schema-tolerant logic over strict string matching.
- Assume additive fields may appear over time.

Breaking changes should be signaled via Conventional Commits (using the `!` marker) and documented
in the changelog.
