<!--
topmark:header:start

  project      : TopMark
  file         : roadmap.md
  file_relpath : docs/dev/roadmap.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark stable 1.x roadmap

## Motivation / Why this matters

TopMark 1.0 has completed its stabilization and release-readiness cycle. The major architecture
refactors, contract-freeze decisions, CI/release workflow stabilization, documentation governance
work, late-beta validation passes, release-candidate validation, final 1.0 release preparation, and
initial 1.0.1 patch-release hardening have been completed. The roadmap now focuses on preserving
stable 1.x behavior, tracking explicit post-1.0 deferrals, and recording future evolution areas
without reopening frozen 1.0 contracts.

This roadmap now serves two purposes:

- a **release-governance record** for the frozen 1.0 contracts, explicit deferrals, and stable 1.x
  maintenance posture;
- a **strategic planning reference** for broad future directions that are intentionally not yet
  actionable issue scope.

This roadmap is not the canonical backlog. Actionable work belongs in GitHub issues and pull
requests; release outcomes belong in `CHANGELOG.md`; detailed 1.0 stabilization history belongs in
[Road to TopMark 1.0](./road-to-1.0.md). The roadmap should only keep context that helps maintainers
understand stable-line scope boundaries, deferred architecture directions, and why broad future work
should not be treated as unplanned stable-line maintenance.

After the final `1.0.0` release and first `1.0.1` patch-release preparation, this roadmap remains a
concise governance reference. Detailed achievements and design decisions are tracked in
[Road to TopMark 1.0](./road-to-1.0.md), so this file can remain focused on stable 1.x maintenance,
compatibility preservation, and post-1.0 scope.

A key deferred post-1.0 opportunity remains support for data that is not naturally file-backed:
generated code, editor buffers, CI-provided snippets, or API-driven integrations. Today, almost all
of TopMark's processing pipeline assumes filesystem I/O, which makes testing heavier, limits reuse,
and complicates future integrations. This broader direction is now tracked as the future streaming
pipeline architecture work, initiated while fixing issue #52.

Future in-memory pipeline support would enable:

- Faster, more isolated tests without filesystem setup/teardown
- Cleaner API boundaries (pipeline as a pure transformation)
- Future integrations (editors, LSPs, CI bots) without temporary files
- Clearer separation between what TopMark does and how input is obtained

For the stable 1.x line, the priority is to keep the already-refactored system stable, predictable,
well-documented, reproducible in CI/release environments, and operationally transparent while
continuing to treat new integration scope as post-1.0 evolution.

______________________________________________________________________

## Roadmap governance

Use this page as a maintainer-facing planning document, not as a parallel issue tracker.

Roadmap content should be limited to:

- stable-line maintenance posture and compatibility boundaries;
- strategic directions that are too broad or early for a single GitHub issue;
- explicit deferrals that explain why work is out of scope for the current stable line;
- links to canonical issues, pull requests, release notes, or design documents when details already
  live elsewhere.

Do not use this page for:

- task-level backlog items that can be tracked as GitHub issues;
- release-note history that belongs in `CHANGELOG.md`;
- completed stabilization narrative that belongs in [Road to TopMark 1.0](./road-to-1.0.md);
- duplicated acceptance criteria from open issues or pull requests.

When a roadmap item becomes actionable, create or update a GitHub issue and keep only a concise
strategic note here. When an item is completed, either remove it from the active roadmap or move any
lasting rationale to the appropriate design, release, or historical document.

______________________________________________________________________

## Stable 1.x baseline

The 0.12 development line, 1.0 alpha/beta series, `1.0.0rc1` validation, final 1.0 release
preparation, and initial stable-line patch-release work completed the major stabilization work
needed for the 1.x line. Detailed historical achievements and design decisions belong in
[Road to TopMark 1.0](./road-to-1.0.md), `CHANGELOG.md`, and the closed GitHub issues and pull
requests that implemented them.

This roadmap keeps only the maintainer-facing baseline that affects stable 1.x governance:

- registry, resolution, and file-type identity contracts are explicit, namespace-aware, and
  compatibility-governed;
- configuration loading follows the TOML → layered configuration → runtime overlay split, with
  discovery anchors and source identity handled as part of the documented configuration contract;
- filesystem identity semantics now cover symlinked workspace roots, configuration-source identity,
  public API compatibility boundaries, and hard-link blocking for mutation targets;
- CLI behavior, exit codes, command applicability, STDIN handling, human output, and
  machine-readable output remain treated as externally observable contracts;
- documentation conventions, documentation-pipeline validation, changelog hygiene, and prose
  consistency are established as ongoing governance mechanisms;
- CI and release workflow hardening, including Windows symlink coverage and GitHub Actions pin-audit
  repair support, are handled through focused issues and pull requests rather than roadmap-level
  task tracking;
- in-memory and streaming pipeline support, richer staged diagnostics exposure, registry
  query/filter commands, schema versioning, generated command-help documentation, Markdown output
  refactoring, and broader workflow factoring remain explicitly deferred beyond the current stable
  maintenance scope.

