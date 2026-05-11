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
[![Development Status](https://img.shields.io/badge/status-beta-orange.svg)](https://pypi.org/project/topmark/)
[![Downloads](https://static.pepy.tech/badge/topmark)](https://pepy.tech/project/topmark)

**TopMark** is a command-line tool to inspect, insert, validate, and manage file headers in diverse
codebases.\
It maintains consistent metadata across files by supporting multiple comment styles, configuration
formats, dry-run safety, and transparent resolution diagnostics.

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
- Comment-aware rendering for line and block comment styles
- Dry-run by default, with explicit `--apply` required for mutation
- Layered configuration via `topmark.toml`, `pyproject.toml`, user config, explicit config files,
  and CLI overrides
- Policy controls for insertion, update, empty-file behavior, file-type filtering, and content
  probing
- Resolution diagnostics with `topmark probe`
- Machine-readable JSON, NDJSON, and Markdown output where supported
- Stable exit-code contracts for CI and scripting
- Public Python API for programmatic access to all CLI commands
- Plugin architecture which enables extending support for custom file types and header processors
- Pre-commit, CI, and Git hook friendly
- Preserves standard newline styles, shebangs, BOMs, and file-specific comment rules
- Strictly typed Python implementation using Pyright

______________________________________________________________________

## Example headers

TopMark adapts headers to the comment syntax of each supported file type.

### Bash / Shell

```bash
#!/bin/bash

# topmark:header:start
#
#   project   : TopMark
#   file      : script.sh
#   license   : MIT
#   copyright : (c) 2025 Olivier Biot
#
# topmark:header:end

echo "Hello, World!"
```

### XML

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!--
topmark:header:start

  project   : TopMark
  file      : config.xml
  license   : MIT
  copyright : (c) 2025 Olivier Biot

topmark:header:end
-->

<configuration>
    <!-- XML content here -->
</configuration>
```

### JavaScript

```javascript
// topmark:header:start
//
//   project   : TopMark
//   file      : app.js
//   license   : MIT
//   copyright : (c) 2025 Olivier Biot
//
// topmark:header:end

console.log("Hello, World!");
```

### CSS

```css
/*
 * topmark:header:start
 *
 *   project   : TopMark
 *   file      : styles.css
 *   license   : MIT
 *   copyright : (c) 2025 Olivier Biot
 *
 * topmark:header:end
 */

body { margin: 0; }
```

______________________________________________________________________

## Installation

### From PyPI

```bash
pip install topmark
```

### From source (development setup)

```bash
git clone https://github.com/shutterfreak/topmark.git
cd topmark
make venv
make venv-sync-dev
```

TopMark uses **`uv` as the canonical dependency manager**. `pyproject.toml` declares dependency
ranges, `uv.lock` is the committed lock source of truth, and a project-local `.venv` is used as the
standard environment for editor integration and interactive development.

TopMark’s package version is no longer maintained manually in `pyproject.toml`; installed versions
are derived from Git tags via `setuptools-scm`.

Run checks to confirm setup:

```bash
make verify
make test
```

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

### Subcommands

| Command               | Description                                                                   |
| --------------------- | ----------------------------------------------------------------------------- |
| `check`               | Add or update TopMark headers                                                 |
| `strip`               | Remove TopMark headers                                                        |
| `probe`               | Explain file-type and processor resolution                                    |
| `config check`        | Check the merged config for errors.                                           |
| `config defaults`     | Show the built-in default TopMark TOML document                               |
| `config dump`         | Show resolved configuration (merged TOML), optionally with layered provenance |
| `config init`         | Output the bundled example TopMark TOML resource with documentation           |
| `registry filetypes`  | List supported file types from the registry                                   |
| `registry processors` | List header processors and mappings from the registry                         |
| `registry bindings`   | List effective filetype to processor bindings                                 |
| `version`             | Print version (PEP 440 or SemVer)                                             |

### Examples

```bash
# Preview (dry-run)
topmark check src/

# Apply in place
topmark check --apply src/

# Remove headers (dry-run)
topmark strip src/

# Remove headers and apply changes
topmark strip --apply src/

# Treat config warnings as errors for this run
topmark check --strict src/

# Explain how TopMark resolves a file type and processor
topmark probe README.md

# Show candidate scores and match signals
topmark probe -vv README.md

# Filter file types (by local identifier):
topmark check --include-file-types python src/

# Filter file types (by qualified identifier):
topmark check --include-file-types topmark:python src/

# Process one file's content from STDIN
cat README.md | topmark check - --stdin-filename README.md

# Show why a path was filtered by discovery rules
topmark probe __pycache__/example.cpython-312.pyc

# Inspect merged configuration with layered provenance
topmark config dump --show-layers

# Emit machine-readable config provenance + flattened config
topmark config dump --show-layers --output-format json

# Show supported file types in Markdown format
topmark registry filetypes --output-format markdown --long

# List effective filetype to processor bindings
topmark registry bindings --output-format markdown --long
```

> Note:
>
> - `-v` / `--verbose` applies only to TEXT output.
> - `-q` / `--quiet` is available only on commands that support TEXT output suppression, such as
>   `check`, `strip`, `probe`, `config check`, and `config dump`.
> - Pure informational content-producing commands such as `version`, `config defaults`,
>   `config init`, and registry commands do not support `--quiet`.
> - TopMark does not provide a `--stdin` flag. Use the POSIX-style `-` PATH sentinel together with
>   `--stdin-filename NAME` when reading one file's content from STDIN.
> - File-agnostic commands such as `version`, `config defaults`, `config init`, and registry
>   commands reject positional paths and file-processing STDIN modes.
> - Markdown output is document-oriented and ignores TEXT-only verbosity controls.
> - JSON/NDJSON output is machine-readable and also ignores TEXT-only verbosity controls.
> - `topmark probe` also reports explicitly requested paths that were filtered out before
>   resolution, distinguishing between path filters, file-type filters, and a generic fallback.

TopMark preserves standard line endings (LF, CRLF, CR), shebangs, BOMs, and file-specific
indentation rules. Non-standard Unicode newline separators (NEL/LS/PS) are treated as ordinary
content rather than physical line endings.

### Exit codes (CI / scripting)

TopMark uses a small, stable set of exit codes for automation:

- `SUCCESS (0)` — success (no changes needed or changes applied)
- `WOULD_CHANGE (2)` — dry-run indicates changes would be made (`check`, `strip`)
- `FAILURE (1)` — validation failed (`config check`)
- `USAGE_ERROR (64)` — CLI usage error
- invalid command/option combinations, positional paths on file-agnostic commands, and unsupported
  STDIN modes are reported as usage errors
- `CONFIG_ERROR (78)` — configuration error

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
project = "TopMark"
license = "MIT"
copyright = "(c) 2025 Olivier Biot"

[header]
fields = ["file", "file_relpath", "project", "license", "copyright"]
relative_to = "."

[policy]
header_mutation_mode = "all"
allow_header_in_empty_files = false
empty_insert_mode = "logical_empty"
render_empty_header_when_no_fields = false
allow_reflow = false
allow_content_probe = true

[policy_by_type."topmark:python"]
allow_header_in_empty_files = true

[files]
include_file_types = ["topmark:python", "topmark:markdown", "topmark:env"]
exclude_file_types = ["topmark:html"]
exclude_from = [".gitignore"]
```

TopMark can also control mutation policy, empty-file behavior, content probing, and per-file-type
overrides. File type filters and `policy_by_type` keys accept local identifiers such as `python`
when unambiguous and qualified identifiers such as `topmark:python` when explicitness matters.

Use the CLI to inspect the effective configuration:

```bash
topmark config dump --show-layers
topmark config dump --show-layers --output-format json
```

Detailed configuration and policy behavior is documented in:

- [Configuration Guide (hosted docs)](https://topmark.readthedocs.io/en/latest/configuration/discovery/)
- [Example TOML document](https://github.com/shutterfreak/topmark/blob/main/src/topmark/toml/topmark-example.toml)
- [Policy Guide (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/policies/)
- [Filtering (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/filtering/)

______________________________________________________________________

## Pre-commit Integration

TopMark includes **pre-commit** hooks for automated header management.

| Hook ID         | Purpose                            |
| --------------- | ---------------------------------- |
| `topmark-check` | Validate headers (non-destructive) |
| `topmark-apply` | Apply header updates (manual)      |

Install hooks:

```bash
pre-commit install
pre-commit run --all-files
```

Manual header fix (safe interactive mode):

```bash
pre-commit run topmark-apply --hook-stage manual --all-files
```

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

paths: list[Path] = [Path("src")]

policy = {
    "header_mutation_mode": "add_only",
}

# Dry-run (apply=False) header checks
result = api.check(
    paths,
    apply=False,
    policy=policy,
    report="actionable",
)

print(result.summary)
print(result.had_errors)

# Apply changes
result = api.check(
    paths,
    apply=True,
)

# Remove headers
result = api.strip(
    paths,
    apply=True,
)
```

For read-only resolution diagnostics, use `api.probe()`, which returns stable public DTOs without
exposing resolver internals or pipeline objects.

```python
from pathlib import Path

from topmark import api

# Explain file-type / processor resolution
probe_result = api.probe([Path("README.md")])

for file_result in probe_result.files:
    print(file_result.path, file_result.status, file_result.reason)
```

For API details, see:

- [API reference (hosted docs)](https://topmark.readthedocs.io/en/latest/api/)
- [Registry model](docs/dev/registry-model.md)

______________________________________________________________________

## Packaging and Versioning

TopMark uses Git-tag-driven package versions via `setuptools-scm`. Versions are derived from Git
tags at build time rather than maintained manually in `pyproject.toml`.

TopMark follows Semantic Versioning for compatibility intent while Python packaging uses SCM-derived
PEP 440 versions.

Typical release tag forms are:

- final releases: `vX.Y.Z`
- alpha releases: `vX.Y.ZaN`
- beta releases: `vX.Y.ZbN`
- release candidates: `vX.Y.ZrcN`

Build and validate artifacts locally:

```bash
make package-check
```

Releases are published by GitHub Actions when matching Git tags are pushed. Prereleases are
published to TestPyPI for validation before final releases are published to PyPI.

For detailed release architecture and maintainer guidance, see:

- [Release Process](docs/dev/release-process.md)
- [CI/CD documentation (hosted docs)](https://topmark.readthedocs.io/en/latest/ci/)

______________________________________________________________________

## Development

For day-to-day development, use the local `.venv` for editor integration and interactive work.
Automated testing, typing, documentation, and validation still run in isolated environments managed
by `nox`, which keeps local convenience separate from reproducible QA automation.

Typical development workflows:

To run the full QA suite across all supported Python versions:

```bash
make test              # nox -s qa (matrix)
make api-snapshot      # nox -s api_snapshot (matrix)
```

Run QA for a single Python version:

```bash
nox -s qa -p 3.13
nox -s qa_api -p 3.13
```

For faster iteration:

```bash
make pytest            # run tests in current interpreter (no nox)
make format            # formatting
make lint              # static linting
make docs-build        # build the docs
make verify            # formatting, linting, docs, links
```

For contributor setup and validation details, see:

- [Contributing](docs/contributing.md)
- [CI/CD and validation documentation (hosted docs)](https://topmark.readthedocs.io/en/latest/ci/)
- [Documentation conventions](docs/dev/documentation-conventions.md)

______________________________________________________________________

## License

MIT License © 2025 Olivier Biot

> See [LICENSE](LICENSE)

______________________________________________________________________

**TopMark** — consistent headers for consistent projects.
