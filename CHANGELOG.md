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

______________________________________________________________________

## [1.0.0a4] – 2026-04-22

This fourth **1.0 alpha release** focuses on **finalizing the runtime dependency model** for
reliable execution in isolated environments.

It follows `1.0.0a3` and addresses an additional implicit dependency discovered during pre-commit
usage, while also introducing dependency-audit configuration to reduce the risk of further
dependency drift.

### Highlights — 1.0.0a4

- Completed promotion of implicit runtime dependencies to explicit core dependencies
- Added dependency-audit configuration to help prevent further dependency drift
- Further improved reliability in pre-commit, CI, and clean environments

### Changed — 1.0.0a4

- **Dependencies / packaging**

  - Promoted `packaging` to a **core runtime dependency**.
  - Ensures that version parsing and related utilities used in `topmark.constants` are always
    available at runtime.
  - Aligns declared dependencies with actual runtime import requirements.
  - Added a `deptry` configuration block in `pyproject.toml` so dependency-audit checks model the
    development/documentation optional-dependency groups explicitly.

### Fixed — 1.0.0a4

- **Runtime import failure in isolated environments**

  - Prevented potential `ModuleNotFoundError` for `packaging` when running via:
    - pre-commit hooks
    - fresh virtual environments
    - minimal CI environments

### Notes — 1.0.0a4

- This release continues the cleanup of **implicit runtime dependencies** discovered during alpha
  testing.
- TopMark’s dependency model is now more explicit, reproducible, and better guarded against future
  drift through dependency-audit configuration.
- Remaining work before 1.0 focuses on **CLI / human-output consistency and final contract freeze**.

______________________________________________________________________

## [1.0.0a3] – 2026-04-22

This third **1.0 alpha release** focuses on **packaging correctness, machine-output finalization,
and documentation alignment**.

The primary goal of `1.0.0a3` is to ensure that TopMark behaves reliably in **isolated
environments** and that the **machine-output contract is fully finalized, tested, and documented**
ahead of the 1.0 release.

This release completes the machine-output track and introduces important packaging fixes discovered
during real-world usage.

### Highlights — 1.0.0a3

- Corrected runtime dependency model for reliable execution in isolated environments
- Finalized registry machine-output contract (JSON + NDJSON)
- Strengthened machine-output test coverage with shared helpers
- Fully aligned machine-output documentation and roadmap with frozen 1.0 contract
- Introduced markdownlint integration for documentation quality

### Added — 1.0.0a3

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

### Changed — 1.0.0a3

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

### Fixed — 1.0.0a3

- **Runtime import failure in isolated environments**

  - Resolved `ModuleNotFoundError` for `typing_extensions`
  - Prevented failures in:
    - pre-commit hooks
    - fresh virtual environments
    - minimal CI environments

- **Registry machine-output inconsistencies**

  - Fixed asymmetries between filetypes, processors, and bindings outputs
  - Corrected JSON structure mismatches with documented contract

### Notes — 1.0.0a3

- Machine output is now **fully finalized, tested, and documented** for 1.0.
- The runtime dependency model is now **explicit and reliable across environments**.
- This release completes the **machine-output track** and stabilizes packaging behavior.
- Remaining work before 1.0 is focused on:
  - CLI / human-output consistency
  - final contract freeze decisions
  - line-ending policy audit

______________________________________________________________________

## [1.0.0a2] – 2026-04-21

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

### Highlights — 1.0.0a2

- Staged validation logs as the single internal representation of config diagnostics
- Removal of duplicated flattened diagnostics state from config models
- Boundary-only flattening at exception, presentation, and machine-output layers
- Strengthened machine-output and validation test coverage
- Improved JSONC file-type handling with native `.jsonc` support and safer ambiguous
  `.json`-as-JSONC detection
- Hardened artifact-based release workflow with strict tag preflight rules
- Fully aligned documentation and roadmap for 1.0 contract freeze

### Added — 1.0.0a2

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

### Changed — 1.0.0a2

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

### Removed — 1.0.0a2

- Stored flattened diagnostics fields from configuration models
- Redundant synchronization logic between staged and flattened diagnostics
- Legacy reliance on flattened diagnostics as internal state

### Fixed — 1.0.0a2

- Consistency of config-validation behavior across CLI, API, and machine-output paths
- JSONC handling for real `.jsonc` files, which could previously be blocked by JSON-promotion logic
  intended only for ambiguous `.json` inputs
- Release workflow ambiguity when multiple tags pointed to the same commit
- Documentation inconsistencies around validation behavior and strictness semantics

### Notes — 1.0.0a2

- The **staged validation model is now complete internally** and considered stable for 1.0.
- The **flattened diagnostics contract remains the official 1.0 public surface**.
- `strict_config_checking` remains unchanged and continues to apply across staged validation.
- This release further reduces internal duplication and aligns implementation with documented
  architecture.

