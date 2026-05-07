<!--
topmark:header:start

  project      : TopMark
  file         : pre-commit.md
  file_relpath : docs/usage/pre-commit.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Using TopMark with pre-commit

Pre-commit integration allows TopMark to participate in:

- local Git workflows
- CI validation
- staged-file checks
- repository-wide remediation
- policy enforcement during commits and pushes

See also:

- [CLI overview](cli.md)
- [Configuration](configuration.md)
- [Filtering](filtering.md)
- [Policies](policies.md)
- [Exit codes](exit-codes.md)

TopMark ships a hook manifest so you can run header checks in Git workflows and CI. This page covers
setup, recommended patterns, and troubleshooting.

Hook execution uses the same resolver, filtering, policy, and configuration semantics as normal CLI
execution.

______________________________________________________________________

## Quick start (consumer repos)

For canonical file-type identifier semantics and configuration behavior, see
[Configuration](configuration.md#file-type-identifiers).

Add TopMark to a project's `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/shutterfreak/topmark
    rev: v0.12.0   # pin to a released tag
    hooks:
      - id: topmark-check
        # Optional: limit scope to supported text types
        # files: '\.(py|md|toml|ya?ml|sh|Makefile)$'
        args: ["--report", "actionable", "--summary"]
```

Install and run:

```bash
pre-commit install
pre-commit run --all-files
```

______________________________________________________________________

## Hooks provided by TopMark

TopMark provides two pre-commit hooks to help manage file headers:

- **`topmark-check`** — non-destructive validation. Fails if headers need changes.
  - Entry: `topmark check`
- **`topmark-apply`** — destructive fix; requires `--apply`. Marked `manual` so it only runs when
  explicitly invoked.
  - Entry: `topmark check --apply`

### Hook policy

By default:

- **`topmark-check`** runs automatically at `pre-commit` and `pre-push`.\
  It validates headers and fails if changes are needed.
- **`topmark-apply`** is restricted to the **manual** stage.\
  It may modify files and should only be invoked explicitly by developers.

This policy ensures safety in CI and everyday workflows.\
Teams that want formatter-like behavior (similar to Black or Prettier) may choose to enable
`topmark-apply` at `pre-commit` once the repository is clean.

TopMark intentionally defaults to non-destructive behavior unless `--apply` is explicitly enabled.

The hook manifest intentionally uses minimal defaults. All behavioral flags (such as `--summary`,
`--report`, policy options, or output mode) should be supplied by consuming repositories via the
hook’s `args:` configuration.

TopMark performs whole-source TOML schema validation during hook execution; any TOML-source
diagnostics are included in the reported config diagnostics.

Consumers can control configuration validation strictness using `--strict` / `--no-strict`. This
overrides the effective `strict_config_checking` setting resolved from TOML sources for the duration
of the hook run.

In the current implementation, this strictness is applied across staged config-loading/preflight
validation (TOML-source, merged-config, and runtime-applicability diagnostics), while the reported
diagnostics remain the flattened compatibility view derived from staged validation logs. For 1.0,
this boundary is intentional: staged validation remains primarily internal, while hook output
exposes only the flattened compatibility diagnostics contract.

For the `topmark-check` hook (which runs [`topmark check`](commands/check.md)), consumers may also
pass policy options such as `--header-mutation-mode`, `--allow-header-in-empty-files`, or
`--empty-insert-mode` when they need command-specific behavior on top of the resolved config.

These options follow the same policy-resolution and file-type identifier rules as normal CLI
execution.

Invoke the manual hook locally:

```bash
# Run on the whole repo
pre-commit run topmark-apply --all-files --hook-stage manual

# Or target specific files
pre-commit run topmark-apply --files path/to/file1 path/to/file2 --hook-stage manual
```

______________________________________________________________________

## Pre-commit and files

Pre-commit **batches filenames** to avoid OS argument-length limits (ARG_MAX). Your hook may run
multiple times per invocation (for different batches). This is expected.

TopMark applies the same filtering pipeline during hook execution:

1. path filtering
1. file-type filtering
1. resolver and probe evaluation
1. policy resolution

{% include-markdown "\_snippets/output-contract.md" %}

**Run once per repo** by setting `pass_filenames: false` in the hook manifest and letting TopMark
perform its own file discovery from config:

```yaml
- id: topmark-check
  entry: topmark check
  pass_filenames: false
```

### About args

Arguments passed through `args:` behave exactly like normal CLI arguments.

Pre-commit supports an `args:` list **in consumer repos** (in `.pre-commit-config.yaml`). Because
TopMark’s hook manifest uses minimal defaults, consumer `args:` are the primary mechanism for
configuring TopMark’s behavior when run under pre-commit.

Example (consumer repo):

```yaml
repos:
  - repo: https://github.com/shutterfreak/topmark
    rev: v0.10.1
    hooks:
      - id: topmark-check
        args: ["--report", "noncompliant", "--output-format=ndjson"]
```

For the manual hook:

```yaml
- id: topmark-apply
  args: ["--report", "actionable"]
```

Examples using canonical qualified identifiers:

```yaml
- id: topmark-check
  args: ["--include-file-types", "topmark:python"]
```

Notes:

- `args:` is appended to the hook’s `entry`.

- Prefer `args:` over copying a full `entry:` in the consumer config; it stays compatible when the
  hook entry changes.

- If you need TopMark to run once per repo (self-discovery), combine `pass_filenames: false` with
  `args:` as needed.

- TEXT-only controls such as `-v` / `--verbose` and `-q` / `--quiet` affect only human TEXT output;
  Markdown and machine formats ignore these flags.

### File-type identifier behavior

{% include-markdown "\_snippets/file-type-identifiers.md" %}

Pre-commit hook arguments, TOML configuration, and runtime policy evaluation all share the same
canonical identifier semantics.

______________________________________________________________________

## Recommended patterns

### CI-friendly checks

These patterns are especially useful for repository-wide validation in CI.

```bash
# Focus output on files that would change
topmark check --report actionable
```

```bash
# Suppress TEXT output in CI and rely on exit status
topmark check --report actionable --quiet
```

During these runs, configuration loading includes per-source TOML validation before layered config
merging, so schema issues are surfaced alongside normal check diagnostics.

```bash
# Enforce strict config validation in CI
# (warnings are treated as errors)
topmark check --report actionable --strict
```

You can also pass `--summary` to only receive a summary instead of per-file diagnostics.

### Narrow file scope in consuming repos

______________________________________________________________________

## Exit codes in pre-commit hooks

TopMark hooks rely on the CLI exit-code contract to signal success or failure to pre-commit and CI.

- **`topmark-check` (non-destructive)**:

  - Exits with `SUCCESS (0)` when all headers are up-to-date.
  - Exits with `WOULD_CHANGE (2)` when headers would be added/updated in dry-run mode (this causes
    the hook to fail as intended).
  - May exit with other non-zero codes for errors, for example:
    - `FILE_NOT_FOUND (66)` for explicit missing input paths
    - `IO_ERROR (74)` or `PERMISSION_DENIED (77)` for filesystem issues
    - `CONFIG_ERROR (78)` for configuration problems

- **`topmark-apply` (manual, destructive)**:

  - Exits with `SUCCESS (0)` on successful application of changes.
  - May exit with the same error codes as above if issues occur during processing.

Notes:

- Pre-commit treats any non-zero exit code as a failure; this is expected for `topmark-check` when
  changes are needed (`WOULD_CHANGE (2)`).
- Use `--quiet` in CI to suppress TEXT output and rely solely on exit status.
- For full details and edge cases (mixed-result runs, precedence), see:
  - [`Exit codes`](./exit-codes.md)
  - [`check` command](./commands/check.md)
  - [`strip` command](./commands/strip.md)

```yaml
hooks:
  - id: topmark-check
    files: '\.(py|md|toml|ya?ml|sh|Makefile)$'
    args: ["--report", "actionable"]
```

______________________________________________________________________

## Troubleshooting

### "uses deprecated stage names (commit, push)"

Use modern names in the manifest: `pre-commit` and `pre-push`.

### `FileNotFoundError` when loading `topmark-example.toml`

Ensure the bundled example TopMark TOML resource is loaded via **package resources** (TopMark
already does) and that the file is included as package data. In `pyproject.toml`:

```toml
[tool.setuptools.package-data]
"topmark.toml" = ["topmark-example.toml"]
```

### Test your hook locally

```bash
# Uses the committed manifest from the current repo
topmark version
pre-commit clean
pre-commit try-repo . topmark-check --all-files --verbose
```

______________________________________________________________________

## Related pages

- [CLI overview](cli.md)
- [Configuration](configuration.md)
- [Configuration discovery](../configuration/discovery.md)
- [Filtering](filtering.md)
- [Policies](policies.md)
- [Global options](global-options.md)
- [Exit codes](exit-codes.md)
