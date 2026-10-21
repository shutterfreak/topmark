<!--
topmark:header:start

  project      : TopMark
  file         : test-validation.md
  file_relpath : docs/ci/test-validation.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Test and validation architecture

TopMark groups validation by intent rather than through a single monolithic test command. GitHub
workflows orchestrate validation, nox sessions provide stable reusable commands, pytest markers
describe test purpose, and Makefile targets provide thin local convenience wrappers.

{% include-markdown "\_snippets/terminology.md" %}

This page explains how those layers fit together and how contributors should choose the right
validation path.

## Validation Layers

| Layer            | Role                                                                                                              |
| ---------------- | ----------------------------------------------------------------------------------------------------------------- |
| GitHub workflows | Repository, release, dependency, and published-artifact validation orchestration.                                 |
| nox sessions     | Reusable validation contracts for linting, typing, tests, docs, links, release checks, and performance baselines. |
| pytest markers   | Semantic grouping of tests by behavior, scope, or runtime expectations.                                           |
| Makefile targets | Thin aliases for Nox-backed validation workflows, plus local environment and cleanup shortcuts.                   |

The preferred mental model is:

```text
GitHub workflow -> nox session -> pytest selection or tool command
```

Some workflows intentionally duplicate setup steps instead of sharing a local composite action. This
keeps security-sensitive workflow boundaries explicit, especially around release artifacts and
privileged publishing.

______________________________________________________________________

## Validation model

TopMark intentionally separates:

1. local developer shortcuts;
1. nox validation contracts;
1. pytest marker selection;
1. source-tree CI validation;
1. release artifact validation;
1. published-package validation.

This layered validation model keeps stable local commands, CI workflows, release checks, and
published-artifact validation aligned without collapsing them into one monolithic command.

______________________________________________________________________

## Validation Philosophy

TopMark validation favors:

- explicit CI behavior over hidden workflow abstraction;
- stable nox sessions over ad-hoc shell commands;
- focused pytest markers over broad naming conventions;
- dry-run and source-tree validation before mutation or publication;
- intentionally redundant checks where they validate different compatibility contracts;
- local coverage diagnostics alongside a non-informational Codecov project-comparison policy,
  without treating coverage as a percentage-driven release gate;
- Python-version metadata derived from project metadata rather than duplicated manually in CI where
  practical.

For example, CI artifact generation and published artifact validation may look related, but they
validate different things. CI validates artifacts built from the repository source tree. Published
artifact validation checks what an end user receives from a package index.

______________________________________________________________________

## Pytest Marker Taxonomy

Pytest markers are declared in `pyproject.toml` under `[tool.pytest.ini_options]`.

Pytest markers are reserved for cross-cutting test semantics rather than package membership.
Package- or subsystem-specific test selection should normally use test paths (for example,
`pytest tests/cli`) instead of markers. Nox marker expressions should reference only declared
markers so exclusions remain visible in the central pytest configuration.

| Marker                | Purpose                                                                                                                                                             | CI expectation                                                                    |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `case_insensitive_fs` | Tests for behavior that depends on case-insensitive filesystem semantics.                                                                                           | Run where the host filesystem can exercise them.                                  |
| `dev_validation`      | Developer-validation checks for repository invariants such as test-layout consistency and pytest marker hygiene.                                                    | Included in normal test runs.                                                     |
| `exit_code`           | Tests that validate the CLI exit-code contract.                                                                                                                     | Included in normal test runs.                                                     |
| `hypothesis_slow`     | Long-running property tests.                                                                                                                                        | Skipped in CI unless explicitly selected.                                         |
| `integration`         | Environment-dependent integration checks that exercise interactions with external tooling, the operating system, or shell features (for example, shell completion). | Run selectively where the environment supports them.                              |
| `smoke`               | Small, hand-picked cross-cutting checks that provide early feedback for the CLI, public API, and registry.                                                          | Runs on canonical Python as an early-feedback job; full QA remains authoritative. |

Pytest's project defaults include `-rsx`, so completed test runs report the reasons for skipped and
expected-failure tests. This improves review and troubleshooting feedback only; it does not select
tests or change their pass/fail semantics.

______________________________________________________________________

## Developer Validation Tests

The `dev_validation` marker identifies repository-internal invariant checks rather than user-facing
behavior. It is reserved for test-suite and validation-taxonomy invariants. Run them explicitly when
working on test infrastructure:

```bash
pytest -m dev_validation
# or run the QA session and select the marker:
nox -s qa -p 3.15 -- -m dev_validation
```

The marked checks live under `tests/dev_validation/` and include:

- test-package layout checks that keep Python test directories importable by absolute package name.
- pytest marker declarations and marker-expression consistency.

Example:

```python
import pytest


@pytest.mark.dev_validation
def test_pytest_markers_are_declared() -> None: ...
```

These tests are part of the normal test suite and do not require a dedicated CI job. Registry and
processor-placement invariants are ordinary parameterized tests: they run in the normal test suite,
are included in its coverage report, and do not require a runtime environment variable.

Executable tests for repository maintenance and validation tools live under `tests/tools/`,
mirroring the relevant `tools/` subdirectories. Select them by path rather than applying the
`dev_validation` marker:

