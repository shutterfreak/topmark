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
(``ctx.views.header.range``) and delegates removal to the active header processor.
It sets ``ctx.views.updated`` with the stripped image (no I/O) and updates
``StripStatus`` to ``READY`` or ``NOT_NEEDED`` accordingly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.pipeline.hints import Axis, Cluster, KnownCode
from topmark.pipeline.processors.types import StripDiagKind, StripDiagnostic
from topmark.pipeline.status import (
    ContentStatus,
    FsStatus,
    HeaderStatus,
    ResolveStatus,
    StripStatus,
)
from topmark.pipeline.steps.base import BaseStep
from topmark.pipeline.views import HeaderView, UpdatedView

if TYPE_CHECKING:
    from topmark.config.logging import TopmarkLogger
    from topmark.filetypes.policy import FileTypeHeaderPolicy
    from topmark.pipeline.context.model import ProcessingContext

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


class StripperStep(BaseStep):
    """Remove the TopMark header when present (view-based).

    Uses the `HeaderProcessor` and `HeaderView.range` (if available) to create a
    stripped image in `UpdatedView`. Does not perform I/O.

    Axes written:
      - strip

    Sets:
      - StripStatus: {PENDING, READY, NOT_NEEDED, FAILED}
    """

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.STRIP,
            axes_written=(Axis.STRIP,),
        )

    def may_proceed(self, ctx: ProcessingContext) -> bool:
        """Return True when content is processable and a processor is available.

        Requires:
          - `resolve == RESOLVED`
          - `file_type` and `header_processor` are set
          - `content not in {PENDING, UNSUPPORTED, UNREADABLE}`

        Args:
            ctx (ProcessingContext): The processing context for the current file.

        Returns:
            bool: True if processing can proceed to the build step, False otherwise.
        """
        if ctx.is_halted:
            return False
        return (
            ctx.status.resolve == ResolveStatus.RESOLVED
            and ctx.header_processor is not None
            and ctx.status.content
            not in {
                ContentStatus.PENDING,
                ContentStatus.UNSUPPORTED,
                ContentStatus.UNREADABLE,
            }
        )

    def run(self, ctx: ProcessingContext) -> None:
        """Remove the TopMark header using the processor and known span if available (view‑based).

        Args:
            ctx (ProcessingContext): Pipeline context. Must contain a file image, the
                active header processor, and (optionally) the scanner‑detected header span.

        Raises:
            RuntimeError: If header processor is not defined.

        Mutations:
            ProcessingContext: The same context, with ``ctx.views.updated`` populated when a
                removal occurs and ``StripStatus`` updated to reflect the outcome.

        Notes:
        - Leaves ``HeaderStatus`` untouched (owned by the scanner).
        - Trims a single leading blank line when the header starts at the top of the file
            (handled inside the processor).
        """
        if ctx.header_processor is None:
            # For static code analysis
            raise RuntimeError("ctx.header_processor not defined")

        if ctx.status.content != ContentStatus.OK:
            # Respect content policy: do not attempt to strip when content was refused
            ctx.status.strip = StripStatus.NOT_NEEDED
            if ctx.status.fs == FsStatus.EMPTY:
                logger.debug("Stripper: skipping (file status=%s)", ctx.status.fs.value)
                reason: str = "Could not strip header from empty file."
            else:
                logger.debug("Stripper: skipping (content status=%s)", ctx.status.content.value)
                reason = f"Could not strip header from file (status: {ctx.status.content.value})."
            ctx.info(reason)
            return

        if ctx.status.header is HeaderStatus.MISSING:
            ctx.status.strip = StripStatus.NOT_NEEDED
            reason = "No header to be stripped."
            ctx.info(reason)
            return
        if ctx.status.header not in [HeaderStatus.EMPTY, HeaderStatus.DETECTED]:
            if ctx.status.header in {
                HeaderStatus.MALFORMED_ALL_FIELDS,
                HeaderStatus.MALFORMED_SOME_FIELDS,
            }:
                # TODO: enable stripping based on future policy
                ctx.status.strip = StripStatus.FAILED
                reason = f"No header to be stripped: {ctx.status.header}"
                ctx.info(reason)
                ctx.request_halt(reason=reason, at_step=self)
            else:
                # No header to be stripped
                ctx.status.strip = StripStatus.FAILED
                reason = f"No header to be stripped: {ctx.status.header}"
                ctx.info(reason)
                ctx.request_halt(reason=reason, at_step=self)
            return

        original_lines: list[str] = list(ctx.iter_image_lines())
        if not original_lines:
            # Empty file
            ctx.status.strip = StripStatus.NOT_NEEDED
            reason = "Empty file, stripping not needed."
            ctx.info(reason)
            return

        # Prefer the span detected by the scanner; fall back to processor logic otherwise.
        header_view: HeaderView | None = ctx.views.header
        span: tuple[int, int] | None = header_view.range if header_view else None
        new_lines: list[str]
        removed: tuple[int, int] | None
        diag: StripDiagnostic
        new_lines, removed, diag = ctx.header_processor.strip_header_block(
            lines=original_lines,
            span=span,
            newline_style=ctx.newline_style,
            ends_with_newline=ctx.ends_with_newline,
        )

        # Surface any additional diagnostic notes from the processor
        for note in getattr(diag, "notes", []) or []:
            ctx.info(note)

        # Handle diagnostic outcome explicitly before continuing.
        if diag.kind is StripDiagKind.NOT_FOUND:
            ctx.status.strip = StripStatus.NOT_NEEDED
            reason = diag.reason or "No header detected."
            ctx.info(reason)
            return

        if diag.kind is StripDiagKind.NOOP_EMPTY:
            ctx.status.strip = StripStatus.NOT_NEEDED
            reason = diag.reason or "Empty file, nothing to strip."
            ctx.info(reason)
            return

        if diag.kind is StripDiagKind.MALFORMED_REFUSED:
            ctx.status.strip = StripStatus.NOT_NEEDED
            reason = diag.reason or "Malformed header detected; removal refused by policy."
            ctx.error(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        if diag.kind is StripDiagKind.ERROR:
            ctx.status.strip = StripStatus.NOT_NEEDED
            reason = diag.reason or "Error while analyzing header for stripping."
            ctx.error(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        # For REMOVED or MALFORMED_REMOVED, proceed with post-removal normalization.
        # Guard: if processor reported removal but we somehow have no span/changes, treat as no-op.
        if removed is None or new_lines == original_lines:
            ctx.status.strip = StripStatus.NOT_NEEDED
            reason = diag.reason or "Nothing to strip."
            ctx.info(reason)
            return

        # Optionally remove a single trailing blank line that TopMark inserted after the header.
        # This restores the pre-insert image and makes insert→strip→insert idempotent.
        policy: FileTypeHeaderPolicy | None = ctx.file_type.header_policy if ctx.file_type else None
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
        ctx.views.updated = UpdatedView(lines=updated_lines)

        # A header was present and removed
        ctx.status.strip = StripStatus.READY
        logger.debug("stripper: removed header lines at span %d..%d", removed[0], removed[1])
        return

    def hint(self, ctx: ProcessingContext) -> None:
        """Attach strip hints (non-binding).

        Args:
            ctx (ProcessingContext): The processing context.
        """
        apply: bool = ctx.config.apply_changes is True
        st: StripStatus = ctx.status.strip

        # May proceed to next step (always):
        if st == StripStatus.READY:
            ctx.hint(
                axis=Axis.STRIP,
                code=KnownCode.STRIP_READY,
                cluster=Cluster.CHANGED if apply else Cluster.WOULD_CHANGE,
                message="header removal available",
            )
        elif st == StripStatus.NOT_NEEDED:
            ctx.hint(
                axis=Axis.STRIP,
                code=KnownCode.STRIP_NONE,
                cluster=Cluster.UNCHANGED,
                message="no header to remove",
            )
        # Stop processing:
        elif st == StripStatus.FAILED:
            ctx.hint(
                axis=Axis.STRIP,
                code=KnownCode.STRIP_FAILED,
                cluster=Cluster.ERROR,
                message="failed to prepare header removal",
                terminal=True,
            )
        elif st == StripStatus.PENDING:
            # stripper did not complete
            ctx.request_halt(reason=f"{self.__class__.__name__} did not set state.", at_step=self)
