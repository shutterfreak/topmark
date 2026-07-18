# topmark:header:start
#
#   project      : TopMark
#   file         : result_protocols.py
#   file_relpath : tests/typecheck/pipeline/result_protocols.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Static structural contracts shared by mutable and durable pipeline results."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.engine import SupportsPipelineExitResult
    from topmark.pipeline.outcomes import SupportsOutcomeClassification
    from topmark.pipeline.reporting import SupportsReportFiltering
    from topmark.pipeline.result import ProcessingResult

__all__ = [
    "verify_context_exit_protocol",
    "verify_context_outcome_protocol",
    "verify_context_reporting_protocol",
    "verify_result_exit_protocol",
    "verify_result_outcome_protocol",
    "verify_result_reporting_protocol",
]


def verify_context_exit_protocol(
    context: ProcessingContext,
) -> SupportsPipelineExitResult:
    """Statically assert that mutable contexts support exit-code selection."""
    return context


def verify_result_exit_protocol(
    result: ProcessingResult,
) -> SupportsPipelineExitResult:
    """Statically assert that durable results support exit-code selection."""
    return result


def verify_context_outcome_protocol(
    context: ProcessingContext,
) -> SupportsOutcomeClassification:
    """Statically assert that mutable contexts support outcome classification."""
    return context


def verify_result_outcome_protocol(
    result: ProcessingResult,
) -> SupportsOutcomeClassification:
    """Statically assert that durable results support outcome classification."""
    return result


def verify_context_reporting_protocol(
    context: ProcessingContext,
) -> SupportsReportFiltering:
    """Statically assert that mutable contexts support report filtering."""
    return context


def verify_result_reporting_protocol(
    result: ProcessingResult,
) -> SupportsReportFiltering:
    """Statically assert that durable results support report filtering."""
    return result