Recent post-1.0 governance and maintenance work confirms that TopMark now operates primarily through
GitHub issue and pull-request tracking. The roadmap should therefore avoid repeating completed issue
scope, PR summaries, or release-note history. It should instead explain why the stable 1.x line is
constrained, which broad future directions are intentionally deferred, and where contributors should
look for actionable work.

______________________________________________________________________

## Breaking changes introduced so far

This section summarizes the externally relevant breaking changes introduced during the 0.12 refactor
series and the 1.0 alpha/beta stabilization line. It is retained in the roadmap for final 1.0
release validation because downstream users, plugin authors, documentation readers, and automation
consumers may still need to compare older alpha/beta behavior with the frozen 1.0 contracts.

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

- `check` / `strip` use `WOULD_CHANGE (3)` for dry-run would-change results;
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

These changes are now treated as frozen 1.0 contracts. Final release preparation should preserve and
validate those contracts rather than introduce new breaking changes.

______________________________________________________________________

## Active strategic directions

The large architectural redesign, contract-freeze work, documentation-governance effort,
machine-output stabilization, CI/release workflow hardening, typing cleanup, late-beta validation,
final 1.0 release, and first stable-line hardening passes are complete.

Remaining roadmap content should be limited to broad directions that are intentionally too large or
too early for a single actionable issue. When a direction becomes actionable, track the concrete
work in GitHub issues and leave only the stable-line rationale here.

### Stable 1.x maintenance posture

Stable 1.x maintenance is limited to:

- post-release validation in realistic environments;
- downstream ecosystem and automation compatibility observation;
- targeted hardening from concrete post-release findings;
- preserving documentation and output-contract consistency;
- monitoring CI, release, dependency, and workflow health through focused maintenance issues;
- and maintaining explicit post-1.0 scope boundaries.

Stable 1.x maintenance is not expected to introduce broad architectural redesign, new output
contracts, new configuration semantics, or new filesystem identity semantics unless a concrete
compatibility or correctness issue requires it.

### Deferred architecture directions

The following remain strategic post-1.0 directions rather than active stable-line maintenance:

- in-memory and streaming pipeline architecture for generated code, editor buffers, CI-provided
  snippets, API-driven integrations, and lighter-weight tests;
- richer registry query/filter and introspection commands;
- explicit configuration schema versioning;
- broader staged-validation exposure where it would improve public diagnostics without leaking
  internal implementation details;
- generated command-help documentation and help-layout refinements;
- Markdown output refactoring where it naturally follows from presentation-layer evolution;
- broader workflow factoring or infrastructure extraction once repeated maintenance work justifies
  it.

These directions should become GitHub issues only when their intended scope, compatibility impact,
and acceptance criteria are clear enough for reviewable implementation.

### Frozen 1.x contract areas

The following areas are frozen for 1.x and should now primarily receive compatibility validation,
documentation clarification, focused confidence-building tests, downstream-consumer verification, or
concrete correctness fixes:

- registry and file-type identity semantics;
- CLI applicability, STDIN, verbosity, quiet, and exit-code behavior;
- TOML/config/runtime layering and staged-validation boundaries;
- filesystem identity, path serialization, configuration-source identity, symlink, and hard-link
  semantics;
- machine-readable output schemas and naming conventions;
- TEXT and Markdown human-output behavior;
- artifact-based CI → release publication;
- uv/nox-based tooling and metadata-driven CI Python-version handling;
- and documentation/prose-governance validation.

______________________________________________________________________

## Stable-line validation checklist

TopMark 1.x follows a contract-first maintenance strategy: externally observable behavior should
remain stable, documented, reproducible, and tested.

Use this checklist as a stable-line validation reminder, not as a task tracker:

- [x] CLI, presentation, API, and runtime/core responsibilities are separated and documented
- [x] TOML → configuration → runtime layering is stabilized
- [x] public/internal API boundaries are reviewed and documented
- [x] filesystem-backed execution is accepted for stable 1.x
- [x] in-memory and streaming pipeline support is explicitly deferred beyond the current stable
  maintenance scope
- [x] namespace-aware file-type identity and registry binding semantics are frozen
- [x] symlink, hard-link, canonical path, and configuration-source identity semantics are documented
  and regression-tested where practical
- [x] CLI applicability, STDIN behavior, exit-code behavior, and human-output behavior are frozen
- [x] JSON/NDJSON machine-readable output schemas and path serialization rules are stabilized
- [x] documentation conventions, snippet governance, documentation-pipeline validation, prose
  hygiene, and changelog hygiene are part of the maintenance workflow
- [x] uv/nox tooling, metadata-driven CI Python-version handling, and artifact-based release
  publication are established
- [x] Windows symlink-dependent CI coverage is enforced rather than silently skipped
- [x] CI/tooling maintenance items are handled through focused GitHub issues and pull requests

The stable 1.x maintenance path should avoid introducing new broad scope, architectural churn, or
output-contract redesign unless a concrete compatibility or correctness issue requires it.
