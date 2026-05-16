<!--
topmark:header:start

  project      : TopMark
  file         : published-artifact-validation.md
  file_relpath : docs/ci/published-artifact-validation.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Published artifact validation workflow

This page documents `.github/workflows/published-artifact-validation.yml`.

The published artifact validation workflow verifies that a package already published to PyPI or
TestPyPI installs and behaves correctly in clean environments across the supported platform and
Python-version matrix.

{% include-markdown "\_snippets/terminology.md" %}

## Purpose

The published artifact validation workflow validates the user-visible installation experience from
published packages rather than from repository source trees.

Unlike the normal CI workflow, this workflow does not validate repository source code, editable
installs, local builds, or unpublished artifacts. Instead, it validates exactly what end users
install from PyPI or TestPyPI.

This helps detect issues such as:

- missing runtime dependencies;
- packaging metadata problems;
- wheel or source-distribution installation regressions;
- TestPyPI or PyPI dependency-resolution issues;
- platform-specific installation failures;
- missing console entry points;
- public API import failures.

______________________________________________________________________

## Trigger conditions

| Trigger             | When it runs          | Purpose                                                     |
| ------------------- | --------------------- | ----------------------------------------------------------- |
| `workflow_dispatch` | Manual maintainer run | Validate an already published package from PyPI or TestPyPI |

The workflow intentionally remains manual-only. Published-package validation is usually performed
after a prerelease or final release has already been published.

______________________________________________________________________

## Permissions and trust boundary

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

Instead, it installs TopMark from the selected package index into clean GitHub Actions runner
environments.

The workflow intentionally validates published artifacts in isolation from repository source trees.
No local checkout build logic or editable installation path is used.

______________________________________________________________________

## Workflow Inputs

| Input            | Required | Default    | Purpose                                                              |
| ---------------- | -------- | ---------- | -------------------------------------------------------------------- |
| `version`        | Yes      | None       | Published TopMark version to validate                                |
| `index`          | Yes      | `testpypi` | Package index to install from                                        |
| `platform`       | Yes      | `all`      | Restrict validation to a specific platform subset                    |
| `python-version` | Yes      | `all`      | Restrict validation to a specific Python-version subset              |
| `log-level`      | Yes      | `none`     | Optional runtime logging level for installed-package validation runs |

Example manual run:

```text
version: 1.0.0b3
index: testpypi
platform: windows-latest
python-version: 3.11
log-level: DEBUG
```

Supported package indexes are:

| Value      | Meaning                                               |
| ---------- | ----------------------------------------------------- |
| `testpypi` | Validate prereleases or staged releases from TestPyPI |
| `pypi`     | Validate final releases from PyPI                     |

Supported platform selections are:

| Value            | Meaning                          |
| ---------------- | -------------------------------- |
| `all`            | Run the complete platform matrix |
| `ubuntu-latest`  | Validate Linux only              |
| `macos-latest`   | Validate macOS only              |
| `windows-latest` | Validate Windows only            |

Supported Python-version selections are:

| Value  | Meaning                                          |
| ------ | ------------------------------------------------ |
| `all`  | Run the complete supported Python-version matrix |
| `3.10` | Validate Python 3.10 only                        |
| `3.11` | Validate Python 3.11 only                        |
| `3.12` | Validate Python 3.12 only                        |
| `3.13` | Validate Python 3.13 only                        |
| `3.14` | Validate Python 3.14 only                        |

Supported runtime logging selections are:

| Value     | Meaning                                                |
| --------- | ------------------------------------------------------ |
| `none`    | Disable explicit TopMark runtime logging configuration |
| `TRACE`   | Enable maximum runtime diagnostic logging              |
| `DEBUG`   | Enable detailed runtime diagnostic logging             |
| `INFO`    | Enable informational runtime logging                   |
| `WARNING` | Enable warning-only runtime logging                    |
| `ERROR`   | Enable error-only runtime logging                      |

______________________________________________________________________

## Jobs and validation scope

| Job                             | Purpose                                                                                                 | Main tools                             |
| ------------------------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| `published-artifact-validation` | Install and validate published TopMark packages across the supported platform and Python-version matrix | `pip`, `topmark`, `importlib.metadata` |

By default, the workflow validates installation across:

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

The `platform` and `python-version` workflow inputs can reduce the matrix to a single platform or
single Python version when reproducing or diagnosing platform-specific installation or runtime
issues.

The matrix uses:

```yaml
fail-fast: false
```

so failures on one platform or Python version do not prevent validation of the remaining matrix
combinations.

The workflow also supports optional runtime diagnostic logging through the `TOPMARK_LOG_LEVEL`
environment variable exposed through the `log-level` workflow input.

This is primarily intended for diagnosing installed-package runtime failures in isolated runner
environments, especially platform-specific issues such as Windows filesystem or permission behavior.

For each matrix environment, the workflow:

1. sets up Python;
1. upgrades `pip`;
1. installs TopMark from PyPI or TestPyPI;
1. verifies the installed distribution version;
1. configures UTF-8 console behavior for deterministic cross-platform output handling;
1. creates a temporary validation workspace;
1. runs representative CLI validation checks;
1. optionally emits runtime diagnostic logs from the installed package;
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

On Windows runners, the workflow also executes additional diagnostic inspection commands when
investigating platform-specific failures. These diagnostics intentionally expose workspace state,
machine-readable command output, and runtime logging behavior from the installed package.

The workflow also validates the public Python API:

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

## Artifact handling

This workflow does not produce, consume, or publish build artifacts.

Instead, it validates packages already published to PyPI or TestPyPI.

The workflow intentionally validates the package exactly as an external consumer would install it
from a package index. This complements the CI and release workflows, which validate and publish
release artifacts before package-index publication.

For TestPyPI installs, the workflow uses:

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  "topmark==<version>"
```

because TestPyPI does not mirror the complete PyPI dependency ecosystem or package availability.

This ensures:

- TopMark itself is installed from TestPyPI;
- normal dependencies resolve from PyPI when unavailable on TestPyPI.

______________________________________________________________________

## Local reproduction

The workflow cannot be fully reproduced locally because it validates packages already published to a
package index across the GitHub Actions platform matrix.

The closest local reproduction workflow is:

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

Local validation can confirm basic installation and runtime behavior, but it does not reproduce the
full GitHub Actions platform matrix or workflow environment.

______________________________________________________________________

## Maintenance notes

Prefer validating prereleases on TestPyPI before final releases.

When using this workflow:

- use the exact version published by the release workflow;
- validate prereleases from TestPyPI before publishing finals to PyPI;
- use restricted platform or Python-version subsets when reproducing platform-specific failures;
- temporarily enable `DEBUG` or `TRACE` runtime logging when diagnosing installed-package runtime
  behavior;
- confirm package metadata is visible before running validation;
- investigate dependency-resolution failures separately from repository-source validation failures;
- remember that this workflow validates published artifacts, not local source trees.

The validation workspace intentionally starts without repository-specific TopMark configuration.
This ensures the workflow validates installed-package defaults, runtime logging behavior, and CLI
behavior rather than repository-specific policy configuration.

GitHub Actions are pinned to commit SHAs. Use the [GitHub Action pin audit](./action-pin-audit.md)
to detect drift between workflow files and local composite actions.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
