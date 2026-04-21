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
goals. The focus has been on **architectural separation, deterministic behavior, strict typing, and
removal of legacy implicit behavior**. The system is now largely aligned with a clean *TOML → Config
→ Runtime → Pipeline → Presentation* model.

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
- Implemented **ambiguity-aware resolution** with explicit error types.
- Moved resolution logic into `topmark.resolution.*` and removed legacy resolver paths.
- Established **canonical identity semantics** across machine output, CLI, and API.

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
- Standardized verbosity model (`default`, `-v`, `-vv`)
- Unified summary generation via pipeline outcomes instead of ad-hoc hint logic

Result: output is now **fully deterministic, testable, and reusable outside CLI contexts**.

### Runtime vs config separation (completed)

A strict separation between **configuration and execution intent** is now in place:

- Introduced `RunOptions` for runtime-only behavior (apply, stdin, etc.)
- Removed runtime concerns from `Config`
- Ensured CLI and API both follow:
  - TOML → Config → Runtime overlay

Result: config is now **pure, layered, and reproducible**, while runtime behavior is explicit.

### TOML / config system (completed)

The configuration system has been fully restructured:

- Clear split:
  - `topmark.toml` → parsing + validation
  - `topmark.config` → layered merge + resolution
  - `topmark.runtime` → execution behavior
- Implemented **layered config with provenance**
- Added **per-path effective config resolution**
- Introduced **strict validation model** with diagnostics + strict mode
- Introduced **staged config-loading validation logs**:
  - TOML-source diagnostics
  - merged-config diagnostics
  - runtime-applicability diagnostics
- Removed stored flattened diagnostics from `Config` / `MutableConfig`
  - flattening is now performed only at exception, presentation, and machine-output boundaries
- Removed legacy helpers and compatibility layers
- Standardized API inputs via `ConfigMapping`

Result: configuration is now **typed, layered, validated, and consistent across CLI/API**.

### Pipeline semantics & policy model (completed)

The pipeline has been stabilized with clearer semantics:

- Introduced **preview vs apply split**
- Normalized write statuses (PREVIEWED vs INSERTED/REPLACED/REMOVED)
- Introduced **empty-file classification model**
- Refactored policy handling:
  - `HeaderMutationMode` replaces boolean flags
- Standardized summary output:
  - grouped by `(outcome, reason)`
- Ensured **idempotence and deterministic behavior**

Result: pipeline behavior is now **explicit, consistent, and predictable**.

### Machine output system (near-complete)

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
- Supported by shared JSON/NDJSON test helpers for machine-output parsing and record/meta assertions
- Documented with aligned machine-format and machine-output reference pages, plus registry command
  usage pages

Remaining work is limited to a **final naming audit and CLI/output-surface follow-up**, not
architecture.

### Human output system (completed)

- Consolidated formats: TEXT + MARKDOWN
- Introduced `topmark.presentation` as canonical rendering layer
- Ensured all renderers are:
  - pure (no I/O)
  - reusable
  - testable

Result: human output is now **consistent, composable, and decoupled from CLI**.

### Documentation & developer tooling (completed)

- Major documentation alignment with new architecture
- Added pipeline docs and registry documentation
- Enforced docstring standards and validation
- Introduced link-checking and stricter docs CI
- Reorganized tests and helpers for clarity
- Added shared JSON/NDJSON parsing and assertion helpers for machine-output tests

### CI / release / dependency model (completed)

- Migrated to **uv-first dependency model**
- Replaced tox with **nox**
- Implemented **artifact-based CI → release pipeline**
- Adopted **SCM-based versioning (setuptools-scm)**
- Hardened CI with:
  - link checks
  - permissions model
  - SHA-pinned actions

Result: release process is now **secure, reproducible, and automated**.

### Overall status (done)

At this point:

- Core architecture is **fully refactored**
- Legacy implicit behavior is **eliminated**
- System boundaries are **clear and enforced**
- Remaining work is **focused and incremental**, not structural
- Machine-output contract coverage is now strong for config, pipeline, version, and registry
  commands

The project is now in a **pre-1.0 stabilization phase**, with only a few major decisions and
targeted features (notably in-memory pipeline support) remaining.

______________________________________________________________________

## Breaking changes introduced so far

