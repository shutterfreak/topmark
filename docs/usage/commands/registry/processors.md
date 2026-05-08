<!--
topmark:header:start

  project      : TopMark
  file         : processors.md
  file_relpath : docs/usage/commands/registry/processors.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `registry processors` Command Guide

**Purpose:** Display registered header processor identities.

The `registry processors` subcommand lists registered **header processors** and their
comment/delimiter capabilities. Use it to understand what processing logic is available in the
system.

______________________________________________________________________

## Command applicability

`registry processors` is informational and file-agnostic. It inspects TopMark's effective composed
registry state, not project files or configuration discovery.

It does not accept file-processing inputs:

- positional PATH arguments are rejected as invalid CLI usage
- `-` is not a content-STDIN sentinel for this command
- `--stdin-filename` does not apply
- file-list STDIN modes (for example, `--files-from -`) do not apply
- `--quiet` is not supported; use output-format options for machine-readable or lower-noise output

To see which processor is used for a given file type, use [`registry bindings`](bindings.md).

______________________________________________________________________

## Quick start

```bash
# Brief list
topmark registry processors

# Detailed Markdown table
topmark registry processors --long --output-format markdown

# Machine‑readable
topmark registry processors --output-format json | jq
```

______________________________________________________________________

### See also

- [Registry model](../../../dev/registry-model.md)
- [Plugins and extensibility](../../../dev/plugins.md)
- [Resolution model](../../../dev/resolution.md)
- [Machine-readable output schema](../../../dev/machine-output.md)
- [Machine-readable formats](../../../dev/machine-formats.md)

For the canonical, version-accurate list (used for the docs), see:

- [Supported header processors (generated)](../../generated/processors.md)

(This page is generated via `topmark registry processors --long --output-format markdown`.)

______________________________________________________________________

## Processor identity semantics

Registry processor identities use canonical qualified identifiers.

Examples:

```text
topmark:pound
topmark:xml
```

Registry-oriented machine-readable output exposes canonical identity fields such as:

- `qualified_key`
- `file_type_key`
- `processor_key`

These fields are intended for stable comparisons, joins, tooling integration, and runtime
introspection.

Processor identities are registry-level runtime identities and are independent from file type
identities and processor bindings.

{% include-markdown "\_snippets/file-type-identifiers.md" %}

This page is one of the primary introspection surfaces for the freeze semantics.

______________________________________________________________________

## Output formats

Use `--output-format` to pick the output format:

- `text` — human‑readable (brief or detailed)
- `json` — a single JSON document with `meta` and `processors` keys
- `ndjson` — one JSON object per line (stream-friendly, record-oriented)
- `markdown` — a beautified Markdown table

The `--long` flag controls the detail level for all output formats.

This flag controls the data/detail depth across all formats. TEXT-only verbosity (`-v`) affects
presentation (e.g., headings) and does not change the data fields emitted.

{% include-markdown "\_snippets/output-contract-no-quiet.md" %}

______________________________________________________________________

### JSON structure

The JSON output has the following structure:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "processors": [ /* ProcessorEntry ... */ ]
}
```

- `meta` contains machine metadata (tool, version, platform, and optionally `detail_level`).
- `processors` is a list of processor entries. Processor entries expose canonical qualified
  identities.

In `--long` mode, each entry is expanded with additional fields such as delimiter and comment
capabilities.

Machine-readable output emits canonical processor identities suitable for stable automation and
tooling integration.

______________________________________________________________________

Unlike [`registry bindings`](bindings.md), this command focuses on canonical processor identities,
not processor-dispatch relationships.

## What it shows

### Brief (default)

- **Canonical qualified key** — unique processor identifier
- **Description** — short description of the processor

### Detailed (`--long`)

Rendered consistently across `text`, `json`, `ndjson`, and `markdown`:

- **Canonical qualified key**
- **Namespace / local key**
- **Description**
- **Delimiter / comment capabilities** (if applicable)
- **Bound** (`true`/`false`) — whether the processor is referenced by any binding

______________________________________________________________________

## Numbered output & verbosity

In human-readable formats, TopMark renders a **numbered list** of processors with right-aligned
indices (e.g., `1.`, `2.`, …) to keep long lists scannable. With `--long`, additional processor
identity and capability details are shown. TEXT verbosity (`-v`) affects presentation only (for TEXT
output).

______________________________________________________________________

## Examples

```bash
# Brief list
topmark registry processors

# Detailed Markdown table (ideal for project docs)
topmark registry processors --long --output-format markdown

# JSON for scripting
topmark registry processors --long --output-format json | jq '.processors[] | {cls: .class}'

# NDJSON for streaming
topmark registry processors --output-format ndjson | grep processor | head -n 5
```

______________________________________________________________________

## Exit codes

`topmark registry processors` is a purely informational command and exits with `SUCCESS (0)` on
successful execution.

Common `registry processors` exit codes:

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

- Processors define how headers are parsed, rendered, updated, and stripped.
- The output is independent of project configuration discovery.
- Whether a processor is actually used is determined by bindings (see
  [`registry bindings`](bindings.md)).
- The effective runtime processor view is composed from built-in processor definitions plus runtime
  overlays.
- Prefer [`registry bindings`](bindings.md) when investigating which processor handles a file type.
- `--quiet` is not supported for registry commands; use output-format options instead if you need
  non-TEXT output.

______________________________________________________________________

## Troubleshooting

- **Unexpected identifier form**: registry commands intentionally emit canonical qualified
  identifiers.
- **Unexpected processor usage**: inspect [`registry bindings`](bindings.md) to view effective
  processor-dispatch relationships.
- **Unexpected missing processor**: ensure the processor is registered in the effective composed
  registry view.

______________________________________________________________________

## Related commands

- [`registry filetypes`](filetypes.md) — inspect canonical file type identities, matching rules, and
  policies.
- [`registry bindings`](bindings.md) — inspect effective processor-dispatch relationships between
  file types and processors.

An overview of all CLI commands is available in [CLI overview](../../cli.md).
