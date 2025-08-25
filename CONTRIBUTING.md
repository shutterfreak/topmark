<!--
topmark:header:start

  file         : CONTRIBUTING.md
  file_relpath : CONTRIBUTING.md
  project      : TopMark
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Contributing to TopMark

Thank you for your interest in contributing to **TopMark**! This document provides guidance for
developers on setting up the project, maintaining code quality, running tests, building
distributions, and publishing packages.

______________________________________________________________________

## 🚀 Development Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-org/topmark.git
   cd topmark
   ```

2. **Create a virtual environment and install dependencies:**

   ```bash
   make setup
   ```

   > ℹ️ The `make compile` and `make compile-dev` targets use `pip-compile` with the
   > `--strip-extras` option to generate requirements files without optional extras.
   >
   > 💡 To upgrade development dependencies interactively, use `make upgrade-dev`, which leverages
   > `pip-review`.
   >
   > ⚠️ Ensure you're using `pip-tools >=7.4` to avoid deprecation warnings.

3. **Install pre-commit hooks:**

   ```bash
   make pre-commit-install
   ```

   To keep hooks up to date:

   ```bash
   make pre-commit-autoupdate
   ```

   For more information, see the [pre-commit documentation](https://pre-commit.com).

______________________________________________________________________

## 🎨 Code Style and Tooling

- **Formatting:**

  ```bash
  make format
  ```

  This command formats Python, Markdown, and TOML files to maintain consistent style.

- **Linting:**

  ```bash
  make lint
  ```

- **Full check (lint + format check):**

  ```bash
  make check
  ```

- **Taplo Linter Note:**

  The Taplo linter is configured to skip fetching remote schema catalogs to avoid timeouts in CI and
  isolated environments. See the `[tool.taplo.schemas]` section in `pyproject.toml` for details.

- **VS Code Integration:**

  The project is configured to work seamlessly with VS Code and pre-commit hooks to ensure code
  quality and style consistency.

- **Typing and Documentation Style:**

  The project enforces strict static typing via Pyright. All code must use precise type annotations,
  preferably with PEP 604 syntax (e.g., `str | None`), and be compatible with Python 3.11+.

  Docstrings must follow the Google style. Focus on clear, concise parameter and return
  descriptions. Avoid repeating type hints that are already present in function signatures.

______________________________________________________________________

## 🧪 Running Tests

Use the following command to run all tests:

```bash
make test
```

### Testing across multiple Python versions

TopMark supports Python 3.10–3.13.

To ensure compatibility, use [tox](https://tox.wiki/) to run tests and type checks across all
supported versions.

You must install the required Python versions prior to testing with `tox`. With `pyenv`:

```sh
# Install the Python versions with pyenv
pyenv install 3.10.14
pyenv install 3.11.9
pyenv install 3.12.5
pyenv install 3.13.0

# make them visible in this repo (so tox finds all versions):
pyenv local 3.10.14 3.11.9 3.12.5 3.13.0

# or for the current shell:
pyenv shell 3.10.14 3.11.9 3.12.5 3.13.0
```

```bash
# Run all environments sequentially
tox

# or run in parallel
tox run-parallel

# Run a specific Python version
tox -e py311

# Run type checking for a specific Python version
tox -e py312-typecheck
```

This will validate both the test suite and type checking under each interpreter.

______________________________________________________________________

## 📦 Building Distributions

TopMark follows [PEP 517/518](https://peps.python.org/pep-0517/) standards.

To build source and wheel distributions:

```bash
make build
```

This creates a `dist/` folder containing `.tar.gz` and `.whl` files.

______________________________________________________________________

## 🚀 Publishing to PyPI

### 1. **Set up your `.pypirc` file** (in `~/.pypirc`)

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository: https://upload.pypi.org/legacy/
username: __token__
password: pypi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

[testpypi]
repository: https://test.pypi.org/legacy/
username: __token__
password: pypi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

An example PyPI configuration template is available in `.pypirc.example`.

> 💡 Use [API tokens](https://pypi.org/manage/account/token) instead of passwords. Do **not** commit
> this file!

### 2. **Upload to PyPI or TestPyPI:**

#### From command line and `twine`

```bash
# Validate distribution
.venv/bin/twine check dist/*

# Upload to PyPI
.venv/bin/twine upload dist/*

# Or upload to TestPyPI
.venv/bin/twine upload --repository testpypi dist/*
```

#### From the GitHub Workflow

An example GitHub workflow integration script is availeble in `.gitgub/workflows/release.yml`.

______________________________________________________________________

## 📄 Versioning

Update the version in `pyproject.toml` before releasing a new build:

```toml
[project]
version = "0.2.0"
```

______________________________________________________________________

## 💬 Need Help?

Open an [issue](https://github.com/shutterfreak/topmark/issues) on GitHub.

Happy coding! 🎉
