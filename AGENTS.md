<!--
topmark:header:start

  project      : TopMark
  file         : AGENTS.md
  file_relpath : AGENTS.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Agent guidance

## Scope and sources of truth

This file applies to the entire repository.

- Treat `CONTRIBUTING.md` as the canonical contributor guide.
- Consult `docs/dev/documentation-conventions.md` for documentation changes.
- Consult `docs/dev/api-stability.md` before changing the public API.
- Consult `docs/ci/test-validation.md` for validation architecture.
- Consult `docs/dev/dependency-maintenance.md` before changing dependencies.
- Keep this file concise. Put detailed policies in their canonical documentation rather than
  duplicating them here.

______________________________________________________________________

## Repository map

- `src/topmark/` contains the Python package.
- `tests/` mirrors the package and contains integration, repository-tooling, and
  developer-validation tests.
- `tests/typecheck/` contains Pyright-only structural-conformance fixtures. They are not pytest
  tests and do not contribute runtime coverage; use real production providers rather than test
  doubles. See `docs/dev/protocol-contracts.md`.
- `docs/` contains the Zensical documentation source.
- `tools/` contains repository maintenance and validation utilities.
- `.github/` contains CI, release, and dependency-maintenance automation.
- `noxfile.py` defines canonical isolated validation sessions.
- `Makefile` provides the preferred contributor-facing command entry points.

______________________________________________________________________

## Project constraints

- Preserve support for Python 3.11 through 3.15.
- Treat Python 3.15 as the canonical local QA interpreter.
- Preserve the stable public API exported through `topmark.api.__all__`.
- Treat CLI behavior, configuration semantics, machine-readable output, and filesystem/path
  serialization as compatibility-sensitive contracts.
- Do not update `tests/api/public_api_snapshot.json` merely to make a test pass. Update it only
  after confirming that the public API change is intentional.
- Package versions come from Git tags through `setuptools-scm`; do not add or change a manual
  version in `pyproject.toml`.
- Keep compatibility ranges in `pyproject.toml` distinct from resolved versions in `uv.lock`.
- Preserve TopMark headers in eligible tracked files and ensure new, renamed, and relocated files
  include the standard TopMark comment header block. Use `topmark check --apply FILE` to add or
  update headers; use the existing pre-commit checks to verify compliance instead of editing
  generated header metadata casually.
- Never add repository secrets, service tokens, coverage credentials, or local environment data to
  tracked files or diagnostic output.

______________________________________________________________________

## Implementation practices

### Core workflows

- Inspect the working tree before editing and preserve unrelated user changes.
- Leave changes unstaged by default. Do not auto-commit; stage or commit only when the user
  explicitly asks.
- Keep changes focused and add or update tests alongside behavioral changes.
- Prefer the existing Make, Nox, and repository tool entry points over ad hoc replacements.
- For ad hoc Python or tool invocation, use `uv run` (e.g., `uv run pytest`, `uv run pyright`) to
  ensure execution inside the project environment. Prefer the documented Make or Nox entry points
  for repository validation.
- Keep documentation links relative inside `docs/` unless the documented conventions specifically
  require a hosted URL.
- Update documentation when behavior, configuration, commands, CI, or supported workflows change.

### Code quality and validation

- When Pyright or Ruff reports an error, fix the root cause (e.g., correct the type annotation or
  refactor) rather than masking it with `# type: ignore` or `# noqa` unless there is a documented,
  unavoidable justification.
- Follow the Ruff and Pyright configuration in `pyproject.toml`.

### Docstring formatting rules

- Use Google-style docstrings and maintain accurate public exception contracts.
- Every public module, class, function, and method must contain a docstring.
- If a docstring requires more than 1 line, structure it exactly with the following ordering and
  spacing:
  1. A concise, single-line "title" summary string.
  1. Exactly one blank line.
  1. An expanded descriptive paragraph detailing functional behavior (one or more paragraphs).
  1. Exactly one blank line.
  1. An `Args:` or `Attributes:` section itemizing elements, matching block indentation.
  1. Exactly one blank line.
  1. A `Returns:` section itemizing the output description.
