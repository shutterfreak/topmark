<!--
topmark:header:start

  project      : TopMark
  file         : probe.md
  file_relpath : docs/usage/commands/probe.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# `topmark probe`

**Purpose:** Explain file-type and processor resolution.

The `probe` command explains how TopMark resolves a file to a file type and header processor. It is
diagnostic-only: it does not read full file content for header detection, does not compare or mutate
headers, and does not write files.

Instead, it exposes the resolution decision process, including:

- the selected file type and processor
- canonical resolved file type identities and qualified keys
- the runtime-resolution status and reason
- all scored candidate file types
- match signals (extension, filename, pattern, content probing)
- explicit inputs filtered during discovery before file-type resolution

{% include-markdown "\_snippets/terminology.md" %}

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

## Input applicability

`probe` is read-only and diagnostic-only. It shares input discovery, filtering, configuration, and
file-type resolution controls with [`check`](check.md) and [`strip`](strip.md), but it rejects
options that belong to file mutation, patch planning, reporting summaries, diffs, or
generated-header rendering.

Use [`check`](check.md) or [`strip`](strip.md) for header comparison, patch previews, reports, or
mutation.

### STDIN modes

`probe` supports both list STDIN mode (`--files-from -`, `--include-from -`, or `--exclude-from -`)
and content STDIN mode (`-` plus `--stdin-filename NAME`). These modes are mutually exclusive.

