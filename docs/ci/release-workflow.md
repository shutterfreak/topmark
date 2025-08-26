<!--
topmark:header:start

  file         : release-workflow.md
  file_relpath : docs/ci/release-workflow.md
  project      : TopMark
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# GitHub Actions Workflow: Release to PyPI

This workflow, defined in `.github/workflows/release.yml`, handles publishing TopMark to both
**PyPI** and **TestPyPI** using **Trusted Publishing**.

______________________________________________________________________

## Triggers

- Runs when tags matching `v*.*.*` are pushed (final releases)
- Runs when tags matching `v*.*.*-rc*` are pushed (release candidates → TestPyPI)

______________________________________________________________________

## Permissions

```yaml
permissions:
  contents: read
  id-token: write   # REQUIRED for PyPI/TestPyPI Trusted Publishing (OIDC)
```

- `contents: read` — required for checkout
- `id-token: write` — required for OIDC authentication with PyPI/TestPyPI

______________________________________________________________________

## Concurrency

```yaml
concurrency:
  group: pypi-${{ github.ref }}
  cancel-in-progress: false
```

Ensures that concurrent release jobs for the same ref don’t overlap.

______________________________________________________________________

## Jobs

### 1. publish-pypi

- **Condition:** Only runs for final releases (`!contains(github.ref, '-rc')`)
- **Runs-on:** `ubuntu-latest`
- **Environment:** `pypi`
- **Steps:**
  1. Check out repository
  2. Set up Python 3.12
  3. Build source distribution (sdist) and wheel
  4. Publish to PyPI via `pypa/gh-action-pypi-publish@release/v1`

### 2. publish-testpypi

- **Condition:** Only runs for RC tags (`contains(github.ref, '-rc')`)
- **Runs-on:** `ubuntu-latest`
- **Environment:** `testpypi`
- **Steps:**
  1. Check out repository
  2. Set up Python 3.12
  3. Build sdist and wheel
  4. Publish to TestPyPI using Trusted Publishing (`repository-url: https://test.pypi.org/legacy/`)

### 3. github-release

- **Condition:** Runs only for final releases
- **Needs:** `publish-pypi` (must succeed first)
- **Steps:**
  1. Check out repository
  2. Create a GitHub Release using `softprops/action-gh-release@v2`
     - `tag_name` and `name` from the pushed tag
     - Auto-generate release notes

______________________________________________________________________

## Summary

- Push **`vX.Y.Z-rcN`** → Publishes to **TestPyPI**
- Push **`vX.Y.Z`** → Publishes to **PyPI** and creates a GitHub Release

______________________________________________________________________

## Recommended placement

Save this file at:

```
docs/ci/release-workflow.md
```

and link it from your MkDocs navigation (e.g., under a new **CI/CD** or **Workflows** section).
