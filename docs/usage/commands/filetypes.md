<!--
topmark:header:start

  file         : filetypes.md
  file_relpath : docs/usage/commands/filetypes.md
  project      : TopMark
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `filetypes` Command Guide

The `filetypes` subcommand lists TopMark’s supported **file type identifiers** and their primary
**comment styles**. Use it to discover which identifiers you can pass to `--file-type` and to
understand how headers will be rendered per type.

______________________________________________________________________

## Quick start

```bash
# List all supported file types (brief mode)
topmark filetypes

# List all supported file types in MarkDown (detailed mode)
topmark filetypes --long --format markdown
```

______________________________________________________________________

## What it shows

A table per file type, including:

- **Identifier** — the file type identifier to use with `--file-type` (e.g., `python`, `markdown`,
  `env`).
- **Description** — the description of the file type.

When specifying `--long`, additional information will be rendered.
