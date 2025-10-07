<!--
topmark:header:start

  project      : TopMark
  file         : INSTALL.md
  file_relpath : INSTALL.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Installation

This guide covers how to **install** TopMark for regular use, and how to set up a **development** environment that matches our current tooling (`tox.ini`, `Makefile`, and `CONTRIBUTING.md`).

______________________________________________________________________

## Requirements

- Python **3.10 – 3.14**
- Git (for cloning and contributing)
- macOS, Linux, or Windows

> For development: `make`, `tox`, and optionally `pyenv` to install multiple Python versions.

______________________________________________________________________

## Quick install (users)

Install from PyPI:

```bash
pip install topmark
```

Verify the CLI is available:

```bash
topmark version
# or:
topmark --help
```

______________________________________________________________________

## Development setup (contributors)

### 1) Clone the repository

```bash
git clone https://github.com/shutterfreak/topmark.git
cd topmark
```

### 2) Create an editor-friendly virtual environment (optional)

We keep a small `.venv` only for editor integration (e.g., Pyright import resolution). Tox will still manage test environments.

```bash
make venv
make venv-sync-dev  # installs dev deps into .venv
```

Activate it:

```bash
source .venv/bin/activate
```

To deactivate:

```bash
deactivate
```

To remove it later:

```bash
make venv-clean
```

### 3) Run local checks

Run the core quality gates (formatting, linting, docs build, link checks):

```bash
make verify
```

Run the test suite across the default tox environments:

```bash
make test
```

Run tests with your current interpreter only (no tox):

```bash
make pytest
# or in parallel:
make pytest PYTEST_PAR="-n auto"
```

### 4) Type checks and property tests (optional)

Per-version Pyright check (example):

```bash
tox -e py313-typecheck
```

Long-running Hypothesis hardening tests (manual, opt-in):

```bash
make property-test
```

### 5) Build and serve documentation

Strict build (CI-equivalent):

```bash
make docs-build
```

Local live-reload server:

```bash
make docs-serve
# visit http://127.0.0.1:8000
```

### 6) (Optional) Editable install of TopMark

If you want to run `topmark` from your checkout without building a wheel:

```bash
pip install -e .
topmark version
```

______________________________________________________________________

## API stability (for contributors)

TopMark enforces a stable public API using a JSON snapshot (`tests/api/public_api_snapshot.json`).

- Quick local check (current interpreter):

  ```bash
  make api-snapshot-dev
  ```

- Full matrix across supported Python versions:

  ```bash
  make api-snapshot
  ```

- Regenerate snapshot when you intentionally change the API:

  ```bash
  make api-snapshot-update
  ```

- Fail the build if the snapshot differs:

  ```bash
  make api-snapshot-ensure-clean
  ```

If you **intentionally** changed the public API, commit the updated snapshot and bump the version in `pyproject.toml`.

______________________________________________________________________

## Packaging (maintainers & advanced)

Build and validate artifacts:

```bash
python -m build
python -m twine check dist/*
```

Upload to PyPI (or TestPyPI):

```bash
python -m twine upload dist/*
# or:
python -m twine upload --repository testpypi dist/*
```

Releases are typically published by CI when you push a tag (see `CONTRIBUTING.md` for details).

______________________________________________________________________

## Troubleshooting

- **Missing tools**: create `.venv` and install dev deps:

  ```bash
  make venv
  make venv-sync-dev
  ```

- **Docs build errors**: run a strict build to surface issues:

  ```bash
  make docs-build
  ```

  For quicker feedback with live reload:

  ```bash
  make docs-serve
  ```

- **Multiple Python versions**: if running tox across versions locally, install interpreters with `pyenv` (e.g., `3.10–3.14`). Tox will only run environments that exist on your machine.

- **Windows PowerShell activation**: allow script execution:

  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
  ```

______________________________________________________________________

For contribution guidelines, testing strategies, and release policies, see **`CONTRIBUTING.md`**.
