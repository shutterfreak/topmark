<!--
topmark:header:start

  project      : TopMark
  file         : strip.md
  file_relpath : docs/usage/commands/strip.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# `topmark strip`

**Purpose:** Strip TopMark headers.

The `strip` command removes the entire TopMark header block from targeted files. It is **dry-run by
default** (summaries end with `- previewed`) and becomes destructive only with `--apply` (summaries
end with `- removed`).

{% include-markdown "\_snippets/terminology.md" %}

______________________________________________________________________

## Quick start

```bash
# Dry-run: show which files would have their TopMark header removed
topmark strip src/

# Apply in place
topmark strip --apply src/

# Show unified diffs (human output)
topmark strip --diff src/

# Summary-only view (CI-friendly)
topmark strip --summary src/

# Suppress TEXT rendering and rely on the exit code
topmark strip --quiet src/

# Render document-oriented Markdown output
topmark strip --output-format markdown src/

# Treat staged configuration-loading validation warnings as errors for this run
topmark strip --strict src/

# Read targets from stdin (one path per line) and generate unified diff output
git ls-files | topmark strip --files-from - --diff
```

______________________________________________________________________

## Input applicability

- Dry-run by default; exit code `WOULD_CHANGE (3)` when removals would occur.
- Preserves the file's original newline style (LF/CRLF/CR).
- Preserves a leading UTF-8 BOM if present.
- Honors XML/HTML placement rules and preserves the XML declaration (`<?xml ...?>`).
- Respects Markdown fenced code blocks: header-like snippets inside fences are ignored.
- Idempotent: once stripped, subsequent runs are no-ops.

### STDIN modes

`strip` supports both list STDIN mode (`--files-from -`, `--include-from -`, or `--exclude-from -`)
and content STDIN mode (`-` plus `--stdin-filename NAME`). These modes are mutually exclusive.

With `--apply` in content mode, transformed content is written to STDOUT and diagnostics are routed
to STDERR.

