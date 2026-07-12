# topmark:header:start
#
#   project      : TopMark
#   file         : context_protocols.py
#   file_relpath : tests/typecheck/pipeline/context_protocols.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Static structural contracts for pipeline context protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.context.protocols import SupportsPolicyEvaluation

__all__ = ["verify_processing_context_protocol"]


def verify_processing_context_protocol(
    context: ProcessingContext,
) -> SupportsPolicyEvaluation:
    """Statically assert that ProcessingContext satisfies the protocol."""
    return context
