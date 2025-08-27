<!--
topmark:header:start

  file         : release-workflow.md
  file_relpath : docs/ci/release-workflow.md
  project      : TopMark
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Release workflow (GitHub Actions → PyPI/TestPyPI)

TopMark uses GitHub Actions with **Trusted Publishing** to release packages to PyPI.\
This workflow runs automatically when version tags are pushed to the repository.

## How to cut a release (maintainers)

1. Update the version in `pyproject.toml`.

2. Commit and push your changes.

3. Tag the release:

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

Defined in `.github/workflows/release.yml`.

### Triggers

- Final release: tags matching `v*.*.*`
- Release candidate: tags matching `v*.*.*-rc*`

### Permissions

```yaml
permissions:
  contents: read
  id-token: write   # REQUIRED for OIDC with PyPI/TestPyPI
```

- `contents: read` — required for checkout
- `id-token: write` — required for authentication with PyPI/TestPyPI

### Concurrency

Ensures concurrent release jobs for the same ref don’t overlap:

```yaml
concurrency:
  group: pypi-${{ github.ref }}
  cancel-in-progress: false
```

### Jobs

1. **publish-pypi** (final releases only)

   - Runs on `ubuntu-latest`
   - Builds sdist & wheel
   - Publishes to PyPI via `pypa/gh-action-pypi-publish@release/v1`

2. **publish-testpypi** (release candidates only)

   - Runs on `ubuntu-latest`
   - Builds sdist & wheel
   - Publishes to TestPyPI using Trusted Publishing
     (`repository-url: https://test.pypi.org/legacy/`)

3. **github-release** (final releases only, after publish-pypi)

   - Runs on `ubuntu-latest`
   - Creates a GitHub Release using `softprops/action-gh-release@v2`
   - Uses `tag_name` and `name` from the pushed tag
   - Auto-generates release notes

## Summary

- Push **`vX.Y.Z-rcN`** → Publishes to **TestPyPI**
- Push **`vX.Y.Z`** → Publishes to **PyPI** and creates a GitHub Release
