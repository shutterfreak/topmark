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

This document describes the **automated package publish pipeline** defined in
`.github/workflows/release.yml` (`Publish package`).

______________________________________________________________________

## Trigger Conditions

The release workflow runs automatically when:

- The **CI** workflow completes successfully for a commit that has exactly one matching release tag
  (for example `v1.0.0`, `v1.0.0rc1`, `v1.0.0-a1`)

It supports both **final** and **pre-release** (rc/a/b) versions using **PEP 440 normalization**
derived from Git tags via `setuptools-scm`.

If no matching release tag points at the CI commit, the workflow exits cleanly without publishing.
If multiple matching release tags point at the same commit, preflight fails rather than choosing one
implicitly.

______________________________________________________________________

## Job Summary

| Job                 | Purpose                                                                                                                                 |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **preflight**       | Resolve release context, tag, version, and publish eligibility                                                                          |
| **details**         | Verify downloaded CI-built artifacts and release metadata                                                                               |
| **publish-package** | Verify and publish prebuilt artifacts to [PyPI](https://pypi.org/project/topmark/) / [TestPyPI](https://test.pypi.org/project/topmark/) |
| **github-release**  | Create a GitHub release for final (non-prerelease) tags                                                                                 |

______________________________________________________________________

## 🧱 Core Design

The release workflow is intentionally **artifact-only** and does not execute repository build logic.

Prereleases are published to [TestPyPI](https://test.pypi.org/project/topmark/) for validation,
while final releases are published to [PyPI](https://pypi.org/project/topmark/).

### Trusted Publishing via OIDC

No API tokens are stored — PyPI and TestPyPI releases use **Trusted Publishing** with OIDC
credentials.

### 🧰 Caching

Each job restores the uv cache and keys it from the canonical dependency inputs:

```yaml
- name: Cache uv
  uses: actions/cache@v5
  with:
      path: ~/.cache/uv
      key: ${{ runner.os }}-py${{ steps.setup-python.outputs.python-version }}-${{ hashFiles('pyproject.toml', 'uv.lock', 'noxfile.py') }}
```

### 🧩 Version Validation

Before publishing, the workflow ensures:

- The **SCM-derived version** (via `setuptools-scm`) matches the release tag
- The version does not already exist on the target index
- (Final releases only) the new version is greater than the latest final on PyPI
- Exactly **one** matching release tag points at the CI commit; ambiguous multi-tag release commits
  are rejected during preflight

Version validation is performed on **CI-built artifacts (wheel + sdist)** downloaded from the CI
workflow, ensuring that the artifacts published to
[TestPyPI](https://test.pypi.org/project/topmark/) or [PyPI](https://pypi.org/project/topmark/) are
exactly those validated during CI.

______________________________________________________________________

## 🔁 Release Flow

1. Commit changes (no manual version bump required)

1. Tag the release with exactly one release-style tag on the target commit (version is derived from
   Git tags):

   ```bash
   git commit -am "chore(release): 1.0.0"
   git tag v1.0.0
   git push origin main --tags
   ```

1. CI runs and passes (including building release artifacts)

1. Release workflow downloads and verifies CI-produced artifacts

1. Artifacts are published to [TestPyPI](https://test.pypi.org/project/topmark/) (prereleases) or
   [PyPI](https://pypi.org/project/topmark/) (final releases)

1. GitHub release is created automatically (for non-prereleases)

______________________________________________________________________

## 🔖 Channels

| Tag          | Channel  | Example           |
| ------------ | -------- | ----------------- |
| `v1.0.0`     | PyPI     | Stable            |
| `v1.0.0rc1`  | TestPyPI | Release candidate |
| `v1.0.0-rc1` | TestPyPI | Release candidate |
| `v1.0.0a1`   | TestPyPI | Alpha             |
| `v1.0.0-a1`  | TestPyPI | Alpha             |
| `v1.0.0b1`   | TestPyPI | Beta              |
| `v1.0.0-b1`  | TestPyPI | Beta              |

______________________________________________________________________

## 🧠 Notes for Maintainers

- Ensure release tags follow the expected versioning scheme (PEP 440-compatible, e.g. `v1.0.0`,
  `v1.0.0rc1`, `v1.0.0-a1`).

- Do not place multiple release-style tags on the same commit. The release workflow now fails
  preflight rather than choosing between ambiguous matching tags implicitly.

- Prefer compact PEP 440 tag forms (e.g. `v1.0.0rc1`) for new releases; dashed variants remain
  supported for backward compatibility.

- Delete stale `.nox`, `*.egg-info` or `.venv` dirs before local build tests.

- Validate with:

  ```bash
  nox -s docs
  nox -s links_site
  nox -s links_all

  uv build
  ```

- Run `make verify` before tagging.

GitHub Actions used by this workflow are pinned to specific commit hashes for supply-chain security.

Dependabot periodically opens PRs updating these hashes. Maintainers should review and merge these
PRs once CI passes.

See [`docs/ci/dependabot.md`](./dependabot.md) for details.
