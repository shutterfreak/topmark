<!--
topmark:header:start

  project      : TopMark
  file         : index.md
  file_relpath : docs/index.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark Documentation (%%TOPMARK_VERSION%%)

TopMark inspects and manages per-file headers (project/license/copyright) across codebases. It is
comment‑aware, file‑type‑aware, and **dry‑run by default** for safe CI usage.

TopMark provides consistent semantics across:

- CLI execution
- TOML configuration
- API overlays
- layered configuration discovery
- resolver and probe filtering
- pre-commit and CI integration

## Common workflows

| Goal                                  | Command                                                 | More info                                                                                                                                                                    |
| ------------------------------------- | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Check headers safely                  | `topmark check src/`                                    | [`topmark check`](usage/commands/check.md), [Shared options](usage/shared-options.md), [Exit codes](usage/exit-codes.md)                                                     |
| Apply header updates                  | `topmark check --apply src/`                            | [`topmark check`](usage/commands/check.md), [Policies](usage/policies.md)                                                                                                    |
| Remove TopMark headers                | `topmark strip src/`, then `topmark strip --apply src/` | [`topmark strip`](usage/commands/strip.md), [Header placement](usage/header-placement.md)                                                                                    |
| Understand file type resolution       | `topmark probe README.md`                               | [`topmark probe`](usage/commands/probe.md), [Filtering](usage/filtering.md), [Policies](usage/policies.md)                                                                   |
| Inspect effective configuration       | `topmark config dump --show-layers`                     | [`topmark config dump`](usage/commands/config/dump.md), [Configuration](usage/configuration.md), [Configuration discovery](configuration/discovery.md)                       |
| Generate a starter TOML configuration | `topmark config init > topmark.toml`                    | [`topmark config init`](usage/commands/config/init.md), [Configuration](usage/configuration.md), [Configuration discovery](configuration/discovery.md)                       |
| Inspect the built-in defaults         | `topmark config defaults`                               | [`topmark config defaults`](usage/commands/config/defaults.md), [Default TOML settings](configuration/generated/config-defaults.md), [Configuration](usage/configuration.md) |

## Quickstart

```bash
pip install topmark
# Check (dry-run)
topmark check --summary --config topmark.toml src/
# Apply changes
topmark check --apply src/
# Explain file-type / processor resolution
topmark probe README.md
# Process one file's content from STDIN
cat README.md | topmark check - --stdin-filename README.md
# Explain why a path was filtered by discovery rules
topmark probe __pycache__/example.cpython-312.pyc
```

### Public API quickstart

```python
from topmark import api

res1 = api.check(["src"], report="actionable")  # dry-run
res2 = api.check(["src"], apply=True)
res3 = api.check(
    ["src"],
    include_file_types=["topmark:python"],
)
```

```python
from topmark.registry.registry import Registry
for b in Registry.bindings():
    print(b.filetype.name, bool(b.processor))
```

## What it does

- Detects, inserts, and updates per‑file headers
- Honors shebangs, XML declarations, and native comment styles
- Preserves newline style (LF/CRLF/CR) and BOM
- Provides [`strip`](usage/commands/strip.md) to remove headers (also dry‑run by default)
- Works well in CI and with pre‑commit hooks
- Explains file-type and processor resolution via [`topmark probe`](usage/commands/probe.md),
  including why explicit inputs may be filtered before probing
- Inspects **layered configuration provenance** via `topmark config dump --show-layers`
- Validates whole-source TOML configuration before layered config merging
- Normalizes file type identifiers to canonical qualified keys such as `topmark:python`
- Supports local identifiers such as `python` when unambiguous

## Example headers

Here’s how TopMark headers appear in different file types (truncated for brevity):

```bash
#!/bin/bash

# topmark:header:start
#
#   project   : TopMark
#   file      : script.sh
#   license   : MIT
#   copyright : (c) 2025 Olivier Biot

# topmark:header:end
...
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!--
topmark:header:start

  project   : TopMark
  file      : config.xml
  license   : MIT
  copyright : (c) 2025 Olivier Biot

topmark:header:end
-->
...
```

## Commands

`topmark [COMMAND] ([SUBCOMMAND]) [OPTIONS] [PATHS]...`

For a structured command overview, common workflows, shared options, and command applicability
semantics, see [Command overview](usage/cli.md).

Core commands: [`check`](usage/commands/check.md), [`strip`](usage/commands/strip.md),
[`probe`](usage/commands/probe.md), [`config`](usage/commands/config.md),
[`registry`](usage/commands/registry.md), [`version`](usage/commands/version.md).

Informational commands ([`version`](usage/commands/version.md),
[`config defaults`](usage/commands/config/defaults.md),
[`config init`](usage/commands/config/init.md), and [`registry`](usage/commands/registry.md)
commands) are file-agnostic: they do not accept positional paths or STDIN input modes and reject
them as CLI usage errors.

### Exit codes (overview)

TopMark uses a small, stable set of exit codes suitable for CI and scripting:

- `SUCCESS (0)` — success (no changes needed or changes applied)
- `WOULD_CHANGE (2)` — dry-run indicates changes would be made ([`check`](usage/commands/check.md),
  [`strip`](usage/commands/strip.md))
- `FAILURE (1)` — validation failed ([`config check`](usage/commands/config/check.md))
- `USAGE_ERROR (64)` — CLI usage error (invalid options, unsupported STDIN modes, or positional
  paths on file-agnostic commands)

Additional codes are used for configuration errors and runtime conditions (for example
`CONFIG_ERROR (78)`, `FILE_NOT_FOUND (66)`). These apply after CLI usage has been accepted.

