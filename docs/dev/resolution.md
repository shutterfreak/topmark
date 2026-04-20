<!--
topmark:header:start

  project      : TopMark
  file         : resolution.md
  file_relpath : docs/dev/resolution.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# File Type Resolution and Ambiguity Policy

This page documents how TopMark resolves a concrete filesystem path to the most specific matching
\[`FileType`\][topmark.filetypes.model.FileType], and then to the bound
\[`HeaderProcessor`\][topmark.processors.base.HeaderProcessor] registered for that file type.

It complements the registry architecture described in [`architecture.md`](architecture.md):

- registries define **what exists**
- the resolver defines **what wins for a concrete path**

This resolver operates within the broader TOML → Config → Runtime architecture (see
[`architecture.md`](architecture.md)). It consumes the effective registry state and does not perform
configuration discovery, layered config provenance export, or staged config-loading/preflight
validation strictness resolution itself.

In particular, source-local TOML options such as `[config].root` and `strict_config_checking` are
resolved before runtime file-type resolution begins. They influence discovery and staged
config-loading/preflight validation behaviour, but are not part of the resolver's matching or
tie-break logic.

This distinction is also visible in `topmark config dump --show-layers`: layered provenance exports
are produced earlier from resolved TOML sources and flattened config state, while file-type
resolution happens later against the already-validated effective runtime configuration.

______________________________________________________________________

## Overview

TopMark has two different resolution modes:

- **Identifier-based lookup** resolves file types or processors from explicit identifiers or
  canonical keys through the registries.
- **Path-based resolution** resolves a real path by evaluating extension, filename, pattern, and
  optional content-based signals.

Path-based resolution is implemented in
\[`topmark.resolution.filetypes`\][topmark.resolution.filetypes] and consumed by
\[`ResolverStep`\][topmark.pipeline.steps.resolver.ResolverStep].

The main public entry points are:

- \[`resolve_file_type_for_path()`\][topmark.resolution.filetypes.resolve_file_type_for_path]
- \[`resolve_binding_for_path()`\][topmark.resolution.filetypes.resolve_binding_for_path]

These entry points participate only in **path-based runtime resolution**. They do not surface or
consume layered config provenance payloads such as the human-facing `[[layers]]` export or the
machine-readable `config_provenance` payload used by `topmark config dump --show-layers`.

They operate after staged config-loading/preflight validation has completed and the effective
configuration is finalized.

See also:

- [`Architecture`](architecture.md)
- [`Pipelines (Concepts)`](pipelines.md)
- [`Pipelines (Reference)`](pipelines-reference.md)
- [`Configuration discovery`](../configuration/discovery.md)
- [`Configuration index`](../configuration/index.md)

`resolve_binding_for_path()` first resolves the best matching file type for a path, then looks up
the bound processor through the registry facade.

______________________________________________________________________

## Candidate generation

Candidate generation is performed by
\[`get_file_type_candidates_for_path()`\][topmark.resolution.filetypes.get_file_type_candidates_for_path].

For each effective `FileType`, the resolver evaluates name-based signals and, when allowed, optional
content-based signals.

### Name-based signals

The resolver computes three name-based match signals:

- **extension**: the basename ends with one of the file type's configured extensions
- **filename**: the basename or normalized path tail matches one of the file type's configured
  filenames
- **pattern**: the basename fully matches one of the file type's configured regular-expression
  patterns

These signals are represented by \[`MatchSignals`\][topmark.resolution.filetypes.MatchSignals].

### Content gating

Content probing is controlled by the file type's
\[`ContentGate`\][topmark.filetypes.model.ContentGate]. This prevents unrelated files from being
probed unnecessarily and allows overlay-style file types to refine generic matches.

Examples:

- `ContentGate.NEVER` disables content probing entirely
- `ContentGate.IF_EXTENSION` only allows probing when an extension matched
- `ContentGate.IF_FILENAME` only allows probing when a filename or tail matched
- `ContentGate.IF_PATTERN` only allows probing when a pattern matched
- `ContentGate.IF_ANY_NAME_RULE` allows probing when any name-based rule matched
- `ContentGate.IF_NONE` allows probing only when the file type declares no name-based rules
- `ContentGate.ALWAYS` allows content probing unconditionally

### Candidate inclusion

A file type becomes a candidate when its evaluated signals satisfy the resolver's inclusion rules.

This means that:

- a candidate may be included purely from name-based signals
- a candidate may be included only after a successful content probe
- a candidate may be excluded even when some name-based signals matched if the configured content
  gate requires a positive content hit

