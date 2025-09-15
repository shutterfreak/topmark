<!--
topmark:header:start

  project      : TopMark
  file         : CHANGELOG.md
  file_relpath : CHANGELOG.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Change Log

All notable changes to this project will be documented in this file. This project adheres to
[Semantic Versioning](https://semver.org/) and follows a Keep‑a‑Changelog–style structure with the
sections **Added**, **Changed**, **Removed**, and **Fixed**.

## [0.6.1] - 2025-09-15

### Added

- **Docstring link checker**: new `tools/check_docstring_links.py` to enforce reference-style object links and flag raw URLs in docstrings. Includes accurate line/range reporting, code-region masking, and CLI flags `--stats` and `--ignore-inline-code`.
- **Makefile targets**: `docstring-links`, `links`, `links-src`, `links-all`; centralized `check-lychee` gate.

### Changed

- **MkDocs build**: enable `strict: true` and link validation to fail on broken internal links.
- **Docstrings/x‑refs**: convert internal references to mkdocstrings+autorefs style (e.g., `` [`pkg.mod.Object`][] `` or `[Text][pkg.mod.Object]`) and prefer fully‑qualified names.
- **Docs structure**: normalize mkdocstrings blocks (minor tidy‑ups).

### Fixed

- **README**: correct the “Adding & updating headers with topmark” link to `docs/usage/commands/check.md`.

### Tooling

- **Lychee integration**: adopt Lychee for link checks (local + CI); scoped pre‑commit hooks.
- **Testing**: raise `pytest` minimum to `>=8.0` in the `test` optional dependencies.
- **Refactors**: minor non‑functional cleanups (rename local import alias in filetype registry; small typing improvements).

## [0.6.0] - 2025-09-12

### Added

- **Public API docs**: explain configuration via mappings and why runtime uses an immutable `Config`. (Commit: `d778ace`)
- **API snapshot tooling**:
  - `tools/api_snapshot.py` to generate a curated public API snapshot.
  - Make targets: `public-api-update`, `.public-api-update`, `public-api-check`, `public-api-ensure-clean`.
  - Tox envs `py{310,311,312,313}-api` to run only the snapshot test. (Commit: `a584577`)
- **Docs quality**:
  - Standardize Google-style docstrings; integrate `pydoclint`.
  - Improve MkDocs + mkdocstrings rendering. (Commit: `f649731`)

### Changed

- **Configuration architecture**:
  - Introduce **`MutableConfig`** (internal builder) and **immutable `Config`** (runtime snapshot).
  - Public API continues to accept **`Mapping[str, Any] | None`**; inputs are normalized internally and frozen before execution.
  - Renderer constructs an effective snapshot without mutating inputs. (Commit: `d778ace`)
- **Config resolution (CLI)**:
  - Resolution order now explicit and consistent:
    1. packaged defaults → 2) discovered project config in CWD (`pyproject.toml` `[tool.topmark]`, else `topmark.toml`) **unless** `--no-config` or explicit `--config` → 3) `--config` files (in order) → 4) CLI overrides. (Commit: `d778ace`)
- **Header field ordering**:
  - `topmark check` enforces the configured field order consistently. (Commit: `d778ace`)
- **Typing/import hygiene**:
  - Adopt postponed annotations and move type-only imports under `TYPE_CHECKING`.
  - Narrow typing imports; reduce unnecessary list materialization in CLI plumbing.
  - Faster imports; fewer cycles. (Commit: `adc35f9`)

### Fixed

- CLI and pipeline now reflect header order deterministically (no “up-to-date” false negatives when order differed). (Commit: `d778ace`)
- Type-checking and lint issues (casts, variable redefinitions, analyzer false positives) resolved in CLI helpers and resolver paths. (Commits: `d778ace`, `adc35f9`)

### Docs

- Add **“Configuration via mappings (immutable at runtime)”** section to the public API docs and mirror a concise note in the `topmark.api` module docstring. (Commit: `d778ace`)
- Normalize docstrings across the codebase; remove Sphinx roles in favor of Markdown-friendly mkdocstrings. (Commit: `f649731`)

### Tooling

- Add `pydoclint` to dev toolchain; wire into Makefile and pre-commit.
- Reorder pre-commit hooks for faster feedback.
- Snapshot workflow integrated into Makefile and CI-friendly checks. (Commits: `f649731`, `a584577`)

### Chore

- Repository-wide header reformat to the new field order (no functional changes). (Commit: `bcac2ed`)

#### Notes

- **No public API surface changes**: `topmark.api.check/strip` signatures unchanged.
- `MutableConfig` is **internal** (not part of the stable API); public callers should pass a mapping or a frozen `Config`.

## [0.5.1] - 2025-09-09

### Fixed

- **Python 3.10/3.11 compatibility**: replace multiline f‑strings in CLI output code paths
  (not supported before Python 3.12) with concatenation/temporary variables.
  Affected commands:
  - `filetypes`: numbered list rendering and detail lines (description/content matcher)
  - `processors`: processor header lines and per‑filetype detail lines

### Tooling

- Bump project version to `0.5.1` in `pyproject.toml`.
- Update local pre‑commit hook to use TopMark **v0.5.0**.

