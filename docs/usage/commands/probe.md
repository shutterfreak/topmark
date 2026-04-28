<!--
topmark:header:start

  project      : TopMark
  file         : probe.md
  file_relpath : docs/usage/commands/probe.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `probe` Command Guide

**Purpose:** Explain file-type and processor resolution.

The `probe` command explains how TopMark resolves a file to a file type and header processor. It is
**diagnostic-only**: it does not read full file content for header detection, does not compare or
mutate headers, and does not write files.

Instead, it exposes the **resolution decision process**, including:

- the selected file type and processor
- the resolution status and reason
- all scored candidate file types
- match signals (extension, filename, pattern, content probing)

______________________________________________________________________

## Quick start

```bash
# Explain how a file is classified
topmark probe README.md

# Increase detail (selected fields, then candidates)
topmark probe -v README.md
topmark probe -vv README.md

# Multiple files
topmark probe src/

# Machine-readable output
topmark probe --output-format json README.md
topmark probe --output-format ndjson README.md

# Markdown report (document-style)
topmark probe --output-format markdown README.md
```

______________________________________________________________________

## Key properties

- **Read-only**: does not modify files.
- **Resolution-only**: does not perform scanning, comparison, or mutation.
- Uses the same **file discovery and filtering** as other commands.
- Uses the same resolution policy and scoring logic as `check` and `strip`.
- Exposes the same resolution logic used internally by `check` / `strip`.
- Idempotent: repeated runs produce identical output for unchanged inputs.

### STDIN modes

TopMark supports **two different STDIN modes**:

- **List mode**: read newline-delimited paths or patterns from STDIN using:
  - `--files-from -`
  - `--include-from -`
  - `--exclude-from -`
- **Content mode**: process one file’s *content* from STDIN by passing `-` as the sole PATH and
  providing `--stdin-filename NAME`.

These modes are mutually exclusive: do **not** mix `-` (content mode) with `--files-from -`,
`--include-from -`, or `--exclude-from -` (list mode).

{% include-markdown "\_snippets/config-resolution.md" %}

______________________________________________________________________

## Filtering

TopMark determines which files to process using a combination of path-based filters and file-type
filters.

### File type filters

- `--include-file-types / -t` Restrict processing to the given file type identifiers.
- `--exclude-file-types / -T` Exclude the given file type identifiers.

Exclude rules take precedence over include rules.

### Path-based filters

- `--include`, `--exclude` Include or exclude glob patterns.
- `--include-from`, `--exclude-from` Load patterns from files (one per line).
- `--files-from` Provide an explicit list of files to process.

Notes:

- Path-based filters are evaluated **before** file-type filters.
- Exclude rules win over include rules when both match a path.
- File-type filters are applied after path-based include/exclude filtering.

______________________________________________________________________

## Output formats

### TEXT output

TEXT output provides a concise summary by default, with increasing detail via verbosity:

- default: one-line summary per file
- `-v`: include selected file type and processor
- `-vv`: include candidate list and match signals

### Markdown output

Use `--output-format markdown` to render a document-oriented report.

Notes:

- Markdown output **ignores verbosity and quiet mode**
- Always includes selected details and candidate tables
- Suitable for documentation or review artifacts

### Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tooling.

- **JSON**: a single document containing `meta`, `config`, `config_diagnostics`, and `probes`
- **NDJSON**: one record per line; includes `kind="probe"` records for each file

For the canonical schema, see:

- [Machine output schema (JSON & NDJSON)](../../dev/machine-output.md)
- [Machine formats](../../dev/machine-formats.md)

______________________________________________________________________

## Machine output schema

### JSON

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "probes": [
    {
      "path": "README.md",
      "status": "resolved",
      "reason": "selected_highest_score",
      "selected_file_type": { ... },
      "selected_processor": { ... },
      "candidates": [ ... ]
    }
  ]
}
```

### NDJSON

```jsonc
{"kind":"config",...}
{"kind":"config_diagnostics",...}
{"kind":"diagnostic",...}
{"kind":"probe","meta":{...},"probe":{...}}
```

______________________________________________________________________

## Global options

Output format, TEXT verbosity, quiet mode, and color output are configured with
[global options](../global-options.md).

### Verbosity & logging

- `-v`, `--verbose` increases TEXT output detail
- `-q`, `--quiet` suppresses TEXT output (no effect on Markdown or machine formats)

Notes:

- Markdown output ignores verbosity
- Machine output is unaffected by verbosity and quiet mode

______________________________________________________________________

## Options (subset)

| Option                        | Description                                                            |
| ----------------------------- | ---------------------------------------------------------------------- |
| `-q`, `--quiet`               | Suppress TEXT output while preserving exit status.                     |
| `--files-from`                | Read newline-delimited paths from file (use '-' for STDIN).            |
| `-` (PATH)                    | Read a single file’s content from STDIN (requires `--stdin-filename`). |
| `--include`                   | Add paths by glob.                                                     |
| `--include-from`              | File of patterns to include.                                           |
| `--exclude`                   | Exclude paths by glob.                                                 |
| `--exclude-from`              | File of patterns to exclude.                                           |
| `--include-file-types` / `-t` | Restrict to specific file type identifiers.                            |
| `--exclude-file-types` / `-T` | Exclude specific file type identifiers.                                |
| `--stdin-filename`            | Assumed filename when PATH is '-' (content from STDIN).                |

> Run `topmark probe -h` for the full list of options.

______________________________________________________________________

## Exit codes

| Code | Meaning                                   |
| ---- | ----------------------------------------- |
| 0    | All files resolved successfully           |
| 69   | One or more files could not be resolved   |
| 70   | Internal probe or pipeline error occurred |

______________________________________________________________________

## Typical workflows

### 1) Debug file classification

```bash
topmark probe README.md
```

### 2) Investigate ambiguous matches

```bash
topmark probe -vv README.md
```

### 3) Integrate with tooling

```bash
topmark probe --output-format json README.md
```

______________________________________________________________________

## Related commands

- [`topmark check`](./check.md) — verify and update headers.
- [`topmark strip`](./strip.md) — remove detected TopMark headers.
- [`topmark config check`](./config/check.md) — validate configuration.

______________________________________________________________________

## Troubleshooting

- **Unsupported file**: ensure file type patterns or extensions are configured correctly.
- **Unexpected selection**: use `-vv` to inspect candidate scores and match signals.
- **No processor**: check that a processor is registered for the selected file type.
