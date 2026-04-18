<!--
topmark:header:start

  project      : TopMark
  file         : dependabot.md
  file_relpath : docs/ci/dependabot.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# 🤖 Dependabot and Automated Dependency Updates

This page documents how TopMark uses **Dependabot** to keep both **GitHub Actions** and **Python
project dependencies** current without giving up reproducibility or supply-chain safety.

______________________________________________________________________

## Overview

TopMark uses Dependabot for two distinct update surfaces:

- **GitHub Actions** used by CI and release automation
- **Python dependencies** managed through `uv`

These update flows are intentionally conservative:

- workflow actions are pinned to **exact commit SHAs**
- Python dependency resolution is driven by **`pyproject.toml` + `uv.lock`**
- maintainers review and merge Dependabot PRs after CI passes

TopMark uses **Git-based versioning (`setuptools-scm`)**, meaning package versions are derived from
Git tags rather than being declared manually in `pyproject.toml`. Dependency updates therefore do
not involve version bumps in source files.

______________________________________________________________________

## Why TopMark Uses Dependabot

Dependabot helps keep infrastructure current while reducing manual maintenance work.

In TopMark, this means:

- security and bug-fix updates for workflow actions arrive as PRs
- Python dependency updates are proposed against the **uv-based** dependency model
- the update history stays visible in normal Git review flow

Dependabot is an assistant, not an auto-merge system: maintainers still review each PR and decide
whether it should be merged immediately, postponed, or closed.

______________________________________________________________________

## GitHub Actions Pinning Policy

TopMark pins GitHub Actions to **full commit hashes** rather than version tags.

Example:

```yaml
uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd # v5.0.1
```

This is intentional.

Benefits:

- protects against accidental or malicious tag movement
- makes CI and release automation more reproducible
- aligns with GitHub's supply-chain hardening guidance

The trailing version comment is kept for readability. The **hash** is the real execution target; the
comment simply tells maintainers which upstream release that hash corresponds to.

______________________________________________________________________

## How Dependabot Updates Pinned Actions

Although TopMark pins actions to commit SHAs, Dependabot still understands how to update them.

Typical workflow:

1. Upstream publishes a new release of an action.
1. Dependabot opens a PR updating the pinned SHA.
1. The PR title normally reflects the upstream action/version bump.
1. CI runs against the new pinned commit.
1. A maintainer reviews and merges the PR if the change is acceptable.

This gives TopMark the safety of SHA pinning without giving up update automation.

______________________________________________________________________

## Python Dependency Strategy

TopMark uses a **uv-first** dependency model.

The roles are:

- **`pyproject.toml`** — declares supported dependency ranges
- **`uv.lock`** — committed lockfile and canonical resolved dependency graph

The lockfile (`uv.lock`) is the **authoritative source of resolved dependency versions** and must
always be committed.

TopMark no longer treats exported `requirements*.txt` files as a primary dependency source. They are
not part of the normal dependency-management workflow.

This means the authoritative update path is:

1. adjust compatibility ranges in `pyproject.toml` when needed
1. refresh the lock with `uv`
1. commit the updated lockfile

______________________________________________________________________

## Dependabot and `uv`

Dependabot is configured to track Python dependencies in alignment with the **`uv`-based project
model**.

That means:

- Python update PRs are aligned with the `uv`-based project model
- the lockfile is treated as part of the dependency-management surface
- maintainers do not need a parallel pip- or requirements-file update workflow

This keeps the project dependency story simple:

- one declaration source (`pyproject.toml`)
- one lock source (`uv.lock`)
- one update bot configuration for Python dependencies

All Dependabot updates are validated through CI, which includes packaging checks aligned with the
project's SCM-based versioning model.

______________________________________________________________________

## Reviewing Dependabot PRs

When Dependabot opens a PR, maintainers should review it like any other infrastructure change.

Recommended review flow:

1. Read the PR title and identify what changed.

1. Check whether the change affects:

   - GitHub Actions infrastructure
   - Python tooling or runtime dependencies
   - release automation
   - documentation tooling

1. Confirm CI passes.

1. Skim the changed files.

1. Merge if the change is low risk and CI is green.

Extra caution is recommended for:

- major version jumps
- release/publishing actions
- documentation toolchain changes
- formatter or linting changes that may cascade into repository-wide diffs

______________________________________________________________________

## Recommended Manual Commands After Dependency Changes

For Python dependency changes, these commands are useful during review or follow-up maintenance:

```bash
make uv-lock
make uv-lock-upgrade
make venv
make venv-sync-all
make verify
make test
```

Typical usage:

- use `make uv-lock` after adjusting dependency ranges intentionally
- use `make uv-lock-upgrade` when refreshing resolved versions within existing ranges
- use `make verify` and `make test` to confirm the repository still passes local quality gates

______________________________________________________________________

## Labels and PR Volume Control

TopMark configures Dependabot with repository labels and a limit on concurrent open PRs.

This helps keep update traffic manageable:

- update PRs are easier to filter and review
- the repository avoids sudden bursts of many dependency PRs at once
- maintainers can merge small, low-risk updates incrementally

If Dependabot reports missing labels, create those labels in the repository settings so future PRs
can be categorized automatically.

______________________________________________________________________

## What Dependabot Does **Not** Replace

Dependabot does not replace normal maintainer judgment.

It does **not** decide:

- whether a version bump is appropriate for the current release phase
- whether an upstream change should be postponed
- whether a lock refresh should happen together with other coordinated tooling updates
- whether documentation and contributor guidance should be updated after a tooling change

Dependabot proposes updates. Maintainers still control policy.

______________________________________________________________________

## Versioning Notes

TopMark uses **Git tags as the single source of truth** for versioning.

- Versions are derived at build time via `setuptools-scm`
- No manual version bumps are performed in `pyproject.toml`
- Dependency updates do not affect package versioning

Examples assume post-1.0 versioning (e.g. `1.0.0`, `1.1.0`, `1.2.0`).

______________________________________________________________________

## Related Pages

- [`ci-workflow.md`](./ci-workflow.md) — overall CI design
- [`release-workflow.md`](./release-workflow.md) — release pipeline and publishing flow
- [`../contributing.md`](../contributing.md) — contributor workflow and dependency guidance
