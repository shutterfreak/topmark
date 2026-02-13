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
buffers, CI-provided snippets, or API-driven integrations. Today, almost all of TopMark’s
processing pipeline assumes filesystem I/O, which makes testing heavier, limits reuse, and
complicates future integrations.

Supporting an in-memory pipeline enables:

- Faster, more isolated tests without filesystem setup/teardown
- Cleaner API boundaries (pipeline as a pure transformation)
- Future integrations (editors, LSPs, CI bots) without temporary files
- Clearer separation between what TopMark does and how input is obtained

______________________________________________________________________

## Done so far

This section tracks work completed during the 0.12 development series that directly supports the
1.0 goals.

### CLI output architecture

- Introduced a clearer split between:
  - \[`topmark.cli.emitters.*`\][topmark.cli.emitters] (Click-facing, console printing)
  - \[`topmark.cli_shared.*`\][topmark.cli_shared] (Click-free CLI concerns: presentation helpers, color policy, small shared utilities)
- Refactored many commands to share the same conceptual pipeline:
  - prepare Click-free model → render (text/markdown) → print
- Introduced shared Click-layer validators/policies (\[`topmark.cli.validators`\][topmark.cli.validators]) to centralize:
  - output-format policies (e.g., diff restrictions, machine-format limitations)
  - file-agnostic command behaviors (ignoring positional paths)
  - color policy enforcement for non-text outputs
- Moved verbosity (`-v`) and color (`--color/--no-color`) options from the root CLI group to individual commands.
- Added a convenience decorator to consistently attach common verbosity/color options per command.
- Clarified and centralized CLI initialization state in `cli.cmd_common`.
- Moved all machine-format generation out of `cli_shared` into domain-specific `*.machine` packages.
- Replaced legacy "emitters" with explicit `serializers` in core/config/pipeline/registry layers.
- Introduced a clear separation between:
  - pure serializers (no console, no Click)
  - CLI emitters (console-only, Click-aware)
- Centralized `build_meta_payload()` at CLI initialization (computed once per process and reused).
- Introduced `compute_version_text()` in `utils.version` to unify SemVer conversion and fallback logic across CLI and machine formats.

### Pipeline semantics: preview vs apply

- Made write-status reporting **honest** and consistent across dry-run and apply pipelines:
  - Dry-run now emits `WriteStatus.PREVIEWED` (no terminal verbs like “removed” / “replaced”).
  - Apply mode (`--apply`) emits terminal statuses (`INSERTED`, `REPLACED`, `REMOVED`) and writers perform the actual filesystem updates.
- Plumbed apply intent end-to-end:
  - Added `Config.apply_changes` as a tri-state runtime intent and ensured CLI + API set it on the final merged config.
  - Updated the updater step to gate terminal `WriteStatus` values on `apply_changes`.
  - Refined bucketing/outcomes so “would change” vs “changed” categories align with apply intent and reasons match the established convention.
- Updated human summaries (`ProcessingContext.format_summary`) so dry-run output is no longer misleading (e.g., “would strip header” without claiming it was removed).

### Human output formats

- Consolidated human formats under:
  - `OutputFormat.TEXT` (label `"text"`)
  - `OutputFormat.MARKDOWN`
- Renamed emitter package *topmark.cli.emitters.default* to \[`topmark.cli.emitters.text`\][topmark.cli.emitters.text] to align naming with `OutputFormat.TEXT`.
- Extracted shared pipeline rendering primitives (diff rendering, per-command guidance)
  into \[`topmark.cli_shared.emitters.shared.pipeline`\][topmark.cli_shared.emitters.shared.pipeline].
- Improved consistency of wording across commands by reusing shared helpers for registry/config outputs.

### Command output consistency improvements

- `processors` and `filetypes` human output now uses **numbered lists** (right-aligned indices) and clearer counts.
- `dump-config` / `init-config` emit **plain TOML** by default; BEGIN/END markers are shown only at higher verbosity.
- `version` command output is now script-friendly (prints only the SemVer string, no label).
- Documentation updated across command pages to match the new verbosity and summary semantics.

### Machine output formats

Machine-readable output is now domain-scoped and schema-driven, with consistent envelopes and stable keys across commands.

- Shared payload shapes and builders under \[`topmark.config.machine`\][topmark.config.machine] and related modules
- Consistent envelope structures (metadata + data) across commands
- Aligned semantics for config, registry, and version commands

