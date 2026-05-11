<!--
topmark:header:start

  project      : TopMark
  file         : published-artifact-validation.md
  file_relpath : docs/ci/published-artifact-validation.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Published Artifact Validation Workflow

This page documents `.github/workflows/published-artifact-validation.yml`.

The published artifact validation workflow verifies that a package already published to PyPI or
TestPyPI installs and behaves correctly in clean environments across the supported platform and
Python-version matrix.

## Purpose

The published artifact validation workflow validates the user-visible installation experience from
published packages rather than from the repository source tree.

Unlike the normal CI workflow, this workflow does not validate repository code, editable installs,
local builds, or unpublished artifacts. Instead, it validates exactly what end users receive from
PyPI or TestPyPI.

This helps detect issues such as:

- missing runtime dependencies;
- packaging metadata problems;
- wheel or source-distribution installation regressions;
- TestPyPI or PyPI dependency-resolution issues;
- platform-specific installation failures;
- missing console entry points;
- public API import failures.

______________________________________________________________________

## Trigger Conditions

| Trigger             | When it runs          | Purpose                                                     |
| ------------------- | --------------------- | ----------------------------------------------------------- |
| `workflow_dispatch` | Manual maintainer run | Validate an already published package from PyPI or TestPyPI |

The workflow is intentionally manual-only. Published-package validation is usually performed after a
prerelease or final release has already been published.

______________________________________________________________________

## Permissions and Trust Boundary

The workflow uses read-only repository permissions:

```yaml
permissions:
  contents: read
```

The workflow does not:

- publish packages;
- upload artifacts;
- create releases;
- require OIDC Trusted Publishing;
- consume repository build artifacts.

Instead, it installs TopMark from the selected package index into clean runner environments.

The workflow intentionally validates published artifacts in isolation from the repository source
tree. No local checkout build logic or editable installation path is used.

______________________________________________________________________

## Workflow Inputs

The workflow exposes manual `workflow_dispatch` inputs:

| Input     | Required | Default    | Purpose                               |
| --------- | -------- | ---------- | ------------------------------------- |
| `version` | Yes      | None       | Published TopMark version to validate |
| `index`   | Yes      | `testpypi` | Package index to install from         |

Example manual run:

```text
version: 1.0.0b2
index: testpypi
```

Supported package indexes are:

| Value      | Meaning                                               |
| ---------- | ----------------------------------------------------- |
| `testpypi` | Validate prereleases or staged releases from TestPyPI |
| `pypi`     | Validate final releases from PyPI                     |

______________________________________________________________________

## Jobs and Validation Scope

| Job                             | Purpose                                                                                                 | Main tools                             |
| ------------------------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| `published-artifact-validation` | Install and validate published TopMark packages across the supported platform and Python-version matrix | `pip`, `topmark`, `importlib.metadata` |

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

The matrix uses:

```yaml
fail-fast: false
```

so failures on one platform or Python version do not prevent validation of the remaining matrix
environments.

For each matrix environment, the workflow:

1. sets up Python;
1. upgrades `pip`;
1. installs TopMark from PyPI or TestPyPI;
1. verifies the installed distribution version;
1. configures UTF-8 console behavior for deterministic cross-platform output handling;
1. creates a temporary validation workspace;
1. runs representative CLI validation checks;
1. runs a minimal public API validation check.

The workflow validates representative CLI entry points such as:

```bash
topmark version
topmark config defaults
topmark registry filetypes
topmark probe README.md
topmark check --apply README.md --no-color
topmark check README.md --no-color
cp README.md STRIPME.md
topmark strip --apply STRIPME.md --no-color
topmark strip STRIPME.md --no-color
```

It also validates the public Python API:

```python
from pathlib import Path

from topmark.api import probe

result = probe([Path("README.md")])
```

These checks validate:

- console entry-point installation;
- runtime dependency correctness;
- CLI startup behavior;
- registry initialization;
- probe pipeline behavior;
- basic pipeline execution;
- importability of the installed package;
- public API availability.

______________________________________________________________________

## Artifact Handling

This workflow does not produce, consume, or publish build artifacts.

Instead, it validates packages already published to PyPI or TestPyPI.

The workflow intentionally validates the package as an external consumer would install it from a
package index. This complements the CI and release workflows, which validate and publish artifacts
before publication.

For TestPyPI installs, the workflow uses:

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  "topmark==<version>"
```

because TestPyPI does not mirror the complete PyPI dependency ecosystem.

This ensures:

- TopMark itself is installed from TestPyPI;
- normal dependencies resolve from PyPI when unavailable on TestPyPI.

______________________________________________________________________

## Local Reproduction

The workflow cannot be fully reproduced locally because it validates packages already published to a
package index across the GitHub Actions platform matrix.

The closest local reproduction path is:

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  "topmark==1.0.0b2"
```

followed by representative CLI validation commands:

```bash
topmark version
topmark probe README.md
topmark check README.md --no-color
```

and a minimal API validation check:

```bash
python - <<'PY'
from pathlib import Path

from topmark.api import probe

result = probe([Path("README.md")])
print(result)
PY
```

Local validation can confirm basic installability and runtime behavior, but it does not reproduce
the full GitHub Actions platform matrix or workflow environment.

______________________________________________________________________

## Maintenance Notes

Prefer validating prereleases on TestPyPI before final releases.

When using this workflow:

- use the exact version published by the release workflow;
- validate prereleases from TestPyPI before publishing finals to PyPI;
- confirm package metadata is visible before running validation;
- investigate dependency-resolution failures separately from repository-source CI failures;
- remember that this workflow validates published artifacts, not local source trees.

The validation workspace intentionally starts without repository-specific TopMark configuration.
This ensures the workflow validates installed-package defaults and CLI behavior rather than
repository policy configuration.

GitHub Actions are pinned to commit SHAs. Use the [GitHub Action pin audit](./action-pin-audit.md)
to detect drift between workflow files and local composite actions.

______________________________________________________________________

## Related Pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
