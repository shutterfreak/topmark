<!--
topmark:header:start

  project      : TopMark
  file         : discovery.md
  file_relpath : docs/configuration/discovery.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Configuration: Discovery, Precedence & Policy

TopMark merges configuration from multiple sources with **clear precedence** and now supports **policy-based control** over header insertion and updates.

______________________________________________________________________

## Discovery order (lowest → highest precedence)

1. **Built-in defaults**\
   The packaged `topmark-default.toml`.

1. **User config**

   - `$XDG_CONFIG_HOME/topmark/topmark.toml`, or
   - `~/.topmark.toml`

1. **Project configs (root → current)**\
   Discovered upward from the **discovery anchor** to the filesystem root:

   - **Anchor selection:** the first input path you pass (its **parent** directory if it is a file).\
     If no input paths are given (or you read from STDIN), the anchor is the **current working directory**.\
     Use `--no-config` to skip this layer.
   - In each directory, TopMark considers both:
     - `pyproject.toml` (`[tool.topmark]`)
     - `topmark.toml`
   - **Same-directory precedence:** `pyproject.toml` is merged first, then `topmark.toml` can override it.
   - **Nearest-last wins:** directories are merged **root → current** (the nearest config wins).
   - **Stopping discovery:** set `root = true` to stop traversal above that directory.

1. **Explicit config files**\
   Provided via `--config PATH`, merged **in the order given** (after discovery).

1. **CLI overrides (highest)**\
   Options and flags on the command line.

> **Summary:** defaults → user → project chain (root→current) → `--config` (in order) → CLI.\
> Use `--no-config` to skip discovery.

### Summary table

| Layer            | Example location                                      | Notes                                                                                           |
| ---------------- | ----------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 1. Defaults      | bundled `topmark-default.toml`                        | lowest precedence                                                                               |
| 2. User          | `~/.config/topmark/topmark.toml` or `~/.topmark.toml` | personal overrides                                                                              |
| 3. Project chain | `pyproject.toml` / `topmark.toml`                     | walk **root → current**; same-dir precedence: `pyproject` then `topmark`; stop on `root = true` |
| 4. `--config`    | paths passed on CLI                                   | merged **in order**                                                                             |
| 5. CLI           | flags & options                                       | highest precedence                                                                              |

______________________________________________________________________

## Path semantics

TopMark resolves paths relative to **where they are defined**:

| Source                                                               | Resolution base                               |
| -------------------------------------------------------------------- | --------------------------------------------- |
| Config-declared globs (`include_patterns`, `exclude_patterns`)       | Directory of the config file                  |
| CLI globs (`--include`, `--exclude`)                                 | Current working directory                     |
| Path-to-file settings (`include_from`, `exclude_from`, `files_from`) | Directory of defining config (or CWD for CLI) |

Note: `relative_to` only affects metadata fields like `file_relpath`, not file matching.

______________________________________________________________________

## Root semantics

`root = true` stops traversal above the directory where it’s defined.\
This defines a discovery boundary similar to tools like **Black**, **isort**, or **ruff**.

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
- [Path semantics](#path-semantics)

______________________________________________________________________

## Policy resolution

TopMark applies **effective policies** by merging global and per-file-type rules:

```toml
[tool.topmark.policy]
add_only = false
update_only = false
allow_header_in_empty_files = false

[tool.topmark.policy_by_type."python"]
allow_header_in_empty_files = true
```

The effective policy is computed as:

```text
effective = merge(global_policy, policy_by_type[file_type])
```

| Policy key                    | Description                                                 |
| ----------------------------- | ----------------------------------------------------------- |
| `add_only`                    | Only allow header insertion (no updates)                    |
| `update_only`                 | Only allow header updates (no new insertions)               |
| `allow_header_in_empty_files` | Permit header addition to empty files (e.g., `__init__.py`) |

______________________________________________________________________

## Gatekeeping & Pipeline

Each pipeline step (reader, builder, renderer, comparer, updater, writer) is protected by **gating helpers** such as `may_proceed_to_writer(ctx)`.\
These consider:

- File system status
- Comparison result
- Strip vs insert/update mode
- Policy permissions (`permitted_by_policy`)
- Feasibility (`can_change`)

This ensures TopMark won’t modify files unless explicitly permitted by configuration and policy.

______________________________________________________________________

## Observability

Run with `-v` or `--verbose` to see:

- Discovery anchor and workspace base
- Config chain (root → current)
- Normalization of pattern-file paths
- Active policy and per-file-type overrides

______________________________________________________________________

## Examples

### Allow headers in empty Python files

```toml
[tool.topmark.policy_by_type."python"]
allow_header_in_empty_files = true
```

Now, even an empty `__init__.py` or `placeholder.py` can receive a header.

______________________________________________________________________

## See also

- Default configuration: `src/topmark/config/topmark-default.toml`
- Implementation: `MutableConfig.load_merged()` and `effective_policy()` in `topmark.config.model`
- Related doc: `README.md`
