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

This guide covers:

- installing TopMark for normal CLI usage;
- testing prereleases;
- upgrading from earlier TopMark versions;
- setting up a contributor-oriented development environment.

Hosted user documentation lives at:

- <https://topmark.readthedocs.io/>

______________________________________________________________________

## Requirements

### Regular usage

- Python **3.10 - 3.14**

### Development and contribution

- Git
- `make`
- `uv`
- `nox`
- optionally `pyenv` for managing multiple Python versions

TopMark supports macOS, Linux, and Windows.

______________________________________________________________________

## Install from PyPI

Stable releases are published on [PyPI](https://pypi.org/project/topmark/).

```bash
pip install topmark
```

Verify that the CLI is available:

```bash
topmark version
# or:
topmark --help
```

For a guided first setup, see:

- [Getting started (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/getting-started/)

______________________________________________________________________

## Install prereleases from TestPyPI

Prereleases are published to [TestPyPI](https://test.pypi.org/project/topmark/) before stable PyPI
publication. To test a prerelease:

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  topmark==1.0.0rc1
```

The extra PyPI index is needed so dependencies can still resolve from PyPI.

______________________________________________________________________

## Upgrading from TopMark 0.11.x

TopMark 1.0 introduces breaking changes to:

- CLI options and reporting behavior;
- pre-commit hook arguments;
- TOML configuration structure and policy settings;
- TEXT, Markdown, JSON, and NDJSON output formats;
- machine-readable runtime diagnostics and reporting contracts.

Before upgrading an existing repository, review the migration guide:

- [Upgrading to TopMark 1.0 (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/upgrading-to-1.0/)

______________________________________________________________________

## Development setup (contributors)

### 1) Clone the repository

```bash
git clone https://github.com/shutterfreak/topmark.git
cd topmark
```

### 2) Create a local development environment (optional)

A project-local `.venv` is the recommended environment for editor integration and interactive
development. `uv` manages this environment directly.

Automated validation environments used by CI and quality checks are still created and managed by
`nox` (via the `uv` backend), ensuring reproducible and isolated validation environments while
keeping the local developer workflow simple.

```bash
make venv
make venv-sync-all  # syncs dev/docs/test/typing extras into .venv
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

### 3) Run validation commands

Run the main validation workflow:

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

### 4) Additional validation workflows

Run Pyright directly (example, from `.venv`):

```bash
pyright --pythonversion 3.13
```

In practice, Pyright is usually run via `nox` sessions:

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

### 6) Editable install (optional)

If you want to run `topmark` from your checkout without building a wheel, install the project in
editable mode inside your active environment:

```bash
uv pip install --system -e .
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

If you **intentionally** changed the public API, commit the updated snapshot, update
[`CHANGELOG.md`](./CHANGELOG.md), and ensure the next release tag reflects the intended version
stage. TopMark uses Git tags as the single source of truth for versioning via `setuptools-scm`, so
there is no manual version bump in `pyproject.toml`.

______________________________________________________________________

## Release workflow (maintainers)

Releases are triggered by pushing a Git tag.

**Release candidate / prerelease:**

```bash
git tag vX.Y.ZrcN
git push origin vX.Y.ZrcN
```

Compact PEP 440-style prerelease tags are preferred for new releases; legacy dashed variants remain
supported for backward compatibility.

**Final release:**

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

The GitHub Actions workflow:

- Resolves the package version from Git tags via `setuptools-scm`
- Validates the SCM-derived artifact version against the release tag
- Builds docs (strict)
- Builds sdist and wheel
- Publishes to:
  - [TestPyPI](https://test.pypi.org/project/topmark/) (for prereleases such as `a`, `b`, `rc`)
  - [PyPI](https://pypi.org/project/topmark/) (final releases)

Manual uploads are discouraged and should only be used in exceptional cases.

______________________________________________________________________

## Packaging and release validation (maintainers)

Build and validate artifacts locally:

```bash
make package-check
```

Run the deterministic pre-release validation workflow:

```bash
make release-check
```

Uploads to PyPI and TestPyPI are normally handled by GitHub Actions when release tags are pushed.

Manual uploads are intended only for exceptional maintainer workflows:

```bash
twine upload dist/*
# or:
twine upload --repository testpypi dist/*
```

TopMark uses Git tags as the single source of truth for package versions via `setuptools-scm`.

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

- **Multiple Python versions**: if running `nox` across versions locally, install interpreters with
  `pyenv` (e.g., `3.10-3.14`). `nox` will skip sessions whose interpreter is missing (unless
  configured to error).

- **Windows PowerShell activation**: allow script execution:

  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
  ```

______________________________________________________________________

Further reading:

- [Getting started (hosted docs)](https://topmark.readthedocs.io/en/latest/usage/getting-started/)
- [Contributing (hosted docs)](https://topmark.readthedocs.io/en/latest/contributing/)
- [CI/CD documentation (hosted docs)](https://topmark.readthedocs.io/en/latest/ci/)
- [Development documentation (hosted docs)](https://topmark.readthedocs.io/en/latest/dev/)
