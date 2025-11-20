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
newline convention (LF, CRLF, or CR), and loads the file image (lines) while preserving
original line endings. It updates the processing context with the detected
newline style, whether the file ends with a newline, and exposes the file image for subsequent
steps via a view (see `ctx.views.image`).

Implementation details:
  * Uses an incremental UTF-8 decoder to avoid false negatives when multibyte
    sequences span chunk boundaries during the binary/text sniff.
  * Detects CRLF robustly across read chunk boundaries by carrying a 1-byte tail,
    preferring CRLF over LF and CR when both appear.
  * If no newline is observed during sniffing (e.g., single-line files), defaults
    to "\n" and proceeds, rather than skipping the file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.filetypes.base import FileType
from topmark.pipeline.adapters import PreInsertViewAdapter
from topmark.pipeline.context.policy import (
    allow_content_reflow_by_policy,
    allows_bom_before_shebang_by_policy,
    allows_mixed_line_endings_by_policy,
)
from topmark.pipeline.hints import Axis, Cluster, KnownCode
from topmark.pipeline.status import (
    ContentStatus,
    FsStatus,
)
from topmark.pipeline.steps.base import BaseStep
from topmark.pipeline.views import ListFileImageView

if TYPE_CHECKING:
    from topmark.config.logging import TopmarkLogger
    from topmark.filetypes.base import FileType, InsertChecker, InsertCheckResult
    from topmark.pipeline.context.model import ProcessingContext

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


