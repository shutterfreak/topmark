<!--
topmark:header:start

  project      : TopMark
  file         : upgrading-to-1.0.md
  file_relpath : docs/usage/upgrading-to-1.0.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Upgrading to TopMark 1.0

TopMark 1.0 is a stable release, but it is not a drop-in replacement for the older 0.11.x command,
configuration, and output contracts.

This guide summarizes the changes most likely to affect users upgrading from the latest stable
0.11.x release to 1.0. It focuses on practical migration steps for CLI usage, pre-commit hooks, TOML
configuration, output snapshots, and automation.

{% include-markdown "\_snippets/terminology.md" %}

______________________________________________________________________

## Who should read this

Read this page if you:

- have an existing `topmark.toml` or `[tool.topmark]` configuration;
- run TopMark from shell scripts or CI;
- use TopMark through pre-commit hooks;
- compare TopMark TEXT or Markdown output in tests;
- parse TopMark JSON or NDJSON output;
- use registry, configuration, or low-level runtime APIs.

If you are installing TopMark for the first time, start with [Installation](../install.md) and the
[CLI overview](./cli.md) instead.

______________________________________________________________________

## Recommended upgrade workflow

Use the upgrade as a validation pass rather than immediately applying changes.

1. Install TopMark 1.0 in a clean environment.

1. Review your `topmark.toml` or `[tool.topmark]` configuration.

1. Validate the configuration strictly:

   ```bash
   topmark config check --strict -v
   ```

1. Inspect the discovered and resolved runtime configuration:

   ```bash
   topmark config dump --show-layers -v
   ```

1. Run a dry-run compliance check:

   ```bash
   topmark check --report noncompliant .
   ```

1. Update shell scripts, CI jobs, and pre-commit hook arguments.

1. Regenerate expected output snapshots if your tests assert human or machine-readable output.

1. Apply changes only after the dry-run output is understood:

   ```bash
   topmark check --apply .
   ```

______________________________________________________________________

## CLI option changes

TopMark 1.0 makes command applicability stricter. Options are now exposed only on commands where
they are meaningful.

Important changes include:

- `--skip-compliant` was replaced by `--report actionable`.
- `--skip-unsupported` was replaced by `--report noncompliant`.
- `--add-only` and `--update-only` were replaced by `--header-mutation-mode`.
- Verbosity and color options moved from the root CLI group to individual commands.
- `-v` / `--verbose` affects only TEXT rendering.
- `-q` / `--quiet` affects only TEXT rendering on commands that explicitly support quiet mode.
- Markdown, JSON, and NDJSON output ignore TEXT-oriented verbosity and quiet controls.
- Informational content-producing commands such as `topmark version`, `topmark config defaults`,
  `topmark config init`, and registry commands do not expose `--quiet`.
- Path-processing commands do not expose a `--stdin` flag; use `-` plus `--stdin-filename` for
  content STDIN mode.

Before:

```bash
topmark check --skip-compliant --add-only src/
```

After:

```bash
topmark check --report actionable --header-mutation-mode add_only src/
```

Before:

```bash
topmark check --skip-unsupported .
```

After:

```bash
topmark check --report noncompliant .
```

See [CLI overview](./cli.md), [shared options](./shared-options.md), and
[`topmark check`](./commands/check.md) for the current command contracts.

______________________________________________________________________

## Pre-commit hook changes

Pre-commit hooks use the same CLI option and runtime policy model as normal command-line execution.
If your `.pre-commit-config.yaml` passes older TopMark options through `args:`, update those options
before enabling TopMark 1.0 in CI.

Common migrations:

```yaml
# Before
args: ["--skip-compliant", "--add-only"]
```

```yaml
# After
args: ["--report", "actionable", "--header-mutation-mode", "add_only"]
```

```yaml
# Before
args: ["--skip-unsupported"]
```

```yaml
# After
args: ["--report", "noncompliant"]
```

Recommended hook validation workflow:

```bash
pre-commit run topmark-check --all-files
pre-commit run topmark-probe --all-files --hook-stage manual
```

