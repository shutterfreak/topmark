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
[Semantic Versioning](https://semver.org/) and follows a Keep-a-Changelog-style structure with the
sections **Added**, **Changed**, **Removed**, and **Fixed**.

______________________________________________________________________

## [Unreleased]

> [!CAUTION] **Breaking changes**
>
> This release includes breaking changes to CLI exit-code semantics, `config check` validation
> failures, option-like path parsing, `check`/`strip` diff-option semantics, STDOUT/STDERR output
> routing, machine-readable processing-result serialization, filename-rule validation/normalization,
> and public API report-scope defaults. Consumers should review the **Breaking Changes** and
> **Notes** sections before upgrading automation, CI jobs, golden tests, machine-output parsers, or
> plugin/custom file-type definitions.
>
> In particular, `WOULD_CHANGE` now exits with code `3` instead of `2`; Click parser-level usage
> errors reserve exit code `2`; `--diff` is now supported for machine-readable detail output;
> machine-readable diff information is emitted as dedicated structured diff payloads rather than via
> `ProcessingResult.details`; CLI diagnostics are consistently routed to `stderr` while machine
> payloads remain on `stdout`; JSON/NDJSON `check` and `strip` result paths use POSIX `/` separators
> on all platforms; invalid `FileType.filenames` rules are rejected during file-type construction;
> and public API `check()` and `strip()` now default to `report="actionable"` instead of `"all"`.

### Added - Unreleased

- Added a durable `ProcessingDetailSnapshot` on `ProcessingResult` that captures generated
  unified-diff text without retaining volatile pipeline views and exposes reduced detail state
  through `ProcessingResult` serialization.
- Added durable human display-path state to `ProcessingResult`, allowing check/strip presentation to
  render logical STDIN filenames and per-file labels after context reduction without retaining
  runtime options.
- Added `tools/perf/pipeline_memory_baseline.py`, a measurement-only benchmarking tool for
  establishing memory and allocation baselines for pipeline processing.
- Added `docs/dev/performance-baselines.md` documenting benchmark methodology, workload definitions,
  measurement scope, benchmark output layout, and initial baseline results.
- Added canonical benchmark suites (`smoke`, `pathological`, and `baseline`) together with preserved
  run metadata, JSON reports, and Markdown summaries under `artifacts/perf/`.
- Added an exploratory repository-scale benchmark suite for measuring many-file pipeline execution,
  durable `ProcessingResult` snapshot retention, aggregate diff-detail ownership, and run
  throughput.
- Added a local `perf_baseline` Nox session and `make perf-baseline` entry point for reproducible
  memory/allocation baseline generation.
- Added structured planned-edit metadata (`EditView`, `PlannedEdit`, and `PlanEditKind`) together
  with a single-splice structured unified-diff renderer used for GitHub issue 167 validation work.

### Changed - Unreleased

- Migrated public API `check()` and `strip()` result packaging to consume durable `ProcessingResult`
  snapshots after context reduction, using reduced detail snapshots for public diff exposure while
  preserving existing API DTO behavior.
- Migrated `check`/`strip` machine-readable result serialization to consume durable
  `ProcessingResult` snapshots after context reduction, using reduced detail snapshots for JSON and
  NDJSON detail output while deriving summary classification from each result's execution-mode
  snapshot.
- Refined machine-readable diff presentation so JSON detail embeds an optional per-result `diff`
  object while NDJSON detail emits adjacent standalone `diff` records, preserving streaming output
  for NDJSON and aligning machine-readable diff ownership with durable `ProcessingResult` snapshots.
- Relaxed the previous output-format restriction on `--diff`; machine-readable detail output now
  supports retained diff payloads while machine-readable summary output intentionally suppresses
  per-file diffs and emits a diagnostic warning.
- Migrated `check`/`strip` TEXT and Markdown human report rendering to consume durable
  `ProcessingResult` snapshots after context reduction, using reduced display-path and diff-detail
  state while keeping probe rendering and patcher-generated diff headers context-based.
- Migrated `probe` public API DTO assembly, machine-readable output, and TEXT/Markdown rendering to
  consume durable `ProcessingResult` snapshots carrying reduced `ProbeSnapshot` state, completing
  the current mutable-context to durable-result handover for output-facing consumers.
- Migrated probe API orchestration onto the result-oriented `run_probe_pipeline_results()` runtime
  adapter so real probe contexts and synthetic probe outcomes are reduced to durable
  `ProcessingResult` snapshots before public API finalization.
- Made human report-scope filtering result-compatible by introducing protocol-based filtering
  support for durable `ProcessingResult` snapshots while preserving context-based filtering support
  for pre-reduction probe consumers.
- Aligned public API and CLI report-scope semantics by making `check()` and `strip()` default to the
  actionable report scope and by using command-specific actionable classification for report
  filtering.
- Avoided formatting a duplicate unified-diff preview during patch generation when INFO-level
  pipeline logging is disabled, reducing transient allocations for diff-heavy workloads while
  preserving retained diff output.
- Pruned consumed pipeline views incrementally between steps when view pruning is enabled, reducing
  transient retention before later patch/write phases while preserving requested diff output.
- Clarified pipeline execution and reduction ownership by renaming execution collections to
  `contexts`, keeping runner pruning limited to between-step consumed-view release, and moving final
  volatile-view release to the durable `ProcessingResult` reduction boundary for check/strip paths.
- Replaced string-based pipeline view-pruning decisions with typed `ViewSlot` consumer metadata
  declared by concrete pipeline steps.
- Replaced eager replacement-image composition with a repeatable updated-content abstraction and
  segment-backed updated-file views, allowing replacement planning to retain composed updated
  content without requiring one materialized updated-file list.
- Streamed writer-owned updated-content consumption through repeatable updated-line iteration for
  file sinks and STDOUT emission, removing the remaining writer-local eager updated-line
  materialization while preserving existing comparison, patch-generation, and presentation behavior.
- Replaced the CLI presentation backend with Rich.
- Adopted `rich-click` for CLI help rendering while preserving Click runtime semantics.
- Centralized CLI option metadata and command-applicability groups used by diagnostics.
- Hid singular file-type compatibility aliases from help output while preserving them as accepted
  hidden aliases.
- Reworked CLI exit-code semantics to reserve exit code `2` for Click parser-level usage errors and
  moved `WOULD_CHANGE` to exit code `3`.
- Updated `config check` to report validation failures using `CONFIG_ERROR (78)` instead of the
  generic `FAILURE (1)` exit code.
- Aligned path-oriented command parsing with Click and POSIX-style option handling: unknown
  option-like tokens are now parser errors unless passed after `--`.
- Standardized processing machine-output path serialization for `check` and `strip` JSON/NDJSON
  result payloads to use POSIX `/` separators, matching existing `probe` machine-output behavior.
- Normalized `FileType.filenames` tail-subpath rules to canonical POSIX-style `/` separators during
  file-type construction.
- Standardized registry, resolver, presentation, and machine-readable registry output to consume the
  canonical filename-rule representation.
- Clarified that `FileType.filenames` entries are declarative registry matching rules rather than
  filesystem paths.
- Centralized path serialization and human-facing path presentation helpers for processing output,
  generated header metadata, TEXT rendering, Markdown rendering, and unified diff labels.
- Clarified that unified diff file labels follow human-facing display-path policy rather than the
  machine-readable path serialization contract.
- Extended the POSIX path-serialization contract to configuration machine-output payloads,
  TOML/config provenance payloads, configuration-export serialization, and configuration diagnostic
  summaries.
- Defined TopMark's filesystem-identity evaluation model for existing processing inputs by
  separating filesystem-identity normalization from processing-target eligibility checks.
- Standardized symlink handling so file symlink spellings resolve to the target path before runtime
  probing, processing, header metadata generation, and machine-readable output.
- Defined configuration-source identity for file-backed TOML sources using the resolved
  configuration-file target for precedence, scope applicability, layered provenance, and
  machine-readable configuration provenance.
- Deduplicated repeated resolved configuration-source identities during TOML-side resolution,
  keeping the highest-precedence occurrence for layered configuration and provenance.
- Extended machine-readable configuration provenance to expose the resolved configuration-discovery
  anchor separately from configuration-source identity, scope roots, processing targets, and
  filesystem identity.
- Added a hard-link filesystem-identity guard: selected paths sharing `(st_dev, st_ino)` are all
  blocked as hard-linked processing targets while unrelated files continue processing normally.
- Extended the GitHub Actions pin audit with an optional `--fix` mode that can repair stale repeated
  action refs using an already-present preferred pinned ref selected from version-comment metadata.
- Required symlink-dependent regression tests to execute in the cross-platform filesystem CI job
  instead of silently skipping when symlink creation is unavailable.
- Added workflow-level concurrency for CI and GitHub Actions pin-audit pull-request runs so
  superseded PR commits cancel older in-progress runs while preserving `main`, scheduled, manual,
  and release-tag validation.
- Clarified CI workflow maintainability by adding explicit job-level permissions for selected
  third-party-action jobs, bounded link-check jobs with explicit timeouts, and summarized
  path-filter decisions in the GitHub Actions step summary.
- Made pipeline outcome bucketing compatible with durable `ProcessingResult` snapshots by
  introducing typed outcome, pre-insert advisory, and execution-mode snapshots, while preserving
  existing `ProcessingContext` consumers, CLI/API behavior, and machine-output shapes.
- Clarified pipeline intent modelling by renaming derived per-result action intent helpers,
  introducing explicit pipeline catalogue definitions and selection DTOs, and deriving runtime
  execution options from selected pipelines while preserving CLI, API, and machine-output behavior.
- Introduced streaming-capable execution and reduction seams through `iter_steps_for_files()`,
  `iter_processing_results()`, `run_pipeline_results()`, and `run_probe_pipeline_results()`, while
  preserving existing CLI, API, presentation, machine-output, ordering, summary, and exit-code
  behavior.
- Strengthened public API `FileResult` DTO invariants so `bucket_key` and `bucket_label` are always
  populated strings, matching the aggregation data produced by durable result finalization.
- Extended planner and stripper mutation paths to record structured single-splice edit metadata
  alongside updated-content generation, preparing future diff generation work without changing
  current unified-diff output contracts.
- Added shadow-validation of structured unified-diff rendering against the existing difflib-based
  patch generation path, keeping difflib as the production source of truth while parity is validated
  for GitHub issue 167.
- Reduced comparison-time materialization for supported single-edit pipeline mutations by allowing
  `ComparerStep` to classify valid structured-edit contexts directly from retained `EditView`
  metadata before falling back to full-image comparison.
- Reduced patch-generation materialization for supported single-edit pipeline mutations by allowing
  `PatcherStep` to render structured unified diffs directly from retained planned-edit metadata and
  original image views before falling back to `difflib`-based diff generation.
- Centralized pipeline lifecycle enforcement in `BaseStep`, making halt ownership a `run()`-phase
  responsibility and treating `hint()` as diagnostic-only. Steps whose primary status axis remains
  `PENDING` after execution are now halted consistently by the shared lifecycle wrapper.

### Breaking Changes - Unreleased

- Exit code `WOULD_CHANGE` changed from `2` to `3`.
- Exit code `2` is now reserved for Click parser-level usage errors (for example, unknown options or
  invalid option values encountered before TopMark command logic runs).
- CI workflows, shell scripts, tests, and automation that previously treated exit code `2` as the
  TopMark dry-run change signal must be updated to expect exit code `3` instead.
- `topmark config check` now reports validation failures using `CONFIG_ERROR (78)` instead of the
  generic `FAILURE (1)` exit code.
- `topmark check`, `topmark strip`, and `topmark probe` now reject unknown option-like arguments
  before `--` as Click parser-level usage errors. Literal filenames that begin with `-` must be
  passed after the standard `--` delimiter, for example `topmark check -- --generated.py`.
- `topmark check` and `topmark strip` JSON/NDJSON `result.path` values now use POSIX `/` separators
  on all platforms. Consumers that compare Windows machine-output paths literally may need to update
  expectations from backslash-separated paths to slash-separated paths.
- `check` and `strip` no longer reject `--diff` for machine-readable output. CLI validation now
  enforces only the semantic mutual exclusion between `--diff` and `--apply`; machine-readable
  summary output intentionally ignores retained diff payloads and emits a diagnostic warning.
- Machine-readable `check` and `strip` diff serialization has changed. The previous
  `ProcessingResult.details`-based diff representation has been replaced by explicit structured diff
  payloads: JSON detail embeds an optional per-result `diff` object, while NDJSON detail emits
  dedicated adjacent `diff` records. Consumers parsing previous machine-output payloads must update
  accordingly.
- CLI output ownership has been clarified. Machine-readable payloads are emitted exclusively on
  standard output while warnings, diagnostics, and informational messages are emitted on standard
  error. Automation that previously consumed mixed output streams should be updated.
- `FileType.filenames` tail-subpath rules are now canonicalized during file-type construction.
  Definitions that previously used backslash separators are normalized to POSIX-style `/` separators
  before matching, registry composition, presentation, and machine-readable output.
- Invalid filename-rule definitions are now rejected during file-type construction. Rejected forms
  include:
  - empty rules;
  - absolute paths;
  - UNC paths;
  - Windows drive paths;
  - rules containing empty path segments;
  - rules containing `.` or `..` path segments.
- Plugin authors and custom file-type providers should treat `FileType.filenames` values as relative
  registry matching rules rather than filesystem paths.
- Public API `check()` and `strip()` now default to `report="actionable"` instead of `"all"`.
  Integrations that relied on receiving every processed file in `RunResult.files` must now pass
  `report="all"` explicitly.

### Fixed - Unreleased

- Fixed post-1.0.1 documentation hygiene violations.
- Trapped underscored option spellings consistently and suggested hyphenated alternatives.
- Improved CLI validation diagnostic formatting.
- Fixed misleading synthetic `probe` results for explicit directories that successfully expand to
  selected child files.
- Fixed duplicate `probe` records for missing explicit inputs.
- Fixed strict config-validation failures so the triggering diagnostics remain visible in
  human-readable output.
- Preserved valid JSON/NDJSON config diagnostics when strict config validation stops command
  execution.
- Clarified and disambiguated Click parser-level usage errors versus TopMark semantic exit-code
  outcomes.
- Fixed unknown options passed to `check`, `strip`, and `probe` so they are no longer interpreted as
  missing input paths.
- Fixed inconsistent path serialization between `probe` machine output and `check` / `strip`
  processing result machine output.
- Fixed platform-dependent registry filename-rule behavior by normalizing tail-subpath matching
  rules before resolution and registry serialization.
- Fixed inconsistent registry output where equivalent filename rules could be represented using
  different path-separator spellings.
- Fixed STDIN-backed unified diff labels so they use the logical `--stdin-filename` instead of the
  materialized temporary file path.
- Fixed inconsistent machine-readable path serialization across configuration payloads, TOML
  provenance payloads, configuration export output, and configuration diagnostic summaries by
  normalizing real filesystem paths to POSIX-style **/** separators on all platforms while
  preserving synthetic configuration-source identifiers as stable labels.
- Fixed undocumented symlink and filesystem-identity behavior by making resolved processing-target
  identity explicit in file discovery, configuration resolution, pipelines, generated header
  metadata, public API behavior, and machine-readable output.
- Clarified and regression-tested workspace-root discovery through symlinked CWD, input-anchor, and
  parent-directory spellings.
- Fixed ambiguity around symlinked configuration files by documenting and testing that provenance,
  precedence, and scope applicability use the resolved configuration target rather than the symlink
  spelling.
- Fixed ambiguous hard-linked processing-target behavior by blocking every selected path that shares
  `(st_dev, st_ino)` identity with another selected path instead of choosing a source, target,
  winner, or loser path.
- Fixed duplicate configuration-source provenance when the same resolved TOML source is reached
  through multiple discovery or explicit `--config` paths.
- Fixed missing machine-readable visibility into configuration-discovery starting points by
  exporting the resolved discovery anchor in configuration provenance payloads while preserving
  existing provenance and identity semantics.
- Fixed the VS Code Run On Save Markdown formatter integration by simplifying the workspace `match`
  pattern so saves of `.md` files reliably trigger the configured `mdformat` command.
- Fixed report-scope filtering for `strip` so supported files without removable headers are treated
  as compliant rather than actionable.
- Fixed report-scope parity between the CLI and public API by applying the same actionable-filtering
  semantics and default report scope to both entry points.
- Fixed Markdown pipeline output so report scopes with no visible per-file results no longer render
  an empty `## Files` section.
- Fixed check/strip human diff output so TEXT and Markdown summary or per-file reports no longer
  render empty diff sections when `--diff` is requested but no file has diff content.
- Fixed machine-readable diff output to avoid embedding terminal-oriented unified diff text inside
  processing-result payloads, replacing it with structured diff payloads that preserve streaming
  NDJSON behavior and provide a clearer JSON compatibility contract.

### Documentation - Unreleased

- Updated probe and machine-output documentation for corrected explicit-input probe behavior.
- Clarified strict configuration-validation diagnostics in shared configuration strictness
  documentation.
- Documented machine-readable output behavior when strict config validation stops commands before
  probing or processing.
- Updated CLI exit-code documentation to distinguish Click-owned parser failures from TopMark-owned
  semantic outcomes.
- Documented the exit-code migration from `WOULD_CHANGE (2)` to `WOULD_CHANGE (3)` and the revised
  `config check` validation-failure behavior.
- Documented use of the standard `--` delimiter for literal dash-prefixed path names.
- Documented TopMark's machine-readable path serialization contract for header metadata, processing
  output, probe output, configuration payloads, TOML/config provenance payloads, and human-readable
  display output boundaries.
- Removed obsolete documentation caveats that previously excluded configuration and provenance
  payloads from the POSIX path-serialization contract.
- Clarified that registry filename tail-subpath rules are declarative matching rules that use
  POSIX-style `/` separators, not discovered filesystem paths.
- Documented the canonical filename-rule contract for `FileType.filenames`.
- Documented normalization and validation behavior for tail-subpath filename rules.
- Clarified plugin-author guidance around filename-rule definitions and canonical registry metadata.
- Documented the boundary between machine-readable path serialization and human-facing path
  presentation, including TEXT, Markdown, and unified diff output.
- Clarified that unified diff labels are human-facing display labels and should not be treated as
  JSON/NDJSON path fields.
- Documented and aligned the recommended VS Code workspace tooling configuration around Pylance,
  `mdformat`, Run On Save integration, and project-maintained task entry points.
- Documented filesystem-identity evaluation, filesystem-identity normalization, processing-path
  selection, symlink handling, hard-link policy, and the boundary between identity evaluation and
  machine-readable path serialization across user, API, and developer documentation.
- Documented configuration-source identity, duplicate resolved-source deduplication, and symlinked
  configuration-file behavior across configuration discovery, configuration schema, architecture,
  terminology, machine-output, command, and API documentation.
- Documented workspace-root discovery and resolved discovery-anchor behavior across configuration,
  command, machine-output, terminology, architecture, and API-stability documentation.
- Documented `config_provenance.discovery_anchor` and clarified its distinction from
  configuration-source identity, scope roots, processing targets, and filesystem identity across
  machine-output and configuration-command documentation.
- Documented the TopMark 1.1.0 hard-link compatibility contract for processing and probe machine
  output.
- Clarified TopMark's identity-domain terminology and compatibility boundaries for processing-target
  identity, configuration-source identity, registry identity, path serialization, and
  filesystem-identity evaluation.
- Added cross-references between public API, terminology, and API-stability documentation so
  filesystem-identity concepts link directly to the authoritative identity-domain compatibility
  classification.
- Documented local repair workflows, trust boundaries, and maintenance guidance for the GitHub
  Actions pin audit, including the new `--fix` mode.
- Documented that the filesystem CI job requires symlink capability through
  `TOPMARK_REQUIRE_SYMLINKS=1` on Ubuntu, macOS, and Windows.
- Clarified the recommended VS Code Run On Save configuration for Markdown formatting so the
  workspace `mdformat` integration triggers reliably for saved `.md` files.
- Reviewed documentation clarity, consistency, governance, tooling, structure, duplication, and
  snippet usage for GitHub issue 108.
- Synchronized documentation-governance guidance with the current generated-reference layout and
  snippet inventory.
- Clarified roadmap governance by defining `docs/dev/roadmap.md` as a maintainer-facing
  strategic-planning document rather than a parallel issue tracker.
- Simplified the stable-line roadmap to focus on governance boundaries, deferred architecture
  directions, frozen 1.x contract areas, and GitHub issue-driven execution.
- Updated `Road to TopMark 1.0` to distinguish historical stabilization decisions from post-1.0
  maintenance work, including the later completion of the Rich and `rich-click` migration.
- Clarified pytest marker documentation by restoring the `case_insensitive_fs` marker entry and
  fixing the malformed `pipeline` marker table row in CI test-validation guidance.
- Documented the normalized pytest marker taxonomy, including the shift to cross-cutting semantic
  markers, path-based package or subsystem test selection, marker-expression hygiene expectations,
  and the reduced marker set used by CI and local validation tooling.
- Clarified the report-scope contract, including the distinction between actionable and noncompliant
  results and the applicability of report filtering across human-readable output formats.
- Added dedicated performance-baseline documentation covering subprocess-isolated RSS measurement,
  tracemalloc methodology, benchmark-corpus scope, benchmark preservation guidance, and initial
  memory-baseline findings from GitHub issue 134.
- Added cross-references from development and CI documentation to the performance-baseline workflow
  and benchmark methodology.
- Documented GitHub issue 140 follow-up measurements showing that consumed-view pruning reduces
  retained memory in header-heavy workloads while preserving the GitHub issue 134 baseline
  comparison modes.
- Documented pipeline view consumer declarations, `consumes_views`, and typed `ViewSlot` pruning
  behavior in the developer pipeline documentation.
- Documented GitHub issue 138 follow-up measurements showing reduced diff-generation allocations in
  diff-heavy workloads after avoiding duplicate INFO-level diff-preview formatting.
- Documented GitHub issues 135 and 136, including repeatable updated-content architecture, remaining
  materialization boundaries, follow-up benchmark measurements, and cumulative Track B
  memory-allocation improvements relative to the GitHub issue 134 baseline.
- Documented GitHub issue 137, including writer-owned updated-content streaming, remaining
  materialization boundaries, follow-up benchmark measurements, and the separation between writer
  streaming and broader stdout-rendering ownership.
- Documented GitHub issue 147, including output ownership findings, streaming-output architecture
  alternatives, benchmark relevance, and the rationale for closing Track B without further
  implementation.
- Documented the revised machine-readable diff contract, including JSON versus NDJSON detail
  rendering, summary-mode diff suppression, `--diff` applicability across output formats, and the
  separation between human unified-diff rendering and structured machine-readable diff payloads.
- Clarified the architecture boundary between mutable `ProcessingContext` execution state and
  durable `ProcessingResult` snapshots, including execution-context ownership, reduction-driven
  volatile-view release, outcome classification, report filtering, reduced detail snapshots,
  check/strip machine output, and check/strip human rendering.
- Added an internal batch reduction boundary from mutable processing contexts to durable processing
  results, including durable detail-state capture that prepares reporting logic for future streaming
  consolidation without changing current runner behavior.
- Updated architecture documentation to reflect durable probe snapshots, reduced probe state, and
  the completion of the current output-facing mutable-context to durable-result migration.
- Documented the pipeline catalogue and selection architecture, including the separation between
  command intent, selected executable pipeline definitions, durable runtime options, and public API
  or machine-output compatibility boundaries.
- Documented the streaming-capable execution and reduction architecture completed for GitHub issue
  165, including iterator-based engine/reduction seams, check/strip and probe durable-result runtime
  adapters, synthetic probe-result ownership, and the rationale for preserving batch-oriented public
  contracts.
- Documented the ownership boundary between `PipelineSelection` and `RunOptions`, clarifying
  executable pipeline selection versus invocation-specific runtime state, the
  `RunOptions.from_pipeline_selection(...)` derivation boundary, and the durable ownership chain
  from pipeline selection through runtime options, processing contexts, and processing results
  (GitHub issue 169).
- Documented pipeline catalogue compatibility guarantees, catalogue-evolution boundaries, extension
  guidelines, ownership responsibilities, and future streaming/event-API compatibility expectations
  for pipeline families, selections, runtime options, and durable processing results (GitHub issue
  170).
- Documented GitHub issue 183, including structured-edit-driven comparison, reduced patch-generation
  materialization, centralized step lifecycle enforcement, follow-up benchmark measurements, and the
  remaining comparison/diff ownership boundaries.
- Documented supported local `pytest-xdist` workflows, including the rationale for keeping CI pytest
  execution serial within individual jobs while using job-level parallelism.
- Updated contributor and CI guidance to recommend the local pre-PR validation gate, document its
  relationship to GitHub CI, and cross-reference the relevant validation workflow documentation.
- Documented the machine-readable JSON/NDJSON compatibility and evolution policy, including stable
  compatibility guarantees, additive minor-release evolution, breaking-change boundaries,
  unknown-field handling, JSON versus NDJSON operational differences, and the current absence of a
  separate `schema_version` field.
- Documented CLI stream-routing ownership, including STDOUT payload ownership, STDERR
  diagnostics/signaling, machine-readable parseability, and human diff/content-to-STDOUT routing
  behavior.

### Internal - Unreleased

- Removed stale tox references.
- Migrated pytest collection to `--import-mode=importlib` and made repository-local developer
  tooling imports explicit for the test suite.
- Packaged all test subdirectories consistently and relocated remaining generic unit tests into
  source-aligned test packages.
- Added dedicated developer-validation tests for registry integrity, processor strategy usage, and
- Audited and normalized pytest marker usage by removing package-only subsystem markers, retaining
  only cross-cutting semantic markers, and aligning Nox and Makefile marker expressions with the
  declared marker set.
- Added developer-validation coverage for pytest marker hygiene so undeclared marker usage, stale
  marker declarations, and stale Nox marker expressions are detected during repository validation.
- Updated pre-commit dependencies, including TopMark itself.
- Raised the minimum supported runtime dependency version for `click` to 8.4.2 to align with the
  current validated compatibility baseline.
- Raised the minimum supported development dependency version for `build` to 1.5.0 and refreshed
  locked development tooling, including `ruff`, `hypothesis`, and `uv`.
- Added shared machine-path formatting helpers and regression coverage for Windows-style processing
  machine-output path serialization.
- Expanded cross-platform filesystem regression coverage for machine-readable path serialization,
  Windows and UNC path formatting, symlink discovery and deduplication, `--files-from -` processing,
  configuration path resolution, and include-pattern discovery seeding behavior.
- Centralized POSIX path-formatting helpers for machine-readable payloads, configuration/provenance
  serialization, and synthetic configuration-source formatting.
- Added centralized filename-rule normalization and validation helpers.
- Added regression coverage for filename-rule normalization, validation, matching, registry
  serialization, resolver behavior, and presentation output.
- Added dedicated header-metadata path serialization and display-path presentation helper modules.
- Added regression coverage for header metadata path serialization, TEXT and Markdown path labels,
  and STDIN-backed unified diff labels.
- Refreshed editor and contributor tooling configuration, including VS Code workspace
  recommendations, task definitions, and Markdown formatting integration.
- Added lightweight pre-commit hygiene checks for documentation hygiene, code-documentation hygiene,
  and docstring link validation to better align local workflows with Nox validation.
- Added `canonical_processing_path()` as the named helper for TopMark's resolved processing-target
  filesystem identity policy.
- Added regression coverage for symlinked file inputs, symlinked directory behavior, broken symlink
  diagnostics, generated header metadata for symlinked inputs, configuration-source identity,
  layered provenance, public machine output, and processing-path serialization.
- Added regression coverage for workspace-root discovery through symlinked input anchors, symlinked
  current working directories, and repositories reached through symlinked parent paths.
- Added regression coverage for duplicate resolved configuration-source identities across
  discovered, explicit, and symlinked configuration paths.
- Added machine-output and TOML-provenance regression coverage for discovery-anchor serialization,
  POSIX path formatting, provenance-only schema handling, and symlinked discovery scenarios.
- Added regression coverage for hard-linked selected processing paths across pipeline execution,
  `check`, `strip`, `probe`, JSON output, NDJSON output, and mixed hard-linked plus unrelated file
  selections.
- Added deterministic repair support for GitHub Actions pin drift in local composite actions and
  workflow files without introducing network access, dynamic version resolution, or Dependabot
  replacement behavior.
- Added a `TOPMARK_REQUIRE_SYMLINKS` test-helper guard so symlink-dependent tests fail loudly in CI
  jobs that are expected to exercise symlink behavior.
- Aligned generated API-page tooling prose with the current generated documentation path layout.
- Added targeted coverage tests for coverage-strategy GitHub issue 129 across whitespace-policy
  helpers, pipeline planning and stripping behavior, registry binding validation, and processor
  insertion mixins.
- Extended project validation tooling to type-check benchmark tooling under `tools/` and excluded
  generated benchmark artifacts from Ruff scanning.
- Added subprocess-isolated benchmark execution so per-scenario RSS measurements reflect individual
  workload peaks rather than cumulative process high-water marks.
- Added explicit pruned benchmark modes to measure view-pruning lifecycle behavior without changing
  the historical benchmark suite modes used for baseline comparability.
- Added regression coverage for consumed-view release behavior, diff retention, and concrete
  pipeline step `consumes_views` declarations.
- Added regression coverage for diff-preview formatting behavior so expensive unified-diff preview
  rendering only occurs when INFO-level pipeline logging is enabled.
- Added repeatable `UpdatedContent` pipeline abstractions together with segment-backed updated-file
  composition for replacement-planning paths.
- Added streaming writer helpers and regression coverage for repeatable updated-content consumption
  through atomic-file, in-place-file, and STDOUT writer paths, including STDOUT write-failure
  handling.
- Added regression coverage for repeatable updated-content iteration and updated-view lifecycle
  behavior.
- Renamed internal pipeline execution collections from `results` to `contexts` where they still
  carry mutable `ProcessingContext` instances, preserving a clearer distinction from durable
  `ProcessingResult` snapshots.
- Added immutable `StatusSnapshot` and `ProcessingResult` result-reduction primitives as the first
  stage of separating volatile pipeline execution state from durable processing outcomes (GitHub
  issue #148).
- Added typed outcome-classification, pre-insert advisory, and execution-mode snapshots so
  policy-derived bucketing state and invocation intent can be reduced from mutable pipeline contexts
  without retaining volatile execution objects.
- Reworked internal pipeline selection around `Pipeline`, `PipelineDefinition`, and
  `PipelineSelection`, moved selection ownership into the pipeline catalogue, and added targeted
  coverage for catalogue metadata, selection variants, and runtime-option synchronization.
- Added result-oriented runtime orchestration through `run_pipeline_results()` and
  `run_probe_pipeline_results()`, migrated check, strip, and probe API execution to consume durable
  `ProcessingResult` snapshots through result-oriented runtime paths, and added regression coverage
  for empty durable-result batches and filtered explicit probe inputs.
- Removed the remaining context-oriented API runtime helpers `run_pipeline()` and
  `run_probe_pipeline()` after their check/strip, probe, and nested-configuration test consumers
  were migrated to durable result-oriented paths.
- Added focused regression coverage for structured diff rendering, planned-edit inference,
  planner/stripper edit metadata generation, patcher shadow-validation behavior, and unified-diff
  formatter line-number rendering.
- Made structured unified-diff rendering the primary patch-generation backend for valid single-edit
  pipeline mutations, with `difflib.unified_diff()` retained as a fallback for missing, invalid, or
  future multi-edit metadata.
- Added focused CLI regression coverage for empty check/strip diff-output composition across TEXT
  and Markdown summary and per-file report modes.
- Audited CLI human-output regression tests, introduced reusable semantic assertion helpers for
  strict file-type overlap diagnostics, and reduced duplication while preserving output-contract
  coverage.
- Added focused regression coverage for Rich-aware CLI output assertion helpers, including
  layout-independent verification of strict file-type overlap diagnostics across ANSI styling, panel
  rendering, and wrapped terminal output.
- Expanded presentation-layer regression coverage for TEXT, Markdown, and shared presentation
  helpers, including pipeline guidance rendering, probe rendering, version formatting, configuration
  presentation, diagnostic presentation, and shared presentation utilities. Added focused contract
  tests for durable `ProcessingResult` and diagnostic models while reducing duplicated
  probe-rendering logic through shared presentation helpers.
- Hardened CLI human-output regression tests against Rich styling, panel borders, terminal-width
  wrapping, and other layout differences by replacing brittle raw output assertions with semantic
  Rich-aware assertion helpers.
- Reduced duplicate Linux validation in GitHub Actions by limiting the dedicated cross-platform
  filesystem job to macOS and Windows while retaining canonical Linux QA through the supported
  Python-version matrix.
- Added a dedicated `pre_pr` Nox session together with a `make pre-pr` convenience target,
  establishing the recommended local pre-PR validation gate while preserving GitHub CI as the
  authoritative validation surface.
- Standardized Makefile `.PHONY` declarations by colocating them with their associated targets,
  reducing maintenance overhead for predominantly phony developer targets and aligning with the
  project's `mbake` formatting conventions.
- Added focused machine-output contract tests covering documented JSON/NDJSON compatibility
  guarantees, including stable envelope structure and additive-schema compatibility expectations.
- Added CLI stream-routing contract tests and small command-layer stream-emission helpers clarifying
  explicit STDOUT payload ownership for check/strip output.
- Centralized shared pipeline summary preparation for TEXT and Markdown renderers, keeping compact
  file-type, outcome, write/diff, and diagnostic triage semantics consistent while leaving styling
  and Markdown escaping in the format-specific presentation layers.

### Notes - Unreleased

- CLI help output and selected human-facing validation diagnostics now use Rich / `rich-click`
  presentation. Runtime behavior and machine-readable JSON/NDJSON contracts are unchanged, but
  consumers or tests that assert exact human-readable terminal formatting may need to update
  formatting-sensitive expectations.
- Strict configuration-validation failures now preserve machine-readable JSON/NDJSON output. This
  fixes invalid machine output in error paths, but consumers that previously treated such failures
  as unparseable plain text may need to adjust their error handling.
- Machine-readable `check` and `strip` processing result paths now match the existing `probe` path
  serialization convention by using POSIX `/` separators on all platforms. This improves
  cross-platform stability for machine consumers, but may require updates to Windows-specific golden
  tests or literal path comparisons.
- This release intentionally introduces a breaking CLI exit-code change: `WOULD_CHANGE` now exits
  with code `3` instead of `2` so automation can distinguish dry-run change signals from Click
  parser-level usage errors. Existing CI jobs, shell scripts, and tests that checked for exit code
  `2` must be updated.
- TopMark now documents resolved processing-target identity as the filesystem identity model for
  existing processing inputs. Symlink spellings are not preserved for runtime processing identity,
  generated filesystem-related header metadata, or machine-readable path fields; consumers that need
  the exact invocation spelling should retain it outside TopMark's processing result payloads.
- Hard-linked selected processing paths are now treated as unsupported processing targets. TopMark
  reports each affected path independently and does not choose a source, target, winner, or loser
  path from the hard-link group.
- Performance baseline outputs are written to Git-ignored `artifacts/perf/` run directories and are
  intended for local analysis rather than source control.
- GitHub issue 165 performance validation regenerated an informational smoke benchmark after the
  probe runtime migration. The current benchmark corpus remains effectively flat because it measures
  single-file check/strip processing rather than cumulative probe orchestration or public streaming
  output.

______________________________________________________________________

## [1.0.1] - 2026-05-26

This first TopMark 1.0 patch release focuses on post-1.0 correctness fixes, documentation
architecture refinement, and dependency maintenance.

It preserves the stable 1.x CLI, configuration, registry, probe, pipeline, public API, and
machine-readable output contracts established in `1.0.0`.

### Highlights - 1.0.1

- Fixed unified diff rendering when pipeline views are pruned.
- Fixed Markdown diff rendering for diffs containing nested fenced code blocks.
- Reorganized and refined the 1.0 documentation architecture.
- Added dedicated getting-started and CI integration documentation.
- Refreshed dependencies and pre-commit tooling.

### Changed - 1.0.1

- Simplified internal pipeline selection logic for readability and maintainability.
- Clarified pipeline view-pruning option naming internally.
- Refined documentation structure by separating user-facing workflows from developer internals.
- Moved machine-output documentation from:
  - `docs/dev/machine-output.md`
  - to `docs/usage/machine-output.md`

### Fixed - 1.0.1

- Fixed `topmark check --diff` and `topmark strip --diff` losing unified diff output when pipeline
  view pruning was enabled.
- Fixed Markdown diff rendering when changed Markdown content itself contains triple-backtick or
  longer fenced code blocks.
- Added regression coverage for CLI/API diff output with view pruning enabled.

### Documentation - 1.0.1

- Added:
  - `docs/usage/getting-started.md`
  - `docs/usage/ci.md`
- Improved README quick-start and product positioning.
- Improved installation and contribution guidance.
- Refined configuration, pipeline, architecture, command-reference, and hosted-doc navigation pages.
- Updated MkDocs navigation for the revised documentation information architecture.

### Internal - 1.0.1

- Updated machine-output tests to match documentation and output-contract wording changes.
- Added regression coverage for diff-view preservation and Markdown fence collision handling.
- Refreshed locked dependencies including `click`, `ruff`, and `uv`.
- Updated pre-commit dependencies, including TopMark itself.

### Notes - 1.0.1

- This release is intended as a patch release for the stable 1.x line.
- It does not intentionally introduce new user-facing CLI behavior or machine-readable output schema
  changes.
- Larger architectural follow-ups remain deferred, including:
  - evaluating `rich-click`;
  - replacing `yachalk` with `rich`;
  - and moving toward streaming pipeline processing.

______________________________________________________________________

## [1.0.0] - 2026-05-21

This first stable **TopMark 1.0 release** finalizes the long-running stabilization, contract-freeze,
documentation-governance, CI/release-hardening, and published-artifact validation work completed
through the alpha, beta, and release-candidate series.

TopMark 1.0 establishes the stable 1.x release line with frozen contracts for:

- CLI behavior and exit-code semantics;
- layered runtime configuration behavior and policy evaluation;
- registry composition and runtime resolution;
- probe semantics and runtime applicability behavior;
- machine-readable JSON and NDJSON output contracts;
- pipeline execution and semantic outcome reporting;
- public API compatibility governance;
- and deterministic CI/release validation behavior.

The final stabilization cycle validated these contracts through:

- local validation and reproducible release workflows;
- GitHub Actions CI and release orchestration;
- TestPyPI prerelease publication;
- GitHub prerelease publication;
- cross-platform published-artifact validation;
- ecosystem and compatibility observation;
- and focused late-stage correctness and portability fixes.

`1.0.0` itself primarily promotes the validated `1.0.0rc1` contracts into the stable 1.x release
line and finalizes the user-facing migration, governance, onboarding, installation, release, and
documentation posture for long-term maintenance.

> [!IMPORTANT]
>
> TopMark 1.0 introduces stable 1.x compatibility governance for:
>
> - CLI behavior and semantic exit-code handling;
> - runtime configuration structure and layered resolution behavior;
> - machine-readable JSON and NDJSON output contracts;
> - public API compatibility expectations;
> - registry identity and runtime resolution behavior;
> - deterministic CI/release validation architecture.

\\

> [!CAUTION] **Upgrade guidance**
>
> Users upgrading from TopMark `0.11.x` or earlier should review:
>
> - `docs/usage/upgrading-to-1.0.md`
>
> before migrating existing repositories, CI workflows, or pre-commit hooks.

### Highlights - 1.0.0

- Finalized the stable 1.x compatibility and governance model.
- Promoted the validated `1.0.0rc1` contracts into the stable release line.
- Added a dedicated user-facing migration guide for upgrading from TopMark `0.11.x` and earlier.
- Finalized stable release wording across installation, contributor, release, API, CI, runtime,
  configuration, terminology, and architecture documentation.
- Finalized the roadmap transition from release-candidate readiness toward stable 1.x governance and
  maintenance posture.
- Finalized hosted documentation linking and onboarding flow for the published documentation site.
- Preserved the stabilized artifact-based CI/release publication architecture and published-artifact
  validation workflow.

### Added - 1.0.0

- **TopMark 1.0 migration guidance**

  - Added:
    - `docs/usage/upgrading-to-1.0.md`
  - Documented:
    - CLI migration considerations;
    - configuration restructuring;
    - pre-commit hook migration;
    - machine-readable output migration;
    - runtime policy changes;
    - staged validation and upgrade workflows.

- **Upgrade-guide integration**

  - Added upgrade-guide references across:
    - `README.md`
    - `INSTALL.md`
    - `docs/install.md`
    - `docs/index.md`
    - `docs/dev/release-process.md`

### Changed - 1.0.0

- **Stable 1.x governance posture**

  - Transitioned roadmap and governance documentation from:
    - release-candidate readiness;
    - final validation posture;
    - prerelease governance.
  - Toward:
    - stable 1.x maintenance;
    - compatibility preservation;
    - post-1.0 deferral tracking;
    - long-term governance posture.

- **Stable release wording**

  - Finalized stable-release wording across:
    - installation documentation;
    - contributor documentation;
    - API governance documentation;
    - CI/release documentation;
    - runtime architecture documentation;
    - terminology and configuration documentation.

- **Hosted documentation integration**

  - Replaced repository-local links to published documentation pages with stable hosted
    documentation URLs where appropriate.
  - Preserved repository-local references for:
    - `CHANGELOG.md`
    - `LICENSE`
    - contributor workflow files;
    - repository-owned resources.

### Fixed - 1.0.0

- **Release-governance wording drift**

  - Fixed remaining prerelease-oriented wording after successful `1.0.0rc1` validation.
  - Clarified stable 1.x compatibility guarantees and maintenance posture across roadmap, release,
    installation, API, CI, and contributor documentation.

- **Migration discoverability**

  - Fixed missing centralized upgrade guidance for users migrating from pre-1.0 releases.

### Documentation - 1.0.0

- Finalized stable 1.x wording throughout the documentation set.
- Added and integrated the dedicated TopMark 1.0 migration guide.
- Finalized hosted documentation navigation and onboarding references.
- Finalized roadmap/governance separation between:
  - historical stabilization narrative;
  - stable 1.x governance;
  - explicit post-1.0 deferrals.
- Finalized terminology and compatibility wording around:
  - runtime configuration;
  - registry composition;
  - runtime resolution;
  - machine-readable compatibility contracts;
  - CI/release validation behavior.

### Internal - 1.0.0

- Preserved the stabilized artifact-based CI/release publication architecture.
- Preserved published-artifact validation as an external validation surface separate from release
  gating.
- Preserved frozen 1.0 CLI, API, configuration, registry, probe, machine-readable output, and
  pipeline contracts established during the alpha/beta/RC stabilization cycle.
- Continued emphasizing semantic validation and compatibility preservation over metric-based release
  governance.

### Notes - 1.0.0

- This release intentionally avoids reopening frozen 1.0 contracts established during the prerelease
  stabilization cycle.
- The stable 1.x maintenance path is intentionally focused on:
  - compatibility preservation;
  - ecosystem observation;
  - focused correctness fixes;
  - documentation clarity;
  - and explicit post-1.0 evolution tracking.
- Broad architectural redesign, output-contract churn, and large new integration scope remain
  intentionally deferred unless required by a concrete stable 1.x compatibility or correctness
  issue.

______________________________________________________________________

## [1.0.0rc1] - 2026-05-20

This first **1.0 release candidate** marks the transition from late-beta stabilization into final
release-candidate validation for TopMark's 1.0 release line.

The release-candidate phase is now focused on compatibility preservation, packaging validation,
published-artifact verification, ecosystem observation, and release-blocking fixes only. It does not
reopen frozen CLI, API, configuration, registry, probe, machine-readable output, pipeline, or policy
contracts.

`1.0.0rc1` primarily consolidates the stabilization work completed across the beta series by:

- finalizing the RC governance roadmap;
- extracting the detailed 1.0 stabilization history into a dedicated historical document;
- improving PyPI package discoverability and onboarding clarity;
- simplifying pytest marker usage after improved typing support;
- documenting prerelease installation guidance through TestPyPI;
- and tightening final release-process documentation ahead of `1.0.0`.

> [!CAUTION] **Breaking changes**
>
> - The temporary typed pytest marker/decorator wrapper layer has been removed.
> - Tests now consistently use direct native `pytest.mark.*` decorators and pytest APIs.
> - Project metadata, release documentation, and roadmap governance were finalized for the RC phase.

### Breaking Changes - 1.0.0rc1

- **Typed pytest wrapper removal**

  - Removed the temporary typed pytest helper layer from:
    - `tests/conftest.py`
  - Tests now consistently use native pytest decorators directly:
    - `pytest.mark.*`
    - `pytest.mark.parametrize`
    - `pytest.hookimpl`
  - Removed the local typed wrapper helpers:
    - `parametrize()`
    - `hookimpl()`
  - Existing pytest marker names and selection behavior remain unchanged.

- **Roadmap and stabilization-document restructuring**

  - Refactored `docs/dev/roadmap.md` into a concise RC-governance and release-readiness document.
  - Extracted the historical alpha/beta stabilization narrative into:
    - `docs/dev/road-to-1.0.md`
  - Remaining roadmap scope is now explicitly limited to:
    - compatibility preservation;
    - release validation;
    - ecosystem observation;
    - release-blocking fixes.

### Highlights - 1.0.0rc1

- Finalized the split between active RC governance and historical stabilization documentation.
- Added the dedicated:
  - `docs/dev/road-to-1.0.md` historical stabilization narrative.
- Refined project metadata and README onboarding/discoverability ahead of final release.
- Simplified pytest marker/decorator usage after improved typing-environment support.
- Added canonical prerelease installation guidance through TestPyPI.
- Finalized RC-oriented release-process and published-artifact validation documentation.
- Preserved all frozen 1.0 CLI, API, configuration, registry, probe, pipeline, and machine-readable
  output contracts.

### Added - 1.0.0rc1

- **Historical stabilization reference**

  - Added:
    - `docs/dev/road-to-1.0.md`
  - Documented:
    - alpha stabilization themes;
    - beta validation goals;
    - contract-freeze philosophy;
    - CI/release maturation;
    - documentation-governance evolution;
    - coverage-governance rationale;
    - release-validation hardening.

- **Prerelease installation guidance**

  - Added canonical TestPyPI prerelease installation instructions to:
    - `INSTALL.md`
  - Added cross-references from release and validation documentation to the canonical install
    guidance.

### Changed - 1.0.0rc1

- **RC governance posture**

  - Condensed the roadmap's:
    - breaking-changes ledger;
    - remaining-work sections;
    - readiness checklist;
    - release-governance wording.
  - Clarified the distinction between:
    - stabilization history;
    - RC governance;
    - post-1.0 deferrals.

- **PyPI package discoverability**

  - Refined `pyproject.toml` metadata and classifiers.
  - Expanded project keywords around:
    - file-header management;
    - CI automation;
    - developer tooling;
    - validation workflows.
  - Improved README onboarding language and discoverability wording.

- **Pytest usage consistency**

  - Standardized tests on direct native pytest decorator usage.
  - Removed obsolete local typing workarounds after improved typing-environment support.

- **Release documentation**

  - Updated release-process and published-artifact validation documentation for:
    - RC terminology;
    - prerelease installation;
    - validation sequencing;
    - release-governance clarity.

### Fixed - 1.0.0rc1

- **Typing-workaround drift**

  - Removed obsolete typed pytest wrappers that were no longer needed after improved typing support.
  - Reduced decorator indirection and simplified test readability.

- **Roadmap/documentation drift**

  - Fixed stale roadmap wording that still described future extraction of stabilization history
    after the historical document had already been created.
  - Clarified RC-phase wording around:
    - contract freezes;
    - compatibility preservation;
    - release governance.

- **Prerelease-installation discoverability**

  - Fixed missing canonical user-facing guidance for installing prereleases from TestPyPI.

### Documentation - 1.0.0rc1

- Added the dedicated `Road to TopMark 1.0` historical stabilization document.
- Refactored the active roadmap into a concise RC-governance reference.
- Updated release-process documentation for prerelease installation and RC validation flow.
- Updated published-artifact validation examples for the `1.0.0rc1` release-candidate path.
- Expanded README onboarding and project-discovery wording.
- Expanded package metadata and classifiers for improved PyPI discoverability.
- Updated testing documentation to remove obsolete typed pytest wrapper examples.

### Internal - 1.0.0rc1

- Preserved all frozen 1.0 contracts established during the alpha and beta stabilization series.
- Continued emphasizing coverage as a confidence-building signal rather than a release gate.
- Preserved the existing artifact-based CI/release publication architecture.
- Kept published-artifact validation external to release gating while maintaining it as a mandatory
  RC-validation activity.
- Reduced local testing indirection by removing obsolete pytest typing helper layers.

### Notes - 1.0.0rc1

- This release candidate intentionally avoids introducing new user-facing functionality.
- The focus is final release validation, packaging verification, ecosystem observation, and
  release-blocking fixes only.
- CLI behavior, configuration semantics, registry/resolution behavior, probe semantics,
  machine-readable output contracts, and pipeline behavior remain frozen.
- Coverage reporting remains intentionally informational rather than percentage-gated.
- Published-artifact validation should be executed against the `1.0.0rc1` TestPyPI artifacts before
  final `1.0.0` release approval.
- Unless concrete release blockers are identified, the remaining path to `1.0.0` should now be
  limited to:
  - release-candidate feedback;
  - compatibility preservation;
  - ecosystem observation;
  - packaging validation;
  - and narrowly scoped release-blocking fixes.

______________________________________________________________________

## [1.0.0b7] - 2026-05-20

This seventh **1.0 beta release** focuses on final late-beta CI/release workflow stabilization,
canonical coverage reporting integration, metadata-driven Python-version management, workflow
bootstrap hardening, and dependency-refresh validation ahead of `1.0.0rc1`.

It does not reopen frozen CLI, API, configuration, registry, probe, machine-readable output, or
pipeline behavior contracts. Instead, it strengthens the CI, release, validation, coverage,
workflow-bootstrap, and operational-governance surfaces around those frozen contracts by finalizing
coverage-reporting architecture, stabilizing Python-version provenance handling, centralizing CI
bootstrap ownership, improving release metadata diagnostics, documenting workflow boundaries, and
validating the resulting model through real GitHub workflow runs.

> [!CAUTION] **Breaking changes**
>
> - CI Python-version metadata is now derived dynamically through `nox -s print_python_matrix`.
> - Canonical single-version CI jobs now consume resolved metadata rather than duplicated version
>   literals.
> - Shared uv cache ownership is now centralized through explicit `actions/cache` integration.

### Breaking Changes - 1.0.0b7

- **Metadata-driven CI Python-version resolution**

  - The CI workflow now derives supported and canonical Python versions dynamically through:
    - `nox -s print_python_matrix`
  - Compatibility-matrix jobs and canonical single-version jobs now consume resolved metadata rather
    than duplicated version literals embedded directly in the workflow.
  - The shared `setup-python-nox` composite action is now workflow-neutral and no longer hard-codes
    the canonical TopMark Python version.

- **Release-tooling provenance diagnostics**

  - Release publication intentionally continues to use an explicit tooling/runtime Python version.
  - The release workflow now emits non-blocking drift warnings when the explicit release-tooling
    Python version differs from the canonical CI Python metadata.

- **Explicit uv cache ownership**

  - Disabled the built-in `setup-uv` cache integration.
  - Centralized shared uv cache ownership through explicit `actions/cache` integration.
  - Concurrent CI jobs no longer compete for implicit uv cache ownership.

### Highlights - 1.0.0b7

- Added canonical CI coverage reporting through the existing `nox -s coverage` session.
- Added GitHub Step Summary coverage reporting and published HTML/XML/JSON coverage artifacts.
- Stabilized coverage-summary generation after multiple GitHub Actions shell/YAML edge cases.
- Integrated coverage reporting into the late-beta release-validation workflow model while keeping
  coverage diagnostic rather than release-blocking.
- Added metadata-driven CI Python-version management through `nox -s print_python_matrix`.
- Simplified Python-version management by deriving supported interpreters directly from project
  metadata.
- Added CI/release provenance reporting for canonical vs explicit release-tooling Python versions.
- Added dedicated documentation for:
  - CI workflows;
  - release workflows;
  - test-validation layering;
  - install-smoke validation;
  - and the `setup-python-nox` composite action.
- Eliminated noisy concurrent uv cache-reservation warnings by centralizing explicit cache
  ownership.
- Refreshed locked dependencies within the existing supported version ranges.

### Added - 1.0.0b7

- **Canonical CI coverage reporting**

  - Added a dedicated coverage job to the main CI workflow.
  - Coverage runs through the existing:
    - `nox -s coverage`
  - Coverage executes on Ubuntu using the canonical single-version Python runtime instead of the
    full compatibility matrix.
  - Added GitHub Step Summary coverage reporting including:
    - coverage percentage;
    - covered-line count;
    - total-statement count;
    - and links to workflow artifacts.
  - Added published coverage artifacts for:
    - HTML coverage output;
    - XML coverage reports;
    - JSON coverage reports.

- **Python metadata resolution**

  - Added:
    - `nox -s print_python_matrix`
  - The session emits:
    - supported Python matrix metadata;
    - canonical single-version metadata.
  - Added a dedicated CI metadata-resolution job that:
    - derives compatibility-matrix interpreters;
    - derives canonical single-version interpreters;
    - exports metadata to downstream jobs and release workflows.

- **Workflow provenance reporting**

  - Added release-workflow diagnostics for:
    - canonical CI Python version;
    - explicit release-tooling Python version;
    - non-blocking drift warnings.

- **Workflow/bootstrap documentation**

  - Added:
    - `docs/ci/setup-python-nox-action.md`
  - Documented:
    - bootstrap responsibilities;
    - cache ownership;
    - metadata resolution;
    - workflow neutrality;
    - maintenance expectations.

### Changed - 1.0.0b7

- **Coverage workflow architecture**

  - Coverage reporting now runs only after the full compatibility test matrix succeeds.
  - Kept coverage reporting informational rather than percentage-gated.
  - Avoided full matrix-wide coverage execution to reduce duplicated CI cost and runtime.

- **CI workflow structure**

  - Added explicit job names across CI and release workflows.
  - Clarified workflow naming and sequencing around:
    - tests;
    - coverage;
    - release publication;
    - metadata reporting.

- **Nox metadata handling**

  - Replaced custom TOML parsing with Nox's built-in pyproject helpers.
  - Simplified noxfile metadata handling and reduced custom parsing logic substantially.
  - Simplified GitHub Actions metadata parsing by emitting clean JSON directly from Nox.

- **Cache ownership model**

  - Standardized explicit uv cache ownership through:
    - `actions/cache`
  - Kept `setup-uv` cache integration disabled intentionally.
  - Reduced CI noise from concurrent cache-reservation attempts.

- **CI and release documentation**

  - Expanded workflow documentation for:
    - trigger semantics;
    - trust boundaries;
    - metadata handling;
    - canonical vs compatibility Python runtimes;
    - coverage architecture;
    - artifact publication;
    - bootstrap/cache ownership.
  - Updated roadmap status to reflect:
    - finalized workflow stabilization;
    - metadata-driven CI architecture;
    - canonical coverage reporting;
    - explicit cache ownership;
    - remaining README coverage-badge deferral.

- **Dependency maintenance**

  - Refreshed locked dependencies including:
    - `click`
    - `hypothesis`
    - `mkdocs-include-markdown-plugin`
    - `pydoclint`
    - `uv`

### Fixed - 1.0.0b7

- **Coverage summary publication failures**

  - Fixed GitHub Actions shell/heredoc parsing failures during coverage-summary publication.
  - Fixed quoting/parsing issues caused by embedded Python inside GitHub Actions YAML.
  - Stabilized coverage-summary generation using temporary-script execution.

- **CI metadata parsing drift**

  - Fixed GitHub Actions metadata parsing failing because Nox prefixes normal session output.
  - Fixed fragile inline workflow parsing by emitting clean JSON directly from:
    - `nox -s print_python_matrix`

- **Workflow cache-reservation noise**

  - Fixed repeated warnings such as:
    - `Unable to reserve cache ... another job may be creating this cache`
  - Eliminated concurrent implicit cache writers by centralizing cache ownership explicitly.

- **Workflow naming clarity**

  - Fixed ambiguous workflow/job naming around coverage sequencing and release publication behavior.

### Documentation - 1.0.0b7

- Added dedicated documentation for the `setup-python-nox` composite action.
- Expanded CI workflow documentation for:
  - canonical coverage reporting;
  - metadata-driven Python resolution;
  - explicit uv cache ownership;
  - workflow sequencing;
  - release provenance reporting.
- Expanded release-workflow documentation for:
  - canonical vs explicit release-tooling Python runtimes;
  - provenance diagnostics;
  - drift warnings.
- Expanded test-validation documentation for:
  - canonical coverage execution;
  - local coverage reproduction;
  - metadata-driven Python-version handling.
- Updated roadmap status to record:
  - finalized CI/release workflow stabilization;
  - explicit cache-ownership governance;
  - metadata-driven CI architecture;
  - validated coverage reporting integration;
  - remaining README coverage-badge deferral.

### Internal - 1.0.0b7

- Preserved the existing artifact-based release architecture while strengthening workflow metadata
  provenance and diagnostics.
- Kept coverage reporting diagnostic-only to avoid turning percentage targets into release
  governance.
- Preserved explicit release-tooling Python selection for deterministic release publication while
  surfacing metadata drift non-fatally.
- Reduced duplicated CI-version literals by centralizing metadata resolution through Nox.
- Simplified workflow bootstrap ownership and cache behavior.
- Validated the finalized late-beta workflow model through real GitHub Actions runs.

### Notes - 1.0.0b7

- This beta primarily finalizes CI/release workflow governance and operational stabilization rather
  than introducing new user-facing functionality.
- Frozen 1.0 contracts for CLI behavior, configuration semantics, registry/resolution, probe
  behavior, machine-readable output, and public API surfaces remain unchanged.
- Coverage reporting is intentionally informational rather than release-blocking.
- README coverage badge integration remains intentionally deferred pending longer-term signal
  stability review.
- Remaining work before `1.0.0rc1` should now primarily consist of:
  - final release validation;
  - packaging checks;
  - published-artifact validation;
  - ecosystem observation across real CI/release runs;
  - and any concrete final beta feedback.

______________________________________________________________________

## [1.0.0b6] - 2026-05-20

This sixth **1.0 beta release** focuses on pre-RC internal typing, ownership-boundary cleanup, and
typed-result hardening ahead of `1.0.0rc1`.

> [!CAUTION] **Breaking changes**
>
> - `run_pipeline()` and `run_probe_pipeline()` now return `ApiPipelineRun`.
> - `run_steps_for_files()` now returns `PipelineExecution`.
> - Several internal helper APIs now return frozen typed result objects instead of positional
>   tuples.

### Breaking Changes - 1.0.0b6

- **Typed low-level API runtime results**

  - `run_pipeline()` and `run_probe_pipeline()` now return `ApiPipelineRun` instead of:
    - `(FrozenConfig, list[Path], list[ProcessingContext], ExitCode | None)`
  - `ApiPipelineRun` is exposed through the public API snapshot for integrations that intentionally
    consume low-level runtime state.

- **Typed pipeline engine results**

  - `run_steps_for_files()` now returns `PipelineExecution` instead of:
    - `(list[ProcessingContext], ExitCode | None)`

- **Typed internal helper results**

  - Replaced several mixed tuple return contracts with frozen typed result objects across:
    - version formatting;
    - TOML template loading;
    - config resolution;
    - CLI input planning;
    - processor stripping;
    - diagnostic presentation;
    - glob rebasing;
    - file type candidate ordering.

### Highlights - 1.0.0b6

- Replaced ambiguous mixed tuple returns with named frozen value objects.
- Tightened read-only protocol and view ownership boundaries.
- Clarified public API snapshot vs plugin-facing protocol surfaces.
- Tightened XML strip diagnostics so spacer-cleanup notes are emitted only when XML-specific cleanup
  actually occurs.
- Simplified CLI input planning by removing duplicated dash-sentinel cleanup.
- Preserved user-facing CLI behavior and machine-readable output schemas.

### Changed - 1.0.0b6

- **Typing and ownership boundaries**

  - Tightened protocol/view surfaces toward read-only semantics where mutation is not intended.
  - Replaced mutable `dict` exposure with `Mapping` where callers only observe values.
  - Clarified intentional mutable registry bindings and instance-level processor delimiter state.

- **Typed result objects**

  - Added typed result objects including:
    - `ComputedVersion`
    - `DefaultTomlTemplateText`
    - `ApiPipelineRun`
    - `PipelineExecution`
    - `StripHeaderResult`
    - `HumanDiagnostics`
    - `RebasedGlobPatterns`
    - `ResolvedConfigDraft`
    - `PreparedCliConfig`
    - `FileTypeCandidateOrderKey`

- **CLI input planning**

  - Replaced tuple-based `--*-from` helper returns with typed result objects.
  - Simplified `plan_cli_inputs()` so dash-sentinel cleanup is performed once after mode-specific
    input routing.

- **Protocol documentation**

  - Clarified plugin-facing protocols, diagnostic protocols, console protocols, processor mixins,
    and writer sink contracts.
  - Clarified that `api/protocols.py` is public-adjacent integration surface, not part of the
    exported public API snapshot.

### Fixed - 1.0.0b6

- **XML strip diagnostic precision**

  - Fixed XML strip diagnostics claiming policy-spacer cleanup even when no XML-specific spacer was
    removed.

- **Typing ambiguity**

  - Fixed multiple strict-typing ambiguity points caused by positional mixed tuples and mutable
    protocol/view surfaces.

- **Stale internal documentation**

  - Fixed stale tuple-return docstrings, outdated comments, typo drift, and incorrect ownership
    wording across runtime, pipeline, processor, CLI, config, and presentation helpers.

### Documentation - 1.0.0b6

- Updated roadmap status to record substantial completion of late-beta typing and ownership cleanup.
- Documented the remaining coverage workflow/reporting follow-up as an open roadmap item.
- Clarified that README coverage badge adoption remains deferred until CI coverage reporting exists
  and provides a stable public quality signal.

### Internal - 1.0.0b6

- Improved Pyright strict-mode clarity by replacing positional result tuples with typed DTOs.
- Updated tests to consume named result fields instead of tuple positions.
- Refined processor, pipeline, runtime, config, CLI, and presentation ownership boundaries.
- Preserved existing user-facing CLI behavior and emitted machine-readable output schemas.

### Notes - 1.0.0b6

- This beta is an internal hardening release, not a new feature release.
- The main focus is strict typing, ownership clarity, and pre-RC maintainability.
- Coverage workflow/reporting and possible README coverage badge integration remain open roadmap
  items for follow-up.

______________________________________________________________________

## [1.0.0b5] - 2026-05-19

This fifth **1.0 beta release** focuses on late-stage pre-release hardening through expanded
semantic coverage, presentation-contract stabilization, pipeline lifecycle validation, TOML mutation
testing, and internal ownership-boundary cleanup ahead of the `1.0.0rc1` release candidate.

It does not reopen frozen CLI, API, configuration, registry, probe, machine-readable output, or
pipeline behavior contracts. Instead, it strengthens confidence in those frozen contracts by adding
focused coverage for planner, stripper, patcher, writer, TOML surgery, diagnostic rendering,
registry rendering, pipeline rendering, CLI validator policy handling, XML processor edge cases, and
pipeline outcome classification.

This release also continues internal ownership-boundary refinement by relocating shared constants
and shared outcome primitives into the `topmark.core` package, removing the obsolete
`topmark.rendering` package, and tightening presentation-layer ownership semantics.

> [!CAUTION] **Breaking changes**
>
> - The former `topmark.constants` module has moved to `topmark.core.constants`.
> - The obsolete `topmark.rendering` package has been removed.
> - Internal presentation and outcome helpers were reorganized around canonical core ownership
>   boundaries.

### Breaking Changes - 1.0.0b5

- **Core constants relocation**

  - The former top-level `topmark.constants` module has moved to `topmark.core.constants`.
  - Shared package metadata, registry-token primitives, marker strings, newline constants, and TOML
    resource constants now live under the canonical `topmark.core` namespace.
  - Internal and advanced callers importing from `topmark.constants` must update imports.

- **Rendering package removal**

  - Removed the obsolete `topmark.rendering` package.
  - The unused `topmark.rendering.api` convenience layer has been deleted.
  - Unified diff formatting helpers now live under:
    - `topmark.presentation.formatters`
  - Internal callers importing `format_patch_plain()` from the old rendering package must update
    imports.

- **Internal ownership-boundary cleanup**

  - Shared outcome primitives (`Outcome`, `OUTCOME_ORDER`, `NO_REASON_PROVIDED`) now live in
    `topmark.core.outcomes`.
  - Pipeline, presentation, and API layers now consume the shared core outcome primitives directly.
  - `Outcome` remains a stable `topmark.api` re-export for public API consumers.

### Highlights - 1.0.0b5

- Added extensive focused semantic coverage for planner, stripper, patcher, writer, TOML surgery,
  TOML template surgery, pipeline outcomes, CLI validators, pipeline rendering, registry rendering,
  diagnostic rendering, and XML processor edge cases.
- Expanded XML processor coverage for declaration-safe insertion, BOM handling, DOCTYPE anchoring,
  strip cleanup, and policy-aware spacing behavior.
- Added dedicated semantic rendering tests for text and Markdown pipeline, registry, and diagnostic
  presentation.
- Added focused CLI validator and typed CLI state bootstrap coverage without invoking the full Click
  command tree.
- Added focused outcome bucketing coverage for semantic pipeline result classification and summary
  aggregation behavior.
- Added JSON-like insertion-policy coverage and improved JSONC detection for block comments.
- Removed the obsolete `topmark.rendering` package and consolidated rendering ownership under
  `topmark.presentation`.
- Relocated shared constants and outcome primitives into the `topmark.core` package.
- Removed the unused introspection utility module and simplified planner diagnostic handling.
- Improved generated API page generation for empty package sections and child-link rendering.
- Fixed CLI color warning rendering so diagnostics use stable CLI-facing enum values across Python
  versions.
- Continued late-beta coverage and ownership-boundary hardening ahead of `1.0.0rc1`.

### Added - 1.0.0b5

- **Pipeline lifecycle coverage**

  - Added focused coverage for:
    - `PlannerStep`
    - `StripperStep`
    - `PatcherStep`
    - `WriterStep`
  - Added tests for:
    - dry-run behavior;
    - replace vs insert planning;
    - malformed-header handling;
    - blocked insertion policies;
    - unified diff generation;
    - write sink behavior;
    - atomic and in-place writes;
    - header mutation policy enforcement;
    - non-mutating execution paths;
    - failure handling without target truncation.

- **Presentation rendering coverage**

  - Added focused semantic rendering tests for:
    - pipeline presentation;
    - registry presentation;
    - diagnostic presentation.
  - Added normalized Markdown table assertion helpers for stable semantic table assertions without
    spacing-sensitive snapshots.

- **TOML mutation coverage**

  - Added focused tests for:
    - TOML surgery helpers;
    - TOML template surgery helpers;
    - pyproject nesting;
    - root flag insertion/removal;
    - idempotence;
    - invalid TOML handling;
    - target-table scoping;
    - TopMark header-block placement.

- **CLI validator and state coverage**

  - Added dedicated unit coverage for:
    - CLI validation helpers;
    - option-policy handling;
    - typed CLI state bootstrapping;
    - legacy mapping lifting;
    - STDIN dash validation;
    - mutually exclusive options;
    - machine-format restrictions.

- **Pipeline outcome coverage**

  - Added dedicated semantic coverage for:
    - intent inference;
    - outcome bucketing;
    - policy veto handling;
    - dry-run vs apply mapping;
    - summary aggregation;
    - deterministic outcome ordering.

- **XML processor edge-case coverage**

  - Added focused XML processor tests covering:
    - BOM and declaration offset detection;
    - DOCTYPE anchoring;
    - malformed declaration fallback behavior;
    - single-line prolog insertion;
    - declaration-safe strip cleanup;
    - policy-aware spacing and trimming behavior.

- **JSON-like insertion and JSONC detection coverage**

  - Added focused coverage for:
    - JSON-like insertion policies;
    - explicit JSON promotion behavior;
    - JSONC comment detection;
    - block comment handling;
    - unterminated comment detection;
    - escaped string behavior.

- **Utility and enum coverage**

  - Added focused unit coverage for:
    - enum parsing helpers;
    - keyed enum metadata behavior;
    - merge helper utilities;
    - processing status helpers;
    - pipeline status serialization.

### Changed - 1.0.0b5

- **Core ownership boundaries**

  - Moved shared constants into `topmark.core.constants`.
  - Moved shared outcome primitives into `topmark.core.outcomes`.
  - Updated API, pipeline, presentation, CLI, processor, registry, and test imports accordingly.
  - Clarified ownership boundaries in module docstrings and generated API pages.

- **Presentation ownership**

  - Removed the obsolete `topmark.rendering` package.
  - Relocated unified diff formatting into:
    - `topmark.presentation.formatters.unified_diff`
  - Consolidated presentation formatting helpers under the presentation layer.

- **Generated API page generation**

  - Refactored `tools/docs/gen_api_pages.py` to centralize breadcrumb and child-section rendering.
  - Improved handling for packages with no top-level modules.
  - Prevented invalid generated `(none).md` links for empty package sections.

- **JSONC detection**

  - Updated JSONC detection to recognize block comments in addition to line comments.
  - Preserved correct behavior for comment markers appearing inside JSON strings.

- **Planner diagnostics**

  - Removed the standalone introspection helper module.
  - Inlined planner checker-name fallback logic used only for diagnostic reporting.

- **CLI validator diagnostics**

  - Updated forced-color warnings to render stable CLI-facing enum values such as:
    - `--color=always`
  - Avoided Python-version-specific enum repr formatting in diagnostics.

- **Merge helper behavior**

  - Updated `none_if_empty()` so empty iterators behave consistently with empty containers by
    materializing iterables before emptiness checks.

### Fixed - 1.0.0b5

- **Generated API navigation drift**

  - Fixed generated API package indices emitting invalid `(none).md` links when packages lacked
    top-level modules.
  - Fixed empty generated-package sections rendering placeholder names instead of explicit empty
    states.

- **CLI warning rendering drift**

  - Fixed forced-color warnings using Python enum repr output such as:
    - `ColorMode.ALWAYS`
  - Diagnostics now consistently render canonical CLI-facing values such as:
    - `always`

- **JSONC detection gaps**

  - Fixed JSONC detection missing block comments while still correctly ignoring comment markers
    inside strings.

- **Merge helper iterator handling**

  - Fixed `none_if_empty()` incorrectly treating empty iterators differently from empty sized
    containers.

- **Rendering ownership drift**

  - Fixed obsolete rendering helpers remaining outside the canonical presentation layer.

### Documentation - 1.0.0b5

- Updated generated API documentation ownership boundaries for shared constants and outcome
  primitives.
- Updated generated API page helpers and package index generation behavior.
- Updated presentation-layer ownership references after removing the obsolete rendering package.
- Updated roadmap status to reflect:
  - expanded late-beta semantic coverage;
  - pipeline lifecycle hardening;
  - presentation-contract validation;
  - TOML mutation coverage;
  - ownership-boundary cleanup ahead of `1.0.0rc1`.

### Internal - 1.0.0b5

- Continued the late-beta semantic coverage pass across pipeline, presentation, TOML, CLI,
  processors, registry, and utility layers.
- Preferred semantic assertions over formatting-sensitive snapshots in new rendering tests to
  stabilize frozen presentation contracts.
- Preserved existing CLI, API, config, registry, and pipeline behavior while tightening lifecycle
  validation coverage.
- Reduced cross-layer imports by relocating shared primitives into `topmark.core`.
- Simplified planner diagnostics by removing the standalone introspection utility module.
- Improved strict typing coverage in validator tests and JSON-like insertion checks.

### Notes - 1.0.0b5

- This beta primarily strengthens semantic validation coverage and ownership-boundary clarity rather
  than introducing new user-facing functionality.
- Frozen 1.0 contracts for CLI behavior, config semantics, registry/resolution, probe behavior,
  machine-readable output, and pipeline execution remain unchanged.
- The focus is semantic lifecycle hardening, presentation validation, TOML mutation coverage, and
  internal cleanup ahead of the release-candidate phase.
- Remaining work before `1.0.0rc1` should now primarily consist of:
  - final release validation;
  - packaging checks;
  - published-artifact validation;
  - selective internal cleanup items already documented in the roadmap;
  - and any concrete final beta feedback.

______________________________________________________________________

## [1.0.0b4] - 2026-05-18

This fourth **1.0 beta release** focuses on final release-workflow polish, GitHub prerelease
visibility, published-artifact validation closure, documentation terminology stabilization,
canonical mutable/immutable runtime type naming, command documentation consistency, TOML template
polish, and documentation/code prose hygiene ahead of the release-candidate phase.

It does not reopen frozen CLI, API, configuration, registry, probe, machine-readable output, or
pipeline behavior contracts. Instead, it strengthens the public and developer-facing surfaces around
those contracts by finalizing terminology, aligning command pages, tightening changelog hygiene,
adding Python prose hygiene validation, documenting the prerelease GitHub Release policy, adding a
read-only pre-commit probe hook, and completing the canonical `MutableX` / `FrozenX` naming model.

> [!CAUTION] **Breaking changes**
>
> - The immutable public/runtime configuration type `Config` is now named `FrozenConfig`.
> - The immutable policy snapshot type `Policy` is now named `FrozenPolicy`.
> - The mutable diagnostic log type `DiagnosticLog` is now named `MutableDiagnosticLog`.
> - The immutable staged validation-log type `ValidationLogs` is now named `FrozenValidationLogs`.
> - The canonical terminology glossary moved from `docs/dev/terminology.md` to
>   `docs/terminology.md`.

### Breaking Changes - 1.0.0b4

- **Canonical mutable/immutable runtime type naming**

  - Renamed immutable and mutable runtime-support types to align with the canonical `MutableX` /
    `FrozenX` naming model:
    - `Config` -> `FrozenConfig`
    - `Policy` -> `FrozenPolicy`
    - `DiagnosticLog` -> `MutableDiagnosticLog`
    - `ValidationLogs` -> `FrozenValidationLogs`
  - Freeze/thaw semantics remain unchanged:
    - `MutableConfig.freeze()` returns `FrozenConfig`
    - `MutablePolicy.freeze()` returns `FrozenPolicy`
    - `MutableDiagnosticLog.freeze()` returns `FrozenDiagnosticLog`
    - `MutableValidationLogs.freeze()` returns `FrozenValidationLogs`
  - Downstream callers importing or referencing the old type names must update.

- **Configuration bridge helper naming**

  - Several configuration-resolution bridge helpers were renamed to describe mutable configuration
    construction explicitly.
  - Internal or advanced callers using these helpers must update imports and call sites.

- **Terminology glossary location**

  - The canonical terminology glossary moved from `docs/dev/terminology.md` to
    `docs/terminology.md`.
  - Internal links and external references to the old developer-only glossary path must be updated.

- **Documentation and prose hygiene gates**

  - Documentation and Python code-prose hygiene are now stricter validation surfaces.
  - Markdown prose and Python comments, docstrings, and prose-oriented string literals are checked
    for smart punctuation where applicable.
  - Contributors may need to replace Unicode dashes, curly quotes, or ellipses with ASCII
    punctuation before validation passes.

### Highlights - 1.0.0b4

- Finalized the canonical `MutableX` / `FrozenX` naming model across configuration, policy,
  diagnostics, and validation-log types.
- Enabled GitHub prerelease creation for alpha, beta, and release-candidate tags while preserving
  TestPyPI routing for prerelease package artifacts.
- Backfilled GitHub prereleases for `v1.0.0b1` and `v1.0.0b2` so the beta series now has coherent
  public release-note history.
- Confirmed the `v1.0.0b3` published artifacts install and run successfully on Windows, macOS, and
  Ubuntu after the Windows atomic-writer fix.
- Promoted the terminology glossary to `docs/terminology.md` as a project-wide vocabulary reference.
- Renamed `docs/dev/config-schema.md` to `docs/dev/configuration-schema.md` to align developer
  documentation terminology with the stabilized runtime configuration model.
- Added `_snippets/terminology.md` as the shared terminology note reused across documentation pages.
- Completed the command documentation consistency pass across pipeline, config, registry, probe,
  version, and shared usage pages.
- Harmonized terminology around effective runtime configuration, staged configuration-loading
  validation, runtime policy evaluation, processor bindings, semantic outcomes, and TEXT-oriented
  output.
- Refined `topmark-example.toml` into a calmer reference-style starter template.
- Added changelog-specific hygiene checks for release heading shape, allowed section headings,
  separator style, and heading depth.
- Added `tools/docs/check_code_hygiene.py` for Python comments, docstrings, and prose-oriented
  strings.
- Added a diagnostic-only `topmark-probe` pre-commit hook.
- Refreshed dependencies and pre-commit hooks, including removing an obsolete Pyright ignore after
  improved `tomlkit` typing.

### Added - 1.0.0b4

- **GitHub prerelease publication**

  - Updated the release workflow so prerelease tags create GitHub prereleases.
  - Kept package publishing policy unchanged:
    - prerelease artifacts continue to publish to TestPyPI;
    - final release artifacts publish to PyPI.
  - Documented GitHub prereleases as the public release-note and traceability surface for prerelease
    milestones.

- **Python prose hygiene tooling**

  - Added `tools/docs/check_code_hygiene.py`.
  - Added token-based checks for Python comments, docstrings, and prose-oriented string literals.
  - Added smart-punctuation diagnostics for Unicode dashes, curly quotes, and ellipses.
  - Wired code hygiene into nox, Makefile, verification, and release validation paths.

- **Shared terminology note**

  - Added `_snippets/terminology.md` as the shared terminology cross-reference note.
  - Reused the snippet across command, usage, API, CI, configuration, and developer documentation.

- **Pre-commit probe hook**

  - Added a manual `topmark-probe` pre-commit hook for read-only file-type and processor resolution
    diagnostics.
  - Documented manual invocation, recommended arguments, verbosity/output-format usage, and
    pre-commit exit-code behavior.

- **Changelog hygiene validation**

  - Added `CHANGELOG.md`-specific hygiene checks for:
    - release heading shape;
    - release section heading shape;
    - allowed section names;
    - disallowed heading depth.
  - Documented strict changelog heading and section conventions.

### Changed - 1.0.0b4

- **Release workflow and prerelease visibility**

  - Changed the GitHub release job so it runs for prerelease tags as well as final tags.
  - Marked alpha, beta, and release-candidate GitHub releases as prereleases automatically.
  - Kept final tags published as normal GitHub releases.
  - Updated release workflow documentation to describe prerelease GitHub Release creation,
    permissions, trust boundaries, and release visibility policy.

- **Runtime type naming**

  - Renamed core mutable/immutable runtime support types to align with the finalized naming model.
  - Updated source, tests, public API references, generated API documentation, user docs, and
    developer docs.
  - Normalized prose so "frozen" refers primarily to release-contract stabilization unless naming a
    concrete `FrozenX` type.

- **Documentation terminology**

  - Normalized terminology across developer, usage, API, CI, configuration, and command
    documentation.
  - Standardized wording for:
    - effective runtime configuration;
    - layered configuration;
    - staged configuration-loading validation;
    - runtime policy evaluation;
    - runtime resolution;
    - processor bindings;
    - canonical qualified identifiers;
    - machine-readable output;
    - semantic outcomes;
    - TEXT-oriented human-readable output;
    - public/internal API boundaries.
  - configuration schema terminology and staged validation wording across developer and command
    documentation.

- **Command documentation**

  - Finalized command-page wording and structure across:
    - `topmark check`;
    - `topmark strip`;
    - `topmark probe`;
    - `topmark version`;
    - `topmark config` and subcommands;
    - `topmark registry` and subcommands.
  - Replaced repeated terminology paragraphs with the shared terminology snippet.
  - Clarified user-facing implementation boundaries so command pages avoid internal dataclass names,
    `freeze()` / `thaw()` mechanics, internal DTO names, and helper/bridge implementation details.

- **TOML starter template**

  - Harmonized `topmark-example.toml` with a mature reference-template style.
  - Clarified configuration discovery, precedence, TOML-source-local settings, writer options,
    runtime policy behavior, and file-selection comments.
  - Normalized ASCII punctuation and reduced implementation-specific wording.

- **Documentation hygiene**

  - Extended Markdown hygiene checks to report smart punctuation in documentation prose.
  - Reworked emoji/decorative-symbol checks to use dependency-free Unicode range checks.
  - Updated snippet guidance for `mkdocs-include-markdown-plugin` relative-link rewriting.
  - Updated documentation conventions and documentation pipeline guidance for separate Markdown and
    Python prose hygiene validation.

- **Dependency and tooling maintenance**

  - Refreshed dependencies and pre-commit hook revisions.
  - Updated indirect dependencies including `urllib3`, `nox-uv`, and `hypothesis`.
  - Removed an obsolete Pyright ignore after improved `tomlkit` typing.

### Fixed - 1.0.0b4

- **Published artifact validation closure**

  - Confirmed the `v1.0.0b3` artifacts validate successfully on Windows, macOS, and Ubuntu.
  - Updated roadmap wording to record cross-platform published-artifact validation success through
    the `v1.0.0b3` stabilization release.
  - Clarified that remaining pre-1.0 work is now limited to release-candidate validation, packaging
    checks, and concrete final beta feedback.

- **GitHub prerelease history**

  - Backfilled GitHub prereleases for `v1.0.0b1` and `v1.0.0b2` from their existing tags.
  - Used concise GitHub release-note bodies that summarize each beta milestone and point to
    `CHANGELOG.md` for full release notes.
  - Avoided backfilling the full alpha series to keep prerelease history focused and readable.

- **Documentation terminology drift**

  - Fixed stale references to "effective merged configuration" in CLI help text, command examples,
    and source docstrings.
  - Fixed remaining `config-loading/preflight validation` wording.
  - Fixed remaining `resolver` wording where the intended concept is runtime resolution.
  - Fixed inconsistent TEXT-only vs TEXT-oriented wording.

- **Changelog structure drift**

  - Normalized historical `CHANGELOG.md` headings to use plain hyphen separators.
  - Moved historical non-whitelisted release subsections under approved Keep-a-Changelog-compatible
    headings.
  - Fixed changelog heading validation gaps that allowed deeper or inconsistent release headings.
  - Fixed inconsistent changelog section naming and separator usage by enforcing canonical
    Keep-a-Changelog-compatible level-3 section headings.

- **Documentation and code punctuation drift**

  - Replaced smart punctuation in Markdown documentation prose.
  - Replaced smart punctuation in source comments, docstrings, tests, helper docstrings, and
    generated-doc tooling prose.
  - Kept runtime behavior unchanged while making code-facing prose ASCII-clean.

- **Navigation and reference drift**

  - Fixed broken MkDocs navigation after introducing and moving the terminology page.
  - Updated links after renaming `docs/dev/config-schema.md` to `docs/dev/configuration-schema.md`.
  - Updated internal references after promoting the glossary to `docs/terminology.md`.

### Documentation - 1.0.0b4

- Updated release workflow documentation to explain GitHub prerelease creation for prerelease tags.
- Updated published-artifact validation and roadmap documentation to reflect successful
  cross-platform validation after `v1.0.0b3`.
- Added concise GitHub prerelease notes for backfilled `v1.0.0b1` and `v1.0.0b2` releases.
- Added and promoted `docs/terminology.md` as the canonical project-wide terminology reference.
- Renamed `docs/dev/config-schema.md` to `docs/dev/configuration-schema.md` and aligned related
  developer documentation references and navigation.
- Updated documentation conventions with:
  - changelog heading rules;
  - command-page implementation-boundary guidance;
  - snippet-link behavior;
  - smart-punctuation guidance;
  - Python code-prose hygiene guidance.
- Updated documentation pipeline guidance to distinguish Markdown documentation hygiene from Python
  code-prose hygiene.
- Updated roadmap status to reflect:
  - completed command documentation consistency review;
  - terminology glossary promotion;
  - shared terminology snippet adoption;
  - TOML template polish;
  - Markdown and Python prose hygiene validation;
  - late-beta contract stabilization status.
- Updated pre-commit documentation for the new diagnostic `topmark-probe` hook.
- Updated configuration, API, usage, CI, registry, command, and developer documentation for the
  finalized terminology model.

### Internal - 1.0.0b4

- Preserved the artifact-based release split while extending GitHub Release creation to prerelease
  tags.
- Kept prerelease package publication on TestPyPI while making prerelease milestones visible on
  GitHub.
- Completed canonical mutable/immutable naming across configuration, policy, diagnostics, and staged
  validation logs.
- Updated public API snapshots, tests, helpers, machine schemas, serializers, presentation code, and
  pipeline internals for renamed types.
- Improved `tools/docs/check_docs_hygiene.py` typing and diagnostics.
- Raised the minimum supported `tomlkit` version to `0.15.0` to rely on improved typing support for
  `tomlkit.dumps()` without retaining Pyright suppression comments.
- Added code-prose hygiene validation as a separate tool rather than expanding Markdown hygiene into
  a mixed-purpose checker.
- Preserved runtime behavior while normalizing comments, docstrings, and prose-oriented strings.
- Simplified Click option kwargs typing in `topmark.cli.options._ClickOptionKwargs` after updating
  Click.

### Notes - 1.0.0b4

- The beta prerelease series now has coherent GitHub release history from `v1.0.0b1` through
  `v1.0.0b4`.
- This beta does not introduce new user-facing CLI behavior or new machine-readable output payload
  semantics.
- Frozen 1.0 contracts for CLI behavior, config semantics, probe, registry/resolution,
  machine-readable output, and pipeline execution remain unchanged.
- This release does include public/runtime type renames for the canonical `MutableX` / `FrozenX`
  naming model.
- The main focus is terminology finalization, documentation consistency, prose hygiene, and release
  readiness before the release-candidate phase.
- Remaining work before `1.0.0rc1` should be limited to validation runs, packaging checks, published
  artifact validation, and any concrete final beta feedback.

______________________________________________________________________

## [1.0.0b3] - 2026-05-11

This third **1.0 beta release** focuses on CI/workflow documentation harmonization,
documentation-governance hardening, published-artifact validation, and Windows portability fixes
ahead of the `1.0.0rc1` release candidate.

It does not reopen frozen CLI, API, configuration, registry, probe, machine-readable output, or
pipeline contracts. Instead, it strengthens the documentation, workflow, release, and validation
surfaces around those contracts by standardizing workflow documentation, expanding documentation
hygiene checks, clarifying release responsibilities, improving contributor-facing navigation, and
hardening published-artifact validation across platforms.

It also fixes a Windows-only atomic writer failure discovered by the published-artifact validation
workflow after `1.0.0b2`. On Windows, `topmark check --apply` could fail with `PIPELINE_ERROR (70)`
because the atomic writer called POSIX-only APIs such as `os.fchmod()`.

> [!CAUTION] **Breaking changes**
>
> - Markdown headings across repository and generated documentation are now intentionally
>   emoji-free.
> - `make docs-hygiene` now validates MkDocs navigation membership and rejects emoji in headings.
> - CI and workflow documentation structure was standardized across all documented workflows.

### Breaking Changes - 1.0.0b3

- **Documentation governance and heading policy**

  - Markdown headings and navigation labels are now standardized as plain, emoji-free text.
  - Changelog breaking-change entries now use GitHub `[!CAUTION]` callouts followed by plain,
    anchor-friendly level-3 headings.
  - `make docs-hygiene` now rejects emoji in Markdown headings and validates that Markdown files
    under `docs/` are represented in the MkDocs navigation.

- **Workflow documentation structure**

  - CI workflow documentation now follows a shared page structure covering purpose, trigger
    conditions, permissions/trust boundaries, validation scope, artifact handling, local
    reproduction, maintenance notes, and related pages.
  - Documentation contributors should follow the standardized workflow-page structure for future
    workflow documentation.

### Highlights - 1.0.0b3

- Fixed Windows atomic writer portability by avoiding unconditional use of POSIX-only `os.fchmod()`
  and `os.O_DIRECTORY`.
- Added configurable platform, Python-version, and TopMark runtime-log-level controls to the
  published-artifact validation workflow.
- Added focused Windows diagnostics to published-artifact validation for investigating installed
  package failures.
- Added a GitHub Action pin-audit workflow and offline audit tool for detecting diverging action
  pins across workflows and local composite actions.
- Standardized CI workflow documentation across CI, release, published-artifact validation,
  Dependabot, and action-pin-audit pages.
- Renamed `docs/ci/dev-validation.md` to `docs/ci/test-validation.md` and expanded it into a broader
  validation and pytest-marker taxonomy page.
- Extracted detailed maintainer release guidance into `docs/dev/release-process.md`.
- Reorganized documentation conventions and documentation-pipeline guidance around current
  documentation hygiene, reuse, snippet, heading, and workflow conventions.
- Expanded `tools/docs/check_docs_hygiene.py` to validate emoji-free headings, MkDocs navigation
  membership, top-level Markdown files, nested snippets, and related-pages snippet exceptions.
- Improved README, CONTRIBUTING, changelog, and API-stability documentation discoverability.

### Added - 1.0.0b3

- **GitHub Action pin audit**

  - Added `.github/workflows/action-pin-audit.yml` as a scheduled, manual, and pull-request based
    maintenance workflow for auditing GitHub Action pin consistency.
  - Added `tools/ci/audit_action_pins.py` as an offline static-analysis tool for scanning workflow
    files and local composite actions.
  - Added optional action-pin audit reports for:
    - summary reporting;
    - per-file reporting;
    - version-count reporting;
    - file-count reporting.

- **Published artifact validation controls**

  - Added manual workflow inputs to `.github/workflows/published-artifact-validation.yml` for:
    - selecting all platforms or a single platform;
    - selecting all supported Python versions or one specific Python version;
    - selecting optional TopMark runtime logging (`TRACE`, `DEBUG`, `INFO`, `WARNING`, `ERROR`) or
      leaving runtime logging disabled.
  - Added dynamic matrix generation so targeted platform/interpreter combinations can be rerun
    without executing the full validation matrix.
  - Added Windows-only diagnostic steps for inspecting validation workspace contents and check
    machine output when investigating platform-specific failures.

- **Release-process documentation**

  - Added `docs/dev/release-process.md` as the canonical maintainer release-process page.
  - Documented release philosophy, versioning, tag forms, TestPyPI/PyPI routing, artifact handoff,
    prerelease/final release flow, published artifact validation, and recovery notes.

- **CI documentation family**

  - Added `docs/ci/index.md` as the CI and validation overview page.
  - Added `docs/ci/action-pin-audit.md` for the new action-pin audit workflow and tool.
  - Added `docs/_snippets/ci/related-pages.md` as the shared related-pages block for CI workflow
    documentation pages.

### Changed - 1.0.0b3

- **Published artifact validation workflow**

  - Renamed the workflow job and temporary workspace terminology from smoke testing to validation.
  - Added explicit UTF-8 environment handling for deterministic cross-platform behavior.
  - Expanded installed-package validation to exercise both dry-run and mutating forms of
    `topmark check` and `topmark strip`.
  - Split CLI validation into focused read-only, check-apply, check-idempotence, strip-apply, and
    strip-idempotence steps for easier platform-specific diagnosis.
  - Replaced heredoc-based validation file creation with deterministic `printf` output.
  - Centralized `TOPMARK_LOG_LEVEL` handling at job scope and made runtime logging opt-in through a
    workflow input instead of hardcoding Windows `DEBUG` logging.

- **CI and validation documentation**

  - Renamed `docs/ci/dev-validation.md` to `docs/ci/test-validation.md`.
  - Expanded the validation documentation to cover pytest markers, validation layering, nox
    integration, CI inclusion/exclusion semantics, and local validation workflows.
  - Updated MkDocs navigation and cross-references for the renamed validation page.

- **Workflow documentation harmonization**

  - Standardized the structure and terminology of:
    - `docs/ci/ci-workflow.md`;
    - `docs/ci/release-workflow.md`;
    - `docs/ci/published-artifact-validation.md`;
    - `docs/ci/dependabot.md`;
    - `docs/ci/action-pin-audit.md`.
  - Documented workflow trigger models, trust boundaries, validation scope, artifact handling, local
    reproduction, and maintenance expectations consistently across workflow pages.

- **Atomic writer portability**

  - Updated `AtomicFileSink` to treat POSIX durability and permission helpers as optional platform
    capabilities.
  - Preserved POSIX behavior by using file-descriptor permission updates and directory `fsync()`
    when available.
  - Documented the Windows deviation where path-based `chmod()` is used as a best-effort fallback
    and directory `fsync()` is skipped.

- **Documentation conventions and pipeline guidance**

  - Reorganized `docs/dev/documentation-conventions.md` around documentation surfaces, page
    structure, navigation, links, callouts, command/workflow templates, docstrings, snippets,
    generated docs, validation, reuse, and stability expectations.
  - Updated `docs/dev/documentation-pipeline.md` to focus on documentation generation and validation
    tooling while delegating authoring rules to the conventions page.
  - Moved public API exception-docstring guidance into the documentation conventions page.

- **Documentation hygiene tooling**

  - Expanded `tools/docs/check_docs_hygiene.py` to scan documentation sources and top-level Markdown
    files.
  - Added emoji-in-heading rejection and MkDocs navigation membership validation.
  - Added nested snippet discovery and related-pages snippet exceptions for reusable navigation
    snippets named `related-pages*.md`.
  - Improved typing, constants, path handling, and hygiene statistics.

- **Repository-facing documentation**

  - Updated `README.md` for clearer project discovery, hosted-documentation links, public API
    examples, release references, and CI/validation navigation.
  - Fixed README API links by pointing separately to the hosted public API page and generated
    internal API reference.
  - Updated `CONTRIBUTING.md` for clearer local environment, nox, documentation, release, and pull
    request guidance.
  - Updated `docs/contributing.md` to summarize release guidance and point to the canonical release
    process.

- **Changelog formatting**

  - Replaced emoji-based breaking-change headings with plain level-3 headings.
  - Added standardized `[!CAUTION] **Breaking changes**` summaries before detailed breaking-change
    sections.
  - Preserved Keep-a-Changelog-compatible level-3 release section headings.

- **API stability documentation**

  - Improved `docs/dev/api-stability.md` with clearer scope, stability boundaries, relationships to
    machine-readable output, CI validation, and release/versioning semantics.

### Fixed - 1.0.0b3

- **Windows atomic writer failure**

  - Fixed `AtomicFileSink` calling `os.fchmod()` unconditionally on Windows, where the API is not
    available.
  - Fixed published-artifact validation failure where `topmark check --apply README.md --no-color`
    reported `no changes to apply` but exited with `PIPELINE_ERROR (70)` after the underlying
    `AttributeError: module 'os' has no attribute 'fchmod'`.
  - Added best-effort fallback behavior that applies permissions to the temporary path when
    file-descriptor permission updates are unavailable.
  - Guarded directory `fsync()` behind `os.O_DIRECTORY` availability so Windows skips the POSIX-only
    durability step cleanly.

- **Published artifact validation diagnostics**

  - Fixed the workflow's initial installed-package validation sequence so default configuration is
    tested against a deterministic validation workspace rather than repository-specific TopMark
    header policy.
  - Improved workflow failure localization by separating check and strip lifecycle phases into
    independent steps.
  - Added opt-in runtime logging and targeted matrix selection to make platform-specific failures
    reproducible without running the entire matrix.

- **Documentation drift and discoverability**

  - Fixed stale or inconsistent references across CI, release, validation, README, contributing, and
    developer documentation.
  - Fixed outdated release-process details duplicated in contributor-facing files by moving detailed
    maintainer guidance to `docs/dev/release-process.md`.
  - Fixed inconsistent workflow-documentation headings and section ordering.
  - Fixed README hosted API links that referenced a non-existent top-level API page.

- **Documentation hygiene coverage**

  - Fixed documentation hygiene gaps where top-level Markdown files, nested snippets, emoji
    headings, and MkDocs nav membership were not validated.
  - Fixed the reusable CI related-pages snippet warning by explicitly allowing relative links in
    navigation snippets.

### Documentation - 1.0.0b3

- Added and updated CI documentation pages for workflow responsibilities, trigger semantics,
  validation scope, release boundaries, dependency automation, published artifact validation, and
  action-pin auditing.
- Added maintainer release-process documentation and reduced release-process duplication in
  repository-facing contributor docs.
- Updated documentation conventions to formalize:
  - emoji-free headings;
  - GitHub alert callouts;
  - hosted-doc link labeling;
  - command and workflow page templates;
  - snippet governance;
  - documentation reuse and duplication policy;
  - docs hygiene validation expectations.
- Updated documentation pipeline and API stability pages for clearer cross-page navigation and
  validation context.
- Updated changelog formatting for stable, anchor-friendly breaking-change sections.
- Updated published-artifact validation documentation for the renamed validation terminology,
  configurable platform/Python/log-level controls, Windows diagnostics, and check/strip validation
  lifecycle.

### Internal - 1.0.0b3

- **Composite-action governance clarification**

  - Clarified the rationale for retaining some duplicated workflow setup logic after moving away
    from direct shared composite-action reuse for security-boundary reasons.
  - Added the action-pin audit to detect version drift between workflow files and local composite
    actions that Dependabot may not update consistently.

- **Documentation reuse policy**

  - Formalized that snippets should remain semantic and lightweight.
  - Documented that broad prose reuse is discouraged.
  - Accepted related-pages navigation snippets for tightly coupled documentation families.
  - Clarified that limited duplication is acceptable when it improves discoverability, onboarding,
    and local readability.

- **Published artifact validation diagnostics**

  - Added workflow controls that allow maintainers to rerun a single platform and Python version
    with elevated runtime logging when investigating published-package behavior.
  - Kept runtime logging disabled by default so normal validation output remains concise.

### Notes - 1.0.0b3

- This beta does not introduce new user-facing CLI/API features.
- Frozen 1.0 contracts for CLI behavior, config semantics, probe, registry/resolution,
  machine-readable output, and public API remain unchanged.
- The focus is CI/workflow documentation consistency, release-process discoverability,
  documentation-governance hardening, validation-tooling coverage, and Windows published-artifact
  validation fixes.
- The Windows `os.fchmod` failure discovered in `1.0.0b2` is fixed by making atomic writer
  permission and durability handling platform-aware.
- Current validation status is clean for Ruff, Pyright, documentation links, and `make verify`.
- Remaining work before `1.0.0rc1` should be limited to release validation, packaging checks,
  published artifact validation, and any final beta feedback fixes.

______________________________________________________________________

## [1.0.0b2] - 2026-05-10

This second **1.0 beta release** focuses on documentation UX, documentation governance, generated
site maintainability, and release-validation tooling. It does not reopen frozen CLI, API,
configuration, registry, probe, machine-readable output, or pipeline contracts. Instead, it
strengthens the documentation system around those contracts by standardizing page structure,
improving navigation, reducing snippet overuse, and adding lightweight documentation hygiene
validation to the normal verification and release gates.

### Highlights - 1.0.0b2

- Established canonical documentation conventions for TopMark's 1.0 documentation system
- Harmonized command-page structure across pipeline, config, registry, version, and shared-option
  documentation
- Improved MkDocs navigation, generated API navigation, sidebar density, and overview-page
  discoverability
- Refined snippet governance and removed over-broad reusable snippets in favor of canonical
  reference pages
- Added lightweight documentation hygiene validation and integrated it into nox, Makefile, verify,
  and release validation flows
- Expanded registry model documentation around runtime registry composition, overlays, bindings, and
  public/internal registry boundaries
- Updated roadmap status to reflect post-beta documentation governance and release-readiness status

### Added - 1.0.0b2

- **Documentation conventions**
  - Added `docs/dev/documentation-conventions.md` as the canonical guide for documentation
    structure, navigation, command-page layout, snippet governance, cross-references, generated
    docs, emoji usage, and validation expectations.
  - Added explicit conventions for:
    - command documentation structure
    - related-command and related-doc sections
    - sidebar and table-of-contents density
    - generated API navigation
    - snippet extraction and retirement criteria
    - accepted duplication vs over-abstraction
- **Documentation hygiene tooling**
  - Added `tools/docs/check_docs_hygiene.py`.
  - Added validation for:
    - broken snippet include paths
    - malformed docs-root-relative include paths
    - include targets resolving outside `docs/`
    - nested snippet includes
    - accidental macOS `._*` files
    - missing horizontal-rule separators before level-2 sections
  - Added non-fatal maintainability warnings for:
    - orphaned snippets
    - headings inside snippets
    - relative links inside snippets
    - snippet includes missing the formatter-stable `_snippets/` prefix
- **Tooling integration**
  - Added a `docs_hygiene` nox session.
  - Added `make docs-hygiene`.
  - Integrated docs hygiene checks into `verify`, `release-check`, and `release-full`.

### Changed - 1.0.0b2

- **Documentation navigation and site UX**
  - Improved MkDocs navigation discoverability.
  - Reduced sidebar density for command and generated API documentation.
  - Simplified generated API internals navigation so nested internals remain discoverable through
    package indexes, breadcrumbs, links, and search instead of exhaustive sidebar entries.
  - Refined Usage navigation labels and command grouping.
  - Improved overview pages with compact task-oriented navigation tables.
- **Command documentation**
  - Harmonized structure and terminology across:
    - `check`
    - `strip`
    - `probe`
    - `version`
    - `config` and its subcommands
    - `registry` and its subcommands
    - shared options
  - Standardized placement and wording for:
    - summary
    - quick start
    - input applicability
    - configuration and validation
    - filtering and discovery
    - behavior details
    - output behavior
    - machine-readable output
    - command-specific options
    - exit codes
    - related commands
    - related docs
    - troubleshooting
  - Clarified distinctions between:
    - output behavior
    - machine-readable output
    - machine-readable formats
    - machine-readable contracts
- **Snippet governance**
  - Retired over-broad or over-abstracted snippets.
  - Centralized canonical STDIN, filtering, and configuration-resolution explanations into stable
    reference pages.
  - Shortened the reusable file-type identifier snippet and linked consumers to the canonical
    filtering guide.
  - Removed retired snippet files such as broad config-resolution, config-validation-contract,
    no-stdin-option, and file-discovery-pattern snippets.
- **Registry documentation**
  - Expanded `docs/dev/registry-model.md`.
  - Clarified:
    - runtime registry composition
    - overlay semantics
    - cache invalidation behavior
    - registry facade responsibilities
    - advanced/internal registry APIs
    - relationships between file types, processors, bindings, and runtime composition
- **Documentation pipeline**
  - Updated `docs/dev/documentation-pipeline.md` to document docs hygiene validation.
  - Documented fatal vs non-fatal hygiene checks.
  - Documented snippet/include validation and section-separator validation.
- **Dependency/tooling maintenance**
  - Updated the TopMark pre-commit hook to `v1.0.0b1`.
  - Updated locked dependency versions for `uv` and `build`.

### Fixed - 1.0.0b2

- **Documentation drift and navigation density**
  - Fixed inconsistent command-page structure across command families.
  - Fixed stale or duplicated cross-reference patterns in command docs.
  - Fixed overly dense generated API navigation.
  - Fixed inconsistent terminology around command pages, shared options, machine-readable output,
    and generated references.
- **Snippet and include hygiene**
  - Fixed file-type identifier alert syntax.
  - Removed retired snippets after moving their content into canonical reference pages.
  - Added tooling to catch broken, nested, or unsafe snippet includes before release.
- **Documentation validation coverage**
  - Replaced the previous docstring-link-only validation entry point with broader documentation
    hygiene validation.
  - Ensured documentation structure issues are checked as part of release validation.

### Documentation - 1.0.0b2

- Added the documentation conventions guide.
- Updated command, shared-option, filtering, registry, configuration, architecture, machine-readable
  output, documentation-pipeline, and developer documentation for consistent structure and wording.
- Updated `mkdocs.yml` navigation for improved discoverability.
- Updated documentation overview pages and CLI overview pages for task-oriented navigation.
- Updated roadmap status to record completed documentation governance, documentation validation, and
  post-beta readiness work.

### Notes - 1.0.0b2

- This beta does not introduce new user-facing CLI/API features.
- Frozen 1.0 contracts for CLI behavior, config semantics, probe, registry/resolution,
  machine-readable output, and public API remain unchanged.
- The focus is documentation maturity, validation tooling, and release-readiness hardening.
- Documentation hygiene validation is now part of the normal verification and release flow.
- Remaining work before `1.0.0rc1` should be limited to release validation, packaging checks, and
  beta feedback fixes.

______________________________________________________________________

## [1.0.0b1] - 2026-05-09

This first **1.0 beta release** marks the transition from alpha contract stabilization to beta
validation for TopMark's 1.0 release line.

It completes the final documentation consistency, generated-site, CLI/help, alpha-semantics,
warning/error wording, and machine-readable output freeze review. It also fixes the remaining
config/runtime boundary issue where TOML-authored runtime sections such as `[writer]` could be
accepted and applied at runtime but omitted from config output snapshots.

The beta is intended for final validation of the already-frozen 1.0 contracts rather than for new
feature exploration. Post-1.0 deferrals such as in-memory pipeline support, Rich / `rich-click`
migration, staged diagnostic schema expansion, registry query commands, and config schema versioning
remain deferred.

> [!CAUTION] **Breaking changes**
>
> - Config machine-readable payloads now include TOML-authored runtime sections such as `[writer]`
> - Synthetic config provenance is now typed and rendered as stable labels.
> - `config init` machine-readable output now represents the bundled starter template.
> - CLI and documentation terminology was finalized for shared options and machine-readable output

### Breaking Changes - 1.0.0b1

- **Config machine-readable payloads now include TOML-authored runtime sections such as
  `[writer]`.**

  - `topmark config dump`, `topmark config check`, `topmark config defaults`, and
    `topmark config init` machine-readable config snapshots may now include:

    ```json
    "writer": {
      "strategy": "atomic"
    }
    ```

  - Consumers that assumed the `config` payload contained only layered `Config` fields must allow
    runtime-facing TOML sections that are resolved outside the layered config model.

- **Synthetic config provenance is now typed and rendered as stable labels.**

  - Built-in and bundled config sources now render as labels such as:
    - `<defaults>`
    - `<built-in topmark defaults>`
    - `<bundled topmark-template.toml>`
  - These labels are no longer accidentally normalized into absolute filesystem-looking paths.
  - Consumers of `config.files.config_files` should treat these values as provenance identifiers,
    not guaranteed filesystem paths.

- **`config init` machine-readable output now represents the bundled starter template.**

  - Earlier alpha behavior used a shortcut based on built-in `Config` defaults.
  - `json` and `ndjson` output for `topmark config init` is now produced by parsing and resolving
    the bundled starter template, preserving template semantics while omitting comments and
    formatting.

- **CLI and documentation terminology was finalized for shared options and machine-readable
  output.**

  - Documentation and help text now consistently prefer "shared options" over the older "global
    options" wording.
  - User-facing prose now consistently uses "machine-readable output" / "machine-readable formats"
    while retaining "machine-output contract/schema" where referring to formal internal contracts.
  - Downstream tests that assert exact help text or documentation snippets may need updating.

### Highlights - 1.0.0b1

- Completed the final beta freeze review for CLI help, docs, generated site, alpha semantics,
  warnings/errors, and machine-readable output wording
- Preserved `[writer]` and other TOML-authored runtime sections in config output snapshots
- Introduced typed synthetic config provenance for bundled, built-in, CLI/API, and other
  non-filesystem config sources
- Aligned `config defaults` and `config init` semantics across text, Markdown, JSON, and NDJSON
- Clarified canonical built-in defaults vs bundled starter-template behavior
- Removed remaining transitional CLI-state scaffolding and finalized typed CLI state behavior
- Centralized enum-value help rendering for CLI options with canonical underscore values and
  CLI-facing hyphen aliases
- Added reusable documentation for CLI option spelling vs TOML/API/machine-readable value spelling
- Renamed the former global-options documentation to shared-options documentation
- Harmonized machine-readable output terminology across docs, source docstrings, and tests
- Updated the roadmap to mark the `v1.0.0b1` beta freeze review complete

### Added - 1.0.0b1

- **Typed synthetic config provenance**

  - Added a `SyntheticConfigSource` value object for non-filesystem config sources.
  - Added stable synthetic provenance markers for:
    - built-in defaults
    - bundled starter template
    - defaults layer
    - CLI/API override layers
  - Preserved typed provenance through config resolution and merge layers until presentation or
    serialization boundaries.

- **Default/template TOML resolution helpers**

  - Added bridge helpers that resolve:
    - the canonical built-in default TOML table
    - the bundled starter template TOML resource
  - These helpers feed the same TOML loading and config-draft construction path used by normal
    config sources.

- **Option spelling documentation**

  - Added a reusable documentation snippet explaining:
    - hyphenated CLI option names
    - CLI value aliases using hyphens or underscores
    - canonical underscore values for TOML, Python API values, and machine-readable output

- **Regression coverage**

  - Added tests proving that TOML writer options reach CLI runtime option assembly.
  - Added tests proving that explicit CLI `--write-mode` overrides TOML writer options.
  - Added tests proving the bundled starter template and built-in default TOML table resolve without
    error diagnostics.
  - Added tests for typed synthetic provenance preservation and config model export behavior.

### Changed - 1.0.0b1

- **Config output snapshots**

  - `ConfigPayload` now includes a `writer` section when writer options are present in the effective
    TOML source.
  - Human config reports now render effective TOML by composing layered `Config` entries with
    TOML-authored runtime sections such as `[writer]`.
  - Machine-readable config serializers now receive the resolved TOML context so they can include
    TOML-authored runtime sections consistently.

- **`config defaults` semantics**

  - Text and Markdown output continue to render the canonical, comment-free built-in default TOML
    document.
  - JSON and NDJSON output now derive from the canonical built-in default TOML table through the
    TOML loading and resolution pipeline.
  - Runtime-facing TOML sections such as `[writer]` are included when present in the canonical
    defaults.

- **`config init` semantics**

  - Text and Markdown output continue to render the bundled commented starter template.
  - JSON and NDJSON output now parse and resolve the bundled starter template instead of using a
    built-in `Config` defaults shortcut.
  - Machine-readable output now reflects the bundled template semantics while omitting comments and
    formatting.

- **CLI state and validators**

  - Removed the remaining generic CLI-state `extras` mapping and dict-like mutation behavior.
  - Replaced the remaining hidden writer-options handoff with typed CLI state.
  - Updated validator state mutation to use explicit typed-state handling instead of generic key
    assignment.

- **CLI help and option wording**

  - Centralized enum-value help text rendering for CLI options.
  - Standardized CLI examples around hyphenated values while preserving canonical underscore values
    for TOML/API/machine-readable surfaces.
  - Added explicit wording that CLI option names use hyphens and that underscored option names are
    rejected with suggestions.

- **Documentation terminology**

  - Renamed the former global-options usage page to shared-options documentation.
  - Updated CLI overview, command pages, configuration docs, policy docs, developer docs, README,
    source docstrings, and tests for consistent terminology.
  - Clarified that "machine-readable output" is the preferred user-facing term, while
    "machine-output contract/schema" remains appropriate for formal schema references.

### Fixed - 1.0.0b1

- **Missing `[writer]` in config output snapshots**

  - Fixed `config dump` and `config check` output omitting TOML-authored runtime writer options even
    when they were accepted, validated, and applied at runtime.
  - Fixed `config defaults` and `config init` machine-readable output omitting writer defaults by
    shortcutting directly to `Config` defaults.

- **Synthetic source path normalization**

  - Fixed built-in and bundled config provenance being rendered as filesystem-looking absolute paths
    such as `/current/working/directory/<built-in topmark defaults>`.
  - Synthetic config sources now remain typed through resolution and render as stable provenance
    labels only at output boundaries.

- **`config init` machine-readable semantic drift**

  - Fixed mismatch where text output represented the bundled starter template but JSON/NDJSON output
    represented only built-in config defaults.

- **CLI state transitional wording and behavior**

  - Removed stale transitional CLI-state wording and generic dict-style state mutation.
  - Made the remaining validator state-clearing behavior explicit and typed.

- **Documentation drift**

  - Fixed stale references to built-in layered defaults where the docs now refer to canonical
    built-in default TOML documents.
  - Fixed stale "global options" wording where the finalized CLI model uses shared options.
  - Fixed machine-readable terminology drift across command docs, machine-format docs, generated
    API-facing docstrings, and tests.

### Documentation - 1.0.0b1

- Completed the documentation consistency and generated-site freeze review.
- Updated CLI usage docs for `config defaults`, `config init`, shared options, option spelling,
  policy values, and machine-readable output semantics.
- Updated developer documentation for config/runtime separation, machine-readable output, synthetic
  provenance, generated-site expectations, and the beta readiness gate.
- Updated roadmap status to record the completed final beta freeze review and accepted post-1.0
  deferrals.
- Kept historical alpha release notes unchanged except where current documentation surfaces needed
  beta-facing clarification.

### Notes - 1.0.0b1

- This is the first beta release in the 1.0 line.
- The beta focuses on validation of frozen contracts, not broad new feature development.
- Runtime-facing TOML sections such as `[writer]` remain outside layered `Config`; they are resolved
  from TOML and preserved in config output snapshots.
- `config defaults` and `config init` intentionally use different sources:
  - `config defaults` uses the canonical built-in default TOML table.
  - `config init` uses the bundled starter template resource.
- Synthetic config provenance labels are user-facing provenance identifiers, not filesystem paths.
- In-memory pipeline support, Rich / `rich-click` migration, richer staged diagnostic machine
  schemas, registry query commands, ProperDocs evaluation, and explicit TOML schema versioning
  remain deferred beyond the beta.

______________________________________________________________________

## [1.0.0a13] - 2026-05-07

This thirteenth **1.0 alpha release** finalizes TopMark's TOML strictness naming and closes the
explicit schema-versioning decision for the 1.0 configuration contract.

It renames the alpha-cycle `[config].strict_config_checking` setting to `[config].strict`, updates
machine-output naming accordingly, and documents the decision not to add an explicit TOML schema
version key for 1.0. Explicit configuration schema versioning remains deferred until a future
non-additive schema change requires it.

> [!CAUTION] **Breaking changes**
>
> - The alpha-only TOML setting `[config].strict_config_checking` has been renamed to
>   `[config].strict`.
> - The `config check` machine-output payload now emits `strict` instead of
>   `strict_config_checking`.

### Breaking Changes - 1.0.0a13

- The alpha-only TOML setting `[config].strict_config_checking` has been renamed to
  `[config].strict`.
  - No compatibility alias is provided because `strict_config_checking` existed only during the 1.0
    alpha cycle.
  - Configuration files created against earlier 1.0 alpha releases must rename the key before using
    `1.0.0a13` or later.
- The `config check` machine-output payload now emits `strict` instead of `strict_config_checking`.
  - Consumers of alpha config-check JSON/NDJSON output must update their parsers.

### Highlights - 1.0.0a13

- Renamed `[config].strict_config_checking` to `[config].strict`
- Updated config-check machine-output naming from `strict_config_checking` to `strict`
- Added reusable documentation for `[config].strict`
- Clarified strictness semantics across user, API, developer, and machine-output documentation
- Decided to defer explicit TOML schema versioning beyond 1.0 until it is actually needed
- Updated roadmap status for the completed strictness rename and schema-versioning decision

### Changed - 1.0.0a13

- **TOML strictness key**

  - Renamed the source-local strictness key:
    - old alpha key: `[config].strict_config_checking`
    - new 1.0 key: `[config].strict`
  - Standardized code, tests, examples, and documentation on the shorter `strict` terminology.
  - Clarified that `[config].strict` is a source-local strictness preference for staged
    configuration, resolution, and runtime-applicability diagnostics.

- **Machine output**

  - Renamed the config-check machine payload field from `strict_config_checking` to `strict`.
  - Updated machine-output tests to assert the finalized pre-1.0 key name.

- **Configuration schema-versioning decision**

  - Decided not to add a `[config].version` or equivalent schema-version key for 1.0.
  - Deferred explicit TOML schema versioning until a future non-additive schema change requires it.
  - Updated the roadmap to mark this decision as complete for the 1.0 freeze.

### Documentation - 1.0.0a13

- Added `_snippets/config-strictness.md` for consistent `[config].strict` wording.
- Updated README, configuration docs, command pages, API docs, pipeline docs, machine-output docs,
  contributing docs, and roadmap entries to use `[config].strict`.
- Removed obsolete documentation references to the alpha-only `strict_config_checking` name.
- Documented that schema versioning remains intentionally absent from the 1.0 TOML format.

### Notes - 1.0.0a13

- This rename is intentionally completed before the stable 1.0 configuration contract is frozen.
- `[config].strict` is now the stable 1.0 TOML key for config-loading strictness behavior.
- Explicit TOML schema versioning is a post-1.0 concern and should be introduced only when a future
  non-additive schema change makes it necessary.

______________________________________________________________________

## [1.0.0a12] - 2026-05-07

This twelfth **1.0 alpha release** finalizes two remaining pre-1.0 public-boundary contracts:

1. the stable public probe API; and
1. the qualified-vs-local file type identifier semantics used by CLI filters, TOML configuration,
   API overlays, policy resolution, resolution and filtering, diagnostics, and registry-facing APIs.

It introduces `topmark.api.probe()` as the stable, read-only public API counterpart to the
`topmark probe` CLI command. Probe results are exposed through small, frozen DTOs instead of raw
resolver enums, registry objects, pipeline contexts, or synthetic contexts.

It also freezes TopMark's file type identifier contract: public inputs may use either canonical
qualified identifiers such as `topmark:python`, or local identifiers such as `python` when the local
identifier is unambiguous. Internally, TopMark now normalizes file type filters and `policy_by_type`
keys to canonical qualified keys.

This release continues the 1.0 boundary-freeze work from earlier alphas by aligning CLI/API probe
parity, classifying typed override helpers as internal bridge objects, freezing canonical file type
identifier behavior, and documenting the resulting public/internal boundaries across the user and
developer documentation.

> [!CAUTION] **Breaking changes**
>
> - Frozen `Config.policy_by_type` keys are now canonical qualified file type identifiers.
> - Runtime effective-policy lookup now uses canonical qualified file type identifiers.
> - Configuration, CLI, API, and machine-output consumers should expect normalized identifiers.

### Breaking Changes - 1.0.0a12

- **Frozen `Config.policy_by_type` keys are now canonical qualified file type identifiers.**

  - Previously, per-file-type policy maps could remain keyed by local identifiers such as `python`.
  - Frozen config now stores canonical qualified keys such as `topmark:python`.
  - Internal callers that directly inspect `Config.policy_by_type` or call low-level policy helpers
    must use canonical qualified keys.

- **Runtime effective-policy lookup now uses canonical qualified file type identifiers.**

  - `ProcessingContext.get_effective_policy()` now looks up policies by
    `ctx.file_type.qualified_key` instead of `ctx.file_type.local_key`.
  - Direct internal calls such as `effective_policy(cfg, "python")` no longer match a normalized
    `topmark:python` policy entry; use `effective_policy(cfg, "topmark:python")` instead.

- **Configuration, CLI, API, and machine-output consumers should expect normalized identifiers.**

  - File type filters and `policy_by_type` entries supplied as local identifiers may be emitted as
    canonical qualified identifiers after configuration normalization.
  - Downstream tooling that relied on preserving the exact user-supplied identifier spelling should
    compare canonical keys instead.

### Highlights - 1.0.0a12

- Added `topmark.api.probe()` as the stable public Python API for resolution diagnostics
- Introduced normalized public probe DTOs for run, file, and candidate results
- Aligned probe API behavior with the `topmark probe` CLI command
- Preserved missing and filtered explicit inputs in API probe results
- Froze qualified-vs-local file type identifier semantics for 1.0
- Normalized CLI/API/config file type filters to canonical qualified keys
- Added qualified identifier support for `policy_by_type`
- Normalized frozen `policy_by_type` maps to canonical qualified keys
- Updated runtime policy lookup to use canonical qualified file type identifiers
- Added registry, config, resolver, CLI, API, TOML, and policy regression coverage
- Kept resolver internals, pipeline contexts, synthetic contexts, and typed override helpers outside
  the stable public API contract
- Added shared documentation for file type identifier semantics and the public/internal override
  boundary
- Reorganized registry and plugin documentation around a dedicated registry model reference

### Added - 1.0.0a12

- **Public probe API**

  - Added `topmark.api.probe()` as a read-only API entry point for file-type and processor
    resolution diagnostics.
  - Added stable public DTOs:
    - `ProbeRunResult`
    - `ProbeFileResult`
    - `ProbeCandidateInfo`
  - Exposed `probe` and probe DTOs via `topmark.api.__all__`.

- **Qualified/local file type identifier contract**

  - Added canonical normalization of public file type identifiers to qualified keys such as
    `topmark:python` during config freeze.
  - Added qualified identifier support for:
    - `include_file_types`
    - `exclude_file_types`
    - `policy_by_type`
    - API overlays
    - resolution and filtering helpers
  - Accepted local identifiers such as `python` only when unambiguous in the effective file type
    registry.
  - Added deterministic handling for ambiguous, unknown, and malformed file type identifiers.

- **Probe result model**

  - API probe results include:
    - per-path probe status and reason strings
    - selected file type and processor, when resolved
    - normalized candidate information
    - selected/rank/match-signal fields for candidate interpretation
  - Explicit missing paths are preserved as error results.
  - Explicit inputs filtered before file-type probing are preserved as filtered probe results.

- **Tests**

  - Added focused API tests for `topmark.api.probe()` covering:
    - empty explicit directories
    - resolved Python files
    - unsupported explicit files
    - missing explicit paths
    - file-type-filtered explicit inputs
    - stable candidate DTO shape
  - Added registry identity tests for:
    - local identifier resolution
    - qualified identifier resolution
    - default namespace behavior
    - ambiguous local identifiers
    - malformed qualified identifiers
  - Added config and TOML regression coverage for `policy_by_type` normalization, ambiguity,
    malformed identifiers, and unknown identifiers.
  - Added API, CLI, and resolver regression coverage for local and qualified file type filters.
  - Updated public API import coverage and the public API snapshot for the new stable API surface.

- **Documentation snippets and pages**

  - Added `_snippets/no-stdin-option.md` to keep STDIN option guidance consistent across command and
    usage documentation.
  - Added `_snippets/api-internal-overrides.md` to keep the public/internal override-boundary
    wording consistent across API, configuration, architecture, schema, and resolution
    documentation.
  - Added `_snippets/file-type-identifiers.md` as the canonical reusable wording for local vs
    qualified file type identifiers.
  - Reused shared documentation snippets for file type identifier semantics, STDIN handling, and
    public/internal API boundary wording across user-facing and developer-facing documentation.
  - Added user-facing usage overview pages:
    - `docs/usage/cli.md`
    - `docs/usage/configuration.md`
  - Added `docs/dev/registry-model.md` as the dedicated registry architecture, identity, binding,
    overlay, and plugin-integration reference.

### Changed - 1.0.0a12

- **Configuration normalization**

  - `MutableConfig.freeze()` now normalizes `include_file_types`, `exclude_file_types`, and
    `policy_by_type` keys to canonical qualified file type identifiers.
  - Unknown identifiers are ignored diagnostically.
  - Malformed qualified identifiers are ignored diagnostically.
  - Ambiguous local identifiers are ignored diagnostically and require the qualified form.
  - Overlapping include/exclude file type filters are compared after canonical normalization.
  - Duplicate local/qualified `policy_by_type` entries that normalize to the same qualified key are
    merged deterministically.

- **Runtime policy lookup**

  - `ProcessingContext.get_effective_policy()` now looks up per-file-type policies by canonical
    qualified file type key.
  - This aligns frozen config, runtime policy lookup, resolver output, and registry identity
    semantics.

- **Resolver and file selection**

  - Resolver filtering now evaluates effective file type candidates by canonical qualified key while
    remaining tolerant of direct helper calls that pass local identifiers.
  - File selection diagnostics now distinguish unknown, malformed, and ambiguous configured file
    type identifiers more explicitly.
  - Resolver debug logging now reports qualified file type keys.

- **API runtime orchestration**

  - Added a probe-specific API runtime path that mirrors CLI probe behavior while returning public
    DTOs.
  - Refactored shared API runtime setup through `PreparedApiRun` so `check`, `strip`, and `probe`
    share config discovery, runtime policy overlays, writer-option handling, selected-file
    resolution, and per-path config setup.
  - Kept `topmark.api.runtime` internal; public callers should use `topmark.api.probe()`,
    `topmark.api.check()`, and `topmark.api.strip()`.

- **Synthetic probe handling**

  - Moved shared synthetic probe helpers into `topmark.pipeline.synthetic`.
  - Reused synthetic contexts internally so CLI output, machine output, API summaries, and exit-code
    selection remain aligned.
  - Prevented missing explicit paths from being reported twice as both hard errors and filtered
    probe results.

- **Public/internal API boundary**

  - Clarified that `topmark.api.probe()` is the stable public probe surface.
  - Clarified that low-level resolver helpers such as `probe_resolution_for_path()` are advanced /
    internal debugging surfaces outside the `topmark.api` stability contract.
  - Ensured probe API results expose normalized strings and DTOs rather than internal enum classes
    or implementation objects.

- **Configuration override boundary**

  - Classified `PolicyOverrides` and `ConfigOverrides` as internal typed bridge objects used by
    CLI/API orchestration.
  - Clarified that public Python callers should use plain mapping-based inputs through `config=...`,
    `policy=...`, and `policy_by_type=...` instead of constructing internal override dataclasses.
  - Documented the distinction between public configuration data and internal override machinery in
    user-facing configuration, policy, and command documentation.

- **File type identifier guidance**

  - Replaced local-only or ambiguous wording with a single contract:
    - qualified identifiers are canonical internally;
    - local identifiers are accepted only when unambiguous;
    - ambiguous local identifiers require the qualified form.
  - Documented that CLI filters, TOML configuration, API overlays, machine output, resolver
    diagnostics, and registry-facing APIs share this identifier model.

- **Plugin and registry documentation alignment**

  - Split detailed registry architecture, binding, overlay, and identity semantics into
    `docs/dev/registry-model.md`.
  - Updated plugin documentation to focus on plugin authoring while linking to the registry model
    for lower-level registry details.
  - Updated registry command documentation to describe effective composed registry views and
    canonical qualified identity fields.

### Fixed - 1.0.0a12

- Fixed `policy_by_type` inconsistency where filters accepted qualified identifiers but per-type
  policy keys were effectively local-only.
- Fixed runtime policy lookup missing per-type policies after canonical key normalization.
- Fixed resolver and CLI/API filter behavior so local and qualified file type identifiers select the
  same file types when unambiguous.
- Fixed config freeze behavior so ambiguous local `policy_by_type` identifiers do not silently map
  to an arbitrary namespace.
- Fixed malformed qualified identifiers such as `:python`, `topmark:`, and `topmark:python:extra`
  being treated as ordinary unknown identifiers.
- Fixed documentation drift around registry helpers, plugin identity guidance, command filtering,
  machine-output identity fields, and public mapping-based API overlays.

### Documentation - 1.0.0a12

- Updated README with:
  - a public `api.probe()` usage example
  - local and qualified file type filter examples
  - canonical `policy_by_type` examples
  - API identifier-semantics guidance
- Updated public API documentation to describe:
  - `topmark.api.probe()`
  - probe DTOs
  - missing and filtered input behavior
  - public/internal resolver boundary
- Updated architecture documentation to describe the API probe boundary and synthetic-context model.
- Updated pipeline documentation to distinguish `ProberStep` from probe orchestration and synthetic
  probe results.
- Added reusable file type identifier and STDIN guidance snippets and reused them across user and
  developer docs.
- Added and wired new user-facing pages:
  - CLI overview
  - Configuration guide
- Added and wired the new registry model developer page.
- Updated public and internal API docs to distinguish stable API surfaces from registry and resolver
  internals.
- Updated configuration, discovery, schema, filtering, policy, pre-commit, exit-code, global-option,
  command, machine-output, machine-format, architecture, resolution, plugin, registry, and API
  stability documentation.
- Updated all command pages for `check`, `strip`, `probe`, `config`, `registry`, and `version` to
  align with canonical identifier semantics and effective frozen configuration terminology.
- Updated `mkdocs.yml` navigation for the new CLI, configuration, and registry model pages.
- Updated API, configuration, architecture, resolution, policy, filtering, command, and README pages
  to document the public mapping-based override model.
- Updated plugin documentation to remove stale registry-helper references.
- Updated roadmap status to reflect completion of the public probe API, resolution-diagnostics
  boundary freeze and qualified/local file type identifier semantics freeze.

### Notes - 1.0.0a12

- `topmark.api.probe()` is now considered part of the stable 1.x public API contract.
- Probe remains read-only and does not perform header inspection, comparison, planning, patching, or
  mutation.
- Qualified file type identifiers such as `topmark:python` are the canonical internal identity.
- Local file type identifiers such as `python` remain accepted at public boundaries only when
  unambiguous.
- `policy_by_type`, `include_file_types`, and `exclude_file_types` all support the same identifier
  forms and normalize to canonical qualified keys internally.
- `PolicyOverrides` and `ConfigOverrides` are internal implementation details, not stable public API
  inputs.
- Public callers should use mapping-based `config`, `policy`, and `policy_by_type` arguments exposed
  by `topmark.api`.
- Remaining 1.0 work now focuses on final release validation, documentation build/link checks,
  packaging rehearsal, and any last release-path polish tracked in the roadmap.

______________________________________________________________________

## [1.0.0a11] - 2026-05-04

This eleventh **1.0 alpha release** finalizes TopMark's **CLI command-applicability contract**,
STDIN handling rules, and user-facing policy/report semantics for 1.0.

It tightens option scoping across `check`, `strip`, `probe`, `config`, `registry`, and `version`,
ensures invalid command/option combinations fail as CLI usage errors, and documents the final
behavior across CLI help, user documentation, architecture notes, and the roadmap.

This release completes the remaining CLI/policy freeze work after the exit-code and output-contract
milestones from earlier alphas.

> [!CAUTION] **Breaking changes**
>
> - CLI command and option applicability is now strictly enforced.
> - The `--stdin` flag is rejected; use `-` with `--stdin-filename` for STDIN content.
> - CLI help and error text changed; downstream exact-output assertions may need updates.

### Breaking Changes - 1.0.0a11

- CLI now strictly enforces command applicability:
  - unsupported options are rejected with usage errors instead of being ignored
  - file-agnostic commands (`config *`, `version`, registry commands) reject positional PATHS and
    STDIN inputs
- `--stdin` flag is no longer accepted (and is now explicitly rejected); only `-` with
  `--stdin-filename` is supported
- Option applicability is now strictly validated:
  - `--apply`, `--report`, and policy options are rejected on unsupported commands (e.g. `probe`,
    `strip`)
- CLI help and error messages updated for consistency; downstream tooling relying on exact output
  may need adjustment

### Added - 1.0.0a11

- Finalized and enforced CLI command-applicability contract across all commands
- Introduced global CLI applicability validation with consistent error handling
- Added focused CLI tests for:
  - command-specific option rejection
  - STDIN misuse and conflicts
  - file-agnostic command behavior
- Added reusable documentation snippets for:
  - STDIN handling
  - report-scope semantics
- Added config-dump-specific `--files-from` option decorator to clarify compatibility semantics

### Changed - 1.0.0a11

- Standardized STDIN contract:
  - content input uses POSIX-style `-` sentinel plus `--stdin-filename`
  - `--stdin` option flag is explicitly not supported and rejected
- Harmonized CLI help text, epilog formatting, and option descriptions across all commands
- Clarified file-agnostic command behavior:
  - positional PATHS and file-processing STDIN modes are now consistently rejected
- Refined `config dump --files-from` semantics:
  - accepted for compatibility only
  - listed paths do not affect dumped configuration
- Unified wording across CLI, docs, and tests for:
  - "rejected" vs "ignored" behavior
  - report-scope semantics
- Improved robustness of CLI help tests by normalizing whitespace to account for Click wrapping

### Fixed - 1.0.0a11

- Fixed STDIN handling inconsistencies when using unsupported `--stdin` flag
- Fixed incorrect or misleading CLI help text regarding:
  - STDIN usage
  - file-agnostic command behavior
  - `--files-from` semantics in `config dump`
- Fixed epilog formatting issues in nested command groups (`config *`) using Click paragraph
  preservation
- Fixed brittle CLI help assertions caused by line wrapping in test output

### Documentation - 1.0.0a11

- Updated all CLI command pages (`check`, `strip`, `probe`, `config`, registry, version) to reflect
  frozen applicability and STDIN contracts
- Updated configuration, filtering, and architecture docs to align with finalized CLI behavior
- Updated README and documentation index for consistency
- Updated roadmap to reflect completion of CLI/policy contract freeze and shift remaining work to
  API/config boundaries

### Notes - 1.0.0a11

- CLI applicability, error/diagnostic behavior, STDIN handling, and user-facing policy/report
  semantics are now considered frozen for 1.0
- Remaining work toward 1.0 focuses on API/public boundary freeze, configuration contract
  finalization, and release validation

______________________________________________________________________

## [1.0.0a10] - 2026-05-04

This tenth **1.0 alpha release** finalizes TopMark's **CLI exit-code contract**, tightens the
`--quiet` / verbosity surface, and completes the file-resolution diagnostics model for 1.0.

It introduces structured file-list resolution with explicit diagnostics, preserves missing inputs
end-to-end via synthetic pipeline contexts, and centralizes exit-code derivation from pipeline
results using deterministic priority ordering.

This release completes the CLI contract work following the output-contract, probe, and resolution
explainability milestones from earlier alphas.

> [!CAUTION] **Breaking changes**
>
> - The CLI `--quiet` / verbosity contract was tightened for pure informational commands.
> - Explicit missing inputs are now reported and affect output and exit codes.
> - File-list resolution and pipeline-result exit-code semantics changed.

### Breaking Changes - 1.0.0a10

- **CLI quiet/verbosity contract tightened**

  - The `--quiet` flag is no longer accepted by **pure informational commands**:
    - `version`
    - `config defaults`
    - `config init`
  - These commands now:
    - always produce output in TEXT/Markdown modes
    - reject `--quiet` as a usage error
  - This finalizes the CLI contract where:
    - `--quiet` is available only on commands with meaningful status, inspection, or mutation
      signals

- **CLI behavior for missing inputs**

  - Explicit missing input paths are no longer silently ignored or collapsed into "no files to
    process".
  - Missing inputs are now reported as per-file errors in:
    - TEXT output
    - Markdown output
    - JSON / NDJSON machine output
  - CLI commands now exit with:
    - `FILE_NOT_FOUND (66)` when one or more explicit inputs are missing

- **Resolver API change**

  - `resolve_file_list()` has been replaced by:
    - `resolve_file_list_with_diagnostics()`
  - Callers must now handle a structured `FileListResolution` object with:
    - `selected`
    - `missing_literals`
    - `unmatched_patterns`
  - Legacy assumptions about resolver returning only a list of files are no longer valid.

- **Exit-code semantics**

  - Pipeline-result-derived exit-code behavior is now centralized and enforced with deterministic
    priority ordering, including:
    - `PERMISSION_DENIED (77)` > `FILE_NOT_FOUND (66)` > `IO_ERROR (74)` > `CONFIG_ERROR (78)` >
      `FAILURE (1)`
  - Mixed-result runs now deterministically return the highest-priority failure.
  - CLI commands (`check`, `strip`, `probe`) now share consistent exit-code semantics.

- **Unmatched glob behavior clarified**

  - Unmatched glob patterns are treated as:
    - non-fatal diagnostics for `check` / `strip`
    - semantic resolution outcomes for `probe` (`UNSUPPORTED_FILE_TYPE (69)`)

### Highlights - 1.0.0a10

- Finalized CLI `--quiet` / verbosity contract for pure informational commands
- Finalized CLI exit-code contract for 1.0
- Introduced diagnostic-aware file resolution
- Preserved missing inputs via synthetic pipeline contexts
- Unified exit-code derivation across all CLI commands
- Completed probe/check/strip parity for filesystem and resolution errors
- Fully aligned tests, CLI behavior, and documentation

### Added - 1.0.0a10

- **File resolution diagnostics**

  - Added `FileListResolution` model exposing:
    - selected files
    - missing literal inputs
    - unmatched glob patterns
  - Added `resolve_file_list_with_diagnostics()` as the canonical resolver entry point.

- **Synthetic pipeline contexts**

  - Added `pipeline.synthetic.build_missing_file_contexts(...)`.
  - Represent missing inputs as `ProcessingContext` instances with `FsStatus.NOT_FOUND`
  - Ensure missing inputs participate in:
    - pipeline execution
    - rendering
    - summaries
    - exit-code selection

- **Exit-code engine**

  - Added `exit_code_from_pipeline_results(...)` to centralize pipeline-result-derived exit-code
    selection.
  - Implemented deterministic priority ordering for mixed-result runs.

- **Tests**

  - Added CLI tests for:
    - missing inputs (`FILE_NOT_FOUND`)
    - write/permission errors
    - unmatched glob behavior
    - probe exit-code semantics
    - mixed-result exit-code priority
  - Introduced `pytest.mark.exit_code` and centralized assertion helpers

### Changed - 1.0.0a10

- **CLI quiet/verbosity behavior**

  - Removed `--quiet` support from pure informational commands:
    - `version`
    - `config defaults`
    - `config init`
  - Informational commands now:
    - always emit output in TEXT and Markdown formats
    - treat `--quiet` as an invalid option
  - Reinforces the CLI contract:
    - `--quiet` applies only to commands with meaningful status, inspection, or mutation signals
  - Simplified version presentation by removing quiet-dependent branching for informational output

- **CLI behavior**

  - `check`, `strip`, and `probe` now:
    - propagate resolver diagnostics end-to-end
    - report missing inputs explicitly
    - no longer short-circuit on "no files to process" when inputs are invalid
  - Total file counts now include synthetic resolver-level results

- **Pipeline / outcome classification**

  - Updated `map_bucket()` to prioritize filesystem failures before resolution state
  - Prevented synthetic contexts from being classified as "resolve pending"
  - Ensured missing inputs are consistently classified as errors

- **Probe semantics**

  - Ensured missing inputs produce hard failures (`FILE_NOT_FOUND`)
  - Preserved semantic outcomes (`UNSUPPORTED_FILE_TYPE`) for filtered/unsupported inputs
  - Completed exit-code parity with `check` and `strip`

- **Documentation: output contract, verbosity and `--quiet`**

  - Updated command docs (`version`, `config defaults`, `config init`) to remove `--quiet`
  - Introduced dedicated output-contract snippets:
    - `output-contract.md`
    - `output-contract-no-quiet.md`
  - Clarified in global options and README:
    - `--quiet` is not universally available
    - informational commands always produce output

- **Documentation: exit codes and hint ordering**

  - Added and aligned a canonical exit-code contract (`docs/usage/exit-codes.md`)
  - Updated:
    - command pages (`check`, `strip`, `probe`, `config`, `registry`, `version`)
    - filtering and pre-commit docs
    - architecture, API, machine-output, and roadmap docs
    - README and documentation index
  - Clarified:
    - missing vs unmatched input behavior
    - machine output vs process exit status separation
    - presentation-level nature of hint ordering

- **Test suite**

  - Refactored CLI test suite into domain-specific modules
  - Removed legacy `test_exit_codes.py`
  - Standardized exit-code assertions and naming
  - Updated CLI tests to:
    - assert rejection of `--quiet` for informational commands
    - remove overlapping quiet-behavior tests for version/config commands
    - align logging flag tests with commands that support quiet

### Fixed - 1.0.0a10

- **Missing input handling**

  - Fixed bug where missing inputs were dropped during resolution and not reflected in CLI output or
    exit codes
  - Ensured missing inputs are preserved across resolver → pipeline → presentation

- **Exit-code inconsistencies**

  - Fixed inconsistent exit-code behavior across `check`, `strip`, and `probe`
  - Ensured mixed-result runs always return the highest-priority failure

- **Probe edge cases**

  - Fixed probe behavior where semantic outcomes could override filesystem errors
  - Ensured missing inputs take precedence over unsupported-type outcomes

- **Resolver/test mismatches**

  - Fixed tests relying on legacy resolver behavior returning plain file lists
  - Aligned resolver tests with diagnostic-aware model

- **Documentation generation**

  - Fixed the generated `config defaults` documentation page incorrectly showing `config init`
    output.

### Notes - 1.0.0a10

- The **CLI exit-code contract and `--quiet` / verbosity surface are now finalized and considered
  stable for 1.0**.
- File resolution, pipeline execution, and CLI reporting now form a **single unified diagnostic
  flow**.
- Machine output (JSON/NDJSON) remains intentionally **decoupled from process exit codes**.
- Primary/headline hint selection is explicitly **presentation-level and not part of the stable CLI
  contract**.
- Remaining work before 1.0 is limited to:
  - minor wording and presentation refinements
  - final release-path validation and polish

______________________________________________________________________

## [1.0.0a9] - 2026-04-28

This ninth **1.0 alpha release** finalizes TopMark's **line-ending support contract** for 1.0.

It audits and freezes how the pipeline detects, preserves, and rejects newline styles, clarifying
that TopMark supports only standard physical newline sequences while tolerating nonstandard Unicode
separators as ordinary content characters.

### Highlights - 1.0.0a9

- Froze the 1.0 line-ending support contract
- Standardized newline detection around LF, CRLF, and CR only
- Clarified that exotic Unicode separators are content, not line delimiters
- Strengthened reader, sniffer, XML safety, and property-based tests
- Documented that newline behavior is global and not configurable by policy for 1.0

### Added - 1.0.0a9

- **Pipeline / newline contract**

  - Added canonical standard newline helpers:
    - `STANDARD_NEWLINES`
    - `STANDARD_NEWLINE_SET`
    - `STANDARD_NEWLINE_RE`
  - Established LF, CRLF, and CR as the only recognized physical newline styles.

- **Tests**

  - Added reader coverage confirming exotic separators are treated as content.
  - Added sniffer coverage confirming exotic separators are not counted as newline styles.
  - Added XML processor coverage for conservative idempotence skips near unsupported separators.
  - Updated property-based tests to generate only standard newline styles.

### Changed - 1.0.0a9

- **Pipeline behavior**

  - Reader and sniffer logic now consistently use the standard newline contract.
  - Newline detection preserves CRLF-first ordering to avoid misclassifying CRLF as separate CR/LF.
  - Mixed-line-ending detection applies only to recognized standard newline styles.
  - Rendering, planning, patching, and writing preserve the recognized newline style and do not
    normalize mixed styles implicitly.

- **Nonstandard separators**

  - Unicode NEL (`U+0085`), LS (`U+2028`), and PS (`U+2029`) are not treated as newline delimiters.
  - Such characters are tolerated as ordinary content characters.
  - They are not counted in newline histograms and do not participate in mixed-line-ending
    detection.
  - XML-specific boundary safety remains conservative where such characters could affect
    idempotence.

- **Documentation**

  - Documented the newline contract in user and developer docs.
  - Clarified that newline handling is global, not per-file-type.
  - Clarified that no newline-related policy surface is introduced for 1.0.
  - Updated roadmap status to mark the line-ending support audit as completed.

### Fixed - 1.0.0a9

- **Property-test overreach**

  - Removed accidental implication that exotic Unicode separators are supported newline styles.
  - Aligned Hypothesis strategies with the intended 1.0 newline contract.

- **Pipeline consistency**

  - Ensured reader and sniffer behavior agree on which newline styles are recognized.
  - Reduced risk of accidental future expansion of newline semantics through tests or regex changes.

### Notes - 1.0.0a9

- TopMark's supported physical newline styles for 1.0 are:
  - LF (`\n`)
  - CRLF (`\r\n`)
  - CR (`\r`)
- Nonstandard Unicode separators remain tolerated as content, but are not supported as line endings.
- Extended/rich Unicode newline support and newline-related policy controls are explicitly deferred
  beyond 1.0 unless a concrete file-type requirement emerges.

______________________________________________________________________

## [1.0.0a8] - 2026-04-28

This eighth **1.0 alpha release** refines the filtered-input diagnostics introduced in `1.0.0a7` by
distinguishing **path-filtered** inputs from **file-type-filtered** inputs.

It keeps exact pattern/source attribution out of scope, but improves `topmark probe` explainability
with stable, machine-friendly reason categories.

> [!CAUTION] **Breaking changes**
>
> - Filtered probe results no longer always use `reason="excluded_by_discovery_filter"`.
> - Probe machine output may emit more specific filtered-input reason values.

### Breaking Changes - 1.0.0a8

- Filtered probe results no longer always use `reason="excluded_by_discovery_filter"`.
- Probe machine output may now emit:
  - `reason="excluded_by_path_filter"`
  - `reason="excluded_by_file_type_filter"`
  - `reason="excluded_by_discovery_filter"` as fallback
- Consumers that assumed only `excluded_by_discovery_filter` for filtered probe results must accept
  the refined reason values.

### Highlights - 1.0.0a8

- Refined filtered-input reasons for `topmark probe`
- Distinguished path filters from file-type filters
- Preserved generic discovery-filter fallback
- Updated TEXT, JSON, and NDJSON tests
- Aligned probe, filtering, machine-output, API, README, and roadmap documentation

### Added - 1.0.0a8

- **Refined filtered probe reasons**

  - Added:
    - `excluded_by_path_filter`
    - `excluded_by_file_type_filter`
  - Kept:
    - `excluded_by_discovery_filter` as a fallback when no broad category is identified

- **Tests**

  - Added resolver coverage for:
    - path-filtered explicit inputs
    - include-file-type filtered inputs
    - exclude-file-type filtered inputs
    - generic fallback filtering
  - Updated CLI human-output and machine-output tests for refined reason values.

### Changed - 1.0.0a8

- **Probe behavior**

  - `topmark probe` now classifies explicit filtered inputs by broad filter category.
  - `--exclude` / path-pattern filtering now reports `excluded_by_path_filter`.
  - file-type include/exclude filtering now reports `excluded_by_file_type_filter`.

- **Documentation**

  - Updated probe command documentation.
  - Updated machine-output and machine-format references.
  - Updated resolution, filtering, API, README, and roadmap documentation.
  - Clarified that exact filter pattern/source attribution remains out of scope.

### Notes - 1.0.0a8

- This alpha refines the `1.0.0a7` filtered-input probe contract.
- `topmark probe` still reports only explicitly requested filtered inputs.
- Files ignored implicitly during recursive discovery are still not enumerated.
- Exact matching pattern/source attribution remains a possible future enhancement.

______________________________________________________________________

## [1.0.0a7] - 2026-04-28

This seventh **1.0 alpha release** completes the `probe` diagnostics surface by explaining
**explicit inputs filtered during discovery** before file-type probing begins.

It follows `1.0.0a6`, which introduced the `probe` command and probe-backed resolution contract, and
extends that contract so explicitly requested paths that are filtered out are still reported in
TEXT, Markdown, JSON, and NDJSON output.

> [!CAUTION] **Breaking changes**
>
> - `topmark probe` now reports explicitly requested paths filtered during discovery.
> - Probe JSON / NDJSON output should now be interpreted as per-path / per-result output.
> - Filtered explicit inputs can now affect the `topmark probe` exit code.

### Breaking Changes - 1.0.0a7

- `topmark probe` now reports explicitly requested paths filtered during discovery instead of
  treating them as silently absent from the probe result set.
- Probe machine output now includes a new status / reason pair:
  - `status="filtered"`
  - `reason="excluded_by_discovery_filter"`
- Probe JSON / NDJSON output should now be interpreted as **per-path** / **per-result** output
  rather than strictly per-file output.
- `topmark probe` returns `UNSUPPORTED_FILE_TYPE` (69) when one or more explicit inputs are filtered
  before probing, because those paths did not resolve to a supported file type and processor.

### Highlights - 1.0.0a7

- Added discovery-level explainability for explicitly filtered inputs
- Completed the `probe` diagnostics model across discovery and resolution
- Added `filtered` probe results to TEXT, Markdown, JSON, and NDJSON output
- Split probe presentation from check/strip pipeline presentation
- Strengthened unit and CLI coverage for filtered probe inputs
- Aligned user and developer documentation with the updated probe contract

### Added - 1.0.0a7

- **Discovery-level probe model**

  - Added `FileSelectionProbeResult` for explaining explicit inputs before file-type probing.
  - Added machine-friendly selection statuses and reasons for discovery-level filtering.
  - Added focused resolver tests for:
    - selected explicit inputs
    - filtered explicit inputs
    - missing explicit inputs
    - explicit directories

- **Filtered probe results**

  - Added `ResolutionProbeStatus.FILTERED`.
  - Added `ResolutionProbeReason.EXCLUDED_BY_DISCOVERY_FILTER`.
  - `topmark probe` now emits synthetic probe results for explicitly requested paths excluded during
    discovery.
  - Filtered probe results use:
    - `selected_file_type = null`
    - `selected_processor = null`
    - `candidates = []`

- **Probe presentation modules**

  - Added dedicated TEXT probe renderer (`topmark.presentation.text.probe`).
  - Added dedicated Markdown probe renderer (`topmark.presentation.markdown.probe`).
  - Kept probe presentation separate from check/strip pipeline rendering.

- **Tests**

  - Added CLI human-output coverage for filtered explicit inputs.
  - Added JSON / NDJSON machine-output coverage for filtered probe payloads.
  - Added path-preservation assertions for filtered explicit inputs.
  - Added resolver-level discovery tests for the new discovery explanation helper.

### Changed - 1.0.0a7

- **Probe behavior**

  - `topmark probe` now explains explicit inputs that disappear during discovery/filtering.

  - Filtered explicit inputs are rendered in TEXT output as:

    ```text
    <path>: <filtered> - filtered: excluded_by_discovery_filter
    ```

  - Recursive discovery still does **not** enumerate every ignored file; only explicitly requested
    paths are reported as filtered probe results.

- **Machine output**

  - Probe output is now documented and treated as **per-path** rather than strictly per-file.
  - JSON `probes` entries and NDJSON `kind="probe"` records may represent:
    - normal file-type probe results
    - unsupported paths
    - unbound processor cases
    - filtered explicit inputs
  - Machine schemas, payload builders, envelopes, and serializers now document filtered synthetic
    probe contexts.

- **Presentation layer**

  - Split probe-specific rendering out of generic pipeline renderers.
  - Updated probe banners to use **TopMark Resolution Probe Results** wording.
  - Updated filtered TEXT output from `<unknown>` to `<filtered>`.
  - Kept Markdown probe output document-oriented and independent from TEXT verbosity/quiet controls.

- **Documentation**

  - Updated machine-output and machine-format references to document filtered probe payloads.
  - Updated resolution and pipeline docs to distinguish discovery filtering from file-type probing.
  - Updated `topmark probe` command documentation with filtered payload examples and exit-code
    wording.
  - Updated filtering documentation to describe how probe reports explicitly requested filtered
    inputs.
  - Updated README and docs index with filtered-input probe examples.

### Fixed - 1.0.0a7

- **Probe explainability gap**

  - Explicit inputs filtered before file-type probing are no longer reported as simply missing or as
    "no files to process".
  - Users can now distinguish "unsupported file type" from "filtered before probing".

- **Presentation coupling**

  - Removed probe rendering code from check/strip pipeline presentation modules.
  - Cleaned stale pipeline/check/strip wording from probe renderers.
  - Improved docstrings and inline comments in probe, pipeline, discovery, and machine-output code
    paths.

### Notes - 1.0.0a7

- `topmark probe` now covers both:
  - discovery-level explanations for explicitly filtered inputs
  - file-type / processor resolution explanations for paths that reached probing
- Filtered probe payloads intentionally use a coarse `excluded_by_discovery_filter` reason for now.
  Exact filter-pattern/source attribution remains a possible future enhancement.
- Files ignored implicitly during recursive discovery are not enumerated by `probe`; only explicit
  command inputs and `--files-from` entries are reported this way.
- This alpha further stabilizes the 1.0 resolution explainability contract introduced in `1.0.0a6`.

______________________________________________________________________

## [1.0.0a6] - 2026-04-28

This sixth **1.0 alpha release** focuses on **finalizing the resolution contract** and introducing
full **resolution explainability** via the new `probe` command and probe-backed pipeline model.

It completes the registry / resolution freeze by unifying file-type and processor resolution around
a single probe-based contract, removing legacy helpers, and exposing deterministic, inspectable
resolution behavior across CLI, pipeline, API, documentation, and machine formats.

> [!CAUTION] **Breaking changes**
>
> - Legacy resolution helpers were removed.
> - Resolution is now probe-driven across pipeline and public diagnostic surfaces.
> - `probe_resolution_for_path()` is the single path-based resolution surface for callers that need
>   file-type / processor resolution details.

### Breaking Changes - 1.0.0a6

- Removed legacy resolution helpers:
  - `resolve_file_type_for_path()`
  - `resolve_binding_for_path()`
  - `ResolvedBinding`
- `probe_resolution_for_path()` is now the single path-based resolution surface for callers that
  need file-type / processor resolution details.
- Resolution is now **probe-driven**:
  - pipeline resolution derives from `ResolutionProbeResult`
  - no parallel file-type / binding resolution path remains

### Highlights - 1.0.0a6

- Introduced **resolution explainability** via `topmark probe`
- Unified resolution across CLI, pipeline, and API using a shared **probe result** model
- Completed the **registry / resolution contract freeze**
- Removed legacy resolution helpers and redundant resolution paths
- Added full **machine-output support** for probe diagnostics (JSON + NDJSON)
- Strengthened test coverage across resolution, pipeline, CLI, and machine formats

### Added - 1.0.0a6

- **Probe command (`topmark probe`)**

  - New CLI command to explain file-type and processor resolution
  - Supports:
    - TEXT output (verbosity-aware)
    - Markdown output (document-style)
    - JSON output (`probes` envelope)
    - NDJSON output (`kind="probe"` records)
  - Provides:
    - candidate file types with scores
    - match signals
    - selected file type and processor
    - deterministic tie-break reasoning

- **Resolution probe model**

  - New `ResolutionProbeResult` data model exposing:
    - candidate ranking
    - scoring
    - match signals
    - selected outcome
  - Shared across:
    - CLI (`probe`)
    - pipeline (`ProberStep`, `ResolverStep`)
    - API (`probe_resolution_for_path()`)

- **Pipeline**

  - New `ProberStep` producing resolution probe results
  - Dedicated `Pipeline.PROBE` variant for resolution-only diagnostics

- **Machine output**

  - Added probe payloads and schemas:
    - JSON: `probes` collection
    - NDJSON: one `kind="probe"` record per file
  - Integrated probe output into machine emitters and serializers

- **Testing**

  - Resolver-level probe tests for candidate selection, ranking, and unsupported cases
  - Pipeline step tests for `ProberStep`
  - CLI tests for:
    - exit codes
    - TEXT and Markdown output contracts
  - Machine-output tests for:
    - JSON schema shape
    - NDJSON record shape
    - regression coverage for probe record wrapping

### Changed - 1.0.0a6

- **Resolution model**

  - Resolution is now fully **probe-backed and deterministic**
  - Path-based resolution is unified under `probe_resolution_for_path()`
  - Removed internal duplication between probing and effective resolution

- **Pipeline architecture**

  - Refactored `ResolverStep` to consume probe results instead of recomputing resolution
  - Shared effective resolution mapping between `ResolverStep` and `ProberStep`
  - Preserved existing `check` / `strip` pipeline semantics while making resolution explainable

- **CLI behavior**

  - Added probe-specific exit behavior:
    - `SUCCESS` (0): all files resolved
    - `UNSUPPORTED_FILE_TYPE` (69): one or more files could not resolve to a supported file type and
      processor
  - Kept `probe` independent from `check` / `strip` mutation semantics
  - Kept probe output focused on resolution diagnostics rather than actionable header hints

- **Presentation layer**

  - Added dedicated rendering for probe output in:
    - TEXT (verbosity-aware)
    - Markdown (document-oriented and verbosity-independent)
  - Aligned probe output with the existing human-output contract for TEXT vs Markdown behavior

- **Documentation**

  - Added full probe command documentation (`docs/usage/commands/probe.md`)
  - Updated:
    - resolution docs (probe-based model)
    - pipeline docs (`ProberStep` and `Pipeline.PROBE`)
    - machine-output and machine-format docs (probe schemas)
    - API docs (probe-based resolution surface)
    - README and index pages (probe as a first-class feature)
  - Roadmap updated to mark resolution explainability as complete and registry query/filter commands
    as deferred

### Removed - 1.0.0a6

- Legacy non-probe resolution helpers:
  - `resolve_file_type_for_path()`
  - `resolve_binding_for_path()`
  - `ResolvedBinding`
- Redundant file-type / processor resolution paths outside the probe-backed model

### Fixed - 1.0.0a6

- **NDJSON probe output**

  - Fixed double-wrapping of probe records
  - Ensured one `kind="probe"` record is emitted per probed file

- **Resolution consistency**

  - Eliminated discrepancies between resolver and probing logic
  - Preserved header-unsupported precedence for `skip_processing=True` file types
  - Ensured deterministic tie-break behavior is consistently applied and exposed

### Notes - 1.0.0a6

- The **resolution contract is now finalized and considered stable for 1.0**.
- `probe_resolution_for_path()` is the canonical path-based resolution surface.
- `topmark probe` is the canonical diagnostics interface for resolution explainability.
- Registry query/filter commands remain explicitly deferred beyond this alpha.
- Remaining work before 1.0 focuses on:
  - optional discovery/filter explainability for explicitly skipped inputs
  - final release-path validation and polish

______________________________________________________________________

## [1.0.0a5] - 2026-04-27

This fifth **1.0 alpha release** focuses on **finalizing the CLI output contract and human-output
semantics** across TEXT, Markdown, and machine formats.

It completes the CLI/output-surface stabilization work by enforcing a clear separation between
console-oriented output, document-oriented rendering, and machine-readable formats, backed by
comprehensive tests and fully aligned documentation.

> [!CAUTION] **Breaking changes**
>
> - TopMark now requires `pathspec>=1.1.0,<1.2.0`.

### Breaking Changes - 1.0.0a5

- TopMark now requires `pathspec>=1.1.0,<1.2.0`. Environments pinning older `pathspec` versions must
  update their constraints.

### Highlights - 1.0.0a5

- Finalized and enforced the **TEXT vs Markdown vs machine output contract**
- Introduced **typed CLI runtime state** and removed untyped context usage
- Standardized **verbosity and quiet semantics** across all commands
- Strengthened **human-output test coverage** across pipeline, config, registry, and version
  commands
- Fully aligned CLI, presentation layer, and documentation ahead of the 1.0 freeze

### Added - 1.0.0a5

- **CLI / human-output tests**

  - Dedicated CLI test coverage for pipeline commands (`check`, `strip`) validating:
    - TEXT quiet mode suppressing output while preserving exit status
    - Markdown output ignoring TEXT-only controls
    - TEXT verbosity affecting output shape
    - `--apply --quiet` performing mutations without emitting output
  - Additional tests for:
    - version command (TEXT, Markdown, JSON, NDJSON quiet/verbosity behavior)
    - config, registry, and diagnostic human-output consistency

- **Presentation tests**

  - New test module validating diagnostic rendering across TEXT and Markdown:
    - compact summary at default verbosity
    - detailed output at higher verbosity levels
    - consistent behavior across formats

### Changed - 1.0.0a5

- **CLI output contract**

  - Enforced strict separation between:
    - TEXT output (console-oriented, verbosity/quiet controlled)
    - Markdown output (document-oriented, independent of verbosity/quiet)
    - machine output (JSON/NDJSON, schema-driven and unaffected by presentation flags)
  - `--verbose` and `--quiet` are now explicitly **TEXT-only controls**
  - Markdown rendering is now stable and independent from TEXT verbosity/quiet behavior
  - Registry commands no longer expose `--quiet`

- **CLI runtime architecture**

  - Introduced `TopmarkCliState` as the **typed runtime state container**
  - Replaced untyped `ctx.obj` usage with structured helpers:
    - `bootstrap_cli_state()`
    - `get_cli_state()`
  - Removed implicit console resolution and now pass console explicitly
  - Improved type safety and predictability of CLI execution

- **Verbosity and quiet semantics**

  - Normalized verbosity handling via `normalize_verbosity()` with bounded levels
  - Converted `--quiet` from a count-based flag to a **boolean suppression flag**
  - Restricted quiet suppression to **TEXT rendering only**
  - Non-TEXT formats now ignore or normalize verbosity/quiet flags safely

- **Presentation layer**

  - Further decoupled presentation from CLI and runtime concerns
  - Ensured all renderers are:
    - pure (no I/O)
    - reusable
    - independently testable
  - Aligned diagnostic rendering behavior across TEXT and Markdown

- **Documentation**

  - Unified CLI output contract wording across all documentation surfaces
  - Introduced reusable snippets:
    - `output-contract.md`
    - `output-contract-no-quiet.md`
  - Replaced duplicated explanations across:
    - command docs (check, strip, version, config, registry)
    - global options and pre-commit docs
    - README and index pages
  - Updated developer docs (architecture, machine-output, roadmap) to reflect:
    - strict separation of output layers
    - finalized verbosity/quiet semantics
  - Marked CLI/output behavior as **effectively frozen for 1.0**

- **Dependencies / file resolution**

  - Updated `pathspec` requirement to **`>=1.1.0,<1.2.0`**.
  - Aligned TopMark with the generic `PathSpec` API introduced in `pathspec 1.1`.
  - Introduced a typed `GitIgnorePathSpec` alias backed by `GitIgnoreBasicPattern` for Pyright
    strict compatibility.
  - Updated config pattern compilation and file-resolution logic to use the typed API.
  - TopMark now requires the `pathspec 1.1.x` series; environments pinning older `pathspec` versions
    must update their constraints.

### Fixed - 1.0.0a5

- **Version command output**

  - Ensured `--quiet` suppresses only TEXT output without emitting blank lines
  - Preserved Markdown and machine output visibility under quiet mode
  - Aligned Markdown rendering with TEXT verbosity expectations

- **Diagnostic rendering consistency**

  - Resolved inconsistencies between TEXT and Markdown summary/detail behavior
  - Ensured consistent compact vs detailed output across verbosity levels

### Notes - 1.0.0a5

- The **CLI output contract is now finalized and considered stable for 1.0**.
- TEXT, Markdown, and machine outputs now have **clearly defined and enforced roles**.
- Presentation, CLI orchestration, and machine serialization are now **fully decoupled**.
- Remaining work before 1.0 is limited to:
  - minor presentation refinements (e.g. hint ordering, diff rendering)
  - final release-path validation and polish

______________________________________________________________________

## [1.0.0a4] - 2026-04-22

This fourth **1.0 alpha release** focuses on **finalizing the runtime dependency model** for
reliable execution in isolated environments.

It follows `1.0.0a3` and addresses an additional implicit dependency discovered during pre-commit
usage, while also introducing dependency-audit configuration to reduce the risk of further
dependency drift.

### Highlights - 1.0.0a4

- Completed promotion of implicit runtime dependencies to explicit core dependencies
- Added dependency-audit configuration to help prevent further dependency drift
- Further improved reliability in pre-commit, CI, and clean environments

### Changed - 1.0.0a4

- **Dependencies / packaging**

  - Promoted `packaging` to a **core runtime dependency**.
  - Ensures that version parsing and related utilities used in `topmark.constants` are always
    available at runtime.
  - Aligns declared dependencies with actual runtime import requirements.
  - Added a `deptry` configuration block in `pyproject.toml` so dependency-audit checks model the
    development/documentation optional-dependency groups explicitly.

### Fixed - 1.0.0a4

- **Runtime import failure in isolated environments**

  - Prevented potential `ModuleNotFoundError` for `packaging` when running via:
    - pre-commit hooks
    - fresh virtual environments
    - minimal CI environments

### Notes - 1.0.0a4

- This release continues the cleanup of **implicit runtime dependencies** discovered during alpha
  testing.
- TopMark's dependency model is now more explicit, reproducible, and better guarded against future
  drift through dependency-audit configuration.
- Remaining work before 1.0 focuses on **CLI / human-output consistency and final contract freeze**.

______________________________________________________________________

## [1.0.0a3] - 2026-04-22

This third **1.0 alpha release** focuses on **packaging correctness, machine-output finalization,
and documentation alignment**.

The primary goal of `1.0.0a3` is to ensure that TopMark behaves reliably in **isolated
environments** and that the **machine-output contract is fully finalized, tested, and documented**
ahead of the 1.0 release.

This release completes the machine-output track and introduces important packaging fixes discovered
during real-world usage.

### Highlights - 1.0.0a3

- Corrected runtime dependency model for reliable execution in isolated environments
- Finalized registry machine-output contract (JSON + NDJSON)
- Strengthened machine-output test coverage with shared helpers
- Fully aligned machine-output documentation and roadmap with frozen 1.0 contract
- Introduced markdownlint integration for documentation quality

### Added - 1.0.0a3

- **Registry machine-output tests**

  - Dedicated CLI machine tests for:
    - `registry filetypes`
    - `registry processors`
    - `registry bindings`
  - Coverage includes:
    - flattened JSON shapes
    - NDJSON record kinds
    - detail-level projections
    - ordering guarantees
    - bound/unbound/unused registry scenarios

- **Testing helpers**

  - Shared NDJSON helpers for:
    - record kind validation
    - payload extraction
    - metadata assertions
  - Helpers now reusable across:
    - config
    - pipeline
    - version
    - registry

- **Tooling**

  - Added `markdownlint-cli2` integration via pre-commit
  - Introduced `.markdownlint.jsonc` for documentation consistency

### Changed - 1.0.0a3

- **Dependencies / packaging**

  - Promoted `typing-extensions` to a **core runtime dependency**
  - Packaging metadata now reflects the actual runtime import surface
  - Ensures consistent behavior across:
    - pre-commit environments
    - CI runners
    - clean/isolated virtual environments

- **Machine output (registry)**

  - Flattened JSON envelopes for registry commands:
    - `filetypes` → `{meta, filetypes}`
    - `processors` → `{meta, processors}`
    - `bindings` → `{meta, bindings, unbound_filetypes, unused_processors}`
  - Removed nested wrapper objects in favor of stable top-level collections
  - Aligned registry machine typing surface with homogeneous entry-list schemas
  - Ensured consistency between JSON (aggregated) and NDJSON (record-oriented) outputs

- **Tests**

  - Refactored existing machine tests to use shared NDJSON helpers
  - Reduced duplication in NDJSON parsing and validation
  - Improved clarity and consistency of machine contract assertions

- **Documentation**

  - Updated machine-output and machine-format docs to match the frozen 1.0 contract
  - Added explicit JSON and NDJSON examples across:
    - config
    - pipeline
    - version
    - registry
  - Finalized machine-output naming conventions and documented them explicitly
  - Updated registry command docs with correct shapes and examples
  - Roadmap updated to:
    - mark machine-output work as complete
    - reflect contract freeze
    - narrow remaining work to CLI/human-output

### Fixed - 1.0.0a3

- **Runtime import failure in isolated environments**

  - Resolved `ModuleNotFoundError` for `typing_extensions`
  - Prevented failures in:
    - pre-commit hooks
    - fresh virtual environments
    - minimal CI environments

- **Registry machine-output inconsistencies**

  - Fixed asymmetries between filetypes, processors, and bindings outputs
  - Corrected JSON structure mismatches with documented contract

### Notes - 1.0.0a3

- Machine output is now **fully finalized, tested, and documented** for 1.0.
- The runtime dependency model is now **explicit and reliable across environments**.
- This release completes the **machine-output track** and stabilizes packaging behavior.
- Remaining work before 1.0 is focused on:
  - CLI / human-output consistency
  - final contract freeze decisions
  - line-ending policy audit

______________________________________________________________________

## [1.0.0a2] - 2026-04-21

This second **1.0 alpha release** finalizes the internal configuration-validation model, strengthens
machine-output and test coverage, and hardens the release workflow.

The focus of `1.0.0a2` is **internal contract completion and release-path reliability**:

- configuration validation now uses a **staged validation log model** internally,
- flattened diagnostics are now strictly a **boundary-level compatibility view**,
- test coverage and helpers were expanded to support the new validation model,
- release automation is now **fully deterministic and ambiguity-safe**,
- documentation and roadmap now reflect the **true 1.0 contract and stabilization status**.

This alpha continues the transition from large-scale refactoring to **final contract validation
before 1.0**.

### Highlights - 1.0.0a2

- Staged validation logs as the single internal representation of config diagnostics
- Removal of duplicated flattened diagnostics state from config models
- Boundary-only flattening at exception, presentation, and machine-output layers
- Strengthened machine-output and validation test coverage
- Improved JSONC file-type handling with native `.jsonc` support and safer ambiguous
  `.json`-as-JSONC detection
- Hardened artifact-based release workflow with strict tag preflight rules
- Fully aligned documentation and roadmap for 1.0 contract freeze

### Added - 1.0.0a2

- **Configuration / validation**

  - Staged validation log model with explicit stages:
    - TOML-source diagnostics
    - merged-config diagnostics
    - runtime-applicability diagnostics
  - New validation-log helpers and test utilities for:
    - stage-level assertions
    - diagnostic count validation
  - Focused test module for `ConfigValidationError` behavior and staged summaries

- **Testing**

  - Shared JSON and NDJSON parsing helpers for machine-output tests
  - Dedicated machine-output test coverage for:
    - config commands
    - pipeline commands
    - version command (JSON + NDJSON)
  - Reorganized TOML schema validation tests into focused modules

- **File types / JSONC**

  - Added a native built-in `jsonc` file type for `.jsonc` extension files.
  - Renamed the former content-detected `.json` JSONC variant from `jsonc` to `json-as-jsonc`.

### Changed - 1.0.0a2

- **Configuration / validation model**

  - Removed stored flattened diagnostics from `Config` and `MutableConfig`
  - Staged validation logs are now the **single source of truth**
  - Flattened diagnostics are now derived **only at boundaries**
  - Validity checks now evaluate all staged diagnostics consistently
  - `ConfigValidationError` now:
    - consumes staged logs
    - summarizes per-stage diagnostics
    - exposes flattened compatibility diagnostics at the exception boundary

- **Machine output**

  - Config/TOML diagnostics continue to use the **flattened `{level, message}` contract**
  - Machine output now consistently derives diagnostics from staged validation logs
  - Machine-output test suite refactored for shared parsing and clearer assertions

- **Documentation**

  - Full alignment of configuration and validation documentation with staged model
  - Introduced canonical documentation snippet for validation contract wording
  - Roadmap updated to reflect completed staged-validation refactor and 1.0 freeze decisions

- **Release workflow**

  - Enforced **single release-tag per commit** preflight rule
  - Release workflow now:
    - skips when no matching tag is present
    - fails when multiple matching tags exist
  - Improved determinism and debuggability of release preflight

- **JSON / JSONC handling**

  - Plain `json` remains unheaderable / `skip_processing=True`.
  - JSON-like pre-insert checking is now limited to the ambiguous `json-as-jsonc` case instead of
    applying JSON-promotion logic to native `.jsonc` files.
  - Processor-path resolution and tests now distinguish native `.jsonc` handling from ambiguous
    `.json` files detected as JSONC by content.

### Removed - 1.0.0a2

- Stored flattened diagnostics fields from configuration models
- Redundant synchronization logic between staged and flattened diagnostics
- Legacy reliance on flattened diagnostics as internal state

### Fixed - 1.0.0a2

- Consistency of config-validation behavior across CLI, API, and machine-output paths
- JSONC handling for real `.jsonc` files, which could previously be blocked by JSON-promotion logic
  intended only for ambiguous `.json` inputs
- Release workflow ambiguity when multiple tags pointed to the same commit
- Documentation inconsistencies around validation behavior and strictness semantics

### Notes - 1.0.0a2

- The **staged validation model is now complete internally** and considered stable for 1.0.
- The **flattened diagnostics contract remains the official 1.0 public surface**.
- `strict_config_checking` remains unchanged and continues to apply across staged validation.
- This release further reduces internal duplication and aligns implementation with documented
  architecture.

TopMark is now firmly in the **final 1.0 stabilization phase**, with remaining work focused on
contract freeze, coverage completion, and selected feature decisions (notably in-memory pipeline).

______________________________________________________________________

## [1.0.0a1] - 2026-04-18

This first **1.0 alpha release** consolidates the large pre-1.0 refactor series into a coherent
release candidate for wider testing. It introduces major architectural cleanup across the registry,
resolution, CLI/presentation, configuration/runtime, machine-output, and release/tooling layers.

The focus of `1.0.0a1` is **contract stabilization**:

- registry identities and bindings are now explicit and namespace-aware,
- CLI, presentation, and machine-output responsibilities are more cleanly separated,
- configuration now follows a documented **TOML → Config → Runtime** split,
- developer and release workflows now use an **uv-first / nox-based** model,
- package versioning is now derived from **Git tags via `setuptools-scm`**.
- release automation now follows an **artifact-based CI → release workflow split**, where CI builds
  and uploads artifacts and the privileged release workflow verifies and publishes them.

This alpha is intended for validation of the new 1.0 architecture and observable contracts before
the final 1.0 release.

> [!CAUTION] **Breaking changes**
>
> - Registry and resolution behavior now use explicit namespace-aware bindings and qualified
>   identities.
> - Configuration is split across TOML loading, layered config construction, and runtime execution.
> - Machine-output contracts were realigned across config, pipeline, registry, and version commands.
> - Developer and release workflows moved to a uv-first / nox-based model with SCM-derived versions
>   and artifact-based publishing.

### Breaking Changes - 1.0.0a1

- **Registry / resolution model:**

  - Built-in processor registration no longer relies on import-time decorators or bootstrap
    scanning. Processor/file-type relationships now use an explicit **binding model**.
  - Registry responsibilities are now explicitly split across:
    - file types,
    - processors,
    - bindings,
    - and a thin façade.
  - File types and processors now expose **namespace-aware stable identities** with canonical
    `qualified_key` values.
  - Unqualified file type identifiers may now be treated as **ambiguous** where multiple namespaces
    overlap; callers must be prepared for explicit ambiguity handling.
  - Registry machine and human outputs are now **identity-focused** and expose
    namespace/qualified-key metadata.
  - A first-class `bindings` view is now part of the registry surface.

- **Config / TOML / runtime boundary:**

  - Configuration concerns are now explicitly separated into:
    - `topmark.toml.*` for TOML loading, source resolution, defaults/templates, and whole-source
      TOML validation,
    - `topmark.config.*` for layered config construction, merge semantics, and effective per-path
      resolution,
    - `topmark.runtime.*` for execution-only runtime state.
  - Package/runtime behavior no longer depends on conflating layered configuration with
    execution-time intent.
  - The old boolean mutation policy pair (`add_only` / `update_only`) has been replaced by the
    scalar `header_mutation_mode` model.
  - Source-local TOML options such as `strict_config_checking` are now treated explicitly as
    **TOML-source-local config-loading options**, not as layered `Config` fields.
  - Whole-source TOML validation is now stricter and happens earlier in the load path; malformed or
    unknown TOML structure now surfaces consistently as diagnostics.

- **CLI / output / machine-format contracts:**

  - CLI output architecture has been refactored around a clearer split between:
    - Click-free human presentation,
    - CLI console/runtime helpers,
    - and domain-scoped machine serializers.
  - Machine-output generation is no longer constructed ad hoc in CLI commands.
  - Machine-output contracts were realigned across config, pipeline, registry, and version commands.
  - Pipeline summary machine output now uses explicit flat rows with:
    - `outcome`
    - `reason`
    - `count`
  - `config check` machine output now consistently uses the explicit `config_check` payload/record
    kind.
  - Human output behavior was also normalized:
    - dry-run/apply semantics are now explicit,
    - summary grouping is outcome-driven,
    - verbosity behavior is more clearly defined.

- **Developer / release workflow:**

  - tox support was removed; contributors and CI now use **nox** with **uv-backed** environments.
  - The project no longer maintains committed `requirements*.txt` / `constraints.txt` as its primary
    dependency workflow.
  - `uv.lock` is now the canonical committed lock artifact.
  - Package versioning no longer uses a manually maintained static `[project].version` in
    `pyproject.toml`.
  - TopMark now derives package versions from Git tags via `setuptools-scm`, and release validation
    checks the **SCM-derived artifact version** against the release tag.
  - The GitHub release pipeline has been restructured to an **artifact-based model**:
    - CI (`ci.yml`) builds and uploads `sdist` and `wheel` artifacts on tag pushes in an
      unprivileged context.
    - The release workflow (`release.yml`) runs in a privileged `workflow_run` context, downloads
      these artifacts, verifies tag/version consistency and checksums, and publishes them.
  - Repository code is no longer built or executed in the privileged release workflow; only prebuilt
    CI artifacts are used for publishing.
  - Compact PEP 440-style prerelease tags (`vX.Y.ZaN`, `vX.Y.ZbN`, `vX.Y.ZrcN`) are now the
    preferred form for new releases, while legacy dashed prerelease tags remain supported for
    backward compatibility.

### Highlights - 1.0.0a1

- Explicit, namespace-aware registry architecture with canonical qualified identities
- Shared resolution layer for file discovery and file-type binding resolution
- Clean CLI/presentation/machine-output separation
- Fully documented TOML → Config → Runtime architecture
- Stable preview vs apply semantics across pipeline and API
- uv-first / nox-based developer and CI workflow
- Git-tag-driven SCM versioning via `setuptools-scm`
- Broad documentation alignment across contributor, CI, machine-output, and command-reference pages

### Added - 1.0.0a1

- **Registry & resolution**

  - Explicit processor/file-type binding model and canonical binding registry
  - Namespace-aware file type and processor identities
  - Dedicated `topmark.resolution` package for:
    - file-input resolution
    - file-type / binding resolution
  - First-class registry bindings command/output
  - Dedicated resolution documentation for path-based resolution and ambiguity handling

- **Presentation / output**

  - New `topmark.presentation` package for Click-free human-facing rendering
  - Shared presentation reports and pure `render_*()` helpers
  - Shared CLI console/runtime helpers and validators
  - Extended machine metadata including `detail_level`

- **Configuration / machine output**

  - Layered configuration provenance export for `config dump --show-layers`
  - `config_provenance` machine output for layered dumps
  - Explicit whole-source TOML validation before layered config deserialization
  - Stronger typed machine schemas across config, pipeline, and registry domains

- **Tooling / CI / release**

  - Shared local composite GitHub Action for Python + uv + nox bootstrap
  - Dependabot support for GitHub Actions and uv-managed Python dependencies
  - Built-site link checking as part of CI/release gating
  - Generated package version metadata via `topmark/_version.py`
  - Artifact-based release pipeline using GitHub Actions (`workflow_run`) with CI-produced artifacts
    (`dist/` + release metadata) consumed by the release workflow

### Changed - 1.0.0a1

- **Registry architecture**

  - Removed legacy bootstrap/discovery registration flow for built-in processors
  - Canonical qualified identity is now the default internal model
  - File-type resolution and binding selection are deterministic and ambiguity-aware

- **CLI / presentation**

  - Replaced the older emitter split with a clearer three-layer output architecture
  - Moved verbosity/color options from the root CLI group to individual commands
  - Standardized human rendering flow across commands
  - Registry human output is now cleanly split into:
    - file types
    - processors
    - bindings

- **Configuration / runtime**

  - Completed the TOML/config/runtime split
  - Refactored override handling around typed override objects
  - Unified policy override routing across CLI and API
  - Clarified and documented current `strict_config_checking` behavior
  - Per-path effective config resolution is now implemented and used by the pipeline engine

- **Policy / pipeline behavior**

  - Replaced legacy mutually exclusive mutation booleans with `HeaderMutationMode`
  - Improved empty / empty-like file handling and insert policy semantics
  - Standardized preview vs apply semantics end-to-end
  - Outcome summaries now preserve `(outcome, reason, count)` explicitly

- **Developer workflow**

  - Migrated project automation fully from tox to nox
  - Completed the shift to a uv-first dependency and environment model
  - Updated Read the Docs, CI, release automation, and contributor docs to match the new workflow

- **Packaging / release**

  - Package versioning is now SCM-derived from Git tags
  - Release workflow now validates **CI-built artifacts** (wheel + sdist) against the resolved
    release tag
  - Release orchestration is now split into explicit preflight/details/publish stages, with a strict
    separation between build (CI) and publish (release workflow)

### Removed - 1.0.0a1

- Legacy built-in processor bootstrap / decorator registration path
- `topmark.processors.bootstrap`
- `topmark.processors.registry`
- `topmark.registry.resolver`
- tox support and `tox.ini`
- Committed `requirements*.txt` / `constraints.txt` dependency-management workflow
- Static package version maintenance in `pyproject.toml`
- Legacy CLI/machine-output construction paths that mixed rendering, serialization, and console I/O

### Fixed - 1.0.0a1

- Namespace-aware configured file-type filtering in file-input resolution
- Resolver behavior when include/exclude file type collections are empty
- Deterministic tie-break handling for overlapping file-type candidates
- Python < 3.12 compatibility issues in CLI output code paths
- PathSpec deprecation warnings in file-resolution logic
- Markdown formatter/plugin alignment across local, CI, and editor environments
- Taplo configuration layout so CLI/editor integrations consume the same source of truth
- Schema/doc drift in pipeline and config machine-output documentation
- `config check` machine-output naming drift (`config_check` vs generic summary wording)
- Empty-file, empty-like-file, and placeholder handling so insert/strip/apply behavior remains
  idempotent and understandable
- Built-site docs/linkcheck reliability in CI and release workflows

### Notes - 1.0.0a1

- This is the **first 1.0 alpha release**, intended to validate the new architecture and observable
  contracts before 1.0 final.
- Public API and machine-output consumers should review the breaking changes above carefully,
  especially around:
  - registry identity/output,
  - config/TOML/runtime boundaries,
  - machine-format payloads,
  - release/developer workflow expectations.
- New prereleases should prefer compact PEP 440-style tags such as `v1.0.0a1`, `v1.0.0b1`, and
  `v1.0.0rc1`.
- Some 1.0 freeze/rehearsal items remain tracked in `docs/dev/roadmap.md`; this alpha marks the
  transition from large-scale refactor work to final contract validation and release-path rehearsal.

______________________________________________________________________

## [0.11.1] - 2026-01-18

This patch release focuses exclusively on **developer tooling, CI reliability, and release
automation**. There are **no user-facing or runtime behavior changes** relative to 0.11.0.

### Changed - 0.11.1

- **CI / developer automation migrated from tox to nox (uv-backed)**

  - Removed `tox` support entirely and dropped `tox.ini`.
  - Introduced a first-class `noxfile.py` defining all project automation:
    - Formatting and linting gates
    - Test + Pyright QA sessions
    - API snapshot validation
    - Documentation builds and link checking
    - Packaging sanity checks
    - Deterministic and full release gates
  - Switched all GitHub Actions workflows to bootstrap and run **Nox** instead of tox.
  - Enabled **uv-backed virtualenv creation and syncing** for faster CI and local runs.
  - Centralized Python version resolution in `noxfile.py`, derived from `pyproject.toml`.

- **Makefile streamlined to delegate orchestration to nox**

  - Updated targets (`verify`, `test`, `qa`, `qa-api`, `links`, `package-check`, `release-check`,
    `release-full`) to call nox sessions directly.
  - Added support for parallel per-Python release QA via `make -j`.

- **Release workflow hardening**

  - Release gates now reuse the same nox sessions as CI for consistency.
  - Packaging, docs, and QA checks are enforced uniformly for both release candidates and final
    releases.
  - Pre-releases (`-rc`, `-a`, `-b`) automatically publish to **TestPyPI**; finals publish to
    **PyPI**.

### Fixed - 0.11.1

- **Nox bootstrap robustness on Python < 3.11**

  - Ensured `noxfile.py` can be imported on Python 3.10 by:
    - Using stdlib `tomllib` on Python 3.11+
    - Falling back to `tomli` on older interpreters (as provided by nox itself)
  - Prevented CI failures caused by missing TOML parsers during nox bootstrap.
  - Clarified via inline comments that TOML parsing in `noxfile.py`:
    - Happens at **nox import/bootstrap time**
    - Relies only on tooling dependencies, not TopMark runtime dependencies

### Notes - 0.11.1

- This release **does not change TopMark's runtime behavior, public API, or CLI output**.
- The migration affects **developers and CI only**.
- Existing users upgrading from 0.11.0 require no action.

______________________________________________________________________

## [0.11.0] - 2026-01-15

This release introduces a set of **internal architectural improvements** that strengthen policy
correctness, STDIN handling, and CLI/API parity. While user-facing behavior remains compatible with
the 0.10.x series, there is an **intentional internal breaking change** for integrators relying on
TopMark internals.

> [!CAUTION] **Breaking changes**
>
> - `ProcessingContext.bootstrap()` now requires an explicit `PolicyRegistry`.
> - Internal pipeline bootstrapping and test harness setup must construct a `PolicyRegistry`.
> - Public CLI and `topmark.api` entry points remain source-compatible.

### Breaking Changes - 0.11.0

- **PolicyRegistry is now mandatory at pipeline bootstrap time**

  - `ProcessingContext.bootstrap()` now **requires a `PolicyRegistry` argument**.
  - Internal callers must construct a `PolicyRegistry` from the resolved `Config` and pass it
    explicitly when bootstrapping a context.
  - This removes ad-hoc policy resolution, eliminates repeated per-context merging, and guarantees
    deterministic effective policy selection across all pipeline steps.

  > **Note:** This affects **internal and test code only**. The public API (`topmark.api.check`,
  > `topmark.api.strip`, CLI commands) remains source-compatible.

### Changed - 0.11.0

- **Policy evaluation**

  - Introduced `PolicyRegistry` to precompute effective policies (global + per-file-type) once per
    run.
  - Centralized all effective-policy lookups via `ctx.get_effective_policy()`.
  - Removed per-context caching and `None`-guarded policy fallbacks.
  - Ensured strip eligibility and guidance are based on the strip axis and effective policy,
    independent of comparison status.

- **Outcome bucketing**

  - Refactored outcome bucketing into a **precedence-ordered classifier** with first-match-wins
    semantics.
  - Added stable debug tags (`bucket[...]`) for easier diagnosis of complex bucketing paths.
  - Normalized bucket labels and reduced duplication across header/comparison/strip reasons.

- **CLI / config / runtime alignment**

  - Unified write-mode semantics across CLI, config, and writer:
    - CLI `write_mode` now cleanly maps to `OutputTarget` + `FileWriteStrategy`.
    - STDIN content mode consistently forces STDOUT output and clears file write strategies.
    - Explicit diagnostics are emitted when config or CLI settings are overridden due to STDIN.
  - Renamed `stdin` → `stdin_mode` throughout CLI, config, API, and runtime for clarity.
  - Propagated `stdin_filename` so STDIN-backed runs participate correctly in config discovery,
    policy evaluation, and file resolution.
  - Centralized STDIN-related normalization in `MutableConfig.sanitize()` to enforce invariants
    before freezing and avoid duplicated CLI-only logic.

- **Enums & config parsing**

  - Introduced a stable, machine-keyed enum pattern (`KeyedStrEnum`) for config-facing enums
    (`OutputTarget`, `FileWriteStrategy`).
  - Decoupled machine identifiers from human-readable labels and removed brittle
    string/Literal-based parsing.
  - Standardized `.parse()` helpers for config and CLI normalization.

- **Writer behavior**

  - Updated `WriterStep.may_proceed()` to respect apply intent, output target, and STDIN mode
    consistently instead of relying on ad-hoc checks.
  - Ensured writer eligibility rules are enforced uniformly across CLI and API runs.

- **API runtime parity**

  - Aligned API runtime behavior with CLI behavior by applying the same config discovery,
    normalization, and policy overlays.

### Fixed - 0.11.0

- **CLI guidance correctness**
  - Made `check` and `strip` per-file guidance policy-aware and feasibility-aware.
  - Prevented misleading "run --apply ..." suggestions when policy or feasibility blocks changes,
    especially for empty files and strip-only scenarios.

### Internal - 0.11.0

- Updated pipeline and API tests to bootstrap contexts via `PolicyRegistry`.
- Added shared helpers to keep test setup DRY and consistent across pipeline, API, and CLI tests.

### Notes - 0.11.0

- There are **no user-facing breaking changes** relative to 0.10.x.
- The public API surface remains stable, but **internal consumers and test harnesses must be
  updated** to construct and pass a `PolicyRegistry` when bootstrapping pipeline contexts.

______________________________________________________________________

## [0.10.1] - 2025-11-20

This patch release republishes the intended `0.10.0` release with two commits that were accidentally
omitted from the PyPI artifact.\
There are **no functional code changes** relative to `0.10.0`; this release only corrects packaging
and metadata.

### Changed - 0.10.1

- **Tooling & dependency maintenance**

  - Updated `.pre-commit-config.yaml` with the latest versions of:
    - `mdformat` 1.0.0 (migrated to `mdformat-gfm`)
    - `ruff-pre-commit` v0.14.x
    - `pydoclint` 0.8.x
    - `pyright-python` v1.1.407
  - Tightened dependency ranges in `pyproject.toml` and regenerated `requirements*.txt` via
    pip-tools.

- **Metadata**

  - Added the `0.10.0` CHANGELOG entry that was missing in the PyPI package.
  - Set the project version to `0.10.0` in `pyproject.toml` for the corrected build.

### Notes - 0.10.1

This release contains **only packaging, metadata, and dependency housekeeping**.\
All functionality, schemas, and breaking changes remain exactly as described in **0.10.0**.

______________________________________________________________________

## [0.10.0] - 2025-11-20

This release introduces **major pipeline and CLI changes**, a full **machine-output schema
redesign**, a refactored **ProcessingContext**, and multiple BREAKING CHANGES. It also includes
substantial internal cleanup, dependency updates, and correctness fixes.

> [!CAUTION] **Breaking changes**
>
> - Machine-output JSON and NDJSON schemas were redesigned and are not backward compatible.
> - Internal pipeline module structure and import paths changed.
> - Legacy CLI compatibility commands and code paths were removed.

### Breaking Changes - 0.10.0

- **Machine Output (JSON / NDJSON):**

  - Completely redesigned schema\*\*:
    - All records include a `kind` discriminator (`config`, `config_diagnostics`, `result`,
      `summary`).
    - All records include a top-level `meta` block (version, intent, timestamps).
    - File-level results now use a stable, explicit envelope (`file`, `statuses`, `hints`,
      `diagnostic_counts`, `outcome`).
    - NDJSON encoding is now strictly one-record-per-line with unified keys.
  - **Old JSON/NDJSON formats from \<0.10.0 are no longer emitted.**
  - Downstream tools **must** update their parsers.

- **CLI / Presentation Rendering:**

  - CLI output formatting has been fully rewritten:
    - Bucketing semantics changed (mapping to new axes + unified policy signals).
    - Summary footer replaced with new consistent reporting structure.
    - Changed/unchanged/would-change groupings now computed via the new comparison axis.
    - Hints are now grouped and severity-ordered; rendering is verbosity-dependent.
  - Legacy formatting and legacy summary behavior have been removed.

- **Pipeline Architecture:**

  - `ProcessingContext` split into:
    - `pipeline.context.model` (state + orchestration),
    - `pipeline.context.policy` (pure policy + feasibility),
    - `pipeline.context.status` (all axis statuses).
  - Legacy modules (`pipeline/context.py`, `pipeline/contracts.py`, etc.) removed.
  - Steps updated to use new context accessors and policy helpers.
  - Any consumer importing internal pipeline modules by path must update imports.

- **Legacy CLI Commands:**

  - Several deprecated commands were **removed entirely**:
    - Old compatibility shims for `topmark header ...`
    - Legacy updater/stripper debug modes.
  - These commands now fail fast with a clear error.

### Highlights - 0.10.0

- Clean separation of pipeline responsibilities (context, policy, status).
- Unified machine-readable output schema supporting stable integrations.
- Significantly clearer CLI output with accurate bucket, hint, and summary logic.
- Simplified type system with uniform abstract collections (`collections.abc`) and Ruff `UP`/`TC`
  enforcement.
- Full modernization of imports, dependency ranges, and development tooling.
- Large suite of correctness fixes across header bounds, scanner, renderer, patcher, and writer.

### Added - 0.10.0

- New `pipeline/context/` package with:
  - `model.py` (ProcessingContext core),
  - `policy.py` (feasibility, effective policy checks, intent validation),
  - `status.py` (HeaderProcessingStatus + axis enums).
- New machine-output builder (`cli_shared.machine_output`) as the single source of truth.
- New structured summary renderer (`topmark.api.view.format_summary`).
- Linting policy section in `CONTRIBUTING.md`.
- Support for GitHub-Flavored Markdown tables via `mdformat-gfm`.

### Changed - 0.10.0

- **`ProcessingContext`:**

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

### Removed - 0.10.0

- `ReasonHint` (unused).
- Legacy updater header code paths.
- Deprecated CLI commands and code paths for pre-0.9 behaviors.
- Legacy summary and bucket rendering pipeline.

### Fixed - 0.10.0

- Correct final newline + BOM + shebang interactions.
- Accurate indentation handling for Markdown/HTML/XML processors.
- Numerous header bound edge cases (multi-header, malformed, block comment variants).
- Writer stability in dry-run and apply modes.
- Accurate tracking of "would change" vs "changed" under mixed policy conditions.
- Corrected normalization for multi-line headers with mixed whitespace.
- Better FileType detection for HTML/Markdown block-comments.

### Notes - 0.10.0

`topmark.api` remains *public and stable*, but all **machine-readable formats** and **internal
pipeline interfaces** changed and require downstream updates. Integrators consuming NDJSON/JSON must
migrate to the new envelopes and keys.

______________________________________________________________________

## [0.9.1] - 2025-10-07

### Highlights - 0.9.1

- **Python 3.14 support (prerelease)** - test matrix, classifiers, and tooling updated for
  3.10-3.14.
- **Tox-first developer workflow** - Makefile simplified to delegate heavy lifting to tox;
  consistent local/CI behavior.
- **Property-based hardening** - Hypothesis harness added for idempotence and edge-case discovery.
- **Robust idempotence & XML/HTML guardrails** - Safer insertion rules and whitespace/newline
  preservation.

### Added - 0.9.1

- **Testing & quality**
  - Hypothesis-based **property tests** for insert→strip→insert idempotence and edge cases across
    common file types.
  - CI **pre-commit** job to run fast hooks on every PR/push (heavy/duplicated hooks handled
    elsewhere).
- **Python versions**
  - CI matrix extended to **3.14** (rc/dev as needed) with `allow-prereleases: true`.

### Changed - 0.9.1

- **Developer workflow**
  - **Makefile overhaul**: now a thin wrapper that delegates to tox envs:
    - Core targets: `verify`, `test`, `pytest`, `property-test`, `lint`, `lint-fixall`, `format`,
      `format-check`, `docs-build`, `docs-serve`, `api-snapshot*`.
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

### Fixed - 0.9.1

- **Idempotence & formatting drift**
  - Preserve user whitespace; avoid collapsing whitespace-only lines (e.g., `" \n"` vs `"\n"`).
  - Normalize handling of the **single blank line** after headers (owned newline only).
  - Respect **BOM** and trailing blanks; collapse only file-style blanks, not arbitrary whitespace.
  - Stripper/Updater: honor content status; avoid unintended rewrites.
- **Insertion safety**
  - Skip reflow-unsafe XML/HTML cases (e.g., single-line prolog/body, NEL/LS/PS scenarios).
  - Mixed line endings are skipped by the reader to avoid non-idempotent outcomes.

### Internal - 0.9.1

- **CI (`ci.yml`)**
  - **Tox-first** for lint (`format-check`, `lint`, `docstring-links`), docs (`docs`), tests
    (`py310...py314`), and API snapshot (`py313-api`).
  - Add caching for **pip** and **.tox** across jobs; add `actions/checkout@v4` before cache
    globbing.
  - New **pre-commit** job; skip heavy/duplicated hooks in that job (`lychee-*`, `pyright`,
    `docstring-ref-links`) since they run in other jobs.
- **Release (`release.yml`)**
  - Build docs via **tox**; add pip/.tox caching to **build-docs** and **publish-package**.
- **Docs**
  - Refresh **CONTRIBUTING.md**, **INSTALL.md**, **README.md**, and **docs/dev/api-stability.md** to
    match the tox/Makefile workflow.
  - New CI/release workflow docs; fix broken links to workflow YAMLs.

### Notes - 0.9.1

- We've moved from pure **venv** workflows (`.venv`, `.rtd`) to a **tox-based** model.
  - Please **delete** any old `.venv` and `.rtd` directories.

  - If you want IDE/Pyright import resolution, recreate only the **optional** editor venv:

    ```bash
    make venv && make venv-sync-dev
    ```

  - Use `make verify`, `make test`, `make pytest [PYTEST_PAR="-n auto"]`, `make docs-*`,
    `make api-snapshot*`, and the `lock-*` targets for daily work.

______________________________________________________________________

## [0.9.0] - 2025-10-06

TopMark 0.9.0 consolidates its configuration system, aligns CLI and API behavior, and modernizes the
documentation pipeline. Config resolution, discovery anchors, and formatting flags now work
predictably across CLI, API, and generated docs.

### Highlights - 0.9.0

- **Configuration resolution finalized** - TopMark now fully supports layered config discovery with
  deterministic merge precedence, explicit anchor semantics, and path-aware pattern resolution.
- **Docs & MkDocs rebuild** - Documentation migrated to a snippet-driven architecture with reusable
  callouts, dynamic version injection, and a modernized MkDocs toolchain.
- **CLI alignment fix** - The `--align-fields` flag is now tri-state, preserving `pyproject.toml`
  defaults when the flag is omitted.
- **Public API parity** - The Python API now mirrors CLI behavior, respecting discovery, precedence,
  and formatting options such as `align_fields`.
- **Note:** Config discovery and precedence are now finalized; projects that relied on implicit or
  CWD-only behavior may see changes in which configuration takes effect.\
  See [**Configuration → Discovery & Precedence**](docs/configuration/discovery.md).

### Added - 0.9.0

- **Configuration system**
  - Complete implementation of **layered discovery**:
    - Precedence: defaults → user → project chain (`root → cwd`; per-dir: `pyproject.toml` →
      `topmark.toml`) → `--config` → CLI.
    - **Discovery anchor** = first input path (or its parent if file) → falls back to CWD.
    - **`root = true`** stops traversal; ensures predictable isolation.
  - Added `PatternSource` abstraction for tracking pattern bases.
  - Added `MutableConfig.load_merged()` and detailed docstrings for all discovery steps.
  - New test suite `tests/config/test_config_resolution.py` for full coverage of anchors, globs, and
    precedence.
- **Header rendering**
  - Conditional field alignment via `config.align_fields` in
    `HeaderProcessor.render_header_lines()`.
- **API**
  - Public API functions use the authoritative discovery and merge logic.
  - Added `tests/api/test_api_discovery_parity.py` to guarantee CLI/API parity.
- **MkDocs & docs**
  - Introduced snippet-based reusable callouts (`> [!NOTE]`) rendered through a custom **simple
    hook**.
  - Added `docs/hooks.py` to convert callouts and inject `%%TOPMARK_VERSION%%` dynamically.
  - Added `docs/_snippets/config-resolution.md` for consistent "How config is resolved" sections.
  - Automated generation of API reference pages for `topmark.api` and `topmark.registry`.
  - Updated `mkdocs.yml` plugin chain (include-markdown, simple-hooks, md_in_html, gen-files).
  - Added dynamic version display in docs (via `pre_build` hook).

### Changed - 0.9.0

- **CLI**
  - `--align-fields` is now **tri-state** (`True`, `False`, `None`)-when omitted, TOML defaults are
    respected.
  - `topmark dump-config` and all CLI flows now reflect the effective runtime configuration.
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

### Fixed - 0.9.0

- **Config precedence bug** - Same-directory order (`pyproject.toml` before `topmark.toml`) was
  previously inverted; now fixed via per-directory grouping.
- **CLI override bug** - `--align-fields` no longer forces `false` when omitted; correctly inherits
  TOML default.
- **Header alignment** - Processors no longer align fields when `align_fields = false`.
- **Docs build** - Resolved missing MkDocs plugin errors in CI (`include-markdown` and
  `simple-hooks`).
- **Lychee false positives** - Updated snippet links and exclusion list to prevent link-checker
  failures.
- **Version token substitution** - The documentation now correctly substitutes `%%TOPMARK_VERSION%%`
  via pre-build hook.

### Documentation - 0.9.0

- Overhauled `pyproject.toml` `[project.optional-dependencies].docs` section to include all MkDocs
  plugins.
- Added `requirements-docs.txt` synced with `pyproject.toml` extras for CI.
- CI and release workflows (`ci.yml`, `release.yml`) now install docs extras (`-e .[docs]`) with
  constraints.
- Bumped doc dependencies: `mkdocs>=1.6.0`, `mkdocs-material>=9.5.19`, `pymdown-extensions>=10.16`.
- Removed obsolete `.mdformat.yml` and outdated constraints for `backrefs` and `markdown-it-py`.

> [!CAUTION] **Breaking changes**
>
> - No intentional public breaking changes in this release.
> - Configuration discovery and precedence behavior was finalized and may affect effective config
>   resolution in some repositories.

### Breaking Changes - 0.9.0

None (pre-1.0).\
All changes are backward-compatible with v0.8.x configurations and APIs.

______________________________________________________________________

## [0.8.1] - 2025-09-26

### Highlights - 0.8.1

- **XML re-apply fix**: prevent double-wrapped `<!-- ... -->` blocks by anchoring bounds via
  character offset for XML/HTML processors.

### Added - 0.8.1

- **Developer validation (opt-in)**: set `TOPMARK_VALIDATE=1` to validate:
  - Processor ↔ FileType registry integrity.
  - XML-like processors use the char-offset strategy (`NO_LINE_ANCHOR` for line index).
- **Docs**:
  - Placement strategies (line-based vs char-offset) documented in `base.py` / `xml.py`.
  - New page `docs/ci/dev-validation.md`; CONTRIBUTING updated.

### Changed - 0.8.1

- **Processor refactor**:
  - Introduce mixins: `LineCommentMixin`, `BlockCommentMixin`, `XmlPositionalMixin`.
  - Add `compute_insertion_anchor()` façade and route updater through it.
  - Tighten typing (`Final[int]` for `NO_LINE_ANCHOR`; stricter annotations) and micro-perf (cache
    compiled encoding regex).
- **File types**:
  - Instances module made lazy, plugin-aware, and type-safe; detectors split out (JSONC).

### Fixed - 0.8.1

- **XML idempotency**: re-apply no longer nests comment fences.
- **Type checking & mypy**: generator return, entrypoint discovery, and strict typing cleanups.

### Internal - 0.8.1

- **New CI job**: "Dev validation" runs only tests marked `dev_validation` with
  `TOPMARK_VALIDATE=1`.
- **Pre-commit**: bump `ruff-pre-commit` to `v0.13.2`.

______________________________________________________________________

## [0.8.0] - 2025-09-24

### Highlights - 0.8.0

- **New C-style block header support**: introduce `CBlockHeaderProcessor` and register it for **CSS,
  SCSS, Less, Stylus, SQL, and Solidity**.
- **Python stubs**: `.pyi` now use `PoundHeaderProcessor` (`#`-style), with sensible defaults (no
  shebang).

### Added - 0.8.0

- **Processors**
  - `CBlockHeaderProcessor` (C-style `/* ... */` with per-line `*`) including tolerant directive
    detection (accepts `* topmark:...` or bare `topmark:...`).
  - File type registrations: `css`, `scss`, `less`, `stylus`, `sql`, `solidity`.
- **File types**
  - `python-stub` (`.pyi`) bound to `PoundHeaderProcessor` (shebang disabled; ensure blank after
    header).
- **Tests**
  - Comprehensive `test_cblock.py` suite: insertion (top and not-at-top), tolerant detection,
    idempotency, CRLF preservation, strip (auto/explicit span), and parametric checks across
    registered extensions.

### Changed - 0.8.0

- **Typing hardening (non-functional)**
  - Widespread strict typing across `pipeline/`, `cli/` & `cli_shared/`, remaining `src/` modules,
    and `tools/`:
    - Adopt postponed annotations; move type-only imports under `TYPE_CHECKING`.
    - Introduce `TopmarkLogger` annotations; add precise return/locals typing.
    - Minor import and hygiene cleanups for Pyright strict mode.

### Fixed - 0.8.0

- **CLI `processors` command**
  - Treat `filetypes` as dicts in `--long` + Markdown/default renderers to avoid `AttributeError`
    when running\
    `topmark processors --format markdown --long`.
- **Typing**
  - Resolve a redefinition error from an incorrectly placed annotation in types code.

### Documentation - 0.8.0

- **README.md**: mention block (`/* ... */`) alongside line (`#`, `//`) comment styles; add a CSS
  example.
- **docs/usage/filetypes.md**: expand processor table with modules and registered file types; add
  `CBlockHeaderProcessor`.

### Internal - 0.8.0

- Add standard TopMark headers to files in `typings/`.
- Dev tooling: keep pre-commit/hooks in sync (see commit history for exact bumps).

______________________________________________________________________

## [0.7.0] - 2025-09-23

### Highlights - 0.7.0

- **Version CLI overhaul**: `topmark version` now defaults to **PEP 440** output and supports
  multiple formats via `--format {pep440,semver,json,markdown}` (alias: `--semver`).
- **Release hardening**: Fully revamped GitHub Actions release flow with strict gates (version/tag
  match, artifact checks, **docs must build**, TestPyPI for prereleases, PyPI for finals).

### Added - 0.7.0

- **CLI - `version` command**
  - `--semver` option to render a **SemVer** view while keeping **PEP 440** as the default.
  - `--format json|markdown|pep440|semver` with standardized outputs.
  - `topmark.utils.version.pep440_to_semver()` with graceful fallback.
- **Tests**
  - Expanded/parameterized tests for `version` across text/JSON/Markdown (PEP 440 vs SemVer).

### Changed - 0.7.0

- **CLI output (breaking schemas; see "Breaking" below)**
  - **JSON** schema is now:

    ```json
    {"version": "<str>", "format": "pep440|semver"}
    ```

  - **Markdown** now includes the format label:

    ```markdown
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

### Fixed - 0.7.0

- N/A (no user-visible fixes included in this release; tests/docs/tooling updates only).

### Documentation - 0.7.0

- New & updated workflow docs:
  - `docs/ci/release-workflow.md` (RC vs final, gates, publishing).
  - `CONTRIBUTING.md` (CI expectations, local checks).
- `README.md` and `docs/index.md` examples updated for the new `version` outputs.

### Removed - 0.7.0

- Duplicate "Build docs (strict)" step from the `lint` job.
- Stray `topmark.toml` at repo root.

### Internal - 0.7.0

- Adopt pinned lockfiles (`requirements.txt`, `requirements-dev.txt`, `requirements-docs.txt`) and
  `constraints.txt`.
- Cache keyed on lockfiles; consistent `python -m pip` usage.
- Pre-commit: bump `topmark-check` hook to v0.6.2.
- Minor `tox.ini` whitespace tidy-ups.

> [!CAUTION] **Breaking changes**
>
> - The `version` command JSON and Markdown output schemas changed.
> - Consumers parsing previous machine or Markdown output formats must update their parsers.

### Breaking Changes - 0.7.0

- **JSON** schema changed from `{"topmark_version": "<str>"}` to
  `{"version": "<str>", "format": "pep440|semver"}`.
- **Markdown** now explicitly includes the format label:\
  `**TopMark version (pep440|semver): <version>**`.\
  Update any consumers/parsers that relied on the previous key or phrasing.

### Notes - 0.7.0

- For RCs: keep `pyproject.toml` at `0.7.0rcN` and tag `v0.7.0-rcN` to publish to TestPyPI.
- For GA: bump to `0.7.0`, tag `v0.7.0`, and the workflow publishes to PyPI after docs/tests gates.
- `0.7.0-rc1` and `0.7.0-rc2` were published to **TestPyPI** for validation; their contents are
  fully included in this final release.

______________________________________________________________________

## [0.6.2] - 2025-09-15

### Fixed - 0.6.2

- **Docs build**: resolve Griffe parsing error by normalizing a parameter docstring format (remove
  stray space before colon) for `skip_compliant` in `topmark.api.check()` (file:
  `src/topmark/api/__init__.py`). This unblocks MkDocs/ReadTheDocs builds. No functional code
  changes.

______________________________________________________________________

## [0.6.1] - 2025-09-15

### Added - 0.6.1

- **Docstring link checker**: new `tools/check_docs_hygiene.py` to enforce reference-style object
  links and flag raw URLs in docstrings. Includes accurate line/range reporting, code-region
  masking, and CLI flags `--stats` and `--ignore-inline-code`.
- **Makefile targets**: `docstring-links`, `links`, `links-src`, `links-all`; centralized
  `check-lychee` gate.

### Changed - 0.6.1

- **MkDocs build**: enable `strict: true` and link validation to fail on broken internal links.
- **Docstrings/x-refs**: convert internal references to mkdocstrings+autorefs style (e.g.,
  `` [`pkg.mod.Object`][] `` or `[Text][pkg.mod.Object]`) and prefer fully-qualified names.
- **Docs structure**: normalize mkdocstrings blocks (minor tidy-ups).

### Fixed - 0.6.1

- **README**: correct the "Adding & updating headers with topmark" link to
  `docs/usage/commands/check.md`.

### Internal - 0.6.1

- **Lychee integration**: adopt Lychee for link checks (local + CI); scoped pre-commit hooks.
- **Testing**: raise `pytest` minimum to `>=8.0` in the `test` optional dependencies.
- **Refactors**: minor non-functional cleanups (rename local import alias in filetype registry;
  small typing improvements).

______________________________________________________________________

## [0.6.0] - 2025-09-12

### Added - 0.6.0

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

### Changed - 0.6.0

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

### Fixed - 0.6.0

- CLI and pipeline now reflect header order deterministically (no "up-to-date" false negatives when
  order differed). (Commit: `d778ace`)
- Type-checking and lint issues (casts, variable redefinitions, analyzer false positives) resolved
  in CLI helpers and resolver paths. (Commits: `d778ace`, `adc35f9`)

### Documentation - 0.6.0

- Add **"Configuration via mappings (immutable at runtime)"** section to the public API docs and
  mirror a concise note in the `topmark.api` module docstring. (Commit: `d778ace`)
- Normalize docstrings across the codebase; remove Sphinx roles in favor of Markdown-friendly
  mkdocstrings. (Commit: `f649731`)

### Internal - 0.6.0

- Add `pydoclint` to dev toolchain; wire into Makefile and pre-commit.
- Reorder pre-commit hooks for faster feedback.
- Snapshot workflow integrated into Makefile and CI-friendly checks. (Commits: `f649731`, `a584577`)
- Repository-wide header reformat to the new field order (no functional changes). (Commit:
  `bcac2ed`)

### Notes - 0.6.0

- **No public API surface changes**: `topmark.api.check/strip` signatures unchanged.
- `MutableConfig` is **internal** (not part of the stable API); public callers should pass a mapping
  or a frozen `Config`.

______________________________________________________________________

## [0.5.1] - 2025-09-09

### Fixed - 0.5.1

- **Python 3.10/3.11 compatibility**: replace multiline f-strings in CLI output code paths (not
  supported before Python 3.12) with concatenation/temporary variables. Affected commands:
  - `filetypes`: numbered list rendering and detail lines (description/content matcher)
  - `processors`: processor header lines and per-filetype detail lines

### Internal - 0.5.1

- Bump project version to `0.5.1` in `pyproject.toml`.
- Update local pre-commit hook to use TopMark **v0.5.0**.

______________________________________________________________________

## [0.5.0] - 2025-09-09

### Added - 0.5.0

- **Honest write statuses** across the pipeline:
  - Dry-run ⇒ `WriteStatus.PREVIEWED`
  - Apply (`--apply`) ⇒ terminal statuses (`INSERTED`, `REPLACED`, `REMOVED`)
- **Apply intent plumbing** end-to-end:
  - `Config.apply_changes` (tri-state) consumed via `apply_cli_args()` and respected in updater
  - CLI and public API forward **apply** to the pipeline

### Changed - 0.5.0

- **CLI & console output**
  - Decoupled program-output verbosity from internal logging; all user output routed through
    `ConsoleLike`
  - Banners/extra guidance are gated by verbosity (quiet by default; add `-v` for more detail)
  - `filetypes` and `processors` now render numbered lists with right-aligned indices
  - `dump-config` / `init-config`: emit **plain TOML** by default; BEGIN/END markers appear at
    higher verbosity
- **Public API (behavioral)**
  - Apply vs preview now consistently reflected in per-file results (`PREVIEWED` vs terminal write
    statuses)

### Fixed - 0.5.0

- **Pre-commit hooks**: remove redundant `--quiet` (default output is already terse) and fix its
  placement.

### Documentation - 0.5.0

- Refresh CLI docs:
  - Explicit subcommands in examples; stdin examples use `topmark check - ...`
  - Clarify dry-run vs apply summary text (`- previewed` vs `- inserted`/`- replaced`/`- removed`)
  - Add "Numbered output & verbosity" notes to `filetypes` / `processors`
  - Add `version` command page; tidy headings and separators

> [!CAUTION] **Breaking changes**
>
> - Dry-run summaries now use `previewed` instead of terminal mutation verbs.
> - Human-readable CLI output formatting changed and may affect output parsers.

### Breaking Changes - 0.5.0

- Dry-run summaries now end with **`- previewed`** instead of terminal verbs.\
  Update any scripts/tests parsing human summaries that previously matched `- inserted` /
  `- removed` / `- replaced` during dry-run.
- Human-readable CLI output may differ (verbosity-gated banners and numbered lists).

______________________________________________________________________

## [0.4.0] - 2025-09-08

### Added - 0.4.0

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

### Changed - 0.4.0

- **Public API**: `diagnostics` in `RunResult` now returns a mapping
  `dict[str, list[PublicDiagnostic]]` instead of `dict[str, list[str]]`.
- **Summaries**: `ProcessingContext.format_summary()` now aligns with pipeline outcomes and appends
  compact triage (e.g., `1 error, 2 warnings`) plus hints (`previewed`, `diff`).
- **Verbosity handling**: CLI `-v/--verbose` and `-q/--quiet` feed a program-output verbosity level
  separately from the logger level; per-command logger overrides were removed.
- **Config.merge_with()**: `verbosity_level` now honors **override semantics** (other wins), and
  supports tri-state inheritance.
- **API surface**: `PublicDiagnostic` re-exported from `topmark.api` and included in `__all__`.

### Fixed - 0.4.0

- Reader now surfaces an explicit diagnostic for empty files.
- Minor wording/formatting improvements in `classify_outcome()` and summary output.
- Import order cleanup in `pipelines.py`.

### Documentation - 0.4.0

- Expanded inline docstrings for diagnostics, public types, and verbosity semantics.

> [!CAUTION] **Breaking changes**
>
> - `RunResult.diagnostics` now exposes structured diagnostic objects instead of plain strings.
> - New aggregate diagnostic fields were added to `RunResult`.

### Breaking Changes - 0.4.0

- `RunResult.diagnostics` type changed to a structured public form. Integrations consuming plain
  strings should switch to `d["message"]` and may use `d["level"]` for triage.
- New aggregate fields (`diagnostic_totals`, `diagnostic_totals_all`) are added alongside
  `diagnostics`.

______________________________________________________________________

## [0.3.2] - 2025-09-07

### Fixed - 0.3.2

- **Pre-commit hooks**: update TopMark hooks to use the explicit `check` subcommand
  (`topmark check ...`) instead of the removed implicit default command. This restores correct
  behavior for `topmark-check` and `topmark-apply` hooks.

### Documentation - 0.3.2

- Add **API Stability** page and wire it into the MkDocs navigation (`Development → API Stability`).
- Add a stability note/link to `docs/api/public.md` referencing the snapshot policy.

### Internal - 0.3.2

- Bump project version to `0.3.2` in `pyproject.toml`.

______________________________________________________________________

## [0.3.1] - 2025-09-07

### Fixed - 0.3.1

- **Snapshot tests**: stabilize public API snapshot across Python 3.10-3.13 by normalizing
  constructor signatures in tests (`<enum>` for Enum subclasses, `<class>` for other classes) while
  retaining real signatures for callables. Updated baseline `tests/api/public_api_snapshot.json`
  accordingly and refreshed the REPL snippet in the test docstring to generate a
  cross-version-stable snapshot.

______________________________________________________________________

## [0.3.0] - 2025-09-07

### Added - 0.3.0

- **Stable public API surface** under `topmark.api` and `topmark.registry`.
  - Functions: `check()`, `strip()`, `version()`, `get_filetype_info()`, `get_processor_info()`.
  - Result/metadata types: `Outcome`, `FileResult`, `RunResult`, `FileTypeInfo`, `ProcessorInfo`,
    `WritePolicy`.
  - Structural protocols for plugins: `PublicFileType`, `PublicHeaderProcessor`.
  - `Registry` facade for read-only discovery of file types, processors, and bindings.
  - Public API tests and snapshot (`tests/api/public_api_snapshot.json`) to guard semver stability.
    (Commits: `9ddd18e`, `ca5e3d7`)
- **Docs overhaul** for API & internals:
  - New `docs/api/public.md` (stable public API) and `docs/api/internals.md` (internals landing).
  - New `docs/gen_api_pages.py` generator for per-module internals with **breadcrumbs** and
    **first-line summaries**; mkdocs wiring via `mkdocs-gen-files` & `autorefs`.
  - Local typing stub `typings/mkdocs_gen_files/__init__.pyi` so dev envs don't need the plugin.
  - Stability policy & semver guardrails added to CONTRIBUTING. (Commits: `bf67c9e`, `41e2543`)
- **CLI improvement**: re-export `cli` at `topmark.cli` for `from topmark.cli import cli`. (Commit:
  `cb7437f`)
- **New `processors` command** to list registered header processors and their file types (with
  `--long` and `--format default|json|ndjson|markdown`). Shared Click-free `markdown_table` helper
  for Markdown output. (Commits: `8742a46`, `ab346ed`)

### Changed - 0.3.0

- **CLI refactor** to explicit subcommands and unified input planning; migrate away from custom
  `typed_*` helpers to native Click decorators. Includes: `check`, `strip`, `dump-config`,
  `filetypes`, `init-config`, `show-defaults`, `version`; shared plumbing; standardized exit policy
  & summaries. (Commit: `58476b9`)
- **Config layer** now accepts `ArgsLike` mapping (CLI-free) and no longer requires a Click
  namespace in public API entry points. (Commit: `9ddd18e`)
- **Docs**: split monolithic API page, add generator-based internals, and fix breadcrumb/link
  regressions; align pre-commit and mdformat settings with new docs layout. (Commits: `bf67c9e`,
  `41e2543`)
- **Output formatting**: use Click's built-in styling; unify Markdown views for `filetypes` &
  `processors`. (Commits: `cf5b789`, `8742a46`)
- **Tooling**: bump pre-commit hooks (ruff v0.12.12, pyright v1.1.405); set project version to
  `0.3.0` in `pyproject.toml` and `CONTRIBUTING.md`.

> [!CAUTION] **Breaking changes**
>
> - The stable public API surface was explicitly defined starting with this release.
> - The implicit default CLI command and legacy `typed_*` helpers were removed.

### Breaking Changes - 0.3.0

- The public API surface is explicitly defined from this release forward and will follow semver.
  Low-level registries and internals remain **unstable**.
- Implicit default CLI command removed (`topmark --...` → use `topmark check --...`). (Commit:
  `58476b9`)
- Legacy `typed_*` Click helpers removed. (Commit: `58476b9`)

### Fixed - 0.3.0

- Correct enum comparisons for `OutputFormat` across commands. (Commit: `c815f72`)
- Markdown rendering branches trigger consistently; format handling unified. (Commit: `8742a46`)
- Docs warnings around internal links/breadcrumbs resolved; configs aligned with `api/public.md`.
  (Commits: `bf67c9e`, `41e2543`)

______________________________________________________________________

## [0.2.1] - 2025-08-27

### Added - 0.2.1

- BOM-aware pipeline behavior: detect BOM in reader and re-attach in updater on all write paths.\
  (Commit: `27ad903`)
- Newline detection utility centralised; tests and docs expanded accordingly.\
  (Commit: `27ad903`)

### Changed - 0.2.1

- Comparer/renderer/updater flow consolidated; recognize formatting-only drift as change; clarify
  responsibilities via richer docstrings.\
  (Commit: `10bbf72`)
- CLI summary bucket precedence stabilized (e.g., "up-to-date").\
  (Commit: `10bbf72`)

### Fixed - 0.2.1

- Strip fast-path and BOM/newline preservation edge cases via new test coverage (matrix tests,
  inclusive spans).\
  (Commits: `7d8dbb8`, `10bbf72`)

______________________________________________________________________

## [0.2.0] - 2025-08-26

### Added - 0.2.0

- New `strip` command to remove TopMark headers (supports dry-run/apply/summary).\
  (Commits: `c6b9df3`, `8b028d2`)
- Pre-commit integration docs and hooks; GitHub Actions workflow for PyPI releases.\
  (Commit: `050445a`)

### Changed - 0.2.0

- CLI and pipeline improvements: comparer/patcher tweaks; context and processors updated.\
  (Commits: `c6b9df3`, `8b028d2`)

### Fixed - 0.2.0

- Initial CLI test suite for `strip`; early bug fixes discovered by tests.\
  (Commit: `8b028d2`)

______________________________________________________________________

## [0.1.1] - 2025-08-25

### Added - 0.1.1

- Initial public repository with CLI, pipeline, processors, docs site (MkDocs), tests, and build
  tooling.\
  (Commit: `b3f0169`)
- Trusted publishing workflow for PyPI and automated release notes.\
  (Commits: `6d702b4`, `0785e3c`)

### Changed - 0.1.1

- Documentation passes and configuration updates (pre-commit, pyproject, mkdocs).\
  (Commits: `399ea49`, `204a617`)

### Fixed - 0.1.1

- Early CI/publishing configuration issues.\
  (Commit: `0785e3c`)

______________________________________________________________________

## [0.1.0] - 2025-08-25

Initial commit.
