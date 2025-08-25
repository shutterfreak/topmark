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

TopMark supports Python 3.10–3.13. To ensure compatibility, use [tox](https://tox.wiki/) to run
tests and type checks across all supported versions:

```bash
# Run all environments sequentially
tox

# Run in parallel
tox run-parallel

# Run a specific Python version
tox -e py311

# Run type checking for a specific Python version
tox -e py312-typecheck
```

This will validate both the test suite and type checking under each interpreter.

______________________________________________________________________

## 🤖 GPT Integration Support

The `INSTRUCTIONS.md` file defines the structured project instructions used by GPT-based tools like
ChatGPT. These instructions help guide AI-assisted development by describing the project's goals,
configuration formats, CLI behavior, and header logic.

To convert `INSTRUCTIONS.md` into a machine-readable JSON format for ChatGPT project setup, run:

```bash
make update-instructions-json
```

This will regenerate `project_instructions_topmark.json` with a structured summary of the latest
instructions.

> ✅ Tip: You can use this JSON file when configuring project instructions inside ChatGPT to ensure
> consistent, context-aware assistance during development.

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

```bash
# Validate distribution
.venv/bin/twine check dist/*

# Upload to PyPI
.venv/bin/twine upload dist/*

# Or upload to TestPyPI
.venv/bin/twine upload --repository testpypi dist/*
```

______________________________________________________________________

## 📄 Versioning

Update the version in `pyproject.toml` before releasing a new build:

```toml
[project]
version = "0.2.0"
```

______________________________________________________________________

## 💬 Need Help?

Open an issue or contact the maintainer at `your-email@example.com`.

Happy coding! 🎉
