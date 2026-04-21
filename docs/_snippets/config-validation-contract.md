<!--
topmark:header:start

  project      : TopMark
  file         : config-validation-contract.md
  file_relpath : docs/_snippets/config-validation-contract.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

> [!NOTE] **Configuration validation contract (1.0)**
>
> TopMark evaluates configuration validity across staged config-loading/preflight diagnostics:
>
> - TOML-source diagnostics
> - merged-config diagnostics
> - runtime-applicability diagnostics
>
> For 1.0, this staged form remains internal. Reporting and machine/API/CLI surfaces expose only the
> flattened compatibility diagnostics contract (stable entry shape `{level, message}` where
> applicable).
