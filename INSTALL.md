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

This guide covers how to **install** TopMark for regular use, and how to set up a **development** environment that matches our current tooling (`noxfile.py`, `Makefile`, and `CONTRIBUTING.md`).

______________________________________________________________________

## Requirements

- Python **3.10 – 3.14**
- Git (for cloning and contributing)
- macOS, Linux, or Windows

> For development: `make`, `nox`, `uv` and optionally `pyenv` to install multiple Python versions.

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

We keep a small `.venv` only for editor integration (e.g., Pyright import resolution); `nox` (using the `uv` backend) manages the automated QA environments used by CI and `Makefile` targets.

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

Run the test suite across the supported Python versions via `nox`:

```bash
make test
```

Run tests with your current interpreter only (no `nox`):

```bash
make pytest
# or in parallel:
make pytest PYTEST_PAR="-n auto"
```

### 4) Type checks and property tests (optional)

Run Pyright directly (example, from `.venv`):

```bash
pyright --pythonversion 3.13
```

In practice you’ll usually run Pyright via `nox` sessions:

- `qa`: runs tests (`pytest`) and type checks (`pyright`)
- `qa_api`: runs tests, the API snapshot check, and type checks (`pyright`)

Run QA for a specific Python version (example: 3.13):

```bash
nox -s qa -p 3.13
nox -s qa_api -p 3.13
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

## `nox` basics

```bash
nox -l               # list sessions
nox -s qa -p 3.12    # run QA for a single Python
nox -s qa -- -k foo  # forward args to pytest (after --)
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

## Release workflow (maintainers)

Releases are triggered by pushing a Git tag.

Release candidate:

```bash
git tag vX.Y.Z-rcN
git push origin vX.Y.Z-rcN
```

Final release:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

The GitHub Actions workflow:

- Validates version in `pyproject.toml`
- Builds docs (strict)
- Builds sdist and wheel
- Publishes to:
  - TestPyPI (for `-rc`, `-a`, `-b`)
  - PyPI (final releases)

Manual uploads are discouraged and should only be used in exceptional cases.

______________________________________________________________________

## Packaging (maintainers & advanced)

Build and validate artifacts locally:

```bash
make package-check
```

For a full deterministic pre-release gate:

```bash
make release-check
```

Upload to PyPI (or TestPyPI) is normally handled by `.github/workflows/release.yml` when pushing a tag.

Manual upload (maintainers only):

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

- **Multiple Python versions**: if running `nox` across versions locally, install interpreters with `pyenv` (e.g., `3.10–3.14`).
  `nox` will skip sessions whose interpreter is missing (unless configured to error).

- **Windows PowerShell activation**: allow script execution:

  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
  ```

______________________________________________________________________

For contribution guidelines, testing strategies, and release policies, see **`CONTRIBUTING.md`**.
