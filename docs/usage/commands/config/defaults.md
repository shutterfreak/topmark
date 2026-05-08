<!--
topmark:header:start

  project      : TopMark
  file         : defaults.md
  file_relpath : docs/usage/commands/config/defaults.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `config defaults` Command Guide

**Purpose:** Show the built-in default TopMark TOML document.

The `config defaults` subcommand (part of the TopMark [`config` Command Family](../config.md))
prints TopMark’s canonical built-in default TOML representation. It uses a cleaned, comment-free
TOML document generated from the built-in defaults table (no project files are discovered or
merged).

Because the output is generated from TopMark's built-in defaults, it reflects only the built-in
default TOML surface. Source-local TOML sections such as `[config]` and runtime-facing sections such
as `[writer]` are included when they are part of the canonical defaults, but no project, user, or
explicitly supplied config files are discovered or merged.

See also:

- [CLI overview](../../cli.md)
- [Configuration](../../configuration.md)
- [Filtering](../../filtering.md)
- [Policies](../../policies.md)
- [Configuration discovery](../../../configuration/discovery.md)
- [Configuration schema](../../../dev/config-schema.md)

Output formats:

- `text` / `markdown`: minimal, comment-free TOML. Markdown is document-oriented and ignores
  TEXT-only verbosity controls.
- `json` / `ndjson`: a machine-readable config snapshot derived from the canonical built-in defaults
  table, including TOML-authored runtime sections such as `[writer]` when present. No diagnostics
  are emitted. Machine-readable formats ignore TEXT-only verbosity controls.

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
# Show the internal default configuration (TOML)
topmark config defaults

# Render document-oriented Markdown output
topmark config defaults --output-format markdown
```

______________________________________________________________________

## Key properties

- **Isolated**: ignores project/user config files and CLI overrides.
- **File‑agnostic**: does not resolve or process any PATHS. Positional paths are rejected as invalid
  CLI usage. STDIN content mode (`-`) and file-list modes (such as `--files-from -`) do not apply.
- **Reference**: useful for understanding the canonical built-in defaults, header layout, policy
  behavior, and TOML/config/runtime split.

> **How config is resolved**
>
> TopMark merges config from **defaults → user → project chain → `--config` → CLI**. Globs are
> evaluated relative to the **workspace base** (`relative_to`). Paths to other files (like
> `exclude_from`) are resolved relative to the **config file** that declared them.
>
> See: [`Configuration → Discovery & Precedence`](../../../configuration/discovery.md).

______________________________________________________________________

## When to use

- To compare your project’s configuration with the baseline shipped by TopMark.
- To seed your own config manually (you can copy & modify the parts you need).
- To debug why a field or policy is present when you did not set it explicitly.

______________________________________________________________________

## Input applicability

`config defaults` is a pure informational command that emits built-in defaults only. It does not
accept file-processing inputs:

- positional PATH arguments are rejected as invalid CLI usage
- `-` is not a content-STDIN sentinel for this command
- `--stdin-filename` does not apply
- file-list STDIN modes (for example, `--files-from -`) do not apply

This ensures the output always reflects only the built-in defaults, independent of any workspace
state.

No config discovery, project traversal, resolver filtering, or runtime policy overlay evaluation
occurs for this command.

______________________________________________________________________

## Options (subset)

This command is intentionally minimal and usually has no options. See `topmark config defaults -h`
for any environment‑specific flags that may be available in your build.

`topmark config defaults` supports content-rendering options such as `--output-format`,
`--pyproject`, `--root`, color controls, and TEXT verbosity. See `topmark config defaults -h` for
the complete command help.

Note: `-v` / `--verbose` applies only to TEXT output. This pure content-producing command does not
support `--quiet`. Markdown and machine-readable formats ignore TEXT-only verbosity controls.

______________________________________________________________________

## Exit codes

`topmark config defaults` is a pure informational/content-producing command and exits with
`SUCCESS (0)` on successful execution.

Common `config defaults` exit codes:

| Scenario                       | Exit code          |
| ------------------------------ | ------------------ |
| Defaults rendered successfully | `SUCCESS (0)`      |
| Invalid CLI usage              | `USAGE_ERROR (64)` |

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

Machine-readable config snapshots emit normalized canonical qualified file type identifiers after
configuration freeze.

Notes:

- `config defaults` is **file-agnostic** and emits a configuration snapshot derived only from the
  canonical built-in defaults table (no discovery and no merge with project/user config).
- The machine-readable snapshot includes TOML-authored runtime sections such as `[writer]` when they
  are present in the canonical defaults, even though those sections are resolved outside the layered
  `Config` model at runtime.
- No diagnostics are emitted for this command.

### JSON schema

A single JSON document is emitted:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload (canonical defaults snapshot) */ }
}
```

### NDJSON schema

NDJSON is a stream where each line is a JSON object. Every record includes `kind` and `meta`.

Stream:

1. `kind="config"` (canonical defaults snapshot)

Example:

```jsonc
{"kind":"config","meta":{...},"config":{...}}
```

______________________________________________________________________

## Troubleshooting

- **Unexpected defaults**: remember that `config defaults` ignores all project, user, and CLI
  overlay configuration.
- **Unexpected identifier formatting**: machine-readable output may emit normalized canonical
  qualified identifiers such as `topmark:python`.
- **Need the real effective config**: use [`topmark config dump`](./dump.md) instead.

______________________________________________________________________

## Related commands

- [`topmark config check`](./check.md) — validate the effective frozen merged configuration and
  staged config-loading diagnostics.
- [`topmark config dump`](./dump.md) — show the effective frozen configuration, including normalized
  canonical file type identifiers.
- [`topmark config init`](./init.md) — print the bundled example TopMark TOML resource.

An overview of all CLI commands is available in [CLI overview](../../cli.md).
