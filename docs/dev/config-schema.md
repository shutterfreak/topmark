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

This page is a **machine-readable summary** of TopMark’s external configuration schema
as consumed from `topmark.toml` and from `[tool.topmark]` in `pyproject.toml`.

> [!NOTE] **Config diagnostics**
>
> - This is a schema *summary* (not a full JSON Schema).
> - The ordering mirrors `src/topmark/config/topmark-default.toml`.
> - Keys are defined authoritatively in `src/topmark/config/keys.py`.

```yaml
topmark:
  root:
    type: bool
    default: false
    description: Stop upward config discovery when set in a discovered config.

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

    header_format:
      type: str
      default: "native"
      enum: ["native", "plain", "json"]
      description: Header output format for rendering.

  writer:
    target:
      type: str
      default: "file"
      enum: ["file", "stdout"]
      description: Where results are emitted.

    strategy:
      type: str
      default: "atomic"
      enum: ["atomic", "inplace"]
      description: How file writes are performed when target="file".

  policy:
    add_only:
      type: bool
      default: false
      description: Insert missing headers only (do not update existing).

    update_only:
      type: bool
      default: false
      description: Update existing headers only (do not insert missing).

    allow_header_in_empty_files:
      type: bool
      default: false
      description: Allow inserting headers into otherwise empty files.

  policy_by_type:
    type: table
    default: {}
    description: Per-file-type policy overrides, keyed by file type identifier.
    additionalProperties:
      allow_header_in_empty_files:
        type: bool
        optional: true
      add_only:
        type: bool
        optional: true
      update_only:
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

    relative_to:
      type: path
      default: "."
      description: Affects header metadata (file_relpath), not discovery.
```
