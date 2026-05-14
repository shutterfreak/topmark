<!--
topmark:header:start

  project      : TopMark
  file         : option-spelling.md
  file_relpath : docs/_snippets/option-spelling.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

> [!NOTE] **CLI spelling vs configuration/API spelling**
>
> TopMark uses *hyphenated spelling* for CLI option names:
>
> ```bash
> topmark check --header-mutation-mode=add-only
> ```
>
> For multi-word option values, the CLI accepts both hyphenated and canonical underscore forms:
>
> ```bash
> topmark check --header-mutation-mode=add-only
> topmark check --header-mutation-mode=add_only
> ```
>
> TOML configuration, Python API values, and machine-readable output use the canonical underscore
> form:
>
> ```toml
> [policy]
> header_mutation_mode = "add_only"
> ```
>
> CLI option names themselves do not accept underscores. Use `--header-mutation-mode`, not
> `--header_mutation_mode`.
