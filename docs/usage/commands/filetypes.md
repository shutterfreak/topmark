<!--
topmark:header:start

  project      : TopMark
  file         : filetypes.md
  file_relpath : docs/usage/commands/filetypes.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `filetypes` Command Guide

The `filetypes` subcommand lists TopMark’s supported **file type identifiers** and their **header
policies**. Use it to discover which identifiers you can pass to `--file-type` and to understand how
headers will be rendered per type.

______________________________________________________________________

## Quick start

```bash
# List all supported file types (brief mode)
topmark filetypes

# List all supported file types in Markdown (detailed mode)
topmark filetypes --long --output-format markdown

# Machine‑readable
topmark filetypes --output-format json | jq
```

______________________________________________________________________

## Output formats

Use `--output-format` to pick the output format:

- `default` — human‑readable (brief or detailed)
- `json` — a single JSON document (array of file types)
- `ndjson` — one JSON object per line (stream‑friendly)
- `markdown` — a beautified Markdown table (great for docs)

The `--long` flag controls the level of detail for **all** formats.

______________________________________________________________________

## What it shows

### Brief (default)

- **Identifier** — the file type identifier (e.g., `python`, `markdown`, `env`)
- **Description** — a short description

### Detailed (`--long`)

Rendered consistently across `default`, `json`, `ndjson`, and `markdown`:

- **Identifier**
- **Extensions** (comma‑separated)
- **Filenames** (comma‑separated)
- **Patterns** (comma‑separated)
- **skip_processing** (`true`/`false`)
- **has_content_matcher** (`true`/`false`)
- **header_policy** (policy name)
- **Description**

______________________________________________________________________

## Numbered output & verbosity

In human-readable formats, TopMark renders a **numbered list** of file types with right-aligned
indices (e.g., `1.`, `2.`, …) to keep long lists scannable. With `--long` or higher verbosity,
additional details are shown alongside each identifier.

______________________________________________________________________

## Examples

```bash
# Brief list
topmark filetypes

# Detailed list (human)
topmark filetypes --long

# Detailed Markdown table (ideal for project docs)
topmark filetypes --long --output-format markdown

# JSON for scripting
topmark filetypes --long --output-format json | jq '.[] | select(.skip_processing==false)'

# NDJSON for streaming
topmark filetypes --output-format ndjson | head -n 5
```

______________________________________________________________________

## Notes

- The identifiers shown here can be passed to `--file-type` on commands like `check` and `strip`.
- Header placement and comment styles are file‑type specific. See the dedicated guides for details.
