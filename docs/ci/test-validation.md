<!--
topmark:header:start

  project      : TopMark
  file         : test-validation.md
  file_relpath : docs/ci/test-validation.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Test & Validation Architecture

TopMark groups validation by intent rather than by a single monolithic test command. GitHub
workflows orchestrate validation, nox sessions provide stable reusable commands, pytest markers
describe test purpose, and Makefile targets offer local convenience wrappers.

This page explains how those layers fit together and how contributors should choose the right
validation path.

## Validation Layers

| Layer            | Role                                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------ |
| GitHub workflows | Repository, release, dependency, and published-artifact orchestration.                     |
| nox sessions     | Reusable validation contracts for linting, typing, tests, docs, links, and release checks. |
| pytest markers   | Semantic grouping of tests by behavior, scope, or runtime expectations.                    |
| Makefile targets | Local shortcuts for common contributor workflows.                                          |

The preferred mental model is:

```text
GitHub workflow -> nox session -> pytest selection / tool command
```

Some workflows intentionally duplicate setup steps instead of sharing a local composite action. This
keeps security-sensitive workflow boundaries explicit, especially around release artifacts and
privileged publishing.

______________________________________________________________________

## Validation Philosophy

TopMark validation favors:

- explicit CI behavior over hidden workflow abstraction;
- stable nox sessions over ad-hoc shell commands;
- focused pytest markers over broad naming conventions;
- dry-run and source-tree validation before mutation or publication;
- redundant checks where they validate different contracts.

For example, CI artifact generation and published artifact validation may look related, but they
validate different things. CI validates artifacts built from the repository source tree. Published
artifact validation checks what an end user receives from a package index.

______________________________________________________________________

## Pytest Marker Taxonomy

Pytest markers are declared in `pyproject.toml` under `[tool.pytest.ini_options]`.

| Marker            | Purpose                                                                                     | CI expectation                                       |
| ----------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `api`             | Tests that exercise the public API.                                                         | Included in normal test runs.                        |
| `cli`             | Tests that exercise the command-line interface.                                             | Included in normal test runs.                        |
| `config`          | Tests for config deserialization, path normalization, strictness, and layer merge behavior. | Included in normal test runs.                        |
| `dev_validation`  | Developer validation tests for internal invariants such as registry consistency.            | Included in normal test runs.                        |
| `exit_code`       | Tests that validate the CLI exit-code contract.                                             | Included in normal test runs.                        |
| `hypothesis_slow` | Long-running property tests.                                                                | Skipped in CI unless explicitly selected.            |
| `integration`     | Environment-dependent integration checks, such as shell completion.                         | Run selectively where the environment supports them. |
| `pipeline`        | Tests that exercise the processing pipeline.                                                | Included in normal test runs.                        |
| `toml`            | Tests for TopMark TOML loading, extraction, schema validation, and source resolution.       | Included in normal test runs.                        |

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
from tests.conftest import mark_dev_validation

@mark_dev_validation
def test_registered_processors_map_to_existing_filetypes() -> None:
    ...
```

These tests are part of the normal test suite. Earlier versions used a dedicated
developer-validation CI job, but this was folded into the general test path to keep the workflow
simpler.

______________________________________________________________________

## Local Test Selection

Run the full default test suite through nox:

```bash
nox -s qa -p 3.13
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

Some internal validation can also be enabled at runtime with `TOPMARK_VALIDATE=1`.

```bash
TOPMARK_VALIDATE=1 pytest -q
# or when running the CLI during development
TOPMARK_VALIDATE=1 topmark registry processors --output-format json
# or:
pytest -m dev_validation
# or run the QA session and select the marker:
nox -s qa -p 3.13 -- -m dev_validation
```

Runtime validation is intended for development and debugging. It should remain lightweight and
should not introduce end-user overhead unless explicitly enabled.

______________________________________________________________________

## What Developer Validation Checks

Current developer-validation checks include:

- **Registry integrity**: every registered header processor maps to an existing `FileType` name.
- **Placement strategy for XML/HTML**: processors based on `XmlHeaderProcessor` must signal the
  character-offset strategy by returning `NO_LINE_ANCHOR` from `get_header_insertion_index()`.

These checks avoid accidental miswiring, such as registering a processor under a typo key, and help
prevent XML/HTML-like processors from regressing into line-based insertion behavior.

______________________________________________________________________

## nox and Makefile Mapping

nox sessions are the stable validation interface used by CI and local development. Makefile targets
should remain convenience wrappers rather than a separate source of validation truth.

Common mappings are:

| Need                              | Preferred command                  |
| --------------------------------- | ---------------------------------- |
| Run the main quality gate         | `nox -s qa -p 3.13`                |
| Run a marker-specific test subset | `nox -s qa -p 3.13 -- -m <marker>` |
| Build documentation               | `nox -s docs`                      |
| Validate documentation links      | `nox -s links`                     |
| Run release checks                | `nox -s release_check`             |

If a Makefile target wraps one of these commands, the nox session remains the canonical contract.

______________________________________________________________________

## Slow and Integration Tests

Slow and environment-dependent tests should be marked explicitly.

- Use `hypothesis_slow` for long-running property tests that are not suitable for default CI runs.
- Use `integration` for tests that require external shell behavior, optional platform support, or
  environment-specific assumptions.

These markers make CI exclusions visible and intentional instead of relying on hidden filename or
directory conventions.

______________________________________________________________________

## Release and Artifact Validation

Release validation and published-artifact validation are related but distinct.

- Release validation checks whether the repository, version, changelog, built distributions, and
  release metadata are coherent before publication.
- Published artifact validation checks whether an already published package can be installed and
  used from a clean consumer-like environment.

This distinction is intentional and should remain documented even when commands appear redundant.

______________________________________________________________________

## Related Pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
