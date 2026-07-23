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
> Multiword enum values at the CLI boundary require hyphens:
>
> ```bash
> topmark check --header-mutation-mode=add-only
> ```
>
> Snake-case CLI aliases such as `add_only`, `update_only`, `logical_empty`, and `remove_bom` are
> rejected with a suggestion for the canonical hyphenated spelling. Value matching remains
> case-insensitive, so `ADD-ONLY` is accepted as `add-only`.
>
> TOML configuration, Python API values, and machine-readable output use the canonical underscore
> form:
>
> ```toml
> [policy]
> header_mutation_mode = "add_only"
> ```
>
> CLI option names themselves also do not accept underscores. Use `--header-mutation-mode`, not
> `--header_mutation_mode`.
