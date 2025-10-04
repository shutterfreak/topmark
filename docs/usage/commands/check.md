<!--
topmark:header:start

  project      : TopMark
  file         : check.md
  file_relpath : docs/usage/commands/check.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `check` Command Guide

The `check` command verifies the presence and correctness of TopMark headers in targeted files. It does not modify files (dry‑run) but reports which files would need updates. In this mode summaries end with `- previewed`. When run with `--apply`, files are actually modified and summaries end with `- inserted`, `- replaced` or other terminal statuses.dates.

______________________________________________________________________

## Quick start

```bash
# Dry‑run: show which files would get a TopMark header or be updated
topmark check src/

# Apply in place
topmark check --apply src/

# Show unified diffs (human output)
topmark check --diff src/

# Summary‑only view (CI‑friendly)
topmark check --summary src/

# Read targets from stdin (one path per line) and generate unified diff output
git ls-files | topmark check --files-from - --diff
```

______________________________________________________________________

## Key properties

- Dry‑run by default; return code **2** when changes *would* occur.
- Preserves the file’s original **newline style** (LF/CRLF/CR).
- Preserves a leading **UTF‑8 BOM** if present.
- Places headers according to file‑type policy (shebang and PEP 263 in Python; XML
  declaration/DOCTYPE in XML/HTML; no insertion inside Markdown fenced code). Uses the same file
  discovery and filtering as other commands:
- Read lists from STDIN with `--files-from -` (or `--include-from -` / `--exclude-from -`).
- To process a *single* file’s **content** from STDIN, pass `-` as the sole PATH and provide
  `--stdin-filename NAME`.
- Do **not** mix `-` (content mode) with `--files-from -` / `--include-from -` / `--exclude-from -`
  (list mode).
- Idempotent: re‑running on already‑correct files results in **no changes**.

> **How config is resolved**
>
> TopMark merges config from **defaults → user → project chain → `--config` → CLI**.
> Globs are evaluated relative to the **workspace base** (`relative_to`).
> Paths to other files (like `exclude_from`) are resolved relative to the **config file** that declared them.
>
> See: [`Configuration → Discovery & Precedence`](../../configuration/discovery.md).

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

> Run `topmark check -h` for the full list of options and help text.

______________________________________________________________________

## Exit codes

| Code | Meaning                                      |
| ---- | -------------------------------------------- |
| 0    | Nothing to change **or** writes succeeded    |
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

topmark check --include-from inc.txt --exclude-from exc.txt --diff
```

______________________________________________________________________

## Behavior details

- **Placement rules** (processor‑aware):
  - **Pound** (e.g., Python/Shell/Ruby/Makefile): after shebang (and optional encoding line), else
    at top; keep exactly one blank around the block as per policy.
  - **Slash** (C/CPP/TS/etc.): at top with consistent spacing.
  - **XML/HTML**: after XML declaration and DOCTYPE; maintain a single intentional blank; never
    break the declaration.
  - **Markdown**: uses HTML comments for the header; fenced code blocks are ignored for detection.
- **Newline/BOM**: preserved across all paths (insert/replace). Reader normalizes in‑memory; updater
  re‑attaches BOM and keeps line endings.
- **Idempotency**: running `topmark check` again on a file that already has a correct header
  produces no diff and exit code 0 (unless other files would change).

______________________________________________________________________

## Typical workflows

### 1) Add headers to a project

```bash
# Start with a dry‑run to see impact
topmark check src/
# Then apply
topmark check --apply src/
```

### 2) Review a change set

```bash
git ls-files -m -o --exclude-standard | topmark check --files-from - --diff
```

### 3) CI: summarize and fail when changes are needed

```bash
# Print summary only. Exit 2 signals “would change” to fail the job.
topmark check --summary
```

## Pre‑commit integration

TopMark provides two hooks:

- **`topmark-check`** – validates headers and fails if fixes are needed (runs automatically on
  commit).
- **`topmark-apply`** – inserts/updates headers (manual only by default; may modify files).

**Consumer configuration** (in a project using TopMark):

```yaml
# .pre-commit-config.yaml (consumer repo)
repos:
  - repo: https://github.com/shutterfreak/topmark
    rev: v0.6.0  # Or latest version
    hooks:
      - id: topmark-check
      - id: topmark-apply    # manual; invoke explicitly when desired
```

The `topmark-check` hook runs automatically at `pre-commit`. You can also invoke it manually:

```bash
# Validate TopMark headers for all files in the repo
pre-commit run topmark-check --all-files

# Validate specific files
pre-commit run topmark-check -- <path/to/file1> <path/to/file2>
```

The `topmark-apply` hook is **manual** by default (to avoid unintended edits). Run it explicitly
when you want to apply changes:

```bash
# Add or update TopMark headers for all files in the repo
pre-commit run topmark-apply --all-files

# Apply to specific files
pre-commit run topmark-apply -- <path/to/file1> <path/to/file2>
```

______________________________________________________________________

## Troubleshooting

- **No files to process**: Ensure you passed positional paths (unless using stdin). Use `-vv` for
  debug logs.
- **Patterns don’t match**: Remember that include/exclude patterns are **relative to CWD**. `cd`
  into the project root before running.
- **Unexpected placement**: For pound/slash formats, check for leading banners or shebang/encoding
  lines. For XML/HTML, verify declaration/doctype positions.
