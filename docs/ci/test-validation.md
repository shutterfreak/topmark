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
describe test purpose, and Makefile targets provide local convenience wrappers.

{% include-markdown "\_snippets/terminology.md" %}

This page explains how those layers fit together and how contributors should choose the right
validation path.

## Validation Layers

| Layer            | Role                                                                                                              |
| ---------------- | ----------------------------------------------------------------------------------------------------------------- |
| GitHub workflows | Repository, release, dependency, and published-artifact validation orchestration.                                 |
| nox sessions     | Reusable validation contracts for linting, typing, tests, docs, links, release checks, and performance baselines. |
| pytest markers   | Semantic grouping of tests by behavior, scope, or runtime expectations.                                           |
| Makefile targets | Local shortcuts for common contributor workflows.                                                                 |

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
- coverage reporting as a diagnostic confidence signal rather than a percentage-driven release gate;
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

| Marker                | Purpose                                                                                                                                                             | CI expectation                                       |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `case_insensitive_fs` | Tests for behavior that depends on case-insensitive filesystem semantics.                                                                                           | Run where the host filesystem can exercise them.     |
| `dev_validation`      | Developer validation tests for internal invariants such as registry integrity, test-layout consistency, and pytest marker hygiene.                                  | Included in normal test runs.                        |
| `exit_code`           | Tests that validate the CLI exit-code contract.                                                                                                                     | Included in normal test runs.                        |
| `hypothesis_slow`     | Long-running property tests.                                                                                                                                        | Skipped in CI unless explicitly selected.            |
| `integration`         | Environment-dependent integration checks that exercise interactions with external tooling, the operating system, or shell features (for example, shell completion). | Run selectively where the environment supports them. |

______________________________________________________________________

## Developer Validation Tests

The `dev_validation` marker identifies tests that check internal invariants rather than user-facing
behavior.

Typical examples live under `tests/dev_validation/` and include:

- registry consistency between processors and file types;
- sanity checks for internal plugin mappings;
- placement-strategy checks for XML/HTML-like processors;
- test-package layout checks that keep Python test directories importable by absolute package name.
- pytest marker declarations and marker-expression consistency.

Example:

```python
import pytest

@pytest.mark.dev_validation
def test_registered_processors_map_to_existing_filetypes() -> None:
    ...
```

These tests are part of the normal test suite. Developer-validation checks are part of the normal
test path and do not require a dedicated CI job.

______________________________________________________________________

## Local Test Selection

Supported Python versions are resolved by `noxfile.py` from `pyproject.toml` using Nox's project
metadata helpers. Matrix sessions run across the supported Python versions, while canonical
single-version sessions use the second most recent supported Python version.

Run the recommended local pre-PR validation gate before opening or updating a pull request:

```bash
make pre-pr
```

The pre-PR gate runs formatting checks, lint checks, documentation hygiene, a strict docs build, the
canonical Python QA session, and the public API snapshot check. It is a local confidence shortcut
rather than a replacement for GitHub CI.

Run the full default test suite through nox on the canonical Python version:

```bash
nox -s qa -p 3.13
```

Generate the canonical local coverage report:

```bash
nox -s coverage -p 3.13
```

Inspect the Python metadata consumed by CI:

```bash
nox -s print_python_matrix
```

Run only developer-validation tests:

```bash
pytest -m dev_validation
```

Or run the same marker selection through nox:

```bash
nox -s qa -p 3.13 -- -m dev_validation
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
make release-check PYTEST_PAR="-n auto"
nox -s pre_pr -- -n auto
nox -s qa -p 3.13 -- -n auto
nox -s qa_api -p 3.13 -- -n auto
nox -s coverage -p 3.13 -- -n auto
nox -s release_check -- -n auto
```

CI keeps pytest execution serial inside each job even though local parallel execution is supported.
The workflow already uses job-level parallelism for the supported Python matrix and the
cross-platform filesystem checks. Keeping per-job pytest execution serial makes coverage artifacts,
release-gate diagnostics, and failure logs easier to compare across runs.

______________________________________________________________________

## Runtime Validation Hooks

Some internal validation checks can also be enabled at runtime with `TOPMARK_VALIDATE=1`.

```bash
TOPMARK_VALIDATE=1 pytest -q
# or when running the CLI during development
TOPMARK_VALIDATE=1 topmark registry processors --output-format json
# or:
pytest -m dev_validation
# or run the QA session and select the marker:
nox -s qa -p 3.13 -- -m dev_validation
```

Runtime validation is intended for development and debugging. It should remain lightweight and must
not introduce end-user overhead unless explicitly enabled.

______________________________________________________________________

## What Developer Validation Checks

Developer-validation checks include:

- **Registry integrity**: every registered header processor maps to an existing canonical file type
  identity.
- **Placement strategy for XML/HTML**: processors based on `XmlHeaderProcessor` must signal the
  character-offset strategy by returning `NO_LINE_ANCHOR` from `get_header_insertion_index()`.
- **Test package layout**: every directory under `tests/` that contains Python modules must include
  an `__init__.py` marker so test modules have stable absolute package names.
- **Pytest marker hygiene**: every custom marker used by the test suite is declared in
  `pyproject.toml`, and marker expressions referenced by project tooling remain aligned with the
  declared marker set.

These checks avoid accidental miswiring, such as registering a processor under a typo key, help
prevent XML/HTML-like processors from regressing into line-based insertion behavior, and keep the
test suite aligned with TopMark's absolute-import convention.

______________________________________________________________________

## nox and Makefile Mapping

nox sessions are the stable validation interface used by CI and local development. Makefile targets
should remain convenience wrappers rather than a separate source of validation truth.

Common mappings are:

| Need                                              | Preferred command                  |
| ------------------------------------------------- | ---------------------------------- |
| Run the recommended local pre-PR gate             | `make pre-pr`                      |
| Run the main quality gate on the canonical Python | `nox -s qa -p 3.13`                |
| Generate canonical coverage data                  | `nox -s coverage -p 3.13`          |
| Run local pytest in parallel                      | `nox -s qa -p 3.13 -- -n auto`     |
| Print CI Python metadata                          | `nox -s print_python_matrix`       |
| Run a marker-specific test subset                 | `nox -s qa -p 3.13 -- -m <marker>` |
| Build documentation                               | `nox -s docs`                      |
| Validate documentation links                      | `nox -s links`                     |
| Run release checks                                | `nox -s release_check`             |
| Run pipeline memory/allocation baselines          | `nox -s perf_baseline`             |

The concrete canonical version shown above is expected to move when the supported Python range
moves. CI consumes the JSON output from `print_python_matrix` so the test matrix and canonical
single-version jobs can follow `pyproject.toml` without duplicating version literals in the main CI
workflow.

If a Makefile target wraps one of these commands, the nox session remains the canonical validation
contract.

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
validation. Coverage is used as a lightweight diagnostic signal for repository health and test
effectiveness, not as a publication-time compatibility contract.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
