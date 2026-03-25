# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/presentation/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Human-facing presentation layer for TopMark.

This package provides **Click-free, format-agnostic presentation helpers** used
by CLI commands to render human-readable output (TEXT, MARKDOWN, and future
formats).

It sits between the **domain/API layer** and the **format-specific renderers**
and is responsible for preparing structured, presentation-ready data.

Responsibilities:
- Build typed, human-facing report models (e.g. registry, config, diagnostics).
- Normalize and enrich raw API/domain data for presentation purposes.
- Apply verbosity rules and safe defaults.
- Provide shared formatting helpers reused across output formats.

Non-responsibilities:
- **No I/O**: this package never writes to stdout/stderr.
- **No CLI framework dependency**: remains usable outside Click (e.g. tests,
  alternative frontends).
- **No machine formats**: JSON/NDJSON are handled by `topmark.*.machine`.

Architecture:
- [`topmark.api`][topmark.api] → canonical structured metadata
- [`topmark.presentation`][topmark.presentation] → human-facing report models and helpers
    (this package)
- [`topmark.presentation.text`][topmark.presentation.text] → TEXT renderers
- [`topmark.presentation.markdown`][topmark.presentation.markdown] → MARKDOWN renderers
- [`topmark.cli.commands`][topmark.cli.commands] → orchestration and printing

Design principles:
- **Separation of concerns**: preparation vs rendering vs orchestration
- **Deterministic output**: TEXT and MARKDOWN derive from the same prepared data
- **Strong typing**: explicit report models instead of ad-hoc dicts

This package mirrors the conceptual domains of TopMark (registry, config,
diagnostics, pipeline, …) to keep symmetry with machine-format layers and to
support future extensions.
"""

from __future__ import annotations
