# topmark:header:start
#
#   project      : TopMark
#   file         : views.py
#   file_relpath : src/topmark/pipeline/views.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""View abstractions for large, phase-scoped pipeline data.

This module defines lightweight, typed "views" that expose file and header data
without committing to a concrete backing representation. Implementations can be
list-backed today and evolve to memory-mapped or generator-based forms later,
while keeping step contracts stable and memory usage low.

The views are intentionally minimal: callers iterate or count lines instead of
materializing whole images, and rich blocks/mappings are grouped in small
dataclasses per phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from typing import Protocol
from typing import runtime_checkable

from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator
    from collections.abc import Mapping
    from collections.abc import Sequence

    from topmark.core.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)


class ViewSlot(str, Enum):
    """Named view slots that pipeline steps may consume.

    The values are intentionally plain strings so they remain stable in logs,
    tests, and machine-oriented diagnostics if exposed later.
    """

    IMAGE = "image"
    HEADER = "header"
    BUILD = "build"
    RENDER = "render"
    UPDATED = "updated"
    DIFF = "diff"


@runtime_checkable
class Releasable(Protocol):
    """Protocol for views that can release large in-memory buffers.

    This optional lifecycle hook allows memory-heavy views to discard their
    materialized state (e.g., lists of lines) after downstream steps no longer
    need them. The pipeline runner invokes ``release()`` when pruning is enabled
    to keep peak memory usage low.

    Implementers should make ``release()`` idempotent: calling it multiple times
    must be safe and should not raise. Views that do not hold large buffers can
    implement a no-op ``release()`` to satisfy the protocol if needed.

    Examples:
        * ``ListFileImageView`` clears its backing ``list[str]`` reference.
        * A memory-mapped view could close or unmap its file handle.
    """

    def release(self) -> None:
        """Release any materialized buffers to reduce memory usage."""
        ...


# Keep Protocol explicit so Pyright treats this as a structural protocol,
# not as a nominal subclass of Releasable.
class FileImageView(Releasable, Protocol):
    """Protocol for read-only access to a file's logical lines.

    ``FileImageView`` extends `Releasable` so implementations must provide
    a ``release()`` method that frees materialized buffers when called by the
    pipeline runner during pruning.
    """

    def line_count(self) -> int:
        """Return the number of logical lines in the file image.

        Returns:
            int: Total number of lines available via ``iter_lines()``.
        """
        ...

    def iter_lines(self) -> Iterable[str]:
        r"""Iterate the file's logical lines, preserving original line endings.

        Returns:
            Iterable[str]: An iterator over the file's lines. The iterator
            must yield strings exactly as they appear in the source (e.g.,
            with ``\n``/``\r\n`` kept as read).
        """
        ...


@dataclass(kw_only=True, slots=True, eq=False)
class ListFileImageView:
    """List-backed ``FileImageView`` implementation (and ``Releasable``).

    This view wraps an in-memory ``list[str]`` where each element represents a
    logical line including its original newline sequence (``keepends`` semantics).
    Calling `release` discards the backing list to free memory; subsequent
    iteration yields an empty sequence.

    Args:
        lines: Source lines to expose. The list is not copied; the caller retains ownership and
            must not mutate it while the view is used.
    """

    _lines: list[str] | None  # use a leading underscore to signal "internal"

    def __init__(self, lines: list[str]) -> None:
        self._lines: list[str] | None = lines

    def line_count(self) -> int:
        """Return the number of lines in the underlying list.

        Returns:
            int: Total line count.
        """
        return 0 if self._lines is None else len(self._lines)

    def iter_lines(self) -> Iterable[str]:
        """Iterate lines from the underlying list without copying.

        Returns:
            Iterable[str]: An iterator over the stored lines.
        """
        return iter(self._lines or ())

    # New:
    def release(self) -> None:
        """Release materialized lines."""
        self._lines = None