TopMark is now firmly in the **final 1.0 stabilization phase**, with remaining work focused on
contract freeze, coverage completion, and selected feature decisions (notably in-memory pipeline).

______________________________________________________________________

## [1.0.0a1] – 2026-04-18

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

### ⚠️ Breaking Changes - 1.0.0a1

#### Registry / resolution model

- Built-in processor registration no longer relies on import-time decorators or bootstrap scanning.
  Processor/file-type relationships now use an explicit **binding model**.
- Registry responsibilities are now explicitly split across:
  - file types,
  - processors,
  - bindings,
  - and a thin façade.
- File types and processors now expose **namespace-aware stable identities** with canonical
  `qualified_key` values.
- Unqualified file type identifiers may now be treated as **ambiguous** where multiple namespaces
  overlap; callers must be prepared for explicit ambiguity handling.
- Registry machine and human outputs are now **identity-focused** and expose namespace/qualified-key
  metadata.
- A first-class `bindings` view is now part of the registry surface.

#### Config / TOML / runtime boundary

- Configuration concerns are now explicitly separated into:
  - `topmark.toml.*` for TOML loading, source resolution, defaults/templates, and whole-source TOML
    validation,
  - `topmark.config.*` for layered config construction, merge semantics, and effective per-path
    resolution,
  - `topmark.runtime.*` for execution-only runtime state.
- Package/runtime behavior no longer depends on conflating layered configuration with execution-time
  intent.
- The old boolean mutation policy pair (`add_only` / `update_only`) has been replaced by the scalar
  `header_mutation_mode` model.
- Source-local TOML options such as `strict_config_checking` are now treated explicitly as
  **TOML-source-local config-loading options**, not as layered `Config` fields.
- Whole-source TOML validation is now stricter and happens earlier in the load path; malformed or
  unknown TOML structure now surfaces consistently as diagnostics.

#### CLI / output / machine-format contracts

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

#### Developer / release workflow

- tox support was removed; contributors and CI now use **nox** with **uv-backed** environments.
- The project no longer maintains committed `requirements*.txt` / `constraints.txt` as its primary
  dependency workflow.
- `uv.lock` is now the canonical committed lock artifact.
- Package versioning no longer uses a manually maintained static `[project].version` in
  `pyproject.toml`.
- TopMark now derives package versions from Git tags via `setuptools-scm`, and release validation
  checks the **SCM-derived artifact version** against the release tag.
- The GitHub release pipeline has been restructured to an **artifact-based model**:
  - CI (`ci.yml`) builds and uploads `sdist` and `wheel` artifacts on tag pushes in an unprivileged
    context.
  - The release workflow (`release.yml`) runs in a privileged `workflow_run` context, downloads
    these artifacts, verifies tag/version consistency and checksums, and publishes them.
- Repository code is no longer built or executed in the privileged release workflow; only prebuilt
  CI artifacts are used for publishing.
- Compact PEP 440-style prerelease tags (`vX.Y.ZaN`, `vX.Y.ZbN`, `vX.Y.ZrcN`) are now the preferred
  form for new releases, while legacy dashed prerelease tags remain supported for backward
  compatibility.

### Highlights — 1.0.0a1

- Explicit, namespace-aware registry architecture with canonical qualified identities
- Shared resolution layer for file discovery and file-type binding resolution
- Clean CLI/presentation/machine-output separation
- Fully documented TOML → Config → Runtime architecture
- Stable preview vs apply semantics across pipeline and API
- uv-first / nox-based developer and CI workflow
- Git-tag-driven SCM versioning via `setuptools-scm`
- Broad documentation alignment across contributor, CI, machine-output, and command-reference pages

### Added — 1.0.0a1

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

### Changed — 1.0.0a1

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

### Removed — 1.0.0a1

- Legacy built-in processor bootstrap / decorator registration path
- `topmark.processors.bootstrap`
- `topmark.processors.registry`
- `topmark.registry.resolver`
- tox support and `tox.ini`
- Committed `requirements*.txt` / `constraints.txt` dependency-management workflow
- Static package version maintenance in `pyproject.toml`
- Legacy CLI/machine-output construction paths that mixed rendering, serialization, and console I/O

### Fixed — 1.0.0a1

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

### Notes — 1.0.0a1

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

## [0.11.1] – 2026-01-18

This patch release focuses exclusively on **developer tooling, CI reliability, and release
automation**. There are **no user-facing or runtime behavior changes** relative to 0.11.0.

### Changed — 0.11.1

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

### Fixed — 0.11.1

