<!--
topmark:header:start

  project      : TopMark
  file         : configuration-schema.md
  file_relpath : docs/dev/configuration-schema.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Configuration schema summary

This page summarizes TopMark's stable external configuration schema as consumed from `topmark.toml`
and `[tool.topmark]` in `pyproject.toml`.

> [!NOTE]
>
> - This page is a schema summary, not a full JSON Schema.
> - The ordering mirrors `src/topmark/toml/topmark-example.toml`.
> - Keys are defined authoritatively in `src/topmark/toml/keys.py`.
>
> TopMark internally maintains staged validation diagnostics, but public reporting, machine-readable
> output, and API surfaces expose a flattened compatibility view.
>
> For the stable 1.x line, this flattened compatibility view is the machine-readable and API
> compatibility contract.

\\

> [!NOTE]
>
> Human-facing TEXT verbosity (`-v`) and quiet mode (`--quiet`) are presentation-layer concerns.
>
> They do not affect:
>
> - configuration schema validation
> - staged diagnostics
> - machine-readable output
> - API surfaces
>
> Markdown and machine-readable output always expose the full flattened compatibility view.

See also:

- [Configuration](../usage/configuration.md)
- [Filtering](../usage/filtering.md)
- [Policies](../usage/policies.md)
- [Registry model](registry-model.md)
- [Resolution](resolution.md)

See [Terminology and Canonical Vocabulary](../terminology.md) for the normative definitions of
machine-readable output, canonical identity, applicability, and staged diagnostics terminology.

{% include-markdown "\_snippets/api-internal-overrides.md" %}

At the configuration-schema layer, override handling is represented as plain mapping data.

Internal typed runtime override objects are introduced later during CLI/API orchestration and are
not part of the stable external configuration schema.

File type identifiers in TOML configuration may use either:

- local identifiers such as `python`
- canonical qualified file type identities such as `topmark:python`

TopMark normalizes identifiers to canonical qualified keys during configuration normalization before
resolver, filtering, policy, and binding evaluation.

Local identifiers are accepted only when unambiguous in the effective composed registry.

`strict` is a TOML-source-local config-loading option, not a layered configuration field. It is
resolved from `[config]` / `[tool.topmark.config]` during TOML source resolution and applied after
layered configuration merging.

Its effective value governs staged config-loading validation across TOML-source, merged-config, and
runtime-applicability diagnostics.

This distinction matters for
[`topmark config dump --show-layers`](../usage/commands/config/dump.md):

- the human-facing layered TOML export exposes source-local TOML fragments under `[[layers]].toml.*`
- the machine-readable layered export exposes the same source-local TOML fragments under
  `config_provenance.layers[].toml`

For the canonical user-facing discovery, precedence, path-resolution, and staged validation
contract, see [Configuration discovery, precedence, and policy](../configuration/discovery.md).

Configuration discovery begins from a discovery anchor (the current working directory or an input
path). Project-chain discovery walks upward from the resolved discovery anchor before layered
configuration precedence is evaluated.

For file-backed configuration sources, schema processing operates on configuration-source identity
based on the resolved configuration-file target.

Different path spellings such as:

```text
real/topmark.toml
link-to-topmark.toml
```

may therefore identify the same configuration source.

Workspace-root and project-chain discovery are evaluated earlier. Discovery uses the resolved anchor
location when determining which project configuration files participate in layered configuration
construction.

Configuration-source identity affects:

- precedence and layer ordering;
- scope-root selection;
- applicability evaluation;
- layered provenance exports; and
- machine-readable configuration provenance.

Symlink spellings are not preserved once a configuration source has been loaded.

Configuration-source identity is distinct from workspace-root discovery and from processing-target
identity.

Workspace-root discovery determines where configuration discovery starts. Configuration-source
identity determines how loaded configuration files participate in precedence, applicability, and
provenance after discovery has completed.

The hard-link processing policy used by runtime filesystem-processing commands does not affect the
external configuration schema, workspace-root discovery, configuration-source discovery, precedence,
scope-root selection, applicability evaluation, or layered provenance exports.

## Schema validation model

For `pyproject.toml`, "whole source" means the exact `[tool.topmark]` table after extraction, not
the entire project document. Unrelated `[project]`, `[build-system]`, and sibling `[tool.*]` content
is outside TopMark's schema. A missing or structurally malformed `[tool.topmark]` is not a TopMark
source; an explicitly empty table is a real empty source and therefore receives the normal
missing-section INFO diagnostics.

TopMark performs **whole-source TOML schema validation** before any layered configuration is
deserialized:

- unknown top-level sections (e.g. `[foo]`) are reported as TOML validation issues
- missing known sections are reported as INFO diagnostics
- unknown keys within known sections (e.g. `[config].bogus`) are also reported
- validation is source-local and happens per TOML file during loading

After this step, only the layered configuration fragment is passed to
\[`MutableConfig`\][topmark.config.model.MutableConfig] for parsing and normalization before
freezing into the immutable layered configuration snapshot.

