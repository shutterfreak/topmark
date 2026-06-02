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
> TopMark serializes header metadata, processing machine-output paths, and probe machine-output
> paths with POSIX `/` separators on all platforms.
>
> Human-facing output follows display-path policy instead:
>
> - CLI and Markdown reports may use the host platform's native path representation;
> - STDIN-backed processing displays the logical `--stdin-filename` when available; and
> - unified diff file labels are human-facing display labels, not machine-readable path fields.
