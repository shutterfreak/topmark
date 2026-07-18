# topmark:header:start
#
#   project      : TopMark
#   file         : writer_protocols.py
#   file_relpath : tests/typecheck/pipeline/writer_protocols.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Static structural contracts for writer sinks."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.pipeline.steps.writer import AtomicFileSink
    from topmark.pipeline.steps.writer import InplaceFileSink
    from topmark.pipeline.steps.writer import StdoutSink
    from topmark.pipeline.steps.writer import WriteSink

__all__ = [
    "verify_atomic_sink_protocol",
    "verify_inplace_sink_protocol",
    "verify_stdout_sink_protocol",
]


def verify_stdout_sink_protocol(
    sink: StdoutSink,
) -> WriteSink:
    """Statically assert that the stdout sink satisfies the writer contract."""
    return sink


def verify_inplace_sink_protocol(
    sink: InplaceFileSink,
) -> WriteSink:
    """Statically assert that the in-place sink satisfies the writer contract."""
    return sink


def verify_atomic_sink_protocol(
    sink: AtomicFileSink,
) -> WriteSink:
    """Statically assert that the atomic sink satisfies the writer contract."""
    return sink
