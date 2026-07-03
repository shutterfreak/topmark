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
> `[config].strict` is a TOML-source-local strictness preference controlling staged
> configuration-loading validation for the current TOML source.
>
> Effective strictness is evaluated across:
>
> - TOML-source diagnostics;
> - merged-config diagnostics;
> - runtime applicability diagnostics.
>
> When strict validation fails, TopMark exits with `CONFIG_ERROR`. The diagnostics that triggered
> the failure remain visible in human-readable and machine-readable output formats.
>
> `strict` is resolved during TOML loading and does not become a layered configuration field.
>
> In non-strict mode, configuration diagnostics remain advisory. Markdown reports include advisory
> diagnostics for completeness. Default TEXT output may instead report only the resulting runtime
> outcome, such as a file being filtered after configuration normalization. When `--strict` is
> enabled, advisory diagnostics become fatal configuration errors and are surfaced consistently
> across output formats.