@dataclass(kw_only=True, slots=True)
class HeaderView(Releasable):
    """Structured view of the *existing* header detected by the scanner.

    Attributes:
        range: Inclusive ``(start, end)`` line indices of the detected header block within the
            file, or ``None`` when absent.
        lines: Header lines exactly as found (keepends), or ``None`` when not captured.
        block: Concatenated header text (``"".join(lines)``), or ``None`` when not captured.
        mapping: Parsed field mapping extracted from the header, or ``None`` when parsing was
            not performed.
        success_count: The number of header lines that were successfully parsed and added to the
            ``mapping``. Defaults to 0.
        error_count: The number of header lines that were malformed (e.g., missing a colon, or
            having an empty field name). Defaults to 0.
    """

    range: tuple[int, int] | None
    lines: Sequence[str] | None
    block: str | None
    mapping: Mapping[str, str] | None
    success_count: int = 0
    error_count: int = 0

    def release(self) -> None:
        """Release header buffers (lines, block, mapping)."""
        self.lines = None
        self.block = None
        self.mapping = None


@dataclass(kw_only=True, slots=True)
class BuilderView(Releasable):
    """Structured view of field dictionaries produced by the builder step.

    Attributes:
        builtins: Derived built-in fields (e.g., file, relpath).
        selected: The subset (and overrides) selected for rendering, aligned with the
            configuration's ``header_fields`` order.

    Notes:
        The contained mappings are exposed read-only through abstract mapping
        types. Calling `release()` clears the references to allow pruning.
    """

    builtins: Mapping[str, str] | None
    selected: Mapping[str, str] | None

    def release(self) -> None:
        """Release the diff payload to reduce memory usage."""
        self.builtins = None
        self.selected = None


@dataclass(kw_only=True, slots=True)
class RenderView(Releasable):
    """Structured view of the *expected* header produced by the renderer.

    Attributes:
        lines: Rendered header lines (keepends), or ``None`` when not rendered.
        block: Concatenated rendered header text, or ``None``.

    Notes:
        Large buffers may be pruned by calling `release()`, which clears
        ``lines`` and ``block``.
    """

    lines: Sequence[str] | None
    block: str | None

    def release(self) -> None:
        """Release the renderer payload to reduce memory usage."""
        self.lines = None
        self.block = None


@runtime_checkable
class UpdatedContent(Protocol):
    """Repeatable updated-file content abstraction.

    Implementations expose updated file lines without requiring callers to own
    one eagerly materialized ``list[str]``. Unlike a bare iterator, each call to
    `iter_lines` must return a fresh iterator so comparer, patcher, and writer
    can consume the same updated content independently.
    """

    def iter_lines(self) -> Iterable[str]:
        """Iterate updated file lines repeatably."""
        ...

    def __iter__(self) -> Iterator[str]:
        """Iterate updated file lines repeatably."""
        ...


@dataclass(frozen=True, kw_only=True, slots=True)
class SegmentUpdatedContent:
    """Segment-backed repeatable updated file content.

    The content is represented as ordered line segments, typically slices of the
    original image plus a rendered-header segment. The segments themselves are
    not copied by this class. Each iteration walks the segments in order.

    Attributes:
        segments: Ordered, repeatable line segments composing the updated image.
    """

    segments: tuple[Sequence[str], ...]

    def iter_lines(self) -> Iterable[str]:
        """Iterate the composed updated image without materializing it as one list.

        Returns:
            Iterable[str]: Updated lines from every segment in order.
        """
        return iter(self)

    def __iter__(self) -> Iterator[str]:
        """Iterate the composed updated image as a repeatable iterable.

        Yields:
            str: Updated lines from every segment in order.
        """
        for segment in self.segments:
            yield from segment


def compose_updated_content(*segments: Sequence[str]) -> SegmentUpdatedContent:
    """Create a repeatable segment-backed updated-content view.

    Args:
        *segments: Ordered line segments. Empty segments are retained only when
            all segments are empty so an explicitly empty updated image remains
            representable.

    Returns:
        SegmentUpdatedContent: Repeatable content composed from the supplied
        segments.
    """
    return SegmentUpdatedContent(segments=tuple(segments))


