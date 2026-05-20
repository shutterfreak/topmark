<!--
topmark:header:start

  project      : TopMark
  file         : road-to-1.0.md
  file_relpath : docs/dev/road-to-1.0.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Road to TopMark 1.0

## Purpose

This page records the curated stabilization history behind TopMark 1.0. It extracts the historical
achievement narrative from the active 1.0 roadmap so the roadmap can remain focused on release
candidate governance, explicit deferrals, and final readiness.

The 0.12 development line and the 1.0 alpha/beta series transformed TopMark from a set of evolving
header-processing components into a contract-oriented CLI and Python library with explicit runtime
boundaries, deterministic processing, documented output contracts, strict typing, and reproducible
CI/release automation.

This page is historical and explanatory. For current release status, remaining validation work, and
post-1.0 deferrals, see [TopMark 1.0 Roadmap](./roadmap.md).

______________________________________________________________________

## Stabilization overview

The stabilization effort focused on separating responsibilities that were previously entangled:

- TOML parsing and validation;
- layered configuration resolution;
- runtime execution intent;
- file discovery and file-type resolution;
- pipeline processing;
- human presentation;
- machine-readable output;
- and CI/release automation.

By the end of the beta line, TopMark was aligned around this model:

```text
TOML → Configuration → Runtime → Pipeline → Presentation
```

The main outcomes were:

- explicit registry and binding architecture;
- namespace-aware file-type identities;
- stable CLI behavior and exit-code contracts;
- separated human and machine output systems;
- staged configuration-validation internals with flattened compatibility diagnostics at public
  boundaries;
- deterministic pipeline semantics;
- documented public/internal API boundaries;
- strict documentation and prose-governance tooling;
- artifact-based release publication;
- and canonical CI coverage/reporting workflows.

______________________________________________________________________

## Registry and resolution redesign

The registry system was redesigned into a deterministic, explicit, namespace-aware model.

The final architecture separates:

- `filetypes` for file-type identity;
- `processors` for processor identity;
- `bindings` for relationships between file types and processors.

Implicit registration through decorators or bootstrap scanning was replaced with explicit bindings.
This made registry behavior predictable, testable, and plugin-ready without import-time side
effects.

Legacy bootstrap-oriented entry points such as:

- `topmark.processors.bootstrap`;
- `topmark.processors.registry`;
- `topmark.registry.resolver`;
- `register_all_processors()`;
- `Registry.ensure_processors_registered()`.

were removed during stabilization in favor of explicit registration and binding ownership.

The file-type identifier contract was frozen around qualified keys:

- canonical identities use `<namespace>:<name>`, such as `topmark:python`;
- local identifiers, such as `python`, are accepted only when unambiguous;
- ambiguous local identifiers require the qualified form;
- fuzzy matching, aliases, and implicit namespace fallback are intentionally unsupported.

Resolution was moved into `topmark.resolution.*`, and probe-backed resolution became the shared
evidence model for diagnostics and effective pipeline resolution. The read-only `topmark probe`
command and `topmark.api.probe()` API expose stable resolution DTOs without requiring callers to
consume registry internals.

Result: registry and resolution behavior is explicit, deterministic, explainable, and ready for
future plugin work.

______________________________________________________________________

## CLI and presentation architecture

The CLI and presentation layers were separated into distinct responsibilities:

- `topmark.presentation.*` renders pure output without I/O or Click;
- `topmark.cli.console.*` owns console/runtime concerns;
- `topmark.cli.commands.*` orchestrates commands.

The old emitter-oriented shape was replaced by a clearer distinction between serializers for machine
output and renderers for human output. Rendering is Click-free, testable, and reusable outside CLI
commands.

The final human-output contract is:

- TEXT output is console-oriented and owns verbosity/quiet behavior;
- Markdown output is document-oriented and ignores TEXT-oriented controls;
- JSON and NDJSON output are machine-readable and ignore human presentation controls.

The CLI command-applicability and exit-code contracts were implemented, tested, and documented. This
included dry-run `WOULD_CHANGE` behavior, missing-file handling, unmatched-glob semantics,
configuration-validation failures, probe semantic outcomes, and mixed-result priority ordering.

The path-command STDIN contract was also frozen:

- content STDIN uses the POSIX-style `-` PATH sentinel plus `--stdin-filename`;
- TopMark intentionally does not expose a `--stdin` option flag;
- unsupported `--stdin` spellings are rejected as CLI usage errors.

Result: CLI behavior is stable, explicit, scriptable, and separated from presentation internals.

______________________________________________________________________

## Configuration and runtime separation

Configuration and execution intent were split into separate layers.

The final model separates:

- `topmark.toml` for TOML parsing and whole-source validation;
- `topmark.config` for layered configuration merge and effective runtime configuration resolution;
- `topmark.runtime` for execution-time behavior.

Runtime-only behavior, such as apply/preview and STDIN handling, moved into `RunOptions` instead of
layered configuration.

Several user-facing policy/configuration behaviors were also normalized during stabilization:

