<!--
topmark:header:start

  project      : TopMark
  file         : dump_config.md
  file_relpath : docs/usage/commands/dump_config.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `dump-config` Command Guide

The `dump-config` subcommand prints the **effective TopMark configuration** as TOML after applying
built-in defaults, discovered project/user config, and any CLI overrides.

It is **file-agnostic**: it does not resolve or process any files.

______________________________________________________________________

## Quick start

```bash
# Dump merged configuration (TOML)
topmark dump-config

# Honor include/exclude patterns and pattern files
topmark dump-config --exclude .venv --exclude-from .gitignore

# Honor patterns from STDIN
printf "*.py\n" | topmark dump-config --include-from -
```

______________________________________________________________________

## Key properties

- Shows the **merged** configuration (defaults ⟶ discovered config ⟶ `--config` files ⟶ CLI flags).

- **File-agnostic**:

  - Positional PATHS are **ignored** (a note is printed).
  - `--files-from` is **ignored** (a note is printed).

- **Filters are config**:

  - `--include`, `--exclude` are honored.
  - `--include-from` / `--exclude-from` are honored.
  - `--include-from -` / `--exclude-from -` read patterns from STDIN.

- Output is **plain TOML**. When run with higher verbosity (e.g., `-v`), the TOML is wrapped between
  BEGIN/END markers for easy parsing:

  # === BEGIN ===

  ...TOML...

  # === END ===

{% include-markdown "\_snippets/config-resolution.md" %}

______________________________________________________________________

## Input modes

- **List on STDIN for patterns**: `--include-from -` or `--exclude-from -` read newline-delimited
  patterns from STDIN.
- **Content on STDIN** (`-` as PATH) is **ignored** by `dump-config`. This mode is only meaningful
  for file-processing commands (e.g., `check`, `strip`).
- **`--files-from`** is **ignored**. File lists are considered *inputs*, not *configuration*.

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

> Run `topmark dump-config -h` for the full list of options and help text.

______________________________________________________________________

## Verbosity

`dump-config` prints configuration; it does not render program output with per‑file diagnostics. The
`verbosity_level` setting is a runtime/CLI concern and is **not** serialized to TOML in the output.

When verbosity ≥ 1, BEGIN/END markers are included around the TOML output.

______________________________________________________________________

## Notes

- The output reflects the configuration **TopMark would use** if you ran the processing commands
  (`check`, `strip`) with the same flags in the current working directory.
- For per-file configuration (e.g., overrides that may depend on path), consider a future option
  like `--for FILE` (not currently implemented), similar to ESLint’s `--print-config`.
