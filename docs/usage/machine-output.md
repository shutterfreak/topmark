<!--
topmark:header:start

  project      : TopMark
  file         : machine-output.md
  file_relpath : docs/usage/machine-output.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Machine-readable output

This document describes the stable machine-readable JSON and NDJSON formats emitted by TopMark for
the 1.x line.

It is intended for integrators and tooling authors who consume TopMark programmatically.

Covered command groups:

- **Processing commands**: [`check`](../usage/commands/check.md),
  [`strip`](../usage/commands/strip.md)
- **Resolution diagnostics**: [`probe`](../usage/commands/probe.md)
- **Registry commands**: [`registry filetypes`](../usage/commands/registry/filetypes.md),
  [`registry processors`](../usage/commands/registry/processors.md),
  [`registry bindings`](../usage/commands/registry/bindings.md)
- **Configuration commands**: [`config check`](../usage/commands/config/check.md),
  [`config init`](../usage/commands/config/init.md),
  [`config defaults`](../usage/commands/config/defaults.md),
  [`config dump`](../usage/commands/config/dump.md)
- **Version reporting**: [`version`](../usage/commands/version.md)

This page is the canonical reference for TopMark's machine-readable output shapes. Usage guides for
individual commands (for example, [`check`](../usage/commands/check.md),
[`strip`](../usage/commands/strip.md), and [`probe`](../usage/commands/probe.md)) provide
task-oriented examples consistent with this schema.

{% include-markdown "\_snippets/terminology.md" %}

See also:

- [CLI overview](../usage/cli.md)
- [Shared options](../usage/shared-options.md)
- [Exit codes](../usage/exit-codes.md)
- [Configuration](../usage/configuration.md)
- [Filtering](../usage/filtering.md)
- [Registry model](../dev/registry-model.md)
- [Machine-readable format conventions](../dev/machine-formats.md)
- [Terminology and Canonical Vocabulary](../terminology.md)

## Output formats

TopMark exposes four stable `--output-format` values:

- human-oriented formats (not machine-stable):
  - `text`: default human-oriented text.
  - `markdown`: human-oriented Markdown.
- machine-readable formats (schema described in this document):
  - `json`: a single JSON document per invocation.
  - `ndjson`: a newline-delimited JSON stream.

The schemas below apply only to **`json`** and **`ndjson`**.

Notes:

- Machine-readable formats never include ANSI color codes and are **not affected** by `--color`.
- Machine-readable formats are independent of human-facing presentation controls.
- TEXT-only flags such as `-v` / `--verbose` and `-q` / `--quiet` do not affect machine-readable
  output.
- Markdown output is also independent from machine-readable formats and follows its own
  document-oriented contract.

______________________________________________________________________

## Exit codes and machine-readable output

Machine-readable output (`json`, `ndjson`) is intentionally **decoupled from CLI exit codes**:

- Exit codes are not embedded in JSON or NDJSON payloads.
- Structured payloads represent results, diagnostics, and resolution state only.

Consumers must:

- inspect the process exit code for success or failure semantics,
- parse machine-readable output for detailed diagnostics and results.

This design ensures a clean separation between:

- **process status** (exit code), and
- **structured data contract** (machine-readable output).

Refer to [`Exit codes`](../usage/exit-codes.md) for the full contract.

______________________________________________________________________

## Shared concepts

### MetaPayload

All machine-readable outputs include a small metadata block, either:

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
  Registry machine-readable output currently includes `detail_level`; other command families may
  omit it.

`detail_level` is distinct from TEXT verbosity (`-v`) and quiet mode (`--quiet`). It reflects an
explicit machine-facing projection such as `--long`, not presentation detail.

Shared metadata keys are defined in
\[`topmark.core.machine.schemas.MachineMetaKey`\][topmark.core.machine.schemas.MachineMetaKey].
Diagnostic-domain identifiers used in diagnostic payloads are defined in
\[`topmark.core.machine.schemas.MachineDomain`\][topmark.core.machine.schemas.MachineDomain].

