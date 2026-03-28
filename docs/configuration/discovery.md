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

TopMark merges configuration from multiple sources with **clear precedence** and now supports
**policy-based control** over header insertion and updates.

______________________________________________________________________

## Discovery order

Configuration is discovered as follows (lowest → highest precedence):

1. **Built-in defaults**\
   Builtin runtime defaults.

1. **User config**

   - `$XDG_CONFIG_HOME/topmark/topmark.toml`, or
   - `~/.topmark.toml`

1. **Project configs (root → current)**\
   Discovered upward from the **discovery anchor** to the filesystem root:

   - **Anchor selection:** the first input path you pass (its **parent** directory if it is a
     file).\
     If no input paths are given (or you read from STDIN), the anchor is the **current working
     directory**.\
     Use `--no-config` to skip this layer.
   - In each directory, TopMark considers both:
     - `pyproject.toml` (`[tool.topmark]`)
     - `topmark.toml`
   - **Same-directory precedence:** `pyproject.toml` is merged first, then `topmark.toml` can
     override it.
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
| 1. Defaults      | Builtin runtime defaults                              | lowest precedence                                                                               |
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

- [Discovery order](#discovery-order)
- [Path semantics](#path-semantics)

______________________________________________________________________

## Policy resolution

TopMark applies **effective policies** by merging global and per-file-type rules:

```toml
[tool.topmark.policy]
header_mutation_mode = "all"
allow_header_in_empty_files = false
empty_insert_mode = "logical_empty"

[tool.topmark.policy_by_type."python"]
allow_header_in_empty_files = true
```

The effective policy is computed as:

```text
effective = merge(global_policy, policy_by_type[file_type])
```

### Empty file semantics

The meaning of "empty" is controlled by `empty_insert_mode`:

| Mode               | Description                                                        |
| ------------------ | ------------------------------------------------------------------ |
| `bytes_empty`      | Only true 0-byte files                                             |
| `logical_empty`    | 0-byte files + placeholders (BOM, optional whitespace, ≤1 newline) |
| `whitespace_empty` | Any file containing only whitespace / newlines                     |

This classification is used when evaluating `allow_header_in_empty_files`.

For `topmark check`, these policy values may also be overridden from the CLI via
`--header-mutation-mode`, `--allow-header-in-empty-files`, `--empty-insert-mode`,
`--render-empty-header-when-no-fields`, `--allow-reflow`, and the shared `--allow-content-probe`
option.

### Policy keys

| Policy key                           | Description                                                           |
| ------------------------------------ | --------------------------------------------------------------------- |
| `header_mutation_mode`               | Controls insertion/update behavior (`all`, `add_only`, `update_only`) |
| `allow_header_in_empty_files`        | Permit header insertion in empty-like files                           |
| `empty_insert_mode`                  | Defines how "empty" is interpreted (see above)                        |
| `render_empty_header_when_no_fields` | Allow inserting empty headers when no fields are defined              |
| `allow_reflow`                       | Allow content reflow (may break idempotence)                          |
| `allow_content_probe`                | Allow resolver to inspect file contents for type detection            |

______________________________________________________________________

## Gatekeeping & Pipeline

Each pipeline step (`ResolverStep`, `SnifferStep`, `ReaderStep`, `ScannerStep`, `BuilderStep`,
`RendererStep`, `ComparerStep`, `StripperStep`, `PatcherStep`, `PlannerStep`, `WriterStep`) is
protected by a `may_proceed(ctx)` gating helper.

These gates consider:

- File system status (including empty vs empty-like classification)
- Content status (readability, encoding, newline policy)
- Comparison result and update intent
- Policy permissions (for example `allow_insert_into_empty_like`)
- Feasibility (`can_change`)

This ensures TopMark only mutates files when explicitly permitted by both policy and pipeline
feasibility rules.

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

- Default configuration: `src/topmark/config/topmark-example.toml`
- Implementation: \[`load_resolved_config()`\][topmark.config.io.resolution.load_resolved_config]
  and \[`effective_policy()`\][topmark.config.policy.effective_policy] in
  \[`topmark.config`\][topmark.config]
- Related doc: `README.md`
