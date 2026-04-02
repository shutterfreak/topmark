<!--
topmark:header:start

  project      : TopMark
  file         : init.md
  file_relpath : docs/usage/commands/config/init.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `config init` Command Guide

**Purpose:** Render the bundled example TopMark TOML resource.

The `config init` subcommand (part of the TopMark [`config` Command Family](../config.md)) prints
the **bundled example TopMark TOML resource**. This file is heavily commented and is intended as a
starting point for a new configuration file.

- `text` / `markdown`: full commented template from the bundled resource.
- `json` / `ndjson`: minimal Config snapshot derived from the same defaults, without comments or
  diagnostics.

Notes:

- Specify `--pyproject` if you want to add the configuration to your project's `pyproject.toml`.
  This nests the example TOML under a `[tool.topmark]` table.
- When choosing `json` or `ndjson`, the output is identical to
  [`topmark config defaults`](./defaults.md)

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

- `[config]` – source-local options such as `root` and strictness behavior
- `[fields]` – default header fields (`project`, `license`, …)
- `[header]` – order of fields to render in the header
- `[formatting]` – layout options (e.g., `align_fields`)
- `[files]` – file discovery knobs (e.g., `include_file_types`, `exclude_file_types`)

You can safely edit the generated file to match your project’s needs.

______________________________________________________________________

## Key properties

- **File‑agnostic**: does not inspect any files.
- **Non‑destructive**: writes nothing; you control redirection.
- **Self‑documenting**: comments explain each field and reasonable defaults.

______________________________________________________________________

## Verbosity

`config init` prints plain TOML to stdout. When run with higher verbosity (e.g., `-v`), the output
is wrapped between BEGIN/END markers for easier parsing in scripts and tests.

______________________________________________________________________

## Options (subset)

This command is intentionally minimal and usually has no options. See `topmark config init -h` for
any environment‑specific flags that may be available in your build.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tools.

The canonical schema, stable `kind` values, and shared conventions are documented here:

- [Machine output schema (JSON & NDJSON)](../../../dev/machine-output.md)
- [Machine formats](../../../dev/machine-formats.md)

Notes:

- In machine formats, `config init` emits a built-in default configuration snapshot.
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

## Related commands

- [`topmark config check`](./check.md) — check the *effective merged* configuration for errors.
- [`topmark config dump`](./dump.md) — show the *effective merged* configuration as TOML.
- [`topmark config defaults`](./defaults.md) — show TopMark’s *built-in defaults* as TOML.
