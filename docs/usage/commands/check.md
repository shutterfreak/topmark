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

**Purpose:** Verify TopMark headers and optionally insert or update them with `--apply`.

The `check` command verifies the presence and correctness of TopMark headers in targeted files. It
does not modify files (dry‑run) but reports which files would need updates. In this mode summaries
end with `- previewed`. When run with `--apply`, files are actually modified and summaries end with
`- inserted`, `- replaced`, or other terminal statuses.

See also:

- [CLI overview](../cli.md)
- [Configuration](../configuration.md)
- [Filtering](../filtering.md)
- [Policies](../policies.md)
- [Exit codes](../exit-codes.md)

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

# Suppress TEXT output and rely on the exit code
topmark check --quiet src/

# Render document-oriented Markdown output
topmark check --output-format markdown src/

# Treat staged config-loading validation warnings as errors for this run
topmark check --strict src/

# Read targets from stdin (one path per line) and generate unified diff output
git ls-files | topmark check --files-from - --diff
```

______________________________________________________________________

- Dry‑run by default; exit code **2** when changes *would* occur.
- Preserves the file’s original **newline style** (LF/CRLF/CR).
- Preserves a leading **UTF‑8 BOM** if present.
- Places headers according to file‑type policy (shebang and PEP 263 in Python; XML
  declaration/DOCTYPE in XML/HTML; no insertion inside Markdown fenced code).
- Uses the same file discovery and filtering as other commands.

### STDIN modes

TopMark supports **two different STDIN modes**:

- **List mode**: read newline-delimited paths or patterns from STDIN using:
  - `--files-from -`
  - `--include-from -`
  - `--exclude-from -`
- **Content mode**: process one file’s *content* from STDIN by passing `-` as the sole PATH and
  providing `--stdin-filename NAME`.

{% include-markdown "\_snippets/no-stdin-option.md" %}

These modes are mutually exclusive: do **not** mix `-` (content mode) with `--files-from -`,
`--include-from -`, or `--exclude-from -` (list mode).

In content mode, `--stdin-filename` is required so TopMark can resolve file type, processor, and
path-sensitive header policy exactly as it would for a real file path.

- Idempotent: re‑running on already‑correct files results in **no changes**.
- Supports `--strict` / `--no-strict` to override the effective `strict_config_checking` value for
  the run.
- Performs whole-source TOML schema validation during configuration loading; TOML-source diagnostics
  (including missing-section INFO diagnostics) are evaluated together with merged-config and
  runtime-applicability diagnostics during staged config-loading/preflight validation for the run.

{% include-markdown "\_snippets/config-resolution.md" %}

______________________________________________________________________

## Filtering

TopMark determines which files to process using a combination of path-based filters and file-type
filters.

For the full filtering contract and recipes, see [Filtering](../filtering.md).

### File type filters

- `--include-file-types / -t` Restrict processing to the given file type identifiers. May be
  repeated and/or provided as a comma-separated list.
- `--exclude-file-types / -T` Exclude the given file type identifiers. May be repeated and/or
  provided as a comma-separated list.

Exclude rules take precedence over include rules.

{% include-markdown "../../\_snippets/file-type-identifiers.md" %}

Examples:

```bash
topmark check --include-file-types python src/
topmark check --include-file-types topmark:python src/
topmark check --exclude-file-types topmark:markdown docs/
```

### Path-based filters

- `--include`, `--exclude` Include or exclude glob patterns.
- `--include-from`, `--exclude-from` Load patterns from files (one per line).
- `--files-from` Provide an explicit list of files to process.

Notes:

- Path-based filters are evaluated **before** file-type filters.
- Exclude rules win over include rules when both match a path.
- File-type filters are applied after path-based include/exclude filtering.
- File-type filters are normalized to canonical qualified keys before resolver and policy
  evaluation.
- Explicit missing literal paths (for example `fubar.py`) are reported as `FILE_NOT_FOUND (66)`.
- Unmatched glob patterns (for example `missing/**/*.py`) are treated as soft discovery diagnostics
  and do not fail `check`.

______________________________________________________________________

## Policy options (check only)

The `check` command supports policy overrides that control how headers are inserted or updated.

See also: [TopMark Policy Guide](../policies.md).

Policy overrides passed to `check` follow the same resolution semantics as TOML configuration and
API overlays.

Use `--header-mutation-mode` to control the mutation intent for `check`:

- `all` (default): insert missing headers and update existing headers
- `add-only`: insert missing headers only; existing headers are not updated
- `update-only`: update existing headers only; missing headers are not inserted

This policy affects dry-run reporting, `--apply` behavior, API result views, and outcome bucketing.
It is a check-only policy; [`strip`](strip.md) removes existing headers and [`probe`](probe.md) is
read-only.

Safety gates still take precedence. Malformed headers, unreadable files, unsupported files, blocked
filesystem states, and other non-mutable conditions are not made mutable by
`--header-mutation-mode`.

### Empty file behavior

- `--allow-header-in-empty-files / --no-allow-header-in-empty-files`
- `--empty-insert-mode`

These options control how `check` classifies empty files and whether headers may be inserted.

`--empty-insert-mode` defines which empty or empty-like files are eligible for insertion:

- `bytes_empty`: only true 0-byte files
- `logical_empty`: true 0-byte files plus logically empty placeholders
- `whitespace_empty`: any decoded content containing only whitespace or newlines

This policy affects dry-run reporting, `--apply` behavior, API result views, and outcome bucketing.

This classification is evaluated together with `--allow-header-in-empty-files`:

- when disabled (default), empty-like files are treated as unchanged/compliant
- when enabled, eligible empty-like files may receive headers, subject to safety gates

`--render-empty-header-when-no-fields` is separate and controls whether an otherwise empty header
may be rendered when no fields are configured.

Safety gates still take precedence. Unreadable files, unsupported files, malformed headers, blocked
filesystem states, and other non-mutable conditions are not made mutable by these options.

### Formatting and safety

- `--allow-reflow / --no-allow-reflow`
- `--render-empty-header-when-no-fields / --no-render-empty-header-when-no-fields`

These options influence rendering behavior and idempotence.

### Shared policy

- `--allow-content-probe / --no-allow-content-probe`

Controls whether file-type detection may inspect file contents.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tooling:

- **JSON**: a single JSON document containing `meta`, the effective `config` snapshot,
  `config_diagnostics`, and then either `results` (detail mode) or `summary` (summary mode).
- **NDJSON**: one record (JSON object) per line. Every record includes `kind` and `meta`, and the
  payload is stored under a container key that matches `kind`.

For the canonical schema and stable `kind` values, see:

- [Machine output schema (JSON & NDJSON)](../../dev/machine-output.md)
- [Machine formats](../../dev/machine-formats.md)

{% include-markdown "\_snippets/output-contract.md" %}

Machine output emits resolved file type identities using canonical qualified keys when available.
Configuration payloads also emit normalized file type filters and `policy_by_type` keys.

Notes:

- Diffs (`--diff`) are **human-only** and are not included in JSON/NDJSON.
- Summary mode aggregates outcomes and suppresses per-file guidance lines.
- The `config` payload in JSON / NDJSON is the resolved config snapshot after per-source TOML
  validation, layered config merge, staged config-loading/preflight validation, and CLI override
  application.

### JSON schema (detail mode)

When `--summary` is **not** set, `topmark check` emits a single JSON object:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "results": [
    { /* per-file result payload */ }
  ]
}
```