- **Nox bootstrap robustness on Python < 3.11**

  - Ensured `noxfile.py` can be imported on Python 3.10 by:
    - Using stdlib `tomllib` on Python 3.11+
    - Falling back to `tomli` on older interpreters (as provided by nox itself)
  - Prevented CI failures caused by missing TOML parsers during nox bootstrap.
  - Clarified via inline comments that TOML parsing in `noxfile.py`:
    - Happens at **nox import/bootstrap time**
    - Relies only on tooling dependencies, not TopMark runtime dependencies

### Notes — 0.11.1

- This release **does not change TopMark’s runtime behavior, public API, or CLI output**.
- The migration affects **developers and CI only**.
- Existing users upgrading from 0.11.0 require no action.

______________________________________________________________________

## [0.11.0] – 2026-01-15

This release introduces a set of **internal architectural improvements** that strengthen policy
correctness, STDIN handling, and CLI/API parity. While user-facing behavior remains compatible with
the 0.10.x series, there is an **intentional internal breaking change** for integrators relying on
TopMark internals.

### ⚠️ Breaking Changes - 0.11.0

- **PolicyRegistry is now mandatory at pipeline bootstrap time**

  - `ProcessingContext.bootstrap()` now **requires a `PolicyRegistry` argument**.
  - Internal callers must construct a `PolicyRegistry` from the resolved `Config` and pass it
    explicitly when bootstrapping a context.
  - This removes ad-hoc policy resolution, eliminates repeated per-context merging, and guarantees
    deterministic effective policy selection across all pipeline steps.

  > **Note:** This affects **internal and test code only**. The public API (`topmark.api.check`,
  > `topmark.api.strip`, CLI commands) remains source-compatible.

### Changed — 0.11.0

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

### Fixed — 0.11.0

- **CLI guidance correctness**
  - Made `check` and `strip` per-file guidance policy-aware and feasibility-aware.
  - Prevented misleading “run --apply …” suggestions when policy or feasibility blocks changes,
    especially for empty files and strip-only scenarios.

### Tests — 0.11.0

- Updated pipeline and API tests to bootstrap contexts via `PolicyRegistry`.
- Added shared helpers to keep test setup DRY and consistent across pipeline, API, and CLI tests.

### Notes — 0.11.0

- There are **no user-facing breaking changes** relative to 0.10.x.
- The public API surface remains stable, but **internal consumers and test harnesses must be
  updated** to construct and pass a `PolicyRegistry` when bootstrapping pipeline contexts.

______________________________________________________________________

## [0.10.1] – 2025-11-20

This patch release republishes the intended `0.10.0` release with two commits that were accidentally
omitted from the PyPI artifact.\
There are **no functional code changes** relative to `0.10.0`; this release only corrects packaging
and metadata.

### Changed — 0.10.1

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

### Notes — 0.10.1

This release contains **only packaging, metadata, and dependency housekeeping**.\
All functionality, schemas, and breaking changes remain exactly as described in **0.10.0**.

______________________________________________________________________

## [0.10.0] – 2025-11-20

This release introduces **major pipeline and CLI changes**, a full **machine-output schema
redesign**, a refactored **ProcessingContext**, and multiple BREAKING CHANGES. It also includes
substantial internal cleanup, dependency updates, and correctness fixes.

### ⚠️ Breaking Changes - 0.10.0

#### Machine Output (JSON / NDJSON)

- **Completely redesigned schema**:
  - All records include a `kind` discriminator (`config`, `config_diagnostics`, `result`,
    `summary`).
  - All records include a top-level `meta` block (version, intent, timestamps).
  - File-level results now use a stable, explicit envelope (`file`, `statuses`, `hints`,
    `diagnostic_counts`, `outcome`).
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

### Highlights — 0.10.0

- Clean separation of pipeline responsibilities (context, policy, status).
- Unified machine-readable output schema supporting stable integrations.
- Significantly clearer CLI output with accurate bucket, hint, and summary logic.
- Simplified type system with uniform abstract collections (`collections.abc`) and Ruff `UP`/`TC`
  enforcement.
- Full modernization of imports, dependency ranges, and development tooling.
- Large suite of correctness fixes across header bounds, scanner, renderer, patcher, and writer.

### Added — 0.10.0

- New `pipeline/context/` package with:
  - `model.py` (ProcessingContext core),
  - `policy.py` (feasibility, effective policy checks, intent validation),
  - `status.py` (HeaderProcessingStatus + axis enums).
- New machine-output builder (`cli_shared.machine_output`) as the single source of truth.
- New structured summary renderer (`topmark.api.view.format_summary`).
- Linting policy section in `CONTRIBUTING.md`.
- Support for GitHub-Flavored Markdown tables via `mdformat-gfm`.

### Changed — 0.10.0

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

### Removed — 0.10.0

- `ReasonHint` (unused).
- Legacy updater header code paths.
- Deprecated CLI commands and code paths for pre-0.9 behaviors.
- Legacy summary and bucket rendering pipeline.

