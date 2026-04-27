<!--
topmark:header:start

  project      : TopMark
  file         : processors.md
  file_relpath : docs/usage/commands/registry/processors.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `registry processors` Command Guide

**Purpose:** Display registered header processor identities.

The `registry processors` subcommand lists registered **header processors** and their
comment/delimiter capabilities. Use it to understand what processing logic is available in the
system.

To see which processor is used for a given file type, use [`registry bindings`](./bindings.md).

______________________________________________________________________

## Quick start

```bash
# Brief list
topmark registry processors

# Detailed Markdown table
topmark registry processors --long --output-format markdown

# Machine‑readable
topmark registry processors --output-format json | jq
```

______________________________________________________________________

### See also

For the canonical, version-accurate list (used for the docs), see:

- [Supported header processors (generated)](../../generated/processors.md)

(This page is generated via `topmark registry processors --long --output-format markdown`.)

______________________________________________________________________

## Output formats

Use `--output-format` to pick the output format:

- `text` — human‑readable (brief or detailed)
- `json` — a single JSON document with `meta` and `processors` keys
- `ndjson` — one JSON object per line (stream-friendly, record-oriented)
- `markdown` — a beautified Markdown table

The `--long` flag controls the level of detail for **all** formats.

This flag controls the data/detail depth across all formats. TEXT-only verbosity (`-v`) affects
presentation (e.g., headings) and does not change the data fields emitted.

{% include-markdown "\_snippets/output-contract-no-quiet.md" %}

______________________________________________________________________

### JSON structure

The JSON output has the following structure:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "processors": [ /* ProcessorEntry ... */ ]
}
```

- `meta` contains machine metadata (tool, version, platform, and optionally `detail_level`).
- `processors` is a list of processor entries.

In `--long` mode, each entry is expanded with additional fields such as delimiter and comment
capabilities.

______________________________________________________________________

Unlike [`registry bindings`](./bindings.md), this command focuses on **processor identities**, not
their relationships.

## What it shows

### Brief (default)

- **Qualified key** — unique processor identifier
- **Description** — short description of the processor

### Detailed (`--long`)

Rendered consistently across `text`, `json`, `ndjson`, and `markdown`:

- **Qualified key**
- **Local key / namespace**
- **Description**
- **Delimiter / comment capabilities** (if applicable)
- **Bound** (`true`/`false`) — whether the processor is referenced by any binding

______________________________________________________________________

## Numbered output & verbosity

In human-readable formats, TopMark renders a **numbered list** of processors with right-aligned
indices (e.g., `1.`, `2.`, …) to keep long lists scannable. With `--long`, additional details (and
per-file-type descriptions) are shown. TEXT verbosity (`-v`) affects presentation only (for TEXT
output).

______________________________________________________________________

## Examples

```bash
# Brief list
topmark registry processors

# Detailed Markdown table (ideal for project docs)
topmark registry processors --long --output-format markdown

# JSON for scripting
topmark registry processors --long --output-format json | jq '.processors[] | {cls: .class}'

# NDJSON for streaming
topmark registry processors --output-format ndjson | grep processor | head -n 5
```

______________________________________________________________________

## Notes

- Processors define how headers are parsed, rendered and stripped.
- Whether a processor is actually used is determined by bindings (see
  [`registry bindings`](./bindings.md)).
- Prefer [`registry bindings`](./bindings.md) when investigating which processor handles a file
  type.
- `--quiet` is not supported for registry commands; use output-format options instead if you need
  non-TEXT output.
