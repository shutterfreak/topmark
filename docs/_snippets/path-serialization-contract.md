<!--
topmark:header:start

  project      : TopMark
  file         : path-serialization-contract.md
  file_relpath : docs/_snippets/path-serialization-contract.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

> [!NOTE] **Path representation**
>
> TopMark serializes machine-readable filesystem path fields with POSIX `/` separators on all
> platforms.
>
> This contract applies to:
>
> - header metadata path fields;
> - processing machine-output payloads;
> - probe machine-output payloads;
> - configuration machine-output payloads; and
> - TOML/config provenance payloads.
>
> Human-facing output follows display-path policy instead:
>
> - CLI and Markdown reports may use the host platform's native path representation;
> - STDIN-backed processing displays the logical `--stdin-filename` when available; and
> - unified diff file labels are human-facing display labels, not machine-readable path fields.
>
> Synthetic configuration-source identifiers (for example built-in defaults) are serialized as
> stable labels rather than filesystem paths.
