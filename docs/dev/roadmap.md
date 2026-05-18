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

TopMark 1.0 is now primarily a contract-stabilization effort. The major architecture refactors are
complete, and the remaining work is focused on preserving stable behavior across CLI usage,
configuration loading, machine-readable output, documentation, release validation, and finalized
public/runtime naming.

A key deferred post-1.0 opportunity remains support for data that is not naturally file-backed:
generated code, editor buffers, CI-provided snippets, or API-driven integrations. Today, almost all
of TopMark's processing pipeline assumes filesystem I/O, which makes testing heavier, limits reuse,
and complicates future integrations.

Future in-memory pipeline support would enable:

- Faster, more isolated tests without filesystem setup/teardown
- Cleaner API boundaries (pipeline as a pure transformation)
- Future integrations (editors, LSPs, CI bots) without temporary files
- Clearer separation between what TopMark does and how input is obtained

For 1.0 itself, the priority is to keep the already-refactored system stable, predictable, and
well-documented while deferring new integration scope until after the final release.

______________________________________________________________________

## Done so far

This section tracks work completed during the 0.12 development series and the 1.0 alpha/beta
stabilization line. The focus has been on **architectural separation, deterministic behavior, strict
typing, documentation governance, validation hygiene, canonical public/runtime naming, and removal
of legacy implicit behavior**. The system is now largely aligned with a clean *TOML → Configuratin →
Runtime → Pipeline → Presentation* model and is in late beta stabilization.

### Registry architecture (completed)

The registry system has been fully refactored into a **deterministic, explicit, namespace-aware
model**:

- Introduced a strict **three-registry architecture**:
  - `filetypes` → identity of file types
  - `processors` → identity of processors
  - `bindings` → relationships between file types and processors
- Added a thin façade (`registry.registry`) to compose these concerns without hiding behavior.
- Replaced all implicit registration (decorators, bootstrap scanning) with **explicit bindings**.
- Introduced **namespace-aware identities**:
  - `qualified_key = "<namespace>:<name>"`
  - canonical keys are now the default across APIs and outputs
- Froze the qualified-vs-local file type identifier semantics for 1.0:
  - canonical internal identity is the qualified key, such as `topmark:python`
  - public inputs may use local identifiers, such as `python`, only when unambiguous
  - ambiguous local identifiers require the qualified form
  - fuzzy matching, aliases, and implicit namespace fallback are intentionally unsupported
- Implemented **ambiguity-aware resolution** with explicit error types.
- Moved resolution logic into `topmark.resolution.*` and removed legacy resolution paths.
- Established **canonical identity semantics** across machine output, CLI, and API.
- Introduced probe-based resolution via `ResolutionProbeResult` as the shared evidence model for
  runtime-resolution diagnostics and effective pipeline resolution.
- Added the read-only `topmark probe` command and matching `topmark.api.probe()` public API to
  expose file-type candidates, selected file type, selected processor, scores, match signals, and
  explicit inputs filtered before probing through stable DTOs at the API boundary.
- Refactored `ResolverStep` and `ProberStep` so normal pipelines and the probe pipeline share the
  same probe-backed resolution mapping.

Result: the registry is now **predictable, testable, and plugin-ready**, with no import-time side
effects.

### CLI & presentation architecture (completed)

The CLI and output system has been restructured into **strictly separated layers**:

- `topmark.presentation.*` → pure rendering (no I/O, no Click)
- `topmark.cli.console.*` → runtime/console concerns
- `topmark.cli.commands.*` → orchestration only

Key improvements:

- Removed emitter confusion and replaced with:
  - **serializers** (machine output)
  - **renderers** (human output)
- Enforced **Click-free rendering**
- Introduced **semantic styling (StyleRole)** instead of inline coloring
- Froze the 1.0 color-backend decision: keep `yachalk` because styling is confined to CLI
  presentation internals through `StyleRole`, `Theme`, and string-in/string-out styling helpers;
  defer any Rich migration until after 1.0.
- Standardized TEXT verbosity model (`default`, `-v`, `-vv`).
- Unified summary generation via pipeline outcomes instead of ad-hoc hint logic.
- Introduced a strongly typed `TopmarkCliState` for Click invocation state.
- Removed raw `ctx.obj` dictionary access from CLI command/runtime paths.
- Removed implicit active-console resolution from CLI emitters and helpers.
- Standardized explicit console passing for human and machine CLI output.
- Split shared CLI option decorators so commands opt into TEXT verbosity and TEXT quiet mode
  independently.
- Clarified the final human-output contract:
  - TEXT output is console-oriented and may use `-v` / `-vv` for progressive disclosure.
  - `-q` / `--quiet` suppresses TEXT output only where the command still has a useful status,
    inspection, or mutation signal.
  - Markdown output is document-oriented and ignores TEXT-oriented verbosity, quiet, and styling
    controls.
  - JSON/NDJSON output is machine-readable and ignores TEXT-oriented presentation controls.
  - Pure informational content-producing commands (`version`, `config defaults`, `config init`, and
    registry commands) intentionally do not support `--quiet`.
- Added Click-free shared human report models across config, registry, version, diagnostics, and
  pipeline presentation surfaces.
- Aligned command help text, epilogs, and developer docstrings across CLI entry-point, command
  groups and commands.
- Replaced lingering "global options" wording with the finalized shared-options terminology.
- Documented the public spelling contract for CLI option names, CLI value aliases, and canonical
  TOML/API/machine-readable values.
- Completed a final help/epilog reflow and wording pass for command groups and subcommands.
- Aligned config command help, source docstrings, and examples with the finalized “effective runtime
  configuration” terminology.
- Expanded focused human-output tests for version, diagnostics, config, registry, and pipeline
  commands.
- Documented and enforced the stable CLI exit-code contract across implementation, tests, the
  canonical usage page, command pages, command-group pages, README, documentation index, pre-commit
  guidance, and developer-facing machine/API documentation.
- Documented and enforced the CLI command-applicability contract across implementation, focused
  tests, command pages, command-group pages, README, documentation index, filtering guidance,
  architecture documentation, and public API documentation.
- Froze the path-command STDIN contract:
  - content STDIN uses the POSIX-style `-` PATH sentinel plus `--stdin-filename`
  - TopMark intentionally does not expose a `--stdin` option flag
  - unsupported `--stdin` spellings are rejected as CLI usage errors before input planning

Result: output is now **fully deterministic, testable, and reusable outside CLI contexts**.

### Runtime vs config separation (completed)

A strict separation between **configuration and execution intent** is now in place:

- Introduced `RunOptions` for runtime-only behavior (apply, stdin, etc.)
- Removed runtime concerns from layered configuration
- Ensured CLI and API both follow:
  - TOML → layered configuration → runtime overlay
- Kept TOML-authored runtime sections such as `[writer]` outside layered configuration while
  preserving them in config dumps, config checks, and machine-readable configuration snapshots.
- Aligned `config defaults` and `config init` so machine-readable output is generated through TOML
  parsing/resolution rather than by shortcutting directly to configuration defaults.

Result: config is now **pure, layered, and reproducible**, while runtime behavior is explicit.

### TOML / config system (completed)

The configuration system has been fully restructured:

- Clear split:
  - `topmark.toml` → parsing + validation
  - `topmark.config` → layered configuration merge + resolution
  - `topmark.runtime` → execution behavior
- Implemented **layered configuration with provenance**
- Introduced typed synthetic config provenance for built-in defaults, bundled templates, CLI/API
  overrides, and other non-filesystem config sources.
- Finalized the canonical `MutableX` / `FrozenX` naming model across configuration, policy,
  diagnostics, and staged validation-log types.
- Added **per-path effective runtime configuration resolution**
- Introduced **strict validation model** with diagnostics + strict mode
- Introduced **staged configuration-loading validation logs**:
  - TOML-source diagnostics
  - merged-config diagnostics
  - runtime-applicability diagnostics
- Renamed the alpha-only `[config].strict_config_checking` key to `[config].strict` before the 1.0
  config contract freeze.
- Removed stored flattened diagnostics from `Config` / `MutableConfig`
  - flattening is now performed only at exception, presentation, and machine-readable output
    boundaries
- Removed legacy helpers and compatibility layers
- Standardized API inputs via `ConfigMapping`
- Normalized file type identifier handling across configuration normalization and runtime policy
  lookup:
  - `include_file_types` and `exclude_file_types` normalize to canonical qualified keys
  - `policy_by_type` accepts both qualified identifiers and unambiguous local identifiers
  - frozen `policy_by_type` maps are keyed by canonical qualified file type identifiers
  - runtime policy lookup uses `ctx.file_type.qualified_key`
- Classified `PolicyOverrides` and `ConfigOverrides` as internal CLI/API orchestration bridge types,
  with public callers using plain mapping-based `config`, `policy`, and `policy_by_type` inputs.

Result: configuration is now **typed, layered, validated, normalized, and consistent across
CLI/API**.

### Pipeline semantics & policy model (completed)

The pipeline has been stabilized with clearer semantics:

- Introduced **preview vs apply split**
- Normalized write statuses (PREVIEWED vs INSERTED/REPLACED/REMOVED)
- Introduced **empty-file classification model**
- Refactored policy handling:
  - `HeaderMutationMode` replaces boolean flags
