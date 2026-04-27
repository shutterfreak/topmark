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
prints TopMark’s **built‑in default TopMark TOML document** as TOML. It uses a cleaned, comment-free
TOML representation derived from the built-in defaults (no project files are discovered or merged).

Because the output is generated from TopMark's built-in defaults, it reflects only the **layered
default config fragment**. Source-local TOML sections such as `[config]` and `[writer]` are not
resolved from project files here.

- `text` / `markdown` formats: minimal, comment-free TOML. Markdown is document-oriented and ignores
  TEXT-only verbosity/quiet controls.
- `json` / `ndjson`: a plain Config snapshot, with no diagnostics. Machine formats ignore TEXT-only
  verbosity/quiet controls.

______________________________________________________________________

## Quick start

```bash
# Show the internal default configuration (TOML)
topmark config defaults

# Suppress TEXT output and rely on the exit code
topmark config defaults --quiet

# Render document-oriented Markdown output
topmark config defaults --output-format markdown
```

______________________________________________________________________

## Key properties

- **Isolated**: ignores project/user config files and CLI overrides.
- **File‑agnostic**: does not resolve or process any PATHS.
- **Reference**: useful to understand the default layered config fragment, header layout, policy
  behavior, and TOML/config split.

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

## Options (subset)

This command is intentionally minimal and usually has no options. See `topmark config defaults -h`
for any environment‑specific flags that may be available in your build.

Note: `-v` / `--verbose` and `-q` / `--quiet` apply only to TEXT output. Markdown and machine
formats ignore these controls.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tools.

The canonical schema, stable `kind` values, and shared conventions are documented here:

- [Machine output schema (JSON & NDJSON)](../../../dev/machine-output.md)
- [Machine formats](../../../dev/machine-formats.md)

{% include-markdown "\_snippets/output-contract.md" %}

Notes:

- `config defaults` is **file-agnostic** and emits a configuration snapshot derived only from the
  built-in defaults (no discovery and no merge with project/user config).
- The output corresponds to the built-in layered config defaults, not to a whole-source TOML
  document after discovery/resolution.
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
- [`topmark config init`](./init.md) — print the bundled example TopMark TOML resource.
