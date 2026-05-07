<!--
topmark:header:start

  project      : TopMark
  file         : filetypes.md
  file_relpath : docs/usage/commands/registry/filetypes.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `registry filetypes` Command Guide

**Purpose:** Display registered file type identities.

The `registry filetypes` subcommand lists TopMark’s known **file types**, including their matching
rules and header policies. Use it to understand how TopMark classifies files and what behavior is
associated with each type.

______________________________________________________________________

## Command applicability

`registry filetypes` is informational and file-agnostic. It inspects TopMark's effective composed
registry state, not project files or configuration discovery.

It does not accept file-processing inputs:

- positional PATH arguments are rejected as invalid CLI usage
- `-` is not a content-STDIN sentinel for this command
- `--stdin-filename` does not apply
- file-list STDIN modes (for example, `--files-from -`) do not apply
- `--quiet` is not supported; use output-format options for machine-readable or lower-noise output

______________________________________________________________________

## Quick start

```bash
# List all supported file types (brief mode)
topmark registry filetypes

# List all supported file types in Markdown (detailed mode)
topmark registry filetypes --long --output-format markdown

# Machine‑readable
topmark registry filetypes --output-format json | jq
```

______________________________________________________________________

### See also

- [Registry model](../../../dev/registry-model.md)
- [Plugins and extensibility](../../../dev/plugins.md)
- [Resolution model](../../../dev/resolution.md)
- [Machine-readable output](../../../dev/machine-output.md)
- [Machine format conventions](../../../dev/machine-formats.md)

For the canonical, version-accurate list (used for the docs), see:

- [Supported file types (generated)](../../generated/filetypes.md)

(This page is generated via `topmark registry filetypes --long --output-format markdown`.)

______________________________________________________________________

## File type identity semantics

Registry file type identities use canonical qualified identifiers.

Examples:

```text
topmark:python
topmark:markdown
```

Registry-oriented machine output exposes canonical identity fields such as:

- `qualified_key`
- `file_type_key`
- `processor_key`

These fields are intended for stable comparisons, joins, tooling integration, and runtime
introspection.

Local identifiers such as:

```text
python
markdown
```

may still be accepted in public configuration and CLI filtering when unambiguous, but registry file
type views always operate on canonical qualified identities.

{% include-markdown "\_snippets/file-type-identifiers.md" %}

This page is one of the primary introspection surfaces for the freeze semantics.

______________________________________________________________________

## Output formats

Use `--output-format` to pick the output format:

- `text` — human‑readable (brief or detailed)
- `json` — a single JSON document with `meta` and `filetypes` keys
- `ndjson` — one JSON object per line (stream‑friendly, record-oriented)
- `markdown` — a beautified Markdown table (great for docs)

The `--long` flag controls the level of detail for **all** formats.

This flag controls the data/detail depth across all formats. TEXT-only verbosity (`-v`) affects
presentation (e.g., headings) and does not change the data fields emitted.

{% include-markdown "\_snippets/output-contract-no-quiet.md" %}

______________________________________________________________________

### JSON structure

The JSON output has the following structure:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "filetypes": [ /* FileTypeEntry ... */ ]
}
```

- `meta` contains machine metadata (tool, version, platform, and optionally `detail_level`).
- `filetypes` is a list of file type entries. File type entries expose canonical qualified
  identities.

In `--long` mode, each entry is expanded with additional fields such as matching rules and header
policy information.

Machine-readable output emits canonical qualified identities suitable for stable automation and
tooling integration.

Unlike [`registry bindings`](bindings.md), this command focuses on canonical file type identities,
not processor-dispatch relationships.

## What it shows

### Brief (default)

- **Local key** — the namespace-local identifier (e.g., `python`, `markdown`, `env`)
- **Description** — a short description

### Detailed (`--long`)

Rendered consistently across `text`, `json`, `ndjson`, and `markdown`:

- **Canonical qualified key**
- **Namespace / local key**
- **Extensions** (comma‑separated)
- **Filenames** (comma‑separated)
- **Patterns** (comma‑separated)
- **skip_processing** (`true`/`false`)
- **has_content_matcher** (`true`/`false`)
- **header_policy** (structured policy fields)
- **Bound** (`true`/`false`)
- **Description**

______________________________________________________________________

## Numbered output & verbosity

In human-readable formats, TopMark renders a **numbered list** of file types with right-aligned
indices (e.g., `1.`, `2.`, …) to keep long lists scannable. With `--long`, additional canonical
identity and matching details are shown alongside each entry. TEXT verbosity (`-v`) affects
presentation only (for TEXT output).

______________________________________________________________________

## Examples

```bash
# Brief list
topmark registry filetypes

