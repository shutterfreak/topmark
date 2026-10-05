<!--
topmark:header:start

  project      : TopMark
  file         : pull-request-title.md
  file_relpath : docs/ci/pull-request-title.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Pull request title validation

This page documents `.github/workflows/pull-request-title.yml`.

TopMark validates pull request titles against the Conventional Commits structure before merge. This
keeps the pull request title suitable for use as the squash-merge commit title and aligns it with
the repository's commit-message policy.

______________________________________________________________________

## Purpose

The workflow rejects titles that do not use this form:

```text
<type>[optional scope]: <short summary>
```

For example, `build(deps): refresh pre-commit hooks` is valid, while
`build (deps): refresh pre-commit hooks` is not. The allowed types are `build`, `chore`, `ci`,
`docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, and `test`.

______________________________________________________________________

## Trigger conditions

The workflow runs for opened, edited, reopened, and updated pull requests. It is independent from
the path-filtered source-tree CI workflow so a title edit is always checked.

______________________________________________________________________

## Permissions and trust boundary

The workflow uses `pull_request_target` with read-only pull-request permission. It does not check
out the pull-request branch or run repository code; it reads only the pull-request title. This lets
the validation run safely for pull requests from forks while keeping the policy defined on `main`.

______________________________________________________________________

## Local commit-message validation

The repository's pre-commit configuration enforces the same Conventional Commit structure at the
`commit-msg` hook stage. Install or refresh the hooks with:

```bash
pre-commit install --install-hooks
```

When the default Python interpreter changes, reinstall the `uv`-managed pre-commit launcher before
refreshing the hooks:

```bash
uv tool install pre-commit --force
pre-commit install --install-hooks
```

The local hook prevents malformed commit subjects before Git creates the commit. The GitHub workflow
is the merge-time guard for pull request titles and for contributors who have not installed local
hooks.

______________________________________________________________________

## Maintenance notes

Keep the allowed types synchronized between `.pre-commit-config.yaml`, this workflow, and
`CONTRIBUTING.md`. The workflow action is pinned to a full commit SHA; update it through the normal
GitHub Action dependency-maintenance process and action-pin audit.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
