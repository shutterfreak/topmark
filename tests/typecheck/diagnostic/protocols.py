# topmark:header:start
#
#   project      : TopMark
#   file         : protocols.py
#   file_relpath : tests/typecheck/diagnostic/protocols.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Static structural contracts for diagnostic containers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.diagnostic.model import FrozenDiagnosticLog
    from topmark.diagnostic.model import MutableDiagnosticLog
    from topmark.diagnostic.types import DiagnosticsLike

__all__ = [
    "verify_frozen_diagnostics_protocol",
    "verify_mutable_diagnostics_protocol",
]


def verify_mutable_diagnostics_protocol(
    log: MutableDiagnosticLog,
) -> DiagnosticsLike:
    """Statically assert that mutable diagnostic logs expose the read-only view."""
    return log


def verify_frozen_diagnostics_protocol(
    log: FrozenDiagnosticLog,
) -> DiagnosticsLike:
    """Statically assert that frozen diagnostic logs expose the read-only view."""
    return log
