<!--
topmark:header:start

  project      : TopMark
  file         : roadmap.md
  file_relpath : docs/dev/roadmap.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark 1.0 Roadmap

## Motivation / Why this matters

TopMark increasingly operates on data that is not naturally file-backed: generated code, editor
buffers, CI-provided snippets, or API-driven integrations. Today, almost all of TopMark’s processing
pipeline assumes filesystem I/O, which makes testing heavier, limits reuse, and complicates future
integrations.

Supporting an in-memory pipeline enables:

- Faster, more isolated tests without filesystem setup/teardown
- Cleaner API boundaries (pipeline as a pure transformation)
- Future integrations (editors, LSPs, CI bots) without temporary files
- Clearer separation between what TopMark does and how input is obtained

______________________________________________________________________

## Done so far

This section tracks work completed during the 0.12 development series that directly supports the 1.0
goals.

### Registry architecture: explicit processor bindings, namespaces, and shared resolution

- Replaced legacy decorator/bootstrap-based built-in processor registration with an explicit,
  deterministic binding model:
  - Added \[`topmark.processors.bindings`\][topmark.processors.bindings] with `ProcessorBinding` and
    `bindings_for(...)`.
  - Added \[`topmark.processors.instances`\][topmark.processors.instances] as the source of truth
    for built-in processor bindings and base processor registry construction.
  - Removed the old bootstrap/discovery path for built-in processors and deleted
    `topmark.processors.bootstrap` / `topmark.processors.registry`.
- Moved concrete built-in header processors into
  \[`topmark.processors.builtins`\][topmark.processors.builtins] and made them pure class-definition
  modules (no import-time registration side effects).
- Introduced namespace-aware identities for file types and processors:
  - `namespace` is now part of the stable identity model.
  - File types and processors expose `qualified_key` (`"<namespace>:<name>"` or
    `"<namespace>:<key>"`).
  - The built-in namespace token is explicitly represented as `topmark`.
- Added namespace-aware file type identifier resolution in
  \[`topmark.registry.filetypes.FileTypeRegistry.resolve_filetype_id`\][topmark.registry.filetypes.FileTypeRegistry.resolve_filetype_id],
  supporting both unqualified and qualified identifiers.
- Added ambiguity-aware file type lookup with
  \[`AmbiguousFileTypeIdentifierError`\][topmark.core.errors.AmbiguousFileTypeIdentifierError] so
  callers can distinguish:
  - unknown file type identifiers,
  - ambiguous unqualified identifiers, and
  - known-but-unsupported file types.
- Strengthened TopMark-specific registry errors in \[`topmark.core.errors`\][topmark.core.errors],
  including:
  - `ProcessorBindingError`
  - `ProcessorRegistrationError`
  - `DuplicateProcessorRegistrationError`
  - `DuplicateProcessorKeyError`
  - `UnknownFileTypeError`
  - `AmbiguousFileTypeIdentifierError`
- Completed the registry split into three explicit layers plus a thin façade:
  - \[`topmark.registry.filetypes`\][topmark.registry.filetypes] manages file type identities
  - \[`topmark.registry.processors`\][topmark.registry.processors] manages processor identities
  - \[`topmark.registry.bindings`\][topmark.registry.bindings] manages effective
    file-type-to-processor relationships
  - \[`topmark.registry.registry`\][topmark.registry.registry] now acts only as a thin
    cross-registry façade
- Normalized naming and public semantics across registries:
  - canonical identity keys (`qualified_key`) are now the default across APIs
  - `file_type_id` is reserved for user input that may be qualified or unqualified
  - helper naming now reflects canonical-key-first semantics (no `_by_qualified_key` suffix for
    default operations)
- Made canonical key semantics explicit throughout the registry layer:
  - processor identity is keyed canonically by processor key
  - binding relationships are keyed canonically by file type key and processor key
  - file types expose both a local-key compatibility view and a canonical qualified-key view
- Removed convenience façade helpers that mixed identity registration with binding side effects:
  - removed `Registry.register_processor()` / `Registry.try_register_processor()`
  - removed `Registry.register_filetype()` / `Registry.unregister_filetype()`
  - processor-definition creation is now explicit through `HeaderProcessorRegistry.register(...)`
  - file type registration is now explicit through `FileTypeRegistry.register(...)`
  - binding remains explicit through `Registry.bind(...)` / `BindingRegistry.bind(...)`
  - Introduced the new \[`topmark.resolution`\][topmark.resolution] package and clarified resolution
    responsibilities:
  - \[`topmark.resolution.files`\][topmark.resolution.files] resolves **which files** should be
    processed.
  - \[`topmark.resolution.filetypes`\][topmark.resolution.filetypes] resolves **what each file is**
    using scoring-based file type and processor binding selection.
- Simplified exception handling in registry façade helpers by removing redundant catch-and-reraise
  patterns and documenting propagated exceptions as part of the public contract
- Moved scoring-based file type resolution out of
  \[`topmark.pipeline.steps.resolver`\][topmark.pipeline.steps.resolver] into the shared resolution
  layer and slimmed the pipeline resolver step down to orchestration/context mutation.
- Deleted the old `topmark.registry.resolver` compatibility module after tests were migrated to the
  shared resolution helpers.
- Moved the former top-level `topmark.file_resolver` module into
  \[`topmark.resolution.files`\][topmark.resolution.files] to consolidate all runtime resolution
  logic under a dedicated package.
- Made configured file type filtering in file-input resolution namespace-aware by resolving config
  identifiers through `FileTypeRegistry.resolve_filetype_id(...)` rather than raw registry-key
  lookup.
- Fixed a regression in the new shared resolver where empty include/exclude file type collections
  were treated as active filters. Empty collections are now normalized to mean “no filter”,
  restoring expected file type resolution behavior.
- Formalized the resolver's ambiguity policy in the shared resolution layer:
  - overlapping `FileType` candidates are allowed and are treated as a resolver concern rather than
    a registry error
  - candidate selection is deterministic and now uses score, namespace, and local key as the stable
    tie-break order
  - tied top-scoring candidates emit debug logs before deterministic tie-break selection is applied
- Added dedicated developer documentation for path-based resolution and ambiguity handling in
  [`docs/dev/resolution.md`](resolution.md), and cross-linked it from architecture, pipelines, and
  plugin documentation.

### CLI output architecture

- Introduced a clearer split between:
  - \[`topmark.cli.emitters.*`\][topmark.cli.emitters] (Click-facing, console printing)
  - \[`topmark.cli_shared.*`\][topmark.cli_shared] (Click-free CLI concerns: presentation helpers,
    color policy, small shared utilities)
- Refactored many commands to share the same conceptual pipeline:
  - prepare Click-free model → render (text/markdown) → print
- Introduced shared Click-layer validators/policies
  (\[`topmark.cli.validators`\][topmark.cli.validators]) to centralize:
  - output-format policies (e.g., diff restrictions, machine-format limitations)
  - file-agnostic command behaviors (ignoring positional paths)
  - color policy enforcement for non-text outputs
- Moved verbosity (`-v`) and color (`--color/--no-color`) options from the root CLI group to
  individual commands.
