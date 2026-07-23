<!--
topmark:header:start

  project      : TopMark
  file         : check.md
  file_relpath : docs/usage/commands/check.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# `topmark check`

**Purpose:** Verify TopMark headers and optionally insert or update them with `--apply`.

The `check` command verifies the presence and correctness of TopMark headers in targeted files. It
does not modify files (dry-run) but reports which files would need updates. In this mode summaries
end with `- previewed`. When run with `--apply`, files are actually modified and summaries end with
`- inserted`, `- replaced`, or other terminal statuses.

{% include-markdown "\_snippets/terminology.md" %}

{% include-markdown "\_snippets/path-serialization-contract.md" %}

______________________________________________________________________

## Quick start

```bash
# Dry-run: show which files would get a TopMark header or be updated
topmark check src/

# Apply in place
topmark check --apply src/

# Show unified diffs in human output
topmark check --diff src/

# Summary-only view (CI-friendly)
topmark check --summary src/

# Suppress TEXT rendering and rely on the exit code
topmark check --quiet src/

# Render document-oriented Markdown output
topmark check --output-format markdown src/

# Treat staged configuration-loading validation warnings as errors for this run
topmark check --strict src/

# Read targets from stdin (one path per line) and generate unified diff output
git ls-files | topmark check --files-from - --diff

# Read targets from a file
find src -name '*.py' > files.txt
topmark check --files-from files.txt
```

______________________________________________________________________

## Input applicability

- Dry-run by default; exit code `WOULD_CHANGE (3)` when changes would occur.
- `--apply` and `--diff` are mutually exclusive. Use `--diff` to preview changes or `--apply` to
  write them.
- Preserves the file's original newline style (LF/CRLF/CR).
- Preserves a leading UTF-8 BOM unless `bom_before_shebang = "remove_bom"` remediates a BOM directly
  before a shebang.
- Places headers according to file-type policy (shebang and PEP 263 in Python; XML
  declaration/DOCTYPE in XML/HTML; no insertion inside Markdown fenced code).
- Idempotent: re-running on already-correct files results in **no changes**.

`--bom-before-shebang reject|remove-bom` overrides the remediation policy for this run. The
`remove-bom` mode is standalone: dry-run reports `WOULD_CHANGE (3)` and `--diff` shows BOM removal
even when the header is already compliant; `--apply` writes the BOM-free bytes.

### STDIN modes

`check` supports both list STDIN mode (`--files-from -`, `--include-from -`, or `--exclude-from -`)
and content STDIN mode (`-` plus `--stdin-filename NAME`). These modes are mutually exclusive.

`--files-from FILE` may also be used without positional `PATH` arguments. When the referenced file
is empty, the command proceeds normally and reports that there are no files to process rather than
treating the invocation as invalid CLI usage.

With `--apply` in content mode, transformed content is written to STDOUT and diagnostics are routed
to STDERR.

