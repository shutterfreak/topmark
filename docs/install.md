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

## Upgrade from TopMark 0.11.x or earlier

TopMark 1.0 includes breaking changes to:

- CLI options and reporting behavior;
- pre-commit hook arguments;
- TOML configuration structure and runtime policy settings;
- TEXT, Markdown, JSON, and NDJSON output contracts.

Before upgrading an existing repository, review:

- [Upgrading to TopMark 1.0](usage/upgrading-to-1.0.md)

______________________________________________________________________

## Further reading

- [Getting started](usage/getting-started.md)
- [Usage documentation](usage/index.md)
- [Configuration overview](configuration/index.md)
- [CI and validation](ci/index.md)
- [Contributing](contributing.md)
