<!--
topmark:header:start

  project      : TopMark
  file         : python-support.md
  file_relpath : docs/usage/python-support.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Python support policy

This page defines TopMark's Python-runtime support lifecycle. It applies to package metadata,
runtime checks, local validation, CI, and published-artifact validation.

______________________________________________________________________

## Support window

TopMark supports every final Python feature-release series that CPython currently lists as receiving
bugfix or security updates. It also supports the most recently end-of-life (EOL) series for one year
after its upstream EOL date.

This policy follows the [CPython version-status page](https://devguide.python.org/versions/). It
does not promise support for unreleased Python versions, prereleases, or CPython's development
branch. TopMark may test those versions before their final release, but adds them to its published
support range only after final-release validation succeeds.

______________________________________________________________________

## Current support

| Python series | Upstream status | TopMark status                                 |
| ------------- | --------------- | ---------------------------------------------- |
| 3.11–3.15     | Maintained      | Supported                                      |
| 3.10          | EOL             | Compatibility-supported through 1 October 2027 |

Python 3.10 reached upstream EOL on 1 October 2026. Its temporary TopMark support gives existing
projects time to upgrade without immediately losing access to current TopMark releases.

______________________________________________________________________

## Security and upgrade guidance

Compatibility support for an upstream-EOL Python series is not security support for that
interpreter. TopMark cannot patch CPython or its bundled libraries. Use a maintained Python version
for new deployments and security-sensitive environments.

When using the EOL compatibility window, plan and test an upgrade before the stated end date. Once
that window closes, a TopMark release may raise its minimum supported Python version, update package
metadata, and remove the retired interpreter from its validation matrix.

______________________________________________________________________

## Maintaining the policy

TopMark records its supported range in `pyproject.toml`. The Nox and CI test matrices derive from
that metadata, while published-artifact validation retains an explicit matrix that must be updated
with the same release change.

When a Python series is added or retired, maintainers update the package metadata, runtime version
checks, CI and artifact-validation matrices, contributor and installation documentation, and the
changelog. The change is validated across the resulting supported matrix before release.

See also:

- [Installation guide](../install.md)
- [Contributor guide](../contributing.md)
- [Test and validation architecture](../ci/test-validation.md)
