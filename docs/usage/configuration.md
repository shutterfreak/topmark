<!--
topmark:header:start

  project      : TopMark
  file         : configuration.md
  file_relpath : docs/usage/configuration.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# User configuration

TopMark runtime configuration may be provided through:

- `topmark.toml`
- `pyproject.toml` (`[tool.topmark]`)
- CLI overrides
- API overlays

Configuration is resolved through layered discovery, normalization, and precedence rules.
Higher-precedence layers override lower-precedence layers.

Project-chain discovery starts from a discovery anchor: the first input path, or the current working
directory when no input path is provided. That anchor is resolved before TopMark walks upward
looking for project configuration files, so symlinked working directories or input anchors follow
their filesystem targets for discovery.

For file-backed configuration sources, TopMark determines configuration-source identity using the
resolved configuration-file target. Symlink spellings are not preserved for precedence, scope, or
applicability evaluation.

Configuration-source identity is distinct from processing-target identity. The hard-link processing
policy used by runtime file-processing commands such as `check`, `strip`, and `probe` does not
affect configuration discovery, configuration precedence, scope evaluation, or applicability
evaluation.

{% include-markdown "\_snippets/terminology.md" %}

______________________________________________________________________

## Configuration-source identity

TopMark evaluates file-backed configuration sources using configuration-source identity rather than
invocation spelling.

Examples such as:

```text
real/topmark.toml
link-to-topmark.toml
```

may refer to the same configuration source.

Configuration precedence, scope evaluation, layered configuration export, and machine-readable
configuration provenance operate on the resolved configuration-file target. If multiple discovered
or explicit entries resolve to the same configuration-source identity, TopMark keeps the
highest-precedence occurrence and reports that source once in layered provenance. This prevents one
physical configuration file from contributing multiple layers through different path spellings or
discovery paths.

> [!NOTE]
>
> This behavior mirrors the processing-path contract used for runtime file processing, but the two
> identity systems are evaluated independently. Configuration-source identity governs configuration
> loading and precedence, while processing-target identity governs runtime file-processing behavior
> such as path selection and hard-link policy enforcement.

______________________________________________________________________

## CLI, configuration, and API value spelling

Configuration keys use consistent naming across the CLI, API, and TOML configuration surfaces. Some
options accept predefined multi-word values such as `add_only` or `whitespace_empty`.

TopMark uses different spelling conventions depending on the interface: finite-choice CLI values
require exact lowercase spelling and *hyphenated forms* for multiword values, while TOML
configuration, Python API values, and machine-readable output use *canonical underscore forms*.

{% include-markdown "\_snippets/option-spelling.md" %}

Unless otherwise noted, configuration and policy values shown throughout this page use the canonical
TOML/API/machine-readable underscore form.

______________________________________________________________________

## Multiline field values

Custom `[fields]` values may use TOML multiline strings. TopMark normalizes semantic CRLF and CR to
LF, then renders each logical line as an explicit literal continuation record:

```toml
[fields]
notice = """
First literal line.
Second literal line."""

[header]
fields = ["notice"]
```

The closing delimiter follows the final content on the same line so this example has no semantic
terminal newline. An empty final TOML line is meaningful and renders as a bare `|` record. See
[Multiline header field serialization](../dev/multiline-header-fields.md) for empty-line,
boundary-whitespace, validation, and canonicalization details.

### Deterministic field wrapping

Selected single-line values can be wrapped into canonical folded continuation records:

```toml
[formatting]
max_header_line_length = 100
wrap_fields = ["notice", "copyright"]
```

Wrapping is disabled unless both a positive width and an allowlisted field are present. The width
counts Unicode code points across the complete physical field line, including comment syntax and
indentation but excluding the line terminator. It is a soft target: TopMark wraps only at lossless
U+0020 SPACE boundaries and never hard-splits URLs, paths, identifiers, or other unbreakable
content.

Folded `>` and `>=` records are TopMark-managed on-disk serialization. Their physical boundaries are
presentation-only and are canonically reflowed from the semantic value and effective configuration.
Literal `|`, bare `|`, and `|=` records continue to preserve semantic line breaks and are never
reflowed as folded text.

______________________________________________________________________

