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
  - `"long"` when `--long` / detailed projection is requested

In JSON, `meta` appears once at the top level.

In NDJSON, `meta` appears in **every record**.

Canonical keys, kinds, and helper builders for machine output live under
\[`topmark.core.machine`\][topmark.core.machine]. Domain packages (for example
\[`topmark.config.machine`\][topmark.config.machine] and
\[`topmark.pipeline.machine`\][topmark.pipeline.machine]) build on these shared primitives.

Unlike human-facing verbosity, `detail_level` is part of the machine contract. Consumers should
prefer this field over inferring the projection from payload shape alone.

## NDJSON envelope contract

Each NDJSON line is a JSON object with a stable envelope:

```jsonc
{"kind": "<kind>", "meta": { ... }, "<kind>": { ... } }
```

- `kind` determines the payload container key (by default, container key == kind).
- `meta` appears in every record.
- the payload object is stored under a container key that matches `kind`.

______________________________________________________________________

## Shared `kind` values

Common NDJSON kinds include:

- `config`
- `config_diagnostics` (counts-only in NDJSON prefix records)
- `diagnostic` (one diagnostic per record; see "Diagnostics" below)
- `result` (per-file result)
- `summary` (aggregated `(outcome, reason)` summary entry)
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

- **JSON** uses stable `{level, message}` entries within domain payloads (for example
  `config_diagnostics.diagnostics`).
- **NDJSON** emits one `diagnostic` record per diagnostic, with a `domain` field identifying the
  originating domain (for example `"config"`).

The JSON-friendly schema helpers for diagnostics are named with a `Machine*` prefix (for example
`MachineDiagnosticEntry` and `MachineDiagnosticCounts`) and live under
\[`topmark.diagnostic.machine.schemas`\][topmark.diagnostic.machine.schemas].

______________________________________________________________________

## Processing commands

`topmark check` and `topmark strip` share conventions:

- JSON emits: `meta`, `config`, `config_diagnostics`, plus either:
  - `results` (detail mode), or
  - `summary` (summary mode)
- NDJSON emits a stable prefix:
  - `config`
  - `config_diagnostics` (counts-only)
  - zero or more `diagnostic` records (config diagnostics)
  - then either per-file `result` records (detail mode) or per-outcome **reason-preserving**
    `summary` records (summary mode)

In **summary mode**, TopMark aggregates results by the pair `(outcome, reason)` rather than
collapsing all reasons under a single outcome bucket.

Each summary entry therefore contains:

- `outcome` — the pipeline outcome (for example `inserted`, `replaced`, `unchanged`)
- `reason` — the short lowercase reason string used for bucketing
- `count` — the number of files that produced this `(outcome, reason)` pair

This guarantees that machine consumers can distinguish between different causes that lead to the
same high-level outcome.

### Summary payload shape

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

## Config commands

Config commands are file-agnostic and emit config-centric payloads:

- `config dump`: resolved config snapshot (no diagnostics)
- `config defaults`: built-in default TopMark TOML snapshot (no diagnostics)
- `config init`: built-in default configuration snapshot in machine formats (no diagnostics)
- `config check`: resolved config snapshot plus diagnostics and a config-check status payload

In human-facing formats, `config defaults` and `config init` differ noticeably: `config defaults`
renders a cleaned TOML view of the built-in defaults, while `config init` renders the bundled
example TopMark TOML resource with extensive comments. In machine formats, both emit the same
underlying default configuration snapshot shape.

Refer to each command’s documentation for its emitted keys and shapes. Registry commands are
documented in the schema reference and now include the separate `registry bindings` machine format.
