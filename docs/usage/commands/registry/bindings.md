<!--
topmark:header:start

  project      : TopMark
  file         : bindings.md
  file_relpath : docs/usage/commands/registry/bindings.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# `topmark registry bindings`

**Purpose:** Display effective file type ↔ header processor bindings.

The `registry bindings` subcommand lists how TopMark connects file types to header processors. Use
it to understand which processor will handle a given file type at runtime after resolution, and to
identify:

- file types without a processor (unbound)
- processors that are not used (unused)

{% include-markdown "\_snippets/terminology.md" %}

______________________________________________________________________

## Input applicability

`registry bindings` is informational and file-agnostic. It inspects TopMark's effective composed
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
# List all registered bindings (brief mode)
topmark registry bindings

# List all registered bindings in Markdown (detailed mode)
topmark registry bindings --long --output-format markdown

# Machine-readable
topmark registry bindings --output-format json | jq
```

______________________________________________________________________

## Binding semantics

Bindings use canonical qualified identities.

Examples:

```text
topmark:python
topmark:markdown
```

Binding-oriented machine-readable output exposes canonical identity fields such as:

- `file_type_key`
- `processor_key`

And in long mode:

- `file_type_local_key`
- `file_type_namespace`
- `processor_local_key`
- `processor_namespace`

These fields are intended for stable comparisons, joins, tooling integration, and runtime
introspection.

{% include-markdown "\_snippets/file-type-identifiers.md" %}

See [file-type filtering](../../filtering.md#file-type-filtering) for the full identifier contract.

Bindings expose the effective runtime processor-dispatch relationships using canonical qualified
identities.

______________________________________________________________________

## Output behavior

Use `--output-format` to pick the output format:

- `text` - human-readable (brief or detailed)
- `json` - a single machine-readable JSON document with `meta`, `bindings`, `unbound_filetypes`, and
  `unused_processors` keys
- `ndjson` - one machine-readable NDJSON record per line (stream-friendly, record-oriented)
- `markdown` - a document-oriented Markdown table

The `--long` flag controls the detail level for all output formats.

{% include-markdown "\_snippets/output-contract-no-quiet.md" %}

______________________________________________________________________

## Detail levels

### Brief output (default)

- File type -> processor binding using canonical qualified identifiers

### Detailed output (`--long`)

Rendered consistently across `text`, `json`, `ndjson`, and `markdown`:

- Canonical file type qualified key
- Canonical processor qualified key
- File type local key / namespace
- Processor local key / namespace
- Descriptions (file type and processor descriptions)

Additional sections:

- Unbound file types - recognized file types without an effective processor binding
- Unused processors - processors not referenced by any effective binding

______________________________________________________________________

## Shared output controls

In human-readable formats, TopMark renders a numbered list of bindings with right-aligned indices
(e.g., `1.`, `2.`, ...) to keep long lists scannable. With `--long`, additional details are shown
alongside each identifier. TEXT verbosity (`-v`) affects presentation only.

______________________________________________________________________

## Machine-readable output

JSON output emits one machine-readable document with shared metadata and separate collections for
bindings, unbound file types, and unused processors:

```jsonc
{
  "meta": { /* MetaPayload */ },
  "bindings": [ /* BindingEntry ... */ ],
  "unbound_filetypes": [ /* FileTypeRef ... */ ],
  "unused_processors": [ /* ProcessorRef ... */ ]
}
```

- `meta` contains shared machine metadata, including `tool`, `version`, `platform`, and
  `detail_level`.
- `bindings` contains the effective file type ↔ processor relationships.
- Brief binding entries include `file_type_key` and `processor_key`.
- Long binding entries add descriptive identity fields such as `file_type_local_key`,
  `file_type_namespace`, `processor_local_key`, `processor_namespace`, and descriptions.
- `unbound_filetypes` lists file types without an effective processor relationship.
- `unused_processors` lists processors that are registered but not referenced by any effective
  binding.

NDJSON output emits one machine-readable record per binding or registry-state entry:

```jsonc
{
  "kind": "binding",
  "meta": { /* MetaPayload */ },
  "binding": { /* BindingEntry */ }
}
```

Additional NDJSON record kinds include `unbound_filetype` and `unused_processor`.

Each NDJSON record repeats the shared metadata and stores the payload under a kind-specific key.

Unlike [`topmark registry filetypes`](filetypes.md) and
[`topmark registry processors`](processors.md), which focus on identities, this command focuses on
runtime processor-dispatch bindings.

Machine-readable output exposes canonical binding identities suitable for stable automation and
tooling integration.

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
topmark registry bindings --long --output-format json | jq '.bindings[] | {filetype: .file_type_key, processor: .processor_key}'

# Inspect unbound file types
topmark registry bindings --output-format json | jq '.unbound_filetypes[]'

# Inspect unused processors
topmark registry bindings --output-format json | jq '.unused_processors[]'

# NDJSON for streaming
topmark registry bindings --output-format ndjson | jq -r 'select(.kind == "binding") | .binding.file_type_key'
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

- Bindings represent the effective runtime processor-dispatch mapping used by TopMark.
- The effective binding view is composed from built-in bindings plus runtime overlays.
- The output is independent of project configuration discovery.
- A file type may be intentionally unbound, for example when it is marked `skip_processing = true`.
- This command is the best way to debug processor-dispatch issues, missing processor registrations,
  or unexpected runtime bindings.
- `--quiet` is not supported for registry commands; use output-format options instead if you need
  non-TEXT output.

______________________________________________________________________

## Related commands

- [`topmark registry filetypes`](filetypes.md) - inspect canonical file type identities, matching
  rules, and policies.
- [`topmark registry processors`](processors.md) - inspect canonical processor identities and
  capabilities.

______________________________________________________________________

## Related docs

- [Command overview](../../cli.md)
- [Registry model](../../../dev/registry-model.md)
- [Plugins and extensibility](../../../dev/plugins.md)
- [Resolution model](../../../dev/resolution.md)
- [Machine-readable output](../../../dev/machine-output.md)
- [Machine-readable format conventions](../../../dev/machine-formats.md)
- [Supported bindings](../../generated/bindings.md)
- [Exit codes](../../exit-codes.md)
- [Terminology and Canonical Vocabulary](../../../terminology.md)

______________________________________________________________________

## Troubleshooting

- **Unexpected processor binding**: inspect the canonical qualified file type identity and verify
  the effective runtime binding layer.
- **Unexpected identifier form**: registry commands intentionally emit canonical qualified
  identifiers such as `topmark:python`.
- **Missing processor relationship**: inspect [`registry processors`](processors.md) and
  [`registry filetypes`](filetypes.md) to verify the underlying identities.