- `add_only` / `update_only` were replaced by `header_mutation_mode`;
- `skip_compliant` / `skip_unsupported` were replaced by `report`;
- `policy_by_type`, `include_file_types`, and `exclude_file_types` now share the same
  qualified/local file-type identifier contract.

Runtime-facing TOML sections such as `[writer]` remain outside layered configuration while still
appearing in config dumps, config checks, and machine-readable configuration snapshots.

Configuration validation was hardened through staged internal validation logs:

- TOML-source diagnostics;
- merged-config diagnostics;
- runtime-applicability diagnostics.

Public compatibility surfaces continue to expose flattened diagnostics at exception, presentation,
and machine-readable output boundaries.

The canonical mutable/frozen naming model was finalized across configuration, policy, diagnostics,
and staged validation-log types. Public API inputs were standardized around mapping-based overlays,
while typed override bridge types remain internal CLI/API orchestration details.

Result: configuration is typed, layered, validated, normalized, and reproducible, while runtime
behavior is explicit.

______________________________________________________________________

## Pipeline and policy stabilization

Pipeline behavior was stabilized around deterministic preview/apply semantics.

Key outcomes included:

- explicit preview vs apply behavior;
- normalized write statuses;
- empty-file and empty-like classification;
- policy handling through `HeaderMutationMode` rather than boolean flags;
- idempotent processing and deterministic summaries;
- centralized exit-code derivation from pipeline results;
- synthetic pipeline contexts for explicit missing literal inputs;
- and typed value objects replacing ambiguous tuple-shaped return contracts.

The user-facing policy/report contract was frozen:

- `--report` controls human per-file output scope only;
- `header_mutation_mode` controls `check` insertion/update intent;
- `empty_insert_mode` classifies empty and empty-like files;
- safety gates remain authoritative over all policy options.

Line-ending support was also audited and frozen. TopMark recognizes LF, CRLF, and CR as physical
newline styles. Non-standard Unicode separators are treated as ordinary content rather than line
endings.

Result: pipeline behavior is explicit, consistent, idempotent, and policy driven.

______________________________________________________________________

## Machine output contracts

Machine-readable output was redesigned as a schema-driven system separated from CLI formatting.

The final machine-output model is:

- domain-scoped;
- JSON/NDJSON based;
- schema-driven with TypedDict contracts;
- separated from human presentation;
- and covered by focused contract tests.

Machine output now uses consistent envelope and metadata conventions across configuration, pipeline,
registry, version, and probe command families.

The stabilization effort also froze several important naming and shape conventions:

- plural domain-specific JSON collection keys;
- singular NDJSON record kinds;
- explicit `(outcome, reason, count)` pipeline summary rows;
- `qualified_key` plus `namespace` / `local_key` identity metadata;
- and flattened domain-specific registry envelopes.

Important frozen decisions included:

- pipeline summaries use explicit `(outcome, reason, count)` rows;
- `config check` uses the explicit `config_check` payload/record kind;
- registry JSON output uses flattened domain-specific envelopes;
- `detail_level` reflects projection depth where emitted;
- machine-readable payloads emit canonical qualified file-type identifiers;
- JSON/NDJSON payloads do not imply process status, which remains the CLI exit code.

Probe machine output was added with per-path probe results and filtered explicit-input reporting.

Result: machine-readable formats are stable, documented, and suitable for downstream automation.

______________________________________________________________________

## Human output contracts

Human output was consolidated into TEXT and Markdown.

TEXT output remains compact and console-oriented. It may use `-v` and `-vv` for progressive
disclosure, and `--quiet` only where suppressing output still leaves a meaningful status,
inspection, or mutation signal.

Markdown output is document-oriented and intentionally ignores TEXT-oriented verbosity, quiet, and
styling controls.

Semantic styling was routed through `StyleRole`, `Theme`, `TextStyler`, and `maybe_style()`. The 1.0
decision was to keep `yachalk` because styling is confined to CLI presentation internals, while
deferring any Rich or `rich-click` migration until after 1.0 unless a concrete blocker appears.

Result: human output is consistent, composable, and decoupled from CLI command functions.

______________________________________________________________________

## Documentation governance

Documentation was updated to match the final architecture and contract model.

Major outcomes included:

- canonical command-page structure across command and command-group documentation;
- aligned usage, configuration, architecture, API, machine-output, and README documentation;
- explicit public/internal boundary documentation;
- shared snippets for terminology, strict config loading, qualified/local file-type identifiers, and
  override boundaries;
- generated-site navigation and TOC-density improvements;
- a project-wide terminology glossary;
- terminology governance through reusable snippets and shared canonical wording;
- and calmer starter-template prose.

Documentation hygiene was added through `tools/docs/check_docs_hygiene.py`, exposed via nox and
Makefile targets. It validates snippet includes, docs-root-relative include paths, section
structure, heading conventions, accidental macOS resource files, and changelog heading shape.

Python code-prose hygiene was added through `tools/docs/check_code_hygiene.py`, covering comments,
docstrings, and prose-oriented string literals.

