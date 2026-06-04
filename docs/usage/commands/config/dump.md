<!--
topmark:header:start

  project      : TopMark
  file         : dump.md
  file_relpath : docs/usage/commands/config/dump.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# `topmark config dump`

**Purpose:** Dump the *effective* runtime configuration used by TopMark.

The `config dump` subcommand (part of [`topmark config`](../config.md)) prints the effective runtime
configuration as TOML after applying built-in defaults, discovered project/user configuration files,
and CLI overrides.

During loading, TopMark first performs whole-source TOML validation before layered configuration
merging and runtime applicability evaluation. Only validated layered configuration fragments
contribute to the final runtime output.

It is file-agnostic: it does not resolve or process any files.

{% include-markdown "\_snippets/terminology.md" %}

______________________________________________________________________

## File type identifier semantics

{% include-markdown "\_snippets/file-type-identifiers.md" %}

See [file-type filtering](../../filtering.md#file-type-filtering) for the full identifier contract.

______________________________________________________________________

## Quick start

```bash
# Dump effective configuration (TOML)
topmark config dump

# Honor include/exclude patterns and pattern files
topmark config dump --exclude .venv --exclude-from .gitignore

# Honor patterns from STDIN
printf "*.py\n" | topmark config dump --include-from -
```

```bash
# Suppress TEXT rendering and rely on the exit code
topmark config dump --quiet

# Render document-oriented Markdown output
topmark config dump --output-format markdown
```

______________________________________________________________________

## Behavior details

- Shows the effective runtime configuration (defaults ⟶ discovered configuration ⟶ `--config` files
  ⟶ CLI flags), after per-source TOML validation.

- With `--show-layers`, also shows the **layered configuration provenance** before the flattened
  effective runtime configuration.

- File-agnostic:

  - Positional PATHS are not accepted (the command fails if provided).
  - `--files-from` is accepted for compatibility, but listed paths do not affect the dumped
    configuration.

- Filters are configuration:

  - `--include`, `--exclude` are honored.
  - `--include-from` / `--exclude-from` are honored.
  - `--include-from -` / `--exclude-from -` read patterns from STDIN.

- Output is plain TOML. In TEXT rendering, when run with higher verbosity (e.g., `-v`), the TOML is
  wrapped between BEGIN/END markers for easy parsing. Markdown output is document-oriented and
  ignores TEXT-oriented verbosity and quiet controls:

  ```text
  \# === BEGIN[TOML] ===

  ...TOML...

  \# === END[TOML] ===
  ```

### Layered provenance output (`--show-layers`)

When `--show-layers` is used, `config dump` emits two TOML documents in sequence:

1. A layered provenance export describing how configuration was constructed.
1. The final flattened effective runtime configuration (unchanged default behavior).

The layered provenance export is inspection-oriented and uses an array-of-tables structure:

```toml
[[layers]]
origin = "<defaults>"
kind = "default"
precedence = 0

[layers.toml.config]
strict = false
```

Each layer includes:

- `origin` - where the configuration came from (e.g. `<defaults>`, resolved configuration-file path)
- `kind` - layer type (e.g. `default`, `discovered`)
- `precedence` - merge order
- `scope_root` - optional applicability root associated with the configuration source
- `toml` - the source-local TopMark TOML fragment after TOML-layer validation

For file-backed layers, `origin` and `scope_root` describe the resolved configuration-file target
used for configuration-source identity. If a configuration file is loaded through a symlink, layered
provenance reports the resolved target rather than the symlink spelling.

The second TOML document is identical to the standard flattened runtime configuration output.

TopMark resolves configuration from defaults, user config, the project chain, explicit `--config`
files, and CLI overrides before staged validation produces the effective runtime configuration.

For file-backed configuration sources, TopMark determines configuration-source identity using the
resolved configuration-file target. If a configuration file is reached through a symlink,
precedence, scope evaluation, applicability checks, and layered provenance operate on the resolved
target rather than the symlink spelling. See
[Configuration discovery, precedence, and policy](../../../configuration/discovery.md) for the full
configuration-loading and validation contract.

Configuration and policy override values shown by this command are part of the stable public
configuration surface. Internal implementation details are not part of the user-facing CLI or Python
API compatibility contract.

______________________________________________________________________

## Input applicability

- **List on STDIN for patterns**: `--include-from -` or `--exclude-from -` read newline-delimited
  patterns from STDIN. When using `-`, STDIN must be piped; otherwise the command fails.
- **Content on STDIN** (`-` as PATH) is not supported by `config dump`. This mode is only meaningful
  for file-processing commands (for example, [`check`](../check.md), [`strip`](../strip.md), and
  [`probe`](../probe.md)). `--stdin-filename` does not apply.
- **`--files-from`** is accepted for compatibility, but listed paths do not affect the dumped
  configuration. File lists are inputs for file-processing commands, not runtime configuration
  state.

When `--config PATH` refers to a symlinked configuration file, configuration loading and layered
provenance use the resolved configuration target as the configuration source. This mirrors the
configuration-source identity model used throughout configuration discovery.

Positional PATH arguments are rejected as invalid CLI usage. `config dump` explains configuration
state; it does not process source files.

______________________________________________________________________

## Command-specific options

| Option            | Description                                                                                         |
| ----------------- | --------------------------------------------------------------------------------------------------- |
| `--config`        | Merge an explicit TOML configuration file (can be repeated).                                        |
| `--no-config`     | Do not discover local project/user configuration file.                                              |
| `--include`       | Add include patterns (can be repeated).                                                             |
| `--exclude`       | Add exclude patterns (can be repeated).                                                             |
| `--include-from`  | Read include patterns from file (one per line, `#` comments allowed).                               |
| `--exclude-from`  | Read exclude patterns from file (one per line, `#` comments allowed).                               |
| `--files-from`    | Accept a file-list input for compatibility; listed paths do not affect the dumped configuration.    |
| `--file-type`     | Restrict to local or qualified TopMark file type identifiers (affects runtime configuration state). |
| `--relative-to`   | Base directory for relative path handling in configuration.                                         |
| `--align-fields`  | Whether to align header fields (captured in configuration).                                         |
| `--header-format` | Header rendering format override (captured in configuration).                                       |
| `-q`, `--quiet`   | Suppress TEXT rendering while preserving the command's exit status.                                 |

> Run `topmark config dump -h` for the full list of options and help text.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tools.

The canonical schema, stable `kind` values, and shared conventions are documented here:

- [Machine-readable output](../../machine-output.md)
- [Machine-readable format conventions](../../../dev/machine-formats.md)

{% include-markdown "\_snippets/output-contract.md" %}

Machine-readable configuration snapshots emit normalized canonical qualified file type identities
after configuration normalization.

Machine-readable configuration provenance uses configuration-source identity based on the resolved
configuration-file target. Configuration-source paths reported by machine-readable output therefore
describe the resolved configuration target rather than a symlink spelling used to reach it.

{% include-markdown "\_snippets/path-serialization-contract.md" %}

Notes:

- `config dump` is file-agnostic and emits the effective runtime configuration after applying
  defaults -> discovered configuratin -> `--config` files -> CLI overrides, with whole-source TOML
  validation performed per source before layered configuration merging.
- With `--show-layers`, machine-readable output also includes a `config_provenance` payload before
  the flattened runtime configuration snapshot.
- File-backed provenance entries use configuration-source identity based on resolved configuration
  targets. `origin` and `scope_root` therefore describe resolved configuration targets rather than
  symlink spellings.
- Diagnostics are not emitted for this command; it is an inspection view of the effective runtime
  configuration.

### JSON schema

A single machine-readable JSON document is emitted:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload (effective runtime snapshot) */ }
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

