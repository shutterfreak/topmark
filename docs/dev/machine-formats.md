<!--
topmark:header:start

  project      : TopMark
  file         : machine-formats.md
  file_relpath : docs/dev/machine-formats.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Machine formats

This page documents TopMark’s **machine-readable output conventions** across commands.

______________________________________________________________________

## Output formats

TopMark exposes four `--output-format` values:

- human-oriented formats (not machine-stable):
  - `text`: default human-oriented text.
  - `markdown`: human-oriented Markdown.
- machine formats:
  - `json`: a single JSON document per invocation.
  - `ndjson`: a newline-delimited JSON stream.

Notes:

- Machine formats (`json`, `ndjson`) are independent of human-facing presentation controls.
- TEXT-only flags such as `-v` / `--verbose` and `-q` / `--quiet` do not affect machine output.
- Markdown output is also independent from machine formats and follows its own document-oriented
  contract.

This page describes the **conventions** shared across machine formats. For the canonical field-level
schema reference, see:

- [Machine output schema (JSON & NDJSON)](machine-output.md)

______________________________________________________________________

## Machine-stable guarantees

The `json` and `ndjson` formats are designed for CI and programmatic use.

Stability guarantees:

- Machine payloads contain no ANSI color codes.
- Payload shapes are JSON-safe (no Python-specific objects).
- New fields may be added over time (additive evolution).
- Existing fields are not removed or renamed without a breaking-change signal.

Consumers should:

- Treat machine output as the authoritative contract; do not rely on TEXT or Markdown output for
  programmatic use.

- Switch on `kind` (NDJSON) rather than relying on ordering.

- Tolerate unknown fields.

- Avoid string matching against formatted output.

______________________________________________________________________

## Meta block

All machine output includes a `meta` object:

- `tool`: the tool name (always `"topmark"`)
- `version`: the TopMark package version (PEP 440)
- `platform`: short runtime identifier (e.g. `sys.platform`)
- `detail_level`: optional machine-facing projection level for some commands:
  - `"brief"` for default machine output
  - `"long"` when `--long` / detailed projection is requested Registry commands include
    `detail_level` in both JSON and NDJSON. Other command families may omit this field.

In JSON, `meta` appears once at the top level.

In NDJSON, `meta` appears in **every record**.

Shared envelope keys and helpers for machine output live under
\[`topmark.core.machine`\][topmark.core.machine]. Domain packages (for example
\[`topmark.config.machine`\][topmark.config.machine] and
\[`topmark.pipeline.machine`\][topmark.pipeline.machine]) define their own payload keys and NDJSON
record kinds in their respective `*.machine.schemas` modules.

Unlike human-facing verbosity, `detail_level` is part of the machine contract. Consumers should
prefer this field over inferring the projection from payload shape alone.

Note:

- `detail_level` is distinct from TEXT verbosity (`-v`) and quiet mode (`--quiet`).
- It reflects an explicit machine-facing projection (`--long`), not presentation detail.

## NDJSON envelope contract

Each NDJSON line is a JSON object with a stable envelope:

```jsonc
{"kind": "<kind>", "meta": { ... }, "<kind>": { ... } }
```

- `kind` determines the payload container key (by default, container key == kind).
- `meta` appears in every record.
- the payload object is stored under a container key that matches `kind`.

Note:

- Some NDJSON record kinds carry scalar payloads in brief mode (for example registry reference kinds
  such as `unbound_filetype` and `unused_processor`, which emit qualified-key strings). In `--long`
  mode, these payloads expand to structured objects.

## JSON envelope conventions

Unlike NDJSON, JSON output is **domain-specific and aggregated**. Each command defines its own
stable top-level keys for collections.

Examples:

- Registry filetypes:

```jsonc
{ "meta": { ... }, "filetypes": [ ... ] }
```

- Registry processors:

```jsonc
{ "meta": { ... }, "processors": [ ... ] }
```

- Registry bindings:

```jsonc
{
  "meta": { ... },
  "bindings": [ ... ],
  "unbound_filetypes": [ ... ],
  "unused_processors": [ ... ]
}
```

- Processing commands (summary mode):

```jsonc
{
  "meta": { ... },
  "config": { ... },
  "config_diagnostics": { ... },
  "summary": [
    { "outcome": "unchanged", "reason": "up-to-date", "count": 30 },
    { "outcome": "skipped", "reason": "known file type, headers not supported", "count": 1 }
  ]
}
```

- `config check`:

```jsonc
{
  "meta": { ... },
  "config": { ... },
  "config_diagnostics": {
    "diagnostic_counts": { "info": 0, "warning": 1, "error": 0 },
    "diagnostics": [
      { "level": "warning", "message": "Duplicate included file types found in config" }
    ]
  },
  "config_check": {
    "ok": true,
    "strict_config_checking": false,
    "diagnostic_counts": { "info": 0, "warning": 1, "error": 0 },
    "config_files": ["/repo/topmark.toml"]
  }
}
```