At this boundary, diagnostics remain **staged**; flattening into the public compatibility view is
performed only at reporting, exception, machine-readable output, and API boundaries.

This reporting boundary is independent of human presentation controls: TEXT verbosity (`-v`) and
quiet mode (`--quiet`) only influence how diagnostics are rendered in console output, not how they
are produced, staged, or exposed through machine/API interfaces.

For the stable 1.x line, staged validation remains internal, while public reporting and machine/API
surfaces expose only the flattened compatibility diagnostics contract.

At the TOML layer, malformed known sections are handled as warning-and-ignore diagnostics, while
missing known sections are emitted as INFO diagnostics.

This allows callers to distinguish absent sections from malformed-present sections before staged
config-validation semantics are applied.

These TOML-source diagnostics then participate together with merged-config and runtime-applicability
diagnostics during staged config-loading validation.

> [!NOTE]
>
> - TOML schema validation is handled in \[`topmark.toml`\][topmark.toml]
> - file type identifier normalization and ambiguity evaluation are performed during configuration
>   normalization and runtime-applicability validation
> - configuration value/type validation is handled in \[`topmark.config`\][topmark.config] as staged
>   validation logs (merged-config and runtime-applicability stages)
> - layered config deserialization
>   (\[`mutable_config_from_layered_toml_table`\][topmark.config.io.deserializers.mutable_config_from_layered_toml_table])
>   assumes schema validation already happened, but still performs defensive parsing for API and
>   test inputs

The following summary uses a YAML-like notation for readability and is not itself a machine-readable
schema definition.

```yaml
topmark:
  # In layered provenance exports, source-local TOML fragments preserve their
  # original TOML grouping, including `[config]` and `[writer]`, rather than
  # collapsing everything into the final flattened Config payload.
  config:
    type: table
    description: TOML-source-local options resolved during TOML loading, not part of layered
      configuration merging.
    root:
      type: bool
      default: false
      description: Stop upward project-chain discovery when set in a discovered config reached from
        the resolved discovery anchor.
    strict:
      type: bool
      default: false
      description: Source-local strictness preference applied to staged config-loading validation;
        warnings become failures when effective strict config checking is enabled across
        TOML-source, merged-config, and runtime-applicability diagnostics.

  header:
    fields:
      type: list[str]
      default: ["file", "file_relpath"]
      description: Header metadata fields to render (order preserved).

  fields:
    type: table
    default: {}
    description: User-defined header field values (e.g., project/license/copyright).

  formatting:
    align_fields:
      type: bool
      default: true
      description: Align header field labels/colons.

    relative_to:
      type: path
      default: "."
      description: Affects header metadata (file_relpath) for the selected processing target, not
        discovery.

  writer:
    type: table
    description: TOML-source-local writer options (not part of layered configuration state).
    strategy:
      type: str
      default: "atomic"
      enum: ["atomic", "inplace"]
      description: How file writes are performed when writing back to files.

  policy:
    header_mutation_mode:
      type: str
      default: "all"
      enum: ["all", "add_only", "update_only"]
      description: Controls check mutation intent: insert and update headers, insert missing headers
        only, or update existing headers only. Safety gates still take precedence.

    bom_before_shebang:
      type: str
      default: "reject"
      enum: ["reject", "remove_bom"]
      description: Reject a UTF-8 BOM before a shebang or plan standalone BOM removal.

    allow_header_in_empty_files:
      type: bool
      default: false
      description: Allow inserting headers into files considered empty under the effective empty
        insertion policy.

    empty_insert_mode:
      type: str
      default: "logical_empty"
      enum: ["bytes_empty", "logical_empty", "whitespace_empty"]
      description: Control how TopMark classifies files as empty for header insertion.

    render_empty_header_when_no_fields:
      type: bool
      default: false
      description: Allow inserting an empty header when no header fields are configured.

    allow_reflow:
      type: bool
      default: false
      description: Allow content reflow during header insertion or update.

    allow_content_probe:
      type: bool
      default: true
      description: Allow file-type detection to inspect file contents when needed.

  policy_by_type:
    type: table
    default: {}
    description: Per-file-type policy overrides, keyed by local or canonical qualified file type
      identifiers.
    additionalProperties:
      # Examples:
      #
      # [policy_by_type.python]
      # [policy_by_type."topmark:python"]
      #
      # Identifiers normalize to canonical qualified keys.

      header_mutation_mode:
        type: str
        optional: true
        enum: ["all", "add_only", "update_only"]
        description: Per-file-type override for check mutation intent.

      bom_before_shebang:
        type: str
        optional: true
        enum: ["reject", "remove_bom"]
        description: Per-file-type BOM-before-shebang remediation override.
      allow_header_in_empty_files:
        type: bool
        optional: true
      empty_insert_mode:
        type: str
        optional: true
        enum: ["bytes_empty", "logical_empty", "whitespace_empty"]
      render_empty_header_when_no_fields:
        type: bool
        optional: true
      allow_reflow:
        type: bool
        optional: true
      allow_content_probe:
        type: bool
        optional: true

  files:
    # Runtime filtering order:
    # 1) Path filters (include/exclude patterns + *_from + files_from)
    # 2) File type filters (include_file_types / exclude_file_types)
    # 3) Runtime eligibility (supported vs unsupported processing targets)
    #
    # Filesystem-identity eligibility checks such as hard-link policy are runtime
    # processing concerns and are not represented as configuration schema fields.

    include_patterns:
      type: list[str]
      default: []
      description: Glob patterns to include (resolved relative to the declaring configuration file).

    exclude_patterns:
      type: list[str]
      default: []
      description: Glob patterns to exclude (resolved relative to the declaring configuration file).

    include_from:
      type: list[path]
      default: []
      description: Files containing include patterns (one per line; comments allowed; resolved
        relative to the declaring configuration file).

    exclude_from:
      type: list[path]
      default: []
      description: Files containing exclude patterns (one per line; comments allowed; resolved
        relative to the declaring configuration file).

    files_from:
      type: list[path]
      default: []
      description: Files containing explicit file lists (one path per line; comments allowed;
        resolved relative to the declaring configuration file).

    include_file_types:
      type: list[str]
      default: []
      description: Restrict processing to these local or canonical qualified file type identifiers.

    exclude_file_types:
      type: list[str]
      default: []
      description: Exclude these local or canonical qualified file type identifiers.

    files:
      type: list[path]
      default: []
      description: Input paths (files/directories) to scan; commonly provided via CLI.
```

