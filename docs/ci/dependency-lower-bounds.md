<!--
topmark:header:start

  project      : TopMark
  file         : dependency-lower-bounds.md
  file_relpath : docs/ci/dependency-lower-bounds.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Dependency lower bounds workflow

This page documents `.github/workflows/dependency-lower-bounds.yml` and the
`dependency_lower_bounds` Nox session.

TopMark validates that the lower bounds declared for direct dependencies can resolve and support the
repository's test, type-check, and linting contracts. The workflow does not change dependency
ranges, refresh the committed lockfile, or publish artifacts.

{% include-markdown "\_snippets/terminology.md" %}

______________________________________________________________________

## Purpose

The committed `uv.lock` records TopMark's current reproducible dependency graph. Its normal
highest-compatible resolution does not demonstrate that the direct lower bounds in `pyproject.toml`
work. A package consumer can receive those older, declared-compatible versions instead.

The workflow creates a disposable `lowest-direct` resolution. It selects the lowest available
versions of direct dependencies within TopMark's declared ranges while keeping transitive
dependencies current. It then validates that resolution across the supported Python matrix.

This provides evidence for direct dependency-floor claims without attempting the impractical task of
testing every possible combination of intermediate and historical transitive versions.

______________________________________________________________________

## Trigger conditions

| Trigger             | When it runs                           | Purpose                                       |
| ------------------- | -------------------------------------- | --------------------------------------------- |
| `schedule`          | Mondays at 03:37 UTC                   | Revalidate floors as package metadata evolves |
| `workflow_dispatch` | Manual maintainer run                  | Revalidate floors on demand                   |
| `pull_request`      | Dependency-bound or validation changes | Validate changed floors before merge          |

Pull-request runs are limited to changes in `pyproject.toml`, `uv.lock`, `noxfile.py`, `Makefile`,
or the workflow itself. New pull-request runs cancel older in-progress runs for the same pull
request; scheduled and manual runs are retained.

______________________________________________________________________

## Permissions and trust boundary

The workflow uses only read-only repository permissions:

```yaml
permissions:
  contents: read
```

It checks out trusted repository content, resolves public package metadata, and creates temporary
environments on the GitHub-hosted runner. It cannot push commits, update the committed lockfile,
publish artifacts, create pull requests, or access repository secrets.

______________________________________________________________________

## Workflow inputs

The workflow-dispatch trigger has no inputs. Run it from the default branch when a maintainer needs
to revalidate a declared dependency floor outside a pull request.

______________________________________________________________________

## Jobs and validation scope

| Job                     | Purpose                                                       | Main tools                    |
| ----------------------- | ------------------------------------------------------------- | ----------------------------- |
| `validate-lower-bounds` | Validate direct dependency floors across the supported matrix | `uv`, `pytest`, Pyright, Ruff |

The job runs on `ubuntu-26.04`, installs Nox through the shared setup action, and invokes the
repository-owned `dependency_lower_bounds` session.

{% include-markdown "\_snippets/python-support-policy.md" %}

For every supported Python version, the session:

1. creates a temporary `uv lock --upgrade --resolution lowest-direct` resolution;
1. runs the normal pytest selection; and
1. runs Pyright with that interpreter version.

On canonical Python, it also runs `ruff check .` and `ruff format --check .`. Ruff does not need a
full Python matrix, but exercising it once verifies that its declared floor works with TopMark's
source tree.

The session first creates a disposable detached Git worktree, so its temporary `lowest-direct` lock
never modifies the caller's checkout. Its isolated temporary environments and worktree are discarded
after the run.

The workflow does not build documentation, run link checks, run all pre-commit hooks, generate
coverage, or validate every direct tooling command. Those checks remain part of the normal CI and
pre-PR gates.

______________________________________________________________________

## Artifact handling

This workflow does not produce, consume, upload, or publish build or release artifacts.

Its temporary lockfile resolution and environments exist only for the duration of the validation
run. The committed `uv.lock` remains the canonical resolution for normal contributor and CI work.

______________________________________________________________________

## Local reproduction

Run the same validation locally:

```bash
make dependency-lower-bounds
```

For faster local pytest execution, forward xdist arguments:

```bash
make dependency-lower-bounds PYTEST_PAR="-n auto"
```

The parallel option affects pytest only. The workflow keeps pytest serial so its logs and resource
use remain predictable on GitHub-hosted runners.

For focused local diagnosis, run one validation at a time. Each command creates and restores its own
temporary lowest-direct resolution:

| Validation | Command                                                   |
| ---------- | --------------------------------------------------------- |
| Tests      | `make dependency-lower-bounds-tests PYTEST_PAR="-n auto"` |
| Pyright    | `make dependency-lower-bounds-types`                      |
| Ruff       | `make dependency-lower-bounds-ruff`                       |

`make dependency-lower-bounds` remains the aggregate command and is the workflow's CI contract.

______________________________________________________________________

## Maintenance notes

Keep this workflow focused on direct lower-bound validation. A changed dependency range must still
receive the dependency-maintenance review described in
[Dependency baseline maintenance](../dev/dependency-maintenance.md), including its compatibility
rationale, lockfile review, and appropriate normal CI validation.

When adding a new direct dependency, ensure its lower bound is intentional and its normal usage is
covered by tests or an appropriate tool invocation. Add a focused validation only when pytest,
Pyright, or canonical Ruff execution cannot exercise the new dependency's contract.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
