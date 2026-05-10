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

## Input applicability

- Dry-run by default; exit code **2** when changes *would* occur.
- Preserves the file's original **newline style** (LF/CRLF/CR).
- Preserves a leading **UTF-8 BOM** if present.
- Places headers according to file-type policy (shebang and PEP 263 in Python; XML
  declaration/DOCTYPE in XML/HTML; no insertion inside Markdown fenced code).
- Idempotent: re-running on already-correct files results in **no changes**.

### STDIN modes

`check` supports both list STDIN mode (`--files-from -`, `--include-from -`, or `--exclude-from -`)
and content STDIN mode (`-` plus `--stdin-filename NAME`). These modes are mutually exclusive.

With `--apply` in content mode, transformed content is written to STDOUT and diagnostics are routed
to STDERR.

See [shared input modes](../shared-options.md#shared-input-modes) for the full STDIN contract,
including why TopMark does not provide a `--stdin` option flag.

______________________________________________________________________

## Configuration and validation

`check` supports `--strict` / `--no-strict` to override the effective `strict` value for the run.

Before any file processing begins, TopMark performs whole-source TOML schema validation during
configuration loading. TOML-source diagnostics (including missing-section INFO diagnostics) are
evaluated together with merged-config and runtime-applicability diagnostics during staged
config-loading/preflight validation for the run.

{% include-markdown "\_snippets/config-strictness.md" %}

{% include-markdown "\_snippets/config-resolution.md" %}

______________________________________________________________________

## Filtering and file discovery

TopMark determines which files to process using a combination of path-based filters and file-type
filters.

Path arguments, include/exclude patterns, `--files-from`, and file-type filters follow the shared
TopMark filtering pipeline. Positional paths and relative patterns are resolved from the current
working directory; path-based filters run before file-type filters, and exclude rules take
precedence. See [Filtering](../filtering.md#path-based-filtering) for the full path discovery
contract.

### File type filters

- `--include-file-types / -t` Restrict processing to the given file type identifiers. May be
  repeated and/or provided as a comma-separated list.
- `--exclude-file-types / -T` Exclude the given file type identifiers. May be repeated and/or
  provided as a comma-separated list.

Exclude rules take precedence over include rules.

{% include-markdown "\_snippets/file-type-identifiers.md" %}

See [file-type filtering](../filtering.md#file-type-filtering) for the full identifier contract.

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

- Positional arguments are resolved **relative to the current working directory** (CWD),
  Black-style.
- Patterns in `--include`, `--exclude`, and the files passed to `--include-from` / `--exclude-from`
  are also resolved **relative to CWD**. Absolute patterns are not supported.
- Path-based filters are evaluated **before** file-type filters.
- Exclude rules win over include rules when both match a path.
- File-type filters are applied after path-based include/exclude filtering.
- File-type filters are normalized to canonical qualified keys before resolver and policy
  evaluation.
- Explicit missing literal paths (for example `fubar.py`) are reported as `FILE_NOT_FOUND (66)`.
- Unmatched glob patterns (for example `missing/**/*.py`) are treated as soft discovery diagnostics
  and do not fail `check`.

{% include-markdown "\_snippets/report-scope.md" %}

### Example

```bash
# Use include/exclude files with relative patterns
printf "*.py\n" > inc.txt
printf "tests/*\n# ignored\n" > exc.txt

topmark check --include-from inc.txt --exclude-from exc.txt --diff
```

______________________________________________________________________

## Command-specific policy options

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

## Output behavior

Output format, TEXT verbosity, quiet mode, color output, and shared exit-code behavior are
documented in [shared options](../shared-options.md) and [exit codes](../exit-codes.md).

### Shared output controls

TEXT output verbosity is separate from internal logging:

- `-v`, `--verbose` increases TEXT output detail for `check`, such as per-line diagnostics and
  additional hints.
- `-q`, `--quiet` suppresses TEXT output while preserving the command’s exit status.
- Markdown output is document-oriented and renders diagnostics and hints when present without
  requiring `-v`.
- Machine-readable output ignores TEXT-only verbosity and quiet controls.

Notes:

- **Summary mode** aggregates outcomes and suppresses per-file guidance lines.
- In TEXT output, **per-line diagnostics** are shown with `-v` and above.
- Primary/headline hint selection is presentation-level guidance and is not part of the stable CLI
  contract; rely on exit codes and machine-readable output for automation.
- **Diffs** (`--diff`) are always **human-only** and never included in JSON/NDJSON.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tooling:

- **JSON**: a single JSON document containing `meta`, the effective `config` snapshot,
  `config_diagnostics`, and then either `results` (detail mode) or `summary` (summary mode).
- **NDJSON**: one record (JSON object) per line. Every record includes `kind` and `meta`, and the
  payload is stored under a container key that matches `kind`.

For the canonical schema, stable `kind` values, and shared conventions, see:

- [Machine-readable output schema](../../dev/machine-output.md)
- [Machine-readable formats](../../dev/machine-formats.md)

{% include-markdown "\_snippets/output-contract.md" %}

Machine-readable output emits resolved file type identities using canonical qualified keys when
available. Configuration payloads also emit normalized file type filters and `policy_by_type` keys.

Notes:

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

The per-file result payload mirrors [`strip`](strip.md) but reflects the *check* intent (e.g.
`outcome.check.*` fields instead of `outcome.strip.*`).

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

## Command-specific options

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

## Pre-commit integration

`topmark check` is the command used by the non-destructive `topmark-check` pre-commit hook.

The hook runs `topmark check` against files selected by pre-commit and follows the same resolver,
filtering, policy, configuration, output, and exit-code behavior documented on this page.

For general pre-commit integration guidance, CI workflows, and repository hook configuration, see
[Pre-commit integration](../pre-commit.md).

______________________________________________________________________

## Related commands

- [`topmark strip`](./strip.md) — remove detected TopMark headers instead of inserting or updating
  them.
- [`topmark probe`](./probe.md) — explain file-type and processor resolution.
- [`topmark config check`](./config/check.md) — validate the effective merged configuration and
  report diagnostics.
- [`topmark config dump`](./config/dump.md) — inspect the effective frozen configuration, including
  normalized file type identifiers.

______________________________________________________________________

## Related docs

- [Command overview](../cli.md)
- [Configuration](../configuration.md)
- [Filtering](../filtering.md)
- [Policies](../policies.md)
- [Shared options](../shared-options.md)
- [Exit codes](../exit-codes.md)
- [Machine-readable output schema](../../dev/machine-output.md)
- [Machine-readable formats](../../dev/machine-formats.md)
- [Pre-commit integration](../pre-commit.md)

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
