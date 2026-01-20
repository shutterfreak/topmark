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
res = api.check(["src"])          # dry-run
res2 = api.check(["src"], apply=True)
```

```python
from topmark.registry import Registry
for b in Registry.bindings():
    print(b.filetype.name, bool(b.processor))
```

## What it does

- Detects, inserts, and updates per‑file headers
- Honors shebangs, XML declarations, and native comment styles
- Preserves newline style (LF/CRLF/CR) and BOM
- Provides `strip` to remove headers (also dry‑run by default)
- Works well in CI and with pre‑commit hooks

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

`topmark [SUBCOMMAND] [OPTIONS] [PATHS]...`

Core subcommands: `check`, `strip`, `dump-config`, `show-defaults`, `init-config`, `filetypes`,
`version`.

Read lists from STDIN with `--files-from -` (or `--include-from -` / `--exclude-from -`). To process
a *single* file’s **content** from STDIN, pass `-` as the sole PATH and provide
`--stdin-filename NAME`.

## Header placement (short version)

- **Pound‑style** (Python, Shell, Makefile, YAML, TOML, …): after shebang and optional encoding
  line; else at top. Ensure a single blank line separation and a trailing blank line when needed.
- **XML/HTML‑style**: after XML declaration/DOCTYPE when present; otherwise at top. Uses native
  comment wrapper.

> For full rules, supported file types, JSON vs JSONC handling, and resolver specifics, see the
> sections in the repository README.

## Configuration (example)

```toml
[fields]
project = "TopMark"
license = "MIT"

[header]
fields = ["file", "file_relpath", "project", "license"]

[formatting]
align_fields = true

[files]
include_file_types = ["python", "markdown", "env"]
exclude_file_types = ["html"]
relative_to = "."
```

## Next steps

- **Install:** [Installation guide](install.md)
- **Usage:** Pre‑commit integration ([usage/pre-commit.md](usage/pre-commit.md))
- **CI/CD:** Release workflow ([ci/release-workflow.md](ci/release-workflow.md))
- **Public API:** Reference ([api/public.md](api/public.md))
- **Internals:** Reference ([api/internals.md](api/internals.md))
- **Contributing:** [Guidelines](contributing.md)

______________________________________________________________________

Need the complete, canonical introduction? See the project README on GitHub.
