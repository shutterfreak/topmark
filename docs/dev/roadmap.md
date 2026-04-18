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
goals, including the registry refactor, CLI/presentation architecture cleanup, configuration/runtime
split, machine-format stabilization, and the transition to SCM-driven versioning and artifact-based
release workflows.

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

- Replaced the older split between *topmark.cli.emitters* and *topmark.cli_shared* with a clearer
  three-layer structure:
  - `topmark.presentation.*` → Click-free, human-facing report preparation and rendering
  - `topmark.cli.console.*` → console/runtime concerns (printing, color policy, width helpers)
  - `topmark.cli.commands.*` → command orchestration and final output
- Refactored many commands to follow the same conceptual pipeline:
  - prepare Click-free report/model → render string (TEXT/MARKDOWN) → print via console
- Introduced shared Click-layer validators/policies
  (\[`topmark.cli.validators`\][topmark.cli.validators]) to centralize:
  - output-format policies (e.g., diff restrictions, machine-format limitations)
  - file-agnostic command behaviors (ignoring positional paths)
  - color policy enforcement for non-text outputs
- Moved verbosity (`-v`) and color (`--color/--no-color`) options from the root CLI group to
  individual commands.
- Added a convenience decorator to consistently attach common verbosity/color options per command.
- Clarified and centralized CLI initialization state in `cli.cmd_common`, while keeping
  machine-output metadata derivation explicit at the command boundary.
- Reorganized console/runtime support under \[`topmark.cli.console`\]\[topmark.cli.console\]:
  - `ConsoleProtocol` as the minimal console contract
  - Click-backed `Console` and stdlib `StdConsole`
  - `resolve_console()` for safe context-aware console resolution
  - `ColorMode` / `resolve_color_mode()` and terminal width helpers
- Removed console abstractions from human renderers:
  - renderers no longer print directly
  - console usage is now confined to command modules and console/runtime helpers
- Moved all machine-format generation out of CLI-shared helpers into domain-specific `*.machine`
  packages.
- Replaced legacy "emitters" with explicit `serializers` in core/config/pipeline/registry layers.
- Introduced a clear separation between:
  - pure serializers (no console, no Click)
  - pure human renderers (no console, no I/O)
  - CLI output/runtime helpers (console-only, Click-aware)
- Kept `build_meta_payload()` as a cached, process-stable machine metadata helper and introduced
  command-local enrichment (for example `detail_level`) when machine output is emitted.
- Introduced `compute_version_text()` in `utils.version` and later `VersionHumanReport` /
  `render_*()` flow to unify version rendering across CLI and machine formats.

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

### Runtime split: preview vs apply and execution intent

- Made write-status reporting **honest** and consistent across dry-run and apply pipelines:
  - Dry-run now emits `WriteStatus.PREVIEWED` (no terminal verbs like “removed” / “replaced”).
  - Apply mode (`--apply`) emits terminal statuses (`INSERTED`, `REPLACED`, `REMOVED`) and writers
    perform the actual filesystem updates.
- Plumbed apply intent end-to-end and then completed the runtime split:
  - runtime-only execution intent no longer lives in layered `Config`
  - `RunOptions` now carries execution-time behavior such as apply mode and STDIN/content handling
  - CLI and API now thread `run_options` separately from frozen `Config`
  - the updater step still gates terminal `WriteStatus` values on apply intent, but that intent is
    now part of runtime state rather than layered config
  - bucketing/outcomes now align cleanly with preview vs apply semantics
- Updated human summaries (`ProcessingContext.format_summary`) so dry-run output is no longer
  misleading (e.g., “would strip header” without claiming it was removed).

### Config/TOML/runtime split: layered resolution, source-local TOML options, and API/CLI parity

- Completed the split of configuration concerns into three clearer layers:
  - `topmark.toml.*` owns TOML loading, parsing, defaults/template resources, source resolution,
    rendering, and TOML-specific surgery/helpers
  - `topmark.config.*` owns layered config data shapes, config-layer construction, merge semantics,
    and effective per-path config resolution
  - `topmark.runtime.*` owns execution-only runtime state (`RunOptions`) and persisted writer
    preferences (`WriterOptions`)
- Removed duplicated config resolution logic from the CLI path:
  - deleted `topmark.cli.config_resolver`
  - updated `topmark.cli.cmd_common.build_config_for_plan()` to call config-layer helpers directly
  - made `--no-config` behavior consistent with the intended semantics of skipping all discovered
    config layers
- Added `mutable_config_from_mapping()` so API/runtime code no longer routes generic Python mappings
  through TOML-named helpers.
- Completed the TOML/config boundary cleanup around layered fragment deserialization:
  - introduced `mutable_config_from_layered_toml_table()` as the canonical config-layer entry point
  - removed the older `mutable_config_from_toml_dict()` compatibility path after callers/tests were
    migrated
  - clarified in code and docs that whole-source TOML validation belongs to `topmark.toml`, while
    layered value parsing and defensive normalization belong to `topmark.config`
- Updated `topmark.api.runtime` so API-side config/file preparation now mirrors the same
  TOML-resolution / config-merge / runtime-overlay split as the CLI:
  - TOML sources are resolved first
  - layered config is built from those resolved TOML sources
  - explicit seeded mode remains available when API callers provide a mapping or frozen `Config`
  - final runtime intent is applied separately from layered config merging
- Removed remaining non-model TOML/render convenience methods from `MutableConfig` and moved call
  sites to dedicated config I/O helpers.
- Renamed `ArgsLike` to `ConfigMapping` and moved it to `topmark.api.types` so the accepted public
  API mapping shape is named from the API/config domain rather than from CLI argument handling.
- Removed the legacy `ArgsLike` alias entirely and standardized all API/config entry points on
  `ConfigMapping`, eliminating ambiguity between CLI argument shapes and generic configuration
  mappings.
- Moved generic merge helpers out of `topmark.config.model` into shared utility code, further
  reducing coupling between config data models and reusable collection-merging helpers.
- Updated documentation and tests so the refactored TOML/config/runtime module layout and helper
  names are reflected consistently across CLI, API, and config-resolution paths.
- Completed the config override model refactor around typed override objects instead of ad-hoc
  CLI/API keyword plumbing:
  - introduced `PolicyOverrides` / `ConfigOverrides` in `topmark.config.overrides`
  - refactored `apply_config_overrides(...)` to consume structured overrides
  - aligned CLI and API override application on the same config-layer helper path
  - Clarified the separation between CLI argument parsing and config-layer application by ensuring
    that CLI-specific argument namespaces are no longer propagated into config models, reinforcing a
    clean API/CLI boundary.
- Replaced the older boolean header-mutation policy flags (`add_only`, `update_only`) with the
  scalar `header_mutation_mode` policy model:
  - updated mutable/frozen policy models
  - updated TOML deserialization/serialization and documented example config
  - updated CLI/API-facing policy overlay handling
- Introduced split parsing of TopMark TOML sources:
  - layered config TOML fragments are extracted separately from source-local TOML options
  - source-local options such as `[config].root` and `strict_config_checking` are resolved outside
    `ConfigLayer` merging
  - normal discovered config loading now behaves as layered-config-only merging, with TOML
    source-local metadata resolved in parallel
  - Introduced explicit config validation semantics and strictness control:
    - added `Config.is_valid(...)`, `Config.ensure_valid(...)`, and `_is_config_valid(...)` helpers
      with a consistent validation contract
    - introduced `ConfigValidationError` and extended `ErrorContext` to carry validation diagnostics
      and strictness metadata
    - validation is now always executed, with strictness (`strict_config_checking`) controlling
      whether violations raise or are only reported
    - aligned CLI (`config check`) and API validation behavior on the same validation path and error
      model
  - Completed migration away from compatibility config-loading facades:
    - removed `load_resolved_config()` and `discover_config_layers()` in favor of the TOML-first
      resolution flow
    - standardized all callers on `resolve_toml_sources_and_build_config_draft(...)` and explicit
      layer-building helpers
    - clarified naming and documentation to consistently refer to “mutable config drafts” instead of
      “compatibility drafts”
  - Added explicit whole-source TOML schema validation before layered config deserialization:
    - unknown top-level sections/keys, unknown keys in known sections, and malformed section shapes
      are now validated in `topmark.toml`
    - source-local TOML sections such as `[config]` and `[writer]` are validated on the TOML side
      and no longer rely on duplicate config-layer checks
    - validation issues are propagated into config diagnostics so CLI/API validation paths report
      TOML schema problems alongside config-layer diagnostics
