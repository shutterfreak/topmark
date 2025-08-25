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
- Selective removal
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
topmark [OPTIONS] [PATHS]...
```

TopMark uses Click 8.2 and supports shell completions. The base command performs a dry‑run *check*
by default and applies changes when `--apply` is provided.

Logging verbosity is controlled globally:

- `-v`, `--verbose`: Increase verbosity (can be repeated)
- `-q`, `--quiet`: Suppress most output (overrides verbosity)

All other options, such as `--stdin`, `--file-type`, and path filters, are specific to individual
subcommands like `check` or `apply`.

### Examples

```bash
# Check Python files in the src/ directory
topmark --file-type python src/

# Use exclusion patterns, and compute relative paths from src
topmark --file-type python --exclude .venv --relative-to src src/

# Add one verbosity level to topmark, use exclusion patterns from .gitignore
topmark -v --file-type python --exclude-from .gitignore src/

# Read files from stdin, generate summary
find . -name "*.py" | topmark --file-type python --summary --stdin

# Process all files in a Git repo
git ls-files -c -o --exclude-standard | sort -u | topmark --stdin --apply

# Dump the merged configuration (after loading all applicable config layers)
topmark dump-config --file-type python --exclude .venv --exclude-from .gitignore

# Display the default configuration without any merging
topmark show-defaults

# Output a starter configuration to stdout
topmark init-config

# Show TopMark version
topmark version

# Apply changes to files in-place
topmark --apply src/
```

## 📐 Header placement rules

TopMark is comment-aware and places the header block according to the file type and its policy.

### Pound-style files (e.g., Python, Shell, Ruby, Makefile, YAML, TOML, Dockerfile)

Rules:

- If a **shebang** is present (e.g., `#!/usr/bin/env python3`), place the header **after** the
  shebang and ensure **exactly one** blank line in-between.
- If a **coding/encoding line** follows the shebang (PEP 263 style), place the header **after**
  shebang **and** encoding line.
- Otherwise, place the header **at the top of the file**.
- Ensure **one trailing blank line** after the header block when the next line is not already blank.

Example (Python):

```py
#!/usr/bin/env python3

# topmark:header:start
#
#   file         :
#   file_relpath :
#
# topmark:header:end

print("hello")
```

### XML-style files (XML, HTML/XHTML, SVG, Vue/Svelte/Markdown via HTML comments)

Rules:

- If present, place the header **after the XML declaration** and **DOCTYPE**, with **one blank
  line** before the header block.
- Otherwise, place the header **at the top of the file**.
- The header uses the file’s native comment syntax; for XML/HTML it’s a comment block wrapper:

```html
<!--
topmark:header:start

  file         :
  file_relpath :

topmark:header:end
-->

<html>...</html>
```

### General guarantees

- **Newline preservation:** The inserted header uses the same newline style as the file
  (LF/CRLF/CR).
- **BOM preservation:** If a UTF‑8 BOM is present, it is preserved.
- **Idempotency:** Re-running TopMark on a file with a correct header makes **no changes**.

### Common Options

The following options can be used with most commands.

| Option           | Description                              |
| ---------------- | ---------------------------------------- |
| `--file-type`    | Specify file type (python, markdown, …)  |
| `--relative-to`  | Set base path for relative header fields |
| `--include`      | Include paths or glob patterns           |
| `--include-from` | Read inclusion patterns from file        |
| `--exclude`      | Exclude paths or glob patterns           |
| `--exclude-from` | Read exclusion patterns from file        |
| `--stdin`        | Read file paths from stdin               |
| `--apply`        | Actually modify files instead of dry-run |
| `-v, --verbose`  | Increase verbosity (can be repeated)     |
| `-q, --quiet`    | Suppress most output                     |

### Subcommands

| Command         | Description                                        |
| --------------- | -------------------------------------------------- |
| `dump-config`   | Show the resolved configuration in TOML format     |
| `filetypes`     | List supported file types and their comment styles |
| `version`       | Print TopMark version                              |
| `show-defaults` | Show default config (without merging)              |
| `init-config`   | Output a starter configuration file                |

## 🧩 Supported file types

| Processor            | File types (examples)                                                      |
| -------------------- | -------------------------------------------------------------------------- |
| PoundHeaderProcessor | python, shell, ruby, r, julia, perl, makefile, dockerfile, yaml, toml, env |
| XmlHeaderProcessor   | xml, xhtml, html, svg, xsl/xslt, vue, svelte, markdown                     |

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

Markdown formatting is handled by `mdformat` with the `mdformat-tables` plugin, and configuration is
read from `pyproject.toml`.