### JSON schema (summary mode)

In summary mode (`--summary`), `results` is omitted and replaced by a flat `summary` list of rows:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "summary": [
    { "outcome": "unchanged", "reason": "up-to-date", "count": 30 },
    { "outcome": "would insert", "reason": "header missing, changes found", "count": 1 }
  ]
}
```

### NDJSON schema (detail vs summary)

NDJSON is a stream with a stable prefix followed by either per-file `result` records (detail mode)
or per-bucket `summary` records (summary mode):

- Prefix records:
  1. `kind="config"` (effective config snapshot)
  1. `kind="config_diagnostics"` (**counts-only**)
  1. zero or more `kind="diagnostic"` records (each with `domain="config"`; these may originate from
     TOML-source, merged-config, or runtime-applicability diagnostics)
- Then:
  - detail mode (no `--summary`): one `kind="result"` record per file
  - summary mode (`--summary`): one `kind="summary"` record per `(outcome, reason)` bucket

Example (summary mode):

```jsonc
{"kind":"config","meta":{...},"config":{...}}
{"kind":"config_diagnostics","meta":{...},"config_diagnostics":{"diagnostic_counts":{"info":0,"warning":0,"error":0}}}
{"kind":"summary","meta":{...},"summary":{"outcome":"would insert","reason":"header missing, changes found","count":1}}
```

______________________________________________________________________

Output format, TEXT verbosity, quiet mode, color output, and shared exit-code behavior are
documented in [global options](../global-options.md) and [exit codes](../exit-codes.md).

### Verbosity & logging

TEXT output verbosity is separate from internal logging:

- `-v`, `--verbose` increases TEXT output detail for `check`, such as per-line diagnostics and
  additional hints.
- `-q`, `--quiet` suppresses TEXT output while preserving the command’s exit status.
- See the output-format note above for Markdown and machine-output behavior.

Notes:

- **Summary mode** aggregates outcomes and suppresses per-file guidance lines.
- In TEXT output, **per-line diagnostics** are shown with `-v` and above.
- In Markdown output, diagnostics and hints are rendered when present without requiring `-v`.
- Primary/headline hint selection is presentation-level guidance and is not part of the stable CLI
  contract; rely on exit codes and machine output for automation.
- **Diffs** (`--diff`) are always human‑only and never included in JSON/NDJSON.

## Options (subset)

| Option                        | Description                                                            |
| ----------------------------- | ---------------------------------------------------------------------- |
| `--apply`                     | Write changes to files (off by default).                               |
| `--diff`                      | Show unified diffs (human output only).                                |
| `--summary`                   | Show outcome counts instead of per‑file details.                       |
| `-q`, `--quiet`               | Suppress TEXT output while preserving the command’s exit status.       |
| `--files-from`                | Read newline‑delimited paths from file (use '-' for STDIN).            |
| `-` (PATH)                    | Read a single file’s content from STDIN (requires `--stdin-filename`). |
| `--include`                   | Add paths by glob (can be used multiple times).                        |
| `--include-from`              | File of patterns to include (one per line, `#` comments allowed).      |
| `--exclude`                   | Exclude paths by glob (can be used multiple times).                    |
| `--exclude-from`              | File of patterns to exclude.                                           |
| `--include-file-types` / `-t` | Restrict to local or qualified TopMark file type identifiers.          |
| `--exclude-file-types` / `-T` | Exclude local or qualified TopMark file type identifiers.              |
| `--report`                    | Control reporting scope: actionable, noncompliant, or all.             |
| `--header-mutation-mode`      | Check-only policy override: `all`, `add-only`, or `update-only`.       |
| `--empty-insert-mode`         | Check-only policy override controlling empty-file classification.      |
| `--strict` / `--no-strict`    | Override effective config-validation strictness for this run.          |
| `--stdin-filename`            | Assumed filename when PATH is '-' (content from STDIN).                |

