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

It runs on the explicit `ubuntu-26.04` image, consistent with the repository's Linux runner baseline
and independent of unreviewed `ubuntu-latest` migrations.

______________________________________________________________________

## Local commit-message validation

The repository's Commit Check hook reads `.github/cchk.toml` and checks Conventional Commit
structure and allowed types at the `commit-msg` stage. It also checks subject length, imperative
wording, and DCO sign-offs; the GitHub title workflow does not enforce these extra local checks.
Install or refresh the hooks with:

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

Keep the allowed types synchronized between `.github/cchk.toml`, this workflow, and
`CONTRIBUTING.md`. The workflow action is pinned to a full commit SHA; update it through the normal
GitHub Action dependency-maintenance process and action-pin audit.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
