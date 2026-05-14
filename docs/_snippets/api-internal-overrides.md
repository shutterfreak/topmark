<!--
topmark:header:start

  project      : TopMark
  file         : api-internal-overrides.md
  file_relpath : docs/_snippets/api-internal-overrides.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

> [!NOTE]
>
> Internal helper types such as \[`PolicyOverrides`\][topmark.config.overrides.PolicyOverrides] and
> \[`ConfigOverrides`\][topmark.config.overrides.ConfigOverrides] are not part of the stable public
> API surface. They are internal runtime orchestration helpers used by the CLI and public API
> wrappers.
>
> Public callers should pass plain mapping-based inputs through `config=...`, `policy=...`, and
> `policy_by_type=...` instead of constructing these objects directly.