The remaining gaps are primarily in pipeline-oriented commands (`check`, `strip`), where
historical CLI-specific emitters are still being phased out in favor of shared serializers.

The 1.0 goal is full symmetry:

- identical field names and structure across commands
- no ad-hoc JSON construction inside CLI modules
- machine formats completely independent from color, verbosity, or human formatting concerns

Completed work:

- Completed full separation of machine-format responsibilities into domain-specific packages:
  - \[`topmark.core.machine`\][topmark.core.machine] (shared keys/schemas/meta payloads)
  - \[`topmark.config.machine`\][topmark.config.machine] (config-related shapes and serializers)
  - \[`topmark.pipeline.machine`\][topmark.pipeline.machine] (processing results shapes and serializers)
  - \[`topmark.registry.machine`\][topmark.registry.machine] (filetype and processor registry shapes and serializers)
- Removed ad-hoc JSON construction from CLI command modules (`check`, `strip`, `config_*`, `filetypes`, `processors`, `version`).
- Standardized naming conventions:
  - `build_*` → payload construction (pure data)
  - `build_*_envelope` / `iter_*_records` → shape builders
  - `serialize_*` → JSON/NDJSON serialization (no console I/O)
  - `emit_*` → CLI-layer console output only
- Introduced shared NDJSON prefix builders for config + config_diagnostics records to avoid duplication across commands.
- Centralized machine keys and canonical values in \[`topmark.core.machine.schemas`\][topmark.core.machine.schemas], eliminating circular imports and key drift.
- Added explicit `MachineMeta` keys and extended the `meta` payload with `platform` information.
- Introduced typed `TypedDict` schemas for:
  - outcome summary entries and records (pipeline)
  - filetype registry entries
  - processor registry entries
- Documented the stable envelope and key conventions in `docs/dev/machine-formats.md` (and updated command pages accordingly).

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

### Documentation: pipeline docs + generated API internals

- Added pipeline documentation under `docs/dev/`:
  - `pipelines.md` (concepts): Mermaid diagrams for the pipeline overview, CLI flows (`check` vs `strip`), and per-axis lifecycles.
  - `pipelines-reference.md` (reference hub): formatter-safe links into generated internals pages (no `mkdocstrings` directives).
- Introduced `mkdocs.linkcheck.yml` to support local/CI link checking without baking production-only base URLs.
- Clarified the documentation authoring rule: handwritten Markdown must not contain `mkdocstrings` directives; generated pages own all `:::` blocks.

### CI + link checking hardening (docs integrity)

- Added a built-site link check (`links-site`) that validates the rendered MkDocs HTML output, including generated API pages.
  - Uses `mkdocs.linkcheck.yml` and runs `lychee` against `site/` with `--root-dir` to resolve root-relative links.
- Updated GitHub Actions workflows to gate releases on built-site link integrity:
  - CI: conditional `links` (source Markdown) + `links-site` (built site) based on detected docs changes.
  - Release: publishing is gated on `links-site`.
- Updated CI documentation pages to reflect the new “docs integrity” model and to explicitly note that generated API pages are only validated via `links-site`.
- Hardened resolver behavior: exceptions in file type `content_matcher` functions are treated as misses (not failures), preserving resolution safety.

### Developer automation: nox + uv (tox removal)

- Migrated project automation from tox to nox and removed `tox.ini`.
- Added `noxfile.py` sessions for formatting, linting, docs build, QA (pytest + pyright), API snapshot, link checks, packaging checks, and release gates.
- Switched to uv-backed environments to reduce env creation and dependency install time.
- Updated Makefile targets to call nox sessions (including parallel QA via `make -j`).
- Made `noxfile.py` import-time TOML parsing robust on Python < 3.11 (`tomllib`/`tomli` fallback).
- Hardened lychee invocation for large file lists by chunking arguments to avoid command line length limits.

### Compatibility and release hygiene

- Fixed a Python < 3.12 incompatibility caused by multiline f-strings in CLI output code paths.
- Updated pre-commit hook recommendations to rely on the default terse output.
- Improved internal debug logging around bucket mapping and summary formatting.

______________________________________________________________________

## Breaking changes introduced so far

These are changes already landed (or expected to land) during the 0.12 refactor series.

### CLI / output format changes

- Output format rename: `DEFAULT` was removed and replaced by `TEXT`
  (label now `"text"`).