- Added layered configuration provenance export for `config dump`:
  - `topmark config dump --show-layers` now emits an inspection-oriented layered TOML export before
    the final flattened effective config
  - layered human output now preserves source-local TopMark TOML fragments under `[[layers]].toml.*`
  - machine-readable `config dump` output now supports `config_provenance` in JSON and NDJSON when
    `--show-layers` is enabled
  - machine and human layered exports preserve ordering semantics (defaults first, then resolved
    TOML sources, then the final flattened config snapshot)
- Config-loading entry points were consolidated around TOML-first resolution:
  - callers must now explicitly handle the `(resolved_sources, draft_config)` tuple when provenance
    is needed
  - direct “flattened config only” helpers are no longer provided
- Strengthened TOML/config typing boundaries by introducing recursive TOML value/table typing and
  centralizing validation/narrowing helpers in config I/O support modules.
- Completed relocation of TOML-specific helpers and resources out of `topmark.config`:
  - default/example TOML resources now live under `topmark.toml`
  - TOML enums, utilities, typing helpers, template surgery, and defaults/document helpers now live
    under `topmark.toml.*`
  - `config.io` is now focused on config deserialization/serialization rather than generic TOML
    document handling

### Config layering: provenance-aware merge semantics, per-path resolution, and TOML-first draft construction

- Introduced provenance-aware config layering using explicit config layers and per-field merge
  semantics.
- Refactored `MutableConfig.merge_with()` to implement field-specific behavior:
  - accumulate: provenance (`config_files`), diagnostics, discovery inputs (`include_from`,
    `exclude_from`, `files_from`)
  - nearest-non-empty wins: scalar and list fields (e.g. `header_fields`, `files`, file-type
    filters)
  - key-wise overlay: mapping fields (`field_values`, `policy_by_type`)
- Added explicit pattern provenance via `PatternSource` and pattern groups, enabling correct scoping
  of include/exclude logic.
- Introduced per-path effective config resolution:
  - layered discovery → applicable layer selection → per-path merge
  - engine now consumes path-specific effective configs instead of a single flattened config
- Added focused regression tests to lock down merge semantics invariants and prevent regressions.
- Added engine-level tests to verify correct application of per-path configs and policy registry
  behavior.
- Optimized pipeline engine to avoid constructing unused shared `PolicyRegistry` instances when
  path-specific configs are provided.
- Clarified the conceptual split between:
  - file-backed layered configuration (provenance-aware, per-path)
  - runtime execution intent (CLI/API overlays such as `apply_changes`, `stdin_*`, output settings)
- Introduced API/runtime helpers that apply runtime overlays **after** layered config resolution,
  rather than mixing them into config merging.
- Completed the bridge from TOML-side resolution to config-layer merge through
  `resolve_toml_sources_and_build_config_draft(...)`, which now acts as the main integration point
  between TOML source resolution and layered config draft construction.

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
- Replaced the legacy mutually-exclusive `add_only` / `update_only` booleans with the scalar
  `HeaderMutationMode` runtime/config model:
  - `all`
  - `add_only`
  - `update_only`
- Unified policy override routing so both CLI and API public policy overlays now flow through the
  same `ConfigOverrides` / `PolicyOverrides` application path before freezing the config.
- Added shared policy documentation and clarified command applicability:
  - `check` exposes mutation/insertion policy options plus shared resolver policy
  - `strip` exposes only the shared resolver/content-probe policy

### Registry output formats: qualified identifiers in machine and human output

- Updated \[`topmark.registry.machine`\][topmark.registry.machine] payloads and schemas so registry
  machine formats now emit namespace-aware, identity-focused data:
  - file type entries now use `local_key`, `namespace`, and `qualified_key`
  - processor entries now use `local_key`, `namespace`, and `qualified_key`
  - bindings are now exposed as a first-class machine format via `topmark registry bindings`
- Refactored registry machine formats to align with the split registry model:
  - `filetypes` reports file type identities and matching/policy metadata
  - `processors` reports processor identities and delimiter capabilities
  - `bindings` reports effective file-type-to-processor relationships plus auxiliary lists for
    unbound file types and unused processors
- Extended machine metadata with `detail_level` so JSON and NDJSON explicitly distinguish brief vs
  long projections instead of requiring consumers to infer shape.
- Updated human-facing registry renderers and shared Click-free registry report builders so registry
  output is now split cleanly along the same three concerns:
  - file types → identity-focused
  - processors → identity-focused
  - bindings → relationship-focused
- Fixed file type policy handling in registry output:
  - header policy metadata is now exposed and rendered as structured fields rather than via raw
    `str(...)` conversion of policy objects
  - file type policy defaults are now initialized consistently in the model/factory so built-in file
    type modules compose reliably during registry startup
- Updated plugin/API-facing documentation to explain:
  - qualified vs unqualified file type identifiers
  - ambiguity of unqualified names once multiple namespaces are present
  - runtime processor overlay registration against qualified file type identifiers
  - the split between file type identities, processor identities, and effective bindings

### Human output formats

- Consolidated human formats under:
  - `OutputFormat.TEXT` (label "text")
  - `OutputFormat.MARKDOWN`
- Introduced the new `topmark.presentation` package as the canonical home for **Click-free,
  human-facing rendering**:
  - `topmark.presentation.shared.*` → report models and preparation helpers
  - `topmark.presentation.text.*` → TEXT renderers
  - `topmark.presentation.markdown.*` → MARKDOWN renderers
- Completed migration away from legacy CLI emitters for version, config, diagnostic, pipeline, and
  registry-related human output paths:
  - removed migrated `topmark.cli.emitters.*` / `topmark.cli_shared.emitters.*` paths in favor of
    `topmark.presentation.*`
  - replaced `emit_*()` helpers with pure `render_*()` helpers returning strings
- Standardized the rendering pipeline across commands:
  - API/domain → presentation report (`*HumanReport`) → `render_*()` → CLI prints
- Ensured all renderers are:
  - Click-free (no console dependency)
  - side-effect free (no I/O)
  - reusable from tests and API contexts
- Moved shared formatting utilities into `topmark.presentation.formatters.*` and format-specific
  `utils` modules
- Removed console abstractions from rendering logic:
  - styling is now applied via semantic roles (`StyleRole`) and helper functions
  - console is only responsible for final output (`console.print(...)`)
- Completed the registry human-output split along the three registry concerns:
  - `registry filetypes` → file type identity and policy-oriented output
  - `registry processors` → processor identity and delimiter-oriented output
  - `registry bindings` → effective relationship-oriented output
- Improved consistency of wording and structure across commands by reusing shared presentation
  helpers

### Command output consistency improvements

- `processors` and `filetypes` human output now uses **numbered lists** (right-aligned indices) and
  clearer counts.
- `config dump`, `config defaults`, and `config init` emit **plain TOML** by default; BEGIN/END
  markers are shown only at higher verbosity.
- `version` command output is now script-friendly (prints only the SemVer string, no label).
- Documentation updated across command pages to match the new verbosity and summary semantics.

### Machine output formats

Machine-readable output is now domain-scoped and schema-driven, with consistent envelopes and stable
keys across commands.

- Shared payload shapes and builders under \[`topmark.config.machine`\][topmark.config.machine] and
  related modules
- Consistent envelope structures (metadata + data) across commands
- Aligned semantics for config, registry, and version commands

