<!--
topmark:header:start

  project      : TopMark
  file         : init.md
  file_relpath : docs/usage/commands/config/init.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# `topmark config init`

**Purpose:** Render the bundled example TopMark TOML template.

The `config init` subcommand (part of [`topmark config`](../config.md)) prints the bundled example
TopMark TOML template. This resource is heavily commented and is intended as a starting point for a
new configuration file.

The example includes both layered configuration sections (such as `[header]`, `[fields]`,
`[formatting]`, and `[files]`) and TOML-source-local sections such as `[config]`. During normal
loading, TopMark validates the whole source first and then deserializes only the layered fragment
into the effective runtime configuration.

{% include-markdown "\_snippets/terminology.md" %}

______________________________________________________________________

## File type identifier semantics

{% include-markdown "\_snippets/file-type-identifiers.md" %}

See [file-type filtering](../../filtering.md#file-type-filtering) for the full identifier contract.

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

## Behavior details

- `[config]` - source-local options such as `root` and strictness behavior
- `[fields]` - default header fields (`project`, `license`, ...)
- `[header]` - order of fields to render in the header
- `[formatting]` - layout options (e.g., `align_fields`)
- `[files]` - file discovery knobs (e.g., `include_file_types`, `exclude_file_types`)

You can safely edit the generated file to match your project's needs.

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

## When to use

- File-agnostic: does not inspect any files. Positional paths are rejected as invalid CLI usage.
  STDIN content mode (`-`) and file-list modes (such as `--files-from -`) do not apply.
- Non-destructive: writes nothing; you control redirection.
- Self-documenting: comments explain layered configuration fields, TOML-source-local options, and
  reasonable defaults.

______________________________________________________________________

## Output behavior

Output formats:

- `text` / `markdown`: full commented template from the bundled resource. Markdown is
  document-oriented and ignores TEXT-oriented verbosity controls.
- `json` / `ndjson`: a machine-readable config snapshot produced by parsing and resolving the
  bundled starter template, without comments or diagnostics.

Notes:

- Specify `--pyproject` if you want to add the configuration to your project's `pyproject.toml`.
  This nests the example TOML under a `[tool.topmark]` table.

- When choosing `json` or `ndjson`, TopMark parses and resolves the bundled starter template before
  emitting the machine-readable snapshot. This preserves template semantics, including TOML-authored
  runtime sections such as `[writer]`, while omitting comments and formatting.

- In TEXT output, `-v` adds BEGIN/END markers around the TOML output.

- Markdown output is document-oriented and ignores TEXT-only verbosity controls.

- Machine-readable JSON/NDJSON output ignores TEXT-oriented verbosity controls.

______________________________________________________________________

## Command-specific options

`topmark config init` supports content-rendering options such as `--output-format`, `--pyproject`,
`--root`, color controls, and TEXT verbosity. See `topmark config init -h` for the complete command
help.

Note: `-v` / `--verbose` applies only to TEXT output. This pure content-producing command does not
support `--quiet`. Markdown and machine-readable formats ignore TEXT-oriented verbosity controls.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tools.

The canonical schema, stable `kind` values, and shared conventions are documented here:

- [Machine-readable output](../../../dev/machine-output.md)
- [Machine-readable format conventions](../../../dev/machine-formats.md)

{% include-markdown "\_snippets/output-contract-no-quiet.md" %}

Notes:

- In machine-readable JSON/NDJSON output, `config init` emits a configuration snapshot produced by
  parsing and resolving the bundled starter template.
- The machine-readable output represents the bundled template view, not a discovered or merged
  project configuration.
- The snapshot includes TOML-authored runtime sections such as `[writer]` when they are present in
  the bundled template, even though those sections are resolved outside the layered configuration
  model at runtime.
- Machine-readable configuration snapshots emit normalized canonical qualified file type identifiers
  after configuration normalization.
- No diagnostics are emitted for this command.

### JSON schema

A single JSON document is emitted:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload (bundled template snapshot) */ }
}
```

### NDJSON schema

NDJSON is a stream where each line is a JSON object. Every record includes `kind` and `meta`.

Stream:

1. `kind="config"` (bundled template snapshot)

Example:

```jsonc
{"kind":"config","meta":{...},"config":{...}}
```

______________________________________________________________________

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

## Related commands

- [`topmark config check`](./check.md) - validate the effective runtime configuration and staged
  configuration-loading diagnostics.
- [`topmark config dump`](./dump.md) - show the effective runtime configuration, including
  normalized canonical file type identifiers.
- [`topmark config defaults`](./defaults.md) - show TopMark's canonical built-in default TOML
  document.

______________________________________________________________________

## Related docs

- [Command overview](../../cli.md)
- [Configuration](../../configuration.md)
- [Filtering](../../filtering.md)
- [Policies](../../policies.md)
- [Configuration discovery, precedence, and policy](../../../configuration/discovery.md)
- [Configuration schema](../../../dev/configuration-schema.md)
- [Machine-readable output](../../../dev/machine-output.md)
- [Machine-readable format conventions](../../../dev/machine-formats.md)
- [Exit codes](../../exit-codes.md)
- [Terminology and Canonical Vocabulary](../../../terminology.md)

______________________________________________________________________

## Troubleshooting

- **Unexpected identifier formatting**: machine-readable output may emit normalized canonical
  qualified identifiers such as `topmark:python`.
- **Need the real effective runtime configuration**: use [`topmark config dump`](./dump.md).
- **Need built-in defaults only**: use [`topmark config defaults`](./defaults.md).
