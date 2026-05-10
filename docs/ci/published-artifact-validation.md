<!--
topmark:header:start

  project      : TopMark
  file         : published-artifact-validation.md
  file_relpath : docs/ci/published-artifact-validation.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# 🧪 Published Artifact Validation Workflow

This document describes the **published-package installation smoke-test pipeline** defined in
`.github/workflows/published-artifact-validation.yml` (`Published Artifact Validation`).

______________________________________________________________________

## Purpose

The install-smoke workflow validates that a **published TopMark package** can be:

- installed successfully
- resolved with the expected dependency set
- executed successfully from a clean environment
- imported through the public Python API

Unlike the normal CI workflow, this workflow validates:

> the published package exactly as end users install it.

This helps detect issues such as:

- missing runtime dependencies
- packaging metadata problems
- wheel/sdist installation regressions
- TestPyPI/PyPI dependency-resolution issues
- platform-specific installation failures
- missing console entry points
- public API import failures

______________________________________________________________________

## Trigger Conditions

The workflow is currently **manual-only** and runs through:

```text
GitHub Actions → Published Artifact Validation → Run workflow
```

It uses `workflow_dispatch` inputs:

| Input     | Purpose                                              |
| --------- | ---------------------------------------------------- |
| `version` | TopMark version to install (for example `1.0.0b2`)   |
| `index`   | Package index to install from (`testpypi` or `pypi`) |

Example:

```text
version: 1.0.0b2
index: testpypi
```

______________________________________________________________________

## 🧱 Core Design

The workflow intentionally validates:

- published artifacts
- dependency resolution
- clean-environment installation behavior

rather than repository source checkouts.

No local repository build logic is used.

### TestPyPI behavior

[TestPyPI](https://test.pypi.org/) does not mirror the full PyPI dependency ecosystem.

For prerelease validation, installation therefore uses:

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  "topmark==<version>"
```

This ensures:

- TopMark itself is installed from TestPyPI
- normal dependencies are resolved from PyPI when unavailable on TestPyPI

______________________________________________________________________

## 🌍 Platform Matrix

The workflow validates installation across:

| Platform | Runner           |
| -------- | ---------------- |
| Linux    | `ubuntu-latest`  |
| macOS    | `macos-latest`   |
| Windows  | `windows-latest` |

and across supported Python versions:

- 3.10
- 3.11
- 3.12
- 3.13
- 3.14

The matrix is configured with:

```yaml
fail-fast: false
```

so platform-specific failures do not prevent validation of the remaining environments.

______________________________________________________________________

## 🔁 Validation Flow

For each matrix environment, the workflow:

1. Sets up Python
1. Upgrades `pip`
1. Installs TopMark from TestPyPI or PyPI
1. Verifies the installed distribution version
1. Creates a temporary smoke-test workspace
1. Runs CLI smoke tests
1. Runs a minimal public API smoke test

______________________________________________________________________

## 🧪 CLI Smoke Tests

The workflow validates representative CLI entry points such as:

```bash
topmark version
topmark config defaults
topmark registry filetypes
topmark probe README.md
topmark check . --no-color
```

These smoke tests help validate:

- console entry-point installation
- runtime dependency correctness
- CLI startup behavior
- registry initialization
- probe pipeline behavior
- basic pipeline execution

______________________________________________________________________

## 🧩 Public API Smoke Test

The workflow also validates the public Python API:

```python
from pathlib import Path

from topmark.api import probe

result = probe([Path("README.md")])
```

This confirms:

- importability of the installed package
- public API availability
- runtime dependency correctness
- basic API execution behavior

______________________________________________________________________

## 🧠 Relationship to Other Workflows

| Workflow                            | Responsibility                                                   |
| ----------------------------------- | ---------------------------------------------------------------- |
| `ci.yml`                            | Validate repository source, tests, QA, docs, and build artifacts |
| `release.yml`                       | Publish CI-validated artifacts to TestPyPI/PyPI                  |
| `published-artifact-validation.yml` | Validate published-package installation and execution behavior   |

The install-smoke workflow complements CI and release validation by verifying the final user-visible
installation experience.

______________________________________________________________________

## 🧾 Notes for Maintainers

- Prefer validating prereleases on TestPyPI before final releases.
- Run install-smoke validation after publishing a beta, RC, or final release.
- Use the same version string that was published by the release workflow.
- If TestPyPI installation fails unexpectedly, first verify:
  - package publication succeeded
  - metadata is visible on TestPyPI
  - required dependencies are available on PyPI
- The workflow intentionally validates the installed package from a clean environment rather than
  editable installs.
- GitHub Actions used by this workflow are pinned to specific commit hashes for supply-chain
  security.

See also:

- [`release-workflow.md`](./release-workflow.md)
- [`ci-workflow.md`](./ci-workflow.md)
- [`dev-validation.md`](./dev-validation.md)
