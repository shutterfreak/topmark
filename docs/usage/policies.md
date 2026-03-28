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

Policies can be supplied from:

- discovered config files (`topmark.toml` or `[tool.topmark]` in `pyproject.toml`)
- command-specific CLI options
- the Python API via public policy overlays

Command-line policy options override resolved config for the current run only.

______________________________________________________________________

## Policy layers

TopMark resolves policy in this order:

1. defaults
1. discovered config files
1. explicit config overlays
1. CLI or API overrides

Per-file-type policy in `policy_by_type` is resolved on top of the global `policy` section.

______________________________________________________________________

## Global policy keys

### `header_mutation_mode`

Controls which files `topmark check` may modify.

Allowed values:

- `all`: insert missing headers and update existing headers
- `add_only`: only insert missing headers
- `update_only`: only update existing headers

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

Controls how TopMark classifies files as empty for insertion.

Allowed values:

- `bytes_empty`
- `logical_empty`
- `whitespace_empty`

```toml
[policy]
empty_insert_mode = "whitespace_empty"
```

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

## Per-file-type policy

Use `policy_by_type.<file_type_id>` to override policy for one file type while inheriting
unspecified values from the global `policy` section.

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

Header insertion/update policies do not apply to `strip`.

______________________________________________________________________

## Reporting vs policy

Reporting controls what the CLI prints. Policy controls what the pipeline is allowed to do.

Examples:

- `--report actionable`: show only files that would be mutated
- `--report noncompliant`: include actionable files plus unsupported file types
- `--header-mutation-mode add-only`: change pipeline mutation behavior

These settings are independent and may be combined.