This section summarizes the **externally relevant breaking changes** already introduced during the
0.12 refactor series. The emphasis is on **contract changes**, not internal implementation details.

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
- Namespace-aware file type lookup now supports qualified identifiers and may raise
  `AmbiguousFileTypeIdentifierError` for ambiguous unqualified identifiers.
- Registry machine and human outputs now expose canonical qualified identifiers and namespace
  metadata, and add a first-class bindings view.
- Public API registry metadata was reshaped to align with the split filetype / processor / binding
  model.
  - Downstream callers using older field names or processor-grouped binding views must update.

Result: registry behavior is now more explicit and deterministic, but downstream registry/plugin/API
consumers must update to the canonical identity and explicit binding model.

### Config / TOML / runtime surface

- Configuration is no longer treated as a single mixed layer.
  - `topmark.toml` handles TOML parsing and whole-source schema validation
  - `topmark.config` handles layered merge / effective config resolution
  - `topmark.runtime` handles execution-time behavior
- Several older config/TOML helper entry points were removed or relocated.
  - Callers using older helper locations must migrate to the new module layout.
- Generic config/API mapping input is now represented as `ConfigMapping`.
  - The legacy `ArgsLike` alias was removed.
- Config-loading entry points were consolidated around TOML-first resolution.
  - Callers needing provenance must explicitly handle `(resolved_sources, draft_config)`.
- Source-local TOML options such as `[config].root` and `strict_config_checking` now live outside
  layered `Config` merging.
- TOML validation is now stricter and happens earlier:
  - unknown top-level sections/keys, malformed known sections, and malformed nested policy sections
    are reported during whole-source TOML loading
  - these diagnostics now participate in shared CLI/API validation behavior
- Policy/config surface changed:
  - `add_only` / `update_only` → replaced by `header_mutation_mode`
  - `skip_compliant` / `skip_unsupported` → replaced by `report`
- Config merge semantics are no longer uniformly “last-wins”:
  - some fields accumulate
  - some fields merge key-wise
  - effective config is now resolved per path rather than as a single flat snapshot

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
- Runtime-only execution intent is now modeled separately from layered config.
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
- Command applicability rules are stricter:
  - `strip` now rejects check-only mutation/insertion policy options at the CLI layer

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
  final flattened config payload.
- `detail_level` is now part of the machine-output contract for command families that emit
  projection metadata (notably registry machine output).
- Registry JSON machine output was flattened for 1.0 contract stability:
  - `registry filetypes` → `{meta, filetypes}`
  - `registry processors` → `{meta, processors}`
  - `registry bindings` → `{meta, bindings, unbound_filetypes, unused_processors}`

Result: machine formats are much more stable and structured, but downstream consumers that relied on
older payload naming or outcome-keyed summaries must update.

### Documentation / docs build behavior

- Documentation now assumes the TOML → Config → Runtime architecture and the new CLI/output model.
- Generated API/reference pages are part of the docs build contract.
  - missing or stale generated pages can now fail `mkdocs build --strict`
- Documentation/tooling now relies on dedicated formatter config files:
  - `.mdformat.toml`
  - `.taplo.toml`
- Built-site link checking (`links-site`) is now part of the CI path that gates release-artifact
  creation on tag pushes.

Result: documentation is more accurate and better validated, but docs generation/validation is now
stricter than before.

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
- GitHub Actions behavior is more aggressively gated by changed-file buckets on pull requests, so
  some jobs may now be skipped unless relevant files changed.

Result: contributor/release workflow is more secure and reproducible, but maintainers must update
both their mental model and automation expectations for CI, publishing, dependency management, and
versioning.

### Overall impact

The major breaking changes are no longer about isolated helper removals; they are about a **new
system shape**:

- explicit registry/binding model
- layered TOML/config/runtime boundaries
- explicit preview/apply runtime model
- schema-driven machine output with domain-specific JSON envelopes and stable NDJSON record kinds
- uv/nox-based tooling and artifact-based release automation

The 1.0 task is therefore not large-scale redesign anymore, but **contract freeze and final
stabilization** on top of these already-landed changes.

______________________________________________________________________

## Still undecided / still to do

This section captures the **remaining 1.0 decisions and targeted implementation work**. The large
structural refactors are already done; what remains is mostly about **contract freeze, scope
choices, and deciding what is in or out for 1.0**.

### Registry / resolution freeze

The registry architecture is largely complete, but a few 1.0 decisions remain:

- Decide whether the **local-key compatibility view** in `FileTypeRegistry` remains an explicit
  long-term 1.0 feature or should be treated as transitional.
- Freeze and document where **local keys** remain valid user-facing input:
  - CLI/config include/exclude filters
  - API resolver-style helpers
  - plugin-facing examples and tests
- Confirm that canonical identity terminology (`qualified_key`, `file_type_id`, `local_key`, etc.)
  is fully stabilized across docs, tests, CLI, and public API references.
- Finish freezing the public surface of `topmark.resolution.*`:
  - what remains public
  - what becomes internal
  - what ambiguity behavior is guaranteed for 1.0

Recommended direction:

- Keep **canonical qualified identity** as the default internal and external model.
- Keep local-key support only where it provides clear user-facing compatibility value.
- Keep ambiguity handling in the resolver layer rather than treating overlapping file types as a
  registry error.

### In-memory pipeline: implement or defer

This is the largest remaining product/architecture decision before 1.0.

Question:

- Should TopMark gain **first-class in-memory pipeline support** before 1.0, or should it be
  explicitly deferred?

Current status:

- design drafted
- implementation not started
- architecture direction understood

Proposed direction remains:

- keep the existing file-based pipeline intact
- introduce an `InputSource` abstraction
- add a memory-oriented early-stage pipeline variant
- reuse the existing later pipeline steps unchanged where possible

What still needs deciding:

- whether mixed file + memory inputs are allowed in one run
- how synthetic paths/display names should be represented
- whether stdin should be modeled through the same abstraction
- whether this is a 1.0 feature or a documented post-1.0 deferral

If implemented before 1.0, this should also drive a clearer split between:

- fast memory-based unit tests
- smaller, focused filesystem integration tests

### API / CLI / presentation boundary freeze

The separation is much clearer now, but a few boundary questions remain:

- Remove any remaining Click-facing concerns from non-CLI modules.
- Keep formatting, verbosity, and color decisions strictly split between:
  - CLI policy/orchestration
  - pure presentation rendering
  - core/domain logic
- Confirm that TOML validation diagnostics surface consistently in CLI and API flows without leaking
  CLI-specific formatting concerns into shared validation logic.
- Decide whether API-side convenience helpers in `topmark.api.runtime` should remain as part of the
  long-term public surface or be slimmed further.
- Confirm that provenance inspection (`config dump --show-layers`) remains an inspection concern and
  does not leak into validation-oriented commands or public API contracts.
- Keep release-automation concerns artifact/download-oriented and scoped to CLI/automation, not to
  public Python API surfaces.

### Config / validation contract freeze

The architecture is now stable, but the **exact 1.0 contract** still needs to be frozen in a few
places.

Remaining decisions:

- Freeze and document the typed override boundary:
  - `PolicyOverrides`
  - `ConfigOverrides`
- Decide how much of that override structure is truly public/stable for Python callers.
- Freeze and document the staged validation model now implemented internally:
  - TOML-source diagnostics
  - merged-config diagnostics
  - runtime-applicability diagnostics
- Keep staged validation primarily internal for 1.0, with only the flattened compatibility
  diagnostics contract exposed at exception, presentation, and machine-output boundaries.
- Keep `strict_config_checking` as-is for 1.0 and revisit any possible rename only after the 1.0
  contract freeze.
- Confirm that sanitization/runtime-applicability warnings intentionally remain inside the effective
  `strict_config_checking` gate for 1.0.
- Confirm that TOML validation, config validation, runtime overlay, and layered provenance remain
  clearly separated responsibilities.
- Decide whether configuration schema versioning should remain implicit for 1.0, with any explicit
  schema-version key deferred until a future non-additive schema change.

Recommended direction:

- keep the current TOML → Config → Runtime split,
- keep `strict_config_checking` as the public config-loading strictness knob for 1.0,
- freeze the staged validation semantics now implemented internally,
- keep flattened diagnostics as a derived compatibility/reporting surface only at exception,
  presentation, and machine-output boundaries,
- defer broader staged-gate exposure in CLI/API/machine output unless clearly justified before final
  freeze,
- defer explicit config schema versioning until a future non-additive schema change requires it.

### Output contract freeze

Most output architecture work is done. Machine-output implementation, tests, and reference
documentation are now largely frozen; the remaining work is about **final semantics, naming audit,
and CLI/human-output follow-up**, not redesigning the system.

