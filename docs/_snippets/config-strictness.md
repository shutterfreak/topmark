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
> When configuration validation fails, CLI commands exit with `CONFIG_ERROR`, preserving the
> diagnostics in human-readable and machine-readable output. Public API calls raise
> \[`ConfigValidationError`\][topmark.core.errors.ConfigValidationError] with those diagnostics.
>
> `strict` is resolved during TOML loading and does not become a layered configuration field.
>
> Configuration errors are fatal in both modes. In non-strict mode, warnings remain advisory.
> Markdown reports include advisory diagnostics for completeness. Default TEXT output may instead
> report only the resulting runtime outcome, such as a file being filtered after configuration
> normalization. When `--strict` is enabled, warning diagnostics make configuration validation fail
> and are surfaced consistently across output formats.
