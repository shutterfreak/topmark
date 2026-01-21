<!--
topmark:header:start

  project      : TopMark
  file         : strip.md
  file_relpath : docs/usage/commands/strip.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `strip` Command Guide

The `strip` command removes the entire TopMark header block from targeted files. It is
**dry‑run by default** (summaries end with `- previewed`) and becomes destructive only with
`--apply` (summaries end with `- removed`) when run with `--apply`.

______________________________________________________________________

## Quick start

```bash
# Dry‑run: show which files would have their TopMark header removed
topmark strip src/

# Apply in place
topmark strip --apply src/

# Show unified diffs (human output)
topmark strip --diff src/

# Summary‑only view (CI‑friendly)
topmark strip --summary src/

# Read targets from stdin (one path per line) and generate unified diff output
git ls-files | topmark strip --files-from - --diff
```

______________________________________________________________________

## Key properties

- Dry‑run by default; return code **2** when changes *would* occur.
- Preserves the file’s original **newline style** (LF/CRLF/CR).
- Preserves a leading **UTF‑8 BOM** if present.
- Honors XML/HTML placement rules and preserves the XML declaration (`<?xml …?>`).
- Respects Markdown fenced code blocks: header‑like snippets inside fences are ignored. Uses the
  same file discovery and filtering as other commands:
- Read lists from STDIN with `--files-from -` (or `--include-from -` / `--exclude-from -`).
- To process a *single* file’s **content** from STDIN, pass `-` as the sole PATH and provide
  `--stdin-filename NAME`.
- Do **not** mix `-` (content mode) with `--files-from -` / `--include-from -` / `--exclude-from -`
  (list mode).
- Idempotent: re‑running after headers are removed results in **no changes**.

{% include-markdown "\_snippets/config-resolution.md" %}

______________________________________________________________________

## Filtering

TopMark determines which files to process using a combination of
path-based filters and file-type filters.

### File type filters

- `--include-file-types / -t`
  Restrict processing to the given file type identifiers.
  May be repeated and/or provided as a comma-separated list.

- `--exclude-file-types / -T`
  Exclude the given file type identifiers.
  May be repeated and/or provided as a comma-separated list.

Exclude rules take precedence over include rules.

### Path-based filters

- `--include`, `--exclude`
  Include or exclude glob patterns.

- `--include-from`, `--exclude-from`
  Load patterns from files (one per line).

- `--files-from`
  Provide an explicit list of files to process.

Notes:

- Path-based filters are evaluated **before** file-type filters.
- Exclude rules win over include rules when both match a path.
- File-type filters are applied after path-based include/exclude filtering.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tooling:

- **JSON**: single JSON document with `meta`, `config`, `config_diagnostics` and
  either `results` (detail mode) or `summary` (summary mode).
- **NDJSON**: one JSON object per line (or one summary line per outcome with `--summary`).

For the canonical JSON/NDJSON schema, see
[Machine output schema (JSON & NDJSON)](../../dev/machine-output.md).

Notes:

- Diffs (`--diff`) are **human-only** and are not included in JSON/NDJSON.
- Summary mode aggregates outcomes and suppresses per-file guidance lines.

### JSON schema (detail mode)

