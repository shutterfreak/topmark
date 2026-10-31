<!--
topmark:header:start

  project      : TopMark
  file         : commit-check.md
  file_relpath : docs/ci/commit-check.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Commit Check workflow

This page documents `.github/workflows/commit-check.yml`.

## Purpose

The Commit Check workflow compares pull request titles with TopMark's local commit-message policy.
It is an advisory evaluation alongside [pull request title validation](./pull-request-title.md),
which remains the authoritative title check. Do not require the advisory status in branch protection
while its behavior is being evaluated.

______________________________________________________________________

## Trigger conditions

The workflow runs when a pull request is opened, edited, reopened, or updated. It is independent of
the path-filtered [CI workflow](./ci-workflow.md), so title edits trigger a new comparison.

______________________________________________________________________

## Permissions and trust boundary

The workflow uses `pull_request` with read-only `contents` and `pull-requests` permissions. It
checks out the base commit to obtain `.github/cchk.toml`, without persisting checkout credentials.
The configured steps do not check out or execute pull-request source code. The Action reads the pull
request title from the event and runs on `ubuntu-26.04`. GitHub evaluates the workflow from the pull
request's merge commit, so changes to the workflow itself are subject to review.

A policy change in a pull request is evaluated against the existing base policy; the new policy is
used after it reaches the base branch. Fork pull requests use GitHub's restricted read-only token.

______________________________________________________________________

## Jobs and validation scope

The `Commit Check title (advisory)` job runs the pinned Commit Check Action against the PR title. It
checks Conventional Commit structure, configured types, subject length, and the local
imperative-wording heuristic. It disables commit-message, branch, author, and comment checks. The
sign-off rule is disabled for this title-only check because titles do not contain commit trailers;
the separate DCO app checks PR commits. The existing title workflow remains independent.

The Action can report a failure even though this status is not required. Its pinned release installs
its own pinned Commit Check version, which can differ from the version used by pre-commit. The
imperative heuristic can also reject valid wording. Neither this workflow nor the DCO app guarantees
that the final editable squash-merge message retains all sign-off trailers.

______________________________________________________________________

## Artifact handling

The workflow does not produce, consume, or publish artifacts.

______________________________________________________________________

## Local reproduction

From a checkout containing the base branch policy, inspect `requirements.txt` in the
[Commit Check Action repository](https://github.com/commit-check/commit-check-action) at the commit
SHA pinned in `.github/workflows/commit-check.yml`. Substitute its `commit-check` version below:

```bash
printf '%s\n' 'chore: update contributor guidance' | \
  uv run --with 'commit-check==<VERSION>' commit-check --message --require-signed-off-by=false
```

This reproduces title validation, not GitHub event handling, permissions, or Action installation.
The temporary `--with` dependency is separate from TopMark's project lockfile. The normal local
commit hook also checks sign-off trailers and can use a different tool version.

______________________________________________________________________

## Maintenance notes

Review the advisory result against the existing title check on title edits, fork pull requests,
Dependabot, and policy-only changes before deciding whether to retain it, replace the existing
workflow, or remove it. Keep it non-required throughout the evaluation. The Action is pinned to a
full commit SHA; review its bundled Commit Check version when updating it. Preserve the base-policy
checkout and read-only trust boundary.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
