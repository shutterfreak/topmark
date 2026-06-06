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
behavior, and stable public API compatibility.

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
tests, docs, link checks, pre-commit validation, and API snapshot checks run only when relevant. It
also writes a short GitHub Step Summary showing which changed-file groups were detected, making
path-filtered job decisions easier to inspect from the workflow run.

Version-tag pushes are not path-filtered by pull-request change groups. They run the
release-artifact path after the required validation jobs succeed.

The workflow also uses a workflow-level concurrency group keyed by the workflow name and either the
pull-request number or Git ref. New pushes to the same pull request cancel older in-progress CI
runs, so contributors see the latest failure signal without spending runner time on superseded
commits. Pushes to `main` and version tags keep their in-progress runs instead of being canceled,
preserving post-merge and release-tag validation.

______________________________________________________________________

## Permissions and trust boundary

The workflow uses read-only repository permissions by default:

```yaml
permissions:
  contents: read
```

Jobs that use third-party actions or upload diagnostic artifacts declare the minimum required
job-level permissions explicitly where useful. For example, the `changes` job grants read-only
repository access plus read-only pull-request metadata access for path filtering, while link-check,
pre-commit, coverage, and release-artifact jobs keep read-only repository permissions. The workflow
does not publish packages, create releases, or request elevated release permissions.

The trust boundary is intentional:

- CI checks out and runs repository code in an unprivileged context.
- CI builds release artifacts from the tagged source tree.
- The privileged release workflow later downloads, verifies, and publishes those artifacts instead
  of rebuilding them.

This separation keeps artifact production and package publication in separate trust boundaries.

Some setup logic is shared through the local composite action
[`setup-python-nox`](./setup-python-nox-action.md), while other jobs keep explicit setup steps where
their caching or environment needs differ. This limited duplication is acceptable because it keeps
job behavior and trust boundaries explicit.

______________________________________________________________________

## Jobs and validation scope

| Job                 | Purpose                                                                 | Main tools                                 |
| ------------------- | ----------------------------------------------------------------------- | ------------------------------------------ |
| `changes`           | Detect changed file groups for PR job gating and summarize the result   | `dorny/paths-filter`                       |
| `python-metadata`   | Resolve supported and canonical Python versions for CI jobs             | `nox`, `pyproject.toml`                    |
| `lint`              | Validate formatting, linting, typing, and docstring links               | `nox`, `ruff`, `pyright`                   |
| `pre-commit`        | Run configured pre-commit hooks                                         | `pre-commit`                               |
| `docs`              | Build the documentation site in strict mode                             | `nox`, `mkdocs`                            |
| `tests`             | Run the supported Python test matrix                                    | `nox`, `pytest`                            |
| `filesystem-tests`  | Run canonical Python tests across Linux, macOS, and Windows filesystems | `nox`, `pytest`                            |
| `coverage`          | Generate and publish canonical coverage reports                         | `nox`, `coverage.py`, `pytest`             |
| `api-snapshot`      | Check public API stability for source-changing pull requests            | `nox`, `tools/api_snapshot.py`             |
| `links`             | Validate links in source Markdown files                                 | `lycheeverse/lychee-action`, `lychee.toml` |
| `links-site`        | Validate links in the rendered MkDocs site, including generated pages   | `mkdocs`, `lycheeverse/lychee-action`      |
| `release-artifacts` | Build and upload release artifacts for version tags                     | `uv build`, `actions/upload-artifact`      |

Most jobs delegate validation to nox sessions so local development and CI share the same stable
validation contracts and execution semantics. The `python-metadata` job resolves supported Python
versions and the canonical single-version Python from project metadata through
`nox -s print_python_matrix`. The test matrix consumes that supported-version list with `fail-fast`
disabled so failures on one Python version do not hide failures on others.

Filesystem-sensitive behavior is validated separately by the `filesystem-tests` job. That job runs
the canonical Python QA session across Ubuntu, macOS, and Windows so platform-dependent path and
filesystem semantics are checked on real GitHub-hosted filesystems without multiplying the full
supported Python-version matrix across every operating system.

This job also protects TopMark's filesystem-identity evaluation contract. That includes
filesystem-identity normalization for platform-sensitive path spellings and processing-target
eligibility checks such as hard-link policy where the host filesystem supports the required
semantics. Symlink-dependent regressions are required in this job: the workflow sets
`TOPMARK_REQUIRE_SYMLINKS=1`, so a runner that cannot create symlinks fails the job instead of
silently skipping those tests.

Coverage reporting runs in a dedicated canonical job on Ubuntu using the resolved canonical Python
version and the existing `nox -s coverage` session. Coverage intentionally runs outside the full
test matrix to avoid duplicating expensive QA work that is already covered by the compatibility
matrix.

