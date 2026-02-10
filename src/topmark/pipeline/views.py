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
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


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


@dataclass(slots=True, eq=False)
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

    _lines: list[str] | None  # use a leading underscore to signal “internal”

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


@dataclass(slots=True)
class HeaderView(Releasable):
    """Structured view of the *existing* header detected by the scanner.

    Attributes:
        range: Inclusive ``(start, end)`` line indices of the detected header block within the
            file, or ``None`` when absent.
        lines: Header lines exactly as found (keepends), or ``None`` when not captured.
        block: Concatenated header text (``"".join(lines)``), or ``None`` when not captured.
        mapping: Parsed field dictionary extracted from the header, or ``None`` when parsing was
            not performed.
        success_count: The number of header lines that were successfully parsed and added to the
            ``mapping`` dictionary. Defaults to 0.
        error_count: The number of header lines that were malformed (e.g., missing a colon, or
            having an empty field name). Defaults to 0.
    """

    range: tuple[int, int] | None
    lines: Sequence[str] | None
    block: str | None
    mapping: dict[str, str] | None
    success_count: int = 0
    error_count: int = 0

    def release(self) -> None:
        """Release header buffers (lines, block, mapping)."""
        self.lines = None
        self.block = None
        self.mapping = None


@dataclass(slots=True)
class BuilderView(Releasable):
    """Structured view of field dictionaries produced by the builder step.

    Attributes:
        builtins: Derived built-in fields (e.g., file, relpath).
        selected: The subset (and overrides) selected for rendering, aligned with the
            configuration's ``header_fields`` order.

    Notes:
        This view is intentionally lightweight and does not implement `Releasable`.
    """

    builtins: dict[str, str] | None
    selected: dict[str, str] | None

    def release(self) -> None:
        """Release the diff payload to reduce memory usage."""
        self.builtins = None
        self.selected = None


@dataclass(slots=True)
class RenderView(Releasable):
    """Structured view of the *expected* header produced by the renderer.

    Attributes:
        lines: Rendered header lines (keepends), or ``None`` when not rendered.
        block: Concatenated rendered header text, or ``None``.

    Notes:
        Large buffers may be pruned by the runner by setting ``lines``/``block`` to ``None``
        rather than via ``release()``.
    """

    lines: Sequence[str] | None
    block: str | None

    def release(self) -> None:
        """Release the renderer payload to reduce memory usage."""
        self.lines = None
        self.block = None


@dataclass(slots=True)
class UpdatedView(Releasable):
    """View of the pipeline's updated file image.

    ``lines`` may be a sequence (e.g., ``list[str]``) or a lazy iterable
    (e.g., a generator composing a three-segment view) to avoid materializing
    large buffers up-front.

    Attributes:
        lines: Updated file image as a sequence or iterable of lines, or ``None`` when no update
            was produced.

    Notes:
        Pruning is handled by the runner, which may set ``lines`` to ``None`` to save memory.
        This view is not ``Releasable`` because it may be an iterator owned by upstream logic.
    """

    lines: Sequence[str] | Iterable[str] | None

    def release(self) -> None:
        """Release the updated file image payload to reduce memory usage."""
        self.lines = None


@dataclass(slots=True)
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


@dataclass(slots=True)
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

    def release_all(self) -> None:
        """Release all non-None views safely (idempotent)."""
        if self.image:
            self.image.release()
        if self.header:
            self.header.release()
        if self.build:
            self.build.release()
        if self.render:
            self.render.release()
        if self.updated:
            self.updated.release()
        if self.diff:
            self.diff.release()
        # HeaderView is intentionally light; no release.

    def as_dict(self) -> dict[str, object]:
        """Short machine-friendly summary; avoid heavy text blobs."""
        return {
            "image_lines": self.image.line_count() if self.image else 0,
            "header_range": getattr(self.header, "range", None),
            "header_fields": (self.header.mapping or {}) if self.header else None,
            "build_selected": (self.build.selected if self.build else None),
            "render_line_count": (
                len(self.render.lines) if (self.render and self.render.lines is not None) else 0
            ),
            "updated_has_lines": self.updated is not None and self.updated.lines is not None,
            "diff_present": bool(self.diff and self.diff.text),
        }