The remaining gaps are now mostly schema freeze, naming audits, and coverage expansion rather than
architectural separation work.

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
  - \[`topmark.registry.machine`\][topmark.registry.machine] (filetype, processor and binding
    registry shapes and serializers)
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
- Renamed machine key `strict` to `strict_config_checking` for config diagnostics payloads to align
  with CLI/config terminology and avoid ambiguity with other “strict” concepts
- Added explicit machine keys/kinds and extended the `meta` payload with:
  - `platform` runtime information
  - `detail_level` (`"brief"` / `"long"`) as part of the machine contract
- Introduced typed `TypedDict` schemas for:
  - outcome summary entries and records (pipeline)
  - file type registry entries
  - processor registry entries
  - binding registry entries and auxiliary reference rows
- Documented the stable envelope and key conventions in `docs/dev/machine-formats.md` (and updated
  command pages accordingly).
- Extended config machine output to support layered provenance inspection:
  - layered provenance is currently exposed only via `config dump --show-layers`; other config
    commands (e.g. `config check`) intentionally remain validation-focused and do not emit
    provenance
  - added `config_provenance` as a stable machine key/kind for `config dump --show-layers`
  - JSON now emits `config_provenance` before the final flattened `config` payload when layered
    provenance is requested
  - NDJSON now emits a `config_provenance` record first and a `config` record second in layered
    provenance mode
  - added dedicated contract tests for `config dump` machine output in both JSON and NDJSON modes,
    including defaults-layer ordering and TOML-fragment shape checks

### Config template handling

- Strengthened config template handling for `config init` / `config defaults` by applying
  conservative, string-based edits followed by TOML validation.
- Fixed the `config init --pyproject` flow so the bundled example TopMark TOML resource is edited in
  plain TOML shape first, then nested under `[tool.topmark]`.
- Updated template handling and validation to use `[config]` / `[tool.topmark.config]` for
  source-local options such as `root`.

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

- Completed a broad documentation alignment pass across README, configuration docs, CLI command
  guides, API docs, internals, architecture, policies, machine-output docs, and contributor docs so
  they now consistently describe:

  - the TOML → Config → Runtime architecture
  - whole-source TOML schema validation before layered config deserialization
  - `[config]` / `[tool.topmark.config]` placement for source-local TOML options
  - layered provenance as the validated source-local TOML view plus the final flattened config
  - `config defaults` as the built-in layered default config view
  - `config init` as the bundled example TopMark TOML resource

- Reorganized test support code around explicit helper modules instead of accumulating logic in
  `conftest.py` files:

  - added focused shared helper modules under `tests/helpers/*`
  - split TOML-layer helpers from pytest-facing wrappers in `tests/toml/conftest.py`
  - aligned test module structure with the TOML/config/runtime architectural split

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

### GitHub Actions: artifact-based release pipeline (CI → release split)

- Reworked the GitHub Actions release model to follow an **artifact-based CI → release split**:
  - `ci.yml` now builds release artifacts (`sdist` and `wheel`) on tag pushes in an **unprivileged
    context** and uploads them as workflow artifacts.
  - `release.yml` runs only via `workflow_run` after CI completes successfully and operates in a
    **privileged context**.
- Removed repository checkout and build execution from privileged release jobs:
  - release workflow now downloads CI-produced artifacts instead of rebuilding the project
  - prevents execution of repository code in privileged contexts
- Introduced explicit release-artifact metadata and validation:
  - tag, normalized PEP 440 version, and checksums are generated in CI
  - release workflow validates artifact version against the tag and verifies integrity before
    publishing
- Simplified release responsibilities:
  - CI is responsible for **build + validation + artifact creation**
  - release workflow is responsible for **verification + publish + GitHub release creation**
- Aligned the workflow design with GitHub security best practices and CodeQL recommendations for
  `workflow_run`-based privileged workflows.

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

### Versioning model: Git-tag-based SCM versioning

- Replaced static version management in `pyproject.toml` with a **single-source-of-truth SCM
  model**:
  - removed manually maintained `[project].version`
  - enabled `dynamic = ["version"]`
  - integrated `setuptools-scm` for build-time version derivation
- Configured generation of `topmark/_version.py` during build, embedding:
  - resolved version string
  - version tuple
  - commit identifier
- Updated runtime version resolution:
  - `topmark.constants` now prefers `_version.py`
  - optional fallback to `importlib.metadata` when needed
- Standardized Git tag conventions:
  - preferred: compact PEP 440 forms (`vX.Y.Z`, `vX.Y.ZaN`, `vX.Y.ZrcN`)
  - legacy dashed prerelease tags remain supported for compatibility
- Refactored release workflow validation:
  - removed comparison against static `pyproject.toml` version
  - now validates SCM-derived artifact version against the release tag
- Updated documentation and contributor guidance:
  - no manual version bump step remains
  - release process is fully tag-driven

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

### Pre-1.0 stabilization (validation, diagnostics, TOML schema, machine output)

- Strengthened the TOML schema validation model in `topmark.toml`:
  - Distinguished between unknown top-level sections (tables) and unknown top-level scalar keys by
    introducing `UNKNOWN_TOP_LEVEL_KEY` alongside `UNKNOWN_TOP_LEVEL_SECTION`.
  - Centralized whole-source TOML validation in `topmark.toml.schema` and ensured downstream layers
    rely on validated input rather than re-validating structure.
- Clarified and hardened the validation boundary between layers:
  - `topmark.toml` is now the single authority for whole-source TOML schema validation.
  - `topmark.config` focuses on layered deserialization, merge semantics, and runtime/config
    validation, without duplicating schema checks.
- Stabilized malformed-section handling policy in TOML validation:
  - Known sections with invalid shapes (non-table values) are reported as diagnostics (warnings) and
    ignored during parsing.
  - Nested sections such as `[policy_by_type.<filetype>]` follow the same warning-and-ignore policy
    when malformed.
  - Missing known sections are now emitted as `INFO` diagnostics, allowing callers to distinguish
    absent sections from malformed-present sections.
- Confirmed and documented the current config-validation strictness behavior:
  - `strict_config_checking` acts on the aggregated config-diagnostics set, including replayed TOML
    validation issues, config-layer diagnostics, and sanitization warnings.
  - CLI and API validation paths share the same strictness semantics and validation helpers.
- Tightened pre-release documentation around generated configuration reference material and Markdown
  output:
  - added a generated example TOML configuration page under
    `docs/configuration/generated/example-config.md` based on `topmark config init`
  - linked the generated example from configuration documentation and navigation instead of relying
    only on source-file references
  - standardized generated Markdown footers so config, registry, and pipeline Markdown output now
    includes a versioned "Generated with TopMark v..." footer
- Audited and aligned machine output formats across domains:
  - Confirmed consistent JSON and NDJSON envelope structure across config, pipeline, registry, and
    version commands.
  - Standardized pipeline summary payloads to emit flat rows with `(outcome, reason, count)` in both
    JSON and NDJSON formats.
  - Fixed schema/doc drift in pipeline machine schemas/payloads/envelopes so code, docs, and typed
    machine schemas now consistently use flat summary rows rather than legacy outcome-keyed
    map/`key`/`label` terminology.
  - Fixed stale `config check` machine-output wording so JSON/NDJSON docs and emitter descriptions
    consistently refer to the explicit `config_check` payload/record kind rather than a generic
    `summary` container.
- Tightened and documented the current `strict_config_checking` contract:
  - clarified in code and user docs that `strict_config_checking` is a TOML-source-local
    config-loading option rather than a layered `Config` field
  - documented that its current effect applies to the aggregated config-resolution/preflight
    diagnostic pool rather than only to TOML parsing or layered-config merge validation in isolation
  - aligned CLI/API/runtime wording, example TOML comments, configuration docs, and command docs on
    the same effective-strictness semantics
- Clarified validation-boundary ownership across TOML, config, and runtime layers:
  - `topmark.toml.getters` is now documented as checked TOML value extraction rather than
    whole-document schema validation
  - config deserializers and resolution bridge helpers now explicitly document that whole-source
    TOML schema validation belongs to `topmark.toml`
  - runtime/config validity helpers now describe aggregated diagnostics and effective resolved
    strictness consistently
