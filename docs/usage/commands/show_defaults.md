<!--
topmark:header:start

  project      : TopMark
  file         : show_defaults.md
  file_relpath : docs/usage/commands/show_defaults.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `show-defaults` Command Guide

The `show-defaults` subcommand prints TopMark’s **built‑in default configuration** as TOML. No
project files are discovered or merged — this is the raw baseline that ships with TopMark.

______________________________________________________________________

## Quick start

```bash
# Show the internal default configuration (TOML)
topmark show-defaults
```

______________________________________________________________________

## Key properties

- **Isolated**: ignores project/user config files and CLI overrides.
- **File‑agnostic**: does not resolve or process any PATHS.
- **Reference**: useful to understand default header layout and file‑type policies.

______________________________________________________________________

## When to use

- To compare your project’s configuration with the baseline shipped by TopMark.
- To seed your own config manually (you can copy & modify the parts you need).
- To debug why a field or policy is present when you did not set it explicitly.

______________________________________________________________________

## Options (subset)

This command is intentionally minimal and usually has no options. See `topmark show-defaults -h` for
any environment‑specific flags that may be available in your build.

______________________________________________________________________

## Related commands

- `topmark init-config` — prints a **starter** config scaffold you can save and edit.
- `topmark dump-config` — prints the **effective merged** configuration (defaults → discovered →
  CLI).
