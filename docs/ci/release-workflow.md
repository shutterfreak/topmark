<!--
topmark:header:start

  project      : TopMark
  file         : release-workflow.md
  file_relpath : docs/ci/release-workflow.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Release workflow (GitHub Actions → PyPI/TestPyPI)

TopMark uses GitHub Actions with **Trusted Publishing** (OIDC) to release to PyPI/TestPyPI.\
The workflow runs automatically when version tags are pushed. You can also manually trigger a dry-run.

## How to cut a release (maintainers)

1. Update the version in `pyproject.toml`.

1. Commit and push your changes.

1. Tag the release:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

   For a release candidate (RC):

   ```bash
   git tag vX.Y.Z-rc1
   git push origin vX.Y.Z-rc1
   ```

- Tags like `vX.Y.Z-rcN` → publish to **TestPyPI**
- Tags like `vX.Y.Z` → publish to **PyPI** and create a GitHub Release

## Workflow overview

Defined in `.github/workflows/release.yml`. The pipeline gates publishing on **docs** and **tests**.

### Triggers

- Final release: tags matching `v*.*.*`
- Release candidate: tags matching `v*.*.*-rc*`
- Manual: `workflow_dispatch` with `dry_run=true` to run docs only (no publish)

### Permissions

```yaml
permissions:
  contents: read    # required for checkout
  id-token: write   # required for authentication (OIDC) with PyPI/TestPyPI
```

### Concurrency

Ensures concurrent release jobs for the same ref don’t overlap:

```yaml
concurrency:
  group: pypi-${{ github.ref }}
  cancel-in-progress: false
```

### Jobs

1. **build-docs** (always)

   - Installs docs extras from **pinned** `requirements-docs.txt`
   - Uses `cache-dependency-path` for cache invalidation (`requirements-*.txt`, `constraints.txt`)
   - `mkdocs build --strict`

1. **tests** (always)

   - Installs dev extras from **pinned** `requirements-dev.txt`
   - Uses `cache-dependency-path` for cache invalidation
   - Runs smoke tests: `tox -e py313`
   - Runs public API snapshot: `tox -e py313-api`
   - Exports `PIP_CONSTRAINT=constraints.txt` so tox-created envs also honor pins

1. **publish-package** (skipped when `workflow_dispatch` with `dry_run=true`)

   - Verifies **version ↔ tag** match (PEP 440; e.g. `v1.2.3-rc1` → `1.2.3rc1`)
   - Builds **sdist + wheel** and verifies artifacts exist
   - If tag contains `-rc`, first checks **TestPyPI** does **not** already have that version
   - Publishes with `pypa/gh-action-pypi-publish@release/v1`
     - RC tags (`-rcN`) → **TestPyPI** (`repository-url: https://test.pypi.org/legacy/`, `skip-existing: true`)
     - Final tags → **PyPI**

1. **github-release** (final releases only)

   - Creates a GitHub Release via `softprops/action-gh-release@v2`
   - Uses the pushed tag and auto-generates notes

### Environments

Publishing targets are selected automatically:

```yaml
environment: ${{ contains(github.ref, '-rc') && 'testpypi' || 'pypi' }}
```

Use the repo’s **Environments** to set any environment-specific protections.

## Summary

- Push **`vX.Y.Z-rcN`** → Build docs & tests, publish to **TestPyPI**
- Push **`vX.Y.Z`** → Build docs & tests, publish to **PyPI**, create a GitHub Release
- Manual **`workflow_dispatch`** with `dry_run=true` → Build docs only (no publish)
