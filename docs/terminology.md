<!--
topmark:header:start

  project      : TopMark
  file         : terminology.md
  file_relpath : docs/terminology.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Terminology and Canonical Vocabulary

This page defines the canonical terminology used throughout TopMark's stable documentation,
machine-readable compatibility contracts, CLI help, and public API surfaces.

The goal is to ensure stable and consistent terminology across architecture, configuration,
pipelines, registry behavior, resolution, CLI semantics, runtime policy, and machine-readable
documentation.

______________________________________________________________________

## Stability terminology

### Compatibility contract

The documented behavior that TopMark guarantees to preserve across compatible releases.

### Stable

Supported public behavior expected to remain compatible across the 1.x release series unless
explicitly documented otherwise.

### Frozen

Behavior, terminology, or compatibility contracts considered finalized during the 1.0 stabilization
cycle.

"Frozen" refers to release-contract stabilization rather than long-term immutability.

> [!NOTE]
>
> In API and runtime contexts, "frozen" may additionally refer to immutable runtime objects such as
> frozen dataclasses, immutable snapshots, or frozen runtime state.

### Internal

Implementation details that are intentionally excluded from the supported public compatibility
contract.

> [!NOTE]
>
> Internal APIs, helpers, DTOs, and modules may change without notice.

### Deferred

Intentionally postponed work that is not required for the stable 1.x release contract.

### Post-1.0

Work intentionally scoped beyond the initial 1.0 stabilization effort.

### Experimental

Behavior or APIs intentionally excluded from compatibility guarantees.

______________________________________________________________________

## Registry and file type terminology

### File type