### Fixed — 0.10.0

- Correct final newline + BOM + shebang interactions.
- Accurate indentation handling for Markdown/HTML/XML processors.
- Numerous header bound edge cases (multi-header, malformed, block comment variants).
- Writer stability in dry-run and apply modes.
- Accurate tracking of “would change” vs “changed” under mixed policy conditions.
- Corrected normalization for multi-line headers with mixed whitespace.
- Better FileType detection for HTML/Markdown block-comments.

### Notes — 0.10.0

`topmark.api` remains *public and stable*, but all **machine-readable formats** and **internal
pipeline interfaces** changed and require downstream updates. Integrators consuming NDJSON/JSON must
migrate to the new envelopes and keys.

______________________________________________________________________

## [0.9.1] - 2025-10-07

### Highlights — 0.9.1

- **Python 3.14 support (prerelease)** — test matrix, classifiers, and tooling updated for
  3.10–3.14.
- **Tox-first developer workflow** — Makefile simplified to delegate heavy lifting to tox;
  consistent local/CI behavior.
- **Property-based hardening** — Hypothesis harness added for idempotence and edge-case discovery.
- **Robust idempotence & XML/HTML guardrails** — Safer insertion rules and whitespace/newline
  preservation.

### Added — 0.9.1

- **Testing & quality**
  - Hypothesis-based **property tests** for insert→strip→insert idempotence and edge cases across
    common file types.
  - CI **pre-commit** job to run fast hooks on every PR/push (heavy/duplicated hooks handled
    elsewhere).
- **Python versions**
  - CI matrix extended to **3.14** (rc/dev as needed) with `allow-prereleases: true`.

### Changed — 0.9.1

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

### Fixed — 0.9.1

- **Idempotence & formatting drift**
  - Preserve user whitespace; avoid collapsing whitespace-only lines (e.g., `" \n"` vs `"\n"`).
  - Normalize handling of the **single blank line** after headers (owned newline only).
  - Respect **BOM** and trailing blanks; collapse only file-style blanks, not arbitrary whitespace.
  - Stripper/Updater: honor content status; avoid unintended rewrites.
- **Insertion safety**
  - Skip reflow-unsafe XML/HTML cases (e.g., single-line prolog/body, NEL/LS/PS scenarios).
  - Mixed line endings are skipped by the reader to avoid non-idempotent outcomes.

### CI / Tooling — 0.9.1

- **CI (`ci.yml`)**
  - **Tox-first** for lint (`format-check`, `lint`, `docstring-links`), docs (`docs`), tests
    (`py310…py314`), and API snapshot (`py313-api`).
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

### Developer Notes — 0.9.1

- We’ve moved from pure **venv** workflows (`.venv`, `.rtd`) to a **tox-based** model.
  - Please **delete** any old `.venv` and `.rtd` directories.

  - If you want IDE/Pyright import resolution, recreate only the **optional** editor venv:

    ```bash
    make venv && make venv-sync-dev
    ```

  - Use `make verify`, `make test`, `make pytest [PYTEST_PAR="-n auto"]`, `make docs-*`,
    `make api-snapshot*`, and the `lock-*` targets for daily work.

### ⚠️ Breaking Changes - 0.9.1

None.\
Public API remains stable; changes focus on tooling, CI reliability, and correctness fixes.

______________________________________________________________________

## [0.9.0] - 2025-10-06

### Highlights — 0.9.0

- **Configuration resolution finalized** — TopMark now fully supports layered config discovery with
  deterministic merge precedence, explicit anchor semantics, and path-aware pattern resolution.
- **Docs & MkDocs rebuild** — Documentation migrated to a snippet-driven architecture with reusable
  callouts, dynamic version injection, and a modernized MkDocs toolchain.
- **CLI alignment fix** — The `--align-fields` flag is now tri-state, preserving `pyproject.toml`
  defaults when the flag is omitted.
- **Public API parity** — The Python API now mirrors CLI behavior, respecting discovery, precedence,
  and formatting options such as `align_fields`.
- **Note:** Config discovery and precedence are now finalized; projects that relied on implicit or
  CWD-only behavior may see changes in which configuration takes effect.\
  See [**Configuration → Discovery & Precedence**](docs/configuration/discovery.md).

### Added — 0.9.0

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
  - Added `docs/_snippets/config-resolution.md` for consistent “How config is resolved” sections.
  - Automated generation of API reference pages for `topmark.api` and `topmark.registry`.
  - Updated `mkdocs.yml` plugin chain (include-markdown, simple-hooks, md_in_html, gen-files).
  - Added dynamic version display in docs (via `pre_build` hook).

### Changed — 0.9.0

