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
> Finite-choice CLI values require their exact documented lowercase spelling. Multiword values
> additionally require hyphens:
>
> ```bash
> topmark check --header-mutation-mode=add-only
> ```
>
> Uppercase, mixed-case, and snake_case CLI aliases such as `ADD-ONLY`, `Update-Only`, `add_only`,
> `logical_empty`, and `REMOVE_BOM` are rejected. When lowercasing the token and replacing
> underscores with hyphens produces an exact declared choice, TopMark suggests that canonical
> spelling.
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
> `--header_mutation_mode`. These spelling rules apply only to option names and finite-choice
> values; paths, filenames, globs, header content, and other free-form inputs retain their original
> case.