At runtime, file type identifiers normalize to canonical qualified keys before:

- resolution and filtering
- policy lookup
- processor binding lookup
- probe evaluation
- API overlay application

This normalization behavior is shared consistently across:

- TOML configuration
- CLI options
- API overlays
- effective runtime policy resolution

Configuration-source identity normalization follows the same path-spelling model. File-backed
configuration sources are normalized to their resolved configuration-file target before precedence,
scope, and applicability evaluation occur.

If multiple discovered or explicit configuration entries resolve to the same configuration-source
identity, TopMark retains only the highest-precedence occurrence for configuration layering and
provenance evaluation. A physical configuration file therefore contributes at most one effective
layer, even when reached through multiple discovery paths or symlink spellings.

Workspace-root discovery is evaluated earlier and determines which project configuration files are
found. Discovery uses the resolved discovery anchor when walking the project chain.

This normalization is separate from runtime processing-target eligibility. Hard-link policy is
evaluated for selected processing paths during runtime filesystem processing and is not a
configuration-schema feature.

______________________________________________________________________

## Identifier ambiguity

Local identifiers such as:

```text
python
markdown
html
```

are accepted only when they remain unambiguous in the effective composed registry.

If multiple file types share the same local identifier, callers must use the canonical qualified
form:

```text
topmark:python
acme:python
```

Malformed identifiers participate in staged config-loading validation diagnostics.

______________________________________________________________________

## Policy token notes

### header_mutation_mode

`header_mutation_mode` uses TOML/API tokens with underscores:

- `all`: insert missing headers and update existing headers
- `add_only`: insert missing headers only; existing headers are not updated
- `update_only`: update existing headers only; missing headers are not inserted

The equivalent CLI values use hyphens for the non-default modes: `add-only` and `update-only`.

This policy affects only the [`check`](../usage/commands/check.md) pipeline behavior.

It affects dry-run reporting, apply behavior, API result views, and outcome bucketing.

It does not apply to [`strip`](../usage/commands/strip.md) or [`probe`](../usage/commands/probe.md),
and safety gates still take precedence: malformed headers, unreadable files, unsupported files,
blocked filesystem states, and other non-mutable conditions are not made mutable by this policy.

______________________________________________________________________

## Non-goals

The configuration schema intentionally does not support:

- fuzzy matching for file type identifiers
- implicit namespace fallback
- automatic alias expansion
- silent ambiguity resolution
- plugin-specific schema mutation during config loading

Identifier handling intentionally remains explicit, deterministic, and ambiguity-aware.

______________________________________________________________________

## Configuration-source identity notes

The external configuration schema does not expose a separate configuration identity field.

Instead, file-backed configuration sources implicitly use the resolved configuration-file target as
their identity.

Workspace-root discovery is a separate concern. Discovery-anchor resolution determines which
configuration files are discovered before configuration-source identity is evaluated.

This means:

- layered provenance exports report resolved configuration targets;
- scope applicability is evaluated relative to resolved configuration targets;
- symlink spellings are not preserved for configuration precedence; and
- machine-readable provenance reflects configuration-source identity rather than invocation
  spelling.

This behavior mirrors the path-spelling normalization part of TopMark's processing-target identity
model for runtime file processing. Runtime processing-target eligibility checks, such as hard-link
policy enforcement, are separate from configuration-source identity and are not exposed by the
external configuration schema.
