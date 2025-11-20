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

## [0.10.1] – 2025-11-20

This patch release republishes the intended `0.10.0` release with two commits that were accidentally omitted from the PyPI artifact.\
There are **no functional code changes** relative to `0.10.0`; this release only corrects packaging and metadata.

### Changed

- **Tooling & dependency maintenance**

  - Updated `.pre-commit-config.yaml` with the latest versions of:
    - `mdformat` 1.0.0 (migrated to `mdformat-gfm`)
    - `ruff-pre-commit` v0.14.x
    - `pydoclint` 0.8.x
    - `pyright-python` v1.1.407
  - Tightened dependency ranges in `pyproject.toml` and regenerated `requirements*.txt` via pip-tools.

- **Metadata**

  - Added the `0.10.0` CHANGELOG entry that was missing in the PyPI package.
  - Set the project version to `0.10.0` in `pyproject.toml` for the corrected build.

### Notes

This release contains **only packaging, metadata, and dependency housekeeping**.\
All functionality, schemas, and breaking changes remain exactly as described in **0.10.0**.

## [0.10.0] – 2025-11-20

This release introduces **major pipeline and CLI changes**, a full **machine-output schema redesign**, a refactored **ProcessingContext**, and multiple BREAKING CHANGES. It also includes substantial internal cleanup, dependency updates, and correctness fixes.

______________________________________________________________________

### ⚠️ BREAKING CHANGES

#### Machine Output (JSON / NDJSON)

- **Completely redesigned schema**:
  - All records include a `kind` discriminator (`config`, `config_diagnostics`, `result`, `summary`).
  - All records include a top-level `meta` block (version, intent, timestamps).
  - File-level results now use a stable, explicit envelope (`file`, `statuses`, `hints`, `diagnostic_counts`, `outcome`).
  - NDJSON encoding is now strictly one-record-per-line with unified keys.
- **Old JSON/NDJSON formats from \<0.10.0 are no longer emitted.**
- Downstream tools **must** update their parsers.

#### CLI / Presentation Rendering

- CLI output formatting has been fully rewritten:
  - Bucketing semantics changed (mapping to new axes + unified policy signals).
  - Summary footer replaced with new consistent reporting structure.
  - Changed/unchanged/would-change groupings now computed via the new comparison axis.
  - Hints are now grouped and severity-ordered; rendering is verbosity-dependent.
- Legacy formatting and legacy summary behavior have been removed.

#### Pipeline Architecture

- `ProcessingContext` split into:
  - `pipeline.context.model` (state + orchestration),
  - `pipeline.context.policy` (pure policy + feasibility),
  - `pipeline.context.status` (all axis statuses).
- Legacy modules (`pipeline/context.py`, `pipeline/contracts.py`, etc.) removed.
- Steps updated to use new context accessors and policy helpers.
- Any consumer importing internal pipeline modules by path must update imports.

#### Legacy CLI Commands

- Several deprecated commands were **removed entirely**:
  - Old compatibility shims for `topmark header …`
  - Legacy updater/stripper debug modes.
- These commands now fail fast with a clear error.

______________________________________________________________________

### Highlights

- Clean separation of pipeline responsibilities (context, policy, status).
- Unified machine-readable output schema supporting stable integrations.
- Significantly clearer CLI output with accurate bucket, hint, and summary logic.
- Simplified type system with uniform abstract collections (`collections.abc`) and Ruff `UP`/`TC` enforcement.
- Full modernization of imports, dependency ranges, and development tooling.
- Large suite of correctness fixes across header bounds, scanner, renderer, patcher, and writer.

______________________________________________________________________

### Added

- New `pipeline/context/` package with:
  - `model.py` (ProcessingContext core),
  - `policy.py` (feasibility, effective policy checks, intent validation),
  - `status.py` (HeaderProcessingStatus + axis enums).
- New machine-output builder (`cli_shared.machine_output`) as the single source of truth.
- New structured summary renderer (`topmark.api.view.format_summary`).
- Linting policy section in `CONTRIBUTING.md`.
- Support for GitHub-Flavored Markdown tables via `mdformat-gfm`.

______________________________________________________________________

### Changed

- **ProcessingContext**

  - No longer contains embedded policy decisions.
  - Explicit release interfaces for summary, machine-output, and updated lines.
  - Stronger invariants, better separation of concerns.

