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

| Job                 | Purpose                                                                |
| ------------------- | ---------------------------------------------------------------------- |
| **details**         | Parse the release tag and extract version, channel, and release name   |
| **build-docs**      | Build docs in strict mode via nox                                      |
| **links-site**      | Validate links in the built MkDocs site (includes generated API pages) |
| **publish-package** | Verify, build, and publish to PyPI/TestPyPI                            |
| **github-release**  | Create a GitHub release for final (non-prerelease) tags                |

______________________________________________________________________

## 🧱 Core Design

### Trusted Publishing via OIDC

No API tokens are stored — PyPI and TestPyPI releases use **Trusted Publishing** with OIDC credentials.

### 🧰 Nox-Centric Docs Build

Documentation is built through **nox** for parity with CI and local development:

```yaml
- name: Bootstrap nox
  run: |
      python -m pip install -U pip
      pip install nox nox-uv uv

- name: Build docs (strict via nox)
  run: |
      nox -s docs
```

### 🧰 Caching

Each job caches both pip and uv directories for faster re-runs:

```yaml
- name: Cache pip & nox
  uses: actions/cache@v4
  with:
      path: |
          ~/.cache/pip
          ~/.cache/uv
      key: ${{ runner.os }}-py${{ steps.setup-python.outputs.python-version }}-${{ hashFiles('noxfile.py', 'pyproject.toml', 'requirements-*.txt', 'constraints.txt') }}
```

### 🔗 Built-site Link Checking

Releases are gated by a **built-site** link check:

- Builds the docs with `mkdocs.linkcheck.yml` (to avoid production-only base URLs)
- Runs `lychee` against the generated `site/` output using `--root-dir` so root-relative links are resolved

This catches broken links in **generated API pages** and theme navigation that source-only checks cannot see.

This is the only stage where links inside generated API documentation are validated.

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
  nox -s docs
  nox -s links_site
  nox -s links_all

  python -m build
  ```

- Run `make verify` before tagging.
