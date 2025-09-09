<!--
topmark:header:start

  file         : strip.md
  file_relpath : docs/usage/commands/strip.md
  project      : TopMark
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `strip` Command Guide

The `topmark strip` subcommand removes the entire TopMark header block from targeted files. It is
**dry‑run by default** and becomes destructive only with `--apply`.

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

______________________________________________________________________

## Machine-readable output

Use `--format json` or `--format ndjson` to emit output suitable for tooling:

- **JSON**: pretty-printed array (or summary object when `--summary`).
- **NDJSON**: one JSON object per line (or one summary line per outcome with `--summary`).

Notes:

- Diffs (`--diff`) are **human-only** and are not included in JSON/NDJSON.
- Summary mode aggregates outcomes and suppresses per-file guidance lines.

## Verbosity & logging

Program-output verbosity is separate from internal logging:

- `-v`, `--verbose` increases **program output** detail (adds per‑line diagnostics in summaries) and also increases the logger level.
- `-q`, `--quiet` suppresses most **program output** and lowers logger noise.

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
