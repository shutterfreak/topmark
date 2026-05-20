<!--
topmark:header:start

  project      : TopMark
  file         : ci-workflow.md
  file_relpath : docs/ci/ci-workflow.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# CI workflow

This page documents `.github/workflows/ci.yml`.

The CI workflow is TopMark's primary source-tree validation workflow. It validates pull requests,
pushes to `main`, and version-tag pushes before release publication consumes CI-built artifacts.

{% include-markdown "\_snippets/terminology.md" %}

## Purpose

The CI workflow validates that the repository source tree is healthy before changes are merged or
released. It checks formatting, linting, typing, documentation integrity, link integrity, test
behavior, and public API stability.

The workflow also builds release artifacts on version-tag pushes. This is intentional: release
artifacts are built in the unprivileged CI workflow and later consumed by the privileged release
workflow, so the release workflow does not rebuild the project from repository source code.

______________________________________________________________________

## Trigger conditions

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

## Permissions and trust boundary

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

This separation keeps artifact production and package publication in separate trust boundaries.

Some setup logic is shared through the local composite action
`.github/actions/setup-python-nox/action.yml`, while other jobs keep explicit setup steps where
their caching or environment needs differ. This limited duplication is acceptable because it keeps
job behavior and trust boundaries explicit.

______________________________________________________________________

## Jobs and validation scope

| Job                 | Purpose                                                               | Main tools                                 |
| ------------------- | --------------------------------------------------------------------- | ------------------------------------------ |
| `changes`           | Detect changed file groups for PR job gating                          | `dorny/paths-filter`                       |
| `lint`              | Validate formatting, linting, typing, and docstring links             | `nox`, `ruff`, `pyright`                   |
| `pre-commit`        | Run configured pre-commit hooks                                       | `pre-commit`                               |
| `docs`              | Build the documentation site in strict mode                           | `nox`, `mkdocs`                            |
| `tests`             | Run the supported Python test matrix                                  | `nox`, `pytest`                            |
| `coverage`          | Generate and publish canonical coverage reports                       | `nox`, `coverage.py`, `pytest`             |
| `api-snapshot`      | Check public API stability for source-changing pull requests          | `nox`, `tools/api_snapshot.py`             |
| `links`             | Validate links in source Markdown files                               | `lycheeverse/lychee-action`, `lychee.toml` |
| `links-site`        | Validate links in the rendered MkDocs site, including generated pages | `mkdocs`, `lycheeverse/lychee-action`      |
| `release-artifacts` | Build and upload release artifacts for version tags                   | `uv build`, `actions/upload-artifact`      |

Most jobs delegate validation to nox sessions so local development and CI share the same validation
contracts and execution semantics. The test matrix runs on Python 3.10 through 3.14 with `fail-fast`
disabled so failures on one Python version do not hide failures on others.

Coverage reporting runs in a dedicated canonical job on Ubuntu with Python 3.13 using the existing
`nox -s coverage` session. Coverage intentionally runs outside the full test matrix to avoid
duplicating expensive QA work that is already covered by the compatibility matrix.

The API snapshot check is pull-request-only and runs when Python-relevant files change. It is a fast
guardrail for unexpected stable public API surface changes, not a replacement for the full test
matrix.

Documentation integrity is validated at multiple levels:

- the `docs` job runs a strict MkDocs build;
- the `links` job validates links in source Markdown files;
- the `links-site` job validates links in the rendered site, including generated API pages.

Generated API pages are visible only after the site is built, so source-only link checks cannot
fully replace the built-site link check.

______________________________________________________________________

## Artifact handling

The CI workflow produces release artifacts only for tag pushes matching `v*`.

The workflow also publishes coverage artifacts from the dedicated `coverage` job:

- an HTML coverage report;
- XML and JSON machine-readable reports;
- a short GitHub Step Summary.

Coverage artifacts are diagnostic CI outputs only. They are not release artifacts and are not
consumed by the release workflow.

On a version-tag push, the `release-artifacts` job:

- builds the source distribution and wheel with `uv build`;
- derives release metadata from the tag;
- normalizes the tag version with `packaging.version.Version`;
- writes checksum metadata with `sha256sum`;
- uploads `topmark-dist` and `topmark-release-meta` artifacts.

The release workflow consumes those uploaded artifacts after validating the triggering CI run and
tag context. CI does not publish the package itself.

This artifact handoff is part of the release trust-boundary model. Artifact creation happens where
repository code is already expected to run; publication happens later in a privileged workflow that
does not rebuild the project from repository source code.

______________________________________________________________________

## Local reproduction

The closest local equivalents are the nox sessions used by CI:

```bash
nox -s format_check
nox -s lint
nox -s docstring_links
nox -s docs
nox -s qa -p 3.13
```

```bash
nox -s coverage -p 3.13
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

Local commands can reproduce most validation behavior, but they do not reproduce GitHub event
context, pull-request path filtering, artifact-upload behavior, or downstream release-workflow
handoff semantics.

______________________________________________________________________

## Maintenance notes

Keep the CI workflow explicit enough that contributors can determine which validation contract
failed from the job name and log output.

When editing this workflow:

- update path filters when adding new source, docs, tooling, or workflow-maintenance files;
- keep nox sessions as the canonical validation contracts where practical;
- keep coverage reporting lightweight and diagnostic rather than turning it into a percentage-driven
  release gate;
- keep release artifact building in CI unless the release trust model is deliberately redesigned;
- avoid moving package publication into this workflow;
- keep generated-site link validation separate from source Markdown link validation;
- keep action pins synchronized across workflows and local composite actions.

GitHub Actions are pinned to commit SHAs. Use the [GitHub Action pin audit](./action-pin-audit.md)
to detect drift between workflow files and local composite actions.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