Canonical keys are defined in \[`topmark.core.machine.schemas`\][topmark.core.machine.schemas].

For version-reporting commands, the machine-readable output metadata reflects the same
runtime-resolved package version used by [`topmark version`](../usage/commands/version.md), which is
sourced from generated package version metadata rather than a static config field.

### NDJSON record contract

NDJSON output is a stream of JSON objects ("records"). Each record:

- MUST include:
  - `kind` (string)
  - `meta` (MetaPayload)
- MUST store its payload under a **container key that matches** `kind`.

Example:

```json
{"kind":"config","meta":{...},"config":{...}}
```

Consumers should switch on the `kind` field rather than relying on ordering. Some command families
emit a stable prefix, as documented below.

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

### Naming conventions

The machine-readable output naming audit for the stable 1.x line adopts the following conventions
across domains:

- Shared envelope and metadata keys are owned by
  \[`topmark.core.machine.schemas`\][topmark.core.machine.schemas].
- JSON uses **domain-specific aggregated keys** (for example `filetypes`, `processors`, `bindings`,
  `results`, `probes`, `config_layers`) rather than a generic container such as `items`.
- NDJSON uses **singular record kinds** (for example `filetype`, `processor`, `binding`, `result`,
  `probe`, `summary`) and stores each payload under a container key that matches `kind`.
- Header processor identities and file type identities in machine-readable output always report
  canonical qualified keys such as `topmark:pound` and `topmark:python` when a resolved identity is
  available.
- Decomposed identities use `namespace` + `local_key`.
- Relationship references use `*_key` (for example `file_type_key`, `processor_key`).
- `detail_level` is an **extended metadata field** rather than baseline metadata:
  - baseline metadata is `tool`, `version`, `platform`
  - `detail_level` is emitted only by command families whose machine-readable output exposes a brief
    vs long projection

These conventions are part of the stable 1.x machine-readable output contract.

### File type identity fields

Machine-readable output uses the same canonical identity model as the runtime registry and
resolution system.

When a file type identity is present, payloads expose:

- `qualified_key`: canonical identifier, for example `topmark:python`;
- `namespace`: producer namespace, for example `topmark`;
- `local_key`: local identifier within the namespace, for example `python`.

Public inputs may use local identifiers such as `python` when unambiguous, but machine-readable
output emits resolved canonical identities. Consumers should prefer `qualified_key` for durable
comparisons and joins across payloads.

