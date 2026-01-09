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
`ctx.views.updated` and selected the intended `WriteStatus` (INSERTED, REPLACED, REMOVED).
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

import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from topmark.config.logging import get_logger
from topmark.config.types import FileWriteStrategy, OutputTarget
from topmark.pipeline.context.policy import can_change, check_permitted_by_policy
from topmark.pipeline.hints import Axis, Cluster, KnownCode
from topmark.pipeline.status import (
    PlanStatus,
    WriteStatus,
)
from topmark.pipeline.steps.base import BaseStep
from topmark.pipeline.views import UpdatedView

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.logging import TopmarkLogger
    from topmark.config.policy import Policy
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.views import UpdatedView


logger: TopmarkLogger = get_logger(__name__)


# --- DRY helpers for writer sinks ---
def _updated_lines(ctx: ProcessingContext) -> list[str] | None:
    """Materialize updated lines or return None if unavailable.

    Args:
        ctx (ProcessingContext): Processing context.

    Returns:
        list[str] | None: Updated lines as a list, or None if no updated image exists.
    """
    uv: UpdatedView | None = ctx.views.updated
    if not uv or uv.lines is None:
        return None
    return ctx.materialize_updated_lines()


def _normalize_eof(text: str, ctx: ProcessingContext) -> str:
    """Normalize end-of-file newline according to the original file policy.

    If the original file did not end with a newline, remove a trailing newline
    from ``text`` using the detected newline style.
    """
    nl: str = ctx.newline_style or "\n"
    if ctx.ends_with_newline is False and text.endswith(nl):
        return text[: -len(nl)]
    return text


class WriteSink(Protocol):
    """Protocol for write sinks used by the writer step.

    Implementations receive a ProcessingContext and return a WriteResult.
    """

    def write(self, *, ctx: ProcessingContext) -> WriteResult:
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

    def write(self, *, ctx: ProcessingContext) -> WriteResult:
        """No-op write for dry-run mode.

        Args:
            ctx (ProcessingContext): Processing context for the current file.

        Returns:
            WriteResult: The input ``ctx.status.write`` echoed back with zero bytes written.
        """
        return WriteResult(status=ctx.status.write, bytes_written=0)


class StdoutSink:
    """Standard-output sink (stdin-content mode)."""

    def write(self, *, ctx: ProcessingContext) -> WriteResult:
        """Emit updated content to standard output.

        This sink is used when the CLI/API is configured to read a single file's
        content from STDIN and emit the updated result to STDOUT.

        Args:
            ctx (ProcessingContext): Processing context containing the updated lines.

        Returns:
            WriteResult: ``WRITTEN`` with the number of UTF-8 bytes printed when
            content is available; otherwise ``SKIPPED`` with zero bytes written.
        """
        lines: list[str] | None = _updated_lines(ctx)
        if lines is None:
            logger.debug(
                "StdoutSink: ctx.views.updated not defined or ctx.views.updated.lines not defined: "
                "nothing to do"
            )
            return WriteResult(status=WriteStatus.SKIPPED, bytes_written=0)

        text: str = "".join(lines)
        size: int = len(text.encode("utf-8"))
        print(text, end="")  # noqa: T201 (intentional: pipeline handles stdout here)
        return WriteResult(status=WriteStatus.WRITTEN, bytes_written=size)


