<!--
topmark:header:start

  project      : TopMark
  file         : dependency-maintenance.md
  file_relpath : docs/dev/dependency-maintenance.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Dependency baseline maintenance

This page defines how TopMark maintains dependency compatibility ranges, its resolved development
environment, CI validation, and pre-commit tooling over time.

The policy is maintainer-facing. Contributor commands remain summarized in
[`CONTRIBUTING.md`](https://github.com/shutterfreak/topmark/blob/main/CONTRIBUTING.md), while
workflow-specific behavior is documented under [CI and validation](../ci/index.md).

{% include-markdown "\_snippets/terminology.md" %}

## Purpose

Dependency maintenance must balance four goals:

- preserve an honest compatibility contract for package consumers;
- keep repository development and validation environments reproducible;
- exercise supported Python versions against a current, resolvable dependency set;
- keep developer automation current without silently changing the published runtime contract.

No single file represents all four goals. Maintainers must distinguish declared compatibility from a
resolved environment and from isolated tool pins.

______________________________________________________________________

## Baseline model

TopMark uses four related dependency baselines:

| Baseline                  | Source                                         | Meaning                                                               |
| ------------------------- | ---------------------------------------------- | --------------------------------------------------------------------- |
| Declared compatibility    | `pyproject.toml`                               | Dependency versions that published TopMark releases claim to support  |
| Resolved repository graph | `uv.lock`                                      | One complete, reproducible resolution used by the uv project workflow |
| CI validation             | `pyproject.toml`, `noxfile.py`, GitHub Actions | Supported Python matrix plus representative dependency resolution     |
| Pre-commit tooling        | `.pre-commit-config.yaml`                      | Isolated hook repositories, revisions, and hook-only dependencies     |

These baselines should remain coherent, but they are not expected to contain identical version
numbers.

### Declared compatibility

Runtime dependencies and optional dependency groups are declared as bounded ranges in
`pyproject.toml`. The lower bound is a compatibility claim: TopMark should not require behavior that
is absent from that version. The upper bound limits resolution across versions that have not yet
been accepted.

Published wheels and source distributions contain these ranges, not the repository lockfile. Package
installers therefore resolve a compatible environment for each consumer.

### Resolved repository graph

`uv.lock` is the canonical resolved graph for the uv project workflow. It records one complete
solution across the project's supported Python and platform markers and supports reproducible
`uv sync` operations, lockfile review, and Dependabot updates.

The lockfile is not the published compatibility contract. A version appearing in `uv.lock` does not
automatically become a new lower bound, and refreshing the lockfile does not by itself withdraw
support for older versions permitted by `pyproject.toml`.

### CI validation

The supported Python matrix is derived from `project.requires-python` through
`nox -s print_python_matrix`. Nox sessions install TopMark and the required optional dependency
groups from `pyproject.toml`.

This validates that the declared ranges produce a working contemporary resolution across supported
Python versions. It does not exhaustively test every permitted dependency combination, and it is not
a dedicated minimum-version matrix. Cache keys include `uv.lock`, but cache invalidation does not
turn the lockfile into the published dependency contract.

When a lower bound depends on a specific API or behavior, maintainers should retain focused test
coverage for that behavior and verify the boundary version explicitly when practical.

### Pre-commit tooling

`.pre-commit-config.yaml` pins hook repositories independently from Python project dependencies.
Hook `rev` values and hook-local `additional_dependencies` describe isolated pre-commit
environments; they are not resolved through `uv.lock`.

When the same tool also appears in `pyproject.toml`, exact version equality is useful where it keeps
local, nox, and pre-commit behavior consistent, but it is not automatic. Mirrors, hook repositories,
and Python distributions can have different release identifiers or update timing. Review and
validate each surface deliberately.

______________________________________________________________________

## Version-range policy

### Lower bounds

Set lower bounds to the oldest version TopMark intentionally supports, backed by a concrete reason.
A lower bound may be raised when:

- TopMark uses an API, behavior, type definition, or metadata correction introduced by a newer
  version;
- an older version does not support a Python version or platform that TopMark supports;
- a security or correctness issue makes the older version unsuitable;
- continued compatibility requires disproportionate work and the project intentionally withdraws
  that support.

Do not raise a lower bound merely because:

- a newer release exists;
- Dependabot or `uv lock --upgrade` selected a newer version;
- the current lockfile no longer contains the old version;
- pre-commit uses a newer revision of the same tool.

Any lower-bound change must include a reviewable rationale. Add or retain a regression test when the
new floor is required for observable runtime behavior.

### Upper bounds

Upper bounds prevent unreviewed resolution across compatibility boundaries. Runtime dependencies
normally remain capped below the next major version. Narrower caps are appropriate for dependencies
whose compatibility policy or release history requires them.

Raise an upper bound only after reviewing the new release family, resolving the lockfile, and
running the relevant validation. Avoid speculative widening merely to suppress resolver warnings.

### Adding, replacing, or removing dependencies

A new runtime dependency must correspond to an actual runtime requirement and be declared directly;
do not rely on a transitive dependency. Removal requires confirming that no supported runtime path,
optional feature, type-checking surface, or packaging metadata still relies on it.

Dependency Review applies the repository's runtime license and vulnerability policy to pull request
dependency diffs. That check complements version compatibility review rather than replacing it.

______________________________________________________________________

## Update classification

Classify dependency work by its effect, not only by which file changed:

| Change                                                           | Default classification    | Review expectation                                                         |
| ---------------------------------------------------------------- | ------------------------- | -------------------------------------------------------------------------- |
| Refresh `uv.lock` within unchanged ranges                        | Maintenance               | Review direct and transitive changes; run normal validation                |
| Update a pre-commit hook revision without changing policy        | Tooling maintenance       | Run pre-commit and reconcile related project-tool constraints if necessary |
| Raise or narrow a published dependency range                     | Compatibility-impacting   | Document rationale and assess release and migration impact                 |
| Widen a range for a newly accepted release family                | Compatibility expansion   | Validate the new family and refresh the lockfile                           |
| Add, replace, or remove a runtime dependency                     | Runtime/packaging change  | Review imports, metadata, license, vulnerability, and consumer impact      |
| Change tooling behavior that contributors must accommodate       | Developer-workflow change | Update contributor guidance and release notes                              |
| Apply a dependency update that fixes shipped vulnerable behavior | Correctness/security fix  | Document the affected behavior and any minimum-version change              |

A range change is not routine lockfile maintenance. If it makes an environment previously described
as supported impossible to install, treat that as a compatibility decision and apply TopMark's
normal breaking-change assessment.

______________________________________________________________________

## Maintenance workflow

### Refreshing the lockfile

Use the non-upgrading command after an intentional manifest edit:

```bash
make uv-lock
```

Use the upgrading command for a deliberate refresh of versions within the existing ranges:

```bash
make uv-lock-upgrade
```

Then:

1. inspect both direct and transitive changes in `uv.lock`;
1. confirm unexpected package additions or removals;
1. review platform markers and supported-Python constraints;
1. run `uv lock --check` to confirm that the lockfile matches `pyproject.toml`;
1. inspect the resolved graph with `uv tree --frozen`;
1. commit `pyproject.toml` and `uv.lock` together when the declared ranges changed.

Avoid combining an unrelated whole-lockfile upgrade with a focused compatibility fix. A smaller diff
is easier to review, diagnose, and revert.

### Updating pre-commit hooks

Use `pre-commit autoupdate` as a proposal generator, not as an automatic approval step. Review:

- release notes and compatibility changes for every updated hook;
- whether matching tools in `pyproject.toml` should move at the same time;
- hook-local `additional_dependencies`;
- repository-local hooks and manual stages that `autoupdate` does not manage;
- TopMark's exported hook revision independently from the checked-out project version.

Run all hooks after an update:

```bash
pre-commit run --all-files
```

GitHub Action dependencies are maintained separately through SHA-pinned workflow references,
Dependabot, and the GitHub Action pin audit.

### Validating an update

For routine dependency maintenance, run:

```bash
make venv-sync-all
make pre-pr
make test
```

Use focused tests or a clean boundary-version environment when changing a lower bound. GitHub CI
then validates the supported Python matrix, while Dependency Review checks changed runtime
dependencies for accepted licenses and high- or critical-severity known vulnerabilities.

Published artifact validation remains relevant when a dependency change can affect installation or
runtime resolution from PyPI or TestPyPI.

______________________________________________________________________

## Changelog and release policy

Record dependency changes according to their effect:

- use **Changed** for published range changes, dependency replacements, and contributor-visible
  tooling behavior;
- use **Fixed** when a dependency change corrects a shipped defect or vulnerability;
- use **Added** when a new dependency enables a new user-visible capability;
- use **Internal** for routine lockfile, transitive dependency, or pre-commit refreshes with no
  consumer-visible effect.

The changelog entry should name an important lower-bound or compatibility change and explain why it
was required. A generic "updated dependencies" entry is sufficient only for a routine refresh with
no separate compatibility significance.

Before release, confirm that:

- `pyproject.toml` expresses the intended published compatibility ranges;
- `uv.lock` is synchronized and reviewed;
- CI has validated all supported Python versions;
- pre-commit pins represent the intended contributor tooling;
- compatibility-impacting changes appear in `CHANGELOG.md` and any necessary migration guidance.

Dependency changes do not alter TopMark's package version directly. Versions remain derived from Git
tags through `setuptools-scm`, and maintainers select the release impact after reviewing the actual
compatibility effect.

______________________________________________________________________

## Related pages

- [Contributing to TopMark](../contributing.md)
- [Dependabot workflow](../ci/dependabot.md)
- [Dependency review workflow](../ci/dependency-review.md)
- [Test and validation architecture](../ci/test-validation.md)
- [CI workflow](../ci/ci-workflow.md)
- [Release process](release-process.md)