See [shared input modes](../shared-options.md#shared-input-modes) for the full STDIN contract,
including why TopMark does not provide a `--stdin` option flag.

______________________________________________________________________

## Configuration and validation

`check` supports `--strict` / `--no-strict` to override the effective `strict` value for the run.

Before any file processing begins, TopMark performs whole-source TOML schema validation during
configuration loading. TOML-source diagnostics (including missing-section INFO diagnostics) are
evaluated together with merged-config and runtime applicability diagnostics during staged
configuration-loading validation for the run.

{% include-markdown "\_snippets/config-strictness.md" %}

TopMark resolves configuration from defaults, user config, the project chain discovered from the
resolved discovery anchor, explicit `--config` files, and CLI overrides before staged validation
produces the effective runtime configuration. For path-processing commands such as `check`, the
discovery anchor is derived from the first selected input path when one is available, or from the
current working directory otherwise.

Configuration discovery is evaluated before runtime filesystem-identity evaluation selects
processing paths. Symlinked discovery anchors therefore affect which project configuration files are
found before selected processing paths, header metadata, or machine-readable `result.path` fields
are produced. See
[Configuration discovery, precedence, and policy](../../configuration/discovery.md) for the full
configuration-loading and validation contract.

______________________________________________________________________

## Filtering and file discovery

TopMark determines which files to process using a combination of path-based filters and file-type
filters.

Path arguments, `--files-from` file lists, include/exclude patterns, and file-type filters follow
the shared TopMark filtering pipeline. Positional paths and relative patterns are resolved from the
current working directory; path-based filters run before file-type filters, and exclude rules take
precedence. See [Filtering](../filtering.md#path-inputs-and-path-based-filtering) for the full path
discovery contract.

During discovery, TopMark performs filesystem-identity evaluation and selects processing paths. If
multiple path spellings resolve to the same filesystem target (for example a symlink and its
target), `check` processes the resolved target once. Downstream filtering, probing, header
generation, and machine-readable output operate on the selected processing path rather than the
original spelling. Hard-link policy is evaluated as a processing-target eligibility check: if
multiple selected processing paths are hard links to the same filesystem object, each affected path
is reported as an unsupported, policy-blocked processing target.

This runtime discovery stage is separate from configuration discovery. Project-chain configuration
files have already been selected from the resolved discovery anchor before `check` evaluates file
filters and processing-target identity.

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

`--files-from` contributes explicit processing inputs in the same way as positional paths. It may
therefore be used on its own or together with positional paths. By contrast, `--include-from` and
`--exclude-from` provide filtering rules only and do not contribute processing inputs by themselves.
Notes:

- Positional arguments are parsed by Click and resolved **relative to the current working
  directory** (CWD).
- Unknown option-like tokens before the standard `--` delimiter are parser errors. Use `--` before
  literal path names that begin with a dash, for example `topmark check -- --generated.py`.
- Patterns in `--include`, `--exclude`, and the files passed to `--include-from` / `--exclude-from`
  are also resolved **relative to CWD**. Absolute patterns are not supported.
- Path-based filters are evaluated **before** file-type filters.
- Existing filesystem inputs are normalized to selected processing paths before runtime processing.
- Symlink spellings are not preserved for runtime identity, generated filesystem-related header
  metadata, or machine-readable `result.path` fields.
- Hard-linked selected paths are handled as processing-target eligibility failures. Each affected
  path is reported independently and blocked from processing; TopMark does not select a preferred
  source, target, winner, or loser path.
- Exclude rules win over include rules when both match a path.
- File-type filters are applied after path-based include/exclude filtering.
- File-type filters are normalized to canonical qualified file type identities before filtering,
  runtime resolution, policy evaluation, diagnostics, and registry lookup.
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

See also: [Policy guide](../policies.md).

Policy overrides passed to `check` follow the same resolution semantics as TOML configuration and
API overlays.

Use `--header-mutation-mode` to control mutation behavior for `check`:

- `all` (default): insert missing headers and update existing headers
- `add-only`: insert missing headers only; existing headers are not updated
- `update-only`: update existing headers only; missing headers are not inserted

This policy affects dry-run reporting, `--apply` behavior, API result views, and semantic runtime
outcome bucketing. It is a check-only policy; [`strip`](strip.md) removes existing headers and
[`probe`](probe.md) is read-only.

Safety gates still take precedence. Malformed headers, unreadable files, unsupported files, blocked
filesystem states, and other non-mutable conditions are not made mutable by
`--header-mutation-mode`.

### Empty file behavior

- `--allow-header-in-empty-files / --no-allow-header-in-empty-files`
- `--empty-insert-mode`

These options control how `check` classifies empty files and whether headers may be inserted.

`--empty-insert-mode` defines which empty or empty-like files are eligible for insertion:

- `bytes-empty`: only true 0-byte files
- `logical-empty`: true 0-byte files plus logically empty placeholders
- `whitespace-empty`: any decoded content containing only whitespace or newlines

This policy affects dry-run reporting, `--apply` behavior, API result views, and semantic runtime
outcome bucketing.

This classification is evaluated together with `--allow-header-in-empty-files`:

- when disabled (default), empty-like files are treated as unchanged and compliant
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

Controls whether file-type detection may inspect file contents when needed.

______________________________________________________________________

## Behavior details

- Placement rules (processor-aware):
  - Pound-style processors (for example Python, Shell, Ruby, Makefile): after shebang (and optional
    encoding line), else at top; keep exactly one blank around the block as per policy.
  - Slash-style processors (for example C, C++, TypeScript): at top with consistent spacing.
  - XML/HTML processors: after XML declaration and DOCTYPE; maintain a single intentional blank;
    never break the declaration.
  - Markdown processor: uses HTML comments for the header; fenced code blocks are ignored for
    detection.
- Newline/BOM preservation: preserved across all paths (insert/replace). Reader normalizes in
  memory; updater reattaches BOM and keeps line endings.
- Header metadata path fields: generated from the selected processing target. If a file is reached
  through a symlink, `file_relpath`, `file_abspath`, `relpath`, and `abspath` describe the resolved
  target TopMark reads and writes rather than the symlink spelling.
- Hard-link safety: if multiple selected paths refer to the same filesystem object through hard
  links, `check` blocks every affected path. No header is inserted or updated for those paths, and
  no source, target, winner, or loser path is selected.
- Idempotency: running `topmark check` again on a file that already has a correct header produces no
  diff and exit code 0 (unless other files would change).

______________________________________________________________________

## Output behavior

Output format, TEXT verbosity, quiet mode, color output, and shared exit-code behavior are
documented in [shared options](../shared-options.md) and [exit codes](../exit-codes.md).

### Shared output controls

TEXT verbosity is separate from internal logging:

- `-v`, `--verbose` increases TEXT output detail for `check`, such as per-line diagnostics and
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
- The `--diff` option is supported by both human and machine-readable output. TEXT and Markdown
  render unified diffs for human review; JSON and NDJSON expose structured diff payloads in detail
  mode. With human output, unified diffs are written to STDOUT and report/guidance output is routed
  to STDERR.
- `--apply` and `--diff` are mutually exclusive because `--diff` reserves STDOUT for preview
  payloads while `--apply` performs mutation.

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

Machine-readable output emits selected processing paths with POSIX `/` separators and resolved file
type identities using canonical qualified identity strings when available. If a checked file is
reached through a symlink, per-file `result.path` describes the resolved processing target rather
than the symlink spelling. If selected paths are hard links to the same filesystem object, `check`
emits one result per selected path and reports each affected path as a policy-blocked unsupported
processing target. Configuration payloads also emit normalized file type filters and
`policy_by_type` keys.

Notes:

- The `--diff` option is supported for machine-readable detail output. JSON embeds an optional
  `diff` object under each affected result, while NDJSON emits an adjacent standalone `kind="diff"`
  record after the corresponding result record.
- Machine-readable summary output omits per-file diff payloads even when `--diff` is requested.
  TopMark emits a warning on STDERR to make that suppression explicit.
- Summary mode aggregates outcomes and suppresses per-file guidance lines.
- The `config` payload in JSON and NDJSON is the resolved runtime configuration snapshot after
  per-source TOML validation, layered configuration merge, staged configuration-loading validation,
  and CLI override application.
- Per-file `result.path` values are selected processing paths serialized with POSIX `/` separators
  on all platforms. This path serialization contract applies to processing result payloads; human
  TEXT output remains display-oriented.

### JSON schema (detail mode)

When `--summary` is **not** set, `topmark check` emits a single JSON object:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* RuntimeConfigPayload */ },
  "config_diagnostics": { /* ConfigDiagnosticsPayload */ },
  "results": [
    { /* per-file result payload */ }
  ]
}
```

The per-file result payload mirrors [`strip`](strip.md) but reflects the *check* intent (e.g.
`outcome.check.*` fields instead of `outcome.strip.*`). When `--diff` is requested, changed results
may include an optional `diff` object with a `diff_text` field. See
[Machine-readable output](../machine-output.md#per-file-result-payload) for the canonical schema.
When `--diff` is combined with machine-readable summary mode, per-file diff payloads are omitted and
TopMark emits a warning on STDERR.

### JSON schema (summary mode)

In summary mode (`--summary`), `results` is omitted and replaced by a flat `summary` list of rows:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "config": { /* RuntimeConfigPayload */ },
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
  1. `kind="config"` (effective runtime configuration snapshot)
  1. `kind="config_diagnostics"` (**counts-only**)
  1. zero or more `kind="diagnostic"` records (each with `domain="config"`; these may originate from
     TOML-source, merged-config, or runtime applicability diagnostics)
- Then:
  - detail mode (no `--summary`): one `kind="result"` record per file, optionally followed by an
    adjacent `kind="diff"` record when `--diff` is requested and a diff is available for that file
  - summary mode (`--summary`): one `kind="summary"` record per `(outcome, reason)` bucket; per-file
    `result` and `diff` records are omitted

Example (summary mode):

```jsonc
{"kind":"config","meta":{...},"config":{...}}
{"kind":"config_diagnostics","meta":{...},"config_diagnostics":{"diagnostic_counts":{"info":0,"warning":0,"error":0}}}
{"kind":"summary","meta":{...},"summary":{"outcome":"would insert","reason":"header missing, changes found","count":1}}
```

______________________________________________________________________

## Command-specific options

| Option                        | Description                                                                  |
| ----------------------------- | ---------------------------------------------------------------------------- |
| `--apply`                     | Write changes to files (off by default; mutually exclusive with `--diff`).   |
| `--diff`                      | Preview diffs; emits human unified diffs or machine diff payloads.           |
| `--summary`                   | Show outcome counts instead of per-file details.                             |
| `-q`, `--quiet`               | Suppress TEXT rendering while preserving the command's exit status.          |
| `--files-from`                | Read newline-delimited paths from file (use '-' for STDIN).                  |
| `-` (PATH)                    | Read one virtual file from STDIN content (requires `--stdin-filename`).      |
| `--include`                   | Add paths by glob (can be used multiple times).                              |
| `--include-from`              | File of patterns to include (one per line, `#` comments allowed).            |
| `--exclude`                   | Exclude paths by glob (can be used multiple times).                          |
| `--exclude-from`              | File of patterns to exclude.                                                 |
| `--include-file-types` / `-t` | Restrict to local or qualified TopMark file type identifiers.                |
| `--exclude-file-types` / `-T` | Exclude local or qualified TopMark file type identifiers.                    |
| `--report`                    | Control reporting scope: actionable, noncompliant, or all.                   |
| `--header-mutation-mode`      | Check-only policy override: `all`, `add-only`, or `update-only`.             |
| `--empty-insert-mode`         | Check-only policy override controlling empty-file classification.            |
| `--strict` / `--no-strict`    | Override effective configuration-loading validation strictness for this run. |
| `--stdin-filename`            | Assumed filename when PATH is '-' (content from STDIN).                      |

