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

**Purpose:** Display all recognized/supported file types.

The `filetypes` subcommand lists TopMark’s supported **file type identifiers** and their **header
policies**. Use it to discover which identifiers you can pass to `--include-file-types` / `--exclude-file-types` and to understand how TopMark classifies files.

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

### See also

For the canonical, version-accurate list (used for the docs), see:

- [Supported file types (generated)](../generated-filetypes.md)

(This page is generated via `topmark filetypes --long --output-format markdown`.)

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

______________________________________________________________________

## How TopMark resolves file types

TopMark may have multiple `FileType` definitions that match a given path. The resolver evaluates
all matching file types and selects the most specific match.

In practice, specificity follows this order:

1. **Explicit filenames / tail subpaths** (e.g., `Makefile`, `.vscode/settings.json`)
1. **Regex patterns** (e.g., `Dockerfile(\..+)?`, `requirements.*\.(in|txt)$`)
1. **Extensions** (e.g., `.py`, `.md`, `.json`)

If multiple candidates remain tied, TopMark prefers the more “headerable” choice (i.e., file types
that are not marked `skip_processing = true`).

### Tail subpath matching

`FileType.filenames` entries that contain a path separator (e.g., `.vscode/settings.json`) are
matched as **path suffixes** against `path.as_posix()`. Plain names still match the basename only.

### JSON vs JSONC

- `json` is recognized but typically has `skip_processing = true` because strict JSON has no
  comments, and TopMark will not insert headers into it.
- `jsonc` is an opt‑in type that uses `//` headers. It relies on a content matcher and an insert
  checker to avoid misclassifying strict JSON.

### Unsupported but recognized types

Some file types are recognized but intentionally unmodified (reported as “unsupported”):

- `license_text` (keep verbatim)
- `python-typed-marker` (`py.typed` is a single-token marker)

Use `--skip-unsupported` to hide these from reports.