See [shared input modes](../shared-options.md#shared-input-modes) for the full STDIN contract,
including why TopMark does not provide a `--stdin` option flag.

______________________________________________________________________

## Configuration and validation

`strip` supports `--strict` / `--no-strict` to override the effective `strict` value for the run.

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
topmark strip --include-file-types python src/
topmark strip --include-file-types topmark:python src/
topmark strip --exclude-file-types topmark:markdown docs/
```

### Path-based filters

- `--include`, `--exclude` Include or exclude glob patterns.
- `--include-from`, `--exclude-from` Load patterns from files (one per line).
- `--files-from` Provide an explicit list of files to process.

See [Filtering](../filtering.md#path-based-filtering) for CWD-resolution rules, missing vs unmatched
input behavior, include/exclude precedence, and STDIN interactions.

{% include-markdown "\_snippets/report-scope.md" %}

### Example

```bash
# Use include/exclude files with relative patterns
printf "*.py\n" > inc.txt
printf "tests/*\n# ignored\n" > exc.txt

topmark strip --include-from inc.txt --exclude-from exc.txt --diff
```

______________________________________________________________________

## Command-specific policy options

The `strip` command supports only shared runtime resolution and file-type-detection policy options.

See also: [Policy guide](../policies.md).

Policy overrides passed to `strip` follow the same runtime resolution semantics as TOML
configuration and API overlays.

### Shared policy

- `--allow-content-probe / --no-allow-content-probe`

Controls whether file-type detection may inspect file contents when needed.

Header insertion and update policies (such as mutation mode, empty-file behavior, or
generated-header formatting) do not apply to `strip` and are rejected when provided.

______________________________________________________________________

## Behavior details

- Removal policy: if a valid TopMark header is detected (policy-aware), remove the whole block. A
  permissive fallback accepts legacy single-line-wrapped markers (e.g., HTML/XML `<!-- ... -->`).
- Newline/BOM preservation: preserved across removal. Reader normalizes in-memory; updater
  re-attaches BOM and keeps line endings.
- XML/HTML processors: keep the XML declaration as the first logical line; maintains a single
  intentional blank as needed.
- Markdown processor: ignores code fences for detection; header-like text inside fences is not
  removed.

______________________________________________________________________

## Output behavior

Output format, TEXT verbosity, quiet mode, color output, and shared exit-code behavior are
documented in [shared options](../shared-options.md) and [exit codes](../exit-codes.md).

### Shared output controls

TEXT verbosity is separate from internal logging:

- `-v`, `--verbose` increases TEXT output detail for `strip`, such as per-line diagnostics and
  additional hints.
- `-q`, `--quiet` suppresses TEXT rendering while preserving the command's exit status.
- Markdown output is document-oriented and renders diagnostics and hints when present without
  requiring `-v`.
- Machine-readable JSON and NDJSON output ignore TEXT-oriented verbosity and quiet controls.

Notes:

- Summary mode aggregates outcomes and suppresses per-file guidance lines.
- In TEXT rendering, per-line diagnostics are shown with `-v` and above.
- Primary/headline hint selection is presentation-level guidance and is not part of the stable CLI
  contract; rely on exit codes and machine-readable output for automation.
- Diffs (`--diff`) are always human-readable only and never included in JSON or NDJSON output.

______________________________________________________________________

## Machine-readable output

Use `--output-format json` or `--output-format ndjson` to emit output suitable for tooling:

- JSON: a single machine-readable JSON document containing `meta`, the effective runtime
  configuration snapshot, `config_diagnostics`, and then either `results` (detail mode) or `summary`
  (summary mode).
- NDJSON: one machine-readable NDJSON record per line. Every record includes `kind` and `meta`, and
  the payload is stored under a container key that matches `kind`.

For the canonical schema, stable `kind` values, and shared conventions, see:

- [Machine-readable output](../machine-output.md)
- [Machine-readable format conventions](../../dev/machine-formats.md)

{% include-markdown "\_snippets/output-contract.md" %}

Machine-readable output emits resolved file type identities using canonical qualified identity
strings when available. Configuration payloads also emit normalized file type filters and
`policy_by_type` keys.

Notes:

- Diffs (`--diff`) are human-readable only and are not included in JSON or NDJSON output.
- Summary mode aggregates outcomes and suppresses per-file guidance lines.
- The `config` payload in JSON and NDJSON is the resolved runtime configuration snapshot after
  per-source TOML validation, layered configuration merge, staged configuration-loading validation,
  and CLI override application.

### JSON schema (detail mode)

When `--summary` is **not** set, `topmark strip` emits a single JSON object:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* RuntimeConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "results": [
    { /* per-file strip result payload */ }
  ]
}
```

The per-file result payload mirrors [`check`](check.md) but reflects the *strip* intent (e.g.
`outcome.strip.*` fields instead of `outcome.check.*`).

### JSON schema (summary mode)

In summary mode (`--summary`), `results` is omitted and replaced by a flat `summary` list of rows:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* RuntimeConfigPayload */ },
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
  1. `kind="config"` (effective runtime configuration snapshot)
  1. `kind="config_diagnostics"` (**counts-only**)
  1. zero or more `kind="diagnostic"` records (each with `domain="config"`; these may originate from
     TOML-source, merged-config, or runtime applicability diagnostics)
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

## Command-specific options

| Option                                               | Description                                                                  |
| ---------------------------------------------------- | ---------------------------------------------------------------------------- |
| `--apply`                                            | Write changes to files (off by default).                                     |
| `--diff`                                             | Show unified diffs (human output only).                                      |
| `--summary`                                          | Show outcome counts instead of per-file details.                             |
| `-q`, `--quiet`                                      | Suppress TEXT rendering while preserving the command's exit status.          |
| `--files-from`                                       | Read newline-delimited paths from file (use '-' for STDIN).                  |
| `-` (PATH)                                           | Read one virtual file from STDIN content (requires `--stdin-filename`).      |
| `--include`                                          | Add paths by glob (can be used multiple times).                              |
| `--include-from`                                     | File of patterns to include (one per line, `#` comments allowed).            |
| `--exclude`                                          | Exclude paths by glob (can be used multiple times).                          |
| `--exclude-from`                                     | File of patterns to exclude.                                                 |
| `--include-file-types` / `-t`                        | Restrict to local or qualified TopMark file type identifiers.                |
| `--exclude-file-types` / `-T`                        | Exclude local or qualified TopMark file type identifiers.                    |
| `--report`                                           | Control reporting scope: actionable, noncompliant, or all.                   |
| `--allow-content-probe` / `--no-allow-content-probe` | Shared policy override for file-type detection.                              |
| `--strict` / `--no-strict`                           | Override effective configuration-loading validation strictness for this run. |
| `--stdin-filename`                                   | Assumed filename when PATH is '-' (content from STDIN).                      |

