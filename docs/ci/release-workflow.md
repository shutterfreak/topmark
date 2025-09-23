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
The release workflow runs on:

- Direct **tag pushes** (`v*`)
- **After CI completes successfully** via `workflow_run` on the `CI` workflow

> **RC vs final:**\
> Tags with a suffix (`-rcN`, `-aN`, `-bN`) go to **TestPyPI**.\
> Final tags (`vX.Y.Z`) go to **PyPI** and create a GitHub Release.

## How to cut a release (maintainers)

1. Update the version in `pyproject.toml` (PEP 440).

1. Commit and push your changes.

1. Tag and push:

   ```bash
   # Final release
   git tag vX.Y.Z
   git push origin vX.Y.Z

   # Release candidate
   git tag vX.Y.Z-rc1
   git push origin vX.Y.Z-rc1
   ```

1. Wait for **CI** to finish green. The release workflow will run (via `workflow_run`) and publish.

## Workflow overview

Defined in `.github/workflows/release.yml`. Publishing is gated by **docs** (built here) and **CI success** (gated upstream).

### Triggers

- **push**: tags matching `v*`
- **workflow_run**: when the `CI` workflow has `conclusion: success`

### Permissions

```yaml
permissions:
  contents: read     # required for checkout and reading repo
  id-token: write    # required for PyPI/TestPyPI Trusted Publishing (OIDC)
```

### Concurrency

Ensures release runs for the **same tag/commit** don’t overlap (works for both triggers):

```yaml
concurrency:
  group: >-
    pypi-${{ github.event_name == 'push'
      && github.ref
      || format('sha-{0}', github.event.workflow_run.head_sha) }}
  cancel-in-progress: true
```

- For `push`: group is the tag ref (e.g., `refs/tags/v0.7.0-rc2`)
- For `workflow_run`: group is the CI head SHA (`sha-<commit>`)
- This keeps the push-triggered run and the CI-triggered run serialized per release.

### Jobs

1. **details** (extract release info)

   Discovers the driving tag (from `push` ref or from the CI head SHA), normalizes versions, and decides where to publish:

   - Outputs:
     - `tag` (e.g., `v1.2.3`, `v1.2.3-rc1`)
     - `tag_no_v` (e.g., `1.2.3`, `1.2.3-rc1`)
     - `version_pep440` (e.g., `1.2.3rc1`)
     - `version_semver` (e.g., `1.2.3-rc1`)
     - `is_prerelease` (`true` for `-rc/-a/-b`)
     - `channel` (`testpypi` for pre-release; otherwise `pypi`)
   - Ensures `pyproject.toml` version **equals** the tag’s **PEP 440** value.

1. **build-docs** (always)

   - Installs docs deps from **pinned** `requirements-docs.txt`
   - Uses pip caching with `cache-dependency-path` (`requirements-*.txt`, `constraints.txt`)
   - Builds with `mkdocs build --strict`

1. **publish-package** (needs: `details`, `build-docs`)

   - **Skips** unless:

     - `push` on tag, **or**
     - `workflow_run` of `CI` with `conclusion: success`

   - Environment is selected from `details.outputs.channel`:

     ```yaml
     environment: ${{ needs.details.outputs.channel }}  # 'testpypi' or 'pypi'
     ```

   - Steps:

     - **Ensure target version isn’t already on the index** (PyPI/TestPyPI JSON check)
     - **Build artifacts**: `sdist` + `wheel`
     - **Verify filenames embed the exact version**
     - **Final-only**: ensure the new version is **greater** than the latest **final** on PyPI (PEP 440 compare)
     - **Publish** with `pypa/gh-action-pypi-publish@release/v1`
       - Pre-releases → **TestPyPI** (`repository-url` set, `skip-existing: true`)
       - Finals → **PyPI** (no `repository-url`)

1. **github-release** (final releases only)

   - Creates a GitHub Release via `softprops/action-gh-release@v2`
   - Uses the discovered tag and auto-generated notes

### Test gating

- Full test matrix is handled by the **CI** workflow.
- The release workflow **listens to CI** via `workflow_run` and only publishes when CI has **succeeded**.

### Version & artifacts validation

- Tag ↔ `pyproject.toml` version must match (PEP 440).
- Artifacts must exist and include the exact version in their filenames:
  - `dist/topmark-<version>.tar.gz`
  - `dist/topmark-<version>-*.whl`

## Summary

- Push **`vX.Y.Z-rcN`** → CI runs → Release workflow runs → Build docs → Publish to **TestPyPI**.
- Push **`vX.Y.Z`** → CI runs → Release workflow runs → Build docs → Publish to **PyPI** → Create a GitHub Release.
- Pre-release vs final publishing is **automatic** via the `details` job; no manual toggles needed.
