<!--
topmark:header:start

  project      : TopMark
  file         : check.md
  file_relpath : docs/usage/commands/config/check.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `config check` Command Guide

**Purpose:** Check the config for errors.

The `config check` subcommand (part of the TopMark [`config` Command Family](../config.md))
validates the **effective merged configuration** and reports any configuration diagnostics.

Unlike [`check`](../check.md) / [`strip`](../strip.md), this command is **file-agnostic**: it does
not resolve or process files. It is intended for CI validation and debugging configuration
precedence issues.

See also:

- [CLI overview](../../cli.md)
- [Configuration](../../configuration.md)
- [Filtering](../../filtering.md)
- [Policies](../../policies.md)
- [Configuration discovery](../../../configuration/discovery.md)
- [Configuration schema](../../../dev/config-schema.md)

Output formats:

- `text`: human-readable validation result (optionally verbose).
- `markdown`: Markdown report suitable for pasting into tickets or CI logs.
- `json` / `ndjson`: machine-readable envelopes/records aligned with TopMark’s machine format
  conventions.

______________________________________________________________________

## File type identifier semantics

File type identifiers in configuration may use either:

- local identifiers such as `python`
- canonical qualified identifiers such as `topmark:python`

Internally, configuration freeze normalizes identifiers to canonical qualified keys before resolver,
filtering, policy, and binding evaluation.

Local identifiers are accepted only when unambiguous in the effective composed registry.

{% include-markdown "\_snippets/file-type-identifiers.md" %}

______________________________________________________________________

## Quick start

```bash
# Validate merged config (default human output)
topmark config check

# Fail if warnings are present (in addition to errors)
topmark config check --strict

# CLI override wins over TOML strictness
# (even if topmark.toml contains `[config] strict_config_checking = true`)
topmark config check --no-strict

# Machine-readable JSON (single document)
topmark config check --output-format json

# Machine-readable NDJSON (record stream)
topmark config check --output-format ndjson

# Suppress TEXT output and rely on the exit code
topmark config check --quiet

# Render document-oriented Markdown output
topmark config check --output-format markdown
```

______________________________________________________________________

## Key properties

- **Validates merged config**: loads defaults → discovered config → `--config` files → CLI
  overrides, performs whole-source TOML schema validation per source before layered config merge and
  runtime applicability evaluation, then validates staged config-loading diagnostics and freezes the
  final configuration.

- **Reports TOML schema issues**: unknown sections/keys, malformed TOML structures, and missing
  known sections are surfaced as configuration diagnostics originating from the TOML layer.

- **File-agnostic**: positional PATHS are rejected as unexpected arguments. `-` is not
  content-on-STDIN for this command, and file-list STDIN modes such as `--files-from -` do not
  apply.

- **CI-friendly**: exits with `FAILURE (1)` when validation fails.

- **Strict mode**: effective strictness is determined as:

  - CLI override (`--strict` / `--no-strict`)
  - resolved TOML value from `[config].strict_config_checking` /
    `[tool.topmark.config].strict_config_checking`
  - default non-strict mode

  Errors always fail; warnings fail only when strict config checking is enabled across staged
  config-loading/preflight validation.

{% include-markdown "\_snippets/config-resolution.md" %}

Configuration and policy override values shown by this command are part of the stable public
configuration surface. Internal implementation helpers such as
\[`PolicyOverrides`\][topmark.config.overrides.PolicyOverrides] and
\[`ConfigOverrides`\][topmark.config.overrides.ConfigOverrides] are not part of the user-facing CLI
or Python API contract.

API overlays follow the same identifier normalization and policy-resolution semantics documented
above for TOML configuration and CLI filtering.

______________________________________________________________________

## When to use

- In CI to ensure config changes do not introduce warnings/errors.
- When debugging configuration discovery/precedence (e.g. *why is this policy enabled?*).
- When integrating TopMark configuration into external tooling that needs a validated snapshot.

______________________________________________________________________

## Input applicability

`config check` validates configuration state, not source files. It therefore does not accept
file-processing inputs:

- positional PATH arguments are rejected as invalid CLI usage
- `-` is not a content-STDIN sentinel for this command
- `--stdin-filename` does not apply
- file-list STDIN modes (for example, `--files-from -`) do not apply

Use `--config PATH` to validate an explicit config file, or rely on normal config discovery to
validate the effective merged configuration for the current working directory.

______________________________________________________________________

## Options (subset)

| Option                 | Description                                                      |
| ---------------------- | ---------------------------------------------------------------- |
| `--strict/--no-strict` | Override resolved TOML strict config checking for this run.      |
| `--output-format`      | Output format (`text`, `markdown`, `json`, `ndjson`).            |
| `-q`, `--quiet`        | Suppress TEXT output while preserving the command’s exit status. |
| `--config`             | Merge an explicit TOML config file (can be repeated).            |
| `--no-config`          | Do not discover local project/user config.                       |
| `-v`, `--verbose`      | Increase human-readable diagnostic detail.                       |

> Run `topmark config check -h` for the full list of options and help text.

______________________________________________________________________

## Exit codes

`topmark config check` exits with `SUCCESS (0)` when the effective configuration is valid. It exits
with `FAILURE (1)` when validation completes and reports failing diagnostics:

- errors are present, or
- effective strict config checking is enabled and warnings are present.

Common `config check` exit codes:

| Scenario                                       | Exit code           |
| ---------------------------------------------- | ------------------- |
| Valid effective configuration                  | `SUCCESS (0)`       |
| Validation completed with failing diagnostics  | `FAILURE (1)`       |
| Invalid CLI usage                              | `USAGE_ERROR (64)`  |
| Configuration cannot be loaded for the command | `CONFIG_ERROR (78)` |

