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

This document describes the automated **CI pipeline** for TopMark, implemented in [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml).

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

| Job              | Purpose                                                         | Tools                                                          |
| ---------------- | --------------------------------------------------------------- | -------------------------------------------------------------- |
| **changes**      | Detect if `src/**` changed to gate PR jobs                      | `dorny/paths-filter`                                           |
| **lint**         | Run formatting, linting, type checks, and docstring link checks | `tox -e format-check`, `tox -e lint`, `tox -e docstring-links` |
| **pre-commit**   | Validate all configured `pre-commit` hooks                      | `pre-commit`                                                   |
| **docs**         | Build documentation strictly (warnings = errors)                | `tox -e docs`                                                  |
| **tests**        | Run test matrix across Python 3.10–3.14                         | `tox -e py310..py314`                                          |
| **api-snapshot** | Verify public API stability for PRs                             | `tox -e py313-api`                                             |
| **links**        | Validate all Markdown links (docs + root files)                 | `lycheeverse/lychee-action`                                    |

______________________________________________________________________

## Key Features

### 🧱 Tox-Centric Execution

All heavy lifting is delegated to **tox environments**:

- Ensures local runs and CI behave identically
- Simplifies Makefile and workflow logic
- Uses per-job caching for `~/.cache/pip` and `.tox`

```yaml
- name: Bootstrap tox
  run: |
      python -m pip install -U pip
      pip install tox
```

### ⚡ Caching

Each job caches both pip and tox environments for speed:

```yaml
- name: Cache pip & tox
  uses: actions/cache@v4
  with:
      path: |
          ~/.cache/pip
          .tox
      key: ${{ runner.os }}-py${{ steps.setup-python.outputs.python-version }}-${{ hashFiles('tox.ini', 'pyproject.toml', 'requirements-*.txt', 'constraints.txt') }}
```

### ✅ Pre-commit Validation

Runs all hooks defined in `.pre-commit-config.yaml`:

```yaml
- name: Run pre-commit hooks
  run: pre-commit run --all-files --show-diff-on-failure
```

### 🔍 API Stability Check

For pull requests that modify `src/**`, a quick snapshot test ensures the **public API has not changed** unexpectedly.

______________________________________________________________________

## Local Reproduction

Run equivalent checks locally with:

```bash
make verify     # runs all lint/format/docs checks
make test       # runs tox matrix
make pytest     # run pytest in current interpreter
```

______________________________________________________________________

## Future Improvements

- Optionally switch `api-snapshot` job to use `tox -m api-check` (runs across all Python versions)
- Enable coverage reporting and artifact upload
- Integrate performance regressions or profiling gates
