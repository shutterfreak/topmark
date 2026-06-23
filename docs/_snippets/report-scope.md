<!--
topmark:header:start

  project      : TopMark
  file         : report-scope.md
  file_relpath : docs/_snippets/report-scope.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

- `--report` controls the scope of human per-file output for TEXT and Markdown rendering. It does
  not affect processing, mutation behavior, summaries, machine-readable output, or exit-code
  selection.

  Values:

  - `actionable`: show files that are actionable for the selected command, failed, or otherwise
    require attention; hide unsupported entries from the per-file listing while summaries may still
    count them.
  - `noncompliant`: show actionable entries plus unsupported entries.
  - `all`: show every processed result, including unchanged/compliant entries.
