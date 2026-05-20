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

TopMark 1.0 is now entering the release-candidate phase. The major architecture refactors,
contract-freeze decisions, CI/release workflow stabilization, documentation governance work, and
late-beta validation passes are complete. The remaining work is focused on preserving stable
behavior, validating the frozen release candidate in realistic environments, and addressing only
concrete release-blocking findings.

This roadmap now serves two purposes:

- a **release-governance record** for the frozen 1.0 contracts, explicit deferrals, and remaining
  release-candidate validation posture;
- a **historical stabilization ledger** for the architectural, documentation, CI/release, and
  testing decisions made during the 0.12 development line and 1.0 alpha/beta series.

As the project moves from `1.0.0rc1` toward `1.0.0`, the roadmap should become progressively less of
a working checklist and more of a concise governance reference. Detailed achievements and design
decisions may be extracted later into a dedicated release-retrospective document or GitHub project
page so this file can remain focused on release readiness and post-1.0 scope.

A key deferred post-1.0 opportunity remains support for data that is not naturally file-backed:
generated code, editor buffers, CI-provided snippets, or API-driven integrations. Today, almost all
of TopMark's processing pipeline assumes filesystem I/O, which makes testing heavier, limits reuse,
and complicates future integrations.

Future in-memory pipeline support would enable:

- Faster, more isolated tests without filesystem setup/teardown
- Cleaner API boundaries (pipeline as a pure transformation)
- Future integrations (editors, LSPs, CI bots) without temporary files
- Clearer separation between what TopMark does and how input is obtained

For 1.0 itself, the priority is to keep the already-refactored system stable, predictable,
well-documented, reproducible in CI/release environments, and operationally transparent while
continuing to defer new integration scope until after the final release.

______________________________________________________________________

## Done so far

The 0.12 development line and 1.0 alpha/beta series completed the major stabilization work needed
for the 1.0 release-candidate phase. The system is now aligned around a clean *TOML → Configuration
→ Runtime → Pipeline → Presentation* model, with explicit registry bindings, separated
CLI/presentation layers, schema-driven machine output, documented CLI behavior, hardened
configuration validation, and artifact-based release automation.

Detailed historical achievements and design decisions have been extracted to
[Road to TopMark 1.0](./road-to-1.0.md). This roadmap now keeps only the release-governance summary
needed for `1.0.0rc1` and final `1.0.0` readiness.

Completed stabilization themes:

- registry, resolution, and file-type identity contracts are explicit and namespace-aware;
- CLI behavior, exit codes, command applicability, STDIN handling, and human/machine output
  contracts are frozen for 1.0;
- configuration loading follows the TOML → layered configuration → runtime overlay split;
- pipeline behavior is deterministic, idempotent, preview/apply aware, and policy driven;
- documentation governance, terminology, command-page structure, snippets, and prose hygiene are
  established and validated;
- CI, release, packaging, install-smoke validation, coverage reporting, and uv/nox-based tooling are
  automated, documented, and validated through real workflow runs;
- in-memory pipeline support, richer staged diagnostics exposure, registry query/filter commands,
  schema versioning, Rich migration, and broader workflow factoring are explicitly deferred beyond
  1.0.

At RC time, remaining work is no longer broad architectural redesign. It is limited to release
candidate validation, ecosystem observation, downstream compatibility checks, documentation
clarifications, and concrete release-blocking fixes.

______________________________________________________________________

## Breaking changes introduced so far

This section summarizes the externally relevant breaking changes introduced during the 0.12 refactor
series and the 1.0 alpha/beta stabilization line. It is retained in the roadmap for RC validation
because downstream users, plugin authors, documentation readers, and automation consumers may still
need to compare older alpha/beta behavior with the frozen 1.0 contracts.

For the full historical stabilization narrative, see [Road to TopMark 1.0](./road-to-1.0.md).

### Registry, resolution, and file-type identity

TopMark no longer relies on implicit processor registration, decorator-based bootstrap behavior, or
legacy registry entry points. Registry behavior is now explicit and split by responsibility:

- file-type registration;
- processor registration;
- binding file types to processors.

Downstream integrations must use the explicit registry/binding model instead of older bootstrap
helpers such as `register_all_processors()` or implicit processor discovery.

File-type identity is now namespace-aware:

