<!--
topmark:header:start

  project      : TopMark
  file         : no-stdin-option.md
  file_relpath : docs/_snippets/no-stdin-option.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

> [!NOTE] **STDIN input**
>
> TopMark does **not** provide a `--stdin` option flag. Use the POSIX-style `-` PATH sentinel
> together with `--stdin-filename` for content mode.
>
> Passing `--stdin` is treated as an invalid option and results in a CLI usage error.