- **Pipeline Steps**

  - Updated to use new context fields and pure policy helpers.
  - Comparison, plan, and patch steps rewritten for correctness and stability.

- **Rendering**

  - Summary: fully redesigned (cluster ordering, hint ranking, status grouping).
  - Bucketing logic: aligned with new axes and comparison semantics.
  - Writer output harmonized with patch/plan steps.

- **Machine Output**

  - Unified schema with predictable envelopes.
  - NDJSON deterministic ordering.
  - Config dump and diagnostics included in machine mode.

- **Imports & Typing**

  - `collections.abc` now used consistently.
  - Ruff `UP` and `TC` rules enabled; repository-wide cleanup applied.

- **Dependencies & Tooling**

  - Dependency ranges tightened in `pyproject.toml`.
  - All requirements files regenerated via pip-tools.
  - Switched from `mdformat-tables` → `mdformat-gfm`.

______________________________________________________________________

### Removed

- `ReasonHint` (unused).
- Legacy updater header code paths.
- Deprecated CLI commands and code paths for pre-0.9 behaviors.
- Legacy summary and bucket rendering pipeline.

______________________________________________________________________

### Fixed

- Correct final newline + BOM + shebang interactions.
- Accurate indentation handling for Markdown/HTML/XML processors.
- Numerous header bound edge cases (multi-header, malformed, block comment variants).
- Writer stability in dry-run and apply modes.
- Accurate tracking of “would change” vs “changed” under mixed policy conditions.
- Corrected normalization for multi-line headers with mixed whitespace.
- Better FileType detection for HTML/Markdown block-comments.

______________________________________________________________________

### Notes

`topmark.api` remains *public and stable*, but all **machine-readable formats** and **internal pipeline interfaces** changed and require downstream updates. Integrators consuming NDJSON/JSON must migrate to the new envelopes and keys.

## [0.9.1] - 2025-10-07

### Highlights

- **Python 3.14 support (prerelease)** — test matrix, classifiers, and tooling updated for 3.10–3.14.
- **Tox-first developer workflow** — Makefile simplified to delegate heavy lifting to tox; consistent local/CI behavior.
- **Property-based hardening** — Hypothesis harness added for idempotence and edge-case discovery.
- **Robust idempotence & XML/HTML guardrails** — Safer insertion rules and whitespace/newline preservation.

### Added

- **Testing & quality**
  - Hypothesis-based **property tests** for insert→strip→insert idempotence and edge cases across common file types.
  - CI **pre-commit** job to run fast hooks on every PR/push (heavy/duplicated hooks handled elsewhere).
- **Python versions**
  - CI matrix extended to **3.14** (rc/dev as needed) with `allow-prereleases: true`.

### Changed

- **Developer workflow**
  - **Makefile overhaul**: now a thin wrapper that delegates to tox envs:
    - Core targets: `verify`, `test`, `pytest`, `property-test`, `lint`, `lint-fixall`, `format`, `format-check`, `docs-build`, `docs-serve`, `api-snapshot*`.
    - Lock management: `lock-compile-*`, `lock-dry-run-*`, `lock-upgrade-*`.
    - Parallel runners passthroughs: `PYTEST_PAR`, `TOX_PAR`.
  - **tox.ini refactor**:
    - Clear env families for typecheck, lint, docs, link checks, property tests, API checks.
    - Less duplication; per-env Pyright via `--pythonversion`.
- **Type checking & compatibility**
  - Keep editor Pyright baseline at `pythonVersion = "3.10"`; run version-specific checks via tox.
  - Python 3.14 compatibility for `Traversable` import via `importlib.resources.abc`.
- **XML/HTML insertion policy**
  - Assign XML insert checker to HTML where appropriate; add reflow/idempotence safety checks.

### Fixed

- **Idempotence & formatting drift**
  - Preserve user whitespace; avoid collapsing whitespace-only lines (e.g., `" \n"` vs `"\n"`).
  - Normalize handling of the **single blank line** after headers (owned newline only).
  - Respect **BOM** and trailing blanks; collapse only file-style blanks, not arbitrary whitespace.
  - Stripper/Updater: honor content status; avoid unintended rewrites.
- **Insertion safety**
  - Skip reflow-unsafe XML/HTML cases (e.g., single-line prolog/body, NEL/LS/PS scenarios).
  - Mixed line endings are skipped by the reader to avoid non-idempotent outcomes.