Result: documentation is convention-driven, validated, and aligned with the frozen 1.0 behavior.

______________________________________________________________________

## CI, release, and dependency model

The project migrated to a uv-first dependency model and replaced tox with nox.

The contributor workflow also migrated away from tox toward uv-backed nox sessions with
metadata-driven Python-version management.

Release publication was redesigned around an artifact-based CI → release split:

- CI builds release artifacts on tag pushes;
- release artifacts and metadata are uploaded from CI;
- the privileged release workflow downloads, verifies, and publishes those artifacts;
- the release workflow no longer rebuilds from repository source.

Versioning moved to `setuptools-scm`, making Git tags the source of truth. Release validation now
checks SCM-derived artifact versions against the resolved release tag rather than comparing against
a static project version.

Install-smoke validation was added across Linux, macOS, and Windows, validating wheel and sdist
installation from built artifacts in isolated environments.

CI was hardened through:

- link checks;
- documentation hygiene checks;
- SHA-pinned actions;
- explicit permissions;
- metadata-driven Python-version resolution;
- dynamic compatibility-matrix generation through `nox -s print_python_matrix`;
- canonical CI coverage reporting;
- and explicit uv cache ownership.

The `nox -s print_python_matrix` session centralizes Python-version metadata for CI. Compatibility
matrix jobs and canonical single-version jobs consume resolved metadata, while release publication
keeps an explicit release-tooling Python runtime and reports non-blocking drift warnings.

Result: release and installation validation are reproducible, automated, documented, and validated
across real workflow runs.

______________________________________________________________________

## Typing and API hardening

Late-beta stabilization tightened internal typing and ownership boundaries under Pyright strict
mode.

Key outcomes included:

- replacing ambiguous tuple-shaped returns with frozen value objects or DTO-style models;
- tightening protocol/view contracts toward read-only semantics where mutation is not intended;
- documenting public API snapshot exports vs public-adjacent integration surfaces;
- preserving Python 3.10 compatibility;
- replacing temporary typed pytest decorator wrappers with direct pytest marker/decorator usage once
  typing support stabilized;
- and removing obsolete or redundant helper layers where they no longer contributed to the frozen
  architecture.

Examples of typed result-object cleanup included version/config preparation, TOML/config bridges,
CLI input planning, runtime execution, pipeline execution, processor results, diagnostics,
glob-rebasing, and file-type resolution paths.

Result: the implementation is clearer, better typed, and less dependent on positional ownership
contracts.

______________________________________________________________________

## Coverage and validation stabilization

Coverage-driven stabilization was used as a confidence-building signal, not as a percentage target.

Focused coverage expansion improved confidence around:

- outcomes;
- status/context behavior;
- merge utilities;
- file-type gating;
- enum mixins;
- diff rendering;
- validation/error paths;
- config, pipeline, registry, version, and probe machine contracts.

Canonical CI coverage reporting was added through the existing `nox -s coverage` session. CI now
publishes a GitHub Step Summary plus HTML, XML, and JSON coverage artifacts. Coverage remains
informational and is not a release-blocking percentage gate.

README coverage badge adoption remains deferred until the published signal proves stable,
representative, and useful over time.

Result: coverage now supports release confidence without becoming release governance.

______________________________________________________________________

## Contract freezes

By the end of the beta line, the following 1.0 contracts were frozen:

- registry and file-type identity semantics;
- CLI command applicability;
- CLI exit codes;
- STDIN handling;
- user-facing policy/report behavior;
- TOML/config/runtime layering;
- staged validation internals with flattened compatibility diagnostics at public boundaries;
- JSON/NDJSON machine-output schemas;
- TEXT and Markdown human-output behavior;
- artifact-based release workflow;
- uv/nox dependency tooling;
- documentation governance and hygiene checks.

The 1.0 release candidate therefore represents a contract freeze rather than a feature-completion
milestone.

______________________________________________________________________

## Deferred post-1.0 scope

Several items were explicitly deferred beyond 1.0 to preserve release focus:

- in-memory pipeline support and a future `InputSource` abstraction;
- configuration schema versioning;
- richer staged validation exposure in CLI/API/machine output;
- registry query/filter commands;
- multi-line TopMark header fields;
- Rich or `rich-click` migration;
- broader workflow/release-infrastructure factoring;
- deeper documentation-structure validation;
- and README coverage badge publication.

These deferrals are deliberate scope decisions rather than incomplete 1.0 requirements.

______________________________________________________________________

## Lessons learned

The 1.0 stabilization effort reinforced several project-level lessons:

- explicit boundaries are easier to document, test, and preserve than implicit behavior;
- machine-readable output should be treated as a schema contract, not a CLI formatting variant;
- human output needs a separate presentation model from automation output;
- release workflows are easier to trust when artifact creation and privileged publication are
  separated;
- documentation governance needs lightweight automated checks to remain sustainable;
- coverage is most useful as a confidence signal when it avoids percentage chasing;
- and explicit deferrals are healthier than forcing architectural ideas into a release candidate.
