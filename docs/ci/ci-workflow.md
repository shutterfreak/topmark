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

This repository runs CI on pull requests and on pushes to `main`. Jobs are split by concern to keep signals crisp and runs fast.

## Jobs

### `changes`

Determines whether source-related paths changed (used to gate quick checks on PRs):

- Uses `dorny/paths-filter`
- Output: `src_changed` (`true`/`false`) when any of:
  - `src/**`
  - `tests/**`
  - `tools/**`

### `lint`

Fast quality gates on Python 3.13:

- Installs the dev toolchain from the **pinned** `requirements-dev.txt`
- Runs:
  - `ruff format --check .`
  - `ruff check .`
  - `pyright`
  - `pre-commit` TopMark header policy: `pre-commit run topmark-check --all-files`
  - custom docstring checks: `python tools/check_docstring_links.py --stats`

### `docs`

Strict documentation build (same pins as RTD):

- Installs docs toolchain from **pinned** `requirements-docs.txt`
- Builds with `mkdocs build --strict`

### `tests`

Full test matrix via `tox` on Python 3.10–3.13:

- Installs dev toolchain from **pinned** `requirements-dev.txt`
- Runs the matching tox env per Python: `py310`, `py311`, `py312`, `py313`

### `api-snapshot`

PR-only, **quick** public API surface check that only runs when `src/**` changed:

- Python 3.13 only
- `tox -e py313-api`

### `links`

Site/link hygiene using `lycheeverse/lychee-action` against:

- `docs/`
- top-level `*.md`

## Triggers

- **Pull requests**:
  - `changes`, `lint`, `docs`, `tests`, `links`
  - `api-snapshot` runs **only** if `changes.src_changed == 'true'`
- **Push to `main`**:
  - `lint`, `docs`, `tests`, `links` (and `api-snapshot` is skipped)

## Caching & Pins

- Python installs: `actions/setup-python` pip cache is enabled.
- Cache invalidation: workflows set `cache-dependency-path` to the lockfiles (`requirements-*.txt`, `constraints.txt`).
- Pin usage:
  - Dev checks/tests install from `requirements-dev.txt`
  - Docs build installs from `requirements-docs.txt`
  - You can also export `PIP_CONSTRAINT=constraints.txt` for steps that create new venvs (e.g., inside tox) to force resolver pinning.

## Docstring checker policy

`tools/check_docstring_links.py` enforces stable links in Python docstrings and warns on undesired patterns (e.g., raw URLs unless whitelisted). Keep it fast and deterministic so the `lint` job stays snappy.