Candidate generation may therefore yield **multiple** file types for the same path. This is
intentional and is handled by the deterministic selection policy described below.

______________________________________________________________________

## Scoring model

Each included candidate is assigned a precedence score by `_score_file_type_candidate()`.

Higher scores are better.

The current precedence model is:

1. explicit filename or filename-tail match
1. content-confirmed match
1. pattern match
1. extension match

A small bonus is applied to file types that are not marked `skip_processing=True`, which gives
header-capable types a stable advantage on otherwise equal matches.

More specifically:

- filename and path-tail matches receive the highest scores and become more specific as the matched
  tail becomes longer
- content-confirmed matches outrank generic pattern and extension matches
- pattern matches outrank plain extension matches
- extension matches remain valid fallbacks for generic formats

The scoring model is intentionally biased toward the **most specific** match, while still keeping
generic file types useful as fallbacks.

______________________________________________________________________

## Deterministic selection

Final selection is handled by `_select_best_file_type_candidate()`.

TopMark does **not** treat multiple candidates as an error. Instead, it applies a deterministic
ordering key defined by
\[`candidate_order_key()`\][topmark.resolution.filetypes.candidate_order_key].

Candidates are ordered by:

1. score (**descending**)
1. namespace (**ascending**)
1. local key (**ascending**)

In practice, this means:

- the highest-scoring candidate wins
- if multiple candidates have the same score, namespace is used as the first stable tie-breaker
- if score and namespace are equal, local key is used as the final stable tie-breaker

This policy guarantees that the same path, content, and effective registry state always produce the
same winning `FileType`.

TopMark currently uses a deterministic winner-selection policy rather than an ambiguity error
policy.

______________________________________________________________________

## Ambiguity policy

Resolution may produce multiple matching file type candidates. This is **not** considered a registry
error.

Overlap between file types is allowed because it enables useful patterns such as:

- a generic built-in file type plus a more specific plugin-defined variant
- a content-refined overlay type (for example, a JSON-like subtype over a generic JSON fallback)
- shared extensions with different filename or content rules

TopMark's ambiguity policy is therefore:

- multiple candidates are allowed during candidate generation
- the resolver must return **at most one** effective winner
- the winner is selected deterministically using the documented precedence and tie-break policy
- ambiguity does **not** raise an exception in the current model

This keeps resolution stable and practical while still allowing rich, overlapping file type
ecosystems.

______________________________________________________________________

## Logging and observability

When multiple candidates share the top score,
\[`resolve_file_type_for_path()`\][topmark.resolution.filetypes.resolve_file_type_for_path] emits a
debug log before applying the deterministic tie-break.

This makes ambiguous-but-resolvable situations observable during development and debugging without
turning them into hard failures.

The log includes:

- the path being resolved
- the shared top score
- the qualified keys of the tied top candidates

This helps explain why a particular file type won when multiple strong candidates existed.

______________________________________________________________________

## Design rationale

TopMark intentionally resolves ambiguity in the resolver layer rather than in the registries.

This separation keeps responsibilities clear:

- \[`FileTypeRegistry`\][topmark.registry.filetypes.FileTypeRegistry] stores file type identities
- \[`HeaderProcessorRegistry`\][topmark.registry.processors.HeaderProcessorRegistry] stores
  processor identities
- \[`BindingRegistry`\][topmark.registry.bindings.BindingRegistry] stores effective
  file-type-to-processor relationships
- the resolver decides which file type best matches a **concrete path**

This design has several advantages:

- registries remain simple and declarative
- overlapping file types remain legal
- resolution remains deterministic and testable
- plugin authors can define specialized file types without needing a separate override system in the
  registries

______________________________________________________________________

## Non-goals

The current resolver deliberately does **not** provide:

- user-configurable namespace priority
- a strict ambiguity error mode
- registry-time rejection of overlapping file type definitions
- pluggable custom precedence strategies

These may be introduced later if there is a strong use case, but they are not part of the current
TopMark resolution contract.

______________________________________________________________________

## Possible future extensions

Possible future improvements include:

- a strict mode that surfaces certain ambiguities as explicit resolution errors
- user-configurable precedence overrides
- richer diagnostics or hints when deterministic tie-breaks are used
- plugin-defined precedence policies layered on top of the default scoring model

Until then, the documented deterministic policy on this page is the source of truth.

______________________________________________________________________

## See also

- [`Architecture`](architecture.md) — registry design and system overview
- [`Plugins`](plugins.md) — how file types and processors are registered
- [`Machine output schema`](machine-output.md) — how resolution results surface in outputs
