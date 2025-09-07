<!--
topmark:header:start

  file         : README.md
  file_relpath : README.md
  project      : TopMark
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark

[![PyPI version](https://img.shields.io/pypi/v/topmark.svg)](https://pypi.org/project/topmark/)
[![Documentation Status](https://readthedocs.org/projects/topmark/badge/?version=latest)](https://topmark.readthedocs.io/en/latest/?badge=latest)
[![Downloads](https://static.pepy.tech/badge/topmark)](https://pepy.tech/project/topmark)
[![GitHub release](https://img.shields.io/github/v/release/shutterfreak/topmark)](https://github.com/shutterfreak/topmark/releases)

**TopMark** is a command-line tool to inspect, validate, and manage file headers in diverse
codebases. It helps maintain consistent header metadata across projects by supporting per-file-type
header formats, customizable fields, inclusion/exclusion rules, and dry-run safety.

## 📚 Documentation

Full documentation is available on Read the Docs: <https://topmark.readthedocs.io>

This README is the canonical, complete introduction for GitHub/PyPI. The docs site provides a
concise landing page and deep links into topics (install, usage, CI, API, etc.).

## ✨ Features

- File header detection, insertion, and replacement
- Supports multiple file types (Python, Makefile, Markdown, `.env`, ...)
- Configurable comment styles and header fields
- Inclusion and exclusion logic (via CLI, globs, stdin, or config)
- Dry-run by default; safe for CI/CD integration
- Configuration via `pyproject.toml` or `topmark.toml`
- Shell completion for enum-based options
- Colorized CLI output (via `yachalk`)
- Python ≥3.10
- Integrated pre-commit hooks for automated checks
- Formatting and linting support via Makefile targets
- CI-friendly design for safe automated use
- Strict static typing with mypy and Pyright, using PEP 604 union syntax
- Google-style docstrings without redundant type declarations
- Full header removal (`topmark strip`)
- Preserves original newline style (LF/CRLF/CR) and BOM
- Idempotent updates (re-running does not change already-correct files)

## 🚀 Installation

```bash
git clone https://github.com/shutterfreak/topmark.git
cd topmark
make setup  # creates virtualenv, installs dependencies and tools
```

Or install into an existing virtualenv:

```bash
pip install -e .
```

Or install the latest release from PyPI:

```bash
pip install topmark
```

## ⚙️ Usage

```bash
topmark [SUBCOMMAND] [OPTIONS] [PATHS]...
```

TopMark uses Click 8.2 and supports shell completions. The base command performs a dry‑run *check*
by default and applies changes when `--apply` is provided.

The `strip` subcommand is provided to remove entire headers.

Logging verbosity is controlled globally:

- `-v`, `--verbose`: Increase verbosity (can be repeated)
- `-q`, `--quiet`: Suppress most output (overrides verbosity)

All other options are specific to individual subcommands.

______________________________________________________________________

### Subcommands

| Command         | Description                                        |
| --------------- | -------------------------------------------------- |
| `dump-config`   | Show the resolved configuration in TOML format     |
| `filetypes`     | List supported file types and their comment styles |
| `processors`    | List registered header processors and file types   |
| `strip`         | Remove TopMark headers from files (destructive)    |
| `version`       | Print TopMark version                              |
| `show-defaults` | Show default config (without merging)              |
| `init-config`   | Output a starter configuration file                |

______________________________________________________________________

### Examples

```bash
# Check Python files in the src/ directory
topmark check --file-type python src/

# Use exclusion patterns, and compute relative paths from src
topmark check --file-type python --exclude .venv --relative-to src src/

# Add one verbosity level to topmark, use exclusion patterns from .gitignore
topmark -v check --file-type python --exclude-from .gitignore src/

# Read a list of files from STDIN, generate summary
find . -name "*.py" | topmark check --file-type python --files-from -  --summary

# Process all files that are either staged, or untracked but not ignored in a Git repo (needs dedulication with `sort -u`)
git ls-files -c -o --exclude-standard | sort -u | topmark check --files-from - --apply

# Read a single file's *content* from STDIN and render the resultng unified diff
cat README.md | topmark - --stdin-filename README.md --diff

# Read a single file's *content* from STDIN and print the updated content to stdout
cat README.md | topmark - --stdin-filename README.md --apply

# Dump the merged configuration (after loading all applicable config layers)
topmark dump-config --file-type python --exclude .venv --exclude-from .gitignore

# Display the default configuration without any merging
topmark show-defaults

# Output a starter configuration to stdout
topmark init-config

# Show TopMark version in JSON format
topmark version --format json

# Apply changes to files in-place
topmark check --apply src/

# Remove headers from files (dry-run)
topmark strip src/

# Remove headers from files and apply changes
topmark strip --apply src/

# CI-friendly summary: only show issues; ignore unsupported types
topmark check --skip-compliant --skip-unsupported src/

# Apply fixes, don't report unsupported files, muted output (useful for pre-commit)
topmark check --apply --skip-unsupported --quiet

# Show supported file types in MarkDown format, providing detailed output:
topmark filetypes --format markdown --long

# Show registered header processors (brief)
topmark processors

# Detailed Markdown listing of processors and their file types
topmark processors --format markdown --long
```

______________________________________________________________________

## 🔌 Public API (stable)

TopMark exposes a small, stable Python API for integrations. Import from `topmark.api` for core
operations, and use the registry facade for read-only discovery.

### Quickstart

```python
from pathlib import Path
from topmark import api

# Check (dry-run by default)
result = api.check([Path("src")])
print(result.summary)           # {"unchanged": N, "error": M, ...}
print(result.had_errors)        # True/False

# Apply changes explicitly
applied = api.check([Path("src")], apply=True)

# Remove headers
stripped = api.strip([Path("src")], apply=False)
```

### Registry facade (read-only)

```python
from topmark.registry import Registry

fts = Registry.filetypes()      # Mapping[str, FileType]
procs = Registry.processors()   # Mapping[str, HeaderProcessor]
for b in Registry.bindings():   # (filetype, optional processor)
    print(b.filetype.name, bool(b.processor))
```

> **Note:** `Registry` is **not** re-exported from `topmark.api`; import it from `topmark.registry`.

### Version helper

```python
from topmark import api
print(api.version())  # e.g. "0.3.1"
```

### Stability

- `topmark.api` and the `Registry` facade are covered by semantic versioning.
- Low-level registries (`FileTypeRegistry`, `HeaderProcessorRegistry`) remain available for
  plugins/tests but are **advanced** and may change between minor versions.

### Adding & updating headers

Use the `topmark check` command to insert or update headers. It’s **dry‑run by default**; add
`--apply` to write changes. Placement follows file‑type policy (shebang/encoding for Python, XML
declaration for XML/HTML, etc.). Newline style and BOM are preserved; runs are idempotent.

#### Quick examples

```bash
# Preview (exit code 2 when changes are pending)
topmark src/

# Apply in place
topmark check --apply src/
```

> For full details, options, examples, and exit codes, see the dedicated guide:
> **[Adding & updating headers with `topmark`](docs/usage/commands/topmark.md)**

### Removing headers with `strip`

Use `topmark strip` to remove the entire TopMark header block. The command is **dry-run by
default**; add `--apply` to write changes. It preserves newline style and BOM, and keeps XML
declarations and Markdown code fences intact.

#### Quick examples

```bash
# Preview (exit code 2 when removals are pending)
topmark strip src/

# Apply in place
topmark strip --apply src/
```

> For full details, options, examples, and exit codes, see the dedicated guide:
> **[Removing headers with `topmark strip`](docs/usage/commands/strip.md)**

### Dumping the merged configuration

Use `topmark dump-config` to print the **effective** configuration (defaults → discovered config →
`--config` files → CLI flags) as TOML. This command is **file‑agnostic**: positional paths and
`--files-from` are ignored; filter flags (`--include/--exclude`, `--include-from/--exclude-from`)
are honored.

```bash
# Dump merged configuration
topmark dump-config

# Include/exclude filters still apply
topmark dump-config --exclude .venv --exclude-from .gitignore

# Read patterns from STDIN
printf "*.py\n" | topmark dump-config --include-from -
```

> For details and notes, see:
> **[Dumping the merged configuration with `dump-config`](docs/usage/commands/dump_config.md)**

### Listing supported file types

Use `topmark filetypes` to see the identifiers you can pass to `--file-type` and the associated
comment styles TopMark will use when rendering headers.

```bash
# Show available file type identifiers
topmark filetypes

# Then restrict processing to one or more types
topmark check --file-type python src/
topmark check --file-type markdown --file-type env docs/ config/
```

> For details, see:
> **[Listing supported file types with `filetypes`](docs/usage/commands/filetypes.md)**

## 📐 Header placement rules

TopMark is comment-aware and places the header block according to the file type and its policy.

The complete header placement rules are documented in the usage guide:

- [Header placement rules](docs/usage/header-placement.md)

## 🧩 Supported file types

See the full list and resolver behavior in the dedicated guide:

- [Supported file types](docs/usage/filetypes.md)

## 🪝 Pre-commit integration

TopMark ships with pre-commit hooks to validate or update file headers.

- **`topmark-check`** — runs automatically at `pre-commit` / `pre-push`, fails if headers need
  changes.
- **`topmark-apply`** — manual only; applies fixes and may modify files.

For configuration examples, hook policies, and troubleshooting, see the dedicated guide:

- [Using TopMark with pre-commit](docs/usage/pre-commit.md)

## 🛠 Configuration

You can specify one or more `--config` files, or rely on local fallback resolution:

- `topmark.toml` in the working directory
- `pyproject.toml` using the `[tool.topmark]` table

TopMark reads configuration from one or more TOML files. Configuration is merged from:

1. Built-in defaults
1. Local project config (if not disabled via `--no-config`)
1. Additional files via `--config`
1. CLI overrides

Example configuration snippet (`topmark.toml`):

```toml
[fields]
project = "TopMark"
license = "MIT"
copyright = "(c) 2025 Olivier Biot"

[header]
fields = [ "file", "file_relpath", "project", "license", "copyright",]

[formatting]
align_fields = true
raw_header = false

[files]
file_types = [ "python", "markdown", "env" ]
include = []
include_from = []
exclude = []
exclude_from = [ ".gitignore" ]
relative_to = "."
```

### Notes

- `formatting.align_fields = true` vertically aligns the field names within the rendered header
  lines for readability.
- File-type specific behavior (shebang handling, XML prolog, blank line policies) is driven by
  internal **FileTypeHeaderPolicy** defaults and can be extended to new types.

The `EnumParam` class enables shell completion for enum-based CLI options.

## 🧪 Development Setup

For development setup and contribution guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md).

To verify compatibility across supported Python versions (3.10–3.13), use `tox` to run tests and
type checks in each environment.

## 📄 License

MIT License © 2025 Olivier Biot

> **[LICENSE (MIT)](LICENSE)**