- canonical identity uses qualified keys such as `topmark:python`;
- local identifiers such as `python` are accepted only when unambiguous;
- ambiguous local identifiers require the qualified form;
- machine output, registry output, diagnostics, configuration normalization, and policy lookup use
  canonical qualified identifiers where a resolved identity is available.

Result: registry and resolution behavior is deterministic and plugin-ready, but callers using older
registry helpers, local-only identifiers, or processor-grouped binding views must update.

### Configuration, TOML, and runtime boundaries

Configuration is no longer treated as a single mixed layer. The 1.0 architecture separates:

- TOML parsing and whole-source validation;
- layered configuration merge and provenance;
- per-path effective runtime configuration;
- execution-time runtime options.

Runtime-only behavior such as apply/preview and STDIN handling is modeled separately from layered
configuration. TOML-authored runtime sections such as `[writer]` remain outside layered
configuration while still appearing in configuration output snapshots.

The public configuration surface changed in several important ways:

- `[config].strict` is the finalized configuration-loading strictness option;
- `add_only` / `update_only` were replaced by `header_mutation_mode`;
- `skip_compliant` / `skip_unsupported` were replaced by `report`;
- `policy_by_type`, `include_file_types`, and `exclude_file_types` share the same qualified/local
  file-type identifier contract;
- resolved runtime `policy_by_type` maps use canonical qualified file-type keys;
- staged validation remains primarily internal, with flattened compatibility diagnostics exposed at
  exception, presentation, and machine-readable output boundaries.

Result: configuration behavior is clearer, typed, and reproducible, but callers relying on older
helper locations, older policy tokens, or local-only file-type keys must update.

### CLI behavior, runtime execution, and human output

The CLI behavior contract was narrowed and stabilized for 1.0.

Important changes include:

- `TEXT` is the canonical plain human-output format; legacy `DEFAULT` output naming was removed;
- human rendering is separated from CLI runtime and printing;
- verbosity, quiet, and color controls are command-level concerns rather than root-only global
  behavior;
- `-v` / `--verbose` and `-q` / `--quiet` apply only to TEXT output where supported;
- Markdown output is document-oriented and ignores TEXT-oriented verbosity and quiet controls;
- JSON/NDJSON output is machine-readable and ignores human presentation controls;
- pure informational commands such as `version`, `config defaults`, `config init`, and registry
  commands do not expose `--quiet`.

Command applicability is stricter:

- `strip` rejects check-only mutation, insertion, and generated-header formatting options;
- `probe` rejects mutation, write-mode, diff, summary/reporting, and generated-header controls;
- path-processing commands intentionally do not expose a `--stdin` option flag;
- content STDIN uses `-` plus `--stdin-filename`;
- file-agnostic commands reject positional paths and file-processing STDIN modes.

The CLI exit-code contract is now enum-backed, documented, and tested. Notable stable outcomes
include:

- `check` / `strip` use `WOULD_CHANGE (2)` for dry-run would-change results;
- explicit missing literal inputs produce `FILE_NOT_FOUND (66)`;
- unmatched globs are soft discovery diagnostics for `check` / `strip`;
- `probe` reports unresolved, unsupported, filtered, and unmatched-glob semantic outcomes with
  `UNSUPPORTED_FILE_TYPE (69)`.

Several low-level runtime helpers now return typed result objects rather than positional tuples.
Internal and advanced callers should consume named fields instead of relying on tuple positions.

Result: CLI behavior is more explicit, scriptable, and stable, but existing invocation habits,
output snapshots, and low-level runtime integrations may need adjustment.

### Machine-readable output contracts

Machine-readable output is now schema-driven, domain-scoped, and separated from human presentation.

Breaking output-contract changes include:

- pipeline summaries use explicit flat `(outcome, reason, count)` rows;
- `config check` uses the explicit `config_check` payload/record kind;
- `config dump --show-layers` emits layered provenance before the final flattened runtime
  configuration payload;
- registry JSON output uses flattened domain-specific envelopes for file types, processors, and
  bindings;
- `detail_level` reflects projection depth in machine output where emitted;
- registry, configuration, resolution, and probe payloads emit canonical qualified file-type
  identifiers where a resolved identity is available;
- probe machine output uses per-path probe records and includes filtered explicit inputs;
- JSON/NDJSON payloads do not imply process status, which remains the CLI exit code.