@dataclass(kw_only=True, slots=True)
class UpdatedView(Releasable):
    """View of the pipeline's updated file image.

    ``lines`` may be a sequence or an `UpdatedContent` implementation. Bare
    iterables remain accepted for backward compatibility, but repeatable
    `UpdatedContent` is preferred for pipeline-generated updates.

    Attributes:
        lines: Updated file image as a sequence or iterable of lines, or ``None`` when no update
            was produced.

    Notes:
        Pruning is handled by calling `release()`, which clears the updated file
        image reference. Pipeline-generated lazy content should be repeatable;
        arbitrary caller-provided iterables may still be single-pass.
    """

    lines: UpdatedContent | Sequence[str] | None

    def release(self) -> None:
        """Release the updated file image payload to reduce memory usage."""
        self.lines = None


@dataclass(kw_only=True, slots=True)
class DiffView(Releasable):
    """Unified diff view for CLI/CI consumption.

    Attributes:
        text: Unified diff as a single string, or ``None`` when no diff was generated.

    Notes:
        Pruning is done by calling ``release()``, which nulls ``text`` to free memory.
    """

    text: str | None

    def release(self) -> None:
        """Release the diff payload to reduce memory usage."""
        self.text = None


@dataclass(kw_only=True, slots=True)
class Views:
    """Bundle of phase-scoped, releasable views for a single file.

    Notes:
        The bundle itself provides `release_all()` to prune memory after a run.
        Individual views remain responsible for their own `release()` behavior.
    """

    image: FileImageView | None = None
    header: HeaderView | None = None
    build: BuilderView | None = None
    render: RenderView | None = None
    updated: UpdatedView | None = None
    diff: DiffView | None = None

    def release_all(
        self,
    ) -> None:
        """Release all non-None views safely (idempotent)."""
        self.release_image()
        self.release_header()
        self.release_build()
        self.release_render()
        self.release_updated()
        self.release_diff()

    def release_image(self) -> None:
        """Release the original file image view when it is no longer needed."""
        if self.image:
            self.image.release()

    def release_header(self) -> None:
        """Release detected-header payloads when they are no longer needed."""
        if self.header:
            self.header.release()

    def release_build(self) -> None:
        """Release builder payloads when they are no longer needed."""
        if self.build:
            self.build.release()

    def release_render(self) -> None:
        """Release rendered-header payloads when they are no longer needed."""
        if self.render:
            self.render.release()

    def release_updated(self) -> None:
        """Release updated-file payloads when they are no longer needed."""
        if self.updated:
            self.updated.release()

    def release_diff(self) -> None:
        """Release diff payloads when they are no longer needed."""
        if self.diff:
            self.diff.release()

    def release_consumed(
        self,
        *,
        remaining_view_consumers: set[ViewSlot],
        keep_diff_view: bool = False,
    ) -> None:
        """Release views that no remaining pipeline step declares as consumed.

        Args:
            remaining_view_consumers: View slots consumed by steps that have not run yet.
            keep_diff_view: Whether to preserve the diff view for callers that render it after the
                pipeline completes.
        """
        if ViewSlot.IMAGE not in remaining_view_consumers:
            self.release_image()

        if ViewSlot.HEADER not in remaining_view_consumers:
            self.release_header()

        if ViewSlot.BUILD not in remaining_view_consumers:
            self.release_build()

        if ViewSlot.RENDER not in remaining_view_consumers:
            self.release_render()

        if ViewSlot.UPDATED not in remaining_view_consumers:
            self.release_updated()

        if not keep_diff_view and ViewSlot.DIFF not in remaining_view_consumers:
            self.release_diff()

    def as_dict(self) -> dict[str, object]:
        """Short machine-friendly summary; avoid heavy text blobs."""
        return {
            "image_lines": self.image.line_count() if self.image else 0,
            "header_range": getattr(self.header, "range", None),
            "header_fields": dict(self.header.mapping or {}) if self.header else None,
            "build_selected": dict(self.build.selected or {}) if self.build else None,
            "render_line_count": (
                len(self.render.lines) if (self.render and self.render.lines is not None) else 0
            ),
            "updated_has_lines": self.updated is not None and self.updated.lines is not None,
            "diff_present": bool(self.diff and self.diff.text),
        }
