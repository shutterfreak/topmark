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

**Purpose:** Display all header processors and the registered file types.

The `registry processors` subcommand lists registered **header processors** and the **file types** they
handle, as well as file types that aren't registered to a header processor (such types are recognized but left alone).
Use it to verify how file types are mapped to their processing logic.

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
- `json` — a single JSON document
- `ndjson` — one JSON object per line
- `markdown` — a beautified Markdown table

The `--long` flag controls the level of detail for **all** formats.

______________________________________________________________________

## What it shows

### Brief (default)

- **Processor** — class name
- **Module** — fully‑qualified module path
- **File Types** — names handled by this processor

### Detailed (`--long`)

- Same as brief, plus: for each file type, its **description**

You’ll also see a separate section for **file types without a registered processor**.

______________________________________________________________________

## Numbered output & verbosity

In human-readable formats, TopMark renders a **numbered list** of processors with right-aligned
indices. With `--long` or higher verbosity, additional details (and per-file-type descriptions) are
shown.

______________________________________________________________________

## Examples

```bash
# Brief list
topmark registry processors

# Detailed Markdown table (ideal for project docs)
topmark registry processors --long --output-format markdown

# JSON for scripting
topmark registry processors --long --output-format json | jq '.processors[] | {cls: .class, n: (.filetypes|length)}'

# NDJSON for streaming
topmark registry processors --output-format ndjson | grep processor | head -n 5
```

______________________________________________________________________

## Notes

- The mapping between file types and processors is established at registration time.
- Unbound file types may be intentional (e.g., skip processing) or indicate a missing
  implementation.
