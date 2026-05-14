<!--
topmark:header:start

  project      : TopMark
  file         : config-strictness.md
  file_relpath : docs/_snippets/config-strictness.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

> [!NOTE]
>
> `[config].strict` is a TOML-source-local strictness preference controlling staged config-loading
> validation for the current TOML source.
>
> Effective strictness is evaluated across:
>
> - TOML-source diagnostics;
> - merged-config diagnostics;
> - runtime-applicability diagnostics.
>
> `strict` is resolved during TOML loading and does not become a layered configuration field.
