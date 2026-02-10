# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/config/machine/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output helpers for config commands.

This package contains the *config domain* implementation of TopMark's
machine-readable output for config-related commands (for example
`topmark config dump` and `topmark config check`).

Layers:
    - **schemas**: Typed schema fragments for config-specific payloads (static typing only).
    - **payloads**: Pure payload builders for the config domain (no `meta`/`kind`, no
      serialization).
    - **shapes**: Composition of domain payloads into full machine shapes:
      - JSON envelope (`meta` + domain payloads)
      - NDJSON record stream (Pattern A: every record includes `kind` and `meta`)
    - **serializers**: Pure JSON/NDJSON helpers that turn shaped objects/records into strings
      (no Click/Console printing).

Notes:
    This package intentionally re-exports only the config serializer facades
    (`serialize_config`, `serialize_config_check`, `serialize_config_diagnostics`).
    Typed payload schemas, payload builders, and shape builders remain available from:
    [`topmark.config.machine.schemas`][topmark.config.machine.schemas],
    [`topmark.config.machine.payloads`][topmark.config.machine.payloads] and
    [`topmark.config.machine.shapes`][topmark.config.machine.shapes],
    This keeps call sites explicit about which layer they depend on.

See Also:
    - [`topmark.core.machine`][topmark.core.machine]: shared machine-output primitives
      (keys/kinds/domains, envelopes/records, normalization, JSON/NDJSON serialization helpers).
"""

from __future__ import annotations

from topmark.config.machine.serializers import (
    serialize_config,
    serialize_config_check,
    serialize_config_diagnostics,
)

__all__ = [
    "serialize_config",
    "serialize_config_check",
    "serialize_config_diagnostics",
]
