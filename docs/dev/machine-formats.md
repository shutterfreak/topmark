<!--
topmark:header:start

  project      : TopMark
  file         : machine-formats.md
  file_relpath : docs/dev/machine-formats.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Machine-readable formats

This page documents TopMark’s **machine-readable output conventions** across commands.

The canonical vocabulary used by this page is defined in
[`Terminology and Canonical Vocabulary`](../terminology.md).

See also:

- [Machine-readable output](machine-output.md)
- [CLI overview](../usage/cli.md)
- [Shared options](../usage/shared-options.md)
- [Exit codes](../usage/exit-codes.md)
- [Configuration](../usage/configuration.md)
- [Filtering](../usage/filtering.md)
- [Registry model](registry-model.md)
- [Terminology and Canonical Vocabulary](../terminology.md)

______________________________________________________________________

## Exit codes vs machine-readable output

Machine-readable formats (`json`, `ndjson`) intentionally **do not encode CLI exit codes inside
payloads**.

- Exit status is communicated exclusively via the process exit code.
- Machine-readable payloads represent **structured results and diagnostics**, not process-level
  success/failure.

Implications for consumers:

- Always check the process exit code in addition to parsing machine-readable output.
- Do not attempt to infer success/failure solely from payload content (for example, empty results or
  filtered probes).

This separation ensures that:

- machine-readable payloads remain stable and composable,
- exit-code semantics can evolve independently,
- CI tooling can rely on standard process semantics.

______________________________________________________________________

## Output formats

TopMark exposes four `--output-format` values:

- human-oriented formats (not machine-stable):
  - `text`: default human-oriented text.
  - `markdown`: human-oriented Markdown.
- machine-readable formats:
  - `json`: a single JSON document per invocation.
  - `ndjson`: a newline-delimited JSON stream.

Notes:

- Machine-readable formats (`json`, `ndjson`) are independent of human-facing presentation controls.
- TEXT-only flags such as `-v` / `--verbose` and `-q` / `--quiet` do not affect machine-readable
  output.
- Markdown output is also independent from machine-readable formats and follows its own
  document-oriented contract.

This page describes the conventions shared across machine-readable formats.

For the canonical field-level schema reference, see [Machine-readable output](machine-output.md).

______________________________________________________________________

## Terminology

- **Format:** the encoding style, such as JSON or NDJSON.
- **Schema:** the structure of a payload or record.
- **Payload:** a concrete emitted JSON object or scalar value.
- **Record kind:** the stable NDJSON discriminator stored in `kind`.
- **Collection key:** a top-level JSON key containing a collection of domain objects.

______________________________________________________________________

## Machine-stable guarantees

The `json` and `ndjson` formats are designed for CI and programmatic use.

Stability guarantees:

- Machine-readable payloads contain no ANSI color codes.
- Payload shapes are JSON-safe (no Python-specific objects).
- New fields may be added over time (additive evolution).
- Existing fields are not removed or renamed without a breaking-change signal.
- Resolved file type identities are emitted using canonical qualified keys when available.

Consumers should:

- Treat machine-readable output as the authoritative machine-readable contract; do not rely on TEXT
  or Markdown output for programmatic use.

- Switch on `kind` (NDJSON) rather than relying on ordering.

- Tolerate unknown fields.

- Avoid string matching against formatted output.

- Prefer canonical identity fields such as `qualified_key`, `file_type_key`, and `processor_key`
  over display-oriented names or user-supplied input spellings.

______________________________________________________________________

## File type identifiers in machine-readable output

Machine-readable formats use the same canonical identity model as the runtime registry and resolver.

Public inputs may use local identifiers such as `python` when unambiguous, or qualified identifiers
such as `topmark:python`. Machine-readable output emits resolved canonical identities when a file
type is known.

When a file type identity is present, payloads generally expose one or more of:

- `qualified_key`: canonical file type identity, for example `topmark:python`
- `namespace`: producer namespace, for example `topmark`
- `local_key`: local identifier within that namespace, for example `python`
- `file_type_key`: canonical file type key used by binding-oriented payloads