- **CLI**
  - `--align-fields` is now **tri-state** (`True`, `False`, `None`)—when omitted, TOML defaults are
    respected.
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

### Fixed — 0.9.0

- **Config precedence bug** — Same-directory order (`pyproject.toml` before `topmark.toml`) was
  previously inverted; now fixed via per-directory grouping.
- **CLI override bug** — `--align-fields` no longer forces `false` when omitted; correctly inherits
  TOML default.
- **Header alignment** — Processors no longer align fields when `align_fields = false`.
- **Docs build** — Resolved missing MkDocs plugin errors in CI (`include-markdown` and
  `simple-hooks`).
- **Lychee false positives** — Updated snippet links and exclusion list to prevent link-checker
  failures.
- **Version token substitution** — The documentation now correctly substitutes `%%TOPMARK_VERSION%%`
  via pre-build hook.

### Docs / Tooling — 0.9.0

- Overhauled `pyproject.toml` `[project.optional-dependencies].docs` section to include all MkDocs
  plugins.
- Added `requirements-docs.txt` synced with `pyproject.toml` extras for CI.
- CI and release workflows (`ci.yml`, `release.yml`) now install docs extras (`-e .[docs]`) with
  constraints.
- Bumped doc dependencies: `mkdocs>=1.6.0`, `mkdocs-material>=9.5.19`, `pymdown-extensions>=10.16`.
- Removed obsolete `.mdformat.yml` and outdated constraints for `backrefs` and `markdown-it-py`.

### ⚠️ Breaking Changes - 0.9.0

None (pre-1.0).\
All changes are backward-compatible with v0.8.x configurations and APIs.

### Summary — 0.9.0

TopMark 0.9.0 consolidates its configuration system, aligns CLI and API behavior, and modernizes the
documentation pipeline. Config resolution, discovery anchors, and formatting flags now work
predictably across CLI, API, and generated docs.

______________________________________________________________________

## [0.8.1] - 2025-09-26

### Highlights — 0.8.1

- **XML re-apply fix**: prevent double-wrapped `<!-- … -->` blocks by anchoring bounds via character
  offset for XML/HTML processors.

### Added — 0.8.1

- **Developer validation (opt-in)**: set `TOPMARK_VALIDATE=1` to validate:
  - Processor ↔ FileType registry integrity.
  - XML-like processors use the char-offset strategy (`NO_LINE_ANCHOR` for line index).
- **Docs**:
  - Placement strategies (line-based vs char-offset) documented in `base.py` / `xml.py`.
  - New page `docs/ci/dev-validation.md`; CONTRIBUTING updated.

### Changed — 0.8.1

- **Processor refactor**:
  - Introduce mixins: `LineCommentMixin`, `BlockCommentMixin`, `XmlPositionalMixin`.
  - Add `compute_insertion_anchor()` façade and route updater through it.
  - Tighten typing (`Final[int]` for `NO_LINE_ANCHOR`; stricter annotations) and micro-perf (cache
    compiled encoding regex).
- **File types**:
  - Instances module made lazy, plugin-aware, and type-safe; detectors split out (JSONC).

### Fixed — 0.8.1

- **XML idempotency**: re-apply no longer nests comment fences.
- **Type checking & mypy**: generator return, entrypoint discovery, and strict typing cleanups.

### CI / Tooling — 0.8.1

- **New CI job**: “Dev validation” runs only tests marked `dev_validation` with
  `TOPMARK_VALIDATE=1`.
- **Pre-commit**: bump `ruff-pre-commit` to `v0.13.2`.

### ⚠️ Breaking Changes - 0.8.1

None.

______________________________________________________________________

## [0.8.0] - 2025-09-24

### Highlights — 0.8.0

- **New C-style block header support**: introduce `CBlockHeaderProcessor` and register it for **CSS,
  SCSS, Less, Stylus, SQL, and Solidity**.
- **Python stubs**: `.pyi` now use `PoundHeaderProcessor` (`#`-style), with sensible defaults (no
  shebang).

### Added — 0.8.0

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

### Changed — 0.8.0

- **Typing hardening (non-functional)**
  - Widespread strict typing across `pipeline/`, `cli/` & `cli_shared/`, remaining `src/` modules,
    and `tools/`:
    - Adopt postponed annotations; move type-only imports under `TYPE_CHECKING`.
    - Introduce `TopmarkLogger` annotations; add precise return/locals typing.
    - Minor import and hygiene cleanups for Pyright strict mode.

### Fixed — 0.8.0

- **CLI `processors` command**
  - Treat `filetypes` as dicts in `--long` + Markdown/default renderers to avoid `AttributeError`
    when running\
    `topmark processors --format markdown --long`.
- **Typing**
  - Resolve a redefinition error from an incorrectly placed annotation in types code.

### Docs — 0.8.0

