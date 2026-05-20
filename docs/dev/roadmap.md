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

The large architectural redesign, contract-freeze work, documentation-governance effort,
machine-output stabilization, CI/release workflow hardening, typing cleanup, and late-beta
validation work are complete.

The remaining work before `1.0.0` is intentionally narrow:

- release-candidate validation in realistic environments;
- downstream ecosystem and automation compatibility observation;
- targeted hardening from concrete findings;
- preserving documentation and output-contract consistency;
- monitoring the finalized CI/release metadata and uv-cache ownership model across real workflow
  runs;
- and maintaining explicit post-1.0 scope boundaries.

The release-candidate phase is therefore not expected to introduce further architectural redesign or
new broad contract changes.

### Release-candidate validation posture

The following areas are considered frozen for 1.0 and should now primarily receive:

- compatibility validation;
- wording/documentation clarification;
- focused test additions;
- downstream-consumer verification;
- or concrete release-blocking fixes.

Frozen areas include:

- registry and file-type identity semantics;
- CLI applicability, STDIN, verbosity, quiet, and exit-code behavior;
- TOML/config/runtime layering and staged-validation boundaries;
- machine-readable output schemas and naming conventions;
- TEXT and Markdown human-output behavior;
- artifact-based CI → release publication;
- uv/nox-based tooling and metadata-driven CI Python-version handling;
- and documentation/prose-governance validation.

### Registry and resolution

Registry and resolution behavior are frozen for 1.0.

The accepted 1.0 model includes:

- canonical qualified file-type identifiers;
- unambiguous local identifiers at public boundaries;
- explicit registry bindings;
- deterministic ambiguity handling;
- and `topmark probe` plus `topmark.api.probe()` as the supported explainability surfaces.

Registry query/filter commands, richer discovery tooling, and broader registry introspection remain
explicitly deferred beyond 1.0.

Remaining work is limited to downstream validation, compatibility preservation, generated-reference
consistency, and targeted hardening.

### In-memory pipeline support

In-memory pipeline support is explicitly deferred beyond 1.0.

The 1.0 release continues using the filesystem-backed execution model together with the existing
STDIN runtime mechanisms.

Future post-1.0 work may introduce:

- an `InputSource` abstraction;
- memory-backed execution;
- mixed file/memory input models;
- and lighter-weight memory-oriented test strategies.

This is an intentional scope deferral rather than unfinished 1.0 work.

### API, CLI, and presentation boundaries

The API/CLI/presentation separation is frozen for 1.0.

Remaining work is limited to:

- consistency validation;
- release-candidate wording cleanup;
- preserving Click isolation from presentation/core modules;
- preserving presentation isolation from domain/runtime logic;
- and maintaining the documented public/internal API boundaries.

The following remain intentionally internal:

- `topmark.api.runtime`;
- low-level runtime orchestration helpers;
- `PolicyOverrides` / `ConfigOverrides`;
- low-level resolver/probe implementation helpers;
- and staged-validation implementation details.

### Configuration and validation

The TOML → layered configuration → runtime overlay architecture is frozen for 1.0.

The accepted 1.0 behavior includes:

- `[config].strict` as the configuration-loading strictness control;
- canonical qualified file-type identifiers as the normalized internal representation;
- flattened compatibility diagnostics at public boundaries;
- internal staged validation logs;
- and runtime-facing TOML sections such as `[writer]` remaining outside layered configuration.

Explicit configuration schema versioning and broader staged-validation exposure remain deferred
beyond 1.0.

Remaining work is limited to validation, compatibility preservation, and focused documentation or
warning/error clarification.

### Output contracts

Output-contract work is complete and frozen for 1.0.

Machine-readable output:

- remains schema driven;
- uses flattened domain-specific envelopes;
- emits canonical qualified identifiers where available;
- and treats process status as the CLI exit code rather than JSON payload state.

Human output:

- keeps TEXT as the console-oriented format;
- keeps Markdown document-oriented;
- keeps verbosity/quiet behavior TEXT-specific;
- and keeps semantic styling routed through the current `yachalk`-based presentation layer.

