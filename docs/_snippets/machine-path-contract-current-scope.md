<!--
topmark:header:start

  project      : TopMark
  file         : machine-path-contract-current-scope.md
  file_relpath : docs/_snippets/machine-path-contract-current-scope.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

> [!NOTE] **Current machine path contract scope**
>
> TopMark currently guarantees POSIX `/` path serialization for:
>
> - header metadata path fields; and
> - processing and probe machine-readable output.
>
> Some machine-readable configuration and provenance payloads may still emit path-like values
> outside this contract. A future compatibility update may extend POSIX serialization to all
> machine-readable path fields.