```bash
pytest tests/tools
pytest tests/tools/docs
```

______________________________________________________________________

## Local Test Selection

Supported Python versions are resolved by `noxfile.py` from `pyproject.toml` using Nox's project
metadata helpers. Matrix sessions run across the supported Python versions, while canonical
single-version sessions use the most recent supported Python version.

Run the recommended local pre-PR validation gate before opening or updating a pull request:

```bash
make pre-pr
```

The pre-PR gate runs formatting checks, lint checks, documentation hygiene, a strict docs build, a
self-check of every tracked file through the current TopMark checkout, the canonical Python QA
session, and the public API snapshot check. It is a local confidence shortcut rather than a
replacement for GitHub CI.

The public API snapshot is a schema-versioned structural equality check derived from
`topmark.api.__all__`. It protects callable signatures, exported dataclass and TypedDict contracts,
public type-alias expressions, enum members, and the deliberately narrow ordinary-class category.
Use `make api-snapshot-dev` for the current interpreter, `make api-snapshot` for Python 3.10-3.15,
and `make api-snapshot-update` only for an intentional, reviewed golden-file change.

Run the full default test suite through nox on the canonical Python version:

```bash
nox -s qa -p 3.15
```

Validate the declared lower bounds for direct dependencies:

```bash
make dependency-lower-bounds
```

This command temporarily resolves direct dependencies with uv's `lowest-direct` strategy, runs the
normal pytest and Pyright QA contract across the supported Python matrix, then restores the exact
original `uv.lock`. It validates TopMark's direct dependency-floor claims while keeping transitive
dependencies current; it does not claim to validate every possible historical transitive-dependency
combination.

Run the fast smoke suite when you need an early signal from representative contracts:

```bash
nox -s smoke
# or
make smoke
```

The smoke suite is selected exclusively by `pytest.mark.smoke`; it is deliberately not a replacement
for the full QA suite or pre-PR gate.

Generate the canonical local coverage report:

```bash
make coverage
```

This measures only `src/topmark/` and generates local HTML, XML, and JSON reports without publishing
them. Measure repository tooling separately with:

```bash
make coverage-tools
```

