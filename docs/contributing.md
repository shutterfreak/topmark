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

## 📂 Where things live

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

## 🧠 Architecture overview

TopMark uses a layered architecture:

- **TOML layer** (`topmark.toml`) — config discovery, parsing, and whole-source TOML schema
  validation (unknown sections/keys, malformed shapes), plus source-local options (e.g.
  `[config].root`, `strict_config_checking`)
- **Config layer** (`topmark.config`) — layered merge into `Config` and staged
  config-loading/preflight validation (TOML-source, merged-config, runtime-applicability
  diagnostics)
- **Runtime layer** (`topmark.runtime`) — execution-time behavior

Internally, configuration validation is represented as staged validation logs. A flattened
compatibility view of diagnostics is derived only at reporting, exception, and machine-output
boundaries.

For 1.0, this boundary is intentional: staged validation remains primarily internal, while public
reporting and machine/API/CLI surfaces expose only the flattened compatibility diagnostics contract.

See also:

- [`Configuration overview`](./configuration/index.md)
- [`Architecture`](./dev/architecture.md)
- [`CI workflow`](./ci/ci-workflow.md)
- [`Release workflow`](./ci/release-workflow.md)

Read the full contributor guide on GitHub:
[CONTRIBUTING.md](https://github.com/shutterfreak/topmark/blob/main/CONTRIBUTING.md)

- <https://github.com/shutterfreak/topmark/blob/main/CONTRIBUTING.md>

TopMark’s package versioning is Git-tag-driven via `setuptools-scm`; contributor and release
workflow details are documented in the root `CONTRIBUTING.md` and the CI/release docs linked above.

The release process uses an artifact-based workflow:

- CI builds and uploads release artifacts on tag pushes
- The release workflow downloads and verifies these artifacts before publishing

This separation between build (CI) and publish (release workflow) avoids executing repository code
in privileged contexts and improves supply-chain security.

If you’re viewing this on the published docs site, the link above opens the same document in the
repository with richer GitHub rendering.