- Froze the user-facing policy/report flag semantics for 1.0:
  - `--report` controls human per-file output scope only and does not affect processing, summaries,
    machine output, or exit-code selection
  - `header_mutation_mode` controls `check` mutation intent (`all`, `add_only`, `update_only`) while
    safety gates still take precedence
  - `empty_insert_mode` controls empty/empty-like classification only and is evaluated together with
    `allow_header_in_empty_files`
  - `render_empty_header_when_no_fields` remains separate from empty-file insertion permission
- Standardized summary output:
  - grouped by `(outcome, reason)`
- Ensured **idempotence and deterministic behavior**
- Audited and froze the 1.0 line-ending support contract:
  - LF (`\n`), CRLF (`\r\n`), and CR (`\r`) are the only recognized physical newline styles
  - non-standard Unicode separators such as NEL (`U+0085`), Line Separator (`U+2028`), and Paragraph
    Separator (`U+2029`) are treated as ordinary content, not line endings
  - XML-specific insertion checks may conservatively skip mutation near such characters as a local
    idempotence guard, not as extended newline support
- Centralized standard newline constants and aligned reader, sniffer, whitespace, XML, and property
  tests with the frozen newline contract.
- Centralized pipeline-result-to-exit-code derivation with explicit priority ordering for mixed
  result runs.
- Added resolution-level synthetic pipeline contexts for explicit missing literal inputs so missing
  files appear in human output, machine output, summaries, and exit-code selection.

Result: pipeline behavior is now **explicit, consistent, and predictable**.

### Machine output system (completed)

Machine formats are now:

- **Domain-scoped** (`config`, `pipeline`, `registry`, `core`, `version`)
- **Schema-driven (TypedDict)**
- Fully separated from CLI
- Using consistent JSON/NDJSON envelope conventions
- Supporting JSON and NDJSON
- Backed by focused JSON + NDJSON contract tests for:
  - config commands
  - pipeline commands
  - version command
  - registry commands
  - probe command
- Supported by shared JSON/NDJSON test helpers for machine-readable output parsing and record/meta
  assertions
- Documented with aligned machine-format and machine-readable output reference pages, plus registry
  command usage pages
- Added probe-specific JSON and NDJSON machine output with a per-path `probes` JSON collection and
  `probe` NDJSON records, including filtered explicit inputs.
- Clarified that machine payloads are decoupled from process exit codes: JSON/NDJSON expose
  structured results and diagnostics, while process status remains the CLI exit code.
- Aligned config machine-readable output so `[writer]` and other TOML-authored runtime sections are
  included when present in the effective TOML source.
- Clarified `config defaults` vs `config init` machine-readable semantics:
  - `config defaults` emits a canonical built-in defaults snapshot.
  - `config init` emits a bundled starter-template snapshot parsed through the TOML resolution
    pipeline.

Result: machine output is now **schema-driven, documented, and separated from human presentation**.
Remaining work is limited to beta feedback and targeted hardening, not architecture.

### Human output system (completed)

- Consolidated human formats: TEXT + MARKDOWN.
- Introduced `topmark.presentation` as canonical rendering layer.
- Established the final presentation contract:
  - TEXT is console-oriented and owns verbosity/quiet semantics.
  - Markdown is document-oriented and ignores TEXT-oriented verbosity/quiet controls.
  - Machine formats are not part of the human-output layer.
- Ensured all renderers are:
  - pure (no I/O)
  - reusable
  - testable
- Added direct presentation tests for shared diagnostic rendering.
- Added CLI-level human-output tests for version, config, registry, pipeline, and probe command
  groups.

Result: human output is now **consistent, composable, and decoupled from CLI**.

### Documentation & developer tooling (completed)

- Major documentation alignment with new architecture
- Added pipeline docs and registry documentation
- Enforced docstring standards and validation
- Introduced link-checking and stricter docs CI
- Reorganized tests and helpers for clarity
- Added shared JSON/NDJSON parsing and assertion helpers for machine-readable output tests
- Recorded machine-readable output naming conventions in the canonical machine-readable output
  reference
- Updated usage, configuration, architecture, machine-output, API, README, and index documentation
  to reflect the finalized TEXT / Markdown / machine output contract.
- Updated exit-code, filtering, command, command-group, pre-commit, architecture, API, machine
  output, README, and index documentation to reflect the finalized exit-code contract, including
  missing-vs-unmatched input behavior and mixed-result priority.
- Documented probe-based resolution and filtered explicit-input reporting in the resolution,
  pipeline, filtering, machine-output, machine-format, and `topmark probe` usage pages.
- Documented `topmark.api.probe()` as the stable public probe surface, with internal resolution
  objects, synthetic contexts, and low-level probe helpers kept outside the 1.0 public API contract.
- Updated policy, command, configuration discovery, schema, and roadmap documentation to reflect the
  frozen `--report`, `header_mutation_mode`, and `empty_insert_mode` contracts.
- Added a shared documentation snippet for the public/internal override boundary and reused it
  across API, configuration, architecture, schema, and resolution documentation.
- Added a shared documentation snippet for qualified vs local file type identifiers and reused it
  across usage, configuration, command, API, registry, plugin, resolution, and machine-output
  documentation.
- Added a shared documentation snippet for `[config].strict` and reused it across the configuration,
  command, usage, architecture, resolution, and pipeline documentation.
- Added dedicated user-facing CLI and configuration overview pages.
- Added a dedicated registry model developer page covering registry layers, bindings, overlays,
  canonical identities, plugin integration, and registry CLI inspection.
- Completed the documentation consistency and generated-site freeze review for `v1.0.0b1`.
- Established canonical documentation conventions in `docs/dev/documentation-conventions.md`,
  covering command-page structure, navigation, cross-references, related links, emoji use,
  generated-doc expectations, TOC density, and snippet governance.
- Harmonized CLI command-page structure across command and command-group documentation, including
  consistent sections for quick starts, applicability, output behavior, machine-readable output,
  exit codes, related commands, related docs, and troubleshooting.
- Improved generated-site discoverability by reducing navigation and TOC density, simplifying
  generated API internals navigation, and relying on package indexes, breadcrumbs, search, and
  cross-references for deeper internals.
- Renamed the former global-options documentation to shared-options documentation and aligned
  command, configuration, and generated-site references.
- Harmonized machine-readable output terminology across usage docs, developer docs, source
  docstrings, and tests while preserving formal machine-output contract terminology where needed.
- Documented the intentional distinction between canonical built-in defaults and the bundled starter
  template for `config defaults` and `config init`.
- Reviewed and reduced the `docs/_snippets/` inventory to stable reusable contracts, retiring
  over-abstracted snippets and centralizing conceptual semantics into canonical reference pages.
- Promoted the canonical terminology glossary from `docs/dev/terminology.md` to
  `docs/terminology.md` as a project-wide vocabulary reference.
- Added `_snippets/terminology.md` as the shared terminology cross-reference note and reused it
  across command, usage, API, CI, configuration, and developer documentation.
- Completed the command documentation consistency pass across pipeline, config, registry, and
  version commands, including user-facing/runtime terminology, related links, machine-readable
  wording, and troubleshooting sections.
- Updated documentation conventions to clarify user-facing implementation boundaries for command
  pages, including avoiding internal dataclass names, `freeze()` / `thaw()` mechanics, and internal
  DTO names in usage documentation.
- Harmonized the bundled `topmark-example.toml` template into a calmer reference-style starter
  configuration with normalized runtime-policy, configuration-discovery, and TOML-source-local
  wording.
- Added lightweight documentation hygiene validation through `tools/docs/check_docs_hygiene.py`,
  exposed as `nox -s docs_hygiene` and `make docs-hygiene`.
- Added changelog-specific hygiene validation for release heading shape, enforcing
  Keep-a-Changelog-compatible level-3 section structure and heading conventions, disallowed deeper
  headings, and decorative-symbol-free headings.
- Integrated documentation hygiene validation into local verification and release gates, including
  `make verify`, `make release-check`, and `make release-full`.
- Enforced objective documentation hygiene checks for broken snippet includes, malformed
  docs-root-relative include paths, include targets outside `docs/`, nested snippet includes,
  accidental macOS `._*` files, level-2 section separators, heading emoji/decorative-symbol policy,
  and `CHANGELOG.md` heading conventions.
- Integrated documentation hygiene validation into local verification and release gates, including
  `make verify`, `make release-check`, and `make release-full`.
- Enforced objective documentation hygiene checks for broken snippet includes, malformed
  docs-root-relative include paths, include targets outside `docs/`, nested snippet includes,
  accidental macOS `._*` files, level-2 section separators, heading emoji/decorative-symbol policy,
  and `CHANGELOG.md` heading conventions.
- Added smart-punctuation hygiene for Markdown prose and normalized documentation prose to ASCII
  punctuation where appropriate.
- Added `tools/docs/check_code_hygiene.py` to validate Python comments, docstrings, and
  prose-oriented string literals for ASCII-oriented punctuation hygiene.
- Wired Python prose hygiene into nox, Makefile, verification, and release validation paths.

### CI / release / dependency model (completed)

