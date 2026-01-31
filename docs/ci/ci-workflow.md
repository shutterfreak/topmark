<!--
topmark:header:start

  project      : TopMark
  file         : ci-workflow.md
  file_relpath : docs/ci/ci-workflow.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# 🧪 Continuous Integration (CI)

This document describes the automated **CI pipeline** for TopMark, implemented in `.github/workflows/ci.yml`.

______________________________________________________________________

## Overview

The CI workflow validates all contributions (pushes and pull requests).\
It ensures **type safety, formatting, linting, documentation integrity, test coverage, and API stability**.

### Trigger Conditions

- On **push** to `main`
- On **tag** push (`v*`)
- On **pull request** affecting `src/**`, `tests/**`, `tools/**`, or documentation

______________________________________________________________________

## Jobs Summary

| Job              | Purpose                                                      | Tools                                                          |
| ---------------- | ------------------------------------------------------------ | -------------------------------------------------------------- |
| **changes**      | Detect what changed so we can gate PR-only jobs              | `dorny/paths-filter`                                           |
| **lint**         | Formatting, linting, type checks, and docstring link checks  | `nox -s format_check`, `nox -s lint`, `nox -s docstring_links` |
| **pre-commit**   | Validate configured pre-commit hooks                         | `pre-commit`                                                   |
| **docs**         | Build documentation strictly (warnings = errors)             | `nox -s docs`                                                  |
| **tests**        | Run test matrix across Python 3.10–3.14                      | `nox -s qa -p py3xx`                                           |
| **api-snapshot** | Verify public API stability (PR-only; when `src` changed)    | `nox -s api_snapshot -p 3.13`                                  |
| **links**        | Validate links in source Markdown (docs + top-level)         | `lycheeverse/lychee-action` + `lychee.toml`                    |
| **links-site**   | Validate links in the built MkDocs site (includes generated) | `mkdocs` + `lycheeverse/lychee-action` + `--root-dir`          |

______________________________________________________________________

## Key Features

### 🧱 Nox-Centric Execution

Most heavy lifting is delegated to **nox sessions**:

- Ensures local runs and CI behave identically
- Keeps workflow logic thin
- Centralizes environment configuration in `noxfile.py`

```yaml
- name: Bootstrap nox
  run: |
      python -m pip install -U pip
      pip install nox nox-uv uv
```

### ⚡ Caching

Each job caches both pip and uv caches for speed:

```yaml
- name: Cache pip & nox
  uses: actions/cache@v4
  with:
      path: |
          ~/.cache/pip
          ~/.cache/uv
      key: ${{ runner.os }}-py${{ steps.setup-python.outputs.python-version }}-${{ hashFiles('noxfile.py', 'pyproject.toml', 'requirements-*.txt', 'constraints.txt') }}
```

### ✅ Pre-commit Validation

Runs all hooks defined in `.pre-commit-config.yaml`:

```yaml
- name: Run pre-commit hooks
  run: pre-commit run --all-files --show-diff-on-failure
```

In CI we skip a small set of slower hooks (notably lychee and pyright) because dedicated jobs cover them.

### 📚 Docs integrity

Documentation integrity is validated at multiple levels:

- **Strict MkDocs build** (`docs` job): ensures all pages build without warnings or errors. This includes pages generated at build time (e.g. API reference pages).
- **Source link checking** (`links` job): validates links in handwritten Markdown files (e.g. `docs/**`, `README.md`).
- **Built-site link checking** (`links-site` job): validates links in the rendered HTML output, including theme navigation and **generated API pages**.

**Important:** generated API pages are only validated by the built-site link check (`links-site`). Source-only checks cannot see these pages.

### 🔍 API Stability Check

For pull requests that modify `src/**`, a quick snapshot test ensures the **public API has not changed** unexpectedly.

______________________________________________________________________

## Local Reproduction

Run equivalent checks locally with:

```bash
nox -s lint -s format_check
nox -s docs
nox -s qa -p 3.13

# Link checking
nox -s links_all        # source Markdown + docstrings
nox -s links_site       # built site (includes generated pages)
```

______________________________________________________________________

## Future Improvements

- Optionally expand the API snapshot check beyond Python 3.14 if needed
- Upload coverage and/or docs build artifacts for easier debugging