- Reduced schema-maintenance drift and generic-helper coupling:
  - removed duplicated structural TOML schema metadata from `topmark.toml.keys`, leaving section/key
    names in `keys.py` and structural schema/validation rules in `schema.py`
  - moved generic mapping helpers out of `topmark.toml.getters` into `topmark.core.typing_guards`,
    clarifying that they operate on generic Python mappings rather than TOML-specific structures
- Expanded targeted regression coverage for pre-release stabilization:
  - added focused TOML validation tests for unknown top-level scalar vs table diagnostics, malformed
    known sections, malformed nested policy sections, dump-only input keys, and missing-section
    `INFO` diagnostics
  - added machine-format regression tests to lock in `config_check` payload naming and flat pipeline
    summary rows without legacy `key` / `label` fields
  - added strictness-behavior tests confirming the current aggregated gate semantics: replayed TOML
    warnings and sanitization warnings fail only in strict mode, while missing-section `INFO`
    diagnostics do not fail either mode
- Identified and documented remaining follow-up work:
  - staged validation / integrity gates (TOML → config → runtime) remain intentionally deferred to a
    dedicated post-alpha refactor
  - the long-term treatment of sanitization warnings under strictness remains an explicit follow-up
    decision

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
  file types/processors and add a first-class bindings view. Downstream tooling or snapshots
  expecting unqualified-only or processor-grouped registry output may need to be updated.
- Public API registry metadata in \[`topmark.api`\][topmark.api] was reshaped to align with the
  split filetype / processor / binding model:
  - `FileTypeInfo.name` was removed in favor of `local_key`, `namespace`, and `qualified_key`
  - `FileTypeInfo.processor_name` was removed
  - `FileTypeInfo.supported` was replaced by `bound`
  - `FileTypeInfo.policy` is now structured metadata rather than an opaque rendered object
  - `ProcessorInfo.name` was removed in favor of `local_key`, `namespace`, and `qualified_key`
  - `ProcessorInfo` is now identity-focused and includes `bound` plus delimiter capability fields
  - `BindingInfo` was added / stabilized as the explicit relationship-oriented API shape
  - `list_bindings()` was added as the explicit relationship-oriented API entry point
  - downstream callers consuming the old TypedDict field names or binding-flavored processor views
    must be updated
- File type resolution ambiguity is now an explicitly documented resolver concern:
  - overlapping `FileType` definitions are permitted
  - deterministic tie-breaks are part of the resolver contract
  - the policy is documented in `docs/dev/resolution.md`

### Config/TOML/runtime package and Python helper surface changes

- Several config-construction and TOML-rendering helpers were removed from `Config` /
  `MutableConfig` and relocated into dedicated `topmark.config.io.*` and `topmark.toml.*` modules.

- `topmark.cli.config_resolver` was removed after CLI config building was switched to the shared
  config-layer helpers.

- `topmark.config.args_io` was removed as part of the config package refactor.

- `load_resolved_config()` and `discover_config_layers()` were removed after callers/tests were
  migrated to the TOML-first resolution flow via `resolve_toml_sources_and_build_config_draft(...)`
  and `build_config_layers_from_resolved_toml_sources(...)`.

- Config-loading entry points were consolidated around TOML-first resolution:

  - callers must now explicitly handle the `(resolved_sources, draft_config)` tuple when provenance
    is needed
  - direct “flattened config only” helpers are no longer provided

- Generic API/CLI mapping input is now represented as `ConfigMapping` in `topmark.api.types` instead
  of `ArgsLike` in `topmark.config.types`.

- The legacy `ArgsLike` alias was removed entirely; downstream callers should use `ConfigMapping`
  (or plain `Mapping[str, object]`-compatible inputs) for generic API/config mappings.

- API/runtime config coercion now distinguishes generic mapping input from TOML-backed
  deserialization via `mutable_config_from_mapping()`.

- The layered config / TOML fragment deserialization boundary is now explicit in the helper surface:

  - `mutable_config_from_layered_toml_table()` replaced the older `mutable_config_from_toml_dict()`
    entry point
  - downstream callers/tests using the old helper name must migrate to the layered-fragment helper
    or to TOML-layer loading helpers, depending on whether they start from a layered fragment or a
    whole TOML source

- The layered config / TOML source boundary is now explicit:

  - source-local TOML options such as `[config].root` and `strict_config_checking` are resolved
    outside layered `Config` merging
  - discovered TOML sources are first resolved and whole-source TOML-validated on the TOML side,
    then merged into layered config drafts
  - source-local sections such as `[config]` and `[writer]` are validated on the TOML side rather
    than via duplicate config-layer checks

- Introduced explicit config validation semantics and strictness control:

  - validation is now always executed via `Config.is_valid(...)` / `Config.ensure_valid(...)`
  - `strict_config_checking` now controls whether validation violations raise
    (`ConfigValidationError`) or are only reported as diagnostics
  - CLI (`config check`, `--strict`) and API validation now share the same validation path and error
    model
  - downstream callers relying on silent acceptance of invalid configs must account for validation
    diagnostics or exceptions depending on strictness
  - `strict_config_checking` now effectively governs the aggregated config-resolution diagnostic
    pool, which may include replayed TOML validation issues, config-layer diagnostics, and
    sanitization warnings
  - callers/tests that previously interpreted strictness as a TOML-only or layered-config-only check
    must update expectations to the broader current preflight/config-resolution semantics

- Downstream Python callers importing moved/removed config helpers from older module locations must
  update their imports to the new `topmark.config.io.*`, `topmark.toml.*`, `topmark.runtime.*`, and
  `topmark.config.overrides` layout.

- Policy override application is now centered on typed override objects (`PolicyOverrides` /
  `ConfigOverrides`) rather than the older wide keyword-argument surface.

- Public/config-facing policy representation changed from the boolean pair `add_only` /
  `update_only` to the scalar `header_mutation_mode` token.

- Public API result-view filtering changed from legacy `skip_compliant` / `skip_unsupported`
  booleans to the scalar `report` selection (`"all"`, `"actionable"`, `"noncompliant"`).

- Config merge semantics are no longer uniformly "last-wins":

  - `field_values` now merge key-wise instead of being replaced wholesale
  - `include_from`, `exclude_from`, and `files_from` now accumulate across layers instead of
    replacing

- Layered config resolution now produces per-path effective configs rather than a single flattened
  configuration, which may change behavior for nested config setups

- The TOML schema changed for source-local options:

  - `root` no longer lives at top level / `[tool.topmark]`
  - source-local options now live under `[config]` in `topmark.toml`
  - and under `[tool.topmark.config]` in `pyproject.toml`

- TOML validation behavior is now stricter and earlier in the load path:

  - unknown top-level sections/keys, unknown keys in known sections, and malformed section shapes
    are reported during whole-source TOML loading
  - these TOML-layer diagnostics now surface alongside config-layer diagnostics in CLI/API
    validation flows
  - callers that previously relied on such issues being silently ignored or only noticed later in
    config deserialization must update expectations and tests
  - unknown top-level scalar keys are now classified separately from unknown top-level table
    sections (`UNKNOWN_TOP_LEVEL_KEY` vs `UNKNOWN_TOP_LEVEL_SECTION`), so tests and tooling that
    assert on TOML diagnostic codes must update accordingly
  - malformed known sections and malformed nested policy-by-type sections are now explicitly treated
    as TOML-layer warning-and-ignore cases; callers/tests that previously relied on config-layer
    fallback behavior should treat this as a TOML validation concern instead
  - missing known sections are now emitted as TOML-layer `INFO` diagnostics rather than being
    treated as completely silent absence; callers/tests that previously expected no diagnostics for
    empty-but-present TopMark TOML sources must update accordingly

- Built-in/default TOML resources and helpers were moved out of `topmark.config`:

  - `topmark-example.toml` now lives under `topmark.toml`
  - default/template helpers now live under `topmark.toml.defaults`
  - template-edit helpers now live under `topmark.toml.template_surgery`