That command measures `tools/` through `tests/tools/` and writes distinct reports. Tool
implementation tests belong under `tests/tools/`, including the structured API snapshot generator;
the API snapshot's baseline-equality contract remains under `tests/api/`. The dedicated CI coverage
job retains both report sets as GitHub Actions artifacts and uploads them separately to Codecov.
Product coverage retains the documented tolerance and informational patch status. Tooling coverage
has a separate informational Codecov project status against its reviewed 71.8% baseline, allowing a
2 percentage-point tolerance; it is visible for review but does not block a merge. The tooling
report covers deterministic repository-maintenance tools; generator and performance-baseline tests
exercise their deterministic generation, parsing, and reporting paths, but do not execute full
documentation builds or performance workloads merely to raise coverage. Contributors do not need
Codecov credentials for local coverage. See the [CI workflow](./ci-workflow.md#artifact-handling)
for the reporting and artifact model.

Afterwards, run the changed-lines diagnostic:

```bash
make coverage-changed
```

It compares changed executable `src/topmark/` lines and branch exits with `coverage.json`, reporting
uncovered locations with source context. It is informational and does not add CI enforcement or
modify Codecov policy. The default base is the merge base of `origin/main`, falling back to `main`.
For a CI-style comparison, `GITHUB_BASE_REF` selects the base branch (preferring its `origin/`
remote); use `COVERAGE_CHANGED_ARGS="--base <revision>"` or `COVERAGE_CHANGED_BASE` to choose an
explicit base. The comparison includes staged and unstaged changes, maps renamed files to their
current paths, and omits deleted files. If `coverage.json` is absent, it reports that coverage was
not assessed rather than treating the change as covered.

Run `make coverage` after the source and test edits you want to review, then run
`make coverage-changed` immediately afterwards. A report generated before later source edits can
have stale execution and line data, producing a misleading assessment. A clean working tree is still
valid when branch changes are committed because the diagnostic compares the branch with its merge
base. An unchanged `main` checkout, or a branch that changes only documentation/tooling, has no
changed package source lines to assess. Stage newly added `src/topmark/` files before running the
diagnostic: untracked files do not appear in Git's diff.

Inspect the Python metadata consumed by CI:

```bash
nox -s print_python_matrix
```

Run only developer-validation invariant checks:

```bash
pytest -m dev_validation
```

Or run the same marker selection through nox:

```bash
nox -s qa -p 3.15 -- -m dev_validation
```

Run slow property tests only when intentionally investigating property-test behavior:

```bash
pytest -m hypothesis_slow
```

______________________________________________________________________

## Parallel local pytest execution

TopMark includes `pytest-xdist` in the test dependency group. Normal nox sessions and selected
Makefile targets keep pytest execution serial by default, but they support forwarded pytest
arguments for local experimentation and faster feedback.

Common opt-in examples are:

```bash
make pre-pr PYTEST_PAR="-n auto"
make test PYTEST_PAR="-n auto"
make coverage PYTEST_PAR="-n auto"
make coverage-tools PYTEST_PAR="-n auto"
make release-check PYTEST_PAR="-n auto"
nox -s pre_pr -- -n auto
nox -s qa -p 3.15 -- -n auto
nox -s qa_api -p 3.15 -- -n auto
nox -s coverage -p 3.15 -- -n auto
nox -s coverage_tools -p 3.15 -- -n auto
nox -s release_check -- -n auto
```

CI keeps pytest execution serial inside each job even though local parallel execution is supported.
The workflow already uses job-level parallelism for the supported Python matrix and the
cross-platform filesystem checks. Keeping per-job pytest execution serial makes coverage artifacts,
release-gate diagnostics, and failure logs easier to compare across runs.

______________________________________________________________________

## nox and Makefile Mapping

nox sessions are the stable validation interface used by CI and local development. Makefile
validation targets should remain thin convenience wrappers rather than a separate source of
validation truth or composite orchestration.

Common mappings are:

| Need                                               | Preferred command                  |
| -------------------------------------------------- | ---------------------------------- |
| Run the recommended local pre-PR gate              | `make pre-pr`                      |
| Run non-test local quality checks, including links | `nox -s verify`                    |
| Run the main quality gate on the canonical Python  | `nox -s qa -p 3.15`                |
| Validate direct dependency lower bounds            | `make dependency-lower-bounds`     |
| Run the fast marker-selected smoke suite           | `nox -s smoke`                     |
| Generate canonical coverage data                   | `nox -s coverage -p 3.15`          |
| Generate repository-tooling coverage data          | `nox -s coverage_tools -p 3.15`    |
| Diagnose changed-lines coverage                    | `nox -s coverage_changed -p 3.15`  |
| Run local pytest in parallel                       | `nox -s qa -p 3.15 -- -n auto`     |
| Print CI Python metadata                           | `nox -s print_python_matrix`       |
| Run a marker-specific test subset                  | `nox -s qa -p 3.15 -- -m <marker>` |
| Build documentation                                | `nox -s docs`                      |
| Build production Zensical documentation            | `nox -s docs`                      |
| Serve production Zensical documentation            | `nox -s docs_serve`                |
| Validate documentation links                       | `nox -s links`                     |
| Run release checks                                 | `nox -s release_check`             |
| Run the full release gate                          | `nox -s release_full`              |
| Run pipeline memory/allocation baselines           | `nox -s perf_baseline`             |

The concrete canonical version shown above is expected to move when the supported Python range
moves. CI consumes the JSON output from `print_python_matrix` so the test matrix and canonical
single-version jobs can follow `pyproject.toml` without duplicating version literals in the main CI
workflow. Automation that needs this metadata must consume `print_python_matrix` rather than parse
the human-facing output of `nox -l`.

If a Makefile target wraps one of these commands, the Nox session remains the canonical validation
contract. The `verify` and `release_full` composites are defined only in `noxfile.py`; their Make
targets are aliases.

______________________________________________________________________

## Performance baseline measurements

TopMark includes an opt-in performance baseline session for memory and allocation investigations.

Run the canonical baseline suite:

```bash
nox -s perf_baseline
```

Or use the local convenience target:

```bash
make perf-baseline
```

The performance baseline tooling is intentionally separate from the normal quality gates.

Performance measurements are exploratory diagnostics rather than correctness checks. They are not
currently executed in CI and do not gate releases.

See [Performance baselines](../dev/performance-baselines.md) for benchmark methodology, workload
definitions, output layout, and baseline results.

______________________________________________________________________

## Slow and Integration Tests

Slow and environment-dependent tests should be marked explicitly.

- Use `hypothesis_slow` for long-running property tests that are not suitable for default CI runs.
- Use `integration` for tests that require external shell behavior, optional platform support, or
  environment-specific assumptions.

These markers make CI exclusions visible and intentional instead of relying on hidden filename or
directory-selection conventions. Marker expressions used by Nox and other project tooling (such as
the `Makefile`) should remain aligned with the declarations in `pyproject.toml`;
developer-validation tests help detect stale references.

______________________________________________________________________

## Release and Artifact Validation

Release validation and published-artifact validation are related but distinct.

- Release validation checks whether the repository, version, changelog, built distributions, and
  release metadata are coherent before publication.
- Published artifact validation checks whether an already published package can be installed and
  used from a clean consumer-like environment.

This distinction is intentional and should remain explicit even when commands or workflows appear
similar.

______________________________________________________________________

## Coverage reporting

Coverage reporting is intentionally separate from release validation and published-artifact
validation. It has distinct diagnostic and pull-request-policy roles: local reports and the
changed-lines diagnostic help contributors assess repository health and test effectiveness, while
the CI coverage job must generate the canonical report successfully. Codecov's non-informational
project status separately fails when pull-request project coverage declines by more than the
documented tolerance.

This does not make coverage a release-publication gate or a GitHub-required branch-protection
status: coverage runs only for Python-relevant pull requests. Patch coverage remains informational.
See the [Codecov coverage policy](./codecov.md) for the project-status threshold and review model.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
