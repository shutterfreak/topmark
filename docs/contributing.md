<!--
topmark:header:start

  project      : TopMark
  file         : contributing.md
  file_relpath : docs/contributing.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Contributor guide

This page exists to preserve internal documentation links when the MkDocs site is built in strict
mode. The canonical contributor guide lives at the repository root.

## Where things live

- **README.md** - overview, features, usage, examples
- **INSTALL.md** - installation and development setup
- **CONTRIBUTING.md** - canonical contributor guide at the repository root
- **docs/** - MkDocs documentation site
  - **docs/index.md** - docs landing page
  - **docs/usage/** - detailed usage guides (pre-commit, header placement, file types, ...)
- **docs/ci/** - CI workflows, release automation, published-artifact validation, and dependency
  automation
  - **docs/api/** - API reference
- **Makefile** - development automation (setup, lint, test, docs, packaging)
- **.pre-commit-config.yaml** - enabled hooks for this repo
- **.pre-commit-hooks.yaml** - hook definitions exported to consumer repos

______________________________________________________________________

## Architecture overview

TopMark uses a layered architecture:

- **TOML layer** (`topmark.toml`) - configuration discovery, parsing, and whole-source TOML
  validation (unknown sections/keys, malformed section shapes), plus TOML-source-local options (e.g.
  `[config].root`, `strict`)
- **Configuration layer** (`topmark.config`) - layered configuration merging into `FrozenConfig` and
  staged config-loading validation (TOML-source, merged-config, runtime-applicability diagnostics)
- **Runtime layer** (`topmark.runtime`) - runtime overlays and execution-time behavior

{% include-markdown "\_snippets/config-strictness.md" %}

Internally, configuration validation is represented as staged validation logs. Flattened
compatibility views of diagnostics are derived only during reporting, exception handling, and
machine-readable output emission.

For 1.0, this boundary is intentional: staged validation remains primarily internal, while public
reporting and CLI, API, and machine-readable output expose only the flattened compatibility
diagnostics contract and machine-readable compatibility surface.

{% include-markdown "\_snippets/terminology.md" %}

______________________________________________________________________

## See also

- [`Configuration overview`](./configuration/index.md)
- [`Architecture`](./dev/architecture.md)
- [`CI workflow`](./ci/ci-workflow.md)
- [`Release workflow`](./ci/release-workflow.md)

Read the full contributor guide on GitHub:
[CONTRIBUTING.md](https://github.com/shutterfreak/topmark/blob/main/CONTRIBUTING.md)

TopMark package versioning is Git-tag-driven through `setuptools-scm`. Contributor-facing release
guidance for the stable 1.x line is summarized in the root `CONTRIBUTING.md` file.

The detailed maintainer release process, including the artifact trust boundary, prerelease and final
release workflows, and post-publication validation expectations, is documented in
[Release process](./dev/release-process.md).

If you are viewing this from the published documentation site, the link above opens the same
document in the repository with GitHub-native rendering and navigation.