- Generic mapping extraction helpers that were temporarily living in `topmark.toml.getters` were
  moved to `topmark.core.typing_guards`; downstream Python callers should no longer treat those
  helpers as TOML-specific utilities.

- Duplicated structural TOML schema metadata was removed from `topmark.toml.keys`; `keys.py` now
  acts as the canonical registry of external TOML section/key names, while `topmark.toml.schema`
  owns structural schema metadata and validation rules.

### CLI / output / runtime behavior changes

- Output format rename: `DEFAULT` was removed and replaced by `TEXT` (label now `"text"`).
- Emitter package rename: *topmark.cli.emitters.default* →
  \[`topmark.presentation.text`\][topmark.presentation.text].
- Shared pipeline helpers moved to
  \[`topmark.presentation.shared.pipeline`\][topmark.presentation.shared.pipeline].
- Verbosity and color options were moved from the root CLI group to individual commands. Global
  invocation patterns may need to be updated.
- Runtime-only execution intent is now separated from layered config:
  - apply/preview behavior is no longer carried on `Config`
  - `RunOptions` now carries runtime-only execution state
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
- Reporting CLI flags were simplified and renamed:
  - `--skip-compliant` was removed in favor of `--report actionable`
  - `--skip-unsupported` was removed in favor of `--report noncompliant`
- Header-mutation policy CLI/config surface changed:
  - removed `--add-only` / `--update-only`
  - introduced `--header-mutation-mode`
  - config policy now uses `header_mutation_mode` instead of `add_only` / `update_only`
- Policy option applicability is now enforced more strictly:
  - `strip` accepts only shared resolver/content-probe policy options
  - check-only mutation/insertion policy options are rejected at the CLI layer for `strip`, even
    under permissive path-command parsing
- STDIN handling is now documented and modeled more explicitly as two distinct modes:
  - list mode (`--files-from -`, `--include-from -`, `--exclude-from -`)
  - content mode (`-` plus `--stdin-filename`)
- Config validation strictness is now exposed consistently in the CLI:
  - `config check` and pipeline commands support `--strict` to enforce validation errors
  - non-strict mode reports diagnostics without failing
  - this strictness currently applies to the aggregated config-resolution diagnostic set rather than
    only to TOML parsing or layered-config merge validation in isolation
- `config dump --show-layers` adds a new inspection mode in both human and machine output:
  - human output now emits layered TOML provenance before the final flattened config snapshot
  - machine output now emits `config_provenance` before `config` when layered provenance is
    requested
  - downstream tooling that assumed `config dump` machine output always consisted of a single
    flattened `config` payload/record must be updated when using `--show-layers`

### Breaking changes in machine output formats

- Downstream consumers of pipeline summary machine output must now expect flat summary rows keyed by
  `(outcome, reason, count)` rather than outcome-keyed maps or collapsed per-outcome labels.
- Legacy pipeline machine summary row terminology (`key` / `label`) is no longer accurate; code,
  docs, and tests now consistently use `outcome` / `reason` / `count`.
- `config check` machine output now uses the explicit `config_check` payload/record kind for the
  command summary; downstream tests/docs/tooling that previously referred to a generic `summary`
  record in this path must be updated.
- Pipeline and `config check` machine-format docs/schemas were aligned with the implemented payloads
  during pre-release stabilization, so older assumptions about legacy wrapper names or generic
  summary containers should be treated as obsolete.

### Documentation and documentation-build behavior

- User-facing and developer-facing documentation was broadly realigned to the new TOML → Config →
  Runtime architecture, including:
  - whole-source TOML schema validation before layered config deserialization
  - `[config]` / `[tool.topmark.config]` placement for source-local TOML options
  - layered provenance as the validated source-local TOML view plus the final flattened config
  - `config defaults` as the built-in layered default config view
  - `config init` as the bundled example TopMark TOML resource
  - the current meaning of `strict_config_checking` as a TOML-source-local strictness preference for
    the aggregated config-resolution/preflight diagnostic pool
  - missing known TOML sections as `INFO` diagnostics and malformed known sections as
    warning-and-ignore cases at the TOML layer
- Configuration documentation now links to a generated example TOML document produced from
  `topmark config init` rather than relying only on source-file references, and generated Markdown
  output now includes a standardized version footer. Downstream docs tooling or expectations around
  generated Markdown snapshots may therefore need updating.
- Documentation build now depends on the generated API/reference pages and on the stabilized
  presentation/rendering paths for registry/pipeline commands. Missing or stale modules will fail
  the docs build (`mkdocs build --strict`).
- CI now performs built-site link checks (`links-site`) as part of the unprivileged validation path
  that gates release-artifact creation on tag pushes; link validation failures block artifact
  creation and therefore block publishing indirectly.
- GitHub-style alert handling in the docs pipeline no longer attempts to infer custom titles from
  inline/body text; rendered admonition titles now always come from the alert kind (`Note`, `Tip`,
  etc.).
- Formatter configuration for Markdown and TOML is now sourced from dedicated tool config files
  (`.mdformat.toml`, `.taplo.toml`) rather than mixed into `pyproject.toml`.
- User-facing documentation now includes a dedicated policy guide and command/configuration
  cross-links to it; older docs that referred to legacy skip/report and add/update flags were
  updated to the new report/policy model.

### Developer tooling / CI

- tox support removed; contributors and CI must use `nox` (and uv-backed envs) going forward.
- The project now assumes the uv-first workflow and nox-based automation model throughout
  contributor, CI, and release documentation.
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
  publishing now depends on a successful `CI` `workflow_run`, a valid release tag, and CI-produced
  release artifacts built on the tag-push run.
- The GitHub release pipeline now follows an artifact-based CI → release split:
  - `ci.yml` builds and uploads release artifacts (`sdist`, `wheel`, release metadata) on tag pushes
    in an unprivileged context
  - `release.yml` runs in a privileged `workflow_run` context, downloads those artifacts, verifies
    tag/version/checksum consistency, and publishes them
  - repository code is no longer checked out and built inside the privileged release workflow
- Release artifact creation is now a first-class CI responsibility on tag pushes, so maintainers who
  previously expected the release workflow itself to build docs/site/package artifacts must update
  their mental model and troubleshooting flow.
- The shared local composite action (`.github/actions/setup-python-nox`) remains the standard
  bootstrap path for CI, but privileged release jobs intentionally inline trusted setup steps rather
  than invoking repo-local actions.
- Package versioning no longer uses a manually maintained static `[project].version` in
  `pyproject.toml`.
- TopMark now derives package versions from Git tags via `setuptools-scm`, with a generated
  `topmark._version` module included in built artifacts.
- Release validation no longer compares the release tag against `pyproject.toml`; it now validates
  the SCM-derived artifact version against the resolved release tag.
- Release/contributor workflows no longer include a manual version-bump step; version progression is
  now driven by release tags.
- Compact PEP 440-style prerelease tags (`vX.Y.ZaN`, `vX.Y.ZbN`, `vX.Y.ZrcN`) are now the preferred
  form for new releases, while legacy dashed prerelease tags remain supported for backward
  compatibility.
- GitHub Actions workflow behavior on pull requests is now more aggressively gated by changed-file
  buckets, so some jobs that previously ran for all PRs may now be skipped unless the relevant files
  changed.

### uv workflow follow-up and ecosystem stabilization

The uv migration is functionally complete, but a few ecosystem-level follow-up decisions remain
before 1.0:

- Decide whether `uv.lock` should be represented in TopMark’s built-in file type registry as a
  recognized-but-header-unsupported generated artifact.
- Keep validating that local `.venv`, nox, CI, pre-commit, and RTD all continue to reflect the same
  dependency and formatter/plugin expectations under the uv-first model.

### GitHub Actions follow-up and release-path rehearsal

The security and workflow-model refactor is now functionally in place:

- CI builds release artifacts on tag pushes in an unprivileged context
- the privileged release workflow consumes downloaded artifacts instead of rebuilding the project
- release publishing now depends on successful CI, a valid tag, and artifact verification