> Run `topmark check -h` for the full list of options and help text.

______________________________________________________________________

## Exit codes

`topmark check` uses exit code `WOULD_CHANGE (2)` as a stable dry-run signal when changes would be
needed. Successful clean runs and successful `--apply` runs exit with `SUCCESS (0)`.

Common `check` exit codes:

| Scenario                     | Exit code                |
| ---------------------------- | ------------------------ |
| Clean run / successful apply | `SUCCESS (0)`            |
| Dry-run would add or update  | `WOULD_CHANGE (2)`       |
| Missing explicit input path  | `FILE_NOT_FOUND (66)`    |
| Write/apply failure          | `IO_ERROR (74)`          |
| Permission failure           | `PERMISSION_DENIED (77)` |
| Configuration error          | `CONFIG_ERROR (78)`      |
| Invalid CLI usage            | `USAGE_ERROR (64)`       |

Notes:

- Explicit missing literal paths are hard input errors and produce `FILE_NOT_FOUND (66)`.
- Unmatched glob patterns are soft discovery diagnostics and do not fail `check`.
- In mixed-result runs, hard input and filesystem errors take precedence over `WOULD_CHANGE (2)`.

See [`Exit codes`](../exit-codes.md) for the complete CLI-wide exit-code contract.

______________________________________________________________________

## File discovery & patterns

- Positional arguments are resolved **relative to the current working directory** (CWD),
  Black‑style.

- Patterns in `--include`, `--exclude`, and the files passed to `--include-from` / `--exclude-from`
  are also resolved **relative to CWD**. Absolute patterns are not supported.

- Explicit missing literal paths are reported as `FILE_NOT_FOUND (66)`. Unmatched glob patterns are
  non-fatal for `check`.

{% include-markdown "\_snippets/file-discovery-patterns.md" %}

{% include-markdown "\_snippets/report-scope.md" %}

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
- **Configuration loading**: before any file processing begins, TopMark resolves TOML sources,
  validates each whole-source TOML fragment, merges the validated layered config fragments, then
  evaluates staged config-loading/preflight validation before freezing the effective config for the
  run.
- **File type identifiers**: local identifiers such as `python` are accepted when unambiguous;
  internally, TopMark normalizes identifiers to canonical qualified keys such as `topmark:python`.

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

### 4) Run with strict config checking

```bash
# Fail when staged config-loading validation warnings are present
# (for example TOML-source, merged-config, or runtime-applicability warnings)
topmark check --strict src/
```

______________________________________________________________________

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
    rev: v1.0.0  # Or latest version
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

## Related commands

- [`topmark strip`](./strip.md) — remove detected TopMark headers instead of inserting or updating
  them.
- [`topmark probe`](./probe.md) — explain file-type and processor resolution.
- [`topmark config check`](./config/check.md) — validate the effective merged configuration and
  report diagnostics.
- [`topmark config dump`](./config/dump.md) — inspect the effective frozen configuration, including
  normalized file type identifiers.

An overview of all CLI commands is available in [CLI overview](../cli.md).

______________________________________________________________________

## Troubleshooting

- **No files to process**: Ensure you passed positional paths, or selected the correct STDIN mode
  (`--files-from -` for list mode, or `-` with `--stdin-filename` for content mode). Use `-vv` for
  detailed TEXT output; use logging options for internal debug logs.
- **Patterns don’t match**: Remember that include/exclude patterns are **relative to CWD**. `cd`
  into the project root before running.
- **File type filter does not match**: use [`topmark probe`](probe.md) to inspect resolver
  decisions, and prefer qualified identifiers such as `topmark:python` when local identifiers may be
  ambiguous.
- **Missing file error**: A literal path such as `fubar.py` is treated as an explicit input and
  fails with `FILE_NOT_FOUND (66)` when it does not exist. Use a glob pattern when an empty match
  set should be non-fatal.
- **Unexpected placement**: For pound/slash formats, check for leading banners or shebang/encoding
  lines. For XML/HTML, verify declaration/doctype positions.
