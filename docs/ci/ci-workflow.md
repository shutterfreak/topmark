<!--
topmark:header:start

  project      : TopMark
  file         : ci-workflow.md
  file_relpath : docs/ci/ci-workflow.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# CI Workflow

This page documents `.github/workflows/ci.yml`.

The CI workflow is TopMark's primary source-tree validation workflow. It validates pull requests,
pushes to `main`, and version-tag pushes before release publication consumes CI-built artifacts.

## Purpose

The CI workflow validates that the repository source tree is healthy before changes are merged or
released. It checks formatting, linting, typing, documentation integrity, link integrity, test
behavior, and public API stability.

The workflow also builds release artifacts on version-tag pushes. This is intentional: release
artifacts are built in the unprivileged CI workflow and later consumed by the privileged release
workflow, so the release workflow does not need to rebuild the project from repository code.

______________________________________________________________________

## Trigger Conditions

| Trigger         | When it runs                                                                                           | Purpose                                                     |
| --------------- | ------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------- |
| `pull_request`  | Pull requests affecting source, tests, tools, documentation, workflow, dependency, or validation files | Validate proposed changes before merge                      |
| `push.branches` | Pushes to `main`                                                                                       | Validate committed source changes                           |
| `push.tags`     | Tags matching `v*`                                                                                     | Validate the tagged source tree and build release artifacts |

Pull-request runs are path-filtered at the workflow level so unrelated changes do not trigger CI.
Within the workflow, the `changes` job performs finer-grained path filtering so jobs such as lint,
tests, docs, link checks, pre-commit validation, and API snapshot checks run only when relevant.

Version-tag pushes are not path-filtered by pull-request change groups. They run the
release-artifact path after the required validation jobs succeed.

______________________________________________________________________

## Permissions and Trust Boundary

The workflow uses read-only repository permissions by default:

```yaml
permissions:
  contents: read
```

The `release-artifacts` job also declares `contents: read` explicitly. The workflow does not publish
packages, create releases, or request elevated release permissions.

The trust boundary is intentional:

- CI checks out and runs repository code in an unprivileged context.
- CI builds release artifacts from the tagged source tree.
- The privileged release workflow later downloads, verifies, and publishes those artifacts instead
  of rebuilding them.

This separation keeps artifact production and package publication in different security contexts.

Some setup logic is shared through the local composite action
`.github/actions/setup-python-nox/action.yml`, while other jobs keep explicit setup steps where
their caching or environment needs differ. This limited duplication is acceptable because it keeps
job behavior and trust boundaries visible.

______________________________________________________________________

## Jobs and Validation Scope

| Job                 | Purpose                                                               | Main tools                                 |
| ------------------- | --------------------------------------------------------------------- | ------------------------------------------ |
| `changes`           | Detect changed file groups for PR job gating                          | `dorny/paths-filter`                       |
| `lint`              | Validate formatting, linting, typing, and docstring links             | `nox`, `ruff`, `pyright`                   |
| `pre-commit`        | Run configured pre-commit hooks                                       | `pre-commit`                               |
| `docs`              | Build the documentation site in strict mode                           | `nox`, `mkdocs`                            |
| `tests`             | Run the supported Python test matrix                                  | `nox`, `pytest`                            |
| `api-snapshot`      | Check public API stability for source-changing pull requests          | `nox`, `tools/api_snapshot.py`             |
| `links`             | Validate links in source Markdown files                               | `lycheeverse/lychee-action`, `lychee.toml` |
| `links-site`        | Validate links in the rendered MkDocs site, including generated pages | `mkdocs`, `lycheeverse/lychee-action`      |
| `release-artifacts` | Build and upload release artifacts for version tags                   | `uv build`, `actions/upload-artifact`      |

Most jobs delegate validation to nox sessions so local development and CI share the same validation
contracts. The test matrix runs on Python 3.10 through 3.14 with `fail-fast` disabled so failures on
one Python version do not hide failures on others.

The API snapshot check is pull-request-only and runs when Python-relevant files change. It is a fast
guardrail for unexpected public API changes, not a replacement for the full test matrix.

Documentation integrity is validated at multiple levels:

- the `docs` job runs a strict MkDocs build;
- the `links` job validates links in source Markdown files;
- the `links-site` job validates links in the rendered site, including generated API pages.

Generated API pages are only visible after the site is built, so source-only link checks cannot
fully replace the built-site link check.

______________________________________________________________________

## Artifact Handling

The CI workflow produces release artifacts only for tag pushes matching `v*`.

On a version-tag push, the `release-artifacts` job:

- builds the source distribution and wheel with `uv build`;
- derives release metadata from the tag;
- normalizes the tag version with `packaging.version.Version`;
- writes checksum metadata with `sha256sum`;
- uploads `topmark-dist` and `topmark-release-meta` artifacts.

The release workflow consumes those uploaded artifacts after validating the triggering CI run and
tag context. CI does not publish the package itself.

This artifact handoff is part of the release security model. Artifact creation happens where
repository code is already expected to run; publication happens later in a privileged workflow that
does not rebuild the project.

______________________________________________________________________

## Local Reproduction

The closest local equivalents are the nox sessions used by CI:

```bash
nox -s format_check
nox -s lint
nox -s docstring_links
nox -s docs
nox -s qa -p 3.13
```

Run link checks with:

```bash
nox -s links_all
nox -s links_site
```

Run the API snapshot check with:

```bash
nox -s api_snapshot -p 3.13
```

Build release artifacts locally with:

```bash
uv build
```

Local commands can reproduce the validation logic, but they do not reproduce GitHub event context,
pull-request path filtering, artifact upload behavior, or the downstream release workflow handoff.

______________________________________________________________________

## Maintenance Notes

Keep the CI workflow explicit enough that contributors can understand which contract failed from the
job name and log output.

When editing this workflow:

- update path filters when adding new source, docs, tooling, or workflow-maintenance files;
- keep nox sessions as the canonical validation contracts where practical;
- keep release artifact building in CI unless the release trust model is deliberately redesigned;
- avoid moving package publication into this workflow;
- keep generated-site link validation separate from source Markdown link validation;
- keep action pins synchronized across workflows and local composite actions.

GitHub Actions are pinned to commit SHAs. Use the [GitHub Action pin audit](./action-pin-audit.md)
to detect drift between workflow files and local composite actions.

______________________________________________________________________

## Related Pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
