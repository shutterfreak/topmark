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
- `tests/typecheck/` contains Pyright-only protocol-conformance fixtures; they are not pytest tests
  and do not contribute runtime coverage. See `docs/dev/protocol-contracts.md`.
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

- Inspect the working tree before editing and preserve unrelated user changes.
- Keep changes focused and add or update tests alongside behavioral changes.
- Prefer the existing Make, Nox, and repository tool entry points over ad hoc replacements.
- For ad hoc Python or tool invocation, use `uv run` (e.g., `uv run pytest`, `uv run pyright`) to
  ensure execution inside the project environment. Prefer the documented Make or Nox entry points
  for repository validation.
- When Pyright or Ruff reports an error, fix the root cause (e.g., correct the type annotation or
  refactor) rather than masking it with `# type: ignore` or `# noqa` unless there is a documented,
  unavoidable justification.
- Follow the Ruff and Pyright configuration in `pyproject.toml`.
- Use Google-style docstrings and maintain accurate public exception contracts.
- Keep documentation links relative inside `docs/` unless the documented conventions specifically
  require a hosted URL.
- Update documentation when behavior, configuration, commands, CI, or supported workflows change.

______________________________________________________________________

## Python coding standards for agents

- **Single-Line Imports Only:** Ruff is configured with `force-single-line = true`. Never write
  multi-line bracketed imports (e.g., `from x import (a, b)`). Each imported name must be on its own
  line (`from x import a`, `from x import b`).
- **Pathlib Over OS Path:** Ruff's `PTH` rules are active. Prefer `pathlib.Path` for filesystem path
  construction and traversal; use `os.path` only for a platform-specific operation that `Path` does
  not express clearly, and document the reason.
- **Strict Typing & Annotations:**
  - Every function and method argument and return value must be fully annotated (`ANN` rules +
    Pyright strict mode).
  - Include `from __future__ import annotations` at the top of every new Python file (enforced by
    isort rules).
  - Do not use `# type: ignore` or `Any` as a shortcut; fix type errors at the root.

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

Additional rules:

- Parallelize pytest-capable Make targets when useful by passing `PYTEST_PAR="-n auto"`, for example
  `make pre-pr PYTEST_PAR="-n auto"`, `make pytest PYTEST_PAR="-n auto"`, or
  `make dependency-lower-bounds PYTEST_PAR="-n auto"`.
- Run `make docs-build` for documentation, docstring, or generated-reference changes.
- Run `make links-site` when changing documentation links or link-validation behavior.
- Run `make api-snapshot-dev` when touching the stable public API.
- Run `make api-snapshot-update` only for an intentional, reviewed public API change.
- For behavior-changing product code, run `make coverage` when feasible, then inspect changed
  executable lines and branches with `make coverage-changed`; report the diagnostic result or why it
  was not run. For behavior-changing repository tooling, run `make coverage-tools` when feasible.
  Coverage is a diagnostic, not a percentage-driven release gate.
- After dependency edits, update `uv.lock` with `make uv-lock` or `make uv-lock-upgrade`, as
  appropriate.
- Report checks that were not run and the reason they were skipped.

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
