<!--
topmark:header:start

  project      : TopMark
  file         : filtering.md
  file_relpath : docs/usage/filtering.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Common filtering recipes

Filtering controls determine:

- which paths are considered during discovery
- which file types are eligible for processing
- how explicit inputs are classified
- how probe diagnostics are reported

See also:

- [CLI overview](cli.md)
- [Configuration](configuration.md)
- [Global options](global-options.md)

TopMark determines which files to process using a combination of **path-based filters** and **file
type filters**.

{% include-markdown "\_snippets/file-type-identifiers.md" %}

For canonical file-type identifier semantics and configuration behavior, see
[Configuration](configuration.md).

Filtering order:

This order is deterministic and is shared consistently across:

- CLI execution
- TOML configuration
- API overlays
- resolver and probe filtering

1. Path filters (include/exclude patterns, `*_from`, `files_from`)
1. File type filters (`include_file_types`, `exclude_file_types`)
1. Eligibility (supported vs unsupported)

Note: For [`topmark probe`](commands/probe.md), paths excluded during step 1 or 2 may still be
reported as `filtered` results if they were explicitly requested.

## Missing vs unmatched inputs

TopMark distinguishes between **explicit literal paths** and **glob patterns**:

- **Explicit missing literal paths** (e.g., `fubar.py`) are treated as **hard input errors** and
  result in `FILE_NOT_FOUND (66)`.
- **Unmatched glob patterns** (e.g., `missing/**/*.py`) are treated as **soft discovery
  diagnostics** and do **not** cause a failure for processing commands
  ([`check`](commands/check.md), [`strip`](commands/strip.md)) (exit `SUCCESS (0)`).

This distinction ensures that typos in explicit inputs are surfaced, while flexible patterns that
match nothing do not break automation.

## STDIN support

TopMark supports two STDIN modes when supplying file lists or content:

- **List mode**: provide newline-delimited paths or patterns via:
  - `--files-from -`
  - `--include-from -`
  - `--exclude-from -`
- **Content mode**: process a single file's content from STDIN by passing `-` as the sole PATH
  together with `--stdin-filename NAME`

{% include-markdown "\_snippets/no-stdin-option.md" %}

These modes are mutually exclusive and should not be combined. In content mode, `--stdin-filename`
is required so TopMark can resolve file type and header policy consistently with path-based inputs.

Note that STDIN handling is independent from configuration validation. Options such as `--strict` /
`--no-strict` still apply and control how staged config-loading/preflight validation warnings are
treated during the run.

## Interaction with [`topmark probe`](commands/probe.md)

The [`topmark probe`](commands/probe.md) command uses the same discovery and filtering rules
described above.

This includes:

- path filtering
- file-type filtering
- canonical file-type identifier normalization
- ambiguity handling

However, unlike processing commands ([`check`](commands/check.md), [`strip`](commands/strip.md)),
[`probe`](commands/probe.md) also reports **explicit inputs that were filtered out before file-type
probing**.

Additionally, [`probe`](commands/probe.md) treats unmatched glob patterns as **filtered semantic
outcomes** rather than silent no-ops. As a result:

- Unmatched glob patterns are reported as `filtered` probe results (e.g.,
  `filtered: excluded_by_discovery_filter`).
- The command exits with `UNSUPPORTED_FILE_TYPE (69)`, reflecting incomplete resolution.

This differs from processing commands, which treat unmatched patterns as non-fatal diagnostics.

[`probe`](commands/probe.md) is read-only and diagnostic-only. It shares discovery and filtering
behavior with [`check`](commands/check.md) and [`strip`](commands/strip.md), but rejects mutation,
diff, reporting, and generated-header options that do not apply.

For example, when a path is excluded via `--exclude` or `exclude_patterns`,
[`topmark probe`](commands/probe.md) will still show it in the output as:

```text
<path>: <filtered> - filtered: excluded_by_path_filter
```

In machine-readable formats (JSON / NDJSON), these are represented as probe results with:

```jsonc
{
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
- `excluded_by_discovery_filter` — excluded before probing, but exact category not identified
- `no_candidates` — no file-type candidates were found (e.g., unsupported extension)

Only explicitly requested inputs (CLI paths or `--files-from`) are reported this way. Files excluded
implicitly during recursive discovery are not enumerated.

## Recipe: Process only Python and Markdown

CLI:

```bash
topmark check --include-file-types python,markdown .
```

Equivalent canonical form:

```bash
topmark check --include-file-types topmark:python,topmark:markdown .
```

TOML:

```toml
[files]
include_file_types = ["python", "markdown"]
```

## Recipe: Exclude generated/virtualenv folders

TOML:

```toml
[files]
exclude_patterns = [
  ".venv/**",
  "**/__pycache__/**",
  "**/.mypy_cache/**",
  "**/.pytest_cache/**",
  "dist/**",
  "build/**",
]
```

## Recipe: Include only `src/` and `tests/`

TOML:

```toml
[files]
include_patterns = ["src/**", "tests/**"]
```

## Recipe: Use include/exclude pattern files (portable across repos)

```toml
[files]
include_from = ["include.txt"]
exclude_from = ["exclude.txt"]
```

These files may also be provided via STDIN by using `-` as the file path.

Example `include.txt`:

```text
src/**
tests/**
```

Example `exclude.txt`:

```text
.venv/**
**/__pycache__/**
```

## Recipe: Exclude a specific file type after path filtering

```toml
[files]
include_patterns = ["**/*.toml", "**/*.yaml", "**/*.yml"]
exclude_file_types = ["yaml"]
```

Equivalent canonical form:

```toml
[files]
exclude_file_types = ["topmark:yaml"]
```

## Recipe: Process only a known file list (from Git)

Generate a file list:

```bash
git ls-files > files.txt
```

Then:

```bash
topmark check --files-from files.txt
```

You can also stream the file list via STDIN:

```bash
git ls-files | topmark check --files-from -
```

## Recipe: Show only actionable files (would change)

```bash
topmark check --report actionable .
```

## Recipe: Include unsupported files in reporting

```bash
topmark check --report noncompliant .
topmark strip --report noncompliant .
```

## File-type identifier behavior

{% include-markdown "\_snippets/file-type-identifiers.md" %}

Filtering accepts:

- local identifiers such as `python`
- canonical qualified identifiers such as `topmark:python`

Internally, TopMark normalizes configured identifiers to canonical qualified keys before resolver
and policy evaluation.

## Exit-code interaction

Filtering decisions can influence exit codes indirectly:

- Missing explicit inputs → `FILE_NOT_FOUND (66)`
- Unmatched glob patterns → no failure ([`check`](commands/check.md) / [`strip`](commands/strip.md),
  `SUCCESS (0)`), or `UNSUPPORTED_FILE_TYPE (69)` in [`probe`](commands/probe.md)

Missing explicit inputs take precedence over semantic probe outcomes.

When multiple conditions occur, TopMark applies an exit-code priority model (see
[Exit Codes documentation](exit-codes.md)), where hard input and filesystem errors take precedence.

Invalid CLI usage (for example, unsupported options or inappropriate STDIN modes) is reported as a
usage error and takes precedence over filtering outcomes.

## Notes on configuration strictness

Filtering determines *which* files are processed, while staged config-loading/preflight validation
determines whether a run is allowed to proceed.

Effective strictness is controlled by:

1. CLI override (`--strict` / `--no-strict`)
1. TOML setting (`strict_config_checking`)
1. default non-strict behaviour

When strict config checking is enabled, validation warnings are treated as errors and may cause the
command to fail before processing files.

______________________________________________________________________

## Related pages

- [CLI overview](cli.md)
- [Configuration](configuration.md)
- [Global options](global-options.md)
- [Policies](policies.md)
- [Exit codes](exit-codes.md)
- [Configuration discovery](../configuration/discovery.md)