Remaining decisions before 1.0:

- Decide whether the current artifact split between CI and release should be treated as the stable
  1.0 release architecture, with any further factoring deferred post-1.0.
- Decide whether the `tests` matrix job should eventually reuse the shared setup composite action by
  adding optional settings such as prerelease-Python support, or whether the current explicit matrix
  setup should remain the clearer implementation.
- Decide whether workflow-file indentation/style should be enforced only through `.editorconfig` and
  editor policy, or also documented explicitly in contributor-facing CI guidance.
- Keep validating that workflow trigger coverage, changed-file buckets, tag-push artifact creation,
  and release-artifact verification stay aligned as project tooling and config files evolve.

______________________________________________________________________

## Still undecided / still to do

This section lists remaining 1.0 decisions and implementation work. Items are grouped by theme.

### Namespace-based registry completion

#### Registry completion status

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
- Ensure machine and human output formats consistently use canonical qualified identifiers as the
  primary identity representation, with local keys treated as optional compatibility input.
- Align CLI commands and API representations with the split registry model (filetypes / processors /
  bindings) and remove remaining binding-flavored coupling from processor-oriented views

Recommended direction:

- Keep canonical qualified identity as the default internal model.
- Keep the file-type local-key view only as an explicit compatibility layer where it provides real
  user-facing value.
- Preserve fail-fast behavior for duplicate processor registration while keeping overlap between
  file types a resolver concern rather than a registry error.

### In-memory pipeline (Option A, still undecided)

#### In-memory pipeline status

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
- Align in-memory execution with the existing TOML → Config → Runtime flow so runtime overlays and
  config validation behave identically regardless of input source

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
- Should input resolution helper names be further tightened for 1.0, or is the current
  `topmark.resolution.files` public surface stable enough as-is?
- Should the resolution layer stay decoupled from full config objects and instead continue to accept
  only the specific include/exclude file type filters it actually needs?
- Should TopMark keep the current deterministic winner-selection policy for overlapping `FileType`
  candidates through 1.0, or introduce a stricter ambiguity mode later?
- Should namespace ever become a semantic precedence signal, or remain only a stable tie-breaker?

Before 1.0, the package should have:

- a documented stable responsibility split between `resolution.files` and `resolution.filetypes`
- explicit documentation of how resolution integrates with TOML-source-local options and layered
  config filtering (include/exclude file types)
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
- Keep validating that Nox, pre-commit, local `.venv`, editor integrations, CI jobs, and the
  artifact-based release workflow all consume the same formatter plugin set and tool configuration.

### API vs CLI separation

#### API vs CLI separation status

Some CLI-oriented concerns may still leak into API-facing or presentation-adjacent modules, mainly
around final output policy, verbosity/color handling boundaries, and a few convenience helpers.

Before 1.0, aim for:

- A clean API surface usable without Click
- CLI modules acting strictly as orchestration and final output layers
- Human-facing rendering isolated in `topmark.presentation`
- No CLI-specific behavior (verbosity, coloring, formatting decisions) inside core logic

Additional progress:

- Machine-format serializers are fully API-usable (no Click dependency).
- Base machine metadata is cached in shared helpers, while command-specific machine metadata
  enrichment (for example `detail_level`) now happens explicitly at the command boundary.
- API remains free of CLI-specific meta concerns unless machine output is explicitly requested.
- Introduced `topmark.presentation` as the Click-free, human-facing presentation layer between
  API/domain data and CLI printing.
- Migrated `version`, config, diagnostic, and pipeline human-output paths to presentation report
  builders plus pure `render_*()` helpers.
- Refactored CLI command modules so human output now follows a clearer pipeline: prepare report →
  render string → `console.print(...)`.
- CLI config building now delegates TOML/config resolution to the shared TOML-first resolution
  helpers and final override application to `topmark.config.overrides` instead of maintaining a
  separate CLI-local resolver path.
- API runtime config/file preparation now mirrors the same TOML → Config → Runtime split and no
  longer builds config state through TOML-named helpers when given a generic Python mapping.
- Config validation now also follows the same shared path in CLI and API code:
  - effective strictness is resolved outside layered `Config`
  - validation helpers and `ConfigValidationError` are shared across runtime entry points

#### Remaining work

- Remove remaining Click-facing concerns from non-CLI modules.
- Ensure formatting/verbosity/color decisions remain strictly split between:
  - CLI policy/orchestration (`topmark.cli`)
  - human-facing rendering (`topmark.presentation`)
  - core/domain logic (Click-free and presentation-free)
- Confirm that TOML validation diagnostics are surfaced consistently in both CLI and API flows
  without introducing CLI-specific formatting concerns into core validation logic
- Clarify ownership of `meta` in the API only when machine output becomes part of the API surface.
- Confirm that the current artifact-based GitHub release workflow remains a CLI/automation concern
  only and does not leak release-specific metadata/download assumptions into public Python API
  surfaces.
- Decide whether the current API-side convenience helpers for seeded config/file preparation should
  remain in `topmark.api.runtime` long-term or be slimmed further around a smaller config-layer
  façade.
- Confirm that provenance inspection concerns (layered TOML sources) remain scoped to dedicated
  inspection commands (`config dump --show-layers`) and are not mixed into validation-oriented
  commands.

### Override model and runtime overlay boundary

The configuration/runtime boundary now has a much clearer split between:

- TOML-side source resolution in `topmark.toml.resolution`
- layered config construction/merge in `topmark.config.resolution`
- highest-precedence override application in `topmark.config.overrides`
- runtime-only execution intent in `topmark.runtime.*`

Additional progress:

- removed duplicate CLI-local config resolution logic and switched CLI config building to the shared
  TOML-first resolution helpers
- introduced `ConfigMapping` as the public API-facing mapping alias in `topmark.api.types`
- added `mutable_config_from_mapping()` so generic API mappings are no longer routed through a
  TOML-named helper
- resolved `strict_config_checking` on the TOML side rather than treating it as a layered config
  field
- confirmed and documented that the current `strict_config_checking` behavior is an aggregated
  config-resolution/preflight gate rather than a pure layered-config setting
- explicitly deferred the staged validation/integrity-gates redesign to a dedicated post-alpha
  refactor; the remaining open decision is whether 1.0 should intentionally freeze the current
  aggregated gate semantics or introduce staged gates before final schema/contract freeze

Decision to make before 1.0:

- Freeze and document the typed override model (`PolicyOverrides` / `ConfigOverrides`) as the stable
  long-term override boundary, or slim it further if parts of the current structure are still too
  CLI/API-shaped.
- Decide how much of the typed override model should be treated as public/stable for Python callers
  versus as an internal config-layer contract used by the CLI and API runtime.
- Decide whether `strict_config_checking` should remain the stable public/source-local knob for the
  current aggregated config-resolution/preflight diagnostic pool for 1.0, or whether final 1.0
  schema/contract freeze requires a more explicit staged validation model.
- Decide whether sanitization/runtime-applicability warnings should intentionally remain in the same
  strictness gate as TOML validation issues and merged-config diagnostics for 1.0.

Desired outcome:

- Core config loading/merging stays reusable and independent of CLI concerns.
- CLI parsing/normalization produces a clear override structure.
- The same override structure remains usable by API callers (without importing Click).
- Freeze and document the long-term boundary between typed config overrides and runtime-only overlay
  state.
- Freeze the 1.0 contract for config-validation strictness: either keep the current aggregated
  preflight gate or replace it with staged validation gates before final schema/contract freeze.
- If the aggregated gate is kept for 1.0, preserve the now-documented behavior that it may include
  replayed TOML validation issues, config-layer diagnostics, and sanitization warnings.
- Confirm that runtime-only fields remain outside layered config merging and are applied only after
  config resolution.
- Confirm that TOML-layer validation and config-layer validation remain clearly separated and do not
  regress into duplicated validation logic across layers
- Keep TOML-source-local config-loading options (for example `strict_config_checking`) outside the
  layered `Config` contract.

### Machine output formats: remaining work

