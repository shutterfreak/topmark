# topmark:header:start
#
#   project      : TopMark
#   file         : base_protocols.py
#   file_relpath : tests/typecheck/processors/base_protocols.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Static structural contracts for processor dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.processors.base import ProcessingContextLike
    from topmark.processors.base import RuntimeConfigLike

__all__ = [
    "verify_processing_context_protocol",
    "verify_runtime_config_protocol",
]


def verify_runtime_config_protocol(
    config: FrozenConfig,
) -> RuntimeConfigLike:
    """Statically assert that frozen config exposes processor render settings."""
    return config


def verify_processing_context_protocol(
    context: ProcessingContext,
) -> ProcessingContextLike:
    """Statically assert that processing context exposes processor dependencies."""
    return context