### CI / Tooling

- **CI (`ci.yml`)**
  - **Tox-first** for lint (`format-check`, `lint`, `docstring-links`), docs (`docs`), tests (`py310…py314`), and API snapshot (`py313-api`).
  - Add caching for **pip** and **.tox** across jobs; add `actions/checkout@v4` before cache globbing.
  - New **pre-commit** job; skip heavy/duplicated hooks in that job (`lychee-*`, `pyright`, `docstring-ref-links`) since they run in other jobs.
- **Release (`release.yml`)**
  - Build docs via **tox**; add pip/.tox caching to **build-docs** and **publish-package**.
- **Docs**
  - Refresh **CONTRIBUTING.md**, **INSTALL.md**, **README.md**, and **docs/dev/api-stability.md** to match the tox/Makefile workflow.
  - New CI/release workflow docs; fix broken links to workflow YAMLs.

### Developer notes

- We’ve moved from pure **venv** workflows (`.venv`, `.rtd`) to a **tox-based** model.
  - Please **delete** any old `.venv` and `.rtd` directories.

  - If you want IDE/Pyright import resolution, recreate only the **optional** editor venv:

    ```bash
    make venv && make venv-sync-dev
    ```

  - Use `make verify`, `make test`, `make pytest [PYTEST_PAR="-n auto"]`, `make docs-*`, `make api-snapshot*`, and the `lock-*` targets for daily work.

**Breaking changes**: *None.*\
Public API remains stable; changes focus on tooling, CI reliability, and correctness fixes.

## [0.9.0] - 2025-10-06

### Highlights

- **Configuration resolution finalized** — TopMark now fully supports layered config discovery with deterministic merge precedence, explicit anchor semantics, and path-aware pattern resolution.
- **Docs & MkDocs rebuild** — Documentation migrated to a snippet-driven architecture with reusable callouts, dynamic version injection, and a modernized MkDocs toolchain.
- **CLI alignment fix** — The `--align-fields` flag is now tri-state, preserving `pyproject.toml` defaults when the flag is omitted.
- **Public API parity** — The Python API now mirrors CLI behavior, respecting discovery, precedence, and formatting options such as `align_fields`.
- **Note:** Config discovery and precedence are now finalized; projects that relied on implicit or CWD-only behavior may see changes in which configuration takes effect.\
  See [**Configuration → Discovery & Precedence**](docs/configuration/discovery.md).

### Added

- **Configuration system**
  - Complete implementation of **layered discovery**:
    - Precedence: defaults → user → project chain (`root → cwd`; per-dir: `pyproject.toml` → `topmark.toml`) → `--config` → CLI.
    - **Discovery anchor** = first input path (or its parent if file) → falls back to CWD.
    - **`root = true`** stops traversal; ensures predictable isolation.
  - Added `PatternSource` abstraction for tracking pattern bases.
  - Added `MutableConfig.load_merged()` and detailed docstrings for all discovery steps.
  - New test suite `tests/config/test_config_resolution.py` for full coverage of anchors, globs, and precedence.
- **Header rendering**
  - Conditional field alignment via `config.align_fields` in `HeaderProcessor.render_header_lines()`.
- **API**
  - Public API functions use the authoritative discovery and merge logic.
  - Added `tests/api/test_api_discovery_parity.py` to guarantee CLI/API parity.
- **MkDocs & docs**
  - Introduced snippet-based reusable callouts (`> [!NOTE]`) rendered through a custom **simple hook**.
  - Added `docs/hooks.py` to convert callouts and inject `%%TOPMARK_VERSION%%` dynamically.
  - Added `docs/_snippets/config-resolution.md` for consistent “How config is resolved” sections.
  - Automated generation of API reference pages for `topmark.api` and `topmark.registry`.
  - Updated `mkdocs.yml` plugin chain (include-markdown, simple-hooks, md_in_html, gen-files).
  - Added dynamic version display in docs (via `pre_build` hook).

### Changed

- **CLI**
  - `--align-fields` is now **tri-state** (`True`, `False`, `None`)—when omitted, TOML defaults are respected.
  - `topmark dump-config` and all CLI flows now reflect the effective merged configuration.
- **Processor pipeline**
  - Field alignment respects `config.align_fields`.
  - Improved XML and JSON insertion gate logic to prevent unsafe mutations.