class ReaderStep(BaseStep):
    """Load text image, detect newline style, and set `ContentStatus`.

    Loads the file as UTF-8 text (preserving native newlines), captures BOM/shebang
    facts from the sniffer, computes a newline histogram, and determines the dominant
    newline style for later rendering/comparison.

    Axes written:
      - content

    Sets:
      - ContentStatus: {PENDING, OK, UNSUPPORTED,
                        SKIPPED_MIXED_LINE_ENDINGS, SKIPPED_POLICY_BOM_BEFORE_SHEBANG,
                        UNREADABLE}
    """

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.CONTENT,
            axes_written=(Axis.CONTENT,),
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
            bool: True if processing can proceed to the read step, False otherwise.
        """
        if ctx.is_halted:
            # SnifferStep already flagged FsStatus statuses which halt processng
            return False
        # The remaining FsStatus states are either OK or controlled by policy
        return True

    def run(self, ctx: ProcessingContext) -> None:
        """Loads file lines and detects newline style.

        This function preserves native newline conventions and records them
        in ``ctx.newline_style``.vIt assumes the sniffer has already performed existence,
        permission, binary, BOM/shebang, and mixed-newlines policy checks.

        Args:
            ctx (ProcessingContext): The processing context for the current file.

        Notes:
            - Assumes `sniffer.sniff()` has already handled existence, permissions,
            binary detection, BOM/shebang ordering policy, and mixed-newlines policy.
            - Sets `ctx.views.image = ListFileImageView(lines)` (preserving original line endings),
            provides streaming access through `ctx.iter_file_lines()`, and records
            `ctx.ends_with_newline`, a precise newline histogram in `ctx.newline_hist`,
            and the dominant newline style in `ctx.newline_style`.
        """
        logger.debug("ctx: %s", ctx)

        # Safeguard: header_processor and file_type have been set in resolver.resolve()
        assert ctx.header_processor, "context.header_processor not defined"
        assert ctx.file_type, "context.file_type not defined"

        if ctx.status.fs == FsStatus.BOM_BEFORE_SHEBANG:
            # Strict default: refuse unless policy says otherwise
            if allows_bom_before_shebang_by_policy(ctx):
                # TODO later: apply policies
                # (remove BOM before shebang)
                pass
            else:
                ctx.status.content = ContentStatus.SKIPPED_POLICY_BOM_BEFORE_SHEBANG
                reason: str = "BOM appears before shebang; policy forbids proceeding"
                ctx.error(reason)
                ctx.request_halt(reason=reason, at_step=self)
                return

        if ctx.status.fs == FsStatus.MIXED_LINE_ENDINGS:
            # Strict default: refuse unless policy says otherwise
            if allows_mixed_line_endings_by_policy(ctx):
                # TODO later: apply policies
                # (refine what to do when mixed line endngs are present)
                pass
            else:
                ctx.status.content = ContentStatus.SKIPPED_MIXED_LINE_ENDINGS
                reason = "Mixed line endings refused by policy"
                ctx.error(reason)
                ctx.request_halt(reason=reason, at_step=self)
                return

        def _initialize_empty_file_content(ctx: ProcessingContext) -> None:
            """Initialize the in-memory image and content status for empty files.

            This helper is used both when Sniffer has already marked the file as EMPTY
            and when the file becomes empty between sniff and read. It always treats an
            empty file as a valid (but zero-line) text image; whether a header may be
            inserted later is governed by policy in downstream steps (builder/planner),
            not here.
            """
            if ctx.status.fs != FsStatus.EMPTY:
                return

            ctx.ends_with_newline = False
            ctx.views.image = ListFileImageView([])
            ctx.newline_hist = {}
            ctx.dominant_newline = None
            ctx.dominance_ratio = None
            ctx.mixed_newlines = False
            ctx.status.content = ContentStatus.OK
            logger.debug(
                "Reader: empty file %s; content status set to %s.",
                ctx.path,
                ctx.status.content,
            )

        # Check if file empty
        _initialize_empty_file_content(ctx)

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
                ctx.ends_with_newline = False
                ctx.status.fs = FsStatus.EMPTY
                # NOTE: real zero-length files already marked EMPTY in sniffer
                _initialize_empty_file_content(ctx)
                return

            # Record whether the file ends with a newline (used when generating patches)
            ctx.ends_with_newline = lines[-1].endswith(("\r\n", "\n", "\r"))

            # Preserve original line endings; each element contains its own terminator
            ctx.views.image = ListFileImageView(lines)

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

            # # Policy option: Update the newline_style to the dominant newline if any
            # if ctx.dominant_newline:
            #     ctx.newline_style = ctx.dominant_newline
            # # Policy option: apply preferred newlne style
            # # Policy option: convert every line ending to a given preferred style
            #   (akin to dos2unix, unix2dos...)

            # Exit if mixed line endings found in file
            if ctx.mixed_newlines:
                ctx.status.content = ContentStatus.SKIPPED_MIXED_LINE_ENDINGS
                lf: int = ctx.newline_hist.get("\n", 0)
                crlf: int = ctx.newline_hist.get("\r\n", 0)
                cr: int = ctx.newline_hist.get("\r", 0)
                ctx.error(
                    f"Mixed line endings detected (LF={lf}, CRLF={crlf}, CR={cr}). "
                    "Strict policy refuses to process mixed files."
                )
                return

            ctx.status.content = ContentStatus.OK
            logger.debug(
                "Reader step completed for %s, detected newline style: %r, ends_with_newline: %s",
                ctx.path,
                ctx.newline_style,
                ctx.ends_with_newline,
            )
            logger.trace(
                "File '%s' (content status: %s) - lines: %d",
                ctx.path,
                ctx.status.content.value,
                len(lines) if lines else 0,
            )

            # Advisory-only pre-insert probe.
            # Now that the file image is available, we can compute a *preview* of
            # whether insertion would be allowed. This is used for bucketing and
            # debug logs only; the updater remains the authoritative gate and is the
            # only step that emits user-facing diagnostics.
            ft: FileType | None = ctx.file_type
            checker: InsertChecker | None = ft.pre_insert_checker if ft else None
            if checker is not None:
                # Keep the reader resilient: the checker is extensible code and may raise.
                # We intentionally keep the try/except *tight* around the invocation.
                try:
                    from topmark.filetypes.base import InsertCapability  # local to avoid cycles

                    view = PreInsertViewAdapter(ctx)
                    res: InsertCheckResult = checker(view) or {}
                    if res:
                        ctx.pre_insert_capability = res.get(
                            "capability", InsertCapability.UNEVALUATED
                        )
                        ctx.pre_insert_reason = res.get("reason", "")
                        ctx.pre_insert_origin = res.get("origin", __name__)
                    logger.debug(
                        "reader advisory: pre-insert %s – %s",
                        getattr(ctx.pre_insert_capability, "value", ctx.pre_insert_capability),
                        ctx.pre_insert_reason,
                    )
                    if ctx.pre_insert_capability == InsertCapability.SKIP_IDEMPOTENCE_RISK:
                        if allow_content_reflow_by_policy(ctx) is True:
                            reason = (
                                f"Strict policy: {ctx.pre_insert_capability.value} "
                                "- overridden (OK to proceed)"
                            )
                            ctx.info(reason)
                            return
                        else:
                            ctx.status.content = ContentStatus.SKIPPED_REFLOW
                            reason = f"Strict policy: {ctx.pre_insert_capability.value}"
                            ctx.info(reason)
                            ctx.request_halt(reason=reason, at_step=self)

                except Exception:
                    # Advisory-only; never fail the reader on checker issues.
                    logger.debug(
                        "reader advisory pre-insert checker failed; ignoring", exc_info=True
                    )

            return

        except Exception as e:  # Log and attach diagnostic; continue without raising
            logger.error("Error reading file %s: %s", ctx.path, e)
            ctx.status.content = ContentStatus.UNREADABLE
            reason = f"Error reading file file: {e}"
            ctx.error(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

    def hint(self, ctx: ProcessingContext) -> None:
        """Attach content outcome hints (non-binding).

        Args:
            ctx (ProcessingContext): The processing context.
        """
        st: ContentStatus = ctx.status.content

        # May proceed to next step (always):
        if st == ContentStatus.OK:
            pass  # healthy, no hint
        # Stop processing (policy):
        elif st == ContentStatus.SKIPPED_MIXED_LINE_ENDINGS:
            ctx.hint(
                axis=Axis.CONTENT,
                code=KnownCode.CONTENT_SKIPPED_MIXED,
                cluster=Cluster.BLOCKED_POLICY,
                message="policy: mixed line endings",
                terminal=True,
            )
        elif st == ContentStatus.SKIPPED_POLICY_BOM_BEFORE_SHEBANG:
            ctx.hint(
                axis=Axis.CONTENT,
                code=KnownCode.CONTENT_SKIPPED_BOM_SHEBANG,
                cluster=Cluster.BLOCKED_POLICY,
                message="policy: BOM before shebang",
                terminal=True,
            )
        elif st == ContentStatus.SKIPPED_REFLOW:
            ctx.hint(
                axis=Axis.CONTENT,
                code=KnownCode.CONTENT_SKIPPED_REFLOW,
                cluster=Cluster.BLOCKED_POLICY,
                message="policy: would reflow contet",
                terminal=True,
            )
        # Stop processing:
        elif st == ContentStatus.UNSUPPORTED:  # NOTE: Currently not used
            ctx.hint(
                axis=Axis.CONTENT,
                code=KnownCode.CONTENT_NOT_SUPPORTED,
                cluster=Cluster.SKIPPED,
                message="unsupported content (binary/decode)",
                terminal=True,
            )
        elif st == ContentStatus.UNREADABLE:
            ctx.hint(
                axis=Axis.CONTENT,
                code=KnownCode.CONTENT_UNREADABLE,
                cluster=Cluster.SKIPPED,
                message="cannot read content",
                terminal=True,
            )
        elif st == ContentStatus.PENDING:
            # reader did not complete
            ctx.request_halt(reason=f"{self.__class__.__name__} did not set state.", at_step=self)
