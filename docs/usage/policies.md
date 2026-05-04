<!--
topmark:header:start

  project      : TopMark
  file         : policies.md
  file_relpath : docs/usage/policies.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark Policy Guide

TopMark policies control how the pipeline detects file types, classifies empty files, and decides
whether headers may be inserted or updated.

Policy settings are part of the layered configuration (`Config`) and are merged according to
discovery and precedence rules. See:

- [`Configuration overview`](../configuration/index.md)
- [`Discovery & Precedence`](../configuration/discovery.md)

Policies can be supplied from:

- discovered config files (`topmark.toml` or `[tool.topmark]` in `pyproject.toml`)
- command-specific CLI options
- the Python API via public policy overlays

In `topmark.toml`, policy is defined under `[policy]` and `[policy_by_type.<file_type>]`. In
`pyproject.toml`, the same settings live under `[tool.topmark.policy]` and
`[tool.topmark.policy_by_type.<file_type>]`.

During configuration loading, TopMark first validates each whole-source TOML fragment (unknown
sections, unknown keys, malformed section shapes, etc.). Only the validated layered config fragment
contributes to policy resolution.

Command-line policy options override resolved config for the current run only.

______________________________________________________________________

## Policy layers

TopMark resolves policy in this order:

1. defaults
1. discovered config files
1. explicit config overlays
1. CLI or API overrides

These layers are built after TOML-layer validation. Source-local TOML sections (e.g. `[config]`) do
not participate in policy layering.

Per-file-type policy in `policy_by_type` is resolved on top of the global `policy` section.

______________________________________________________________________

## Global policy keys

### `header_mutation_mode`

Controls the mutation intent for `topmark check`.

Allowed TOML/API values:

- `all`: insert missing headers and update existing headers
- `add_only`: insert missing headers only; existing headers are not updated
- `update_only`: update existing headers only; missing headers are not inserted

This policy affects dry-run reporting, apply behavior, API result views, and outcome bucketing. It
applies only to `check`; `strip` and `probe` reject generated-header mutation controls.

Safety gates still take precedence. Malformed headers, unreadable files, unsupported files, blocked
filesystem states, and other non-mutable conditions are not made mutable by `header_mutation_mode`.

Example:

```toml
[policy]
header_mutation_mode = "add_only"
```

### `allow_header_in_empty_files`

Controls whether TopMark may insert headers into files considered empty under the effective
`empty_insert_mode`.

```toml
[policy]
allow_header_in_empty_files = true
```

### `empty_insert_mode`

Controls which empty or empty-like files are classified as empty for insertion.

This policy affects dry-run reporting, `--apply` behavior, API result views, and outcome bucketing.

This setting is evaluated together with `allow_header_in_empty_files`:

- If `allow_header_in_empty_files = false` (default), files classified as empty for insertion are
  treated as unchanged/compliant by default.
- If `allow_header_in_empty_files = true`, files classified as empty for insertion may receive
  generated headers, subject to normal safety gates.

Allowed values:

- `bytes_empty`: only true 0-byte files
- `logical_empty`: true 0-byte files plus logically empty placeholders (optional BOM, optional
  horizontal whitespace, and at most one trailing newline)
- `whitespace_empty`: true 0-byte files plus any decoded content containing only whitespace or
  newlines

```toml
[policy]
empty_insert_mode = "whitespace_empty"
```

`render_empty_header_when_no_fields` is separate. It controls whether TopMark may render an
otherwise empty header when no header fields are configured.

Safety gates still take precedence. Unreadable files, unsupported files, malformed headers, blocked
filesystem states, and other non-mutable conditions are not made mutable by `empty_insert_mode`.

### `render_empty_header_when_no_fields`

Controls whether TopMark may insert an otherwise empty header when no header fields are configured.

```toml
[policy]
render_empty_header_when_no_fields = true
```

### `allow_reflow`

Controls whether TopMark may reflow content while inserting or updating a header.

This can reduce strict idempotence in some cases.

```toml
[policy]
allow_reflow = true
```

### `allow_content_probe`

Controls whether file-type detection may consult file contents when needed.

This policy applies to both `check` and `strip`.

```toml
[policy]
allow_content_probe = false
```

______________________________________________________________________

## Line-ending handling (not a policy)

TopMark’s line-ending behavior is fixed for 1.0 and is **not configurable via policy**.

- Only LF (`\n`), CRLF (`\r\n`), and CR (`\r`) are recognized as physical line-ending styles.
- These styles are preserved across rendering, planning, patching, and writing.
- Files with mixed recognized newline styles are skipped by the mixed-line-ending guard.

Non-standard Unicode separators such as NEL (`U+0085`), Line Separator (`U+2028`), and Paragraph
Separator (`U+2029`) are treated as ordinary content characters. They are not considered line
endings and do not affect newline detection or mixed-newline diagnostics.

Some file-type-specific checks (notably XML) may conservatively skip mutation when such characters
appear near insertion boundaries due to idempotence concerns. This is a localized safety behavior,
not an extension of newline support.

## Per-file-type policy

Use `policy_by_type.<file_type_id>` to override policy for one file type while inheriting
unspecified values from the global `policy` section.

In `pyproject.toml`, this section is written as `[tool.topmark.policy_by_type.<file_type>]`.

Example:

```toml
[policy]
header_mutation_mode = "all"
allow_content_probe = true

[policy_by_type.python]
header_mutation_mode = "update_only"
allow_header_in_empty_files = true
```

In this example:

- Python files inherit `allow_content_probe = true`
- Python files override `header_mutation_mode`
- Python files additionally allow header insertion into empty files

______________________________________________________________________

## Policy options by command

### `topmark check`

`check` supports both check-only and shared policy options.

Check-only policy options:

- `--header-mutation-mode`
- `--allow-header-in-empty-files / --no-allow-header-in-empty-files`
- `--empty-insert-mode`
- `--render-empty-header-when-no-fields / --no-render-empty-header-when-no-fields`
- `--allow-reflow / --no-allow-reflow`

Shared policy options:

- `--allow-content-probe / --no-allow-content-probe`

### `topmark strip`

`strip` supports only shared policy options:

- `--allow-content-probe / --no-allow-content-probe`

Header insertion/update policies, including `header_mutation_mode`, do not apply to `strip` and are
rejected when provided.

______________________________________________________________________

## Reporting vs policy

Reporting controls what the CLI prints. Policy controls what the pipeline is allowed to do.

Examples:

- `--report actionable`: show human per-file entries that would change, changed, failed, or
  otherwise need attention
- `--report noncompliant`: include actionable files plus unsupported file types in human per-file
  output
- `--header-mutation-mode add-only`: allow `check` to insert missing headers but not update existing
  headers

These settings are independent and may be combined.
