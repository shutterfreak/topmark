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

The example includes both layered-config sections (such as `[header]`, `[fields]`, `[formatting]`,
and `[files]`) and TOML-source-local sections such as `[config]`. During normal loading, TopMark
validates the whole source first and then deserializes only the layered fragment into the final
merged config.

- `text` / `markdown`: full commented template from the bundled resource. Markdown is
  document-oriented and ignores TEXT-only verbosity controls.
- `json` / `ndjson`: minimal defaults-derived config snapshot, without comments or diagnostics.
  Machine formats ignore TEXT-only verbosity controls.

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

# Render document-oriented Markdown output
topmark config init --output-format markdown
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
- **Self‑documenting**: comments explain layered config fields, source-local TOML options, and
  reasonable defaults.

______________________________________________________________________

## Verbosity

`config init` prints plain TOML to stdout.

- In TEXT output, `-v` adds BEGIN/END markers around the TOML output.
- Markdown output is document-oriented and ignores TEXT-only verbosity controls.
- JSON/NDJSON output is machine-readable and ignores TEXT-only verbosity controls.

______________________________________________________________________

## Options (subset)

This command is intentionally minimal and usually has no options. See `topmark config init -h` for
any environment‑specific flags that may be available in your build.

Note: `-v` / `--verbose` applies only to TEXT output. This pure content-producing command does not
support `--quiet`. Markdown and machine formats ignore TEXT-only verbosity controls.

## Exit codes

`topmark config init` is a pure informational/content-producing command and exits with `SUCCESS (0)`
on successful execution.

Common `config init` exit codes:

| Scenario                      | Exit code          |
| ----------------------------- | ------------------ |
| Example rendered successfully | `SUCCESS (0)`      |
| Invalid CLI usage             | `USAGE_ERROR (64)` |

Notes:

- This command does not inspect project files and does not use file-processing exit codes such as
  `WOULD_CHANGE (2)`, `FILE_NOT_FOUND (66)`, or `IO_ERROR (74)`.
- `--quiet` is unsupported because the command's primary purpose is to emit content.

See [`Exit codes`](../../exit-codes.md) for the complete CLI-wide exit-code contract.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tools.

The canonical schema, stable `kind` values, and shared conventions are documented here:

- [Machine output schema (JSON & NDJSON)](../../../dev/machine-output.md)
- [Machine formats](../../../dev/machine-formats.md)

{% include-markdown "\_snippets/output-contract-no-quiet.md" %}

Notes:

- In machine formats, `config init` emits a built-in defaults-derived config snapshot.
- The machine output represents the built-in defaults view, not a discovered or merged project
  configuration.
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
- [`topmark config defaults`](./defaults.md) — show TopMark’s built-in layered defaults as TOML.
