# topmark:header:start
#
#   project      : TopMark
#   file         : adapters.py
#   file_relpath : src/topmark/pipeline/adapters.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Adapters bridging between high-level ProcessingContext and lightweight view protocols.

This module provides helper classes and functions that adapt a full
[`topmark.pipeline.context.ProcessingContext`][] into protocol-compatible
view objects such as [`topmark.filetypes.base.PreInsertContextView`][].
These adapters allow downstream components like InsertChecker or other
file-type-specific validation utilities to operate without depending on the
entire pipeline internals.

The design ensures a stable and memory-efficient interface by exposing only
the minimal attributes or iterators required for read-only inspection of
file contents and metadata.

All adapters defined here are intentionally lightweight and immutable within
their lifecycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from topmark.filetypes.base import FileType
    from topmark.pipeline.context import ProcessingContext
    from topmark.pipeline.processors.base import HeaderProcessor


# --- Adapter for PreInsertContextView (streaming-friendly) -----------
class PreInsertViewAdapter:
    """Adapter that exposes a ProcessingContext as a PreInsertContextView.

    This class extracts only the fields required by the
    [`topmark.filetypes.base.PreInsertContextView`][] protocol and
    presents them through lightweight, read-only attributes.

    Attributes:
        lines (Iterable[str]): Streaming access to the file lines as provided
            by the ProcessingContext image view.
        newline_style (str): Detected newline style ("LF", "CR", "CRLF").
        header_processor (HeaderProcessor | None): The file-type-specific HeaderProcessor instance.
        file_type (FileType | None): The resolved FileType instance or ``None`` if unresolved.

    Args:
        ctx (ProcessingContext): The processing context to wrap.

    """

    lines: Iterable[str]
    newline_style: str
    header_processor: HeaderProcessor | None
    file_type: FileType | None

    def __init__(self, ctx: ProcessingContext) -> None:
        self.lines: Iterable[str] = ctx.iter_image_lines()
        self.newline_style: str = ctx.newline_style
        self.header_processor: HeaderProcessor | None = ctx.header_processor
        self.file_type: FileType | None = ctx.file_type

    def __repr__(self) -> str:
        """Return a developer-friendly string representation of the adapter.

        Returns:
            str: A concise description including file type and newline style.
        """
        return (
            f"<PreInsertViewAdapter lines={type(self.lines).__name__} "
            f"newline_style={self.newline_style!r} "
            f"file_type={getattr(self.file_type, 'name', None)!r}>"
        )


def as_sequence(lines: Sequence[str] | Iterable[str] | None) -> list[str]:
    """Convert an iterable or sequence of lines into a list.

    This utility ensures that downstream components expecting a concrete
    ``list[str]`` receive one, while gracefully handling ``None`` and
    already-list inputs without unnecessary copying.

    Args:
        lines (Sequence[str] | Iterable[str] | None): The source of line
            strings, which may be a list, tuple, generator, or ``None``.

    Returns:
        list[str]: A list of line strings. Returns an empty list when
        ``lines`` is ``None``.
    """
    if lines is None:
        return []
    return list(lines) if not isinstance(lines, list) else lines
