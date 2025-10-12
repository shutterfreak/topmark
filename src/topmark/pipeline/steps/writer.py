# src/topmark/pipeline/steps/writer.py
# topmark:header:start
#
#   project      : TopMark
#   file         : writer.py
#   file_relpath : src/topmark/pipeline/steps/writer.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Writer step for committing updated content to a sink.

This step is the canonical place where TopMark writes results to a destination
(filesystem, stdout, or dry-run). It avoids implementation drift between the CLI
and public API.

This step is responsible for the final I/O after all other steps have computed
`ctx.updated` and selected the intended `WriteStatus` (INSERTED, REPLACED, REMOVED).
It also applies policy gates (e.g., add-only / update-only) so that command-line intent
and config policies are centralized here.

Sinks
-----
- FileSystemSink: writes in-place to the file path.
- StdoutSink: writes the updated content to stdout (stdin-content mode).
- NullSink: no-op (dry-run).

The step respects `topmark.pipeline.context.may_proceed_to_writer` and the
tri-state intent/feasibility via `ProcessingContext.would_change` and `can_change`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.config.policy import Policy, effective_policy
from topmark.pipeline.context import (
    ProcessingContext,
    WriteStatus,
    may_proceed_to_writer,
)

logger: TopmarkLogger = get_logger(__name__)


class WriteSink(Protocol):
    """Protocol for write sinks used by the writer step.

    Implementations receive a ProcessingContext and return a WriteResult.
    """

    def write(self, *, ctx: ProcessingContext) -> "WriteResult":
        """Write the updated content for ``ctx`` to the target sink.

        Implementations perform the final write operation for a processed file,
        such as writing to disk, emitting to stdout, or performing no operation
        in dry-run mode.

        Args:
            ctx (ProcessingContext): Context that holds updated content and write status.

        Returns:
            WriteResult: Structured result indicating the write status and the number
            of bytes written (if applicable).
        """
        ...


@dataclass
class WriteResult:
    """Structured result of a write operation."""

    status: WriteStatus
    bytes_written: int = 0


class NullSink:
    """Dry-run sink: does not write anything."""

    def write(self, *, ctx: ProcessingContext) -> WriteResult:  # type: ignore[override]
        """No-op write for dry-run mode.

        Args:
            ctx (ProcessingContext): Processing context for the current file.

        Returns:
            WriteResult: The input ``ctx.status.write`` echoed back with zero bytes written.
        """
        return WriteResult(status=ctx.status.write, bytes_written=0)


class StdoutSink:
    """Standard-output sink (stdin-content mode)."""

    def write(self, *, ctx: ProcessingContext) -> WriteResult:  # type: ignore[override]
        """Emit updated content to standard output.

        This sink is used when the CLI/API is configured to read a single file's
        content from STDIN and emit the updated result to STDOUT.

        Args:
            ctx (ProcessingContext): Processing context containing the updated lines.

        Returns:
            WriteResult: ``WRITTEN`` with the number of UTF-8 bytes printed when
            content is available; otherwise ``SKIPPED`` with zero bytes written.
        """
        if not ctx.updated or ctx.updated.lines is None:
            return WriteResult(status=WriteStatus.SKIPPED, bytes_written=0)
        seq: Sequence[str] | Iterable[str] = ctx.updated.lines
        text: str = "".join(seq if isinstance(seq, list) else list(seq))
        print(text, end="")  # noqa: T201 (intentional: pipeline handles stdout here)
        return WriteResult(status=WriteStatus.WRITTEN, bytes_written=len(text.encode("utf-8")))