See [shared input modes](../shared-options.md#shared-input-modes) for the full STDIN contract,
including why TopMark does not provide a `--stdin` option flag.

______________________________________________________________________

## Configuration and validation

`probe` supports `--strict` / `--no-strict` to override the effective `strict` value for the run.

Before any file processing begins, TopMark performs whole-source TOML schema validation during
configuration loading. TOML-source diagnostics (including missing-section INFO diagnostics) are
evaluated together with merged-config and runtime applicability diagnostics during staged
configuration-loading validation for the run.

{% include-markdown "\_snippets/config-strictness.md" %}

TopMark resolves configuration from defaults, user config, the project chain, explicit `--config`
files, and CLI overrides before staged validation produces the effective runtime configuration. See
[Configuration discovery, precedence, and policy](../../configuration/discovery.md) for the full
configuration-loading and validation contract.

______________________________________________________________________

## Filtering and file discovery

TopMark determines which files to process using a combination of path-based filters and file-type
filters.

Path arguments, include/exclude patterns, `--files-from`, and file-type filters follow the shared
TopMark filtering pipeline. Positional paths and relative patterns are resolved from the current
working directory; path-based filters run before file-type filters, and exclude rules take
precedence. See [Filtering](../filtering.md#path-based-filtering) for the full path discovery
contract.

Unlike processing commands, `probe` may report explicitly requested files as filtered diagnostic
results instead of silently omitting them.

Explicit directories that successfully expand to selected files are treated as discovery inputs and
are not reported as separate filtered probe results. Explicit missing paths are reported as missing
input errors rather than filtered probe results.

### File type filters

- `--include-file-types / -t` Restrict processing to the given file type identifiers. May be
  repeated and/or provided as a comma-separated list.
- `--exclude-file-types / -T` Exclude the given file type identifiers. May be repeated and/or
  provided as a comma-separated list.

File type identifiers are normalized to canonical qualified file type identities before filtering,
diagnostics, policy evaluation, and registry resolution.

{% include-markdown "\_snippets/file-type-identifiers.md" %}

See [file-type filtering](../filtering.md#file-type-filtering) for the full identifier contract.

Examples:

```bash
topmark probe --include-file-types python README.md
topmark probe --include-file-types topmark:markdown README.md
topmark probe --exclude-file-types topmark:python src/
```

### Path-based filters

- `--include`, `--exclude` Include or exclude glob patterns.
- `--include-from`, `--exclude-from` Load patterns from files (one per line).
- `--files-from` Provide an explicit list of files to process.

See [Filtering](../filtering.md#path-based-filtering) for CWD-resolution rules, missing vs unmatched
input behavior, include/exclude precedence, and STDIN interactions.

### Example

```bash
# Probe only Python-like files selected through include/exclude filters
printf "*.py\n" > inc.txt
printf "tests/*\n# ignored\n" > exc.txt

topmark probe --include-from inc.txt --exclude-from exc.txt -vv
```

______________________________________________________________________

## Behavior details

- Read-only: does not modify files.
- Resolution-only: does not perform header scanning, comparison, mutation planning, or writes.
- Shared discovery: uses the same discovery and filtering pipeline as [`check`](check.md) and
  [`strip`](strip.md), while preserving filtered explicit inputs as diagnostic probe results.
- Shared runtime resolution: uses the same normalization, scoring, and runtime resolution logic as
  [`check`](check.md) and [`strip`](strip.md).
- Candidate visibility: exposes selected file type, processor, candidate scores, match signals,
  runtime-resolution status, and runtime-resolution reason.
- Idempotency: repeated runs produce identical output for unchanged inputs.

______________________________________________________________________

## Output behavior

### TEXT rendering

TEXT rendering provides a concise summary by default, with increasing detail via verbosity:

- default: one-line summary per file
- `-v`: include selected file type and processor
- `-vv`: include candidate lists, match signals, and resolution details

### Markdown output

Use `--output-format markdown` to render a document-oriented report.

Notes:

- Markdown output is document-oriented and ignores TEXT-oriented verbosity and quiet controls.
- Always includes selected details and candidate tables
- Suitable for documentation or review artifacts

### Machine-readable output (JSON, NDJSON)

Machine-readable formats are intended for automation and tooling integration.

- JSON: a single machine-readable JSON document containing `meta`, `config`, `config_diagnostics`,
  and `probes`
- NDJSON: one machine-readable NDJSON record per line; includes `kind="probe"` records for each
  probe result

For the canonical schema, see:

- [Machine-readable output](../machine-output.md)
- [Machine-readable format conventions](../../dev/machine-formats.md)

Probe machine-readable output emits resolved file type identities using canonical qualified identity
strings when available.

### Shared output controls

Output format, TEXT verbosity, quiet mode, color output, and shared exit-code behavior are
documented in [shared options](../shared-options.md) and [exit codes](../exit-codes.md).

TEXT verbosity is separate from internal logging:

- `-v`, `--verbose` increases TEXT output detail for probe diagnostics.
- `-q`, `--quiet` suppresses TEXT rendering while preserving the command's exit status.
- Markdown output is document-oriented and ignores TEXT-oriented verbosity and quiet controls.
- Machine-readable JSON and NDJSON output are unaffected by TEXT-oriented verbosity and quiet
  controls.

Notes:

- Primary/headline hint selection, where rendered in human-readable output, is presentation-level
  guidance and is not part of the stable CLI contract; rely on exit codes and machine-readable
  output for automation.
- `probe` is diagnostic-only and never renders diffs or patch previews.

______________________________________________________________________

## Machine-readable output

### JSON

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* RuntimeConfigPayload */ },
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

Only explicit inputs that actually fail selection are represented as filtered probe payloads.

Directories that successfully expand to selected files are not emitted as additional filtered probe
results. Explicit missing paths are represented as missing-input probe results rather than filtered
probe results.

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

- `excluded_by_path_filter` - excluded by path-based include/exclude rules
- `excluded_by_file_type_filter` - excluded by file-type include/exclude rules after identifier
  normalization to canonical qualified file type identities
- `excluded_by_discovery_filter` - excluded before probing but exact category not identified

### NDJSON

```jsonc
{"kind":"config",...}
{"kind":"config_diagnostics",...}
{"kind":"diagnostic",...}
{"kind":"probe","meta":{...},"probe":{...}}  <!-- one per probe result -->
```

Canonical file type identities in machine-readable output use normalized qualified-key identities
such as `topmark:python`.

______________________________________________________________________

## Command-specific options

| Option                                               | Description                                                             |
| ---------------------------------------------------- | ----------------------------------------------------------------------- |
| `-q`, `--quiet`                                      | Suppress TEXT rendering while preserving exit status.                   |
| `--files-from`                                       | Read newline-delimited paths from file (use '-' for STDIN).             |
| `-` (PATH)                                           | Read one virtual file from STDIN content (requires `--stdin-filename`). |
| `--include`                                          | Add paths by glob.                                                      |
| `--include-from`                                     | File of patterns to include.                                            |
| `--exclude`                                          | Exclude paths by glob.                                                  |
| `--exclude-from`                                     | File of patterns to exclude.                                            |
| `--include-file-types` / `-t`                        | Restrict to local or qualified file type identifiers.                   |
| `--exclude-file-types` / `-T`                        | Exclude local or qualified file type identifiers.                       |
| `--stdin-filename`                                   | Assumed filename when PATH is '-' (content from STDIN).                 |
| `--allow-content-probe` / `--no-allow-content-probe` | Shared runtime policy override for file-type detection.                 |

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

- `UNSUPPORTED_FILE_TYPE (69)` indicates runtime-resolution failure (e.g., unsupported file type or
  filtered input), not a crash.
- Explicit missing literal paths are treated as hard input errors and produce `FILE_NOT_FOUND (66)`.
- Missing explicit inputs take precedence over runtime-resolution outcomes (`69`).
- Unmatched glob patterns are reported as filtered probe results (e.g.,
  `filtered: excluded_by_discovery_filter`) and result in `UNSUPPORTED_FILE_TYPE (69)`.
- Ambiguous local file type identifiers may also contribute to runtime-resolution outcomes unless
  callers use canonical qualified identifiers such as `topmark:python`.

See [`Exit codes`](../exit-codes.md) for the complete CLI-wide exit-code contract.

______________________________________________________________________

## Typical workflows

### 1) Inspect file classification

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

- [`topmark check`](./check.md) - verify and update headers.
- [`topmark strip`](./strip.md) - remove detected TopMark headers.
- [`topmark config check`](./config/check.md) - validate the effective runtime configuration and
  report diagnostics.
- [`topmark config dump`](./config/dump.md) - inspect the effective runtime configuration, including
  normalized file type identifiers.

______________________________________________________________________

## Related docs

- [Command overview](../cli.md)
- [Configuration](../configuration.md)
- [Filtering](../filtering.md)
- [Policies](../policies.md)
- [Shared options](../shared-options.md)
- [Exit codes](../exit-codes.md)
- [Registry model](../../dev/registry-model.md)
- [Resolution model](../../dev/resolution.md)
- [Machine-readable output](../machine-output.md)
- [Machine-readable format conventions](../../dev/machine-formats.md)
- [Terminology and Canonical Vocabulary](../../terminology.md)

______________________________________________________________________

## Troubleshooting

- **Unsupported file**: ensure file type patterns, bindings, or extensions are configured correctly.
- **Unexpected resolution result**: use `-vv` to inspect candidate scores and match signals.
- **File type filter does not match**: prefer qualified identifiers such as `topmark:python` when
  local identifiers may be ambiguous.
- **No processor**: check that a processor binding exists for the selected file type.
- **Filtered input**: the path was excluded during discovery or filtering evaluation (e.g.,
  `--exclude`). The probe output will show one of:
  - `filtered: excluded_by_path_filter`
  - `filtered: excluded_by_file_type_filter`
  - `filtered: excluded_by_discovery_filter`
- **`--stdin` is rejected**: Use `-` as the PATH sentinel together with `--stdin-filename NAME` when
  reading one virtual file from STDIN content.
- **Missing file error**: A literal path such as `fubar.py` is treated as an explicit input and
  fails with `FILE_NOT_FOUND (66)` when it does not exist. Missing explicit inputs are reported as
  missing-input probe results rather than filtered probe results.
