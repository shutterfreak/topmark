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

from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence, runtime_checkable


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
        lines (list[str]): Source lines to expose. The list is not copied; the
            caller retains ownership and must not mutate it while the view is used.
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
class HeaderView:
    """Structured view of the *existing* header detected by the scanner.

    Attributes:
        range (tuple[int, int] | None): Inclusive ``(start, end)`` line indices
            of the detected header block within the file, or ``None`` when absent.
        lines (Sequence[str] | None): Header lines exactly as found (keepends), or
            ``None`` when not captured.
        block (str | None): Concatenated header text (``"".join(lines)``), or
            ``None`` when not captured.
        mapping (dict[str, str] | None): Parsed field dictionary extracted from
            the header, or ``None`` when parsing was not performed.
        success_count (int): The number of header lines that were successfully
            parsed and added to the ``mapping`` dictionary. Defaults to 0.
        error_count (int): The number of header lines that were malformed (e.g.,
            missing a colon, or having an empty field name). Defaults to 0.

    Notes:
        This view is intentionally lightweight and does not implement
        `Releasable`. The runner prunes heavy buffers elsewhere.
    """

    range: tuple[int, int] | None
    lines: Sequence[str] | None
    block: str | None
    mapping: dict[str, str] | None
    success_count: int = 0
    error_count: int = 0


@dataclass(slots=True)
class BuilderView:
    """Structured view of field dictionaries produced by the builder step.

    Attributes:
        builtins (dict[str, str] | None): Derived built-in fields (e.g., file, relpath).
        selected (dict[str, str] | None): The subset (and overrides) selected for rendering,
            aligned with the configuration's ``header_fields`` order.

    Notes:
        This view is intentionally lightweight and does not implement
        `Releasable`.
    """

    builtins: dict[str, str] | None
    selected: dict[str, str] | None


@dataclass(slots=True)
class RenderView:
    """Structured view of the *expected* header produced by the renderer.

    Attributes:
        lines (Sequence[str] | None): Rendered header lines (keepends), or
            ``None`` when not rendered.
        block (str | None): Concatenated rendered header text, or ``None``.

    Notes:
        Large buffers may be pruned by the runner by setting ``lines``/``block`` to ``None``
        rather than via ``release()``.
    """

    lines: Sequence[str] | None
    block: str | None


@dataclass(slots=True)
class UpdatedView:
    """View of the pipeline's updated file image.

    ``lines`` may be a sequence (e.g., ``list[str]``) or a lazy iterable
    (e.g., a generator composing a three-segment view) to avoid materializing
    large buffers up-front.

    Attributes:
        lines (Sequence[str] | Iterable[str] | None): Updated file image as
            a sequence or iterable of lines, or ``None`` when no update was
            produced.

    Notes:
        Pruning is handled by the runner, which may set ``lines`` to ``None`` to save memory.
        This view is not ``Releasable`` because it may be an iterator owned by upstream logic.
    """

    lines: Sequence[str] | Iterable[str] | None


@dataclass(slots=True)
class DiffView:
    """Unified diff view for CLI/CI consumption.

    Attributes:
        text (str | None): Unified diff as a single string, or ``None`` when
            no diff was generated.

    Notes:
        Pruning is done by nulling ``text`` in the runner.
    """

    text: str | None