# Detailed list (human)
topmark registry filetypes --long

# Detailed Markdown table (ideal for project docs)
topmark registry filetypes --long --output-format markdown

# JSON for scripting
topmark registry filetypes --long --output-format json | jq '.filetypes[] | select(.skip_processing==false)'

# NDJSON for streaming
topmark registry filetypes --output-format ndjson | head -n 5
```

______________________________________________________________________

## Exit codes

`topmark registry filetypes` is a purely informational command and exits with `SUCCESS (0)` on
successful execution.

Common `registry filetypes` exit codes:

| Scenario                      | Exit code          |
| ----------------------------- | ------------------ |
| Command executed successfully | `SUCCESS (0)`      |
| Invalid CLI usage             | `USAGE_ERROR (64)` |

Notes:

- This command does not process project files and does not use file-processing exit codes such as
  `WOULD_CHANGE (2)`, `FILE_NOT_FOUND (66)`, or `IO_ERROR (74)`.
- Invalid positional paths are reported as CLI usage errors, not file-processing diagnostics.
- `--quiet` is not supported for registry commands; use output-format options instead for non-TEXT
  output.

See [`Exit codes`](../../exit-codes.md) for the complete CLI-wide exit-code contract.

______________________________________________________________________

## Notes

- File types define **how files are matched and classified**.
- The output is independent of project configuration discovery.
- Processor-dispatch behavior is determined by bindings (see [`registry bindings`](bindings.md)).
- The effective runtime file type view is composed from built-in definitions plus runtime overlays.
- A file type may be present but not processed if it is unbound or marked `skip_processing`.
- `--quiet` is not supported for registry commands; use output-format options instead if you need
  non-TEXT output.

______________________________________________________________________

## How TopMark resolves file types

TopMark may have multiple `FileType` definitions that match a given path. The resolver evaluates all
matching file types and deterministically selects the most specific match.

In practice, specificity follows this order:

1. **Explicit filenames / tail subpaths** (e.g., `Makefile`, `.vscode/settings.json`)
1. **Regex patterns** (e.g., `Dockerfile(\..+)?`, `requirements.*\.(in|txt)$`)
1. **Extensions** (e.g., `.py`, `.md`, `.json`)

If multiple candidates remain tied, TopMark prefers the more “headerable” choice (that is, file
types not marked `skip_processing = true`).

### Tail subpath matching

`FileType.filenames` entries that contain a path separator (e.g., `.vscode/settings.json`) are
matched as **path suffixes** against `path.as_posix()`. Plain names still match the basename only.

### JSON vs JSONC

- `json` is recognized but typically has `skip_processing = true` because strict JSON has no
  comments, and TopMark will not insert headers into it.
- `jsonc` is an opt‑in type that uses `//` headers. It relies on a content matcher and an insert
  checker to avoid misclassifying strict JSON.

### Unsupported but recognized types

Some file types are recognized but intentionally left unmodified (reported as “unsupported”):

- `license_text` (keep verbatim)
- `python-typed-marker` (`py.typed` is a single-token marker)

These are hidden by default; use `--report=noncompliant` or `--report=all` to show these in reports.

______________________________________________________________________

## Troubleshooting

- **Unexpected identifier form**: registry commands intentionally emit canonical qualified
  identifiers such as `topmark:python`.
- **Unexpected processor behavior**: inspect [`registry bindings`](bindings.md) to view effective
  processor-dispatch relationships.
- **Unexpected file type selection**: use [`topmark probe`](../probe.md) to inspect resolver
  candidate evaluation.

______________________________________________________________________

## Related commands

- [`registry processors`](processors.md) — inspect canonical processor identities and capabilities.
- [`registry bindings`](bindings.md) — inspect effective processor-dispatch relationships between
  file types and processors.

An overview of all CLI commands is available in [CLI overview](../../cli.md).