- `config dump --show-layers`:

```jsonc
{
  "meta": { ... },
  "config_provenance": {
    "layers": [
      {
        "origin": "<defaults>",
        "kind": "default",
        "precedence": 0,
        "toml": {
          "config": { "strict_config_checking": false }
        }
      }
    ]
  },
  "config": { ... }
}
```

- `version`:

```jsonc
{
  "meta": { ... },
  "version_info": {
    "version": "1.0.0a2",
    "version_format": "pep440"
  }
}
```

- Resolution diagnostics (`probe`):

```jsonc
{
  "meta": { ... },
  "config": { ... },
  "config_diagnostics": { ... },
  "probes": [ ... ]
}
```

Consumers should **not assume a single generic container key** (such as `items` or a bare array),
but instead switch on documented domain-specific keys.

______________________________________________________________________

## Shared `kind` values

NDJSON record kinds are owned by the schema module of the corresponding machine-output domain (for
example \[`topmark.config.machine.schemas.ConfigKind`\][topmark.config.machine.schemas.ConfigKind]
or
\[`topmark.registry.machine.schemas.RegistryKind`\][topmark.registry.machine.schemas.RegistryKind]).
The list below reflects commonly emitted kinds across commands.

Common NDJSON kinds include:

- `config`
- `config_provenance`
- `config_diagnostics` (counts-only in NDJSON prefix records)
- `diagnostic` (one diagnostic per record; see "Diagnostics" below)
- `result` (per-file result)
- `probe` (per-file resolution probe)
- `summary` (one aggregated `(outcome, reason)` summary entry)
- `version`
- registry-specific kinds:
  - `filetype`
  - `processor`
  - `binding`
  - `unbound_filetype`
  - `unused_processor`

Individual commands may emit subsets of these kinds.

______________________________________________________________________

## Diagnostics

TopMark uses internal \[`Diagnostic`\][topmark.diagnostic.model.Diagnostic] objects to represent
warnings and errors. For machine output:

Diagnostics emitted in machine output represent the flattened compatibility view derived from staged
config-validation logs. Internally, these diagnostics may originate from TOML-source, merged-config,
or runtime-applicability validation.

For 1.0, this flattened compatibility form is the accepted final machine contract for config/TOML
validation diagnostics. Machine output does **not** serialize stage-local validation structure; the
stable emitted diagnostic entry shape remains `{level, message}`.

- **JSON** uses stable `{level, message}` entries within domain payloads (for example
  `config_diagnostics.diagnostics`).
- **NDJSON** emits one `diagnostic` record per diagnostic, with a `domain` field identifying the
  originating domain (for example `"config"`, using values from
  \[`topmark.core.machine.schemas.MachineDomain`\][topmark.core.machine.schemas.MachineDomain]).

The JSON-friendly schema helpers and keys for diagnostics are defined under
\[`topmark.diagnostic.machine.schemas`\][topmark.diagnostic.machine.schemas], including
\[`DiagnosticKey`\][topmark.diagnostic.machine.schemas.DiagnosticKey] and
\[`DiagnosticKind`\][topmark.diagnostic.machine.schemas.DiagnosticKind].

______________________________________________________________________

## Processing commands

`topmark check` and `topmark strip` share conventions:

- JSON emits: `meta`, `config`, `config_diagnostics`, plus either:
  - `results` (detail mode), or
  - `summary` (summary mode)
- NDJSON emits a stable prefix:
  - `config`
  - `config_diagnostics` (counts-only)
  - zero or more `diagnostic` records (config diagnostics, domain=`"config"` via
    \[`MachineDomain`\][topmark.core.machine.schemas.MachineDomain])
  - then either per-file `result` records (detail mode) or per-outcome **reason-preserving**
    `summary` records (summary mode)

These diagnostics correspond to the flattened compatibility view derived from staged
config-validation logs.

Machine output for processing commands is unaffected by TEXT verbosity or quiet mode; these flags
only influence human TEXT output.

In **summary mode**, TopMark aggregates results by the pair `(outcome, reason)` rather than
collapsing all reasons under a single outcome bucket.

Each summary entry therefore contains:

- `outcome` — the pipeline outcome (for example `inserted`, `replaced`, `unchanged`)
- `reason` — the short lowercase reason string used for bucketing
- `count` — the number of files that produced this `(outcome, reason)` pair

This guarantees that machine consumers can distinguish between different causes that lead to the
same high-level outcome.

Example NDJSON summary records:

```jsonc
{"kind":"summary","meta":{...},"summary":{"outcome":"unchanged","reason":"up-to-date","count":30}}
{"kind":"summary","meta":{...},"summary":{"outcome":"skipped","reason":"known file type, headers not supported","count":1}}
```

### Summary payload shape

In the pipeline machine schema, this row shape is represented by `OutcomeSummaryRow`.

In both JSON and NDJSON machine formats, summary entries follow the same logical structure.

Conceptually the summary is a flat list of rows:

```json
{
  "outcome": "unchanged",
  "reason": "empty-like file (policy)",
  "count": 12
}
```

Important properties of the summary model:

- The summary is **not nested by outcome**.
- Each row represents one `(outcome, reason)` bucket.
- Ordering is deterministic:
  - outcomes follow the internal `Outcome` ordering
  - reasons are sorted alphabetically within each outcome.

This design keeps JSON and NDJSON schemas consistent and avoids ambiguous aggregation when different
reasons share the same outcome.

______________________________________________________________________

## Resolution diagnostics (`probe`)

`topmark probe` exposes file-type and processor resolution as a machine-readable diagnostic surface.

- JSON emits: `meta`, `config`, `config_diagnostics`, `probes`
- NDJSON emits a stable prefix:
  - `config`
  - `config_diagnostics` (counts-only)
  - zero or more `diagnostic` records (domain=`"config"`)
  - then one `probe` record per file

Unlike processing commands, `probe`:

- does not emit `results` or `summary`
- does not compute header changes or plans
- is purely diagnostic and resolution-focused

Machine output for `probe` is unaffected by TEXT verbosity or quiet mode.

Refer to the machine schema reference for the per-file probe payload:

- [Machine output schema (JSON & NDJSON)](machine-output.md)

______________________________________________________________________

## Config commands

Config commands are file-agnostic and emit config-centric payloads:

- `config dump`: resolved config snapshot (no diagnostics); when `--show-layers` is used in machine
  formats, it also emits layered `config_provenance` before the final flattened config snapshot
- `config defaults`: built-in default TopMark TOML snapshot (no diagnostics)
- `config init`: built-in default configuration snapshot in machine formats (no diagnostics)
- `config check`: resolved config snapshot plus diagnostics and a config-check status payload

In human-facing formats, `config defaults` and `config init` differ noticeably: `config defaults`
renders a cleaned TOML view of the built-in defaults, while `config init` renders the bundled
example TopMark TOML resource with extensive comments. In machine formats, both emit the same
underlying default configuration snapshot shape.

For `config check`, the machine payload uses `strict_config_checking` to report the effective
config-validation strictness after applying CLI override precedence over resolved TOML strictness.
This strictness is evaluated across staged config-loading/preflight validation (TOML-source,
merged-config, and runtime-applicability diagnostics), while machine output continues to expose the
flattened compatibility diagnostics view.

Example `config check` NDJSON prefix:

```jsonc
{"kind":"config","meta":{...},"config":{...}}
{"kind":"config_diagnostics","meta":{...},"config_diagnostics":{
  "diagnostic_counts":{"info":0,"warning":1,"error":0}
}}
{"kind":"diagnostic","meta":{...},"diagnostic":{
  "domain":"config",
  "level":"warning",
  "message":"Duplicate included file types found in config"
}}
{"kind":"config_check","meta":{...},"config_check":{
  "ok":true,
  "strict_config_checking":false,
  "diagnostic_counts":{"info":0,"warning":1,"error":0},
  "config_files":["/repo/topmark.toml"]
}}
```

For 1.0, this boundary is intentional: staged validation remains an internal representation, while
machine output exposes only the flattened compatibility diagnostics contract.

For `config dump --show-layers`, machine output preserves the same logical ordering as the
human-facing layered export:

- JSON includes `config_provenance` before `config` in the top-level envelope.
- NDJSON emits a `config_provenance` record first and a `config` record second.

The `config_provenance` payload is inspection-oriented. Each provenance layer preserves metadata
such as `origin`, `kind`, `precedence`, and optional `scope_root`, and exposes the corresponding
source-local TopMark TOML fragment under `toml`.

Config-specific payload keys and NDJSON kinds are defined in
\[`topmark.config.machine.schemas.ConfigKey`\][topmark.config.machine.schemas.ConfigKey] and
\[`topmark.config.machine.schemas.ConfigKind`\][topmark.config.machine.schemas.ConfigKind]. Shared
diagnostic keys used within config payloads are defined in
\[`topmark.diagnostic.machine.schemas`\][topmark.diagnostic.machine.schemas].

Refer to each command’s documentation for its emitted keys and shapes. Registry commands are
documented in the schema reference and now include the separate `registry bindings` machine format.