- Added a convenience decorator to consistently attach common verbosity/color options per command.
- Clarified and centralized CLI initialization state in `cli.cmd_common`.
- Moved all machine-format generation out of `cli_shared` into domain-specific `*.machine` packages.
- Replaced legacy "emitters" with explicit `serializers` in core/config/pipeline/registry layers.
- Introduced a clear separation between:
  - pure serializers (no console, no Click)
  - CLI emitters (console-only, Click-aware)
- Centralized `build_meta_payload()` at CLI initialization (computed once per process and reused).
- Introduced `compute_version_text()` in `utils.version` to unify SemVer conversion and fallback
  logic across CLI and machine formats.

### Semantic styling and unified rendering

- Introduced a semantic styling layer based on `StyleRole`, decoupling presentation from business
  logic:
  - styling decisions are now mapped from semantic roles instead of applied directly in emitters
- Refactored text and Markdown emitters to use shared semantic styling helpers instead of direct
  Click/yachalk usage
- Centralized presentation helpers in \[`topmark.cli.presentation`\][topmark.cli.presentation] and
  aligned CLI-facing rendering logic with core presentation semantics
- Unified summary rendering across emitters using `map_bucket()`:
  - CLI output is now consistently derived from pipeline outcomes instead of ad-hoc hint inspection
- Introduced `DiagnosticStats.triage_summary()` to centralize diagnostic aggregation logic and
  remove duplication across emitters
- Extracted shared diagnostic rendering into reusable helpers (`render_diagnostics_text`)
- Aligned verbosity semantics across emitters:
  - default: concise summary with optional diagnostic hint
  - `-v`: primary hint + diagnostic summary
  - `-vv`: full hint list + detailed diagnostics
- Removed duplication between summary line rendering, diagnostic output, and hint rendering
- Removed `Hint.headline()` and simplified hint rendering semantics:
  - newest hint is treated as primary at `-v`
  - full ordered list is rendered at `-vv`
- Improved Markdown emitter:
  - switched to numbered result lists
  - aligned structure with text emitter (summary → guidance → diagnostics → hints)

### Pipeline semantics: preview vs apply

- Made write-status reporting **honest** and consistent across dry-run and apply pipelines:
  - Dry-run now emits `WriteStatus.PREVIEWED` (no terminal verbs like “removed” / “replaced”).
  - Apply mode (`--apply`) emits terminal statuses (`INSERTED`, `REPLACED`, `REMOVED`) and writers
    perform the actual filesystem updates.
- Plumbed apply intent end-to-end:
  - Added `Config.apply_changes` as a tri-state runtime intent and ensured CLI + API set it on the
    final merged config.
  - Updated the updater step to gate terminal `WriteStatus` values on `apply_changes`.
  - Refined bucketing/outcomes so “would change” vs “changed” categories align with apply intent and
    reasons match the established convention.
- Updated human summaries (`ProcessingContext.format_summary`) so dry-run output is no longer
  misleading (e.g., “would strip header” without claiming it was removed).

### Policy model, empty-file semantics, and outcome summaries

- Introduced a clearer runtime distinction between:
  - true empty files (`FsStatus.EMPTY`)
  - logically empty placeholders
  - effectively empty decoded images
  - derived `is_empty_like` classification in `ProcessingContext`
- Added processing-context emptiness flags and derived helpers used consistently across reader,
  planner, stripper, policy evaluation, and bucketing.
- Introduced `EmptyInsertMode` so insertion policy can distinguish between:
  - 0-byte files only
  - logical-empty placeholders
  - broader whitespace-empty images
- Refactored policy helpers in `topmark.pipeline.context.policy` so the same empty classification is
  reused for:
  - insert gating (`allow_insert_into_empty_like`)
  - change feasibility (`can_change`)
  - unchanged-by-default bucketing for empty-for-insert files
- Fixed reader behavior so only true 0-byte files remain `FsStatus.EMPTY`, while BOM-only,
  newline-only, and other empty-like decoded images preserve newline semantics and are represented
  via the emptiness flags instead.
- Fixed planner and stripper normalization for BOM-only, newline-only, and other placeholder images
  so insert → strip → insert remains idempotent.
- Updated outcome summary aggregation so counts are grouped by **(Outcome, reason)** instead of
  collapsing all reasons inside the same outcome bucket.
- Updated human-facing text/Markdown summaries and machine JSON/NDJSON summary payloads to preserve
  `outcome`, `reason`, and `count` explicitly.
- Improved summary rendering to include deterministic ordering and explicit total counts in
  human-facing summary output.
- Renamed machine summary/data wrapper terminology from `shapes.py` to `envelopes.py` where
  appropriate to better match responsibility.

### Registry output formats: qualified identifiers in machine and human output

- Updated \[`topmark.registry.machine`\][topmark.registry.machine] payloads and schemas so registry
  machine formats now emit namespace-aware identity data:
  - file type entries now include `name`, `namespace`, and `qualified_key`
  - processor entries now include `namespace`, `key`, and `qualified_key`
  - processor-bound and unbound file type references use qualified file type identifiers in brief
    output and expanded identity fields in detailed output
- Aligned machine payload grouping around processor identity rather than just `(module, class)`.
- Updated human-facing registry emitters (text and Markdown) and the shared Click-free registry
  report builders so file types are shown as qualified identifiers in human output as well.
- Updated plugin/API-facing documentation to explain:
  - qualified vs unqualified file type identifiers
  - ambiguity of unqualified names once multiple namespaces are present
  - runtime processor overlay registration against qualified file type identifiers

### Human output formats

- Consolidated human formats under:
  - `OutputFormat.TEXT` (label `"text"`)
  - `OutputFormat.MARKDOWN`
- Renamed emitter package *topmark.cli.emitters.default* to
  \[`topmark.cli.emitters.text`\][topmark.cli.emitters.text] to align naming with
  `OutputFormat.TEXT`.
- Extracted shared pipeline rendering primitives (diff rendering, per-command guidance) into
  \[`topmark.cli_shared.emitters.shared.pipeline`\][topmark.cli_shared.emitters.shared.pipeline].
- Improved consistency of wording across commands by reusing shared helpers for registry/config
  outputs.

### Command output consistency improvements

- `processors` and `filetypes` human output now uses **numbered lists** (right-aligned indices) and
  clearer counts.
- `dump-config` / `init-config` emit **plain TOML** by default; BEGIN/END markers are shown only at
  higher verbosity.
- `version` command output is now script-friendly (prints only the SemVer string, no label).
- Documentation updated across command pages to match the new verbosity and summary semantics.

### Machine output formats

Machine-readable output is now domain-scoped and schema-driven, with consistent envelopes and stable
keys across commands.

- Shared payload shapes and builders under \[`topmark.config.machine`\][topmark.config.machine] and
  related modules
- Consistent envelope structures (metadata + data) across commands
- Aligned semantics for config, registry, and version commands

The remaining gaps are primarily in pipeline-oriented commands (`check`, `strip`), where historical
CLI-specific emitters are still being phased out in favor of shared serializers.

The 1.0 goal is full symmetry:

- identical field names and structure across commands
- no ad-hoc JSON construction inside CLI modules
- machine formats completely independent from color, verbosity, or human formatting concerns

Completed work:

- Completed full separation of machine-format responsibilities into domain-specific packages:
  - \[`topmark.core.machine`\][topmark.core.machine] (shared keys/schemas/meta payloads)
  - \[`topmark.config.machine`\][topmark.config.machine] (config-related shapes and serializers)
  - \[`topmark.pipeline.machine`\][topmark.pipeline.machine] (processing results shapes and
    serializers)
  - \[`topmark.registry.machine`\][topmark.registry.machine] (filetype and processor registry shapes
    and serializers)
- Removed ad-hoc JSON construction from CLI command modules (`check`, `strip`, `config_*`,
  `filetypes`, `processors`, `version`).
- Standardized naming conventions:
  - `build_*` → payload construction (pure data)
  - `build_*_envelope` / `iter_*_records` → shape builders
  - `serialize_*` → JSON/NDJSON serialization (no console I/O)
  - `emit_*` → CLI-layer console output only
- Introduced shared NDJSON prefix builders for config + config_diagnostics records to avoid
  duplication across commands.
- Centralized machine keys and canonical values in
  \[`topmark.core.machine.schemas`\][topmark.core.machine.schemas], eliminating circular imports and
  key drift.
- Added explicit `MachineMeta` keys and extended the `meta` payload with `platform` information.
- Introduced typed `TypedDict` schemas for:
  - outcome summary entries and records (pipeline)
  - filetype registry entries
  - processor registry entries
- Documented the stable envelope and key conventions in `docs/dev/machine-formats.md` (and updated
  command pages accordingly).

### Config template handling

- Strengthened config template handling for `config init` / `config defaults` by applying
  conservative, string-based edits followed by TOML validation.
- Improved safety around `[tool.topmark]` insertion and `root = true` placement.

### Documentation and docstring tooling

- Tightened docstring linting and formatting:
  - pydoclint checks for argument order and raises sections
  - pydocstringformatter for consistent formatting
- Removed duplicate type hints from docstrings in the typed codebase
  (`arg-type-hints-in-docstring = false`).
- Documented and standardized exception documentation policy for public APIs:
  - `Raises:` sections now describe the observable caller contract, including intentionally
    propagated exceptions where relevant
  - targeted `# noqa: DOC503` suppressions are used on closing docstring lines for façade/delegation
    helpers that intentionally document propagated exceptions
  - contributor and developer docs now explain why redundant `try/except: raise` blocks should not
    be added solely to satisfy docstring linting

### Documentation: pipeline docs + generated API internals

- Added pipeline documentation under `docs/dev/`:
  - `pipelines.md` (concepts): Mermaid diagrams for the pipeline overview, CLI flows (`check` vs
    `strip`), and per-axis lifecycles.
  - `pipelines-reference.md` (reference hub): formatter-safe links into generated internals pages
    (no `mkdocstrings` directives).
- Introduced `mkdocs.linkcheck.yml` to support local/CI link checking without baking production-only
  base URLs.
- Clarified the documentation authoring rule: handwritten Markdown must not contain `mkdocstrings`
  directives; generated pages own all `:::` blocks.

### CI + link checking hardening (docs integrity)

- Added a built-site link check (`links-site`) that validates the rendered MkDocs HTML output,
  including generated API pages.
  - Uses `mkdocs.linkcheck.yml` and runs `lychee` against `site/` with `--root-dir` to resolve
    root-relative links. This built-site validation is now also used as part of the release gating
    flow.
- Updated GitHub Actions workflows to gate releases on built-site link integrity:
  - CI: conditional `links` (source Markdown) + `links-site` (built site) based on detected docs
    changes.
  - Release: publishing is gated on `links-site`.
- Updated CI documentation pages to reflect the new “docs integrity” model and to explicitly note
  that generated API pages are only validated via `links-site`.
- Hardened resolver behavior: exceptions in file type `content_matcher` functions are treated as
  misses (not failures), preserving resolution safety.

### GitHub Actions workflow refactor: CI gating, release preflight, and shared setup

- Refactored GitHub Actions into a clearer two-workflow model:

  - `CI` remains the main validation workflow for pull requests, pushes to `main`, and tag pushes.
  - `Release to PyPI` now runs only via `workflow_run` after `CI` completes, instead of also being
    triggered directly by tag pushes.

- Added an explicit **release preflight** job to the release workflow that:

  - verifies the trigger is a successful `workflow_run` from `CI`,
  - resolves the release tag from the CI head SHA,
  - exits cleanly with `should_release=false` when the run is not a real release,
  - gates all downstream release jobs (`details`, docs build, built-site link check, publish, GitHub
    release).

- This turns non-release `workflow_run` executions into a quiet no-op instead of a noisy or failing
  path.

- Split release responsibilities more clearly:

  - `preflight` decides whether a release should happen and derives tag/channel/version metadata,
  - `details` validates repository and package metadata against the resolved tag,
  - later jobs perform docs checks, packaging, publishing, and GitHub release creation only when
    preflight succeeds.

- Introduced a reusable local composite action at `/.github/actions/setup-python-nox/action.yml` to
  standardize Python setup, pip/uv cache handling, and nox bootstrap across workflows.

- Simplified the composite action API so `python-version` is the only public input; cache dependency
  inputs are now fixed internally to the canonical dependency set.

- Standardized GitHub Actions cache dependency globs and ordering around:

  - `pyproject.toml`
  - `noxfile.py`
  - `uv.lock` so setup, cache keys, and trigger logic do not drift out of sync.

- Refined CI changed-file detection into explicit buckets:

  - `python_changed`
  - `docs_changed`
  - `markdown_links_changed`
  - `precommit_changed`

- Used those buckets to gate CI jobs more precisely on pull requests:

  - `lint`, `tests`, and `api-snapshot` follow Python/code changes,
  - `docs` and `links-site` follow docs and docstring-related changes,
  - `links` follows Markdown/docs-link changes,
  - `pre-commit` follows code, docs, workflow, tooling, and config changes.

- Expanded CI trigger coverage so pull-request workflow execution now responds correctly to:

  - workflow/action changes,
  - docs-tooling changes,
  - selected top-level Markdown files (`README.md`, `INSTALL.md`, `CONTRIBUTING.md`),
  - shared editor/tooling config relevant to validation.

- Confirmed via PR-based validation that the new CI gating behaves as intended:

  - a top-level Markdown-only PR runs `changes`, `links`, and `pre-commit`, while skipping
    code-heavy and docs-heavy jobs,
  - a `src/**`-only PR runs `changes`, `lint`, `pre-commit`, `docs`, `links-site`, `tests`, and
    PR-only `api-snapshot`, while skipping top-level Markdown link checks.

- Retained a small permanent troubleshooting log in release preflight that prints tags pointing at
  the CI SHA before selecting a release tag.

### Developer automation: nox + uv (tox removal)

- Migrated project automation from tox to nox and removed `tox.ini`.
- Added `noxfile.py` sessions for formatting, linting, docs build, QA (pytest + pyright), API
  snapshot, link checks, packaging checks, and release gates.
- Switched to uv-backed environments to reduce env creation and dependency install time.
- Updated Makefile targets to call nox sessions (including parallel QA via `make -j`).
- Made `noxfile.py` import-time TOML parsing robust on Python < 3.11 (`tomllib`/`tomli` fallback).
- Hardened lychee invocation for large file lists by chunking arguments to avoid command line length
  limits.

### Dependency workflow modernization: uv-first project model

