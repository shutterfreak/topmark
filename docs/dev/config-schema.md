<!--
topmark:header:start

  project      : TopMark
  file         : config-schema.md
  file_relpath : docs/dev/config-schema.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Configuration schema summary

This page is a **machine-readable summary** of TopMark’s external configuration schema as consumed
from `topmark.toml` and from `[tool.topmark]` in `pyproject.toml`.

> [!NOTE]
>
> - This is a schema *summary* (not a full JSON Schema).
> - The ordering mirrors `src/topmark/toml/topmark-example.toml`.
> - Keys are defined authoritatively in `src/topmark/toml/keys.py`.
>
> Machine and human outputs expose a flattened compatibility view derived from these staged
> validation logs; the staged form is not serialized directly. For 1.0, this flattened form is the
> accepted machine/API contract (stable entry shape `{level, message}`).

```md
`strict_config_checking` is a **TOML-source-local config-loading option**, not a
layered `Config` field. It is resolved from `[config]` / `[tool.topmark.config]`
during TOML source resolution and applied after layered config merging. In the
current implementation, its effective value governs staged config-loading
validation evaluated across TOML-source, merged-config, and
runtime-applicability diagnostics.

This distinction matters for `topmark config dump --show-layers`:
- the human-facing layered TOML export exposes source-local TOML fragments under
  `[[layers]].toml.*`
- the machine-readable layered export exposes the same source-local TOML
  fragments under `config_provenance.layers[].toml`
```

## Schema validation model

TopMark performs **whole-source TOML schema validation** before any layered configuration is
deserialized:

- unknown top-level sections (e.g. `[foo]`) are reported as TOML validation issues
- missing known sections are reported as INFO diagnostics
- unknown keys within known sections (e.g. `[config].bogus`) are also reported
- validation is source-local and happens per TOML file during loading

After this step, only the **layered config fragment** is passed to the config layer
(`MutableConfig`) for value parsing and normalization.

At this boundary, diagnostics remain **staged**; flattening into a single compatibility view is
performed only at reporting, exception, and machine-output boundaries. For 1.0, staged validation
remains primarily internal, while public reporting and machine/API surfaces expose only the
flattened compatibility diagnostics contract.

At the TOML layer, malformed known sections are handled as warning-and-ignore cases, while missing
known sections are emitted as INFO diagnostics. This lets callers distinguish absent sections from
malformed-present sections before staged config-validation semantics are applied. These TOML-source
diagnostics are then evaluated together with merged-config and runtime-applicability diagnostics
during staged config-loading/preflight validation.

This means:

- TOML schema validation is handled in `topmark.toml`
- config value/type validation is handled in `topmark.config` as staged validation logs
  (merged-config and runtime-applicability stages)
- layered config deserialization (`mutable_config_from_layered_toml_table`) assumes schema
  validation already happened, but still performs defensive parsing for API and test inputs

```yaml
topmark:
  # In layered provenance exports, source-local TOML fragments preserve their
  # original TOML grouping, including `[config]` and `[writer]`, rather than
  # collapsing everything into the final flattened Config payload.
  config:
    type: table
    description: TOML-source-local options resolved during TOML loading, not part of layered Config merging.
    root:
      type: bool
      default: false
      description: Stop upward config discovery when set in a discovered config.
    strict_config_checking:
      type: bool
      default: false
      description: Source-local strictness preference applied to staged config-loading/preflight validation; warnings become failures when effective strict config checking is enabled across TOML-source, merged-config, and runtime-applicability diagnostics.

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
      description: Affects header metadata (file_relpath), not discovery.

  writer:
    type: table
    description: TOML-source-local writer options (not part of layered Config).
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
      description: Control whether TopMark inserts and updates headers, only inserts missing headers, or only updates existing headers.

    allow_header_in_empty_files:
      type: bool
      default: false
      description: Allow inserting headers into files considered empty under the effective empty insertion policy.

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
    description: Per-file-type policy overrides, keyed by file type identifier.
    additionalProperties:
      header_mutation_mode:
        type: str
        optional: true
        enum: ["all", "add_only", "update_only"]
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
    # Filtering order:
    # 1) Path filters (include/exclude patterns + *_from + files_from)
    # 2) File type filters (include_file_types / exclude_file_types)
    # 3) Eligibility (supported vs unsupported)

    include_patterns:
      type: list[str]
      default: []
      description: Glob patterns to include (relative to declaring config source).

    exclude_patterns:
      type: list[str]
      default: []
      description: Glob patterns to exclude (relative to declaring config source).

    include_from:
      type: list[path]
      default: []
      description: Files containing include patterns (one per line; comments allowed).

    exclude_from:
      type: list[path]
      default: []
      description: Files containing exclude patterns (one per line; comments allowed).

    files_from:
      type: list[path]
      default: []
      description: Files containing explicit file lists (one path per line; comments allowed).

    include_file_types:
      type: list[str]
      default: []
      description: Restrict processing to these file type identifiers.

    exclude_file_types:
      type: list[str]
      default: []
      description: Exclude these file type identifiers.

    files:
      type: list[path]
      default: []
      description: Input paths (files/directories) to scan; commonly provided via CLI.
```