- **Documentation build**
  - Rebuilt MkDocs toolchain to use:
    - `mkdocs-include-markdown-plugin`
    - `mkdocs-simple-hooks`
    - `mkdocstrings[python]`
    - `mkdocs-gen-files`
  - Moved mdformat configuration from `.mdformat.yml` → `[tool.mdformat]` in `pyproject.toml`.
  - Updated pre-commit and CI workflows to install `[docs]` extras automatically.
- **Formatting**
  - Reflowed all documentation via `mdformat` (100-column wrap, normalized lists and spacing).

### Fixed

- **Config precedence bug** — Same-directory order (`pyproject.toml` before `topmark.toml`) was previously inverted; now fixed via per-directory grouping.
- **CLI override bug** — `--align-fields` no longer forces `false` when omitted; correctly inherits TOML default.
- **Header alignment** — Processors no longer align fields when `align_fields = false`.
- **Docs build** — Resolved missing MkDocs plugin errors in CI (`include-markdown` and `simple-hooks`).
- **Lychee false positives** — Updated snippet links and exclusion list to prevent link-checker failures.
- **Version token substitution** — The documentation now correctly substitutes `%%TOPMARK_VERSION%%` via pre-build hook.

### Docs / Tooling

- Overhauled `pyproject.toml` `[project.optional-dependencies].docs` section to include all MkDocs plugins.
- Added `requirements-docs.txt` synced with `pyproject.toml` extras for CI.
- CI and release workflows (`ci.yml`, `release.yml`) now install docs extras (`-e .[docs]`) with constraints.
- Bumped doc dependencies: `mkdocs>=1.6.0`, `mkdocs-material>=9.5.19`, `pymdown-extensions>=10.16`.
- Removed obsolete `.mdformat.yml` and outdated constraints for `backrefs` and `markdown-it-py`.

**Breaking changes**: *None* (pre-1.0).\
All changes are backward-compatible with v0.8.x configurations and APIs.

______________________________________________________________________

✅ **Summary:**\
TopMark 0.9.0 consolidates its configuration system, aligns CLI and API behavior, and modernizes the documentation pipeline. Config resolution, discovery anchors, and formatting flags now work predictably across CLI, API, and generated docs.

## [0.8.1] - 2025-09-26

### Highlights

- **XML re-apply fix**: prevent double-wrapped `<!-- … -->` blocks by anchoring bounds via character
  offset for XML/HTML processors.

### Added

- **Developer validation (opt-in)**: set `TOPMARK_VALIDATE=1` to validate:
  - Processor ↔ FileType registry integrity.
  - XML-like processors use the char-offset strategy (`NO_LINE_ANCHOR` for line index).
- **Docs**:
  - Placement strategies (line-based vs char-offset) documented in `base.py` / `xml.py`.
  - New page `docs/ci/dev-validation.md`; CONTRIBUTING updated.

### Changed

- **Processor refactor**:
  - Introduce mixins: `LineCommentMixin`, `BlockCommentMixin`, `XmlPositionalMixin`.
  - Add `compute_insertion_anchor()` façade and route updater through it.
  - Tighten typing (`Final[int]` for `NO_LINE_ANCHOR`; stricter annotations) and micro-perf (cache
    compiled encoding regex).
- **File types**:
  - Instances module made lazy, plugin-aware, and type-safe; detectors split out (JSONC).

### Fixed

- **XML idempotency**: re-apply no longer nests comment fences.
- **Type checking & mypy**: generator return, entrypoint discovery, and strict typing cleanups.

### CI / Tooling

- **New CI job**: “Dev validation” runs only tests marked `dev_validation` with
  `TOPMARK_VALIDATE=1`.
- **Pre-commit**: bump `ruff-pre-commit` to `v0.13.2`.

**Breaking changes**: *None.*

## [0.8.0] - 2025-09-24

### Highlights

- **New C-style block header support**: introduce `CBlockHeaderProcessor` and register it for **CSS,
  SCSS, Less, Stylus, SQL, and Solidity**.
- **Python stubs**: `.pyi` now use `PoundHeaderProcessor` (`#`-style), with sensible defaults (no
  shebang).

### Added

- **Processors**
  - `CBlockHeaderProcessor` (C-style `/* … */` with per-line `*`) including tolerant directive
    detection (accepts `* topmark:…` or bare `topmark:…`).
  - File type registrations: `css`, `scss`, `less`, `stylus`, `sql`, `solidity`.
