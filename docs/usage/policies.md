<!--
topmark:header:start

  project      : TopMark
  file         : policies.md
  file_relpath : docs/usage/policies.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark policy guide

Policies control:

- whether headers may be inserted or updated
- how empty files are classified
- whether file-content probing is allowed
- how runtime-resolution behavior interacts with safety gates
- how file-type-specific runtime policy overrides interact with global policy

See also:

- [Configuration](configuration.md)
- [Filtering](filtering.md)
- [CLI overview](cli.md)
- [Shared options](shared-options.md)

TopMark policies control how the runtime pipeline detects file types, classifies empty files,
evaluates runtime safety gates, and determines whether headers may be inserted or updated.

Policy settings are part of the layered runtime configuration
(\[`FrozenConfig`\][topmark.config.model.FrozenConfig]) and are merged according to workspace-root
discovery, layered discovery, normalization, precedence, and runtime overlay rules. See:

- [`Configuration overview`](../configuration/index.md)
- [`Discovery & Precedence`](../configuration/discovery.md)

Policy semantics behave consistently across:

- discovered config files (`topmark.toml` or `[tool.topmark]` in `pyproject.toml`)
- TOML configuration overlays
- command-specific CLI options
- API overlays
- effective runtime policy evaluation and runtime resolution

Runtime policy evaluation operates on selected processing paths after filesystem-identity evaluation
and processing-path selection have completed. Filesystem-identity normalization resolves equivalent
path spellings, while processing-target eligibility checks such as hard-link policy are evaluated
separately from policy resolution.

Policy values shown here are part of the public configuration surface.

> [!NOTE]
>
> Internal runtime helper types such as
> \[`PolicyOverrides`\][topmark.config.overrides.PolicyOverrides] and
> \[`ConfigOverrides`\][topmark.config.overrides.ConfigOverrides] are not part of the user-facing
> CLI or Python API contract. Public callers should use plain mapping-based inputs via `config=...`,
> `policy=...`, and `policy_by_type=...` when using `topmark.api`.

In `topmark.toml`, policy is defined under `[policy]` and `[policy_by_type.<file_type>]`. In
`pyproject.toml`, the same settings live under `[tool.topmark.policy]` and
`[tool.topmark.policy_by_type.<file_type>]`.