See [Registry model](../dev/registry-model.md#qualified-vs-local-identifiers) for the full identity
contract.

______________________________________________________________________

## Resolution diagnostics ([`probe`](../usage/commands/probe.md))

The [`topmark probe`](../usage/commands/probe.md) command exposes stable file-type and processor
resolution diagnostics. It is a diagnostic command, not a compliance or mutation command: it does
not compute header changes, diffs, strip plans, or write plans.

Probe output reports canonical file type identities after identifier normalization and file-type
filtering.

Probe machine-readable output is unaffected by TEXT verbosity or quiet mode. The JSON and NDJSON
formats expose the same resolution evidence used by the human-facing probe renderers:

- selected file type and selected processor
- probe status and reason
- all scored candidate file types
- candidate match signals
- explicit file inputs filtered during discovery before file-type probing
- explicit missing inputs that could not produce a normal resolution probe

### JSON schema

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* RuntimeConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "probes": [
    { /* per-path probe payload */ }
  ]
}
```

- `meta`: small metadata block, including tool name and TopMark version.
- `config`: snapshot of the effective runtime configuration used for file filtering and resolution
  policy.
- `config_diagnostics`: full diagnostics payload including counts and the list of config
  diagnostics.
- `probes`: one resolution probe payload per probed path, including explicit file inputs filtered
  before file-type probing and explicit missing inputs that could not produce a normal resolution
  probe.

### NDJSON schema

NDJSON output follows the same stable config prefix used by processing commands, then emits one
`probe` record per probe result:

```jsonc
{"kind":"config","meta":{...},"config":{...}}
{"kind":"config_diagnostics","meta":{...},"config_diagnostics":{"diagnostic_counts":{...}}}
{"kind":"diagnostic","meta":{...},"diagnostic":{"domain":"config","level":"warning","message":"..."}}
{"kind":"probe","meta":{...},"probe":{ /* per-path probe payload */ }}
```

NDJSON rules for `probe`:

- Every record includes `kind` and `meta`.
- Payload container key matches `kind`.
- The stream begins with:
  1. `config`
  1. `config_diagnostics` (**counts-only**)
  1. zero or more `diagnostic` records (each with `domain="config"`)
- Then one `probe` record is emitted per probe result.

The JSON `probes` key and NDJSON `probe` kind are defined in
\[`topmark.pipeline.machine.schemas.PipelineKey`\][topmark.pipeline.machine.schemas.PipelineKey] and
\[`topmark.pipeline.machine.schemas.PipelineKind`\][topmark.pipeline.machine.schemas.PipelineKind].
The NDJSON stream is produced by:

- \[`topmark.pipeline.machine.envelopes.iter_probe_results_ndjson_records`\][topmark.pipeline.machine.envelopes.iter_probe_results_ndjson_records]
- serialization helpers in
  \[`topmark.pipeline.machine.serializers`\][topmark.pipeline.machine.serializers]

______________________________________________________________________

## Per-path probe payload

Each element of the JSON `probes` array and each NDJSON `probe` record contains a **per-path
resolution probe payload**. Most probe payloads correspond to files that reached file-type probing,
but explicit file inputs filtered during discovery are also represented as probe payloads. Explicit
missing inputs are represented as `probe_missing` payloads when no normal resolution probe could be
recorded.

High-level shape:

```jsonc
{
  "path": "README.md",
  "status": "resolved",
  "reason": "selected_highest_score",
  "selected_file_type": {
    "qualified_key": "topmark:markdown",
    "namespace": "topmark",
    "local_key": "markdown",
    "score": 54
  },
  "selected_processor": {
    "qualified_key": "topmark:html",
    "namespace": "topmark",
    "local_key": "html"
  },
  "candidates": [
    {
      "qualified_key": "topmark:markdown",
      "namespace": "topmark",
      "local_key": "markdown",
      "score": 54,
      "selected": true,
      "tie_break_rank": 1,
      "match": {
        "extension": true,
        "filename": false,
        "pattern": false,
        "content_probe_allowed": false,
        "content_match": false,
        "content_error": null
      }
    }
  ]
}
```

Filtered explicit input shape:

```jsonc
{
  "path": "__pycache__/example.cpython-312.pyc",
  "status": "filtered",
  "reason": "excluded_by_path_filter",
  "selected_file_type": null,
  "selected_processor": null,
  "candidates": []
}
```

Missing explicit input shape:

```jsonc
{
  "path": "topmark-does-not-exist",
  "status": "probe_missing",
  "reason": "no_resolution_probe_result",
  "selected_file_type": null,
  "selected_processor": null,
  "candidates": []
}
```

Filtered probe payloads are emitted only for explicit file inputs supplied to
[`topmark probe`](../usage/commands/probe.md) (including paths loaded via `--files-from`). TopMark
does not enumerate every recursively discovered file that was ignored by discovery filters.

Explicit directories that successfully expand to selected child files are treated as discovery
sources and are not emitted as separate filtered probe payloads. Explicit missing inputs are emitted
as `probe_missing` payloads rather than filtered payloads.

Filtered probe payloads may use one of these reasons:

- `excluded_by_path_filter` - excluded by path-based include/exclude rules.
- `excluded_by_file_type_filter` - excluded by file-type include/exclude rules after identifier
  normalization to canonical qualified keys.
- `excluded_by_discovery_filter` - excluded before probing, but exact category was not identified.

Fields:

- `path`: probed or explicitly requested filesystem path. For filtered and missing explicit inputs,
  this is the path supplied to the command.
- `status`: probe status, currently one of:
  - `resolved` - a file type and processor were selected.
  - `unsupported` - no file type candidate matched.
  - `no_processor` - a file type was selected, but no processor binding was available.
  - `filtered` - an explicitly requested file input was filtered during discovery before file-type
    probing.
  - `probe_missing` - an explicit input could not produce a normal resolution probe payload.
- `reason`: machine-friendly explanation for the status and selection, for example:
  - `selected_highest_score`
  - `selected_by_tie_break`
  - `no_candidates`
  - `selected_file_type_has_no_bound_processor`
  - `excluded_by_path_filter`
  - `excluded_by_file_type_filter`
  - `excluded_by_discovery_filter`
  - `no_resolution_probe_result`
- `selected_file_type`: selected canonical file type identity and score, or `null` when unresolved,
  unbound, filtered, or missing.
- `selected_processor`: selected processor identity, or `null` when unresolved, unbound, filtered,
  or missing.
- `candidates`: scored candidate file types in deterministic resolution order. Empty for filtered
  explicit inputs, missing explicit inputs, and unsupported paths with no candidates.

Candidate fields:

- `qualified_key`, `namespace`, `local_key`: canonical file type identity fields. Consumers should
  prefer `qualified_key` for stable comparisons.
- `score`: resolver score for this candidate. Higher scores are preferred.
- `selected`: whether this candidate is the effective selected file type.
- `tie_break_rank`: one-based deterministic rank after score and tie-break ordering.
- `match`: probe-visible match signals:
  - `extension`
  - `filename`
  - `pattern`
  - `content_probe_allowed`
  - `content_match`
  - `content_error`

> [!NOTE]
>
> Scores are exposed for explainability and ordering. Automation should primarily rely on `status`,
> `selected`, and canonical identities (`qualified_key`, `namespace`, `local_key`) rather than
> hard-coding exact numeric scores.
>
> Filtered probe payloads have no candidate-level `match` object because file-type probing did not
> run. The reason identifies whether the path was excluded by path filters, file-type filters, or a
> generic discovery filter fallback.

Note:

- Explicit missing literal inputs are represented as `probe_missing` probe payloads and still fail
  the CLI invocation with `FILE_NOT_FOUND (66)`.
- Synthetic filtered probe entries may still appear for explicitly requested files that were
  filtered during discovery, but exit-code precedence is resolved at the CLI layer.

______________________________________________________________________

## Processing commands ([`check`](../usage/commands/check.md), [`strip`](../usage/commands/strip.md))

Processing commands produce either **detail** output (per-file results) or **summary** output
(bucket counts), depending on whether the CLI is in `--summary` mode.

Processing machine-readable output is unaffected by TEXT verbosity or quiet mode; those flags affect
only human TEXT output.

### JSON schema (detail mode)

Detail mode corresponds to `summary_mode = false`.

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* RuntimeConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "results": [
    { /* per-file result payload */ }
  ]
}
```