- **No Type Redundancy:** Never repeat type annotations or structural shapes inside the text
  descriptions of `Args:`, `Attributes:`, or `Returns:` sections. Let the source code type
  declarations handle type definitions natively.

______________________________________________________________________

## Python coding standards for agents

### Imports

Ruff is configured with `force-single-line = true`. Never write multi-line bracketed imports (for
example, `from x import (a, b)`); put each imported name on its own line.

### Filesystem behavior

Ruff's `PTH` rules are active. Prefer `pathlib.Path` for filesystem construction and traversal, and
write code and tests against platform-independent path behavior whenever possible. Use `os.path`,
native path strings, or other platform-specific behavior only when the contract requires it, and
document why. Mark tests that require a particular platform with `@pytest.mark.skipif()` and a brief
reason; prefer `PurePath` variants or portable fixtures when they can exercise the same contract on
every host.

### Typing

Every function and method argument and return value must be fully annotated (`ANN` rules and Pyright
strict mode). Include `from __future__ import annotations` at the top of every new Python file, as
enforced by isort. Do not use `# type: ignore` or `Any` as shortcuts; fix the type error at its
root. Use `typing.cast()` only when a documented invariant cannot be expressed to Pyright. Prefer an
`isinstance` check, a type guard, a protocol, or a better annotation, and keep any necessary cast
tightly scoped to the boundary it represents. Use built-in generic types in annotations
(`dict[str, int]`, `list[Path]`, `tuple[str, ...]`) rather than deprecated `typing.Dict`,
`typing.List`, and similar aliases. Use `collections.abc` for abstract container interfaces where
appropriate.

______________________________________________________________________

## Validation

Run focused checks while iterating. Before handing off a PR-sized change, run:

```bash
make pre-pr
```

Use the narrower commands when appropriate:

```bash
make pytest
make lint
make format-check
make docs-build
make links-site
make api-snapshot-dev
make coverage
make coverage-tools
```

### Test execution

Run the narrowest check that exercises the change while iterating, then run `make pre-pr` before
handoff for a PR-sized change. Where it helps, parallelize pytest-capable Make targets with
`PYTEST_PAR="-n auto"` (including `pre-pr`, `pytest`, `coverage`, `coverage-tools`, and
`dependency-lower-bounds`). Use the documented Make or Nox targets for the full supported-Python
matrix rather than inventing an ad hoc replacement.

### Change-triggered checks

- Documentation, docstrings, or generated-reference changes: run `make docs-build`.
- Documentation links or link-validation behavior: also run `make links-site`.
- Stable public API changes: run `make api-snapshot-dev`; run `make api-snapshot-update` only for an
  intentional, reviewed baseline change.
- Dependency changes: update `uv.lock` with `make uv-lock` or `make uv-lock-upgrade`, as
  appropriate.

### Coverage and handoff

For behavior-changing product code, run `make coverage` when feasible, followed by
`make coverage-changed`; inspect the changed executable lines and branches. For behavior-changing
repository tooling, run `make coverage-tools` when feasible. Coverage is diagnostic, not a
percentage-driven release gate. Report every relevant check run, its result, and any skipped check
with the reason.

______________________________________________________________________

## Change records and pull requests

- Update `CHANGELOG.md` for user-visible changes and material API, configuration, CI, dependency, or
  contributor-workflow changes.
- Use Conventional Commit titles in the form `<type>[optional scope]: <short summary>` and keep
  titles at or below 72 characters. Use commit bodies for non-trivial rationale, compatibility
  impact, or follow-up context; PR bodies should summarize changes, validation (including relevant
  coverage results or omissions), and related issues.
- In handoff summaries, describe the outcome, list relevant validation, and call out remaining
  external configuration or follow-up work.
