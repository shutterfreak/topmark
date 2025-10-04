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

- Defaults → User → Project chain → `--config` → CLI
- Globs evaluated relative to the **workspace base** (`relative_to`)
- Path-to-file settings resolved relative to the **config file's directory**

Start here:

- [`Discovery & Precedence`](./discovery.md)

Also see:

- `src/topmark/config/topmark-default.toml` (built-in defaults with extensive comments)
- API docs: `MutableConfig.load_merged()`, `Config`, `MutableConfig`