## [0.5.0] - 2025-09-09

### Added

- **Honest write statuses** across the pipeline:
  - Dry‑run ⇒ `WriteStatus.PREVIEWED`
  - Apply (`--apply`) ⇒ terminal statuses (`INSERTED`, `REPLACED`, `REMOVED`)
- **Apply intent plumbing** end‑to‑end:
  - `Config.apply_changes` (tri‑state) consumed via `apply_cli_args()` and respected in updater
  - CLI and public API forward **apply** to the pipeline

### Changed

- **CLI & console output**
  - Decoupled program‑output verbosity from internal logging; all user output routed through `ConsoleLike`
  - Banners/extra guidance are gated by verbosity (quiet by default; add `-v` for more detail)
  - `filetypes` and `processors` now render numbered lists with right‑aligned indices
  - `dump-config` / `init-config`: emit **plain TOML** by default; BEGIN/END markers appear at higher verbosity
- **Public API (behavioral)**
  - Apply vs preview now consistently reflected in per‑file results (`PREVIEWED` vs terminal write statuses)

### Fixed

- **Pre‑commit hooks**: remove redundant `--quiet` (default output is already terse) and fix its placement.

### Docs

- Refresh CLI docs:
  - Explicit subcommands in examples; stdin examples use `topmark check - …`
  - Clarify dry‑run vs apply summary text (`- previewed` vs `- inserted`/`- replaced`/`- removed`)
  - Add “Numbered output & verbosity” notes to `filetypes` / `processors`
  - Add `version` command page; tidy headings and separators

#### ⚠️ Breaking (pre‑1.0)

- Dry‑run summaries now end with **`- previewed`** instead of terminal verbs.\
  Update any scripts/tests parsing human summaries that previously matched
  `- inserted` / `- removed` / `- replaced` during dry‑run.
- Human‑readable CLI output may differ (verbosity‑gated banners and numbered lists).

## [0.4.0] - 2025-09-08

### Added

- **Structured diagnostics with severities** across the pipeline (`info`, `warning`, `error`).
  - New internal `DiagnosticLevel` enum and `Diagnostic` dataclass.
  - New public JSON-friendly shape `PublicDiagnostic` with `level` and `message` fields.
  - Aggregate counts exposed from the public API:
    - `RunResult.diagnostic_totals` (for the returned **view**) and
    - `RunResult.diagnostic_totals_all` (for the **entire run**, pre filter).
- **Program-output verbosity**:
  - `Config.verbosity_level` is now **tri-state**: `None` (inherit), `0` (terse), `1` (verbose).
  - Per-file verbose diagnostic lines in summaries are shown when `verbosity_level >= 1`.
- **Console abstraction** to cleanly separate CLI user output from internal logging.
  - Console is initialized in the CLI and available via `ctx.obj["console"]`.

### Changed

- **Public API**: `diagnostics` in `RunResult` now returns a mapping
  `dict[str, list[PublicDiagnostic]]` instead of `dict[str, list[str]]`.
- **Summaries**: `ProcessingContext.format_summary()` now aligns with pipeline outcomes and
  appends compact triage (e.g., `1 error, 2 warnings`) plus hints (`previewed`, `diff`).
- **Verbosity handling**: CLI `-v/--verbose` and `-q/--quiet` feed a program-output verbosity
  level separately from the logger level; per-command logger overrides were removed.
- **Config.merge_with()**: `verbosity_level` now honors **override semantics** (other wins),
  and supports tri-state inheritance.
- **API surface**: `PublicDiagnostic` re-exported from `topmark.api` and included in `__all__`.

### Fixed

- Reader now surfaces an explicit diagnostic for empty files.
- Minor wording/formatting improvements in `classify_outcome()` and summary output.
- Import order cleanup in `pipelines.py`.

### Docs

- Expanded inline docstrings for diagnostics, public types, and verbosity semantics.

#### ⚠️ Breaking (pre‑1.0)

- `RunResult.diagnostics` type changed to a structured public form. Integrations consuming
  plain strings should switch to `d["message"]` and may use `d["level"]` for triage.
- New aggregate fields (`diagnostic_totals`, `diagnostic_totals_all`) are added alongside
  `diagnostics`.

## [0.3.2] - 2025-09-07

### Fixed

- **Pre-commit hooks**: update TopMark hooks to use the explicit `check` subcommand
  (`topmark check …`) instead of the removed implicit default command. This restores correct
  behavior for `topmark-check` and `topmark-apply` hooks.

### Docs

- Add **API Stability** page and wire it into the MkDocs navigation (`Development → API Stability`).
- Add a stability note/link to `docs/api/public.md` referencing the snapshot policy.

### Tooling

- Bump project version to `0.3.2` in `pyproject.toml`.

## [0.3.1] - 2025-09-07

### Fixed

- **Snapshot tests**: stabilize public API snapshot across Python 3.10–3.13 by normalizing
  constructor signatures in tests (`<enum>` for Enum subclasses, `<class>` for other classes) while
  retaining real signatures for callables. Updated baseline `tests/api/public_api_snapshot.json`
  accordingly and refreshed the REPL snippet in the test docstring to generate a
  cross‑version‑stable snapshot.

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