- **README.md**: mention block (`/* … */`) alongside line (`#`, `//`) comment styles; add a CSS
  example.
- **docs/usage/filetypes.md**: expand processor table with modules and registered file types; add
  `CBlockHeaderProcessor`.

### Chore — 0.8.0

- Add standard TopMark headers to files in `typings/`.
- Dev tooling: keep pre-commit/hooks in sync (see commit history for exact bumps).

### ⚠️ Breaking Changes - 0.8.0

None.

______________________________________________________________________

## [0.7.0] - 2025-09-23

### Highlights — 0.7.0

- **Version CLI overhaul**: `topmark version` now defaults to **PEP 440** output and supports
  multiple formats via `--format {pep440,semver,json,markdown}` (alias: `--semver`).
- **Release hardening**: Fully revamped GitHub Actions release flow with strict gates (version/tag
  match, artifact checks, **docs must build**, TestPyPI for prereleases, PyPI for finals).

### Added — 0.7.0

- **CLI – `version` command**
  - `--semver` option to render a **SemVer** view while keeping **PEP 440** as the default.
  - `--format json|markdown|pep440|semver` with standardized outputs.
  - `topmark.utils.version.pep440_to_semver()` with graceful fallback.
- **Tests**
  - Expanded/parameterized tests for `version` across text/JSON/Markdown (PEP 440 vs SemVer).

### Changed — 0.7.0

- **CLI output (breaking schemas; see “Breaking” below)**
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

### Fixed — 0.7.0

- N/A (no user-visible fixes included in this release; tests/docs/tooling updates only).

### Docs — 0.7.0

- New & updated workflow docs:
  - `docs/ci/release-workflow.md` (RC vs final, gates, publishing).
  - `CONTRIBUTING.md` (CI expectations, local checks).
- `README.md` and `docs/index.md` examples updated for the new `version` outputs.

### Tooling / Reproducibility — 0.7.0

- Adopt pinned lockfiles (`requirements.txt`, `requirements-dev.txt`, `requirements-docs.txt`) and
  `constraints.txt`.
- Cache keyed on lockfiles; consistent `python -m pip` usage.

### Removed — 0.7.0

- Duplicate “Build docs (strict)” step from the `lint` job.
- Stray `topmark.toml` at repo root.

### Chore — 0.7.0

- Pre-commit: bump `topmark-check` hook to v0.6.2.
- Minor `tox.ini` whitespace tidy-ups.

### ⚠️ Breaking Changes - 0.7.0

- **JSON** schema changed from `{"topmark_version": "<str>"}` to
  `{"version": "<str>", "format": "pep440|semver"}`.
- **Markdown** now explicitly includes the format label:\
  `**TopMark version (pep440|semver): <version>**`.\
  Update any consumers/parsers that relied on the previous key or phrasing.

#### Pre-Releases — 0.7.0

- `0.7.0-rc1` and `0.7.0-rc2` were published to **TestPyPI** for validation; their contents are
  fully included in this final release.

### Developer Notes — 0.7.0

- For RCs: keep `pyproject.toml` at `0.7.0rcN` and tag `v0.7.0-rcN` to publish to TestPyPI.
- For GA: bump to `0.7.0`, tag `v0.7.0`, and the workflow publishes to PyPI after docs/tests gates.

______________________________________________________________________

## [0.6.2] - 2025-09-15

### Fixed — 0.6.2

- **Docs build**: resolve Griffe parsing error by normalizing a parameter docstring format (remove
  stray space before colon) for `skip_compliant` in `topmark.api.check()` (file:
  `src/topmark/api/__init__.py`). This unblocks MkDocs/ReadTheDocs builds. No functional code
  changes.

______________________________________________________________________

## [0.6.1] - 2025-09-15

### Added — 0.6.1

- **Docstring link checker**: new `tools/check_docstring_links.py` to enforce reference-style object
  links and flag raw URLs in docstrings. Includes accurate line/range reporting, code-region
  masking, and CLI flags `--stats` and `--ignore-inline-code`.
- **Makefile targets**: `docstring-links`, `links`, `links-src`, `links-all`; centralized
  `check-lychee` gate.

### Changed — 0.6.1

- **MkDocs build**: enable `strict: true` and link validation to fail on broken internal links.
- **Docstrings/x‑refs**: convert internal references to mkdocstrings+autorefs style (e.g.,
  `` [`pkg.mod.Object`][] `` or `[Text][pkg.mod.Object]`) and prefer fully‑qualified names.
- **Docs structure**: normalize mkdocstrings blocks (minor tidy‑ups).

### Fixed — 0.6.1

- **README**: correct the “Adding & updating headers with topmark” link to
  `docs/usage/commands/check.md`.

### Tooling — 0.6.1