- Migrated to **uv-first dependency model**
- Replaced tox with **nox**
- Implemented **artifact-based CI → release pipeline**
- Added a dedicated multi-platform install-smoke GitHub Actions workflow:
  - validates wheel and sdist installation from built artifacts on Linux, macOS, and Windows
  - verifies isolated installation behavior using clean virtual environments
  - performs lightweight CLI smoke checks from installed artifacts
  - helps detect packaging, dependency, entry-point, and platform-specific installation regressions
- Added dedicated install-smoke workflow documentation covering:
  - workflow purpose and scope
  - artifact-install validation strategy
  - relationship with release and CI workflows
  - supported platforms and Python versions
  - expected smoke-test coverage
- Adopted **SCM-based versioning (setuptools-scm)**
- Corrected the runtime dependency model by promoting `typing-extensions` to core dependencies after
  isolated-environment failures revealed it was still required at runtime.
- Corrected additional implicit dependency by promoting `packaging` to core dependencies after
  pre-commit/isolated-environment usage revealed it is required at runtime.
- Added `deptry` configuration in `pyproject.toml` so optional dependency groups used for
  development and documentation are modeled explicitly during dependency-audit checks.
- Refreshed dependencies and pre-commit hooks during beta stabilization, including removal of an
  obsolete Pyright ignore after improved `tomlkit` typing.
- Hardened CI with:
  - link checks
  - documentation hygiene checks
  - permissions model
  - SHA-pinned actions

Result: release and installation validation are now secure, reproducible, automated, and validated
across multiple platforms through dedicated artifact-install smoke testing.

### Overall status (done)

At this point:

- Core architecture is **fully refactored**
- Legacy implicit behavior is **eliminated**
- System boundaries are **clear and enforced**
- Remaining work is **focused and incremental**, not structural
- Machine-output contract coverage is now strong for config, pipeline, version, registry, and probe
  commands
- The public probe API is now aligned with the CLI probe command while preserving the
  public/internal boundary around resolution internals
- Qualified-vs-local file type identifier semantics are now frozen, implemented, tested, and
  documented across CLI, TOML configuration, API overlays, resolution and filtering, policy lookup,
  registry-facing APIs, diagnostics, and machine output
- Final documentation, generated-site, CLI/help, warning/error wording, beta-semantics,
  command-page, terminology, and machine-readable output terminology reviews have been completed
  through the beta stabilization releases
- Documentation UX, command-page structure, cross-reference conventions, snippet governance, and
  generated-site navigation are now convention-driven and validated through the documentation
  hygiene tooling
- Project-wide terminology, reusable terminology notes, command documentation, TOML template prose,
  Markdown prose hygiene, and Python code-prose hygiene are now aligned with the 1.0 documentation
  governance model
- The canonical `MutableX` / `FrozenX` naming model is finalized across configuration, policy,
  diagnostics, and staged validation-log types.

The project is now in a **late beta stabilization phase**, with broad architecture complete,
in-memory pipeline support explicitly deferred, documentation governance and prose hygiene
established, and the remaining work focused primarily on real-world beta feedback, downstream
ecosystem validation, and final targeted hardening before `1.0.0`.

______________________________________________________________________

## Breaking changes introduced so far

This section summarizes the **externally relevant breaking changes** introduced during the 0.12
refactor series and the 1.0 alpha/beta stabilization line. The emphasis is on **frozen contract and
workflow changes**, not internal implementation details.

### Registry / resolution model

- Built-in processor registration no longer relies on decorator-based or bootstrap-style implicit
  registration.
  - Integrations must use the explicit binding/overlay model.
- Legacy registry/bootstrap entry points were removed, including:
  - `topmark.processors.bootstrap`
  - `topmark.processors.registry`
  - `topmark.registry.resolver`
  - `register_all_processors()`
  - `Registry.ensure_processors_registered()`
- Registry mutation is now fully explicit and split by responsibility:
  - processor registration → `HeaderProcessorRegistry.register(...)`
  - file type registration → `FileTypeRegistry.register(...)`
  - binding → `Registry.bind(...)` / `BindingRegistry.bind(...)`
- Namespace-aware file type lookup now supports qualified identifiers and rejects ambiguous local
  identifiers unless the caller uses the qualified form.
- Registry machine and human outputs now expose canonical qualified identifiers and namespace
  metadata, and add a first-class bindings view.
- Local file type identifiers are accepted at public boundaries only when unambiguous; canonical
  qualified keys are the stable comparison and storage form.
- Public API registry metadata was reshaped to align with the split filetype / processor / binding
  model.
  - Downstream callers using older field names or processor-grouped binding views must update.

Result: registry behavior is now more explicit and deterministic, but downstream registry/plugin/API
consumers must update to the canonical identity and explicit binding model.

### Config / TOML / runtime surface

- Configuration is no longer treated as a single mixed layer.
  - `topmark.toml` handles TOML parsing and whole-source schema validation
  - `topmark.config` handles layered configuration merge and effective runtime configuration
    resolution
  - `topmark.runtime` handles execution-time behavior
- Several older config/TOML helper entry points were removed or relocated.
  - Callers using older helper locations must migrate to the new module layout.
- Generic config/API mapping input is now represented as `ConfigMapping`.
  - The legacy `ArgsLike` alias was removed.
- Configuration-loading entry points were consolidated around TOML-first resolution.
  - Callers needing provenance must explicitly handle resolved sources and mutable configuration
    state.
- Source-local TOML options such as `[config].root` and `[config].strict` now live outside layered
  configuration merging.
- The canonical mutable/frozen runtime naming model was finalized:
  - mutable runtime/configuration dataclasses now consistently use `MutableX`
  - immutable runtime/configuration dataclasses now consistently use `FrozenX`
  - older mixed naming conventions were removed before the 1.0 freeze
- Runtime-facing TOML sections such as `[writer]` are resolved outside layered configuration but
  remain part of the effective TOML surface shown by config output commands and machine-readable
  configuration snapshots.
- Runtime-facing TOML options such as `[writer].strategy` remain outside layered configuration but
  are resolved from TOML and preserved in human-readable and machine-readable configuration output.
- TOML validation is now stricter and happens earlier:
  - unknown top-level sections/keys, malformed known sections, and malformed nested policy sections
    are reported during whole-source TOML loading
  - these diagnostics now participate in shared CLI/API validation behavior
- Policy/config surface changed:
  - `add_only` / `update_only` → replaced by `header_mutation_mode`
  - `skip_compliant` / `skip_unsupported` → replaced by `report`
- Immutable runtime configuration `policy_by_type` keys are now canonical qualified file type
  identifiers.
  - Consumers that inspect resolved runtime configuration or call low-level effective-policy helpers
    must use keys such as `topmark:python` instead of assuming local-only keys such as `python`.
- `policy_by_type`, `include_file_types`, and `exclude_file_types` now share the same identifier
  contract: qualified identifiers are accepted explicitly, and local identifiers are accepted only
  when unambiguous.
- Configuration merge semantics are no longer uniformly "last-wins":
  - some fields accumulate
  - some fields merge key-wise
  - effective runtime configuration is now resolved per path rather than as a single flat snapshot

Result: configuration behavior is clearer and more powerful, but callers relying on older helpers,
older policy tokens, or older TOML layout/validation assumptions must update.

### CLI / output / runtime behavior

- Output format naming changed:
  - legacy `DEFAULT` was removed
  - `TEXT` is now the canonical plain human-output format
- Human rendering is now split cleanly from CLI runtime/printing.
  - Older emitter/import paths were removed or renamed.
- Verbosity and color options moved from the root CLI group to individual commands.
  - Existing invocation patterns may need updating.
- Verbosity and quiet semantics were narrowed:
  - `-v` / `--verbose` applies only to TEXT output.
  - `-q` / `--quiet` applies only to TEXT output on commands that explicitly support output
    suppression.
  - Markdown output is document-oriented and ignores TEXT-oriented verbosity/quiet controls.
  - JSON/NDJSON output is machine-readable and ignores TEXT-oriented presentation controls.
  - Pure informational content-producing commands (`version`, `config defaults`, `config init`, and
    registry commands) no longer expose `--quiet`.
- Runtime-only execution intent is now modeled separately from layered configuration.
  - `RunOptions` now carries runtime behavior such as apply/preview and stdin handling.
- Dry-run / apply semantics are now explicit:
  - preview runs report preview statuses
  - apply runs report terminal write outcomes
- Summary output is now grouped by `(outcome, reason)` rather than by a single collapsed outcome
  label.
- CLI/report surface changes:
  - `--skip-compliant` → replaced by `--report actionable`
  - `--skip-unsupported` → replaced by `--report noncompliant`
  - `--add-only` / `--update-only` → replaced by `--header-mutation-mode`
- Command applicability rules are stricter and enforced at the CLI layer:
  - `strip` rejects check-only mutation, insertion, and generated-header formatting options
  - `probe` rejects mutation, write-mode, diff, summary/reporting, and generated-header controls
  - path-processing commands intentionally do not expose a `--stdin` option flag; content STDIN uses
    `-` plus `--stdin-filename`
  - file-agnostic commands reject positional paths and file-processing STDIN modes as usage errors
