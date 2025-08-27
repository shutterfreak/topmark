<!--
topmark:header:start

  file         : index.md
  file_relpath : docs/index.md
  project      : TopMark
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark

TopMark inspects and manages per-file headers (project/license/copyright) across codebases. It is
comment‑aware, file‑type‑aware, and **dry‑run by default** for safe CI usage.

## Quickstart

```bash
pip install topmark
# Check (dry-run)
topmark --summary --config topmark.toml src/
# Apply changes
topmark --apply src/
```

## What it does

- Detects, inserts, and updates per‑file headers
- Honors shebangs, XML declarations, and native comment styles
- Preserves newline style (LF/CRLF/CR) and BOM
- Provides `strip` to remove headers (also dry‑run by default)
- Works well in CI and with pre‑commit hooks

## Commands

`topmark [SUBCOMMAND] [OPTIONS] [PATHS]...`

Core subcommands: `check` *(default)*, `strip`, `dump-config`, `show-defaults`, `init-config`,
`filetypes`, `version`.

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
file_types = ["python", "markdown", "env"]
relative_to = "."
```

## Next steps

- **Install:** [Installation guide](install.md)
- **Usage:** Pre‑commit integration ([usage/pre-commit.md](usage/pre-commit.md))
- **CI/CD:** Release workflow ([ci/release-workflow.md](ci/release-workflow.md))
- **API:** Reference ([api/index.md](api/index.md))
- **Contributing:** [Guidelines](contributing.md)

______________________________________________________________________

Need the complete, canonical introduction? See the project README on GitHub.