class FileSystemSink:
    """Filesystem sink that writes in-place to ``ctx.path``."""

    def write(self, *, ctx: ProcessingContext) -> WriteResult:
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
        lines: list[str] | None = _updated_lines(ctx)
        if lines is None:
            logger.debug(
                "FileSystemSink: ctx.views.updated not defined or ctx.views.updated.lines "
                "not defined: nothing to do"
            )
            return WriteResult(status=WriteStatus.SKIPPED, bytes_written=0)

        text: str = "".join(lines)

        # Respect original EOF newline policy
        text = _normalize_eof(text, ctx)

        try:
            with open(ctx.path, "w", encoding="utf-8", newline="") as f:
                f.write(text)

            bytes_written: int = len(text.encode("utf-8"))
            logger.debug("FileSystemSink: wrote %d bytes to file %s", bytes_written, ctx.path)
            return WriteResult(status=WriteStatus.WRITTEN, bytes_written=bytes_written)

        except UnicodeEncodeError as e:
            # Log that the text contains characters that can't be saved with the chosen encoding
            logger.error("Failed to write file due to encoding issue in content: %s", e)
            # Consider returning an appropriate status or re-raising a custom exception
            return WriteResult(status=WriteStatus.FAILED)

        except OSError as e:
            # Catches FileNotFoundError, PermissionError, IsADirectoryError, etc.
            logger.error("Failed to write file %s due to file system error: %s", ctx.path, e)
            return WriteResult(status=WriteStatus.FAILED)


class InplaceFileSink(WriteSink):
    """Write updated content by truncating the original file and writing in place.

    Pros:
        - Keeps inode identity stable.
        - Minimal I/O.
    Cons:
        - Risk of partial/truncated files on crash.
        - Live readers may observe mid-write changes.
    """

    def write(self, *, ctx: ProcessingContext) -> WriteResult:
        """Write updated content directly into the original file (in-place).

        Opens the file in binary write mode, truncates its contents, and writes
        `ctx.views.updated.lines` directly. This operation preserves the inode identity
        but may leave a truncated file if the process is interrupted mid-write.

        Args:
            ctx (ProcessingContext): The active processing context, expected to
                contain `ctx.views.updated.lines` with UTF-8-encoded text to write.

        Returns:
            WriteResult: Result containing `WriteStatus.WRITTEN` on success,
            or `WriteStatus.FAILED` with diagnostic info on error.
        """
        path: Path = ctx.path
        try:
            # Preserve mode; other metadata handled best-effort.
            try:
                st: os.stat_result | None = os.stat(path)
                mode: int | None = stat.S_IMODE(st.st_mode) if st else None
            except Exception:
                st = None
                mode = None

            with open(path, "wb") as f:
                # Prefer streaming via the iterator (good for memory)
                for line in ctx.iter_updated_lines():
                    f.write(line.encode("utf-8"))
                f.flush()
                os.fsync(f.fileno())
            if mode is not None:
                try:
                    os.chmod(path, mode)
                except Exception:
                    pass
            return WriteResult(status=WriteStatus.WRITTEN)
        except Exception as e:
            ctx.error(f"In-place write failed: {e}")
            return WriteResult(status=WriteStatus.FAILED)