A structured definition describing how TopMark recognizes, classifies, and binds processing behavior
to a file through a [binding](#binding).

Represented by \[`FileType`\][topmark.filetypes.model.FileType].

### Header processor

A component responsible for detecting, rendering, inserting, updating, comparing, or stripping
headers for one or more resolved file types.

Represented by \[`HeaderProcessor`\][topmark.processors.base.HeaderProcessor].

### Binding

An explicit relationship between a file type and a header processor.

Bindings are resolved independently from file type and processor registration.

### Qualified key

The canonical internal identifier for a file type.

Format:

```text
<namespace>:<local_key>
```

Example:

```text
topmark:python
```

### Local identifier

The local portion of a qualified key.

Example:

```text
python
```

> [!NOTE]
>
> Local identifiers may be accepted at public boundaries only when unambiguous.

### Canonical identity

The normalized representation used internally for comparison, storage, machine-readable output,
filtering, runtime policy lookup, registry composition, and resolution.

Examples include qualified file-type identities and canonicalized registry matching rules.

### Filesystem identity

The canonical filesystem object identity used by TopMark when processing existing files,
configuration sources, and runtime inputs.

Filesystem identity is evaluated before runtime processing begins.

Filesystem-identity evaluation consists of two related concepts:

- **Filesystem-identity normalization**: collapsing equivalent path spellings that refer to the same
  filesystem target (for example a symlink and its target) into a selected processing path.
- **Filesystem-identity eligibility checks**: determining whether a selected processing path is
  eligible for processing according to filesystem-identity policy.

For ordinary filesystem processing, identity is based on the resolved processing target rather than
the original invocation spelling.

Examples:

```text
real/file.py
link-to-file.py
./real/file.py
```

may all refer to the same filesystem identity.

Hard links are handled differently from symlink spelling aliases. When two or more selected
processing paths have the same `(st_dev, st_ino)` filesystem identity, TopMark preserves one result
per selected path but blocks every affected path as a hard-linked processing target. It does not
select a source, target, winner, or loser path automatically.

> [!NOTE]
>
> Filesystem identity is distinct from machine-readable path serialization. TopMark first evaluates
> filesystem identity and then serializes the selected processing path according to the
> machine-output contract.

### Namespace

A logical ownership boundary for file type identities.

> [!NOTE]
>
> Namespaces avoid collisions between independently defined file types.

______________________________________________________________________

## Resolution terminology

### Resolution

The process of selecting the most appropriate file type for a path or input.

Resolution operates after filesystem-identity evaluation has selected eligible processing paths.
Filesystem-identity normalization may collapse multiple path spellings, such as symlinks, to a
single selected processing path before runtime processing begins.

### Filename rule

A declarative file-type matching rule used by `FileType.filenames`.

Filename rules are registry matching rules rather than filesystem paths.

Two forms are supported:

- exact-basename rules (for example `Makefile`);
- relative tail-subpath rules (for example `.vscode/settings.json`).

Tail-subpath rules are stored and emitted using canonical POSIX-style `/` separators regardless of
platform.

> [!NOTE]
>
> Absolute paths, UNC paths, Windows drive paths, empty rules, empty path segments, and `.` / `..`
> path segments are invalid filename rules.

### Probe

A read-only diagnostic operation exposing resolution candidates, scores, filtering behavior, and
selected bindings.

> [!NOTE]
>
> Probe does not perform header mutation, mutation planning, comparison, patch generation, or
> writing.

### Resolution engine

The runtime component responsible for mapping inputs to file types, processor bindings, and runtime
resolution outcomes.

### Ambiguity

A resolution state where a local identifier or candidate match is not uniquely identifiable.

> [!NOTE]
>
> Ambiguous local identifiers require the qualified form.

______________________________________________________________________

## Configuration and runtime terminology

### Layered configuration

The merged runtime configuration state derived from one or more TOML configuration sources.

### Runtime overlay

Runtime-only behavior applied after layered configuration resolution without mutating the underlying
layered configuration state.

### Runtime configuration

The immutable resolved configuration state consumed by runtime execution, pipelines, registry
composition, and policy evaluation.

### Runtime policy evaluation

The process of applying layered configuration, runtime overlays, applicability rules, and
file-type-specific policy to runtime execution behavior.

### RunOptions

Typed runtime execution intent such as apply/preview behavior and stdin handling.

### TOML-source-local option

Configuration behavior that applies only to the TOML source currently being loaded rather than to
the merged layered configuration.

Example:

```text
[config].strict
```

### Runtime-facing TOML section

A TOML section preserved in effective configuration output while resolved outside layered
configuration merging semantics.

Example:

```text
[writer]
```

### Effective configuration

The fully resolved runtime configuration applicable to a specific path, command invocation, or
execution context.

### Configuration source identity

The normalized identity assigned to a loaded TOML configuration source.

Configuration-source identity is based on the resolved processing target of the loaded configuration
file. Symlink spellings are not preserved for precedence, scope, or applicability evaluation.

______________________________________________________________________

## Pipeline terminology

### Pipeline

An ordered sequence of processing steps implementing a specific runtime execution intent.

### Step

A single-responsibility processing unit within a pipeline.

### Preview mode

A non-mutating runtime execution mode that reports intended changes without mutating filesystem
content.

### Apply mode

A mutating execution mode that performs filesystem writes.

### Idempotence

The guarantee that repeated runs without source changes converge to the same result.

Filesystem-identity normalization contributes to idempotence by preventing the same target file from
being processed multiple times through different path or symlink spellings. Filesystem-identity
eligibility checks, such as hard-link policy, contribute to safety by blocking ambiguous write
targets before mutation planning.

### Mutation planning

The process of determining intended header insertions, replacements, removals, or filesystem writes
before mutating content.

______________________________________________________________________

## Output terminology

### Human output

Console-oriented or document-oriented rendered output intended for human readers.

Formats:

- TEXT: console-oriented output format which optionally supports ANSI color and styling.
- MARKDOWN: document-oriented output format.

### Machine-readable output

Structured output intended for tooling and automation.

Formats:

- JSON: one machine-readable JSON document.
- NDJSON: a stream of newline-delimited JSON records.

### Machine-readable contract

The compatibility guarantees governing machine-readable schemas, record kinds, field naming, payload
structure, and semantic stability.

The machine-readable contract governs path serialization but does not define filesystem identity
semantics.

### Payload

A concrete emitted machine-readable JSON-compatible object.

### Record kind

The stable discriminator identifying a machine-readable NDJSON record type.

### Semantic outcome

A stable runtime classification describing the result of processing, filtering, mutation planning,
or resolution behavior.

Examples include changed, unchanged, filtered, unsupported, blocked-policy, or unresolved outcomes.

### Collection key

The top-level JSON object key containing a collection of domain objects within a machine-readable
JSON document.

### Detail level

The machine-readable projection depth selected by `--long` where supported by a command.

### Verbosity

TEXT-oriented progressive-disclosure rendering behavior selected by `-v` / `--verbose` (repeatable).

> [!NOTE]
>
> Verbosity is separate from machine-readable projection depth.

### Flattened compatibility view

The stable machine-readable and API-facing projection derived from staged internal validation,
diagnostic, or runtime-processing state.

The flattened compatibility view intentionally hides stage-local implementation structure while
preserving stable caller-facing semantics.

______________________________________________________________________

## CLI terminology

### Applicability

Whether a command, option, override, or policy rule is valid in a specific runtime or command
context.

### Usage error

An invalid CLI invocation rejected before runtime execution begins.

### File-agnostic command

A command that does not operate on filesystem paths or content-processing pipelines.

### Path-processing command

A command that processes filesystem paths through discovery, filtering, resolution, or runtime
pipelines.

### Processing path

The canonical path selected by TopMark for runtime processing.

A processing path represents the resolved filesystem target chosen after path normalization,
discovery, filtering, and deduplication. It is the path exposed to runtime pipelines, header
generation, and machine-readable output.

> [!NOTE]
>
> A processing path is not necessarily identical to the original CLI argument, configuration entry,
> glob match, or symlink spelling supplied by the user.

______________________________________________________________________

## Public API terminology

### Public API

Documented interfaces covered by TopMark's compatibility guarantees.

### Internal API

Undocumented or explicitly internal implementation details outside the compatibility contract.

### DTO

A structured data-transfer object exposed through a documented stable public boundary.

### Snapshot policy

The compatibility-validation strategy used to verify stable public API surfaces across supported
Python versions.