- Completed the transition from mixed pip/requirements-based dependency management to a **uv-first**
  workflow:
  - `pyproject.toml` remains the declaration source for runtime and extra dependency ranges.
  - `uv.lock` is now the canonical committed lockfile and source of truth for reproducible
    dependency resolution.
- Refactored `noxfile.py` so sessions install from **project extras** instead of exported
  `requirements-*.txt` files:
  - introduced shared dependency constants for dev/docs extras,
  - kept base-project installation only where appropriate (for example entry-point validation),
  - aligned session behavior with the `pyproject.toml` extras model.
- Completed the migration of local development workflow to uv-managed environments:
  - `.venv` is now created through `uv venv` and synchronized through uv extras-based sync targets,
  - local `.venv` is documented as the standard long-term environment for IDE integration and
    interactive development,
  - `nox` remains the isolated QA/CI-parity execution layer.
- Removed legacy exported dependency artifacts and the associated compatibility workflow:
  - deleted `requirements.txt`, `requirements-dev.txt`, `requirements-docs.txt`, and
    `constraints.txt`,
  - removed the corresponding Makefile export/compile targets,
  - removed workflow/cache/trigger dependence on those files.
- Updated GitHub Actions and release automation to treat `uv.lock` as the canonical dependency
  signal:
  - cache keys now derive from `pyproject.toml`, `uv.lock`, and `noxfile.py`,
  - docs installation in CI/release jobs now installs from project extras (`.[docs]`) instead of
    exported requirements files,
  - built-site link checking was restored with `lycheeverse/lychee-action` after confirming that the
    nox session itself does not provision the `lychee` binary in GitHub-hosted runners.
- Migrated Read the Docs build commands to a uv-based installation flow:
  - install `uv`,
  - install the project with `.[docs]`,
  - build MkDocs from project metadata rather than compatibility requirements files.
- Updated documentation (`README.md`, `INSTALL.md`, `CONTRIBUTING.md`, CI docs) to describe the new
  uv-first model, including:
  - `.venv` as the standard local development environment,
  - `uv.lock` as the canonical lock source,
  - `nox` as the isolated QA/automation layer.

### Compatibility and release hygiene

- Fixed a Python < 3.12 incompatibility caused by multiline f-strings in CLI output code paths.
- Updated pre-commit hook recommendations to rely on the default terse output.
- Improved internal debug logging around bucket mapping and summary formatting.
- Removed PathSpec deprecation warnings by replacing deprecated `GitWildMatchPattern` usage with the
  supported `"gitignore"` pattern family in file-resolution logic, while preserving include/exclude
  behavior.

### Supply-chain hardening and Dependabot policy

- Upgraded GitHub Actions to Node 24-compatible releases where available and pinned workflow actions
  to **full commit SHAs** instead of floating tags.
- Added Dependabot configuration for:
  - GitHub Actions updates,
  - uv-managed Python dependency updates.
- Switched Dependabot from the pip ecosystem to the **uv ecosystem** so dependency automation aligns
  with `pyproject.toml` + `uv.lock` rather than exported requirements files.
- Added repository labels and PR-volume controls for Dependabot to keep automated update traffic
  manageable.
- Documented action pinning, SHA updates, and Dependabot review policy in dedicated CI documentation
  (`docs/ci/dependabot.md`) and cross-linked the CI/release workflow docs.

### Formatting/tooling alignment: Markdown, TOML, docs hooks, and packaging metadata

- Centralized Markdown formatter configuration in `.mdformat.toml` and TOML formatter configuration
  in `.taplo.toml` so CLI tools, pre-commit, CI, and editor integrations use the same source of
  truth.
- Fixed an incorrect Markdown formatter setup by explicitly supporting GitHub Flavored Markdown
  alert/callout syntax through `mdformat-gfm-alerts`.
- Fixed an incorrect Taplo configuration layout by moving Taplo-specific settings out of
  `pyproject.toml` into Taplo’s native config file, improving consistency across the Taplo CLI and
  the VS Code extension.
- Updated pre-commit and development dependency wiring so Markdown formatting environments
  consistently install the required mdformat plugins.
- Simplified GitHub alert conversion in `tools.docs.hooks`:
  - Material admonition titles are now always derived from the alert kind (`NOTE`, `TIP`, etc.).
  - Authored callout content is preserved as admonition body content without attempting to infer a
    separate custom title.
  - The regex and helper logic were simplified to be robust against `mdformat` normalization of
    GitHub alert blocks.
- Improved packaging metadata in `pyproject.toml`:
  - modern license metadata (`license` + `license-files`)
  - richer keywords and topic classifiers
  - maintainer metadata
  - additional project URLs (Issues, Discussions, CI, Changelog)
- Simplified local environment bootstrap in `Makefile` so `make venv` only creates the environment
  and installs `uv`; dependency synchronization is handled explicitly by the sync targets.

______________________________________________________________________

## Breaking changes introduced so far

These are changes already landed (or expected to land) during the 0.12 refactor series.

### Registry / resolution model changes

- Built-in processor registration no longer relies on import-time decorators or bootstrap scanning.
  Integrations depending on decorator/bootstrap-era processor registration behavior must migrate to
  the explicit binding/overlay model.
- Removed:
  - `topmark.processors.bootstrap`
  - `topmark.processors.registry`
  - `topmark.registry.resolver`
  - `register_all_processors()`
  - `Registry.ensure_processors_registered()`
- Concrete built-in processor classes now live under
  \[`topmark.processors.builtins`\][topmark.processors.builtins]. Older import paths such as
  `topmark.processors.xml.XmlHeaderProcessor` were migrated to the new package layout.
- Path-based resolution is now centralized in \[`topmark.resolution`\][topmark.resolution].
  Callers/tests that previously relied on legacy resolver helpers must use the shared resolution
  helpers instead (for example `resolve_binding_for_path(...)`).
- Registry mutation is now fully explicit and split by responsibility:
  - processor-definition registration must go through `HeaderProcessorRegistry.register(...)`
  - file type registration must go through `FileTypeRegistry.register(...)`
  - file-type-to-processor association must go through `Registry.bind(...)` /
    `BindingRegistry.bind(...)`
  - the former convenience helpers that combined registration and binding in `Registry` were removed
- Namespace-aware file type lookup now supports qualified identifiers and may raise
  \[`AmbiguousFileTypeIdentifierError`\][topmark.core.errors.AmbiguousFileTypeIdentifierError] when
  an unqualified identifier matches multiple file types.
- Registry mutation and registration errors now use TopMark-specific core errors instead of generic
  `ValueError` / `RuntimeError` in the refactored code paths.
- Registry machine and human outputs now expose qualified identifiers and namespace metadata for
  file types/processors. Downstream tooling or snapshots expecting unqualified-only registry output
  may need to be updated.
- Public API registry metadata in \[`topmark.api`\][topmark.api] was reshaped to align with the
  split filetype / processor / binding model:
  - `FileTypeInfo.name` was removed in favor of `local_key`, `namespace`, and `qualified_key`
  - `FileTypeInfo.processor_name` was removed
  - `FileTypeInfo.supported` was replaced by `bound`
  - `ProcessorInfo.name` was removed in favor of `local_key`, `namespace`, and `qualified_key`
  - `list_bindings()` was added as the explicit relationship-oriented API entry point
  - downstream callers consuming the old TypedDict field names must be updated