- Emitter package rename:
  *topmark.cli.emitters.default* → \[`topmark.cli.emitters.text`\][topmark.cli.emitters.text].
- Shared pipeline helpers moved to
  \[`topmark.cli_shared.emitters.shared.pipeline`\][topmark.cli_shared.emitters.shared.pipeline].
- Verbosity and color options were moved from the root CLI group to individual commands.
  Global invocation patterns may need to be updated.
- Color behavior tightened:
  - color is only meaningful for `OutputFormat.TEXT`
  - non-text formats ignore color requests and may warn (policy is centralized in validators)
- Dry-run summaries now end with `- previewed` instead of terminal verbs; apply runs show `- inserted` / `- replaced` / `- removed`.

### Documentation build behavior

- Documentation build now depends on Markdown output paths for registry/pipeline commands. Missing
  emitter modules will fail the docs build (`mkdocs build --strict`).
- CI now performs built-site link checks (`links-site`) during release gating; link validation failures may block publishing.

### Developer tooling / CI

- tox support removed; contributors and CI must use `nox` (and uv-backed envs) going forward.

______________________________________________________________________

## Still undecided / still to do

This section lists remaining 1.0 decisions and implementation work. Items are grouped by theme.

### In-memory pipeline (Option A)

#### Status

- Design: drafted and reviewed
- Implementation: not started
- Target window: post-0.12, before 1.0 feature freeze

Goal: enable TopMark to run the existing processing pipeline on **in-memory** inputs (strings or
bytes) without restructuring the pipeline architecture or changing the default file-based CLI behavior.

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

- **File-type detection**: Some file types rely heavily on filename or path semantics.
  In-memory inputs must either provide a synthetic name or accept reduced detection
  fidelity in edge cases.
- **Synthetic paths**: Introducing fake or sentinel paths risks accidental assumptions
  in downstream code (e.g. path arithmetic, parent traversal).
- **Behavior parity**: Ensuring identical behavior between file-based and memory-based
  pipelines requires disciplined reuse of sniffers, matchers, and policies.

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
- Ensure the final `FileType` selection matches file-based behavior when given equivalent name/content.

##### Reader

Current responsibility: read file bytes/text from disk.

In-memory variant:

- No I/O. Populate the same context fields that the file reader would populate
  (e.g. `original_text`, `newline`, `encoding`, etc.)

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
- Consolidate overlapping tests that currently exercise the same logic via different filesystem setups
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

### API vs CLI separation

#### Status

Some CLI-oriented concerns still leak into API-facing modules (notably in \[`topmark.config`\][topmark.config]
and parts of pipeline orchestration).

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

Today, `MutableConfig.apply_args()` lives in \[`topmark.config.model`\][topmark.config.model] and applies a generic `ArgsLike`
mapping (CLI or API) directly onto the config. This keeps CLI and API behavior aligned, but it also
introduces CLI-shaped concepts (argument keys and CLI option semantics) into a core module.

Decision to make before 1.0:

- Keep `MutableConfig.apply_args()` in core config (but narrow the surface and decouple from CLI keys), or
- Move override application to a CLI-shared semantics layer (Click-free), or
- Introduce a typed overrides model (e.g., *topmark.config.overrides*) that CLI/API construct, and core applies.

Desired outcome:

- Core config loading/merging stays reusable and independent of CLI concerns.
- CLI parsing/normalization produces a clear override structure.
- The same override structure remains usable by API callers (without importing Click).

### Machine output formats

Machine formats are now fully centralized and domain-scoped.

Completed work:

- Pipeline commands (`check`, `strip`) use \[`topmark.pipeline.machine`\][topmark.pipeline.machine] shape builders and serializers.
- Registry commands (`filetypes`, `processors`) use \[`topmark.registry.machine`\][topmark.registry.machine].
- Config commands (`init`, `defaults`, `dump`, `check`) use \[`topmark.config.machine`\][topmark.config.machine].
- Version command uses \[`topmark.core.machine`\][topmark.core.machine] serializers with shared meta handling.
- All commands emit identical envelope structures for JSON and NDJSON.
- CLI modules no longer construct machine payloads directly.

Remaining work before 1.0:

- Final audit of field naming consistency across domains.
- Expand test coverage for machine formats (especially registry + pipeline commands, JSON + NDJSON).
- Stabilize and freeze machine schema documentation (`docs/dev/machine-formats.md`).

### Human-facing output formats

Text (ANSI) and Markdown output formats have been refactored for most commands,
with shared Click-free renderers and centralized CLI policy enforcement.

