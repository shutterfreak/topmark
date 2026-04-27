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

## Quickstart

```bash
pip install topmark
# Check (dry-run)
topmark check --summary --config topmark.toml src/
# Apply changes
topmark check --apply src/
```

### Public API quickstart

```python
from topmark import api

res = api.check(["src"], report="actionable")  # dry-run
res2 = api.check(["src"], apply=True)
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
- Provides `strip` to remove headers (also dry‑run by default)
- Works well in CI and with pre‑commit hooks
- Inspects **layered configuration provenance** via `topmark config dump --show-layers`
- Validates whole-source TOML configuration before layered config merging

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

Core commands: `check`, `strip`, `config`, `registry`, `version`.

The `config` command has the following subcommands: `check`, `defaults`, `dump`, `init`.

{% include-markdown "\_snippets/output-contract.md" %}

Use `config dump --show-layers` to inspect how configuration is built from individual sources and
how precedence is applied.

TopMark supports two STDIN modes:

- **List mode**: read newline-delimited paths or patterns via `--files-from -` (or
  `--include-from -` / `--exclude-from -`)
- **Content mode**: process one file’s content by passing `-` as the sole PATH together with
  `--stdin-filename NAME`

## Header placement (short version)

- **Pound‑style** (Python, Shell, Makefile, YAML, TOML, …): after shebang and optional encoding
  line; else at top. Ensure a single blank line separation and a trailing blank line when needed.
- **XML/HTML‑style**: after XML declaration/DOCTYPE when present; otherwise at top. Uses native
  comment wrapper.

> For full rules, supported file types, JSON vs JSONC handling, and resolver specifics, see the
> sections in the repository README.

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

In `pyproject.toml`, the same settings live under `[tool.topmark]`, with source-local options such
as `root` and `strict_config_checking` under `[tool.topmark.config]`.

Source-local options under `[config]` / `[tool.topmark.config]` do not participate in layered config
merging. For example, `strict_config_checking` affects configuration validation behaviour rather
than becoming a normal layered `Config` field.

{% include-markdown "\_snippets/config-validation-contract.md" %}

At the TOML layer, malformed known sections are handled as warning-and-ignore cases, while missing
known sections are emitted as INFO diagnostics. This lets callers distinguish absent sections from
malformed-present sections before staged config-validation semantics are applied. These TOML-source
diagnostics are then evaluated together with merged-config and runtime-applicability diagnostics
during staged config-loading/preflight validation.

### Inspecting configuration

Use `topmark config dump` to inspect the effective merged configuration.

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
- **Usage:** Pre‑commit integration ([usage/pre-commit.md](usage/pre-commit.md))
- **CI/CD:** Release workflow ([ci/release-workflow.md](ci/release-workflow.md))
- **Policies:** Guide ([usage/policies.md](usage/policies.md))
- **Public API:** Reference ([api/public.md](api/public.md))
- **Internals:** Reference ([api/internals.md](api/internals.md))
- **Contributing:** [Guidelines](contributing.md)

______________________________________________________________________

Need the complete, canonical introduction? See the project README on GitHub.