- **Lychee integration**: adopt Lychee for link checks (local + CI); scoped pre‑commit hooks.
- **Testing**: raise `pytest` minimum to `>=8.0` in the `test` optional dependencies.
- **Refactors**: minor non‑functional cleanups (rename local import alias in filetype registry;
  small typing improvements).

______________________________________________________________________

## [0.6.0] - 2025-09-12

### Added — 0.6.0

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

### Changed — 0.6.0

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

### Fixed — 0.6.0

- CLI and pipeline now reflect header order deterministically (no “up-to-date” false negatives when
  order differed). (Commit: `d778ace`)
- Type-checking and lint issues (casts, variable redefinitions, analyzer false positives) resolved
  in CLI helpers and resolver paths. (Commits: `d778ace`, `adc35f9`)

### Docs — 0.6.0

- Add **“Configuration via mappings (immutable at runtime)”** section to the public API docs and
  mirror a concise note in the `topmark.api` module docstring. (Commit: `d778ace`)
- Normalize docstrings across the codebase; remove Sphinx roles in favor of Markdown-friendly
  mkdocstrings. (Commit: `f649731`)

### Tooling — 0.6.0

- Add `pydoclint` to dev toolchain; wire into Makefile and pre-commit.
- Reorder pre-commit hooks for faster feedback.
- Snapshot workflow integrated into Makefile and CI-friendly checks. (Commits: `f649731`, `a584577`)

### Chore — 0.6.0

- Repository-wide header reformat to the new field order (no functional changes). (Commit:
  `bcac2ed`)

#### Notes — 0.6.0

- **No public API surface changes**: `topmark.api.check/strip` signatures unchanged.
- `MutableConfig` is **internal** (not part of the stable API); public callers should pass a mapping
  or a frozen `Config`.

______________________________________________________________________

## [0.5.1] - 2025-09-09

### Fixed — 0.5.1

- **Python 3.10/3.11 compatibility**: replace multiline f‑strings in CLI output code paths (not
  supported before Python 3.12) with concatenation/temporary variables. Affected commands:
  - `filetypes`: numbered list rendering and detail lines (description/content matcher)
  - `processors`: processor header lines and per‑filetype detail lines

### Tooling — 0.5.1

- Bump project version to `0.5.1` in `pyproject.toml`.
- Update local pre‑commit hook to use TopMark **v0.5.0**.

______________________________________________________________________

## [0.5.0] - 2025-09-09

### Added — 0.5.0

- **Honest write statuses** across the pipeline:
  - Dry‑run ⇒ `WriteStatus.PREVIEWED`
  - Apply (`--apply`) ⇒ terminal statuses (`INSERTED`, `REPLACED`, `REMOVED`)
- **Apply intent plumbing** end‑to‑end:
  - `Config.apply_changes` (tri‑state) consumed via `apply_cli_args()` and respected in updater
  - CLI and public API forward **apply** to the pipeline

### Changed — 0.5.0

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

### Fixed — 0.5.0

- **Pre‑commit hooks**: remove redundant `--quiet` (default output is already terse) and fix its
  placement.

### Docs — 0.5.0

- Refresh CLI docs:
  - Explicit subcommands in examples; stdin examples use `topmark check - …`
  - Clarify dry‑run vs apply summary text (`- previewed` vs `- inserted`/`- replaced`/`- removed`)
  - Add “Numbered output & verbosity” notes to `filetypes` / `processors`
  - Add `version` command page; tidy headings and separators

### ⚠️ Breaking Changes - 0.5.0

- Dry‑run summaries now end with **`- previewed`** instead of terminal verbs.\
  Update any scripts/tests parsing human summaries that previously matched `- inserted` /
  `- removed` / `- replaced` during dry‑run.
- Human‑readable CLI output may differ (verbosity‑gated banners and numbered lists).

______________________________________________________________________

## [0.4.0] - 2025-09-08

### Added — 0.4.0

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

### Changed — 0.4.0

- **Public API**: `diagnostics` in `RunResult` now returns a mapping
  `dict[str, list[PublicDiagnostic]]` instead of `dict[str, list[str]]`.
- **Summaries**: `ProcessingContext.format_summary()` now aligns with pipeline outcomes and appends
  compact triage (e.g., `1 error, 2 warnings`) plus hints (`previewed`, `diff`).
- **Verbosity handling**: CLI `-v/--verbose` and `-q/--quiet` feed a program-output verbosity level
  separately from the logger level; per-command logger overrides were removed.
- **Config.merge_with()**: `verbosity_level` now honors **override semantics** (other wins), and
  supports tri-state inheritance.
- **API surface**: `PublicDiagnostic` re-exported from `topmark.api` and included in `__all__`.

### Fixed — 0.4.0

- Reader now surfaces an explicit diagnostic for empty files.
- Minor wording/formatting improvements in `classify_outcome()` and summary output.
- Import order cleanup in `pipelines.py`.