- File type resolution ambiguity is now an explicitly documented resolver concern:
  - overlapping `FileType` definitions are permitted
  - deterministic tie-breaks are part of the resolver contract
  - the policy is documented in `docs/dev/resolution.md`

### CLI / output format changes

- Output format rename: `DEFAULT` was removed and replaced by `TEXT` (label now `"text"`).
- Emitter package rename: *topmark.cli.emitters.default* →
  \[`topmark.cli.emitters.text`\][topmark.cli.emitters.text].
- Shared pipeline helpers moved to
  \[`topmark.cli_shared.emitters.shared.pipeline`\][topmark.cli_shared.emitters.shared.pipeline].
- Verbosity and color options were moved from the root CLI group to individual commands. Global
  invocation patterns may need to be updated.
- Color behavior tightened:
  - color is only meaningful for `OutputFormat.TEXT`
  - non-text formats ignore color requests and may warn (policy is centralized in validators)
- Dry-run summaries now end with `- previewed` instead of terminal verbs; apply runs show
  `- inserted` / `- replaced` / `- removed`.
- Summary output (human and machine) now groups by `(outcome, reason)` rather than collapsing all
  reasons into a single per-outcome label.
- Machine summary payloads now emit explicit summary rows with:
  - `outcome`
  - `reason`
  - `count`
- Policy around inserting into empty files is now interpreted through `EmptyInsertMode`; behavior
  for BOM-only, newline-only, and other empty-like placeholders may therefore differ from older
  0-byte-only semantics.
- Machine summary payloads are now flat row lists keyed by `(outcome, reason)` rather than
  outcome-keyed maps with a single collapsed label.
- Summary line rendering is now **outcome-driven** (via `map_bucket()`) instead of hint-driven;
  wording and structure of per-file output may differ from previous versions.
- Verbosity behavior refined:
  - `-v` now shows a single primary hint (newest)
  - `-vv` shows the full hint list
- Diagnostics are no longer embedded in summary lines and are rendered via dedicated helpers.
- Removal of `Hint.headline()`; downstream consumers must no longer rely on headline-specific
  behavior.
- Introduction of `would_change` vs `changed` outcome distinction in CLI output (check vs apply).
- Removal of legacy diff utilities (`topmark.utils.diff`) in favor of unified diff rendering
  modules.

### Documentation build behavior

- Documentation build now depends on Markdown output paths for registry/pipeline commands. Missing
  emitter modules will fail the docs build (`mkdocs build --strict`).
- CI now performs built-site link checks (`links-site`) during release gating; link validation
  failures may block publishing.
- GitHub-style alert handling in the docs pipeline no longer attempts to infer custom titles from
  inline/body text; rendered admonition titles now always come from the alert kind (`Note`, `Tip`,
  etc.).
- Formatter configuration for Markdown and TOML is now sourced from dedicated tool config files
  (`.mdformat.toml`, `.taplo.toml`) rather than mixed into `pyproject.toml`.

### Developer tooling / CI

- tox support removed; contributors and CI must use `nox` (and uv-backed envs) going forward.
- Local/editor/Nox/pre-commit environments now assume dedicated mdformat and Taplo tool
  configuration files are present and authoritative.
- Packaging metadata was modernized in `pyproject.toml` (including SPDX-style `license` and
  `license-files`), which may require older packaging/tooling environments to be refreshed.
- The project no longer maintains committed `requirements*.txt` or `constraints.txt` artifacts as
  part of its dependency-management model.
- `uv.lock` is now the canonical lock artifact; CI, release automation, and local workflows derive
  dependency resolution from `pyproject.toml` + `uv.lock`.
- Local development now assumes `uv` is installed and available on `PATH` for the standard Makefile
  and environment-management workflow.
- `nox` session dependency installation now comes from project extras (`.[dev,...]`, `.[docs]`,
  etc.) instead of exported requirement files.
- GitHub workflow action references are pinned to commit SHAs rather than release tags, which may
  affect maintainers who previously expected floating-tag behavior.
- Dependabot now tracks the `uv` ecosystem instead of pip/requirements-file inputs.
- Release publishing is no longer triggered directly by tag pushes in the release workflow;
  publishing now depends on a successful `CI` `workflow_run` plus a valid release tag resolved from
  the CI head SHA.
- GitHub Actions workflow behavior on pull requests is now more aggressively gated by changed-file
  buckets, so some jobs that previously ran for all PRs may now be skipped unless the relevant files
  changed.
- CI/release workflow bootstrap is now centralized through a shared local composite action
  (`.github/actions/setup-python-nox`). Maintainers changing workflow bootstrap behavior should
  update that action rather than duplicating edits across workflow files.

### uv workflow follow-up and ecosystem stabilization

The uv migration is functionally complete, but a few follow-up decisions remain before 1.0:

- Perform a final documentation wording sweep for stale references to:
  - tox,
  - requirements/constraints files,
  - legacy target names,
  - older pip-oriented setup language.
- Decide whether `uv.lock` should be represented in TopMark’s built-in file type registry as a
  recognized-but-header-unsupported generated artifact.
- Keep validating that local `.venv`, nox, CI, pre-commit, and RTD all continue to reflect the same
  dependency and formatter/plugin expectations under the uv-first model.

### GitHub Actions follow-up and release-path rehearsal

The workflow refactor is functionally in place, but a few follow-up decisions remain before 1.0:

- Decide whether to rehearse the positive release path with a dedicated dry-run or a TestPyPI
  publish before 1.0.
- Decide whether the duplicated built-site docs/linkcheck steps in CI and release should remain
  inline or later be factored into a reusable workflow.
- Decide whether the `tests` matrix job should eventually reuse the shared setup composite action by
  adding optional settings such as prerelease-Python support, or whether the current explicit matrix
  setup should remain the clearer implementation.
- Decide whether workflow-file indentation/style should be enforced only through `.editorconfig` and
  editor policy, or also documented explicitly in contributor-facing CI guidance.
- Keep validating that workflow trigger coverage and changed-file buckets stay aligned as project
  tooling and config files evolve.

______________________________________________________________________

## Still undecided / still to do

This section lists remaining 1.0 decisions and implementation work. Items are grouped by theme.

### Namespace-based registry completion

#### Status

- Identity model: implemented
- Canonical processor/binding storage: implemented
- File type dual-view model: implemented and under review for 1.0 freeze

Current state:

- File types and processors now have namespace-aware stable identities.
- Processor definitions are stored canonically by processor key.
- Effective bindings are stored canonically by file type key → processor key.
- `FileTypeRegistry` intentionally maintains two overlapping views:
  - a local-key compatibility view
  - a canonical qualified-key view
- The public registry façade now treats canonical keys as the default identity form and uses
  `file_type_id` only for resolver-style inputs that may be local or qualified.

Remaining work before 1.0:

- Decide whether the local-key compatibility view in `FileTypeRegistry` should remain an explicit
  long-term 1.0 feature or be treated as a transitional bridge.
- Freeze and document where local keys remain acceptable user-facing input:
  - CLI/config include/exclude filters
  - API resolver-style helpers
  - plugin-facing examples and tests
