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

In the current implementation, effective strictness applies across staged config-loading/preflight
validation.

{% include-markdown "\_snippets/config-validation-contract.md" %}

TopMark performs whole-source TOML schema validation during loading. Unknown sections or keys,
malformed section shapes, and missing known sections are reported as configuration diagnostics
before staged config-validation semantics are applied. Only the validated layered fragment is passed
to the config layer for merging.

- [`topmark config check`](./config/check.md) — validate the *effective merged* configuration and
  report diagnostics.
- [`topmark config dump`](./config/dump.md) — show the *effective merged* configuration.
- [`topmark config defaults`](./config/defaults.md) — show the *built-in default TopMark TOML
  document*.
- [`topmark config init`](./config/init.md) — print the bundled example TopMark TOML resource.

## Exit codes

Exit-code behavior for `config` subcommands follows a consistent pattern:

- Informational commands (`config dump`, `config defaults`, `config init`) exit with `SUCCESS (0)`
  on success.
- Validation command (`config check`) exits with:
  - `SUCCESS (0)` when configuration is valid
  - `FAILURE (1)` when validation completes and reports failing diagnostics
- CLI usage errors (invalid options, incompatible flags) exit with `USAGE_ERROR (64)`.
- Configuration loading/processing failures exit with `CONFIG_ERROR (78)` where applicable.
- Unexpected internal failures exit with `UNEXPECTED_ERROR (255)`.

See [`Exit codes`](../exit-codes.md) for the complete CLI-wide exit-code contract.

Note on output controls:

- `-v` / `--verbose` applies only to TEXT output across all `config` subcommands.
- `--quiet` is supported only for commands that provide a meaningful status or inspection signal
  (`config check`, `config dump`). Pure content-producing commands (`config defaults`,
  `config init`) do not support `--quiet`.

When using `topmark config dump --show-layers`, the command also exposes **layered configuration
provenance** in addition to the flattened effective configuration. This layered view reflects how
configuration was built from individual TOML sources (defaults, discovered config, CLI overrides)
and includes source-local TOML fragments. This includes the original TOML fragments (after schema
validation) that contributed to each layer.

When running `config check`, effective validation strictness is determined by:

1. CLI override (`--strict` / `--no-strict`)
1. TOML value (`strict_config_checking`)
1. default non-strict behaviour

Warnings are treated as errors only when strict config checking is enabled. In the current
implementation, this applies to staged config-loading/preflight validation as a whole. For 1.0, this
evaluation occurs over staged validation, while only the flattened compatibility diagnostics
contract is exposed at CLI/API/machine boundaries.

Note that `strict_config_checking` is a **source-local TOML option**, not a layered configuration
field. It influences validation behaviour but is not part of the final merged config; however, it is
visible in layered provenance output (`config dump --show-layers`).
