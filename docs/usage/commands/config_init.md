<!--
topmark:header:start

  project      : TopMark
  file         : config_init.md
  file_relpath : docs/usage/commands/config_init.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `config init` Command Guide

**Purpose:** Render a fully documented example config.

The `config init` subcommand (part of the TopMark [`config` Command Family](config.md))
prints the **annotated default template** that ships with TopMark.
This file is heavily commented and is intended as a scaffold for a new config file.

- `default` / `markdown`: full commented template from the bundled resource.
- `json` / `ndjson`: minimal Config snapshot derived from the same defaults,
  without comments or diagnostics.

Notes:

- Specify `--pyproject` if you want to add the configuration to your project's `pyproject.toml`.
  This will encapsulate the TopMark TOML config in a `[tool.topmark]` table.
- When choosing `json` or `ndjson`, the output is identical to
  [`topmark config defaults`](config_defaults.md)

______________________________________________________________________

## Quick start

```bash
# Print a starter configuration to stdout
topmark config init

# Create a new project config file
topmark config init > topmark.toml

# Or integrate into pyproject
topmark config init --pyproject >> pyproject.toml
```

______________________________________________________________________

## What it includes

The starter config provides a well‑commented TOML scaffold with the most common sections:

- `[fields]` – default header fields (`project`, `license`, …)
- `[header]` – order of fields to render in the header
- `[formatting]` – layout options (e.g., `align_fields`)
- `[files]` – file discovery knobs (`include_file_types`, `exclude_file_types`, `relative_to`, include/exclude lists)

You can safely edit the generated file to match your project’s needs.

______________________________________________________________________

## Key properties

- **File‑agnostic**: does not inspect any files.
- **Non‑destructive**: writes nothing; you control redirection.
- **Self‑documenting**: comments explain each field and reasonable defaults.

______________________________________________________________________

## Verbosity

`config init` prints plain TOML to stdout. When run with higher verbosity (e.g., `-v`), the output
is wrapped between BEGIN/END markers for easy parsing in scripts and tests.

______________________________________________________________________

## Options (subset)

This command is intentionally minimal and usually has no options. See `topmark config init -h` for
any environment‑specific flags that may be available in your build.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tools.

The canonical schema, stable `kind` values, and shared conventions are documented here:

- [Machine output schema (JSON & NDJSON)](../../dev/machine-output.md)
- [Machine formats](../../dev/machine-formats.md)

Notes:

- In machine formats, `config init` emits the same defaults-derived configuration snapshot as
  [`topmark config defaults`](config_defaults.md).
- No diagnostics are emitted for this command.

### JSON schema

A single JSON document is emitted:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload (defaults-derived) */ }
}
```

### NDJSON schema

NDJSON is a stream where each line is a JSON object. Every record includes `kind` and `meta`.

Stream:

1. `kind="config"` (defaults-derived config snapshot)

Example:

```jsonc
{"kind":"config","meta":{...},"config":{...}}
```

______________________________________________________________________

## Notes

- Use `topmark show-defaults` to view the **built‑in defaults** without a scaffold.
- Use `topmark dump-config` to view the **effective merged configuration** (defaults → discovered →
  CLI).
