<!--
topmark:header:start

  project      : TopMark
  file         : report-scope.md
  file_relpath : docs/_snippets/report-scope.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

- `--report` controls the scope of the human per-file report for TEXT and Markdown output. It does
  not affect pipeline execution, mutation behavior, summary aggregation, diff generation,
  machine-readable output, or exit-code selection. When `--diff` is requested, unified diffs are
  rendered as a separate human-output section after the per-file report. Diff visibility is
  determined solely by whether a diff was produced for a file and is independent of the selected
  report scope.

  Values:

  - `actionable`: show files that are actionable for the selected command, failed, or otherwise
    require attention; hide unsupported entries from the per-file listing while summaries may still
    count them.
  - `noncompliant`: show actionable entries plus unsupported entries.
  - `all`: show every processed result, including unchanged/compliant entries.

  Notes:

  - Report filtering applies only to the human per-file report section.
  - Unified diff output is rendered separately from the per-file report and is not filtered by
    `--report`.
  - Machine-readable formats ignore `--report`; JSON detail embeds per-result diff payloads and
    NDJSON detail emits adjacent standalone `diff` records when `--diff` is requested.
  - Machine-readable summary output suppresses per-file diff payloads even when `--diff` is
    requested and emits a warning to `stderr`.
