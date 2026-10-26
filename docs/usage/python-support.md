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
bugfix or security updates. When CPython reaches end of life (EOL), TopMark retires that series from
support in the next applicable TopMark release.

This policy follows the [CPython version-status page](https://devguide.python.org/versions/). It
does not promise support for unreleased Python versions, prereleases, or CPython's development
branch. TopMark may test those versions before their final release, but adds them to its published
support range only after final-release validation succeeds.

______________________________________________________________________

## Current support

| Python series | Upstream status | TopMark status |
| ------------- | --------------- | -------------- |
| 3.11-3.15     | Maintained      | Supported      |

TopMark 3.0 and later require Python 3.11 or later. Older TopMark releases retain the support window
published with those releases.

______________________________________________________________________

## Lifecycle transitions

- When CPython publishes a release candidate for a new feature-release series, TopMark begins
  compatibility and packaging readiness work. A release candidate does not itself create a TopMark
  support commitment.
- When CPython publishes the final release, TopMark adds that series to its supported range after
  final validation succeeds.
- When CPython reaches EOL, TopMark prepares and releases the corresponding retirement change:
  package metadata, runtime bounds, test and CI matrices, artifact validation, dependency
  resolution, documentation, and release notes.

______________________________________________________________________

## Rationale and upgrade guidance

This policy aligns TopMark's supported runtimes with CPython's maintained releases. It reduces
compatibility and security risk by allowing TopMark to adopt dependency updates that no longer
support retired Python versions, while giving users a clear, predictable upgrade path.

TopMark cannot patch CPython or its bundled libraries. Use a maintained Python version for new
deployments and security-sensitive environments. Plan and test an upgrade before your Python series
reaches EOL.

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
