<!--
topmark:header:start

  project      : TopMark
  file         : config.md
  file_relpath : docs/usage/commands/config.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `config` Command Family

TopMark exposes a `config` command group to inspect and scaffold configuration:

Source-local options under `[config]` / `[tool.topmark.config]` (such as `root` and
`strict_config_checking`) are resolved during configuration loading. They do not participate in
layered config merging, but influence discovery and validation behaviour.

- [`topmark config check`](./config/check.md) — validate the *effective merged* configuration and
  report diagnostics.
- [`topmark config dump`](./config/dump.md) — show the *effective merged* configuration.
- [`topmark config defaults`](./config/defaults.md) — show the *built-in default TopMark TOML
  document*.
- [`topmark config init`](./config/init.md) — print the bundled example TopMark TOML resource.

When running `config check`, effective validation strictness is determined by:

1. CLI override (`--strict` / `--no-strict`)
1. TOML value (`strict_config_checking`)
1. default non-strict behaviour

Warnings are treated as errors only when strict config checking is enabled.