Rich or `rich-click` migration remains explicitly deferred beyond 1.0 unless a concrete release
blocker appears.

Remaining work is limited to compatibility validation, wording consistency, and downstream consumer
verification.

### Tooling, CI, and release workflow

The uv/nox tooling model and artifact-based release workflow are frozen for 1.0.

Accepted 1.0 behavior includes:

- `uv.lock` as the canonical lock artifact;
- metadata-driven CI Python-version resolution through `nox -s print_python_matrix`;
- explicit uv cache ownership through `actions/cache`;
- artifact creation in CI on tag pushes;
- and privileged release publication consuming CI-built artifacts.

Remaining work is limited to:

- observing the finalized workflow model in real runs;
- validating metadata/reporting consistency;
- monitoring cache behavior;
- validating downstream packaging/install behavior;
- and targeted hardening from concrete findings.

Broader workflow factoring and infrastructure extraction remain deferred beyond 1.0.

### Coverage and validation posture

Coverage remains a confidence-building signal rather than a release gate.

The canonical CI coverage workflow is now integrated and validated through real GitHub workflow
runs. Coverage reporting remains informational and publishes:

- GitHub Step Summary output;
- HTML artifacts;
- XML artifacts;
- and JSON artifacts.

README coverage-badge publication remains intentionally deferred until the published signal proves
stable and meaningful over time.

Additional coverage expansion before `1.0.0` should remain focused on:

- orchestration-heavy paths;
- integration-heavy behavior;
- or concrete confidence gaps discovered during RC validation.

### Human-facing policy and behavior

The user-facing policy, terminology, reporting, and command-behavior decisions are frozen for 1.0.

Accepted 1.0 behavior includes:

- `report` replacing legacy `skip_*` behavior;
- `header_mutation_mode` replacing legacy add/update flags;
- the current default “all supported file types” processing model;
- probe-based resolution explainability;
- and stable TEXT/Markdown/machine-output separation.

Public API callers continue using stable string policy tokens for 1.0. A dedicated public enum
surface may be reconsidered after the final release.

### Overall status

TopMark is now in the release-candidate stabilization phase.

The remaining work is primarily:

- real-world RC validation;
- ecosystem compatibility verification;
- downstream machine-readable output validation;
- documentation consistency preservation;
- coverage-confidence monitoring;
- workflow/release observation;
- and explicit post-1.0 follow-up management.

The project should avoid introducing new broad scope or contract changes unless a concrete
release-blocking issue is discovered.

______________________________________________________________________

## 1.0 readiness checklist

TopMark 1.0 follows a contract-first release strategy: externally observable behavior must remain
stable, documented, reproducible, and well tested.

The major architecture refactors, beta stabilization passes, contract freezes, documentation
harmonization, release-path rehearsals, install-smoke validation, CI/release hardening, coverage
integration, prose/documentation governance, and late-beta typing cleanup are complete.

This checklist now records:

- the frozen 1.0 contract surface;
- explicit post-1.0 deferrals;
- and the remaining RC-validation posture before the final `1.0.0` release.

### Frozen 1.0 contract areas

The following areas are considered frozen for 1.0 and should not receive new broad redesign unless
required by a concrete release blocker:

#### Architecture and runtime boundaries

- [x] CLI, presentation, API, and runtime/core responsibilities separated and documented
- [x] TOML → configuration → runtime layering stabilized
- [x] public/internal API boundaries reviewed and frozen
- [x] mutable/frozen runtime naming finalized
- [x] filesystem-backed execution model accepted for 1.0
- [x] in-memory pipeline support explicitly deferred beyond 1.0

#### Registry and resolution readiness

- [x] namespace-aware file-type identity contract frozen
- [x] qualified/local identifier semantics documented and validated
- [x] explicit registry/binding model stabilized
- [x] deterministic ambiguity handling implemented and tested
- [x] `topmark probe` and `topmark.api.probe()` accepted as the supported explainability surfaces
- [x] richer registry query/filter tooling deferred beyond 1.0

