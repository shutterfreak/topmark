<!--
topmark:header:start

  project      : TopMark
  file         : configuration.md
  file_relpath : docs/usage/configuration.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Configuration

TopMark configuration may be provided through:

- `topmark.toml`
- `pyproject.toml` (`[tool.topmark]`)
- CLI overrides
- API overlays

Configuration is resolved using layered discovery. Higher-precedence layers override lower layers.

______________________________________________________________________

## CLI, configuration, and API value spelling

Configuration keys use the same names across the CLI, API, and TOML configuration. Some options
accept predefined multi-word values such as `add_only` or `whitespace_empty`.

TopMark uses different spelling conventions depending on the interface: CLI examples prefer
*hyphenated forms* for readability, while TOML configuration, Python API values, and
machine-readable output use *canonical underscore forms*.

{% include-markdown "\_snippets/option-spelling.md" %}

Unless otherwise noted, configuration and policy values shown throughout this page use the canonical
TOML/API/machine-readable spelling.

______________________________________________________________________

## File type identifiers

{% include-markdown "\_snippets/file-type-identifiers.md" %}

File type identifiers are used by:

- `include_file_types`
- `exclude_file_types`
- `policy_by_type`
- CLI file-type filters
- API file-type filters and policy overlays

______________________________________________________________________

## File-type filters

File-type filters allow restricting processing to a selected subset of file types.

Example using local identifiers:

```toml
[files]
include_file_types = ["python", "markdown"]
```

Equivalent configuration using canonical qualified identifiers:

```toml
[files]
include_file_types = ["topmark:python", "topmark:markdown"]
```

Exclude filters work the same way:

```toml
[files]
exclude_file_types = ["topmark:yaml"]
```

Internally, TopMark normalizes all configured file type identifiers to canonical qualified keys.

______________________________________________________________________

## Per-file-type policy

`policy_by_type` allows overriding policy settings for selected file types.

Example using a local identifier:

```toml
[policy_by_type.python]
header_mutation_mode = "update_only"
```

Equivalent configuration using a canonical qualified identifier:

```toml
[policy_by_type."topmark:python"]
header_mutation_mode = "update_only"
```

Both forms are accepted when the local identifier is unambiguous.

Internally, TopMark stores and resolves per-type policies using canonical qualified file type
identifiers.

### Example: Different policy per file type

```toml
[policy]
header_mutation_mode = "add_only"

[policy_by_type."topmark:python"]
header_mutation_mode = "update_only"

[policy_by_type.markdown]
allow_content_probe = false
```

In this example:

- the global default policy uses `add_only`
- Python files override this with `update_only`
- Markdown files disable content probing

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

Ambiguous identifiers are ignored diagnostically during configuration sanitization and validation.

______________________________________________________________________

## Unknown and malformed identifiers

Unknown identifiers are ignored diagnostically.

Malformed qualified identifiers are also ignored diagnostically.

Examples of malformed identifiers:

```text
:python
topmark:
topmark:python:extra
```

______________________________________________________________________

## CLI and API parity

CLI options, TOML configuration, and API overlays all support the same file type identifier
semantics.

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

## See also

- [Filtering recipes and behavior](filtering.md)
- [Configuration reference](../configuration/index.md)
- [Configuration discovery and precedence](../configuration/discovery.md)
