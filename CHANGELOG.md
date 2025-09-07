<!--
topmark:header:start

  file         : CHANGELOG.md
  file_relpath : CHANGELOG.md
  project      : TopMark
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Change Log

All notable changes to this project will be documented in this file. This project adheres to
[Semantic Versioning](https://semver.org/) and follows a Keep‑a‑Changelog–style structure with the
sections **Added**, **Changed**, **Removed**, and **Fixed**.

## [0.3.0] - 2025-09-07

### Added

- **Stable public API surface** under `topmark.api` and `topmark.registry`.
  - Functions: `check()`, `strip()`, `version()`, `get_filetype_info()`, `get_processor_info()`.
  - Result/metadata types: `Outcome`, `FileResult`, `RunResult`, `FileTypeInfo`, `ProcessorInfo`,
    `WritePolicy`.
  - Structural protocols for plugins: `PublicFileType`, `PublicHeaderProcessor`.
  - `Registry` facade for read‑only discovery of file types, processors, and bindings.
  - Public API tests and snapshot (`tests/api/public_api_snapshot.json`) to guard semver stability.
    (Commits: `9ddd18e`, `ca5e3d7`)
- **Docs overhaul** for API & internals:
  - New `docs/api/public.md` (stable public API) and `docs/api/internals.md` (internals landing).
  - New `docs/gen_api_pages.py` generator for per‑module internals with **breadcrumbs** and
    **first‑line summaries**; mkdocs wiring via `mkdocs-gen-files` & `autorefs`.
  - Local typing stub `typings/mkdocs_gen_files/__init__.pyi` so dev envs don’t need the plugin.
  - Stability policy & semver guardrails added to CONTRIBUTING. (Commits: `bf67c9e`, `41e2543`)
- **CLI improvement**: re‑export `cli` at `topmark.cli` for `from topmark.cli import cli`. (Commit:
  `cb7437f`)
- **New `processors` command** to list registered header processors and their file types (with
  `--long` and `--format default|json|ndjson|markdown`). Shared Click‑free `markdown_table` helper
  for Markdown output. (Commits: `8742a46`, `ab346ed`)

### Changed

- **CLI refactor** to explicit subcommands and unified input planning; migrate away from custom
  `typed_*` helpers to native Click decorators. Includes: `check`, `strip`, `dump-config`,
  `filetypes`, `init-config`, `show-defaults`, `version`; shared plumbing; standardized exit policy
  & summaries. (Commit: `58476b9`)
- **Config layer** now accepts `ArgsLike` mapping (CLI‑free) and no longer requires a Click
  namespace in public API entry points. (Commit: `9ddd18e`)
- **Docs**: split monolithic API page, add generator‑based internals, and fix breadcrumb/link
  regressions; align pre‑commit and mdformat settings with new docs layout. (Commits: `bf67c9e`,
  `41e2543`)
- **Output formatting**: use Click’s built‑in styling; unify Markdown views for `filetypes` &
  `processors`. (Commits: `cf5b789`, `8742a46`)
- **Tooling**: bump pre-commit hooks (ruff v0.12.12, pyright v1.1.405); set project version to
  `0.3.0` in `pyproject.toml` and `CONTRIBUTING.md`.

#### ⚠️ Breaking

- The public API surface is explicitly defined from this release forward and will follow semver.
  Low‑level registries and internals remain **unstable**.
- Implicit default CLI command removed (`topmark --…` → use `topmark check --…`). (Commit:
  `58476b9`)
- Legacy `typed_*` Click helpers removed. (Commit: `58476b9`)

### Fixed

- Correct enum comparisons for `OutputFormat` across commands. (Commit: `c815f72`)
- Markdown rendering branches trigger consistently; format handling unified. (Commit: `8742a46`)
- Docs warnings around internal links/breadcrumbs resolved; configs aligned with `api/public.md`.
  (Commits: `bf67c9e`, `41e2543`)

______________________________________________________________________

## [0.2.1] - 2025-08-27

### Added

- BOM‑aware pipeline behavior: detect BOM in reader and re‑attach in updater on all write paths.\
  (Commit: `27ad903`)
- Newline detection utility centralised; tests and docs expanded accordingly.\
  (Commit: `27ad903`)

### Changed

- Comparer/renderer/updater flow consolidated; recognize formatting‑only drift as change; clarify
  responsibilities via richer docstrings.\
  (Commit: `10bbf72`)
- CLI summary bucket precedence stabilized (e.g., “up‑to‑date”).\
  (Commit: `10bbf72`)

### Fixed

- Strip fast‑path and BOM/newline preservation edge cases via new test coverage (matrix tests,
  inclusive spans).\
  (Commits: `7d8dbb8`, `10bbf72`)

______________________________________________________________________

## [0.2.0] - 2025-08-26

### Added

- New `strip` command to remove TopMark headers (supports dry‑run/apply/summary).\
  (Commits: `c6b9df3`, `8b028d2`)
- Pre‑commit integration docs and hooks; GitHub Actions workflow for PyPI releases.\
  (Commit: `050445a`)

### Changed

- CLI and pipeline improvements: comparer/patcher tweaks; context and processors updated.\
  (Commits: `c6b9df3`, `8b028d2`)

### Fixed

- Initial CLI test suite for `strip`; early bug fixes discovered by tests.\
  (Commit: `8b028d2`)

______________________________________________________________________

## [0.1.1] - 2025-08-25

### Added

- Initial public repository with CLI, pipeline, processors, docs site (MkDocs), tests, and build
  tooling.\
  (Commit: `b3f0169`)
- Trusted publishing workflow for PyPI and automated release notes.\
  (Commits: `6d702b4`, `0785e3c`)

### Changed

- Documentation passes and configuration updates (pre‑commit, pyproject, mkdocs).\
  (Commits: `399ea49`, `204a617`)

### Fixed

- Early CI/publishing configuration issues.\
  (Commit: `0785e3c`)

## [0.1.0] - 2025-08-25

Initial commit.