### Docs — 0.4.0

- Expanded inline docstrings for diagnostics, public types, and verbosity semantics.

### ⚠️ Breaking Changes - 0.4.0

- `RunResult.diagnostics` type changed to a structured public form. Integrations consuming plain
  strings should switch to `d["message"]` and may use `d["level"]` for triage.
- New aggregate fields (`diagnostic_totals`, `diagnostic_totals_all`) are added alongside
  `diagnostics`.

______________________________________________________________________

## [0.3.2] - 2025-09-07

### Fixed — 0.3.2

- **Pre-commit hooks**: update TopMark hooks to use the explicit `check` subcommand
  (`topmark check …`) instead of the removed implicit default command. This restores correct
  behavior for `topmark-check` and `topmark-apply` hooks.

### Docs — 0.3.2

- Add **API Stability** page and wire it into the MkDocs navigation (`Development → API Stability`).
- Add a stability note/link to `docs/api/public.md` referencing the snapshot policy.

### Tooling — 0.3.2

- Bump project version to `0.3.2` in `pyproject.toml`.

______________________________________________________________________

## [0.3.1] - 2025-09-07

### Fixed — 0.3.1

- **Snapshot tests**: stabilize public API snapshot across Python 3.10–3.13 by normalizing
  constructor signatures in tests (`<enum>` for Enum subclasses, `<class>` for other classes) while
  retaining real signatures for callables. Updated baseline `tests/api/public_api_snapshot.json`
  accordingly and refreshed the REPL snippet in the test docstring to generate a
  cross‑version‑stable snapshot.

______________________________________________________________________

## [0.3.0] - 2025-09-07

### Added — 0.3.0

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

### Changed — 0.3.0

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

### ⚠️ Breaking Changes - 0.3.0

- The public API surface is explicitly defined from this release forward and will follow semver.
  Low‑level registries and internals remain **unstable**.
- Implicit default CLI command removed (`topmark --…` → use `topmark check --…`). (Commit:
  `58476b9`)
- Legacy `typed_*` Click helpers removed. (Commit: `58476b9`)

### Fixed — 0.3.0

- Correct enum comparisons for `OutputFormat` across commands. (Commit: `c815f72`)
- Markdown rendering branches trigger consistently; format handling unified. (Commit: `8742a46`)
- Docs warnings around internal links/breadcrumbs resolved; configs aligned with `api/public.md`.
  (Commits: `bf67c9e`, `41e2543`)

______________________________________________________________________

## [0.2.1] - 2025-08-27

### Added — 0.2.1

- BOM‑aware pipeline behavior: detect BOM in reader and re‑attach in updater on all write paths.\
  (Commit: `27ad903`)
- Newline detection utility centralised; tests and docs expanded accordingly.\
  (Commit: `27ad903`)

### Changed — 0.2.1

- Comparer/renderer/updater flow consolidated; recognize formatting‑only drift as change; clarify
  responsibilities via richer docstrings.\
  (Commit: `10bbf72`)
- CLI summary bucket precedence stabilized (e.g., “up‑to‑date”).\
  (Commit: `10bbf72`)

### Fixed — 0.2.1

- Strip fast‑path and BOM/newline preservation edge cases via new test coverage (matrix tests,
  inclusive spans).\
  (Commits: `7d8dbb8`, `10bbf72`)

______________________________________________________________________

## [0.2.0] - 2025-08-26

### Added — 0.2.0

- New `strip` command to remove TopMark headers (supports dry‑run/apply/summary).\
  (Commits: `c6b9df3`, `8b028d2`)
- Pre‑commit integration docs and hooks; GitHub Actions workflow for PyPI releases.\
  (Commit: `050445a`)

### Changed — 0.2.0

- CLI and pipeline improvements: comparer/patcher tweaks; context and processors updated.\
  (Commits: `c6b9df3`, `8b028d2`)

### Fixed — 0.2.0

- Initial CLI test suite for `strip`; early bug fixes discovered by tests.\
  (Commit: `8b028d2`)

______________________________________________________________________

## [0.1.1] - 2025-08-25

### Added — 0.1.1

- Initial public repository with CLI, pipeline, processors, docs site (MkDocs), tests, and build
  tooling.\
  (Commit: `b3f0169`)
- Trusted publishing workflow for PyPI and automated release notes.\
  (Commits: `6d702b4`, `0785e3c`)

### Changed — 0.1.1

- Documentation passes and configuration updates (pre‑commit, pyproject, mkdocs).\
  (Commits: `399ea49`, `204a617`)

### Fixed — 0.1.1

- Early CI/publishing configuration issues.\
  (Commit: `0785e3c`)

______________________________________________________________________

## [0.1.0] - 2025-08-25

Initial commit.
