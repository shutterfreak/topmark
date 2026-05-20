<!--
topmark:header:start

  project      : TopMark
  file         : report-scope.md
  file_relpath : docs/_snippets/report-scope.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

- `--report` controls the scope of human per-file TEXT rendering only. It does not affect
  processing, mutation behavior, summaries, machine-readable output, or exit-code selection.

  Values:

  - `actionable`: show files that would change, changed, failed, or otherwise require attention;
    hide unsupported entries from the per-file listing while summaries may still count them.
  - `noncompliant`: show actionable entries plus unsupported entries.
  - `all`: show every processed result, including unchanged/compliant entries.
