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

TopMark ships a hook manifest so you can run header checks in Git workflows and CI. This page covers
setup, recommended patterns, and troubleshooting.

______________________________________________________________________

## Quick start (consumer repos)

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

The hook manifest intentionally uses minimal defaults. All behavioral flags (such as `--summary`,
`--report`, policy options, or output mode) should be supplied by consuming repositories via the
hook’s `args:` configuration.

For the `topmark-check` hook (which runs `topmark check`), consumers may also pass policy options
such as `--header-mutation-mode`, `--allow-header-in-empty-files`, or `--empty-insert-mode` when
they need command-specific behavior on top of the resolved config.

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

> Tip: Keep human banners at `INFO` level in TopMark and use `--quiet` in hooks to avoid repeated
> banners in batched runs.

**Run once per repo** by setting `pass_filenames: false` in the hook manifest and letting TopMark
perform its own file discovery from config:

```yaml
- id: topmark-check
  entry: topmark check
  pass_filenames: false
```

### About args

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

Notes:

- `args:` is appended to the hook’s `entry`.
- Prefer `args:` over copying a full `entry:` in the consumer config; it stays compatible when the
  hook entry changes.
- If you need TopMark to run once per repo (self-discovery), combine `pass_filenames: false` with
  `args:` as needed.

______________________________________________________________________

## Recommended patterns

### CI-friendly checks

```bash
# Focus output on files that would change
topmark check --report actionable
```

You can also pass `--summary` to only receive a summary instead of per-file diagnostics.

### Narrow file scope in consuming repos

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

Ensure the default config is loaded via **package resources** (TopMark already does) and that the
file is included as package data. In `pyproject.toml`:

```toml
[tool.setuptools.package-data]
"topmark.config" = ["topmark-example.toml"]
```

### Test your hook locally

```bash
# Uses the committed manifest from the current repo
topmark version
pre-commit clean
pre-commit try-repo . topmark-check --all-files --verbose
```