- **File types**
  - `python-stub` (`.pyi`) bound to `PoundHeaderProcessor` (shebang disabled; ensure blank after
    header).
- **Tests**
  - Comprehensive `test_cblock.py` suite: insertion (top and not-at-top), tolerant detection,
    idempotency, CRLF preservation, strip (auto/explicit span), and parametric checks across
    registered extensions.

### Changed

- **Typing hardening (non-functional)**
  - Widespread strict typing across `pipeline/`, `cli/` & `cli_shared/`, remaining `src/` modules,
    and `tools/`:
    - Adopt postponed annotations; move type-only imports under `TYPE_CHECKING`.
    - Introduce `TopmarkLogger` annotations; add precise return/locals typing.
    - Minor import and hygiene cleanups for Pyright strict mode.

### Fixed

- **CLI `processors` command**
  - Treat `filetypes` as dicts in `--long` + Markdown/default renderers to avoid `AttributeError`
    when running\
    `topmark processors --format markdown --long`.
- **Typing**
  - Resolve a redefinition error from an incorrectly placed annotation in types code.

### Docs

- **README.md**: mention block (`/* … */`) alongside line (`#`, `//`) comment styles; add a CSS
  example.
- **docs/usage/filetypes.md**: expand processor table with modules and registered file types; add
  `CBlockHeaderProcessor`.

### Chore

- Add standard TopMark headers to files in `typings/`.
- Dev tooling: keep pre-commit/hooks in sync (see commit history for exact bumps).

**Breaking changes**: *None.*

## [0.7.0] - 2025-09-23

### Highlights

- **Version CLI overhaul**: `topmark version` now defaults to **PEP 440** output and supports
  multiple formats via `--format {pep440,semver,json,markdown}` (alias: `--semver`).
- **Release hardening**: Fully revamped GitHub Actions release flow with strict gates (version/tag
  match, artifact checks, **docs must build**, TestPyPI for prereleases, PyPI for finals).

### Added

- **CLI – `version` command**
  - `--semver` option to render a **SemVer** view while keeping **PEP 440** as the default.
  - `--format json|markdown|pep440|semver` with standardized outputs.
  - `topmark.utils.version.pep440_to_semver()` with graceful fallback.
- **Tests**
  - Expanded/parameterized tests for `version` across text/JSON/Markdown (PEP 440 vs SemVer).

### Changed

- **CLI output (breaking schemas; see “Breaking” below)**
  - **JSON** schema is now:

    ```json
    {"version": "<str>", "format": "pep440|semver"}
    ```

  - **Markdown** now includes the format label:

    ```
    **TopMark version (pep440|semver): <version>**
    ```

  - **Plain text** remains just the version string (script-friendly).
- **CI (`.github/workflows/ci.yml`)**
  - Triggers on PRs, pushes to `main`, and **tags `v*`** (to feed the release workflow).
  - PR path filters widened (e.g., `tests/**`, `tools/**`).
- **Release (`.github/workflows/release.yml`)**
  - **Dual trigger**: tag **push** and **workflow_run** (proceeds only after green CI).
  - New **`details`** job: normalizes tag, derives PEP 440/SemVer, decides **channel** (TestPyPI for
    `-rc/-a/-b`, PyPI for finals), and verifies `pyproject.toml` matches the tag.
  - Improved **concurrency** to prevent overlapping runs for the same ref.
  - **Publish** job:
    - Requires green CI (via `workflow_run`) or allows direct tag push.
    - `environment` auto-selects **TestPyPI** vs **PyPI**.
    - Checks that the target version does **not** already exist.
    - Builds artifacts and **verifies filenames** embed the exact PEP 440 version.
    - **Finals only**: guard that version is newer than latest final on PyPI.
    - Publishes via trusted publishing (TestPyPI w/ `skip-existing: true` for prereleases; PyPI for
      finals).
  - Creates a **GitHub Release** for finals using `details` outputs.

### Fixed

- N/A (no user-visible fixes included in this release; tests/docs/tooling updates only).

### Docs

- New & updated workflow docs:
  - `docs/ci/release-workflow.md` (RC vs final, gates, publishing).
  - `CONTRIBUTING.md` (CI expectations, local checks).
