<!--
topmark:header:start

  project      : TopMark
  file         : index.md
  file_relpath : docs/configuration/index.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Configuration Overview

TopMark supports layered configuration with explicit precedence:

- **Defaults** → **User** (e.g. `$HOME/.config/topmark.toml`) → **Project chain** (root → current) →
  **`--config`** → **CLI**
- **Globs declared in config files** are resolved relative to the **directory of that config file**.
- **Globs declared via CLI** are resolved relative to the **current working directory** (invocation
  site).
- **Path-to-file settings** (e.g., `exclude_from`, `files_from`) are resolved relative to the
  **declaring config file** (or CWD for CLI-provided values).
- **Merge semantics vary by field**: behavioral settings usually use nearest-wins semantics, mapping
  fields usually overlay keys, and discovery inputs usually accumulate across applicable layers.
- `relative_to` affects only header metadata (e.g., `file_relpath`), not discovery.

Start here:

- [`Discovery & Precedence`](./discovery.md)
- [`Merge semantics by field`](./discovery.md#merge-semantics-overview)
- [`Root semantics`](./discovery.md#root-semantics) for how discovery stops at
  `[config].root = true`
- [`Policy resolution`](./discovery.md#policy-resolution) for understanding how policy settings are
  defined and overridden at global level and per file type.

Also see:

- `src/topmark/toml/topmark-example.toml` (bundled example TopMark TOML resource)
- API docs:
  - `resolve_toml_sources_and_build_config_draft()`
  - `Config`, `MutableConfig`
