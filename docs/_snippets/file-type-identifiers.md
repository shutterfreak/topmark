<!--
topmark:header:start

  project      : TopMark
  file         : file-type-identifiers.md
  file_relpath : docs/_snippets/file-type-identifiers.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

TopMark accepts file type identifiers in local form, such as `python`, or qualified form, such as
`topmark:python`.

Local identifiers are accepted only when unambiguous. Internally, TopMark normalizes identifiers to
canonical qualified file type identities before filtering, runtime resolution, policy evaluation,
diagnostics, and registry lookup.
