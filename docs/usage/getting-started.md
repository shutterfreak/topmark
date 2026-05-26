<!--
topmark:header:start

  project      : TopMark
  file         : getting-started.md
  file_relpath : docs/usage/getting-started.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Getting started

> A five-minute path for adding TopMark safely to a repository.

## 1. Install TopMark

Stable releases are published on [PyPI](https://pypi.org/project/topmark/):

```bash
pip install topmark
```

Verify that the CLI is available:

```bash
# Display the installed TopMark version:
topmark version

# Display the command-line help:
topmark --help
```

## 2. Create a starter configuration

TopMark reads configuration from either:

- `topmark.toml`
- `pyproject.toml`

A minimal repository-level `topmark.toml` configuration may look like this:

```toml
[config]
root = true

[fields]
project = "MyProject"
license = "MIT"

[header]
fields = [
  "file",
  "file_relpath",
  "project",
  "license",
]
```

> [!NOTE]
>
> When using `pyproject.toml`, TopMark settings must be placed under the `tool.topmark` table prefix
> (for example: `[config]` becomes `[tool.topmark.config]`).

Generate a documented starter configuration:

### Repository-level configuration

Generate a `topmark.toml` configuration file at the repository root:

```bash
topmark config init --root >> topmark.toml
```

Alternatively, generate configuration inside `pyproject.toml`:

```bash
topmark config init --root --pyproject >> pyproject.toml
```

The `--root` option marks the repository boundary for TopMark configuration resolution and prevents
configuration discovery from continuing into parent directories.

### Local overrides

Generate a local override configuration:

```bash
topmark config init >> topmark.toml
```

Local overrides usually should not specify `--root`, so repository-level settings continue to apply
before local overrides are merged.

### Git repositories

When using `git`, you may want TopMark to:

- ignore `.git/`
- respect `.gitignore`

Add the following settings:

```toml
[files]
exclude_from = [".gitignore"]
exclude_patterns = [".git/"]
```

Further reading:

- [Configuration discovery, precedence, and policy](./configuration.md)
- [`topmark config init`](./commands/config/init.md)
- [`topmark config check`](./commands/config/check.md)
- [`topmark config dump`](./commands/config/dump.md)
- [`topmark config defaults`](./commands/config/defaults.md)
- [Filtering](filtering.md)

## 3. Preview header compliance

Check if the files have TopMark headers compliant with the settings defined.

```bash
topmark check .
```

## 4. Preview changes (unified diff)

The precise changes TopMark will apply to files are generated as unified diff when specifying the
`--diff` option:

```bash
topmark check --diff .
```

## 5. Apply changes

You can add / update the TopMark headers in files by specifying `--apply`:

```bash
topmark check --apply .
```

## 6. Validate repeatability

Running `topmark check .` again should now report no pending changes.

This idempotent behavior is important for CI and repeatable repository automation workflows.

## 7. Add pre-commit validation

Add TopMark to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/shutterfreak/topmark
    rev: v1.0.0
    hooks:
      - id: topmark-check
```

Install hooks:

```bash
pre-commit install
pre-commit run --all-files
```

For advanced hook usage and manual apply hooks, see:

- [Pre-commit integration](pre-commit.md)

## 8. Add CI validation

Validate repository headers in CI:

```bash
topmark check .
```

Exit code `2` means files would require header updates.

Further reading:

- [Exit codes](./exit-codes.md)
- [CI integration](./ci.md)

## Next steps

Continue with:

- [Configuration discovery and precedence](./configuration.md)
- [Filtering](./filtering.md)
- [Pre-commit integration](./pre-commit.md)
- [CI integration](./ci.md)
- [Exit codes](./exit-codes.md)
- [Command overview](./cli.md)
- [Public Python API](../api/public.md)
