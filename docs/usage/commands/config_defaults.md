<!--
topmark:header:start

  project      : TopMark
  file         : config_defaults.md
  file_relpath : docs/usage/commands/config_defaults.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `config defaults` Command Guide

The `config defaults` subcommand (part of the TopMark [`config` Command Family](config.md))
prints TopMark’s **built‑in default configuration** as TOML.
It uses a cleaned, comment-free representation derived from the bundled
default config (no project files are discovered or merged).

- `default` / `markdown` formats: minimal, comment-free TOML.
- `json` / `ndjson`: a plain Config snapshot, with no diagnostics.

______________________________________________________________________

## Quick start

```bash
# Show the internal default configuration (TOML)
topmark config defaults
```

______________________________________________________________________

## Key properties

- **Isolated**: ignores project/user config files and CLI overrides.
- **File‑agnostic**: does not resolve or process any PATHS.
- **Reference**: useful to understand default header layout and file‑type policies.

> **How config is resolved**
>
> TopMark merges config from **defaults → user → project chain → `--config` → CLI**. Globs are
> evaluated relative to the **workspace base** (`relative_to`). Paths to other files (like
> `exclude_from`) are resolved relative to the **config file** that declared them.
>
> See: [`Configuration → Discovery & Precedence`](../../configuration/discovery.md).

______________________________________________________________________

## When to use

- To compare your project’s configuration with the baseline shipped by TopMark.
- To seed your own config manually (you can copy & modify the parts you need).
- To debug why a field or policy is present when you did not set it explicitly.

______________________________________________________________________

## Options (subset)

This command is intentionally minimal and usually has no options. See `topmark config defaults -h` for
any environment‑specific flags that may be available in your build.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tools.

The canonical schema, stable `kind` values, and shared conventions are documented here:

- [Machine output schema (JSON & NDJSON)](../../dev/machine-output.md)
- [Machine formats](../../dev/machine-formats.md)

Notes:

- `config defaults` is **file-agnostic** and emits a configuration snapshot derived only from
  TopMark’s built-in defaults (no discovery and no merge with project/user config).
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

- `topmark init-config` — prints a **starter** config scaffold you can save and edit.
- `topmark dump-config` — prints the **effective merged** configuration (defaults → discovered →
  CLI).
