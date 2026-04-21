<!--
topmark:header:start

  project      : TopMark
  file         : filetypes.md
  file_relpath : docs/usage/commands/registry/filetypes.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `registry filetypes` Command Guide

**Purpose:** Display registered file type identities.

The `registry filetypes` subcommand lists TopMark’s known **file types**, including their matching
rules and header policies. Use it to understand how TopMark classifies files and what behavior is
associated with each type.

______________________________________________________________________

## Quick start

```bash
# List all supported file types (brief mode)
topmark registry filetypes

# List all supported file types in Markdown (detailed mode)
topmark registry filetypes --long --output-format markdown

# Machine‑readable
topmark registry filetypes --output-format json | jq
```

______________________________________________________________________

### See also

For the canonical, version-accurate list (used for the docs), see:

- [Supported file types (generated)](../../generated/filetypes.md)

(This page is generated via `topmark registry filetypes --long --output-format markdown`.)

______________________________________________________________________

## Output formats

Use `--output-format` to pick the output format:

- `text` — human‑readable (brief or detailed)
- `json` — a single JSON document with `meta` and `filetypes` keys
- `ndjson` — one JSON object per line (stream‑friendly, record-oriented)
- `markdown` — a beautified Markdown table (great for docs)

The `--long` flag controls the level of detail for **all** formats.

______________________________________________________________________

### JSON structure

The JSON output has the following structure:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "filetypes": [ /* FileTypeEntry ... */ ]
}
```

- `meta` contains machine metadata (tool, version, platform, and optionally `detail_level`).
- `filetypes` is a list of file type entries.

In `--long` mode, each entry is expanded with additional fields such as matching rules and header
policy information.

Unlike [`registry bindings`](./bindings.md), this command focuses on **file type identities**, not
which processor handles them.

## What it shows

### Brief (default)

- **Local key** — the file type identifier (e.g., `python`, `markdown`, `env`)
- **Description** — a short description

### Detailed (`--long`)

Rendered consistently across `text`, `json`, `ndjson`, and `markdown`:

- **Qualified key**
- **Local key / namespace**
- **Extensions** (comma‑separated)
- **Filenames** (comma‑separated)
- **Patterns** (comma‑separated)
- **skip_processing** (`true`/`false`)
- **has_content_matcher** (`true`/`false`)
- **header_policy** (structured policy fields)
- **Bound** (`true`/`false`)
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
topmark registry filetypes

# Detailed list (human)
topmark registry filetypes --long

# Detailed Markdown table (ideal for project docs)
topmark registry filetypes --long --output-format markdown

# JSON for scripting
topmark registry filetypes --long --output-format json | jq '.filetypes[] | select(.skip_processing==false)'

# NDJSON for streaming
topmark registry filetypes --output-format ndjson | head -n 5
```

______________________________________________________________________

## Notes

- File types define **how files are matched and classified**.
- Processing behavior is determined by bindings (see [`registry bindings`](./bindings.md)).
- A file type may be present but not processed if it is unbound or marked `skip_processing`.

______________________________________________________________________

## How TopMark resolves file types

TopMark may have multiple `FileType` definitions that match a given path. The resolver evaluates all
matching file types and selects the most specific match.

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

These are hidden by default; use `--report=noncompliant` or `--report=all` to show these in reports.
