<!--
topmark:header:start

  project      : TopMark
  file         : bindings.md
  file_relpath : docs/usage/commands/registry/bindings.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `registry bindings` Command Guide

**Purpose:** Display effective file type ↔ processor relationships.

The `registry bindings` subcommand lists how TopMark connects **file types** to **header
processors**. Use it to understand which processor will handle a given file type at runtime after
resolution, and to identify:

- file types without a processor (unbound)
- processors that are not used (unused)

______________________________________________________________________

## Command applicability

`registry bindings` is informational and file-agnostic. It inspects TopMark's built-in registry
state, not project files or discovered configuration.

It does not accept file-processing inputs:

- positional PATH arguments are rejected as invalid CLI usage
- `-` is not a content-STDIN sentinel for this command
- `--stdin-filename` does not apply
- file-list STDIN modes (for example, `--files-from -`) do not apply
- `--quiet` is not supported; use output-format options for machine-readable or lower-noise output

______________________________________________________________________

## Quick start

```bash
# List all registered bindings (brief mode)
topmark registry bindings

# List all registered bindings in Markdown (detailed mode)
topmark registry bindings --long --output-format markdown

# Machine‑readable
topmark registry bindings --output-format json | jq
```

______________________________________________________________________

### See also

For the canonical, version-accurate list (used for the docs), see:

- [Supported bindings (generated)](../../generated/bindings.md)

(This page is generated via `topmark registry bindings --long --output-format markdown`.)

______________________________________________________________________

## Output formats

Use `--output-format` to pick the output format:

- `text` — human‑readable (brief or detailed)
- `json` — a single JSON document with `meta`, `bindings`, `unbound_filetypes`, and
  `unused_processors` keys
- `ndjson` — one JSON object per line (stream‑friendly, record-oriented)
- `markdown` — a beautified Markdown table (great for docs)

The `--long` flag controls the level of detail for **all** formats.

{% include-markdown "\_snippets/output-contract-no-quiet.md" %}

______________________________________________________________________

### JSON structure

The JSON output has the following structure:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "bindings": [ /* BindingEntry ... */ ],
  "unbound_filetypes": [ /* FileTypeRef ... */ ],
  "unused_processors": [ /* ProcessorRef ... */ ]
}
```

- `meta` contains machine metadata (tool, version, platform, and optionally `detail_level`).
- `bindings` is the list of effective file type ↔ processor relationships.
- `unbound_filetypes` lists file types without a processor.
- `unused_processors` lists processors not referenced by any binding.

In `--long` mode, entries in all collections are expanded with additional descriptive fields.

______________________________________________________________________

Unlike [`registry filetypes`](./filetypes.md) and [`registry processors`](./processors.md), which
show identities, this command focuses on **relationships**.

## What it shows

### Brief (default)

- **File type → Processor mapping** — using qualified identifiers

### Detailed (`--long`)

Rendered consistently across `text`, `json`, `ndjson`, and `markdown`:

- **File type qualified key**
- **Processor qualified key**
- **File type local key / namespace**
- **Processor local key / namespace**
- **Descriptions** (file type and processor)

Additional sections:

- **Unbound file types** — recognized file types without a processor
- **Unused processors** — processors not referenced by any binding

______________________________________________________________________

## Numbered output & verbosity

In human-readable formats, TopMark renders a **numbered list** of file types with right-aligned
indices (e.g., `1.`, `2.`, …) to keep long lists scannable. With `--long` or higher TEXT verbosity,
additional details are shown alongside each identifier.

______________________________________________________________________

## Examples

```bash
# Brief list
topmark registry bindings

# Detailed list (human)
topmark registry bindings --long

# Detailed Markdown table (ideal for project docs)
topmark registry bindings --long --output-format markdown

# JSON for scripting
topmark registry bindings --long --output-format json | jq '.bindings[]'

# Inspect unbound file types
topmark registry bindings --output-format json | jq '.unbound_filetypes[]'

# Inspect unused processors
topmark registry bindings --output-format json | jq '.unused_processors[]'

# NDJSON for streaming
topmark registry bindings --output-format ndjson | head -n 5
```

______________________________________________________________________

## Exit codes

`topmark registry bindings` is a purely informational command and exits with `SUCCESS (0)` on
successful execution.

Common `registry bindings` exit codes:

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

- Bindings represent the **effective runtime mapping** used by TopMark.
- The output is independent of project configuration discovery.
- A file type may be intentionally unbound (e.g., `skip_processing = true`).
- This command is the best way to debug resolution issues or missing processor registrations.
- `--quiet` is not supported for registry commands; use output-format options instead if you need
  non-TEXT output.
