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
> Path serialization is a presentation contract and is distinct from filesystem identity.
>
> TopMark first determines a canonical processing path for the filesystem target being processed and
> then serializes that processing path according to the machine-output contract.
>
> This contract applies to:
>
> - header metadata path fields;
> - processing machine-output payloads;
> - probe machine-output payloads;
> - configuration machine-output payloads; and
> - TOML/config provenance payloads.
>
> Examples:
>
> ```text
> real/file.py
> ./real/file.py
> link-to-file.py
> ```
>
> may refer to the same filesystem identity and therefore produce the same serialized processing
> path.
>
> TopMark currently defines filesystem identity using the resolved processing target path. Hard-link
> detection and device/inode-based identity are outside the current compatibility contract.
>
> Human-facing output follows display-path policy instead:
>
> - CLI and Markdown reports may use the host platform's native path representation;
> - STDIN-backed processing displays the logical `--stdin-filename` when available; and
> - unified diff file labels are human-facing display labels, not machine-readable path fields.
>
> Synthetic configuration-source identifiers (for example built-in defaults) are serialized as
> stable labels rather than filesystem paths.
