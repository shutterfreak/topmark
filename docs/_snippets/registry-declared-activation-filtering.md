<!--
topmark:header:start

  project      : TopMark
  file         : registry-declared-activation-filtering.md
  file_relpath : docs/_snippets/registry-declared-activation-filtering.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

> [!NOTE] **Filtering by declared activation**
>
> - Repeat `--activation` (or `-a`) to filter by declared activation.
> - Each value is `default`, `opt-in`, or `never`.
> - Values can also be comma-separated, such as `--activation never,opt-in`.
> - Values are deduplicated and combined with OR semantics.
>
> The resulting filter is restrictive alongside other applicable filters.
>
> Empty comma segments and unknown values are usage errors.
>
> It is introspection only: it does not supply opt-in consent or change runtime authorization.