## File type identifiers

{% include-markdown "\_snippets/file-type-identifiers.md" %}

See [file-type filtering](filtering.md#file-type-filtering) for the full identifier contract.

File type identifiers participate in stable runtime behavior such as:

- `include_file_types`
- `exclude_file_types`
- `policy_by_type`
- CLI file-type filters
- API file-type filters and policy overlays

______________________________________________________________________

## File-type filters

File-type filters allow restricting runtime processing to a selected subset of file types.

Example using local identifiers:

```toml
[files]
include_file_types = ["python", "markdown"]
```

Equivalent configuration using canonical qualified keys:

```toml
[files]
include_file_types = ["topmark:python", "topmark:markdown"]
```

Exclude filters work the same way:

```toml
[files]
exclude_file_types = ["topmark:yaml"]
```

> [NOTE] Internally, TopMark normalizes configured file type identifiers to canonical qualified
> identities before filtering, runtime resolution, policy evaluation, diagnostics, and registry
> lookup.

______________________________________________________________________

## Per-file-type policy

`policy_by_type` allows file-type-specific policy overrides for selected file types.

Example using a local identifier:

```toml
[policy_by_type.python]
header_mutation_mode = "update_only"
```

Equivalent configuration using canonical qualified keys:

```toml
[policy_by_type."topmark:python"]
header_mutation_mode = "update_only"
```

Both forms are accepted when the local identifier resolves unambiguously.

Internally, TopMark stores and resolves per-file-type policies using canonical qualified file type
identities.

### Example: Different policy per file type

```toml
[policy]
header_mutation_mode = "add_only"
bom_before_shebang = "reject"
mixed_line_endings = "preserve"

[policy_by_type."topmark:python"]
header_mutation_mode = "update_only"
bom_before_shebang = "remove_bom"
mixed_line_endings = "reject"

[policy_by_type.markdown]
allow_content_probe = false
```

In this example:

- the global default header mutation policy uses `add_only` and mixed line endings are preserved
  when present
- Python files override this with `update_only`
- Python files also remediate a BOM immediately before a shebang
- Python files also reject files with mixed line endings
- Markdown files disable runtime content probing

______________________________________________________________________

## Ambiguous identifiers

When more than one registered file type shares the same local identifier, TopMark requires the
canonical qualified form.

For example, if both:

- `topmark:python`
- `acme:python`

are registered, then:

```toml
include_file_types = ["python"]
```

is ambiguous.

Use:

```toml
include_file_types = ["topmark:python"]
```

instead.

Ambiguous identifiers are ignored diagnostically during configuration normalization and staged
configuration-loading validation.

______________________________________________________________________

## Unknown and malformed identifiers

Unknown identifiers are ignored diagnostically during configuration normalization and staged
configuration-loading validation.

Malformed qualified identifiers are also ignored diagnostically during configuration normalization
and staged configuration-loading validation.

Examples of malformed identifiers:

```text
:python
topmark:
topmark:python:extra
```

______________________________________________________________________

## CLI and API parity

CLI options, TOML configuration, API overlays, and runtime policy evaluation all share the same file
type identity semantics.

Examples:

```bash
topmark check --include-file-types python .
```

```bash
topmark check --include-file-types topmark:python .
```

```python
api.check(
    paths=[repo],
    include_file_types=["topmark:python"],
)
```

______________________________________________________________________

## Runtime configuration model

{% include-markdown "\_snippets/runtime-configuration-model.md" %}

Runtime evaluation consumes the effective configuration produced after workspace-root discovery,
precedence, normalization, and configuration-source identity resolution have completed.

For configuration files loaded through symlinks, the effective configuration is associated with the
resolved configuration target rather than the symlink spelling used to reach it.

Hard-link processing policy is not represented in the runtime configuration model because it is a
processing-target eligibility rule evaluated by runtime file-processing commands rather than a
configuration-layering concern.

______________________________________________________________________

## See also

- [Machine-readable output](machine-output.md#tomlprovenancepayload)
- [Filtering recipes and behavior](filtering.md)
- [Configuration overview](../configuration/index.md)
- [Configuration discovery, precedence, and policy](../configuration/discovery.md)
