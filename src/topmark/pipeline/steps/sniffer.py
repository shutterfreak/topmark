# topmark:header:start
#
#   project      : TopMark
#   file         : sniffer.py
#   file_relpath : src/topmark/pipeline/steps/sniffer.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pre-read file sniffer.

Performs existence/permission checks, fast binary/NUL sniff, strict UTF-8 validation,
BOM+shebang policy, and raw newline histogram (LF/CRLF/CR, mixed).

Sets:
  - `FsStatus` → {OK, EMPTY, NOT_FOUND, NO_READ_PERMISSION, UNREADABLE,
                  BINARY, UNICODE_DECODE_ERROR, BOM_BEFORE_SHEBANG, MIXED_LINE_ENDINGS}
"""

from __future__ import annotations

import codecs
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.context.policy import allow_empty_by_policy
from topmark.pipeline.hints import Axis, Cluster, KnownCode
from topmark.pipeline.status import FsStatus, ResolveStatus
from topmark.pipeline.steps.base import BaseStep

if TYPE_CHECKING:
    from os import stat_result

    from topmark.config.logging import TopmarkLogger
    from topmark.filetypes.base import FileType
    from topmark.filetypes.policy import FileTypeHeaderPolicy
    from topmark.pipeline.context.model import ProcessingContext

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
                # If CR is the last byte of this chunk, carry it to the next chunk
                if i + 1 == n:
                    return _NLCounts(lf, crlf, cr), True
                # Otherwise, it's a standalone CR within this chunk: count it and continue
                cr += 1
                i += 1
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
        ctx.error(
            "UTF-8 BOM appears before the shebang; POSIX requires '#!' at byte 0. "
            "TopMark will not modify this file by default."
        )
        ctx.status.fs = FsStatus.BOM_BEFORE_SHEBANG
        logger.warning(
            "sniffer: BOM precedes shebang; skipping per policy (file type: %s): %s",
            ctx.file_type.name if ctx.file_type else "<unknown>",
            ctx.path,
        )
        return True
    return False


class SnifferStep(BaseStep):
    """Pre-read checks (existence/perm, binary/UTF-8, BOM/shebang, newline mix).

    Performs fast, bytes-level checks and sets `FsStatus`. It does not load the full
    text image; `ReaderStep` remains authoritative for `ContentStatus`.

    Axes written:
      - fs

    Sets:
      - FsStatus: {PENDING, OK, EMPTY, NOT_FOUND, NO_READ_PERMISSION, UNREADABLE,
                   NO_WRITE_PERMISSION, BINARY, BOM_BEFORE_SHEBANG,
                   UNICODE_DECODE_ERROR, MIXED_LINE_ENDINGS}
    """

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.FS,
            axes_written=(Axis.FS,),
        )

    def may_proceed(self, ctx: ProcessingContext) -> bool:
        """Determine if processing can proceed to the read step.

        Processing can proceed if:
        - The file was successfully resolved (ctx.status.resolve is RESOLVED)
        - A file type is present (ctx.file_type is not None)
        - A header processor is available (ctx.header_processor is not None)

        Note:
            The file system status (`ctx.status.fs`) is not strictly required here,
            to allow tests to skip the sniffer and invoke the reader directly. In such
            cases, the reader is the definitive authority for content checks (existence,
            permissions, binary/text, etc).

        Args:
            ctx (ProcessingContext): The processing context for the current file.

        Returns:
            bool: True if `ctx.status.resolve == RESOLVED`, `ctx.file_type` and
                `ctx.header_processor` are set.
        """
        if ctx.is_halted:
            return False
        return ctx.status.resolve == ResolveStatus.RESOLVED

    def run(self, ctx: ProcessingContext) -> None:
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

        apply: bool = False if ctx.config.apply_changes is None else ctx.config.apply_changes
        ctx.status.fs = FsStatus.PENDING

        # Existence / permission
        try:
            st: stat_result = ctx.path.stat()
        except FileNotFoundError:
            logger.info("%s: File not found: %s", ctx.status.fs.value, ctx.path)
            ctx.status.fs = FsStatus.NOT_FOUND
            reason: str = f"File not found: {ctx.path}"
            ctx.request_halt(reason=reason, at_step=self)
            return
        except PermissionError as e:
            logger.error("sniffer: permission denied %s: %s", ctx.path, e)
            ctx.status.fs = FsStatus.NO_READ_PERMISSION
            reason = f"Permission denied: {e}"
            ctx.error(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        if apply is True:
            # Apply mode: check write permission upfront
            if not os.access(ctx.path, os.W_OK):
                ctx.status.fs = FsStatus.NO_WRITE_PERMISSION
                ctx.error("Permission denied: cannot write to file")
                return

        if st.st_size == 0:
            ctx.status.fs = FsStatus.EMPTY

            # If policy does NOT allow inserting headers into empty files for this type,
            # attach a non-terminal hint explaining how to enable it.
            if ctx.file_type is not None and not allow_empty_by_policy(ctx):
                file_type: FileType = ctx.file_type
                table_name: str = f"policy_by_type.{file_type.name}"
                ctx.hint(
                    axis=Axis.FS,
                    code=KnownCode.FS_EMPTY,
                    cluster=Cluster.BLOCKED_POLICY,
                    message="Empty file skipped by default.",
                    detail=(
                        f"{file_type.description}:\n"
                        "To allow headers in empty "
                        f"{file_type.name} files, add the following "
                        "to your TopMark configuration:\n"
                        f"  [{table_name}]\n"
                        "  allow_header_in_empty_files = true\n"
                        f"(for pyproject.toml, use [tool.topmark.{table_name}])"
                    ),
                    terminal=False,
                )
            else:
                ctx.info("File is empty.")

            return

        # Read a small prefix to check BOM/shebang and begin newline counting
        try:
            with ctx.path.open("rb") as bf:
                prefix: bytes = bf.read(4096)
                # Binary heuristic: NUL anywhere in prefix → not text
                if b"\0" in prefix:
                    ctx.status.fs = FsStatus.BINARY
                    logger.warning("%s: Binary (NUL byte): %s", ctx.status.content.value, ctx.path)
                    return

                # Initialize a strict UTF-8 incremental decoder to catch invalid sequences
                decoder: codecs.BufferedIncrementalDecoder = codecs.getincrementaldecoder("utf-8")(
                    "strict"
                )

                # Apply BOM/shebang policy based on the first bytes
                if _apply_bom_shebang_policy(ctx, prefix):
                    # already sets ctx.status.fs = FsStatus.BOM_BEFORE_SHEBANG
                    return

                # Newline counting on prefix and subsequent chunks (bounded),
                # and strict UTF-8 decode
                counts = _NLCounts()
                carry_cr: bool = False
                total_bytes: int = len(prefix)
                chunk: bytes = prefix
                while True:
                    try:
                        # Attempt to decode the current chunk strictly as UTF-8
                        decoder.decode(chunk)
                    except UnicodeDecodeError:
                        ctx.status.fs = FsStatus.UNICODE_DECODE_ERROR
                        ctx.error(
                            "Invalid UTF-8 byte sequence detected; treating as non-text file."
                        )
                        return

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
                    ctx.status.fs = FsStatus.UNICODE_DECODE_ERROR
                    ctx.error("Invalid UTF-8 sequence at end-of-file; treating as non-text file.")
                    logger.warning("sniffer: invalid UTF-8 at EOF → skip: %s", ctx.path)
                    return

                if carry_cr:
                    counts = _NLCounts(lf=counts.lf, crlf=counts.crlf, cr=counts.cr + 1)

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
                    ctx.status.fs = FsStatus.MIXED_LINE_ENDINGS
                    ctx.error(
                        "Mixed line endings detected during sniff "
                        f"(LF={lf}, CRLF={crlf}, CR={cr}). "
                        "Strict policy refuses to process files with mixed line endings."
                    )
                    return

        except FileNotFoundError:
            ctx.status.fs = FsStatus.NOT_FOUND
            logger.warning("%s: File not found: %s", ctx.status.fs.value, ctx.path)
            reason = f"File not found: {ctx.path}"
            ctx.error(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return
        except PermissionError as e:
            logger.error("sniffer: permission denied %s: %s", ctx.path, e)
            ctx.status.fs = FsStatus.NO_READ_PERMISSION
            reason = f"Permission denied: {e}"
            ctx.error(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return
        except Exception as e:
            logger.error("sniffer: error sniffing %s: %s", ctx.path, e)
            ctx.status.fs = FsStatus.UNREADABLE
            reason = f"Error while sniffing: {e}"
            ctx.error(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        # Keep status RESOLVED so the reader proceeds.
        logger.debug(
            "sniffer: nl_style=%r leading_bom=%s has_shebang=%s",
            ctx.newline_style,
            ctx.leading_bom,
            ctx.has_shebang,
        )

        ctx.status.fs = FsStatus.OK
        return

    def hint(self, ctx: ProcessingContext) -> None:
        """Attach sniff outcome hints (non-binding).

        Args:
            ctx (ProcessingContext): The processing context.
        """
        st: FsStatus = ctx.status.fs

        # May proceed to next step (always):
        if st == FsStatus.OK:
            # Implies ctx.status.resolve == ResolveStatus.RESOLVED
            pass  # healthy, no hint
        # May proceed to next step (policy):
        elif st == FsStatus.EMPTY:
            # Implies ctx.status.resolve == ResolveStatus.RESOLVED
            ctx.hint(
                axis=Axis.FS,
                code=KnownCode.CONTENT_EMPTY_FILE,
                cluster=Cluster.BLOCKED_POLICY,
                message="empty file",
            )
        elif st == FsStatus.BOM_BEFORE_SHEBANG:
            # Implies ctx.status.resolve == ResolveStatus.RESOLVED
            ctx.hint(
                axis=Axis.FS,
                code=KnownCode.FS_BOM_BEFORE_SHEBANG,
                cluster=Cluster.BLOCKED_POLICY,
                message="UTF-8 BOM before shebang",
            )
        elif st == FsStatus.MIXED_LINE_ENDINGS:
            # Implies ctx.status.resolve == ResolveStatus.RESOLVED
            ctx.hint(
                axis=Axis.FS,
                code=KnownCode.CONTENT_SKIPPED_MIXED,
                cluster=Cluster.BLOCKED_POLICY,
                message="mixed line endings",
            )
        # Stop processing:
        elif st == FsStatus.NOT_FOUND:
            ctx.hint(
                axis=Axis.FS,
                code=KnownCode.FS_NOT_FOUND,
                cluster=Cluster.SKIPPED,
                message="file not found",
                terminal=True,
            )
        elif st == FsStatus.NO_READ_PERMISSION:
            ctx.hint(
                axis=Axis.FS,
                code=KnownCode.FS_UNREADABLE,
                cluster=Cluster.SKIPPED,
                message="permission denied",
                terminal=True,
            )
        elif st == FsStatus.UNREADABLE:
            ctx.hint(
                axis=Axis.FS,
                code=KnownCode.FS_UNREADABLE,
                cluster=Cluster.SKIPPED,
                message="read error",
                terminal=True,
            )
        elif st == FsStatus.NO_WRITE_PERMISSION:
            ctx.hint(
                axis=Axis.FS,
                code=KnownCode.FS_UNWRITABLE,
                cluster=Cluster.SKIPPED,
                message="no write permission",
                terminal=True,
            )
        elif st == FsStatus.BINARY:
            ctx.hint(
                axis=Axis.FS,
                code=KnownCode.CONTENT_NOT_SUPPORTED,
                cluster=Cluster.SKIPPED,
                message="binary file",
                terminal=True,
            )
        elif st == FsStatus.UNICODE_DECODE_ERROR:
            ctx.hint(
                axis=Axis.FS,
                code=KnownCode.CONTENT_ENCODING_ERROR,
                cluster=Cluster.SKIPPED,
                message="Unicode decode error",
                terminal=True,
            )
        elif st == FsStatus.PENDING:
            # sniffer did not complete
            ctx.request_halt(reason=f"{self.__class__.__name__} did not set state.", at_step=self)
