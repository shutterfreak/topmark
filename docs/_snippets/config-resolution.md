<!--
topmark:header:start

  project      : TopMark
  file         : config-resolution.md
  file_relpath : docs/_snippets/config-resolution.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

> [!NOTE] **How config is resolved**
>
> - TopMark merges config from **defaults → user → project chain → `--config` → CLI**.
> - **Project discovery** starts from the *discovery anchor*: the **first input path** (its parent
>   if it’s a file) or **CWD** when no inputs are provided.
> - Use `--no-config` to skip the project chain.
> - **Globs declared in config files** are resolved relative to the **config file’s directory**.
> - **Globs passed via CLI** are resolved relative to the **current working directory**.
> - Paths to other files (like `exclude_from`) are resolved relative to the **declaring source**
>   (config dir or CWD for CLI).
>
> See: [Configuration → Discovery & Precedence](../configuration/discovery.md).