Machine output remaining work:

- Final audit of field naming consistency across domains.
- Keep flattened `{level, message}` config diagnostics as the accepted 1.0 machine contract. Richer
  TOML-specific structure is explicitly deferred beyond 1.0.
- Registry machine-output contract frozen after the flattened JSON-envelope cleanup (`filetypes`,
  `processors`, `bindings`, `unbound_filetypes`, `unused_processors`).
- `detail_level` semantics frozen:
  - `--long` controls projection depth across formats
  - `detail_level` reflects projection in machine output when present
  - verbosity remains independent (human-output concern)
- Keep `docs/dev/machine-formats.md` and `docs/dev/machine-output.md` aligned as the reference
  machine-format documentation.

Human output remaining work:

- Ensure TEXT and MARKDOWN remain consistent across commands.
- Freeze verbosity semantics (`-v`, `-vv`, `-q`).
- Finalize hint-ordering strategy.
- Decide whether Markdown should remain layout-equivalent to text output or evolve toward a more
  document-oriented format later.
- Continue keeping presentation logic fully out of CLI command functions.

### Tooling / CI / release follow-up

The security and workflow refactor is now functionally complete. What remains is mostly follow-up
and final 1.0 policy decisions.

Remaining work:

- Decide whether the current **artifact-based CI → release split** is the stable long-term 1.0
  release architecture, with any further factoring deferred post-1.0.
- Keep validating that:
  - changed-file buckets remain correct
  - tag-push artifact creation remains aligned with release expectations
  - artifact verification continues to match publish behavior
- Decide whether the current explicit `tests` matrix setup should remain as-is or later be factored
  around the shared setup composite action.
- Decide whether workflow formatting/style rules should remain an editor-policy concern or be
  documented explicitly in contributor-facing CI guidance.
- Keep validating that Nox, pre-commit, local `.venv`, editor integrations, CI jobs, and the
  artifact-based release workflow all consume the same formatter/tool configuration.

### Human-facing policy / behavior questions

A few user-facing behavior questions remain open for 1.0:

- Should the default processing mode remain **“all supported file types”**?
- Should a stricter whitelist-first mode ever become the default?
- Freeze the final public token semantics for `EmptyInsertMode`.
- Decide whether public API callers should continue using stable string literals for policy tokens,
  or whether a dedicated public enum should exist later.
- Decide whether summary reason strings are part of the stable integration contract or only
  presentation-facing labels.
- Keep confirming that API and CLI docs consistently use the `report` model and no longer reference
  legacy `skip_*` filters.

### Overall status (undecided / to do)

The remaining work is no longer broad architectural redesign.

What is left is mainly:

- **freeze decisions**
- **final audits and consistency reviews**
- **CLI / human-output follow-up**
- one major scope choice: **in-memory pipeline before 1.0 vs explicit deferral**

That means TopMark is now in the final stage of the 1.0 effort: auditing the last cross-surface
contracts, deciding what to freeze, and deferring anything non-essential cleanly.

______________________________________________________________________

## 1.0 readiness checklist

TopMark 1.0 follows a **contract-first** release strategy: all externally observable behavior (API
surface, configuration semantics, machine formats, CLI behavior, and release workflow expectations)
must be stable, documented, and well-tested.

The large refactors are already complete. This checklist is therefore about **freeze readiness**:

- what must be stable before `1.0.0`
- what can still be deferred with rationale
- what is better treated as post-1.0 follow-up

### Must finish before 1.0

These are release blockers unless explicitly deferred with a documented rationale.

#### [Must] Architecture & boundaries

- [x] Clear separation between CLI, presentation, API, and core/domain layers
- [x] Runtime behavior separated cleanly from layered config
- [x] No CLI-specific concerns (verbosity, color, formatting) in core logic
- [ ] Remaining public-vs-internal boundaries frozen and documented for:
  - `topmark.resolution.*`
  - `topmark.api.runtime`
  - typed override surfaces (`PolicyOverrides`, `ConfigOverrides`)

#### [Must] Machine output contracts

- [x] No presentation leakage in machine output
- [x] Machine outputs covered by focused JSON + NDJSON contract tests for all command groups
  - [x] config commands
  - [x] pipeline commands
  - [x] version command
  - [x] registry commands
  - [x] top-level command groups reviewed for any remaining machine-output gaps
