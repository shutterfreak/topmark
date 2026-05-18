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

The [`topmark.core`][topmark.core] package provides small, reusable building
blocks that are safe to import from anywhere in the codebase without pulling in
CLI, presentation, pipeline execution, or public API command concerns.

Included modules:

- ``constants``
  Package metadata, marker strings, registry token patterns, resource names,
  and newline definitions shared across the project.

- ``outcomes``
  Stable outcome enum values, deterministic outcome ordering, and fallback
  reason text shared by API DTOs, pipeline classifiers, and presentation code.

- ``errors``
  Core exception types used to classify configuration, TOML, registry,
  processing, and runtime failures.

- ``exit_codes``
  Centralized exit codes for the CLI and runtime, aligned with BSD-style
  ``sysexits`` where practical, with a dedicated ``WOULD_CHANGE`` code for
  dry-run mode.

- ``enum_mixins``
  Typing-friendly enum utilities and mixins for introspection and parsing.

- ``machine``
  Shared machine-output envelopes, payload contracts, and schemas used by
  higher-level serializers.

- ``presentation``
  Minimal semantic presentation primitives that remain independent of concrete
  text, Markdown, or CLI renderers.

- ``typing_guards``
  Narrow runtime type guards used to keep public and internal parsing code
  precise under strict type checking.

Design goals:

- Keep this package free of UI dependencies and side effects.
- Avoid imports from CLI commands, presentation renderers, pipeline steps, or
  public API command helpers.
- Prefer small, well-typed helpers over framework-specific utilities.
- Maintain stable internal contracts that higher-level layers can rely on.
"""

from __future__ import annotations