- CLI exit-code behavior is now implemented, tested, documented, and treated as a stable 1.0
  contract:
  - `check` / `strip` use `WOULD_CHANGE (2)` as the dry-run "would change" signal
  - `config check` uses `FAILURE (1)` for completed validation with failing diagnostics
  - explicit missing literal inputs produce `FILE_NOT_FOUND (66)`
  - unmatched glob patterns are soft discovery diagnostics for `check` / `strip`
  - `probe` reports unresolved, unsupported, filtered, and unmatched-glob semantic outcomes with
    `UNSUPPORTED_FILE_TYPE (69)`
  - filesystem, configuration, usage, and internal failures use the enum-backed CLI-wide exit-code
    contract

Result: CLI behavior is now more explicit and consistent, but command-line invocation habits, output
snapshots, and downstream automation may need adjustment.

### Machine output contracts

- Machine output is now domain-scoped, schema-driven, and separated from CLI formatting.
- Pipeline summary payloads now use explicit flat rows with:
  - `outcome`
  - `reason`
  - `count`
- `config check` machine output now uses the explicit `config_check` payload/record kind rather than
  a generic summary wrapper.
- `config dump --show-layers` now adds layered provenance output (`config_provenance`) before the
  final flattened runtime configuration payload.
- Configuration machine-readable payloads include TOML-authored runtime sections such as `[writer]`
  when present in the effective TOML source, even though those values are resolved outside the
  layered configuration model.
- `detail_level` is now part of the machine-readable output contract for command families that emit
  projection metadata (notably registry machine output).
- Registry JSON machine output was flattened for 1.0 contract stability:
  - `registry filetypes` → `{meta, filetypes}`
  - `registry processors` → `{meta, processors}`
  - `registry bindings` → `{meta, bindings, unbound_filetypes, unused_processors}`
- Machine-output naming conventions are now explicitly frozen for 1.0, including:
  - shared envelope/meta ownership in `topmark.core.machine.schemas`
  - plural/domain-specific JSON collection keys
  - singular NDJSON record kinds
  - `qualified_key`, `namespace` + `local_key`, and `*_key` reference naming
- Machine-readable configuration, registry, resolution, and probe payloads emit canonical qualified
  file type identifiers when a resolved identity is available.
- Probe machine output now treats probe records as per-path results and includes filtered explicit
  inputs via `status="filtered"` with path-filter, file-type-filter, or generic discovery-filter
  reasons.
- Machine output no longer implies process status: consumers must inspect the CLI exit code
  separately from JSON/NDJSON payloads.

Result: machine-readable formats are much more stable and structured, but downstream consumers that
relied on older payload naming or outcome-keyed summaries must update.

### Documentation / docs build behavior

- Documentation now assumes the TOML → layered configuration → runtime overlay architecture and the
  new CLI/output model.
- Generated API/reference pages are part of the docs build contract.
  - missing or stale generated pages can now fail `mkdocs build --strict`
- Documentation/tooling now relies on dedicated formatter config files:
  - `.mdformat.toml`
  - `.taplo.toml`
- Built-site link checking (`links-site`) is now part of the CI path that gates release-artifact
  creation on tag pushes.
- Documentation hygiene and Python prose hygiene validation are now part of local verification and
  release validation.
  - broken snippet includes, malformed include paths, nested snippet includes, accidental macOS
    `._*` files, missing level-2 section separators, and smart punctuation in Markdown prose can now
    fail docs/tooling gates when warning-failure mode is enabled
  - snippet-related maintainability issues may be reported as non-fatal warnings
- Documentation and code-prose hygiene are now split across dedicated tooling:
  - Markdown/MkDocs/snippet hygiene uses `tools/docs/check_docs_hygiene.py`, exposed through
    `make docs-hygiene` and `nox -s docs_hygiene`
  - Python comments, docstrings, and prose-oriented strings use `tools/docs/check_code_hygiene.py`,
    exposed through `make code-hygiene` and `nox -s code_hygiene`
- User and developer documentation now treats qualified file type identifiers as the canonical
  internal representation and documents local identifiers as an unambiguous public-input
  convenience.
- The canonical terminology glossary moved from `docs/dev/terminology.md` to `docs/terminology.md`.
  - Internal links and external references to the old developer-only glossary location must be
    updated.
- Repeated terminology cross-reference notes now use `_snippets/terminology.md`.
- The canonical terminology glossary moved from a developer-only page to the project-wide
  `docs/terminology.md` reference location.

Result: documentation is more accurate and better validated, but docs generation, documentation
hygiene, and code-prose hygiene are now stricter than before.

### Developer tooling / CI / release workflow

- tox was removed; contributors and CI now use `nox` with uv-backed environments.
- The project no longer uses committed `requirements*.txt` / `constraints.txt` as the primary
  dependency-management model.
  - `uv.lock` is now the canonical lock artifact.
- Package versioning no longer uses a manually maintained static `[project].version`.
  - versions are now derived from Git tags via `setuptools-scm`
- Release workflow behavior changed significantly:
  - release publishing no longer builds the repository in the privileged workflow
  - CI now builds and uploads release artifacts on tag pushes
  - the privileged release workflow downloads, verifies, and publishes those artifacts
- Release validation no longer compares tags to static `pyproject.toml` version metadata.
  - it now validates SCM-derived artifact versions against the resolved release tag
- Release/contributor workflow no longer includes a manual version-bump step.
- Compact PEP 440 prerelease tags are now preferred (`vX.Y.ZaN`, `vX.Y.ZbN`, `vX.Y.ZrcN`).
- Dependencies and pre-commit hook revisions are refreshed as part of beta stabilization, and type
  expectations may tighten as dependency metadata improves.
- `typing-extensions` is now treated as a runtime dependency rather than an implicitly available
  development-only/transitive dependency; packaging and isolated-environment installs now reflect
  the actual runtime import surface.
- Documentation hygiene and Python code-prose hygiene are exposed as first-class local/tooling gates
  through `make docs-hygiene`, `make code-hygiene`, `nox -s docs_hygiene`, and
  `nox -s code_hygiene`.
  - `make verify`, `make release-check`, and `make release-full` now include documentation and
    code-prose hygiene validation
- GitHub Actions behavior is more aggressively gated by changed-file buckets on pull requests, so
  some jobs may now be skipped unless relevant files changed.

Result: contributor/release workflow is more secure and reproducible, but maintainers must update
both their mental model and automation expectations for CI, publishing, dependency management, and
versioning.

### Overall impact

The major breaking changes are no longer about isolated helper removals; they are about a **new
system shape**:

- explicit registry/binding model
- layered TOML/configuration/runtime boundaries
- explicit preview/apply runtime model
- schema-driven machine output with domain-specific JSON envelopes and stable NDJSON record kinds
- uv/nox-based tooling and artifact-based release automation
- stricter documentation governance with convention-backed documentation hygiene, changelog
  validation, terminology governance, and code-prose hygiene validation

The 1.0 task is therefore no longer large-scale redesign, but **contract freeze, documentation
freeze, workflow stabilization, and final hardening** on top of these already-landed changes.

______________________________________________________________________

## Still undecided / still to do

This section captures the remaining **post-beta stabilization, ecosystem validation, and targeted
hardening work** before `1.0.0`.

The large structural refactors, contract-freeze decisions, beta validation gates,
documentation-governance work, command-page freeze review, terminology alignment, TOML-template
harmonization, and prose-hygiene tooling work are complete.

What remains is primarily:

- real-world beta feedback,
- downstream ecosystem validation,
- compatibility preservation,
- targeted hardening from concrete findings,
- and explicitly deferred post-1.0 scope.

### Registry / resolution freeze

The registry and resolution identifier contract is now frozen for 1.0.

Completed decisions:

- Canonical file type identity is the qualified key, for example `topmark:python`.
- Local identifiers, such as `python`, remain accepted at public boundaries only when unambiguous.
- Ambiguous local identifiers require the qualified form.
- `include_file_types`, `exclude_file_types`, and `policy_by_type` all share the same identifier
  semantics.
- Effective runtime configuration and runtime policy lookup use canonical qualified keys.
- `topmark probe` and `topmark.api.probe()` are the accepted 1.0 resolution explainability surfaces.
- Low-level helpers such as `probe_resolution_for_path()` remain advanced/internal debugging
  surfaces outside the `topmark.api` stability contract.
- Registry discovery/query commands remain deferred beyond 1.0.

Remaining work is limited to real-world beta validation, targeted hardening, downstream ecosystem
validation, and ensuring generated API references continue reflecting the frozen public/internal
boundary as the code evolves.

### In-memory pipeline: implement or defer

This was the largest remaining product/architecture decision before 1.0 and is now resolved.

- In-memory pipeline support is **explicitly deferred beyond 1.0**.

Current status:

- design drafted
- implementation not started
- architecture direction understood
- explicitly deferred for 1.0 contract freeze

Recorded decision:

- defer in-memory pipeline support to post-1.0
- future design considerations retained for post-1.0 work:
  - whether mixed file + memory inputs are allowed in one run
  - how synthetic paths/display names should be represented
  - whether stdin should be modeled through the same abstraction

For 1.0:

- the existing file-based pipeline remains the only supported execution model
- stdin continues to be handled via the existing runtime mechanisms

Post-1.0:

- introduce an `InputSource` abstraction
- enable memory-backed pipeline execution
- revisit test strategy to split between memory-based unit tests and filesystem integration tests

### API / CLI / presentation boundary freeze

The separation is frozen for 1.0. Remaining work is limited to stability monitoring, consistency
validation, and targeted hardening rather than boundary redesign:

- Keep monitoring for any remaining Click-facing concerns in non-CLI modules.
- Keep formatting, TEXT verbosity/quiet, and color decisions strictly split between:
  - CLI policy/orchestration
  - pure presentation rendering
  - core/domain logic
- Confirm that TOML validation diagnostics surface consistently in CLI and API flows without leaking
  CLI-specific formatting concerns into shared validation logic.
- Keep `topmark.api.runtime` internal; public callers should use `topmark.api.probe()`,
  `topmark.api.check()`, and `topmark.api.strip()` rather than runtime helpers.
- Keep `topmark.config.overrides.PolicyOverrides` and `topmark.config.overrides.ConfigOverrides`
  internal; public callers use mapping-based API inputs instead.
- Confirm that provenance inspection (`config dump --show-layers`) remains an inspection concern and
  does not leak into validation-oriented commands or stable public API contracts.
- Keep release-automation concerns artifact/download-oriented and scoped to CLI/automation, not to
  public Python API surfaces.

### Config / validation contract freeze

The architecture is stable, and the main public configuration, validation, provenance, and
identifier semantics are frozen. Remaining work is limited to real-world beta validation and
explicit post-1.0 deferrals.

Frozen decisions:

- Typed override boundary is now frozen:
  - `PolicyOverrides` and `ConfigOverrides` are internal CLI/API orchestration bridge types
  - public Python callers use plain mapping-based `config`, `policy`, and `policy_by_type` inputs
- Qualified/local file type identifier semantics are now frozen:
  - public inputs may use qualified identifiers or unambiguous local identifiers
  - config freeze normalizes file type filters and `policy_by_type` keys to canonical qualified keys
  - runtime policy lookup uses canonical qualified keys
- Freeze and document the staged configuration-validation model now implemented internally:
  - TOML-source diagnostics
  - merged-config diagnostics
  - runtime-applicability diagnostics
- Project-wide terminology and validation-stage wording are now aligned across CLI help,
  machine-readable output, command pages, API documentation, and generated developer references.
- Keep staged validation primarily internal for 1.0, with only the flattened compatibility
  diagnostics contract exposed at exception, presentation, and machine-readable output boundaries.
- `[config].strict` is now the frozen public configuration-loading strictness knob for 1.0.
- Confirm that sanitization/runtime-applicability warnings intentionally remain inside the effective
  `[config].strict` gate for 1.0.
- TOML validation, config validation, runtime overlay, and typed layered provenance remain clearly
  separated responsibilities.
- Explicit configuration schema versioning is deferred beyond 1.0:
  - no `[config].version` or equivalent schema-version key is added for 1.0
  - schema versioning will be introduced only when a future non-additive schema change requires it

Recommended direction:

- keep the current TOML → layered configuration → runtime overlay split,
- keep canonical qualified file type identifiers as the internal frozen representation,
- keep `[config].strict` as the public configuration-loading strictness knob for 1.0,
- keep runtime-facing TOML sections such as `[writer]` outside layered configuration while
  preserving them in configuration output snapshots,
- freeze the staged validation semantics now implemented internally,
- keep flattened diagnostics as a derived compatibility/reporting surface only at exception,
  presentation, and machine-readable output boundaries,
- defer broader staged-gate exposure in CLI/API/machine output unless clearly justified before final
  freeze,
- keep explicit config schema versioning deferred until a future non-additive schema change requires
  it.

### Output contract freeze

Output architecture work is complete. Machine-readable implementation, human-output rendering,
tests, reference documentation, CLI/help wording, warning/error wording, command-page wording,
terminology alignment, and beta-semantics reviews are frozen for the beta line.

Machine-readable output decisions:

- Keep flattened `{level, message}` config diagnostics as the accepted 1.0 machine contract. Richer
  TOML-specific structure is explicitly deferred beyond 1.0.
- Registry machine-readable output contract frozen after the flattened JSON-envelope cleanup
  (`filetypes`, `processors`, `bindings`, `unbound_filetypes`, `unused_processors`).
- Probe machine-readable output contract added and covered with focused JSON/NDJSON tests (per-path
  `probes` JSON collection and `probe` NDJSON records, including filtered explicit inputs).
- `detail_level` semantics frozen:
  - `--long` controls projection/data depth across formats where supported
  - `detail_level` reflects projection in machine output when present
  - TEXT verbosity remains independent and presentation-only
- Field naming consistency audited across domains and documented in the machine-readable output
  reference.
- Keep `docs/dev/machine-formats.md` and `docs/dev/machine-output.md` aligned as the canonical
  machine-readable output reference documentation.

Human output decisions:

- TEXT and Markdown output contracts reviewed across command groups.
  - TEXT remains compact/console-oriented and may use `-v` / `-vv` for progressive disclosure and
    `--quiet` only where the command exposes meaningful status, inspection, or mutation semantics.
  - Markdown is explicitly document-oriented and ignores TEXT-oriented verbosity/quiet controls.
  - `--long` remains the data/detail-depth control where supported.
- Verbosity semantics (`default`, `-v`, `-vv`, `--quiet`) are frozen for 1.0.
  - `-v` / `-vv` are TEXT-oriented progressive-disclosure controls.
  - `--quiet` is TEXT-oriented and only exposed where suppressing output still leaves a useful
    status, inspection, or mutation signal.
  - Pure informational content-producing commands (`version`, `config defaults`, `config init`, and
    registry commands) intentionally do not support `--quiet`.
- Focused human-output tests added for version, diagnostics, config, registry, and pipeline command
  groups.
- Color backend decision frozen for 1.0:
  - keep `yachalk` as an internal CLI presentation dependency
  - keep semantic styling routed through `StyleRole`, `Theme`, `TextStyler`, and `maybe_style()`
  - defer Rich / `rich-click` migration until after 1.0 unless a concrete release blocker appears
- Hint-ordering strategy is frozen for 1.0.
  - Continue keeping presentation logic fully out of CLI command functions.

CLI exit-code work is now complete for the 1.0 contract freeze: `docs/usage/exit-codes.md` is the
canonical contract, implementation is centralized around pipeline/result prioritization, focused
`pytest.mark.exit_code` coverage enforces the contract, and README, docs index, shared options,
filtering, pre-commit, command-group pages, command pages, API docs, architecture docs, and
machine-readable output docs link or summarize the same behavior. The CLI command-applicability,
usage-error, and user-facing policy/report contracts are also frozen and documented; remaining CLI
work is now limited to any last warning/error wording cleanup discovered during release validation.

### Tooling / CI / release follow-up

The security, workflow, release, tooling-parity, documentation-hygiene, changelog-hygiene, and
Python prose-hygiene work is functionally complete. What remains is primarily follow-up validation,
ecosystem monitoring, and explicitly deferred post-1.0 tooling decisions.

Remaining follow-up:

- The current **artifact-based CI → release split** is accepted as the stable 1.0 release
  architecture, with any further factoring deferred post-1.0.
- Keep validating that:
  - changed-file buckets remain correct
  - tag-push artifact creation remains aligned with release expectations
  - artifact verification continues to match publish behavior
- The current explicit `tests` matrix setup remains accepted for 1.0; further factoring around the
  shared setup composite action is deferred post-1.0.
- Workflow formatting/style rules are governed by checked-in tool configuration and release
  validation gates; broader editor-style guidance remains non-blocking for 1.0.
- Keep validating that Nox, pre-commit, local `.venv`, editor integrations, CI jobs, and the
  artifact-based release workflow all consume the same formatter/tool configuration.
- Keep documentation hygiene validation integrated in local and release gates as the documentation
  conventions evolve.
- Keep Python code-prose hygiene validation integrated in local and release gates as comments,
  docstrings, tooling prose, and generated documentation conventions evolve.
- Keep MkDocs 1.x as the accepted documentation generator through the `v1.0.0` beta stabilization
  releases because the current strict docs build, link checks, generated API pages, release
  validation, and cross-platform packaging/install validation are green. Evaluate ProperDocs as a
  post-beta / post-1.0 tooling follow-up unless MkDocs becomes a concrete release blocker before
  final `1.0.0`.

### Human-facing policy / behavior questions

The main user-facing policy, reporting, terminology, and behavior questions are frozen for 1.0.
Remaining work is limited to monitoring real-world beta feedback, preserving compatibility, and
keeping documentation/help output aligned:

- The default processing mode remains **"all supported file types"** for 1.0.
- A stricter whitelist-first default remains a possible post-1.0 design question, not a 1.0 blocker.
- Public API callers continue using stable string literals for policy tokens in 1.0; a dedicated
  public enum may be revisited later.
- Summary reason strings remain presentation-facing labels rather than a separate stable integration
  contract.
- Keep confirming that API, CLI, and generated documentation consistently use the `report` model and
  no longer reference legacy `skip_*` filters.
- Keep CLI help examples aligned with canonical option/command constants to avoid drift between
  documentation and implementation.
