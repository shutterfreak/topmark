<!--
topmark:header:start

  project      : TopMark
  file         : release-workflow.md
  file_relpath : docs/ci/release-workflow.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# 🚀 Release Workflow

This document describes the **automated release pipeline** defined in `.github/workflows/release.yml`.

______________________________________________________________________

## Trigger Conditions

The release workflow runs automatically when:

- A **tag** matching `v*` is pushed (e.g., `v0.9.1`, `v0.10.0-rc1`), **or**
- The **CI** workflow completes successfully for a tagged commit

It supports both **final** and **pre-release** (rc/a/b) versions using **PEP 440 normalization**.

______________________________________________________________________

## Job Summary

| Job                 | Purpose                                                              |
| ------------------- | -------------------------------------------------------------------- |
| **details**         | Parse the release tag and extract version, channel, and release name |
| **build-docs**      | Build docs in strict mode via tox                                    |
| **publish-package** | Verify, build, and publish to PyPI/TestPyPI                          |
| **github-release**  | Create a GitHub release for final (non-prerelease) tags              |

______________________________________________________________________

## 🧱 Core Design

### Trusted Publishing via OIDC

No API tokens are stored — PyPI and TestPyPI releases use **Trusted Publishing** with OIDC credentials.

### Tox-Centric Docs Build

All docs are built through tox for parity with CI and local dev:

```yaml
- name: Bootstrap tox
  run: |
      python -m pip install -U pip
      pip install tox
- name: Build docs (strict via tox)
  run: tox -e docs
```

### 🧰 Caching

Each job caches both pip and `.tox` directories for faster re-runs:

```yaml
- name: Cache pip & tox
  uses: actions/cache@v4
  with:
      path: |
          ~/.cache/pip
          .tox
      key: ${{ runner.os }}-py${{ steps.setup-python.outputs.python-version }}-${{ hashFiles('tox.ini', 'pyproject.toml', 'requirements-*.txt', 'constraints.txt') }}
```

### 🧩 Version Validation

Before publishing, the workflow ensures:

- `pyproject.toml` version matches the tag.
- Version doesn’t already exist on the target index.
- (Final releases only) new version > latest final on PyPI.

### 📦 Package Validation

- Builds sdist + wheel with `python -m build`

- Verifies filenames and version correctness

- Publishes to PyPI or TestPyPI via:

  ```yaml
  uses: pypa/gh-action-pypi-publish@release/v1
  ```

______________________________________________________________________

## 🔁 Release Flow

1. Bump version in `pyproject.toml`

1. Commit & tag:

   ```bash
   git commit -am "chore(release): 0.9.1"
   git tag v0.9.1
   git push origin main --tags
   ```

1. CI runs and passes

1. Release workflow builds docs, validates, and publishes

1. GitHub release is created automatically (for non-prereleases)

______________________________________________________________________

## 🔖 Channels

| Tag           | Channel  | Example           |
| ------------- | -------- | ----------------- |
| `v0.10.0`     | PyPI     | Stable            |
| `v0.10.0-rc1` | TestPyPI | Release candidate |
| `v0.10.0-a1`  | TestPyPI | Alpha             |
| `v0.10.0-b1`  | TestPyPI | Beta              |

______________________________________________________________________

## 🧠 Notes for Maintainers

- Keep **pyproject version** aligned with tags.

- Delete stale `.tox` or `.venv` dirs before local build tests.

- Validate with:

  ```bash
  tox -e docs
  python -m build && twine check dist/*
  ```

- Run `make verify` before tagging.