- `README.md` and `docs/index.md` examples updated for the new `version` outputs.

### Tooling / Reproducibility

- Adopt pinned lockfiles (`requirements.txt`, `requirements-dev.txt`, `requirements-docs.txt`) and
  `constraints.txt`.
- Cache keyed on lockfiles; consistent `python -m pip` usage.

### Removed

- Duplicate “Build docs (strict)” step from the `lint` job.
- Stray `topmark.toml` at repo root.

### Chore

- Pre-commit: bump `topmark-check` hook to v0.6.2.
- Minor `tox.ini` whitespace tidy-ups.

### Breaking (pre-1.0)

- **JSON** schema changed from `{"topmark_version": "<str>"}` to
  `{"version": "<str>", "format": "pep440|semver"}`.
- **Markdown** now explicitly includes the format label:\
  `**TopMark version (pep440|semver): <version>**`.\
  Update any consumers/parsers that relied on the previous key or phrasing.

#### Pre-releases

- `0.7.0-rc1` and `0.7.0-rc2` were published to **TestPyPI** for validation; their contents are
  fully included in this final release.

**Developer notes**

- For RCs: keep `pyproject.toml` at `0.7.0rcN` and tag `v0.7.0-rcN` to publish to TestPyPI.
- For GA: bump to `0.7.0`, tag `v0.7.0`, and the workflow publishes to PyPI after docs/tests gates.

## [0.6.2] - 2025-09-15

### Fixed

- **Docs build**: resolve Griffe parsing error by normalizing a parameter docstring format (remove
  stray space before colon) for `skip_compliant` in `topmark.api.check()` (file:
  `src/topmark/api/__init__.py`). This unblocks MkDocs/ReadTheDocs builds. No functional code
  changes.

## [0.6.1] - 2025-09-15

### Added

- **Docstring link checker**: new `tools/check_docstring_links.py` to enforce reference-style object
  links and flag raw URLs in docstrings. Includes accurate line/range reporting, code-region
  masking, and CLI flags `--stats` and `--ignore-inline-code`.
- **Makefile targets**: `docstring-links`, `links`, `links-src`, `links-all`; centralized
  `check-lychee` gate.

### Changed

- **MkDocs build**: enable `strict: true` and link validation to fail on broken internal links.
- **Docstrings/x‑refs**: convert internal references to mkdocstrings+autorefs style (e.g.,
  `` [`pkg.mod.Object`][] `` or `[Text][pkg.mod.Object]`) and prefer fully‑qualified names.
- **Docs structure**: normalize mkdocstrings blocks (minor tidy‑ups).

### Fixed

- **README**: correct the “Adding & updating headers with topmark” link to
  `docs/usage/commands/check.md`.

### Tooling

- **Lychee integration**: adopt Lychee for link checks (local + CI); scoped pre‑commit hooks.
- **Testing**: raise `pytest` minimum to `>=8.0` in the `test` optional dependencies.
- **Refactors**: minor non‑functional cleanups (rename local import alias in filetype registry;
  small typing improvements).

## [0.6.0] - 2025-09-12

### Added

- **Public API docs**: explain configuration via mappings and why runtime uses an immutable
  `Config`. (Commit: `d778ace`)
- **API snapshot tooling**:
  - `tools/api_snapshot.py` to generate a curated public API snapshot.
  - Make targets: `public-api-update`, `.public-api-update`, `public-api-check`,
    `public-api-ensure-clean`.
  - Tox envs `py{310,311,312,313}-api` to run only the snapshot test. (Commit: `a584577`)
- **Docs quality**:
  - Standardize Google-style docstrings; integrate `pydoclint`.
  - Improve MkDocs + mkdocstrings rendering. (Commit: `f649731`)

### Changed

- **Configuration architecture**:
  - Introduce **`MutableConfig`** (internal builder) and **immutable `Config`** (runtime snapshot).
  - Public API continues to accept **`Mapping[str, Any] | None`**; inputs are normalized internally
    and frozen before execution.
  - Renderer constructs an effective snapshot without mutating inputs. (Commit: `d778ace`)
- **Config resolution (CLI)**:
  - Resolution order now explicit and consistent:
    1. packaged defaults → 2) discovered project config in CWD (`pyproject.toml` `[tool.topmark]`,
       else `topmark.toml`) **unless** `--no-config` or explicit `--config` → 3) `--config` files
       (in order) → 4) CLI overrides. (Commit: `d778ace`)