- Confirm that canonical key terminology (`file_type_key`, `processor_key`, `file_type_id`,
  `local_key`) is fully stabilized across docs, tests, and public API references.
- Align CLI commands and API representations with the split registry model (filetypes / processors /
  bindings) and remove remaining binding-flavored coupling from processor-oriented views

Recommended direction:

- Keep canonical qualified identity as the default internal model.
- Keep the file-type local-key view only as an explicit compatibility layer where it provides real
  user-facing value.
- Preserve fail-fast behavior for duplicate processor registration while keeping overlap between
  file types a resolver concern rather than a registry error.

### In-memory pipeline (Option A)

#### Status

- Design: drafted and reviewed
- Implementation: not started
- Target window: post-0.12, before 1.0 feature freeze

Goal: enable TopMark to run the existing processing pipeline on **in-memory** inputs (strings or
bytes) without restructuring the pipeline architecture or changing the default file-based CLI
behavior.

This refactor should:

- Preserve the existing step model and execution order (Resolver → Sniffer → Reader → …)
- Introduce an input abstraction that can represent either a filesystem path *or* in-memory content
- Keep file-based operation as the default and the most optimized path
- Allow tests (and future integrations) to run the pipeline without touching disk

#### Scope and non-goals

In scope:

- Add an input abstraction type ("input source")
- Provide alternate steps for in-memory inputs that bypass filesystem-only assumptions
- Keep the rest of the pipeline (header detection/update/write/report) unchanged
- Ensure file-type detection still works when it can rely on content (sniffers/matchers)

Explicit non-goals (for 1.0):

- Implement a full virtual filesystem
- Support directory traversal from in-memory roots
- Rework all steps to accept arbitrary I/O backends

#### Risks & trade-offs

- **File-type detection**: Some file types rely heavily on filename or path semantics. In-memory
  inputs must either provide a synthetic name or accept reduced detection fidelity in edge cases.
- **Synthetic paths**: Introducing fake or sentinel paths risks accidental assumptions in downstream
  code (e.g. path arithmetic, parent traversal).
- **Behavior parity**: Ensuring identical behavior between file-based and memory-based pipelines
  requires disciplined reuse of sniffers, matchers, and policies.

### Concept: Input sources

Introduce a small data model to represent pipeline inputs.

Suggested core type:

- `InputSource` (protocol or dataclass)
  - `kind`: `"path" | "memory"`
  - `display_name`: `str` (for reporting)
  - `path`: `Path | None`
  - `text`: `str | None`
  - `bytes`: `bytes | None`
  - `encoding`: `str | None`

Key invariants:

- Exactly one of `path` or (`text`/`bytes`) is present.
- For memory inputs, `display_name` must be stable and meaningful (e.g., `<stdin>`, `snippet.py`).

#### Wiring approach

Keep the existing pipeline steps but make the **first stage** responsible for yielding a uniform
stream of `ProcessingContext` objects.

Recommended (smallest diff): two pipeline variants.

- Existing pipeline: `file_pipeline` uses Resolver/Sniffer/Reader
- New pipeline: `memory_pipeline` uses InMemoryResolver/InMemorySniffer/InMemoryReader
- Both pipelines share all later steps unchanged

#### Step design (minimal changes)

##### Resolver

Current responsibility: expand CLI paths (files/dirs), apply glob logic, yield concrete files.

In-memory variant:

- Accept `InputSource(kind="memory")`
- Yield a `ProcessingContext` with:
  - `path` unset or set to a synthetic Path-like marker (avoid real filesystem assumptions)
  - `display_name` populated from `InputSource.display_name`
  - source content attached to context

##### Sniffer

Current responsibility: determine file type using path + optional content matcher.

In-memory variant:

- If `display_name` has an extension, use the same registry mapping as path-based resolution.
- Run content matcher / pre-insert checker using the in-memory content.
- Ensure the final `FileType` selection matches file-based behavior when given equivalent
  name/content.

##### Reader

Current responsibility: read file bytes/text from disk.

In-memory variant:

- No I/O. Populate the same context fields that the file reader would populate (e.g.
  `original_text`, `newline`, `encoding`, etc.)

#### API surface

Provide a single public entry point that accepts either:

- filesystem paths (existing CLI/API)
- `InputSource` objects (new)

Possible addition:

- `run_pipeline(inputs: Sequence[Path | InputSource], ...)`
  - internally chooses file_pipeline vs memory_pipeline (or mixes if allowed)

#### Testing strategy

- Add unit tests that pass `InputSource(kind="memory")` with small content samples.
- Reuse existing golden tests by constructing memory inputs from fixture files.
- Keep a smaller number of integration tests to validate real filesystem behavior

### Test reorganization and improved coverage

The introduction of in-memory inputs is an opportunity to improve the test suite:

- Reduce reliance on filesystem I/O in unit tests by using `InputSource(kind="memory")`
- Consolidate overlapping tests that currently exercise the same logic via different filesystem
  setups
- Increase coverage of edge cases (empty files, unusual encodings, synthetic names)
- Keep a smaller number of integration tests to validate real filesystem behavior

The long-term goal is a clearer split between:

- fast, deterministic unit tests (memory-based), and
- a limited set of I/O-heavy integration tests

### Implementation milestones

1. Define `InputSource` and adapt `ProcessingContext` to hold optional in-memory content.
1. Add `InMemoryResolverStep`, `InMemorySnifferStep`, `InMemoryReaderStep`.
1. Add a `memory_pipeline` definition next to the existing one.
1. Extend the public API to accept `InputSource`.
1. Add tests + docs.

### Open questions to decide later

- Mixing file and memory sources in one run: allowed or split?
- How to represent a synthetic path in reports (string vs Path)?
- Should `--stdin` map to `InputSource(display_name="<stdin>")`?

### Resolution package stabilization

The new \[`topmark.resolution`\][topmark.resolution] package now centralizes runtime file-input and
file-type resolution, but its public/internal API surface should still be stabilized before 1.0.

Open decisions:

- Which resolution helpers should remain public versus private implementation details?
- Should `topmark.resolution.filetypes` expose only the high-level trio:
  - `get_file_type_candidates_for_path(...)`
  - `resolve_file_type_for_path(...)`
  - `resolve_binding_for_path(...)` while keeping candidate scoring helpers private?
- Should input resolution (`resolve_file_list`) be renamed to something more explicit such as
  `resolve_files_to_process(...)`, or is the current name stable enough for 1.0?
- Should the resolution layer stay decoupled from full config objects and instead continue to accept
  only the specific include/exclude file type filters it actually needs?
- Should TopMark keep the current deterministic winner-selection policy for overlapping `FileType`
  candidates through 1.0, or introduce a stricter ambiguity mode later?
- Should namespace ever become a semantic precedence signal, or remain only a stable tie-breaker?

Before 1.0, the package should have:

- a documented stable responsibility split between `resolution.files` and `resolution.filetypes`
- a frozen ambiguity policy for path-based file type resolution, including:
  - deterministic tie-break ordering
  - overlap being treated as a resolver concern rather than a registry error
  - documented observability/debug logging behavior for tied top candidates
- a frozen public helper surface
- test coverage for namespace-aware filtering and ambiguity behavior in both file-input and
  file-type resolution

### Documentation/tooling policy stabilization

