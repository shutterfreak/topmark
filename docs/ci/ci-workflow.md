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

This repository runs CI on pull requests, on pushes to `main`, and on version tags (`v*`). Jobs are split by concern to keep signals crisp and runs fast.

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

  - TopMark header policy via pre-commit:

    ```bash
    pre-commit run topmark-check --all-files
    ```

  - Custom docstring link checks:

    ```bash
    python tools/check_docstring_links.py --stats
    ```

### `docs`

Strict documentation build (same pins as RTD):

- Installs docs toolchain from **pinned** `requirements-docs.txt`

- Builds with:

  ```bash
  mkdocs build --strict
  ```

### `tests`

Full test matrix via `tox` on Python 3.10–3.13:

- Installs dev toolchain from **pinned** `requirements-dev.txt`

- Installs project test extras:

  ```bash
  pip install -c constraints.txt -e .[test]
  ```

- Runs the matching tox env per Python: `py310`, `py311`, `py312`, `py313`

### `api-snapshot`

PR-only, **quick** public API surface check that only runs when `src/**` changed:

- Python 3.13 only

- Runs:

  ```bash
  tox -e py313-api
  ```

### `links`

Site/link hygiene using `lycheeverse/lychee-action` against:

- `docs/`
- top-level `*.md`

## Triggers

- **Pull requests**:
  - Always runs: `changes`, `lint`, `docs`, `tests`, `links`
  - `api-snapshot` runs **only** if `changes.src_changed == 'true'`
- **Push to `main`**:
  - Runs: `lint`, `docs`, `tests`, `links`
- **Push tags `v*`**:
  - Runs CI (useful because the release workflow listens to CI completion)

## Caching & Pins

- Pip caching is enabled via `actions/setup-python`.

- Cache invalidation uses:

  ```yaml
  cache-dependency-path:
    - requirements-*.txt
    - constraints.txt
  ```

- Pin usage:

  - Dev checks/tests install from `requirements-dev.txt`
  - Docs build installs from `requirements-docs.txt`
  - You can export `PIP_CONSTRAINT=constraints.txt` inside jobs or tox envs to force the resolver to honor the constraint pins.

## Docstring checker policy

`tools/check_docstring_links.py` enforces stable links in Python docstrings and warns on undesired patterns. Keep it fast and deterministic so the `lint` job stays snappy.