- Keep Markdown documentation and examples aligned with the document-oriented output contract rather
  than treating Markdown as layout-equivalent TEXT output.
- File-recognition / resolution explainability is now accepted for 1.0 via the read-only
  `topmark probe` command and `topmark.api.probe()`.
  - explicit inputs filtered during discovery are reported as `filtered` probe results with broad
    path-filter, file-type-filter, or generic discovery-filter reasons
  - registry query/filter commands remain deferred
  - probe is distinct from `check` / `strip` and does not perform header comparison, planning, or
    write/apply semantics
  - public API probe results expose stable DTOs rather than resolver enums, pipeline contexts, or
    registry internals
  - file type identifiers in probe filters follow the frozen qualified/local identifier contract
- User-facing policy/report flag semantics are now accepted for 1.0:
  - `--report` is a human per-file output filter for `check` and `strip`
  - `header_mutation_mode` controls `check` insertion/update intent
  - `empty_insert_mode` classifies empty/empty-like files for insertion eligibility and does not by
    itself permit insertion
  - safety gates remain authoritative over all policy options

### Overall status (undecided / to do)

The remaining work is no longer broad architectural redesign or contract freeze.

What is left is mainly:

- **real-world beta feedback**
- **ecosystem compatibility validation**
- **downstream machine-readable output consumer validation**
- **targeted hardening from concrete beta findings**
- **ongoing documentation-governance, changelog-governance, and prose-hygiene validation**
- **explicit post-1.0 follow-up for deferred scope**

That means TopMark is now in the late beta stabilization stage of the 1.0 effort: validating the
frozen contracts in realistic environments, preserving compatibility, maintaining documentation and
prose-governance quality, validating downstream ecosystem behavior, and avoiding new scope unless a
concrete release blocker appears.

______________________________________________________________________

## 1.0 readiness checklist

TopMark 1.0 follows a **contract-first** release strategy: all externally observable behavior (API
surface, configuration semantics, machine-readable formats, CLI behavior, documentation behavior,
and release workflow expectations) must be stable, documented, and well-tested.

The large refactors, beta gates, documentation freeze review, documentation-governance work,
command-page consistency review, terminology stabilization, mutable/frozen runtime naming cleanup,
prose-hygiene tooling, changelog hygiene, and release-validation passes are complete. This checklist
now records the frozen 1.0 contract state and remaining post-beta validation posture:

- what is already stable for `1.0.0`
- what has been explicitly deferred with rationale
- what remains as post-beta validation or post-1.0 follow-up

### Must finish before 1.0

These are release blockers unless explicitly deferred with a documented rationale.

#### [Must] Architecture & boundaries

- [x] Clear separation between CLI, presentation, API, and core/domain layers
- [x] Runtime behavior separated cleanly from layered configuration
- [x] No CLI-specific concerns (verbosity, color, formatting) in core logic
- [x] Remaining public-vs-internal boundaries frozen and documented for:
  - [x] `topmark.api.probe()` accepted as the stable public probe API
  - [x] `topmark.api.runtime` documented as internal API orchestration infrastructure
  - [x] low-level resolution/probe objects documented as advanced/internal rather than stable public
    DTOs
  - [x] typed override surfaces (`PolicyOverrides`, `ConfigOverrides`) classified as internal
    CLI/API orchestration bridge types
- [x] Documentation governance and generated-site structure documented as part of the maintained
  developer/tooling boundary
- [x] User-facing command documentation avoids internal runtime implementation details such as
  concrete mutable/frozen dataclass names, `freeze()` / `thaw()` mechanics, and internal DTO names
- [x] Canonical mutable/frozen runtime type naming finalized across public/runtime-facing developer
  surfaces as `MutableX` / `FrozenX`

#### [Must] Machine output contracts

- [x] No presentation leakage in machine output
- [x] Machine outputs covered by focused JSON + NDJSON contract tests for all command groups
  - [x] config commands
  - [x] pipeline commands
  - [x] version command
  - [x] registry commands
  - [x] probe command
  - [x] top-level command groups reviewed for any remaining machine-readable output gaps
- [x] Final schema freeze review completed
  - [x] `(outcome, reason, count)` summary rows frozen
  - [x] `detail_level` semantics frozen
    - [x] `--long` is the cross-format projection selector (brief vs long)
    - [x] `detail_level` reflects this projection in machine output when emitted
    - [x] verbosity remains a separate human-output concern
  - [x] field naming consistency audited across domains
- [x] `config check` payload naming stabilized as `config_check`
- [x] `strict` naming stabilized in config-validation payloads
- [x] Decision made on the 1.0 machine contract for config/TOML diagnostics:
  - [x] flattened `{level, message}` is explicitly accepted as final
  - [x] richer TOML-specific structure is not required before 1.0 freeze (explicitly deferred)
- [x] `docs/dev/machine-formats.md` reviewed and frozen as a reference contract
- [x] `docs/dev/machine-output.md` reviewed and aligned with the current command contracts
- [x] Probe machine output reviewed and documented as part of the 1.0 machine contract, including
  filtered explicit inputs and refined filter reasons

#### [Must] Human output contracts

- [x] TEXT and MARKDOWN outputs reviewed for consistency across command groups
  - [x] config commands
  - [x] pipeline commands
  - [x] registry commands
  - [x] version command
  - [x] diagnostics presentation helpers
  - [x] probe command
- [x] Warning/error phrasing reviewed for CLI-wide consistency around command applicability,
  usage-error boundaries, and policy/report semantics
- [x] Verbosity semantics (default, `-v`, `-vv`, `--quiet`) documented and considered stable
  - [x] CLI plumbing normalized around typed `TopmarkCliState`
  - [x] `-v` / `-vv` treated as TEXT-oriented progressive-disclosure controls
  - [x] `-q` / `--quiet` treated as TEXT-oriented output suppression only where the command exposes
    a useful status, inspection, or mutation signal
  - [x] Markdown output ignores TEXT-oriented verbosity/quiet controls
  - [x] machine-readable formats ignore TEXT-oriented presentation controls
  - [x] pure informational content-producing commands (`version`, `config defaults`, `config init`,
    and registry commands) intentionally do not support `--quiet`
  - [x] final user-facing documentation reviewed and aligned
- [x] Decision made on hint-ordering / "primary hint" semantics for 1.0
  - headline hint selection is based on severity prioritization
  - exact ordering and wording are not part of the stable contract
- [x] Documentation wording, command-page structure, cross-reference labels, and generated-site
  navigation reviewed for consistency with the frozen human-output contract

#### [Must] CLI behavior

- [x] Exit codes implemented, tested, documented, and considered stable
  - [x] canonical contract added in `docs/usage/exit-codes.md`
  - [x] enum-backed exit-code names used consistently in user-facing documentation
  - [x] command and command-group pages aligned with the canonical contract
  - [x] README and docs index include CI/scripting-oriented summaries
  - [x] filtering and pre-commit documentation explain missing-vs-unmatched input behavior
  - [x] machine-output, API, and architecture docs clarify that process status remains the CLI exit
    code and is separate from JSON/NDJSON payloads
  - [x] focused `pytest.mark.exit_code` tests cover success, dry-run would-change, config
    validation, usage errors, missing inputs, permission/write failures, probe semantic outcomes,
    unmatched glob behavior, and mixed-result priority
- [x] CLI command applicability rules fully documented and enforced
  - [x] policy-option applicability for `check`, `strip`, and `probe`
  - [x] stdin/list-vs-content handling frozen and documented
  - [x] `-` plus `--stdin-filename` accepted as the only content-STDIN form
  - [x] unsupported `--stdin` option spellings rejected with actionable usage errors
  - [x] file-agnostic commands reject positional paths and file-processing STDIN modes
  - [x] strict config-checking behavior documented at command level where applicable
  - [x] command help/epilog wording aligned for main CLI entry point, command groups and commands
  - [x] TEXT-oriented verbosity/quiet applicability documented and enforced by command
  - [x] pure informational content-producing commands reject `--quiet` (`version`,
    `config defaults`, `config init`, and registry commands)
- [x] Final review of user-facing policy/report flags completed
  - [x] `--report` semantics frozen
  - [x] `--header-mutation-mode` semantics frozen
  - [x] `EmptyInsertMode` token semantics frozen
- [x] Decision made on registry discovery and file-recognition debugging commands
  - [x] registry filtering/query surface explicitly deferred
  - [x] file-recognition / resolution probe command accepted for 1.0
  - [x] command scope is limited to read-only discovery/diagnostics and documented as distinct from
    `check` / `strip`
- [x] CLI command documentation follows the finalized command-page structure conventions for shared
  options, command-specific options, applicability, output behavior, machine-readable output, exit
  codes, related commands, related docs, and troubleshooting

#### [Must] Configuration & validation

- [x] Config keys and semantics documented and considered stable
- [x] Mutable/frozen configuration, policy, diagnostics, and staged validation-log type naming
  finalized with the canonical `MutableX` / `FrozenX` model
- [x] Qualified/local file type identifier semantics documented and considered stable
  - [x] canonical internal identity is the qualified key, such as `topmark:python`
  - [x] local identifiers are accepted at public boundaries only when unambiguous
  - [x] `include_file_types`, `exclude_file_types`, and `policy_by_type` share the same identifier
    semantics
  - [x] effective runtime configuration and runtime policy lookup use canonical qualified keys