Open follow-up work before 1.0:

- Decide whether GitHub alerts in docs should remain a first-class source format long-term, or
  whether authored Markdown should eventually migrate to native MkDocs/Material admonition syntax.
- Freeze and document the supported Markdown authoring conventions now that formatter normalization
  is part of the pipeline (especially for alerts/callouts, blockquotes, and reference-style links).
- Decide how much packaging metadata policy should be documented for contributors (e.g. required
  project URLs, classifiers, and license metadata conventions).
- Keep validating that Nox, pre-commit, local `.venv`, and editor integrations all install the same
  formatter plugin set and consume the same tool configuration.

### API vs CLI separation

#### Status

Some CLI-oriented concerns still leak into API-facing modules (notably in
\[`topmark.config`\][topmark.config] and parts of pipeline orchestration).

Before 1.0, aim for:

- A clean API surface usable without Click
- CLI modules acting strictly as orchestration and presentation layers
- No CLI-specific behavior (verbosity, coloring, formatting decisions) inside core logic

Additional progress:

- Machine-format serializers are fully API-usable (no Click dependency).
- CLI initialization computes `meta` once and passes it into serializers.
- API remains free of CLI-specific meta concerns unless machine output is explicitly requested.

#### Remaining work

- Remove remaining Click-facing concerns from non-CLI modules.
- Ensure formatting/verbosity/color decisions remain strictly CLI-side.
- Clarify ownership of `meta` in the API only when machine output becomes part of the API surface.

### Config override application boundary

Today, `MutableConfig.apply_args()` lives in \[`topmark.config.model`\][topmark.config.model] and
applies a generic `ArgsLike` mapping (CLI or API) directly onto the config. This keeps CLI and API
behavior aligned, but it also introduces CLI-shaped concepts (argument keys and CLI option
semantics) into a core module.

Decision to make before 1.0:

- Keep `MutableConfig.apply_args()` in core config (but narrow the surface and decouple from CLI
  keys), or
- Move override application to a CLI-shared semantics layer (Click-free), or
- Introduce a typed overrides model (e.g., *topmark.config.overrides*) that CLI/API construct, and
  core applies.

Desired outcome:

- Core config loading/merging stays reusable and independent of CLI concerns.
- CLI parsing/normalization produces a clear override structure.
- The same override structure remains usable by API callers (without importing Click).

### Machine output formats

Machine formats are now fully centralized and domain-scoped.

Completed work:

- Pipeline commands (`check`, `strip`) use \[`topmark.pipeline.machine`\][topmark.pipeline.machine]
  shape builders and serializers.
- Registry commands (`filetypes`, `processors`) use
  \[`topmark.registry.machine`\][topmark.registry.machine].
- Config commands (`init`, `defaults`, `dump`, `check`) use
  \[`topmark.config.machine`\][topmark.config.machine].
- Version command uses \[`topmark.core.machine`\][topmark.core.machine] serializers with shared meta
  handling.
- All commands emit identical envelope structures for JSON and NDJSON.
- CLI modules no longer construct machine payloads directly.

Remaining work before 1.0:

- Final audit of field naming consistency across domains.
- Expand test coverage for machine formats (especially registry + pipeline commands, JSON + NDJSON).
- Stabilize and freeze machine schema documentation (`docs/dev/machine-formats.md`).
- Decide whether summary payloads should remain flat row lists everywhere or also expose
  grouped-by-outcome views in documentation/examples.
- Review whether pipeline summary rows should eventually expose additional structured fields beyond
  `(outcome, reason, count)`.

### Human-facing output formats

Text (ANSI) and Markdown output formats have been refactored for most commands, with shared
Click-free renderers and centralized CLI policy enforcement.

Remaining work before 1.0:

- Ensure `OutputFormat.TEXT` and `OutputFormat.MARKDOWN` are consistent across commands.
- Ensure verbosity semantics are consistent (`-v`, `-vv`, `-q`) and documented.
- Keep all formatting logic out of CLI command functions.
- Finalize hint ordering strategy (newest-first vs oldest-first) and ensure consistency across text
  and Markdown emitters.
- Decide whether the “primary hint” concept (shown at `-v`) should remain explicit or be generalized
  to multi-hint display.
- Evaluate whether Markdown output should remain structurally equivalent to text output or evolve
  toward more document-oriented layouts (e.g., tables or grouped sections).
- Decide whether semantic style roles should be exposed/configurable (themes, CI/no-color modes).
- Further clarify boundary between pipeline outcome computation (`map_bucket()`) and presentation
  logic in emitters.

### Pipeline commands: complete human + machine format refactor

- Finish aligning `check` and `strip` outputs with the established pattern:
  - shared Click-free preparation
  - text emitter (`cli.emitters.text.*`)
  - Markdown emitter (`cli_shared.emitters.markdown.*`)
  - machine serializers for JSON/NDJSON
- Confirm and document verbosity semantics consistently across all commands:
  - `-v`: show per-file guidance / extra hints
  - `-vv`: show detailed diagnostics / expanded sections
- Confirm that no `yachalk` imports remain outside CLI-facing modules once color-boundary cleanup is
  completed.

### CLI framework choice: Click vs Rich

Recommendation: keep Click through 1.0 unless there is a strong feature need.

### Color output and dependency on yachalk

Recent refactoring introduced semantic styling via `StyleRole`, significantly reducing direct
`yachalk` usage in emitters and enabling a cleaner separation between core logic and CLI
presentation. Remaining work focuses on fully eliminating or strictly confining `yachalk` usage to
CLI-only modules.

Open question: remove `yachalk` fully or enforce a strict boundary (CLI-only usage).

Current imports to eliminate or relocate:

```sh
% grep "from yachalk" src/topmark/**/*py
src/topmark/cli/emitters/text/pipeline.py:from yachalk import chalk
src/topmark/cli_shared/outcomes.py:from yachalk import chalk
src/topmark/config/logging.py:from yachalk import chalk
src/topmark/core/presentation.py:    from yachalk import chalk
src/topmark/diagnostic/model.py:from yachalk import chalk
src/topmark/pipeline/hints.py:from yachalk import chalk
src/topmark/pipeline/status.py:from yachalk import chalk
src/topmark/pipeline/steps/patcher.py:from yachalk import chalk
src/topmark/utils/diff.py:from yachalk import chalk
```

If the goal is to remove all color-aware code from non-CLI modules, this likely requires:

- representing colors as semantic tokens in core layers (e.g., status categories)
- mapping those tokens to ANSI styles only in the text emitter

Alternative: keep `yachalk` but enforce a strict boundary (CLI-only usage).

### Configuration format: schema evolution and versioning

Open question: add an explicit configuration schema version.

Trade-offs:

- Pros: easier forward-compatibility handling, clearer upgrades/migrations post-1.0
- Cons: adds new user-visible key and validation logic; can become a burden if not used

Comparable tools vary:

- Many tools evolve config schema implicitly (new keys are additive and ignored by older versions)
- Some introduce explicit versioning when non-additive changes are expected or when migrations are
  supported

Recommendation for 1.0: document and stabilize key semantics. Consider adding a schema version only
when the first non-additive change is planned (post-1.0), paired with migration tooling.

### Human output formats and verbosity levels

Open questions:

- Do we want a second non-colored format (e.g., `text` vs `plain`), or is a single text format with
  optional color sufficient?
- Do we want to keep Markdown as a first-class human format for all commands?
- Are the current verbosity levels sufficient and consistent across commands?

Compare with common CLIs:

- ruff/black: minimal default output, `-v` adds more context
- git: default is concise, verbosity flags and `--porcelain` separate human vs machine

### Docstring formatting and styling guidelines

We now rely on Ruff, pydoclint, pydocstringformatter, and MkDocs build-time scripts. Remaining work
is mostly consistency and authoring guidance:

- When to use single vs double backticks
- Consistent rendering of `True` and `False`
- Consistent bullets/dashes and indentation
- Keep docstrings and Markdown aligned with the same wrap width
- Keep handwritten Markdown style guidance aligned with `.mdformat.toml` so contributor expectations
  match automated formatting.
- Decide whether docs authoring guidance should explicitly forbid semantic dependence on
  formatter-unstable Markdown layouts.

### Policy model and operation modes

TopMark currently processes all resolved and supported file types by default.

Open questions for 1.0:

- Should the default mode remain “process all supported types”?
- Should we introduce a stricter whitelist-first mode (e.g. Python, Markdown, TOML only)?
- How should policies interact with file-type inclusion/exclusion at scale?
- Freeze the public/documented token names for `EmptyInsertMode` and their exact semantics.
- Decide whether API callers should configure `empty_insert_mode` via public string literals only,
  or whether a dedicated public enum should exist post-1.0.
- Decide whether summary bucketing reason strings should be treated as stable integration surface or
  only as presentation-facing labels.

Any change here should preserve backward compatibility unless explicitly gated.

______________________________________________________________________

## 1.0 readiness checklist

This checklist defines the minimum criteria for cutting TopMark 1.0.

### Architecture & boundaries

- [ ] Clear separation between CLI layer and API/core modules
- [ ] No CLI-specific concerns (verbosity, color, formatting) in core logic
- [x] Path-based file resolution and file type / processor resolution are separated into the
  `topmark.resolution` package instead of being split across pipeline and registry helpers
- [x] File type resolution ambiguity policy is documented and deterministic (score + namespace +
  local key tie-breaks)
- [x] All machine-format payloads built outside CLI command modules
- [x] Color handling fully confined to CLI (semantic style roles implemented; remaining yachalk
  usage to be eliminated or isolated)

### Machine formats

- [x] JSON and NDJSON schemas fully aligned across all commands
- [x] Identical envelope structure (metadata + data) everywhere
- [x] Machine payload construction removed from CLI command modules
- [x] Registry machine formats include namespace-aware identity fields (`namespace`,
  `qualified_key`, processor `key`)
- [x] Documented examples for processing summary rows in `docs/dev/machine-formats.md` /
  `docs/dev/machine-output.md`
- [ ] Documented examples for each remaining command category in `docs/dev/machine-formats.md`
- [ ] No presentation leakage (color text, human wording) in machine output
- [ ] Machine outputs are covered by tests for registry commands (`filetypes`, `processors`) and
  pipeline commands (`check`, `strip`) in both JSON and NDJSON modes
- [ ] Final schema freeze review before 1.0 (including `(outcome, reason, count)` summary rows)

### Human formats

- [ ] `OutputFormat.TEXT` and `OutputFormat.MARKDOWN` consistent across commands
  - [ ] Config commands
  - [x] Pipeline commands (check, strip)
  - [ ] Registry commands
  - [x] Version command
- [x] Semantic styling implemented via `StyleRole` and consistently applied across emitters
- [ ] Human-facing registry outputs reviewed/frozen for qualified identifier presentation
- [ ] Verbosity levels (`-v`, `-vv`, `-q`) documented and behave consistently
- [ ] Diff rendering policy consistent across pipeline commands
- [ ] Warnings and error phrasing consistent across CLI
- [x] Summary mode renders stable `(outcome, reason, count)` rows in both text and Markdown
- [x] CLI summary rendering unified via `map_bucket()` and consistent across pipelines and emitters

### CLI behavior

- [x] Global options correctly scoped to commands (verbosity, color)
- [x] Validators centralized and consistently applied
- [ ] Exit codes documented and stable (audit after preview/apply status changes and bucketing
  fixes)
- [ ] Help output accurate and aligned with implemented behavior
- [x] Meta payload initialized once per process and reused across commands

### Configuration

- [ ] Config keys and semantics documented and considered stable
- [ ] Qualified and unqualified file type identifier semantics in config include/exclude filters,
  resolver-style API helpers, and file-type compatibility views are documented and considered stable
- [ ] Decision made on schema versioning (explicit key vs implicit evolution)
- [ ] `config init`, `defaults`, `check`, `dump` produce aligned outputs (text, markdown, machine)
- [ ] Decision made and documented on where config overrides (`MutableConfig.apply_args`) live and
  how API callers apply overrides
- [ ] Packaging/project metadata policy documented and considered stable (license metadata, URLs,
  classifiers, README rendering)
- [x] `uv.lock` is established as the canonical lock artifact and the repository no longer depends
  on exported requirements/constraints files for normal operation
- [ ] `EmptyInsertMode` tokens and semantics documented and considered stable

### Pipeline & testing

- [ ] Decision taken on in-memory pipeline support (implemented or deferred)
- [x] CI validates docs integrity at both source and built-site levels (including generated API
  pages)
- [x] Docs pipeline robust against mdformat normalization of GitHub alerts/callouts
- [ ] Clear split between unit (memory-based) and integration (filesystem) tests
- [ ] Namespace-aware registry lookup and deterministic ambiguity behavior covered by tests across
  config, registry, and resolution layers
- [ ] High-coverage tests for edge cases (encoding, synthetic names, and remaining empty-like
  variants)
- [x] Empty and empty-like file handling is explicit and idempotent (BOM-only, newline-only,
  whitespace-only placeholder cases)
- [x] Resolver treats content matcher exceptions as safe misses (does not abort resolution)
- [x] Preview vs apply semantics are consistent end-to-end (write statuses, bucketing, and
  summaries)
- [ ] API surface clarified for in-memory pipeline inputs (either implemented or deferred with
  rationale)

### Dependency & ecosystem

- [ ] Decision made on long-term CLI framework (Click vs alternative)
- [ ] Decision made on color backend (`yachalk` confinement or removal)
- [x] Canonical dependency workflow migrated to `pyproject.toml` + `uv.lock` with no remaining
  dependence on exported requirements/constraints files for normal development, CI, or release flows
- [ ] Decide whether the explicit local-key compatibility view in `FileTypeRegistry` should remain a
  supported 1.0 feature or be reduced further in favor of canonical qualified-key-only operation
- [ ] Decide whether duplicated built-site docs/linkcheck steps in CI and release workflows should
  remain inline or eventually be factored into a reusable workflow
- [ ] Formatter/tool configuration split stabilized and documented (.mdformat.toml, .taplo.toml,
  pyproject ownership boundaries)
- [ ] Tooling environments (Nox, pre-commit, local venv, editor) verified to consume the same
  formatter plugin set
- [x] Read the Docs uv-based installation/build path verified and documented as stable

Only when all checklist items are either completed or explicitly deferred with rationale should 1.0
be tagged.