Result: machine-readable formats are more stable and automation-friendly, but downstream consumers
that relied on older payload names, outcome-keyed summaries, or older registry shapes must update.

### Documentation and generated-site behavior

Documentation validation is stricter than before. Generated API/reference pages, strict MkDocs
builds, built-site link checks, documentation hygiene, code-prose hygiene, and changelog heading
validation are now part of the local and release validation ecosystem.

Important behavior changes include:

- generated API/reference pages are part of the docs build contract;
- built-site link checking gates release-artifact creation on tag pushes;
- documentation hygiene validates snippet includes, include paths, section separators, heading
  conventions, accidental macOS resource files, and changelog heading shape;
- Python code-prose hygiene validates comments, docstrings, and prose-oriented string literals;
- the terminology glossary moved from `docs/dev/terminology.md` to `docs/terminology.md`;
- repeated terminology notes now use `_snippets/terminology.md`.

Result: documentation is more accurate and better governed, but docs contributors must follow the
stricter generated-site, snippet, heading, and prose-hygiene rules.

### Developer tooling, dependency management, and release workflow

The contributor and release workflow changed significantly:

- tox was removed; contributors and CI now use nox with uv-backed environments;
- `uv.lock` is the canonical lock artifact;
- committed `requirements*.txt` / `constraints.txt` files are no longer the primary dependency
  management model;
- package versions are derived from Git tags through `setuptools-scm`;
- release publishing no longer builds from repository source in the privileged workflow;
- CI builds release artifacts on tag pushes;
- the privileged release workflow downloads, verifies, and publishes CI-built artifacts;
- compact PEP 440 prerelease tags are preferred (`vX.Y.ZaN`, `vX.Y.ZbN`, `vX.Y.ZrcN`).

CI behavior also changed:

- pull-request jobs are gated more aggressively by changed-file buckets;
- supported and canonical Python versions are derived through `nox -s print_python_matrix`;
- compatibility-matrix and canonical single-version jobs consume resolved metadata rather than
  duplicated workflow literals;
- release workflows retain explicit release-tooling Python versions while reporting non-blocking
  drift warnings against canonical CI metadata;
- uv cache ownership is centralized through explicit `actions/cache` integration rather than mixed
  ownership with `setup-uv` built-in caching.

Runtime dependency metadata was tightened after isolated-environment validation revealed implicit
runtime imports. In particular, `typing-extensions` and `packaging` are now treated as runtime
dependencies where required.

Result: the workflow is more secure, reproducible, and observable, but maintainers and contributors
must use the uv/nox/artifact-based release model rather than older tox, manual-version, or
source-build-in-release assumptions.

### Overall impact

The 1.0 breaking changes are not isolated helper removals; they reflect a new system shape:

- explicit registry and binding model;
- namespace-aware file-type identity;
- layered TOML/configuration/runtime boundaries;
- explicit preview/apply runtime behavior;
- schema-driven machine output;
- separated human presentation;
- stricter CLI applicability and exit-code contracts;
- uv/nox-based tooling;
- artifact-based release publication;
- and stricter documentation/prose governance.

These changes are now treated as frozen 1.0 contracts. The release-candidate phase should validate
those contracts in realistic environments rather than introduce new breaking changes.

______________________________________________________________________

## Still undecided / still to do

This section captures the remaining **post-beta stabilization, ecosystem validation, and targeted
hardening work** before `1.0.0`.

The large structural refactors, contract-freeze decisions, beta validation gates,
documentation-governance work, command-page freeze review, terminology alignment, TOML-template
harmonization, prose-hygiene tooling work, late-beta typing/ownership cleanup, and CI/release
workflow stabilization are complete.

What remains is primarily:

- real-world beta feedback,
- downstream ecosystem validation,
- compatibility preservation,
- targeted hardening from concrete findings,
- monitoring the new coverage signal and explicit README badge deferral,
- observing the finalized CI/release metadata and cache-ownership model across real runs,
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
- Keep CI/release Python metadata and release-tooling provenance reporting as workflow concerns, not
  public Python API surfaces.
