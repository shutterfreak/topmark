<!--
topmark:header:start

  project      : TopMark
  file         : contributing.md
  file_relpath : docs/contributing.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Contributing

This page exists to keep MkDocs **strict** mode happy by providing a stable in-site link target. The
canonical contributor guide lives at the repository root.

## Where things live

- **README.md** — overview, features, usage, examples
- **INSTALL.md** — installation & development setup
- **CONTRIBUTING.md** — canonical contributor guide at the repository root
- **docs/** — MkDocs documentation site
  - **docs/index.md** — docs landing page
  - **docs/usage/** — detailed usage guides (pre-commit, header placement, file types, …)
  - **docs/ci/** — CI/CD workflows, release automation, Dependabot policy
  - **docs/api/** — API reference
- **Makefile** — development automation (setup, lint, test, docs, packaging)
- **.pre-commit-config.yaml** — enabled hooks for this repo
- **.pre-commit-hooks.yaml** — hook definitions exported to consumer repos

______________________________________________________________________

## Architecture overview

TopMark uses a layered architecture:

- **TOML layer** (`topmark.toml`) — config discovery, parsing, and whole-source TOML schema
  validation (unknown sections/keys, malformed shapes), plus source-local options (e.g.
  `[config].root`, `strict`)
- **Config layer** (`topmark.config`) — layered merge into `Config` and staged
  config-loading/preflight validation (TOML-source, merged-config, runtime-applicability
  diagnostics)
- **Runtime layer** (`topmark.runtime`) — execution-time behavior

{% include-markdown "\_snippets/config-strictness.md" %}

Internally, configuration validation is represented as staged validation logs. A flattened
compatibility views of diagnostics are derived only during reporting, exception handling, and
machine-readable output emission

For 1.0, this boundary is intentional: staged validation remains primarily internal, while public
reporting and CLI, API, and machine-readable output expose only the flattened compatibility
diagnostics contract.

See also:

- [`Configuration overview`](./configuration/index.md)
- [`Architecture`](./dev/architecture.md)
- [`CI workflow`](./ci/ci-workflow.md)
- [`Release workflow`](./ci/release-workflow.md)

Read the full contributor guide on GitHub:
[CONTRIBUTING.md](https://github.com/shutterfreak/topmark/blob/main/CONTRIBUTING.md)

- <https://github.com/shutterfreak/topmark/blob/main/CONTRIBUTING.md>

TopMark's package versioning is Git-tag-driven via `setuptools-scm`. Contributor-facing release
guidance is summarized in the root `CONTRIBUTING.md` file.

The detailed maintainer release process, including the artifact trust boundary, prerelease/final
release flow, and post-publication validation expectations, is documented in
[Release Process](./dev/release-process.md).

If you’re viewing this on the published docs site, the link above opens the same document in the
repository with richer GitHub rendering.
