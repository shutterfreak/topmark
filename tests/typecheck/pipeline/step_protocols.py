# topmark:header:start
#
#   project      : TopMark
#   file         : step_protocols.py
#   file_relpath : tests/typecheck/pipeline/step_protocols.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Static structural contracts for pipeline steps."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.protocols import Step
    from topmark.pipeline.steps.base import BaseStep

__all__ = ["verify_base_step_protocol"]


def verify_base_step_protocol(
    step: BaseStep,
) -> Step[ProcessingContext]:
    """Statically assert that the common step lifecycle satisfies Step."""
    return step
