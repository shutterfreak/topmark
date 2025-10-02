# topmark:header:start
#
#   project      : TopMark
#   file         : reader.py
#   file_relpath : src/topmark/pipeline/steps/reader.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

r"""File reader step for the TopMark pipeline.

This step determines whether the target is a UTF-8 text file, detects the
newline convention (LF, CRLF, or CR), and loads the file lines while preserving
original line endings. It updates the processing context with the detected
newline style, whether the file ends with a newline, and the raw lines for
subsequent steps.

Implementation details:
  * Uses an incremental UTF-8 decoder to avoid false negatives when multibyte
    sequences span chunk boundaries during the binary/text sniff.
  * Detects CRLF robustly across read chunk boundaries by carrying a 1-byte tail,
    preferring CRLF over LF and CR when both appear.
  * If no newline is observed during sniffing (e.g., single-line files), defaults
    to "\n" and proceeds, rather than skipping the file.
"""

from __future__ import annotations

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.pipeline.context import (
    ContentStatus,
    FsStatus,
    ProcessingContext,
    may_proceed_to_read,
)

logger: TopmarkLogger = get_logger(__name__)


def _newline_histogram(lines: list[str]) -> dict[str, int]:
    hist: dict[str, int] = {"\n": 0, "\r\n": 0, "\r": 0}
    for ln in lines[:-1]:
        if ln.endswith("\r\n"):
            hist["\r\n"] += 1
        elif ln.endswith("\n"):
            hist["\n"] += 1
        elif ln.endswith("\r"):
            hist["\r"] += 1
    # Last line may or may not end with a newline
    if lines:
        last: str = lines[-1]
        if last.endswith("\r\n"):
            hist["\r\n"] += 1
        elif last.endswith("\n"):
            hist["\n"] += 1
        elif last.endswith("\r"):
            hist["\r"] += 1
    return hist


def read(ctx: ProcessingContext) -> ProcessingContext:
    """Loads file lines and detects newline style.

    This function preserves native newline conventions and records them in ``ctx.newline_style``.
    It assumes the sniffer has already performed existence, permission, binary, BOM/shebang,
    and mixed-newlines policy checks.

    Args:
        ctx (ProcessingContext): The processing context for the current file.

    Returns:
        ProcessingContext: The same context, updated in place.

    Notes:
        - Assumes `sniffer.sniff()` has already handled existence, permissions,
          binary detection, BOM/shebang ordering policy, and mixed-newlines policy.
        - Sets `ctx.file_lines` (keepends), `ctx.ends_with_newline`, and a precise
          newline histogram; updates `ctx.newline_style` to the dominant style if observed.
    """
    if not may_proceed_to_read(ctx):
        return ctx

    # Safeguard: header_processor and file_type have been set in resolver.resolve()
    assert ctx.header_processor, "context.header_processor not defined"
    assert ctx.file_type, "context.file_type not defined"

    # Sniffer has already performed existence/permission checks, binary sniff,
    # BOM/shebang ordering policy, and a quick newline histogram. At this point
    # we load the full file as text and compute precise metadata.

    try:
        with ctx.path.open(
            "r",
            encoding="utf-8",
            errors="replace",
            newline="",
        ) as f:
            lines: list[str] = list(f)

        # Normalize a leading UTF‑8 BOM so downstream steps work on BOM‑free text.
        # We remember its presence to re‑attach it at write time in the updater.
        if lines and lines[0].startswith("\ufeff"):
            if not ctx.leading_bom:
                ctx.leading_bom = True
            lines = lines[:]  # copy to avoid mutating any shared list
            lines[0] = lines[0].lstrip("\ufeff")
            # For a BOM-only file, lines == [""], so it doesn’t take the empty-file branch.
            # Downstream, an empty "" line can look like “body exists” to spacing logic.

        # If no lines, or BOM-only (single empty logical line after BOM strip), mark empty.
        if len(lines) == 0 or (len(lines) == 1 and lines[0] == ""):
            # Edge case: file truncated to 0 bytes between sniff and read.
            # Mirror sniffer semantics for consistency.
            ctx.file_lines = []
            ctx.ends_with_newline = False
            ctx.status.fs = FsStatus.EMPTY
            # NOTE: real zero-length files already marked EMPTY in sniffer
            return ctx

        # Record whether the file ends with a newline (used when generating patches)
        ctx.ends_with_newline = lines[-1].endswith(("\r\n", "\n", "\r"))

        # Preserve original line endings; each element contains its own terminator
        ctx.file_lines = lines

        # Compute detailed newline histogram
        hist: dict[str, int] = _newline_histogram(lines)
        ctx.newline_hist = {k: v for k, v in hist.items() if v > 0}
        total: int = sum(hist.values())
        if total > 0:
            dom_nl: str
            dom_cnt: int
            dom_nl, dom_cnt = max(hist.items(), key=lambda kv: kv[1])
            ctx.dominant_newline = dom_nl if dom_cnt > 0 else None
            ctx.dominance_ratio = (dom_cnt / total) if dom_cnt else 0.0
        else:
            ctx.dominant_newline = None
            ctx.dominance_ratio = None

        ctx.mixed_newlines = sum(1 for v in hist.values() if v > 0) >= 2

        logger.debug(
            "sniff nl=%r, hist=%s, dominant=%r, mixed=%s",
            ctx.newline_style,
            ctx.newline_hist,
            ctx.dominant_newline,
            ctx.mixed_newlines,
        )

        # Finalize newline style based on full-text histogram:
        # (sniffer’s value is tentative and used only for early diagnostics)
        # NOTE: will be updated once we implement fixing / updating line endings
        total = sum(hist.values())
        if total > 0 and ctx.dominant_newline:
            ctx.newline_style = ctx.dominant_newline

        # # Option: Update the newline_style to the dominant newline if any
        # if ctx.dominant_newline:
        #     ctx.newline_style = ctx.dominant_newline

        # Exit if mixed line endings found in file
        if ctx.mixed_newlines:
            ctx.status.content = ContentStatus.SKIPPED_MIXED_LINE_ENDINGS
            lf: int = ctx.newline_hist.get("\n", 0)
            crlf: int = ctx.newline_hist.get("\r\n", 0)
            cr: int = ctx.newline_hist.get("\r", 0)
            ctx.add_error(
                f"Mixed line endings detected (LF={lf}, CRLF={crlf}, CR={cr}). "
                "Strict policy refuses to process mixed files."
            )
            logger.warning(
                "Strict policy: mixed line endings (LF=%d, CRLF=%d, CR=%d) – skipping: %s",
                lf,
                crlf,
                cr,
                ctx.path,
            )
            return ctx

        ctx.status.content = ContentStatus.OK
        logger.debug(
            "Reader step completed for %s, detected newline style: %r, ends_with_newline: %s",
            ctx.path,
            ctx.newline_style,
            ctx.ends_with_newline,
        )
        logger.trace(
            "File '%s' (content status: %s) - read_file_lines: lines: %d",
            ctx.path,
            ctx.status.content.value,
            len(ctx.file_lines) if ctx.file_lines else 0,
        )

        return ctx

    except Exception as e:  # Log and attach diagnostic; continue without raising
        ctx.status.content = ContentStatus.UNREADABLE
        logger.error("Error reading file %s: %s", ctx.path, e)
        ctx.add_error(f"Error reading file: {e}")

    logger.warning(
        "%s: File cannot be processed: %s",
        ctx.status.content.value,
        ctx.path,
    )
    return ctx