The coverage job depends on the full supported-version test matrix succeeding before coverage
reports are generated. This keeps the compatibility matrix as the primary validation gate while
avoiding additional coverage-processing noise after known test failures. Platform-dependent
filesystem validation remains a separate gate through `filesystem-tests`.

Canonical single-version jobs such as linting, documentation builds, coverage, API snapshot checks,
and release-artifact construction use the same resolved canonical Python value rather than carrying
separate hard-coded version literals in the workflow.

> [!NOTE] Shared Python/bootstrap jobs intentionally use explicit `actions/cache` ownership while
> keeping the `setup-uv` built-in cache integration disabled. This avoids cache-reservation race
> warnings between concurrent jobs using identical bootstrap inputs.

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
- XML and JSON machine-readable coverage reports;
- a short GitHub Step Summary with a coverage overview and artifact notice.

Coverage artifacts are diagnostic CI outputs only. They are not release artifacts and are not
consumed by the release workflow.

On a version-tag push, the `release-artifacts` job:

- builds the source distribution and wheel with `uv build`;
- derives release metadata from the tag;
- normalizes the tag version with `packaging.version.Version`;
- records the supported and canonical Python metadata used by the CI run;
- writes checksum metadata with `sha256sum`;
- uploads `topmark-dist` and `topmark-release-meta` artifacts.

The release workflow consumes those uploaded artifacts after validating the triggering CI run and
tag context. CI does not publish the package itself.

This artifact handoff is part of the release trust-boundary model. Artifact creation happens where
repository code is already expected to run; publication happens later in a privileged workflow that
does not rebuild the project from repository source code.

______________________________________________________________________

## CI validation model

TopMark intentionally separates:

1. source-tree validation;
1. supported Python-version discovery;
1. canonical single-version validation jobs;
1. compatibility test-matrix execution;
1. diagnostic coverage reporting;
1. release artifact construction;
1. privileged artifact publication in the downstream release workflow.

This layered CI model keeps repository validation, release artifact creation, and package
publication in separate trust boundaries while preserving stable local/CI validation contracts.

______________________________________________________________________

## Local reproduction

The closest local equivalents are the nox sessions used by CI:

```bash
nox -s print_python_matrix
nox -s format_check
nox -s lint
nox -s docstring_links
nox -s docs
nox -s qa -p 3.13
nox -s coverage -p 3.13
```

The `filesystem-tests` job runs the same canonical `qa` session on Ubuntu, macOS, and Windows. Local
reproduction can validate the current machine's filesystem behavior, but it cannot replace the
cross-platform GitHub-hosted runs for case-sensitivity and path-canonicalization behavior. In this
job, symlink creation is mandatory through `TOPMARK_REQUIRE_SYMLINKS=1`; if a Windows runner loses
symlink capability because Developer Mode or equivalent privileges are unavailable, the job fails
rather than reporting a misleading skip.

The concrete `3.13` commands shown here reflect the current canonical Python version. That value is
resolved from project metadata and is expected to move when the supported Python range moves.

Run link checks with:

```bash
nox -s links_all
nox -s links_site
```

Run the API snapshot check with:

```bash
nox -s api_snapshot -p 3.13
```

CI uses the resolved canonical Python value for this session rather than hard-coding the version in
`.github/workflows/ci.yml`.

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
- keep path-filter summaries aligned with the changed-file groups emitted by the `changes` job;
- keep nox sessions as the canonical stable validation contracts where practical;
- keep Python-version metadata sourced from `pyproject.toml` through `nox -s print_python_matrix`;
- keep the coverage job canonical and lightweight rather than instrumenting the full compatibility
  matrix;
- keep platform-dependent filesystem behavior covered by the canonical cross-platform
  `filesystem-tests` job rather than expanding the full Python-version matrix across all operating
  systems;
- keep coverage reporting lightweight and diagnostic rather than turning it into a percentage-driven
  release gate;
- keep release artifact building in CI unless the release trust model is deliberately redesigned;
- avoid moving package publication into this workflow;
- keep generated-site link validation separate from source Markdown link validation;
- keep link-check jobs bounded with explicit timeouts so network-dependent validation cannot hang
  indefinitely;
- keep action pins synchronized across workflows and local composite actions;
- keep uv cache ownership explicit and centralized rather than mixing `setup-uv` cache management
  with separate `actions/cache` ownership.

GitHub Actions are pinned to commit SHAs. Use the [GitHub Action pin audit](./action-pin-audit.md)
to detect drift between workflow files and local composite actions.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