#### CLI behavior and human output

- [x] CLI applicability rules documented and enforced
- [x] STDIN behavior frozen around `-` plus `--stdin-filename`
- [x] exit-code contract documented, tested, and frozen
- [x] TEXT/Markdown/machine-output separation stabilized
- [x] verbosity and quiet semantics stabilized
- [x] warning/error wording reviewed for consistency
- [x] command-page structure conventions harmonized
- [x] Rich / `rich-click` migration explicitly deferred beyond 1.0

#### Machine-readable output

- [x] JSON/NDJSON output schemas stabilized
- [x] `(outcome, reason, count)` summary rows frozen
- [x] registry/configuration/probe payload naming frozen
- [x] canonical qualified identifiers emitted where resolved
- [x] machine contracts covered by focused tests
- [x] flattened compatibility diagnostics accepted as the 1.0 contract
- [x] richer staged-validation exposure deferred beyond 1.0

#### Configuration and validation readiness

- [x] `[config].strict` frozen as the configuration-loading strictness control
- [x] TOML/config/runtime split documented and implemented
- [x] effective per-path runtime configuration implemented
- [x] staged validation retained primarily as an internal mechanism
- [x] flattened diagnostics stabilized at public boundaries
- [x] runtime-facing TOML sections such as `[writer]` preserved in configuration snapshots
- [x] configuration schema versioning deferred beyond 1.0

#### Pipeline behavior and testing

- [x] preview/apply behavior stabilized end-to-end
- [x] empty and empty-like file handling stabilized
- [x] unmatched-glob semantics frozen and tested
- [x] namespace-aware resolution behavior covered by tests
- [x] line-ending policy audited and frozen
- [x] typed result-object cleanup substantially completed before RC
- [x] coverage-driven late-beta stabilization completed

#### Tooling, release workflow, and documentation governance

- [x] uv/nox tooling model stabilized
- [x] artifact-based CI → release publication validated
- [x] metadata-driven CI Python-version handling stabilized
- [x] explicit uv cache ownership stabilized
- [x] install-smoke validation integrated across Linux/macOS/Windows
- [x] `setuptools-scm` versioning model frozen
- [x] documentation hygiene integrated into release validation
- [x] Python code-prose hygiene integrated into release validation
- [x] changelog hygiene validation integrated into documentation governance
- [x] canonical documentation conventions and snippet governance stabilized
- [x] coverage reporting integrated as a non-blocking confidence signal
- [x] README coverage badge intentionally deferred pending longer-term signal stability

### Remaining RC-validation posture

Before cutting final `1.0.0`, continue validating the frozen contracts through:

- real-world release-candidate usage;
- downstream ecosystem compatibility observation;
- install/release workflow observation;
- machine-readable output validation;
- documentation consistency preservation;
- targeted confidence-building tests;
- and focused release-blocking fixes where necessary.

The remaining path to final `1.0.0` should avoid introducing new broad scope, architectural churn,
or output-contract redesign unless a concrete release blocker is discovered.

______________________________________________________________________

`1.0.0rc1` should be cut only after the frozen contract areas above remain green through the local
and CI release-validation gates. The alpha series served as the contract-stabilization and
release-path rehearsal phase, while the beta series validated the frozen contracts, release
pipeline, GitHub prerelease visibility, CI/release metadata handling, coverage-reporting behavior,
documentation governance, changelog hygiene, prose hygiene, terminology stability, and
cross-platform installation behavior.

After `1.0.0rc1`, the path to final `1.0.0` should be limited to preserving compatibility,
collecting release-candidate feedback, validating downstream ecosystem behavior, monitoring the CI
coverage signal, observing the finalized CI/release metadata and cache-ownership model across real
workflow runs, and applying focused release-blocking fixes only. New broad scope, architectural
churn, and output-contract redesign remain out of scope unless required by a concrete release
blocker.
