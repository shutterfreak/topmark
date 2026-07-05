# topmark:header:start
#
#   project      : TopMark
#   file         : errors.py
#   file_relpath : src/topmark/core/machine/errors.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared errors for machine-readable output helpers.

This module centralizes small, Click-free error helpers used by JSON and NDJSON
serializers. The helpers intentionally return built-in exceptions because these
failures are serializer-boundary validation errors, not domain-level TopMark
exceptions.
"""

from __future__ import annotations

from typing import Final

_UNSUPPORTED_MACHINE_READABLE_FORMAT: Final[str] = "Unsupported machine-readable output format"


def unsupported_machine_readable_format(fmt: object) -> ValueError:
    """Build a consistent error for unsupported machine-readable formats.

    Accept object instead of OutputFormat, because this helper is mainly for
    defensive/fail-closed boundaries:
    """
    return ValueError(f"{_UNSUPPORTED_MACHINE_READABLE_FORMAT}: {fmt!r}")
