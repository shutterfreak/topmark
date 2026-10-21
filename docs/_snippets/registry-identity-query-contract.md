<!--
topmark:header:start

  project      : TopMark
  file         : registry-identity-query-contract.md
  file_relpath : docs/_snippets/registry-identity-query-contract.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

> [!NOTE] **Querying by identity**
>
> The structured form is `[namespace-glob]:[local-key-glob]`; an empty component means `*`.
>
> A bare identifier is an exact local-key query, while a bare glob matches the complete canonical
> qualified identity.
>
> Positional queries are alternatives: use one structured query when both namespace and local key
> must match.
>
> `--match-regex PATTERN` values are also alternatives and use a full match against the canonical
> qualified identity; write `.*` when a substring match is intended. Globs are case-sensitive. Quote
> glob and regular-expression values so the shell does not interpret them, for example `'*json*'`.
> Valid queries with no matches succeed and emit an empty result in every output format. Malformed
> identity queries and invalid regular expressions are Click parser errors (exit code `2`).