Machine formats are now fully centralized and domain-scoped.

Completed work:

- Pipeline commands (`check`, `strip`) use \[`topmark.pipeline.machine`\][topmark.pipeline.machine]
  shape builders and serializers.
- Registry commands (`filetypes`, `processors`, `bindings`) use
  \[`topmark.registry.machine`\][topmark.registry.machine].
- Config commands (`init`, `defaults`, `dump`, `check`) use
  \[`topmark.config.machine`\][topmark.config.machine].
  - `topmark.config.machine` remains the canonical home for config command machine payloads;
    TOML-specific helpers may be factored into `topmark.toml.*` over time, but command payload
    schemas stay config-domain-owned
- Version command uses \[`topmark.core.machine`\][topmark.core.machine] serializers with shared meta
  handling.
- All commands emit consistent JSON/NDJSON envelopes with machine-facing metadata.
- CLI modules no longer construct machine payloads directly.
- Registry machine formats are now split cleanly into:
  - file type identities
  - processor identities
  - effective bindings
- `detail_level` is now part of the machine contract instead of being inferred only from payload
  shape.

Remaining work before 1.0:

- Final audit of field naming consistency across domains.
- Confirm that TOML validation diagnostics are consistently represented in machine output alongside
  config-layer diagnostics where applicable
- Decide whether flattened config diagnostics are sufficient for 1.0 machine contracts, or whether
  post-1.0 work should preserve more TOML-specific structured issue data (for example code/path)
  beyond the current `{level, message}` representation.
- Confirm that config-validation payloads consistently use `strict_config_checking`. They no longer
  refer to legacy `strict` naming.
- Confirm command responsibilities for machine output:
  - `config dump` is the single command exposing layered provenance (`config_provenance`)
  - `config check` remains validation-only and does not emit provenance payloads
- Expand test coverage for the remaining machine formats still missing focused contract tests
  (especially registry commands); pipeline summary shape, `config check` payload naming, layered
  `config dump` provenance output, and `version` output are now covered in JSON and NDJSON modes.
- Stabilize and freeze machine schema documentation (`docs/dev/machine-formats.md`).
- Review whether pipeline summary rows should eventually expose additional structured fields beyond
  `(outcome, reason, count)`.
- Decide whether the current flattened `{level, message}` config-diagnostics representation is the
  final 1.0 machine contract, or whether richer TOML-specific issue structure should be preserved
  for a post-1.0 evolution.

### Human-facing output formats

Text (ANSI) and Markdown output formats are now being consolidated under the new
`topmark.presentation` package, with shared Click-free report preparation and pure `render_*()`
helpers returning strings.

Remaining work before 1.0:

- Ensure `OutputFormat.TEXT` and `OutputFormat.MARKDOWN` are consistent across commands.
- Ensure verbosity semantics are consistent (`-v`, `-vv`, `-q`) and documented.
- Keep all formatting logic out of CLI command functions; commands should only orchestrate, render,
  and print.
- Finalize hint ordering strategy (newest-first vs oldest-first) and ensure consistency across text
  and Markdown renderers.
- Decide whether the “primary hint” concept (shown at `-v`) should remain explicit or be generalized
  to multi-hint display.
- Evaluate whether Markdown output should remain structurally equivalent to text output or evolve
  toward more document-oriented layouts (e.g., tables or grouped sections).
- Decide whether semantic style roles should be exposed/configurable (themes, CI/no-color modes).
- Further clarify boundary between pipeline outcome computation (`map_bucket()`) and presentation
  logic in renderers.

### CLI framework choice: Click vs Rich

Recommendation: keep Click through 1.0 unless there is a strong feature need.

### Color output and dependency on yachalk

Recent refactoring introduced semantic styling via `StyleRole`, significantly reducing direct
`yachalk` usage in human-output code and enabling a cleaner separation between core logic,
presentation rendering, and CLI output policy. Remaining work is mainly about deciding whether to
keep `yachalk` as a confined CLI-only dependency or remove it entirely later.

Remaining work focuses on:

- fully eliminating or strictly confining `yachalk` usage to CLI-only modules;
- replacing Click-flavored styling in `ClickConsole` with semantic styling.

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

Related versioning note:

- Package/application versioning is now already settled: TopMark uses Git tags as the single source
  of truth via `setuptools-scm`.
- This remaining question is only about whether TopMark’s **configuration schema** should gain its
  own explicit version key in a future evolution.

Remaining pre-1.0 work in this area:

- Confirm that the current TOML schema validation rules (unknown keys, section shapes, strictness)
  are considered stable for 1.0 and do not require version gating
- Remove or reduce duplicated TOML structure metadata shared between `topmark.toml.keys` and
  `topmark.toml.schema` so schema freeze relies on a single authoritative structure definition.
- Decide whether schema-maintenance cleanup (for example reducing duplicated allowed-key metadata)
  is required before 1.0 or can be deferred immediately after the 1.0 schema freeze.

### Output format strategy and verbosity

Open questions:

- Do we want a second non-colored format (for example `text` vs `plain`), or is a single text format
  with optional color sufficient?
- Do we want to keep Markdown as a first-class human format for all commands?
- Now that package versioning is SCM-derived and the release workflow is artifact-based, do we want
  `version` command examples/docs to show stable release examples only, or also keep representative
  dev-version examples with commit-based metadata?
- Are the current verbosity levels sufficient and consistent across commands?

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
- Freeze the final CLI policy surface and command applicability rules:
  - `check`-only mutation/insertion policy options
  - shared resolver/content-probe policy options
  - `strip` explicitly rejects check-only policy options at the CLI layer (validated despite
    permissive parsing)
- Confirm that the public API `report` model (`"all"`, `"actionable"`, `"noncompliant"`) is the
  final, stable replacement for legacy skip-based filtering and document its guarantees as part of
  the public API contract.
- Decide whether a dedicated public API enum should ever be exposed for policy tokens, or whether
  public API callers should continue to use stable string literals while internal CLI/config code
  uses the internal enum types directly.
- Keep verifying that API documentation and examples consistently use `report` and no longer
  reference `skip_*` parameters.

Any change here should preserve backward compatibility unless explicitly gated; release automation
and artifact-based publishing should remain orthogonal to policy-token and operation-mode contracts.

______________________________________________________________________

## 1.0 readiness checklist

TopMark 1.0 follows a **contract-first** release strategy: all externally observable behavior (API
surface, configuration semantics, machine formats, and CLI exit/status behavior) must be stable,
documented, and well-tested. Items in the “Must finish before 1.0” section are considered release
blockers unless explicitly deferred with a documented rationale; other items are tracked as post-1.0
polish or follow-up work.

This checklist defines the minimum criteria for cutting TopMark 1.0, grouped by priority.

### Must finish before 1.0

#### [Must] Architecture & boundaries

- [x] Clear separation between CLI layer and API/core modules
  - [x] CLI config resolution no longer duplicates layered config discovery/merge logic
  - [x] API runtime config/file preparation now reuses config-layer resolution/override helpers
  - [x] Human-facing rendering isolated in `topmark.presentation`
  - [x] Config validation now follows the same shared path in CLI and API runtime code
- [x] No CLI-specific concerns (verbosity, color, formatting) in core logic

#### [Must] Machine formats

- [x] No presentation leakage (color text, human wording) in machine output
- [ ] Machine outputs are covered by tests for all commands in both JSON and NDJSON modes
  - [x] config commands (`check`, `defaults`, `dump`, `init`)
    - [x] `config check` machine output is covered in both JSON and NDJSON modes
    - [x] `config defaults` machine output is covered in both JSON and NDJSON modes
    - [x] `config dump` layered provenance is now covered in both JSON and NDJSON modes
    - [x] `config init` machine output is covered in both JSON and NDJSON modes
  - [x] pipeline commands (`check`, `strip`)
  - [ ] registry commands (`filetypes`, `processors`, `bindings`)
  - [x] version command (`version`)
