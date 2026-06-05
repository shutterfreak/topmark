<!--
topmark:header:start

  project      : TopMark
  file         : index.md
  file_relpath : docs/ci/index.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# CI and validation

TopMark uses a deliberately explicit CI and validation structure. GitHub workflows provide
orchestration, nox sessions define stable reusable validation contracts, pytest markers describe
validation intent, and Makefile targets provide local developer shortcuts.

{% include-markdown "\_snippets/terminology.md" %}

The current design favors clarity, deterministic behavior, and release safety over aggressive
workflow abstraction. Some repetition between workflows is intentional, especially where privileged
release behavior or artifact trust-boundary behavior is involved.

______________________________________________________________________

## Validation architecture

Repository-source validation starts in the main CI workflow and is delegated to nox sessions where
practical. The test suite is further organized with pytest markers so contributors can understand
the intent and expected scope of each test group.

- [CI workflow](./ci-workflow.md) - validates repository source trees, documentation, tests, typing,
  linting, API snapshots, and release artifacts produced from trusted CI runs.
- [Setup Python + nox action](./setup-python-nox-action.md) - documents the shared Python, uv,
  cache, and nox bootstrap layer used by CI jobs.
- [Test validation](./test-validation.md) - explains pytest markers, validation categories, local
  test commands, CI inclusion rules, and how nox and Makefile targets map onto the test suite.
- [Published artifact validation](./published-artifact-validation.md) - validates installation and
  runtime behavior from packages already published to PyPI or TestPyPI in clean runner environments.

______________________________________________________________________

## Release infrastructure

Release publication is intentionally separated from normal repository-source validation. The release
workflow is privileged and consumes artifacts produced by the CI workflow instead of rebuilding them
in the publishing context.

- [Release workflow](./release-workflow.md) - publishes previously built release artifacts after
  release-tag, artifact, and repository validation checks.
- [Published artifact validation](./published-artifact-validation.md) - verifies the package as an
  end user would install it after publication.

______________________________________________________________________

## Dependency automation

Dependency automation is documented separately because it has different triggers, trust boundaries,
and maintenance expectations than repository-source validation or release publication.

- [Dependabot workflow](./dependabot.md) - documents dependency-update and security-audit behavior.
- [GitHub Action pin audit](./action-pin-audit.md) - audits GitHub Action pin consistency across
  workflows and local composite actions, with an explicit local repair mode for stale repeated refs.

______________________________________________________________________

## Contributor mental model

Use this family of pages as follows:

| Question                                                         | Start here                                                          |
| ---------------------------------------------------------------- | ------------------------------------------------------------------- |
| What runs on pull requests and pushes?                           | [CI workflow](./ci-workflow.md)                                     |
| How are Python, uv, and nox bootstrapped in CI jobs?             | [Setup Python + nox action](./setup-python-nox-action.md)           |
| Which tests are included, skipped, slow, or integration-focused? | [Test validation](./test-validation.md)                             |
| How are release artifacts produced and published?                | [Release workflow](./release-workflow.md)                           |
| How do we validate packages after publication?                   | [Published artifact validation](./published-artifact-validation.md) |
| How are dependency updates handled?                              | [Dependabot](./dependabot.md)                                       |
| How do we audit or locally repair GitHub Action pin consistency? | [GitHub Action pin audit](./action-pin-audit.md)                    |

______________________________________________________________________

## CI and release validation model

TopMark intentionally separates:

1. repository source-tree validation;
1. dependency and GitHub Action maintenance;
1. release artifact construction in CI;
1. privileged artifact publication;
1. post-publication package validation from PyPI or TestPyPI.

This layered model keeps source validation, artifact production, package publication, and
published-package validation in distinct trust boundaries for the stable 1.x release line.

______________________________________________________________________

## Related pages

- [Contributing to TopMark](../contributing.md) - contributor workflow and dependency guidance
- [Release process](../dev/release-process.md) - project-level release workflow and policy
- [`Configuration overview`](../configuration/index.md) - configuration entry point and links to
  discovery, precedence, and merge semantics