The `config_provenance` payload reports configuration layers using configuration-source identity.
For file-backed layers, provenance paths describe resolved configuration targets.

### NDJSON schema

NDJSON is a stream where each line is a machine-readable JSON record.

Default mode:

1. `kind="config"` (effective runtime configuration snapshot)

Example:

```jsonc
{"kind":"config","meta":{...},"config":{...}}
```

With `--show-layers`:

1. `kind="config_provenance"` (layered provenance export snapshot)
1. `kind="config"` (effective runtime configuration snapshot)

Example:

```jsonc
{"kind":"config_provenance","meta":{...},"config_provenance":{...}}
{"kind":"config","meta":{...},"config":{...}}
```

______________________________________________________________________

## Exit codes

`topmark config dump` is an informational inspection command and exits with `SUCCESS (0)` when the
effective runtime configuration is rendered successfully.

Common `config dump` exit codes:

| Scenario                                              | Exit code           |
| ----------------------------------------------------- | ------------------- |
| Effective runtime configuration rendered successfully | `SUCCESS (0)`       |
| Invalid CLI usage                                     | `USAGE_ERROR (64)`  |
| Configuration cannot be loaded for command            | `CONFIG_ERROR (78)` |

Notes:

- Click parser-level usage errors (for example, unknown commands, unknown options, or invalid option
  values) may exit with code `2` before command logic runs.