- [x] `config init`, `config defaults`, `config check`, and `config dump` outputs aligned and frozen
- [x] Runtime-facing TOML sections such as `[writer]` are preserved in configuration output
  snapshots without reintroducing runtime state into layered configuration
- [x] Synthetic config provenance is typed and preserved until presentation or serialization
  boundaries
- [x] Decision made and documented on the final public override model
  - [x] public API command signatures accept plain mapping-based policy/config overlays
  - [x] internal typed override helpers (`PolicyOverrides`, `ConfigOverrides`) classified as
    internal CLI/API orchestration bridge types
- [x] Package/application versioning model documented and stable
  - [x] Git tags are the single source of truth via `setuptools-scm`
  - [x] static `[project].version` is gone
  - [x] release validation uses SCM-derived artifact versions
  - [x] privileged release jobs consume CI-built artifacts
  - [x] no manual version-bump step remains
- [x] Preferred release-tag conventions documented and stable
- [x] `[config].strict` documented and stable as a TOML-source-local configuration-loading option
- [x] Whole-source TOML schema validation rules documented and considered stable
- [x] TOML/config/runtime split documented and implemented
- [x] Per-path effective runtime configuration resolution implemented
- [x] Validation semantics frozen for 1.0:
  - [x] validation always runs
  - [x] strictness controls raise vs report behavior
  - [x] CLI and API use the same validation path
  - [x] staged validation logs implemented internally
  - [x] effective validity now evaluates TOML-source, merged-config, and runtime-applicability
    diagnostics together
  - [x] `[config].strict` remains the public configuration-loading strictness knob
  - [x] `ConfigValidationError` now has focused coverage for staged-count summaries and
    exception-boundary flattening
  - [x] final decision made on 1.0 exposure: keep staged validation primarily internal with
    flattened compatibility diagnostics only at exception/presentation/output boundaries
- [x] Decision made on explicit configuration schema versioning
  - [x] no schema-version key is added for 1.0
  - [x] schema versioning is deferred until a future non-additive schema change requires it

#### [Must] Pipeline & testing

- [x] Decision taken on in-memory pipeline support
  - [x] explicitly deferred beyond 1.0 with rationale
- [x] Test strategy clarified for 1.0:
  - [x] filesystem-backed pipeline remains the supported execution model for 1.0
  - [x] memory-backed unit-test/API split deferred with the in-memory pipeline work
- [x] Line-ending support policy audited and frozen for 1.0
  - [x] decision made: only LF (`\n`), CRLF (`\r\n`), and CR (`\r`) are recognized physical newline
    styles
  - [x] non-standard Unicode separators such as NEL (`U+0085`), Line Separator (`U+2028`), and
    Paragraph Separator (`U+2029`) are treated as ordinary content, not line endings
  - [x] pipeline behavior and diagnostics aligned with that decision
  - [x] hypothesis/property tests aligned with the intended supported line-ending model
  - [x] user-facing docs updated; newline handling remains a fixed contract, not a configurable
    policy surface
- [x] Namespace-aware registry lookup and deterministic ambiguity behavior covered by tests
  - [x] registry identity tests cover local, qualified, default-namespace, ambiguous, malformed, and
    unknown identifier cases
  - [x] config, TOML, resolution, CLI, and API tests cover normalized file type filters and
    `policy_by_type` behavior
- [x] Probe command and public probe API resolution-candidate and filtered explicit-input reporting
  are covered by focused resolution, discovery, pipeline-step, CLI human-output, CLI exit-code,
  machine-output, and API tests, including path-filter, file-type-filter, fallback discovery-filter,
  missing-input, and candidate-shape cases, without weakening the existing check/strip output
  contract
- [x] TOML-layer validation paths have focused coverage
- [x] Empty / empty-like file handling is explicit and idempotent
- [x] Resolver treats content matcher exceptions as safe misses
- [x] Preview vs apply semantics are consistent end-to-end
- [x] Explicit missing literal inputs are preserved as synthetic pipeline results and participate
  consistently in human output, machine output, summaries, and exit-code selection
- [x] Unmatched glob behavior is frozen and tested: non-fatal for `check` / `strip`, semantic
  `UNSUPPORTED_FILE_TYPE (69)` for `probe`
- [x] API and CLI policy override behavior have focused coverage
- [x] Engine applies per-path configs and policy registries correctly

#### [Must] Tooling / dependency / release ecosystem

- [x] Decision made on long-term color backend policy
  - [x] keep `yachalk` for 1.0 because it is confined to CLI presentation internals
  - [x] Rich / `rich-click` migration deferred post-1.0 unless a concrete blocker appears
- [x] Formatter/tool configuration split stabilized and documented
  - [x] `.mdformat.toml` is the Markdown formatter configuration used by mdformat-based local,
    pre-commit, and nox validation paths
  - [x] `.taplo.toml` is the TOML formatter/linter configuration shared by Taplo CLI, pre-commit,
    CI, and editor integrations
- [x] Tooling environments verified to consume the same formatter/plugin/tool expectations:
  - [x] nox
  - [x] pre-commit
  - [x] local `.venv`
  - [x] editor integrations
  - [x] CI
  - [x] artifact-based release workflow
- [x] Artifact-based CI → release pipeline implemented and documented
- [x] GitHub prerelease publication enabled for prerelease tags while preserving TestPyPI package
  publication for prerelease artifacts
- [x] Dedicated multi-platform install-smoke workflow implemented and documented
  - [x] validates wheel and sdist installation from built artifacts
  - [x] validates isolated installation behavior on Linux, macOS, and Windows
  - [x] validates CLI entry-point availability from installed artifacts
  - [x] performs lightweight installed-artifact CLI smoke checks
  - [x] integrated into the documented CI/release validation model
  - [x] documented in dedicated CI workflow documentation
- [x] Positive release-path rehearsal accepted as complete for the path to `1.0.0`
  - [x] prerelease flow (`v1.0.0aN`) validated
  - [x] clean wheel install validated
  - [x] clean sdist install validated
  - [x] uv-managed development environment validated
- [x] TestPyPI install validated with PyPI fallback for dependencies
  - [x] dependency resolution validated in isolated environments
- [x] SCM-derived artifact version validated against the current source state
  - [x] remaining follow-up issues, if any, resolved or explicitly accepted for the beta line
- [x] Runtime dependency model verified against isolated environments
  - [x] `typing-extensions` promoted to core dependencies after isolated-environment failure
  - [x] `packaging` promoted to core dependencies after pre-commit/isolated-environment failure
  - [x] dependency-audit configuration added (`deptry`) to reduce risk of further implicit
    runtime/development dependency drift
  - [x] pre-commit / clean-environment / packaging verification rerun on the final dependency set
- [x] Documentation hygiene tooling integrated into the local and release validation ecosystem
  - [x] `tools/docs/check_docs_hygiene.py` validates snippet/include and section-structure hygiene
  - [x] `nox -s docs_hygiene` exposes the check in nox
  - [x] `make docs-hygiene` exposes the check through the Makefile
  - [x] `make verify`, `make release-check`, and `make release-full` include documentation hygiene
    validation
- [x] Python code-prose hygiene tooling integrated into the local and release validation ecosystem
  - [x] `tools/docs/check_code_hygiene.py` validates Python comments, docstrings, and prose-oriented
    string literals for ASCII-oriented punctuation hygiene
  - [x] `nox -s code_hygiene` exposes the check in nox
  - [x] `make code-hygiene` exposes the check through the Makefile
  - [x] `make verify`, `make release-check`, and `make release-full` include code-prose hygiene
    validation
- [x] Changelog hygiene validation integrated into documentation hygiene checks
  - [x] release headings use `## [version] - YYYY-MM-DD`
  - [x] release sections use the accepted level-3 heading set
  - [x] level-4 and deeper headings are rejected in `CHANGELOG.md`
  - [x] decorative symbols are rejected in headings
- [x] Dependency and pre-commit hook refresh completed during beta stabilization
  - [x] obsolete Pyright ignore removed after improved `tomlkit` typing

#### [Must] Beta stabilization and validation gates

Before cutting the final `1.0.0` release, maintain and record positive validation passes across the
beta stabilization series. Packaging validation is intentionally handled through nox sessions,
GitHub workflows, and release workflow checks rather than dedicated pytest tests.

- [x] Packaging validation completed
- [x] GitHub prerelease visibility validated for the beta line
  - [x] `v1.0.0b1` and `v1.0.0b2` GitHub prereleases backfilled from existing tags
  - [x] `v1.0.0b3` published as a GitHub prerelease through the release workflow
  - [x] prerelease package publication remains routed to TestPyPI
- [x] `nox -s package_check` builds wheel and sdist artifacts and passes `twine check`
- [x] wheel artifact installs into a clean environment and exposes the `topmark` console script
- [x] sdist artifact installs into a clean environment and exposes the `topmark` console script
- [x] dedicated install-smoke workflow validates installation and lightweight CLI execution on
  Linux, macOS, and Windows
- [x] published `v1.0.0b3` artifacts validated successfully on Windows, macOS, and Ubuntu through
  real installation and execution testing
