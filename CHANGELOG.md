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

## [0.3.0] - 2025-09-03

### Added

- New `processors` command to list registered header processors and their file types.
  - Supports `--long` for detailed output including file type descriptions.
  - Supports `--format default|json|ndjson|markdown` for consistent machine‑ and doc‑friendly
    output.\
    (Commits: `8742a46`, `ab346ed`)
- Shared `markdown_table` helper (Click‑free) for beautified Markdown tables with dynamic widths and
  per‑column alignment.\
  (Commit: `8742a46`)

### Changed

- **CLI refactor** to explicit subcommands and unified input planning; migrate away from custom
  `typed_*` helpers to native Click decorators.\
  Includes: `check`, `strip`, `dump-config`, `filetypes`, `init-config`, `show-defaults`, `version`;
  common plumbing; standardized exit policy and summaries.\
  (Commit: `58476b9`)
- Output formatting polish: use Click’s built‑in styling across commands.\
  (Commit: `cf5b789`)
- `filetypes` detailed (`--long`) Markdown view now mirrors fields from default/JSON/NDJSON.\
  (Commit: `8742a46`)
- Documentation overhaul for CLI commands and guides; added new `processors` page; updated
  navigation and README examples.\
  (Commits: `2e26f35`, `ab346ed`)

### Removed

- Implicit default command (`topmark --…`). Use `topmark check --…` instead.\
  (Commit: `58476b9`)
- Legacy `typed_*` Click helpers (`typed_command_of`, `typed_group`, `typed_option`,
  `typed_argument`).\
  (Commit: `58476b9`)

### Fixed

- Correct enum comparisons for `OutputFormat` in `check`, `strip`, and utils.\
  (Commit: `c815f72`)
- Markdown rendering branches in `filetypes` and `processors` trigger consistently; format handling
  unified.\
  (Commit: `8742a46`)
- Typo fix in warning messages: “registered”.

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