Use `topmark-probe` when files are unexpectedly skipped, filtered, unresolved, or bound to a
different processor than expected.

See [pre-commit integration](./pre-commit.md) for the current hook behavior.

______________________________________________________________________

## Configuration file changes

TopMark 1.0 reorganizes configuration into clearer TOML, layered runtime configuration, runtime
policy, and writer/runtime boundaries.

The most important migration areas are:

- source-local config options now live under `[config]`;
- header fields now live under `[header]` and custom values under `[fields]`;
- generated-header formatting lives under `[formatting]`;
- runtime write preferences live under `[writer]`;
- mutation and probing policy lives under `[policy]` and `[policy_by_type.<file_type>]`;
- file discovery and file type filters live under `[files]`;
- file type identifiers normalize to canonical qualified file type identities internally.

### Discovery root moved to `[config]`

In older configuration, `root = true` could be shown at the top level.

Before:

```toml
root = true
```

After:

```toml
[config]
root = true
```

For `pyproject.toml`, use:

```toml
[tool.topmark.config]
root = true
```

### Strict configuration validation

TopMark 1.0 supports stricter staged configuration-loading validation.

```toml
[config]
strict = true
```

For one-off validation, prefer the CLI command:

```bash
topmark config check --strict -v
```

This reports unknown sections, unknown keys, malformed known sections, malformed nested policy
sections, ambiguous file type identifiers, and related configuration-loading diagnostics before the
runtime pipeline mutates files.

### Header fields and custom fields

The rendered field list belongs under `[header]`:

```toml
[header]
fields = ["file", "file_relpath"]
```

Custom field values belong under `[fields]`:

```toml
[fields]
project = "TopMark"
license = "MIT"
copyright = "(c) 2026 Your Name"
```

### Removed or replaced policy fields

Older boolean policy flags were replaced by explicit policy values.

Before:

```toml
[policy]
add_only = true
update_only = false
```

After:

```toml
[policy]
header_mutation_mode = "add_only"
```

Supported `header_mutation_mode` values are:

- `all` - allow both insert and update;
- `add_only` - insert missing headers only;
- `update_only` - update existing headers only.

### Empty-file policy is more explicit

TopMark 1.0 separates whether empty files may receive headers from how "empty" is interpreted.

```toml
[policy]
allow_header_in_empty_files = false
empty_insert_mode = "logical_empty"
```

Supported `empty_insert_mode` values include:

- `bytes_empty`;
- `logical_empty`;
- `whitespace_empty`.

### Content probing policy

Runtime content probing is controlled by:

```toml
[policy]
allow_content_probe = true
```

Disable this only when you want name/extension-only runtime file-type detection.

### Writer configuration

Writer behavior is now represented as runtime write preferences under `[writer]`.

```toml
[writer]
strategy = "atomic"
```

Supported values:

- `atomic` - write to a temporary file and replace the original;
- `inplace` - overwrite the original file in place.

### File discovery and file type filters

File discovery and runtime selection options belong under `[files]`.

```toml
[files]
include_patterns = ["src/**", "tests/**"]
exclude_patterns = [".venv/**", "**/__pycache__/**"]
include_file_types = ["python", "markdown"]
exclude_file_types = ["topmark:html"]
```

Local file type identifiers such as `python` are accepted only when unambiguous. For shared
configuration, prefer qualified file type identities such as `topmark:python`.

______________________________________________________________________

## Policy and reporting changes

TopMark 1.0 separates runtime policy from human reporting.

Runtime policy controls what TopMark may do:

```toml
[policy]
header_mutation_mode = "all"
allow_header_in_empty_files = false
allow_content_probe = true
```

Human reporting controls what TopMark shows in TEXT output:

```bash
topmark check --report all .
topmark check --report actionable .
topmark check --report noncompliant .
```

Use:

- `--report all` to show all relevant per-file results;
- `--report actionable` to focus on files that would change, changed, failed, or need attention;
- `--report noncompliant` to include actionable files plus unsupported file types.

This replaces the older `skip`-oriented reporting model.

______________________________________________________________________

## Output format changes

All output formats changed during the 1.0 stabilization work.