Consumers should prefer `qualified_key` or `file_type_key` for durable comparisons, joins, and cache
keys.

Configuration payloads emit normalized identifiers. This means `include_file_types`,
`exclude_file_types`, and `policy_by_type` keys may appear as `topmark:python` even if the user
supplied `python`.

See [Registry model](registry-model.md#qualified-vs-local-identifiers) for the full identity
contract.

______________________________________________________________________

## Meta block

All machine-readable output includes a `meta` object:

- `tool`: the tool name (always `"topmark"`)
- `version`: the TopMark package version (PEP 440)
- `platform`: short runtime identifier (e.g. `sys.platform`)
- `detail_level`: optional machine-facing projection level for some commands:
  - `"brief"` for default machine-readable output
  - `"long"` when `--long` / detailed projection is requested

Registry commands include `detail_level` in both JSON and NDJSON. Other command families may omit
this field.

In JSON, `meta` appears once at the top level.

In NDJSON, `meta` appears in **every record**.

Shared envelope keys and helpers for machine-readable output live under
\[`topmark.core.machine`\][topmark.core.machine]. Domain packages (for example
\[`topmark.config.machine`\][topmark.config.machine] and
\[`topmark.pipeline.machine`\][topmark.pipeline.machine]) define their own payload keys and NDJSON
record kinds in their respective `*.machine.schemas` modules.

Unlike human-facing verbosity, `detail_level` is part of the machine contract. Consumers should
prefer this field over inferring the projection from payload shape alone.

Note:

- `detail_level` is distinct from TEXT verbosity (`-v`) and quiet mode (`--quiet`).
- It reflects an explicit machine-facing projection (`--long`), not presentation detail.

______________________________________________________________________

## NDJSON envelope contract

Each NDJSON line is a JSON object with a stable envelope:

```jsonc
{"kind": "<kind>", "meta": { ... }, "<kind>": { ... } }
```

- `kind` determines the payload container key; by default, the container key matches `kind`.
- `meta` appears in every record.
- the payload object is stored under a container key that matches `kind`.

Note:

- Some NDJSON record kinds carry scalar payloads in brief mode (for example registry reference kinds
  such as `unbound_filetype` and `unused_processor`, which emit qualified-key strings). In `--long`
  mode, these payloads expand to structured objects.

Registry-oriented scalar payloads use canonical qualified keys.

______________________________________________________________________

## JSON envelope conventions

Unlike NDJSON, JSON output is **domain-specific and aggregated**. Each command defines its own
stable top-level keys for collections.

Examples:

- Registry filetypes:

```jsonc
{ "meta": { ... }, "filetypes": [ ... ] }
```

- Registry processors:

```jsonc
{ "meta": { ... }, "processors": [ ... ] }
```

- Registry bindings:

```jsonc
{
  "meta": { ... },
  "bindings": [ ... ],
  "unbound_filetypes": [ ... ],
  "unused_processors": [ ... ]
}
```

- Processing commands, summary mode:

```jsonc
{
  "meta": { ... },
  "config": { ... },
  "config_diagnostics": { ... },
  "summary": [
    { "outcome": "unchanged", "reason": "up-to-date", "count": 30 },
    { "outcome": "skipped", "reason": "known file type, headers not supported", "count": 1 }
  ]
}
```

- [`config check`](../usage/commands/config/check.md):

```jsonc
{
  "meta": { ... },
  "config": { ... },
  "config_diagnostics": {
    "diagnostic_counts": { "info": 0, "warning": 1, "error": 0 },
    "diagnostics": [
      { "level": "warning", "message": "Duplicate included file types found in config" }
    ]
  },
  "config_check": {
    "ok": true,
    "strict": false,
    "diagnostic_counts": { "info": 0, "warning": 1, "error": 0 },
    "config_files": ["/repo/topmark.toml"]
  }
}
```

- `config dump --show-layers`:

```jsonc
{
  "meta": { ... },
  "config_provenance": {
    "layers": [
      {
        "origin": "<defaults>",
        "kind": "default",
        "precedence": 0,
        "toml": {
          "config": { "strict": false }
        }
      }
    ]
  },
  "config": { ... }
}
```

- [`version`](../usage/commands/version.md):

```jsonc
{
  "meta": { ... },
  "version_info": {
    "version": "1.0.0a2",
    "version_format": "pep440"
  }
}
```

- Resolution diagnostics ([`probe`](../usage/commands/probe.md)):

```jsonc
{
  "meta": { ... },
  "config": { ... },
  "config_diagnostics": { ... },
  "probes": [ ... ]
}
```

Consumers should **not assume a single generic container key** (such as `items` or a bare array),
but instead switch on documented domain-specific keys.

______________________________________________________________________

## Shared `kind` values

NDJSON record kinds are owned by the schema module of the corresponding machine-readable output
domain (for example
\[`topmark.config.machine.schemas.ConfigKind`\][topmark.config.machine.schemas.ConfigKind] or
\[`topmark.registry.machine.schemas.RegistryKind`\][topmark.registry.machine.schemas.RegistryKind]).
The list below reflects commonly emitted record kinds across commands.

Common NDJSON kinds include:

- `config`
- `config_provenance`
- `config_diagnostics` (counts-only in NDJSON prefix records)
- `diagnostic` (one diagnostic per record; see "Diagnostics" below)
- `result` (per-file result)
- `probe` (per-path resolution probe, including filtered explicit inputs)
- `summary` (one aggregated `(outcome, reason)` summary entry)
- `version`
- registry-specific kinds:
  - `filetype`
  - `processor`
  - `binding`
  - `unbound_filetype`
  - `unused_processor`

Individual commands may emit subsets of these kinds.

______________________________________________________________________

## Diagnostics

TopMark uses internal \[`Diagnostic`\][topmark.diagnostic.model.Diagnostic] objects to represent
warnings and errors. For machine-readable output:

Diagnostics emitted in machine-readable output represent the flattened compatibility view derived
from staged config-validation logs. Internally, these diagnostics may originate from TOML-source,
merged-config, or runtime-applicability validation.

For 1.0, this flattened compatibility form is the stable machine-readable contract for config/TOML
validation diagnostics. Machine-readable output does **not** serialize stage-local validation
structure; the emitted diagnostic entry shape remains `{level, message}`.

Diagnostics may include warnings for unknown, malformed, or ambiguous file type identifiers detected
during configuration sanitation and runtime applicability checks.

- **JSON** uses stable `{level, message}` entries within domain payloads (for example
  `config_diagnostics.diagnostics`).
- **NDJSON** emits one `diagnostic` record per diagnostic, with a `domain` field identifying the
  originating domain (for example `"config"`, using values from
  \[`topmark.core.machine.schemas.MachineDomain`\][topmark.core.machine.schemas.MachineDomain]).

The JSON-friendly schema helpers and keys for diagnostics are defined under
\[`topmark.diagnostic.machine.schemas`\][topmark.diagnostic.machine.schemas], including
\[`DiagnosticKey`\][topmark.diagnostic.machine.schemas.DiagnosticKey] and
\[`DiagnosticKind`\][topmark.diagnostic.machine.schemas.DiagnosticKind].

______________________________________________________________________

## Processing commands

[`topmark check`](../usage/commands/check.md) and [`topmark strip`](../usage/commands/strip.md)
share conventions:

- JSON emits: `meta`, `config`, `config_diagnostics`, plus either:
  - `results` (detail mode), or
  - `summary` (summary mode)
- NDJSON emits a stable prefix:
  - `config`
  - `config_diagnostics` (counts-only)
  - zero or more `diagnostic` records (config diagnostics, domain=`"config"` via
    \[`MachineDomain`\][topmark.core.machine.schemas.MachineDomain])
  - then either per-file `result` records (detail mode) or per-outcome **reason-preserving**
    `summary` records (summary mode)

These diagnostics correspond to the flattened compatibility view derived from staged validation
logs.

Machine-readable output for processing commands is unaffected by TEXT verbosity or quiet mode; these
flags only influence human TEXT output.

Per-file result payloads report the resolved file type using the canonical key when resolution
succeeds. Consumers should not expect the original local-or-qualified input spelling to be preserved
in result payloads.

In **summary mode**, TopMark aggregates results by the pair `(outcome, reason)` rather than
collapsing all reasons under a single outcome bucket.

Each summary entry therefore contains:

- `outcome` — the pipeline outcome (for example `inserted`, `replaced`, `unchanged`)
- `reason` — the short lowercase reason string used for bucketing
- `count` — the number of files that produced this `(outcome, reason)` pair

This guarantees that machine consumers can distinguish between different causes that lead to the
same high-level outcome.

Example NDJSON summary records:

```jsonc
{"kind":"summary","meta":{...},"summary":{"outcome":"unchanged","reason":"up-to-date","count":30}}
{"kind":"summary","meta":{...},"summary":{"outcome":"skipped","reason":"known file type, headers not supported","count":1}}
```

### Summary payload shape

In the pipeline machine schema, this row shape is represented by `OutcomeSummaryRow`.

In both JSON and NDJSON machine-readable formats, summary entries follow the same logical structure.

Conceptually the summary is a flat list of rows:

```json
{
  "outcome": "unchanged",
  "reason": "empty-like file (policy)",
  "count": 12
}
```

Important properties of the summary model:

- The summary is **not nested by outcome**.
- Each row represents one `(outcome, reason)` bucket.
- Ordering is deterministic:
  - outcomes follow the internal \[`Outcome`\][topmark.api.types.Outcome] ordering
  - reasons are sorted alphabetically within each outcome.

This design keeps JSON and NDJSON schemas consistent and avoids ambiguous aggregation when different
reasons share the same outcome.

______________________________________________________________________

## Resolution diagnostics ([`probe`](../usage/commands/probe.md))

[`topmark probe`](../usage/commands/probe.md) exposes file-type and processor resolution as a
machine-readable diagnostic surface.

- JSON emits: `meta`, `config`, `config_diagnostics`, `probes`
- NDJSON emits a stable prefix:
  - `config`
  - `config_diagnostics` (counts-only)
  - zero or more `diagnostic` records (domain=`"config"`)
  - then one `probe` record per probe result

Unlike processing commands, [`probe`](../usage/commands/probe.md):

- does not emit `results` or `summary`
- does not compute header changes or plans
- is purely diagnostic and resolution-focused

Machine-readable output for [`probe`](../usage/commands/probe.md) is unaffected by TEXT verbosity or
quiet mode.

Probe output reports canonical file type identities after identifier normalization and file-type
filtering.

Filtered probe results use machine-friendly reasons to explain why a path did not reach probing.
These include:

- `excluded_by_path_filter` — excluded by path-based include/exclude rules
- `excluded_by_file_type_filter` — excluded by file-type include/exclude rules after identifier
  normalization to canonical qualified keys
- `excluded_by_discovery_filter` — excluded before probing, but exact category not identified

Refer to the machine schema reference for the per-path probe payload:

- [Machine-readable output](machine-output.md)

Note:

- Explicit missing literal inputs are surfaced via the CLI exit code (`FILE_NOT_FOUND (66)`), not as
  a distinct probe status.
- In mixed-input runs, probe payloads may still include filtered or unsupported entries, but
  exit-code precedence is resolved outside the payload.

______________________________________________________________________

## Config commands

Config commands are file-agnostic and emit config-centric payloads:

- [`config dump`](../usage/commands/config/dump.md): resolved runtime configuration snapshot (no
  diagnostics); when `--show-layers` is used in machine-readable formats, it also emits layered
  `config_provenance` before the final flattened configuration snapshot
- [`config defaults`](../usage/commands/config/defaults.md): built-in default TopMark TOML snapshot
  (no diagnostics)
- [`config init`](../usage/commands/config/init.md): bundled starter template snapshot in
  machine-readable formats (no diagnostics)
- [`config check`](../usage/commands/config/check.md): resolved runtime configuration snapshot plus
  diagnostics and a config-check status payload

In human-facing formats, [`config defaults`](../usage/commands/config/defaults.md) and
[`config init`](../usage/commands/config/init.md) differ noticeably:
[`config defaults`](../usage/commands/config/defaults.md) renders a cleaned TOML view of the
built-in defaults, while [`config init`](../usage/commands/config/init.md) renders the bundled
example TopMark TOML resource with extensive comments. In machine-readable formats, both emit the
same underlying default configuration snapshot shape.

For [`config check`](../usage/commands/config/check.md), the machine-readable payload uses `strict`
to report the effective config-validation strictness after applying CLI override precedence over
resolved TOML strictness. This strictness is evaluated across staged config-loading validation
(TOML-source, merged-config, and runtime-applicability diagnostics), while machine-readable output
exposes the flattened compatibility diagnostics view.

Resolved runtime configuration snapshots emit normalized file type identifiers. In particular,
`files.include_file_types`, `files.exclude_file_types`, and `policy_by_type` use canonical qualified
keys such as `topmark:python` after configuration normalization.

Example [`config check`](../usage/commands/config/check.md) NDJSON prefix:

```jsonc
{"kind":"config","meta":{...},"config":{...}}
{"kind":"config_diagnostics","meta":{...},"config_diagnostics":{
  "diagnostic_counts":{"info":0,"warning":1,"error":0}
}}
{"kind":"diagnostic","meta":{...},"diagnostic":{
  "domain":"config",
  "level":"warning",
  "message":"Duplicate included file types found in config"
}}
{"kind":"config_check","meta":{...},"config_check":{
  "ok":true,
  "strict":false,
  "diagnostic_counts":{"info":0,"warning":1,"error":0},
  "config_files":["/repo/topmark.toml"]
}}
```

For 1.0, this boundary is intentional: staged validation remains an internal representation, while
machine-readable output exposes the flattened compatibility diagnostics contract.

For [`config dump --show-layers`](../usage/commands/config/dump.md), machine-readable output
preserves the same logical ordering as the human-facing layered export:

- JSON includes `config_provenance` before `config` in the top-level envelope.
- NDJSON emits a `config_provenance` record first and a `config` record second.

The `config_provenance` payload is inspection-oriented. Each provenance layer preserves metadata
such as `origin`, `kind`, `precedence`, and optional `scope_root`, and exposes the corresponding
source-local TopMark TOML fragment under `toml`.

Config-specific payload keys and NDJSON kinds are defined in
\[`topmark.config.machine.schemas.ConfigKey`\][topmark.config.machine.schemas.ConfigKey] and
\[`topmark.config.machine.schemas.ConfigKind`\][topmark.config.machine.schemas.ConfigKind]. Shared
diagnostic keys used within config payloads are defined in
\[`topmark.diagnostic.machine.schemas`\][topmark.diagnostic.machine.schemas].

______________________________________________________________________

## Registry machine-readable output

Registry commands expose the effective composed runtime view.

Important identity fields:

- `qualified_key`: canonical file type or processor identity
- `file_type_key`: canonical file type key used by bindings
- `processor_key`: canonical processor key used by bindings
- `namespace`: producer namespace
- `local_key`: local identifier within a namespace

For binding payloads, `file_type_key` references a file type `qualified_key`, and `processor_key`
references a processor `qualified_key`.

See:

- [`topmark registry filetypes`](../usage/commands/registry/filetypes.md)
- [`topmark registry processors`](../usage/commands/registry/processors.md)
- [`topmark registry bindings`](../usage/commands/registry/bindings.md)
- [Registry model](registry-model.md)

Refer to each command’s documentation for its emitted keys and shapes. Registry commands are also
documented in the schema reference and include the separate
[`registry bindings`](../usage/commands/registry/bindings.md) machine-readable format.
