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
[![Documentation Status](https://readthedocs.org/projects/topmark/badge/?version=latest)](https://topmark.readthedocs.io/en/latest/?badge=latest)
[![Downloads](https://static.pepy.tech/badge/topmark)](https://pepy.tech/project/topmark)
[![GitHub release](https://img.shields.io/github/v/release/shutterfreak/topmark)](https://github.com/shutterfreak/topmark/releases)

**TopMark** is a command-line tool to inspect, validate, and manage file headers in diverse codebases.\
It maintains consistent metadata across files by supporting multiple comment styles, configuration formats, and dry-run safety.

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
- Layered configuration via:
  - `pyproject.toml` (`[tool.topmark]`)
  - `topmark.toml`
  - CLI overrides
- Fine-grained include/exclude rules
- Selective application via file patterns or `stdin`
- Strict static typing (PEP 604 unions, Pyright)
- Works well with `pre-commit`, CI, and Git hooks
- Preserves newline style (LF/CRLF/CR) and BOM
- Idempotent: re-running on already-compliant files makes no changes
- Configurable comment alignment and raw/pretty formatting

______________________________________________________________________

## 🧱 Example headers

TopMark adapts headers to the comment syntax of each file type.

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

| Command         | Description                               |
| --------------- | ----------------------------------------- |
| `check`         | Add or update TopMark headers             |
| `strip`         | Remove TopMark headers                    |
| `dump-config`   | Show resolved configuration (merged TOML) |
| `filetypes`     | List supported file types                 |
| `processors`    | List header processors and mappings       |
| `show-defaults` | Show built-in defaults without merging    |
| `init-config`   | Output a starter configuration            |
| `version`       | Print version (PEP 440 or SemVer)         |

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

# Show supported file types in Markdown format
topmark filetypes --format markdown --long

# List processors and associated file types
topmark processors --format markdown --long
```

TopMark preserves line endings, shebangs, BOMs, and indentation rules for each file type.

______________________________________________________________________

## 🧠 Configuration

TopMark supports **layered configuration discovery**:

1. Built-in defaults (`topmark-default.toml`)
1. User config (`~/.config/topmark/topmark.toml` or `~/.topmark.toml`)
1. Project config (nearest upward `pyproject.toml` or `topmark.toml`)
1. Explicit `--config` files (highest precedence)
1. CLI flags and options

```bash
topmark dump-config --exclude .venv --exclude-from .gitignore
```

### Example `topmark.toml`

```toml
[fields]
project = "TopMark"
license = "MIT"
copyright = "(c) 2025 Olivier Biot"

[header]
fields = ["file", "file_relpath", "project", "license", "copyright"]

[formatting]
align_fields = true
raw_header = false

[files]
file_types = ["python", "markdown", "env"]
exclude_from = [".gitignore"]
relative_to = "."
```

> See [`docs/configuration/discovery.md`](docs/configuration/discovery.md) for details.

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

TopMark exposes a minimal **stable Python API** under `topmark.api`.

### Example

```python
from pathlib import Path
from topmark import api

# Dry-run header checks
result = api.check([Path("src")])
print(result.summary)
print(result.had_errors)

# Apply changes
applied = api.check([Path("src")], apply=True)

# Remove headers
api.strip([Path("src")], apply=True)
```

For programmatic discovery:

```python
from topmark.registry import Registry

for ft, proc in Registry.bindings():
    print(ft.name, bool(proc))
```

______________________________________________________________________

## 📦 Packaging & Versioning

TopMark follows **Semantic Versioning (SemVer)**.

| Change Type                   | Version Impact |
| ----------------------------- | -------------- |
| `fix:`                        | Patch          |
| `feat:`                       | Minor          |
| `feat!:` / `BREAKING CHANGE:` | Major          |

Build and check distributions:

```bash
python -m build
python -m twine check dist/*
```

Upload:

```bash
python -m twine upload dist/*
```

Tags are released via CI/CD.

______________________________________________________________________

## 🧪 Development

To test across all supported Python versions:

```bash
make test              # tox default envs
tox -m api-check       # API stability across all Python versions
```

For faster iteration:

```bash
make pytest            # run tests in current interpreter
make lint              # static linting
make verify            # formatting, linting, docs, links
```

______________________________________________________________________

## 📄 License

MIT License © 2025 Olivier Biot

> See [LICENSE](LICENSE)

______________________________________________________________________

**TopMark** — consistent headers for consistent projects.