- [ ] Final schema freeze review completed
  - [x] `(outcome, reason, count)` summary rows frozen
  - [x] `detail_level` semantics frozen
    - [x] `--long` is the cross-format projection selector (brief vs long)
    - [x] `detail_level` reflects this projection in machine output when emitted
    - [x] verbosity remains a separate human-output concern
  - [ ] field naming consistency audited across domains
- [x] `config check` payload naming stabilized as `config_check`
- [x] `strict_config_checking` naming stabilized in config-validation payloads
- [x] Decision made on the 1.0 machine contract for config/TOML diagnostics:
  - [x] flattened `{level, message}` is explicitly accepted as final
  - [x] richer TOML-specific structure is not required before 1.0 freeze (explicitly deferred)
- [x] `docs/dev/machine-formats.md` reviewed and frozen as a reference contract
- [x] `docs/dev/machine-output.md` reviewed and aligned with the current command contracts

#### [Must] Human output contracts

- [ ] TEXT and MARKDOWN outputs reviewed for consistency across command groups
  - [ ] config commands
  - [x] pipeline commands
  - [x] registry commands
  - [x] version command
- [ ] Warning/error phrasing reviewed for CLI-wide consistency
- [ ] Verbosity semantics (`default`, `-v`, `-vv`, `-q`) documented and considered stable
- [ ] Decision made on hint-ordering / “primary hint” semantics for 1.0

#### [Must] CLI behavior

- [ ] Exit codes documented and considered stable
- [ ] CLI command applicability rules fully documented and enforced
  - [ ] policy-option applicability
  - [ ] stdin/list-vs-content handling
  - [ ] strict config-checking behavior at command level
- [ ] Final review of user-facing policy/report flags completed
  - [ ] `--report` semantics frozen
  - [ ] `--header-mutation-mode` semantics frozen
  - [ ] `EmptyInsertMode` token semantics frozen

#### [Must] Configuration & validation

- [ ] Config keys and semantics documented and considered stable
- [ ] Qualified/unqualified file type identifier semantics documented and considered stable
- [ ] `config init`, `config defaults`, `config check`, and `config dump` outputs aligned and frozen
- [ ] Decision made and documented on the final public override model
- [x] Package/application versioning model documented and stable
  - [x] Git tags are the single source of truth via `setuptools-scm`
  - [x] static `[project].version` is gone
  - [x] release validation uses SCM-derived artifact versions
  - [x] privileged release jobs consume CI-built artifacts
  - [x] no manual version-bump step remains
- [x] Preferred release-tag conventions documented and stable
- [x] `strict_config_checking` documented and stable as a TOML-source-local config-loading option
- [x] Whole-source TOML schema validation rules documented and considered stable
- [x] TOML/config/runtime split documented and implemented
- [x] Per-path effective config resolution implemented
- [ ] Validation semantics frozen for 1.0:
  - [x] validation always runs
  - [x] strictness controls raise vs report behavior
  - [x] CLI and API use the same validation path
  - [x] staged validation logs implemented internally
  - [x] effective validity now evaluates TOML-source, merged-config, and runtime-applicability
    diagnostics together
  - [x] `strict_config_checking` remains the public config-loading strictness knob
  - [x] `ConfigValidationError` now has focused coverage for staged-count summaries and
    exception-boundary flattening
  - [x] final decision made on 1.0 exposure: keep staged validation primarily internal with
    flattened compatibility diagnostics only at exception/presentation/output boundaries
- [ ] Decision made whether explicit configuration schema versioning is deferred past 1.0

#### [Must] Pipeline & testing

- [ ] Decision taken on in-memory pipeline support
  - [ ] implemented before 1.0, or
  - [ ] explicitly deferred with rationale
- [ ] Test strategy clarified and documented:
  - [ ] intended split between memory-based unit tests and filesystem integration tests
  - [ ] API surface expectations for in-memory inputs (if implemented or deferred)
- [ ] Namespace-aware registry lookup and deterministic ambiguity behavior covered by tests
- [x] TOML-layer validation paths have focused coverage
- [x] Empty / empty-like file handling is explicit and idempotent
- [x] Resolver treats content matcher exceptions as safe misses
- [x] Preview vs apply semantics are consistent end-to-end
- [x] API and CLI policy override behavior have focused coverage
- [x] Engine applies per-path configs and policy registries correctly