class FileSystemSink:
    """Filesystem sink that writes in-place to ``ctx.path``."""

    def write(self, *, ctx: ProcessingContext) -> WriteResult:  # type: ignore[override]
        """Write the updated content in-place to ``ctx.path``.

        The sink preserves the original end-of-file newline behavior captured by
        the reader step (``ctx.ends_with_newline``) and uses the detected newline
        style for joins (``ctx.newline_style``).

        Args:
            ctx (ProcessingContext): Processing context containing the updated lines.

        Returns:
            WriteResult: ``WRITTEN`` with the number of UTF-8 bytes written when
            content is available; otherwise ``SKIPPED`` with zero bytes written.
        """
        if not ctx.updated or ctx.updated.lines is None:
            logger.debug(
                "FileSystemSink: ctx.updated not defined or ctx.updated.lines not defined: "
                "nothing to do"
            )
            return WriteResult(status=WriteStatus.SKIPPED, bytes_written=0)
        nl: str = ctx.newline_style or "\n"
        seq: Sequence[str] | Iterable[str] = ctx.updated.lines
        lines: list[str] = seq if isinstance(seq, list) else list(seq)
        text: str = "".join(lines)
        if ctx.ends_with_newline is False and text.endswith(nl):
            # Respect original EOF newline policy
            text = text[: -len(nl)]
        with open(ctx.path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        bytes_written: int = len(text.encode("utf-8"))
        logger.debug("FileSystemSink: wrote %d bytes to file %s", bytes_written, ctx.path)
        return WriteResult(status=WriteStatus.WRITTEN, bytes_written=bytes_written)


def _select_sink(ctx: ProcessingContext) -> WriteSink:
    """Return the appropriate sink for the given context.

    Args:
        ctx (ProcessingContext): Processing context containing the updated lines.

    Returns:
        WriteSink: ``NullSink`` when not applying, ``StdoutSink`` for stdin-content
        mode, otherwise ``FileSystemSink``.
    """
    if not ctx.config.apply_changes:
        logger.debug("Selected NULL sink (ctx.config.apply_changes is False)")
        return NullSink()
    if ctx.config.stdin:
        logger.debug("Selected STDOUT sink (ctx.config.stdin is True)")
        return StdoutSink()
    logger.debug(
        "Selected file system sink (ctx.config.apply_changes is True and ctx.config.stdin is False)"
    )
    return FileSystemSink()


def write(ctx: ProcessingContext) -> ProcessingContext:
    """Writer step: commit updates to the selected sink.

    This step executes only when `may_proceed_to_writer` returns ``True``.
    Otherwise it converts a preview status to a non-mutating terminal status.

    Args:
        ctx (ProcessingContext): The processing context with update intent.

    Returns:
        ProcessingContext: The same context, with ``status.write`` finalized.
    """
    logger.debug("ctx: %s", ctx)

    if not may_proceed_to_writer(ctx):
        logger.info("Writer skipped by may_proceed_to_writer()")
        if ctx.status.write == WriteStatus.PREVIEWED:
            ctx.status.write = WriteStatus.SKIPPED
        logger.warning(
            "may_proceed_to_writer(): May NOT proceed to writing: ProcessingContext: %s",
            ctx.to_dict(),
        )
        return ctx

    # --- Policy enforcement (centralized + FileType-specific (optional) -----
    pol: Policy = effective_policy(
        ctx.config,
        (ctx.file_type.name if ctx.file_type else None) if ctx.file_type else None,
    )
    # Only gate insert/replace (check mode) — strip/removal is not governed by add/update.
    if ctx.status.write == WriteStatus.INSERTED and pol.update_only:
        ctx.status.write = WriteStatus.SKIPPED
        ctx.add_info("Skipped by policy: --update-only")
        logger.debug("Skipped by policy: --update-only")
        return ctx

    if ctx.status.write == WriteStatus.REPLACED and pol.add_only:
        ctx.status.write = WriteStatus.SKIPPED
        ctx.add_info("Skipped by policy: --add-only")
        logger.debug("Skipped by policy: --add-only")
        return ctx

    if not ctx.updated or ctx.updated.lines is None:
        ctx.add_info("File unchanged - nothing to write.")
        logger.debug("File unchanged - nothing to write")
        return ctx  # nothing to write

    logger.debug(
        "writer gate: resolve=%s can_change=%s header=%s comparison=%s strip=%s policy=%s",
        ctx.status.resolve,
        ctx.can_change,
        ctx.status.header,
        ctx.status.comparison,
        ctx.status.strip,
        ctx.permitted_by_policy,
    )
    logger.debug("ProcessingContext before writing: %s", ctx.to_dict())
    sink: WriteSink = _select_sink(ctx)
    result: WriteResult = sink.write(ctx=ctx)

    # If we actually wrote, preserve INSERTED/REPLACED/REMOVED from updater.
    if result.status == WriteStatus.WRITTEN:
        if ctx.status.write not in {
            WriteStatus.INSERTED,
            WriteStatus.REPLACED,
            WriteStatus.REMOVED,
        }:
            ctx.status.write = WriteStatus.WRITTEN
    else:
        ctx.status.write = result.status

    return ctx
