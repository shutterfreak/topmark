<!--
topmark:header:start

  project      : TopMark
  file         : version.md
  file_relpath : docs/usage/commands/version.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `version` Command Guide

The `version` subcommand prints the TopMark version string (semver) and exits.

______________________________________________________________________

## Quick start

```bash
topmark version
# → 1.2.3
```

______________________________________________________________________

## Output

- Prints only the version string (e.g., `1.2.3`, `1.2.3.dev0`, `1.2.3-rc.1`).
- Generate version identifier in SemVer format with the `--semver` option.
- Suitable for scripts (no extra labels or decoration).

______________________________________________________________________

## Options

This command is intentionally minimal and usually has no options. See `topmark version -h` for
any environment-specific flags that may be available in your build.
