<!--
topmark:header:start

  project      : TopMark
  file         : install.md
  file_relpath : docs/install.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Installation guide

This page summarizes TopMark installation and development-environment setup.

The canonical installation and contributor setup guide lives at the repository root in `INSTALL.md`.

TopMark currently supports Python 3.10-3.15. Python 3.10 is in its temporary EOL compatibility
window; use Python 3.11 or later for new or security-sensitive deployments. See the
[Python support policy](usage/python-support.md) for the supported-version lifecycle and transition
dates.

Read the canonical installation guide on GitHub:

- <https://github.com/shutterfreak/topmark/blob/main/INSTALL.md>

If you are viewing this from the published documentation site, the link above opens the same
document in the repository with GitHub-native rendering and navigation.

## Install from PyPI

```bash
pip install topmark
```

Verify the CLI:

```bash
topmark version
```

For a guided first setup, continue with:

- [Getting started](usage/getting-started.md)

______________________________________________________________________

## Upgrade an existing repository

TopMark major releases can change CLI, configuration, and machine-output contracts. Before
upgrading, identify the installed version and follow every major-version guide your repository
crosses.

Choose the applicable version-boundary guide:

- [Upgrading TopMark](usage/upgrading.md)

______________________________________________________________________

## Further reading

- [Getting started](usage/getting-started.md)
- [Usage documentation](usage/index.md)
- [Configuration overview](configuration/index.md)
- [CI and validation](ci/index.md)
- [Contributing](contributing.md)