class AtomicFileSink(WriteSink):
    """Write updated content to a temp file and atomically replace the target.

    This sink writes to a temporary file in the **same directory** as the
    target, `fsync()`s it, then calls `os.replace()` to atomically swap it in.

    Pros:
        - Atomic visibility; crash-safe (old file remains until replace).
    Cons:
        - New inode/ID on POSIX; slightly more I/O.
    """

    def write(self, *, ctx: ProcessingContext) -> WriteResult:
        """Atomically replace the target file by writing to a temp file first.

        Writes `ctx.views.updated.lines` to a temporary file in the same directory,
        calls `os.fsync()` to ensure durability, and performs `os.replace()` to
        atomically swap it in place. The operation guarantees that readers will
        either see the old file or the complete new file, never a partial write.

        Args:
            ctx (ProcessingContext): The active processing context, expected to
                contain `ctx.views.updated.lines` with UTF-8-encoded text to write.

        Returns:
            WriteResult: Result with `WriteStatus.WRITTEN` on success,
            or `WriteStatus.FAILED` if the operation fails.
        """
        path: Path = ctx.path
        dirpath: Path = path.parent
        # Generate a hidden, per-process, per-file temp name.
        tmp: Path = dirpath / f".{path.name}.topmark.tmp-{os.getpid()}-{secrets.token_hex(4)}"
        try:
            # Read original metadata for later re-apply (best-effort)
            try:
                st: os.stat_result | None = os.stat(path)
                mode: int | None = stat.S_IMODE(st.st_mode) if st else None
            except Exception:
                st = None
                mode = None

            with open(tmp, "wb") as f:
                # Apply permissions early to reduce race windows.
                if mode is not None:
                    try:
                        os.fchmod(f.fileno(), mode)
                    except Exception:
                        try:
                            os.chmod(tmp, mode)
                        except Exception:
                            pass
                # Prefer streaming via the iterator (good for memory)
                for line in ctx.iter_updated_lines():
                    f.write(line.encode("utf-8"))
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp, path)

            # Try to fsync the directory for durability (POSIX only)
            try:
                dir_fd: int = os.open(str(dirpath), os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except Exception:
                pass

            return WriteResult(status=WriteStatus.WRITTEN)
        except Exception as e:
            # Best-effort cleanup of the temp file
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
            ctx.error(f"Atomic write failed: {e}")
            return WriteResult(status=WriteStatus.FAILED)


def _select_sink(ctx: ProcessingContext) -> WriteSink:
    """Pick the appropriate sink for this write operation.

    Selection rules:
      * If `ctx.config.output_target == OutputTarget.STDOUT` **or** `ctx.config.stdin` →
        `StdoutSink` (emit updated content to standard output). This path ignores
        `apply_changes` because it does not mutate the filesystem.
      * Else (target is file):
          - If `ctx.config.apply_changes` is falsy → `NullSink` (preview/no‑write).
          - Otherwise select the file sink by strategy:
              · `FileWriteStrategy.IN_PLACE`  → `InplaceFileSink`
              · `FileWriteStrategy.ATOMIC`    → `AtomicFileSink` (default)

    Notes:
      * The *destination* (stdout vs file) is orthogonal to the *write strategy*.
      * `apply_changes` only matters for file targets; it is ignored for stdout.
    """
    # Destination: stdout takes precedence and ignores apply_changes.
    if ctx.config.output_target == OutputTarget.STDOUT or ctx.config.stdin is True:
        logger.info("--> Writer selected StdoutSink")
        return StdoutSink()

    # Destination: file. Respect preview mode (no on-disk mutation).
    if not ctx.config.apply_changes:
        logger.debug("Selected NULL sink (apply_changes=False, file target)")
        return NullSink()

    # Apply to file using the configured strategy (default: atomic).
    if ctx.config.file_write_strategy == FileWriteStrategy.IN_PLACE:
        # In-place writer (faster)
        logger.info("--> Writer selected InplaceFileSink")
        return InplaceFileSink()
    # Default (True, None): atomic writer (safer)
    logger.info("--> Writer selected AtomicFileSink (default)")
    return AtomicFileSink()


class WriterStep(BaseStep):
    """Commit updated content to a sink (filesystem/stdout/null).

    Applies policy gates and the intended write action (insert/replace/remove)
    to produce a final write result. Performs the only I/O in the pipeline.

    Axes written:
      - write

    Sets:
      - WriteStatus: {PENDING, WRITTEN, SKIPPED, FAILED}
    """

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.WRITE,
            axes_written=(Axis.WRITE,),
        )

    def may_proceed(self, ctx: ProcessingContext) -> bool:
        """Return True if the writer is allowed to commit changes.

        The writer should only run when:
          * The pipeline has not requested an early halt (``ctx.flow.halt`` is False);
          * The caller explicitly enabled applying changes (``config.apply_changes`` is True);
          * The updater selected a concrete write action (``INSERTED``/``REPLACED``/``REMOVED``);
          * We have an updated image to write and the engine deemed the change safe
            (``ctx.views.updated.lines`` is present and ``can_change(ctx) is True``).

        Policy and intent have already been enforced by the updater. Re-checking
        header/comparison/strip intent here can drift from the authoritative
        ``UpdateStatus`` and cause double-gating, so we avoid it.

        Args:
            ctx (ProcessingContext): The processing context for the current file.

        Returns:
            bool: True if processing can proceed to the build step, False otherwise.
        """
        if ctx.is_halted:
            return False
        if not ctx.config.apply_changes:
            return False

        # Only execute when updater produced a concrete write operation.
        if ctx.status.plan not in {
            PlanStatus.INSERTED,
            PlanStatus.REPLACED,
            PlanStatus.REMOVED,
        }:
            return False

        # Require an updated image and an affirmative feasibility guard.
        updated_view: UpdatedView | None = ctx.views.updated
        if updated_view is None or updated_view.lines is None:
            return False

        return can_change(ctx) is True

    def run(self, ctx: ProcessingContext) -> None:
        """Writer step: commit updates to the selected sink.

        This step executes only when `may_proceed_to_writer` returns ``True``.
        Otherwise it converts a preview status to a non-mutating terminal status.

        Args:
            ctx (ProcessingContext): The processing context with update intent.

        Mutations:
            ProcessingContext: The same context, with ``status.write`` finalized.
        """
        logger.debug("ctx: %s", ctx)

        if ctx.status.plan == PlanStatus.PREVIEWED:
            ctx.status.write = WriteStatus.SKIPPED
            return

        # --- Policy enforcement (centralized + FileType-specific (optional) -----
        pol: Policy = ctx.get_effective_policy()

        # Only gate insert/replace (check mode) — strip/removal is not governed by add/update.
        if ctx.status.plan == PlanStatus.INSERTED and pol.update_only:
            ctx.status.write = WriteStatus.SKIPPED
            ctx.info("Skipped by policy: --update-only")
            logger.debug("Skipped by policy: --update-only")
            return

        if ctx.status.plan == PlanStatus.REPLACED and pol.add_only:
            ctx.status.write = WriteStatus.SKIPPED
            ctx.info("Skipped by policy: --add-only")
            logger.debug("Skipped by policy: --add-only")
            return

        # Defensive: nothing to write if updater did not produce an updated image
        updated_view: UpdatedView | None = ctx.views.updated
        if updated_view is None or updated_view.lines is None:
            ctx.info("File unchanged - nothing to write.")
            logger.debug("File unchanged - nothing to write")
            return

        logger.debug(
            "writer gate: resolve=%s can_change=%s header=%s comparison=%s strip=%s policy=%s",
            ctx.status.resolve,
            can_change(ctx),
            ctx.status.header,
            ctx.status.comparison,
            ctx.status.strip,
            check_permitted_by_policy(ctx),
        )
        logger.debug("ProcessingContext before writing: %s", ctx.to_dict())
        sink: WriteSink = _select_sink(ctx)
        result: WriteResult = sink.write(ctx=ctx)

        # Update write status:
        ctx.status.write = result.status
        return

    def hint(self, ctx: ProcessingContext) -> None:
        """Attach write hints (non-binding).

        Args:
            ctx (ProcessingContext): The processing context.
        """
        st: WriteStatus = ctx.status.write
        # May proceed to next step (always):
        if st == WriteStatus.WRITTEN:
            ctx.hint(
                axis=Axis.WRITE,
                code=KnownCode.WRITE_WRITTEN,
                cluster=Cluster.CHANGED,
                message="changes written",
            )
        elif st == WriteStatus.SKIPPED:
            if ctx.status.plan in {PlanStatus.INSERTED, PlanStatus.REPLACED}:
                msg: str = "write skipped (policy)"
            else:
                msg = "write skipped"
            ctx.hint(
                axis=Axis.WRITE,
                code=KnownCode.WRITE_SKIPPED,
                cluster=Cluster.SKIPPED,
                message=msg,
            )
        # Stop processing:
        elif st == WriteStatus.FAILED:
            ctx.hint(
                axis=Axis.WRITE,
                code=KnownCode.WRITE_FAILED,
                cluster=Cluster.ERROR,
                message="write failed",
                terminal=True,
            )
        elif st == WriteStatus.PENDING:
            # writer did not complete
            ctx.request_halt(reason=f"{self.__class__.__name__} did not set state.", at_step=self)
