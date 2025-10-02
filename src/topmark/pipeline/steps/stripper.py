# topmark:header:start
#
#   project      : TopMark
#   file         : stripper.py
#   file_relpath : src/topmark/pipeline/steps/stripper.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pipeline step that removes the TopMark header.

The step uses the scanner‑detected header span when available
(``ctx.existing_header_range``) and delegates removal to the active header
processor. It sets ``ctx.updated_file_lines`` only when a removal is performed
and updates ``StripStatus`` to ``READY`` or ``NOT_NEEDED`` accordingly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.pipeline.context import HeaderStatus, ProcessingContext, StripStatus
from topmark.pipeline.policy_whitespace import is_effectively_empty_body, is_pure_spacer

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
    """Remove the TopMark header using the processor and known span if available.

    Args:
        ctx (ProcessingContext): Pipeline context. Must contain file lines, the
            active header processor, and (optionally) the scanner‑detected header span.

    Returns:
        ProcessingContext: The same context, with ``updated_file_lines`` populated
            when a removal occurs and ``StripStatus`` updated to reflect the outcome.

    Notes:
      - Leaves ``HeaderStatus`` untouched (owned by the scanner).
      - Trims a single leading blank line when the header starts at the top of the file
        (handled inside the processor).
    """
    if ctx.status.header is HeaderStatus.MISSING:
        ctx.status.strip = StripStatus.NOT_NEEDED
        return ctx
    if ctx.status.header not in [HeaderStatus.EMPTY, HeaderStatus.DETECTED]:
        # No header to be stripped
        ctx.status.strip = StripStatus.FAILED
        return ctx

    if ctx.header_processor is None:
        return ctx

    lines: list[str] = ctx.file_lines or []
    if not lines:
        # Empty file
        return ctx

    # Prefer the span detected by the scanner; fall back to processor logic otherwise.
    span: tuple[int, int] | None = ctx.existing_header_range
    new_lines: list[str] = []
    removed: tuple[int, int] | None = None
    new_lines, removed = ctx.header_processor.strip_header_block(
        lines=lines,
        span=span,
        newline_style=ctx.newline_style,
        ends_with_newline=ctx.ends_with_newline,
    )
    if removed is None or new_lines == lines:
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
        # After removal, the original header start index is where a spacer would remain.
        if 0 <= start < len(new_lines):
            nxt: str = new_lines[start]
            if is_pure_spacer(nxt, policy):
                logger.debug(
                    "stripper: dropped one trailing pure spacer after removed header "
                    "(ensure_blank_after_header=True)"
                )
                new_lines.pop(start)

    # If the body is effectively empty after stripping, collapse to truly empty here.
    # BOM reattachment (if any) will be handled uniformly below.

    if is_effectively_empty_body(new_lines, policy):
        logger.debug(
            "stripper: body effectively empty after strip (policy-driven); collapsing to empty."
        )
        new_lines = []

    logger.info("Updated file lines: %s", new_lines[:15])
    ctx.updated_file_lines = _reapply_bom_after_strip(new_lines, ctx)

    # Preserve original final-newline (FNL) semantics: if the original file did not
    # end with a newline, strip a single trailing newline sequence from the final line
    # of the stripped image. This keeps single-line XML round-trips stable.
    if ctx.ends_with_newline is False and ctx.updated_file_lines:
        # Only trim when you know the original had no final newline
        # (ctx.ends_with_newline is neither None nor True):
        last: str = ctx.updated_file_lines[-1]
        if last.endswith("\r\n"):
            ctx.updated_file_lines[-1] = last[:-2]
        elif last.endswith("\n") or last.endswith("\r"):
            ctx.updated_file_lines[-1] = last[:-1]

    # Normalize trailing blanks conservatively. If we have BOM-only, keep it.
    if ctx.updated_file_lines:
        if len(ctx.updated_file_lines) == 1 and ctx.updated_file_lines[0] == "\ufeff":
            # Case 1: BOM-only image — keep as-is for round-trip fidelity.
            pass
        else:
            # Case 2: If first is BOM and the rest are blank, collapse to BOM-only.
            # If the stripped image contains only blank lines (and no BOM), collapse to truly empty.
            if (
                ctx.updated_file_lines[0].startswith("\ufeff")
                and len(ctx.updated_file_lines) > 1
                and all(is_pure_spacer(s, policy) for s in ctx.updated_file_lines[1:])
            ):
                # First line is BOM-only, there is at least one trailing line,
                # and everything after is blank: collapse to BOM-only.
                ctx.updated_file_lines = ["\ufeff"]
            elif all(is_pure_spacer(s, policy) for s in ctx.updated_file_lines):
                # Case 3: If *all* lines are blank-like and no BOM, collapse to empty.
                ctx.updated_file_lines = []
            # Case 4: Otherwise, leave as-is (body has non-blank content).

    # A header was present and removed
    ctx.status.strip = StripStatus.READY
    logger.debug(f"stripper: removed header lines at span {removed[0]}..{removed[1]}.")
    return ctx