- [ ] Final schema freeze review before 1.0 (including `(outcome, reason, count)` summary rows)
- [ ] Remove remaining schema/doc drift in machine output definitions:
  - [x] pipeline machine schemas/docs match the flat summary-row shape already used by
    code/tests/docs
  - [x] `config check` machine output is described consistently as `config_check` rather than a
    generic `summary`
- [x] Confirm that config-validation payloads consistently use `strict_config_checking` and no
  longer expose legacy `strict` naming
- [ ] Confirm that TOML validation diagnostics are represented consistently alongside config-layer
  diagnostics in machine output where applicable
- [ ] Decision made and documented on whether flattened `{level, message}` config diagnostics are
  sufficient for 1.0 machine contracts, or whether richer TOML-specific issue structure is required
  before schema freeze
- [ ] Final review/freeze of `detail_level` semantics and brief vs long machine projections

#### [Must] Human formats

- [ ] `OutputFormat.TEXT` and `OutputFormat.MARKDOWN` consistent across commands
  - [ ] Config commands (`check`, `defaults`, `dump`, `init`)
  - [x] Pipeline commands (`check`, `strip`)
  - [x] Registry commands (`filetypes`, `processors`, `bindings`)
  - [x] Version command (`version`)
- [ ] Warnings and error phrasing consistent across CLI

#### [Must] CLI behavior

- [ ] Exit codes documented and stable
- [ ] CLI command applicability rules (policy options, stdin modes, strict config-checking
  overrides) fully documented and enforced

#### [Must] Configuration

- [ ] Config keys and semantics documented and considered stable
- [ ] Qualified and unqualified file type identifier semantics documented and considered stable
- [ ] `config init`, `defaults`, `check`, `dump` produce aligned outputs
- [ ] Decision made and documented on the final public override model
- [x] Package/application versioning model documented and considered stable:
  - [x] Git tags are the single source of truth via `setuptools-scm`
  - [x] static `[project].version` in `pyproject.toml` is no longer used
  - [x] release validation checks SCM-derived artifact versions against release tags
  - [x] privileged release workflow consumes CI-built artifacts instead of rebuilding repository
    code
  - [x] release/contributor workflow no longer includes a manual version-bump step
- [x] Preferred release-tag conventions documented and considered stable for 1.0:
  - [x] compact PEP 440-style prerelease tags (`vX.Y.ZaN`, `vX.Y.ZbN`, `vX.Y.ZrcN`) are preferred
  - [x] legacy dashed prerelease tags remain supported for backward compatibility
- [ ] `EmptyInsertMode` tokens and semantics documented and considered stable
- [ ] Typed override model (`PolicyOverrides` / `ConfigOverrides`) documented and considered stable
- [x] `strict_config_checking` documented and considered stable as a TOML-source-local
  config-loading option (not a layered `Config` field)
- [x] Whole-source TOML schema validation rules documented and considered stable (unknown keys,
  malformed section shapes, source-local section validation)
- [x] Distinction between unknown top-level table sections and unknown top-level scalar keys is
  covered by tests and documented as part of the stable TOML diagnostic contract
- [x] Malformed known sections and malformed nested policy-by-type sections are confirmed and frozen
  as TOML-layer warning-and-ignore behavior
- [x] Layered config discovery/merge and final CLI/API override application are separated into
  dedicated config modules
- [x] `header_mutation_mode` fully replaces legacy `add_only` / `update_only` references
- [x] Field-specific config merge semantics are defined, implemented, and covered by regression
  tests
- [x] Per-path effective config resolution is implemented and used by the pipeline engine
- [x] Final documentation of TOML → Config → Runtime split (including whole-source TOML validation,
  source-local options, layered provenance, and runtime overlays)
- [x] Decide whether duplicated TOML structure metadata in `topmark.toml.keys` vs
  `topmark.toml.schema` must be cleaned up before 1.0 schema freeze or can be deferred with
  rationale
- [ ] Validation semantics documented and considered stable:
  - [x] validation always runs
  - [x] `strict_config_checking` controls whether validation violations raise or are only reported
  - [x] CLI and API validation follow the same path and error model
  - [x] current strictness semantics are documented as applying to the aggregated
    config-resolution/preflight diagnostic pool
  - [ ] decision made whether 1.0 keeps the aggregated strictness gate or introduces staged gates
    for TOML/source validation, merged config validity, and sanitization/runtime applicability

#### [Must] Pipeline & testing

- [ ] Decision taken on in-memory pipeline support (implemented or explicitly deferred)
- [ ] Clear split between unit (memory-based) and integration (filesystem) tests
- [ ] Namespace-aware registry lookup and deterministic ambiguity behavior covered by tests
- [x] TOML-layer validation paths covered by focused tests for:
  - [x] unknown top-level sections vs unknown top-level scalar keys
  - [x] malformed known section shapes
  - [x] malformed nested policy-by-type section shapes
  - [x] propagation into config diagnostics / strict config checking behavior
- [ ] API surface clarified for in-memory pipeline inputs (either implemented or deferred with
  rationale)
- [x] Empty and empty-like file handling is explicit and idempotent
- [x] Resolver treats content matcher exceptions as safe misses
- [x] Preview vs apply semantics are consistent end-to-end
- [x] API and CLI policy override behavior covered by focused tests for valid and invalid overlays
  - [x] CLI policy override behavior
  - [x] API policy override behavior
- [x] Engine correctly applies per-path configs and policy registries (covered by integration tests)
- [x] Explicit separation between layered config, TOML-source-local config-loading options, layered
  provenance export, and runtime overlays

#### [Must] Dependency & ecosystem

- [ ] Decision made on color backend (`yachalk` confinement or removal)
- [ ] Formatter/tool configuration split stabilized and documented (`.mdformat.toml`, `.taplo.toml`)
- [ ] Tooling environments (Nox, pre-commit, local venv, editor, CI, release workflow) verified to
  consume the same formatter plugin set
- [ ] Positive release-path rehearsal completed via the first 1.0 prerelease flow (or otherwise)
  before `1.0.0` final, or explicitly deferred with rationale

______________________________________________________________________

### Strongly recommended (but not blockers)

#### [Recommended] Human formats

- [ ] Human-facing registry outputs reviewed/frozen for qualified identifier presentation
- [ ] Diff rendering policy consistent across pipeline commands
- [ ] Verbosity levels (`-v`, `-vv`, `-q`) documented and behave consistently

#### [Recommended] Machine formats

- [ ] Documented examples for each remaining command category in `docs/dev/machine-formats.md`
- [ ] Include stable examples for config-validation payloads using `strict_config_checking`
- [ ] Include stable examples showing TOML-layer diagnostics alongside config-layer diagnostics
  where applicable
- [ ] Include a short note or example clarifying the current flattened config-diagnostics contract
  versus richer TOML-specific issue data that remains internal for now
- [ ] Sufficient edge-case test coverage to trust core behaviors

#### [Recommended] Dependency & ecosystem

- [ ] Decide whether the explicit local-key compatibility view in `FileTypeRegistry` should remain a
  supported 1.0 feature
- [ ] Decide whether the current artifact-based CI → release split should remain the stable 1.0
  release architecture or later be factored into a reusable workflow / shared release-infra pattern

______________________________________________________________________

### Post-1.0 follow-up (nice-to-have)

#### [Post-1.0] Human formats

- [ ] Further Markdown layout evolution (tables, grouped sections, richer structures)
- [ ] Generalize or refine the “primary hint” concept
- [ ] Evaluate theme/style configurability (semantic roles)

#### [Post-1.0] Dependency & ecosystem

- [ ] Decision made on long-term CLI framework (Click vs alternative)
- [ ] Workflow refactoring into reusable GitHub workflows

Only when all items in the “Must finish before 1.0” section are completed or explicitly deferred
with rationale should `1.0.0` final be cut. The first 1.0 prerelease tag (`v1.0.0a1`) may itself
serve as part of the release-path rehearsal and final contract validation. In particular,
schema/contract freeze must include config validation semantics, whole-source TOML validation
behavior, and the TOML-source-local status of `strict_config_checking`.
