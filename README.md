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
formats, and dry-run safety.

______________________________________________________________________

## 📚 Documentation

Full documentation is hosted on **Read the Docs**:\
👉 <https://topmark.readthedocs.io>

This README provides an overview. See the docs for deeper topics (install, usage, API, CI/CD, etc.).

______________________________________________________________________

## 🧩 Features

- Detect, insert, and replace file headers across multiple file types
- Comment-aware (line and block styles)
- Configurable header fields and alignment
- Dry-run by default for safety
- **Policy-based control** over when headers may be inserted, updated, or added to empty files
- Layered configuration via:
  - `pyproject.toml` (`[tool.topmark]`)
  - `topmark.toml`
  - CLI overrides and `--config`
- Inspectable layered config provenance via `topmark config dump --show-layers` and machine-readable
  `config_provenance` output
- Fine-grained include/exclude rules
- Selective application via file patterns or STDIN (list mode or single-file content mode)
- Strict static typing (PEP 604 unions, Pyright)
- Works well with `pre-commit`, CI, and Git hooks
- Preserves newline style (LF/CRLF/CR) and BOM
- Idempotent: re-running on already-compliant files makes no changes
- Configurable comment alignment and raw/pretty formatting

______________________________________________________________________

## 🧱 Example headers

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

## ⚙️ Installation

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

______________________________________________________________________

## 🚀 Usage

```bash
topmark [COMMAND] [OPTIONS] [PATHS]...
```

### Subcommands

| Command               | Description                                                                   |
| --------------------- | ----------------------------------------------------------------------------- |
| `check`               | Add or update TopMark headers                                                 |
| `strip`               | Remove TopMark headers                                                        |
| `config check`        | Check the merged config for errors.                                           |
| `config defaults`     | Show the built-in default TopMark TOML document                               |
| `config dump`         | Show resolved configuration (merged TOML), optionally with layered provenance |
| `config init`         | Output the bundled example TopMark TOML resource with documentation           |
| `registry filetypes`  | List supported file types from the registry                                   |
| `registry processors` | List header processors and mappings from the registry                         |
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

# Inspect merged configuration with layered provenance
topmark config dump --show-layers

# Emit machine-readable config provenance + flattened config
topmark config dump --show-layers --output-format json

# Show supported file types in Markdown format
topmark registry filetypes --output-format markdown --long

# List processors and associated file types
topmark registry processors --output-format markdown --long
```

TopMark preserves line endings, shebangs, BOMs, and indentation rules for each file type.

______________________________________________________________________

## 🧠 Configuration & Policy

TopMark supports **layered configuration discovery** and a flexible **policy system** controlling
insert/update behavior.

### Discovery order

1. Built-in defaults
1. User config (`~/.config/topmark/topmark.toml` or `~/.topmark.toml`)
1. Project config chain (root-most → nearest upward `pyproject.toml` or `topmark.toml`)
1. Explicit `--config` files (merged in order)
1. CLI flags and options (highest precedence)

This same ordering is exposed by `topmark config dump --show-layers` as a layered provenance view.
Human-facing output renders ordered TOML layers before the final flattened config, while
machine-readable output emits `config_provenance` before the final `config` snapshot.

### Example `topmark.toml`

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

[policy_by_type."python"]
allow_header_in_empty_files = true

[formatting]
align_fields = true

[files]
include_file_types = ["python", "markdown", "env"]
exclude_file_types = ["html"]
exclude_from = [".gitignore"]
```

Source-local TOML options such as discovery boundaries and config-checking strictness live under
`[config]` (or `[tool.topmark.config]` in `pyproject.toml`). They are resolved separately from
layered `Config` values and do not participate in layered config merging.

For example, `strict_config_checking` is resolved from TOML sources and affects configuration
validation behaviour; it is not a normal layered `Config` field. CLI/API strictness overrides still
take precedence for the current run.

In layered provenance output, these source-local TOML fragments remain grouped under their original
TOML sections (for example `[config]` and `[writer]`) rather than being collapsed into the final
flattened runtime config payload.

### Policy semantics

| Setting                              | Meaning                                                                 |
| ------------------------------------ | ----------------------------------------------------------------------- |
| `header_mutation_mode`               | Controls mutation: `all`, `add_only`, or `update_only`                  |
| `allow_header_in_empty_files`        | Allow adding headers to empty-like files                                |
| `empty_insert_mode`                  | Controls how TopMark classifies files as empty for insertion            |
| `render_empty_header_when_no_fields` | Allow inserting an otherwise empty header when no fields are configured |
| `allow_reflow`                       | Allow content reflow during header insertion/update                     |
| `allow_content_probe`                | Allow file-type detection to inspect file contents when needed          |

Per-type overrides under `[policy_by_type."filetype"]` in `topmark.toml` (or
`[tool.topmark.policy_by_type."filetype"]` in `pyproject.toml`) can adjust specific behavior.

These policy options apply equally to the **CLI** and the **public API**.

For CLI usage, see the dedicated [Policy Guide](docs/usage/policies.md).

______________________________________________________________________

## 🪝 Pre-commit Integration

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

## 🔒 Public API

The public API accepts optional `policy` and `policy_by_type` arguments (global or per-type) that
integrate with the same resolution mechanism used by the CLI. The returned result view is controlled
via `report="all" | "actionable" | "noncompliant"`.

### Example

```python
from pathlib import Path
from topmark import api

paths: list[Path] = [Path("src")]

policy: dict[str, object] = {
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

For programmatic discovery:

```python
from topmark.registry.registry import Registry

for binding in Registry.bindings():
    print(
        binding.filetype.name,
        binding.filetype.description,
        "(bound)" if binding.processor else "(unbound)",
    )
```

______________________________________________________________________

## 📦 Packaging & Versioning

TopMark follows **Semantic Versioning (SemVer)**.

For development and CI, dependency resolution is driven by `uv`:

- `pyproject.toml` defines supported dependency ranges
- `uv.lock` is the committed lock file
- `nox` installs session dependencies from project extras

| Change Type                   | Version Impact |
| ----------------------------- | -------------- |
| `fix:`                        | Patch          |
| `feat:`                       | Minor          |
| `feat!:` / `BREAKING CHANGE:` | Major          |

Build and validate artifacts locally:

```bash
make package-check
```

Release candidates and final releases are published by CI when you push a tag.

______________________________________________________________________

## 🧪 Development

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

______________________________________________________________________

## 📄 License

MIT License © 2025 Olivier Biot

> See [LICENSE](LICENSE)

______________________________________________________________________

**TopMark** — consistent headers for consistent projects.
