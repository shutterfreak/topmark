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
- explicit inputs filtered during discovery before file-type probing

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
- Uses the same **file discovery and filtering** as other commands, and reports explicit inputs that
  are filtered before probing.
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
- Explicit missing literal paths (for example `fubar.py`) are reported as `FILE_NOT_FOUND (66)`.
- Unmatched glob patterns (for example `missing/**/*.py`) are reported as filtered probe results and
  contribute to `UNSUPPORTED_FILE_TYPE (69)`.

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
- **NDJSON**: one record per line; includes `kind="probe"` records for each probe result

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

Filtered explicit inputs are also represented as probe payloads with:

```jsonc
{
  "path": "__pycache__/example.cpython-312.pyc",
  "status": "filtered",
  "reason": "excluded_by_path_filter",
  "selected_file_type": null,
  "selected_processor": null,
  "candidates": []
}
```

Filtered probe results may use one of the following reasons:

- `excluded_by_path_filter` — excluded by path-based include/exclude rules
- `excluded_by_file_type_filter` — excluded by file-type include/exclude rules
- `excluded_by_discovery_filter` — excluded before probing but exact category not identified

### NDJSON

```jsonc
{"kind":"config",...}
{"kind":"config_diagnostics",...}
{"kind":"diagnostic",...}
{"kind":"probe","meta":{...},"probe":{...}}  <!-- one per probe result -->
```

______________________________________________________________________

## Global options

Output format, TEXT verbosity, quiet mode, color output, and shared exit-code behavior are
documented in [global options](../global-options.md) and [exit codes](../exit-codes.md).

### Verbosity & logging

- `-v`, `--verbose` increases TEXT output detail
- `-q`, `--quiet` suppresses TEXT output (no effect on Markdown or machine formats; does not affect
  exit codes)

Notes:

- Markdown output ignores verbosity
- Machine output is unaffected by verbosity and quiet mode
- Primary/headline hint selection, where rendered in human output, is presentation-level guidance
  and is not part of the stable CLI contract; rely on exit codes and machine output for automation.

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

`topmark probe` exits with `SUCCESS (0)` when all inputs are fully resolved.

Common `probe` exit codes:

| Scenario                                      | Exit code                    |
| --------------------------------------------- | ---------------------------- |
| All inputs resolved                           | `SUCCESS (0)`                |
| Any input unresolved / unsupported / filtered | `UNSUPPORTED_FILE_TYPE (69)` |
| Missing explicit input path                   | `FILE_NOT_FOUND (66)`        |
| Permission failure                            | `PERMISSION_DENIED (77)`     |
| Configuration error                           | `CONFIG_ERROR (78)`          |
| Invalid CLI usage                             | `USAGE_ERROR (64)`           |

Notes:

- `UNSUPPORTED_FILE_TYPE (69)` indicates semantic resolution failure (e.g., unsupported file type or
  filtered input), not a crash.
- Explicit missing literal paths are treated as hard input errors and produce `FILE_NOT_FOUND (66)`.
- Missing explicit inputs take precedence over semantic probe outcomes (`69`).
- Unmatched glob patterns are reported as filtered probe results (e.g.,
  `filtered: excluded_by_discovery_filter`) and result in `UNSUPPORTED_FILE_TYPE (69)`.

See [`Exit codes`](../exit-codes.md) for the complete CLI-wide exit-code contract.

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
- **Filtered input**: the path was excluded by discovery filters (e.g., `--exclude`). The probe
  output will show one of:
  - `filtered: excluded_by_path_filter`
  - `filtered: excluded_by_file_type_filter`
  - `filtered: excluded_by_discovery_filter`
- **Missing file error**: A literal path such as `fubar.py` is treated as an explicit input and
  fails with `FILE_NOT_FOUND (66)` when it does not exist.
