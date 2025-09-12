<!--
topmark:header:start

  project      : TopMark
  file         : init_config.md
  file_relpath : docs/usage/commands/init_config.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `init-config` Command Guide

The `init-config` subcommand prints a **starter TopMark configuration** as TOML to stdout. It does
not read or write any files by itself — redirect the output to create a config file.

______________________________________________________________________

## Quick start

```bash
# Print a starter configuration to stdout
topmark init-config

# Create a new project config file
topmark init-config > topmark.toml

# Or integrate into pyproject
topmark init-config >> pyproject.toml
```

______________________________________________________________________

## What it includes

The starter config provides a well‑commented TOML scaffold with the most common sections:

- `[fields]` – default header fields (`project`, `license`, …)
- `[header]` – order of fields to render in the header
- `[formatting]` – layout options (e.g., `align_fields`)
- `[files]` – file discovery knobs (`file_types`, `relative_to`, include/exclude lists)

You can safely edit the generated file to match your project’s needs.

______________________________________________________________________

## Key properties

- **File‑agnostic**: does not inspect any files.
- **Non‑destructive**: writes nothing; you control redirection.
- **Self‑documenting**: comments explain each field and reasonable defaults.

______________________________________________________________________

## Verbosity

`init-config` prints plain TOML to stdout. When run with higher verbosity (e.g., `-v`), the
output is wrapped between BEGIN/END markers for easy parsing in scripts and tests.

______________________________________________________________________

## Options (subset)

This command is intentionally minimal and usually has no options. See `topmark init-config -h` for
any environment‑specific flags that may be available in your build.

______________________________________________________________________

## Notes

- Use `topmark show-defaults` to view the **built‑in defaults** without a scaffold.
- Use `topmark dump-config` to view the **effective merged configuration** (defaults → discovered →
  CLI).