- Treat the late-beta internal typing/ownership cleanup as substantially complete for RC:
  - protocol/view surfaces were tightened toward read-only semantics where mutation is not intended
  - ambiguous tuple-shaped internal return contracts were replaced with explicit typed result
    objects or DTO-style models where they materially improved clarity
  - further protocol/DTO cleanup should now be incremental and justified by concrete findings rather
    than reopened as broad pre-1.0 refactoring scope

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
- The CI Python-version model is accepted for 1.0:
  - supported and canonical Python versions are resolved through `nox -s print_python_matrix`
  - the main CI workflow consumes the resolved metadata for compatibility-matrix and canonical
    single-version jobs
  - release publication keeps an explicit release-tooling Python runtime and reports non-blocking
    drift warnings against canonical CI metadata
- Workflow formatting/style rules are governed by checked-in tool configuration and release
  validation gates; broader editor-style guidance remains non-blocking for 1.0.
- Keep validating that Nox, pre-commit, local `.venv`, editor integrations, CI jobs, and the
  artifact-based release workflow all consume the same formatter/tool configuration.
- Keep documentation hygiene validation integrated in local and release gates as the documentation
  conventions evolve.
- Keep Python code-prose hygiene validation integrated in local and release gates as comments,
  docstrings, tooling prose, and generated documentation conventions evolve.
- Keep validating that explicit uv cache ownership remains quiet and deterministic across concurrent
  CI jobs.
- Keep monitoring the canonical CI coverage reporting signal now integrated during late-beta
  stabilization:
  - coverage runs through the existing `nox -s coverage` session on Ubuntu using the resolved
    canonical Python version
  - coverage publishes a GitHub Step Summary plus HTML and XML/JSON workflow artifacts
  - coverage remains diagnostic and is not a release-blocking percentage gate
  - README coverage badge adoption remains intentionally deferred until the published signal proves
    stable, representative, and useful over time
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
- **coverage-signal monitoring and README badge deferral now that canonical CI coverage reporting is
  integrated**
- **observation of the finalized CI Python metadata, release-provenance, and uv cache-ownership
  model across real GitHub workflow runs**
- **ongoing coverage expansion for complex orchestration and integration-heavy paths where
  additional confidence is still valuable despite the frozen 1.0 architecture**
- **explicit post-1.0 follow-up for deferred scope**

That means TopMark is now in the late beta stabilization stage of the 1.0 effort: validating the
frozen contracts in realistic environments, preserving compatibility, maintaining documentation and
prose-governance quality, validating downstream ecosystem behavior, observing the finalized workflow
metadata/cache model in real CI runs, and avoiding new scope unless a concrete release blocker
appears.

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
- [x] Coverage-driven late-beta stabilization and typing hardening completed for the frozen 1.0
  contract surface, with remaining follow-up limited to targeted incremental confidence-building
  rather than architectural risk reduction
  - [x] focused coverage expansion added for outcomes, status/context, merge utilities, file-type
    gating, enum mixins, diff rendering, and validation/error-path behavior
  - [x] obsolete, redundant, or effectively dead internal helper layers removed where they no longer
    contributed to the frozen architecture (`rendering/api.py`, redundant rendering package
    structure, introspection-only helpers)
  - [x] presentation-layer diff rendering consolidated under
    `topmark.presentation.formatters.unified_diff`
  - [x] Python 3.10 compatibility regressions discovered during late-beta coverage expansion were
    resolved without weakening Pyright strict-mode guarantees
  - [x] identified read-only protocol tightening and tuple-shaped internal return contract follow-up
    substantially completed before RC using focused frozen value objects and documentation updates
  - [x] Canonical CI coverage reporting integrated as a non-blocking stabilization signal
    - [x] coverage runs through the existing `nox -s coverage` session on Ubuntu using the resolved
      canonical Python version
    - [x] GitHub Actions publishes Step Summary, HTML, XML, and JSON coverage artifacts
    - [x] coverage remains diagnostic rather than percentage-gated for the 1.0 line
    - [x] README coverage badge intentionally deferred pending longer-term signal stability review
    - [x] coverage-reporting behavior validated across real GitHub workflow runs during the beta
      stabilization line

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
- [x] Explicit uv cache ownership stabilized across shared CI bootstrap paths
  - [x] `setup-uv` built-in cache integration disabled in favor of explicit `actions/cache`
    ownership
  - [x] concurrent cache-reservation race warnings eliminated during beta stabilization
  - [x] cache ownership/documentation aligned across workflows and composite bootstrap actions