- This command does not process files and does not use file-processing exit codes such as
  `WOULD_CHANGE (3)`, `FILE_NOT_FOUND (66)`, or `IO_ERROR (74)`.
- Invalid positional paths are reported as CLI usage errors, not file-processing diagnostics.
- `--quiet` is supported for TEXT rendering and suppresses the rendered TOML while preserving the
  exit status.
- Markdown and machine-readable JSON/NDJSON output ignore TEXT-oriented quiet and verbosity
  controls.

See [`Exit codes`](../../exit-codes.md) for the complete CLI-wide exit-code contract.

______________________________________________________________________

## Shared output controls

`config dump` prints configuration; it does not render program output with per-file diagnostics.

- In TEXT rendering, `-v` adds BEGIN/END markers around the TOML output.
- `--quiet` suppresses TEXT rendering while preserving the exit status.
- Markdown output is document-oriented and ignores TEXT-oriented verbosity and quiet controls.
- Machine-readable JSON and NDJSON output ignore TEXT-oriented verbosity and quiet controls.

______________________________________________________________________

## Related commands

- [`topmark config check`](./check.md) - validate the effective runtime configuration and staged
  configuration-loading diagnostics.
- [`topmark config defaults`](./defaults.md) - show the canonical built-in default TOML document.
- [`topmark config init`](./init.md) - print the bundled example TopMark TOML template.

______________________________________________________________________

## Related docs

- [Command overview](../../cli.md)
- [Configuration](../../configuration.md)
- [Filtering](../../filtering.md)
- [Policies](../../policies.md)
- [Configuration discovery, precedence, and policy](../../../configuration/discovery.md)
- [Configuration schema](../../../dev/configuration-schema.md)
- [Machine-readable output](../../machine-output.md)
- [Machine-readable format conventions](../../../dev/machine-formats.md)
- [Exit codes](../../exit-codes.md)
- [Terminology and Canonical Vocabulary](../../../terminology.md)

______________________________________________________________________

## Notes

- The output reflects the effective runtime configuration TopMark would use if you ran
  file-processing commands ([`check`](../check.md), [`strip`](../strip.md), or
  [`probe`](../probe.md)) with the same configuration-related flags in the current working
  directory, after TOML-layer validation and layered configuration merging.
- For per-file configuration (e.g., overrides that may depend on path), consider a future option
  like `--for FILE` (not currently implemented), similar to ESLint's `--print-config`.

______________________________________________________________________

## Troubleshooting

- **Unexpected file type filter behavior**: prefer qualified identifiers such as `topmark:python`
  when local identifiers may be ambiguous.
- **Unexpected policy application**: inspect normalized identifiers in the dumped runtime
  configuration.
- **Unexpected configuration layering**: use `--show-layers` to inspect layered provenance and
  validated TOML fragments.
- **Configuration path differs from invocation spelling**: layered provenance and machine-readable
  provenance report resolved configuration targets. If a configuration file is loaded through a
  symlink, `origin` and `scope_root` may differ from the path spelling supplied on the command line.