> Run `topmark check -h` for the full list of options and help text.

______________________________________________________________________

## Exit codes

`topmark check` uses exit code `WOULD_CHANGE (3)` as a stable dry-run signal when changes would be
needed. Successful clean runs and successful `--apply` runs exit with `SUCCESS (0)`.

Common `check` exit codes:

| Scenario                     | Exit code                |
| ---------------------------- | ------------------------ |
| Clean run / successful apply | `SUCCESS (0)`            |
| Dry-run would add or update  | `WOULD_CHANGE (3)`       |
| Missing explicit input path  | `FILE_NOT_FOUND (66)`    |
| Write/apply failure          | `IO_ERROR (74)`          |
| Permission failure           | `PERMISSION_DENIED (77)` |
| Configuration error          | `CONFIG_ERROR (78)`      |
| Invalid CLI usage            | `USAGE_ERROR (64)`       |

Notes:

- Click parser-level usage errors (for example, unknown commands, unknown options, or invalid option
  values) may exit with code `2` before command logic runs.
- Explicit missing literal paths are hard input errors and produce `FILE_NOT_FOUND (66)`.
- Unmatched glob patterns are soft discovery diagnostics and do not fail `check`.
- In mixed-result runs, hard input and filesystem errors take precedence over `WOULD_CHANGE (3)`.