For canonical file-type identifier semantics, see
[Configuration discovery, precedence, and policy](configuration.md#file-type-identifiers).

During staged configuration-loading validation, TopMark first validates each whole-source TOML
fragment (unknown sections, unknown keys, malformed section shapes, etc.). Only validated layered
configuration fragments contribute to runtime policy resolution.

Command-line policy options override resolved config for the current run only.

Project-chain discovery uses the resolved discovery anchor before policy layering begins. This keeps
workspace-root discovery separate from configuration-source identity and from runtime
processing-target identity.

______________________________________________________________________

## Policy layers

TopMark resolves policy in this order:

1. defaults
1. discovered config files
1. explicit config overlays
1. CLI or API overrides

Discovered config files are selected by project-chain discovery from the resolved discovery anchor.
Only after those sources have been found does configuration-source identity determine how
file-backed configuration sources participate in precedence, applicability, and layered provenance.

For file-backed configuration sources, policy layering uses configuration-source identity based on
the resolved configuration-file target. If a policy-bearing configuration file is loaded through a
symlink, precedence, applicability, and layered provenance are evaluated using the resolved
configuration target rather than the symlink spelling.

Configuration-source identity is distinct from workspace-root discovery and from processing-target
identity. The hard-link processing policy used by filesystem-processing commands such as `check`,
`strip`, and `probe` does not affect project-chain discovery, policy layering, configuration
precedence, applicability evaluation, or layered policy provenance.

These runtime policy layers are constructed after staged TOML-layer validation. Source-local TOML
sections (e.g. `[config]`) do not participate in runtime policy layering.

Per-file-type policy in `policy_by_type` is evaluated on top of the global `policy` section.

______________________________________________________________________

## CLI, configuration, and API value spelling

Policy configuration keys use the same names across the CLI, API, and TOML configuration. Some
policy options accept predefined multi-word values such as `add_only` or `whitespace_empty`.

TopMark uses different spelling conventions depending on the interface: CLI examples prefer
*hyphenated forms* for readability, while TOML configuration, Python API values, and
machine-readable output use canonical underscore forms.

{% include-markdown "\_snippets/option-spelling.md" %}

Unless otherwise noted, policy values shown throughout this page use the canonical
TOML/API/machine-readable underscore form.

______________________________________________________________________

## Global policy keys

### `header_mutation_mode`

Controls mutation behavior for [`topmark check`](commands/check.md).

Allowed TOML/API values:

- `all`: insert missing headers and update existing headers
- `add_only`: insert missing headers only; existing headers are not updated
- `update_only`: update existing headers only; missing headers are not inserted

This policy affects dry-run reporting, `--apply` behavior, API result views, and semantic runtime
outcome bucketing. It applies only to [`check`](commands/check.md); [`strip`](commands/strip.md) and
[`probe`](commands/probe.md) reject generated-header mutation controls.

Runtime safety gates still take precedence. Malformed headers, unreadable files, unsupported files,
blocked filesystem states, and other non-mutable runtime conditions are not made mutable by
`header_mutation_mode`.

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

This policy affects dry-run reporting, `--apply` behavior, API result views, and semantic runtime
outcome bucketing.

This setting is evaluated together with `allow_header_in_empty_files`:

- If `allow_header_in_empty_files = false` (default), files classified as empty for insertion are
  treated as unchanged and compliant by default.
- If `allow_header_in_empty_files = true`, files classified as empty for insertion may receive
  generated headers, subject to normal runtime safety gates.

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

Runtime safety gates still take precedence. Unreadable files, unsupported files, malformed headers,
blocked filesystem states, and other non-mutable runtime conditions are not made mutable by
`empty_insert_mode`.

### `render_empty_header_when_no_fields`

Controls whether TopMark may insert an otherwise empty header when no header fields are configured.

```toml
[policy]
render_empty_header_when_no_fields = true
```

### `allow_reflow`

Controls whether TopMark may reflow content while inserting or updating a header.

This can reduce strict idempotent runtime rendering behavior in some cases.

```toml
[policy]
allow_reflow = true
```

### `allow_content_probe`

Controls whether runtime file-type detection may inspect file contents when needed.

This policy applies to both [`check`](commands/check.md) and [`strip`](commands/strip.md).

```toml
[policy]
allow_content_probe = false
```

______________________________________________________________________

## Line-ending handling (not a policy)

TopMark's line-ending behavior is fixed for 1.x releases and is not configurable through policy.

- Only LF (`\n`), CRLF (`\r\n`), and CR (`\r`) are recognized as physical line-ending styles.
- These styles are preserved across rendering, planning, patching, and writing.
- Files with mixed recognized newline styles are skipped by the mixed-line-ending guard.

Non-standard Unicode separators such as NEL (`U+0085`), Line Separator (`U+2028`), and Paragraph
Separator (`U+2029`) are treated as ordinary content characters. They are not considered line
endings and do not affect newline detection or mixed-newline diagnostics.

Some file-type-specific checks (notably XML) may conservatively skip mutation when such characters
appear near insertion boundaries due to idempotence concerns. This is a localized safety behavior,
not an extension of newline support.

______________________________________________________________________

## Per-file-type policy

{% include-markdown "\_snippets/file-type-identifiers.md" %}

See [file-type filtering](filtering.md#file-type-filtering) for the full identifier contract.

Use `policy_by_type.<file_type_id>` to override policy for one file type while inheriting
unspecified values from the global `policy` section.

In `pyproject.toml`, this section is written as `[tool.topmark.policy_by_type.<file_type>]`.

Both local identifiers:

```toml
[policy_by_type.python]
```

and canonical qualified identifiers:

```toml
[policy_by_type."topmark:python"]
```

are supported when the local identifier is unambiguous.

Internally, TopMark resolves per-file-type runtime policy using canonical qualified file type
identities.

> [!NOTE] **File-type identity and filesystem identity**
>
> File-type identity and filesystem identity are separate concepts. File-type policy resolution
> operates on the selected processing target after filesystem-identity evaluation has completed.
> Filesystem-identity normalization resolves equivalent path spellings before policy resolution,
> while processing-target eligibility checks such as hard-link policy are evaluated separately from
> policy resolution.

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

Equivalent canonical form:

```toml
[policy_by_type."topmark:python"]
header_mutation_mode = "update_only"
allow_header_in_empty_files = true
```

______________________________________________________________________

## Ambiguous, unknown, and malformed identifiers

Per-file-type runtime policy identifiers follow the same rules as filtering and runtime resolution.

Ambiguous local identifiers require the canonical qualified form.

Examples:

```text
python                # accepted when unambiguous
topmark:python        # canonical qualified form
```

Malformed identifiers are ignored diagnostically during configuration normalization and staged
configuration-loading validation.

Examples:

```text
:python
topmark:
topmark:python:extra
```

______________________________________________________________________

## Policy options by command

### [`topmark check`](commands/check.md)

[`check`](commands/check.md) supports both check-only and shared policy options.

Check-only policy options:

- `--header-mutation-mode`
- `--allow-header-in-empty-files / --no-allow-header-in-empty-files`
- `--empty-insert-mode`
- `--render-empty-header-when-no-fields / --no-render-empty-header-when-no-fields`
- `--allow-reflow / --no-allow-reflow`

Shared policy options:

- `--allow-content-probe / --no-allow-content-probe`

### [`topmark strip`](commands/strip.md)

[`strip`](commands/strip.md) supports only shared runtime policy options:

- `--allow-content-probe / --no-allow-content-probe`

Header insertion/update policies, including `header_mutation_mode`, do not apply to
[`strip`](commands/strip.md) and are rejected when provided.

______________________________________________________________________

## Reporting vs policy

Reporting controls human-readable CLI rendering. Policy controls what the runtime pipeline is
allowed to do.

Reporting examples:

- `--report actionable`: show human-readable per-file entries that would change, changed, failed, or
  otherwise need attention
- `--report noncompliant`: include actionable files plus unsupported file types in human-readable
  per-file output

Policy example:

- `--header-mutation-mode add-only`: allow [`check`](commands/check.md) to insert missing headers
  but not update existing headers

These settings are independent and may be combined.

______________________________________________________________________

## Runtime policy model

Runtime policy evaluation consumes the effective configuration produced after workspace-root
discovery and configuration-source identity normalization have completed.

{% include-markdown "\_snippets/runtime-validation-model.md" %}

______________________________________________________________________

## Related pages

- [Configuration](configuration.md)
- [Filtering](filtering.md)
- [CLI overview](cli.md)
- [Shared options](shared-options.md)
- [Configuration discovery, precedence, and policy](../configuration/discovery.md)
- [Machine-readable output](machine-output.md)
- [Filesystem identity and processing paths](../dev/resolution.md#filesystem-identity-and-processing-paths)