- [x] uv-managed development environment works with the documented development extras
  - [x] TestPyPI upload/install rehearsal succeeds for the prerelease path
  - [x] dependency resolution succeeds without undeclared runtime dependencies
  - [x] generated version metadata matches the release tag through `setuptools-scm`
- [x] CLI smoke validation completed from installed artifacts; validation performed primarily
  through isolated `nox -s qa` CLI test coverage plus wheel/sdist/TestPyPI installation rehearsal
  - [x] `topmark version`
  - [x] `topmark config defaults`
  - [x] `topmark config check`
  - [x] `topmark registry filetypes`
  - [x] `topmark registry processors`
  - [x] `topmark probe ...`
  - [x] `topmark check ...`
  - [x] `topmark strip ...`
- [x] Documentation validation completed
  - [x] `make docs-build`
  - [x] `make links-site`
  - [x] `make docs-hygiene`
  - [x] `make code-hygiene`
  - [x] Markdown prose and Python code-prose hygiene pass validation
  - [x] generated API reference pages are current
  - [x] strict MkDocs build passes in a clean environment
  - [x] snippet/include hygiene and level-2 section-separator conventions pass validation
  - [x] `CHANGELOG.md` heading and section conventions pass validation
- [x] QA validation completed
  - [x] `make test` (runs `nox -s qa`)
  - [x] `make release-check`
  - [x] `make release-full`, or an equivalent CI-backed full release gate, passes
- [x] Tooling parity validation completed
  - [x] nox formatter/linter behavior matches pre-commit behavior
  - [x] local `.venv` behavior matches nox expectations where documented
  - [x] VS Code/editor integration expectations match `.mdformat.toml`, `.taplo.toml`, Ruff, and
    Pyright configuration
  - [x] CI uses the same formatter, linter, type-checking, docs, and packaging expectations as the
    documented local release gates
- [x] Final beta freeze review completed
  - [x] no alpha-only semantics remain exposed in CLI help, docs, or machine-readable output
  - [x] warning and error wording remains consistent with the frozen command-applicability and
    exit-code contracts
  - [x] command-page wording, terminology cross-references, TOML template prose, and user-facing
    implementation-boundary guidance are aligned with the 1.0 documentation conventions
  - [x] accepted imperfections are recorded explicitly as post-1.0 follow-up or non-blocking beta
    notes
    - [x] MkDocs 1.x remains accepted through the beta stabilization releases; ProperDocs evaluation
      is deferred unless the current documentation toolchain becomes a concrete release blocker
    - [x] Documentation UX, command-page structure, cross-reference conventions, snippet governance,
      generated-site navigation, Markdown prose hygiene, and Python code-prose hygiene are accepted
      for the beta line and enforced through lightweight validation tooling

### Strongly recommended (but not blockers)

These items have been completed for the beta line or explicitly deferred. This section is retained
as a record of recommended freeze work that has now been closed.

#### [Recommended] Registry / resolution

- [x] Decide whether local identifiers remain supported for 1.0
  - [x] local identifiers remain supported at public boundaries only when unambiguous
  - [x] canonical qualified keys remain the internal storage, comparison, and output form
- [x] Resolution/probe helper surface reviewed for final public/internal stability wording
  - [x] `topmark.api.probe()` is the public stable surface
  - [x] low-level resolution helpers remain advanced/internal and outside the `topmark.api` snapshot
- [x] Canonical terminology (`qualified_key`, `file_type_id`, `local_key`, etc.) reviewed one final
  time across docs and public surfaces

#### [Recommended] Human output

- [x] Human-facing registry output reviewed/frozen for qualified identifier presentation
- [x] Diff rendering policy reviewed across pipeline commands
- [x] Markdown layout direction explicitly documented as document-oriented, not text-equivalent

#### [Recommended] Machine output

- [x] Add stable examples for any remaining command categories in `docs/dev/machine-formats.md`
- [x] Add examples showing flattened config/TOML diagnostics in both JSON and NDJSON forms where
  relevant
- [x] Add a short explicit note on the flattened config-diagnostics contract if that remains the 1.0
  decision
- [x] Edge-case coverage reviewed for confidence in frozen schemas
  - [x] coverage audit performed on core/config/pipeline/registry/version machine modules
  - [x] no remaining uncovered schema-relevant blind spots identified for frozen machine contracts
  - [x] dedicated CLI machine contract tests now pass for config, pipeline, version, registry, and
    probe, including filtered explicit-input probe payloads and refined filter reasons
  - [x] config command machine tests now cover flattened staged diagnostics behavior
  - [x] version command machine tests now cover JSON and NDJSON output
  - [x] registry command machine tests now cover flattened JSON envelopes, NDJSON record kinds,
    detail levels, and ordering

#### [Recommended] CI / release architecture

- [x] Decide whether the current artifact-based CI → release split should remain the stable 1.0
  release architecture or later be factored into reusable workflow/release-infra patterns
  - current artifact-based CI → release split is accepted for 1.0
  - further factoring into reusable release-infra patterns is deferred post-1.0
- [x] Decide whether multi-platform installation validation should remain a dedicated workflow
  - dedicated install-smoke validation workflow accepted for 1.0
  - broader workflow factoring or reusable workflow extraction deferred post-1.0
- [x] Decide whether workflow formatting/style expectations should stay editor-policy-only or be
  documented explicitly in contributor-facing CI guidance
  - formatter behavior is governed by checked-in tool configuration and release validation gates
  - broader editor-style guidance remains non-blocking for 1.0
- [x] Decide whether the explicit `tests` matrix setup should remain as-is or later reuse more of
  the shared CI bootstrap model
  - the explicit matrix remains accepted for 1.0
  - further reuse of shared CI bootstrap models is deferred post-1.0

#### [Recommended] Documentation governance

- [x] Canonical documentation conventions established in `docs/dev/documentation-conventions.md`
- [x] Command-page structure harmonized across generated and hand-written command documentation
- [x] Cross-reference labels, related-command sections, and related-doc sections reviewed for
  consistency
- [x] Snippet governance reviewed and stabilized
- [x] Over-abstracted snippets retired in favor of canonical reference pages
- [x] Documentation hygiene validation added and integrated into local and release validation gates
- [x] Generated-site navigation and TOC density reviewed and improved
- [x] Project-wide terminology glossary promoted to `docs/terminology.md`
- [x] Historical glossary references updated from the developer-only location to the project-wide
  terminology page
- [x] Shared terminology note centralized in `_snippets/terminology.md`
- [x] Command-page user-facing implementation-boundary guidance documented
- [x] Bundled `topmark-example.toml` template prose harmonized with the finalized documentation
  terminology and reference-template style
- [x] Markdown prose and Python code-prose hygiene validation added and integrated
- [x] Changelog-specific heading and section validation added and integrated

### Post-1.0 follow-up (nice-to-have)

These items are explicitly reasonable to defer. They should not be reopened for 1.0 unless concrete
beta feedback identifies a release blocker.

#### [Post-1.0] Product / architecture

- [ ] Implement in-memory pipeline support if deferred for 1.0
- [ ] Introduce configuration schema versioning only when a future non-additive schema change
  requires it
- [ ] Revisit whether staged validation details should be exposed more directly in
  CLI/API/machine-readable output contracts beyond the current flattened compatibility diagnostics
  view
- [ ] Revisit registry query/filter commands if users need richer registry discovery beyond the
  current read-only registry listings and probe diagnostics
- [ ] Explore support for multi-line TopMark header fields while preserving deterministic parsing,
  rendering, idempotence, and backward compatibility with the existing single-line field contract

#### [Post-1.0] Human output

- [ ] Further Markdown layout evolution (tables, grouped sections, richer structures) within the
  document-oriented output contract
- [ ] Generalize or refine the "primary hint" concept
- [ ] Evaluate Rich / `rich-click` migration and broader theme/style configurability once 1.0 is
  released

#### [Post-1.0] Tooling / ecosystem

- [ ] Revisit whether install-smoke validation should evolve into reusable release-consumer or
  downstream-integration workflows
- [ ] Revisit long-term CLI framework choice (Click vs alternative)
- [ ] Evaluate ProperDocs as a potential successor to MkDocs for documentation generation once the
  current beta gate has closed
- [ ] Consider splitting, renaming, or further consolidating documentation/code-prose hygiene
  tooling if future checks make the current script structure too broad
- [ ] Consider richer documentation-structure validation only if repeated drift appears despite the
  current lightweight hygiene checks
- [ ] Further refactor GitHub workflow structure into reusable workflow/release-infra patterns if
  still worthwhile

______________________________________________________________________

Only when all items in the "Must finish before 1.0" section are completed or explicitly deferred
with rationale should `1.0.0` final be cut. The 1.0 alpha series served as the
contract-stabilization and release-path rehearsal phase, while the beta stabilization series
validated the frozen contracts, release pipeline, GitHub prerelease visibility, documentation
governance, changelog hygiene, prose hygiene, terminology stability, and cross-platform installation
behavior. The remaining path to final `1.0.0` is now focused on preserving compatibility, collecting
final real-world beta feedback, and avoiding new scope unless concrete release-blocking issues are
identified.
