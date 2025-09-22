<!--
topmark:header:start

  project      : TopMark
  file         : ci-workflow.md
  file_relpath : docs/ci/ci-workflow.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Continuous Integration (CI)

This repository runs CI for pull requests and pushes to `main`.

## Jobs

### `changes`

Detects whether `src/**`, `tests/**`, or `tools/**` changed using `dorny/paths-filter`.\
Output: `src_changed` (`true`/`false`).

### `checks`

Runs fast quality gates on Python 3.13:

- install `.[dev,docs]` under the pinned `constraints.txt`
- `ruff format --check .`, `ruff check .`, `pyright`, `topmark-check`
- custom docstring link rules (`tools/check_docstring_links.py --stats`)
- `mkdocs build --strict`

### `tests`

Runs the full tox test matrix:

- Python 3.10–3.13
- `tox -e py310|py311|py312|py313` based on the matrix

### `api-snapshot`

PR-only, **fast** API surface check that **only runs** when `src/**` changed:

- Python 3.13
- `tox -e py313-api`

### `links`

Site/link hygiene via `lycheeverse/lychee-action` against `docs/` and top-level `*.md`.

## Triggers

- **Pull requests**: all jobs; `api-snapshot` runs only if `src_changed == true`.
- **Push to `main`**: everything except `changes`/`api-snapshot`.

## Notes

- Python installs are cached via the `actions/setup-python` built-in pip cache.
- Docs builds use `mkdocs --strict` to fail on broken links/anchors.
- The docstring checker enforces reference-style links for internal symbols and bans raw URLs unless whitelisted.
