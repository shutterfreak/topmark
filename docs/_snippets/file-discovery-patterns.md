<!--
topmark:header:start

  project      : TopMark
  file         : file-discovery-patterns.md
  file_relpath : docs/_snippets/file-discovery-patterns.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

- Positional arguments are resolved **relative to the current working directory** (CWD),
  Black-style.

- Patterns in `--include`, `--exclude`, and the files passed to `--include-from` / `--exclude-from`
  are also resolved **relative to CWD**. Absolute patterns are not supported.

- STDIN supports two modes:

  - **list mode** via `--files-from -` (or `--include-from -` / `--exclude-from -`) for newline-
    delimited paths or patterns
  - **content mode** via `-` plus `--stdin-filename` for one file’s content
    - TopMark does not accept a `--stdin` flag; use the `-` PATH sentinel for content mode.
