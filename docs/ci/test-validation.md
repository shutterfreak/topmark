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

| Layer            | Role                                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------ |
| GitHub workflows | Repository, release, dependency, and published-artifact validation orchestration.          |
| nox sessions     | Reusable validation contracts for linting, typing, tests, docs, links, and release checks. |
| pytest markers   | Semantic grouping of tests by behavior, scope, or runtime expectations.                    |
| Makefile targets | Local shortcuts for common contributor workflows.                                          |

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

| Marker                                                   | Purpose                                                                                            | CI expectation                                       |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `api`                                                    | Tests that exercise the public API.                                                                | Included in normal test runs.                        |
| `cli`                                                    | Tests that exercise the command-line interface.                                                    | Included in normal test runs.                        |
| `config`                                                 | Tests for configuration deserialization, path normalization, strictness, and layer merge behavior. | Included in normal test runs.                        |
| `dev_validation`                                         | Developer validation tests for internal invariants such as registry consistency.                   | Included in normal test runs.                        |
| `exit_code`                                              | Tests that validate the CLI exit-code contract.                                                    | Included in normal test runs.                        |
| `hypothesis_slow`                                        | Long-running property tests.                                                                       | Skipped in CI unless explicitly selected.            |
| `integration`                                            | Environment-dependent integration checks, such as shell completion.                                | Run selectively where the environment supports them. |
| `pipeline`                                               | Tests that exercise the processing pipeline, including filesystem-identity evaluation and          |                                                      |
| processing-target eligibility behavior where applicable. | Included in normal test runs.                                                                      |                                                      |
| `toml`                                                   | Tests for TopMark TOML loading, extraction, schema validation, and source resolution.              | Included in normal test runs.                        |

______________________________________________________________________

## Developer Validation Tests

The `dev_validation` marker identifies tests that check internal invariants rather than user-facing
behavior.

Typical examples include:

- registry consistency between processors and file types;
- sanity checks for internal plugin mappings;
- placement-strategy checks for XML/HTML-like processors.

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

These checks avoid accidental miswiring, such as registering a processor under a typo key, and help
prevent XML/HTML-like processors from regressing into line-based insertion behavior.

______________________________________________________________________

## nox and Makefile Mapping

nox sessions are the stable validation interface used by CI and local development. Makefile targets
should remain convenience wrappers rather than a separate source of validation truth.

Common mappings are:

| Need                                              | Preferred command                  |
| ------------------------------------------------- | ---------------------------------- |
| Run the main quality gate on the canonical Python | `nox -s qa -p 3.13`                |
| Generate canonical coverage data                  | `nox -s coverage -p 3.13`          |
| Print CI Python metadata                          | `nox -s print_python_matrix`       |
| Run a marker-specific test subset                 | `nox -s qa -p 3.13 -- -m <marker>` |
| Build documentation                               | `nox -s docs`                      |
| Validate documentation links                      | `nox -s links`                     |
| Run release checks                                | `nox -s release_check`             |

The concrete canonical version shown above is expected to move when the supported Python range
moves. CI consumes the JSON output from `print_python_matrix` so the test matrix and canonical
single-version jobs can follow `pyproject.toml` without duplicating version literals in the main CI
workflow.

If a Makefile target wraps one of these commands, the nox session remains the canonical validation
contract.

______________________________________________________________________

## Slow and Integration Tests

Slow and environment-dependent tests should be marked explicitly.

- Use `hypothesis_slow` for long-running property tests that are not suitable for default CI runs.
- Use `integration` for tests that require external shell behavior, optional platform support, or
  environment-specific assumptions.

These markers make CI exclusions visible and intentional instead of relying on hidden filename or
directory-selection conventions.

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
