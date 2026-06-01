<!--
topmark:header:start

  project      : TopMark
  file         : config.md
  file_relpath : docs/usage/commands/config.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# `topmark config`

TopMark exposes a `config` command group to inspect and scaffold configuration.

{% include-markdown "\_snippets/terminology.md" %}

## Subcommands

| Command                                         | Purpose                                                                         |
| ----------------------------------------------- | ------------------------------------------------------------------------------- |
| [`topmark config check`](config/check.md)       | Validate the effective runtime configuration and report diagnostics.            |
| [`topmark config dump`](config/dump.md)         | Display the effective runtime configuration and layered provenance information. |
| [`topmark config defaults`](config/defaults.md) | Show the built-in default TopMark TOML document.                                |
| [`topmark config init`](config/init.md)         | Render the bundled starter TopMark TOML configuration template.                 |

Source-local options under `[config]` / `[tool.topmark.config]` (such as `root` and `strict`) are
resolved during configuration loading. They do not participate in layered configuration merging, but
influence discovery and validation behavior.

{% include-markdown "\_snippets/config-strictness.md" %}

For the full discovery, precedence, path-resolution, and staged validation contract, see
[Configuration discovery, precedence, and policy](../../configuration/discovery.md).

Configuration and policy values handled by these commands are part of the stable **public
configuration surface**. Internal helper types such as
\[`PolicyOverrides`\][topmark.config.overrides.PolicyOverrides] and
\[`ConfigOverrides`\][topmark.config.overrides.ConfigOverrides] are not exposed here; they are used
internally by CLI/API orchestration. When using the Python API, provide plain mapping-based inputs
via `config=...`, `policy=...`, and `policy_by_type=...`.

API overlays follow the same identifier normalization and runtime policy-resolution semantics as
TOML configuration and CLI filtering.

TopMark performs whole-source TOML validation during loading before layered configuration merging
and runtime applicability evaluation. Unknown sections or keys, malformed section shapes, and
missing known sections are reported as configuration diagnostics before staged configuration-loading
validation semantics are applied. Only validated layered configuration fragments are passed to the
configuration layer for merging.

{% include-markdown "\_snippets/file-type-identifiers.md" %}

See [file-type filtering](../filtering.md#file-type-filtering) for the full identifier contract.

______________________________________________________________________

## Input applicability

The `config` command family is **file-agnostic**. These commands operate on configuration state and
do not process source files.

Across all `config` subcommands:

- positional PATH arguments are rejected as invalid CLI usage
- `-` is not a content-STDIN sentinel
- `--stdin-filename` does not apply
- file-list STDIN modes (for example, `--files-from -`) do not apply

Config discovery applies only where explicitly documented ([`config check`](config/check.md),
[`config dump`](config/dump.md)) and is not used by purely informational commands
([`config defaults`](config/defaults.md), [`config init`](config/init.md)).

______________________________________________________________________

## Shared configuration semantics

The `config` command family reflects the same stable configuration contract used by:

- CLI processing commands
- API overlays
- runtime resolution and filtering
- machine-readable output
- runtime policy lookup

Configuration handling intentionally does not support:

- fuzzy matching for file type identifiers
- implicit namespace fallback
- automatic alias expansion
- silent ambiguity resolution

______________________________________________________________________

## Shared behavior

### Exit codes

Exit-code behavior for `config` subcommands follows a consistent pattern:

- Informational commands ([`config dump`](config/dump.md), [`config defaults`](config/defaults.md),
  [`config init`](config/init.md)) exit with `SUCCESS (0)` on success.
- Validation command ([`config check`](config/check.md)) exits with:
  - `SUCCESS (0)` when configuration validation succeeds.
  - `CONFIG_ERROR (78)` when configuration validation fails.
- CLI usage errors (invalid options, incompatible flags) exit with `USAGE_ERROR (64)` when handled
  by TopMark command logic.
- Configuration loading and validation failures use `CONFIG_ERROR (78)` where applicable.
- Unexpected internal failures exit with `UNEXPECTED_ERROR (255)`.

Notes:

- `CONFIG_ERROR (78)` covers both configuration-loading failures and completed validation runs that
  report configuration errors.
- Click parser-level usage errors (for example, unknown commands, unknown options or invalid option
  values) may exit with code `2` before command logic runs.

See [`Exit codes`](../exit-codes.md) for the complete CLI-wide exit-code contract.

### Output behavior

Note on output controls:

- `-v` / `--verbose` applies only to TEXT rendering across all `config` subcommands.
- `--quiet` is supported only for commands that provide a meaningful status or inspection signal
  ([`config check`](config/check.md), [`config dump`](config/dump.md)). Pure content-producing
  commands ([`config defaults`](config/defaults.md), [`config init`](config/init.md)) do not support
  `--quiet`.

When using [`topmark config dump --show-layers`](config/dump.md), the command also exposes layered
configuration provenance in addition to the flattened effective runtime configuration. This layered
provenance view reflects how configuration was built from individual TOML sources (defaults,
discovered config, CLI overrides) and includes source-local TOML fragments. This includes the
original TOML fragments (after schema validation) that contributed to each layer.

Machine-readable configuration snapshots emit normalized canonical qualified file type identities
after configuration normalization.

### Strictness and provenance

When running [`config check`](config/check.md), effective validation strictness is determined by:

1. CLI override (`--strict` / `--no-strict`)
1. TOML value (`strict`)
1. default non-strict behavior

Warnings are treated as errors only when strict config checking is enabled. Identifier ambiguity,
malformed identifiers, and runtime applicability diagnostics participate in this staged validation
flow. For the stable 1.x line, this evaluation occurs over staged configuration-loading validation,
while only the flattened compatibility diagnostics surface is exposed at CLI, API, and
machine-readable output boundaries.

Note that `strict` is a **source-local TOML option**, not a layered configuration field. It
influences validation behavior but is not part of the final merged configuration; however, it is
visible in layered provenance output ([`config dump --show-layers`](config/dump.md)).

______________________________________________________________________

## Related docs

- [Command overview](../cli.md)
- [Configuration](../configuration.md)
- [Filtering](../filtering.md)
- [Policies](../policies.md)
- [Configuration discovery, precedence, and policy](../../configuration/discovery.md)
- [Configuration schema](../../dev/configuration-schema.md)
- [Machine-readable output](../machine-output.md)
- [Machine-readable format conventions](../../dev/machine-formats.md)
- [Exit codes](../exit-codes.md)
- [Terminology and Canonical Vocabulary](../../terminology.md)

______________________________________________________________________

## Troubleshooting

- **Unexpected file type filter behavior**: prefer qualified identifiers such as `topmark:python`
  when local identifiers may be ambiguous.
- **Unexpected policy application**: inspect normalized identifiers using
  [`topmark config dump`](config/dump.md).
- **Unexpected validation failures**: use [`topmark config check`](config/check.md) together with
  `-vv` or machine-readable output to inspect staged validation diagnostics.
