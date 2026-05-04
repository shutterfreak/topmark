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

During loading, TopMark first performs whole-source TOML schema validation for all
discovered/configured TOML sources. Only the validated layered config fragment contributes to the
final merged output. Validation is evaluated across staged config-loading/preflight diagnostics,
which remain internal; reporting and machine/API/CLI surfaces expose only the flattened
compatibility diagnostics contract for 1.0.

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

```bash
# Suppress TEXT output and rely on the exit code
topmark config dump --quiet

# Render document-oriented Markdown output
topmark config dump --output-format markdown
```

______________________________________________________________________

## Key properties

- Shows the **merged** configuration (defaults ⟶ discovered config ⟶ `--config` files ⟶ CLI flags),
  after per-source TOML schema validation.

- With `--show-layers`, also shows the **layered configuration provenance** before the flattened
  configuration.

- **File-agnostic**:

  - Positional PATHS are **not accepted** (the command fails if provided).
  - `--files-from` is accepted as a documented config-override compatibility input, but file paths
    read from it do not affect the dumped configuration.

- **Filters are config**:

  - `--include`, `--exclude` are honored.
  - `--include-from` / `--exclude-from` are honored.
  - `--include-from -` / `--exclude-from -` read patterns from STDIN.

- Output is **plain TOML**. In TEXT output, when run with higher verbosity (e.g., `-v`), the TOML is
  wrapped between BEGIN/END markers for easy parsing. Markdown output is document-oriented and
  ignores TEXT-only verbosity and quiet controls:

  ```text
  \# === BEGIN[TOML] ===

  ...TOML...

  \# === END[TOML] ===
  ```

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
- `toml` — the source-local TopMark TOML fragment after TOML-layer validation

The second TOML document is identical to the standard flattened output.

{% include-markdown "\_snippets/config-resolution.md" %}

______________________________________________________________________

## Input modes

- **List on STDIN for patterns**: `--include-from -` or `--exclude-from -` read newline-delimited
  patterns from STDIN. When using `-`, STDIN must be piped; otherwise the command fails.
- **Content on STDIN** (`-` as PATH) is not supported by `config dump`. This mode is only meaningful
  for file-processing commands (for example, `check`, `strip`, and `probe`). `--stdin-filename` does
  not apply.
- **`--files-from`** is accepted but does not influence the dumped configuration. File lists are
  considered inputs for processing commands, not configuration state.

Positional PATH arguments are rejected as invalid CLI usage. `config dump` explains configuration
state; it does not process source files.

______________________________________________________________________

## Options (subset)

| Option            | Description                                                                           |
| ----------------- | ------------------------------------------------------------------------------------- |
| `--config`        | Merge an explicit TOML config file (can be repeated).                                 |
| `--no-config`     | Do not discover local project/user config.                                            |
| `--include`       | Add include patterns (can be repeated).                                               |
| `--exclude`       | Add exclude patterns (can be repeated).                                               |
| `--include-from`  | Read include patterns from file (one per line, `#` comments allowed).                 |
| `--exclude-from`  | Read exclude patterns from file (one per line, `#` comments allowed).                 |
| `--files-from`    | Accept a file-list input for compatibility; listed files do not affect dumped config. |
| `--file-type`     | Restrict to specific TopMark file type identifiers (affects config state).            |
| `--relative-to`   | Base directory for relative path handling in config.                                  |
| `--align-fields`  | Whether to align header fields (captured in config).                                  |
| `--header-format` | Header rendering format override (captured in config).                                |
| `-q`, `--quiet`   | Suppress TEXT output while preserving the command's exit status.                      |

> Run `topmark config dump -h` for the full list of options and help text.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tools.

The canonical schema, stable `kind` values, and shared conventions are documented here:

- [Machine output schema (JSON & NDJSON)](../../../dev/machine-output.md)
- [Machine formats](../../../dev/machine-formats.md)

{% include-markdown "\_snippets/output-contract.md" %}

Notes:

- `config dump` is **file-agnostic** and emits the effective configuration after applying defaults →
  discovered config → `--config` files → CLI overrides, with whole-source TOML validation performed
  per source before layered config merging.
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
  "config_provenance": { /* TomlProvenancePayload */ },
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

`config dump` prints configuration; it does not render program output with per-file diagnostics.

- In TEXT output, `-v` adds BEGIN/END markers around the TOML output.
- `--quiet` suppresses TEXT output while preserving the exit status.
- Markdown output is document-oriented and ignores TEXT-only verbosity and quiet controls.
- JSON/NDJSON output is machine-readable and ignores TEXT-only verbosity and quiet controls.

______________________________________________________________________

## Notes

- The output reflects the configuration **TopMark would use** if you ran processing commands
  (`check`, `strip`, or `probe`) with the same configuration-related flags in the current working
  directory, after TOML-layer validation and layered config merging.
- For per-file configuration (e.g., overrides that may depend on path), consider a future option
  like `--for FILE` (not currently implemented), similar to ESLint’s `--print-config`.

______________________________________________________________________

## Related commands

- [`topmark config check`](./check.md) — check the *effective merged* configuration for errors.
- [`topmark config defaults`](./defaults.md) — show the *built-in default TopMark TOML document*.
- [`topmark config init`](./init.md) — print the bundled example TopMark TOML resource.

## Exit codes

`topmark config dump` is an informational/inspection command and exits with `SUCCESS (0)` when the
effective configuration is rendered successfully.

Common `config dump` exit codes:

| Scenario                                   | Exit code           |
| ------------------------------------------ | ------------------- |
| Effective config rendered successfully     | `SUCCESS (0)`       |
| Invalid CLI usage                          | `USAGE_ERROR (64)`  |
| Configuration cannot be loaded for command | `CONFIG_ERROR (78)` |

Notes:

- This command does not process files and does not use file-processing exit codes such as
  `WOULD_CHANGE (2)`, `FILE_NOT_FOUND (66)`, or `IO_ERROR (74)`.
- Invalid positional paths are reported as CLI usage errors, not file-processing diagnostics.
- `--quiet` is supported for TEXT output and suppresses the rendered TOML while preserving the exit
  status.
- Markdown and machine formats ignore TEXT-only quiet and verbosity controls.

See [`Exit codes`](../../exit-codes.md) for the complete CLI-wide exit-code contract.
