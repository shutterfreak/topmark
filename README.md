<!--
topmark:header:start

  project      : TopMark
  file         : README.md
  file_relpath : README.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark

[![PyPI version](https://img.shields.io/pypi/v/topmark.svg)](https://pypi.org/project/topmark/)
[![GitHub release](https://img.shields.io/github/v/release/shutterfreak/topmark)](https://github.com/shutterfreak/topmark/releases)
[![Python Versions](https://img.shields.io/pypi/pyversions/topmark.svg)](https://pypi.org/project/topmark/)
[![CI](https://github.com/shutterfreak/topmark/actions/workflows/ci.yml/badge.svg)](https://github.com/shutterfreak/topmark/actions/workflows/ci.yml)
[![Documentation Status](https://readthedocs.org/projects/topmark/badge/?version=latest)](https://topmark.readthedocs.io/en/latest/?badge=latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Development Status](https://img.shields.io/badge/status-stable-brightgreen.svg)](https://pypi.org/project/topmark/)
[![Downloads](https://static.pepy.tech/badge/topmark)](https://pepy.tech/project/topmark)

**TopMark** is a dry-run-first Python CLI for keeping license, copyright, project, and file metadata
headers consistent across polyglot repositories.

It was built for real-world codebases where file headers must be safe to inspect, update, remove,
and automate across different languages, comment styles, documentation files, and CI workflows.

It helps teams avoid fragile one-off scripts by providing:

- comment-aware header rendering;
- layered configuration and policy controls;
- dry-run-by-default safety;
- stable CI-friendly exit codes;
- machine-readable output formats;
- transparent file-type resolution diagnostics;
- configuration, registry, and file-resolution introspection commands;
- and a public Python API for automation and integration.

______________________________________________________________________

## Quick start

Install TopMark from PyPI:

```bash
pip install topmark
```

Create a starter configuration:

```bash
topmark config init --root > topmark.toml
```

Preview whether TopMark would insert or update headers:

```bash
topmark check .
```

Preview the changes TopMark would insert or update:

```bash
topmark check --diff .
```

Apply the changes once the preview looks right:

```bash
topmark check --apply .
```

Remove TopMark-managed headers when needed:

```bash
topmark strip .
topmark strip --apply .
```

TopMark also provides diagnostics for understanding how files, configuration, and processors are
resolved:

```bash
topmark probe README.md
topmark config dump --show-layers
topmark registry filetypes
topmark registry processors
topmark registry bindings
```

TopMark never mutates files unless `--apply` is passed.

For a guided first setup, see:

- [Getting started (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/getting-started/).

______________________________________________________________________

## Why TopMark?

TopMark started from a simple need: manage consistent file headers in multi-language codebases
without relying on brittle custom scripts. It began with Python files, expanded to Markdown
documentation, and matured through the 0.x series into a general-purpose CLI for polyglot
repositories.

TopMark is useful when you need to:

- keep license and copyright headers consistent across source and documentation files;
- preview repository-wide changes before anything is written;
- preserve shebangs, BOMs, newline style, and file-specific comment syntax;
- configure behavior differently across nested projects or file types;
- inspect why a file was included, excluded, or matched to a specific processor;
- integrate header checks into CI, pre-commit, Git hooks, or custom automation;
- consume deterministic JSON or NDJSON output from scripts and tooling, with stable machine-readable
  path serialization.

The goal is not to replace formatters, linters, or license scanners. TopMark focuses on one job:
safe, deterministic, comment-aware file header management.

______________________________________________________________________

## Documentation

Full documentation is hosted on **Read the Docs**:\
👉 <https://topmark.readthedocs.io/en/latest/>

This README provides a compact overview for GitHub and PyPI. Detailed usage, configuration,
command-reference, API, CI/CD, and contributor documentation live in the generated documentation
site.

______________________________________________________________________

## Features

- Detect, insert, update, validate, and remove file headers across multiple file types
- Dry-run by default, with explicit `--apply` required for mutation
- Comment-aware rendering for line and block comment styles
- Preserves standard newline styles, shebangs, BOMs, and file-specific comment rules
- Idempotent behavior designed for repeatable CI and repository automation
- Layered configuration via `topmark.toml`, `pyproject.toml`, user config, explicit config files,
  and CLI overrides
- Policy controls for insertion, update, empty-file behavior, file-type filtering, and content
  probing
- Resolution diagnostics with `topmark probe`
- Layered configuration inspection with `topmark config dump --show-layers`
- Registry introspection with `topmark registry filetypes`, `topmark registry processors`, and
  `topmark registry bindings`
- Machine-readable JSON, NDJSON, and Markdown output where supported
- Stable exit-code contracts for CI and scripting
- Pre-commit, CI, and Git hook friendly
- Public Python API for programmatic access to all CLI commands
- Extensible registry and processor architecture for custom file types and header processors
- Strictly typed Python implementation using Pyright

______________________________________________________________________

## Example headers

TopMark adapts headers to the comment syntax of each supported file type.

### Dry-run diff preview

A dry-run preview makes the intended change explicit before files are modified:

```diff
--- src/example.py (current)    2026-05-23 09:37:03 +0000
+++ src/example.py (updated)    2026-05-23 09:37:18 +0000
@@ -1 +1,11 @@
+# topmark:header:start
+#
+#   project      : ACME Project
+#   file         : example.py
+#   file_relpath : src/example.py
+#   license      : MIT
+#   copyright    : (C) 2025 John Doe
+#
+# topmark:header:end
+
 print("Hello, World!")

```

Header rendering and placement rules for supported file types are documented in:

- [Header placement rules (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/header-placement/)

______________________________________________________________________

## Installation

### From PyPI

TopMark stable releases are published on [PyPI](https://pypi.org/project/topmark/):

```bash
pip install topmark
```

> [!NOTE] **Upgrading from 0.11.x or earlier**
>
> If you are upgrading from TopMark 0.11.x or earlier, review the migration guide before changing
> existing configuration, CI jobs, or pre-commit hooks:
>
> - [Upgrading to TopMark 1.0 (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/upgrading-to-1.0/)

### From source

For development setup from source, see:

- [Installation guide (hosted docs)](https://topmark.readthedocs.io/en/latest/install/)
- [Development documentation (hosted docs)](https://topmark.readthedocs.io/en/latest/dev/)

### Verify CLI

```bash
topmark version
topmark --help
```

For development builds between release tags, `topmark version` may report SCM-derived development
versions that include commit-based metadata.

______________________________________________________________________

## Usage

```bash
topmark [COMMAND] [OPTIONS] [PATHS]...
```

The most common workflow is:

```bash
topmark check .           # preview which files would change
topmark check --diff .    # preview unified diffs
topmark check --apply .   # add/update headers

topmark strip .           # preview which files would change
topmark strip --diff .    # preview unified diffs
topmark strip --apply .   # remove headers
```

Common commands:

| Command            | Purpose                                                 |
| ------------------ | ------------------------------------------------------- |
| `topmark check`    | Validate, preview, and optionally apply TopMark headers |
| `topmark strip`    | Preview and remove TopMark-managed headers              |
| `topmark probe`    | Explain file-type and processor resolution              |
| `topmark config`   | Inspect, validate, and generate configuration           |
| `topmark registry` | Inspect file types, processors, and bindings            |
| `topmark version`  | Print version and environment information               |

Useful diagnostics while adopting TopMark:

```bash
topmark probe README.md
topmark config dump --show-layers
topmark registry filetypes
```

All available commands, shared options, output formats, STDIN behavior, and exit codes are
documented in:

- [Command-line interface (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/cli/)
- [Command reference (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/commands/check/)
- [Exit codes (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/exit-codes/)

### Exit codes (CI / scripting)

TopMark uses a small, stable set of exit codes for automation:

- `SUCCESS (0)` - success (no changes needed or changes applied)
- `WOULD_CHANGE (3)` - dry-run indicates changes would be made (`check`, `strip`)
- `CONFIG_ERROR (78)` - configuration validation failed (`check`, `strip`, `probe`, `config check`)
- `USAGE_ERROR (64)` - CLI usage error
- invalid command/option combinations, positional paths on file-agnostic commands, and unsupported
  STDIN modes are reported as usage errors
- `CONFIG_ERROR (78)` - configuration error

Exit code `2` is reserved for Click-owned parser-level usage errors, such as unknown commands,
unknown options or invalid option values.

Other codes (for example `UNSUPPORTED_FILE_TYPE (69)`, `PIPELINE_ERROR (70)`, `IO_ERROR (74)`,
`PERMISSION_DENIED (77)`) are used for more specific runtime conditions after CLI usage has been
accepted.

For the complete, stable contract, see:

- [Exit codes (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/exit-codes/)
- [check command (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/commands/check/)
- [strip command (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/commands/strip/)

______________________________________________________________________

## Configuration and Policy

TopMark supports layered configuration discovery and policy-based control over header mutation.

Common configuration sources include:

- `topmark.toml`
- `pyproject.toml` under `[tool.topmark]`
- user configuration
- explicit `--config` files
- CLI options

A minimal project configuration looks like this:

```toml
[config]
root = true

[fields]
project = "ACME Project"
license = "MIT"

[header]
fields = ["file", "file_relpath", "project", "license"]
```

Generate a documented starter configuration:

```bash
topmark config init --root > topmark.toml
```

Use the CLI to inspect the effective configuration:

```bash
topmark config dump --show-layers
topmark config dump --show-layers --output-format json
```

Detailed configuration, policy, and filtering behavior is documented in:

- [Configuration guide (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/configuration/)
- [Configuration discovery and precedence (hosted docs)](https://topmark.readthedocs.io/en/latest/configuration/discovery/)
- [Policy guide (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/policies/)
- [Filtering (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/filtering/)
- [Example TOML document](https://github.com/shutterfreak/topmark/blob/main/src/topmark/toml/topmark.example.toml)

______________________________________________________________________

## Pre-commit and CI Integration

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

For CI validation, run TopMark without `--apply`:

```bash
topmark config check --strict
topmark check .
```

Exit code `2` means files would require header updates.

Detailed integration guidance is documented in:

- [Getting started (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/getting-started/)
- [Pre-commit integration (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/pre-commit/)
- [CI integration (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/ci/)
- [Exit codes (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/exit-codes/)

______________________________________________________________________

## Public API

TopMark exposes a public Python API for programmatic checks, stripping, probing, and registry
discovery.

Public API callers should use the functions and DTOs exposed from `topmark.api`. Runtime helpers,
resolver internals, and pipeline contexts are implementation details.

Example dry-run check:

```python
from pathlib import Path

from topmark import api

result = api.check(
    [Path("src")],
    apply=False,
    report="actionable",
)

print(result.summary)
print(result.had_errors)
```

For read-only resolution diagnostics, use `api.probe()`:

```python
from pathlib import Path

from topmark import api

result = api.probe([Path("README.md")])

for file_result in result.files:
    print(file_result.path, file_result.status, file_result.reason)
```

For API details, see:

- [Public API (hosted docs)](https://topmark.readthedocs.io/en/latest/api/public/)
- [API reference (hosted docs)](https://topmark.readthedocs.io/en/latest/api/internals/topmark/)
- [Registry model (hosted docs)](https://topmark.readthedocs.io/en/latest/dev/registry-model/)

______________________________________________________________________

## Packaging and Versioning

TopMark uses Git-tag-driven package versions via `setuptools-scm`. Versions are derived from Git
tags at build time rather than maintained manually in `pyproject.toml`.

Stable releases are published to PyPI, and pre-releases are validated through TestPyPI before
promotion.

For detailed release architecture and maintainer guidance, see:

- [Release process (hosted docs)](https://topmark.readthedocs.io/en/latest/dev/release-process/)
- [Release workflow (hosted docs)](https://topmark.readthedocs.io/en/latest/ci/release-workflow/)
- [CI/CD documentation (hosted docs)](https://topmark.readthedocs.io/en/latest/ci/)

______________________________________________________________________

## Development

For day-to-day development, use the local `.venv` for editor integration and interactive work.
Automated testing, typing, documentation, and validation run in isolated environments managed by
`nox`.

Common validation commands:

```bash
make pytest
make test
make docs-build
make verify
```

For contributor setup and validation details, see:

- [Contributing (hosted docs)](https://topmark.readthedocs.io/en/latest/contributing/)
- [Installation guide (hosted docs)](https://topmark.readthedocs.io/en/latest/install/)
- [CI/CD and validation documentation (hosted docs)](https://topmark.readthedocs.io/en/latest/ci/)
- [Documentation conventions (hosted docs)](https://topmark.readthedocs.io/en/latest/dev/documentation-conventions/)

______________________________________________________________________

## License

MIT License © 2025 Olivier Biot

> See [LICENSE](LICENSE)

______________________________________________________________________

**TopMark** - consistent headers for consistent projects.
