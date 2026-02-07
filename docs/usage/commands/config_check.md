<!--
topmark:header:start

  project      : TopMark
  file         : config_check.md
  file_relpath : docs/usage/commands/config_check.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `config check` Command Guide

The `config check` subcommand (part of the TopMark [`config` Command Family](config.md))
validates the **effective merged configuration** and reports any configuration diagnostics.

Unlike `check` / `strip`, this command is **file-agnostic**: it does not resolve or process files.
It is intended for CI validation and debugging configuration precedence issues.

- `default`: human-readable validation result (optionally verbose).
- `markdown`: Markdown report suitable for pasting into tickets or CI logs.
- `json` / `ndjson`: machine-readable envelopes/records aligned with TopMark’s machine format
  conventions.

______________________________________________________________________

## Quick start

```bash
# Validate merged config (default human output)
topmark config check

# Fail if warnings are present (in addition to errors)
topmark config check --strict

# Machine-readable JSON (single document)
topmark config check --output-format json

# Machine-readable NDJSON (record stream)
topmark config check --output-format ndjson
```

______________________________________________________________________

## Key properties

- **Validates merged config**: loads defaults → discovered config → `--config` files → CLI overrides,
  then freezes/validates the final configuration.
- **File-agnostic**: positional PATHS are ignored (a note is printed). `-` (content-on-STDIN) is
  ignored.
- **CI-friendly**: exit code is non-zero when validation fails.
- **Strict mode**: `--strict` causes warnings to fail the command (errors always fail).

{% include-markdown "\_snippets/config-resolution.md" %}

______________________________________________________________________

## When to use

- In CI to ensure config changes do not introduce warnings/errors.
- When debugging configuration discovery/precedence (e.g. *why is this policy enabled?*).
- When integrating TopMark configuration into external tooling that needs a validated snapshot.

______________________________________________________________________

## Options (subset)

| Option                 | Description                                              |
| ---------------------- | -------------------------------------------------------- |
| `--strict/--no-strict` | Fail on warnings as well as errors.                      |
| `--output-format`      | Output format (`default`, `markdown`, `json`, `ndjson`). |
| `--config`             | Merge an explicit TOML config file (can be repeated).    |
| `--no-config`          | Do not discover local project/user config.               |

> Run `topmark config check -h` for the full list of options and help text.

______________________________________________________________________

## Exit codes

- **0**: configuration is valid (no failing diagnostics).
- **non-zero**: configuration validation failed:
  - errors are present, or
  - `--strict` is enabled and warnings are present.

______________________________________________________________________

## Output formats

### Default output (human)

- If there are no diagnostics: prints a short success message.
- If diagnostics exist: prints counts of errors/warnings/info. With higher verbosity, it prints each
  diagnostic line.
- With higher verbosity, it also prints the list of config files that were processed.
- With very high verbosity, it can print the merged config as TOML (wrapped with BEGIN/END markers).

### Markdown output

`--output-format markdown` emits a report containing:

- overall status (`ok` / `failed`)
- whether strict mode was enabled
- diagnostic counts
- (optionally) full diagnostic list and processed config files, depending on verbosity

This format is designed for CI logs and copy/paste into issues.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tools.

The canonical schema, stable `kind` values, and shared conventions are documented here:

- [Machine output schema (JSON & NDJSON)](../../dev/machine-output.md)
- [Machine formats](../../dev/machine-formats.md)

Notes:

- `config check` is **file-agnostic**, so it does not emit per-file `result` records.
- `config check` emits **diagnostics only for configuration loading/validation**, not pipeline
  processing diagnostics.

### JSON schema

A single JSON document is emitted:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "config_check": {
    "ok": true,
    "strict": false,
    "diagnostic_counts": { "info": 0, "warning": 0, "error": 0 },
    "config_files": ["..."]
  }
}
```

### NDJSON schema

NDJSON is a stream where each line is a JSON object. Every record includes `kind` and `meta`.

Stream:

1. `kind="config"` (effective config snapshot)
1. `kind="config_diagnostics"` (counts-only)
1. `kind="config_check"` (summary: ok/strict/counts/config_files)
   4+) zero or more `kind="diagnostic"` records (each with `domain="config"`)

Example:

```jsonc
{"kind":"config","meta":{...},"config":{...}}
{"kind":"config_diagnostics","meta":{...},"config_diagnostics":{"diagnostic_counts":{"info":0,"warning":0,"error":0}}}
{"kind":"config_check","meta":{...},"config_check":{"ok":true,"strict":false,"diagnostic_counts":{...},"config_files":[...]}}
{"kind":"diagnostic","meta":{...},"diagnostic":{"domain":"config","level":"warning","message":"..."}}
```

______________________________________________________________________

## Related commands

- [`topmark config dump`](config_dump.md) — show the *effective merged* configuration as TOML.
- [`topmark config defaults`](config_defaults.md) — show TopMark’s *built-in defaults* as TOML.
- [`topmark config init`](config_init.md) — print a *starter* config scaffold template.
