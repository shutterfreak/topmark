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

## Subcommands

| Command                                         | Purpose                                                                        |
| ----------------------------------------------- | ------------------------------------------------------------------------------ |
| [`topmark config check`](config/check.md)       | Validate the effective merged configuration and report diagnostics.            |
| [`topmark config dump`](config/dump.md)         | Display the effective merged configuration and layered provenance information. |
| [`topmark config defaults`](config/defaults.md) | Show the built-in default TopMark TOML document.                               |
| [`topmark config init`](config/init.md)         | Render the bundled starter TopMark TOML configuration template.                |

Source-local options under `[config]` / `[tool.topmark.config]` (such as `root` and `strict`) are
resolved during configuration loading. They do not participate in layered config merging, but
influence discovery and validation behaviour.

{% include-markdown "\_snippets/config-strictness.md" %}

In the current implementation, effective strictness applies across staged config-loading/preflight
validation.

{% include-markdown "\_snippets/config-validation-contract.md" %}

Configuration and policy values handled by these commands are part of the stable **public
configuration surface**. Internal helper types such as
\[`PolicyOverrides`\][topmark.config.overrides.PolicyOverrides] and
\[`ConfigOverrides`\][topmark.config.overrides.ConfigOverrides] are not exposed here; they are used
internally by CLI/API orchestration. When using the Python API, provide plain mapping-based inputs
via `config=...`, `policy=...`, and `policy_by_type=...`.

API overlays follow the same identifier normalization and policy-resolution semantics as TOML
configuration and CLI filtering.

TopMark performs whole-source TOML schema validation during loading before layered config merging
and runtime applicability evaluation. Unknown sections or keys, malformed section shapes, and
missing known sections are reported as configuration diagnostics before staged config-validation
semantics are applied. Only the validated layered fragment is passed to the config layer for
merging.

File type identifiers in configuration may use either:

- local identifiers such as `python`
- canonical qualified identifiers such as `topmark:python`

Internally, configuration freeze normalizes identifiers to canonical qualified keys before resolver,
filtering, policy, and binding evaluation.

Local identifiers are accepted only when unambiguous in the effective composed registry.

{% include-markdown "\_snippets/file-type-identifiers.md" %}

An overview of all CLI commands is available in [CLI overview](../cli.md).

______________________________________________________________________

## Command applicability

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
- resolver filtering
- machine-readable output
- policy lookup

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
  - `SUCCESS (0)` when configuration is valid
  - `FAILURE (1)` when validation completes and reports failing diagnostics
- CLI usage errors (invalid options, incompatible flags) exit with `USAGE_ERROR (64)`.
- Configuration loading/processing failures exit with `CONFIG_ERROR (78)` where applicable.
- Unexpected internal failures exit with `UNEXPECTED_ERROR (255)`.

See [`Exit codes`](../exit-codes.md) for the complete CLI-wide exit-code contract.

### Output behavior

Note on output controls:

- `-v` / `--verbose` applies only to TEXT output across all `config` subcommands.
- `--quiet` is supported only for commands that provide a meaningful status or inspection signal
  ([`config check`](config/check.md), [`config dump`](config/dump.md)). Pure content-producing
  commands ([`config defaults`](config/defaults.md), [`config init`](config/init.md)) do not support
  `--quiet`.

When using [`topmark config dump --show-layers`](config/dump.md), the command also exposes **layered
configuration provenance** in addition to the flattened effective configuration. This layered
provenance view reflects how configuration was built from individual TOML sources (defaults,
discovered config, CLI overrides) and includes source-local TOML fragments. This includes the
original TOML fragments (after schema validation) that contributed to each layer.

Machine-readable config snapshots emit normalized canonical qualified file type identifiers after
configuration freeze.

When running [`config check`](config/check.md), effective validation strictness is determined by:

1. CLI override (`--strict` / `--no-strict`)
1. TOML value (`strict`)
1. default non-strict behaviour

Warnings are treated as errors only when strict config checking is enabled. Identifier ambiguity,
malformed identifiers, and runtime applicability diagnostics participate in this staged validation
flow. In the current implementation, this applies to staged config-loading/preflight validation as a
whole. For 1.0, this evaluation occurs over staged validation, while only the flattened
compatibility diagnostics contract is exposed at CLI/API/machine boundaries.

Note that `strict` is a **source-local TOML option**, not a layered configuration field. It
influences validation behaviour but is not part of the final merged config; however, it is visible
in layered provenance output ([`config dump --show-layers`](config/dump.md)).

______________________________________________________________________

## Related docs

- [Command overview](../cli.md)
- [Configuration](../configuration.md)
- [Filtering](../filtering.md)
- [Policies](../policies.md)
- [Configuration discovery](../../configuration/discovery.md)
- [Configuration schema](../../dev/config-schema.md)
- [Exit codes](../exit-codes.md)

______________________________________________________________________

## Troubleshooting

- **Unexpected file type filter behavior**: prefer qualified identifiers such as `topmark:python`
  when local identifiers may be ambiguous.
- **Unexpected policy application**: inspect normalized identifiers using
  [`topmark config dump`](config/dump.md).
- **Unexpected validation failures**: use [`topmark config check`](config/check.md) together with
  `-vv` or machine-readable output to inspect staged validation diagnostics.
