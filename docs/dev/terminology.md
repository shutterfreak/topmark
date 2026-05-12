<!--
topmark:header:start

  project      : TopMark
  file         : terminology.md
  file_relpath : docs/dev/terminology.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Terminology and Canonical Vocabulary

This page defines the canonical terminology used throughout the TopMark documentation,
machine-readable output contracts, CLI help, and public API documentation.

The goal is to ensure consistent wording across architecture, configuration, pipeline, registry,
resolution, CLI, and machine-readable output documentation.

______________________________________________________________________

## Stability terminology

### Stable

Supported public behavior that is expected to remain compatible across the 1.x series unless
explicitly documented otherwise.

### Frozen

Behavior or terminology considered finalized for the 1.0 release cycle.

“Frozen” refers to release-contract stabilization rather than long-term immutability.

> [!NOTE]
>
> In API and runtime contexts, “frozen” may additionally refer to immutable runtime objects such as
> frozen dataclasses or immutable snapshots.

### Internal

Implementation details that are not part of the supported public compatibility contract.

Internal APIs, helpers, DTOs, and modules may change without notice.

### Deferred

Intentionally postponed work that is not required for the 1.0 release.

### Post-1.0

Work intentionally scoped beyond the 1.0 release.

### Experimental

Behavior or APIs intentionally excluded from stability guarantees.

______________________________________________________________________

## Registry and file type terminology

### File type

A structured definition describing how TopMark recognizes and classifies a file.

Represented by `FileType`.

### Header processor

A component that detects, renders, inserts, updates, compares, or strips headers for one or more
file types.

Represented by `HeaderProcessor`.

### Binding

An explicit relationship between a file type and a header processor.

Bindings are managed separately from file type and processor registration.

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

The normalized qualified-key representation used internally for comparison, storage,
machine-readable output, and runtime policy lookup.

### Namespace

A logical ownership boundary for file type identities.

> [!NOTE]
>
> Namespaces avoid collisions between independently defined file types.

______________________________________________________________________

## Resolution terminology

### Resolution

The process of selecting the most appropriate file type for a path or input.

### Probe

A read-only diagnostic operation that exposes resolution candidates, scores, filtering behavior, and
selected bindings.

> [!NOTE]
>
> Probe does not perform header mutation, planning, comparison, or writing.

### Resolver

The runtime component responsible for mapping inputs to file types and processors.

### Ambiguity

A resolution state where a local identifier or candidate match is not uniquely identifiable.

> [!NOTE]
>
> Ambiguous local identifiers require the qualified form.

______________________________________________________________________

## Configuration and runtime terminology

### Layered configuration

The merged configuration state derived from one or more TOML configuration sources.

### Runtime overlay

Runtime-only execution behavior applied after layered configuration resolution without mutating the
underlying layered configuration state.

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
configuration merging.

Example:

```text
[writer]
```

### Effective configuration

The fully resolved configuration applicable to a specific path or execution context.

______________________________________________________________________

## Pipeline terminology

### Pipeline

An ordered sequence of processing steps implementing a specific TopMark execution intent.

### Step

A single-responsibility processing unit within a pipeline.

### Preview mode

A non-mutating execution mode that reports intended changes without writing files.

### Apply mode

A mutating execution mode that performs filesystem writes.

### Idempotence

The guarantee that repeated runs without source changes converge to the same result.

______________________________________________________________________

## Output terminology

### Human output

Console-oriented or document-oriented rendered output intended for people.

Formats:

- TEXT: console-oriented output format which optionally supports ANSI color and styling.
- MARKDOWN: document-oriented output format.

### Machine-readable output

Structured output intended for tooling and automation.

Formats:

- JSON: one single JSON object.
- NDJSON: stream of newline-delimited JSON records.

### Machine-readable contract

The stability guarantees governing machine-readable schemas, record kinds, field naming, and payload
structure.

### Payload

A concrete emitted JSON object.

### Record kind

The stable discriminator identifying an NDJSON record type.

### Collection key

The top-level JSON object key containing a collection of domain objects within a machine-readable
JSON document.

### Detail level

The machine-readable projection depth controlled by `--long` where supported.

### Verbosity

TEXT-only progressive-disclosure rendering behavior controlled by `-v` / `--verbose` (can be
repeated).

> [!NOTE]
>
> Verbosity is separate from machine-readable projection depth.

______________________________________________________________________

## CLI terminology

### Applicability

Whether a command or option is valid in a specific command context.

### Usage error

An invalid CLI invocation rejected before execution.

### File-agnostic command

A command that does not operate on filesystem paths or content-processing pipelines.

### Path-processing command

A command that processes paths through discovery, resolution, or pipelines.

______________________________________________________________________

## Public API terminology

### Public API

Documented interfaces covered by TopMark’s compatibility guarantees.

### Internal API

Undocumented or explicitly internal implementation details outside the compatibility contract.

### DTO

A structured data-transfer object exposed at a public boundary.

### Snapshot policy

The compatibility-validation strategy used to verify stable public API surfaces across supported
Python versions.