See:

- [`Exit codes`](usage/exit-codes.md)
- [`check`](usage/commands/check.md)
- [`strip`](usage/commands/strip.md)

The [`probe`](usage/commands/probe.md) command also reports explicitly requested paths that were
filtered out during discovery.

File-type filtering accepts either local identifiers such as `python` or canonical qualified
identifiers such as `topmark:python`.

The [`config`](usage/commands/config.md) command has the following subcommands:
[`config check`](usage/commands/config/check.md),
[`config defaults`](usage/commands/config/defaults.md),
[`config dump`](usage/commands/config/dump.md), [`config init`](usage/commands/config/init.md).

The [`registry`](usage/commands/registry.md) command has the following subcommands:
[`registry filetypes`](usage/commands/registry/filetypes.md),
[`registry processors`](usage/commands/registry/processors.md),
[`registry bindings`](usage/commands/registry/bindings.md).

{% include-markdown "\_snippets/output-contract.md" %}

Use [`config dump --show-layers`](usage/commands/config/dump.md) to inspect how configuration is
built from individual sources and how precedence is applied.

TopMark supports two STDIN modes:

- **List mode**: read newline-delimited paths or patterns via `--files-from -` (or
  `--include-from -` / `--exclude-from -`)
- **Content mode**: process one file’s content by passing `-` as the sole PATH together with
  `--stdin-filename NAME`

{% include-markdown "\_snippets/no-stdin-option.md" %}

## Header placement (short version)

- **Pound‑style** (Python, Shell, Makefile, YAML, TOML, …): after shebang and optional encoding
  line; else at top. Ensure a single blank line separation and a trailing blank line when needed.
- **XML/HTML‑style**: after XML declaration/DOCTYPE when present; otherwise at top. Uses native
  comment wrapper.

> For full rules, supported file types, JSON vs JSONC handling, and resolver specifics, see the
> sections in the repository README.
>
> [`topmark probe`](usage/commands/probe.md) can be used to understand how file types are resolved
> and why certain paths are ignored.

## Configuration (example)

```toml
[config]
root = true

[fields]
project = "TopMark"
license = "MIT"

[header]
fields = ["file", "file_relpath", "project", "license"]
relative_to = "."

[formatting]
align_fields = true

[files]
include_file_types = ["python", "markdown", "env"]
exclude_file_types = ["html"]
```

TopMark also accepts local identifiers such as `python` when unambiguous, but internally normalizes
identifiers to canonical qualified keys such as `topmark:python`. The same example with local keys:

```toml
[files]
include_file_types = ["python", "markdown", "env"]
exclude_file_types = ["html"]
```

In `pyproject.toml`, the same settings live under `[tool.topmark]`, with source-local options such
as `root` and `strict` under `[tool.topmark.config]`.

Source-local options under `[config]` / `[tool.topmark.config]` do not participate in layered config
merging. For example, `strict` affects configuration validation behaviour rather than becoming a
normal layered `Config` field.

{% include-markdown "\_snippets/config-strictness.md" %}

{% include-markdown "\_snippets/config-validation-contract.md" %}

At the TOML layer, malformed known sections are handled as warning-and-ignore cases, while missing
known sections are emitted as INFO diagnostics. This lets callers distinguish absent sections from
malformed-present sections before staged config-validation semantics are applied. These TOML-source
diagnostics are then evaluated together with merged-config and runtime-applicability diagnostics
during staged config-loading/preflight validation.

## File type identifiers

TopMark accepts file type identifiers in either local form, such as `python`, or qualified form,
such as `topmark:python`.

Internally, identifiers normalize to canonical qualified keys such as `topmark:python`.

Local identifiers are accepted only when unambiguous.

See:

- [Configuration](usage/configuration.md)
- [Filtering](usage/filtering.md)
- [Policies](usage/policies.md)
- [CLI overview](usage/cli.md)

### Inspecting configuration

Use [`topmark config dump`](usage/commands/config/dump.md) to inspect the effective merged
configuration.

For deeper insight into how configuration is constructed, use:

```bash
topmark config dump --show-layers
```

This shows:

- the **layered provenance** (defaults → discovered config → `--config` → CLI)
- the final **flattened effective configuration**

Machine-readable formats (`--output-format json|ndjson`) also expose this provenance via the
`config_provenance` payload. The stored TOML fragments correspond to the source-local TOML view
after TOML-layer validation.

## Next steps

- **Install:** [Installation guide](install.md)
- **Usage:**
  - [Command overview](usage/cli.md)
  - [Configuration](usage/configuration.md)
  - [Filtering](usage/filtering.md)
  - [Shared options](usage/shared-options.md)
  - [Exit codes](usage/exit-codes.md)
  - **Commands:**
    - [`check`](usage/commands/check.md)
    - [`strip`](usage/commands/strip.md)
    - [`probe`](usage/commands/probe.md)
    - [`version`](usage/commands/version.md)
    - [`config` commands](usage/commands/config.md)
    - [`registry` commands](usage/commands/registry.md)
  - [Pre‑commit integration](usage/pre-commit.md)
- **CI/CD:** Release workflow ([ci/release-workflow.md](ci/release-workflow.md))
- **Policies:** Guide ([usage/policies.md](usage/policies.md))
- **Public API:** Reference ([api/public.md](api/public.md))
- **Internals:** Reference ([api/internals.md](api/internals.md))
- **Contributing:** [Guidelines](contributing.md)

______________________________________________________________________

Need the complete — canonical introduction? See the project README on GitHub.
