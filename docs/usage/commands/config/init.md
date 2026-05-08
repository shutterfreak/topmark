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
the **bundled example TopMark TOML resource**. This resource is heavily commented and is intended as
a starting point for a new configuration file.

The example includes both layered-config sections (such as `[header]`, `[fields]`, `[formatting]`,
and `[files]`) and TOML-source-local sections such as `[config]`. During normal loading, TopMark
validates the whole source first and then deserializes only the layered fragment into the effective
frozen configuration.

See also:

- [CLI overview](../../cli.md)
- [Configuration](../../configuration.md)
- [Filtering](../../filtering.md)
- [Policies](../../policies.md)
- [Configuration discovery](../../../configuration/discovery.md)
- [Configuration schema](../../../dev/config-schema.md)

Output formats:

- `text` / `markdown`: full commented template from the bundled resource. Markdown is
  document-oriented and ignores TEXT-only verbosity controls.
- `json` / `ndjson`: minimal defaults-derived frozen config snapshot, without comments or
  diagnostics.

Notes:

- Specify `--pyproject` if you want to add the configuration to your project's `pyproject.toml`.
  This nests the example TOML under a `[tool.topmark]` table.
- When choosing `json` or `ndjson`, the output is equivalent to the built-in defaults-derived frozen
  snapshot emitted by [`topmark config defaults`](./defaults.md).

______________________________________________________________________

## File type identifier semantics

File type identifiers in TopMark configuration may use either:

- local identifiers such as `python`
- canonical qualified identifiers such as `topmark:python`

Internally, configuration freeze normalizes identifiers to canonical qualified keys before resolver,
filtering, policy, and binding evaluation.

Local identifiers are accepted only when unambiguous in the effective composed registry.

{% include-markdown "\_snippets/file-type-identifiers.md" %}

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

## Input applicability

`config init` renders a bundled example configuration and does not accept file-processing inputs:

- positional PATH arguments are rejected as invalid CLI usage
- `-` is not a content-STDIN sentinel for this command
- `--stdin-filename` does not apply
- file-list STDIN modes (for example, `--files-from -`) do not apply

Use shell redirection (for example, `> topmark.toml`) to write the generated configuration to a
file.

______________________________________________________________________

## Key properties

- **File‑agnostic**: does not inspect any files. Positional paths are rejected as invalid CLI usage.
  STDIN content mode (`-`) and file-list modes (such as `--files-from -`) do not apply.
- **Non‑destructive**: writes nothing; you control redirection.
- **Self-documenting**: comments explain layered config fields, TOML-source-local options, and
  reasonable defaults.

______________________________________________________________________

## Verbosity

`config init` renders a bundled example TOML resource to stdout.

- In TEXT output, `-v` adds BEGIN/END markers around the TOML output.
- Markdown output is document-oriented and ignores TEXT-only verbosity controls.
- JSON/NDJSON output is machine-readable and ignores TEXT-only verbosity controls.

______________________________________________________________________

## Options (subset)

`topmark config init` supports content-rendering options such as `--output-format`, `--pyproject`,
`--root`, color controls, and TEXT verbosity. See `topmark config init -h` for the complete command
help.

Note: `-v` / `--verbose` applies only to TEXT output. This pure content-producing command does not
support `--quiet`. Markdown and machine-readable formats ignore TEXT-only verbosity controls.

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
- Invalid positional paths are reported as CLI usage errors, not file-processing diagnostics.
- `--quiet` is unsupported because the command's primary purpose is to emit content.

See [`Exit codes`](../../exit-codes.md) for the complete CLI-wide exit-code contract.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tools.

The canonical schema, stable `kind` values, and shared conventions are documented here:

- [Machine-readable output schema](../../../dev/machine-output.md)
- [Machine-readable formats](../../../dev/machine-formats.md)

{% include-markdown "\_snippets/output-contract-no-quiet.md" %}

Notes:

- In machine-readable formats, `config init` emits a built-in defaults-derived config snapshot.
- The machine-readable output represents the built-in defaults view, not a discovered or merged
  project configuration.
- Machine-readable config snapshots emit normalized canonical qualified file type identifiers after
  configuration freeze.
- No diagnostics are emitted for this command.

### JSON schema

A single JSON document is emitted:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload (defaults-derived frozen snapshot) */ }
}
```

### NDJSON schema

NDJSON is a stream where each line is a JSON object. Every record includes `kind` and `meta`.

Stream:

1. `kind="config"` (defaults-derived frozen config snapshot)

Example:

```jsonc
{"kind":"config","meta":{...},"config":{...}}
```

______________________________________________________________________

## Troubleshooting

- **Unexpected identifier formatting**: machine-readable output may emit normalized canonical
  qualified identifiers such as `topmark:python`.
- **Need the real effective config**: use [`topmark config dump`](./dump.md).
- **Need built-in defaults only**: use [`topmark config defaults`](./defaults.md).

______________________________________________________________________

## Related commands

- [`topmark config check`](./check.md) — validate the effective frozen configuration and staged
  config-loading diagnostics.
- [`topmark config dump`](./dump.md) — show the effective frozen configuration, including normalized
  canonical file type identifiers.
- [`topmark config defaults`](./defaults.md) — show TopMark’s built-in layered defaults as TOML.

An overview of all CLI commands is available in [CLI overview](../../cli.md).
