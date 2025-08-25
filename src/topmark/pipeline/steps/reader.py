# topmark:header:start
#
#   file         : reader.py
#   file_relpath : src/topmark/pipeline/steps/reader.py
#   project      : TopMark
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

import codecs

from topmark.config.logging import get_logger
from topmark.pipeline.context import FileStatus, ProcessingContext

logger = get_logger(__name__)


def read(ctx: ProcessingContext) -> ProcessingContext:
    r"""Load file lines and detect newline style.

    Preserves native newline conventions and records them in ``ctx.newline_style``.
    Uses an incremental UTF-8 decoder for robust text sniffing across chunk
    boundaries, detects CRLF even when split across reads, and defaults to LF
    ("\n") when no newline is observed (e.g., single-line files). Also sets
    ``ctx.ends_with_newline`` and populates ``ctx.file_lines``.

    Args:
        ctx: The processing context for the current file.

    Returns:
        ProcessingContext: The same context, updated in place.
    """
    # Safeguard: only proceed if the resolver step succeeded
    if ctx.status.file is not FileStatus.RESOLVED:
        # Stop processing if the file cannot be resolved
        return ctx

    if ctx.path.stat().st_size == 0:
        logger.warning("Found empty file: %s", ctx.path)
        ctx.status.file = FileStatus.EMPTY_FILE
        return ctx

    # Robustly checks if a file is a text file by looking for null bytes and
    # attempting to decode with UTF-8 incrementally to handle multibyte splits.
    # Newline convention detected during the binary/text sniff (\n, \r\n, or \r)
    nl: str | None = None
    try:
        # Sniff the first 4KB to decide "text vs binary" and to detect newline style
        with open(ctx.path, "rb") as bf:
            tail = b""  # carry 1 byte to detect CRLF across chunk boundaries
            dec = codecs.getincrementaldecoder("utf-8")()
            while True:
                chunk = bf.read(4096)
                if not chunk:
                    break

                blob = tail + chunk

                # NUL bytes strongly indicate a binary file; skip further processing
                if b"\0" in blob:
                    ctx.status.file = FileStatus.SKIPPED_NOT_TEXT_FILE
                    logger.warning("%s: Binary (NUL byte): %s", ctx.status.file.value, ctx.path)
                    return ctx

                # Attempt UTF-8 incremental decode; treat failures as non-text
                try:
                    _ = dec.decode(chunk, final=False)
                except UnicodeDecodeError:
                    ctx.status.file = FileStatus.SKIPPED_NOT_TEXT_FILE
                    logger.warning("%s: Not UTF-8 text: %s", ctx.status.file.value, ctx.path)
                    return ctx

                # Choose a newline style heuristic:
                # - Prefer CRLF if present
                # - Else prefer lone CR if present (classic Mac)
                # - Else prefer LF if present
                # If no newline is seen in the sniffed chunks, handle later.
                if b"\r\n" in blob:
                    nl = "\r\n"
                    break
                elif b"\r" in blob and b"\n" not in blob:
                    # Lone CR detected and no LF anywhere in the blob
                    nl = "\r"
                    # Do not break; continue scanning in case CRLF appears later
                elif b"\n" in blob:
                    # LF seen (possibly mixed), tentatively set to LF unless CRLF found later
                    if nl is None:
                        nl = "\n"

                # Carry last byte to join with next chunk for CRLF detection
                tail = chunk[-1:]

    except FileNotFoundError:
        ctx.status.file = FileStatus.SKIPPED_NOT_FOUND
        logger.warning("%s: File not found: %s", ctx.status.file.value, ctx.path)

    except Exception as e:  # Log and attach diagnostic; continue without raising
        ctx.status.file = FileStatus.UNREADABLE
        logger.error("Error reading file %s: %s", ctx.path, e)
        ctx.diagnostics.append(f"Error reading file: {e}")

    if nl:
        # Store the line end style
        ctx.newline_style = nl
    else:
        # No newline detected across sniffed chunks; assume LF and proceed.
        # This allows single-line files without terminators to be processed safely.
        ctx.newline_style = "\n"

    logger.debug("No line end detected for %s; defaulting to LF (\\n)", ctx.path)
    # Read the full content as text using the detected newline convention
    try:
        with ctx.path.open(
            "r",
            encoding="utf-8",
            errors="replace",
            newline="",
        ) as f:
            lines = list(f)

        # Record whether the file ends with a newline (used when generating patches)
        if len(lines) == 0:
            logger.warning("File has no lines (empty): %s", ctx.path)
            ctx.status.file = FileStatus.EMPTY_FILE
            return ctx

        # Check if the last line has a newline
        ctx.ends_with_newline = lines[-1].endswith(("\r\n", "\n", "\r"))

        # Preserve original line endings; each element contains its own terminator
        ctx.file_lines = lines

        ctx.status.file = FileStatus.RESOLVED
        logger.debug(
            "Reader step completed for %s, detected newline style: %r, ends_with_newline: %s",
            ctx.path,
            ctx.newline_style,
            ctx.ends_with_newline,
        )
        logger.trace(
            "File '%s' (file status: %s) - read_file_lines: lines: %d",
            ctx.path,
            ctx.status.file.value,
            len(ctx.file_lines) if ctx.file_lines else 0,
        )

        return ctx

    except Exception as e:  # Log and attach diagnostic; continue without raising
        ctx.status.file = FileStatus.UNREADABLE
        logger.error("Error reading file %s: %s", ctx.path, e)
        ctx.diagnostics.append(f"Error reading file: {e}")

    logger.warning("%s: File cannot be processed: %s", ctx.status.file.value, ctx.path)
    return ctx