When `--summary` is **not** set, `topmark strip` emits a single JSON object:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "results": [
    {
      "path": "README.md",
      "file_type": "markdown",
      "steps": [
        "ResolverStep",
        "SnifferStep",
        "ReaderStep",
        "ScannerStep",
        "StripperStep",
        "ComparerStep"
      ],
      "step_axes": {
        "ResolverStep": ["resolve"],
        "SnifferStep": ["fs"],
        "ReaderStep": ["content"],
        "ScannerStep": ["header"],
        "StripperStep": ["strip"],
        "ComparerStep": ["comparison"]
      },
      "status": {
        "resolve": { "axis": "resolve", "name": "RESOLVED", "label": "resolved" },
        "fs":      { "axis": "fs",      "name": "OK",       "label": "ok" },
        "content": { "axis": "content", "name": "OK",       "label": "ok" },
        "header":  { "axis": "header",  "name": "DETECTED", "label": "header detected" },
        "generation": { "axis": "generation", "name": "PENDING", "label": "header field generation pending" },
        "render":     { "axis": "render",     "name": "PENDING", "label": "header field rendering pending" },
        "strip":      { "axis": "strip",      "name": "READY",   "label": "ready for stripping" },
        "comparison": { "axis": "comparison", "name": "CHANGED", "label": "changes found" }
        /* plan/patch/write omitted for brevity */
      },
      "views": {
        "image_lines": 382,
        "header_range": [0, 10],
        "header_fields": {
          "project": "TopMark",
          "file": "README.md",
          "file_relpath": "README.md",
          "license": "MIT",
          "copyright": "(c) 2025 Olivier Biot"
        },
        "build_selected": null,
        "render_line_count": 0,
        "updated_has_lines": true,
        "diff_present": false
      },
      "diagnostics": [],
      "diagnostic_counts": { "info": 0, "warning": 0, "error": 0 },
      "pre_insert_check": {
        "capability": "UNEVALUATED",
        "reason": null,
        "origin": null
      },
      "outcome": {
        "would_change": true,
        "can_change": true,
        "permitted_by_policy": null,
        "check": {
          "would_add_or_update": true,
          "effective_would_add_or_update": true
        },
        "strip": {
          "would_strip": true,
          "effective_would_strip": true
        }
      }
    }
  ]
}
```

As with `check`, `status` is the axis → `{axis, name, label}` map,
and `steps`/`step_axes` expose the pipeline trace for the `strip` intent.

In summary mode (`--summary`), `results` is omitted and replaced by a
`summary` object:

```jsonc
"summary": {
  "would strip": {
    "count": 30,
    "label": "[08.1] header detected, ready for stripping"
  },
  "skipped": {
    "count": 1,
    "label": "[01] known file type, headers not supported"
  }
}
```

> [!NOTE] **Config diagnostics**
>
> The `config_diagnostics` block only appears in machine-readable output for
> commands that actually *run* a pipeline (`check`, `strip`). It summarises any
> issues discovered while loading and merging configuration (e.g. invalid keys,
> deprecated options, or conflicting settings).
>
> Pure config commands (`topmark config ...`) emit only the `config` snapshot in
> JSON/NDJSON and omit `config_diagnostics`.

## Verbosity & logging

Program-output verbosity is separate from internal logging:

- `-v`, `--verbose` increases **program output** detail (e.g., renders per‑line diagnostics).
- `-q`, `--quiet` suppresses most **program output**.

Notes:

- **Summary mode** aggregates outcomes and suppresses per-file guidance lines.
- **Per‑line diagnostics** are shown when the effective program verbosity ≥ 1.
- **Diffs** (`--diff`) are always human‑only and never included in JSON/NDJSON.

## Options (subset)

| Option               | Description                                                       |
| -------------------- | ----------------------------------------------------------------- |
| `--apply`            | Write changes to files (off by default).                          |
| `--diff`             | Show unified diffs (human output only).                           |
| `--summary`          | Show outcome counts instead of per‑file details.                  |
| `--files-from`       | Read newline‑delimited paths from file (use '-' for STDIN).       |
| `--include`          | Add paths by glob (can be used multiple times).                   |
| `--include-from`     | File of patterns to include (one per line, `#` comments allowed). |
| `--exclude`          | Exclude paths by glob (can be used multiple times).               |
| `--exclude-from`     | File of patterns to exclude.                                      |
| `--file-type`        | Restrict to specific TopMark file type identifiers.               |
| `--skip-compliant`   | Don't report compliant files.                                     |
| `--skip-unsupported` | Don't report unsupported files.                                   |
| `--stdin-filename`   | Assumed filename when PATH is '-' (content from STDIN).           |

> Run `topmark strip -h` for the full list of options and help text.

______________________________________________________________________

## Exit codes

| Code | Meaning                                      |
| ---- | -------------------------------------------- |
| 0    | Nothing to strip **or** writes succeeded     |
| 1    | Errors occurred while writing with `--apply` |
| 2    | Dry‑run detected that changes would occur    |

______________________________________________________________________

## File discovery & patterns

- Positional arguments are resolved **relative to the current working directory** (CWD),
  Black‑style.

- Patterns in `--include`, `--exclude`, and the files passed to `--include-from` / `--exclude-from`
  are also resolved **relative to CWD**. Absolute patterns are not supported.

- Use `--files-from -` (or `--include-from -` / `--exclude-from -`) to read lists from STDIN.

- Use `-` (with `--stdin-filename`) to read a single file’s content from STDIN.

- Use `--skip-compliant` and `--skip-unsupported` to tailor output and speed in CI.

- Diffs (`--diff`) are only shown in human mode; machine formats never include diffs.

### Example

```bash
# Use include/exclude files with relative patterns
printf "*.py\n" > inc.txt
printf "tests/*\n# ignored\n" > exc.txt

topmark strip --include-from inc.txt --exclude-from exc.txt --diff
```

______________________________________________________________________

## Behavior details

- **Removal policy**: If a valid TopMark header is detected (policy‑aware), remove the whole block.
  A permissive fallback accepts legacy single‑line‑wrapped markers (e.g., HTML/XML `<!-- ... -->`).
- **Newline/BOM**: preserved across removal. Reader normalizes in‑memory; updater re‑attaches BOM
  and keeps line endings.
- **XML/HTML**: keeps the XML declaration as the first logical line; maintains a single intentional
  blank as needed.
- **Markdown**: ignores code fences for detection; header‑like text inside fences is not removed.
- **Idempotency**: once stripped, subsequent runs are no‑ops.

______________________________________________________________________

## Typical workflows

### 1) Remove headers from a project

```bash
# Start with a dry‑run to see impact
topmark strip src/
# Then apply
topmark strip --apply src/
```

### 2) Review a change set

```bash
git ls-files -m -o --exclude-standard | topmark strip --files-from - --diff
```

### 3) CI: summarize and fail when removals are needed

```bash
# Print summary only. Exit 2 signals “would change” to fail the job.
topmark strip --summary
```

## Pre‑commit integration

There is currently **no** `topmark-strip` pre-commit hook. Use the CLI directly when you need to
remove headers:

```bash
topmark strip --apply <paths>
```

______________________________________________________________________

## Troubleshooting

- **No files to process**: Ensure you passed positional paths or `--files-from -`. Use `-vv` for
  debug logs.
- **Patterns don’t match**: Remember that include/exclude patterns are **relative to CWD**. `cd`
  into the project root before running.
- **“Header not detected”**: Header‑like text inside code fences or strings is intentionally
  ignored; `strip` won’t remove it.
