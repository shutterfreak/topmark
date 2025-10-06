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
   Discovered upward from the **discovery anchor** to the filesystem root:

   - **Anchor selection:** the first input path you pass (its **parent** directory if it is a file).
     If no input paths are given (or you read from STDIN), the anchor is the **current working
     directory**. Use `--no-config` to skip this layer.
   - In each directory, TopMark considers both:
     - `pyproject.toml` (`[tool.topmark]`)
     - `topmark.toml` (tool-specific file)
   - **Same-directory precedence:** `pyproject.toml` is merged first, then `topmark.toml` can
     override it.
   - **Nearest-last wins:** directories are merged **root → current** (the nearest config wins).
   - **Stopping discovery:** set `root = true` in a discovered config to stop traversal above that
     directory.\
     In `pyproject.toml`, put it under `[tool.topmark]`.

1. **Explicit config files**\
   Provided via `--config PATH`, merged **in the order given** (after discovery).

1. **CLI overrides (highest)**\
   Options and flags on the command line.

> **Summary:** defaults → user → project chain (root→current; same-dir: pyproject then topmark) →
> `--config` (in order) → CLI. Use `--no-config` to skip the project chain.

### Summary table

| Layer            | Example location                                      | Notes                                                                                           |
| ---------------- | ----------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 1. Defaults      | bundled `topmark-default.toml`                        | lowest precedence                                                                               |
| 2. User          | `~/.config/topmark/topmark.toml` or `~/.topmark.toml` | personal overrides                                                                              |
| 3. Project chain | `pyproject.toml` / `topmark.toml`                     | walk **root → current**; same-dir precedence: `pyproject` then `topmark`; stop on `root = true` |
| 4. `--config`    | paths passed on CLI                                   | merged **in order**                                                                             |
| 5. CLI           | flags & options                                       | highest precedence                                                                              |

______________________________________________________________________

## Path semantics: sources define the base

TopMark resolves paths relative to **where they are defined**:

1. **Config‑declared globs** (e.g., `files.include_patterns`, `files.exclude_patterns`)

   - Resolved relative to the **directory containing that config file**.

1. **CLI‑declared globs** (`--include`, `--exclude`)

   - Resolved relative to the **current working directory** (where `topmark` is invoked).

1. **Path‑to‑file settings**

   - Examples: `files.include_from`, `files.exclude_from`, `files.files_from`.
   - Resolved relative to the **declaring config file’s directory**; for CLI options, resolved
     relative to **CWD**. The referenced files’ own patterns are then evaluated relative to each
     file’s own directory.

NOTE: `relative_to` is used **only** for header metadata (e.g., `file_relpath`), and **not** for
glob expansion or filtering.

______________________________________________________________________

## Root semantics

`root = true` in a discovered config stops the upward traversal **above** that directory.

- Where to put it:
  - In `topmark.toml`, at the top level.
  - In `pyproject.toml`, under `[tool.topmark]`.
- Effect:
  - Directories at or below the marked directory remain eligible (the marked directory can still be
    merged), but parent directories are **not** considered.
  - This ensures a repository (or workspace) boundary for discovery.
- Interaction with explicit `--config`:
  - `--config` files are merged **after** discovery, so they still apply even if `root = true`
    stopped discovery.
- Multiple roots:
  - If multiple configs on the path specify `root = true`, the *nearest* one wins (since discovery
    walks **root → current** and the merge order is nearest-last).

Example:

```toml
# repo/topmark.toml
root = true

[files]
include_patterns = ["src/**/*.py"]
```

Running `topmark check` in `repo/app/` will:

1. Use `repo/` as part of the project chain (because it contains a config),
1. Stop searching parents above `repo/`,
1. Evaluate `include_patterns` relative to `repo/`.

See also:

- [Discovery order](#discovery-order-lowest-highest-precedence)
- [Path semantics](#path-semantics-sources-define-the-base)

______________________________________________________________________

## CLI behavior

- **CLI path-to-file options** (`--include-from`, `--exclude-from`, `--files-from`):\
  Resolved relative to the **current working directory** (your invocation site), then normalized to
  absolute.

- **CLI globs** (`--include`, `--exclude`):\
  Resolved relative to the **current working directory** (your invocation site).

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