- [x] Artifact-based CI → release pipeline implemented and documented
- [x] CI/release Python metadata and workflow bootstrap model stabilized and documented
  - [x] supported and canonical Python versions are resolved from `pyproject.toml` through
    `nox -s print_python_matrix`
  - [x] compatibility-matrix and canonical single-version jobs consume resolved metadata rather than
    duplicated version literals
  - [x] release publication intentionally retains an explicit release-tooling Python runtime while
    reporting non-blocking drift warnings against canonical CI metadata
  - [x] shared Python/uv/nox bootstrap behavior documented through the `setup-python-nox`
    composite-action documentation
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
GitHub workflows, release workflow checks, and dedicated install-smoke validation rather than
through standalone pytest-only packaging tests.

- [x] Packaging validation completed
- [x] GitHub prerelease visibility validated for the beta line
  - [x] `v1.0.0b1` and `v1.0.0b2` GitHub prereleases backfilled from existing tags
  - [x] `v1.0.0b3` published as a GitHub prerelease through the release workflow
  - [x] prerelease package publication remains routed to TestPyPI
- [x] `nox -s package_check` builds wheel and sdist artifacts and passes `twine check`
- [x] wheel artifact installs into a clean environment and exposes the `topmark` console script
- [x] sdist artifact installs into a clean environment and exposes the `topmark` console script
- [x] Dedicated install-smoke workflow validates installation and lightweight CLI smoke behavior
  across Linux, macOS, and Windows using built wheel and sdist artifacts
- [x] Coverage workflow/reporting follow-up evaluated and validated during the beta stabilization
  line
  - [x] GitHub workflow coverage reporting added through the canonical `nox -s coverage` session
  - [x] GitHub Step Summary coverage reporting validated
  - [x] HTML and XML/JSON coverage artifacts validated
  - [x] coverage reporting remains informational rather than release-blocking
  - [x] README coverage badge decision recorded: defer until the published signal is stable enough
    to be meaningful
- [x] CI metadata/bootstrap follow-up validated during the beta stabilization line
  - [x] metadata-driven Python-version resolution validated in real GitHub workflow runs
  - [x] release-tooling provenance drift warnings validated as non-blocking diagnostics
  - [x] explicit uv cache ownership validated across concurrent CI jobs
  - [x] CI and release workflow documentation aligned with the finalized bootstrap/cache model
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
- [x] Decide how CI Python-version metadata should be managed for the frozen 1.0 workflow model
  - [x] supported and canonical Python versions are derived from `pyproject.toml` through
    `nox -s print_python_matrix`
  - [x] the compatibility matrix and canonical single-version jobs consume the resolved metadata
    rather than duplicating version literals in the main CI workflow
  - [x] release publication intentionally retains an explicit release-tooling Python runtime while
    reporting non-blocking drift warnings against canonical CI metadata
  - [x] explicit uv cache ownership remains centralized through `actions/cache` rather than mixed
    cache ownership models

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
- [ ] Continue tightening internal protocol/view contracts toward read-only semantics where mutation
  is not intended
- [ ] Replace remaining ambiguous tuple-shaped internal return contracts with explicit typed result
  objects or DTO-style models where this improves clarity without destabilizing the frozen public
  API

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
- [ ] Revisit whether a public README coverage badge adds meaningful signal once the CI coverage
  reporting output has stabilized.

______________________________________________________________________

Only when all items in the "Must finish before 1.0" section are completed or explicitly deferred
with rationale should `1.0.0` final be cut. The 1.0 alpha series served as the
contract-stabilization and release-path rehearsal phase, while the beta stabilization series
validated the frozen contracts, release pipeline, GitHub prerelease visibility, CI/release metadata
handling, coverage-reporting behavior, documentation governance, changelog hygiene, prose hygiene,
terminology stability, and cross-platform installation behavior. The remaining path to final `1.0.0`
is now focused on preserving compatibility, collecting final real-world beta feedback, validating
downstream ecosystem behavior, monitoring the newly integrated CI coverage reporting signal,
observing the finalized CI/release metadata and cache-ownership model across real workflow runs,
continuing targeted post-freeze hardening where appropriate, and avoiding new scope unless concrete
release-blocking issues are identified.