Expect differences in:

- TEXT output grouping and summaries;
- Markdown output layout;
- JSON top-level keys;
- NDJSON record kinds;
- registry output shape;
- configuration diagnostics;
- probe result records;
- summary rows.

If your tests compare TopMark output, regenerate snapshots after reviewing the new output manually.

TEXT output is intended for humans. JSON and NDJSON output are intended for tools. Do not parse TEXT
output in automation.

______________________________________________________________________

## Machine-readable JSON/NDJSON changes

TopMark 1.0 treats machine-readable output as a stable integration surface, but older 0.11.x JSON or
NDJSON consumers must be updated.

Important changes include:

- machine output is domain-scoped and schema-driven;
- machine output does not encode process exit status;
- consumers must inspect the CLI exit code separately;
- summary payloads use flat rows with `outcome`, `reason`, and `count`;
- `topmark config check` uses an explicit `config_check` payload/record kind;
- `topmark config dump --show-layers` emits layered provenance before the final runtime
  configuration;
- registry JSON output uses flattened collection keys such as `filetypes`, `processors`, and
  `bindings`;
- NDJSON uses singular domain-specific record kinds;
- file type identities are emitted as canonical qualified keys when resolved.

Recommended validation commands:

```bash
topmark check --output-format json .
topmark check --output-format ndjson .
topmark config check --output-format json --strict .
topmark config dump --show-layers --output-format json .
topmark probe --output-format json .
```

See [machine-readable output](../dev/machine-output.md) and
[machine-readable format conventions](../dev/machine-formats.md) for the stable 1.x machine-output
contracts.

______________________________________________________________________

## Validate your configuration

Use strict validation before running mutating commands:

```bash
topmark config check --strict -v
```

This command validates the effective runtime configuration and reports configuration-loading
diagnostics.

Use this when:

- migrating from 0.11.x;
- updating `topmark.toml` or `[tool.topmark]`;
- adding `policy_by_type` entries;
- adding file type filters;
- debugging ambiguous or unknown file type identifiers;
- preparing CI or pre-commit integration.

______________________________________________________________________

## Inspect the resolved runtime configuration

Use layered provenance output to understand which configuration sources contributed to the final
runtime configuration:

```bash
topmark config dump --show-layers -v
```

This is especially useful when:

- several `topmark.toml` or `pyproject.toml` files are discovered;
- `[config].root = true` affects discovery;
- CLI `--config` files are used;
- CLI overrides change the final runtime behavior;
- file type filters or per-file-type policies do not behave as expected.

______________________________________________________________________

## Migration checklist

Before tagging your own repository as upgraded to TopMark 1.0:

- Replace removed CLI options:
  - `--skip-compliant` -> `--report actionable`
  - `--skip-unsupported` -> `--report noncompliant`
  - `--add-only` / `--update-only` -> `--header-mutation-mode`
- Move discovery options such as `root` and `strict` under `[config]`.
- Replace `[policy].add_only` / `[policy].update_only` with `[policy].header_mutation_mode`.
- Review `[writer]`, `[policy]`, `[policy_by_type]`, and `[files]` sections against the generated
  starter config.
- Prefer qualified file type identities in shared configuration where ambiguity is possible.
- Run:
  - `topmark config check --strict -v`
  - `topmark config dump --show-layers -v`
  - `topmark check --report noncompliant .`
- Update pre-commit hook `args:` entries.
- Update CI scripts and expected exit-code handling.
- Regenerate TEXT, Markdown, JSON, or NDJSON snapshots after reviewing the new output.

______________________________________________________________________

## Related pages

- [Installation](../install.md)
- [CLI overview](./cli.md)
- [Shared options](./shared-options.md)
- [Configuration](./configuration.md)
- [Configuration discovery, precedence, and policy](../configuration/discovery.md)
- [Policies](./policies.md)
- [Filtering](./filtering.md)
- [Pre-commit integration](./pre-commit.md)
- [Exit codes](./exit-codes.md)
- [Machine-readable output](../dev/machine-output.md)
- [Machine-readable format conventions](../dev/machine-formats.md)