#### [Must] Tooling / dependency / release ecosystem

- [ ] Decision made on long-term color backend policy (`yachalk` confinement or removal)
- [ ] Formatter/tool configuration split stabilized and documented
  - [ ] `.mdformat.toml`
  - [ ] `.taplo.toml`
- [ ] Tooling environments verified to consume the same formatter/plugin/tool expectations:
  - [ ] nox
  - [ ] pre-commit
  - [ ] local `.venv`
  - [ ] editor integrations
  - [ ] CI
  - [ ] artifact-based release workflow
- [x] Artifact-based CI → release pipeline implemented and documented
- [ ] Positive release-path rehearsal accepted as complete for the path to `1.0.0`
  - [x] first prerelease flow (`v1.0.0a1`) succeeded
  - [ ] remaining follow-up issues, if any, resolved or explicitly accepted

### Strongly recommended (but not blockers)

These should ideally be completed for 1.0, but may be deferred more easily if needed.

#### [Recommended] Registry / resolution

- [ ] Decide whether the local-key compatibility view in `FileTypeRegistry` remains a supported 1.0
  feature
- [ ] Resolution helper surface reviewed for public/internal stability
- [ ] Canonical terminology (`qualified_key`, `file_type_id`, `local_key`, etc.) reviewed one final
  time across docs and public surfaces

#### [Recommended] Human output

- [ ] Human-facing registry output reviewed/frozen for qualified identifier presentation
- [ ] Diff rendering policy reviewed across pipeline commands
- [ ] Markdown layout direction explicitly documented (stay text-equivalent vs evolve later)

#### [Recommended] Machine output

- [x] Add stable examples for any remaining command categories in `docs/dev/machine-formats.md`
- [x] Add examples showing flattened config/TOML diagnostics in both JSON and NDJSON forms where
  relevant
- [x] Add a short explicit note on the flattened config-diagnostics contract if that remains the 1.0
  decision
- [x] Edge-case coverage reviewed for confidence in frozen schemas
  - [x] coverage audit performed on core/config/pipeline/registry/version machine modules
  - [x] no remaining uncovered schema-relevant blind spots identified for frozen machine contracts
  - [x] dedicated CLI machine contract tests now pass for config, pipeline, version, and registry
  - [x] config command machine tests now cover flattened staged diagnostics behavior
  - [x] version command machine tests now cover JSON and NDJSON output
  - [x] registry command machine tests now cover flattened JSON envelopes, NDJSON record kinds,
    detail levels, and ordering

#### [Recommended] CI / release architecture

- [ ] Decide whether the current artifact-based CI → release split should remain the stable 1.0
  release architecture or later be factored into reusable workflow/release-infra patterns
- [ ] Decide whether workflow formatting/style expectations should stay editor-policy-only or be
  documented explicitly in contributor-facing CI guidance
- [ ] Decide whether the explicit `tests` matrix setup should remain as-is or later reuse more of
  the shared CI bootstrap model

### Post-1.0 follow-up (nice-to-have)

These items are explicitly reasonable to defer.

#### [Post-1.0] Product / architecture

- [ ] Implement in-memory pipeline support if deferred for 1.0
- [ ] Revisit whether configuration schema versioning needs an explicit version key
- [ ] Revisit whether staged validation details should be exposed more directly in
  CLI/API/machine-output contracts beyond the current flattened compatibility diagnostics view
- [ ] Revisit whether `strict_config_checking` should eventually be renamed once 1.0 contract
  stability no longer constrains config-key naming

#### [Post-1.0] Human output

- [ ] Further Markdown layout evolution (tables, grouped sections, richer structures)
- [ ] Generalize or refine the “primary hint” concept
- [ ] Evaluate theme/style configurability and semantic style exposure

#### [Post-1.0] Tooling / ecosystem

- [ ] Revisit long-term CLI framework choice (Click vs alternative)
- [ ] Further refactor GitHub workflow structure into reusable workflow/release-infra patterns if
  still worthwhile

______________________________________________________________________

Only when all items in the “Must finish before 1.0” section are completed or explicitly deferred
with rationale should `1.0.0` final be cut. The first 1.0 prerelease tag (`v1.0.0a1`) has already
served as a meaningful part of the release-path rehearsal and final contract validation, but it does
not replace the remaining contract-freeze decisions listed above.
