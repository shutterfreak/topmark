<!--
topmark:header:start

  project      : TopMark
  file         : dump.md
  file_relpath : docs/usage/commands/config/dump.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `config dump` Command Guide

**Purpose:** Dump the *effective merged* configuration used by TopMark.

The `config dump` subcommand (part of the TopMark [`config` Command Family](../config.md)) prints
the **effective TopMark configuration** as TOML after applying built-in defaults, discovered
project/user config, and any CLI overrides.

It is **file-agnostic**: it does not resolve or process any files.

______________________________________________________________________

## Quick start

```bash
# Dump merged configuration (TOML)
topmark config dump

# Honor include/exclude patterns and pattern files
topmark config dump --exclude .venv --exclude-from .gitignore

# Honor patterns from STDIN
printf "*.py\n" | topmark config dump --include-from -
```

______________________________________________________________________

## Key properties

- Shows the **merged** configuration (defaults ⟶ discovered config ⟶ `--config` files ⟶ CLI flags).

- With `--show-layers`, also shows the **layered configuration provenance** before the flattened
  configuration.

- **File-agnostic**:

  - Positional PATHS are **not accepted** (the command fails if provided).
  - `--files-from` is accepted and treated as a source of input paths, but input paths do not affect
    the dumped configuration.

- **Filters are config**:

  - `--include`, `--exclude` are honored.
  - `--include-from` / `--exclude-from` are honored.
  - `--include-from -` / `--exclude-from -` read patterns from STDIN.

- Output is **plain TOML**. When run with higher verbosity (e.g., `-v`), the TOML is wrapped between
  BEGIN/END markers for easy parsing:

  \# === BEGIN[TOML] ===

  ...TOML...

  \# === END[TOML] ===

### Layered provenance output (`--show-layers`)

When `--show-layers` is used, `config dump` emits two TOML documents in sequence:

1. A **layered provenance export** describing how configuration was constructed.
1. The final **flattened effective configuration** (unchanged default behaviour).

The layered export is inspection-oriented and uses an array-of-tables structure:

```toml
[[layers]]
origin = "<defaults>"
kind = "default"
precedence = 0

[layers.toml.config]
strict_config_checking = false
```

Each layer includes:

- `origin` — where the configuration came from (e.g. `<defaults>`, file path)
- `kind` — layer type (e.g. `default`, `discovered`)
- `precedence` — merge order
- `scope_root` — optional root for discovered configs
- `toml` — the source-local TopMark TOML fragment

The second TOML document is identical to the standard flattened output.

{% include-markdown "\_snippets/config-resolution.md" %}

______________________________________________________________________

## Input modes

- **List on STDIN for patterns**: `--include-from -` or `--exclude-from -` read newline-delimited
  patterns from STDIN. When using `-`, STDIN must be piped; otherwise the command fails.
- **Content on STDIN** (`-` as PATH) is not supported by `config dump`. This mode is only meaningful
  for file-processing commands (e.g., `check`, `strip`).
- **`--files-from`** is accepted but does not influence the dumped configuration. File lists are
  considered inputs for processing commands, not configuration state.

______________________________________________________________________

## Options (subset)

| Option            | Description                                                                |
| ----------------- | -------------------------------------------------------------------------- |
| `--config`        | Merge an explicit TOML config file (can be repeated).                      |
| `--no-config`     | Do not discover local project/user config.                                 |
| `--include`       | Add include patterns (can be repeated).                                    |
| `--exclude`       | Add exclude patterns (can be repeated).                                    |
| `--include-from`  | Read include patterns from file (one per line, `#` comments allowed).      |
| `--exclude-from`  | Read exclude patterns from file (one per line, `#` comments allowed).      |
| `--file-type`     | Restrict to specific TopMark file type identifiers (affects config state). |
| `--relative-to`   | Base directory for relative path handling in config.                       |
| `--align-fields`  | Whether to align header fields (captured in config).                       |
| `--header-format` | Header rendering format override (captured in config).                     |

> Run `topmark config dump -h` for the full list of options and help text.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tools.

The canonical schema, stable `kind` values, and shared conventions are documented here:

- [Machine output schema (JSON & NDJSON)](../../../dev/machine-output.md)
- [Machine formats](../../../dev/machine-formats.md)

Notes:

- `config dump` is **file-agnostic** and emits the effective configuration after applying defaults →
  discovered config → `--config` files → CLI overrides.
- With `--show-layers`, machine output also includes a `config_provenance` payload before the
  flattened config.
- Diagnostics are not emitted for this command; it is an inspection view of the merged config.

### JSON schema

A single JSON document is emitted:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload (effective merged) */ }
}
```

With `--show-layers`, the JSON envelope becomes:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config_provenance": { /* ConfigProvenancePayload */ },
  "config": { /* ConfigPayload */ }
}
```

### NDJSON schema

NDJSON is a stream where each line is a JSON object. Every record includes `kind` and `meta`.

Default mode:

1. `kind="config"` (effective merged config snapshot)

Example:

```jsonc
{"kind":"config","meta":{...},"config":{...}}
```

With `--show-layers`:

1. `kind="config_provenance"` (layered provenance export)
1. `kind="config"` (effective merged config snapshot)

Example:

```jsonc
{"kind":"config_provenance","meta":{...},"config_provenance":{...}}
{"kind":"config","meta":{...},"config":{...}}
```

______________________________________________________________________

## Verbosity

`config dump` prints configuration; it does not render program output with per‑file diagnostics. The
`verbosity_level` setting is a runtime/CLI concern and is **not** serialized to TOML in the output.

When verbosity ≥ 1, BEGIN/END markers are included around the TOML output.

______________________________________________________________________

## Notes

- The output reflects the configuration **TopMark would use** if you ran processing commands
  (`check`, `strip`) with the same configuration-related flags in the current working directory.
- For per-file configuration (e.g., overrides that may depend on path), consider a future option
  like `--for FILE` (not currently implemented), similar to ESLint’s `--print-config`.

______________________________________________________________________

## Related commands

- [`topmark config check`](./check.md) — check the *effective merged* configuration for errors.
- [`topmark config defaults`](./defaults.md) — show the *built-in default TopMark TOML document*.
- [`topmark config init`](./init.md) — print the bundled example TopMark TOML resource.
