<!--
topmark:header:start

  project      : TopMark
  file         : registry-globs-and-match-regex-filtering.md
  file_relpath : docs/_snippets/registry-globs-and-match-regex-filtering.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

Globs are case-sensitive. `--match-regex` uses a full match against the canonical qualified
identity; write `.*` when a substring match is intended. Malformed identity queries and invalid
regular expressions are CLI usage errors. Quote glob and regular-expression values so the shell does
not interpret them. A query with no matching entries succeeds and emits an empty result in every
output format.
