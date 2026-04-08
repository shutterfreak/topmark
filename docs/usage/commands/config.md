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

TopMark performs whole-source TOML schema validation during loading. Unknown sections or keys are
reported as configuration diagnostics before the layered configuration is built. Only the validated
layered fragment is passed to the config layer for merging.

- [`topmark config check`](./config/check.md) — validate the *effective merged* configuration and
  report diagnostics.
- [`topmark config dump`](./config/dump.md) — show the *effective merged* configuration.
- [`topmark config defaults`](./config/defaults.md) — show the *built-in default TopMark TOML
  document*.
- [`topmark config init`](./config/init.md) — print the bundled example TopMark TOML resource.

When using `topmark config dump --show-layers`, the command also exposes **layered configuration
provenance** in addition to the flattened effective configuration. This layered view reflects how
configuration was built from individual TOML sources (defaults, discovered config, CLI overrides)
and includes source-local TOML fragments. This includes the original TOML fragments (after schema
validation) that contributed to each layer.

When running `config check`, effective validation strictness is determined by:

1. CLI override (`--strict` / `--no-strict`)
1. TOML value (`strict_config_checking`)
1. default non-strict behaviour

Warnings are treated as errors only when strict config checking is enabled.

Note that `strict_config_checking` is a **source-local TOML option**, not a layered configuration
field. It influences validation behaviour but is not part of the final merged config; however, it is
visible in layered provenance output (`config dump --show-layers`).
