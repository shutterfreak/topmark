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

- **Defaults** → **User** (e.g. `$HOME/.config/topmark.toml`) → **Project chain**
  (discovered upward from the discovery anchor) → **`--config`** → **CLI**
- **Globs declared in config files** are resolved relative to the **directory of that config file**.
- **Globs declared via CLI** are resolved relative to the **current working directory** (invocation site).
- **Path-to-file settings** (e.g., `exclude_from`, `files_from`) are resolved relative to the **declaring config file** (or CWD for CLI-provided values).
- `relative_to` affects only header metadata (e.g., `file_relpath`), not discovery.

Start here:

- [`Discovery & Precedence`](./discovery.md)
- [`Root semantics`](./discovery.md#root-semantics) for how discovery stops at `root = true`

Also see:

- `src/topmark/config/topmark-default.toml` (built-in defaults with extensive comments)
- API docs: `MutableConfig.load_merged()`, `Config`, `MutableConfig`
