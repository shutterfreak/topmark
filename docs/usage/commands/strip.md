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

**Purpose:** Strip TopMark headers.

The `strip` command removes the entire TopMark header block from targeted files. It is **dry‑run by
default** (summaries end with `- previewed`) and becomes destructive only with `--apply` (summaries
end with `- removed`) when run with `--apply`.

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

# Treat aggregated config-resolution/preflight warnings as errors for this run
topmark strip --strict src/

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

- Idempotent: re‑running after headers are removed results in **no changes**.
- Supports `--strict` / `--no-strict` to override the effective `strict_config_checking` value for
  the run.
- Performs whole-source TOML schema validation during configuration loading; TOML-layer diagnostics
  (including missing-section INFO diagnostics) are included in the final config diagnostics for the
  run.

{% include-markdown "\_snippets/config-resolution.md" %}

______________________________________________________________________

## Filtering

TopMark determines which files to process using a combination of path-based filters and file-type
filters.

### File type filters

- `--include-file-types / -t` Restrict processing to the given file type identifiers. May be
  repeated and/or provided as a comma-separated list.

- `--exclude-file-types / -T` Exclude the given file type identifiers. May be repeated and/or
  provided as a comma-separated list.

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

## Policy options (strip)

The `strip` command supports only shared policy options.

See also: [TopMark Policy Guide](../policies.md).

### Shared policy

- `--allow-content-probe / --no-allow-content-probe`

Controls whether file-type detection may inspect file contents.

Header insertion and update policies (such as mutation mode or empty-file behavior) do not apply to
`strip`.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tooling:

- **JSON**: a single JSON document containing `meta`, `config`, `config_diagnostics`, and then
  either `results` (detail mode) or `summary` (summary mode).
- **NDJSON**: one JSON object per line. Every record includes `kind` and `meta`, and the payload is
  stored under a container key that matches `kind`.

For the canonical schema, stable `kind` values, and shared conventions, see:

- [Machine output schema (JSON & NDJSON)](../../dev/machine-output.md)
- [Machine formats](../../dev/machine-formats.md)

Notes:

- Diffs (`--diff`) are **human-only** and are not included in JSON/NDJSON.
- Summary mode aggregates outcomes and suppresses per-file guidance lines.
- The `config` payload in JSON / NDJSON is the resolved config snapshot after per-source TOML
  validation, layered config merge, and CLI override application.

### JSON schema (detail mode)

When `--summary` is **not** set, `topmark strip` emits a single JSON object:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "results": [
    { /* per-file strip result payload */ }
  ]
}
```

The per-file result payload mirrors `check` but reflects the *strip* intent (e.g. `outcome.strip.*`
fields instead of `outcome.check.*`).

### JSON schema (summary mode)

In summary mode (`--summary`), `results` is omitted and replaced by a flat `summary` list of rows:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* ConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "summary": [
    { "outcome": "would strip", "reason": "header detected, ready for stripping", "count": 30 },
    { "outcome": "skipped", "reason": "known file type, headers not supported", "count": 1 }
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
     TOML schema validation or config-layer validation)
- Then:
  - detail mode (no `--summary`): one `kind="result"` record per file
  - summary mode (`--summary`): one `kind="summary"` record per `(outcome, reason)` bucket

Example (summary mode):

```jsonc
{"kind":"config","meta":{...},"config":{...}}
{"kind":"config_diagnostics","meta":{...},"config_diagnostics":{"diagnostic_counts":{"info":0,"warning":0,"error":0}}}
{"kind":"summary","meta":{...},"summary":{"outcome":"would strip","reason":"header detected, ready for stripping","count":30}}
```

______________________________________________________________________

## Verbosity & logging

Program-output verbosity is separate from internal logging:

- `-v`, `--verbose` increases **program output** detail (e.g., renders per‑line diagnostics).
- `-q`, `--quiet` suppresses most **program output**.

Notes:

- **Summary mode** aggregates outcomes and suppresses per-file guidance lines.
- **Per‑line diagnostics** are shown when the effective program verbosity ≥ 1.
- **Diffs** (`--diff`) are always human‑only and never included in JSON/NDJSON.

## Options (subset)

| Option                                               | Description                                                            |
| ---------------------------------------------------- | ---------------------------------------------------------------------- |
| `--apply`                                            | Write changes to files (off by default).                               |
| `--diff`                                             | Show unified diffs (human output only).                                |
| `--summary`                                          | Show outcome counts instead of per‑file details.                       |
| `--files-from`                                       | Read newline‑delimited paths from file (use '-' for STDIN).            |
| `-` (PATH)                                           | Read a single file’s content from STDIN (requires `--stdin-filename`). |
| `--include`                                          | Add paths by glob (can be used multiple times).                        |
| `--include-from`                                     | File of patterns to include (one per line, `#` comments allowed).      |
| `--exclude`                                          | Exclude paths by glob (can be used multiple times).                    |
| `--exclude-from`                                     | File of patterns to exclude.                                           |
| `--include-file-types` / `-t`                        | Restrict to specific TopMark file type identifiers.                    |
| `--exclude-file-types` / `-T`                        | Exclude specific TopMark file type identifiers.                        |
| `--report`                                           | Control reporting scope: actionable, noncompliant, or all.             |
| `--allow-content-probe` / `--no-allow-content-probe` | Shared policy override for file-type detection.                        |
| `--strict` / `--no-strict`                           | Override effective config-validation strictness for this run.          |
| `--stdin-filename`                                   | Assumed filename when PATH is '-' (content from STDIN).                |

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

- STDIN supports two modes:

  - **list mode** via `--files-from -` (or `--include-from -` / `--exclude-from -`) for newline-
    delimited paths or patterns
  - **content mode** via `-` plus `--stdin-filename` for one file’s content

- Use `--report actionable` to focus CI output on files that would change, or
  `--report noncompliant` to also include unsupported file types in the report.

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
- **Configuration loading**: before any file processing begins, TopMark resolves TOML sources,
  validates each whole-source TOML fragment, then merges the validated layered config fragments into
  the effective config for the run.

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

### 4) Run with strict config checking

```bash
# Fail when aggregated config-resolution/preflight warnings are present
# (for example TOML validation issues, suspicious config inputs, or sanitization warnings)
topmark strip --strict src/
```

## Pre‑commit integration

There is currently **no** `topmark-strip` pre-commit hook. Use the CLI directly when you need to
remove headers:

```bash
topmark strip --apply <paths>
```

______________________________________________________________________

## Related commands

- [`topmark check`](./check.md) — add or update detected TopMark headers.
- [`topmark config check`](./config/check.md) — validate the effective merged configuration and
  report diagnostics.
- [`topmark config dump`](./config/dump.md) — show the effective merged configuration as TOML.

______________________________________________________________________

## Troubleshooting

- **No files to process**: Ensure you passed positional paths, or selected the correct STDIN mode
  (`--files-from -` for list mode, or `-` with `--stdin-filename` for content mode). Use `-vv` for
  debug logs.
- **Patterns don’t match**: Remember that include/exclude patterns are **relative to CWD**. `cd`
  into the project root before running.
- **“Header not detected”**: Header‑like text inside code fences or strings is intentionally
  ignored; `strip` won’t remove it.
