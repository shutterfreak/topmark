<!--
topmark:header:start

  file         : INSTALL.md
  file_relpath : INSTALL.md
  project      : TopMark
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Installation

This guide covers **development setup** for working on TopMark, plus quick tips for installing the
CLI and verifying it runs correctly.

## Requirements

- Python **3.10 – 3.13**
- Git (for cloning and pre-commit hooks)
- macOS, Linux, or Windows

## Quick install (users)

### Install from PyPI

```bash
pip install topmark
```

Verify:

```bash
topmark version
```

> For usage and command details, see `topmark --help` and the guides under `docs/`.

______________________________________________________________________

## Development setup (contributors)

### 1) Clone the repository

```bash
git clone https://github.com/shutterfreak/topmark.git
cd topmark
```

### 2) Create and activate a virtual environment

```bash
make venv
```

Activate it:

- **macOS/Linux**

  ```bash
  source .venv/bin/activate
  ```

- **Windows (PowerShell)**

  ```powershell
  .venv\Scripts\Activate.ps1
  ```

### 3) Install tools and dependencies

```bash
make setup
```

This will:

- Install `pip-tools`
- Compile runtime & dev requirements
- Install dependencies into the virtualenv

> Note: `make setup` does **not** install TopMark itself. If you want to run `topmark` from your
> checkout, install it in editable mode.

### 3b) Install TopMark in editable mode (optional)

Run the following command from the root directory (where the Makefile is located):

```bash
make dev-install
```

### 4) Install pre-commit hooks

```bash
make pre-commit-install
```

Keep hooks current:

```bash
make pre-commit-autoupdate
```

### 5) Run checks locally (optional)

```bash
# Lint & static analysis
make lint

# Type-check with mypy & pyright
make typecheck

# Run tests (with tox across Python versions if available)
make test
make tox
```

### 6) Build the docs locally (optional)

```bash
make docs-serve   # live-reload at http://127.0.0.1:8000
# or
make docs-build   # build site/ for CI
```

______________________________________________________________________

## Running the CLI

From the repo (editable install) or after `pip install topmark`:

```bash
topmark [GLOBAL_OPTIONS] SUBCOMMAND [OPTIONS] [PATHS]...
```

Examples:

```bash
# Dry-run: check files
topmark check src/

# Apply changes in-place
topmark check --apply src/
```

See `topmark --help` for all commands and options.

______________________________________________________________________

## Troubleshooting

- **mkdocs plugin not found / strict build failures**: ensure `make setup` completed; try
  `make docs-serve` to see missing pages.
- **Multiple Python versions**: Use `pyenv` to install 3.10–3.13; `tox` will run environments that
  exist locally.
- **Permissions on Windows**: If activation fails, allow script execution in PowerShell:
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
