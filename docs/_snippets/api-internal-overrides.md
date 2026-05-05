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
> \[`ConfigOverrides`\][topmark.config.overrides.ConfigOverrides] are **not part of the public API
> surface**. They are used internally by CLI and API orchestration.
>
> Public callers should pass plain mapping-based inputs via `config=...`, `policy=...`, and
> `policy_by_type=...` instead of constructing these objects directly.
