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

Filtering controls determine stable runtime behavior such as:

- which paths participate in discovery
- which file types are eligible for processing
- how explicit inputs participate in semantic runtime outcomes
- how probe diagnostics are reported

TopMark determines which files to process using a combination of **explicit input sources**,
**path-based filters**, and **file type filters**.

{% include-markdown "\_snippets/terminology.md" %}

## Filtering overview

Filtering and discovery semantics are shared consistently across:

- [`topmark check`](commands/check.md)
- [`topmark strip`](commands/strip.md)
- [`topmark probe`](commands/probe.md)
- TOML configuration
- API overlays
- runtime-resolution and probe filtering

TopMark applies input selection and filtering in a deterministic order:

1. Explicit input collection and path-based discovery
1. Path-based filtering
1. File-type filtering
1. Runtime applicability evaluation
1. Runtime processor resolution

Exclude rules take precedence over include rules.

Filesystem-identity evaluation and processing-path selection occur during path discovery before
runtime applicability evaluation and processor resolution.

Filesystem-identity evaluation includes filesystem-identity normalization for equivalent path
spellings (such as symlinks), processing-path selection, and processing-target eligibility checks
(such as hard-link detection).

For canonical file-type identifier semantics, see [File-type filtering](#file-type-filtering). For
layered configuration behavior, see [Configuration](configuration.md).

Filtering occurs after configuration discovery. Project-chain configuration files are discovered
from the resolved discovery anchor before path filters, file-type filters, and runtime applicability
are evaluated.

> [!NOTE]
>
> For [`topmark probe`](commands/probe.md), paths excluded during step 1 or 2 may still be reported
> as `filtered` semantic outcomes when they were explicitly requested inputs.

______________________________________________________________________

## Runtime filtering boundaries

TopMark intentionally separates:

1. explicit input collection
1. path discovery
1. path filtering
1. filesystem-identity evaluation
1. processing-path selection
1. file-type filtering
1. runtime applicability evaluation
1. runtime probing and processor resolution

Each stage consumes the finalized results of the previous stage.

This layered filtering model keeps runtime behavior deterministic while preserving stable probe
diagnostics and machine-readable filtering semantics.

For path-processing commands, the configuration discovery anchor is derived from the first selected
input path when one is available, or from the current working directory otherwise. Project-chain
discovery walks upward from the resolved anchor location before this runtime filtering model starts.

When multiple path spellings resolve to the same filesystem target (for example a symlink and its
target), filesystem-identity normalization resolves symlink spellings to the target path and selects
a canonical processing path before runtime filtering continues. Downstream filtering, probing,
header generation, and machine-readable output operate on that processing path rather than the
original spelling used to reach the file.

Hard-link policy is evaluated as a processing-target eligibility check. If multiple selected paths
refer to the same filesystem object through hard links, TopMark reports each affected path
independently and blocks processing for the entire hard-link group without selecting a preferred
source, target, winner, or loser path.

______________________________________________________________________

## Missing vs unmatched inputs

TopMark distinguishes between **explicit literal paths** and **glob patterns**:

- **Explicit missing literal paths** (e.g., `fubar.py`) are treated as **hard input errors** and
  result in `FILE_NOT_FOUND (66)`.
- **Unmatched glob patterns** (e.g., `missing/**/*.py`) are treated as soft runtime-discovery
  diagnostics and do **not** cause a failure for processing commands ([`check`](commands/check.md),
  [`strip`](commands/strip.md)) (exit `SUCCESS (0)`).

This distinction ensures that typos in explicit inputs are surfaced, while flexible patterns that
match nothing do not cause runtime processing-command failures.

______________________________________________________________________

## Path inputs and path-based filtering

TopMark separates explicit processing inputs from path-based filters. Explicit processing inputs
define the paths that participate in discovery. Path-based filters then narrow those selected
inputs.

Explicit processing inputs are supplied by:

- positional `PATH` arguments
- `--files-from FILE`, which provides an explicit list of files to process

Path-based filtering controls are supplied by:

- `--include`, `--exclude` Include or exclude glob patterns.
- `--include-from`, `--exclude-from` Load patterns from files (one per line).

Stable path-filtering semantics:

- Positional arguments and paths loaded from `--files-from FILE` are resolved relative to the
  current working directory (CWD).
- Configuration discovery is evaluated earlier from the resolved discovery anchor; CWD-relative path
  parsing for filters does not create a separate project-chain discovery root.
- Unknown option-like tokens before the standard `--` delimiter are parser errors. Use `--` before
  literal path names that begin with a dash, for example `topmark check -- --generated.py`.
- Patterns in `--include`, `--exclude`, and files referenced by `--include-from` / `--exclude-from`
  are also resolved **relative to CWD**.
- Absolute patterns are not supported.
- Exclude rules take precedence over include rules.
- Path-based filtering is applied after explicit input collection and before file-type filtering.
- Existing filesystem inputs undergo filesystem-identity evaluation before runtime processing.
- Hard-linked selected paths are handled as processing-target eligibility failures. Each affected
  path is reported independently and blocked from processing; TopMark does not select a preferred
  source, target, winner, or loser path.
- Symlink spellings are not preserved for runtime identity, generated filesystem-related header
  metadata, or machine-readable path fields.

______________________________________________________________________

## STDIN support

File-processing commands support two STDIN modes when supplying file lists or content:

- **List mode**: provide newline-delimited paths or patterns via:
  - `--files-from -`
  - `--include-from -`
  - `--exclude-from -`
- **Content mode**: process a single virtual runtime file from STDIN content by passing `-` as the
  sole PATH together with `--stdin-filename NAME`

See [shared input modes](shared-options.md#shared-input-modes) for the full STDIN contract,
including why TopMark does not provide a `--stdin` option flag.

______________________________________________________________________

## Interaction with [`topmark probe`](commands/probe.md)

The [`topmark probe`](commands/probe.md) command uses the same runtime filtering pipeline and
discovery semantics described above.

As with `check` and `strip`, this runtime discovery and filtering pipeline starts after
configuration discovery has selected project-chain configuration sources from the resolved discovery
anchor.

This includes:

- path filtering
- file-type filtering
- canonical file-type identifier normalization and resolution
- ambiguity handling
- filesystem-identity evaluation and processing-path selection

However, unlike processing commands ([`check`](commands/check.md), [`strip`](commands/strip.md)),
[`probe`](commands/probe.md) also reports \*\*explicit inputs that were filtered out before runtime
file-type probing.

Additionally, [`probe`](commands/probe.md) treats unmatched glob patterns as filtered semantic
outcomes rather than silent runtime no-ops. As a result:

- Unmatched glob patterns are reported as `filtered` probe results (e.g.,
  `filtered: excluded_by_discovery_filter`).
- The command exits with `UNSUPPORTED_FILE_TYPE (69)`, reflecting incomplete runtime semantic
  resolution.

This differs from processing commands, which treat unmatched patterns as non-fatal diagnostics.

[`probe`](commands/probe.md) is read-only and diagnostic-only. It shares discovery and filtering
behavior with [`check`](commands/check.md) and [`strip`](commands/strip.md), but rejects mutation,
diff, reporting, and header-generation options that do not apply.

For example, when a path is excluded via `--exclude` or `exclude_patterns`,
[`topmark probe`](commands/probe.md) will still show it in the output as:

```text
<path>: <filtered> - filtered: excluded_by_path_filter
```

In machine-readable JSON and NDJSON output, these are represented as structured probe results with:

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

- `excluded_by_path_filter` - excluded by path-based include/exclude rules
- `excluded_by_file_type_filter` - excluded by file-type include/exclude rules
- `excluded_by_discovery_filter` - excluded before runtime probing, but exact category not
  identified
- `no_candidates` - no file-type candidates were found (e.g., unsupported extension)

Only explicitly requested runtime inputs (positional paths or `--files-from`) are reported this way.
Files excluded implicitly during recursive discovery are not enumerated.

For probe records that reach runtime probing, reported filesystem paths describe the selected
processing path. They do not guarantee preservation of the original CLI argument, glob match, or
symlink spelling.

If multiple selected paths are hard links to the same filesystem object, probe reports each affected
path independently as an unsupported processing target with reason `hard_link_duplicate`. TopMark
does not select a preferred source, target, winner, or loser path from the hard-link group.

______________________________________________________________________

## Filtering recipes

### Recipe: Process only Python and Markdown

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

### Recipe: Exclude generated/virtualenv folders

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

### Recipe: Include only `src/` and `tests/`

TOML:

```toml
[files]
include_patterns = ["src/**", "tests/**"]
```

### Recipe: Use include/exclude pattern files (portable across repos)

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

### Recipe: Exclude a specific file type after path filtering

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

### Recipe: Use an explicit file list as the input source (from Git)

This is an input-source recipe rather than a filter recipe. Include/exclude filters still apply
after TopMark collects the explicit file list.

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

### Recipe: Show only actionable files (would change)

```bash
topmark check --report actionable .
```

### Recipe: Include unsupported files in reporting

```bash
topmark check --report noncompliant .
topmark strip --report noncompliant .
```

______________________________________________________________________

## File-type filtering

TopMark supports file-type include/exclude filtering via:

- `--include-file-types / -t`
- `--exclude-file-types / -T`
- `include_file_types`
- `exclude_file_types`

File-type filters are evaluated after path-based filtering.

{% include-markdown "\_snippets/file-type-identifiers.md" %}

Plugins and integrations may declare file types in their own namespace, such as `acme:python`. This
allows independent ecosystems to define custom file types and register independent runtime header
processors without colliding with built-in TopMark identifiers.

Local identifiers are accepted only when they are unambiguous. If more than one registered file type
has the same local identifier, the local form is considered ambiguous and TopMark requires the
qualified form.

______________________________________________________________________

## Exit-code interaction

Filtering decisions can influence exit codes indirectly:

- Missing explicit inputs → `FILE_NOT_FOUND (66)`
- Unmatched glob patterns → no failure ([`check`](commands/check.md) / [`strip`](commands/strip.md),
  `SUCCESS (0)`), or `UNSUPPORTED_FILE_TYPE (69)` in [`probe`](commands/probe.md)

Missing explicit inputs take precedence over semantic runtime probe outcomes.

Hard-link processing policy participates through normal processing outcomes and diagnostics and does
not introduce dedicated filtering exit codes.

When multiple conditions occur, TopMark applies a deterministic exit-code priority model (see
[Exit Codes documentation](exit-codes.md)), where hard input and filesystem errors take precedence.

Invalid CLI usage (for example, unsupported options or inappropriate STDIN modes) is reported as a
usage error and takes precedence over filtering outcomes.

______________________________________________________________________

## Notes on configuration strictness

Filtering determines *which* runtime files participate in processing, while staged config-loading
validation determines whether a run is allowed to proceed.

{% include-markdown "\_snippets/config-strictness.md" %}

Effective strictness is controlled by:

1. CLI override (`--strict` / `--no-strict`)
1. TOML setting (`strict`)
1. default non-strict behavior

When strict config checking is enabled, configuration-loading validation warnings are treated as
errors and may cause the command to fail before processing files.

______________________________________________________________________

## See also

- [CLI overview](cli.md)
- [Configuration](configuration.md)
- [Shared options](shared-options.md)
- [Policies](policies.md)
- [Exit codes](exit-codes.md)
- [Configuration discovery, precedence, and policy](../configuration/discovery.md)