Notes:

- `FAILURE (1)` is a validation result for this command, not an unexpected crash.
- Warning-only diagnostics exit with `SUCCESS (0)` unless strict config checking is enabled.
- Malformed TOML discovered by `config check` is reported as a failing validation result and exits
  with `FAILURE (1)`.
- CLI usage errors (for example, invalid options) exit with `USAGE_ERROR (64)`.

Because `config check` is file-agnostic, invalid positional paths or file-processing input options
are reported as CLI usage errors rather than as file-processing diagnostics.

See [`Exit codes`](../../exit-codes.md) for the complete CLI-wide exit-code contract.

______________________________________________________________________

## Output formats

### Default output (human)

- If there are no diagnostics: prints a short success message.
- If diagnostics exist: prints counts of errors/warnings/info. With `-v` and above, it prints each
  diagnostic line.
- With higher TEXT verbosity, it also prints the list of config files that were processed.
- With very high TEXT verbosity, it can print the merged config as TOML (wrapped with BEGIN/END
  markers).
- `--quiet` suppresses TEXT output while preserving the exit status (does not affect exit codes).
- File-processing diagnostics, summaries, diffs, and reports are not emitted by this command.

### Markdown output

`--output-format markdown` emits a report containing:

- overall status (`ok` / `failed`)
- whether effective strict config checking was enabled
- diagnostic counts
- (optionally) full diagnostic list and processed config files, depending on verbosity

This format is designed for CI logs and copy/paste into issues. It is document-oriented and ignores
TEXT-only verbosity and quiet controls.

### Typical validation flow

```mermaid
flowchart TD
    A["Resolve TOML sources<br/>defaults, discovered config, --config, CLI context"]
    B["Validate each whole-source TOML fragment<br/>unknown sections, unknown keys, malformed shapes, missing known sections"]
    C["Extract layered config fragment<br/>source-local sections like [config] and [writer] stay TOML-local"]
    D["Merge layered config into mutable draft<br/>apply precedence and overrides"]
    E["Validate staged config-loading diagnostics<br/>TOML-source, merged-config, runtime-applicability"]
    F["Freeze final Config<br/>validated config snapshot"]
    G["Emit human or machine-readable diagnostics<br/>config check result"]

    A --> B --> C --> D --> E --> F --> G
```

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tools.

The canonical schema, stable `kind` values, and shared conventions are documented here:

- [Machine output schema (JSON & NDJSON)](../../../dev/machine-output.md)
- [Machine formats](../../../dev/machine-formats.md)

{% include-markdown "\_snippets/output-contract.md" %}

Machine-readable config snapshots emit normalized canonical qualified file type identifiers after
configuration freeze.

Notes:

- `config check` emits diagnostics for both TOML schema validation and configuration
  loading/validation, including missing-section INFO diagnostics from the TOML layer, but not
  pipeline processing diagnostics.
- Validation follows staged config-loading/preflight validation: per-source TOML validation first
  (TOML-source diagnostics), then layered config merge (merged-config diagnostics), then final
  config validation including runtime-applicability checks. The effective validity decision is
  evaluated across these staged validation logs collectively. Identifier normalization and runtime
  applicability evaluation participate in this staged validation flow.

Example (`[config].strict_config_checking = true` resolved from TOML, with no CLI override):

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "config_check": {
    "ok": false,
    "strict_config_checking": true,
    "diagnostic_counts": { "info": 0, "warning": 1, "error": 0 },
    "config_files": ["topmark.toml"]
  }
}
```

### JSON schema

A single JSON document is emitted:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "config_check": {
    "ok": true,
    "strict_config_checking": false,
    "diagnostic_counts": { "info": 0, "warning": 0, "error": 0 },
    "config_files": ["..."]
  }
}
```

### NDJSON schema

NDJSON is a stream where each line is a JSON object. Every record includes `kind` and `meta`.

Stream:

1. kind="config" (effective config snapshot)
1. kind="config_diagnostics" (counts-only)
1. kind="config_check" (summary: ok/strict/counts/config_files)
1. zero or more kind="diagnostic" records (each with domain="config")

Example:

```jsonc
{"kind":"config","meta":{...},"config":{...}}
{"kind":"config_diagnostics","meta":{...},"config_diagnostics":{"diagnostic_counts":{"info":0,"warning":0,"error":0}}}
{"kind":"config_check","meta":{...},"config_check":{"ok":true,"strict_config_checking":false,"diagnostic_counts":{...},"config_files":[...]}}
{"kind":"diagnostic","meta":{...},"diagnostic":{"domain":"config","level":"warning","message":"..."}}
```

______________________________________________________________________

## Configuration semantics

`config check` reflects the same stable configuration contract used by:

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

## Related commands

- [`topmark config dump`](./dump.md) — show the effective frozen configuration, including normalized
  canonical file type identifiers.
- [`topmark config defaults`](./defaults.md) — show the *built-in default TopMark TOML document*.
- [`topmark config init`](./init.md) — print the bundled example TopMark TOML resource.

An overview of all CLI commands is available in [CLI overview](../../cli.md).

______________________________________________________________________

## Troubleshooting

- **Unexpected file type filter behavior**: prefer qualified identifiers such as `topmark:python`
  when local identifiers may be ambiguous.
- **Unexpected policy application**: inspect normalized identifiers using
  [`topmark config dump`](./dump.md).
- **Unexpected validation failures**: use `-vv` or machine-readable output to inspect staged
  validation diagnostics.
