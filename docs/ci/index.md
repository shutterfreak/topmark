<!--
topmark:header:start

  project      : TopMark
  file         : index.md
  file_relpath : docs/ci/index.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# CI & Validation

TopMark uses a deliberately explicit CI and validation structure. GitHub workflows provide
orchestration, nox sessions define reusable validation contracts, pytest markers describe test
intent, and Makefile targets provide local developer shortcuts.

The current design favors clarity and release safety over aggressive workflow abstraction. Some
repetition between workflows is intentional, especially where privileged release behavior or
artifact handoff security is involved.

______________________________________________________________________

## Validation Architecture

Source validation starts in the main CI workflow and is delegated to nox sessions where practical.
The test suite is further organized with pytest markers so contributors can understand the intent
and expected scope of each test group.

- [CI workflow](./ci-workflow.md) — validates the source tree, documentation, tests, typing,
  linting, API snapshots, and release artifacts produced from trusted CI runs.
- [Test validation](./test-validation.md) — explains pytest markers, validation categories, local
  test commands, CI inclusion rules, and how nox and Makefile targets map onto the test suite.
- [Published artifact validation](./published-artifact-validation.md) — validates installation and
  runtime behavior from packages already published to PyPI or TestPyPI.

______________________________________________________________________

## Release Infrastructure

Release publishing is intentionally separated from normal source validation. The release workflow is
privileged and consumes artifacts produced by the CI workflow instead of rebuilding them in the
publishing context.

- [Release workflow](./release-workflow.md) — publishes previously built artifacts after
  release-tag, artifact, and repository checks.
- [Published artifact validation](./published-artifact-validation.md) — verifies the package as an
  end user would install it after publication.

______________________________________________________________________

## Dependency Automation

Dependency automation is documented separately because it has different triggers, trust boundaries,
and maintenance expectations than source validation or release publishing.

- [Dependabot](./dependabot.md) — documents dependency update and security-audit behavior.
- [GitHub Action pin audit](./action-pin-audit.md) — audits GitHub Action pin consistency across
  workflows and local composite actions.

______________________________________________________________________

## Contributor Mental Model

Use this family of pages as follows:

| Question                                                         | Start here                                                          |
| ---------------------------------------------------------------- | ------------------------------------------------------------------- |
| What runs on pull requests and pushes?                           | [CI workflow](./ci-workflow.md)                                     |
| Which tests are included, skipped, slow, or integration-focused? | [Test validation](./test-validation.md)                             |
| How are release artifacts produced and published?                | [Release workflow](./release-workflow.md)                           |
| How do we validate packages after publication?                   | [Published artifact validation](./published-artifact-validation.md) |
| How are dependency updates handled?                              | [Dependabot](./dependabot.md)                                       |
| How do we audit GitHub Action pin consistency?                   | [GitHub Action pin audit](./action-pin-audit.md)                    |

______________________________________________________________________

## Related Pages

- [Contributing to TopMark](../contributing.md) — contributor workflow and dependency guidance
- [Release process](../dev/release-process.md) — project-level release procedure
- [`Configuration overview`](../configuration/index.md) — configuration entry point and links to
  discovery/merge semantics
