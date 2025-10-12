# topmark:header:start
#
#   project      : TopMark
#   file         : sniffer.py
#   file_relpath : src/topmark/pipeline/steps/sniffer.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""File sniffer step for the TopMark pipeline.

This step performs lightweight pre-read analysis to annotate the processing
context with characteristics of the target file, including:
  * early existence/permission checks (incl. EMPTY_FILE)
  * fast binary sniff (NUL) and strict UTF-8 validation
  * BOM + shebang policy (BOM-before-shebang skip)
  * quick newline histogram and strict mixed-newlines refusal (policy #1)
  * sets both ``status.file`` (gate) and ``status.sniff`` (source-specific outcome)
  * never populates ``ctx.file_lines``; that is the reader's job

"""

from __future__ import annotations

import codecs
from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.pipeline.context import (
    ContentStatus,
    FsStatus,
    ProcessingContext,
    may_proceed_to_sniffer,
)

if TYPE_CHECKING:
    from os import stat_result

    from topmark.filetypes.policy import FileTypeHeaderPolicy

logger: TopmarkLogger = get_logger(__name__)


@dataclass(frozen=True)
class _NLCounts:
    lf: int = 0
    crlf: int = 0
    cr: int = 0


def _count_newlines(buf: bytes, carry_cr: bool) -> tuple[_NLCounts, bool]:
    """Count newline sequences in a bytes buffer.

    Args:
        buf (bytes): Byte chunk to inspect.
        carry_cr (bool): Whether a CR from the previous chunk should be paired with the first LF.

    Returns:
        tuple[_NLCounts, bool]: A tuple of (_NLCounts, new_carry_cr) where new_carry_cr
            indicates whether the last byte in this chunk was an unmatched CR that may pair
            with an LF in the next chunk.
    """
    lf: int = 0
    crlf: int = 0
    cr: int = 0
    i: int = 0
    n: int = len(buf)

    # If previous chunk ended with CR, and current chunk starts with LF → count one CRLF
    if carry_cr:
        if n and buf[0:1] == b"\n":
            crlf += 1
            i = 1
        else:
            cr += 1  # lone CR previously
    # Scan the rest
    while i < n:
        b: bytes = buf[i : i + 1]
        if b == b"\r":
            if i + 1 < n and buf[i + 1 : i + 2] == b"\n":
                crlf += 1
                i += 2
            else:
                # lone CR for now; may join with LF in the next chunk
                i += 1
                # We'll finalize this CR as lone only if next chunk doesn't start with LF
                # by returning carry_cr=True
                return _NLCounts(lf, crlf, cr), True
        elif b == b"\n":
            lf += 1
            i += 1
        else:
            i += 1
    return _NLCounts(lf, crlf, cr), (n > 0 and buf[-1:] == b"\r")


def _apply_bom_shebang_policy(ctx: ProcessingContext, first_bytes: bytes) -> bool:
    """Apply BOM-before-shebang policy when relevant.

    Args:
        ctx (ProcessingContext): Processing context to update.
        first_bytes (bytes): The first bytes of the file being inspected.

    Returns:
        bool: True if a policy violation was detected and the context was updated to a
            skipped status.
    """
    # Detect BOM and shebang ordering from the first few bytes
    has_bom: bool = first_bytes.startswith(b"\xef\xbb\xbf")
    starts_with_shebang: bool = first_bytes.startswith(b"#!")
    shebang_after_bom: bool = has_bom and first_bytes[3:5] == b"#!"

    if has_bom:
        ctx.leading_bom = True
    if starts_with_shebang or shebang_after_bom:
        ctx.has_shebang = True

    # If the file type supports shebang and BOM precedes shebang, skip
    policy: FileTypeHeaderPolicy | None = ctx.file_type.header_policy if ctx.file_type else None
    if shebang_after_bom and policy and getattr(policy, "supports_shebang", False):
        ctx.add_error(
            "UTF-8 BOM appears before the shebang; POSIX requires '#!' at byte 0. "
            "TopMark will not modify this file by default."
        )
        ctx.status.content = ContentStatus.SKIPPED_POLICY_BOM_BEFORE_SHEBANG
        logger.warning(
            "sniffer: BOM precedes shebang; skipping per policy (file type: %s): %s",
            ctx.file_type.name if ctx.file_type else "<unknown>",
            ctx.path,
        )
        return True
    return False


def sniff(ctx: ProcessingContext) -> ProcessingContext:
    """Lightweight I/O step between resolver and reader.

    Responsibilities:
      - Confirm file exists and is readable.
      - Fast text-vs-binary sniff (NUL bytes, incremental UTF-8 decode of tiny chunks).
      - Detect leading UTF-8 BOM and shebang ordering; enforce policy if BOM precedes shebang.
      - Quick newline histogram (bytes-level) and strict mixed-newlines skip.
      - Establish a tentative newline_style (dominant or default to LF) without loading full text.

    Notes:
      - Does **not** populate `ctx.file_lines`; that is the reader's job.
      - If this step sets a non-RESOLVED file status, later steps will early-return.
    """
    logger.debug("ctx: %s", ctx)

    ctx.status.fs = FsStatus.PENDING

    # Only proceed if resolve succeeded
    if not may_proceed_to_sniffer(ctx):
        logger.info("Sniffer skipped by may_proceed_to_sniffer()")
        return ctx

    # Existence / permission
    try:
        st: stat_result = ctx.path.stat()
    except FileNotFoundError:
        ctx.status.fs = FsStatus.NOT_FOUND
        logger.warning("%s: File not found: %s", ctx.status.fs.value, ctx.path)
        return ctx
    except PermissionError as e:
        ctx.status.fs = FsStatus.NO_READ_PERMISSION
        ctx.add_error(f"Permission denied: {e}")
        logger.error("sniffer: permission denied %s: %s", ctx.path, e)
        return ctx

    if st.st_size == 0:
        ctx.status.fs = FsStatus.EMPTY
        ctx.add_warning("File is empty.")
        logger.warning("sniffer: empty file %s", ctx.path)
        return ctx

    # Read a small prefix to check BOM/shebang and begin newline counting
    try:
        with ctx.path.open("rb") as bf:
            prefix: bytes = bf.read(4096)
            # Binary heuristic: NUL anywhere in prefix → not text
            if b"\0" in prefix:
                ctx.status.content = ContentStatus.SKIPPED_NOT_TEXT_FILE
                logger.warning("%s: Binary (NUL byte): %s", ctx.status.content.value, ctx.path)
                return ctx

            # Initialize a strict UTF-8 incremental decoder to catch invalid sequences
            decoder: codecs.BufferedIncrementalDecoder = codecs.getincrementaldecoder("utf-8")(
                "strict"
            )

            # Apply BOM/shebang policy based on the first bytes
            if _apply_bom_shebang_policy(ctx, prefix):
                ctx.status.content = ContentStatus.SKIPPED_POLICY_BOM_BEFORE_SHEBANG
                return ctx

            # Newline counting on prefix and subsequent chunks (bounded), and strict UTF-8 decode
            counts = _NLCounts()
            carry_cr: bool = False
            total_bytes: int = len(prefix)
            chunk: bytes = prefix
            while True:
                try:
                    # Attempt to decode the current chunk strictly as UTF-8
                    decoder.decode(chunk)
                except UnicodeDecodeError:
                    ctx.status.content = ContentStatus.SKIPPED_NOT_TEXT_FILE
                    ctx.add_error(
                        "Invalid UTF-8 byte sequence detected; treating as non-text file."
                    )
                    logger.warning("sniffer: invalid UTF-8 sequence → skip: %s", ctx.path)
                    return ctx

                # Proceed with newline counting on the raw bytes
                c: _NLCounts
                c, carry_cr = _count_newlines(chunk, carry_cr)
                counts = _NLCounts(
                    lf=counts.lf + c.lf,
                    crlf=counts.crlf + c.crlf,
                    cr=counts.cr + c.cr,
                )
                # Limit total inspected bytes to ~64 KiB to stay lightweight
                if total_bytes >= 64 * 1024:
                    break
                chunk = bf.read(4096)
                if not chunk:
                    break
                total_bytes += len(chunk)

            # After loop, flush the decoder to catch any incomplete trailing sequences
            try:
                decoder.decode(b"", final=True)
            except UnicodeDecodeError:
                ctx.status.content = ContentStatus.SKIPPED_NOT_TEXT_FILE
                ctx.add_error("Invalid UTF-8 sequence at end-of-file; treating as non-text file.")
                logger.warning("sniffer: invalid UTF-8 at EOF → skip: %s", ctx.path)
                return ctx

            # Commit newline histogram to context
            hist: dict[str, int] = {}
            if counts.lf:
                hist["\n"] = counts.lf
            if counts.crlf:
                hist["\r\n"] = counts.crlf
            if counts.cr:
                hist["\r"] = counts.cr
            ctx.newline_hist = hist

            total_terms: int = sum(hist.values())
            if total_terms > 0:
                dom_nl: str
                dom_cnt: int
                dom_nl, dom_cnt = max(hist.items(), key=lambda kv: kv[1])
                ctx.dominant_newline = dom_nl
                ctx.dominance_ratio = dom_cnt / total_terms if dom_cnt else 0.0
                ctx.newline_style = dom_nl
            else:
                # No terminators seen in sniff → default to LF; reader can refine if needed
                ctx.newline_style = "\n"
                ctx.dominant_newline = None
                ctx.dominance_ratio = None

            ctx.mixed_newlines = sum(1 for v in hist.values() if v > 0) >= 2
            if ctx.mixed_newlines:
                lf: int = hist.get("\n", 0)
                crlf: int = hist.get("\r\n", 0)
                cr: int = hist.get("\r", 0)
                ctx.status.content = ContentStatus.SKIPPED_MIXED_LINE_ENDINGS
                ctx.add_error(
                    f"Mixed line endings detected during sniff (LF={lf}, CRLF={crlf}, CR={cr}). "
                    "Strict policy refuses to process files with mixed line endings."
                )
                logger.warning(
                    "sniffer: mixed newlines (LF=%d, CRLF=%d, CR=%d) → skip: %s",
                    lf,
                    crlf,
                    cr,
                    ctx.path,
                )
                return ctx

    except FileNotFoundError:
        ctx.status.fs = FsStatus.NOT_FOUND
        logger.warning("%s: File not found: %s", ctx.status.fs.value, ctx.path)
        return ctx
    except PermissionError as e:
        ctx.status.fs = FsStatus.NO_READ_PERMISSION
        ctx.add_error(f"Permission denied: {e}")
        logger.error("sniffer: permission denied %s: %s", ctx.path, e)
        return ctx
    except Exception as e:
        ctx.status.fs = FsStatus.UNREADABLE
        ctx.add_error(f"Error while sniffing: {e}")
        logger.error("sniffer: error sniffing %s: %s", ctx.path, e)
        return ctx

    # Keep status RESOLVED so the reader proceeds.
    logger.debug(
        "sniffer: nl_style=%r leading_bom=%s has_shebang=%s",
        ctx.newline_style,
        ctx.leading_bom,
        ctx.has_shebang,
    )

    ctx.status.fs = FsStatus.OK
    return ctx