- **Header field ordering**:
  - `topmark check` enforces the configured field order consistently. (Commit: `d778ace`)
- **Typing/import hygiene**:
  - Adopt postponed annotations and move type-only imports under `TYPE_CHECKING`.
  - Narrow typing imports; reduce unnecessary list materialization in CLI plumbing.
  - Faster imports; fewer cycles. (Commit: `adc35f9`)

### Fixed

- CLI and pipeline now reflect header order deterministically (no “up-to-date” false negatives when
  order differed). (Commit: `d778ace`)
- Type-checking and lint issues (casts, variable redefinitions, analyzer false positives) resolved
  in CLI helpers and resolver paths. (Commits: `d778ace`, `adc35f9`)

### Docs

- Add **“Configuration via mappings (immutable at runtime)”** section to the public API docs and
  mirror a concise note in the `topmark.api` module docstring. (Commit: `d778ace`)
- Normalize docstrings across the codebase; remove Sphinx roles in favor of Markdown-friendly
  mkdocstrings. (Commit: `f649731`)

### Tooling

- Add `pydoclint` to dev toolchain; wire into Makefile and pre-commit.
- Reorder pre-commit hooks for faster feedback.
- Snapshot workflow integrated into Makefile and CI-friendly checks. (Commits: `f649731`, `a584577`)

### Chore

- Repository-wide header reformat to the new field order (no functional changes). (Commit:
  `bcac2ed`)

#### Notes

- **No public API surface changes**: `topmark.api.check/strip` signatures unchanged.
- `MutableConfig` is **internal** (not part of the stable API); public callers should pass a mapping
  or a frozen `Config`.

## [0.5.1] - 2025-09-09

### Fixed

- **Python 3.10/3.11 compatibility**: replace multiline f‑strings in CLI output code paths (not
  supported before Python 3.12) with concatenation/temporary variables. Affected commands:
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
  - Decoupled program‑output verbosity from internal logging; all user output routed through
    `ConsoleLike`
  - Banners/extra guidance are gated by verbosity (quiet by default; add `-v` for more detail)
  - `filetypes` and `processors` now render numbered lists with right‑aligned indices
  - `dump-config` / `init-config`: emit **plain TOML** by default; BEGIN/END markers appear at
    higher verbosity
- **Public API (behavioral)**
  - Apply vs preview now consistently reflected in per‑file results (`PREVIEWED` vs terminal write
    statuses)

### Fixed

- **Pre‑commit hooks**: remove redundant `--quiet` (default output is already terse) and fix its
  placement.

### Docs

- Refresh CLI docs:
  - Explicit subcommands in examples; stdin examples use `topmark check - …`
  - Clarify dry‑run vs apply summary text (`- previewed` vs `- inserted`/`- replaced`/`- removed`)
  - Add “Numbered output & verbosity” notes to `filetypes` / `processors`
  - Add `version` command page; tidy headings and separators

#### ⚠️ Breaking (pre‑1.0)

- Dry‑run summaries now end with **`- previewed`** instead of terminal verbs.\
  Update any scripts/tests parsing human summaries that previously matched `- inserted` /
  `- removed` / `- replaced` during dry‑run.
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
- **Summaries**: `ProcessingContext.format_summary()` now aligns with pipeline outcomes and appends
  compact triage (e.g., `1 error, 2 warnings`) plus hints (`previewed`, `diff`).
- **Verbosity handling**: CLI `-v/--verbose` and `-q/--quiet` feed a program-output verbosity level
  separately from the logger level; per-command logger overrides were removed.
- **Config.merge_with()**: `verbosity_level` now honors **override semantics** (other wins), and
  supports tri-state inheritance.
- **API surface**: `PublicDiagnostic` re-exported from `topmark.api` and included in `__all__`.

### Fixed

- Reader now surfaces an explicit diagnostic for empty files.
- Minor wording/formatting improvements in `classify_outcome()` and summary output.
- Import order cleanup in `pipelines.py`.

### Docs

- Expanded inline docstrings for diagnostics, public types, and verbosity semantics.

#### ⚠️ Breaking (pre‑1.0)

- `RunResult.diagnostics` type changed to a structured public form. Integrations consuming plain
  strings should switch to `d["message"]` and may use `d["level"]` for triage.
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
