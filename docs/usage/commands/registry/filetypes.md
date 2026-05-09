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

## Input applicability

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

## Identity semantics

Registry file type identities use canonical qualified identifiers.

Examples:

```text
topmark:python
topmark:markdown
```

Registry-oriented machine-readable output exposes canonical identity fields such as:

- `local_key`
- `namespace`
- `qualified_key`

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

This command exposes the effective runtime file type view after registry composition and
configuration freeze.

______________________________________________________________________

## Output behavior

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

## Detail levels

### Brief output (default)

- **Local key** — the namespace-local identifier (e.g., `python`, `markdown`, `env`)
- **Description** — a short description

### Detailed output (`--long`)

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

## Shared output controls

In human-readable formats, TopMark renders a **numbered list** of file types with right-aligned
indices (e.g., `1.`, `2.`, …) to keep long lists scannable. With `--long`, additional details are
shown alongside each identifier. TEXT verbosity (`-v`) affects presentation only.

______________________________________________________________________

## Machine-readable output

JSON output emits one document with shared metadata and a `filetypes` array:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "filetypes": [ /* FileTypeEntry ... */ ]
}
```

- `meta` contains shared machine metadata, including `tool`, `version`, `platform`, and
  `detail_level`.
- `filetypes` is a list of file type entries.
- Brief entries include `local_key`, `namespace`, `qualified_key`, and `description`.
- Long entries add matching, processing, and policy fields such as `bound`, `extensions`,
  `filenames`, `patterns`, `skip_processing`, `has_content_matcher`, `has_insert_checker`, and
  `policy`.

NDJSON output emits one record per file type:

```jsonc
{
  "kind": "filetype",
  "meta": { /* MetaPayload */ },
  "filetype": { /* FileTypeEntry */ }
}
```

Each NDJSON record repeats the shared metadata and stores the file type payload under `filetype`.
The `kind` field is always `filetype` for this command.

Machine-readable output emits canonical qualified file type identities suitable for stable
automation and tooling integration.

Unlike [`topmark registry bindings`](bindings.md), this command focuses on canonical file type
identities, not processor-dispatch relationships.

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
topmark registry filetypes --long --output-format json | jq '.filetypes[] | select(.skip_processing == false) | .qualified_key'

# NDJSON for streaming
topmark registry filetypes --output-format ndjson | jq -r '.filetype.qualified_key'
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

Registry file types may overlap intentionally. Resolver behavior may depend on extension matching,
content probing, insertability checks, and processing policy.

TopMark may have multiple matching file type candidates for a given path. The resolver evaluates all
matching candidates and deterministically selects the most specific effective file type.

In practice, specificity follows this order:

1. **Explicit filenames / path suffixes** (e.g., `Makefile`, `.vscode/settings.json`)
1. **Regex patterns** (e.g., `Dockerfile(\..+)?`, `requirements.*\.(in|txt)$`)
1. **Extensions** (e.g., `.py`, `.md`, `.json`)

If multiple candidates remain tied, TopMark prefers the more “headerable” choice (that is, file
types not marked `skip_processing = true`).

### Path-suffix matching

Filename rules that contain path separators (for example, `.vscode/settings.json`) are treated as
path-suffix matches against normalized POSIX-style paths. Plain filename rules still match only the
basename.

### Content-based disambiguation

Some file types intentionally share the same filename patterns or extensions.

In these cases, TopMark may use:

- content matchers
- insert checkers
- headerability rules
- `skip_processing` semantics

to determine which effective file type should apply.

A common example is `.json`:

- strict JSON (`topmark:json`) is recognized but treated as unheaderable because JSON does not
  support comments
- JSON-with-comments variants may still be supported through specialized file types such as
  `topmark:json-as-jsonc`
- dedicated `.jsonc` files may map directly to `topmark:jsonc`

This allows TopMark to distinguish between:

- recognized-but-unmodifiable formats
- comment-capable variants
- and files that can safely accept TopMark headers

without relying solely on filename extensions.

### Unsupported but recognized types

Some file types are recognized but intentionally left unmodified (reported as “unsupported”):

- `license_text` (keep verbatim)
- `python-typed-marker` (`py.typed` is a single-token marker)

These are hidden by default; use `--report=noncompliant` or `--report=all` to show these in reports.

______________________________________________________________________

## Related commands

- [`topmark registry processors`](processors.md) — inspect canonical processor identities and
  capabilities.
- [`topmark registry bindings`](bindings.md) — inspect effective processor-dispatch relationships
  between file types and processors.

______________________________________________________________________

## Related docs

- [Command overview](../../cli.md)
- [Registry model](../../../dev/registry-model.md)
- [Plugins and extensibility](../../../dev/plugins.md)
- [Resolution model](../../../dev/resolution.md)
- [Machine-readable output schema](../../../dev/machine-output.md)
- [Machine-readable formats](../../../dev/machine-formats.md)
- [Supported file types](../../generated/filetypes.md)
- [Exit codes](../../exit-codes.md)

______________________________________________________________________

## Troubleshooting

- **Unexpected identifier form**: registry commands intentionally emit canonical qualified
  identifiers such as `topmark:python`.
- **Unexpected processor behavior**: inspect [`registry bindings`](bindings.md) to view effective
  processor-dispatch relationships.
- **Unexpected file type selection**: use [`topmark probe`](../probe.md) to inspect resolver
  candidate evaluation.
