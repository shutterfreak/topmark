<!--
topmark:header:start

  project      : TopMark
  file         : file-type-identifiers.md
  file_relpath : docs/_snippets/file-type-identifiers.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

> [!NOTE] **File type identification**
>
> TopMark accepts file type identifiers in either local form, such as `python`, or qualified form,
> such as `topmark:python`.
>
> Internally, TopMark normalizes file type identifiers to canonical qualified keys such as
> `topmark:python`. This canonical form is used throughout runtime processing, filtering, policy
> resolution, diagnostics, and registry lookups.
>
> Plugins and integrations may declare file types in their own namespace, such as `acme:python`.
> This allows independent ecosystems to define custom file types and to register different header
> processors without colliding with built-in TopMark identifiers.
>
> Local identifiers are accepted only when they are unambiguous. If more than one registered file
> type has the same local identifier, the local form is considered ambiguous and TopMark requires
> the qualified form.
