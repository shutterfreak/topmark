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

import codecs
from typing import TYPE_CHECKING

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.pipeline.context import FileStatus, ProcessingContext

if TYPE_CHECKING:
    from topmark.filetypes.policy import FileTypeHeaderPolicy

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
    It uses an incremental UTF-8 decoder for robust text sniffing, detects CRLF even when split
    across reads, and defaults to LF when no newline is observed (e.g., single-line files).

    Args:
        ctx (ProcessingContext): The processing context for the current file.

    Returns:
        ProcessingContext: The same context, updated in place.

    Notes:
        - Sets ``ctx.ends_with_newline`` and populates ``ctx.file_lines``.
        - Sets ``ctx.leading_bom`` when a UTF-8 BOM is present and strips it from the
          in-memory lines.
    """
    # Safeguard: only proceed if the resolver step succeeded
    if ctx.status.file is not FileStatus.RESOLVED:
        # Stop processing if the file cannot be resolved
        return ctx

    # Safeguard: header_processor and file_type have been set in resolver.resolve()
    assert ctx.header_processor, "context.header_processor not defined"
    assert ctx.file_type, "context.file_type not defined"

    # Guard against races: the file may disappear between bootstrap/resolve and read().
    try:
        st_size = ctx.path.stat().st_size
    except FileNotFoundError:
        ctx.status.file = FileStatus.SKIPPED_NOT_FOUND
        logger.warning("%s: File not found: %s", ctx.status.file.value, ctx.path)
        return ctx
    except PermissionError as e:
        ctx.status.file = FileStatus.UNREADABLE
        logger.error("Permission denied reading file %s: %s", ctx.path, e)
        ctx.add_error(f"Permission denied reading file: {e}")
        return ctx

    if st_size == 0:
        logger.warning("Found empty file: %s", ctx.path)
        ctx.add_warning("File is empty.")
        ctx.status.file = FileStatus.EMPTY_FILE
        return ctx

    # Robustly checks if a file is a text file by looking for null bytes and
    # attempting to decode with UTF-8 incrementally to handle multibyte splits.
    # Newline convention detected during the binary/text sniff (\n, \r\n, or \r)
    nl: str | None = None
    try:
        # Sniff the first 4KB to decide "text vs binary" and to detect newline style
        with open(ctx.path, "rb") as bf:
            tail: bytes = b""  # carry 1 byte to detect CRLF across chunk boundaries
            dec: codecs.BufferedIncrementalDecoder = codecs.getincrementaldecoder("utf-8")()
            while True:
                chunk: bytes = bf.read(4096)
                if not chunk:
                    break

                blob: bytes = tail + chunk

                # NUL bytes strongly indicate a binary file; skip further processing
                if b"\0" in blob:
                    ctx.status.file = FileStatus.SKIPPED_NOT_TEXT_FILE
                    logger.warning("%s: Binary (NUL byte): %s", ctx.status.file.value, ctx.path)
                    return ctx

                # Attempt UTF-8 incremental decode; treat failures as non-text
                try:
                    _: str = dec.decode(chunk, final=False)
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
        ctx.add_error(f"Error reading file: {e}")

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
            lines: list[str] = list(f)

        # Normalize a leading UTF‑8 BOM so downstream steps work on BOM‑free text.
        # We remember its presence to re‑attach it at write time in the updater.
        if lines and lines[0].startswith("\ufeff"):
            ctx.leading_bom = True
            lines = lines[:]  # copy to avoid mutating any shared list
            lines[0] = lines[0].lstrip("\ufeff")

        # Record whether the (BOM‑normalized) first line starts with a shebang.
        # This reflects the actual file content, independent of policy.
        if lines and lines[0].startswith("#!"):
            ctx.has_shebang = True

        # Policy: on POSIX the shebang must be the very first two bytes. If this
        # file type supports shebang handling and a BOM was present *before* the
        # shebang, skip processing by default and surface a clear diagnostic.
        policy: FileTypeHeaderPolicy | None = (
            ctx.header_processor.file_type.header_policy if ctx.header_processor.file_type else None
        )
        if ctx.leading_bom and ctx.has_shebang and policy and policy.supports_shebang:
            ctx.add_error(
                "UTF-8 BOM appears before the shebang; POSIX requires '#!' at byte 0. "
                "TopMark will not modify this file by default. Consider removing the BOM "
                "or using a future '--fix-bom' option to resolve this conflict."
            )
            logger.warning(
                "BOM precedes shebang; skipping per policy (file type: %s): %s",
                ctx.file_type.name if ctx.file_type else "<unknown>",
                ctx.path,
            )
            ctx.status.file = FileStatus.SKIPPED_POLICY_BOM_BEFORE_SHEBANG
            return ctx

        # Record whether the file ends with a newline (used when generating patches)
        if len(lines) == 0:
            logger.warning("File has no lines (empty): %s", ctx.path)
            ctx.add_warning("File is empty.")
            ctx.status.file = FileStatus.EMPTY_FILE
            return ctx

        # Check if the last line has a newline
        ctx.ends_with_newline = lines[-1].endswith(("\r\n", "\n", "\r"))

        # Preserve original line endings; each element contains its own terminator
        ctx.file_lines = lines

        # Check if multiple line endings occur in the file
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

        # Override the tentative sniff with the histogram winner whenever you have any line endings:
        # NOTE: will be updated once we implement fixing / updating line endings
        total = sum(hist.values())
        if total > 0 and ctx.dominant_newline:
            ctx.newline_style = ctx.dominant_newline

        # Exit if mixed line endings found in file
        if ctx.mixed_newlines:
            ctx.status.file = FileStatus.SKIPPED_MIXED_LINE_ENDINGS
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
        ctx.add_error(f"Error reading file: {e}")

    logger.warning("%s: File cannot be processed: %s", ctx.status.file.value, ctx.path)
    return ctx
