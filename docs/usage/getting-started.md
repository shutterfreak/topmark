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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

## 3. Preview header compliance

Check if the files have TopMark headers compliant with the settings defined.

```bash
topmark check .
```

You can also process an explicit list of files:

```bash
find src -name '*.py' > files.txt
topmark check --files-from files.txt
```

`--files-from` may be used on its own or combined with positional paths.

> [!NOTE]
>
> TopMark evaluates filesystem identity before processing files. Filesystem-identity normalization
> resolves equivalent path spellings, such as symlink spellings, to the selected processing path
> used for runtime processing and machine-readable output.
>
> Configuration discovery is evaluated earlier. When TopMark discovers project configuration files,
> it starts from a discovery anchor (the current working directory or an input path) and walks the
> project chain from the resolved anchor location.
>
> Hard-link policy is evaluated as a processing-target eligibility check. If multiple selected paths
> refer to the same filesystem object through hard links, TopMark reports each affected path
> independently and blocks processing for the entire hard-link group without selecting a preferred
> source, target, winner, or loser path.

______________________________________________________________________

## 4. Preview changes (unified diff)

Preview the precise file changes TopMark would make by requesting unified diffs:

```bash
topmark check --diff .
```

> [!NOTE]
>
> `--diff` performs a dry-run preview and is therefore mutually exclusive with `--apply`. Human TEXT
> and Markdown output render unified diffs, while JSON and NDJSON expose structured diff payloads
> for machine-readable consumers. See [Machine-readable output](./machine-output.md) for the JSON
> and NDJSON payload contracts.

______________________________________________________________________

## 5. Apply changes

You can add / update the TopMark headers in files by specifying `--apply`:

```bash
topmark check --apply .
```

> [!TIP]
>
> Generated filesystem-related header fields such as `file_relpath` and `file_abspath` describe the
> selected processing target. If a file is reached through a symlink, header metadata reflects the
> resolved target TopMark reads and writes.
>
> Project configuration discovery follows the same resolved-anchor model. Symlink spellings used to
> reach a working directory or input path do not create separate project-chain discovery roots.
>
> Files blocked by processing-target eligibility checks, such as hard-linked processing targets, are
> not modified and therefore do not receive updated header metadata.

______________________________________________________________________

## 6. Validate repeatability

Running `topmark check .` again should now report no pending changes.

This idempotent behavior is important for CI and repeatable repository automation workflows.

______________________________________________________________________

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

______________________________________________________________________

## 8. Add CI validation

Validate repository headers in CI:

```bash
topmark check .
```

Exit code `3` means files would require header updates.

Further reading:

- [Exit codes](./exit-codes.md)
- [CI integration](./ci.md)

______________________________________________________________________

## Next steps

Continue with:

- [Configuration discovery and precedence](./configuration.md)
- [Filtering](./filtering.md)
- [Machine-readable output](./machine-output.md)
- [Pre-commit integration](./pre-commit.md)
- [CI integration](./ci.md)
- [Exit codes](./exit-codes.md)
- [Command overview](./cli.md)
- [Public Python API](../api/public.md)
