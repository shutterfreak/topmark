# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/core/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Core, UI-agnostic primitives shared across TopMark.

The ``topmark.core`` package provides small, reusable building blocks that are
safe to import from anywhere in the codebase (CLI, config, pipeline, tests)
without pulling in rendering or user-interface concerns.

Included modules:

- ``diagnostics``
  Internal diagnostic types and helpers (levels, messages, aggregation) used
  to collect and report info, warnings, and errors consistently.

- ``exit_codes``
  Centralized exit codes for the CLI and runtime, aligned with BSD-style
  ``sysexits`` where practical, with a dedicated ``WOULD_CHANGE`` code for
  dry-run mode.

- ``enum_mixins``
  Typing-friendly Enum utilities and mixins (introspection, parsing) that
  remain independent of CLI or UI rendering.

Design goals:

- Keep this package free of UI dependencies and side effects.
- Prefer small, well-typed helpers over framework-specific utilities.
- Maintain stable internal contracts that higher-level layers can rely on.
"""

from __future__ import annotations