- `meta`: small metadata block, including tool name and TopMark version.
- `config`: snapshot of the effective runtime configuration as emitted by
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
  "config": { /* RuntimeConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "summary": [
    { "outcome": "unchanged", "reason": "up-to-date", "count": 30 },
    { "outcome": "would insert", "reason": "header missing, changes found", "count": 1 }
  ]
}
```

- `summary`: a **flat list of summary rows**, each representing a unique `(outcome, reason)` bucket
  with the number of files that produced that pair. This row shape corresponds to
  \[`OutcomeSummaryRow`\][topmark.pipeline.machine.schemas.OutcomeSummaryRow] in
  \[`topmark.pipeline.machine.schemas`\][topmark.pipeline.machine.schemas].

Important characteristics:

- The summary is **not nested by outcome**.
- Each row has three stable fields:
  - `outcome` - pipeline outcome (e.g. `inserted`, `replaced`, `unchanged`).
  - `reason` - short lowercase bucket reason used for grouping.
  - `count` - number of files in that bucket.
- Ordering is deterministic: outcomes follow the internal
  \[`Outcome`\][topmark.core.outcomes.Outcome] ordering and reasons are alphabetically sorted within
  each outcome.

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
- stable for CI and tooling integration,
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
  - `file_type` (resolved canonical TopMark file type key, for example `topmark:python`)
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
>
> - Diffs (`--diff`) and any ANSI coloring are **human-only** and are not included in machine
>   payloads.
> - Human presentation controls such as `-v` / `--verbose` and `-q` / `--quiet` are ignored by
>   machine-readable output. Consumers should use JSON/NDJSON fields rather than relying on TEXT or
>   Markdown rendering.

______________________________________________________________________

## ConfigPayload

\[`ConfigPayload`\][topmark.config.machine.schemas] is a JSON-safe representation of the effective
runtime configuration snapshot, derived from \[`FrozenConfig`\][topmark.config.model.FrozenConfig]
and produced by
\[`topmark.config.machine.payloads.build_config_payload`\][topmark.config.machine.payloads.build_config_payload].

High-level structure (keys may be extended over time):

- `fields`: header fields and their effective values.
- `header`: header-related configuration.
- `formatting`: formatting-related configuration.
- `writer`: persisted writer options and related settings (enums serialized to strings).
- `files`: file resolution/filtering options (paths serialized to strings).
- `policy`: global resolved policy flags (booleans).
- `policy_by_type`: per-file-type resolved policy overrides.

File type identifiers in `files.include_file_types`, `files.exclude_file_types`, and
`policy_by_type` are emitted after configuration normalization. Consumers should expect canonical
qualified keys such as `topmark:python` rather than the exact local-or-qualified spelling supplied
by a user.

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

\[`ConfigDiagnosticsPayload`\][topmark.config.machine.schemas.ConfigDiagnosticsPayload] summarizes
the flattened compatibility view derived from staged validation logs.

Diagnostics may include runtime applicability warnings for unknown, malformed, or ambiguous file
type identifiers encountered during configuration sanitation.

These diagnostics may originate from staged config-loading validation logs for:

- TOML-source diagnostics
- merged-config diagnostics
- runtime applicability diagnostics

For the stable 1.x line, the machine-readable contract for configuration-loading diagnostics is this
flattened compatibility view. Stage-local validation structure remains internal and is not
serialized directly.

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

The individual diagnostic entry shape is intentionally fixed at `{level, message}` for the stable
1.x line.

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

> [!NOTE]
>
> In NDJSON, `config_diagnostics` is **counts-only** and each individual config diagnostic is
> emitted as a separate `diagnostic` record with `domain="config"` (one record per diagnostic).

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

## Configuration snapshot commands ([`config dump`](../usage/commands/config/dump.md), [`config defaults`](../usage/commands/config/defaults.md), [`config init`](../usage/commands/config/init.md))

These commands produce a runtime configuration snapshot without running the processing pipeline.

Notes:

- [`config dump`](../usage/commands/config/dump.md) emits the resolved runtime configuration
  snapshot after discovery and merge.
- [`config dump --show-layers`](../usage/commands/config/dump.md) additionally emits a
  machine-readable `config_provenance` payload before the final flattened configuration snapshot.
- [`config defaults`](../usage/commands/config/defaults.md) emits the built-in default runtime
  configuration snapshot.
- [`config init`](../usage/commands/config/init.md) emits the same built-in default runtime
  configuration snapshot in machine-readable formats, even though its human-facing output is the
  bundled example TopMark TOML resource with comments.

Machine-readable output for these commands is unaffected by TEXT verbosity or quiet mode.

### JSON shape for [`config dump`](../usage/commands/config/dump.md), [`config defaults`](../usage/commands/config/defaults.md), [`config init`](../usage/commands/config/init.md)

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ }
}
```

When [`config dump`](../usage/commands/config/dump.md) is invoked with `--show-layers`, the JSON
envelope becomes:

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
          "config": { "strict": false },
          "writer": { "strategy": "atomic" }
        }
      }
    ]
  },
  "config": { /* ConfigPayload */ }
}
```

`config_provenance` is an inspection-oriented payload. Each layer contains:

- `origin` - provenance origin label
- `kind` - resolved config layer kind
- `precedence` - numeric layer precedence
- `scope_root` - optional scope root for discovered layers
- `toml` - the source-local TopMark TOML fragment contributed by that layer

### NDJSON shape for [`config dump`](../usage/commands/config/dump.md), [`config defaults`](../usage/commands/config/defaults.md), [`config init`](../usage/commands/config/init.md)

Default mode emits a single record:

```jsonc
{"kind": "config", "meta": { /* MetaPayload */ }, "config": { /* ConfigPayload */ }}
```

When [`config dump`](../usage/commands/config/dump.md) is invoked with `--show-layers`, NDJSON emits
two records in order:

```jsonc
{"kind": "config_provenance", "meta": { /* MetaPayload */ }, "config_provenance": { /* TomlProvenancePayload */ }}
{"kind": "config", "meta": { /* MetaPayload */ }, "config": { /* ConfigPayload */ }}
```

______________________________________________________________________

## TomlProvenancePayload

\[`TomlProvenancePayload`\][topmark.toml.machine.schemas.TomlProvenancePayload] is a
machine-readable layered provenance export used by `topmark config dump --show-layers`.

JSON shape:

```jsonc
{
  "layers": [
    {
      "origin": "<defaults>",
      "kind": "default",
      "precedence": 0,
      "toml": {
        "config": { "strict": false },
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

The outer `config_layers` container key belongs to the config machine-readable output domain, while
the inner provenance-layer fragment keys (`origin`, `kind`, `precedence`, `toml`, `scope_root`) are
owned by \[`topmark.toml.machine.schemas.TomlKey`\][topmark.toml.machine.schemas.TomlKey].

______________________________________________________________________

## [`topmark config check`](../usage/commands/config/check.md)

This command validates configuration and emits the resolved runtime configuration snapshot,
configuration diagnostics, and a `config_check` status payload.

### JSON shape for [`config check`](../usage/commands/config/check.md)

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* RuntimeConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "config_check": {
    "ok": true,
    "strict": false,
    "diagnostic_counts": { "info": 0, "warning": 1, "error": 0 },
    "config_files": ["..."]
  }
}
```

- `config`: resolved runtime configuration snapshot.
- `config_diagnostics`: full diagnostics payload, including counts and the list of individual config
  diagnostics.
- `config_check`: command-status payload containing:
  - `ok` - whether validation succeeded
  - `strict` - whether strict config-checking mode was enabled
  - `diagnostic_counts` - counts by diagnostic level
  - `config_files` - config files that contributed to the resolved config

The `strict` field reflects the **effective validation strictness** used for the run. It is derived
from TOML source configuration (`[config].strict`) and may be overridden by CLI or API inputs. This
strictness is evaluated across staged config-loading validation, while `config_diagnostics` remains
the flattened compatibility view exposed in machine-readable output.

For the stable 1.x line, this is the explicit contract decision: staged config-loading validation
remains internal, and machine-readable output serializes only the flattened compatibility view.

Machine-readable output for [`config check`](../usage/commands/config/check.md) is unaffected by
TEXT verbosity or quiet mode.

### NDJSON shape for [`config check`](../usage/commands/config/check.md)

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
  compatibility view.

(See `topmark.config.machine.*` for canonical builders/serializers.)

Config-specific JSON payload keys and NDJSON kinds are defined in
\[`topmark.config.machine.schemas.ConfigKey`\][topmark.config.machine.schemas.ConfigKey] and
\[`topmark.config.machine.schemas.ConfigKind`\][topmark.config.machine.schemas.ConfigKind]. Shared
config diagnostic entry/count keys are defined in
\[`topmark.diagnostic.machine.schemas`\][topmark.diagnostic.machine.schemas].

______________________________________________________________________

## [`topmark version`](../usage/commands/version.md)

### JSON shape for [`version`](../usage/commands/version.md)

```jsonc
{
  "meta": { /* MetaPayload */ },
  "version_info": {
    "version": "<package version>",
    "version_format": "pep440"
  }
}
```

### NDJSON shape for [`version`](../usage/commands/version.md)

```jsonc
{"kind":"version","meta":{ /* MetaPayload */ },"version_info":{ "version":"<package version>", "version_format":"pep440" }}
```

The NDJSON `version` record kind is defined in
\[`topmark.version.machine.schemas.VersionKind`\][topmark.version.machine.schemas.VersionKind],
while JSON payload keys such as `version_info` are defined in
\[`topmark.version.machine.schemas.VersionKey`\][topmark.version.machine.schemas.VersionKey].

The version reported in machine-readable output is derived from the installed package metadata /
generated version module, not from a manually maintained static field in `pyproject.toml`.

Machine-readable output for [`version`](../usage/commands/version.md) is unaffected by TEXT
verbosity or quiet mode.

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

Registry machine-readable output uses `--long` to select brief vs detailed projections. Registry
commands do not support `--quiet`, and TEXT verbosity does not affect machine-readable output.

### [`topmark registry filetypes`](../usage/commands/registry/filetypes.md)

JSON envelope:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "filetypes": [ /* FileTypeEntry ... */ ]
}
```

`qualified_key` is the canonical file type identity. `namespace` and `local_key` are provided for
inspection, grouping, and display.

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

Canonical schemas/builders live in \[`topmark.registry.machine.*`\]\[`topmark.registry.machine`\].

The corresponding NDJSON record kind is owned by
\[`topmark.registry.machine.schemas.RegistryKind`\][topmark.registry.machine.schemas.RegistryKind].

### [`topmark registry processors`](../usage/commands/registry/processors.md)

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

Canonical schemas/builders live in \[`topmark.registry.machine.*`\]\[`topmark.registry.machine`\].

The corresponding NDJSON record kind is owned by
\[`topmark.registry.machine.schemas.RegistryKind`\][topmark.registry.machine.schemas.RegistryKind].

### [`topmark registry bindings`](../usage/commands/registry/bindings.md)

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

Binding references use canonical qualified keys. `file_type_key` references a file type
`qualified_key`, and `processor_key` references a processor `qualified_key`.

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
  - long mode: expanded \[`FileTypeRefEntry`\][topmark.registry.machine.schemas.FileTypeRefEntry]
    objects
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

Canonical schemas/builders live in \[`topmark.registry.machine.*`\][topmark.registry.machine].

The corresponding JSON payload keys and NDJSON record kinds are owned by
\[`topmark.registry.machine.schemas.RegistryKind`\][topmark.registry.machine.schemas.RegistryKind].

______________________________________________________________________

## Backwards compatibility and evolution

TopMark's machine-readable output schema is part of its stable integration surface. For the stable
1.x line, documented JSON and NDJSON shapes are treated as machine-readable compatibility contracts.

Consumers should:

- Treat machine-readable output as the authoritative contract for programmatic use; do not parse
  TEXT or Markdown output in automation.
- Rely on `kind` for NDJSON.
- Treat unknown fields as optional/ignorable.
- Prefer parsing and schema-tolerant logic over strict string matching.
- Assume additive fields may appear over time within the 1.x compatibility model.
- Prefer canonical identity fields such as `qualified_key`, `file_type_key`, and `processor_key`
  over display-oriented names.

Breaking machine-readable output changes should be signaled through Conventional Commits using the
`!` marker and documented in the changelog.