Remaining work before 1.0:

- Ensure `OutputFormat.TEXT` and `OutputFormat.MARKDOWN` are consistent across commands.
- Ensure verbosity semantics are consistent (`-v`, `-vv`, `-q`) and documented.
- Keep all formatting logic out of CLI command functions.

### Pipeline commands: complete human + machine format refactor

- Finish aligning `check` and `strip` outputs with the established pattern:
  - shared Click-free preparation
  - text emitter (`cli.emitters.text.*`)
  - Markdown emitter (`cli_shared.emitters.markdown.*`)
  - machine serializers for JSON/NDJSON
- Confirm and document verbosity semantics consistently across all commands:
  - `-v`: show per-file guidance / extra hints
  - `-vv`: show detailed diagnostics / expanded sections
- Confirm that no `yachalk` imports remain outside CLI-facing modules
  once color-boundary cleanup is completed.

### CLI framework choice: Click vs Rich

Recommendation: keep Click through 1.0 unless there is a strong feature need.

### Color output and dependency on yachalk

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

### Policy model and operation modes

TopMark currently processes all resolved and supported file types by default.

Open questions for 1.0:

- Should the default mode remain “process all supported types”?
- Should we introduce a stricter whitelist-first mode (e.g. Python, Markdown, TOML only)?
- How should policies interact with file-type inclusion/exclusion at scale?

Any change here should preserve backward compatibility unless explicitly gated.

______________________________________________________________________

## 1.0 readiness checklist

This checklist defines the minimum criteria for cutting TopMark 1.0.

### Architecture & boundaries

- [ ] Clear separation between CLI layer and API/core modules
- [ ] No CLI-specific concerns (verbosity, color, formatting) in core logic
- [x] All machine-format payloads built outside CLI command modules
- [ ] Color handling either fully confined to CLI or replaced by semantic tokens

### Machine formats

- [x] JSON and NDJSON schemas fully aligned across all commands
- [x] Identical envelope structure (metadata + data) everywhere
- [x] Machine payload construction removed from CLI command modules
- [ ] Documented examples for each command category in `docs/dev/machine-formats.md`
- [ ] No presentation leakage (color text, human wording) in machine output
- [ ] Machine outputs are covered by tests for registry commands (`filetypes`, `processors`) and pipeline commands (`check`, `strip`) in both JSON and NDJSON modes
- [ ] Final schema freeze review before 1.0

### Human formats

- [ ] `OutputFormat.TEXT` and `OutputFormat.MARKDOWN` consistent across commands
- [ ] Verbosity levels (`-v`, `-vv`, `-q`) documented and behave consistently
- [ ] Diff rendering policy consistent across pipeline commands
- [ ] Warnings and error phrasing consistent across CLI

### CLI behavior

- [x] Global options correctly scoped to commands (verbosity, color)
- [x] Validators centralized and consistently applied
- [ ] Exit codes documented and stable (audit after preview/apply status changes and bucketing fixes)
- [ ] Help output accurate and aligned with implemented behavior
- [x] Meta payload initialized once per process and reused across commands

### Configuration

- [ ] Config keys and semantics documented and considered stable
- [ ] Decision made on schema versioning (explicit key vs implicit evolution)
- [ ] `config init`, `defaults`, `check`, `dump` produce aligned outputs (text, markdown, machine)
- [ ] Decision made and documented on where config overrides (`MutableConfig.apply_args`) live and how API callers apply overrides

### Pipeline & testing

- [ ] Decision taken on in-memory pipeline support (implemented or deferred)
- [x] CI validates docs integrity at both source and built-site levels (including generated API pages)
- [ ] Clear split between unit (memory-based) and integration (filesystem) tests
- [ ] High-coverage tests for edge cases (encoding, empty files, synthetic names)
- [x] Resolver treats content matcher exceptions as safe misses (does not abort resolution)
- [x] Preview vs apply semantics are consistent end-to-end (write statuses, bucketing, and summaries)
- [ ] API surface clarified for in-memory pipeline inputs (either implemented or deferred with rationale)

### Dependency & ecosystem

- [ ] Decision made on long-term CLI framework (Click vs alternative)
- [ ] Decision made on color backend (`yachalk` confinement or removal)
- [ ] No unnecessary runtime dependencies remaining

Only when all checklist items are either completed or explicitly deferred with rationale should 1.0 be tagged.