> Run `topmark strip -h` for the full list of options and help text.

______________________________________________________________________

## Exit codes

`topmark strip` uses exit code `WOULD_CHANGE (3)` as a stable dry-run signal when removals would be
needed. Successful no-op runs and successful `--apply` runs exit with `SUCCESS (0)`.

Common `strip` exit codes:

| Scenario                     | Exit code                |
| ---------------------------- | ------------------------ |
| Clean run / successful apply | `SUCCESS (0)`            |
| Dry-run would remove headers | `WOULD_CHANGE (3)`       |
| Missing explicit input path  | `FILE_NOT_FOUND (66)`    |
| Write/apply failure          | `IO_ERROR (74)`          |
| Permission failure           | `PERMISSION_DENIED (77)` |
| Configuration error          | `CONFIG_ERROR (78)`      |
| Invalid CLI usage            | `USAGE_ERROR (64)`       |

Notes:

- Click parser-level usage errors (for example, unknown commands, unknown options or invalid option
  values) may exit with code `2` before command logic runs.
- Explicit missing literal paths are hard input errors and produce `FILE_NOT_FOUND (66)`.
- Unmatched glob patterns are soft discovery diagnostics and do not fail `strip`.
- In mixed-result runs, hard input and filesystem errors take precedence over `WOULD_CHANGE (3)`.

See [`Exit codes`](../exit-codes.md) for the complete CLI-wide exit-code contract.

______________________________________________________________________

## Typical workflows

### 1) Remove headers from a project

```bash
# Start with a dry-run to see impact
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
# Print summary only. Exit 3 signals "would change" to fail the job.
topmark strip --summary
```

### 4) Run with strict config checking

```bash
# Fail when staged configuration-loading validation warnings are present
# (for example TOML-source, merged-config, or runtime applicability warnings)
topmark strip --strict src/
```

______________________________________________________________________

## Pre-commit integration

There is currently no dedicated `topmark-strip` pre-commit hook.

Use `topmark strip --apply` directly when you intentionally want to remove TopMark headers from a
selected set of files.

For general pre-commit integration guidance, CI workflows, and repository hook configuration, see
[Pre-commit integration](../pre-commit.md).

______________________________________________________________________

## Related commands

- [`topmark check`](./check.md) - add or update detected TopMark headers.
- [`topmark probe`](./probe.md) - explain file-type and processor resolution.
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
- [Header placement rules](../header-placement.md)
- [Machine-readable output](../machine-output.md)
- [Machine-readable format conventions](../../dev/machine-formats.md)
- [Pre-commit integration](../pre-commit.md)
- [Terminology and Canonical Vocabulary](../../terminology.md)

______________________________________________________________________

## Troubleshooting

- **No files to process**: Ensure you passed positional paths, or selected the correct STDIN mode
  (`--files-from -` for list mode, or `-` with `--stdin-filename` for content mode). Use `-vv` for
  detailed TEXT rendering; use logging options for internal debug logs.
- **Patterns do not match**: Remember that include/exclude patterns are **relative to CWD**. `cd`
  into the project root before running.
- **File type filter does not match**: use [`topmark probe`](probe.md) to inspect resolution
  decisions, and prefer qualified identifiers such as `topmark:python` when local identifiers may be
  ambiguous.
- **Missing file error**: A literal path such as `fubar.py` is treated as an explicit input and
  fails with `FILE_NOT_FOUND (66)` when it does not exist. Use a glob pattern when an empty match
  set should be non-fatal.
- **"Header not detected"**: Header-like text inside code fences or strings is intentionally
  ignored; `strip` won't remove it.
