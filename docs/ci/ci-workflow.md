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

This document describes the automated **CI pipeline** for TopMark, implemented in
`.github/workflows/ci.yml`.

______________________________________________________________________

## Overview

The CI workflow validates all contributions (pushes and pull requests).\
It ensures **type safety, formatting, linting, documentation integrity, test coverage, and API
stability**.

The CI pipeline also ensures that builds are compatible with the Git-based versioning model
(`setuptools-scm`) by fetching full Git history where needed and validating packaging steps used by
the release workflow.

The CI pipeline is also responsible for building **release artifacts on tag pushes**, which are
later consumed by the release workflow instead of rebuilding the project in a privileged context.

### Trigger Conditions

- On **push** to `main`
- On **tag** push (`v*`)
- On **pull request** affecting `src/**`, `tests/**`, `tools/**`, or documentation

______________________________________________________________________

## Jobs Summary

| Job                   | Purpose                                                      | Tools                                                          |
| --------------------- | ------------------------------------------------------------ | -------------------------------------------------------------- |
| **changes**           | Detect what changed so we can gate PR-only jobs              | `dorny/paths-filter`                                           |
| **lint**              | Formatting, linting, type checks, and docstring link checks  | `nox -s format_check`, `nox -s lint`, `nox -s docstring_links` |
| **pre-commit**        | Validate configured pre-commit hooks                         | `pre-commit`                                                   |
| **docs**              | Build documentation strictly (warnings = errors)             | `nox -s docs`                                                  |
| **tests**             | Run test matrix across Python 3.10–3.14                      | `nox -s qa -p py3xx`                                           |
| **api-snapshot**      | Verify public API stability (PR-only; when `src` changed)    | `nox -s api_snapshot -p 3.13`                                  |
| **links**             | Validate links in source Markdown (docs + top-level)         | `lycheeverse/lychee-action` + `lychee.toml`                    |
| **links-site**        | Validate links in the built MkDocs site (includes generated) | `mkdocs` + `lycheeverse/lychee-action` + `--root-dir`          |
| **release-artifacts** | Build and upload release artifacts for tagged commits        | `uv build`, artifact upload                                    |

______________________________________________________________________

## Key Features

### 🧱 Nox-Centric Execution

Most heavy lifting is delegated to **nox sessions**:

- Ensures local runs and CI behave identically
- Keeps workflow logic thin
- Centralizes environment configuration in `noxfile.py`

```yaml
- uses: ./.github/actions/setup-python-nox
  with:
      python-version: "3.13"
```

### ⚡ Caching

Each job restores the uv cache and keys it from the canonical dependency inputs:

```yaml
- name: Cache uv
  uses: actions/cache@v5
  with:
      path: ~/.cache/uv
      key: ${{ runner.os }}-py${{ steps.setup-python.outputs.python-version }}-${{ hashFiles('pyproject.toml', 'uv.lock', 'noxfile.py') }}
```

### 📦 Release Artifact Build (Tag Pushes)

On tag pushes (`v*`), CI builds release artifacts in an **unprivileged context** and uploads them
for the release workflow:

- Builds `sdist` and `wheel` via `uv build`
- Generates release metadata (tag, normalized version, checksums)
- Uploads artifacts (`dist/` + metadata) using `actions/upload-artifact`

The privileged release workflow (`release.yml`) later downloads and verifies these artifacts before
publishing.

This separation ensures that **repository code is never executed in the privileged release
workflow**, aligning with GitHub security best practices and CodeQL recommendations.

### ✅ Pre-commit Validation

Runs all hooks defined in `.pre-commit-config.yaml`:

```yaml
- name: Run pre-commit hooks
  run: pre-commit run --all-files --show-diff-on-failure
```

In CI we skip a small set of slower hooks (notably lychee and pyright) because dedicated jobs cover
them.

### 📚 Docs integrity

Documentation integrity is validated at multiple levels:

- **Strict MkDocs build** (`docs` job): ensures all pages build without warnings or errors. This
  includes pages generated at build time (e.g. API reference pages).
- **Source link checking** (`links` job): validates links in handwritten Markdown files (e.g.
  `docs/**`, `README.md`).
- **Built-site link checking** (`links-site` job): validates links in the rendered HTML output,
  including theme navigation and **generated API pages**.

**Important:** generated API pages are only validated by the built-site link check (`links-site`).
Source-only checks cannot see these pages.

### 🔍 API Stability Check

For pull requests that modify `src/**`, a quick snapshot test ensures the **public API has not
changed** unexpectedly.

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

## Dependency Automation

TopMark uses **Dependabot** to keep GitHub Actions and dependencies up to date.

For security reasons, GitHub Actions are pinned to **exact commit SHAs** instead of version tags.
Dependabot automatically opens pull requests when upstream actions release updates.

See [`docs/ci/dependabot.md`](./dependabot.md) for details on the update policy and review workflow.

______________________________________________________________________

## Future Improvements

- Optionally expand the API snapshot check beyond Python 3.14 if needed
- Upload coverage and/or docs build artifacts for easier debugging

### 🏷️ SCM-based Versioning Compatibility

CI jobs fetch full Git history (`fetch-depth: 0`) where required to ensure that `setuptools-scm` can
correctly derive package versions from tags. This guarantees that local, CI, and release builds all
resolve versions consistently.
