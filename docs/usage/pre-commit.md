<!--
topmark:header:start

  file         : pre-commit.md
  file_relpath : docs/usage/pre-commit.md
  project      : TopMark
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
    rev: v0.2.0   # pin to a released tag
    hooks:
      - id: topmark-check
        # Optional: limit scope to supported text types
        # files: '\.(py|md|toml|ya?ml|sh|Makefile)$'
```

Install and run:

```bash
pre-commit install
pre-commit run --all-files
```

______________________________________________________________________

## Hooks provided by TopMark

- **`topmark-check`** — non-destructive validation. Fails if headers need changes.
  - Recommended on `pre-commit` and `pre-push`.
  - Entry: `topmark check --skip-compliant --quiet`
- **`topmark-apply`** — destructive fix; requires `--apply`. Marked `manual` so it only runs when
  explicitly invoked.
  - Entry: `topmark apply --apply --quiet`

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
  entry: topmark check --skip-compliant --quiet
  pass_filenames: false
```

______________________________________________________________________

## Recommended patterns

### CI-friendly checks

```bash
# Only show issues; ignore unsupported-but-recognized formats (e.g., strict JSON)
topmark check --skip-compliant --skip-unsupported
```

### Narrow file scope in consuming repos

```yaml
hooks:
  - id: topmark-check
    files: '\.(py|md|toml|ya?ml|sh|Makefile)$'
```

______________________________________________________________________

## Troubleshooting

### "uses deprecated stage names (commit, push)"

Use modern names in the manifest: `pre-commit` and `pre-push`.

### `FileNotFoundError` when loading `topmark-default.toml`

Ensure the default config is loaded via **package resources** (TopMark already does) and that the
file is included as package data. In `pyproject.toml`:

```toml
[tool.setuptools.package-data]
"topmark.config" = ["topmark-default.toml"]
```

### Test your hook locally

```bash
# Uses the committed manifest from the current repo
topmark --version
pre-commit clean
pre-commit try-repo . topmark-check --all-files --verbose
```
