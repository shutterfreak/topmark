# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/cli_shared/emitters/shared/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared, Click-free helpers for human-facing CLI emitters.

This package contains *output-preparation* helpers that are reused by multiple human-facing CLI
formats, primarily **TEXT** (ANSI / console) and **MARKDOWN** outputs.

The helpers in this package are responsible for:
- Preparing structured, presentation-ready data from core domain objects   (e.g. `Config`,
  diagnostics, registry entries).
- Encapsulating formatting-agnostic logic such as:
  - resolving defaults,
  - normalizing data structures,
  - applying verbosity rules,
  - performing safe template transformations.
- Keeping CLI commands themselves focused on orchestration only.

Design principles:
- **No Click dependency**: this package must remain usable from non-Click frontends and tests.
- **No rendering**: helpers here do *not* write to consoles or produce final strings; rendering is
  delegated to format-specific emitters.
- **Human-output only**: machine formats (JSON / NDJSON) are handled via the dedicated
  `topmark.*.machine` packages.

Typical usage:
- CLI commands call a `prepare_*` helper from this package.
- The returned prepared object is then rendered by:
  - `topmark.cli.emitters.text.*` (ANSI / console), or
  - `topmark.cli_shared.emitters.markdown.*` (Markdown).

This package intentionally mirrors the domain structure (config, registry, diagnostics, pipeline, …)
to keep symmetry with machine-format helpers and to support future extensions.
"""

from __future__ import annotations