See [`Exit codes`](../exit-codes.md) for the complete CLI-wide exit-code contract.

______________________________________________________________________

## Typical workflows

### 1) Add headers to a project

```bash
# Start with a dry-run to see impact
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
# Print summary only. Exit 3 signals "would change" to fail the job.
topmark check --summary
```

### 4) Run with strict config checking

```bash
# Fail when staged configuration-loading validation warnings are present
# (for example TOML-source, merged-config, or runtime applicability warnings)
topmark check --strict src/
```

______________________________________________________________________

## Pre-commit integration

`topmark check` is the command used by the non-destructive `topmark-check` pre-commit hook.

The hook runs `topmark check` against files selected by pre-commit and follows the same resolution,
filtering, policy, configuration, output, and exit-code behavior documented on this page.

For general pre-commit integration guidance, CI workflows, and repository hook configuration, see
[Pre-commit integration](../pre-commit.md).

______________________________________________________________________

## Related commands

- [`topmark strip`](./strip.md) - remove detected TopMark headers instead of inserting or updating
  them.
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
- **Symlink path not shown in output**: `check` processes selected processing paths. If a symlink
  and its target resolve to the same file, machine-readable output and generated header metadata
  describe the resolved target rather than the symlink spelling.
- **Hard-linked files are reported as unsupported**: `check` blocks processing when multiple
  selected paths refer to the same filesystem object through hard links. Each affected path is
  reported independently; no preferred path is selected from the hard-link group.
- **File type filter does not match**: use [`topmark probe`](probe.md) to inspect resolution
  decisions, and prefer qualified identifiers such as `topmark:python` when local identifiers may be
  ambiguous.
- **Missing file error**: A literal path such as `fubar.py` is treated as an explicit input and
  fails with `FILE_NOT_FOUND (66)` when it does not exist. Use a glob pattern when an empty match
  set should be non-fatal.
- **Unexpected placement**: For pound/slash formats, check for leading banners or shebang/encoding
  lines. For XML/HTML, verify declaration/doctype positions.
