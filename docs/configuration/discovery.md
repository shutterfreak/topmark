<!--
topmark:header:start

  project      : TopMark
  file         : discovery.md
  file_relpath : docs/configuration/discovery.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Configuration: Discovery & Precedence

TopMark merges configuration from multiple sources with **clear precedence**. This page explains:

- How configuration files are discovered
- How merges are applied (lowest → highest precedence)
- How **globs** vs **path-to-file settings** are resolved with different bases
- How CLI flags fit into the picture

## Discovery order (lowest → highest precedence)

1. **Built-in defaults**\
   The packaged `topmark-default.toml`.

1. **User config**

   - `$XDG_CONFIG_HOME/topmark/topmark.toml`, or
   - `~/.topmark.toml`

1. **Project configs (root → current)**\
   Discovered upward from the **anchor directory** to the filesystem root:

   - In each directory, TopMark considers both:
     - `pyproject.toml` (`[tool.topmark]`)
     - `topmark.toml` (tool-specific file)
   - **Same-directory precedence:** `pyproject.toml` is merged first, then `topmark.toml` can override it.
   - **Nearest-last wins:** directories are merged **root → current** (the nearest config wins).
   - **Stopping discovery:** set `root = true` in a discovered config to stop traversal above that directory.\
     In `pyproject.toml`, put it under `[tool.topmark]`.

1. **Explicit config files**\
   Provided via `--config PATH`, merged **in the order given**.

1. **CLI overrides (highest)**\
   Options and flags on the command line.

> **Anchor selection:** The discovery anchor is the first input path you pass (its parent directory if it is a file). If no input paths are given (or you read from STDIN), the anchor is the **current working directory**.

### Summary table

| Layer            | Example location                                      | Notes                                                                                           |
| ---------------- | ----------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 1. Defaults      | bundled `topmark-default.toml`                        | lowest precedence                                                                               |
| 2. User          | `~/.config/topmark/topmark.toml` or `~/.topmark.toml` | personal overrides                                                                              |
| 3. Project chain | `pyproject.toml` / `topmark.toml`                     | walk **root → current**; same-dir precedence: `pyproject` then `topmark`; stop on `root = true` |
| 4. `--config`    | paths passed on CLI                                   | merged **in order**                                                                             |
| 5. CLI           | flags & options                                       | highest precedence                                                                              |

______________________________________________________________________

## Path semantics: two distinct bases

TopMark uses **two different bases** to resolve paths:

1. **Workspace base** (aka run/project root) → used for **globs**

   - Config key examples: `files.include_patterns`, `files.exclude_patterns`
   - Base path: `relative_to` (if set), otherwise the **nearest discovered config directory**.
   - Effect: globs are evaluated *consistently* regardless of your current working directory.

1. **Config-local base** → used for **paths to other files**

   - Config key examples: `files.include_from`, `files.exclude_from`, `files.files_from`, and (if used) literal `files` lists.
   - Base path: **the directory of the config file** that declares the path.
   - Behavior: these paths are normalized to absolute when a config file is loaded.

**Pattern file semantics:** Pattern files (e.g. `.gitignore`) have their own base: patterns are evaluated relative to the **directory that contains the pattern file**. TopMark preserves this behavior per file.

______________________________________________________________________

## CLI behavior

- **CLI path-to-file options** (`--include-from`, `--exclude-from`, `--files-from`):\
  Resolved relative to the **current working directory** (your invocation site), then normalized to absolute.

- **CLI globs** (`--include`, `--exclude`):\
  Kept as strings and evaluated later relative to the **workspace base** (`relative_to`).

______________________________________________________________________

## Examples

### Basic discovery with `root = true`

```toml
# topmark.toml (in repo root)
root = true

[files]
# Evaluate globs relative to the repo root
include_patterns = ["src/**/*.py"]
```

- Running `topmark check` in subdirectories still uses the **repo root** for glob evaluation.
- Most-near configs override more distant ones unless `root = true` stops traversal earlier.

### Pattern files from different places

```toml
# pyproject.toml, [tool.topmark] table (project root)
[tool.topmark.files]
exclude_from = [".gitignore"]  # resolved to <repo>/.gitignore

# topmark.toml in a nested app/
[files]
exclude_from = ["app.ignore"]  # resolved to <repo>/app/app.ignore
```

- Both entries are normalized to **absolute** paths at load time.
- When applying patterns:
  - `.gitignore` rules apply with base `<repo>/`
  - `app.ignore` rules apply with base `<repo>/app/`

______________________________________________________________________

## Observability

Run with `-v` to see:

- Discovery anchor and workspace base (`relative_to`)
- Discovered config chain (root → current)
- Normalization of pattern-file paths (with their base)
- Which layer provided a given setting

______________________________________________________________________

## See also

- Default config with extensive comments:\
  `src/topmark/config/topmark-default.toml`
- API: `MutableConfig.load_merged()` and `resolve_config_from_click()` (mkdocstrings)
