# topmark:header:start
#
#   project      : TopMark
#   file         : stripper.py
#   file_relpath : src/topmark/pipeline/steps/stripper.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pipeline step that removes the TopMark header (view‑based).

The step uses the scanner‑detected header span when available
(``ctx.header.range``) and delegates removal to the active header processor.
It sets ``ctx.updated`` with the stripped image (no I/O) and updates
``StripStatus`` to ``READY`` or ``NOT_NEEDED`` accordingly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.pipeline.context import ContentStatus, HeaderStatus, ProcessingContext, StripStatus
from topmark.pipeline.views import UpdatedView

if TYPE_CHECKING:
    from topmark.filetypes.policy import FileTypeHeaderPolicy

logger: TopmarkLogger = get_logger(__name__)


def _reapply_bom_after_strip(lines: list[str], ctx: ProcessingContext) -> list[str]:
    """Re-attach a leading UTF-8 BOM to the first line when the original file had one.

    Unlike the updater's BOM policy (which avoids re-adding a BOM in the presence of a shebang),
    the goal here is round-trip fidelity: if the reader observed a leading BOM originally
    (``ctx.leading_bom is True``), then the stripped image should preserve it as well.
    """
    if ctx.leading_bom is False:
        # No BOM was present in the original file
        return lines

    # The file has a leading BOM

    # If the original file had only a BOM (or stripping removed all content),
    # restore a BOM-only image to preserve round-trip fidelity.
    if not lines:
        # Equivalent to ctx.status.fs == FsStatus.EMPTY_FILE
        return ["\ufeff"]

    # The resulting file is non-empty and the original file had a BOM.
    # Ensure the BOM is at the start of the first line.
    first: str = lines[0]
    if not first.startswith("\ufeff"):
        # Re-attach the BOM to the first line
        out: list[str] = lines[:]
        out[0] = "\ufeff" + first
        return out
    return lines


def strip(ctx: ProcessingContext) -> ProcessingContext:
    """Remove the TopMark header using the processor and known span if available (view‑based).

    Args:
        ctx (ProcessingContext): Pipeline context. Must contain a file image, the
            active header processor, and (optionally) the scanner‑detected header span.

    Returns:
        ProcessingContext: The same context, with ``ctx.updated`` populated when a
            removal occurs and ``StripStatus`` updated to reflect the outcome.

    Notes:
      - Leaves ``HeaderStatus`` untouched (owned by the scanner).
      - Trims a single leading blank line when the header starts at the top of the file
        (handled inside the processor).
    """
    if ctx.status.content != ContentStatus.OK:
        # Respect content policy: do not attempt to strip when content was refused
        ctx.status.strip = StripStatus.NOT_NEEDED
        ctx.add_info(f"Could not strip header from file (status: {ctx.status.content.value}).")
        logger.debug("Stripper: skipping (content status=%s)", ctx.status.content.value)
        return ctx

    if ctx.status.header is HeaderStatus.MISSING:
        ctx.status.strip = StripStatus.NOT_NEEDED
        return ctx
    if ctx.status.header not in [HeaderStatus.EMPTY, HeaderStatus.DETECTED]:
        # No header to be stripped
        ctx.status.strip = StripStatus.FAILED
        return ctx

    if ctx.header_processor is None:
        return ctx

    original_lines: list[str] = list(ctx.iter_file_lines())
    if not original_lines:
        # Empty file
        ctx.status.strip = StripStatus.NOT_NEEDED
        return ctx

    # Prefer the span detected by the scanner; fall back to processor logic otherwise.
    span: tuple[int, int] | None = ctx.header.range if ctx.header else None
    new_lines: list[str]
    removed: tuple[int, int] | None
    new_lines, removed = ctx.header_processor.strip_header_block(
        lines=original_lines,
        span=span,
        newline_style=ctx.newline_style,
        ends_with_newline=ctx.ends_with_newline,
    )
    if removed is None or new_lines == original_lines:
        # Nothing to remove
        ctx.status.strip = StripStatus.NOT_NEEDED
        return ctx

    # Optionally remove a single trailing blank line that TopMark inserted after the header.
    # This restores the pre-insert image and makes insert→strip→insert idempotent.
    try:
        policy: FileTypeHeaderPolicy | None = ctx.file_type.header_policy if ctx.file_type else None
    except Exception:
        policy = None
    if policy and policy.ensure_blank_after_header:
        start: int
        _end: int
        start, _end = removed
        # After removal, the original header start index is where our *own* blank
        # separator would remain (if we previously inserted one). Only drop an
        # *exact* blank line that matches the file's newline style (e.g., "\n" or "\r\n"),
        # and DO NOT drop whitespace-only lines like " \n" — those belong to the user's body.
        if 0 <= start < len(new_lines):
            nxt: str = new_lines[start]
            if nxt == ctx.newline_style:
                logger.debug("stripper: dropped exact blank separator after removed header")
                new_lines.pop(start)

    # If the body after header removal consists only of *exact* blank lines that
    # match the file's newline style (e.g., "\n" or "\r\n"), collapse them.
    # Do NOT collapse whitespace-only lines like " \n" — those belong to the user's body.
    if new_lines and all(ln == ctx.newline_style for ln in new_lines):
        logger.debug("stripper: body is only exact blank lines; collapsing to empty.")
        new_lines = []

    logger.info("Updated file lines: %s", new_lines[:15])
    updated_lines: list[str] = _reapply_bom_after_strip(new_lines, ctx)

    # Preserve original final-newline (FNL) semantics: if the original file did not
    # end with a newline, strip a single trailing newline sequence from the final line
    # of the stripped image. This keeps single-line XML round-trips stable.
    if ctx.ends_with_newline is False and updated_lines:
        # Only trim when you know the original had no final newline
        # (ctx.ends_with_newline is neither None nor True):
        last: str = updated_lines[-1]
        if last.endswith("\r\n"):
            updated_lines[-1] = last[:-2]
        elif last.endswith("\n") or last.endswith("\r"):
            updated_lines[-1] = last[:-1]

    # Normalize trailing blanks conservatively. If we have BOM-only, keep it.
    if updated_lines:
        if len(updated_lines) == 1 and updated_lines[0] == "\ufeff":
            # Case 1: BOM-only image — keep as-is for round-trip fidelity.
            pass
        else:
            # Case 2: If first is BOM and the rest are *exact* blanks, collapse to BOM-only.
            # Case 3: If the stripped image contains only *exact* blank lines (and no BOM),
            #         collapse to truly empty.
            if (
                updated_lines[0].startswith("\ufeff")
                and len(updated_lines) > 1
                # TODO - dedicated strip WS policy:
                # and all(is_pure_spacer(s, policy) for s in updated_lines[1:]
                and all(s == ctx.newline_style for s in updated_lines[1:])
            ):
                # First line is BOM-only, there is at least one trailing line,
                # and everything after is blank: collapse to BOM-only.
                updated_lines = ["\ufeff"]
            # elif all(is_pure_spacer(s, policy) for s in updated_lines):
            # (TODO - dedicated strip WS policy - see commented-out previous line)
            elif all(s == ctx.newline_style for s in updated_lines):
                # Case 4: If *all* lines are blank-like and no BOM, collapse to empty.
                updated_lines = []
            # Case 4: Otherwise, leave as-is (body has non-blank content).
    ctx.updated = UpdatedView(lines=updated_lines)

    # A header was present and removed
    ctx.status.strip = StripStatus.READY
    logger.debug("stripper: removed header lines at span %d..%d", removed[0], removed[1])
    return ctx
